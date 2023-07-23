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


# Chinese Lookup Functions
import csv
import random
import re
import time
import bs4
from _config import (
    logger,
    FILE_ADDRESS_OLD_CHINESE,
    FILE_ADDRESS_ZH_BUDDHIST,
    FILE_ADDRESS_ZH_CCCANTO,
    FILE_ADDRESS_ZH_ROMANIZATION,
)
import requests
from lxml import html
from mafan import simplify, tradify
from korean_romanizer.romanizer import Romanizer


def zh_character_oc_search(character):
    """
    A simple routine that retrieves data from a CSV of Baxter-Sagart's reconstruction of Middle and Old Chinese.
    For more information, visit: http://ocbaxtersagart.lsait.lsa.umich.edu/

    :param character: A single Chinese character.
    :return: A formatted string with the Middle and Old Chinese readings if found, None otherwise.
    """

    # Main dictionary for readings
    mc_oc_readings = {}

    # Iterate over the CSV
    csv_file = csv.reader(
        open(FILE_ADDRESS_OLD_CHINESE, encoding="utf-8"), delimiter=","
    )
    for row in csv_file:
        my_character = row[0]
        # It is normally returned as a list, so we need to convert into a string.
        mc_reading = row[2:][0]
        oc_reading = row[4:][0]
        if "(" in oc_reading:
            oc_reading = oc_reading.split("(", 1)[0]

        # Add the character as a key with the readings as a tuple
        mc_oc_readings[my_character] = (mc_reading.strip(), oc_reading.strip())

    # Check to see if I actually have the key in my dictionary.
    if character not in mc_oc_readings:  # Character not found.
        return None
    else:  # Character exists!
        character_data = mc_oc_readings[character]  # Get the tuple
        return f"\n**Middle Chinese** | \\**{character_data[0]}*\n**Old Chinese** | \\*{character_data[1]}*"


def zh_character_variant_search(searchTerm, retries=3):
    """
    Function to search the MOE dictionary for a link to character
    variants, and returns the link if found. None if nothing is found.
    """

    searchTerm = searchTerm.strip()
    entry_url = None
    timeout_amount = 4

    session = requests.Session()
    baseURL = "https://dict.variants.moe.edu.tw/variants/rbt"
    try:
        initialResp = session.get(
            f"{baseURL}/query_by_standard_tiles.rbt",
            timeout=0.5,
        )
    except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError):
        logger.info("Issue with gathering session for variant search.")
        return

    try:
        rci = re.search("componentId=(rci_.*_4)", initialResp.text).group(1)
        cookies = session.cookies.get_dict()  # sets JSESSIONID
    except AttributeError:
        return

    searchParams = {
        "rbtType": "AJAX_INVOKE",
        "componentId": rci,
    }

    data = {"searchedText": searchTerm}
    try:
        searchResponse = requests.post(
            f"{baseURL}/query_by_standard.rbt",
            params=searchParams,
            cookies=cookies,
            data=data,
            timeout=1,
        )
        fetchID = bs4(searchResponse.text, "lxml").findAll("a")[0].get("id")
    except (IndexError, requests.exceptions.ReadTimeout):
        return

    fetchParams = {"quote_code": fetchID}

    # Regular function iteration.
    for _ in range(retries):
        try:
            response = requests.get(
                f"{baseURL}/word_attribute.rbt",
                params=fetchParams,
                cookies=cookies,
                timeout=timeout_amount,
            )

            # Note that the full HTML of the page is response.text.
            entry_url = response.url
            if "quote_code" not in entry_url:
                entry_url = None

            return entry_url
        except (ConnectionError, requests.exceptions.ReadTimeout):
            logger.info("Timed out for variant search, trying again.")
            timeout_amount += 2

    return entry_url


def zh_character_min_hak(character, zw_useragent):
    """
    Function to get the Hokkien and Hakka (Sixian) pronunciations from the ROC Ministry of Education dictionary.
    This actually will accept either single-characters or multi-character words.
    For more information, visit: https://www.moedict.tw/

    :param character: A single Chinese character or word.
    :return: A string. If nothing is found the string will have zero length.
    """

    # Fetch Hokkien results
    min_page = requests.get(
        f"https://www.moedict.tw/'{character}", headers=zw_useragent
    )
    min_tree = html.fromstring(min_page.content)  # now contains the whole HTML page

    # The annotation returns as a list, we want to take the first one.
    try:
        min_reading = min_tree.xpath(
            '//ru[contains(@class,"rightangle") and contains(@order,"0")]/@annotation'
        )[0]
        min_reading = f"\n**Southern Min** | *{min_reading}*"
    except IndexError:  # No character or word found.
        min_reading = ""

    # Fetch Hakka results (Sixian)
    hak_page = requests.get(
        f"https://www.moedict.tw/:{character}", headers=zw_useragent
    )
    hak_tree = html.fromstring(hak_page.content)  # now contains the whole HTML page
    try:
        hak_reading = hak_tree.xpath(
            'string(//span[contains(@data-reactid,"$0.6.2.1")])'
        )

        if len(hak_reading) != 0:
            # Format the tones and words properly with superscript.
            # Wrap in parentheses for consistency
            hak_reading_new = []
            # Add spaces between words.
            hak_reading = re.sub(r"(\d{1,4})([a-z])", r"\1 ", hak_reading)
            hak_reading = hak_reading.split(" ")
            for word in hak_reading:
                new_word = re.sub(r"([a-z])(\d)", r"\1^(\2", word)
                new_word += ")"
                hak_reading_new.append(new_word)
            hak_reading = " ".join(hak_reading_new)

            hak_reading = f"\n**Hakka (Sixian)** | *{hak_reading}*"
    except IndexError:  # No character or word found.
        hak_reading = ""

    # Combine them together.
    return min_reading + hak_reading


def zh_character_calligraphy_search(character):
    """
    A function to get an overall image of Chinese calligraphic search containing different styles from various time
    periods.

    :param character: A single Chinese character.
    :return: None if no image found, a formatted string containing the relevant URLs and images otherwise.
    """

    character = simplify(character)

    # First get data from http://sfds.cn (this will be included as a URL)
    # Get the Unicode assignment (eg 738B)
    unicode_assignment = hex(ord(character)).upper()[2:]
    gx_url = f"http://www.sfds.cn/{unicode_assignment}/"

    # Secondly, get variant data from the MoE dictionary.
    variant_link = zh_character_variant_search(tradify(character))
    if variant_link:
        variant_formatted = f"[YTZZD]({variant_link})"
    else:
        variant_formatted = (
            "[YTZZD](https://dict.variants.moe.edu.tw/variants/rbt/"
            "query_by_standard_tiles.rbt?command=clear)"
        )

    # Next get an image from Shufazidian.
    formdata = {
        "sort": "7",
        "wd": character,
    }  # Form data to pass on to the POST system.
    try:
        rdata = requests.post("http://www.shufazidian.com/", data=formdata)
        tree = bs4(rdata.content, "lxml")
        tree = str(tree)
        tree = html.fromstring(tree)
    except requests.exceptions.ConnectionError:
        # If there's a connection error, return None.
        return None

    images = tree.xpath("//img/@src")
    complete_image = ""
    image_string = None

    if images is not None:
        for url in images:
            if len(url) < 20 or "gif" in url:  # We don't need short links or GIFs.
                continue

            if "shufa6" in url:
                # We try to get the broader summation image instead of the thumbnail.
                complete_image = url.replace("shufa6/1", "shufa6")

        if len(complete_image) != 0:
            logger.debug(
                f"[ZW] ZH-Calligraphy: There is a Chinese calligraphic image for {character}."
            )
            image_string = (
                f"\n\n**Chinese Calligraphy Variants**: [{character}]({complete_image}) (*[SFZD](http://www.shufazidian.com/)*, "
                f"*[SFDS]({gx_url})*, *{variant_formatted}*)"
            )
    else:
        image_string = None
    return image_string


def zh_character_other_readings(character, zw_useragent):
    """
    A function to get non-Chinese pronunciations of characters (Sino-Xenic readings) from the Chinese Character API.
    We use the Korean, Vietnamese, and Japanese readings.
    This information is attached to single-character lookups for Chinese and integrated into a table.
    For more information, visit: https://ccdb.hemiola.com/

    :param character: Any Chinese character.
    :return: None or a string of several table lines with the readings formatted in Markdown.
    """

    to_post = []

    # Access the API
    u_url = f"http://ccdb.hemiola.com/characters/string/{character}?fields=kHangul,kKorean,kJapaneseKun,kJapaneseOn,kVietnamese"
    unicode_rep = requests.get(u_url, headers=zw_useragent)
    try:
        unicode_rep_json = unicode_rep.json()
        unicode_rep_jdict = unicode_rep_json[0]
    except (IndexError, ValueError):  # Don't really have the proper data.
        return None

    if "kJapaneseKun" in unicode_rep_jdict and "kJapaneseOn" in unicode_rep_jdict:
        ja_kun = unicode_rep_jdict["kJapaneseKun"]
        ja_on = unicode_rep_jdict["kJapaneseOn"]
        if ja_kun is not None or ja_on is not None:
            # Process the data, allowing for either of these to be None in value.
            # A space is added since the kun appears first
            ja_kun = ja_kun.lower() + " " if ja_kun is not None else ""
            ja_on = ja_on.upper() if ja_on is not None else ""

            # Recombine the readings
            ja_total = ja_kun + ja_on
            ja_total = ja_total.strip().split(" ")
            ja_total = ", ".join(ja_total)
            ja_string = f"**Japanese** | *{ja_total}*"
            to_post.append(ja_string)
    if "kHangul" in unicode_rep_jdict and "kKorean" in unicode_rep_jdict:
        ko_hangul = unicode_rep_jdict["kHangul"]
        # We apply RR romanization to this.
        if ko_hangul is not None:
            ko_latin = Romanizer(ko_hangul).romanize().lower()
            ko_latin = ko_latin.replace(" ", ", ")  # Replace spaces with commas
            ko_hangul = ko_hangul.replace(" ", ", ")  # Replace spaces with commas
            ko_total = f"{ko_hangul} / *{ko_latin}*"
            ko_string = f"**Korean** | {ko_total}"
            to_post.append(ko_string)
    if "kVietnamese" in unicode_rep_jdict:
        vi_latin = unicode_rep_jdict["kVietnamese"]
        if vi_latin is not None:
            vi_latin = vi_latin.lower()
            vi_string = f"**Vietnamese** | *{vi_latin}*"
            to_post.append(vi_string)

    if len(to_post) > 0:
        return "\n".join(to_post)


def zh_character(character, zw_useragent):
    """
    This function looks up a Chinese character's pronunciations and meanings.
    It also ties together a lot of the other reference functions above.

    :param character: Any Chinese character.
    :return: A formatted string containing the character's information.
    """

    # Whether or not multiple characters are passed to this function
    multi_mode = len(multi_character_list) > 1
    multi_character_dict = {}
    multi_character_list = list(character)

    eth_page = requests.get(
        f"https://www.mdbg.net/chinese/dictionary?page=chardict&cdcanoce=0&cdqchi={character}",
        headers=zw_useragent,
    )
    tree = html.fromstring(eth_page.content)  # now contains the whole HTML page
    pronunciation = [
        div.text_content() for div in tree.xpath('//div[contains(@class,"pinyin")]')
    ]
    # Note that the Yue pronunciation is given as `['zyun2, zyun3']`
    cmn_pronunciation, yue_pronunciation = pronunciation[::2], pronunciation[1::2]

    if len(pronunciation) == 0:  # Check to not return anything if the entry is invalid
        logger.info(f"[ZW] ZH-Character: No results for {character}")
        return (
            f"**There were no results for {character}**. Please check to make sure it is a valid Chinese "
            "character. Alternatively, it may be an uncommon variant that is not in "
            "online dictionaries."
        )

    if not multi_mode:  # Regular old-school character search for just one.
        cmn_pronunciation = " / ".join(cmn_pronunciation)
        yue_pronunciation = tree.xpath(
            '//a[contains(@onclick,"pronounce-jyutping")]/text()'
        )
        yue_pronunciation = " / ".join(yue_pronunciation)
        # Add superscript to the numbers. Wrapped in paragraphs so that
        # it displays the same on both New and Old Reddit.
        for i in range(0, 9):
            yue_pronunciation = yue_pronunciation.replace(str(i), f"^({str(i)} ")
            yue_pronunciation = yue_pronunciation.replace(str(i), f"{str(i)})")

        meaning = tree.xpath('//div[contains(@class,"defs")]/text()')
        meaning = "/ ".join(meaning).strip()

        if tradify(character) == simplify(character):
            logger.debug(
                f"[ZW] ZH-Character: The two versions of {character} are identical."
            )
            lookup_line_1 = str(
                "# [{0}](https://en.wiktionary.org/wiki/{0}#Chinese)".format(character)
            )
            lookup_line_1 += "\n\nLanguage | Pronunciation\n---------|--------------\n"
            lookup_line_1 += "**Mandarin** | *{}*\n**Cantonese** | *{}*"
            lookup_line_1 = lookup_line_1.format(
                cmn_pronunciation, yue_pronunciation[:-1]
            )
        else:
            logger.debug(
                f"[ZW] ZH-Character: The two versions of {character} are *not* identical."
            )
            lookup_line_1 = (
                "# [{0} ({1})](https://en.wiktionary.org/wiki/{0}#Chinese)".format(
                    tradify(character), simplify(character)
                )
            )
            lookup_line_1 += "\n\nLanguage | Pronunciation\n---------|--------------\n"
            lookup_line_1 += "**Mandarin** | *{}*\n**Cantonese** | *{}*"
            lookup_line_1 = lookup_line_1.format(
                cmn_pronunciation, yue_pronunciation[:-1]
            )

        # Hokkien and Hakka Data
        min_hak_data = zh_character_min_hak(tradify(character), zw_useragent)
        lookup_line_1 += min_hak_data

        # Old Chinese
        try:  # Try to get old chinese data.
            ocmc_pronunciation = zh_character_oc_search(tradify(character))
            if ocmc_pronunciation is not None:
                lookup_line_1 += ocmc_pronunciation
        except IndexError:  # There was an error; character has no old chinese entry
            pass

        # Other Language Readings
        other_readings_data = zh_character_other_readings(
            tradify(character), zw_useragent
        )
        if other_readings_data is not None:
            lookup_line_1 += "\n" + other_readings_data

        calligraphy_image = zh_character_calligraphy_search(character)
        if calligraphy_image is not None:
            lookup_line_1 += calligraphy_image

        lookup_line_1 += f'\n\n**Meanings**: "{meaning}."'
    else:  # It's multiple characters, let's make a table.
        # MULTIPLE Start iterating over the characters we have
        if tradify(character) == simplify(character):
            duo_key = f"# {character}"
        else:  # Different versions, different header.
            duo_key = f"# {tradify(character)} ({simplify(character)})"
        duo_header = "\n\nCharacter "
        duo_separator = "\n---|"
        duo_mandarin = "\n**Mandarin**"
        duo_cantonese = "\n**Cantonese** "
        duo_meaning = "\n**Meanings** "

        for wenzi in multi_character_list:  # Got through each character
            multi_character_dict[wenzi] = {}  # Create a new dictionary for it.

            # Get the data.
            character_url = (
                "https://www.mdbg.net/chindict/chindict.php?page=chardict&cdcanoce=0&cdqchi="
                + wenzi
            )
            new_eth_page = requests.get(character_url, headers=zw_useragent)
            # now contains the whole HTML page
            new_tree = html.fromstring(new_eth_page.content)
            pronunciation = [
                div.text_content()
                for div in new_tree.xpath('//div[contains(@class,"pinyin")]')
            ]
            cmn_pronunciation, yue_pronunciation = (
                pronunciation[::2],
                pronunciation[1::2],
            )

            # Format the pronunciation data
            cmn_pronunciation = "*" + " ".join(cmn_pronunciation) + "*"
            yue_pronunciation = new_tree.xpath(
                '//a[contains(@onclick,"pronounce-jyutping")]/text()'
            )
            yue_pronunciation = " ".join(yue_pronunciation)
            for i in range(0, 9):
                yue_pronunciation = yue_pronunciation.replace(str(i), f"^{str(i)} ")
            yue_pronunciation = "*" + yue_pronunciation.strip() + "*"

            multi_character_dict[wenzi]["mandarin"] = cmn_pronunciation
            multi_character_dict[wenzi]["cantonese"] = yue_pronunciation

            # Format the meaning data.
            meaning = new_tree.xpath('//div[contains(@class,"defs")]/text()')
            meaning = "/ ".join(meaning)
            meaning = '"' + meaning.strip() + '."'
            multi_character_dict[wenzi]["meaning"] = meaning

            # Create a randomized wait time.
            wait_sec = random.randint(3, 12)
            time.sleep(wait_sec)

        # Now let's construct the table based on the data.
        for key in multi_character_list:  # Iterate over the characters in order
            character_data = multi_character_dict[key]
            if tradify(key) == simplify(key):  # Same character in both sets.
                duo_header += (
                    " | [{0}](https://en.wiktionary.org/wiki/{0}#Chinese)".format(key)
                )
            else:
                duo_header += (
                    " | [{0} ({1})](https://en.wiktionary.org/wiki/{0}#Chinese)".format(
                        tradify(key), simplify(key)
                    )
                )
            duo_separator += "---|"
            duo_mandarin += f" | {character_data['mandarin']}"
            duo_cantonese += f" | {character_data['cantonese']}"
            duo_meaning += f" | {character_data['meaning']}"

        lookup_line_1 = (
            duo_key
            + duo_header
            + duo_separator
            + duo_mandarin
            + duo_cantonese
            + duo_meaning
        )

    # Format the dictionary links footer
    lookup_line_2 = (
        "\n\n\n^Information ^from "
        "[^(Unihan)](https://www.unicode.org/cgi-bin/GetUnihanData.pl?codepoint={0}) ^| "
        "[^(CantoDict)](https://www.cantonese.sheik.co.uk/dictionary/characters/{0}/) ^| "
        "[^(Chinese Etymology)](https://hanziyuan.net/#{1}) ^| "
        "[^(CHISE)](https://www.chise.org/est/view/char/{0}) ^| "
        "[^(CTEXT)](https://ctext.org/dictionary.pl?if=en&char={1}) ^| "
        "[^(MDBG)](https://www.mdbg.net/chinese/dictionary?page=worddict&wdrst=1&wdqb={0}) ^| "
        "[^(MoE DICT)](https://www.moedict.tw/'{1}) ^| "
        "[^(MFCCD)](https://humanum.arts.cuhk.edu.hk/Lexis/lexi-mf/search.php?word={1})"
    )
    lookup_line_2 = lookup_line_2.format(character, tradify(character))

    logger.info(
        f"[ZW] ZH-Character: Received lookup command for {character} in "
        "Chinese. Returned search results."
    )

    return lookup_line_1 + lookup_line_2


def zh_word_decode_pinyin(s):
    """
    Function to convert numbered pin1 yin1 into proper tone marks. CC-CEDICT's format uses numerical pinyin.
    This code is courtesy of Greg Hewgill on StackOverflow:
    https://stackoverflow.com/questions/8200349/convert-numbered-pinyin-to-pinyin-with-tone-marks

    :param s: A string of numbered pinyin (e.g. pin1 yin1)
    :return result: A string of pinyin with the tone marks properly applied (e.g. pīnyīn)
    """

    pinyintonemark = {
        0: "aoeiuv\u00fc",
        1: "\u0101\u014d\u0113\u012b\u016b\u01d6\u01d6",
        2: "\u00e1\u00f3\u00e9\u00ed\u00fa\u01d8\u01d8",
        3: "\u01ce\u01d2\u011b\u01d0\u01d4\u01da\u01da",
        4: "\u00e0\u00f2\u00e8\u00ec\u00f9\u01dc\u01dc",
    }

    s = s.lower()
    result = ""
    t = ""
    for c in s:
        if "a" <= c <= "z":
            t += c
        elif c == ":":
            assert t[-1] == "u"
            t = t[:-1] + "\u00fc"
        else:
            if "0" <= c <= "5":
                tone = int(c) % 5
                if tone != 0:
                    m = re.search("[aoeiuv\u00fc]+", t)
                    if m is None:
                        t += c
                    elif len(m.group(0)) == 1:
                        t = (
                            t[: m.start(0)]
                            + pinyintonemark[tone][pinyintonemark[0].index(m.group(0))]
                            + t[m.end(0) :]
                        )
                    else:
                        if "a" in t:
                            t = t.replace("a", pinyintonemark[tone][0])
                        elif "o" in t:
                            t = t.replace("o", pinyintonemark[tone][1])
                        elif "e" in t:
                            t = t.replace("e", pinyintonemark[tone][2])
                        elif t.endswith("ui"):
                            t = t.replace("i", pinyintonemark[tone][3])
                        elif t.endswith("iu"):
                            t = t.replace("u", pinyintonemark[tone][4])
                        else:
                            t += "!"
            result += t
            t = ""
    result += t

    return result


def zh_word_buddhist_dictionary_search(chinese_word):
    """
    Function that allows us to consult the Soothill-Hodous 'Dictionary of Chinese Buddhist Terms.'
    For more information, please visit: https://mahajana.net/texts/soothill-hodous.html
    Since the dictionary is saved in the CC-CEDICT format, this also serves as a template for entry conversion.

    :param chinese_word: Any Chinese word. This should be in its *traditional* form.
    :return: None if there is nothing that matches, a dictionary with content otherwise.
    """
    general_dictionary = {}

    # We open the file.
    f = open(FILE_ADDRESS_ZH_BUDDHIST, encoding="utf-8")
    existing_data = f.read()
    existing_data = existing_data.split("\n")
    f.close()

    relevant_line = None

    # Look for the relevant word (should not take long.)
    for entry in existing_data:
        traditional_headword = entry.split(" ", 1)[0]
        if chinese_word == traditional_headword:
            relevant_line = entry
            break

    if relevant_line is not None:  # We found a matching word.
        # Parse the entry (code courtesy Marcanuy at https://github.com/marcanuy/cedict_utils, MIT license)
        hanzis = relevant_line.partition("[")[0].split(" ", 1)
        keywords = dict(
            meanings=relevant_line.partition("/")[2]
            .replace('"', "'")
            .rstrip("/")
            .strip()
            .split("/"),
            traditional=hanzis[0].strip(" "),
            simplified=hanzis[1].strip(" "),
            # Take the content in between the two brackets
            pinyin=relevant_line.partition("[")[2].partition("]")[0],
            raw_line=relevant_line,
        )

        # Format the data nicely.
        if len(keywords["meanings"]) > 2:  # Truncate if too long.
            keywords["meanings"] = keywords["meanings"][:2]
            keywords["meanings"][-1] += "."  # Add a period.
        formatted_line = '\n\n**Buddhist Meanings**: "{}"'.format(
            "; ".join(keywords["meanings"])
        )
        formatted_line += (
            " ([Soothill-Hodous]"
            "(https://mahajana.net/en/library/texts/a-dictionary-of-chinese-buddhist-terms))"
        )

        general_dictionary["meaning"] = formatted_line
        general_dictionary["pinyin"] = keywords["pinyin"]

        return general_dictionary


def zh_word_cccanto_search(cantonese_word):
    """
    Function that parses and returns data from the CC-Canto database, which uses CC-CEDICT's format.
    More information can be found here: https://cantonese.org/download.html

    :param cantonese_word: Any Cantonese word. This should be in its *traditional* form.
    :return: None if there is nothing that matches, a dictionary with content otherwise.
    """
    general_dictionary = {}

    # We open the file.
    f = open(FILE_ADDRESS_ZH_CCCANTO, encoding="utf-8")
    existing_data = f.read()
    existing_data = existing_data.split("\n")
    f.close()

    relevant_line = None

    # Look for the relevant word (should not take long.)
    for entry in existing_data:
        traditional_headword = entry.split(" ", 1)[0]
        if cantonese_word == traditional_headword:
            relevant_line = entry
            break

    if relevant_line is not None:
        # Parse the entry (based on code from Marcanuy at https://github.com/marcanuy/cedict_utils, MIT license)
        hanzis = relevant_line.partition("[")[0].split(" ", 1)
        keywords = dict(
            meanings=relevant_line.partition("/")[2]
            .replace('"', "'")
            .rstrip("/")
            .strip()
            .split("/"),
            traditional=hanzis[0].strip(" "),
            simplified=hanzis[1].strip(" "),
            # Take the content in between the two brackets
            pinyin=relevant_line.partition("[")[2].partition("]")[0],
            jyutping=relevant_line.partition("{")[2].partition("}")[0],
            raw_line=relevant_line,
        )

        formatted_line = '\n\n**Cantonese Meanings**: "{}."'.format(
            "; ".join(keywords["meanings"])
        )
        formatted_line += " ([CC-Canto](https://cantonese.org/search.php?q={}))".format(
            cantonese_word
        )
        for i in range(0, 9):
            keywords["jyutping"] = keywords["jyutping"].replace(
                str(i), f"^{str(i)} "
            )  # Adds syntax for tones
        keywords["jyutping"] = (
            keywords["jyutping"].replace("  ", " ").strip()
        )  # Replace double spaces

        general_dictionary["meaning"] = formatted_line
        general_dictionary["pinyin"] = keywords["pinyin"]
        general_dictionary["jyutping"] = keywords["jyutping"]

        return general_dictionary


# noinspection PyBroadException
def zh_word_tea_dictionary_search(chinese_word, zw_useragent):
    """
    Function that searches the Babelcarp Chinese Tea Lexicon for Chinese tea terms.

    :param chinese_word: Any Chinese word in *simplified* form.
    :return: None if there is nothing that matches, a formatted string with meaning otherwise.
    """
    general_dictionary = {}

    # Conduct a search.
    web_search = (
        f"http://babelcarp.org/babelcarp/babelcarp.cgi?phrase={chinese_word}&define=1"
    )
    eth_page = requests.get(web_search, headers=zw_useragent)
    try:
        tree = html.fromstring(eth_page.content)  # now contains the whole HTML page
        word_content = tree.xpath('//fieldset[contains(@id,"translation")]//text()')
    except BaseException:
        return None

    # Get the headword of the entry.
    try:
        head_word = word_content[2].strip()
    except IndexError:
        return None

    if chinese_word not in head_word:
        # If the characters don't match: Exit. This includes null searches.
        return None
    else:  # It exists.
        try:
            pinyin = re.search(r"\((.*?)\)", word_content[2]).group(1).lower()
        except AttributeError:  # Never mind, it does not exist.
            return None

        meaning = word_content[3:]
        meaning = [item.strip() for item in meaning]

        # Format the entry to return
        formatted_line = f"\n\n**Tea Meanings**: \"{' '.join(meaning)}.\""
        formatted_line = formatted_line.replace(" )", " ")
        formatted_line = formatted_line.replace("  ", " ")
        formatted_line += f" ([Babelcarp]({web_search}))"  # Append source

        general_dictionary["meaning"] = formatted_line
        general_dictionary["pinyin"] = pinyin

        return general_dictionary


def zh_word_alt_romanization(pinyin_string):
    """
    Takes a pinyin with number item and returns version of it in the legacy Wade-Giles and Yale romanization schemes.
    This is only used for zh_word at the moment. We don't deal with diacritics for this. Too complicated.
    Example: ri4 guang1, becomes, jih^4 kuang^1 in Wade Giles and r^4 gwang^1 in Yale.

    :param pinyin_string: A numbered pinyin string (e.g. pin1 yin1).
    :return: A tuple. Yale romanization form first, then the Wade-Giles version.
    """

    yale_list = []
    wadegiles_list = []

    # Get the corresponding pronunciations into a dictonary.
    corresponding_dict = {}
    csv_file = csv.reader(
        open(FILE_ADDRESS_ZH_ROMANIZATION, encoding="utf-8"), delimiter=","
    )
    for row in csv_file:
        pinyin_p, yale_p, wadegiles_p = row
        corresponding_dict[pinyin_p] = [yale_p.strip(), wadegiles_p.strip()]

    # Divide the string into syllables
    syllables = pinyin_string.split(" ")

    # Process each syllable.
    for syllable in syllables:
        tone = syllable[-1]
        syllable = syllable[:-1].lower()

        # Make exception for null tones.
        if tone != "5":  # Add tone as superscript
            yale_equiv = f"{corresponding_dict[syllable][0]}^({tone})"
            wadegiles_equiv = f"{corresponding_dict[syllable][1]}^({tone})"
        else:  # Null tone, no need to add a number.
            yale_equiv = f"{corresponding_dict[syllable][0]}"
            wadegiles_equiv = f"{corresponding_dict[syllable][1]}"
        yale_list.append(yale_equiv)
        wadegiles_list.append(wadegiles_equiv)

    # Reconstitute the equivalent parts into a string.
    yale_post = " ".join(yale_list)
    wadegiles_post = " ".join(wadegiles_list)

    return yale_post, wadegiles_post


def zh_word_chengyu(chengyu):
    """
    Function to get Chinese information for Chinese chengyu, including literary sources and explanations.
    Note: this is the second version. This version just adds supplementary Chinese information to zh_word.

    :param chengyu: Any Chinese idiom (usually four characters)
    :return: None if no results, otherwise a formatted string.
    """

    headers = {
        "Content-Type": "text/html; charset=gb2312",
        "f-type": "chengyu",
        "accept-encoding": "gb2312",
    }
    chengyu = simplify(chengyu)  # This website only takes simplified chinese
    r_tree = None  # Placeholder.

    # Convert Unicode into a string for the URL, which uses GB2312 encoding.
    chengyu_gb = str(chengyu.encode("gb2312"))
    chengyu_gb = chengyu_gb.replace("\\x", "%").upper()[2:-1]

    # Format the search link.
    search_link = "http://cy.51bc.net/serach.php?f_type=chengyu&f_type2=&f_key={}"
    # Note: 'serach' is intentional.
    search_link = search_link.format(chengyu_gb)
    logger.debug(search_link)

    try:
        # We run a search on the site and see if there are results.
        results = requests.get(search_link.format(chengyu), headers=headers)
        results.encoding = "gb2312"
        r_tree = html.fromstring(results.text)  # now contains the whole HTML page
        chengyu_exists = r_tree.xpath('//td[contains(@bgcolor,"#B4D8F5")]/text()')
    except (
        UnicodeEncodeError,
        UnicodeDecodeError,
        requests.exceptions.ConnectionError,
        requests.exceptions.ChunkedEncodingError,
    ):
        # There may be an issue with the conversion. Skip if so.
        logger.error("[ZW] ZH-Chengyu: Unicode encoding error.")
        chengyu_exists = ["", "找到 0 个成语"]  # Tell it to exit later.

    if not chengyu_exists:
        return

    if "找到 0 个成语" in chengyu_exists[1]:  # There are no results...
        logger.info(f"[ZW] ZH-Chengyu: No chengyu results found for {chengyu}.")
        return None
    elif r_tree is not None:  # There are results.
        # Look through the results page.
        link_results = r_tree.xpath('//tr[contains(@bgcolor,"#ffffff")]/td/a')
        try:
            actual_link = link_results[0].attrib["href"]
        except IndexError:
            return None
        logger.info(
            f"[ZW] > ZH-Chengyu: Found a chengyu. Actual link at: {actual_link}"
        )

        # Get the data from the actual link
        try:
            eth_page = requests.get(actual_link)
            eth_page.encoding = "gb2312"
            tree = html.fromstring(eth_page.text)  # now contains the whole HTML page
        except (
            requests.exceptions.ChunkedEncodingError,
            requests.exceptions.ConnectionError,
        ):
            return
        else:
            # Grab the data from the table.
            zh_data = tree.xpath('//td[contains(@colspan, "5")]/text()')

        # Assign them to variables.
        chengyu_meaning = zh_data[1]
        chengyu_source = zh_data[2]

        # Format the data nicely to add to the zh_word output.
        cy_to_post = "\n\n**Chinese Meaning**: {}\n\n**Literary Source**: {}"
        cy_to_post = cy_to_post.format(chengyu_meaning, chengyu_source)
        cy_to_post += " ([5156edu]({}), [18Dao](https://tw.18dao.net/成語詞典/{}))".format(
            actual_link, tradify(chengyu)
        )

        logger.info(
            f"[ZW] > ZH-Chengyu: Looked up the chengyu {chengyu} in Chinese. Returned search results."
        )

        return cy_to_post


def zh_word(word, zw_useragent):
    """
    Function to define Chinese words and return their readings and meanings. A Chinese word is one that is longer than
    a single character.

    :param word: Any Chinese word. This function is used for words longer than one character, generally.
    :return: Word data.
    """

    alternate_meanings = []
    alternate_pinyin = ()
    alternate_jyutping = None

    eth_page = requests.get(
        "https://www.mdbg.net/chinese/dictionary?page=worddict&wdrst=0&wdqb=c:" + word,
        headers=zw_useragent,
    )
    tree = html.fromstring(eth_page.content)  # now contains the whole HTML page
    word_exists = str(tree.xpath('//p[contains(@class,"nonprintable")]/strong/text()'))
    cmn_pronunciation = tree.xpath('//div[contains(@class,"pinyin")]/a/span/text()')
    # We only want the pronunciations to be as long as the input
    cmn_pronunciation = cmn_pronunciation[0 : len(word)]
    # We don't need a dividing character per pinyin standards
    cmn_pronunciation = "".join(cmn_pronunciation)

    # Check to not return anything if the entry is invalid
    if "No results found" in word_exists:
        # First we try to check our specialty dictionaries. Buddhist dictionary first. Then the tea dictionary.
        search_results_buddhist = zh_word_buddhist_dictionary_search(tradify(word))
        search_results_tea = zh_word_tea_dictionary_search(simplify(word), zw_useragent)
        search_results_cccanto = zh_word_cccanto_search(tradify(word))

        # If both have nothing, we kick it down to the character search.
        if (
            search_results_buddhist is None
            and search_results_tea is None
            and search_results_cccanto is None
        ):
            logger.info(
                "[ZW] ZH-Word: No results found. Getting individual characters instead."
            )
            # This will split the word into character chunks.
            if len(word) < 2:
                to_post = zh_character(word)
            else:  # The word is longer than one character.
                to_post = ""
                search_characters = list(word)
                for character in search_characters:
                    to_post += "\n\n" + zh_character(character)
            return to_post

        else:  # Otherwise, let's try to format the data nicely.
            if search_results_buddhist is not None:
                alternate_meanings.append(search_results_buddhist["meaning"])
                alternate_pinyin = search_results_buddhist["pinyin"]
            if search_results_tea is not None:
                alternate_meanings.append(search_results_tea["meaning"])
                alternate_pinyin = search_results_tea["pinyin"]
            if search_results_cccanto is not None:
                alternate_meanings.append(search_results_cccanto["meaning"])
                alternate_pinyin = search_results_cccanto["pinyin"]
                alternate_jyutping = search_results_cccanto["jyutping"]
            logger.info(
                f"[ZW] ZH-Word: No results for word {word}, but results are in specialty dictionaries."
            )

    if len(alternate_meanings) == 0:  # The standard search function for regular words.
        # Get alternate pinyin from a separate function. We get Wade Giles and Yale. Like 'Guan1 yin1 Pu2 sa4'
        try:
            py_split_pronunciation = tree.xpath(
                '//div[contains(@class,"pinyin")]/a/@onclick'
            )
            py_split_pronunciation = re.search(
                r"\|(...+)\'\)", py_split_pronunciation[0]
            ).group(0)
            # Format it nicely.
            py_split_pronunciation = py_split_pronunciation.split("'", 1)[0][1:].strip()
            alt_romanize = zh_word_alt_romanization(py_split_pronunciation)
        except IndexError:
            # This likely means that the page does not contain that information.
            alt_romanize = ("---", "---")

        meaning = [
            div.text_content() for div in tree.xpath('//div[contains(@class,"defs")]')
        ]
        meaning = [
            x for x in meaning if x != " " and x != ", "
        ]  # This removes any empty spaces or commas that are in the list.
        meaning = "/ ".join(meaning)
        meaning = meaning.strip()

        # Obtain the Cantonese information.
        yue_page = requests.get(
            "https://cantonese.org/search.php?q=" + word, headers=zw_useragent
        )
        yue_tree = html.fromstring(yue_page.content)  # now contains the whole HTML page
        yue_pronunciation = yue_tree.xpath(
            '//h3[contains(@class,"resulthead")]/small/strong//text()'
        )
        # This Len needs to be double because of the numbers
        yue_pronunciation = yue_pronunciation[0 : (len(word) * 2)]
        yue_pronunciation = iter(yue_pronunciation)
        yue_pronunciation = [c + next(yue_pronunciation, "") for c in yue_pronunciation]

        # Combines the tones and the syllables together
        yue_pronunciation = " ".join(yue_pronunciation)
        for i in range(0, 9):
            # Adds Markdown syntax
            yue_pronunciation = yue_pronunciation.replace(str(i), f"^({str(i)}) ")
        yue_pronunciation = yue_pronunciation.strip()

    else:  # This is for the alternate search with the specialty dictionaries.
        cmn_pronunciation = zh_word_decode_pinyin(alternate_pinyin)
        alt_romanize = zh_word_alt_romanization(alternate_pinyin)
        if alternate_jyutping is not None:
            yue_pronunciation = alternate_jyutping
        else:
            yue_pronunciation = "---"  # The non-Canto specialty dictionaries do not include Jyutping pronunciation.
        meaning = "\n".join(alternate_meanings)

    # Format the header appropriately.
    if tradify(word) == simplify(word):
        lookup_line_1 = str(
            "# [{0}](https://en.wiktionary.org/wiki/{0}#Chinese)".format(word)
        )
    else:
        lookup_line_1 = (
            "# [{0} ({1})](https://en.wiktionary.org/wiki/{0}#Chinese)".format(
                tradify(word), simplify(word)
            )
        )

    # Format the rest.
    lookup_line_1 += "\n\nLanguage | Pronunciation\n---------|--------------"
    lookup_line_1 += (
        f"\n**Mandarin** (Pinyin) | *{cmn_pronunciation}*\n**Mandarin** (Wade-Giles) | *{alt_romanize[1]}*"
        f"\n**Mandarin** (Yale) | *{alt_romanize[0]}*\n**Cantonese** | *{yue_pronunciation}*"
    )

    # Add Hokkien and Hakka data.
    lookup_line_1 += zh_character_min_hak(tradify(word), zw_useragent)

    # Format the meaning line.
    if len(alternate_meanings) == 0:
        # Format the regular results we have.
        lookup_line_2 = f'\n\n**Meanings**: "{meaning}."'

        # Append chengyu data if the string is four characters.
        if len(word) == 4:
            chengyu_data = zh_word_chengyu(word)
            if chengyu_data is not None:
                logger.info("[ZW] ZH-Word: >> Added additional chengyu data.")
                lookup_line_2 += chengyu_data

        # We append Buddhist results if we have them.
        mainline_search_results_buddhist = zh_word_buddhist_dictionary_search(
            tradify(word)
        )
        if mainline_search_results_buddhist is not None:
            lookup_line_2 += mainline_search_results_buddhist["meaning"]

    else:  # This is for the alternate dictionaries only.
        lookup_line_2 = "\n" + meaning

    # Format the footer with the dictionary links.
    lookup_line_3 = (
        "\n\n\n^Information ^from "
        "[^CantoDict](https://www.cantonese.sheik.co.uk/dictionary/search/?searchtype=1&text={0}) ^| "
        "[^MDBG](https://www.mdbg.net/chinese/dictionary?page=worddict&wdrst=0&wdqb=c:{0}) ^| "
        "[^Yellowbridge](https://yellowbridge.com/chinese/dictionary.php?word={0}) ^| "
        "[^Youdao](https://dict.youdao.com/w/eng/{0}/#keyfrom=dict2.index)"
    )
    lookup_line_3 = lookup_line_3.format(word)

    # Combine everything together.
    to_post = lookup_line_1 + lookup_line_2 + "\n\n" + lookup_line_3
    logger.info(
        f"[ZW] ZH-Word: Received a lookup command for {word} in Chinese. Returned search results."
    )
    return to_post
