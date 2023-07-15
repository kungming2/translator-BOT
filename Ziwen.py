#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""
Ziwen [ZW] is the main active component of u/translator-BOT, servicing r/translator and other communities.

Ziwen posts comments and sends messages and also moderates and keeps r/translator organized. It also provides community
members with useful reference information and enforces the community's formatting guidelines.
"""

import calendar
import sqlite3  # For processing and accessing the databases.
import time
import traceback  # For documenting errors that are encountered.
import sys

import praw  # Simple interface to the Reddit API that also handles rate limiting of requests.
import prawcore  # The base module praw for error logging.

import jieba  # Segmenter for Mandarin Chinese.
import MeCab  # Advanced segmenter for Japanese.
import romkan  # Needed for automatic Japanese romaji conversion.
import tinysegmenter  # Basic segmenter for Japanese; not used on Windows.

import googlesearch
import psutil
import requests

from bs4 import BeautifulSoup as Bs
from korean_romanizer.romanizer import Romanizer
from lxml import html
from mafan import simplify, tradify
from wiktionaryparser import WiktionaryParser

from _languages import *
from _config import *
from _responses import *

"""
UNIVERSAL VARIABLES

These variables (all denoted by UPPERCASE names) are variables used by many functions in Ziwen. These are important
as they define many of the basic functions of the bot.
"""

BOT_NAME = "Ziwen"
VERSION_NUMBER = "1.8.27"
USER_AGENT = (
    "{} {}, a notifications messenger, general commands monitor, and moderator for r/translator. "
    "Written and maintained by u/kungming2.".format(BOT_NAME, VERSION_NUMBER)
)
SUBREDDIT = "translator"
TESTING_MODE = False

# This is how many posts Ziwen will retrieve all at once. PRAW can download 100 at a time.
MAXPOSTS = 100
# This is how many seconds Ziwen will wait between cycles. The bot is completely inactive during this time.
WAIT = 30
# After this many cycles, the bot will clean its database, keeping only the latest (CLEANCYCLES * MAXPOSTS) items.
CLEANCYCLES = 90
# How long do we allow people to `!claim` a post? This is defined in seconds.
CLAIM_PERIOD = 28800
# A boolean that enables the bot to send messages. Used for testing.
MESSAGES_OKAY = True
# A number that defines the soft number of notifications an individual will get in a month *per language*.
NOTIFICATIONS_LIMIT = 100

"""KEYWORDS LISTS"""
# These are the commands on r/translator.
KEYWORDS = [
    "!page:",
    "`",
    "!missing",
    "!translated",
    "!id:",
    "!set:",
    "!note:",
    "!reference:",
    "!search:",
    "!doublecheck",
    "!identify:",
    "!translate",
    "!translator",
    "!delete",
    "!claim",
    "!reset",
    "!long",
    "!restore",
]
# These are the words that count as a 'short thanks' from the OP.
# If a message includes them, the bot won't message them asking them to thank the translator.
THANKS_KEYWORDS = [
    "thank",
    "thanks",
    "tyvm",
    "tysm",
    "thx",
    "danke",
    "arigato",
    "gracias",
    "appreciate",
    "solved",
]
# These are keywords that if included with `!translated` will give credit to the parent commentator.
VERIFYING_KEYWORDS = [
    "concur",
    "agree",
    "verify",
    "verified",
    "approve",
    "is correct",
    "is right",
    "well done",
    "well-done",
    "good job",
    "marking",
    "good work",
]
# A cache for language multipliers, generated each instance of running.
# Allows us to access the wiki less and speed up the process.
CACHED_MULTIPLIERS = {}


"""
CONNECTIONS TO REDDIT & SQL DATABASES

Ziwen relies on several SQLite3 files to store its data and uses PRAW to connect to Reddit's API.
"""

logger.info("[ZW] Startup: Accessing SQL databases...")

# This connects to the local cache used for detecting edits and the multiplier cache for points.
conn_cache = sqlite3.connect(FILE_ADDRESS_CACHE)
cursor_cache = conn_cache.cursor()

# This connects to the main database, including notifications, points, and past processed data.
conn_main = sqlite3.connect(FILE_ADDRESS_MAIN)
cursor_main = conn_main.cursor()

# This connects to the database for Ajos, objects that the bot generates for posts.
conn_ajo = sqlite3.connect(FILE_ADDRESS_AJO_DB)
cursor_ajo = conn_ajo.cursor()

if len(sys.argv) > 1:  # This is a new startup with additional parameters for modes.
    specific_mode = sys.argv[1].lower()
    if specific_mode == "test":
        TESTING_MODE = True
        SUBREDDIT = "trntest"
        MESSAGES_OKAY = False
        logger.info(
            "[ZW] Startup: Starting up in TESTING MODE for r/{}...".format(SUBREDDIT)
        )

# Connecting to the Reddit API via OAuth.
logger.info("[ZW] Startup: Logging in as u/{}...".format(USERNAME))
reddit = praw.Reddit(
    client_id=ZIWEN_APP_ID,
    client_secret=ZIWEN_APP_SECRET,
    password=PASSWORD,
    user_agent=USER_AGENT,
    username=USERNAME,
)
r = reddit.subreddit(SUBREDDIT)
logger.info(
    "[ZW] Startup: Initializing {} {} for r/{} with languages module {}.".format(
        BOT_NAME, VERSION_NUMBER, SUBREDDIT, VERSION_NUMBER_LANGUAGES
    )
)

"""
MAINTENANCE FUNCTIONS

These functions are run at Ziwen's startup and also occasionally in order to refresh their information. Most of them
fetch data from r/translator itself or r/translatorBOT for internal variables.

Maintenance functions are all prefixed with `maintenance` in their name.
"""


def maintenance_template_retriever():
    """
    Function that retrieves the current flairs available on the subreddit and returns a dictionary.
    Dictionary is keyed by the old css_class, with the long-form template ID as a value per key.
    Example: 'cs': XXXXXXXX

    :return new_template_ids: A dictionary containing all the templates on r/translator.
    :return: An empty dictionary if it cannot find the templates for some reason.
    """

    new_template_ids = {}

    # Access the templates on the subreddit.
    for template in r.flair.link_templates:
        css_associated_code = template["css_class"]
        new_template_ids[css_associated_code] = template["id"]

    # Return a dictionary, if there's data, otherwise return an empty dictionary.
    if len(new_template_ids.keys()) != 0:
        return new_template_ids
    else:
        return {}


def maintenance_most_recent():
    """
    A function that grabs the usernames of people who have submitted to r/translator in the last 24 hours.
    Another function can check against this to make sure people aren't submitting too many.

    :return most_recent: A list of usernames that have recently submitted to r/translator. Duplicates will be on there.
    """

    # Define the time parameters (24 hours earlier from present)
    most_recent = []
    current_vaqt = int(time.time())
    current_vaqt_day_ago = current_vaqt - 86400

    # 100 should be sufficient for the last day, assuming a monthly total of 3000 posts.
    posts = []
    posts += list(r.new(limit=100))

    # Process through them - we really only care about the username and the time.
    for post in posts:
        ocreated = int(post.created_utc)  # Unix time when this post was created.

        try:
            oauthor = post.author.name
        except AttributeError:
            # Author is deleted. We don't care about this post.
            continue

        # If the time of the post is after our limit, add it to our list.
        if ocreated > current_vaqt_day_ago:
            if oauthor != "translator-BOT":
                most_recent.append(oauthor)

    # Return the list
    return most_recent


def maintenance_get_verified_thread():
    """
    Function to quickly get the Reddit ID of the latest verification thread on startup.
    This way, the ID of the thread does not need to be hardcoded into Ziwen.

    :return verification_id: The Reddit ID of the newest verification thread as a string.
    """
    verification_id = ""

    # Search for the latest verification thread.
    search_term = "title:verified AND flair:meta"

    # Note that even in testing ('trntest') we will still search r/translator for the thread.
    search_results = reddit.subreddit("translator").search(
        search_term, time_filter="year", sort="new", limit=1
    )

    # Iterate over the results to get the ID.
    for post in search_results:
        verification_id = post.id

    return verification_id


def maintenance_blacklist_checker():
    """
    A start-up function that runs once and gets blacklisted usernames from the wiki of r/translatorBOT.
    Blacklisted users are those who have abused the subreddit functions on r/translator but are not banned.
    This is an anti-abuse system, and it also disallows them from crossposting with Ziwen Streamer.

    :return blacklist_usernames: A list of usernames on the blacklist, all in lowercase.
    """

    # Retrieve the page.
    blacklist_page = reddit.subreddit("translatorBOT").wiki["blacklist"]
    overall_page_content = str(blacklist_page.content_md)  # Get the page's content.
    usernames_raw = overall_page_content.split("####")[1]
    usernames_raw = usernames_raw.split("\n")[2].strip()  # Get just the usernames.

    # Convert the usernames into a list.
    blacklist_usernames = usernames_raw.split(", ")

    # Convert the usernames to lowercase.
    blacklist_usernames = [item.lower() for item in blacklist_usernames]

    # Exclude AutoModerator from the blacklist.
    blacklist_usernames.remove("automoderator")

    return blacklist_usernames


def maintenance_database_processed_cleaner():
    """
    Function that cleans up the database of processed comments, but not posts (yet).

    :return: Nothing.
    """

    pruning_command = "DELETE FROM oldcomments WHERE id NOT IN (SELECT id FROM oldcomments ORDER BY id DESC LIMIT ?)"
    cursor_main.execute(pruning_command, [MAXPOSTS * 10])
    conn_main.commit()

    return


"""
AJO CLASS/FUNCTIONS

The basic unit of Ziwen's functions is not an individual Reddit post on r/translator per se, but rather, an Ajo.
An Ajo class (from Esperanto aĵo, meaning 'thing') is constructed from a Reddit post but is saved locally and contains 
additional information that cannot be stored on Reddit's system. 
In Ziwen, changes to a post's language, state, etc. are made first to the Ajo. Then a function within the class can
determine its flair, flair text, and template. 

Note: Wenyuan (as of version 3.0) also uses Ajos for its statistics-keeping.

External Ajo-specific/related functions are all prefixed with `ajo` in their name. The Ajo class itself contains several
class functions.
"""


def ajo_defined_multiple_flair_assessor(flairtext):
    """
    A routine that evaluates a defined multiple flair text and its statuses as a dictionary.
    It can make sense of the symbols that are associated with various states of a post.

    :param flairtext: The flair text of a defined multiple post. (e.g. `Multiple Languages [CS, DE✔, HU✓, IT, NL✔]`)
    :return final_language_codes: A dictionary keyed by language and their respective states (translated, claimed, etc)
    """

    final_language_codes = {}
    flairtext = flairtext.lower()

    languages_list = flairtext.split(", ")

    for language in languages_list:
        # Get just the language code.
        language_code = " ".join(re.findall("[a-zA-Z]+", language))

        if len(language_code) != len(
            language
        ):  # There's a difference - maybe a symbol in DEFINED_MULTIPLE_LEGEND
            for symbol in DEFINED_MULTIPLE_LEGEND:
                if symbol in language:
                    final_language_codes[language_code] = DEFINED_MULTIPLE_LEGEND[
                        symbol
                    ]
        else:  # No difference, must be untranslated.
            final_language_codes[language_code] = "untranslated"

    return final_language_codes


def ajo_defined_multiple_flair_former(flairdict):
    """
    Takes a dictionary of defined multiple statuses and returns a string.
    To be used with the ajo_defined_multiple_flair_assessor() function above.

    :param flairdict: A dictionary keyed by language and their respective states.
    :return output_text: A string for use in the flair text. (e.g. `Multiple Languages [CS, DE✔, HU✓, IT, NL✔]`)
    """

    output_text = []

    for key, value in flairdict.items():  # Iterate over each item in the dictionary.
        # Try to get the ISO 639-1 if possible
        language_code = iso639_3_to_iso639_1(key)
        if language_code is None:  # No ISO 639-1 code
            language_code = key

        status = value
        symbol = ""

        for key2, value2 in DEFINED_MULTIPLE_LEGEND.items():
            if value2 == status:
                symbol = key2
                continue

        format_type = "{}{}".format(language_code.upper(), symbol)

        output_text.append(format_type)

    output_text = list(sorted(output_text))  # Alphabetize
    output_text = ", ".join(output_text)  # Create a string.
    output_text = "[{}]".format(output_text)

    return output_text


def ajo_defined_multiple_comment_parser(pbody, language_names_list):
    """
    Takes a comment and a list of languages and looks for commands and language names.
    This allows for defined multiple posts to have separate statuses for each language.
    We don't keep English though.

    :param pbody: The text of a comment on a defined multiple post we're searching for.
    :param language_names_list: The languages defined in the post (e.g. [CS, DE✔, HU✓, IT, NL✔])
    :return: None if none found, otherwise a tuple with the language name that was detected and its status.
    """

    detected_status = None

    status_keywords = {
        KEYWORDS[2]: "missing",
        KEYWORDS[3]: "translated",
        KEYWORDS[9]: "doublecheck",
        KEYWORDS[14]: "inprogress",
    }

    # Look for language names.
    detected_languages = language_mention_search(pbody)

    # Remove English if detected.
    if detected_languages is not None and "English" in detected_languages:
        detected_languages.remove("English")

    if detected_languages is None or len(detected_languages) == 0:
        return None

    # We only want to keep the ones defined in the spec.
    for language in detected_languages:
        if language not in language_names_list:
            detected_languages.remove(language)

    # If there are none left then we return None
    if len(detected_languages) == 0:
        return None

    for keyword in status_keywords.keys():
        if keyword in pbody:
            detected_status = status_keywords[keyword]

    if detected_status is not None:
        return detected_languages, detected_status


def ajo_retrieve_script_code(script_name):
    """
    This function takes the name of a script, outputs its ISO 15925 code and the name as a tuple if valid.

    :param script_name: The *name* of a script (e.g. Siddham, Nastaliq, etc).
    :return: None if the script name is invalid, otherwise a tuple with the ISO 15925 code and the script's name.
    """

    codes_list = []
    names_list = []

    csv_file = csv.reader(
        open(FILE_ADDRESS_ISO_ALL, "rt", encoding="utf-8"), delimiter=","
    )
    for row in csv_file:
        if len(row[0]) == 4:  # This is a script code. (the others are 3 characters. )
            codes_list.append(row[0])
            names_list.append(
                row[2:][0]
            )  # It is normally returned as a list, so we need to convert into a string.

    if script_name in names_list:  # The name is in the code list
        item_index = names_list.index(script_name)
        item_code = codes_list[item_index]
        item_code = str(item_code)
        return item_code, script_name
    else:
        return None


class Ajo:
    """
    A equivalent of a post on r/translator. Used as an object for Ziwen and Wenyuan to work with for
    consistency with languages and to store extra data.

    The process is: Submission > Ajo (changes made to it) > Ajo.update().
    After a submission has been turned into an Ajo, Ziwen will only work with the Ajo unless it has to update Reddit's
    flair.

    Attributes:

        id: A Reddit submission that forms the base of this class.
        created_utc: The Unix time that the item was created.
        author: The Reddit username of the creator. [deleted] if not found.
        author_messaged: A boolean that marks whether or not the creator has been messaged that their post has been
                         translated.

        type: single, multiple

        country_code: The ISO 3166-2 code of a country associated with the language. None by default.
        language_name: The English name of the post's language, rendered as a string
                       (Note: Unknown, Nonlanguage, and Conlang posts, etc. count as a language_name)
        language_code_1: The ISO 639-1 code of a post's language, rendered as a string. None if non-existent.
        language_code_3: The ISO 639-3 code of a post's language, rendered as a string.
        language_history: The different names the post has been classified as, stored as a list (in sequence)

        status: The current situation of the post. untranslated, translated, needs review, in progress, or missing.
        title: The title of the post, minus the language tag part. Defaults to the reg. title if it's not determinable.
        title_original: The exact Reddit title of the post.
        script_name: The type of script it's classified as (None normally)
        script_code: Corresponding code

        is_supported: Boolean of whether this is a supported CSS class or not.
        is_bot_crosspost: Is it a crosspost from u/translator-BOT?

        is_identified: Is it a changed class?
        is_long: Is it a long post?
        is_script: Is it an Unknown post whose script has been identified?

        original_source_language_name: The ORIGINAL source language(s) it was classified as.
        original_target_language_name: The ORIGINAL target language(s) it was classified as.
        direction: Is the submission to/from English, both/neither.

        output_oflair_css: The CSS class that it should be flaired as.
        output_oflair_text: The text that accompanies it.

        parent_crosspost: If it's a crosspost, what's the original one.

        time_delta:  The time between the initial submission time and it being marked. This is a dictionary.

        Example of an output for flair is German (Identified/Script) (Long)
    """

    # noinspection PyUnboundLocalVariable
    def __init__(
        self, reddit_submission
    ):  # This takes a Reddit Submission object and generates info from it.
        if type(reddit_submission) is dict:  # Loaded from a file?
            logger.debug("[ZW] Ajo: Loaded Ajo from local database.")
            for key in reddit_submission:
                setattr(self, key, reddit_submission[key])
        else:  # This is loaded from reddit.
            logger.debug("[ZW] Ajo: Getting Ajo from Reddit.")
            self.id = reddit_submission.id  # The base Reddit submission ID.
            self.created_utc = int(reddit_submission.created_utc)

            # Create some empty variables that can be used later.
            self.recorded_translators = []
            self.notified = []
            self.time_delta = {}
            self.author_messaged = False

            # try:
            title_data = title_format(reddit_submission.title)

            try:  # Check if user is deleted
                self.author = reddit_submission.author.name
            except AttributeError:
                # Comment author is deleted
                self.author = "[deleted]"

            if reddit_submission.link_flair_css_class in ["multiple", "app"]:
                self.type = "multiple"
            else:
                self.type = "single"

            # oflair_text is an internal variable used to mimic the linkflair text.
            if reddit_submission.link_flair_text is None:  # There is no linkflair text.
                oflair_text = "Generic"
                self.is_identified = (
                    self.is_long
                ) = self.is_script = self.is_bot_crosspost = self.is_supported = False
            else:
                if "(Long)" in reddit_submission.link_flair_text:
                    self.is_long = True
                    # oflair_text = reddit_submission.link_flair_text.split("(")[0].strip()
                else:
                    self.is_long = False

                if (
                    reddit_submission.link_flair_css_class == "unknown"
                ):  # Check to see if there is a script classified.
                    if "(Script)" in reddit_submission.link_flair_text:
                        self.is_script = True
                        self.script_name = (
                            oflair_text
                        ) = reddit_submission.link_flair_text.split("(")[0].strip()
                        self.script_code = ajo_retrieve_script_code(self.script_name)[0]
                        self.is_identified = False
                    else:
                        self.is_script = False
                        self.is_identified = False
                        self.script_name = self.script_code = None
                        oflair_text = "Unknown"
                else:
                    if "(Identified)" in reddit_submission.link_flair_text:
                        self.is_identified = True
                        oflair_text = reddit_submission.link_flair_text.split("(")[
                            0
                        ].strip()
                    else:
                        self.is_identified = False
                        if "(" in reddit_submission.link_flair_text:  # Contains (Long)
                            oflair_text = reddit_submission.link_flair_text.split("(")[
                                0
                            ].strip()
                        else:
                            oflair_text = reddit_submission.link_flair_text

            if title_data is not None:
                self.direction = title_data[8]

                if len(title_data[0]) == 1:
                    # The source language data is converted into a list. If it's just one, let's make it a string.
                    self.original_source_language_name = title_data[0][
                        0
                    ]  # Take the only item
                else:
                    self.original_source_language_name = title_data[0]
                if len(title_data[1]) == 1:
                    # The target language data is converted into a list. If it's just one, let's make it a string.
                    self.original_target_language_name = title_data[1][
                        0
                    ]  # Take the only item
                else:
                    self.original_target_language_name = title_data[1]
                if len(title_data[4]) != 0:  # Were we able to determine a title?
                    self.title = title_data[4]
                    self.title_original = reddit_submission.title
                else:
                    self.title = self.title_original = reddit_submission.title

                if (
                    "{" in reddit_submission.title and "}" in reddit_submission.title
                ):  # likely contains a country name
                    country_suffix_name = re.search(r"{(\D+)}", reddit_submission.title)
                    country_suffix_name = country_suffix_name.group(
                        1
                    )  # Get the Country name only
                    self.country_code = country_converter(country_suffix_name)[
                        0
                    ]  # Get the code (e.g. CH for Swiss)
                elif (
                    title_data[7] is not None and len(title_data[7]) <= 6
                ):  # There is included code from title routine
                    country_suffix = title_data[7].split("-", 1)[1]
                    self.country_code = country_suffix
                else:
                    self.country_code = None

            if self.type == "single":
                if "[" not in oflair_text:  # Does not have a language tag. e.g., [DE]
                    if (
                        "{" in oflair_text
                    ):  # Has a country tag in the flair, so let's take that out.
                        country_suffix_name = re.search(r"{(\D+)}", oflair_text)
                        country_suffix_name = country_suffix_name.group(
                            1
                        )  # Get the Country name only
                        self.country_code = country_converter(country_suffix_name)[0]
                        # Now we want to take out the country from the title.
                        title_first = oflair_text.split("{", 1)[0].strip()
                        title_second = oflair_text.split("}", 1)[1]
                        oflair_text = title_first + title_second

                    converter_data = converter(oflair_text)
                    self.language_history = []  # Create an empty list.

                    if (
                        reddit_submission.link_flair_css_class != "unknown"
                    ):  # Regular thing
                        self.language_name = converter_data[1]
                        self.language_history.append(converter_data[1])
                    else:
                        self.language_name = "Unknown"
                        self.language_history.append("Unknown")
                    if len(converter_data[0]) == 2:
                        self.language_code_1 = converter_data[0]
                    else:
                        self.language_code_3 = converter_data[0]

                    self.is_supported = converter_data[2]

                    if len(converter_data[0]) == 2:  # Find the matching ISO 639-3 code.
                        self.language_code_3 = MAIN_LANGUAGES[converter_data[0]][
                            "language_code_3"
                        ]
                    else:
                        self.language_code_1 = None
                else:  # Does have a language tag.
                    language_tag = reddit_submission.link_flair_text.split("[")[1][
                        :-1
                    ].lower()  # Get the characters

                    if (
                        language_tag != "?" and language_tag != "--"
                    ):  # Non-generic versions
                        converter_data = converter(language_tag)
                        self.language_name = converter_data[1]
                        self.is_supported = converter_data[2]
                        if len(language_tag) == 2:
                            self.language_code_1 = language_tag
                            self.language_code_3 = MAIN_LANGUAGES[language_tag][
                                "language_code_3"
                            ]
                        elif len(language_tag) == 3:
                            self.language_code_1 = None
                            self.language_code_3 = language_tag
                    else:  # Either a tag for an unknown post or a generic one
                        if (
                            language_tag == "?"
                        ):  # Unknown post that has still been processed.
                            self.language_name = "Unknown"
                            self.language_code_1 = None
                            self.language_code_3 = "unknown"
                            self.is_supported = True
                        elif language_tag == "--":  # Generic post
                            self.language_name = None
                            self.language_code_1 = None
                            self.language_code_3 = "generic"
                            self.is_supported = False
            elif (
                self.type == "multiple"
            ):  # If it's a multiple type, let's put the language names etc as lists.
                self.is_supported = True
                self.language_history = []

                # Handle DEFINED MULTIPLE posts.
                if (
                    "[" in reddit_submission.link_flair_text
                ):  # There is a list of languages included in the flair
                    # Return their names from the code.
                    # test_list_string = "Multiple Languages [DE, FR]"
                    multiple_languages = []

                    actual_list = reddit_submission.link_flair_text.split("[")[1][
                        :-1
                    ]  # Get just the codes
                    actual_list = actual_list.replace(
                        " ", ""
                    )  # Take out the spaces in the tag.

                    # Code to replace the special status characters... Not fully sure how it interfaces with the rest
                    for character in DEFINED_MULTIPLE_LEGEND.keys():
                        if character in actual_list:
                            actual_list = actual_list.replace(character, "")

                    new_code_list = actual_list.split(",")  # Convert to a list

                    for code in new_code_list:  # We wanna convert them to list of names
                        code = code.lower()  # Convert to lowercase.
                        code = "".join(re.findall("[a-zA-Z]+", code))
                        multiple_languages.append(
                            converter(code)[1]
                        )  # Append the names of the languages.
                else:
                    multiple_languages = title_data[
                        6
                    ]  # Get the languages that this is for. Will be a list or None.

                # Handle REGULAR MULTIPLE
                if multiple_languages is None:  # This is a catch-all multiple case
                    if reddit_submission.link_flair_css_class == "multiple":
                        self.language_code_1 = self.language_code_3 = "multiple"
                        self.language_name = "Multiple Languages"
                        self.language_history.append("Multiple Languages")
                    elif reddit_submission.link_flair_css_class == "app":
                        self.language_code_1 = self.language_code_3 = "app"
                        self.language_name = "App"
                        self.language_history.append("App")
                elif multiple_languages is not None:
                    self.language_code_1 = []
                    self.language_code_3 = []
                    self.language_name = []
                    self.language_history.append("Multiple Languages")
                    for language in multiple_languages:  # Start creating the lists.
                        self.language_name.append(language)
                        multi_language_code = converter(language)[0]
                        if len(multi_language_code) == 2:
                            self.language_code_1.append(multi_language_code)
                            self.language_code_3.append(
                                MAIN_LANGUAGES[converter(language)[0]][
                                    "language_code_3"
                                ]
                            )
                        elif len(multi_language_code) == 3:
                            self.language_code_1.append(None)
                            self.language_code_3.append(multi_language_code)

            if reddit_submission.link_flair_css_class == "translated":
                self.status = "translated"
            elif reddit_submission.link_flair_css_class == "doublecheck":
                self.status = "doublecheck"
            elif reddit_submission.link_flair_css_class == "inprogress":
                self.status = "inprogress"
            elif reddit_submission.link_flair_css_class == "missing":
                self.status = "missing"
            elif reddit_submission.link_flair_css_class in ["app", "multiple"]:
                # It's a generic one.
                if isinstance(self.language_code_3, str):
                    self.status = "untranslated"
                elif multiple_languages is not None:  # This is a defined multiple
                    #  Construct a status dictionary.(we could also use multiple_languages)
                    actual_list = reddit_submission.link_flair_text.split("[")[1][
                        :-1
                    ]  # Get just the codes
                    self.status = ajo_defined_multiple_flair_assessor(
                        actual_list
                    )  # Pass it to dictionary constructor
            else:
                self.status = "untranslated"

            try:
                original_post_id = (
                    reddit_submission.crosspost_parent
                )  # Check to see if this is a bot crosspost.
                crossposter = reddit_submission.author.name
                if crossposter == "translator-BOT":
                    self.is_bot_crosspost = True
                    self.parent_crosspost = original_post_id[3:]
                else:
                    self.is_bot_crosspost = False
            except AttributeError:  # It's not a crosspost.
                self.is_bot_crosspost = False

    def __eq__(self, other):
        """
        Two Ajos are defined as the same if the dictionary representation of their contents match.

        :param other: The other Ajo we are comparing against.
        :return: A boolean. True if their dictionary contents match, False otherwise.
        """

        return self.__dict__ == other.__dict__

    def set_status(self, new_status):
        """
        Change the status/state of the Ajo - a status like translated, doublecheck, etc.

        :param new_status: The new status for the Ajo to have, defined as a string.
        """
        self.status = new_status

    def set_status_multiple(self, status_language_code, new_status):
        """
        Similar to `set_status` but changes the status of a defined multiple post. This function does this by writing
        its status as a dictionary instead, keyed by the language.

        :param status_language_code: The language code (e.g. `zh`) we want to define the status for.
        :param new_status: The new status for that language code.
        """
        if isinstance(
            self.status, dict
        ):  # Make sure it's something we can actually update
            if (
                self.status[status_language_code] != "translated"
            ):  # Once something's marked as translated stay there.
                self.status[status_language_code] = new_status
        else:
            pass

    def set_long(self, new_long):
        """
        Change the `is_long` boolean of the Ajo, a variable that defines whether it's considered a long post.
        Moderators can call this function with the command `!long`.

        :param new_long: A boolean on whether the post is considered long. True if it is, False otherwise.
        :return:
        """
        self.is_long = new_long

    def set_author_messaged(self, is_messaged):
        """
        Change the `author_messaged` boolean of the Ajo, a variable that notes whether the OP of the post has been
        messaged that it's been translated.

        :param is_messaged: A boolean on whether the author has been messaged. True if they have, False otherwise.
        :return:
        """
        try:
            self.author_messaged = is_messaged
        except AttributeError:
            self.author_messaged = is_messaged

    def set_country(self, new_country_code):
        """
        A function that allows us to change the country code in the Ajo. Country codes are generally optional for Ajos,
        but they can be defined to provide more granular detail (e.g. `de-AO`).

        :param new_country_code: The country code (as a two-letter ISO 3166-1 alpha-2 code) the Ajo should be set as.
        """

        if new_country_code is not None:
            new_country_code = new_country_code.upper()

        self.country_code = new_country_code

    def set_language(self, new_language_code, new_is_identified=False):
        """
        This changes the language of the Ajo. It accepts a language code as well as an identification boolean.
        The boolean is False by default.

        :param new_language_code: The new language code to set the Ajo as.
        :param new_is_identified: Whether or not the `is_identified` boolean of the Ajo should be set to True.
                                  For example, `!identify` commands will set `is_identified` to True, but
                                  moderator `!set` commands won't. Ajos with `is_identified` as True will have
                                  "(Identified)" appended to their flair text.
        :return:
        """

        old_language_name = str(self.language_name)

        if new_language_code not in [
            "multiple",
            "app",
        ]:  # This is just a single type of languyage.
            self.type = "single"
            if len(new_language_code) == 2:
                self.language_name = converter(new_language_code)[1]
                self.language_code_1 = new_language_code
                self.language_code_3 = MAIN_LANGUAGES[new_language_code][
                    "language_code_3"
                ]
                self.is_supported = converter(new_language_code)[2]
            elif len(new_language_code) == 3:
                self.language_name = converter(new_language_code)[1]
                self.language_code_1 = None
                self.language_code_3 = new_language_code

                # Check to see if this is a supported language.
                if new_language_code in MAIN_LANGUAGES:
                    self.is_supported = MAIN_LANGUAGES[new_language_code]["supported"]
                else:
                    self.is_supported = False
            elif new_language_code == "unknown":  # Reset everything
                self.language_name = "Unknown"
                self.language_code_1 = (
                    self.is_script
                ) = self.script_code = self.script_name = None
                self.language_code_3 = "unknown"
                self.is_supported = True
        elif new_language_code in ["multiple", "app"]:  # For generic multiples (all)
            if new_language_code == "multiple":
                self.language_name = "Multiple Languages"
                self.language_code_1 = self.language_code_3 = "multiple"
                self.status = "untranslated"
                self.type = "multiple"
            elif new_language_code == "app":
                self.language_name = "App"
                self.language_code_1 = self.language_code_3 = "app"
                self.status = "untranslated"
                self.type = "multiple"

        try:
            # We do a check here to make sure we are not including the same thing twice.
            # This is to avoid something like ['Unknown', 'Chinese', 'Chinese']
            if self.language_history[-1] != self.language_name:
                self.language_history.append(
                    self.language_name
                )  # Add the new language name to the history.
        except (
            AttributeError,
            IndexError,
        ):  # There was no language_history defined... Let's create it.
            self.language_history = [old_language_name, self.language_name]

        if (
            new_is_identified != self.is_identified
        ):  # There's a change to the identification
            self.is_identified = new_is_identified  # Update with said change

    def set_script(self, new_script_code):
        """
        Change the script (ISO 15924) of the Ajo, assuming it is an Unknown post. This will also now reset the
        flair to Unknown.

        :param new_script_code: A four-letter ISO 15924 code.
        :return:
        """

        self.language_name = "Unknown"
        self.language_code_1 = None
        self.language_code_3 = "unknown"
        self.is_supported = True
        self.is_script = True
        self.script_code = new_script_code
        self.script_name = lang_code_search(new_script_code, True)[
            0
        ]  # Get the name of the script

    def set_defined_multiple(self, new_language_codes):
        """
        This is a function that sets the language of an Ajo to a defined Multiple one.
        Example: Multiple Languages [AR, KM, VI]

        :param new_language_codes: A string of language names or codes, where each element is separated by a `+`.
                                   Example: arabic+khmer+vi
        :return:
        """

        self.type = "multiple"
        old_language_name = str(self.language_name)

        # Divide into a list.
        set_languages_raw = new_language_codes.split("+")
        set_languages_raw = sorted(set_languages_raw, key=str.lower)

        # Set some default values up.
        set_languages_processed_codes = []
        self.status = {}  # self
        self.language_name = []  # self
        self.language_code_1 = []
        self.language_code_3 = []

        # Iterate through to get a master list.
        for language in set_languages_raw:
            code = converter(language)[0]
            name = converter(language)[1]
            if len(code) != 0 and len(name) != 0:
                set_languages_processed_codes.append(code)
                self.language_name.append(name)
                self.status[code] = "untranslated"

        languages_tag_string = ", ".join(
            set_languages_processed_codes
        )  # Evaluate the length of the potential string

        # The limit for link flair text is 64 characters. we need to trim it so that it'll fit the flair.
        if len(languages_tag_string) > 34:
            languages_tag_short = []
            for tag in set_languages_processed_codes:
                if len(", ".join(languages_tag_short)) <= 30:
                    languages_tag_short.append(tag)
                else:
                    continue
            set_languages_processed_codes = list(languages_tag_short)

        # Now we have code to generate a list of language codes ISO 639-1 and 3.
        for code in set_languages_processed_codes:
            if len(code) == 2:
                self.language_code_1.append(code)  # self
                code_3 = MAIN_LANGUAGES[code]["language_code_3"]
                self.language_code_3.append(code_3)
            elif len(code) == 3:
                self.language_code_3.append(code)
                self.language_code_1.append(None)

        try:
            # We do a check here to make sure we are not including the same thing twice.
            # This is to avoid something like ['Unknown', 'Chinese', 'Chinese']
            if self.language_history[-1] != self.language_name:
                self.language_history.append(
                    "Multiple Languages"
                )  # Add the new language name to the history.
        except (
            AttributeError,
            IndexError,
        ):  # There was no language_history defined... Let's create it.
            self.language_history = [old_language_name, "Multiple Languages"]

    def set_time(self, status, moment):
        """
        This function creates or updates a dictionary, marking times when the status/state of the Ajo changed.
        This updates a dictionary where it is keyed by status and contains Unix times of the changes.

        :param status: The status that it was changed to. Translated, for example.
        :param moment: The Unix UTC time when the action was taken. It should be an integer.
        :return:
        """

        try:
            # We check here to make sure the dictionary exists.
            working_dictionary = self.time_delta
        except (
            AttributeError,
            NameError,
        ):  # There was no time_delta defined... Let's create it.
            working_dictionary = {}

        if (
            status not in working_dictionary
        ):  # This status hasn't been recorded. Create it as a key in the dictionary.
            working_dictionary[status] = int(moment)
        else:
            pass

        self.time_delta = working_dictionary

    def add_translators(self, translator_name):
        """
        A function to add the username of who translated what to the Ajo of a post (by appending their name to list).
        This allows Ziwen to keep track of translators and contributors.

        :param translator_name: The name of the individual who made the translation.
        :return:
        """

        try:
            if (
                translator_name not in self.recorded_translators
            ):  # The username isn't already in it.
                self.recorded_translators.append(
                    translator_name
                )  # Add the username of the translator to the Ajo.
                logger.debug(
                    "[ZW] Ajo: Added translator name u/{}.".format(translator_name)
                )
        except (
            AttributeError
        ):  # There were no translators defined in the Ajo... Let's create it.
            self.recorded_translators = [translator_name]

    def add_notified(self, notified_list):
        """
        A function to add usernames of who has been notified by the bot of a post.
        This allows Ziwen to make sure it doesn't contact people more than once for a post.

        :param notified_list: A LIST of usernames who have been contacted regarding a post.
        :return:
        """

        try:
            for name in notified_list:
                if name not in self.notified:
                    self.notified.append(name)
                    logger.debug(("[ZW] Ajo: Added notified name u/{}.".format(name)))
        except AttributeError:  # There were no notified users defined in the Ajo.
            self.notified = notified_list

    def reset(self, original_title):
        """
        A function that will completely reset it to the original specifications. Not intended to be used often.
        Moderators and OPs can call this with `!reset` to make Ziwen reprocess its flair and languages.

        :param original_title: The title of the post.
        :return:
        """

        self.language_name = title_format(original_title)[3]
        self.status = "untranslated"
        self.time_delta = {}  # Clear this dictionary.
        self.is_identified = False

        if title_format(original_title)[2] in ["multiple", "app"]:
            is_multiple = True
        else:
            is_multiple = False

        provisional_data = converter(self.language_name)  # This is a temporary code
        self.is_supported = provisional_data[2]
        provisional_code = provisional_data[0]
        provisional_country = provisional_data[3]

        if not is_multiple:
            self.type = "single"
            if len(provisional_code) == 2:  # ISO 639-1 language
                self.language_code_1 = provisional_code
                self.language_code_3 = MAIN_LANGUAGES[provisional_code][
                    "language_code_3"
                ]
                self.country_code = provisional_country
            elif (
                len(provisional_code) == 3
                or provisional_code == "unknown"
                and provisional_code != "app"
            ):
                # ISO 639-3 language or Unknown post.
                self.language_code_1 = None
                self.language_code_3 = provisional_code
                self.country_code = provisional_country
                if (
                    provisional_code == "unknown"
                ):  # Fill in the special parameters for Unknown posts.
                    self.is_script = False
                    self.script_code = None
                    self.script_name = None
            elif len(provisional_code) == 4:  # It's a script
                self.language_code_1 = None
                self.language_code_3 = "unknown"
                self.is_script = True
                self.script_code = provisional_code
                self.script_name = lang_code_search(provisional_code, True)[0]
        elif is_multiple:
            # Resetting multiples here.
            self.type = "multiple"
            if title_format(original_title)[2] == "multiple":
                self.language_code_1 = "multiple"
                self.language_code_3 = "multiple"
            if title_format(original_title)[2] == "app":
                self.language_code_1 = "app"
                self.language_code_3 = "app"

    # noinspection PyAttributeOutsideInit,PyAttributeOutsideInit
    def update_reddit(self):
        """
        Sets the flair properly on Reddit. No arguments taken.
        It collates all the attributes and decides what flair
        to give it, then selects the appropriate template for it.

        :return:
        """

        # Get the original submission object.
        original_submission = reddit.submission(self.id)
        code_tag = "[--]"  # Default, this should be changed by the functions below.
        self.output_oflair_css = None  # Reset this
        self.output_oflair_text = None

        # Code here to determine the output data... CSS first.
        unq_types = ["Unknown", "Generic"]
        if (
            self.type == "single"
        ):  # This includes checks to make sure the content are strings, not lists.
            if (
                self.is_supported
                and self.language_name not in unq_types
                and self.language_name is not None
            ):
                if self.language_code_1 is not None and isinstance(
                    self.language_code_1, str
                ):
                    code_tag = "[{}]".format(self.language_code_1.upper())
                    self.output_oflair_css = self.language_code_1
                elif self.language_code_3 is not None and isinstance(
                    self.language_code_3, str
                ):
                    # Supported three letter code
                    code_tag = "[{}]".format(self.language_code_3.upper())
                    self.output_oflair_css = self.language_code_3
            elif (
                not self.is_supported
                and self.language_name not in unq_types
                and self.language_name is not None
            ):
                # It's not a supported language
                if self.language_code_1 is not None and isinstance(
                    self.language_code_1, str
                ):
                    code_tag = "[{}]".format(self.language_code_1.upper())
                    self.output_oflair_css = "generic"
                elif self.language_code_3 is not None and isinstance(
                    self.language_code_3, str
                ):
                    code_tag = "[{}]".format(self.language_code_3.upper())
                    self.output_oflair_css = "generic"
            elif self.language_name == "Unknown":  # It's an Unknown post.
                code_tag = "[?]"
                self.output_oflair_css = "unknown"
                print(f">>> Update Reddit: Unknown post `{self.id}`.")
            elif (
                self.language_name is None
                or self.language_name == "Generic"
                or self.language_name == ""
            ):
                # There is no language flair defined.
                code_tag = "[--]"
                self.output_oflair_css = "generic"
        else:  # Multiple post.
            code_tag = []

            if (
                self.language_code_3 == "multiple"
            ):  # This is a multiple for all languages
                self.output_oflair_css = "multiple"
                code_tag = None  # Blank code tag, don't need it.
            elif (
                self.language_code_3 == "app"
            ):  # This is an app request for all languages
                self.output_oflair_css = "app"
                code_tag = None  # Blank code tag, don't need it.
            else:  # This is a defined multiple post.
                # Check to see if we should give this an 'app' classification.
                real_title = title_format(original_submission.title)[4]
                app_yes = app_multiple_definer(real_title)

                if app_yes:
                    self.output_oflair_css = "app"  # Give it the app flair
                else:
                    self.output_oflair_css = "multiple"  # Default multiple.

                # If the status tag is a dictionary, then give it a proper tag.
                if isinstance(self.status, dict):
                    code_tag = ajo_defined_multiple_flair_former(self.status)

        if self.type == "single":
            # Code to determine the output flair text.
            if self.status == "translated":
                self.output_oflair_css = "translated"
                self.output_oflair_text = "Translated {}".format(code_tag)
            elif self.status == "doublecheck":
                self.output_oflair_css = "doublecheck"
                self.output_oflair_text = "Needs Review {}".format(code_tag)
            elif self.status == "inprogress":
                self.output_oflair_css = "inprogress"
                self.output_oflair_text = "In Progress {}".format(code_tag)
            elif self.status == "missing":
                self.output_oflair_css = "missing"
                self.output_oflair_text = "Missing Assets {}".format(code_tag)
            else:  # It's an untranslated language
                self.output_oflair_text = (
                    self.language_name
                )  # The default flair text is just the language name.
                if self.country_code is not None:  # There is a country code.
                    self.output_oflair_text = "{} {{{}}}".format(
                        self.output_oflair_text, self.country_code
                    )
                    # add the country code in brackets after the language name. It will disappear if translated.
                if self.language_name != "Unknown":
                    if self.is_identified:
                        self.output_oflair_text = "{} (Identified)".format(
                            self.output_oflair_text
                        )
                    if self.is_long:
                        self.output_oflair_text = "{} (Long)".format(
                            self.output_oflair_text
                        )
                else:  # This is for Unknown posts
                    if self.is_script:
                        print(
                            f">>> Update Reddit: Is `{self.id}` script? `{self.is_script}`."
                        )
                        self.output_oflair_text = self.script_name + " (Script)"
        else:  # Flair text for multiple posts
            if code_tag is None:
                self.output_oflair_text = converter(self.output_oflair_css)[1]
            else:
                if self.output_oflair_css == "app":
                    self.output_oflair_text = "App {}".format(code_tag)
                else:
                    self.output_oflair_text = "Multiple Languages {}".format(code_tag)

        # Actually push the updated text to the server
        # original_submission.mod.flair(text=self.output_oflair_text, css_class=self.output_oflair_css)

        # Push the updated text to the server (redesign version)
        # Check the global template dictionary.
        # If we have the css in the keys as a proper flair, then we can mark it with the new template.
        if self.output_oflair_css in POST_TEMPLATES.keys():
            output_template = POST_TEMPLATES[self.output_oflair_css]
            logger.info(
                "[ZW] Update Reddit: Template for CSS `{}` is `{}`.".format(
                    self.output_oflair_css, output_template
                )
            )
            original_submission.flair.select(
                flair_template_id=output_template, text=self.output_oflair_text
            )
            logger.info(
                "[ZW] Set post `{}` to CSS `{}` and text `{}`.".format(
                    self.id, self.output_oflair_css, self.output_oflair_text
                )
            )


def ajo_writer(new_ajo):
    """
    Function takes an Ajo object and saves it to a local database.

    :param new_ajo: An Ajo object that should be saved to the database.
    :return: Nothing.
    """

    ajo_id = str(new_ajo.id)
    created_time = new_ajo.created_utc
    cursor_ajo.execute("SELECT * FROM local_database WHERE id = ?", (ajo_id,))
    stored_ajo = cursor_ajo.fetchone()

    if stored_ajo is not None:  # There's already a stored entry
        stored_ajo = eval(stored_ajo[2])  # We only want the stored dict here.
        if (
            new_ajo.__dict__ != stored_ajo
        ):  # The dictionary representations are not the same
            representation = str(
                new_ajo.__dict__
            )  # Convert the dict of the Ajo into a string.
            update_command = "UPDATE local_database SET ajo = ? WHERE id = ?"
            cursor_ajo.execute(update_command, (representation, ajo_id))
            conn_ajo.commit()
            logger.debug("ZW] ajo_writer: Ajo exists, data updated.")
        else:
            logger.debug("ZW] ajo_writer: Ajo exists, but no change in data.")
            pass
    else:  # This is a new entry, not in my files.
        representation = str(new_ajo.__dict__)
        ajo_to_store = (ajo_id, created_time, representation)
        cursor_ajo.execute("INSERT INTO local_database VALUES (?, ?, ?)", ajo_to_store)
        conn_ajo.commit()
        logger.debug("ZW] ajo_writer: New Ajo not found in the database.")

    logger.debug("[ZW] ajo_writer: Wrote Ajo to local database.")

    return


def ajo_loader(ajo_id):
    """
    This function takes an ID string and returns an Ajo object from a local database that matches that string.
    This ID is the same as the ID of the Reddit post it's associated with.

    :param ajo_id: ID of the Reddit post/Ajo that's desired.
    :return: None if there is no stored Ajo, otherwise it will return the Ajo itself (not a dictionary).
    """

    # Checks the database
    cursor_ajo.execute("SELECT * FROM local_database WHERE id = ?", (ajo_id,))
    new_ajo = cursor_ajo.fetchone()

    if new_ajo is None:  # We couldn't find a stored dict for it.
        logger.debug("[ZW] ajo_loader: No local Ajo stored.")
        return None
    else:  # We do have stored data.
        new_ajo_dict = eval(new_ajo[2])  # We only want the stored dict here.
        new_ajo = Ajo(new_ajo_dict)
        logger.debug("[ZW] ajo_loader: Loaded Ajo from local database.")
        return new_ajo  # Note: the Ajo class can build itself from this dict.


"""
KOMENTO ANALYZER

Similar to the Ajo in its general purpose, a Komento object (which is a dictionary) provides anchors and references
for the bot to check its own output and commands as well.

Komento-related functions are all prefixed with `komento` in their name. 
"""


def komento_submission_from_comment(comment_id):
    """
    Returns the parent submission as an object from a comment ID.

    :param comment_id: The Reddit ID for the comment, expressed as a string.
    :return: Returns the PRAW Submission object of the parent post.
    """

    main_comment = reddit.comment(id=comment_id)  # Convert ID into comment object.
    main_submission = main_comment.link_id[3:]  # Strip the t3_ from front.
    main_submission = reddit.submission(
        id=main_submission
    )  # Get actual PRAW submission object.

    return main_submission


def komento_analyzer(reddit_submission):
    """
    A function that returns a dictionary containing various things that Ziwen checks against. It indexes comments with
    specific keys in the dictionary so that Ziwen can access them directly and easily.

    :param reddit_submission:
    :return: A dictionary with keyed values according to the bot's and user comments.
    """

    try:
        oauthor = reddit_submission.author.name
    except AttributeError:
        return {}  # Changed from None, the idea is to return a null dictionary

    # Flatten the comments into a list.
    reddit_submission.comments.replace_more(
        limit=None
    )  # Replace all MoreComments with regular comments.
    comments = reddit_submission.comments.list()

    results = {}  # The main dictionary file we will return
    corresponding_comments = {}
    lookup_comments = {}
    lookup_replies = {}
    list_of_translators = []

    # Iterate through to the comments.
    for comment in comments:
        try:  # Check if user is deleted
            cauthor = comment.author.name
        except AttributeError:
            # Comment author is deleted
            continue

        cbody = comment.body.lower()  # Lower case everything.
        cid = comment.id
        lookup_keywords = [
            "wiktionary",
            "` doesn't look like anything",
            "no results",
            "couldn't find anything",
        ]

        # Check for OP Short thanks.
        if cauthor == oauthor and any(keyword in cbody for keyword in THANKS_KEYWORDS):
            results["op_thanks"] = True
            # This is thanks. Not short thanks for marking something translated.

        # Check for bot's own comments
        if cauthor == USERNAME:  # Comment is by the bot.
            if "this is a crossposted translation request" in cbody:
                results["bot_xp_comment"] = cid
                # We want to get a few more values.
                op_match = comment.body.split(" at")[0]
                op_match = op_match.split("/")[1].strip()  # Get just the username
                results["bot_xp_op"] = op_match
                requester_match = comment.body.split("**Requester:**")[1]
                requester = requester_match.split("\n", 1)[0].strip()[2:]
                results["bot_xp_requester"] = requester
                original_post = comment.body.split("**Requester:**")[0]  # Split in half
                original_post_id = original_post.split("comments/")[1].strip()[
                    0:6
                ]  # Get just the post ID
                results["bot_xp_original_submission"] = original_post_id
                # Linked comment in other subreddit.
                # Original post is the original cross-posted thing
                original_post = reddit.submission(original_post_id)
                original_post.comments.replace_more(limit=3)
                original_comments = original_post.comments.list()
                for ori_comment in original_comments:
                    try:
                        ori_comment_author = ori_comment.author.name
                    except AttributeError:  # The comment's author was deleted.
                        continue

                    if (
                        ori_comment_author == "translator-BOT"
                        and "I've [crossposted]" in ori_comment.body
                    ):
                        results["bot_xp_original_comment"] = ori_comment.id
            elif any(keyword in cbody for keyword in lookup_keywords):
                bot_replied_comments = []

                # We do need to modify this to accept more than one.
                parent_lookup_comment = (
                    comment.parent()
                )  # This is the comment with the actual lookup words.

                parent_body = parent_lookup_comment.body
                parent_x_id = parent_lookup_comment.id

                if len(parent_body) != 0 and "[deleted]" not in parent_body:
                    # Now we want to create a list/dict linking the specific searches with their data.
                    lookup_results = lookup_matcher(parent_body, None)
                    lookup_comments[
                        cid
                    ] = lookup_results  # We add what specific things were searched
                    corresponding_comments[parent_lookup_comment.id] = lookup_results
                    parent_replies = parent_lookup_comment.replies

                    for reply in parent_replies:
                        # We need to double-check why there are so many replies.
                        if "Ziwen" in reply.body and reply.parent_id[3:] == parent_x_id:
                            bot_replied_comments.append(reply.id)
                    lookup_replies[parent_x_id] = bot_replied_comments

            elif "ethnologue" in cbody or "multitree" in cbody:
                results["bot_reference"] = cid
            elif "translation request tagged as 'unknown.'" in cbody:
                results["bot_unknown"] = cid
            elif "your translation request appears to be very long" in cbody:
                results["bot_long"] = cid
            elif (
                "please+check+this+out" in cbody
            ):  # This is the response to an invalid !identify command
                results["bot_invalid_code"] = cid
            elif "multiple defined languages" in cbody:
                results["bot_defined_multiple"] = cid
            elif "## Search results on r/translator" in cbody:
                results["bot_search"] = cid
            elif "they are working on a translation for this" in cbody:
                # Claim comment. we want to get a couple more values.
                results["bot_claim_comment"] = cid

                claimer = re.search(
                    r"(?<=u/)[\w-]+", cbody
                )  # Get the username of the claimer
                claimer = str(claimer.group(0)).strip()
                results["claim_user"] = claimer

                current_c_time = time.time()
                claimed_time = cbody.split(" at ")[1]
                claimed_time = claimed_time.split(" UTC")[0]
                claimed_date = claimed_time.split(" ")[0]
                claimed_time = claimed_time.split(" ")[1]

                num_year = int(claimed_date.split("-")[0])
                num_month = int(claimed_date.split("-")[1])
                num_day = int(claimed_date.split("-")[2])

                num_hour = int(claimed_time.split(":")[0])
                num_min = int(claimed_time.split(":")[1])
                num_sec = int(claimed_time.split(":")[2])

                comment_datetime = datetime.datetime(
                    num_year, num_month, num_day, num_hour, num_min, num_sec
                )
                utc_timestamp = calendar.timegm(
                    comment_datetime.timetuple()
                )  # Returns the time in UTC.
                time_difference = int(current_c_time - utc_timestamp)
                results[
                    "claim_time_diff"
                ] = time_difference  # How long the thing has been claimed for.
        else:  # Processing comments by non-bot
            # Get a list of people who have contributed to helping. Unused at present.
            if KEYWORDS[3] in cbody or KEYWORDS[9] in cbody:
                list_of_translators.append(cauthor)

    if len(lookup_comments) != 0:  # We have lookup data
        results["bot_lookup"] = lookup_comments
        results["bot_lookup_correspond"] = corresponding_comments
        results["bot_lookup_replies"] = lookup_replies
    if len(list_of_translators) != 0:
        results["translators"] = list_of_translators

    return results  # This will be a dictionary with values.


"""
POINTS TABULATING SYSTEM

Ziwen has a live points system (meaning it calculates users' points as they make their comments) to help users keep
track of their contributions to the community. The points system is not as public as some other communities that have
points bots, but is instead meant to be more private. A summary table to the months' contributors is posted by Wenyuan
at the start of every month.

Points-related functions are all prefixed with `points` in their name. 
"""


def points_retreiver(username):
    """
    Fetches the total number of points earned by a user in the current month.
    This is used with the messages routine to tell people how many points they have earned.

    :param username: The username of a Reddit user as a string.
    :return to_post: A string containing information on how many points the user has received on r/translator.
    """

    month_points = 0
    all_points = 0
    recorded_months = []
    recorded_posts = []
    to_post = ""

    current_time = time.time()
    month_string = datetime.datetime.fromtimestamp(current_time).strftime("%Y-%m")

    sql_s = "SELECT * FROM total_points WHERE username = ? AND month_year = ?"
    cursor_main.execute(sql_s, (username, month_string))
    username_month_points_data = cursor_main.fetchall()  # Returns a list of lists.

    sql_un = "SELECT * FROM total_points WHERE username = ?"
    cursor_main.execute(sql_un, (username,))
    username_all_points_data = cursor_main.fetchall()

    for (
        data
    ) in (
        username_month_points_data
    ):  # Compile the monthly number of points the user has earned.
        month_points += data[3]

    for (
        data
    ) in username_all_points_data:  # Compile the total number of posts participated.
        post_id = data[4]
        recorded_posts.append(post_id)
    recorded_posts = list(set(recorded_posts))
    recorded_posts_count = len(
        recorded_posts
    )  # This is the number of posts the user has participated in.

    for (
        data
    ) in (
        username_all_points_data
    ):  # Compile the total number of points the user has earned.
        all_points += data[3]

    for (
        data
    ) in (
        username_all_points_data
    ):  # Compile the total number of months that have been recorded. .
        recorded_months.append(data[0])
        recorded_months = sorted(list(set(recorded_months)))

    if all_points != 0:  # The user has points listed.
        first_line = (
            "You've earned **{} points** on r/translator this month.\n\n"
            "You've earned **{} points** in total and participated in **{} posts**.\n\n"
        )
        to_post += first_line.format(month_points, all_points, recorded_posts_count)
        to_post += "Year/Month | Points | Number of Posts Participated\n-----------|--------|------------------"
    else:  # User has no points listed.
        to_post = MSG_NO_POINTS
        return to_post

    for month in recorded_months:  # Generate rows of data from the points data.
        recorded_month_points = 0
        scratchpad_posts = []

        command = "SELECT * FROM total_points WHERE username = ? AND month_year = ?"
        cursor_main.execute(command, (username, month))
        month_data = cursor_main.fetchall()
        for data in month_data:
            recorded_month_points += data[3]
            scratchpad_posts.append(data[4])

        recorded_posts = len(list(set(scratchpad_posts)))

        to_post += "\n{} | {} | {}".format(month, recorded_month_points, recorded_posts)
    to_post += "\n*Total* | {} | {}".format(
        all_points, recorded_posts_count
    )  # Add a summary row for the totals.

    return to_post


def points_worth_determiner(language_name):
    """
    This function takes a language name and determines the points worth for a translation for it. (the cap is 20)

    :param language_name: The name of the language we want to know the points worth for.
    :return final_point_value: The points value for the language expressed as an integer.
    """

    if " " in language_name:  # Wiki links need underscores instead of spaces.
        language_name = language_name.replace(" ", "_")
    elif "-" in language_name:  # The wiki does not support hyphens in urls.
        language_name = language_name.replace("-", "_")

    if language_name == "Unknown":
        return 4  # The multiplier for Unknown can be hard coded.

    # Code to check the cache first to see if we have a value already.
    final_point_value = CACHED_MULTIPLIERS.get(
        language_name
    )  # Looks for the dictionary key of the language name.

    if final_point_value is not None:  # It's cached.
        logger.debug(
            "[ZW] Points determiner: {} value in the cache: {}".format(
                language_name, final_point_value
            )
        )
        return final_point_value  # Return the multipler - no need to go to the wiki.
    else:  # Not found in the cache. Get from the wiki.
        overall_page = reddit.subreddit(SUBREDDIT).wiki[
            language_name.lower()
        ]  # Fetch the wikipage.
        try:  # First see if this page actually exists
            overall_page_content = str(overall_page.content_md)
            last_month_data = overall_page_content.split("\n")[-1]
        except prawcore.exceptions.NotFound:  # There is no such wikipage.
            logger.debug("[ZW] Points determiner: The wiki page does not exist.")
            last_month_data = "2017 | 08 | [Example Link] | 1%"
            # Feed it dummy data if there's nothing... this language probably hasn't been done in a while.
        try:  # Try to get the percentage from the page
            total_percent = str(last_month_data.split(" | ")[3])[:-1]
            total_percent = float(total_percent)
        except (
            IndexError
        ):  # There's a page but there is something wrong with data entered.
            logger.debug("[ZW] Points determiner: There was a second error.")
            total_percent = float(1)

        # Calculate the point multiplier.
        # The precise formula here is: (1/percentage)*35
        try:
            raw_point_value = 35 * (1 / total_percent)
            final_point_value = int(round(raw_point_value))
        except ZeroDivisionError:  # In case the total_percent is 0 for whatever reason.
            final_point_value = 20

        if final_point_value > 20:
            final_point_value = 20
        logger.debug(
            "[ZW] Points determiner: Multiplier for {} is {}".format(
                language_name, final_point_value
            )
        )

        # Add to the cached values, so we don't have to do this next time.
        CACHED_MULTIPLIERS.update({language_name: final_point_value})

        # Write data to the cache so that it can be retrieved later.
        current_zeit = time.time()
        month_string = datetime.datetime.fromtimestamp(current_zeit).strftime("%Y-%m")
        insert_data = (month_string, language_name, final_point_value)
        cursor_cache.execute(
            "INSERT INTO multiplier_cache VALUES (?, ?, ?)", insert_data
        )
        conn_cache.commit()

    return final_point_value


def points_worth_cacher():
    """
    Simple routine that caches the most frequently used languages' points worth in a local database.

    :param: Nothing.
    :return: Nothing.
    """

    # These are the most common languages on the subreddit. Also in our sidebar.
    check_languages = [
        "Arabic",
        "Chinese",
        "French",
        "German",
        "Hebrew",
        "Hindi",
        "Italian",
        "Japanese",
        "Korean",
        "Latin",
        "Polish",
        "Portuguese",
        "Russian",
        "Spanish",
        "Thai",
        "Vietnamese",
    ]

    # Code to check the database file to see if the values are current.
    # It will transform the database info into a dictionary.

    # Get the year-month string.
    current_zeit = time.time()
    month_string = datetime.datetime.fromtimestamp(current_zeit).strftime("%Y-%m")

    # Select from the database the current months data if it exists.
    multiplier_command = "SELECT * from multiplier_cache WHERE month_year = ?"
    cursor_cache.execute(multiplier_command, (month_string,))
    multiplier_entries = cursor_cache.fetchall()
    # If not current, fetch new data and save it.

    if len(multiplier_entries) != 0:  # We actually have cached data for this month.
        # Populate the dictionary format from our data
        for entry in multiplier_entries:
            multiplier_name = entry[1]
            multiplier_worth = int(entry[2])
            CACHED_MULTIPLIERS[multiplier_name] = multiplier_worth
    else:  # We don't have cached data so we will retrieve it from the wiki.
        # Delete everything from the cache (clearing out previous months' data as well)
        command = "DELETE FROM multiplier_cache"
        cursor_cache.execute(command)
        conn_cache.commit()

        # Get the data for the common languages
        for language in check_languages:
            # Fetch the number of points it's worth.
            points_worth_determiner(language)

            # Write the data to the cache.
            conn_cache.commit()

    return


def points_tabulator(oid, oauthor, oflair_text, oflair_css, comment):
    """
    The main function to save a user's points, given a post submission's content and comment.
    This is intended to be able to assess the points at the point of the comment's writing.
    The function is different from other points systems where points are calculated much later.

    :param oid: The Reddit ID of the submission the comment is on.
    :param oauthor: The username of the author of the comment.
    :param oflair_text: The flair text of the submission.
    :param oflair_css: The CSS code of the submission (typically this is the language code).
    :param comment: The text of the comment to process.
    """

    current_time = time.time()
    month_string = datetime.datetime.fromtimestamp(current_time).strftime("%Y-%m")
    points_status = []

    if oflair_css in ["meta", "art"]:
        return

    try:  # Check if user is deleted
        pauthor = comment.author.name
    except AttributeError:
        # Comment author is deleted
        return

    if pauthor == "AutoModerator" or pauthor == "translator-BOT":
        return  # Ignore these bots

    # Load the Ajo from the database. We will check against it to see if it's None later.

    translator_to_add = None

    pbody = comment.body.lower().strip()

    # It is an OP comment and it's *not* a short thanks.
    if (
        pauthor == oauthor
        and not any(keyword in pbody for keyword in THANKS_KEYWORDS)
        and len(pbody) < 20
    ):
        return

    if oflair_css in ["multiple", "app", "community"]:
        # If it's a multiple post, let's try and get the language name from the comment
        comment_language_data = language_mention_search(comment.body)
        if comment_language_data is not None:  # There is a language mentioned..
            language_name = comment_language_data[0]
            # process_this = True
        else:
            return None
    else:  # Regular posts here. Let's get the language.
        if "[" in oflair_text:
            language_tag = "[" + oflair_text.split("[")[1]
            language_name = converter(language_tag.lower()[1:-1])[1]
        elif "{" in oflair_text:  # Contains a bracket. Spanish {Mexico} (Identified)
            language_name = oflair_text.split("{")[0].strip()
        elif "(" in oflair_text:  # Contains a parantheses. Spanish (Identified)
            language_name = oflair_text.split("(")[0].strip()
        else:
            language_name = oflair_text

    try:
        language_multiplier = points_worth_determiner(converter(language_name)[1])
        # How much is this language worth? Obtain it from our wiki.
    except prawcore.exceptions.Redirect:  # The wiki doesn't have this.
        language_multiplier = 20
    logger.debug(
        "[ZW] Points tabulator: {}, {} multiplier".format(
            language_name, str(language_multiplier)
        )
    )

    final_translator = (
        ""  # This is in case the commenter is not actually the translator
    )
    final_translator_points = 0  # Same here.

    points = 0  # base number of points
    pid = comment.id  # comment ID for recording.
    # pscore = comment.score # We can't use this in live mode because comments are processed in real-time

    if "+" in pbody and len(pbody) < 3:  # Just a flat add  of points.
        logger.debug("[ZW] Points tabulator: This is a flat point add.")
        parent_comment = comment.parent()  # Get the comment parent.
        try:  # Check if it's a comment:
            parent_post = parent_comment.parent_id
            final_translator = parent_comment.author.name
            logger.debug(
                "[ZW] Points tabulator: Actual translator: u/{} for {}".format(
                    final_translator, parent_post
                )
            )
            final_translator_points += 3  # Give them a flat amount of points.
        except AttributeError:  # Parent is a post. Skip.
            logger.debug("[ZW] Points tabulator: Parent of this comment is a post.")

    if (
        len(pbody) > 13
        and oauthor != pauthor
        and "!translated" in pbody
        or "!doublecheck" in pbody
    ):
        # This is a real translation.
        if (
            len(pbody) < 60
            and "!translated" in pbody
            and any(keyword in pbody for keyword in VERIFYING_KEYWORDS)
        ):
            # This should be a verification command. Someone's agreeing that another is right.
            parent_comment = comment.parent()
            try:  # Check if it's a comment:
                parent_post = parent_comment.parent_id
                final_translator = parent_comment.author.name
                logger.debug(
                    "[ZW] Points tabulator: Actual translator: u/{}, {}".format(
                        final_translator, parent_post
                    )
                )
                final_translator_points += 1 + (1 * language_multiplier)
                points += 1  # Give the cleaner-upper a point.
            except AttributeError:  # Parent is a post.
                logger.debug("[ZW] Points tabulator: Parent of this comment is a post.")
        else:
            logger.debug(
                "[ZW] Points tabulator: Seems to be a solid !translated comment by u/{}.".format(
                    pauthor
                )
            )
            translator_to_add = pauthor
            points += 1 + (1 * language_multiplier)
    elif len(pbody) < 13 and "!translated" in pbody:
        # It's marking someone else's translation as translated. We want to get the parent.
        logger.debug(
            "[ZW] Points tabulator: This is a cleanup !translated comment by u/{}.".format(
                pauthor
            )
        )
        parent_comment = comment.parent()
        try:  # Check if it's a comment:
            parent_post = parent_comment.parent_id
            final_translator = parent_comment.author.name
            logger.debug(
                "[ZW] Points tabulator: Actual translator: u/{} for {}".format(
                    final_translator, parent_post
                )
            )
            final_translator_points += 1 + (1 * language_multiplier)
            if (
                final_translator != pauthor
            ):  # Make sure it isn't someone just calling it on their own here
                points += 1  # We give the person who called the !translated comment a point for cleaning up
        except AttributeError:  # Parent is a post.
            logger.debug("[ZW] Points tabulator: Parent of this comment is a post.")
        points += 1  # Give the cleaner-upper a point.
    elif len(pbody) > 13 and "!translated" in pbody and pauthor == oauthor:
        # The OP marked it !translated, but with a longer comment.
        logger.debug(
            "[ZW] Points tabulator: A !translated comment by the OP u/{} for someone else?.".format(
                pauthor
            )
        )
        parent_comment = comment.parent()
        try:  # Check if it's a comment:
            parent_post = parent_comment.parent_id
            final_translator = parent_comment.author.name
            if final_translator != oauthor:
                logger.debug(
                    "[ZW] Points tabulator: Actual translator: u/{}, {}".format(
                        final_translator, parent_post
                    )
                )
                final_translator_points += 1 + (1 * language_multiplier)
        except AttributeError:  # Parent is a post.
            logger.debug("[ZW] Points tabulator: Parent of this comment is a post.")

    if (
        len(pbody) > 120 and pauthor != oauthor
    ):  # This is an especially long comment...But it's well regarded
        points += 1 + int(round(0.25 * language_multiplier))

    if "!identify:" in pbody or "!id:" in pbody:
        points += 3

    if "`" in pbody:
        points += 2

    if "!missing" in pbody:
        points += 2

    if "!claim" in pbody:
        points += 1

    if "!page" in pbody:
        points += 1

    if "!search" in pbody:
        points += 1

    if "!reference" in pbody:
        points += 1

    if (
        any(keyword in pbody for keyword in THANKS_KEYWORDS)
        and pauthor == oauthor
        and len(pbody) < 20
    ):  # The OP thanked someone. Who?
        logger.debug("[ZW] Points tabulator: Found an OP short thank you.")
        parent_comment = comment.parent()
        try:  # Check if it's a comment:
            parent_post = parent_comment.parent_id
            final_translator = (
                parent_comment.author.name
            )  # This is the person OP thanked.
            logger.debug(
                "[ZW] Points tabulator: Actual translator: u/{} for {}".format(
                    final_translator, parent_post
                )
            )
            # Code here to check in the database if the person already got points.
            final_translator_points += 1 + (1 * language_multiplier)
            command_selection = (
                "SELECT * FROM total_points WHERE username = ? AND oid = ?"
            )
            cursor_main.execute(command_selection, (final_translator, oid))
            obtained_points = cursor_main.fetchall()
            # [('2017-09', 'dn9u1g0', 'davayrino', 2, '71bfh4'), ('2017-09', 'dn9u1g0', 'davayrino', 21, '71bfh4')

            for record in obtained_points:  # Go through
                recorded_points = record[3]  # The points for this particular record.
                recorded_post_id = record[4]  # The Reddit ID of the post.

                if (
                    recorded_points == final_translator_points
                    and recorded_post_id == oid
                ):
                    # The person has gotten the exact same amount of points here. Reset.
                    final_translator_points = 0  # Reset the points if that's the case. Person has gotten it before.

        except AttributeError:  # Parent is a post.
            logger.debug(
                "[ZW] Points tabulator: Parent of this comment is a post. Never mind."
            )

    if any(
        pauthor in s for s in points_status
    ):  # Check if author is already listed in our list.
        for i in range(len(points_status)):  # Add their points if so.
            if points_status[i][0] == pauthor:  # Get their username
                points_status[i][1] += points  # Add the running total of points
    else:
        points_status.append(
            [pauthor, points]
        )  # They're not in the list. Just add them.

    if final_translator_points != 0:  # If we have another person's score to put in...
        points_status.append([final_translator, final_translator_points])
        translator_to_add = final_translator

    if points == 0 and final_translator_points == 0:
        return

    # Code to strip out any points = 0
    points_status = [x for x in points_status if x[1] != 0]

    if translator_to_add is not None:  # We can record this information in the Ajo.
        cajo = ajo_loader(oid)
        if cajo is not None:
            cajo.add_translators(translator_to_add)  # Add the name to the Ajo.
            ajo_writer(cajo)

    for entry in points_status:
        logger.debug("[ZW] Points tabulator: Saved: {}".format(entry))
        # Need code to NOT write it if the points are 0
        if entry[1] != 0:
            addition_command = "INSERT INTO total_points VALUES (?, ?, ?, ?, ?)"
            addition_tuple = (month_string, pid, entry[0], str(entry[1]), oid)
            cursor_main.execute(addition_command, addition_tuple)
            conn_main.commit()

    return points_status


"""
RECORDING FUNCTIONS

This is a collection of functions that record information for Ziwen. Some write to a local Markdown file, while others
may write to the wiki of r/translator.

Recording functions are all prefixed with `record` in their name.
"""


def record_activity_csv(data_tuple):
    """
    Function that writes tuples of data to a CSV. It can be used for
    various things, but the first part should be activity type, then
    the date and time. This is written to FILE_ADDRESS_ACTIVITY.
    :param data_tuple: Package of data we want to insert.
    :return:
    """
    with open(FILE_ADDRESS_ACTIVITY, mode="a", newline="") as csv_file:
        data_writer = csv.writer(
            csv_file, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL
        )
        data_writer.writerow(data_tuple)

    return


def record_filter_log(filtered_title, ocreated, filter_type):
    """
    Simple function to write the titles of removed posts to an external text file as an entry in a Markdown table.

    :param filtered_title: The title that violated the community formatting guidelines.
    :param ocreated: The Unix time when the post was created.
    :param filter_type: The specific rule the post violated (e.g. 1, 1A, 1B, 2, EE).
    :return: Nothing.
    """

    # Access the file.
    f = open(
        FILE_ADDRESS_FILTER, "a+", encoding="utf-8"
    )  # File address for the filter log, cumulative.

    # Format the new line.
    filter_line_template = "\n{} | {} | {}"
    timestamp_utc = str(datetime.datetime.fromtimestamp(ocreated).strftime("%Y-%m-%d"))
    filter_line = filter_line_template.format(
        timestamp_utc, filtered_title, filter_type
    )

    # Write the new line.
    f.write(filter_line)
    f.close()

    return


def record_last_post_comment():
    """
    A simple function to get the last post/comment on r/translator for reference storage when there's an error.
    Typically when something goes wrong, it's the last comment that caused the problem.

    :param: Nothing.
    :return to_post: A formatted string containing the link of the last post as well as the text of the last comment.
    """

    # Some default values just in case.
    nowutc = time.time()
    s_format_time = c_format_time = str(
        datetime.datetime.fromtimestamp(nowutc).strftime("%Y-%m-%d [%I:%M:%S %p]")
    )
    cbody = ""
    slink = ""
    cpermalink = ""

    for submission in r.new(limit=1):  # Get the last posted post in the subreddit.
        sutc = submission.created_utc
        slink = "https://www.reddit.com{}".format(submission.permalink)
        s_format_time = str(
            datetime.datetime.fromtimestamp(sutc).strftime(
                "%a, %b %d, %Y [%I:%M:%S %p]"
            )
        )
    for comment in r.comments(limit=1):  # Get the last posted comment
        cbody = "              > {}".format(comment.body)

        cutc = comment.created_utc
        cpermalink = "https://www.reddit.com" + comment.permalink
        c_format_time = str(
            datetime.datetime.fromtimestamp(cutc).strftime(
                "%a, %b %d, %Y [%I:%M:%S %p]"
            )
        )

    if "\n" in cbody:
        cbody = cbody.replace(
            "\n", "\n              > "
        )  # Nicely format each line to fit with our format.
    to_post_template = "Last post     |   {}:    {}\nLast comment  |   {}:    {}\n"
    to_post = to_post_template.format(
        s_format_time, slink, c_format_time, cpermalink
    )  # Format the text for inclusion
    to_post += cbody + "\n"

    return to_post


def record_error_log(error_save_entry):
    """
    A function to SAVE errors to a log for later examination.
    This is more advanced than the basic version kept in _config, as it includes data about last post/comment.

    :param error_save_entry: The traceback text that we want saved to the log.
    :return: Nothing.
    """

    f = open(
        FILE_ADDRESS_ERROR, "a+", encoding="utf-8"
    )  # File address for the error log, cumulative.
    existing_log = f.read()  # Get the data that already exists

    # If this error entry doesn't exist yet, let's save it.
    if error_save_entry not in existing_log:
        error_date = strftime("%Y-%m-%d [%I:%M:%S %p]")
        last_post_text = (
            record_last_post_comment()
        )  # Get the last post and comment as a string

        try:
            log_template = "\n-----------------------------------\n{} ({} {})\n{}\n{}"
            log_template_txt = log_template.format(
                error_date, BOT_NAME, VERSION_NUMBER, last_post_text, error_save_entry
            )
            f.write(log_template_txt)
        except (
            UnicodeEncodeError
        ):  # Occasionally this may fail on Windows thanks to its crap Unicode support.
            logger.error("[ZW] Error_Log: Encountered a Unicode writing error.")
        f.close()

    return


def record_retrieve_error_log():
    """
    A simple routine to GET the last two errors and counters and include them in a ping reply.

    :return logging_output: A formatted string using Markdown's indenting syntax for code (four spaces per line).
    """

    # Error stuff. Open the file.
    with open(FILE_ADDRESS_ERROR, "r", encoding="utf-8") as f:
        error_logs = f.read()

    # Obtain the last two errors that were recorded.
    penultimate_error = error_logs.split("------------------------------")[-2]
    penultimate_error = penultimate_error.replace(
        "\n", "\n    "
    )  # Add indenting of four spaces
    last_error = error_logs.split("------------------------------")[-1]
    last_error = last_error.replace("\n", "\n    ")  # Add indenting

    # Return the last two errors only.
    ping_error_output = penultimate_error + "\n\n" + last_error

    # Return what has been recorded for today_counter
    logging_output = "\n\n{}".format(ping_error_output)

    return logging_output


def record_to_wiki(odate, otitle, oid, oflair_text, s_or_i, oflair_new, user=None):
    """
    A function that saves information to one of two wiki pages on the r/translator subreddit.
    "Saved" is for languages that do not have an associated CSS class.
    "Identified" is for languages that were changed with an !identify command.

    :param odate: Date of the post.
    :param otitle: Title of the post.
    :param oid: ID of the post.
    :param oflair_text: the flair text.
    :param s_or_i: True for writing to the `saved` page, False for writing to the `identified` page.
    :param oflair_new: The new language category.
    :param user: The user who called this identification.
    :return: Does not return anything.
    """

    oformat_date = datetime.datetime.fromtimestamp(int(odate)).strftime("%Y-%m-%d")

    if s_or_i:  # Means we should write to the 'saved' page:
        page_content = reddit.subreddit(SUBREDDIT).wiki["saved"]
        new_content = "| {} | [{}](https://redd.it/{}) | {} |".format(
            oformat_date,
            otitle,
            oid,
            oflair_text,
        )
        page_content_new = str(page_content.content_md) + "\n" + new_content
        # Adds this language entry to the 'saved page'
        page_content.edit(
            content=page_content_new,
            reason='Ziwen: updating the "Saved" page with a new link',
        )
        logger.info("[ZW] Save_Wiki: Updated the 'saved' wiki page.")
    elif not s_or_i:  # Means we should write to the 'identified' page:
        page_content = reddit.subreddit(SUBREDDIT).wiki["identified"]
        new_content_template = "{} | [{}](https://redd.it/{}) | {} | {} | u/{}"
        new_content = new_content_template.format(
            oformat_date, otitle, oid, oflair_text, oflair_new, user
        )
        # Log in the wiki for later reference
        page_content_new = str(page_content.content_md) + "\n" + new_content
        # Adds this month's entry to the data from the wikipage
        try:
            page_content.edit(
                content=page_content_new,
                reason='Ziwen: updating the "Identified" page with a new link',
            )
        except prawcore.exceptions.TooLarge:  # The wikipage is too large.
            page_name = "identified"
            message_subject = "[Notification] '{}' Wiki Page Full".format(page_name)
            message_template = MSG_WIKIPAGE_FULL.format(page_name)
            logger.warning(
                "[ZW] Save_Wiki: The '{}' wiki page is full.".format(page_name)
            )
            reddit.subreddit("translatorBOT").message(message_subject, message_template)
        logger.info("[ZW] Save_Wiki: Updated the 'identified' wiki page.")

    return


"""
MESSAGING FUNCTIONS

These are functions that are used in messages to users but are not necessarily part of the notifications system. The 
notifications system, however, may still use these functions.

These non-notifier functions are all prefixed with `messaging` in their name.
"""


# noinspection PyUnusedLocal
def messaging_is_valid_user(username):
    """
    Simple function that tests if a Redditor is a valid user. Used to keep the notifications database clean.
    Note that `AttributeError` is returned if a user is *suspended* by Reddit.

    :param username: The username of a Reddit user.
    :return exists: A boolean. False if non-existent or shadowbanned, True if a regular user.
    """

    # Default value.
    exists = True

    try:
        user = reddit.redditor(username).fullname
    except (
        prawcore.exceptions.NotFound,
        AttributeError,
    ):  # AttributeError is thrown if suspended user.
        exists = False

    return exists


def messaging_user_statistics_writer(body_text, username):
    """
    Function that records which commands are written by whom, cumulatively, and stores it into an SQLite file.
    Takes the body text of their comment as an input.
    The database used is the main one but with a different table.

    :param body_text: The content of a comment, likely containing r/translator commands.
    :param username: The username of a Reddit user.
    :return: Nothing.
    """

    # Properly format things.
    recorded_keywords = list(KEYWORDS)
    for nonwanted in [
        "!translate",
        "!translator",
    ]:  # These commands are never used on our subreddit.
        recorded_keywords.remove(nonwanted)
    if recorded_keywords[4] in body_text:
        body_text = body_text.replace(recorded_keywords[4], recorded_keywords[10])

    # Let's try and load any saved record of this
    sql_us = "SELECT * FROM total_commands WHERE username = ?"
    cursor_main.execute(sql_us, (username,))
    username_commands_data = cursor_main.fetchall()

    if len(username_commands_data) == 0:  # Not saved, create a new one
        commands_dictionary = {}
        already_saved = False
    else:  # There's data already for this username.
        already_saved = True
        commands_dictionary = eval(
            username_commands_data[0][1]
        )  # We only want the stored dict here.

    # Process through the text and record the commands used.
    for keyword in recorded_keywords:
        if keyword in body_text:
            if (
                keyword is "`"
            ):  # Since these come in pairs, we have to divide this in half.
                keyword_count = int((body_text.count(keyword) / 2))
            else:  # Regular command
                keyword_count = body_text.count(keyword)

            if keyword in commands_dictionary:
                commands_dictionary[keyword] += keyword_count
            else:
                commands_dictionary[keyword] = keyword_count

    # Save to the database if there's stuff.
    if (
        len(commands_dictionary.keys()) != 0 and not already_saved
    ):  # This is a new username.
        to_store = (username, str(commands_dictionary))
        cursor_main.execute("INSERT INTO total_commands VALUES (?, ?)", to_store)
        conn_main.commit()
    elif (
        len(commands_dictionary.keys()) != 0 and already_saved
    ):  # This username exists. Update instead.
        update_command = "UPDATE total_commands SET commands = ? WHERE username = ?"
        cursor_main.execute(update_command, (str(commands_dictionary), username))
        conn_main.commit()
    else:
        logger.debug("[ZW] messaging_user_statistics_writer: No commands to write.")
        pass

    return


def messaging_user_statistics_loader(username):
    """
    Function that pairs with messaging_user_statistics_writer. Takes a username and looks up what commands they have
    been recorded as using.
    If they have data, it will return a nicely formatted table. Since the notifications data is also recorded in the
    same database, this function will also format the data in that dictionary and integrate it into the table.

    :param username: The username of a Reddit user.
    :return: None if the user has no data (no commands that they called), a sorted table otherwise.
    """

    commands_lines_to_post = []
    notifications_lines_to_post = []
    header = "| Command | Times |\n|---------|-------|\n"

    # Get commands data.
    sql_us = "SELECT * FROM total_commands WHERE username = ?"
    cursor_main.execute(sql_us, (username,))
    username_commands_data = cursor_main.fetchone()

    # Get notifications data.
    sql_us = "SELECT * FROM notify_monthly_limit WHERE username = ?"
    cursor_main.execute(sql_us, (username,))
    notifications_commands_data = cursor_main.fetchone()

    # Iterate over commands data.
    if username_commands_data is None:  # There is no data for this user.
        commands_lines_to_post = None
    else:  # There's data. Get the data and format it line-by-line.
        commands_dictionary = eval(
            username_commands_data[1]
        )  # We only want the stored dict here.
        for key, value in sorted(commands_dictionary.items()):
            command_type = key
            if command_type != "Notifications":  # This is a regular command.
                if command_type == "`":
                    command_type = "`lookup`"
                formatted_line = "| {} | {} |".format(command_type, value)
                commands_lines_to_post.append(formatted_line)

    # Iterate over notifications data. Get the dictionary of notifications that were sent.
    if notifications_commands_data is None:
        notifications_lines_to_post = None
    else:  # There's data
        notification_dict = eval(notifications_commands_data[1])
        for language_code, notification_num in sorted(notification_dict.items()):
            formatted_line = "| Notifications (`{}`) | {} |".format(
                language_code, notification_num
            )
            notifications_lines_to_post.append(
                formatted_line
            )  # Reform it as a string from a list.

    if (
        username_commands_data is None and notifications_commands_data is None
    ):  # Absolutely no information.
        return None
    else:
        # Format everything together. Convert None to blank list.
        if commands_lines_to_post is None:
            commands_lines_to_post = []
        if notifications_lines_to_post is None:
            notifications_lines_to_post = []
        to_post = header + "\n".join(
            commands_lines_to_post + notifications_lines_to_post
        )
        return to_post


def messaging_months_elapsed():
    """
    Simple function that tells us how many months of statistics we have, since May 2016, when the redesign started.
    This is used for assessing the average number of posts are for a given language and can be expected for
    notifications.

    :return months_num: The number of months since May 2017, as an integer.
    """

    month_beginning = 24198  # This is the May 2016 month, when the redesign was implemented. No archive data before.
    current_toki = time.time()

    month_int = int(
        datetime.datetime.fromtimestamp(current_toki).strftime("%m")
    )  # EG 05
    year_int = int(
        datetime.datetime.fromtimestamp(current_toki).strftime("%Y")
    )  # EG 2017

    total_current_months = (year_int * 12) + month_int
    months_num = total_current_months - month_beginning

    return months_num


def messaging_language_frequency_table(language_list):
    """
    This is a function that supercedes `messaging_language_frequency` and can generate a table given a list of language
    codes about the relative frequency for language notifications.
    """

    formatted_lines = []
    header = "| Language Name | Average Number of Posts | Per |\n|-----------|-----:|:----|\n"
    line_template = "| [{}]({}) | {} posts / | {} |"

    # Iterate over the language codes.
    for code in language_list:
        language_name = converter(code)[1]

        # Retrieve stored data.
        language_data = load_statistics_data(code)
        if (
            language_data is not None
        ):  # There is historical statistics for this language.
            daily_rate = language_data["rate_daily"]
            monthly_rate = language_data["rate_monthly"]
            yearly_rate = language_data["rate_yearly"]
            link = language_data["permalink"]

            # Here we try to determine which comment we should return as a line.
            if (
                daily_rate >= 2
            ):  # This is a pretty popular one, with a few requests a day.
                frequency = "day"
                rate = daily_rate
            elif (
                2 > daily_rate > 0.05
            ):  # This is a frequent one, a few requests a month. But not the most.
                frequency = "month"
                rate = monthly_rate
            else:  # These are pretty infrequent languages. Maybe a few times a year at most.
                frequency = "year"
                rate = yearly_rate

            # Combine the lines together as a message.
            new_line = line_template.format(language_name, link, rate, frequency)
        else:  # We have not received data for this language.
            new_line = "| {} | No recorded statistics | --- |".format(language_name)

        # Add the line to our list.
        formatted_lines.append(new_line)

    # Format everything.
    to_post = header + "\n".join(formatted_lines)

    return to_post


def messaging_language_frequency(language_name):
    """
    Function to check how many messages a person can expect for a subscription request. Note that if the language is
    common (that is, it's been requested every single month) we get the last `months_calculate` months' data for more
    accurate statistics.

    :param language_name: The language for which we are checking its statistics.
    :return freq_string: A formatted string that tells a user how often a language is requested.
    :return stats_package: A tuple containing various numerical statistics on the rate of requests.
    """

    # Format the language name in order to get the wiki page.
    lang_wiki_name = language_name.lower()
    lang_wiki_name = lang_wiki_name.replace(" ", "_")

    lang_name_original = language_name
    per_month_lines_edit = []
    total_posts = []

    if " " in language_name:  # Wiki links need underscores instead of spaces.
        language_name = language_name.replace(" ", "_")

    overall_page = reddit.subreddit(SUBREDDIT).wiki[
        language_name.lower()
    ]  # Fetch the wikipage.
    try:
        overall_page_content = str(overall_page.content_md)
    except (
        prawcore.exceptions.NotFound,
        prawcore.exceptions.BadRequest,
        KeyError,
        praw.exceptions.RedditAPIException,
    ):
        # There is no page for this language
        return None  # Exit with nothing.
    except prawcore.exceptions.Redirect:  # Tends to happen with "community" requests
        return None  # Exit with nothing.

    per_month_lines = overall_page_content.split("\n")  # Separate into lines.

    for line in per_month_lines[5:]:  # We omit the header of the page.
        work_line = line.split("(", 1)[
            0
        ]  # We only want the first part, with month|year|total
        # Strip the formatting.
        for character in ["[", "]", " "]:
            work_line = work_line.replace(character, "")
        per_month_lines_edit.append(work_line)

    per_month_lines_edit = [
        x for x in per_month_lines_edit if "20" in x
    ]  # Only get the ones that have a year in them

    for row in per_month_lines_edit:
        month_posts = int(row.split("|")[2])  # We take the number of posts here.
        total_posts.append(month_posts)  # add it to the list of post counts.

    months_with_data = len(
        per_month_lines_edit
    )  # The number of months we have data for the language.
    months_since = (
        messaging_months_elapsed()
    )  # Get the number of months since we started statistic keeping

    if (
        months_with_data == months_since
    ):  # We have data for every single month for the language.
        # We want to take only the last 6 months.
        months_calculate = 6  # Change the time frame to 6 months
        total_rate_posts = sum(
            total_posts[-1 * months_calculate :]
        )  # Add only the data for the last 6 months.
    else:
        total_rate_posts = sum(total_posts)
        months_calculate = months_since

    monthly_rate = round(
        (total_rate_posts / months_calculate), 2
    )  # The average number of posts per month
    daily_rate = round((monthly_rate / 30), 2)  # The average number of posts per day
    yearly_rate = round((monthly_rate * 12), 2)  # The average number of posts per year

    # We add up the cumulative number of posts.
    total_posts = sum(total_posts)

    # A tuple that can be used by other programs.
    stats_package = (daily_rate, monthly_rate, yearly_rate, total_posts)

    # Here we try to determine which comment we should return as a string.
    if daily_rate >= 2:  # This is a pretty popular one, with a few requests a day.
        freq_string = MSG_LANGUAGE_FREQUENCY.format(
            lang_wiki_name, str(daily_rate), "day", lang_name_original
        )
        return freq_string, stats_package
    elif (
        2 > daily_rate > 0.05
    ):  # This is a frequent one, a few requests a month. But not the most.
        freq_string = MSG_LANGUAGE_FREQUENCY.format(
            lang_wiki_name, str(monthly_rate), "month", lang_name_original
        )
        return freq_string, stats_package
    else:  # These are pretty infrequent languages. Maybe a few times a year at most.
        freq_string = MSG_LANGUAGE_FREQUENCY.format(
            lang_wiki_name, str(yearly_rate), "year", lang_name_original
        )
        return freq_string, stats_package


def messaging_translated_message(oauthor, opermalink):
    """
    Function to message requesters (OPs) that their post has been translated.

    :param oauthor: The OP of the post, listed as a Reddit username.
    :param opermalink: The permalink of the post that the OP had made.
    :return: Nothing.
    """

    if oauthor != "translator-BOT":  # I don't want to message myself.
        translated_subject = (
            "[Notification] Your request has been translated on r/translator!"
        )
        translated_body = (
            MSG_TRANSLATED.format(oauthor=oauthor, opermalink=opermalink)
            + BOT_DISCLAIMER
        )
        try:
            reddit.redditor(oauthor).message(translated_subject, translated_body)
        except praw.exceptions.APIException:  # User doesn't allow for messages.
            pass

    logger.info(
        "[ZW] messaging_translated_message: >> Messaged the OP u/{} "
        "about their translated post.".format(oauthor)
    )

    return


"""
NOTIFICATIONS SYSTEM

These functions all relate to Ziwen's notifications - that is, the database of individuals who are on Ziwen's list for 
languages. 

The two main functions are: `ziwen_notifier`, the actual function that sends messages to people.
                            `ziwen_messages`, the function that proccesses incoming messages to the bot.

All other notifier functions are prefixed with `notifier` in their name.
Paging functions, which are a subset of the notifications system, has the prefix `notifier_page`.
"""


def notifier_list_pruner(username):
    """
    Function that removes deleted users from the notifications database.
    It performs a test, and if they don't exist, it will delete their entries from the SQLite database.

    :param username: The username of a Reddit user.
    :return: None if the user does not exist, a string containing their last subscribed languages otherwise.
    """

    if messaging_is_valid_user(username):  # This user does exist
        return None
    else:  # User does not exist.
        final_codes = []

        # Fetch a list of what this user WAS subscribed to. (For the final error message)
        sql_cn = "SELECT * FROM notify_users WHERE username = ?"

        # We try to retrieve the languages the user is subscribed to.
        cursor_main.execute(sql_cn, (username,))
        all_subscriptions = cursor_main.fetchall()

        for subscription in all_subscriptions:
            final_codes.append(
                subscription[0]
            )  # We only want the language codes (don't need the username).
        to_post = ", ".join(
            final_codes
        )  # Gather a list of the languages user WAS subscribed to

        # Remove the user from the database.
        sql_command = "DELETE FROM notify_users WHERE username = ?"
        cursor_main.execute(sql_command, (username,))
        conn_main.commit()
        logger.info(
            "[ZW] notifier_list_pruner: Deleted subscription information for u/{}.".format(
                username
            )
        )

        return to_post  # Return the list of formerly subscribed languages


def notifier_regional_language_fetcher(targeted_language):
    """
    Takes a code like "ar-LB" or an ISO 639-3 code, fetches notifications users for their equivalents too.
    Returns a list of usernames that match both criteria. This will also remove people who are on the broader list.
    This should also be able to work with unknown-specific notifications.

    :param targeted_language: The language code for a regional language or an ISO 639-3 code.
    :return final_specific_determined: A list of users who have signed up for both a broader language (like Arabic)
                                       and the specific regional one (like ar-LB).
    """

    relevant_iso_code = None
    final_specific_usernames = []
    all_broader_usernames = []

    if "-" in targeted_language:  # This is a ITR code. ar-LB
        if targeted_language in ISO_LANGUAGE_COUNTRY_ASSOCIATED:
            # This means there is an ISO 639-3 code for this that we wanna use
            relevant_iso_code = ISO_LANGUAGE_COUNTRY_ASSOCIATED.get(targeted_language)
    else:  # It's an ISO code.
        relevant_iso_code = targeted_language
        for lang_country, language_code in ISO_LANGUAGE_COUNTRY_ASSOCIATED.items():
            if language_code == relevant_iso_code:
                targeted_language = lang_country

    sql_lc = "SELECT * FROM notify_users WHERE language_code = ?"
    cursor_main.execute(sql_lc, (targeted_language,))
    notify_targets = cursor_main.fetchall()

    if (
        relevant_iso_code is not None
    ):  # There is an equvalent code. Let's get the users from that too.
        sql_lc = "SELECT * FROM notify_users WHERE language_code = ?"
        cursor_main.execute(sql_lc, (relevant_iso_code,))
        notify_targets += cursor_main.fetchall()

    for target in notify_targets:
        username = target[1]  # Get the username.
        final_specific_usernames.append(username)

    final_specific_usernames = list(
        set(final_specific_usernames)
    )  # Dedupe the final list.

    # Now we need to find the overall list's user names for the broader langauge (e.g. ar)
    broader_code = targeted_language.split("-")[0]  # Take only the language part (ar).
    sql_lc = "SELECT * FROM notify_users WHERE language_code = ?"
    cursor_main.execute(sql_lc, (broader_code,))
    all_notify_targets = cursor_main.fetchall()

    for target in all_notify_targets:
        all_broader_usernames.append(
            target[1]
        )  # This creates a list of all the people signed up for the original.

    final_specific_determined = set(final_specific_usernames) - set(
        all_broader_usernames
    )
    final_specific_determined = list(final_specific_determined)

    return final_specific_determined


def notifier_duplicate_checker(language_code, username):
    """
    Function that checks to see if there is a duplicate entry in the notifications database. That is, there is a user
    who is signed up for this specific language code.

    :param language_code: The language code the user may be signed up for.
    :param username: The username of a Reddit user.
    :return: True if entry pair is in there (the user is signed up for this language), False if not.
    """

    sql_nc = "SELECT * FROM notify_users WHERE language_code = ? and username = ?"
    sql_nc_tuple = (language_code, username)
    cursor_main.execute(sql_nc, sql_nc_tuple)
    specific_entries = cursor_main.fetchall()

    if len(specific_entries) > 0:  # There already is an entry.
        return True
    else:  # No entry.
        return False


def notifier_title_cleaner(otitle):
    """
    Simple function to replace problematic Markdown characters like `[` or `]` that can mess up links.
    These characters can interfere with the display of Markdown links in notifications.

    :param otitle: The title of a Reddit post.
    :return otitle: The cleaned-up version of the same title with the problematic characters escaped w/ backslashes.
    """

    # Characters to prefix a backslash to.
    specific_characters = ["[", "]"]

    for character in specific_characters:
        if character in otitle:
            otitle = otitle.replace(character, r"\{}".format(character))

    return otitle


def notifier_history_checker(thing_to_send, majo_history):
    """
    This function checks against the language history of an Ajo. This is to prevent people from getting more than one
    notification for the same post. For example, if a post goes from Arabic > Persian > Arabic, we don't want to
    message Arabic users more than once.

    :param thing_to_send: A language code or name.
    :param majo_history: A list containing the languages a post has previously been classified as.
    :return: A boolean indicating whether the language notifications have been sent out for this language.
    """

    # Get the language name.
    language_name = converter(thing_to_send)[1]

    # We allow it to send if it's the last (and only) item in this history.
    if language_name in majo_history and language_name != majo_history[-1]:
        action = False
    else:
        action = True

    return action


def notifier_over_frequency_checker(username):
    """
    This function checks the username against a list of OPs from the last 24 hours.
    If the OP has posted more than the limit it will return True. Notifications will *not* be sent out if the user has
    posted more than the limit, to prevent any potential spam/abuse.

    :param username: The username of a redditor (typically an OP who has submitted a post)
    :return: True if the user has submitted more than the limit in a 24-hour period, False otherwise.
    """

    # This is the limit we want to enforce for a 24-hour period.
    limit = 4

    # Count how many times the username appears in the last 24 hours
    frequency = MOST_RECENT_OP.count(username)

    # If they have exceeded the limit, we're going to return True.
    if frequency > limit:
        return True
    else:
        return False


def notifier_limit_writer(username, language_code, num_notifications=1):
    """
    A function to record how many notifications a user has received. (e.g. kungming2, {'yue': 2, 'unknown': 1, 'ar': 3})
    This function iterates the recorded number by num_notifications each time it's called and stores it in a dictionary.
    It creates a new record if the user has not been recorded before, otherwise it updates a dictionary.
    The database will be cleared out monthly by a separate function contained within Wenyuan.

    :param username: The username of the person who just received a notification.
    :param language_code: The language code for which the notification was for.
    :param num_notifications: The number of notifications the user was sent. 1 by default.
    :return: Nothing.
    """

    monthly_limit_dictionary = {}

    # Fetch the data
    sql_lw = "SELECT * FROM notify_monthly_limit WHERE username = ?"
    cursor_main.execute(sql_lw, (username,))
    user_data = cursor_main.fetchone()

    # Parse the user's data. Load it if it exists.
    if user_data is not None:  # There's a record.
        monthly_limit_dictionary = user_data[1]  # Take the stored dictionary.
        monthly_limit_dictionary = eval(
            monthly_limit_dictionary
        )  # Convert the string to a proper dictionary.

    # Write the changes to the database.
    if (
        language_code not in monthly_limit_dictionary and user_data is None
    ):  # Create a new record, user doesn't exist.
        # Define the key and its value.
        monthly_limit_dictionary[language_code] = num_notifications

        # Write to the database.
        to_store = (username, str(monthly_limit_dictionary))
        cursor_main.execute("INSERT INTO notify_monthly_limit VALUES (?, ?)", to_store)
    else:  # Update an existing one.
        # Attempt to update the dictionary value.
        if language_code in monthly_limit_dictionary:
            monthly_limit_dictionary[language_code] += num_notifications
        else:
            monthly_limit_dictionary[language_code] = num_notifications

        # Write to the database.
        to_store = (str(monthly_limit_dictionary), username)
        update_command = (
            "UPDATE notify_monthly_limit SET received = ? WHERE username = ?"
        )
        cursor_main.execute(update_command, to_store)

    # Commit changes.
    conn_main.commit()

    return


def notifier_limit_over_checker(username, language_code, hard_limit):
    """
    Function that takes a username and checks if they're above a hard monthly limit. This is currently UNUSED.
    True if they're over the limit, False otherwise.

    :param username: The username of the person.
    :param language_code: The language code for the
    :param hard_limit: The hard monthly limit for notifications per user per language. This means that once they exceed
                       this amount they would no longer get notifications for this language. This is an integer.
    :return: True if they are over the limit, False otherwise.
    """

    # Fetch the data
    sql_lw = "SELECT * FROM notify_monthly_limit WHERE username = ?"
    cursor_main.execute(sql_lw, (username,))
    user_data = cursor_main.fetchone()

    if user_data is None:  # No record of this user, so it's okay to send.
        return False
    else:  # There's data already for this username.
        monthly_limit_dictionary = eval(user_data[1])

        # Attempt to get the number of notifications user has received for this language.
        if language_code in monthly_limit_dictionary:
            current_number_notifications = monthly_limit_dictionary[language_code]
        else:  # There is no entry, so this must be zero.
            current_number_notifications = 0

        if current_number_notifications > hard_limit:  # Over the limit
            return True
        else:
            return False


def notifier_equalizer(notify_users_list, language_name, monthly_limit):
    """
    Function that equalizes out notifications for popular languages so that people can get fewer.
    No more than the monthly_limit on average.
    users_to_contact = (users_number * monthly_limit) / monthly_number_notifications
    This is primarily intended for languages which get a lot of monthly requests.

    :param notify_users_list: The full list of users on the notification list for this language.
    :param language_name: The name of the language.
    :param monthly_limit: A soft monthly limit that we try to limit user notifications to per language.
    :return: A list containing a list of users to message.
    """

    # If there are more users than this number, randomize and pick this number's amount of users.
    limit_number = 30

    if notify_users_list is not None:
        users_number = len(notify_users_list)
    else:
        users_number = None

    if (
        users_number is None
    ):  # If there's no one signed up for, just return an empty list
        return []

    # Get the number of requests on average per month for a language
    try:
        if language_name == "Unknown":  # Hardcode Unknown frequency
            monthly_number_notifications = 260
        else:
            frequency_data = messaging_language_frequency(language_name)
            if frequency_data:
                monthly_number_notifications = frequency_data[1][1]
            else:  # No results for this.
                monthly_number_notifications = 1
    except (
        TypeError
    ):  # If there are no statistics for this language, just set it to low.
        monthly_number_notifications = 1

    # Get the number of users we're going to randomly pick for this language
    if monthly_number_notifications == 0:
        users_to_contact = limit_number
    else:
        users_to_contact = round(
            ((users_number * monthly_limit) / monthly_number_notifications), 0
        )
        users_to_contact = int(users_to_contact)

    # There are more users to contact than the recommended amount. Randomize.
    if users_to_contact < users_number:
        notify_users_list = random.sample(notify_users_list, users_to_contact)

        # Get the new number of people on this list.
        users_number = len(notify_users_list)

    # If there are more than limit_number for a language...  Cut it down.
    if users_number > limit_number:
        # Pick X people at random. Cut the list down
        notify_users_list = random.sample(notify_users_list, limit_number)
        logger.info(
            "[ZW] Notifier Equalizer: {}+ people for {} notifications. Randomized.".format(
                limit_number, language_name
            )
        )

    # Alphabetize
    notify_users_list = sorted(notify_users_list, key=str.lower)

    return notify_users_list


def notifier_page_translators(
    language_code, language_name, pauthor, otitle, opermalink, oauthor, is_nsfw
):
    """
    A function (the original purpose Ziwen was written for!) to page up to three users for a post's language.
    Paging now uses the same database as the notification service. It used to rely on a manually populated
    CSV file that was separate.

    :param language_code: Code for the paged language.
    :param language_name: Name for the paged language.
    :param pauthor: Author of the post on which the page command is on.
    :param otitle: Title of the post.
    :param opermalink: Permalink of the post.
    :param oauthor: The user paging others.
    :param is_nsfw: A boolean determining whether or not the post is NSFW (as a warning).
    :return: None if there are no users in our database for a language, True otherwise.
    """

    number_to_page = 5  # How many users we want to page.

    sql_lc = "SELECT * FROM notify_users WHERE language_code = ?"
    cursor_main.execute(sql_lc, (language_code,))
    page_targets = cursor_main.fetchall()

    page_users_list = []

    for target in page_targets:  # This is a list of tuples.
        username = target[
            1
        ]  # Get the user name, as the language is [0] (ar, kungming2)
        page_users_list.append(username)  # Add the username to the list.

    page_users_list = list(set(page_users_list))  # Remove duplicates
    page_users_list = [
        x for x in page_users_list if x != pauthor
    ]  # Remove the caller if on there
    if len(page_users_list) > number_to_page:  # If there are more than three people...
        page_users_list = random.sample(
            page_users_list, number_to_page
        )  # Randomly pick 3

    if len(page_users_list) == 0:  # There is no one on the list for it.
        return None  # Exit, return None.
    else:
        for target_username in page_users_list:
            # if is_page:
            message = MSG_PAGE.format(
                username=target_username,
                pauthor=pauthor,
                language_name=language_name,
                otitle=otitle,
                opermalink=opermalink,
                oauthor=oauthor,
                removal_link=MSG_REMOVAL_LINK.format(language_name=language_code),
            )
            subject_line = (
                "[Page] Message from r/translator regarding a {} post".format(
                    language_name
                )
            )
            # Add on a NSFW warning if appropriate.
            if is_nsfw:
                message += MSG_NSFW_WARNING

            # Send the actual message. Delete the username if an error is encountered.
            try:
                reddit.redditor(str(target_username)).message(
                    subject_line, message + BOT_DISCLAIMER
                )
                logger.info(
                    "[ZW] Paging: Messaged u/{} for a {} post.".format(
                        target_username, language_name
                    )
                )
            except (
                praw.exceptions.APIException
            ):  # There was an error... User probably does not exist anymore.
                logger.debug(
                    "[ZW] Paging: Error occurred sending message to u/{}. Removing...".format(
                        target_username
                    )
                )
                notifier_list_pruner(
                    target_username
                )  # Remove the username from our database.

        return page_users_list


def notifier_page_multiple_detector(pbody):
    """
    Function that checks to see if there are multiple page commands in a comment.

    :param pbody: The text body of the comment we're checking.
    :return: None if there are no valid paging languages or if there's 0 or 1 !page results.
             Will return the paged languages if there's more than 1.
    """

    # Returns a number of pages detected in a single comment.
    num_count_pages = pbody.count("!page:")

    if num_count_pages == 0:
        return None
    elif num_count_pages >= 1:  # There are one or more page languages.
        new_matches = []
        initial_matches = []

        page_chunks = pbody.split("!page:")[1:]
        page_chunks = ["!page:" + s for s in page_chunks]

        for chunk in page_chunks:
            try:
                new_match = comment_info_parser(chunk, "!page:")[0]
                new_matches.append(new_match)
            except TypeError:
                continue

        for match in new_matches:
            match_code = converter(match)[0]
            if len(match_code) != 0:  # This is a valid language code.
                initial_matches.append(match_code)

        # We need code in case we don't have valid data for one.
        if len(initial_matches) != 0:
            return initial_matches
        else:  # We couldn't find anything valid.
            return None


def notifier_language_list_editer(language_list, username, mode="insert"):
    """
    Function that will change the notifications database. It can insert or delete entries for a particular username.

    :param language_list: A list of language codes to insert.
    :param username: The Reddit username of the person whose entries we're changing or updating.
    :param mode: `insert` adds languages for the username, `delete` obviously removes them. `purge` removes all.
    :return: Nothing.
    """

    # If there's nothing in the list, exit.
    if mode == "purge":  # We want to delete everything for this user.
        cursor_main.execute("DELETE FROM notify_users WHERE username = ?", (username,))
        conn_main.commit()
    elif len(language_list) == 0:
        return
    else:  # We have codes to process.
        # Iterate over the codes.
        for code in language_list:
            if len(code) == 4 and code != "meta":  # This is a script
                code = "unknown-" + code  # Format it for insertion.
            elif code is "en":  # Skip inserting English.
                continue

            # Check to see if user is already in our database.
            is_there = notifier_duplicate_checker(code, username)

            sql_package = (code, username)
            if not is_there and mode == "insert":  # No entry, and we want to insert.
                cursor_main.execute(
                    "INSERT INTO notify_users VALUES (? , ?)", sql_package
                )
                conn_main.commit()
            elif (
                is_there and mode == "delete"
            ):  # There is an entry, and we want to delete.
                cursor_main.execute(
                    "DELETE FROM notify_users WHERE language_code = ? and username = ?",
                    sql_package,
                )
                conn_main.commit()
            else:
                continue

    return


def ziwen_notifier(suggested_css_text, otitle, opermalink, oauthor, is_identify):
    """
    This function notifies people about posts they're subscribed to. Unlike ziwen_messages, this is not a top-level
    function and is called by either ziwen_posts or ziwen_bot.

    :param suggested_css_text: Typically this is the language name that we need to send notifications for.
    :param otitle: The title of the post that is the subject of the notification.
    :param opermalink: The link to the post.
    :param oauthor: The author (OP) of the post.
    :param is_identify: A boolean for whether it's a notification from an !identify command.
    :return: The list of users who were notified, for the calling fucntion to save into an Ajo.
    """
    notify_users_list = []
    contacted = []
    post_type = "translation request"

    # We don't want to send testing messages.
    if "trntest" in opermalink:
        return []

    # Load the language_history from the Ajo for this.
    # Exception for dashed stuff for now and meta and community and multiple ones. (defined multiples will just go thru)
    if (
        suggested_css_text not in ["Community", "Meta", "Multiple Languages", "App"]
        and "-" not in suggested_css_text
    ):
        # Load the Ajo to check against its history.
        mid = re.search(r"comments/(.*)/\w", opermalink).group(
            1
        )  # Get just the Reddit ID.
        majo = ajo_loader(mid)  # Load the Ajo

        # Checking the language history and the user history of the particular submission.
        try:
            language_history = (
                majo.language_history
            )  # Load the history of languages this post has been in
            contacted = majo.notified  # Load the people who have been contacted before.
            logger.debug("Ziwen Notifier: Already contacted {}".format(contacted))
            permission_to_proceed = notifier_history_checker(
                suggested_css_text, language_history
            )
        except AttributeError:
            permission_to_proceed = True

        # If it's detected that we may have sent notifications for this already, just end it with no new notifications.
        if not permission_to_proceed:
            return []

    # First we need to do a test to see if it's a specific code or not.
    if "-" not in suggested_css_text:  # This is a regular notification.
        language_code = converter(suggested_css_text)[0]
        language_name = converter(suggested_css_text)[1]
        if (
            suggested_css_text == "Multiple Languages"
        ):  # Debug fix for the multiple ones.
            language_code = "multiple"
            language_name = "Multiple Languages"
        elif suggested_css_text in [
            "meta",
            "community",
        ]:  # Debug fix for the meta & community ones.
            language_code = suggested_css_text
            language_name = suggested_css_text.title()
            post_type = "post"  # Since these are technically not language requests

            # Here we have code to make sure that only mods and the bot send notifications for meta/community posts.
            if not is_mod(oauthor):  # This OP is not a mod. Don't send notifications.
                return []  # Exit.
    else:  # This is a specific code, we want to add the people only signed up for them.
        # Note, this only gets people who are specifically signed up for them, not
        language_code = suggested_css_text.split("-", 1)[
            0
        ]  # We get the broader category here. (ar, unknown)
        language_name = converter(suggested_css_text)[1]
        if language_code == "unknown":  # Add a new script phrase
            language_name += " (Script)"  # This is to distinguish script notifications
        regional_data = notifier_regional_language_fetcher(suggested_css_text)
        if len(regional_data) != 0:
            notify_users_list += (
                regional_data  # add the additional people to the notifications list.
            )

    sql_lc = "SELECT * FROM notify_users WHERE language_code = ?"
    cursor_main.execute(sql_lc, (language_code,))
    notify_targets = cursor_main.fetchall()

    if (
        len(notify_targets) == 0 and len(notify_users_list) == 0
    ):  # If there's no one on the list, just continue
        return []

    for target in notify_targets:  # This is a list of tuples.
        username = target[
            1
        ]  # Get the user name, as the language is [0] (ar, kungming2)
        notify_users_list.append(username)

    notify_users_list = list(set(notify_users_list))  # Eliminate duplicates
    # Remove the usernames of users already contacted about this post.
    notify_users_list = [x for x in notify_users_list if x not in contacted]

    # Code here to equalize data (see function above)
    notify_users_list = notifier_equalizer(
        notify_users_list, language_name, NOTIFICATIONS_LIMIT
    )

    action_counter(
        len(notify_users_list), "Notifications"
    )  # Write to the counter log how many we send
    otitle = notifier_title_cleaner(
        otitle
    )  # Clean up the title, prevent Markdown errors with square brackets

    # Exit if there is nothing to send.
    if len(notify_users_list) == 0:
        return []

    messaging_start = time.time()
    for username in notify_users_list:
        if not is_identify:  # This is just the regular notification
            message = MSG_NOTIFY.format(
                username=username,
                language_name=language_name,
                post_type=post_type,
                otitle=otitle,
                opermalink=opermalink,
                oauthor=oauthor,
            )
        else:  # This is from an !identify command.
            message = MSG_NOTIFY_IDENTIFY.format(
                username=username,
                language_name=language_name,
                post_type=post_type,
                otitle=otitle,
                opermalink=opermalink,
                oauthor=oauthor,
            )
        try:
            message_subject = "[Notification] New {} post on r/translator".format(
                language_name
            )
            reddit.redditor(username).message(
                message_subject, message + BOT_DISCLAIMER + MSG_UNSUBSCRIBE_BUTTON
            )
            notifier_limit_writer(
                username, language_code
            )  # Record that they have been messaged
        except praw.exceptions.APIException:  # If the user deleted their account...
            logger.info(
                "[ZW] Notifier: An error occured while sending a message to u/{}. Removing...".format(
                    username
                )
            )
            notifier_list_pruner(username)  # Remove the username from our database.

    # Record to a log how long it took.
    messaging_mins = (time.time() - messaging_start) / 60
    seconds_per_message = (time.time() - messaging_start) / len(notify_users_list)
    payload = (
        time_convert_to_string(messaging_start),
        "Messaging run",
        len(notify_users_list),
        language_name,
        messaging_mins,
        round(seconds_per_message, 2),
    )
    record_activity_csv(payload)
    logger.info(
        "[ZW] Notifier: Sent notifications to {} users signed up for {}.".format(
            len(notify_users_list), language_name
        )
    )

    return notify_users_list


def ziwen_messages():
    """
    A top-level system to process commands via the messaging system of Reddit. This system acts upon keywords included
    in the message's subject field, including the following.

    * `subscribe`
    * `unsubscribe`
    * `ping`
    * `status`
    * `points`
    * `add`
    * `remove`

    The function will mark any incoming messages/mentions as read, even if they aren't actable. That's going to depend
    on the operator of this script to check the account itself.

    :param: Nothing.
    :return: Nothing.
    """

    # Fetch just the last five unread messages. Ziwen cycles every 30 seconds so this should be sufficient.
    messages = []
    messages += list(reddit.inbox.unread(limit=5))

    for message in messages:
        mauthor = str(message.author)
        msubject = message.subject.lower()  # Convert to lowercase
        mbody = message.body
        message.mark_read()  # Mark the message as read.

        if (
            "subscribe" in msubject and "un" not in msubject
        ):  # User wants to subscribe to language notifications.
            logger.info(
                "[ZW] Messages: New subscription request from u/{}.".format(mauthor)
            )

            # This gets a list of language codes from the message body.
            language_matches = language_list_splitter(mbody)

            if language_matches is None:  # There are no valid codes to subscribe.
                message.reply(
                    MSG_CANNOT_PROCESS.format(MSG_SUBSCRIBE_LINK) + BOT_DISCLAIMER
                )  # Reply to user.
                logger.info(
                    "[ZW] Messages: Subscription languages listed are not valid."
                )
            else:  # There are valid codes. Let's insert them into our database and reply with a confirmation message.
                final_match_names = []

                # Insert the relevant codes.
                notifier_language_list_editer(language_matches, mauthor, "insert")

                # Get the language names of those codes.
                for code in language_matches:
                    final_match_names.append(converter(code)[1])

                # Add the various components of the reply.
                thanks_phrase = MAIN_LANGUAGES.get(language_matches[0], {}).get(
                    "thanks", "Thank you"
                )
                bullet_list = "\n* ".join(final_match_names)
                frequency_table = messaging_language_frequency_table(language_matches)

                # Pull it all together with the template.
                main_body = MSG_SUBSCRIBE.format(
                    thanks_phrase, bullet_list, frequency_table
                )

                # Reply to the subscribing user.
                message.reply(main_body + BOT_DISCLAIMER + MSG_UNSUBSCRIBE_BUTTON)
                logger.info(
                    "[ZW] Messages: Added notification subscriptions for u/"
                    + mauthor
                    + "."
                )
                action_counter(len(language_matches), "Subscriptions")

        elif "unsubscribe" in msubject:  # User wants to unsubscribe from notifications.
            logger.info(
                "[ZW] Messages: New unsubscription request from u/{}.".format(mauthor)
            )

            # This gets a list of language codes from the message body.
            language_matches = language_list_splitter(mbody)

            # Iterate over the results.
            if (
                language_matches is None
            ):  # There are no valid codes to unsubscribe them from.
                # Format the error reply message.
                message.reply(
                    MSG_CANNOT_PROCESS.format(MSG_SUBSCRIBE_LINK) + BOT_DISCLAIMER
                )

                # Forward the message to my creator.
                reddit.redditor("kungming2").message(
                    subject="Unsubscribe Attempt: u/{}".format(mauthor),
                    message="Forwarded message:\n\n---\n\n{}".format(mbody),
                )
                logger.info(
                    "[ZW] Messages: Unsubscription languages listed are invalid. Replied w/ more info."
                )
            elif (
                "all" in language_matches
            ):  # User wants to unsubscribe from everything.
                # Delete the user from the database.
                notifier_language_list_editer(language_matches, mauthor, "purge")

                # Send the reply.
                message.reply(
                    MSG_UNSUBSCRIBE_ALL.format("all", MSG_SUBSCRIBE_LINK)
                    + BOT_DISCLAIMER
                )
                action_counter(1, "Unsubscriptions")
            else:  # Should return a list of specific languages the person doesn't want.
                final_match_names = []

                # Delete the relevant codes.
                notifier_language_list_editer(language_matches, mauthor, "delete")

                # Get the language names of those codes.
                for code in language_matches:
                    final_match_names.append(converter(code)[1])

                # Join the list into a string that is bulleted.
                bullet_list = "\n* ".join(final_match_names)

                # Format the reply message.
                message.reply(
                    MSG_UNSUBSCRIBE_ALL.format(bullet_list, MSG_SUBSCRIBE_LINK)
                    + BOT_DISCLAIMER
                    + MSG_UNSUBSCRIBE_BUTTON
                )
                logger.info(
                    "[ZW] Messages: Removed notification subscriptions for u/"
                    + mauthor
                    + "."
                )
                action_counter(len(language_matches), "Unsubscriptions")

        elif "ping" in msubject:
            logger.info("[ZW] Messages: New status check from u/" + mauthor + ".")
            to_post = "Ziwen is running nominally.\n\n"

            # Determine if user is a moderator.
            if is_mod(mauthor):  # New status check from moderators.
                to_post += (
                    record_retrieve_error_log()
                )  # Get the last two recorded error entries for debugging.
                if len(to_post) > 10000:  # If the PM is too long, shorten it.
                    to_post = to_post[0:9750]
            else:  # Ping from a regular user.
                pass

            # Reply to user.
            message.reply(to_post + BOT_DISCLAIMER)
            logger.info("[ZW] Messages: Replied with ping call.")

        elif "status" in msubject:
            logger.info("[ZW] Messages: New status request from u/" + mauthor + ".")
            final_match_codes = []
            final_match_names = []

            # We try to retrieve the languages the user is subscribed to.
            sql_stat = "SELECT * FROM notify_users WHERE username = ?"
            cursor_main.execute(sql_stat, (mauthor,))
            all_subscriptions = (
                cursor_main.fetchall()
            )  # Returns a list of lists w/ the language code & the username
            for subscription in all_subscriptions:
                final_match_codes.append(
                    subscription[0]
                )  # We only want the language codes (don't need the username).

            # User is not subscribed to anything.
            if len(final_match_codes) == 0:
                status_component = MSG_NO_SUBSCRIPTIONS.format(MSG_SUBSCRIBE_LINK)
            else:
                for code in final_match_codes:  # Convert the codes into names
                    converted_result = converter(code)  # This will return a tuple.
                    match_name = converted_result[1]  # Should get the name from each
                    if code == "meta":
                        match_name = "Meta"
                    elif code == "community":
                        match_name = "Community"
                    elif "unknown-" in code:  # For scripts
                        match_name += " (Script)"
                    final_match_names.append(match_name)

                # De-dupe and sort the returned languages.
                final_match_names = list(set(final_match_names))  # Remove duplicates
                final_match_names = sorted(
                    final_match_names, key=str.lower
                )  # Alphabetize

                # Format the message to send to the requester.
                status_message = (
                    "You're subscribed to notifications on r/translator for:\n\n* {}"
                )
                status_component = status_message.format("\n* ".join(final_match_names))

            # Get the commands the user may have used before.
            user_commands_statistics_data = messaging_user_statistics_loader(mauthor)
            if user_commands_statistics_data is not None:
                commands_component = (
                    "\n\n### User Commands Statistics\n\n"
                    + user_commands_statistics_data
                )
            else:
                commands_component = ""

            # Compile the components together
            compilation = (
                "### Notifications\n\n" + status_component + commands_component
            )

            action_counter(1, "Status checks")
            message.reply(compilation + BOT_DISCLAIMER + MSG_UNSUBSCRIBE_BUTTON)

        elif "add" in msubject and is_mod(
            mauthor
        ):  # Mod manually adding people to the notifications database.
            logger.info(
                "[ZW] Messages: New username addition message from moderator u/{}.".format(
                    mauthor
                )
            )

            # Get the username of the user we want to add to the database.
            add_username = mbody.split("USERNAME:", 1)[1]
            add_username = add_username.split("LANGUAGES", 1)[
                0
            ].strip()  # Get the username (no u/)

            # Split off the languages part.
            language_component = mbody.rpartition("LANGUAGES:")[-1].strip()

            # This gets a list of language codes from the message body.
            language_matches = language_list_splitter(language_component)

            if (
                language_matches is not None
            ):  # In case the moderators' addition string is incomprehensible.
                # Insert the relevant codes.
                notifier_language_list_editer(language_matches, add_username, "insert")

                # Reply to moderator.
                match_codes_print = ", ".join(language_matches)
                addition_message = "Added the language codes **{}** for u/{} into the notifications database."
                message.reply(addition_message.format(match_codes_print, add_username))

        elif "remove" in msubject and is_mod(
            mauthor
        ):  # Mod manually removing people from the notifications database.
            logger.info(
                "[ZW] Messages: New username removal message from moderator u/{}.".format(
                    mauthor
                )
            )

            subscribed_codes = []

            # Get the username of the user we want to add to the database.
            remove_username = mbody.split("USERNAME:", 1)[1].strip()

            # We try to retrieve the languages the user is subscribed to.
            cursor_main.execute(
                "SELECT * FROM notify_users WHERE username = ?", (remove_username,)
            )
            all_subscriptions = (
                cursor_main.fetchall()
            )  # Returns a list of lists with both the code and the username.
            for subscription in all_subscriptions:
                subscribed_codes.append(
                    subscription[0]
                )  # We only want the language codes (no need the username).

            # Actually delete the username from database.
            notifier_language_list_editer([], remove_username, "purge")

            # Send a message back to the moderator confirming this.
            final_match_codes_print = ", ".join(subscribed_codes)
            removal_message = "Removed the subscriptions for u/{} from the notifications database. (**{}**)"
            message.reply(
                removal_message.format(remove_username, final_match_codes_print)
            )

        elif "points" in msubject:
            logger.info(
                "[ZW] Messages: New points status request from u/{}.".format(mauthor)
            )

            # Get the user's points
            user_points_output = "### Points on r/translator\n\n" + points_retreiver(
                mauthor
            )

            # Get the commands the user may have used before.
            user_commands_statistics_data = messaging_user_statistics_loader(mauthor)
            if user_commands_statistics_data is not None:
                commands_component = (
                    "\n\n### Commands Statistics\n\n" + user_commands_statistics_data
                )
            else:
                commands_component = ""

            message.reply(user_points_output + commands_component + BOT_DISCLAIMER)
            action_counter(1, "Points checks")

    return


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
        open(FILE_ADDRESS_OLD_CHINESE, "rt", encoding="utf-8"), delimiter=","
    )
    for row in csv_file:
        my_character = row[0]

        mc_reading = row[2:][
            0
        ]  # It is normally returned as a list, so we need to convert into a string.
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
        to_post = "\n**Middle Chinese** | \**{}*" "\n**Old Chinese** | \*{}*".format(
            character_data[0], character_data[1]
        )
        return to_post


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
        fetchID = Bs(searchResponse.text, "lxml").findAll("a")[0].get("id")
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
            continue

    return entry_url


def zh_character_min_hak(character):
    """
    Function to get the Hokkien and Hakka (Sixian) pronunciations from the ROC Ministry of Education dictionary.
    This actually will accept either single-characters or multi-character words.
    For more information, visit: https://www.moedict.tw/

    :param character: A single Chinese character or word.
    :return: A string. If nothing is found the string will have zero length.
    """

    # Fetch Hokkien results
    min_page = requests.get(
        "https://www.moedict.tw/'{}".format(character), headers=ZW_USERAGENT
    )
    min_tree = html.fromstring(min_page.content)  # now contains the whole HTML page

    # The annotation returns as a list, we want to take the first one.
    try:
        min_reading = min_tree.xpath(
            '//ru[contains(@class,"rightangle") and contains(@order,"0")]/@annotation'
        )[0]
        min_reading = "\n**Southern Min** | *{}*".format(min_reading)
    except IndexError:  # No character or word found.
        min_reading = ""

    # Fetch Hakka results (Sixian)
    hak_page = requests.get(
        "https://www.moedict.tw/:{}".format(character), headers=ZW_USERAGENT
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
            hak_reading = re.sub(
                r"(\d{1,4})([a-z])", r"\1 ", hak_reading
            )  # Add spaces between words.
            hak_reading = hak_reading.split(" ")
            for word in hak_reading:
                new_word = re.sub(r"([a-z])(\d)", r"\1^(\2", word)
                new_word += ")"
                hak_reading_new.append(new_word)
            hak_reading = " ".join(hak_reading_new)

            hak_reading = "\n**Hakka (Sixian)** | *{}*".format(hak_reading)
    except IndexError:  # No character or word found.
        hak_reading = ""

    # Combine them together.
    to_post = min_reading + hak_reading

    return to_post


def zh_character_calligraphy_search(character):
    """
    A function to get an overall image of Chinese calligraphic search containing different styles from various time
    periods.

    :param character: A single Chinese character.
    :return: None if no image found, a formatted string containing the relevant URLs and images otherwise.
    """

    character = simplify(character)

    # First get data from http://sfds.cn (this will be included as a URL)
    unicode_assignment = hex(ord(character)).upper()[
        2:
    ]  # Get the Unicode assignment (eg 738B)
    gx_url = "http://www.sfds.cn/{}/".format(unicode_assignment)

    # Secondly, get variant data from the MoE dictionary.
    variant_link = zh_character_variant_search(tradify(character))
    if variant_link:
        variant_formatted = "[YTZZD]({})".format(variant_link)
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
        tree = Bs(rdata.content, "lxml")
        tree = str(tree)
        tree = html.fromstring(tree)
    except (
        requests.exceptions.ConnectionError
    ):  # If there's a connection error, return None.
        return None

    images = tree.xpath("//img/@src")
    complete_image = ""
    image_string = None

    if images is not None:
        for url in images:
            if len(url) < 20:  # We don't need short links.
                continue
            if "gif" in url:  # Or GIFs
                continue

            if (
                "shufa6" in url
            ):  # We try to get the broader summation image instead of the thumbnail.
                complete_image = url.replace("shufa6/1", "shufa6")

        if len(complete_image) != 0:
            logger.debug(
                "[ZW] ZH-Calligraphy: There is a Chinese calligraphic image for "
                + character
                + "."
            )
            image_format = (
                "\n\n**Chinese Calligraphy Variants**: [{}]({}) (*[SFZD](http://www.shufazidian.com/)*, "
                "*[SFDS]({})*, *{}*)"
            )
            image_string = image_format.format(
                character, complete_image, gx_url, variant_formatted
            )
    else:
        image_string = None

    if image_string is None:
        return None
    else:
        return image_string


def zh_character_other_readings(character):
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
    u_url = "http://ccdb.hemiola.com/characters/string/{}?fields=kHangul,kKorean,kJapaneseKun,kJapaneseOn,kVietnamese"
    unicode_rep = requests.get(u_url.format(character), headers=ZW_USERAGENT)
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
            if ja_kun is not None:
                ja_kun = (
                    ja_kun.lower() + " "
                )  # A space is added since the kun appears first
            else:
                ja_kun = ""
            if ja_on is not None:
                ja_on = ja_on.upper()
            else:
                ja_on = ""

            # Recombine the readings
            ja_total = ja_kun + ja_on
            ja_total = ja_total.strip().split(" ")
            ja_total = ", ".join(ja_total)
            ja_string = "**Japanese** | *{}*".format(ja_total)
            to_post.append(ja_string)
    if "kHangul" in unicode_rep_jdict and "kKorean" in unicode_rep_jdict:
        ko_hangul = unicode_rep_jdict["kHangul"]
        # We apply RR romanization to this.
        if ko_hangul is not None:
            ko_latin = Romanizer(ko_hangul).romanize().lower()
            ko_latin = ko_latin.replace(" ", ", ")  # Replace spaces with commas
            ko_hangul = ko_hangul.replace(" ", ", ")  # Replace spaces with commas
            ko_total = "{} / *{}*".format(ko_hangul, ko_latin)
            ko_string = "**Korean** | {}".format(ko_total)
            to_post.append(ko_string)
    if "kVietnamese" in unicode_rep_jdict:
        vi_latin = unicode_rep_jdict["kVietnamese"]
        if vi_latin is not None:
            vi_latin = vi_latin.lower()
            vi_string = "**Vietnamese** | *{}*".format(vi_latin)
            to_post.append(vi_string)

    if len(to_post) > 0:
        to_post = "\n".join(to_post)
        return to_post
    else:
        return None


def zh_character(character):
    """
    This function looks up a Chinese character's pronunciations and meanings.
    It also ties together a lot of the other reference functions above.

    :param character: Any Chinese character.
    :return: A formatted string containing the character's information.
    """

    multi_mode = False
    multi_character_dict = {}
    multi_character_list = list(character)

    if (
        len(multi_character_list) > 1
    ):  # Whether or not multiple characters are passed to this function
        multi_mode = True

    eth_page = requests.get(
        "https://www.mdbg.net/chinese/dictionary?page=chardict&cdcanoce=0&cdqchi="
        + character,
        headers=ZW_USERAGENT,
    )
    tree = html.fromstring(eth_page.content)  # now contains the whole HTML page
    pronunciation = [
        div.text_content() for div in tree.xpath('//div[contains(@class,"pinyin")]')
    ]
    # Note that the Yue pronunciation is given as `['zyun2, zyun3']`
    cmn_pronunciation, yue_pronunciation = pronunciation[::2], pronunciation[1::2]

    if len(pronunciation) == 0:  # Check to not return anything if the entry is invalid
        to_post = COMMENT_INVALID_ZH_CHARACTER.format(character)
        logger.info("[ZW] ZH-Character: No results for {}".format(character))
        return to_post

    if not multi_mode:  # Regular old-school character search for just one.
        cmn_pronunciation = " / ".join(cmn_pronunciation)
        yue_pronunciation = tree.xpath(
            '//a[contains(@onclick,"pronounce-jyutping")]/text()'
        )
        yue_pronunciation = " / ".join(yue_pronunciation)
        # Add superscript to the numbers. Wrapped in paragraphs so that
        # it displays the same on both New and Old Reddit.
        for i in range(0, 9):
            yue_pronunciation = yue_pronunciation.replace(str(i), "^(%s " % str(i))
        for i in range(0, 9):
            yue_pronunciation = yue_pronunciation.replace(str(i), "%s)" % str(i))

        meaning = tree.xpath('//div[contains(@class,"defs")]/text()')
        meaning = "/ ".join(meaning)
        meaning = meaning.strip()

        if tradify(character) == simplify(character):
            logger.debug(
                "[ZW] ZH-Character: The two versions of {} are identical.".format(
                    character
                )
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
                "[ZW] ZH-Character: The two versions of {} are *not* identical.".format(
                    character
                )
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
        min_hak_data = zh_character_min_hak(tradify(character))
        lookup_line_1 += min_hak_data

        # Old Chinese
        try:  # Try to get old chinese data.
            ocmc_pronunciation = zh_character_oc_search(tradify(character))
            if ocmc_pronunciation is not None:
                lookup_line_1 += ocmc_pronunciation
        except IndexError:  # There was an error; character has no old chinese entry
            lookup_line_1 = lookup_line_1

        # Other Language Readings
        other_readings_data = zh_character_other_readings(tradify(character))
        if other_readings_data is not None:
            lookup_line_1 += "\n" + other_readings_data

        calligraphy_image = zh_character_calligraphy_search(character)
        if calligraphy_image is not None:
            lookup_line_1 += calligraphy_image
        else:  # No image found
            lookup_line_1 = lookup_line_1

        lookup_line_1 += str('\n\n**Meanings**: "' + meaning + '."')
    else:  # It's multiple characters, let's make a table.
        # MULTIPLE Start iterating over the characters we have
        if tradify(character) == simplify(character):
            duo_key = "# {}".format(character)
        else:  # Different versions, different header.
            duo_key = "# {} ({})".format(tradify(character), simplify(character))
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
            new_eth_page = requests.get(character_url, headers=ZW_USERAGENT)
            new_tree = html.fromstring(
                new_eth_page.content
            )  # now contains the whole HTML page
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
                yue_pronunciation = yue_pronunciation.replace(str(i), "^%s " % str(i))
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
            duo_mandarin += " | {}".format(character_data["mandarin"])
            duo_cantonese += " | {}".format(character_data["cantonese"])
            duo_meaning += " | {}".format(character_data["meaning"])

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

    to_post = lookup_line_1 + lookup_line_2
    logger.info(
        "[ZW] ZH-Character: Received lookup command for {} in "
        "Chinese. Returned search results.".format(character)
    )

    return to_post


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
    f = open(FILE_ADDRESS_ZH_BUDDHIST, "r", encoding="utf-8")
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
        else:
            continue

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
    else:  # Nothing found.
        return None


def zh_word_cccanto_search(cantonese_word):
    """
    Function that parses and returns data from the CC-Canto database, which uses CC-CEDICT's format.
    More information can be found here: https://cantonese.org/download.html

    :param cantonese_word: Any Cantonese word. This should be in its *traditional* form.
    :return: None if there is nothing that matches, a dictionary with content otherwise.
    """
    general_dictionary = {}

    # We open the file.
    f = open(FILE_ADDRESS_ZH_CCCANTO, "r", encoding="utf-8")
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
        else:
            continue

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
                str(i), "^%s " % str(i)
            )  # Adds syntax for tones
        keywords["jyutping"] = (
            keywords["jyutping"].replace("  ", " ").strip()
        )  # Replace double spaces

        general_dictionary["meaning"] = formatted_line
        general_dictionary["pinyin"] = keywords["pinyin"]
        general_dictionary["jyutping"] = keywords["jyutping"]

        return general_dictionary
    else:
        return None


# noinspection PyBroadException
def zh_word_tea_dictionary_search(chinese_word):
    """
    Function that searches the Babelcarp Chinese Tea Lexicon for Chinese tea terms.

    :param chinese_word: Any Chinese word in *simplified* form.
    :return: None if there is nothing that matches, a formatted string with meaning otherwise.
    """
    general_dictionary = {}

    # Conduct a search.
    web_search = (
        "http://babelcarp.org/babelcarp/babelcarp.cgi?phrase={}&define=1".format(
            chinese_word
        )
    )
    eth_page = requests.get(web_search, headers=ZW_USERAGENT)
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

    if (
        chinese_word not in head_word
    ):  # If the characters don't match: Exit. This includes null searches.
        return None
    else:  # It exists.
        try:
            pinyin = re.search(r"\((.*?)\)", word_content[2]).group(1).lower()
        except AttributeError:  # Never mind, it does not exist.
            return None

        meaning = word_content[3:]
        meaning = [item.strip() for item in meaning]

        # Format the entry to return
        formatted_line = '\n\n**Tea Meanings**: "{}."'.format(" ".join(meaning))
        formatted_line = formatted_line.replace(" )", " ")
        formatted_line = formatted_line.replace("  ", " ")
        formatted_line += " ([Babelcarp]({}))".format(web_search)  # Append source

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
        open(FILE_ADDRESS_ZH_ROMANIZATION, "rt", encoding="utf-8"), delimiter=","
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
        if tone is not "5":  # Add tone as superscript
            yale_equiv = "{}^({})".format(corresponding_dict[syllable][0], tone)
            wadegiles_equiv = "{}^({})".format(corresponding_dict[syllable][1], tone)
        else:  # Null tone, no need to add a number.
            yale_equiv = "{}".format(corresponding_dict[syllable][0])
            wadegiles_equiv = "{}".format(corresponding_dict[syllable][1])
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
        logger.info("[ZW] ZH-Chengyu: No chengyu results found for {}.".format(chengyu))
        return None
    elif r_tree is not None:  # There are results.
        # Look through the results page.
        link_results = r_tree.xpath('//tr[contains(@bgcolor,"#ffffff")]/td/a')
        try:
            actual_link = link_results[0].attrib["href"]
        except IndexError:
            return None
        logger.info(
            "[ZW] > ZH-Chengyu: Found a chengyu. Actual link at: {}".format(actual_link)
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
            "[ZW] > ZH-Chengyu: Looked up the chengyu {} in Chinese. Returned search results.".format(
                chengyu
            )
        )

        return cy_to_post


def zh_word(word):
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
        headers=ZW_USERAGENT,
    )
    tree = html.fromstring(eth_page.content)  # now contains the whole HTML page
    word_exists = str(tree.xpath('//p[contains(@class,"nonprintable")]/strong/text()'))
    cmn_pronunciation = tree.xpath('//div[contains(@class,"pinyin")]/a/span/text()')
    cmn_pronunciation = cmn_pronunciation[
        0 : len(word)
    ]  # We only want the pronunciations to be as long as the input
    cmn_pronunciation = "".join(
        cmn_pronunciation
    )  # We don't need a dividing character per pinyin standards

    # Check to not return anything if the entry is invalid
    if "No results found" in word_exists:
        # First we try to check our specialty dictionaries. Buddhist dictionary first. Then the tea dictionary.
        search_results_buddhist = zh_word_buddhist_dictionary_search(tradify(word))
        search_results_tea = zh_word_tea_dictionary_search(simplify(word))
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
                "[ZW] ZH-Word: No results for word {}, but results are in specialty dictionaries.".format(
                    word
                )
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
            py_split_pronunciation = py_split_pronunciation.split("'", 1)[0][
                1:
            ].strip()  # Format it nicely.
            alt_romanize = zh_word_alt_romanization(py_split_pronunciation)
        except (
            IndexError
        ):  # This likely means that the page does not contain that information.
            alt_romanize = ("---", "---")

        meaning = [
            div.text_content() for div in tree.xpath('//div[contains(@class,"defs")]')
        ]
        meaning = [
            x for x in meaning if x != " "
        ]  # This removes any empty spaces that are in the list.
        meaning = [
            x for x in meaning if x != ", "
        ]  # This removes any extraneous commas that are in the list
        meaning = "/ ".join(meaning)
        meaning = meaning.strip()

        # Obtain the Cantonese information.
        yue_page = requests.get(
            "https://cantonese.org/search.php?q=" + word, headers=ZW_USERAGENT
        )
        yue_tree = html.fromstring(yue_page.content)  # now contains the whole HTML page
        yue_pronunciation = yue_tree.xpath(
            '//h3[contains(@class,"resulthead")]/small/strong//text()'
        )
        yue_pronunciation = yue_pronunciation[
            0 : (len(word) * 2)
        ]  # This Len needs to be double because of the numbers
        yue_pronunciation = iter(yue_pronunciation)
        yue_pronunciation = [c + next(yue_pronunciation, "") for c in yue_pronunciation]

        # Combines the tones and the syllables together
        yue_pronunciation = " ".join(yue_pronunciation)
        for i in range(0, 9):
            yue_pronunciation = yue_pronunciation.replace(
                str(i), "^(%s) " % str(i)
            )  # Adds Markdown syntax
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
    readings_line = (
        "\n**Mandarin** (Pinyin) | *{}*\n**Mandarin** (Wade-Giles) | *{}*"
        "\n**Mandarin** (Yale) | *{}*\n**Cantonese** | *{}*"
    )
    readings_line = readings_line.format(
        cmn_pronunciation, alt_romanize[1], alt_romanize[0], yue_pronunciation
    )
    lookup_line_1 += readings_line

    # Add Hokkien and Hakka data.
    min_hak_data = zh_character_min_hak(tradify(word))
    lookup_line_1 += min_hak_data

    # Format the meaning line.
    if len(alternate_meanings) == 0:
        # Format the regular results we have.
        lookup_line_2 = str('\n\n**Meanings**: "' + meaning + '."')

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
        "[ZW] ZH-Word: Received a lookup command for "
        + word
        + " in Chinese. Returned search results."
    )
    return to_post


def ja_character(character):
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
            "http://jisho.org/search/{}%20%23particle".format(character),
            headers=ZW_USERAGENT,
        )
        tree = html.fromstring(eth_page.content)  # now contains the whole HTML page
        meaning = tree.xpath('//span[contains(@class,"meaning-meaning")]/text()')
        meaning = " / ".join(meaning)
        is_kana = True
        total_data = "# [{0}](https://en.wiktionary.org/wiki/{0}#Japanese)".format(kana)
        total_data += " (*{}*)".format(romkan.to_hepburn(kana))
        total_data += '\n\n**Meanings**: "{}."'.format(meaning)
    else:
        if not multi_mode:
            # Regular old-school one character search.
            eth_page = requests.get(
                "http://jisho.org/search/" + character + "%20%23kanji",
                headers=ZW_USERAGENT,
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
                logger.info("[ZW] JA-Character: No results for {}".format(character))
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
                lookup_line_1 = lookup_line_1 + calligraphy_image
            else:  # No character exists
                lookup_line_1 = lookup_line_1

            lookup_line_2 = str('\n\n**Meanings**: "' + meaning + '."')

            total_data = lookup_line_1 + lookup_line_2

        elif multi_mode:
            # MULTIPLE Start iterating over the characters we have
            ooi_key = "# {}".format(character)
            ooi_header = "\n\nCharacter "
            ooi_separator = "\n---|"
            ooi_kun = "\n**Kun-readings**"
            ooi_on = "\n**On-readings** "
            ooi_meaning = "\n**Meanings** "

            for moji in multi_character_list:
                multi_character_dict[moji] = {}  # Create a new null dictionary

                eth_page = requests.get(
                    "http://jisho.org/search/" + moji + "%20%23kanji",
                    headers=ZW_USERAGENT,
                )
                tree = html.fromstring(
                    eth_page.content
                )  # now contains the whole HTML page

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
                ooi_kun += " | {}".format(character_data["kun"])
                ooi_on += " | {}".format(character_data["on"])
                ooi_meaning += " | {}".format(character_data["meaning"])

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


def ja_word_sfx(katakana_string):
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
    search_url = "http://thejadednetwork.com/sfx/search/?keyword=+{}&submitSearch=Search+SFX&x=".format(
        katakana_string
    )

    # Conduct a search.
    eth_page = requests.get(search_url, headers=ZW_USERAGENT)
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
        sound_data = [
            x for x in sound_data if len(x.strip()) > 0
        ]  # Take away the blanks.

        # Double-check the entry to make sure it's right.
        katakana_entry = sound_data[4].strip().replace(",", "")
        if katakana_entry != katakana_string:
            return None

        # Parse data, assign variables.
        katakana_reading = "{} (*{}*)".format(
            katakana_string, romkan.to_hepburn(katakana_string)
        )
        sound_effect = sound_data[7].replace("*", r"\*")
        sound_explanation = sound_data[8].strip().replace("*", r"\*")

        # Create the formatted comment.
        formatted_line = (
            "\n\n**English Equivalent**: {}\n\n**Explanation**: {} ".format(
                sound_effect, sound_explanation
            )
        )
        formatted_line += "\n\n\n^Information ^from [^SFX ^Dictionary]({})".format(
            actual_link
        )
        header = "# [{0}](https://en.wiktionary.org/wiki/{0}#Japanese)\n\n##### *Sound effect*\n\n**Reading:** {1}{2}"
        finished_comment = header.format(
            katakana_string, katakana_reading, formatted_line
        )

        logger.info(
            "[ZW] JA-Word-SFX: Found a dictionary entry for {} at {}".format(
                katakana_string, actual_link
            )
        )

        return finished_comment
    else:  # We do not have any results.
        return None


def ja_word_given_name_search(ja_given_name):
    """
    A function to get the kanji readings of Japanese given names, which may not necessarily be in dictionaries.
    This also returns readings of place names, such as temples.

    :param ja_given_name: A Japanese given name, in kanji *only*.
    :return formatted_section: A chunk of text with readings and meanings of the character.
    """

    names_w_readings = []

    # Conduct a search.
    web_search = "http://kanji.reader.bz/{}".format(ja_given_name, headers=ZW_USERAGENT)
    eth_page = requests.get(web_search)
    tree = html.fromstring(eth_page.content)  # now contains the whole HTML page
    name_content = tree.xpath('//div[contains(@id,"main")]/p[1]/text()')
    hiragana_content = tree.xpath('//div[contains(@id,"main")]/p[1]/a/text()')
    print(name_content)
    print(hiragana_content)

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
        name_formatted = name.strip()
        furigana_chunk = "{} (*{}*)".format(
            name_formatted, name_content[hiragana_content.index(name)].title()
        )
        names_w_readings.append(furigana_chunk)
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


def ja_word_surname(name):
    """
    Function to get a Japanese surname (backup if a word search fails).

    :param name: Any Japanese surname (usually two kanji long).
    :return None: if no results, otherwise return a formatted string.
    """

    eth_page = requests.get(
        "https://myoji-yurai.net/searchResult.htm?myojiKanji=" + name,
        headers=ZW_USERAGENT,
    )
    tree = html.fromstring(eth_page.content)  # now contains the whole HTML page
    ja_reading = tree.xpath('//div[contains(@class,"post")]/p/text()')
    ja_reading = str(ja_reading[0])[4:].split(",")
    if len(str(ja_reading)) <= 4:  # This indicates that it's blank. No results.
        return None
    elif len(name) < 2:
        return None
    else:
        furigana_chunk = ""
        for reading in ja_reading:
            furigana_chunk_new = (
                reading.strip() + " (*" + romkan.to_hepburn(reading).title() + "*)"
            )
            furigana_chunk = furigana_chunk + ", " + furigana_chunk_new
        lookup_line_1 = (
            "# [{0}](https://en.wiktionary.org/wiki/{0}#Japanese)\n\n".format(name)
        )
        lookup_line_1 += (
            "**Readings:** " + furigana_chunk[2:]
        )  # We return the formatted readings of this name
        lookup_line_2 = str("\n\n**Meanings**: A Japanese surname.")
        lookup_line_3 = "\n\n\n^Information ^from [^Myoji](https://myoji-yurai.net/searchResult.htm?myojiKanji={0}) "
        lookup_line_3 += "^| [^Weblio ^EJJE](https://ejje.weblio.jp/content/{0})"
        lookup_line_3 = lookup_line_3.format(name)
        to_post = lookup_line_1 + lookup_line_2 + "\n" + lookup_line_3
        logger.info(
            "[ZW] JA-Name: '{}' is a Japanese name. Returned search results.".format(
                name
            )
        )
        return to_post


def ja_word(japanese_word):
    """
    A newer function that uses Jisho's unlisted API in order to return data from Jisho.org for Japanese words.
    See here for more information: https://jisho.org/forum/54fefc1f6e73340b1f160000-is-there-any-kind-of-search-api
    Keep in mind that the API is in many ways more limited than the actual search stack (e.g. no kanji results)

    :param japanese_word: Any word that is expected to be Japanese and longer than a single character.
    :return: A formatted string for use in a comment reply.
    """

    y_data = None

    # Fetch data from the API
    link_json = "https://jisho.org/api/v1/search/words?keyword={}%20%23words".format(
        japanese_word
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
            "[ZW] JA-Word: No results found for a Japanese word '{}'.".format(
                japanese_word
            )
        )

        katakana_test = re.search(
            "[\u30a0-\u30ff]", japanese_word
        )  # Check if katakana. Will return none if kanji.
        surname_data = ja_word_surname(japanese_word)  # Check to see if it's a surname.
        sfx_data = ja_word_sfx(japanese_word)
        given_name_data = ja_word_given_name_search(japanese_word)

        # Test against the other dictionary modules.
        if surname_data is None and sfx_data is None and given_name_data is None:
            if katakana_test is None:  # It's a character
                to_post = ja_character(japanese_word)
                logger.info(
                    "[ZW] JA-Word: No results found for a Japanese name. Getting individual character data."
                )
            else:
                to_post = "There were no results for `{}`.".format(japanese_word)
                logger.info("[ZW] JA-Word: Unknown katakana word. No results.")
            return to_post
        elif surname_data is not None:
            logger.info("[ZW] JA-Word: Found a matching Japanese surname.")
            return surname_data
        elif given_name_data is not None:
            logger.info("[ZW] JA-Word: Found a matching Japanese given name.")
            return given_name_data
        elif sfx_data is not None:
            logger.info("[ZW] JA-Word: Found matching Japanese sound effects.")
            return sfx_data

    # Jisho data is good, format the data from the returned JSON.
    word_reading_chunk = "{} (*{}*)".format(
        word_reading, romkan.to_hepburn(word_reading)
    )
    word_meaning = main_data["senses"][0]["english_definitions"]
    word_meaning = '"{}."'.format(", ".join(word_meaning))
    word_type = main_data["senses"][0]["parts_of_speech"]
    word_type = "*{}*".format(", ".join(word_type))

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
        y_data = ja_word_yojijukugo(japanese_word)
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
        "[ZW] JA-Word: Received a lookup command for the word '{}' in Japanese.".format(
            japanese_word
        )
    )

    return return_comment


def ja_word_yojijukugo(yojijukugo):
    """
    A newer rewrite of the yojijukugo function that has been changed to match the zh_word_chengyu function.
    That is, now its role is to grab a Japanese meaning and explanation in order to give some insight.
    For examples, see https://www.edrdg.org/projects/yojijukugo.html

    :param yojijukugo: Any four-kanji Japanese idiom.
    :return: A formatted string for addition to ja_word or None if nothing is found.
    """

    # Fetch the page and its data.
    url_search = (
        "https://yoji.jitenon.jp/cat/search.php?getdata={}&search=part&page=1".format(
            yojijukugo
        )
    )
    eth_page = requests.get(url_search, headers=ZW_USERAGENT)
    tree = html.fromstring(eth_page.content)  # now contains the whole HTML page
    url = tree.xpath('//th[contains(@scope,"row")]/a/@href')

    if len(url) != 0:  # There's data. Get the url.
        url_entry = url[0]  # Get the actual url of the entry.
        entry_page = requests.get(url_entry, headers=ZW_USERAGENT)
        entry_tree = html.fromstring(
            entry_page.content
        )  # now contains the whole HTML page

        # Check to make sure the data is the same.
        entry_title = entry_tree.xpath("//h1/text()")[0]
        entry_title = entry_title.split("」", 1)[0][
            1:
        ]  # Retrieve only the main title of the page.
        if entry_title != yojijukugo:  # If the data doesn't match
            logger.debug("[ZW] JA-Chengyu: The titles don't match.")
            return None

        # Format the data properly.
        row_data = [td.text_content() for td in entry_tree.xpath("//td")]
        y_meaning = row_data[1].strip()
        y_meaning = "\n\n**Japanese Explanation**: {}\n\n".format(y_meaning)
        logger.info(
            "[ZW] JA-Chengyu: Retrieved information on {} from {}.".format(
                yojijukugo, url_entry
            )
        )

        # Add the literary source.
        y_source = row_data[2].strip()
        y_source = "**Literary Source**: {}".format(y_source)

        y_meaning += y_source
        return y_meaning
    else:
        return None


# General Lookup Functions
def lookup_cjk_matcher(content_text):
    """
    A simple function to allow for compatibility with a greater number of CJK characters.
    This function can be expanded in the future to support more languages and be more robust.
    normal_returned_matches = re.findall('`([\u2E80-\u9FFF]+)`', content_text, re.DOTALL)
    This is a DEPRECATED routine that is NOT currently used. Normally will output a list with breakdowns.

    :param content_text: The body text of the comment we are parsing.
    :return: A list of all matching Chinese characters.
    """

    # Making sure we only have stuff between the graves.
    try:
        content_text = content_text.split("`", 1)[1]  # Delete stuff before
        content_text = content_text.rsplit("`", 1)[0]  # Delete stuff after
        content_text = "`{}`".format(content_text)  # Re-add the graves.
    except IndexError:  # Split improperly
        return []

    content_text = content_text.replace(
        " ", "``"
    )  # Delete spaces, we don't need this for CJK.
    content_text = content_text.replace(
        "\\", ""
    )  # Delete slashes, since the redesign may introduce them.

    # Regular CJK Unified Ideographs range with CJK Unified Ideographs Extension A
    matches = re.findall("`([\u2E80-\u9FFF]+)`", content_text, re.DOTALL)

    # CJK Unified Ideographs Extension B-F (obscure characters that do not have online sources)
    b_matches = re.findall("`([\U00020000-\U0002EBEF]+)`", content_text, re.DOTALL)

    if len(b_matches) != 0:  # We found something in the B sets
        for match in b_matches:
            if not any(
                match in s for s in matches
            ):  # Make sure the a match is not already in the regular set.
                matches.append(match)

    if len(matches) != 0:
        return matches
    else:
        return []


def lookup_matcher(content_text, language_name):
    """
    A general-purpose function that evaluates a comment for lookup and returns the detected text in a dictionary keyed
    by the language that's passed to it. This function also tokenizes spaced languages and Chinese/Japanese.

    :param content_text: The text of the comment to search.
    :param language_name: The language the post was originally in. If it's set to None, it'll just return everything
                          that's in between the graves. The None setting is used in edit_finder.
    :return: A dictionary indexing the lookup terms with a language. {'Japanese': ['高校', 'マレーシア']}
             None if there was no valid information found.
             Note that if the language_name is set to None the function returns a LIST not a DICTIONARY.
    """
    original_text = str(content_text)
    master_dictionary = {}
    language_mentions = language_mention_search(content_text)

    # If there is an identification command, we should classify this as the identified language.
    # First we check to see if there is another identification command here.
    if "!identify:" in original_text:
        # Parse the data from the command.
        parsed_data = comment_info_parser(original_text, "!identify:")[0]

        # Code to help make sense of CJK script codes if they're identified.
        language_keys = ["Chinese", "Japanese", "Korean"]
        for key in language_keys:
            if len(parsed_data) == 4 and parsed_data.title() in CJK_LANGUAGES[key]:
                parsed_data = key

        # Set the language name to the identified language.
        language_name = converter(parsed_data)[1]
    # Secondly we see if there's a language mentioned.
    elif language_mention_search(content_text) is not None:
        if len(language_mentions) == 1:
            language_name = language_mentions[0]

    # Work with the text and clean it up.
    try:
        content_text = content_text.split("`", 1)[1]  # Delete stuff before
        content_text = content_text.rsplit("`", 1)[0]  # Delete stuff after
        content_text = "`{}`".format(content_text)  # Re-add the graves.
    except IndexError:  # Split improperly
        return []
    content_text = content_text.replace(
        " ", "``"
    )  # Delete spaces, we don't need this for CJK.
    content_text = content_text.replace(
        "\\", ""
    )  # Delete slashes, since the redesign may introduce them.
    matches = re.findall("`(.*?)`", content_text, re.DOTALL)

    # Tokenize, remove empty strings
    for match in matches:
        if " " in match:  # This match contains a space, so let's split it.
            new_matches = match.split()
            matches.remove(match)
            matches.append(new_matches)
    matches = [x for x in matches if x]

    combined_text = "".join(
        matches
    )  # A simple string to allow for quick detection of languages that fall in Unicode.
    zhja_true = re.findall("([\u2E80-\u9FFF]+)", combined_text, re.DOTALL)
    zh_b_true = re.findall("([\U00020000-\U0002EBEF]+)", combined_text, re.DOTALL)
    kana_true = re.findall(
        "([\u3041-\u309f]+|[\u30a0-\u30ff]+)", combined_text, re.DOTALL
    )
    ko_true = re.findall(
        "([\uac00-\ud7af]+)", combined_text, re.DOTALL
    )  # Checks if there's hangul there

    if language_name is None:
        return matches

    if zhja_true:  # Chinese or Japanese Characters were detected.
        zhja_temp_list = []
        for match in matches:
            zhja_matches = re.findall(
                "([\u2E80-\u9FFF]+|[\U00020000-\U0002EBEF]+)", match, re.DOTALL
            )
            if zhja_matches:
                for selection in zhja_matches:
                    zhja_temp_list.append(selection)
        logger.debug("[ZW] Lookup_Matcher: Provisional: {}".format(zhja_temp_list))

        # Tokenize them.
        tokenized_list = []
        for item in zhja_temp_list:
            if len(item) >= 2:  # Longer than bisyllabic?
                if language_name is "Chinese" and not kana_true:
                    new_matches = lookup_zhja_tokenizer(simplify(item), "zh")
                elif language_name is "Japanese" or kana_true:
                    new_matches = lookup_zhja_tokenizer(item, "ja")
                else:
                    new_matches = [item]
                for new_word in new_matches:
                    tokenized_list.append(new_word)
            else:
                tokenized_list.append(item)

        if not kana_true:  # There's kana, so we'll mark this as Japanese.
            master_dictionary[language_name] = tokenized_list
        else:
            master_dictionary["Japanese"] = tokenized_list

    # There's text with Hangul, add it to the master dictionary with an Index of Korean.
    if ko_true:
        ko_temp_list = []
        for match in matches:
            ko_matches = re.findall("([\uac00-\ud7af]+)", match, re.DOTALL)
            if ko_matches:  # If it's actually containing data, let's append it.
                for selection in ko_matches:
                    ko_temp_list.append(selection)
        master_dictionary["Korean"] = ko_temp_list

    # Create a master list of all CJK languages to check against.
    all_cjk = []
    for value in CJK_LANGUAGES.values():
        all_cjk += value

    # For all other languages.
    if (
        len(zhja_true + zh_b_true + kana_true + ko_true) == 0
    ):  # Nothing CJK-related. True if all are empty.
        if (
            len(matches) != 0 and language_name not in all_cjk
        ):  # Making sure we don't return Latin words in CJK.
            other_temp_list = []
            for match in matches:
                other_temp_list.append(match)
            other_temp_list = [
                i for n, i in enumerate(other_temp_list) if i not in other_temp_list[:n]
            ]  # De-dupe
            master_dictionary[language_name] = other_temp_list

    return master_dictionary


def lookup_ko_word(word):
    """
    A function to define Korean words from KRDICT.
    Deprecated.

    :param word: Any Korean word.
    :return: A formatted string containing meanings and information to post as a comment.
    """

    eth_page = requests.get(
        "https://krdict.korean.go.kr/m/eng/searchResult?nationCode=6"
        "&nation=eng&divSearch=search&pageNo=1&displayNum=10&preKeyword="
        "&sort=&proverb=&examples=&mainSearchWord=" + word
    )

    tree = html.fromstring(eth_page.content)  # now contains the whole HTML page
    # word_exists = str(tree.xpath('//strong[@class="highlight"]/text()[1]'))
    word_exists = str(tree.xpath('//em[@class="blue ml5"]/text()[1]'))
    print(word_exists)

    if (
        "없습니다" in word_exists
    ):  # Check to not return anything if the entry is invalid (means "there is not")
        to_post = str("> Sorry, but that Korean word doesn't look like anything to me.")
        return to_post
    else:
        hangul_romanization = Romanizer(word).romanize()
        hangul_chunk = word + " (*" + hangul_romanization + "*)"
        hanja = tree.xpath('//*[@id="content"]/div[2]/dl/dt[1]/span/text()')
        if len(hanja) != 0:
            hanja = "".join(hanja)
            hanja = hanja.strip()
        meaning = tree.xpath('//*[@id="content"]/div[2]/dl/dd[1]/div/p[1]//text()')
        meaning = " ".join(meaning)
        meaning = " ".join(meaning.split())

        if len(hanja) != 0:
            lookup_line_1 = (
                "# [{0}](https://en.wiktionary.org/wiki/{0}#Korean)\n\n".format(word)
            )
            lookup_line_1 += "**Reading:** " + hangul_chunk + " (" + hanja + ")"
        else:
            lookup_line_1 = (
                "# [{0}](https://en.wiktionary.org/wiki/{0}#Korean)\n\n".format(word)
            )
            lookup_line_1 += "**Reading:** " + hangul_chunk
        lookup_line_2 = str('\n\n**Meanings**: "' + meaning + '."')
        lookup_line_3 = (
            "\n\n\n^Information ^from ^[Naver](https://en.dict.naver.com/#/"
            "search?range=all&query={0}) ^| ^[Daum](https://dic.daum.net/search.do?q={0}&dic=eng)"
        )
        lookup_line_3 = lookup_line_3.format(word)

        to_post = lookup_line_1 + lookup_line_2 + lookup_line_3
        logger.info(
            "[ZW] lookup_ko_word: Received a word lookup for '{}' in Korean. Returned results.".format(
                word
            )
        )
        return to_post


def lookup_zhja_tokenizer(phrase, language):
    """
    Language should be 'zh' or 'ja'. Returns a list of tokenized words. This uses Jieba for Chinese and either
    TinySegmenter or MeCab for Japanese. The live version should be using MeCab as it is running on Linux.
    This function is used by lookup_matcher.

    It will dynamically change the segmenters / tokenizers based on the OS. On Windows for testing it can use
    TinySegmenter for compatibility. But on Mac/Linux, we can use MeCab's dictionary instead for better
    (but not perfect) tokenizing. See https://www.robfahey.co.uk/blog/japanese-text-analysis-in-python/ for more info.

    :param phrase: The phrase we are seeking to tokenize.
    :param language: Which language it is for, expressed as a code.
    """

    word_list = []
    final_list = []
    if language == "zh":
        seg_list = jieba.cut(phrase, cut_all=False)
        for item in seg_list:
            word_list.append(item)
    elif language == "ja":
        if sys.platform == "win32":  # Windows
            segmenter = tinysegmenter.TinySegmenter()
            word_list = segmenter.tokenize(phrase)
        else:  # Mac/Linux
            '''
            if sys.platform == "darwin":  # Different location of the dictionary files,
                mecab_directory = "/usr/local/lib/mecab/dic/mecab-ipadic-neologd"
            else:
                mecab_directory = "/usr/lib/mecab/dic/mecab-ipadic-neologd"'''
            mt = MeCab.Tagger("r'-d {}'".format(FILE_ADDRESS_MECAB))
            mt.parse(
                phrase
            )  # Per https://github.com/SamuraiT/mecab-python3/issues/3 to fix Unicode issue
            parsed = mt.parseToNode(phrase.strip())
            components = []

            while parsed:
                components.append(parsed.surface)
                # Note: `parsed.feature` produces the parts of speech, e.g. 名詞,一般,*,*,*,*,風景,フウケイ,フーケイ
                parsed = parsed.next

            # Remove empty strings
            word_list = [x for x in components if x]

    for item in word_list:  # Get rid of punctuation and kana (for now)
        if language == "ja":
            kana_test = None
            if len(item) == 1:  # If it's only a single kana...
                kana_test = re.search("[\u3040-\u309f]", item)
            if kana_test is None:
                if (
                    item
                    not in r"\.\!\/_,$%^*(+\"\']+|[+——！，。？、~@#￥%……&*（）：；《）《》“”()»〔〕「」％"
                ):
                    final_list.append(item)
        if language == "zh":
            if item not in r"\.\!\/_,$%^*(+\"\']+|[+——！，。？、~@#￥%……&*（）：；《）《》“”()»〔〕「」％":
                final_list.append(item)

    return final_list  # Returns a list of words / characters


def lookup_wiktionary_search(search_term, language_name):
    """
    This is a general lookup function for Wiktionary, updated and
    cleaned up to be better than the previous version.
    This function is used for all non-CJK languages.
    Using 0.0.97.

    :param search_term: The word we're looking for information.
    :param language_name: Name of the language we're looking up the word in.
    :return post_template: None if it can't find anything, a formatted string for comments otherwise.
    """
    language_name = language_name.title()
    parser = WiktionaryParser()
    try:
        word_info_list = parser.fetch(search_term, language_name)
    except (TypeError, AttributeError):  # Doesn't properly exist, first check
        return None

    try:
        # A simple second test to see if something really has definitions
        exist_test = word_info_list[0]["definitions"]
    except IndexError:
        return None

    if exist_test:
        # Get the dictionary that is wrapped in the list.
        word_info = word_info_list[0]
    else:  # This information doesn't exist.
        return None

    # Do a check to see if the Wiktionary page exists, to prevent
    # accidental returns of English stuff. It checks to see if a header
    # exists in that language. If it doesn't then it will return None.
    test_wikt_link = "https://en.wiktionary.org/wiki/{}#{}".format(
        search_term, language_name
    )
    test_page = requests.get(test_wikt_link, headers=ZW_USERAGENT)
    test_tree = html.fromstring(test_page.content)  # now contains the whole HTML page
    test_language = test_tree.xpath(
        'string(//span[contains(@id,"{}")])'.format(language_name)
    )
    if language_name == test_language:
        logger.info("[ZW] This word exists in its proper language on Wiktionary.")
    else:
        logger.info(
            "[ZW] This word does NOT exist in its proper language on Wiktionary."
        )
        return None

    # First, let's take care of the etymology section.
    post_etymology = word_info["etymology"]
    if len(post_etymology) > 0:  # There's actual information:
        post_etymology = post_etymology.replace(r"\*", "*")
        post_etymology = "\n\n#### Etymology\n\n{}".format(post_etymology.strip())

    # Secondly, let's add a pronunciation section if we can.
    dict_pronunciations = word_info["pronunciations"]
    pronunciations_ipa = ""
    pronunciations_audio = ""
    if len(dict_pronunciations.values()) > 0:  # There's actual information:
        if len(dict_pronunciations["text"]) > 0:
            pronunciations_ipa = dict_pronunciations["text"][0].strip()
        else:
            pronunciations_ipa = ""
        if len(dict_pronunciations["audio"]) > 0:
            pronunciations_audio = " ([Audio](https:{}))".format(
                dict_pronunciations["audio"][0]
            )
        else:
            pronunciations_audio = ""
    if len(pronunciations_ipa + pronunciations_audio) > 0:
        post_pronunciations = "\n\n#### Pronunciations\n\n{}{}".format(
            pronunciations_ipa, pronunciations_audio
        )
    else:
        post_pronunciations = ""

    # Lastly, and most complicated, we deal with 'definitions', including
    # examples, partOfSpeech, text (includes the gender/meaning)
    # A different part of speech is given as its own thing.
    total_post_definitions = []

    if len(word_info["definitions"]) > 0:
        separate_definitions = word_info["definitions"]
        # If they are separate parts of speech they have different definitions.
        for dict_definitions in separate_definitions:
            # Deal with Examples
            if len(dict_definitions["examples"]) > 0:
                examples_data = dict_definitions["examples"]
                if (
                    len(examples_data) > 3
                ):  # If there are a lot of examples, we only want the first three.
                    examples_data = examples_data[:2]
                post_examples = "* " + "\n* ".join(examples_data)
                post_examples = "\n\n**Examples:**\n\n{}".format(post_examples)
            else:
                post_examples = ""

            # Deal with parts of speech
            if len(dict_definitions["partOfSpeech"]) > 0:
                post_part = dict_definitions["partOfSpeech"].strip()
            else:
                post_part = ""

            # Deal with gender/meaning
            if len(dict_definitions["text"]) > 0:
                master_text_list = dict_definitions["text"]
                master_text_list = [
                    x.replace("\xa0", " ^") for x in master_text_list if x
                ]
                master_text_list = [x for x in master_text_list if x]
                print(master_text_list)
                post_word_info = master_text_list[0]

                meanings_format = "* " + "\n* ".join(master_text_list[1:])
                post_meanings = "\n\n*Meanings*:\n\n{}".format(meanings_format)
                post_total_info = post_word_info + post_meanings
            else:
                post_total_info = ""

            # Combine definitions as a format.
            if len(post_examples + post_part) > 0:
                if post_part:  # Use the part of speech as a header if known
                    info_header = post_part.title()
                else:
                    info_header = "Information"
                post_definitions = "\n\n##### {}\n\n{}{}".format(
                    info_header, post_total_info, post_examples
                )
                total_post_definitions.append(post_definitions)

    total_post_definitions = "\n" + "\n\n".join(total_post_definitions)

    # Put it all together.
    post_template = "# [{0}](https://en.wiktionary.org/wiki/{0}#{1}) ({1}){2}{3}{4}"
    post_template = post_template.format(
        search_term,
        language_name,
        post_etymology,
        post_pronunciations,
        total_post_definitions,
    )
    logger.info(
        "[ZW] Looked up information for {} as a {} word..".format(
            search_term, language_name
        )
    )

    return post_template


"""
LANGUAGE REFERENCE FUNCTIONS

These are functions that retrieve reference information about languages. 

All reference functions are prefixed with `reference` in their name.
"""


def reference_search(lookup_term):
    """
    Function to look up reference languages on Ethnologue and Wikipedia.
    This also searches MultiTree (no longer a
    separate function) for languages which may be constructed or dead.
    Due to web settings the live search function of this has been
    disabled.

    :param lookup_term: The language code or text we're looking for.
    :return: A formatted string regardless of whether it found an appropriate match.
    """

    # Regex to check if code is in the private use area qaa-qtz
    private_check = re.search("^q[a-t][a-z]$", lookup_term)
    if (
        private_check is not None
    ):  # This is a private use code. If it's None, it did not match.
        return None  # Just exit.

    # Get the language code (specifically the ISO 639-3 one)
    language_code = converter(lookup_term)[0]
    language_lookup_code = str(language_code)
    if len(language_code) == 2:  # This appears to be an ISO 639-1 code.
        language_code = MAIN_LANGUAGES[language_code][
            "language_code_3"
        ]  # Get the ISO 639-3 version.
    if len(language_code) == 4:  # This is a script code.
        return None

    # Correct for macrolanguages. There is frequently no data for their broad codes.
    if language_code in ISO_MACROLANGUAGES:
        # We replace the macrolanguage with the most frequent individual language code. (e.g. 'zho' becomes 'cmn'.)
        language_code = ISO_MACROLANGUAGES[language_code][0]

    # Now we check the database to see if it has data.
    if len(language_code) != 0:  # There's a valid code here.
        logger.info("[ZW] reference_search Code: {}".format(language_lookup_code))
        sql_command = "SELECT * FROM language_cache WHERE language_code = ?"
        cursor_main.execute(sql_command, (language_lookup_code,))
        reference_results = cursor_main.fetchone()

        if reference_results is not None:  # We found a cached value for this language
            reference_cached_info = reference_results[1]
            logger.info(
                "[ZW] Reference: Retrieved the cached reference information for {}.".format(
                    language_lookup_code
                )
            )
            return reference_cached_info

    return


def reference_reformatter(original_entry):
    """
    Takes a reference string and tries to make it more compact and simple.
    The replacement for Unknown posts will use this abbreviated version.
    !reference will still return the full information, and data will still be available for Wenyuan to use.

    :param original_entry: Data that needs to be parsed and stripped down.
    :return: A simplified version of the string above.
    """

    # Divide the lines.
    original_lines = original_entry.split("\n\n")
    new_lines = []

    # Define which lines to exclude.
    excluded_lines = [
        "Language Name",
        "Alternate Names",
        "Writing system",
        "Population",
    ]

    # Go over the lines and delete links we don't need.
    for line in original_lines:
        if "##" in line and "]" in line:
            sole_language = line.split("]")[0]
            sole_language = sole_language.replace("[", "")
            line = sole_language

        if any(key in line for key in excluded_lines):
            continue

        new_lines.append(line)

    # Combine the lines into a new string.
    new_entry = "\n\n".join(new_lines)

    return new_entry


"""
EDIT FINDER

This is a single function that helps detect changes in r/translator comments, especially checking for the addition of 
commands are changes in the content that's looked up. 
"""


def edit_finder():
    """
    A top-level function to detect edits and changes of note in r/translator comments, including commands and
    lookup items. `comment_limit` defines how many of the latest comments it will store in the cache.

    :param: Nothing.
    :return: Nothing.
    """

    comment_limit = 150

    # Fetch the comments from Reddit.
    comments = []
    try:
        comments += list(
            r.comments(limit=comment_limit)
        )  # Only get the last `comment_limit` comments.
    except prawcore.exceptions.ServerError:  # Server issues.
        return
    cleanup_database = False

    # Process the comments we've retrieved.
    for comment in comments:
        current_time_com = time.time()

        cbody = comment.body
        cid = comment.id
        cedited = comment.edited  # Is a boolean
        ccreated = comment.created_utc

        time_diff = current_time_com - ccreated

        if time_diff > 3600 and not cedited:  # The edit is older than an hour.
            continue
        """
        # Strip punctuation to allow for safe SQL storage.
        replaced_characters = ['\n', '\x00', '(', ')', '[', "]", "'", "\""]
        for character in replaced_characters:
            cbody = cbody.replace(character, " ")
        """

        # Let's retrieve any matching comment text in the cache.
        get_old_sql = "SELECT * FROM comment_cache WHERE id = ?"  # Look for previous data for comment ID
        cursor_cache.execute(get_old_sql, (cid,))
        old_matching_data = (
            cursor_cache.fetchall()
        )  # Returns a list that contains a tuple (comment ID, comment text).

        if (
            len(old_matching_data) != 0
        ):  # This comment has previously been stored. Let's check it.
            logger.debug(
                "[ZW] Edit Finder: Comment '{}' was previously stored in the cache.".format(
                    cid
                )
            )

            # Define a way to override and force a change even if there is no difference in detected commands.
            force_change = False

            # Retrieve the previously stored text for this comment.
            old_cbody = old_matching_data[0][1]

            # Test the new retrieved text with the old one.
            if cbody == old_cbody:  # The cached comment is the same as the current one.
                continue  # Do nothing.
            else:  # There is a change of some sort.
                logger.debug(
                    "[ZW] Edit Finder: An edit for comment '{}' was detected. Processing...".format(
                        cid
                    )
                )
                cleanup_database = True

                # We detected a possible `lookup` change, where the words looked up are now different.
                if "`" in cbody:
                    # First thing is compare the data in a lookup comment against what we have.

                    # Here we use the lookup_matcher function to get a LIST of everything that used to be in the graves.
                    total_matches = lookup_matcher(old_cbody, None)

                    # Then we get data from Komento, specifically looking for its version of results.
                    new_vars = komento_analyzer(komento_submission_from_comment(cid))

                    if "bot_lookup_correspond" in new_vars:  # This will be a dictionary
                        new_overall_lookup_data = new_vars["bot_lookup_correspond"]
                        if (
                            cid in new_overall_lookup_data
                        ):  # This comment is in our data
                            new_total_matches = new_overall_lookup_data[cid]
                            # Get the new matches
                            if set(new_total_matches) == set(
                                total_matches
                            ):  # Are they the same?
                                logger.debug(
                                    "[ZW] Edit-Finder: No change found for lookup comment '{}'.".format(
                                        cid
                                    )
                                )
                                continue
                            else:
                                logger.debug(
                                    "[ZW] Edit-Finder: Change found for lookup comment '{}'.".format(
                                        cid
                                    )
                                )
                                force_change = True

                # Code to swap out the stored comment text with the new text. This does NOT force a reprocess.
                delete_command = "DELETE FROM comment_cache WHERE id = ?"
                cursor_cache.execute(delete_command, (cid,))
                cache_command = "INSERT INTO comment_cache VALUES (?, ?)"
                insertion_tuple = (cid, cbody)
                cursor_cache.execute(cache_command, insertion_tuple)
                conn_cache.commit()

                # Here we edit the cache file too IF there's a edited-in command that's new, omitting the crosspost ones
                first_part = KEYWORDS[0:11]
                second_part = KEYWORDS[13:]
                main_keywords = first_part + second_part

                # Iterate through the command keywords to see what's new.
                for keyword in main_keywords:
                    if keyword in cbody and keyword not in old_cbody:
                        # This means the keyword is a NEW addition to the edited comment.
                        logger.debug(
                            "[ZW] Edit Finder: New command {} detected for comment '{}'.".format(
                                keyword, cid
                            )
                        )
                        force_change = True

                if (
                    force_change
                ):  # Delete the comment from the processed database to force it to update and reprocess.
                    delete_comment_command = "DELETE FROM oldcomments WHERE id = ?"
                    cursor_main.execute(delete_comment_command, (cid,))
                    conn_main.commit()
                    logger.debug(
                        "[ZW] Edit Finder: Removed edited comment `{}` from processed database.".format(
                            cid
                        )
                    )

        else:  # This is a comment that has not been stored.
            logger.debug(
                "[ZW] Edit Finder: New comment '{}' to store in the cache.".format(cid)
            )
            cleanup_database = True

            try:
                # Insert the comment into our cache.
                cache_command = "INSERT INTO comment_cache VALUES (?, ?)"
                new_tuple = (cid, cbody)
                cursor_cache.execute(cache_command, new_tuple)
                conn_cache.commit()
            except ValueError:  # Some sort of invalid character, don't write it.
                logger.debug(
                    "[ZW] Edit Finder: ValueError when inserting comment `{}` into cache.".format(
                        cid
                    )
                )
                pass

    if cleanup_database:  # There's a need to clean it up.
        cleanup = "DELETE FROM comment_cache WHERE id NOT IN (SELECT id FROM comment_cache ORDER BY id DESC LIMIT ?)"
        cursor_cache.execute(cleanup, (comment_limit,))

        # Delete all but the last comment_limit comments.
        conn_cache.commit()
        logger.debug("[ZW] Edit Finder: Cleaned up the edited comments cache.")

    return


"""
POSTS FILTERING & TESTING FUNCTIONS

This is the main routine to check for incoming posts, assign them the appropriate category, and activate notifications.
The function also removes posts that don't match the formatting guidelines.
"""


def is_mod(user):
    """
    A function that can tell us if a user is a moderator of the operating subreddit (r/translator) or not.

    :param user: The Reddit username of an individual.
    :return: True if the user is a moderator, False otherwise.
    """

    moderators = []
    for moderator in r.moderator():  # Get list of subreddit mods from r/translator.
        moderators.append(moderator.name.lower())
    if user.lower() in moderators:  # Person is a mod.
        return True
    else:
        return False  # Person is not a mod.


def css_check(css_class):
    """
    Function that checks if a CSS class is something that a command can act on.
    Generally speaking we do not act upon posts with these two classes.

    :param css_class: The css_class of the post.
    :return: True if the post is something than can be worked with, False if it's in either of the defined two classes.
    """

    if css_class in ["meta", "community"]:
        return False
    else:
        return True


def bad_title_commenter(title_text, author):
    """
    This function takes a filtered title and constructs a comment that contains a suggested new title for the user to
    use and a resubmit link that has that new title filled in automatically. This streamlines the process of
    resubmitting a post to r/translator.

    :param title_text: The filtered title that did not contain the required keywords for the community.
    :param author: The OP of the post.
    :return: A formatted comment that `ziwen_posts` can reply to the post with.
    """

    new_title = bad_title_reformat(
        title_text
    )  # Retrieve the reformed title from the routine in _languages
    new_url = new_title.replace(" ", "%20")  # replace spaces
    new_url = new_url.replace(")", r"\)")  # replace closing parentheses
    new_url = new_url.replace(">", "%3E")  # replace caret with HTML code
    new_title = "`" + new_title + "`"  # add code marks

    # If the new title is for Unknown, let's add a text reminder
    if "[Unknown" in new_title:
        new_title += "\n* (If you know your request's language, replace `Unknown` with its name.)"

    return COMMENT_BAD_TITLE.format(author=author, new_url=new_url, new_title=new_title)


def ziwen_posts():
    """
    The main top-level post filtering runtime for r/translator.
    It removes posts that do not meet the subreddit's guidelines.
    It also assigns flair to posts, saves them as Ajos, and determines what to pass to the notifications system.

    :return: Nothing.
    """

    current_time = int(time.time())  # This is the current time.
    logger.debug("[ZW] Fetching new r/{} posts at {}.".format(SUBREDDIT, current_time))
    posts = []

    # We get the last 80 new posts. Changed from the deprecated `submissions` method.
    # This should allow us to retrieve stuff from up to a day in case of power outages or moving.
    posts += list(r.new(limit=80))
    posts.reverse()  # Reverse it so that we start processing the older ones first. Newest ones last.

    for post in posts:
        # Anything that needs to happen every loop goes here.
        oid = post.id
        otitle = post.title
        ourl = post.url
        opermalink = (
            post.permalink
        )  # This is the comments page, not the URL of an image
        oselftext = post.selftext
        oflair_css = post.link_flair_css_class
        ocreated = post.created_utc  # Unix time when this post was created.
        opost_age = current_time - ocreated  # Age of this post, in seconds

        if oflair_css is None:
            oflair_css = " "  # If it's blank...

        try:
            oauthor = post.author.name
        except AttributeError:
            # Author is deleted. We don't care about this post.
            continue

        # Check the local database to see if this is in there.
        cursor_main.execute("SELECT * FROM oldposts WHERE ID=?", [oid])
        if cursor_main.fetchone():
            # Post is already in the database
            logger.debug(
                "[ZW] Posts: This post {} already exists in the processed database.".format(
                    oid
                )
            )
            continue
        cursor_main.execute("INSERT INTO oldposts VALUES(?)", [oid])
        conn_main.commit()

        if not css_check(oflair_css) and oflair_css is not None:
            # If it's a Meta or Community post (that's what css_check does), just alert those signed up for it.
            suggested_css_text = oflair_css
            logger.info("[ZW] Posts: New {} post.".format(suggested_css_text.title()))

            # Assign it a specific template that exists.
            if oflair_css in POST_TEMPLATES.keys():
                output_template = POST_TEMPLATES[oflair_css]
                post.flair.select(output_template, suggested_css_text.title())

            # We want to exclude the Identification Threads
            if "Identification Thread" not in otitle:
                ziwen_notifier(suggested_css_text, otitle, opermalink, oauthor, False)

            continue  # Then exit.

        if oflair_css in [
            "translated",
            "doublecheck",
            "missing",
            "inprogress",
        ]:  # We don't want to mess with these
            continue  # Basically we only want to deal with untranslated posts

        # We're going to mark the original post author as someone different if it's a crosspost.
        if oauthor == "translator-BOT" and oflair_css != "community":
            komento_data = komento_analyzer(post)
            if "bot_xp_comment" in komento_data:
                op_match = komento_data["bot_xp_op"]
                oauthor = op_match

        if (
            oauthor.lower() in GLOBAL_BLACKLIST
        ):  # This user is on our blacklist. (not used much, more precautionary)
            post.mod.remove()
            action_counter(1, "Blacklisted posts")  # Write to the counter log
            logger.info(
                "[ZW] Posts: Filtered a post out because its author u/{} is on my blacklist.".format(
                    oauthor
                )
            )
            continue

        if (
            opost_age < CLAIM_PERIOD
        ):  # If the post is younger than the claim period, we can act on it. (~8 hours)
            # If the post is under an hour, let's send notifications to people. Otherwise, we won't.
            # This is mainly for catching up with older posts - we want to process them but we don't want to send notes.
            if opost_age < 3600:
                okay_send = True
            else:
                okay_send = False

            returned_info = main_posts_filter(
                otitle
            )  # Applies a filtration test, see if it's okay. False if it is not

            if returned_info[0] is not False:  # Everything appears to be fine.
                otitle = returned_info[1]
                logger.info("[ZW] Posts: New post, {} by u/{}.".format(otitle, oauthor))
            else:  # This failed the test.
                # Remove this post, it failed all routines.
                post.mod.remove()
                post.reply(
                    str(bad_title_commenter(title_text=otitle, author=oauthor))
                    + BOT_DISCLAIMER
                )

                # Write the title to the log.
                filter_num = returned_info[2]
                record_filter_log(
                    filtered_title=otitle, ocreated=ocreated, filter_type=filter_num
                )
                action_counter(1, "Removed posts")  # Write to the counter log
                logger.info(
                    "[ZW] Posts: Removed post that violated formatting guidelines. Title: {}".format(
                        otitle
                    )
                )
                continue  # Exit

            try:
                title_data = title_format(otitle)  # Get the master list of data.
                suggested_source = str(title_data[0])
                suggested_target = str(title_data[1])
                suggested_css = title_data[2]
                suggested_css_text = title_data[3]
                multiple_notifications = title_data[6]
                # This is something that will return a list if it's a multiple request or two non English languages
                # that can be split. None if false.
                specific_sublanguage = title_data[
                    7
                ]  # This is a specific code, like ar-LB, unknown-cyrl
            except (
                Exception
            ) as e_title:  # The title converter couldn't make sense of it. This should not happen.
                # Skip! This will result it in getting whatever AM gave it. (which may be nothing)
                # Send a message to let mods know
                title_error_entry = traceback.format_exc()
                record_error_log(title_error_entry + str(e_title))  # Save the error.

                # Report the post, so that mods know to take a look.
                fail_reason = (
                    "(Ziwen) Crashed my title formatting routine. "
                    "Please check and assign this a language category."
                )
                post.report(fail_reason)
                logger.warning(
                    "[ZW] Posts: Title formatting routine crashed and encountered an exception."
                )

                continue  # Exit

            if (
                suggested_source == suggested_target
            ):  # If it's an English only post, filter it out.
                if "English" in suggested_source and "English" in suggested_target:
                    post.mod.remove()
                    post.reply(COMMENT_ENGLISH_ONLY.format(oauthor=oauthor))
                    record_filter_log(
                        filtered_title=otitle, ocreated=ocreated, filter_type="EE"
                    )
                    action_counter(1, "Removed posts")  # Write to the counter log
                    logger.info("[ZW] Posts: Removed an English-only post.")

            # We're going to consolidate the multiple updates into one Reddit push only.
            # This is a post that we have title data for.
            if suggested_css_text != "Generic":
                final_css_text = str(suggested_css_text)
                final_css_class = str(suggested_css)
                if "generic" in suggested_css and suggested_css_text != "English":
                    # It's a supported language but not a supported
                    # flair, so write to the saved page.
                    record_to_wiki(
                        odate=ocreated,
                        otitle=otitle,
                        oid=oid,
                        oflair_text=suggested_css_text,
                        s_or_i=True,
                        oflair_new="",
                    )
            else:  # This is fully generic.
                # Set generic categories.
                final_css_text = "Generic"
                final_css_class = "generic"

                # Report the post, so that mods know to take a look.
                generic_reason = (
                    "(Ziwen) Failed my title formatting routine. "
                    "Please check and assign this a language category."
                )
                post.report(generic_reason)
                logger.info(
                    "[ZW] Posts: Title formatting routine couldn't make sense of '{}'.".format(
                        otitle
                    )
                )

            """YouTube section currently deprecated due to Pafy not being updated.
            # Check to see if we should add (Long) to the flair. There's a YouTube test and a text length test.
            if "youtube.com" in ourl or "youtu.be" in ourl:
                # This changes the CSS text to indicate if it's a long YouTube video
                try:
                    # Let's try to get the length of the video.
                    video_url = pafy.new(ourl)
                    logger.debug("[ZW] Posts: Analyzing YouTube video post at: {}".format(video_url))

                    if video_url.length > 300 and "t=" not in ourl:
                        # We make an exception if someone posts the exact timestamp
                        logger.info("[ZW] Posts: This is a long YouTube video.")
                        if final_css_text is not None:  # Let's leave None flair text alone
                            final_css_text += " (Long)"
                            post.reply(COMMENT_LONG + BOT_DISCLAIMER)
                except (ValueError, TypeError, UnicodeEncodeError, youtube_dl.utils.ExtractorError,
                        youtube_dl.utils.RegexNotFoundError, OSError, IOError, pafy.util.GdataError):
                    # The pafy routine cannot make sense of it.
                    logger.debug("[ZW] Posts: Unable to process this YouTube link.")
                else:
                    logger.warning("[ZW] Posts: Unable to process YouTube link at {}. Non-listed error.".format(ourl))
            """
            if (
                len(oselftext) > 1400
            ):  # This changes the CSS text to indicate if it's a long wall of text
                logger.info("[ZW] Posts: This is a long piece of text.")
                if (
                    final_css_text is not None and post.author.name != USERNAME
                ):  # Let's leave None flair text alone
                    final_css_text += " (Long)"
                    post.reply(COMMENT_LONG + BOT_DISCLAIMER)

            # This is a boolean. True if the user has posted too much and False if they haven't.
            user_posted_too_much = notifier_over_frequency_checker(oauthor)

            # We don't want to send notifications if we're just testing. We also verify that user is not too extra.
            contacted = (
                []
            )  # A placeholder variable that normally contains a list of users notified.
            if MESSAGES_OKAY and okay_send and not user_posted_too_much:
                action_counter(1, "New posts")  # Write to the counter log
                if (
                    multiple_notifications is None and specific_sublanguage is None
                ):  # This is a regular post.
                    contacted = ziwen_notifier(
                        suggested_css_text, otitle, opermalink, oauthor, False
                    )
                    # Now we notify people who are signed up on the list.
                elif (
                    multiple_notifications is not None and specific_sublanguage is None
                ):
                    # This is a multiple post with a fixed number of languages or two non-English ones.
                    # Also called a "defined multiple language post"
                    # This part of the function also sends notifications if both languages are non-English
                    for notification in multiple_notifications:
                        multiple_language_text = converter(notification)[
                            1
                        ]  # This is the language name for consistency
                        contacted = ziwen_notifier(
                            multiple_language_text, otitle, opermalink, oauthor, False
                        )
                    if (
                        final_css_class is "multiple"
                    ):  # We wanna leave an advisory comment if it's a defined multiple
                        post.reply(COMMENT_DEFINED_MULTIPLE + BOT_DISCLAIMER)
                elif (
                    multiple_notifications is None and specific_sublanguage is not None
                ):
                    # There is a specific subcategory for us to look at (ar-LB, unknown-cyrl) etc
                    # The notifier routine will be able to make sense of the hyphenated code.
                    contacted = ziwen_notifier(
                        specific_sublanguage, otitle, opermalink, oauthor, False
                    )
                    # Now we notify people who are signed up on the list.

            # If it's an unknown post, add an informative comment.
            if final_css_class == "unknown" and post.author.name != "translator-BOT":
                unknown_already = False
                if not unknown_already:
                    post.reply(COMMENT_UNKNOWN + BOT_DISCLAIMER)
                    logger.info(
                        "[ZW] Posts: Added the default 'Unknown' information comment."
                    )

            # Actually update the flair. Legacy version first.
            logger.info(
                "[ZW] Posts: Set flair to class '{}' and text '{}.'".format(
                    final_css_class, final_css_text
                )
            )

            # New Redesign Version to update flair
            # Check the global template dictionary
            if final_css_class in POST_TEMPLATES.keys():
                output_template = POST_TEMPLATES[final_css_class]
                post.flair.select(output_template, final_css_text)
                logger.debug("[ZW] Posts: Flair template selected for post.")

            # Finally, create an Ajo object and save it locally.
            if final_css_class not in ["meta", "community"]:
                pajo = Ajo(
                    reddit.submission(id=post.id)
                )  # Create an Ajo object, reload the post.
                if len(contacted) != 0:  # We have a list of notified users.
                    pajo.add_notified(contacted)
                ajo_writer(pajo)  # Save it to the local database
                logger.debug(
                    "[ZW] Posts: Created Ajo for new post and saved to local database."
                )

    return


"""
MAIN COMMANDS RUNTIME

This is the main routine that processes commands from r/translator users.
"""


def ziwen_bot():
    """
    This is the main runtime for r/translator that checks for keywords and commands.

    :return: Nothing.
    """

    logger.debug("Fetching new r/{} comments...".format(SUBREDDIT))
    posts = []
    try:
        posts += list(r.comments(limit=MAXPOSTS))
    except prawcore.exceptions.ServerError:  # Server issues.
        return

    for post in posts:
        pid = post.id

        try:
            pauthor = post.author.name
        except AttributeError:
            # Comment author is deleted.
            continue

        if pauthor == USERNAME:  # Will not reply to my own comments
            continue

        cursor_main.execute("SELECT * FROM oldcomments WHERE ID=?", [pid])
        if cursor_main.fetchone():
            # Post is already in the database
            continue

        """KEY ORIGINAL POST VARIABLES (NON-COMMENT) (o-)"""
        osubmission = (
            post.submission
        )  # Returns a submission object of the parent to work with
        oid = osubmission.id
        opermalink = osubmission.permalink
        otitle = osubmission.title
        oflair_text = osubmission.link_flair_text  # This is the linkflair text
        oflair_css = (
            osubmission.link_flair_css_class
        )  # This is the linkflair css class (lowercase)
        ocreated = post.created_utc  # Unix time when this post was created.
        osaved = post.saved  # We save verification requests so we don't work on them.
        requester = "Zamenhof"  # Dummy thing just to have data
        current_time = int(time.time())  # This is the current time.

        try:
            oauthor = (
                osubmission.author.name
            )  # Check to see if the submission author deleted their post already
        except AttributeError:  # No submission author found.
            oauthor = None

        if oid != VERIFIED_POST_ID:
            # Enter it into the processed comments database
            cursor_main.execute("INSERT INTO oldcomments VALUES(?)", [pid])
            conn_main.commit()

        pbody = post.body
        pbody_original = str(pbody)  # Create a copy with capitalization
        pbody = pbody.lower()

        # Calculate points for the person.
        if oflair_text is not None and osaved is not True and oauthor is not None:
            # We don't want to process it without the oflair text. Or if its vaerified comment
            logger.debug("[ZW] Bot: Processing points for u/{}".format(pauthor))
            points_tabulator(oid, oauthor, oflair_text, oflair_css, post)

        """AJO CREATION"""
        # Create an Ajo object.
        if css_check(oflair_css):
            # Check the database for the Ajo.
            oajo = ajo_loader(oid)

            if (
                oajo is None
            ):  # We couldn't find a stored dict, so we will generate it from the submission.
                logger.debug("[ZW] Bot: Couldn't find an AJO in the local database.")
                oajo = Ajo(osubmission)

            if oajo.is_bot_crosspost:
                komento_data = komento_analyzer(komento_submission_from_comment(pid))
                if "bot_xp_comment" in komento_data:
                    op_match = komento_data["bot_xp_op"]
                    oauthor = op_match  # We're going to mark the original post author as another if it's a crosspost.
                    requester = komento_data["bot_xp_requester"]
        else:  # This is either a meta or a community post
            logger.debug(
                "[ZW] Bot: Post appears to be either a meta or community post."
            )
            continue

        if not any(key.lower() in pbody for key in KEYWORDS) and not any(
            phrase in pbody for phrase in THANKS_KEYWORDS
        ):
            # Does not contain our keyword
            logger.debug(
                "[ZW] Bot: Post {} does not contain any operational keywords.".format(
                    oid
                )
            )
            continue

        if (
            TESTING_MODE
        ):  # This is a function to help stop the incessant commenting on older posts when testing
            if (
                current_time - ocreated >= 3600
            ):  # If the comment is older than an hour, ignore
                continue

        # Record to the counter with the keyword.
        for keyword in KEYWORDS:
            if keyword in pbody:
                action_counter(1, keyword)  # Write to the counter log

        """RESTORE COMMAND"""

        # This is the `!restore` command, which can try and check Pushshift data. It can be triggered if user deleted it
        if KEYWORDS[17] in pbody and oauthor is None:
            # This command is allowed to be used by people who have either translated the piece or who were notified
            # about it. This is to help resolve the big issue of people deleting their posts.
            logger.info("[ZW] Bot: COMMAND: !restore, from u/{}.".format(pauthor))

            # This is a link post, we can't retrieve that.
            if not osubmission.is_self:
                # Reply and let them know this only works on text-only posts.
                post.reply(MSG_RESTORE_LINK_FAIL + BOT_DISCLAIMER)
                logger.info("[ZW] Bot: !restore request is for a link post. Skipped.")
                continue

            try:  # Get the people who are eligible to check for this.
                try:
                    eligible_people = oajo.notified
                except (
                    AttributeError
                ):  # Since this is a new attribute it's possible older Ajos don't have it.
                    logger.error("[ZW] Bot: Error retrieving notified list from Ajo.")
                    eligible_people = []
                eligible_people += oajo.recorded_translators
            except AttributeError:
                logger.error(
                    "[ZW] Bot: Error in retrieving recorded translators list from Ajo."
                )
                continue

            # The person asking for a restore isn't eligible for it.
            if pauthor not in eligible_people and not is_mod(
                pauthor
            ):  # mods should be able to call it.
                logger.info(
                    "[ZW] Bot: u/{} is not eligible to make a !restore request for this.".format(
                        pauthor
                    )
                )
                post.reply(MSG_RESTORE_NOT_ELIGIBLE + BOT_DISCLAIMER)
                continue
            else:  # Format a search query to Pushshift.
                search_query = (
                    "https://api.pushshift.io/reddit/search/submission/?ids={}".format(
                        oid
                    )
                )
                retrieved_data = requests.get(search_query).json()

                if "data" in retrieved_data:  # We've got some data.
                    returned_submission = retrieved_data["data"][0]
                    original_title = "> **{}**\n\n".format(returned_submission["title"])
                    original_text = returned_submission["selftext"]
                    if len(original_text.strip()) > 0:  # We have text.
                        original_text = "> " + original_text.strip().replace(
                            "\n", "\n > "
                        )
                    else:  # The retrieved text is of zero length.
                        original_text = (
                            "> *It appears this text-only post had no text.*"
                        )
                    original_text = original_title + original_text
                else:
                    # Tell them we were not able to get any proper data.
                    subject_line = "[Notification] About your !restore request"
                    try:
                        reddit.redditor(pauthor).message(
                            subject_line, MSG_RESTORE_TEXT_FAIL.format(opermalink)
                        )
                    except praw.exceptions.APIException:
                        pass
                    else:
                        logger.info(
                            "[ZW] Bot: Replied to u/{} with message, "
                            "unable to retrieve data.".format(pauthor)
                        )
                    continue

                # Actually send them the message, including the original text.
                subject_line = "[Notification] Restored text for your !restore request"
                try:
                    reddit.redditor(pauthor).message(
                        subject_line,
                        MSG_RESTORE_TEXT_TEMPLATE.format(opermalink, original_text)
                        + BOT_DISCLAIMER,
                    )
                except praw.exceptions.APIException:
                    pass
                else:
                    logger.info(
                        "[ZW] Bot: Replied to u/{} with restored text.".format(pauthor)
                    )

        # We move the exit point if there is no author here. Since !restore relies on there being no author.
        if oauthor is None:
            logger.info("[ZW] Bot: >> Author is deleted or non-existent.")
            oauthor = "deleted"

        """REFERENCE COMMANDS (!identify, !page, !reference, !search, `lookup`)"""
        if (
            KEYWORDS[4] in pbody or KEYWORDS[10] in pbody
        ):  # This is the general !identify command (synonym: !id)
            determined_data = comment_info_parser(pbody, "!identify:")
            # This should return what was actually identified. Normally will be a tuple or None.
            if (
                determined_data is None
            ):  # The command is problematic. Wrong punctuation, not enough arguments
                logger.debug("[ZW] Bot: !identify data is invalid.")
                continue

            # Set some defaults just in case. These should be overwritten later.
            match_script = False
            language_code = ""
            language_name = ""

            # If it's not none, we got proper data.
            match = determined_data[0]
            advanced_mode = determined_data[1]
            language_country = None  # Default value
            o_language_name = str(
                oajo.language_name
            )  # Store the original language defined in the Ajo
            # This should return a boolean whether it's in advanced mode.

            logger.info("[ZW] Bot: COMMAND: !identify, from u/{}.".format(pauthor))
            logger.info("[ZW] Bot: !identify data is: {}".format(determined_data))

            if "+" not in match:  # This is just a regular single !identify command.
                if not advanced_mode:  # This is the regular results conversion
                    language_code = converter(match)[0]
                    language_name = converter(match)[1]
                    language_country = converter(match)[
                        3
                    ]  # The country code for the language. Regularly none.
                    match_script = False
                elif advanced_mode:
                    if (
                        len(match) == 3
                    ):  # The advanced mode only accepts codes of a certain length.
                        language_data = lang_code_search(
                            match, False
                        )  # Run a search for the specific thing
                        language_code = match
                        language_name = language_data[0]
                        match_script = language_data[1]
                        if (
                            len(language_name) == 0
                        ):  # If there are no results from the advanced converter...
                            language_code = ""
                            # is_supported = False
                    elif (
                        len(match) == 4
                    ):  # This is a script, resets it to an Unknown state.
                        language_data = lang_code_search(
                            match, True
                        )  # Run a search for the specific script
                        logger.info(
                            "[ZW] Bot: Returned script data is for {}.".format(
                                language_data
                            )
                        )
                        if language_data is None:  # Probably an invalid script.
                            bad_script_reply = COMMENT_INVALID_SCRIPT + BOT_DISCLAIMER
                            post.reply(bad_script_reply.format(match))
                            logger.info(
                                "[ZW] Bot: But '{}' is not a valid script code. Skipping...".format(
                                    match
                                )
                            )
                            continue
                        else:
                            language_code = match
                            language_name = language_data[0]
                            match_script = True
                            logger.info(
                                f"[ZW] Bot: This is a script post with code `{language_code}`."
                            )
                            if (
                                len(language_name) == 0
                            ):  # If there are no results from the advanced converter...
                                language_code = ""
                    else:  # a catch-all for advanced mode that ISN'T a 3 or 4-letter code.
                        post.reply(COMMENT_ADVANCED_IDENTIFY_ERROR + BOT_DISCLAIMER)
                        logger.info(
                            "[ZW] Bot: This is an invalid use of advanced !identify. Skipping this one..."
                        )
                        continue

                if not match_script:
                    if (
                        len(language_code) == 0
                    ):  # The converter didn't give us any results.
                        no_match_text = COMMENT_INVALID_CODE.format(match, opermalink)
                        try:
                            post.reply(no_match_text + BOT_DISCLAIMER)
                        except (
                            praw.exceptions.APIException
                        ):  # Comment has been deleted.
                            pass
                        logger.info(
                            "[ZW] Bot: But '{}' has no match in the database. Skipping this...".format(
                                match
                            )
                        )
                        continue
                    elif len(language_code) != 0:  # This is a valid language.
                        # Insert code for updating country as well here.
                        if (
                            language_country is not None
                        ):  # There is a country code listed.
                            oajo.set_country(
                                language_country
                            )  # Add that code to the Ajo
                        else:  # There was no country listed, so let's reset the code to none.
                            oajo.set_country(None)
                        oajo.set_language(language_code, True)  # Set the language.
                        logger.info(
                            "[ZW] Bot: Changed flair to {}.".format(language_name)
                        )
                elif match_script:  # This is a script.
                    oajo.set_script(language_code)
                    logger.info(
                        "[ZW] Bot: Changed flair to '{}', with an Unknown+script flair.".format(
                            language_name
                        )
                    )

                if (
                    not match_script
                    and o_language_name != oajo.language_name
                    or not converter(oajo.language_name)[2]
                ):
                    # Definitively a language. Let's archive this to the wiki.
                    # We've also made sure that it's not just a change of state, and write to the `identified` page.
                    record_to_wiki(
                        odate=int(ocreated),
                        otitle=otitle,
                        oid=oid,
                        oflair_text=o_language_name,
                        s_or_i=False,
                        oflair_new=oajo.language_name,
                        user=pauthor,
                    )
            else:  # This is an !identify command for multiple defined languages (e.g. !identify:ru+es+ja
                oajo.set_defined_multiple(match)
                logger.info("[ZW] Bot: Changed flair to a defined multiple one.")

            if (
                KEYWORDS[3] not in pbody
                and KEYWORDS[9] not in pbody
                and oajo.status == "untranslated"
            ):
                # Just a check that we're not sending notifications AGAIN if the identified language is the same as orig
                # This makes sure that they're different languages. So !identify:Chinese on Chinese won't send messages.
                if o_language_name != language_name and MESSAGES_OKAY:
                    if not match_script:  # This is not a script.
                        contacted = ziwen_notifier(
                            language_name, otitle, opermalink, oauthor, True
                        )
                        # Notify people on the list if the post hasn't already been marked as translated
                        # no use asking people to see something that's translated
                    else:  # This is a script... Adapt the proper format. (unknown-cyrl for example)
                        contacted = ziwen_notifier(
                            "unknown-{}".format(language_code),
                            otitle,
                            opermalink,
                            oauthor,
                            True,
                        )
                    oajo.add_notified(
                        contacted
                    )  # Add those who have been contacted to the notified list.

            # Update the comments with the language reference comment
            if (
                language_code not in ["unknown", "multiple", "zxx", "art", "app"]
                and not match_script
            ):
                komento_data = komento_analyzer(komento_submission_from_comment(pid))

                if "bot_unknown" in komento_data or "bot_reference" in komento_data:
                    if (
                        "bot_unknown" in komento_data
                    ):  # Previous Unknown template comment
                        unknown_default = komento_data["bot_unknown"]
                        unknown_default = reddit.comment(id=unknown_default)
                        unknown_default.delete()  # Changed from remove
                        logger.debug(">> Deleted my default Unknown comment...")
                    if "bot_invalid_code" in komento_data:
                        invalid_comment = komento_data["bot_invalid_code"]
                        invalid_comment = reddit.comment(id=invalid_comment)
                        invalid_comment.delete()
                        logger.debug(">> Deleted my invalid code comment...")
                    if (
                        "bot_reference" in komento_data
                    ):  # Previous reference template comment
                        previous_reference = komento_data["bot_reference"]
                        previous_reference = reddit.comment(id=previous_reference)
                        previous_reference.delete()
                        logger.debug(
                            ">> Deleted my previous language reference comment..."
                        )
            """
                    # Get the data from the language cache *if* it's not a defined multiple 
                    # identification. This is disabled for now.
                    if "+" not in match:
                        to_post = reference_search(language_code)
                    else:
                        to_post = None

                    # We have reference data that we can return.
                    if to_post is None:  # There is no good data here.
                        continue
                    else:  # We have gotten good data.
                        to_post = reference_reformatter(to_post)  # Simplify the information that's returned
                        if 'Ethnologue' in to_post or 'MultiTree' in to_post:
                            # Add the header for Unknown posts that get identified
                            to_post = COMMENT_REFERENCE_HEADER + to_post + BOT_DISCLAIMER

                            # Add language reference data in a comment reply.
                            osubmission.reply(to_post)
                            logger.info("[ZW] Bot: Added reference information for {}.".format(language_name))
            """
        if KEYWORDS[0] in pbody:  # This is the basic paging !page function.
            logger.info("[ZW] Bot: COMMAND: !page, from u/{}.".format(pauthor))

            determined_data = comment_info_parser(pbody, "!page:")
            # This should return what was actually identified. Normally will be a Tuple or None
            if (
                determined_data is None
            ):  # The command is problematic. Wrong punctuation, not enough arguments
                logger.info("[ZW] Bot: >> !page data is invalid.")
                continue

            # CODE FOR A 14-DAY VERIFICATION SYSTEM
            poster = reddit.redditor(name=pauthor)
            current_time = int(time.time())
            if current_time - int(poster.created_utc) > 1209600:
                # checks to see if the user account is older than 14 days
                logger.debug(
                    "[ZW] Bot: > u/" + pauthor + "'s account is older than 14 days."
                )
            else:
                post.reply(
                    COMMENT_PAGE_DISALLOWED.format(pauthor=pauthor) + BOT_DISCLAIMER
                )
                logger.info(
                    "[ZW] Bot: > However, u/"
                    + pauthor
                    + " is a new account. Replied to them and skipping..."
                )
                continue

            if oflair_css == "meta" or oflair_css == "community":
                logger.debug("[ZW] Bot: > However, this is not a valid pageable post.")
                continue

            # Okay, it's valid, let's start processing data.
            page_results = notifier_page_multiple_detector(pbody)

            if (
                page_results is None
            ):  # There were no valid page results. (it is a placeholder)
                post.reply(
                    COMMENT_NO_LANGUAGE.format(
                        pauthor=pauthor, language_name="it", language_code=""
                    )
                    + BOT_DISCLAIMER
                )
                logger.info(
                    "[ZW] Bot: No one listed. Replied to the pager u/{} and skipping...".format(
                        pauthor
                    )
                )
            else:  # There were results. Let's loop through them.
                for result in page_results:
                    language_code = result
                    language_name = converter(language_code)[1]

                    if post.submission.over_18:
                        is_nsfw = True
                    else:
                        is_nsfw = False

                    # Send a message via the paging system.
                    paged_users = notifier_page_translators(
                        language_code,
                        language_name,
                        pauthor,
                        otitle,
                        opermalink,
                        oauthor,
                        is_nsfw,
                    )
                    if paged_users is not None:
                        oajo.add_notified(
                            paged_users
                        )  # Add the notified users to the list.

        if (
            KEYWORDS[1] in pbody
        ):  # This function returns data for character lookups with `character`.
            post_content = []
            logger.info("[ZW] Bot: COMMAND: `lookup`, from u/{}.".format(pauthor))

            if pauthor == USERNAME:  # Don't respond to !search results from myself.
                continue

            if oflair_css in ["meta", "community", "missing"]:
                continue

            if oajo.language_name is None:
                continue
            elif type(oajo.language_name) is not str:
                # Multiple post?
                search_language = oajo.language_name[0]
            else:
                search_language = oajo.language_name

            # A dictionary keyed by language and search terms. Built in tokenizers.
            total_matches = lookup_matcher(pbody, search_language)

            # This section allows for the deletion of previous responses if the content changes.
            komento_data = komento_analyzer(komento_submission_from_comment(pid))
            if (
                "bot_lookup_correspond" in komento_data
            ):  # This may have had a comment before.
                relevant_comments = komento_data["bot_lookup_correspond"]

                # This returns a dictionary with the called comment as key.
                for key in relevant_comments:
                    if key == pid:  # This is the key for our current comment.
                        if (
                            "bot_lookup_replies" in komento_data
                        ):  # We try to find any corresponding bot replies
                            relevant_replies = komento_data["bot_lookup_replies"]
                            # Previous replies will be a list
                            previous_responses = relevant_replies[pid]
                            for response in previous_responses:
                                earlier_comment = reddit.comment(id=response)
                                earlier_comment.delete()
                                logger.debug("[ZW] Bot: >>> Previous response deleted")
                                # We delete the earlier versions.

            if len(total_matches.keys()) == 0:
                # Checks to see if there's actually anything in between those two graves.
                # If there's nothing, it skips it.
                logger.debug(
                    "[ZW] Bot: > Received a word lookup command, but found nothing. Skipping..."
                )
                # We are just not going to reply if there is literally nothing found.
                continue

            limit_num_matches = 5
            logger.info(
                "[ZW] Bot: >> Determined Lookup Dictionary: {}".format(total_matches)
            )
            for key, value in total_matches.items():
                if key in CJK_LANGUAGES["Chinese"]:
                    logger.info("[ZW] Bot: >> Conducting lookup search in Chinese.")
                    for match in total_matches[key][:limit_num_matches]:
                        match_length = len(match)
                        if match_length == 1:  # Single-character
                            to_post = zh_character(match)
                            post_content.append(to_post)
                        elif match_length >= 2:  # A word or a phrase
                            find_word = str(match)
                            post_content.append(zh_word(find_word))

                        # Create a randomized wait time between requests.
                        wait_sec = random.randint(3, 12)
                        time.sleep(wait_sec)
                elif key in CJK_LANGUAGES["Japanese"]:
                    logger.info("[ZW] Bot: >> Conducting lookup search in Japanese.")
                    for match in total_matches[key][:limit_num_matches]:
                        match_length = len(str(match))
                        if match_length == 1:
                            to_post = ja_character(match)
                            post_content.append(to_post)
                        elif match_length > 1:
                            find_word = str(match)
                            post_content.append(ja_word(find_word))
                elif key in CJK_LANGUAGES["Korean"]:
                    logger.info("[ZW] Bot: >> Conducting lookup search in Korean.")
                    for match in total_matches[key][:limit_num_matches]:
                        find_word = str(match)
                        post_content.append(
                            lookup_wiktionary_search(find_word, "Korean")
                        )
                else:  # Wiktionary search
                    logger.info("[ZW] Bot: >> Conducting Wiktionary lookup search.")
                    for match in total_matches[key][:limit_num_matches]:
                        find_word = str(match)
                        wiktionary_results = lookup_wiktionary_search(find_word, key)
                        if wiktionary_results is not None:
                            post_content.append(wiktionary_results)

            # Join the content together.
            if post_content:  # If we have results lets post them
                # Join the resulting content together as a string.
                post_content = "\n\n".join(post_content)
            else:  # No results, let's set it to None.
                post_content = None
                # For now we are simply not going to reply if there are no results.

            try:
                if post_content is not None:
                    author_tag = (
                        "*u/{} (OP), the following lookup results "
                        "may be of interest to your request.*\n\n".format(oauthor)
                    )
                    post.reply(author_tag + post_content + BOT_DISCLAIMER)
                    logger.info(
                        "[ZW] Bot: >> Looked up the term(s) in {}.".format(
                            search_language
                        )
                    )
                else:
                    logger.info("[ZW] Bot: >> No results found. Skipping...")
            except praw.exceptions.APIException:  # This means the comment is deleted.
                logger.debug("[ZW] Bot: >> Previous comment was deleted.")

        if KEYWORDS[7] in pbody:
            # the !reference command gets information from Ethnologue, Wikipedia, and other sources
            # to post as a reference
            determined_data = comment_info_parser(pbody, "!reference:")
            # This should return what was actually identified. Normally will be a Tuple or None
            if (
                determined_data is None
            ):  # The command is problematic. Wrong punctuation, not enough arguments
                logger.debug("[ZW] Bot: >> !reference data is invalid.")
                continue

            language_match = determined_data[0]
            logger.info("[ZW] Bot: COMMAND: !reference, from u/{}.".format(pauthor))
            post_content = reference_search(language_match)
            if (
                post_content is None
            ):  # There was no good data. We return the invalid comment.
                post_content = COMMENT_INVALID_REFERENCE
            post.reply(post_content)
            logger.info(
                "[ZW] Bot: Posted the reference results for '{}'.".format(
                    language_match
                )
            )

        if (
            KEYWORDS[8] in pbody
        ):  # The !search function looks for strings in other posts on r/translator
            determined_data = comment_info_parser(pbody, "!search:")
            # This should return what was actually identified. Normally will be a Tuple or None
            if (
                determined_data is None
            ):  # The command is problematic. Wrong punctuation, not enough arguments
                logger.debug("[ZW] Bot: >> !search data is invalid.")
                continue

            logger.info("[ZW] Bot: COMMAND: !search, from u/" + pauthor + ".")
            search_term = determined_data[0]

            google_url = []
            reddit_id = []
            reply_body = []

            for url in googlesearch.search(
                search_term + " site:reddit.com/r/translator", num=4, stop=4
            ):
                if "comments" not in url:
                    continue
                google_url.append(url)
                oid = re.search(r"comments/(.*)/\w", url).group(1)
                reddit_id.append(oid)

            if len(google_url) == 0:
                post.reply(COMMENT_NO_RESULTS + BOT_DISCLAIMER)
                logger.info(
                    "[ZW] Bot: > There were no results for "
                    + search_term
                    + ". Moving on..."
                )
                continue

            for oid in reddit_id:
                submission = reddit.submission(id=oid)
                s_title = submission.title
                s_date = datetime.datetime.fromtimestamp(submission.created).strftime(
                    "%Y-%m-%d"
                )
                s_permalink = submission.permalink
                header_string = "#### [{}]({}) ({})\n\n".format(
                    s_title, s_permalink, s_date
                )
                reply_body.append(header_string)
                submission.comments.replace_more(limit=None)
                s_comments = submission.comments.list()

                for comment in s_comments:
                    try:
                        c_author = comment.author.name
                    except AttributeError:
                        # Author is deleted. We don't care about this post.
                        continue

                    if c_author == USERNAME:  # I posted this comment.
                        continue

                    if (
                        KEYWORDS[8] in comment.body.lower()
                    ):  # This contains the !search string.
                        continue  # We don't want this.

                    # Format a comment body nicely.
                    c_body = comment.body

                    # Replace any keywords
                    for keyword in KEYWORDS:
                        c_body = c_body.replace(keyword, "")
                    c_body = str(
                        "\n> ".join(c_body.split("\n"))
                    )  # Indent the lines with Markdown >
                    c_votes = str(comment.score)  # Get the score of the comment

                    if search_term.lower() in c_body.lower():
                        comment_string = (
                            "##### Comment by u/"
                            + c_author
                            + " (+"
                            + c_votes
                            + "):\n\n>"
                            + c_body
                        )
                        reply_body.append(comment_string)
                        continue
                    else:
                        continue

            reply_body = "\n\n".join(
                reply_body[:6]
            )  # Limit it to 6 responses. To avoid excessive length.
            post.reply(
                '## Search results on r/translator for "'
                + search_term
                + '":\n\n'
                + reply_body
            )
            logger.info("[ZW] Bot: > Posted my findings for the search term.")

        """STATE COMMANDS (!doublecheck, !translated, !claim, !missing, short thanks)"""

        if KEYWORDS[9] in pbody:
            # !doublecheck function, used for asking for reviews of one's work.

            logger.info("[ZW] Bot: COMMAND: !doublecheck, from u/{}.".format(pauthor))

            if oajo.type is "multiple":
                if isinstance(
                    oajo.language_name, list
                ):  # It is a defined multiple post.
                    # Try to see if there's data in the comment.
                    # If the comment is just the command, we take the parent comment and together check to see.
                    checked_text = str(pbody_original)
                    if (
                        len(pbody) < 12
                    ):  # This is just the command, so let's get the parent comment.
                        # Get the parent comment
                        parent_item = post.parent_id
                        if "t1" in parent_item:  # The parent is a comment
                            parent_comment = post.parent()
                            # Combine the two together.
                            checked_text = "{} {}".format(
                                parent_comment.body, pbody_original
                            )

                    comment_check = ajo_defined_multiple_comment_parser(
                        checked_text, oajo.language_name
                    )

                    # We have data, we can set the status as different in the flair.
                    if comment_check is not None:
                        # Start setting the flairs, from a list.
                        for language in comment_check[0]:
                            language_code = converter(language)[0]
                            oajo.set_status_multiple(language_code, "doublecheck")
                            logger.info(
                                "[ZW] Bot: > {} in defined multiple post for doublechecking".format(
                                    language
                                )
                            )
                else:
                    logger.info(
                        "[ZW] Bot: > This is a general multiple post that is not eligible for status changes."
                    )
            elif oflair_css in ["translated", "meta", "community", "doublecheck"]:
                logger.info(
                    "[ZW] Bot: > This post isn't eligible for double-checking. Skipping this one..."
                )
                continue
            else:
                oajo.set_status("doublecheck")
                oajo.set_time("doublecheck", current_time)
                logger.info("[ZW] Bot: > Marked post as 'Needs Review.'")

            # Delete any claimed comment.
            komento_data = komento_analyzer(osubmission)
            if "bot_claim_comment" in komento_data:
                claim_comment = komento_data["bot_claim_comment"]
                claim_comment = reddit.comment(claim_comment)
                claim_comment.delete()

        if (
            KEYWORDS[2] in pbody
        ):  # This function picks up a !missing command and messages the OP about it.
            if not css_check(
                oflair_css
            ):  # Basic check to see if this is something that can be acted on.
                continue

            logger.info("[ZW] Bot: COMMAND: !missing, from u/" + pauthor + ".")

            total_message = MSG_MISSING_ASSETS.format(
                oauthor=oauthor, opermalink=opermalink
            )
            try:
                reddit.redditor(oauthor).message(
                    "A message from r/translator regarding your translation request",
                    total_message + BOT_DISCLAIMER,
                )
            except praw.exceptions.APIException:
                pass
            # Send a message to the OP about their post missing content.

            oajo.set_status("missing")
            oajo.set_time("missing", current_time)
            logger.info(
                "[ZW] Bot: > Marked a post by u/{} as missing assets and messaged them.".format(
                    oauthor
                )
            )

        if (
            any(keyword in pbody for keyword in THANKS_KEYWORDS)
            and KEYWORDS[3] not in pbody
            and len(pbody) <= 20
        ):
            # This processes simple thanks into translated, but leaves alone if it's an exception.
            # Has to be a short thanks, and not have !translated in the body.
            if oflair_css in ["meta", "community", "multiple", "app", "generic"]:
                continue

            if (
                pauthor != oauthor
            ):  # Is the author of the comment the author of the post?
                continue  # If not, continue, we don't care about this.

            # This should only be marked if it's untranslated. So it shouldn't affect
            if oajo.status is not "untranslated":
                continue

            # This should only be marked if it's not in an identified state, in case people respond to that command.
            if oajo.is_identified:
                continue

            exceptions_list = ["but", "however", "no"]  # Did the OP have reservations?
            if any(exception in pbody for exception in exceptions_list):
                continue
            else:  # Okay, it really is a short thanks
                logger.info(
                    "[ZW] Bot: COMMAND: Short thanks from u/{}. Sending user a message...".format(
                        pauthor
                    )
                )
                oajo.set_status("translated")
                oajo.set_time("translated", current_time)
                short_msg = (
                    MSG_SHORT_THANKS_TRANSLATED.format(oauthor, opermalink)
                    + BOT_DISCLAIMER
                )
                try:
                    reddit.redditor(oauthor).message(
                        "[Notification] A message about your translation request",
                        short_msg,
                    )
                except praw.exceptions.APIException:  # Likely shadowbanned.
                    pass

        if KEYWORDS[14] in pbody:  # Claiming posts with the !claim command
            if oflair_css in [
                "translated",
                "doublecheck",
                "community",
                "meta",
                "multiple",
                "app",
            ]:
                # We don't want to process these posts.
                continue

            if KEYWORDS[3] in pbody or KEYWORDS[9] in pbody:
                # This is for the scenario where someone edits their original claim comment with the translation
                # Then marks it as !translated or !doublecheck. We just want to ignore it then
                continue

            logger.info("[ZW] Bot: COMMAND: !claim, from u/{}.".format(pauthor))
            current_time = int(time.time())
            utc_timestamp = datetime.datetime.utcfromtimestamp(current_time).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            claimed_already = False  # Boolean to see if it has been claimed as of now.

            komento_data = komento_analyzer(osubmission)

            if "bot_claim_comment" in komento_data:  # Found an already claimed comment
                # claim_comment = komento_data['bot_claim_comment']
                claimer_name = komento_data["claim_user"]
                remaining_time = komento_data["claim_time_diff"]
                remaining_time_text = str(datetime.timedelta(seconds=remaining_time))
                if (
                    pauthor == claimer_name
                ):  # If it's another claim by the same person listed...
                    post.reply("You've already claimed this post." + BOT_DISCLAIMER)
                    claimed_already = True
                    logger.info(
                        "[ZW] Bot: >> But this post is already claimed by them. Replied to them."
                    )
                else:
                    post.reply(
                        COMMENT_CURRENTLY_CLAIMED.format(
                            claimer_name=claimer_name,
                            remaining_time=remaining_time_text,
                        )
                        + BOT_DISCLAIMER
                    )
                    claimed_already = True
                    logger.info(
                        "[ZW] Bot: >> But this post is already claimed. Replied to the claimer about it."
                    )

            if (
                not claimed_already
            ):  # This has not yet been claimed. We can claim it for the user.
                oajo.set_status("inprogress")
                oajo.set_time("inprogress", current_time)
                claim_note = osubmission.reply(
                    COMMENT_CLAIM.format(
                        claimer=pauthor,
                        time=utc_timestamp,
                        language_name=oajo.language_name,
                    )
                    + BOT_DISCLAIMER
                )
                claim_note.mod.distinguish(sticky=True)  # Distinguish the bot's comment
                logger.info(
                    "[ZW] Bot: > Marked a post by u/{} as claimed and in progress.".format(
                        oauthor
                    )
                )

        if KEYWORDS[3] in pbody:
            # This is a !translated function that messages people when their post has been translated.
            thanks_already = False
            translated_found = True

            logger.info("[ZW] Bot: COMMAND: !translated, from u/" + pauthor + ".")

            if oflair_css is None:  # If there is no CSS flair...
                oflair_css = "generic"  # Give it a generic flair.

            if oajo.type is "multiple":
                if isinstance(
                    oajo.language_name, list
                ):  # It is a defined multiple post.
                    # Try to see if there's data in the comment.
                    # If the comment is just the command, we take the parent comment and together check to see.
                    checked_text = str(pbody_original)
                    if (
                        len(pbody) < 12
                    ):  # This is just the command, so let's get the parent comment.
                        # Get the parent comment
                        parent_item = post.parent_id
                        if "t1" in parent_item:  # The parent is a comment
                            parent_comment = post.parent()
                            # Combine the two together.
                            checked_text = "{} {}".format(
                                parent_comment.body, pbody_original
                            )

                    comment_check = ajo_defined_multiple_comment_parser(
                        checked_text, oajo.language_name
                    )

                    # We have data, we can set the status as different in the flair.
                    if comment_check is not None:
                        # Start setting the flairs, from a list.
                        for language in comment_check[0]:
                            language_code = converter(language)[0]
                            oajo.set_status_multiple(language_code, "translated")
                            logger.info(
                                "[ZW] Bot: > Marked {} in this defined multiple post as done.".format(
                                    language
                                )
                            )
                else:
                    logger.debug(
                        "[ZW] Bot: > This is a general multiple post that is not eligible for status changes."
                    )
            elif oflair_css not in ["meta", "community", "translated"]:
                # Make sure we're not altering certain flairs.
                oajo.set_status("translated")
                oajo.set_time("translated", current_time)
                logger.info("[ZW] Bot: > Marked post as translated.")

            komento_data = komento_analyzer(osubmission)

            if oajo.is_bot_crosspost:  # This is a crosspost, lets work some magic.
                if "bot_xp_original_comment" in komento_data:
                    logger.debug("[ZW] Bot: >> Fetching original crosspost comment...")
                    original_comment = reddit.comment(
                        komento_data["bot_xp_original_comment"]
                    )
                    original_comment_text = original_comment.body

                    # We want to strip off the disclaimer
                    original_comment_text = original_comment_text.split("---")[
                        0
                    ].strip()

                    # Add the edited text
                    edited_header = "\n\n**Edit**: This crosspost has been marked as translated on r/translator."
                    original_comment_text += edited_header + BOT_DISCLAIMER
                    if (
                        "**Edit**" not in original_comment.body
                    ):  # Has this already been edited?
                        original_comment.edit(original_comment_text)
                        logger.debug(
                            "[ZW] Bot: >> Edited my original comment on the other subreddit to alert people."
                        )

            if "bot_long" in komento_data:  # Found a bot (Long) comment, delete it.
                long_comment = komento_data["bot_long"]
                long_comment = reddit.comment(long_comment)
                long_comment.delete()
            if (
                "bot_claim_comment" in komento_data
            ):  # Found an older claim comment, delete it.
                claim_comment = komento_data["bot_claim_comment"]
                claim_comment = reddit.comment(claim_comment)
                claim_comment.delete()
            if (
                "op_thanks" in komento_data
            ):  # OP has thanked someone in the thread before.
                thanks_already = True
                translated_found = False

            if (
                translated_found
                and not thanks_already
                and oflair_css not in ["multiple", "app"]
            ):
                # First we check to see if the author has already been recorded as getting a message.
                try:
                    messaged_already = oajo.author_messaged
                except AttributeError:
                    messaged_already = False

                # If the commentor is not the author of the post and they have not been messaged, we can tell them.
                if pauthor != oauthor and not messaged_already:
                    messaging_translated_message(
                        oauthor=oauthor, opermalink=opermalink
                    )  # Sends them notification msg
                    oajo.set_author_messaged(True)

        """MODERATOR-ONLY COMMANDS (!delete, !reset, !note, !set)"""

        if KEYWORDS[13] in pbody:  # This is to allow OP or mods to !delete crossposts
            if not oajo.is_bot_crosspost:  # If this isn't actually a crosspost..
                continue
            else:  # This really is a crosspost.
                logger.info("[ZW] Bot: COMMAND: !delete from u/{}".format(pauthor))
                if pauthor == oauthor or pauthor == requester or is_mod(pauthor):
                    osubmission.mod.remove()  # We'll use remove for now -- can switch to delete() later.
                    logger.info("[ZW] Bot: >> Removed crosspost.")

        if (
            KEYWORDS[15] in pbody
        ):  # !reset command, to revert a post back to as if it were freshly processed
            if (
                is_mod(pauthor) or pauthor == oauthor
            ):  # Check if user is a mod or the OP.
                logger.info(
                    "[ZW] Bot: COMMAND: !reset, from user u/{}.".format(pauthor)
                )
                oajo.reset(otitle)
                logger.info("[ZW] Bot: > Reset everything for the designated post.")
            else:
                continue

        if (
            KEYWORDS[16] in pbody
        ):  # !long command, for mods to mark a post as long for translators.
            if is_mod(pauthor):  # Check if user is a mod.
                logger.info("[ZW] Bot: COMMAND: !long, from mod u/{}.".format(pauthor))

                # This command works as a flip switch. It changes the state to the opposite.
                current_status = oajo.is_long
                new_status = not current_status

                # Delete any long informational comment.
                komento_data = komento_analyzer(komento_submission_from_comment(pid))
                if "bot_long" in komento_data:
                    long_comment = reddit.comment(id=komento_data["bot_long"])
                    long_comment.delete()
                    logger.debug("[ZW] Bot: Deleted my default long comment...")

                # Set the status
                oajo.set_long(new_status)
                logger.info(
                    "[ZW] Bot: Changed the designated post's long state to '{}.'".format(
                        new_status
                    )
                )

        if KEYWORDS[6] in pbody:
            # the !note command saves posts which are not CSS/template supported so they can be used as reference.
            # This is now rarely used.
            if not is_mod(
                pauthor
            ):  # Check to see if the person calling this command is a moderator
                continue
            match = comment_info_parser(pbody, "!note:")[0]
            language_name = converter(match)[1]
            logger.info(
                "[ZW] Bot: COMMAND: !note, from moderator u/{}.".format(pauthor)
            )
            record_to_wiki(
                odate=int(ocreated),
                otitle=otitle,
                oid=oid,
                oflair_text=language_name,
                s_or_i=True,
                oflair_new="",
            )  # Write to the saved page

        if KEYWORDS[5] in pbody:
            # !set is a mod-accessible means of setting the post flair.
            # It removes the comment (through AM) so it looks like nothing happened.
            if not is_mod(
                pauthor
            ):  # Check to see if the person calling this command is a moderator
                continue

            set_data = comment_info_parser(pbody, "!set:")

            if set_data is not None:  # We have data.
                match = set_data[0]
                reset_state = set_data[1]
            else:  # Invalid command (likely did not include a language)
                continue

            logger.info("[ZW] Bot: COMMAND: !set, from moderator u/{}.".format(pauthor))

            language_code = converter(match)[0]
            language_name = converter(match)[1]
            language_country = converter(match)[3]

            if language_country is not None:  # There is a country code listed.
                oajo.set_country(language_country)  # Add that code to the Ajo

            if reset_state:  # Advanced !set mode, we set it to untranslated.
                oajo.set_status("untranslated")

            if "+" not in set_data[0]:  # This is a standard !set
                # Set the language to the Ajo
                oajo.set_language(language_code)
                komento_data = komento_analyzer(komento_submission_from_comment(pid))
                if (
                    "bot_unknown" in komento_data
                ):  # Delete previous Unknown template comment
                    unknown_default = komento_data["bot_unknown"]
                    unknown_default = reddit.comment(id=unknown_default)
                    unknown_default.delete()  # Changed from remove
                    logger.debug("[ZW] Bot: >> Deleted my default Unknown comment...")
                logger.info(
                    "[ZW] Bot: > Updated the linkflair tag to '{}'.".format(
                        language_code
                    )
                )
            else:  # This is a defined multiple !set
                oajo.set_defined_multiple(set_data[0])
                logger.info("[ZW] Bot: > Updated the post to a defined multiple one.")

            # Message the mod who called it.
            set_msg = f"The [post]({opermalink}) has been set to the language code `{language_code}` (`{language_name}`)."
            reddit.redditor(pauthor).message(
                "[Notification] !set command successful", set_msg
            )

        # Push the FINAL UPDATE TO REDDIT
        if oflair_css not in [
            "community",
            "meta",
        ]:  # There's nothing to change for these
            oajo.update_reddit()  # Push all changes to the server
            ajo_writer(oajo)  # Write the Ajo to the local database
            logger.info(
                "[ZW] Bot: Ajo for {} updated and saved to the local database.".format(
                    oid
                )
            )
            messaging_user_statistics_writer(
                pbody, pauthor
            )  # Record data on user commands.
            logger.debug("[ZW] Bot: Recorded user commands in database.")


def verification_parser():
    """
    Top-level function to collect requests for verified flairs. Ziwen will write their information into a log
    and also report their comment to the moderators for inspection and verification.

    :return: Nothing.
    """
    if len(VERIFIED_POST_ID) == 0:
        return

    submission = reddit.submission(id=VERIFIED_POST_ID)
    try:
        submission.comments.replace_more(limit=None)
    except ValueError:
        return
    s_comments = list(submission.comments)

    for comment in s_comments:
        cid = comment.id
        c_body = comment.body.strip()
        try:
            c_author = comment.author.name
            c_author_string = "u/" + c_author
        except AttributeError:
            # Author is deleted. We don't care about this post.
            continue
        cursor_main.execute("SELECT * FROM oldcomments WHERE ID=?", [cid])
        if cursor_main.fetchone():
            # Post is already in the database
            continue
        cursor_main.execute("INSERT INTO oldcomments VALUES(?)", [cid])
        conn_main.commit()

        comment.save()  # Saves the comment on Reddit so we know not to use it. (bot will not process saved comments)

        ocreated = int(comment.created_utc)
        osave = comment.saved  # Should be True if processed, False otherwise.
        current_time = int(time.time())

        if current_time - ocreated >= 300:  # Comment is too old; let's not do it.
            continue

        if osave:  # Comment has been processed already.
            continue

        c_body = c_body.replace("\n", "|")
        c_body = c_body.replace("||", "|")

        components = c_body.split("|")
        components = list(filter(None, components))
        url_regex = r"https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{2,256}\.[a-z]{2,6}\b([-a-zA-Z0-9@:%_\+.~#?&//=]*)"

        try:
            language_name = components[0].strip()
            url_1 = re.search(url_regex, components[1]).group(0).strip()
            url_2 = re.search(url_regex, components[2]).group(0).strip()
            url_3 = re.search(url_regex, components[3]).group(0).strip()
        except (
            IndexError,
            AttributeError,
        ):  # There must be something wrong with the verification comment.
            return  # Exit, don't do anything.

        try:
            notes = components[4]
        except IndexError:  # No notes were listed.
            notes = ""

        # Try and get a native language thank-you from our main language dictionary.
        language_code = converter(language_name)[0]
        thanks_phrase = MAIN_LANGUAGES.get(language_code, {}).get("thanks", "Thank you")

        # Form the entry for the verification log.
        entry = "| {} | {} | [1]({}), [2]({}), [3]({}) | {} |"
        entry = entry.format(c_author_string, language_name, url_1, url_2, url_3, notes)
        page_content = reddit.subreddit(SUBREDDIT).wiki["verification_log"]
        page_content_new = str(page_content.content_md) + "\n" + entry

        # Update the verification log.
        page_content.edit(
            content=page_content_new,
            reason="Updating the verification log with a new request from u/{}".format(
                c_author
            ),
        )

        # Reply to the commenter, report so that moderators can take a look.
        comment.reply(
            COMMENT_VERIFICATION_RESPONSE.format(thanks_phrase, c_author)
            + BOT_DISCLAIMER
        )
        comment.report(
            "Ziwen: Please check verification request from u/{}.".format(c_author)
        )
        logger.info(
            "[ZW] Updated the verification log with a new request from u/" + c_author
        )

    return


def progress_checker():
    """
    This is an independent top-level function that checks to see what posts are still marked as "In Progress."
    It checks to see if they have expired (that is, the claim period is past a defined time).
    If they are expired, this function resets them to the 'Untranslated' state.

    :return: Nothing.
    """

    # Conduct a search on Reddit.
    search_query = (
        'flair:"in progress"'  # Get the posts that are still marked as in progress
    )
    search_results = r.search(search_query, time_filter="month", sort="new")

    for (
        post
    ) in (
        search_results
    ):  # Now we process the ones that are stil marked as in progress to reset them.
        # Variable Creation
        oid = post.id
        oflair_css = post.link_flair_css_class
        opermalink = post.permalink

        if oflair_css is None:
            continue
        elif (
            oflair_css != "inprogress"
        ):  # If it's not actually an in progress one, let's skip it.
            continue

        # Load its Ajo.
        oajo = ajo_loader(oid)  # First check the local database for the Ajo.
        if (
            oajo is None
        ):  # We couldn't find a stored dict, so we will generate it from the submission.
            logger.debug(
                "[ZW] progress_checker: Couldn't find an Ajo in the local database. Loading from Reddit."
            )
            oajo = Ajo(post)

        # Process the post and get some data out of it.
        komento_data = komento_analyzer(post)
        if "claim_time_diff" in komento_data:
            # Get the time difference between its claimed time and now.
            time_difference = komento_data["claim_time_diff"]
            if (
                time_difference > CLAIM_PERIOD
            ):  # This means the post is older than the claim time period.
                # Delete my advisory notice.
                claim_notice = reddit.comment(id=komento_data["bot_claim_comment"])
                claim_notice.delete()  # Delete the notice comment.
                logger.info(
                    "[ZW] progress_checker: Post exceeded the claim time period. Reset. {}".format(
                        opermalink
                    )
                )

                # Update the Ajo.
                oajo.set_status("untranslated")
                oajo.update_reddit()  # Push all changes to the server
                ajo_writer(oajo)  # Write the Ajo to the local database
            else:  # This post is still under the time limit. Do nothing.
                continue

    return


"""LESSER RUNTIMES"""


def cc_ref():
    """
    This is a secondary runtime for Chinese language subreddits. The subreddits the bot monitors are contained in a
    multireddit called 'chinese'. It provides character and word lookup for them, same results as the
    ones on r/translator.

    :return: Nothing.
    """

    multireddit = reddit.multireddit(USERNAME, "chinese")
    posts = []
    posts += list(multireddit.comments(limit=MAXPOSTS))

    for post in posts:
        pid = post.id

        cursor_main.execute("SELECT * FROM oldcomments WHERE ID=?", [pid])
        if cursor_main.fetchone():
            # Post is already in the database
            continue

        pbody = post.body
        pbody = pbody.lower()

        if not any(key.lower() in pbody for key in KEYWORDS):
            # Does not contain our keyword
            continue

        cursor_main.execute("INSERT INTO oldcomments VALUES(?)", [pid])
        conn_main.commit()

        if KEYWORDS[1] in pbody:
            post_content = []
            # This basically checks to make sure it's actually a Chinese/Japanese character.
            # It will return nothing if it is something else.
            matches = re.findall("`([\u2E80-\u9FFF]+)`", pbody, re.DOTALL)
            # match_length = len(str(matches))
            tokenized_list = []
            if len(matches) == 0:
                continue
            for match in matches:  # We are going to break this up
                if len(match) >= 2:  # Longer than bisyllabic?
                    new_matches = lookup_zhja_tokenizer(simplify(match), "zh")
                    for new_word in new_matches:
                        tokenized_list.append(new_word)
                else:
                    tokenized_list.append(match)
            for match in tokenized_list:
                match_length = len(str(match))
                if match_length == 1:
                    to_post = zh_character(match)
                    post_content.append(to_post)
                elif match_length >= 2:
                    find_word = str(match)
                    post_content.append(zh_word(find_word))

            post_content = "\n\n".join(post_content)
            if len(post_content) > 10000:  # Truncate only if absolutely necessary.
                post_content = post_content[:9900]
            try:
                post.reply(post_content + BOT_DISCLAIMER)
                logger.info(
                    "[ZW] CC_REF: Replied to lookup request for {} "
                    "on a Chinese subreddit.".format(tokenized_list)
                )
            except praw.exceptions.RedditAPIException:
                post.reply(
                    "Sorry, but the character data you've requested"
                    "exceeds the amount Reddit allows for a comment."
                )

    return


def ziwen_maintenance():
    """
    A simple top-level function to group together common activities that need to be run on an occasional basis.
    This is usually activated after almost a hundred cycles to update information.

    :return: Nothing.
    """

    global POST_TEMPLATES
    POST_TEMPLATES = maintenance_template_retriever()
    logger.debug(
        "[ZW] # Current post templates retrieved: {} templates".format(
            len(POST_TEMPLATES.keys())
        )
    )

    global VERIFIED_POST_ID
    VERIFIED_POST_ID = (
        maintenance_get_verified_thread()
    )  # Get the last verification thread's ID and store it.
    if len(VERIFIED_POST_ID):
        logger.info(
            "[ZW] # Current verification post found: https://redd.it/{}\n\n".format(
                VERIFIED_POST_ID
            )
        )
    else:
        logger.error("[ZW] # No current verification post found!")

    global ZW_USERAGENT
    ZW_USERAGENT = get_random_useragent()  # Pick a random useragent from our list.
    logger.debug("[ZW] # Current user agent: {}".format(ZW_USERAGENT))

    global GLOBAL_BLACKLIST
    GLOBAL_BLACKLIST = (
        maintenance_blacklist_checker()
    )  # We download the blacklist of users.
    logger.debug(
        "[ZW] # Current global blacklist retrieved: {} users".format(
            len(GLOBAL_BLACKLIST)
        )
    )

    global MOST_RECENT_OP
    MOST_RECENT_OP = maintenance_most_recent()

    points_worth_cacher()  # Update the points cache
    logger.debug("[ZW] # Points cache updated.")

    maintenance_database_processed_cleaner()  # Clean the comments that have been processed.

    return


"""INITIAL VARIABLE SET-UP"""

# We start the bot with a couple of routines to populate the data from our wiki.
ziwen_maintenance()
logger.info("[ZW] Bot routine starting up...")


"""RUNNING THE BOT"""

# This is the actual loop that runs the top-level functions of the bot.
# */10 * * * *

if __name__ == "__main__":
    try:
        # noinspection PyBroadException
        set_start_time = time.time()
        run_information = ()

        try:
            # First it processes the titles of new posts.
            ziwen_posts()
            # Then it checks for any edits to comments.
            edit_finder()
            # Next the bot runs all sub-functions on its main subreddit, r/translator.
            ziwen_bot()
            # Then it checks its messages (generally for new subscription lookups).
            ziwen_messages()
            # Finally checks for posts that are still claimed and 'in progress.'
            progress_checker()

            # Record API usage limit.
            probe = reddit.redditor(USERNAME).created_utc
            used_calls = reddit.auth.limits["used"]

            # Record memory usage at the end of an isochronism.
            mem_num = psutil.Process(os.getpid()).memory_info().rss
            mem_usage = "Memory usage: {:.2f} MB.".format(mem_num / (1024 * 1024))
            logger.info(
                "[ZW] Run complete. Calls used: {}. {}".format(used_calls, mem_usage)
            )

            if (
                not TESTING_MODE
            ):  # Disable these functions if just testing on r/trntest.
                logger.debug("[ZW] Main: Searching other subreddits.")
                verification_parser()  # The bot checks if there are any new requests for verification.
                cc_ref()  # Finally the bot runs lookup searches on Chinese subreddits.

        except Exception as e:  # The bot encountered an error/exception.
            logger.error(f"[ZW] Main: Encounted error {e}.")
            # Format the error text.
            error_entry = traceback.format_exc()
            record_error_log(error_entry)  # Save the error to a log.
            logger.error("[ZW] Main: > Logged this error. Ended run.")
        else:
            # Package data for this run and write it to a record.
            elapsed_time = (time.time() - set_start_time) / 60
            run_time = time_convert_to_string(set_start_time)
            run_information = (
                run_time,
                "Cycle run",
                used_calls,
                mem_usage,
                elapsed_time,
            )
            record_activity_csv(run_information)
            logger.info(
                "[ZW] Main: Run complete. {:.2f} minutes.\n".format(elapsed_time)
            )
    except KeyboardInterrupt:  # Manual termination of the script with Ctrl-C.
        logger.info("Manual user shutdown.")
        sys.exit()
else:
    logger.info("[ZW] Main: Running as imported module.")
