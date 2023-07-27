#!/usr/bin/env python3

"""
CHARACTER/WORD LOOKUP FUNCTIONS

Ziwen uses the regular code-formatting in Markdown (`) as a syntax to define words for it to look up. 
The most supported searches are for Japanese and Chinese as they account for nearly 50% of posts on r/translator. 
There is also a dedicated search function for Korean and a Wiktionary search for every other language.

For Chinese and Japanese, the main functions are `xx_character` and `xx_word`, where xx is the language code (ZH or JA).

Specific language lookup functions are prefixed by the function whose data they return to. (e.g. `zh_word`)
More general ones are prefixed by `lookup`.
"""

import re
from typing import Dict
import requests
from lxml import html
import romkan  # Needed for automatic Japanese romaji conversion.
from _config import logger
from zh_processing import zh_character_calligraphy_search


def ja_character(character, zw_useragent: Dict[str, str]):
    """
    This function looks up a Japanese kanji's pronunciations and meanings

    :param character: A kanji or single hiragana. This function will not work with individual katakana.
    :return to_post: A formatted string with
    """

    is_kana = False
    multi_mode = False
    multi_character_dict = {}  # Dictionary to store the info we get.
    total_data = ""
    kana_test = re.search(
        "[\u3040-\u309f]", character
    )  # Check to see if it's hiragana. Will return none if kanji.

    multi_character_list = list(character)

    if len(multi_character_list) > 1:
        multi_mode = True

    if kana_test is not None:
        kana = kana_test.group(0)
        eth_page = requests.get(
            f"http://jisho.org/search/{character}%20%23particle",
            headers=zw_useragent,
        )
        tree = html.fromstring(eth_page.content)  # now contains the whole HTML page
        meaning = tree.xpath('//span[contains(@class,"meaning-meaning")]/text()')
        meaning = " / ".join(meaning)
        is_kana = True
        total_data = "# [{0}](https://en.wiktionary.org/wiki/{0}#Japanese)".format(kana)
        total_data += f" (*{romkan.to_hepburn(kana)}*)"
        total_data += f'\n\n**Meanings**: "{meaning}."'
    else:
        if not multi_mode:
            # Regular old-school one character search.
            eth_page = requests.get(
                "http://jisho.org/search/" + character + "%20%23kanji",
                headers=zw_useragent,
            )
            tree = html.fromstring(eth_page.content)  # now contains the whole HTML page
            kun_reading = tree.xpath('//dl[contains(@class,"kun_yomi")]/dd/a/text()')
            meaning = tree.xpath(
                '//div[contains(@class,"kanji-details__main-meanings")]/text()'
            )
            meaning = "/ ".join(meaning)
            meaning = meaning.strip()
            if (
                len(meaning) == 0
            ):  # Check to not return anything if the entry is invalid
                to_post = (
                    "There were no results for {}. Please check to make sure it is a valid Japanese "
                    "character or word.".format(character)
                )
                logger.info(f"[ZW] JA-Character: No results for {character}")
                return to_post
            if len(kun_reading) == 0:
                on_reading = tree.xpath(
                    '//*[@id="result_area"]/div/div[1]/div[2]/div/div[1]/div[2]/dl/dd/a/text()'
                )
            else:
                on_reading = tree.xpath(
                    '//div[contains(@class,"kanji-details__main-readings")]/dl[2]/dd/a/text()'
                )
            kun_chunk = ""
            for reading in kun_reading:
                kun_chunk_new = reading + " (*" + romkan.to_hepburn(reading) + "*)"
                kun_chunk = kun_chunk + ", " + kun_chunk_new
            on_chunk = ""
            for reading in on_reading:
                on_chunk_new = reading + " (*" + romkan.to_hepburn(reading) + "*)"
                on_chunk = on_chunk + ", " + on_chunk_new
            lookup_line_1 = (
                "# [{0}](https://en.wiktionary.org/wiki/{0}#Japanese)\n\n".format(
                    character
                )
            )
            lookup_line_1 += (
                "**Kun-readings:** "
                + kun_chunk[2:]
                + "\n\n**On-readings:** "
                + on_chunk[2:]
            )

            # Try to get a Chinese calligraphic image
            calligraphy_image = zh_character_calligraphy_search(character)
            if calligraphy_image is not None:
                lookup_line_1 += calligraphy_image
            total_data = lookup_line_1 + f'\n\n**Meanings**: "{meaning}."'

        elif multi_mode:
            # MULTIPLE Start iterating over the characters we have
            ooi_key = f"# {character}"
            ooi_header = "\n\nCharacter "
            ooi_separator = "\n---|"
            ooi_kun = "\n**Kun-readings**"
            ooi_on = "\n**On-readings** "
            ooi_meaning = "\n**Meanings** "

            for moji in multi_character_list:
                multi_character_dict[moji] = {}  # Create a new null dictionary

                eth_page = requests.get(
                    "http://jisho.org/search/" + moji + "%20%23kanji",
                    headers=zw_useragent,
                )
                # now contains the whole HTML page
                tree = html.fromstring(eth_page.content)

                # Get the readings of the characters
                kun_reading = tree.xpath(
                    '//dl[contains(@class,"kun_yomi")]/dd/a/text()'
                )
                if len(kun_reading) == 0:
                    on_reading = tree.xpath(
                        '//*[@id="result_area"]/div/div[1]/div[2]/div/div[1]/div[2]/dl/dd/a/text()'
                    )
                else:
                    on_reading = tree.xpath(
                        '//div[contains(@class,"kanji-details__main-readings")]/dl[2]/dd/a/text()'
                    )

                # Process and format the kun readings
                kun_chunk = []
                for reading in kun_reading:
                    kun_chunk_new = reading + " (*" + romkan.to_hepburn(reading) + "*)"
                    kun_chunk.append(kun_chunk_new)
                kun_chunk = ", ".join(kun_chunk)
                multi_character_dict[moji]["kun"] = kun_chunk

                # Process and format the on readings
                on_chunk = []
                for reading in on_reading:
                    on_chunk_new = reading + " (*" + romkan.to_hepburn(reading) + "*)"
                    on_chunk.append(on_chunk_new)
                on_chunk = ", ".join(on_chunk)
                multi_character_dict[moji]["on"] = on_chunk

                meaning = tree.xpath(
                    '//div[contains(@class,"kanji-details__main-meanings")]/text()'
                )
                meaning = "/ ".join(meaning)
                meaning = '"' + meaning.strip() + '."'
                multi_character_dict[moji]["meaning"] = meaning

            # Now let's construct our table based on the data we have.
            for key in multi_character_list:
                character_data = multi_character_dict[key]
                ooi_header += (
                    " | [{0}](https://en.wiktionary.org/wiki/{0}#Japanese)".format(key)
                )
                ooi_separator += "---|"
                ooi_kun += f" | {character_data['kun']}"
                ooi_on += f" | {character_data['on']}"
                ooi_meaning += f" | {character_data['meaning']}"

            # Combine the data together.
            total_data = (
                ooi_key + ooi_header + ooi_separator + ooi_kun + ooi_on + ooi_meaning
            )

    if not is_kana:
        ja_to_post = "\n\n^Information ^from [^(Jisho)](https://jisho.org/search/{0}%20%23kanji) ^| "
        ja_to_post += (
            "[^(Goo Dictionary)](https://dictionary.goo.ne.jp/word/en/{0}) ^| "
        )
        ja_to_post += "[^(Tangorin)](https://tangorin.com/kanji/{0}) ^| [^(Weblio EJJE)](https://ejje.weblio.jp/content/{0})"
        ja_to_post = ja_to_post.format(character)
        lookup_line_3 = ja_to_post
    else:
        ja_to_post = "\n\n^Information ^from [^(Jisho)](https://jisho.org/search/{0}%20%23particle) ^| "
        ja_to_post += "[^(Tangorin)](https://tangorin.com/general/{0}%20particle) ^| "
        ja_to_post += "[^(Weblio EJJE)](https://ejje.weblio.jp/content/{0})"
        ja_to_post = ja_to_post.format(character)
        lookup_line_3 = ja_to_post

    to_post = total_data + lookup_line_3
    logger.info(
        "[ZW] JA-Character: Received lookup command for "
        + character
        + " in Japanese. Returned results."
    )

    return to_post


def ja_word_sfx(katakana_string: str, zw_useragent: Dict[str, str]) -> None | str:
    """
    A function that consults the SFX Dictionary to provide explanations for katakana sound effects, often found in manga
    For more information, visit: http://thejadednetwork.com/sfx

    :param katakana_string: Any string of katakana. The function will exit with None if it detects non-katakana.
    :return: None if no results, a formatted string otherwise.
    """

    actual_link = None

    # Check to make sure everything is katakana.
    katakana_test = re.search("[\u30A0-\u30FF]", katakana_string)

    if katakana_test is None:
        return None

    # Format the search URL.
    search_url = f"http://thejadednetwork.com/sfx/search/?keyword=+{katakana_string}&submitSearch=Search+SFX&x="

    # Conduct a search.
    eth_page = requests.get(search_url, headers=zw_useragent)
    tree = html.fromstring(eth_page.content)  # now contains the whole HTML page
    list_of_links = tree.xpath("//td/a/@href")

    # Here we look for the actual dictionary entry.
    for link in list_of_links:
        if "sfx/browse/" in link:
            actual_link = link
            break

    if actual_link is not None:  # We have a real dictionary entry.
        # Access the new page.
        new_page = requests.get(actual_link)
        new_tree = html.fromstring(new_page.content)

        # Gather data.
        sound_data = new_tree.xpath('//table[contains(@class,"definitions")]//text()')
        # Take away the blanks.
        sound_data = [x for x in sound_data if len(x.strip()) > 0]

        # Double-check the entry to make sure it's right.
        katakana_entry = sound_data[4].strip().replace(",", "")
        if katakana_entry != katakana_string:
            return None

        # Parse data, assign variables.
        katakana_reading = f"{katakana_string} (*{romkan.to_hepburn(katakana_string)}*)"
        sound_effect = sound_data[7].replace("*", r"\*")
        sound_explanation = sound_data[8].strip().replace("*", r"\*")

        # Create the formatted comment.
        formatted_line = f"\n\n**English Equivalent**: {sound_effect}\n\n**Explanation**: {sound_explanation} "
        formatted_line += f"\n\n\n^Information ^from [^SFX ^Dictionary]({actual_link})"
        finished_comment = f"# [{katakana_string}](https://en.wiktionary.org/wiki/{katakana_string}#Japanese)\n\n##### *Sound effect*\n\n**Reading:** {katakana_reading}{formatted_line}"

        logger.info(
            f"[ZW] JA-Word-SFX: Found a dictionary entry for {katakana_string} at {actual_link}"
        )

        return finished_comment


def ja_word_given_name_search(
    ja_given_name: str, zw_useragent: Dict[str, str]
) -> str | None:
    """
    A function to get the kanji readings of Japanese given names, which may not necessarily be in dictionaries.
    This also returns readings of place names, such as temples.

    :param ja_given_name: A Japanese given name, in kanji *only*.
    :return formatted_section: A chunk of text with readings and meanings of the character.
    """

    names_w_readings = []

    # Conduct a search.
    web_search = f"http://kanji.reader.bz/{ja_given_name}"
    eth_page = requests.get(web_search, headers=zw_useragent)
    tree = html.fromstring(eth_page.content)  # now contains the whole HTML page
    name_content = tree.xpath('//div[contains(@id,"main")]/p[1]/text()')
    hiragana_content = tree.xpath('//div[contains(@id,"main")]/p[1]/a/text()')

    # Check for validity.
    if "見つかりませんでした" in str(name_content):  # Could not be found
        return None

    # Format the romaji properly.
    name_content = [x for x in name_content if x != "\xa0\xa0"]
    if name_content:
        name_content = name_content[0].split()
        print(name_content)

    # Create the readings list.
    for name in hiragana_content:
        name_content_lookup = name_content[hiragana_content.index(name)].title()
        names_w_readings.append(f"{name.strip()} (*{name_content_lookup}*)")
    name_formatted_readings = ", ".join(names_w_readings)

    # Create the comment
    formatted_section = (
        "# [{0}](https://en.wiktionary.org/wiki/{0}#Japanese)\n\n"
        "**Readings:** {1}\n\n**Meanings**: A Japanese name."
        "\n\n\n^(Information from) [^(Jinmei Kanji Jisho)](https://kanji.reader.bz/{0}) "
        "^| [^(Weblio EJJE)](https://ejje.weblio.jp/content/{0})"
    )
    formatted_section = formatted_section.format(ja_given_name, name_formatted_readings)

    return formatted_section


def ja_word_surname(name: str, zw_useragent: Dict[str, str]) -> None | str:
    """
    Function to get a Japanese surname (backup if a word search fails).

    :param name: Any Japanese surname (usually two kanji long).
    :return None: if no results, otherwise return a formatted string.
    """

    eth_page = requests.get(
        "https://myoji-yurai.net/searchResult.htm?myojiKanji=" + name,
        headers=zw_useragent,
    )
    tree = html.fromstring(eth_page.content)  # now contains the whole HTML page
    ja_reading = tree.xpath('//div[contains(@class,"post")]/p/text()')
    ja_reading = str(ja_reading[0])[4:].split(",")
    if len(str(ja_reading)) <= 4 or len(name) < 2:
        # This indicates that it's blank. No results.
        return None
    furigana_chunk = ""
    for reading in ja_reading:
        furigana_chunk_new = (
            reading.strip() + " (*" + romkan.to_hepburn(reading).title() + "*)"
        )
        furigana_chunk += f", {furigana_chunk_new}"
    lookup_line_1 = "# [{0}](https://en.wiktionary.org/wiki/{0}#Japanese)\n\n".format(
        name
    )
    # We return the formatted readings of this name
    lookup_line_1 += f"**Readings:** {furigana_chunk[2:]}"
    lookup_line_2 = "\n\n**Meanings**: A Japanese surname."
    lookup_line_3 = "\n\n\n^Information ^from [^Myoji](https://myoji-yurai.net/searchResult.htm?myojiKanji={0}) "
    lookup_line_3 += "^| [^Weblio ^EJJE](https://ejje.weblio.jp/content/{0})"
    lookup_line_3 = lookup_line_3.format(name)
    to_post = lookup_line_1 + lookup_line_2 + "\n" + lookup_line_3
    logger.info(f"[ZW] JA-Name: '{name}' is a Japanese name. Returned search results.")
    return to_post


def ja_word(japanese_word: str, zw_useragent: Dict[str, str]):
    """
    A newer function that uses Jisho's unlisted API in order to return data from Jisho.org for Japanese words.
    See here for more information: https://jisho.org/forum/54fefc1f6e73340b1f160000-is-there-any-kind-of-search-api
    Keep in mind that the API is in many ways more limited than the actual search stack (e.g. no kanji results)

    :param japanese_word: Any word that is expected to be Japanese and longer than a single character.
    :return: A formatted string for use in a comment reply.
    """

    y_data = None

    # Fetch data from the API
    link_json = (
        f"https://jisho.org/api/v1/search/words?keyword={japanese_word}%20%23words"
    )
    returned_data = requests.get(link_json)
    word_data = returned_data.json()
    main_data = word_data["data"]

    # Attempt to get the reading of it in hiragana. If there is an Key Error, then it's not a real Jisho entry.
    try:
        main_data = main_data[0]  # Choose the first result.
        word_reading = main_data["japanese"][0]["reading"]
    except (KeyError, IndexError):
        word_reading = ""

    if len(word_reading) == 0:  # It appears that this word doesn't exist on Jisho.
        logger.info(
            f"[ZW] JA-Word: No results found for a Japanese word '{japanese_word}'."
        )

        # Check if katakana. Will return none if kanji.
        katakana_test = re.search("[\u30a0-\u30ff]", japanese_word)
        # Check to see if it's a surname.
        surname_data = ja_word_surname(japanese_word, zw_useragent)
        sfx_data = ja_word_sfx(japanese_word, zw_useragent)
        given_name_data = ja_word_given_name_search(japanese_word, zw_useragent)

        # Test against the other dictionary modules.
        if surname_data is not None:
            logger.info("[ZW] JA-Word: Found a matching Japanese surname.")
            return surname_data
        if given_name_data is not None:
            logger.info("[ZW] JA-Word: Found a matching Japanese given name.")
            return given_name_data
        if sfx_data is not None:
            logger.info("[ZW] JA-Word: Found matching Japanese sound effects.")
            return sfx_data
        if katakana_test is None:  # It's a character
            to_post = ja_character(japanese_word, zw_useragent)
            logger.info(
                "[ZW] JA-Word: No results found for a Japanese name. Getting individual character data."
            )
        else:
            to_post = f"There were no results for `{japanese_word}`."
            logger.info("[ZW] JA-Word: Unknown katakana word. No results.")
        return to_post

    # Jisho data is good, format the data from the returned JSON.
    word_reading_chunk = f"{word_reading} (*{romkan.to_hepburn(word_reading)}*)"
    word_meaning = main_data["senses"][0]["english_definitions"]
    word_meaning = f'"{", ".join(word_meaning)}."'
    word_type = main_data["senses"][0]["parts_of_speech"]
    word_type = f"*{', '.join(word_type)}*"

    # Construct the comment structure with the data.
    return_comment = (
        "# [{0}](https://en.wiktionary.org/wiki/{0}#Japanese)\n\n"
        "##### {3}\n\n**Reading:** {1}\n\n**Meanings**: {2}"
    )
    return_comment = return_comment.format(
        japanese_word, word_reading_chunk, word_meaning, word_type
    )

    # Check if it's a yojijukugo.
    if len(japanese_word) == 4:
        y_data = ja_word_yojijukugo(japanese_word, zw_useragent)
        if y_data is not None:  # If there's data, append it.
            logger.debug("[ZW] JA-Word: Yojijukugo data retrieved.")
            return_comment += y_data

    # Add the footer
    footer = (
        "\n\n^Information ^from ^[Jisho](https://jisho.org/search/{0}%23words) ^| "
        "[^Kotobank](https://kotobank.jp/word/{0}) ^| "
        "[^Tangorin](https://tangorin.com/general/{0}) ^| "
        "[^(Weblio EJJE)](https://ejje.weblio.jp/content/{0})"
    )
    if y_data is not None:  # Add attribution for yojijukugo
        footer += (
            " ^| [^Yoji ^Jitenon](https://yoji.jitenon.jp/cat/search.php?getdata={0})"
        )
    return_comment += footer.format(japanese_word)
    logger.info(
        f"[ZW] JA-Word: Received a lookup command for the word '{japanese_word}' in Japanese."
    )

    return return_comment


def ja_word_yojijukugo(yojijukugo, zw_useragent: Dict[str, str]):
    """
    A newer rewrite of the yojijukugo function that has been changed to match the zh_word_chengyu function.
    That is, now its role is to grab a Japanese meaning and explanation in order to give some insight.
    For examples, see https://www.edrdg.org/projects/yojijukugo.html

    :param yojijukugo: Any four-kanji Japanese idiom.
    :return: A formatted string for addition to ja_word or None if nothing is found.
    """

    # Fetch the page and its data.
    url_search = f"https://yoji.jitenon.jp/cat/search.php?getdata={yojijukugo}&search=part&page=1"
    eth_page = requests.get(url_search, headers=zw_useragent)
    tree = html.fromstring(eth_page.content)  # now contains the whole HTML page
    url = tree.xpath('//th[contains(@scope,"row")]/a/@href')

    if len(url) != 0:  # There's data. Get the url.
        url_entry = url[0]  # Get the actual url of the entry.
        entry_page = requests.get(url_entry, headers=zw_useragent)
        # now contains the whole HTML page
        entry_tree = html.fromstring(entry_page.content)

        # Check to make sure the data is the same.
        entry_title = entry_tree.xpath("//h1/text()")[0]
        # Retrieve only the main title of the page.
        entry_title = entry_title.split("」", 1)[0][1:]
        if entry_title != yojijukugo:  # If the data doesn't match
            logger.debug("[ZW] JA-Chengyu: The titles don't match.")
            return None

        # Format the data properly.
        row_data = [td.text_content() for td in entry_tree.xpath("//td")]
        logger.info(
            f"[ZW] JA-Chengyu: Retrieved information on {yojijukugo} from {url_entry}."
        )

        # Add the literary info.
        y_meaning = row_data[1].strip()
        y_source = row_data[2].strip()
        return f"\n\n**Japanese Explanation**: {y_meaning}\n\n**Literary Source**: {y_source}"
