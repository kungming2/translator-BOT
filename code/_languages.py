#!/usr/bin/env python3

"""A collection of database sets and language functions that all r/translator bots use."""

import csv
import itertools
import os
import re
from typing import Dict, List, NamedTuple, Tuple

from rapidfuzz import fuzz  # Switched to rapidfuzz

from _config import KEYWORDS
from _language_consts import (
    APP_WORDS,
    COUNTRY_LIST,
    ENGLISH_2_WORDS,
    ENGLISH_3_WORDS,
    FUZZ_IGNORE_WORDS,
    ISO_LANGUAGE_COUNTRY_ASSOCIATED,
    MAIN_LANGUAGES,
)

VERSION_NUMBER_LANGUAGES = "1.7.22"

# Access the CSV with ISO 639-3 and ISO 15924 data.
lang_script_directory = os.path.dirname(__file__)  # <-- absolute dir the script is in
lang_script_directory += "/Data/"  # Where the main files are kept.
FILE_ADDRESS_ISO_ALL = os.path.join(lang_script_directory, "_database_iso_codes.csv")

"""LANGUAGE CODE LISTS"""

# These are two-letter and three-letter English words that can be confused for ISO language codes.
# We exclude them when processing the title. When adding new ones, add them in title case.

# Title formatting words.
ENGLISH_DASHES = [
    "English -",
    "English-",
    "-English",
    "- English",
    "-Eng",
    "Eng-",
    "- Eng",
    "Eng -",
    "ENGLISH-",
    "ENGLISH -",
    "EN-",
    "ENG-",
    "ENG -",
    "-ENG",
    "- ENG",
    "-ENGLISH",
    "- ENGLISH",
]
WRONG_DIRECTIONS = ["<", "〉", "›", "》", "»", "⟶", "\udcfe", "&gt;", "→", "←", "~"]
WRONG_BRACKETS_LEFT = ["［", "〚", "【 ", "〔", "〖", "⟦", "｟", "《"]
WRONG_BRACKETS_RIGHT = ["］", "〛", "】", "〕", "〗", "⟧", "｠", "》"]


def language_lists_generator() -> None:
    """
    A routine that creates a bunch of the old lists that used to power `converter()`

    :return: Nothing, but it declares a bunch of global variables.
    """

    global SUPPORTED_CODES, SUPPORTED_LANGUAGES, ISO_DEFAULT_ASSOCIATED, ISO_639_1, ISO_639_2B, ISO_639_3, ISO_NAMES, MISTAKE_ABBREVIATIONS, LANGUAGE_COUNTRY_ASSOCIATED

    SUPPORTED_CODES = []
    SUPPORTED_LANGUAGES = []
    ISO_DEFAULT_ASSOCIATED = []
    ISO_639_1 = []
    ISO_639_2B = {}
    ISO_639_3 = []
    ISO_NAMES = []
    MISTAKE_ABBREVIATIONS = {}
    LANGUAGE_COUNTRY_ASSOCIATED = {}

    for language_code, language_module in MAIN_LANGUAGES.items():
        ISO_639_1.append(language_code)
        ISO_639_3.append(language_module["language_code_3"])
        ISO_NAMES.append(language_module["name"])
        if (
            "alternate_names" in language_module
            and language_module["alternate_names"] is not None
        ):
            for item in language_module["alternate_names"]:
                ISO_NAMES.append(item)

        if language_module["supported"]:
            SUPPORTED_CODES.append(language_code)
            SUPPORTED_LANGUAGES.append(language_module["name"])

        if "countries_default" in language_module:
            ISO_DEFAULT_ASSOCIATED.append(
                f"{language_code}-{language_module['countries_default']}"
            )

        if "countries_associated" in language_module:
            LANGUAGE_COUNTRY_ASSOCIATED[language_code] = language_module[
                "countries_associated"
            ]

        if "mistake_abbreviation" in language_module:
            MISTAKE_ABBREVIATIONS[
                language_module["mistake_abbreviation"]
            ] = language_code

        if "language_code_2b" in language_module:
            ISO_639_2B[language_module["language_code_2b"]] = language_code


# Form the lists from the dictionary that are needed for compatibility.
language_lists_generator()


def fuzzy_text(word: str) -> str | None:
    """
    A quick function that assesses misspellings of supported languages. For example, 'Chinnsse' will be returned as
    'Chinese." The closeness ratio can be adjusted to make this more or less sensitive.
    A higher ratio means stricter, and a lower ratio means less strict.

    :param word: Any word.
    :return: If the word seems to be close to a supported language, return the likely match.
    """

    for language in SUPPORTED_LANGUAGES:
        closeness = fuzz.ratio(language, word)

        if closeness > 75 and language != "Javanese":
            return str(language)


def language_name_search(search_term: str) -> str:
    """
    Function that searches for a language name or its mispellings/alternate names. It will only return the code if it's
    an *exact* match. There's a separate module in `fuzzy_text` above and in `converter` that will take care of
    misspellings or other issues for the main supported languages.

    :param search_term: The term we're looking to check, most likely a language name.
    :return: The equivalent language code if found, a blank string otherwise.
    """

    for key, language_info in MAIN_LANGUAGES.items():
        if search_term == language_info["name"]:
            return key
        if language_info["alternate_names"] is not None:
            for alternate_name in language_info["alternate_names"]:
                if search_term == alternate_name:
                    return key

    return ""


def transbrackets_new(title: str) -> str:
    """
    A simple function that takes a bracketed tag and moves the bracketed component to the front.
    It will also work if the bracketed section is in the middle of the sentence.

    :param title: A title which has the bracketed tag at the end, or in the middle.
    :return: The transposed title, with the tag properly at the front.
    """

    if "]" in title:  # There is a defined end to this tag.
        bracketed_tag = re.search(r"\[(.+)\]", title)
        bracketed_tag = bracketed_tag.group(0)
        title_remainder = title.replace(bracketed_tag, "")
    else:  # No closing tag...
        bracketed_tag = title.split("[", 1)[1]
        title_remainder = title.replace(bracketed_tag, "")[:-1]
        bracketed_tag = "[" + bracketed_tag + "]"  # enclose it

    # reformatted title
    return f"{bracketed_tag} {title_remainder}"


def lang_code_search(search_term: str, script_search: bool):
    """
    Returns a tuple: name of a code or a script, is it a script? (that's a boolean)

    :param search_term: The term we're looking for.
    :param script_search: A boolean that can narrow down our search to just ISO 15925 script codes.
    :return:
    """

    master_dict = {}
    is_script = len(search_term) == 4

    csv_file = csv.reader(open(FILE_ADDRESS_ISO_ALL, encoding="utf-8"), delimiter=",")
    for row in csv_file:
        # We have a master dictionary. Index by code. Tuple has: (language name, language name (lower), alt names lower)
        master_dict[row[0]] = (row[2:][0], row[2:][0].lower(), row[3:][0].lower())

    if len(search_term) == 3:  # This is a ISO 639-3 code
        if search_term.lower() in master_dict:
            item_name = master_dict[search_term.lower()][0]
            # Since the first two rows are the language code and 639-1 code, we take it from the third.
            return item_name, is_script
        return "", False
    if len(search_term) == 4 and script_search:  # This is a script
        if search_term.lower() in master_dict:
            # Since the first two rows are the language code and 639-1 code, we take it from the third row.
            item_name = master_dict[search_term.lower()][0]
            is_script = True
            return item_name, is_script
    elif len(search_term) > 3:  # Probably a name, so let's get the code
        item_code = ""
        for key, value in master_dict.items():
            if search_term.lower() == value[1]:
                if len(key) == 3 and not script_search:  # This is a language code
                    item_code = key
                elif len(key) == 4:
                    item_code = key
                    is_script = True
                return item_code, is_script

        # No name was found, let's check alternates.
        for key, value in master_dict.items():
            # There may be multiple alternate names here
            sorted_alternate = value[2].split("; ") if ";" in value[2] else [value[2]]

            if search_term.lower() in sorted_alternate:
                if len(key) == 3:  # This is a language code
                    item_code = key
                elif len(key) == 4:
                    item_code = key
                    is_script = True
                return item_code, is_script

    return "", False


def iso639_3_to_iso639_1(specific_code: str) -> None | str:
    """
    Function to get the equivalent ISO 639-1 code from an ISO 639-3 code if it exists.

    :param specific_code: An ISO 639-3 code.
    :return:
    """

    for key, value in MAIN_LANGUAGES.items():
        module_iso3 = value["language_code_3"]
        if specific_code == module_iso3:
            return key

    return None


def country_converter(text_input: str, abbreviations_okay: bool = True):
    """
    Function that detects a country name in a given word.

    :param text_input: Any string.
    :param abbreviations_okay: means it's okay to check the list for abbreviations, like MX or GB.
    :return:
    """

    # Set default values
    country_code = ""
    country_name = ""

    if len(text_input) <= 1:  # Too short, can't return anything for this.
        pass
    # This is only two letters long
    elif len(text_input) == 2 and abbreviations_okay:
        text_input = text_input.upper()  # Convert to upper case
        for country in COUNTRY_LIST:
            if text_input == country[1]:  # Matches exactly
                country_code = text_input
                country_name = country[0]
    elif len(text_input) == 3 and abbreviations_okay:  # three letters long code
        text_input = text_input.upper()  # Convert to upper case
        for country in COUNTRY_LIST:
            if text_input == country[2]:  # Matches exactly
                country_code = country[1]
                country_name = country[0]
    else:  # It's longer than three, probably a name. Or abbreviations are disabled.
        text_input = text_input.title()
        for country in COUNTRY_LIST:
            if text_input == country[0]:  # It's an exact match
                country_code = country[1]
                country_name = country[0]
                return country_code, country_name  # Exit the loop, we're done.
            if text_input in country[0] and len(text_input) >= 3:
                country_code = country[1]
                country_name = country[0]

        if country_code == "" and country_name == "":  # Still nothing
            # Now we check against a list of associated words per country.
            for country in COUNTRY_LIST:
                try:
                    # These are keywords associated with it.
                    country_keywords = country[4]
                    for keyword in country_keywords:
                        if text_input.title() == keyword:  # A Match!
                            country_code = country[1]
                            country_name = country[0]
                except IndexError:
                    # No keywords associated with this country.
                    pass

    if "," in country_name:  # There's a comma.
        country_name = country_name.split(",")[0].strip()
        # Take first part if there's a comma (Taiwan, Province of China)

    return country_code, country_name


class ConverterTuple(NamedTuple):
    language_code: str
    language_name: str
    supported: bool
    country_code: str | None


def converter(input_text: str):
    """
    A function that can convert between language names and codes, and also parse additional data.
    This is one of the most crucial components of Ziwen and is very commonly used.

    :param input_text: Any string that may be a language name or code.
    :return: A tuple with Code, Name, Supported (boolean), country (if present).
    """

    # Set default values
    supported = False
    language_code = ""
    language_name = ""
    country_name = ""
    regional_case = False
    is_script = False
    country_code = None
    targeted_language = input_text

    # There's a hyphen... probably a special code.
    if "-" in input_text and "Anglo" not in input_text:
        # Take only the language part (ar).
        # Get the specific code.
        broader_code, specific_code = targeted_language.split("-", 1)
        if len(specific_code) <= 1:  # If it's just a letter it cannot be valid.
            input_text = broader_code
            specific_code = None
    else:  # Normal code
        broader_code = specific_code = None

    # Special code added to process codes with - in it.
    if specific_code is not None:  # special code (unknown-cyrl / ar-LB).
        # This takes a code and returns a name ar-LB becomes Arabic <Lebanon> and unknown-CYRL becomes Cyrillic (Script)
        if broader_code == "unknown":  # This is going to be a script.
            try:
                # Get the script name.
                input_text = lang_code_search(specific_code, script_search=True)[0]
                is_script = True
            except TypeError:  # Not a valid code.
                pass
        else:  # This should be a language code with a country code.
            regional_case = True
            country_code = country_converter(specific_code, True)[0].upper()
            country_name = country_converter(country_code, True)[1]
            input_text = broader_code
            if (
                f"{input_text}-{country_code}" in ISO_DEFAULT_ASSOCIATED
                or country_code.lower() == input_text.lower()
            ):  # Something like de-DE or zh-CN
                regional_case = False
                country_code = None
                # We don't want to mark the default countries as too granular ones.
            if (
                len(country_name) == 0
            ):  # There's no valid country from the converter. Reset it.
                input_text = targeted_language  # Redefine the language as the original (pre-split)
                regional_case = False
                country_code = None
    elif "{" in input_text and len(input_text) > 3:
        # This may have a country tag. Let's be sure to remove it.
        regional_case = True
        input_text, country_name = input_text.split("{", 1)
        country_name = country_name[:-1]
        country_code = country_converter(country_name)[0]

    # Make a special exemption for COUNTRY CODES because people keep messing that up.
    for key, value in MISTAKE_ABBREVIATIONS.items():
        if len(input_text) == 2 and input_text.lower() == key:
            # If it's the same, let's replace it with the proper one.
            input_text = value

    # We also want to help convert ISO 639-2B codes (there are twenty of them)
    for key, value in ISO_639_2B.items():
        if len(input_text) == 3 and input_text.lower() == key:
            # If it's the same, let's replace it with the proper one.
            input_text = value

    # Convert and reassign special-reserved ISO 639-3 codes to their r/translator equivalents.
    if input_text in ["mis", "und", "mul", "qnp"]:
        # These are special codes that we reassign
        supported = True
        if input_text == "mul":
            input_text = "multiple"
        elif input_text in ["mis", "und", "qnp"]:  # These are assigned to "unknown"
            input_text = "unknown"

    # Start processing the string.
    if len(input_text) < 2:  # This is too short.
        language_code = ""
        language_name = ""
    elif is_script and specific_code:  # This is a script.
        language_code = specific_code
        language_name = input_text
    elif input_text.lower() in ISO_639_1:
        # Everything below is accessing languages. This is a ISO 639-1 code.
        language_code = input_text.lower()
        language_name = MAIN_LANGUAGES[language_code]["name"]
        supported = MAIN_LANGUAGES[language_code]["supported"]
    elif len(input_text) == 3 and input_text.lower() in ISO_639_3:
        # This is equivalent to a supported one, eg 'cmn'.
        for key, value in MAIN_LANGUAGES.items():
            if input_text.lower() == value["language_code_3"]:
                language_code = key
                language_name = MAIN_LANGUAGES[language_code]["name"]
                supported = MAIN_LANGUAGES[language_code]["supported"]
    elif len(input_text) == 3 and len(language_name_search(input_text.title())) != 0:
        # This is three letters and name.
        # An example of this is 'Any'.
        language_code = language_name_search(input_text.title())
        language_name = MAIN_LANGUAGES[language_code]["name"]
    elif len(input_text) == 3 and input_text.lower() not in ISO_639_3:
        # This may be a non-supported ISO 639-3 code.
        results = lang_code_search(input_text, False)[0]  # Consult the CSV file.
        if len(results) != 0:  # We found a matching language name.
            language_code = input_text.lower()
            language_name = results
    elif len(input_text) > 3:  # Not a code, let's look for names.
        if input_text.title() in ISO_NAMES:  # This is a defined language with a name.
            # This searches both regular and alternate names.
            language_code = language_name_search(input_text.title())
            language_name = MAIN_LANGUAGES[language_code]["name"]
            supported = MAIN_LANGUAGES[language_code]["supported"]
        elif input_text.title() not in ISO_NAMES:
            fuzzy_result = (
                fuzzy_text(input_text.title().strip())
                if input_text.title() not in FUZZ_IGNORE_WORDS
                else None
            )

            if fuzzy_result is not None:
                # We found a language that this is close to in spelling.
                language_code = language_name_search(fuzzy_result.title())
                language_name = str(fuzzy_result)
                supported = MAIN_LANGUAGES[language_code]["supported"]
            else:  # No fuzzy match. Now we're going to check if it's the name of an ISO 639-3 language or script.
                total_results = lang_code_search(input_text, False)
                specific_results = total_results[0]
                if len(specific_results) != 0:
                    language_code = specific_results
                    language_name = lang_code_search(language_code, total_results[1])[0]
                    if language_code in MAIN_LANGUAGES:
                        supported = MAIN_LANGUAGES[language_code]["supported"]
                elif len(specific_results) == 0 and len(input_text) == 4:
                    # This is a script code.
                    script_results = lang_code_search(input_text, True)[0]
                    if len(script_results) != 0:
                        language_name = script_results
                        language_code = lang_code_search(script_results, True)[0]

    # We are re-enabling using < > to denote country names in certain ISO 639-3 languages.
    # if "<" in language_name:  # Strip the brackets from ISO 639-3 languages.
    #    language_name = language_name.split("<")[0].strip()  # Remove the country name in brackets

    if len(language_code) == 0:
        # There's no valid language so let's reset the country values.
        country_code = None
    elif regional_case and len(country_name) != 0 and len(language_code) != 0:
        # This was for a specific language area.
        language_name += " {" + country_name + "}"
    return ConverterTuple(language_code, language_name, supported, country_code)


def country_validator(
    word_list: List[str], language_list: List[str]
) -> Tuple[str, str] | None:
    """
    Takes a list of words, check for a country and a matching language. This allows us to find combinations like de-AT.

    :param word_list: A list of words that may contain a country name.
    :param language_list: A list of words that may contain a language name.

    :return: If nothing is found it just returns None.
    :return: If something is found, returns tuple (lang-COUNTRY, ISO 639-3 code).
    """

    # Set default values
    detected_word = {}
    all_detected_countries = []
    final_word_list = []

    if len(word_list) > 0:  # There are actually words to process.
        if " " in word_list[-1]:
            # There's a space in the last word list from additive function in the title routine
            # Take the last one out. It'll be processed again later anyway.
            word_list = word_list[:-1]
    else:
        return None  # There's nothing we can process.

    if 2 < len(word_list) <= 4:  # There's more than two words. [Swiss, German, Geneva]
        for position in range(2, len(word_list) + 1):  # Get all possible combinations.
            for subset in itertools.combinations(word_list, position):
                # This is useful for getting countries that have more than one word (Costa Rica)
                # Join the words together as a string for searching.
                final_word_list.append(" ".join(subset))

    final_word_list += word_list

    for word in final_word_list:
        results = country_converter(text_input=word, abbreviations_okay=False)
        if results[0] != "":  # The converter got nothing
            detected_word[word] = results[0]
            all_detected_countries.append(results[0])  # add the country code

    if len(detected_word) != 0:
        for language in language_list:
            language_code = converter(language).language_code

            if language_code in LANGUAGE_COUNTRY_ASSOCIATED:
                # There's a language assoc.
                check_countries = LANGUAGE_COUNTRY_ASSOCIATED.get(language_code)
                # Fetch the list of countries associated with that language.

                lang_country_combined = None
                relevant_iso_code = None

                for country in check_countries:
                    if country in all_detected_countries:  # country is listed.
                        lang_country_combined = f"{language_code}-{country}"
                        relevant_iso_code = ISO_LANGUAGE_COUNTRY_ASSOCIATED.get(
                            lang_country_combined
                        )
                        if relevant_iso_code:
                            return lang_country_combined, relevant_iso_code


def comment_info_parser(pbody: str, command: str):
    """
    A function that takes a comment and looks for actable information like languages or words to lookup.
    This drives commands that take a language variable, like `!identify:` or `!translate:`.
    IMPORTANT: The command part MUST include the colon (:), or else it will fail.

    :param pbody: Any text that contains a Ziwen command.
    :param command: The command we want to parse. For example, `!identify:`.
    :return: Returns a tuple. The first part is the string that the command should act on. The second part is whether or
             not it qualifies for "advanced mode" as part of `!identify`. This means it has an additional `!` after
             the language name or code.
    """

    advanced_mode = False
    longer_search = False
    match = ""

    if KEYWORDS.id in pbody:  # Allows for a synonym
        pbody = pbody.replace(KEYWORDS.id, KEYWORDS.identify)

    if "\n" in pbody:  # Replace linebreaks
        pbody = pbody.replace("\n", " ")

    command_w_space = command + " "
    if command_w_space in pbody:  # Fix in case there's a space after the colon
        pbody = pbody.replace(command_w_space, command)
    elif ":[" in pbody:  # There are square brackets in here... let's replace them
        for character in ["[", "]"]:
            pbody = pbody.replace(character, '"')  # Change them to quotes.

    if ":unknown-" in pbody:  # Special syntax in case someone tries to use this way...
        # This is a bit of a hack but w/e
        script_code = pbody.split(":unknown-", 1)[1][0:4]
        if len(script_code) == 4:  # Truly script code
            pbody = pbody.replace(":unknown-", f":{script_code}! ")
        else:  # Let's not put it into advanced mode otherwise.
            pbody = pbody.replace(":unknown-", f":{script_code} ")

    if command in pbody:  # Check to see the command and test the remainder.
        pbody_test = pbody.split(command)[1]
        if "!" in pbody_test[:5]:
            match = re.search(command + "(.*?)!", pbody)
            match = str(match.group(1)).lower()  # Convert it to a string.
            # might be two stacked comments
            advanced_mode = " " not in match and "\n" not in match
        elif '"' in pbody_test[:2]:  # There's a quotation mark close by. Longer search?
            try:
                match = re.search(':"(.*?)"', pbody)
                match = str(match.group(0))[1:-1].title()
                match = match.replace('"', "")  # Replace extra quote marks.
                longer_search = True
            except AttributeError:  # Error for some reason.
                pass

    if longer_search or advanced_mode:
        return match, advanced_mode

    if command in pbody:  # there is a language specified
        match = re.search("(?<=" + command + r")[\w\-<^\'+]+", pbody)
        try:
            match = str(match.group(0)).lower().strip()
        except AttributeError:
            # There's no match... probably because of punctuation. Invalid match.
            return None  # Exit, we can't do anything.
        # If there's a < in the string, check to make sure it's a cross post command.
        if command not in ["!translate:", "!translator:"]:
            # If it's not a crosspost...
            match = match.replace("<", "")  # Take out the bracket
        # Code to double check if it's a script... even without the second! if it is, return as such
        if len(match) == 4:  # This is four characters long
            # Run a search for the specific script
            language_name = lang_code_search(match, True)

            # It found a script name, and the name is not the name of a language
            if language_name is not None and match.title() not in ISO_NAMES:
                advanced_mode = True  # Return it as an advanced mode.
        return match, advanced_mode


def english_fuzz(word: str) -> bool:
    """
    A quick function that detects if a word is likely to be "English." Used in replace_bad_english_typing below.

    :param word: Any word.
    :return: A boolean. True if it's likely to be a misspelling of the word 'English', false otherwise.
    """

    word = word.title()
    closeness = fuzz.ratio("English", word)
    return closeness > 70  # Very likely


def replace_bad_english_typing(title: str) -> str:
    """
    Function that will replace a misspelling for English, so that it can still pass the title filter routine.

    :param title: A post title on r/translator, presumably one with a misspelling.
    :return: The post title but with any words that were mispellings of 'English' replaced.
    """

    title = re.sub(
        r"""
                   [,.;@#?!&$()“”’"•]+  # Accept one or more copies of punctuation
                   \ *           # plus zero or more copies of a space,
                   """,
        " ",  # and replace it with a single space
        title,
        flags=re.VERBOSE,
    )
    title_words = title.split(" ")  # Split the sentence into words.
    title_words = [str(word) for word in title_words]

    for word in title_words:
        if english_fuzz(word):  # This word is a misspelling of "English"
            # Replace the offending word with the proper spelling.
            title = title.replace(word, "English")

    return title  # Return the title, now cleaned up.


def language_mention_search(search_paragraph: str) -> None | List[str]:
    """
    Returns a list of identified language names from a text. Useful for Wiktionary search and title formatting.
    This function only looks for more common languages; there are too many ISO 639-3 languages (about 7800 of them),
    many of which have names that match English words.

    :param search_paragraph: The text that we're going to look for a language name in.
    :return to_post: None if nothing found; a list of language names found otherwise.
    """

    matches = re.findall(r"\b[A-Z][a-z]+", search_paragraph)
    language_name_matches = []

    for match in matches:
        if len(match) > 3:  # We explicitly DO NOT want to match ISO 639-3 codes.
            converter_result = converter(match)
            language_code = converter_result.language_code
            language_name = converter_result.language_name

            # We do a quick check to make sure it's not some obscure ISO 639-3 language.
            proceed = len(language_code) != 3 or language_code in SUPPORTED_CODES

            if len(language_name) != 0 and proceed:  # The result is not blank.
                language_name_matches.append(language_name)

    # remove blanks and duplicates
    language_name_matches = list({x for x in language_name_matches if x != ""})
    # If it matches nothing... UPDATE
    return language_name_matches or None


def bad_title_reformat(title_text: str) -> str:
    """
    Function that takes a badly formatted title and makes it okay. It searches for a language name in the title text.
    If it finds a language name, then it creates a language tag to it and adds it to the original title.
    If no language name is found, then the default of "Unknown" is added to the title.
    This function is used when filtering out posts that violate the guidelines; the user is given this reformatted title
    as an option they can use to resubmit.

    :param title_text: A problematic Reddit post title that does not match the formatting guidelines.
    :return new_title: A reformatted title that adheres to the community's guidelines.
    """

    # Process the title first - and remove punctuation.
    search_text = re.sub(r"[^\w\s]", " ", title_text)
    search_text = search_text.title()

    listed_languages = language_mention_search(search_text.title())
    if listed_languages is not None:  # We have some results.
        listed_languages = [
            x
            for x in listed_languages
            if x not in ["English", "Multiple Languages", "Nonlanguage"]
        ]

    if (
        listed_languages is None
        or len(listed_languages) == 0
        or listed_languages[0] not in SUPPORTED_LANGUAGES
    ):
        # We couldn't find a language mentioned in the title.
        new_language = "Unknown"  # We want to only return stuff for supported since there can be false
    else:
        new_language = listed_languages[0]

    if "[" in title_text and "]" in title_text:
        # If it already has a tag let's take it out.
        title_text = title_text.split("]")[1].strip()

    if (
        str("to " + new_language) in title_text
        or str("in " + new_language) in title_text
        or "from English" in title_text
    ):
        new_tag = f"[English > {new_language}] "
    else:
        new_tag = f"[{new_language} > English] "
    new_title = new_tag + title_text.strip()

    if len(new_title) >= 300:  # There is a hard limit on Reddit title lengths
        new_title = new_title[0:299]  # Shorten it.

    return new_title


def detect_languages_reformat(title_text: str) -> str | None:
    """
    This function tries to salvage a badly formatted title and render it better for the title routine.
    For example, the title may be: `English to Chinese Lorem Ipsum`. This function can take that and reformat it to
    make more sense: `[English > Chinese] Lorem Ipsum`

    :param title_text: The title to evaluate and reformat.
    :return: None if it is unable to make sense of it, a reformatted title otherwise.
    """

    title_words_selected = {}  # Create a dictionary
    new_title_text = ""
    language_check = last_language = None
    title_words = re.compile(r"\w+").findall(title_text)

    title_words_reversed = list(reversed(title_words))

    for word in title_words[:7]:
        if word.lower() == "to":
            continue

        language_check = language_mention_search(word.title())
        if language_check is not None:
            title_words_selected[word] = language_check[0]

    for word in title_words_reversed[-7:]:
        # Check to see if there are languages in the title
        language_check = language_mention_search(word.title())
        if language_check is not None:  # There are languages mentioned
            last_language = language_check[0]  # this is the last language mentioned
            break

    if language_check is None or len(title_words_selected) == 0:
        return None

    for key in sorted(title_words_selected.keys()):
        if str(key) == title_words[0]:
            new_title_text = title_text.replace(key, "[" + title_words_selected[key])

    for key in sorted(title_words_selected.keys()):
        if title_words_selected[key] == last_language:
            # add a bracket to the last found language
            new_title_text = new_title_text.replace(
                key, title_words_selected[key] + "] "
            )

    if " to " in new_title_text:
        new_title_text = new_title_text.replace(" to ", " > ")
    elif " into " in new_title_text:
        new_title_text = new_title_text.replace(" into ", " > ")

    return new_title_text or None


def app_multiple_definer(title_text: str) -> bool:
    """
    This function takes in a title text and returns a boolean as to whether it should be given the 'App' code.
    This is only applicable for 'multiple' posts.

    :param title_text: A title of a Reddit post to evaluate. This will one that would otherwise be a "Multiple" post.
    :return: True if it *should* be given the 'App' code, False otherwise.
    """

    title_text = title_text.lower()
    return any(keyword in title_text for keyword in APP_WORDS)


def both_non_english_detector(source_language, target_language):
    """
    This function evaluates two lists of languages: One list is source languages, one list is target languages.
    Its purpose is to evaluate if it is a true request for two non-English requests (e.g. [French > Catalan])
    If it detects "English" in both lists, though, then it's not a true non-English request since the user can accept
    English as one of their options.
    The importance of this is because Ziwen will send notifications to both languages if the request is non-English.

    :param source_language: A list of source language names for a post.
    :param target_language: A list of target language names for a post.
    :return: A list of the languages for notifying, or None if there's nothing to return.
    """

    all_languages = list(set(source_language + target_language))

    if "English" in all_languages:
        # English is in here, so it CAN'T be what we're looking for.
        return None

    return None if len(all_languages) <= 1 else all_languages


def determine_title_direction(
    source_languages_list: List[str], target_languages_list: List[str]
) -> str:
    """
    Function takes two language lists and determines what the direction of the request is.
    This statistic is stored in Ajos and Wenyuan uses it for statistics as well.

    :param source_languages_list: A list of languages that are determined to be the source.
    :param target_languages_list: A list of languages that are determined to be the target.
    :return: One of four variables: (english_from, english_to, english_both, english_none)
    """

    # Create local lists to avoid changing the main function's lists
    source_languages_local = list(source_languages_list)
    target_languages_local = list(target_languages_list)

    # Exception to be made for languages with 'English' in their name like "Middle English"
    # Otherwise it will always return 'english_both'
    if (
        all("English" in item for item in source_languages_local)
        and len(source_languages_local) > 1
    ):
        source_languages_local.remove("English")
    elif (
        all("English" in item for item in target_languages_local)
        and len(target_languages_local) > 1
    ):
        target_languages_local.remove("English")

    if (
        "English" in source_languages_local and "English" in target_languages_local
    ):  # It's in both
        combined_list = source_languages_local + target_languages_local
        if len(list(combined_list)) >= 3:  # It's pretty long
            if len(source_languages_local) >= 2:
                source_languages_local.remove("English")
            elif len(target_languages_local) >= 2:
                target_languages_local.remove("English")

    if "English" in source_languages_local and "English" not in target_languages_local:
        return "english_from"
    if "English" in target_languages_local and "English" not in source_languages_local:
        return "english_to"
    if "English" in target_languages_local and "English" in source_languages_local:
        return "english_both"
    return "english_none"


def final_title_salvager(d_source_languages: List[str], d_target_languages: List[str]):
    """
    This function takes two list of languages and tries to salvage SOMETHING out of them. This is used for titles
    that are just plain incomprehensible and is a last-ditch function by title_format() below.

    :param d_source_languages: A list of languages that are determined to be the source.
    :param d_target_languages: A list of languages that are determined to be the target.
    :return: None if it's unable to comprehend the list of languages. A tuple with a CSS code and text otherwise.
    """

    all_languages = d_source_languages + d_target_languages  # Combine the two
    # Remove the generic ones.
    all_languages = [x for x in all_languages if x not in ["Generic", "English"]]

    if len(all_languages) is None:  # No way of saving this.
        return None
    # We can get a last language classification
    try:
        converter_output = converter(all_languages[0])
        return converter_output.language_code, converter_output.language_name
    except IndexError:
        return None


def title_format(title: str, display_process: bool = False):
    """
    This is the main function to help format a title and to determine information from it.
    The creation of Ajos relies on this process, and the flair and flair text that's assigned to an incoming post is
    also determined by this central function.

    This is also a rather unruly function because it's probably the function that been added to and extended the most.

    :param display_process: is a boolean that allows us to see the steps taken (a sort of debug mode, Wenyuan uses it).
    :param title: The title of the r/translator post to evaluate.
    :return: d_source_languages: A list of languages that the function determines are the source.
             d_target_languages: A list of languages that the function determines are the target.
             final_css: The determination of what CSS code the title should get (usually the language's code).
             final_css_text: The determination of what CSS text the title should get (usually the language name).
             actual_title: The title of the post minus its language tag.
             processed_title: The title of the post as processed by the routine (including modifications by other
                              functions listed above).
             notify_languages: (optional) If there are more languages to notify for than just the main one.
             language_country: (optional) A country specified for the language, e.g. Brazil for Portuguese.
             direction: What translation direction (relative to English) the post is for.
    """

    source_language = target_language = country_suffix_code = ""  # Set defaults
    final_css = "generic"
    final_code_tag = final_css.title()

    has_country = False
    notify_languages = None

    # Strip cross-post formatting, which happens at the end.
    if "(x-post" in title:
        title = title.split("(x-post")[0].strip()

    for spelling in MAIN_LANGUAGES["en"][
        "alternate_names"
    ]:  # Replace typos or misspellings in the title for English.
        if spelling in title.title():  # Misspelling is in the title.
            title = title.replace(spelling, "English")

    if "english" in title:
        title = title.replace("english", "English")

    if (
        "Old English" in title
    ):  # Small tweak to ensure Old English works properly. We convert it to "Anglo-Saxon"
        title = title.replace("Old English", "Anglosaxon")
    elif "Anglo-Saxon" in title:
        title = title.replace("Anglo-Saxon", "Anglosaxon")
    elif "Scots Gaelic" in title:
        title = title.replace("Scots Gaelic", "Scottish Gaelic")

    # Let's replace any problematic characters or formatting early. Especially those that are important to splitting.
    if any(
        keyword in title for keyword in WRONG_DIRECTIONS
    ):  # Fix for some Unicode arrow-looking thingies
        for keyword in WRONG_DIRECTIONS:
            title = title.replace(keyword, " > ")
    if any(
        keyword in title for keyword in WRONG_BRACKETS_LEFT
    ):  # Fix for some Unicode left bracket-looking thingies
        for keyword in WRONG_BRACKETS_LEFT:
            title = title.replace(keyword, " [")
    if any(
        keyword in title for keyword in WRONG_BRACKETS_RIGHT
    ):  # Fix for some Unicode right bracket-looking thingies
        for keyword in WRONG_BRACKETS_RIGHT:
            title = title.replace(keyword, "] ")

    if ">" not in title and " to " in title.lower():
        title = title.replace(" To ", " to ")
        title = title.replace(" TO ", " to ")
        title = title.replace(" tO ", " to ")

    if "]" not in title and "[" not in title and re.match(r"\((.+(>| to ).+)\)", title):
        # This is for cases where we have no square brackets but we have a > or " to " between parantheses instead.
        # print("Replacing parantheses...")
        # We only want to replace the first occurence.
        title = title.replace("(", "[", 1)
        title = title.replace(")", "]", 1)
    elif "]" not in title and "[" not in title and re.match(r"{(.+(>| to ).+)}", title):
        # This is for cases where we have no square brackets but we have a > or " to " between curly braces instead.
        # print("Replacing braces...")
        # We only want to replace the first occurence.
        title = title.replace("{", "[", 1)
        title = title.replace("}", "]", 1)

    if (
        "]" not in title and "[" not in title
    ):  # Otherwise try to salvage it and reformat it.
        reformat_example = detect_languages_reformat(title)
        if reformat_example is not None:
            title = reformat_example

    # Some regex magic, replace things like [Language] >/- [language]
    title = re.sub(r"(\]\s*[>\\-]\s*\[)", " > ", title)

    # Code for taking out the country (most likely from cross-posts)
    if (
        "{" in title and "}" in title and "[" in title
    ):  # Probably has a country name in it.
        has_country = True
        country_suffix_name = re.search(r"{(\D+)}", title)
        country_suffix_name = country_suffix_name.group(1)  # Get the Country name only
        country_suffix_code = country_converter(country_suffix_name)[0]
        if len(country_suffix_code) != 0:  # There was a good country code.
            # Now we want to take out the country from the title.
            title_first = title.split("{", 1)[0].strip()
            title_second = title.split("}", 1)[1]
            title = title_first + title_second
    elif "{" in title and "[" not in title:  # Probably a malformed tag. let's fix it.
        title = title.replace("{", "[")
        title = title.replace("}", "]")

    # Adapting for "English -" type situations
    if "-" in title[0:20] and any(
        keyword in title.title() for keyword in ENGLISH_DASHES
    ):
        title = title.replace("-", " > ")

    if "[" in title and "[" not in title[0:10]:
        # There's a bracketed part, but it's not at the beginning, so it's probably at the end.
        # Let's transpose it.
        title = transbrackets_new(title.strip())

    if "]" not in title and "English." in title:
        title = title.replace("English.", "English] ")
        title = "[" + title

    if "_" in title:  # Let's replace underscores with proper spaces.
        title = title.replace("_", " ")

    if "-" in title[0:25]:
        # Let's replace dashes with proper spaces. Those that still remain after conversion
        # Try to match a hyphenated word (Puyo-Paekche)
        hyphen_match = re.search(r"((?:\w+-)+\w+)", title)
        if hyphen_match is not None:
            hyphen_match = hyphen_match.group(0)
            # Check to see if it's a valid language name
            hyphen_match_name = converter(hyphen_match).language_name
            if len(hyphen_match_name) == 0:
                # No language match found, let's replace the dash with a space.
                title = title.replace("-", " ")

    for character in ["&", "+", "/", "\\", "|"]:
        if character in title:  # Straighten out punctuation.
            title = title.replace(character, f" {character} ")

    for compound in [">>>", ">>", "> >"]:
        if compound in title:
            title = title.replace(compound, " > ")

    if ">" in title and "English" in title and "]" not in title and "[" not in title:
        # This is to help solve cases where people forget to put the brackets.
        title = title.replace("English", "English]")
        title = "[" + title

    if ">" not in title:
        if "- Eng" in title[0:25] or "-Eng" in title[0:25]:
            # People sometimes use a dash instead of a bracket.
            title = title.replace("-", " > ")
        if " into " in title[0:30]:
            title = title.replace("into", ">")

    if "KR " in title.upper()[0:10]:
        # KR is technically Kanuri but no one actually means it to be Kanuri.
        title = title.replace("KR ", "Korean ")

    # If all people write is [Unknown], account for that, and just send it back right away.
    if "[Unknown]" in title.title():
        actual_title = title.split("]", 1)[1]
        return (
            ["Unknown"],
            ["English"],
            "unknown",
            "Unknown",
            actual_title,
            title,
            None,
            None,
            "english_to",
        )
    if "???" in title[0:5] or "??" in title[0:4] or "?" in title[0:3]:
        # This is if the first few characters are just question marks...
        return (
            ["Unknown"],
            ["English"],
            "unknown",
            "Unknown",
            title.split("]")[1] if "]" in title else "",
            title,
            None,
            None,
            "english_to",
        )

    if display_process:
        print("\n## Title as Processed:")
        print(title)

    if ">" in title:
        source_language = title.split(">")[0]
    elif " to " in title.lower()[0:50] and ">" not in title:
        source_language = title.split(" to ")[0]
    elif "-" in title and ">" not in title and "to" not in title[0:50]:
        source_language = title.split("-")[0]
    elif "<" in title and ">" not in title:
        source_language = title.split(">")[0]

    source_language = re.sub(
        r"""
                           [,.;@#?!&$()\[\]/“”’"•]+  # Accept one or more copies of punctuation
                           \ *           # plus zero or more copies of a space,
                           """,
        " ",  # and replace it with a single space
        source_language,
        flags=re.VERBOSE,
    )
    source_language = source_language.title()
    source_language = (
        source_language_original
    ) = source_language.split()  # Convert it from a string to a list

    # If there are two or three words only in source language, concatenate them to see if there's another that exists...
    # (e.g. American Sign Language)
    if len(source_language) >= 2 and source_language[1].strip() != "-":
        source_language.append(" ".join(source_language))

    # Remove two/three letter words that can be misconstrued as ISO codes
    source_language = [
        x
        for x in source_language
        if x not in ENGLISH_2_WORDS and x not in ENGLISH_3_WORDS
    ]

    if display_process is True:
        print("\n## Source Language Strings:")
        print(source_language)

    d_source_languages = []  # Account for misspellings
    for language in source_language:
        if "Eng" in language.title() and len(language) <= 8:
            # If it's just English, we can assign it already.
            language = "English"
        converter_search = converter(language).language_name
        if converter_search != "":
            # Try to get only the valid languages. Delete anything that isn't a language.
            d_source_languages.append(converter_search)
    d_source_languages = list(set(d_source_languages))  # Remove duplicates
    if len(d_source_languages) == 0:
        # If we are unable to find a source language, leave it blank
        d_source_languages = ["Generic"]

    processed_title = title

    if display_process is True:
        print("\n## Final Determined Source Languages:")
        print(d_source_languages)

    # Start processing TARGET languages
    split_chars = [">", " to ", "-", "<"]
    replace_chars = ",/+]).:"
    for split_char in split_chars:
        if split_char in title.lower():
            title = title[title.find(split_char) + len(split_char) :]
            # Split it at the tag boundary and take the first part.
            target_language = title.split("]", 1)[0]
            for character in target_language:
                if character in replace_chars:
                    target_language = target_language.replace(character, " ")
            break

    # Replace punctuation in the string. Not yet divided.
    target_language = re.sub(
        r"""
                           [,.;@#?!&$()“”’"\[•]+  # Accept one or more copies of punctuation
                           \ *           # plus zero or more copies of a space,
                           """,
        " ",  # and replace it with a single space
        target_language,
        flags=re.VERBOSE,
    )

    target_language = target_language.split()  # Divide into words

    target_language = [x.title() for x in target_language]
    # Check for a hyphenated word.. like Puyo-Paekche

    if len(target_language) >= 2:
        # If there are more words, we'll also process the whole string.
        target_language.append(" ".join(target_language))
    # Take away white space
    target_language = target_language_original = [x.strip() for x in target_language]

    # Account for English words that are also ISO codes, in malformed titles. It'll remove it from the list. Should be okay with full names.
    target_language = [
        x
        for x in target_language
        if x not in ENGLISH_2_WORDS and x not in ENGLISH_3_WORDS
    ]

    if display_process is True:
        print("\n## Target Language Strings:")
        print(target_language)

    d_target_languages = []  # Account for misspellings

    for language in target_language:
        converter_target_search = converter(language).language_name
        if converter_target_search != "":
            # Try to get only the valid languages. Delete anything that isn't a language.
            d_target_languages.append(converter_target_search)
    # Remove duplicates (Like "Mandarin Chinese")
    d_target_languages = list(set(d_target_languages))
    if len(d_target_languages) == 0:
        # If we are unable to find a target language, leave it blank
        d_target_languages = ["Generic"]

    # If there's more than 1, and english is in both of them, then take out english!
    if (
        all("English" in item for item in d_target_languages)
        and len(d_target_languages) >= 2
        and "English" in d_target_languages
    ):
        d_target_languages.remove("English")

    if display_process is True:
        print("\n## Final Determined Target Languages:")
        print(d_target_languages)

    both_test_languages = both_non_english_detector(
        d_source_languages, d_target_languages
    )
    if both_test_languages is not None:
        # Check to see if there are two non-English things
        notify_languages = both_test_languages
    # By this point, we have the source and target languages broken up into two separate lists.
    # Now we determine what CSS class to give this post.

    if "English" in d_target_languages and "English" not in d_source_languages:
        # If the target language is English, we want to give it a source language CSS.
        if len(d_source_languages) >= 2:
            # Prioritize other than Unknown/English, take it out.
            if (
                "Unknown" in d_source_languages
                or "English" in d_source_languages
                or "Multiple Languages" in d_source_languages
            ):
                # We want to allow the guess to be the CSS.
                d_source_languages_m = [
                    x
                    for x in d_source_languages
                    if x not in ["Unknown", "English", "Multiple Languages"]
                ]
                if len(d_source_languages_m) == 0:  # Uh-oh, we deleted everything.
                    d_source_languages_m = list(d_source_languages)
            else:
                d_source_languages_m = list(d_source_languages)

            complete_override = False  # Defaults
            complete_source = ""

            # Do we have a language that is a complete match? (e.g. Tunisian Arabic)
            for language in d_source_languages_m:
                # Is the complete match in the languages list?
                if language == source_language[-1]:  # It matches!
                    complete_override = True
                    complete_source = language
                    continue

            if not complete_override:
                final_css = converter(str(d_source_languages_m[0])).language_code
            elif complete_override:  # Override.
                final_css = converter(complete_source).language_code
        else:  # every other case
            final_css = converter(str(d_source_languages[0])).language_code
    elif "English" in d_source_languages and "English" not in d_target_languages:
        # If the source language is English, we want to give it a target language CSS.
        final_css = converter(str(d_target_languages[0])).language_code
        if len(d_target_languages) > 1:
            # We do a test to see if there's a specific target, e.g. Egyptian Arabic
            joined_target = target_language[-1]  # Get the last full string.
            joined_target_data = converter(joined_target)
            if len(joined_target_data.language_code) != 0:
                # The converter actually found a specific language code for this.
                final_css = joined_target_data.language_code
                d_target_languages = [joined_target_data.language_name]
    elif "English" in d_source_languages and "English" in d_target_languages:
        # English is in both areas here.
        combined_total = list(set(d_source_languages + d_target_languages))
        combined_total.remove("English")
        if len(combined_total) > 0:  # There's still a Non English item here
            final_css = converter(combined_total[0]).language_code
        else:
            final_css = "en"  # Obviously it was just English

    # Check to see if there is an "or" in the target languages
    # Split it at the tag boundary and take the first part.
    test_chunk = title.split("]", 1)[0]
    # See if there are languages considered optional
    # Type O means that in this sort of case we should really be taking the default
    type_o = " or " in test_chunk.lower() and len(d_target_languages) < 6

    # Check for the direction.
    direction = determine_title_direction(d_source_languages, d_target_languages)

    if len(d_target_languages) >= 2:  # Test to see if it has multiple target languages
        is_multiple_test = list(d_target_languages)
        for name in ["English", "Multiple Languages"]:
            # We want to remove these to see if there really is many targets
            if name in d_target_languages:
                is_multiple_test.remove(name)

        # Check to see if there's a script here
        for language in is_multiple_test:
            code = converter(language).language_code
            if len(code) == 4:  # This is a script
                is_multiple_test.remove(language)

        if len(is_multiple_test) >= 2 and "English" not in d_target_languages:
            # Looks like it really does have more than two non-English target languages.
            final_css = "multiple"  # Then we assign it the "multiple" CSS
            notify_languages = d_target_languages

    language_country = None

    if not has_country:  # There isn't a country digitally in the source language part.
        # Now we check for regional variations.
        source_country_data = country_validator(
            source_language_original, d_source_languages
        )
        target_country_data = country_validator(
            target_language_original, d_target_languages
        )

        if source_country_data is not None or target_country_data is not None:
            # There's data from the country detector
            if source_country_data is not None:
                language_country = source_country_data[0]  # Data like en-US
                # The ISO 639-3 code if exists
                language_country_code = source_country_data[1]
                if (
                    len(d_source_languages) == 1
                    and language_country_code is not None
                    and "English" in d_target_languages
                ):
                    # There is only one source language. Let's replace it with the determined one.
                    # This is also assuming English is the target language.
                    d_source_languages = [
                        converter(language_country_code).language_name
                    ]
                    final_css = language_country_code  # Change it to the ISO 639-3 code
                    # final_css_text = d_source_languages[0]
                    # print(d_source_languages)
                elif (
                    "English" not in d_target_languages and language_country is not None
                ):
                    # Situations where both are non-English
                    # Just take the language code.
                    final_css = language_country.split("-", 1)[0]
            elif target_country_data is not None:
                language_country = target_country_data[0]  # Data like en-US
                language_country_code = target_country_data[
                    1
                ]  # The ISO 639-3 code if exists
                if (
                    len(d_target_languages) == 1
                    and language_country_code is not None
                    and "English" in d_source_languages
                ):
                    # There is only one source language. Let's replace it with the determined one.
                    # This is also assuming English is the target language.
                    d_target_languages = [
                        converter(language_country_code).language_name
                    ]
                    final_css = language_country_code  # Change it to the ISO 639-3 code
                    # print(d_target_languages)
                elif (
                    "English" not in d_source_languages and language_country is not None
                ):
                    # Situations where both are non-English
                    final_css = language_country.split("-", 1)[0]
    elif len(country_suffix_code) != 0 and len(final_css) == 2 or len(final_css) == 3:
        language_country = f"{final_css}-{country_suffix_code}"

    if len(final_css) != 4:  # This is not a script
        # Get the flair text for inclusion.
        final_css_text = converter(final_css).language_name
        if (
            language_country is not None
            and len(language_country) != 0
            and language_country not in ISO_LANGUAGE_COUNTRY_ASSOCIATED
            and final_css != "multiple"
        ):
            # There is a country suffix to include, let's add it to the flair. Not if it's its own langauge code though
            # Add the country code to the output flair
            final_css_text += " {{{}}}".format(language_country[-2:])
    else:  # This is a script
        final_css_text = f"{lang_code_search(final_css, True)[0]} (Script)"
        # Returns a category like unknown-cyrl for notifications
        language_country = f"unknown-{final_css}"

    if (
        notify_languages is not None
        and len(notify_languages) >= 2
        and final_css == "multiple"
    ):
        # Format Multiple Languages with language tags too!
        multiple_code_tag = []
        for language in notify_languages:
            # Get the code from the name
            multiple_code_tag.append(converter(language).language_code.upper())
            multiple_code_tag = sorted(multiple_code_tag)  # Alphabetize
            if "MULTIPLE" in multiple_code_tag:
                multiple_code_tag.remove("MULTIPLE")
            if "UNKNOWN" in multiple_code_tag:
                multiple_code_tag.remove("UNKNOWN")
            # This gives us the string without brackets.
            multiple_code_tag_string = ", ".join(multiple_code_tag)
            # The limit for link flair text is 64 characters. we need to trim.
            if len(multiple_code_tag_string) > 34:
                multiple_code_tag_short = []
                for tag in multiple_code_tag:
                    if len(", ".join(multiple_code_tag_short)) <= 30:
                        multiple_code_tag_short.append(tag)
                multiple_code_tag = multiple_code_tag_short
            final_code_tag = " [" + ", ".join(multiple_code_tag) + "]"
        final_css_text = final_css_text + final_code_tag

    if type_o and final_css == "multiple":
        # This is one where the target languages may not be what we want MULTIPLE.
        if "English" in d_source_languages:
            # The source is English, so let's choose a target css
            final_css = converter(d_target_languages[0]).language_code
            # we will send the multiple notifications, just in case.
            final_css_text = d_target_languages[0]
        else:  # English is in the targets, so let's take the source.
            final_css = converter(d_source_languages[0]).language_code
            final_css_text = d_source_languages[0]  # Just the name
            # Clear the notifications, we don't need them for this one.
            notify_languages = None

    if final_css not in SUPPORTED_CODES and len(final_css) != 4:
        # It's not a supported css and also not a language
        # If we don't have link flair for it, give it a generic linkflair
        final_css = "generic"
    elif len(final_css) == 4:  # It's a script code
        final_css = "unknown"

    # Now we try to get the title. Not really important, but could be useful in the future.
    actual_title = ""

    if "]" in title:
        actual_title = str(title.split("]", 1)[1]).strip()
    elif "English" in title and "]" not in title:
        actual_title = str(title.split("English", 1)[1]).strip()

    if actual_title != "" and actual_title[0] in ["])>,.:"]:
        # Try to properly format the "real title"
        actual_title = actual_title[1:].strip()

    # We calculate whether or not this is an app. This is only applicable to Multiple posts
    if final_css == "multiple":
        app_yes = app_multiple_definer(actual_title)
        if app_yes:  # It looks like it's an app.
            final_css = "app"
            final_css_text = final_css_text.replace("Multiple Languages", "App")
            if d_target_languages == ["Multiple Languages"]:
                d_target_languages = ["App"]

    # Our final attempt to wring something proper out of something that is all generic
    if final_css == "generic" and final_css_text == "Generic":
        salvaged_data = final_title_salvager(d_source_languages, d_target_languages)
        if salvaged_data is not None:
            final_css = salvaged_data[0]
            final_css_text = salvaged_data[1]

    return (
        d_source_languages,
        d_target_languages,
        final_css,
        final_css_text,
        actual_title,
        processed_title,
        notify_languages,
        language_country,
        direction,
    )


def language_list_splitter(list_string: List[str]):
    """
    A function to help split up lists of codes or names of languages with different delimiters.
    An example would be a string like `ar, latin, yi` or `ko+lo`. This function will be able to split it no matter what.

    :param: A possible list of languages as a string.
    :return: A list of language codes that were determined from the string. None if there are no valid ones found.
    """

    final_codes = []

    if "LANGUAGES:" in list_string:  # Remove colon, partition the part we need.
        list_string = list_string.rpartition("LANGUAGES:")[-1].strip()
    else:
        list_string = list_string.strip()  # Remove spaces.

    # Set delimiters and divide. Delimiters: `+`, `,`, `/`, `\n`, ` `. The space is the last resort.
    standard_delimiters = ["+", "\n", "/", ":", ";"]
    for character in standard_delimiters:  # Iterate over our list.
        if character in list_string:
            list_string = list_string.replace(character, ",")

    # Special case if there's only spaces - check to see if the whole thing
    if "," not in list_string and " " in list_string:
        # Assess whether the whole thing is a multi-word language itself.
        all_match = converter(list_string).language_code
        temporary_list = list_string.split() if len(all_match) == 0 else [all_match]
    else:
        # Get the individual elements with a first pass.
        temporary_list = list_string.split(",")

    temporary_list = [x.strip() for x in temporary_list if x]  # Remove blank strings.
    utility_codes = ["meta", "community"]
    # Clean up and get the codes.
    for item in temporary_list:
        item = item.lower()  # Remove spaces.

        # Get the code.
        converted_data = converter(item)

        if (
            converted_data.country_code is None
        ):  # This has no country data attached to it.
            code = converted_data.language_code
        else:
            code = f"{converted_data.language_code}-{converted_data.country_code}"

        if len(code) != 0 and item != "all":
            final_codes.append(code)
        elif item == "all":  # This is to help process 'all' unsubscription requests.
            final_codes.append(item)
        elif item in utility_codes:
            final_codes.append(item)

    # Remove duplicates and alphabetize.
    final_codes = list(set(final_codes))
    final_codes = sorted(final_codes, key=str.lower)

    return None if len(final_codes) == 0 else final_codes


def main_posts_filter_required_keywords() -> Dict[str, List[str]]:
    """
    This function takes the language name list and a series of okay words for English and generates a list of keywords
    that we can use to enforce the formatting requirements. This is case-insensitive and also allows more flexibility
    for non-English requests.

    :return: A dictionary with two keys: `total`, and `to_phrases`.
    """

    possible_strings = {"total": [], "to_phrases": []}

    # Create a master list of words for "English"
    words_for_english = ["english", "en", "eng", "englisch", "англи́йский", "英語", "英文"]

    # Create a list of connecting words between languages.
    words_connection = [">", "to", "<", "〉", "›", "》", "»", "⟶", "→", "~"]

    # Add to the list combinations with 'English' that are allowed.
    for word in words_for_english:
        for connector in words_connection:
            temporary_list = [
                f" {connector} {word}",
                f"{word} {connector} ",
            ]

            if connector != "to":
                temporary_list.append(f"{connector}{word}")
                temporary_list.append(f"{word}{connector}")
            else:
                possible_strings["to_phrases"] += temporary_list
            possible_strings["total"] += temporary_list

    # Add to the list combinations with language names that are allowed.
    for language in SUPPORTED_LANGUAGES:
        language_lower = language.lower()
        for connector in words_connection:
            temporary_list = [
                f" {connector} {language_lower}",
                f"{language_lower} {connector} ",
            ]

            if connector != "to":
                temporary_list.append(f"{connector}{language_lower}")
                temporary_list.append(f"{language_lower}{connector}")
            else:
                possible_strings["to_phrases"] += temporary_list
            possible_strings["total"] += temporary_list

    # Add to the list combinations with just dashes.
    added_hyphens = []
    for item in ENGLISH_DASHES:
        added_hyphens.append(item.lower())
    added_hyphens = list(sorted(added_hyphens))

    # Function tags.
    possible_strings["total"] += [">", "[unknown]", "[community]", "[meta]"]
    possible_strings["total"] += added_hyphens

    # Remove false matches. These often get through even though they should not be allowed.
    bad_matches = [
        "ch to ",
        "en to ",
        " to en",
        " to me",
        " to mi",
        " to my",
        " to mr",
        " to kn",
    ]
    possible_strings["to_phrases"] = [
        x for x in possible_strings["to_phrases"] if x not in bad_matches
    ]
    possible_strings["total"] = [
        x for x in possible_strings["total"] if x not in bad_matches
    ]

    return possible_strings


def main_posts_filter(otitle: str):
    """
    A functionized filter for title filtering (removing posts that don't match the formatting guidelines).
    This was decoupled from ziwen_posts in order to be more easily maintained and to allow Wenyuan to use it.

    :param otitle: Any potential or actual r/translator post title.
    :return: post_okay: A boolean determining whether the post fits the community formatting guidelines.
             otitle: A currently unused variable that would potentially allow this function to change the title text.
             filter_reason: If the post violates the rules, the filter_reason is a one/two-letter code indicating
                            what particular formatting rule it violated.
                            1: The title contained none of the required keywords.
                            1A: The title contained a string like "to English" but it was not in the first part of it.
                            1B: The title was super short and generic. (e.g. 'Translation to English')
                            2: The title contained the important symbol `>` but it was randomly somewhere in the title.
                            EE: (not activated here) English-only post. (e.g. 'English > English')
    """

    post_okay = True
    filter_reason = None

    # Obtain a list of keywords that we will allow.
    main_keywords = main_posts_filter_required_keywords()
    mandatory_keywords = main_keywords["total"]
    to_phrases_keywords = main_keywords["to_phrases"]

    if not any(keyword in otitle.lower() for keyword in mandatory_keywords):
        # This is the same thing as AM's content_rule #1. The title does not contain any of our keywords.
        # But first, we'll try to salvage the title into something we can work with.
        # This replaces any bad words for "English"
        otitle = replace_bad_english_typing(otitle)

        # The function below would allow for a lot looser rules but is currently unused.
        """
        otitle = bad_title_reformat(otitle)
        if "[Unknown > English]" in otitle:  # The title was too generic, we ain't doing it.
            print("> Filtered a post out due to incorrect title format. content_rule #1")
            post_okay = False
        """

        if not any(keyword in otitle.lower() for keyword in mandatory_keywords):
            # Try again
            filter_reason = "1"
            print(
                f"[L] Main_Posts_Filter: > Filtered a post with an incorrect title format. Rule: #{filter_reason}"
            )
            post_okay = False
    elif ">" not in otitle and any(
        phrase in otitle.lower() for phrase in to_phrases_keywords
    ):
        # Try to take out titles that bury the lede.
        if not any(phrase in otitle.lower()[:25] for phrase in to_phrases_keywords):
            # This means the "to LANGUAGE" part is probably all the way at the end. Take it out.
            filter_reason = "1A"
            print(
                f"[L] Main_Posts_Filter: > Filtered a post with an incorrect title format. Rule: #{filter_reason}"
            )
            post_okay = False  # Since it's a bad post title, we don't need to process it anymore.

        # Added a Rule 1B, basically this checks for super short things like 'Translation to English'
        # This should only activate if 1A is not triggered.
        if len(otitle) < 35 and filter_reason is None and "[" not in otitle:
            # Find a list of languages that are listed
            listed_languages = language_mention_search(otitle.title())

            # Remove English, we don't need that.
            if listed_languages is not None:
                listed_languages = [x for x in listed_languages if x != "English"]

            # If there's no listed language, then we can filter it out.
            if listed_languages is None or len(listed_languages) == 0:
                filter_reason = "1B"
                post_okay = False
                print(
                    f"[L] Main_Posts_Filter: > Filtered a post with no valid language. Rule: #{filter_reason}"
                )
    if ">" in otitle and "]" not in otitle and ">" not in otitle[0:50]:
        # If people tack on the languages as an afterthought, it can be hard to process.
        filter_reason = "2"
        print(
            f"[L] Main_Posts_Filter: > Filtered a post out due to incorrect title format. Rule: #{filter_reason}"
        )
        post_okay = False

    return post_okay, otitle if post_okay else None, filter_reason
