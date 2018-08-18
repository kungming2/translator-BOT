#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

"""PYTHON MODULES"""
import calendar
import datetime
import time
import traceback  # For documenting errors
import json  # Used in the Wiktionary parsing
import sqlite3  # For processing the databases
import praw  # simple interface to the reddit API, also handles rate limiting of requests
import prawcore  # Base module for error logging.
import requests
import pafy  # Gets YouTube video length
import youtube_dl  # Needed for some except logging, used by pafy
import romkan  # Needed to include automatic romaji conversion
import jieba  # Segmenter for Chinese
import tinysegmenter  # Segmenter for Japanese
import MeCab  # Japanese tokenizer
import wikipedia  # Needed to include Wikipedia content in the !reference command

from bs4 import BeautifulSoup as Bs
from google import search
from lxml import html
from mafan import simplify, tradify
from wiktionaryparser import WiktionaryParser

from _languages import *
from _config import *
from _responses import *
from Data import _ko_romanizer

BOT_NAME = 'Ziwen'
VERSION_NUMBER = '1.7.36'
USER_AGENT = ('{} {}, a notifications messenger, general commands monitor, and moderator for r/translator.'
              ' Written and maintained by u/kungming2.'.format(BOT_NAME, VERSION_NUMBER))

# This is how many posts Ziwen will retrieve all at once. PRAW can download 100 at a time.
MAXPOSTS = 100
# This is how many seconds I will wait between cycles. The bot is completely inactive during this time.
WAIT = 30
# After this many cycles, the bot will clean its database
# Keeping only the latest (CLEANCYCLES*MAXPOSTS) items
CLEANCYCLES = 90
# How long do we allow people to claim a post? (in seconds)
CLAIM_PERIOD = 28800
# A boolean that enables the bot to send messages or not. Good for testing.
MESSAGES_OKAY = True
# A number that defines the max number of notifications an individual will get in a month.
NOTIFICATIONS_LIMIT = 140

'''KEYWORDS LISTS'''
# These are the words we are looking for (the commands on r/translator).
KEYWORDS = ["!page:", "`", "!missing", "!translated", "!id:", "!set:", "!note:", "!reference:", "!search:",
            "!doublecheck", "!identify:", '!translate', '!translator', '!delete', '!claim', '!reset']
# These are the words that count as a 'thanks' from the OP.
# If a message includes them, the bot won't message them asking them to thank the translator.
THANKS_KEYWORDS = ["thank", "thanks", "tyvm", "thx", "danke", "arigato", "gracias", "appreciate", "solved"]
# These are keywords that if included with !translated will give credit to the parent commentator.
VERIFYING_KEYWORDS = ["concur", "agree", "verify", "verified", "approve", "is correct", "is right", "well done",
                      "well-done", "good job", "marking", "good work"]
# A cache for language multipliers, generated each instance of running.
# Allows us to access the wiki less and speed up the process.
CACHED_MULTIPLIERS = {}


'''CONNECTIONS TO REDDIT & SQL DATABASES'''

print('|==========================Accessing SQL Databases...=========================|')
# This connects the bot with the database of posts and comments that have already been processed.
sql = sqlite3.connect(FILE_ADDRESS_PROCESSED)
cur = sql.cursor()

# This connects the bot with the database of users signed up for notifications.
conn = sqlite3.connect(FILE_ADDRESS_NOTIFY)
cursor = conn.cursor()

# This is the main points database
conn_p = sqlite3.connect(FILE_ADDRESS_POINTS)  # This connects the bot with the database of points
cursor_p = conn_p.cursor()

# We store language data here for the run_reference command as a cache.
zw_reference_cache = sqlite3.connect(FILE_ADDRESS_REFERENCE)
zw_reference_cursor = zw_reference_cache.cursor()

# Local storage for Ajos, objects that the bot uses for posts.
conn_ajo = sqlite3.connect(FILE_ADDRESS_AJO_DB)
cursor_ajo = conn_ajo.cursor()

# This is the comment cache used for detecting edits.
conn_cache = sqlite3.connect(FILE_ADDRESS_COMMENT_CACHE)
cursor_cache = conn_cache.cursor()

# This is the multiplier cache for points.
conn_multiplier = sqlite3.connect(FILE_ADDRESS_MULTIPLIER_CACHE)
cursor_multiplier = conn_multiplier.cursor()

print('|=======================Logging in as u/translator-BOT...=====================|')
reddit = praw.Reddit(client_id=ZIWEN_APP_ID,
                     client_secret=ZIWEN_APP_SECRET, password=PASSWORD,
                     user_agent=USER_AGENT, username=USERNAME)
r = reddit.subreddit(SUBREDDIT)

print('|=============================================================================|')
print('  Initializing {} {} for r/translator...\n'.format(BOT_NAME, VERSION_NUMBER))
print('  with languages module {}'.format(VERSION_NUMBER_LANGUAGES))
print('|=============================================================================|')

'''STARTUP FUNCTIONS'''


def blacklist_checker_run_once():
    """A start-up function that runs once and gets blacklisted usernames from the wiki of r/translatorBOT."""

    # Retrieve the page.
    blacklist_page = reddit.subreddit("translatorBOT").wiki["blacklist"]
    overall_page_content = str(blacklist_page.content_md)  # Get the page's content.
    usernames_raw = overall_page_content.split("####")[1]
    usernames_raw = usernames_raw.split("\n")[2].strip()  # Get just the usernames.

    # Convert the usernames into a list.
    blacklist_usernames = usernames_raw.split(", ")

    # Convert the usernames to lowercase.
    blacklist_usernames = [item.lower() for item in blacklist_usernames]

    # Exclude AutoModerator
    blacklist_usernames.remove("automoderator")

    return blacklist_usernames


def redesign_template_retriever():
    """Function that retrieves the current flairs available on the subreddit and returns a dictionary.
    Dictionary is keyed by the old css_class, with the long-form template ID as a value per key.
    Example: 'cs': XXXXXXXX """

    new_template_ids = {}

    for template in r.flair.link_templates:
        css_associated_code = template["css_class"]
        new_template_ids[css_associated_code] = template['id']

    # Return a dictionary, if there's data, other wise return an empty dictionary.
    if len(new_template_ids.keys()) != 0:
        return new_template_ids
    else:
        return {}


'''AJO ADDITIONS'''


def defined_multiple_flair_assessor(flairtext):
    """A routine that evaluates a defined multiple flairtext and its statuses as a dictionary.
    It can make sense of the symbols that are associated with various states of a post."""

    final_language_codes = {}
    flairtext = flairtext.lower()

    languages_list = flairtext.split(", ")

    for language in languages_list:

        # Get just the language code.
        language_code = " ".join(re.findall("[a-zA-Z]+", language))

        if len(language_code) != len(language):  # There's a difference - maybe a symbol in DEFINED_MULTIPLE_LEGEND
            for symbol in DEFINED_MULTIPLE_LEGEND:
                if symbol in language:
                    final_language_codes[language_code] = DEFINED_MULTIPLE_LEGEND[symbol]
        else:  # No difference, must be untranslated.
            final_language_codes[language_code] = 'untranslated'

    return final_language_codes


def defined_multiple_flair_former(flairdict):
    """Takes a dictionary of defined multiple statuses and returns a string.
    To be used with the defined_multiple_flair_assessor() function above."""

    output_text = []

    for key, value in flairdict.items():  # Iterate over each item in the dictionary.

        try:  # Try to get the ISO 639-1 if possible
            language_code = ISO_639_1[ISO_639_3.index(key)]
        except ValueError:  # No ISO 639-1 code
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


def defined_multiple_comment_parser(pbody, language_names_list):
    """Takes a comment and a list of languages and looks for commands and language names.
    This allows for defined multiple posts to have separate statuses for each language.
    We don't keep English though.
    """

    detected_status = None

    status_keywords = {KEYWORDS[2]: "missing",
                       KEYWORDS[3]: "translated",
                       KEYWORDS[9]: "doublecheck",
                       KEYWORDS[14]: "inprogress"}

    # Look for language names.
    detected_languages = language_mention_search(pbody)

    # Remove English if detected.
    if detected_languages is not None and "English" in detected_languages:
        detected_languages.remove("English")

    if detected_languages is None or len(detected_languages) == 0:
        detected_languages = None

    if detected_languages is None:
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


def retrieve_script_code(script_name):
    """This function takes the name of a script, outputs its ISO 15925 Code and the name as a tuple if valid."""

    codes_list = []
    names_list = []

    csv_file = csv.reader(open(FILE_ADDRESS_ISO_ALL, "rt", encoding='utf-8'), delimiter=",")
    for row in csv_file:
        if len(row[0]) == 4:  # This is a script code. (the others are 3 characters. )
            codes_list.append(row[0])
            names_list.append(row[2:][0])  # It is normally returned as a list, so we need to convert into a string.

    if script_name in names_list:  # The name is in the code list
        item_index = names_list.index(script_name)
        item_code = codes_list[item_index]
        item_code = str(item_code)
        return item_code, script_name
    else:
        return None


'''AJO CODE'''


class Ajo:
    """A post on r/translator. Used as an object for the bot to work with for consistency with languages.

    The process is: Submission > Ajo (changes made to it) > Ajo.update()

    Attributes:

        id: A Reddit submission that forms the base of this class.
        created_utc: The Unix time that the item was created.
        author: The reddit username of the creator. [deleted] if not found.

        type: single, multiple

        country_code: The ISO 3166-2 code of a country associated with the language. None normally.
        language_name: The English name of the post's language, rendered as a string
                       (Note: Unknown, Nonlanguage, and Conlang posts count as a language_name)
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

        Example of an output for flair is German (Identified/Script) (Long)
    """

    # noinspection PyUnboundLocalVariable
    def __init__(self, reddit_submission):  # This takes a Reddit Submission object and generates info from it.

        if type(reddit_submission) is dict:  # Loaded from a file?
            logger.debug("[ZW] Ajo: Loaded Ajo from local database.")
            for key in reddit_submission:
                setattr(self, key, reddit_submission[key])
        else:  # This is loaded from reddit.
            logger.debug("[ZW] Ajo: Getting Ajo from Reddit.")
            self.id = reddit_submission.id  # The base Reddit submission ID.
            self.created_utc = int(reddit_submission.created_utc)

            # If there is no
            self.recorded_translators = []

            # try:
            title_data = title_format(reddit_submission.title)

            try:  # Check if user is deleted
                self.author = reddit_submission.author.name
            except AttributeError:
                # Comment author is deleted
                self.author = "[deleted]"

            if reddit_submission.link_flair_css_class in ["multiple", 'app']:
                self.type = "multiple"
            else:
                self.type = "single"

            # oflair_text is an internal variable used to mimic the linkflair text.
            if reddit_submission.link_flair_text is None:  # There is no linkflair text.
                oflair_text = "Generic"
                self.is_identified = self.is_long = self.is_script = self.is_bot_crosspost = self.is_supported = False
            else:
                if "(Long)" in reddit_submission.link_flair_text:
                    self.is_long = True
                    # oflair_text = reddit_submission.link_flair_text.split("(")[0].strip()
                else:
                    self.is_long = False

                if reddit_submission.link_flair_css_class == "unknown":  # Check to see if there is a script classified.
                    if "(Script)" in reddit_submission.link_flair_text:
                        self.is_script = True
                        self.script_name = oflair_text = reddit_submission.link_flair_text.split("(")[0].strip()
                        self.script_code = retrieve_script_code(self.script_name)[0]
                        self.is_identified = False
                    else:
                        self.is_script = False
                        self.is_identified = False
                        self.script_name = self.script_code = None
                        oflair_text = "Unknown"
                else:
                    if "(Identified)" in reddit_submission.link_flair_text:
                        self.is_identified = True
                        oflair_text = reddit_submission.link_flair_text.split("(")[0].strip()
                    else:
                        self.is_identified = False
                        if "(" in reddit_submission.link_flair_text:  # Contains (Long)
                            oflair_text = reddit_submission.link_flair_text.split("(")[0].strip()
                        else:
                            oflair_text = reddit_submission.link_flair_text

            if title_data is not None:
                self.direction = title_data[8]

                if len(title_data[0]) == 1:
                    # The source language data is converted into a list. If it's just one, let's make it a string.
                    self.original_source_language_name = title_data[0][0]  # Take the only item
                else:
                    self.original_source_language_name = title_data[0]
                if len(title_data[1]) == 1:
                    # The target language data is converted into a list. If it's just one, let's make it a string.
                    self.original_target_language_name = title_data[1][0]  # Take the only item
                else:
                    self.original_target_language_name = title_data[1]
                if len(title_data[4]) != 0:  # Were we able to determine a title?
                    self.title = title_data[4]
                    self.title_original = reddit_submission.title
                else:
                    self.title = self.title_original = reddit_submission.title

                if "{" in reddit_submission.title and "}" in reddit_submission.title:  # likely contains a country name
                    country_suffix_name = re.search(r"{(\D+)}", reddit_submission.title)
                    country_suffix_name = country_suffix_name.group(1)  # Get the Country name only
                    self.country_code = country_converter(country_suffix_name)[0]  # Get the code (e.g. CH for Swiss)
                elif title_data[7] is not None and len(title_data[7]) <= 6:  # We have an included code from the title rout
                    country_suffix = title_data[7].split("-", 1)[1]
                    self.country_code = country_suffix
                else:
                    self.country_code = None

            if self.type == "single":
                if "[" not in oflair_text:  # Does not have a language tag. e.g., [DE]

                    if "{" in oflair_text:  # Has a country tag in the flair, so let's take that out.
                        country_suffix_name = re.search(r"{(\D+)}", oflair_text)
                        country_suffix_name = country_suffix_name.group(1)  # Get the Country name only
                        self.country_code = country_converter(country_suffix_name)[0]
                        # Now we want to take out the country from the title.
                        title_first = oflair_text.split("{", 1)[0].strip()
                        title_second = oflair_text.split("}", 1)[1]
                        oflair_text = title_first + title_second

                    converter_data = converter(oflair_text)
                    self.language_history = []  # Create an empty list.

                    if reddit_submission.link_flair_css_class != "unknown":  # Regular thing
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

                    if len(converter_data[0]) == 2:
                        self.language_code_3 = ISO_639_3[ISO_639_1.index(converter_data[0])]  # Find the matching 639-1 code
                    else:
                        self.language_code_1 = None
                else:  # Does have a language tag.
                    language_tag = reddit_submission.link_flair_text.split("[")[1][:-1].lower()  # Get the characters
                    # print(language_tag)
                    if language_tag != "?" and language_tag != "--":  # Non-generic versions
                        converter_data = converter(language_tag)
                        self.language_name = converter_data[1]
                        self.is_supported = converter_data[2]
                        if len(language_tag) == 2:
                            self.language_code_1 = language_tag
                            self.language_code_3 = ISO_639_3[ISO_639_1.index(language_tag)]
                        elif len(language_tag) == 3:
                            self.language_code_1 = None
                            self.language_code_3 = language_tag
                    else:  # Either a tag for an unknown post or a generic one
                        if language_tag == "?":  # Unknown post that has still been processed.
                            self.language_name = "Unknown"
                            self.language_code_1 = None
                            self.language_code_3 = "unknown"
                            self.is_supported = True
                        elif language_tag == "--":  # Generic post
                            self.language_name = None
                            self.language_code_1 = None
                            self.language_code_3 = "generic"
                            self.is_supported = False
            elif self.type == "multiple":  # If it's a multiple type, let's put the language names etc as lists.
                self.is_supported = True
                self.language_history = []

                # Handle DEFINED MULTIPLE
                if "[" in reddit_submission.link_flair_text:  # There is a list of languages included in the flair
                    # Return their names from the code.
                    # test_list_string = "Multiple Languages [DE, FR]"
                    multiple_languages = []

                    actual_list = reddit_submission.link_flair_text.split("[")[1][:-1]  # Get just the codes
                    actual_list = actual_list.replace(" ", "")  # Take out the spaces in the tag.

                    # Code to replace the special status characters... Not fully sure how it interfaces with the rest
                    for character in DEFINED_MULTIPLE_LEGEND.keys():
                        if character in actual_list:
                            actual_list = actual_list.replace(character, "")

                    new_code_list = actual_list.split(",")  # Convert to a list

                    for code in new_code_list:  # We wanna convert them to list of names
                        code = code.lower()  # Convert to lowercase.
                        code = "".join(re.findall("[a-zA-Z]+", code))
                        multiple_languages.append(converter(code)[1])  # Append the names of the languages.
                else:
                    multiple_languages = title_data[6]  # Get the languages that this is for. Will be a list or None.

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
                            self.language_code_3.append(ISO_639_3[ISO_639_1.index(converter(language)[0])])
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
                    actual_list = reddit_submission.link_flair_text.split("[")[1][:-1]  # Get just the codes
                    self.status = defined_multiple_flair_assessor(actual_list)  # Pass it to the dictionary constructor
            else:
                self.status = "untranslated"

            try:
                original_post_id = reddit_submission.crosspost_parent  # Check to see if this is a bot crosspost.
                crossposter = reddit_submission.author.name
                if crossposter == "translator-BOT":
                    self.is_bot_crosspost = True
                    self.parent_crosspost = original_post_id[3:]
                else:
                    self.is_bot_crosspost = False
            except AttributeError:  # It's not a crosspost.
                self.is_bot_crosspost = False

    def __eq__(self, other):  # Two Ajos are the same if their dictionary contents match.
        return self.__dict__ == other.__dict__

    def set_status(self, new_status):  # Change the status of the Ajo. (translated, doublecheck, etc. )
        self.status = new_status

    def set_status_multiple(self, status_language_code, new_status):  # Change the status of a defined Multiple post
        if isinstance(self.status, dict):  # Make sure it's something we can actually update
            if self.status[status_language_code] != 'translated':  # Once something's marked as translated stay there.
                self.status[status_language_code] = new_status
        else:
            pass

    def set_long(self, new_long):  # Change the status of the Ajo as to whether it's long.
        self.is_long = new_long

    def set_country(self, new_country_code):  # Change the country code in the Ajo.

        if new_country_code is not None:
            new_country_code = new_country_code.upper()

        self.country_code = new_country_code

    def set_language(self, new_language_code, new_is_identified=False):
        # This changes the language of the Ajo and accepts a code as well as an identification boolean.
        old_language_name = str(self.language_name)

        if new_language_code not in ["multiple", "app"]:  # This is just a single type of languyage.
            self.type = "single"
            if len(new_language_code) == 2:
                self.language_name = converter(new_language_code)[1]
                self.language_code_1 = new_language_code
                self.language_code_3 = ISO_639_3[ISO_639_1.index(new_language_code)]
                self.is_supported = converter(new_language_code)[2]
            elif len(new_language_code) == 3 and new_language_code not in SUPPORTED_CODES:
                self.language_name = converter(new_language_code)[1]
                self.language_code_1 = None
                self.language_code_3 = new_language_code
                self.is_supported = False
            elif len(new_language_code) == 3 and new_language_code in SUPPORTED_CODES:
                # These are supported ISO 639-3 codes
                self.language_name = converter(new_language_code)[1]
                self.language_code_1 = None
                self.language_code_3 = new_language_code
                self.is_supported = True
            elif new_language_code == "unknown":  # Reset everything
                self.language_name = "Unknown"
                self.language_code_1 = self.is_script = self.script_code = self.script_name = None
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
                self.language_history.append(self.language_name)  # Add the new language name to the history.
        except (AttributeError, IndexError):  # There was no language_history defined... Let's create it.
            self.language_history = [old_language_name, self.language_name]

        if new_is_identified != self.is_identified:  # There's a change to the identification
            self.is_identified = new_is_identified  # Update with said change

    def set_script(self, new_script_code):
        # Change the script of the Ajo (has to be Unknown though), takes a four letter code
        # This will also now reset the flair to be Unknown.

        self.language_name = "Unknown"
        self.language_code_1 = None
        self.language_code_3 = "unknown"
        self.is_supported = True
        self.is_script = True
        self.script_code = new_script_code
        self.script_name = lang_code_search(new_script_code, True)[0]  # Get the name of the script

    def set_defined_multiple(self, new_language_codes):
        # This is a function that sets the language of an Ajo to a defined Multiple one.
        # Example: Multiple Languages [AR, KM, VI]
        self.type = 'multiple'
        old_language_name = str(self.language_name)

        # Divide into a list.
        set_languages_raw = new_language_codes.split('+')
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
            set_languages_processed_codes.append(code)
            self.language_name.append(name)
            self.status[code] = "untranslated"

        # Now we have code to generate a list of language codes ISO 639-1 and 3.
        for code in set_languages_processed_codes:
            if len(code) == 2:
                self.language_code_1.append(code)  # self
                code_3 = ISO_639_3[ISO_639_1.index(code)]
                self.language_code_3.append(code_3)
            elif len(code) == 3:
                self.language_code_3.append(code)
                self.language_code_1.append(None)

        try:
            # We do a check here to make sure we are not including the same thing twice.
            # This is to avoid something like ['Unknown', 'Chinese', 'Chinese']
            if self.language_history[-1] != self.language_name:
                self.language_history.append("Multiple Languages")  # Add the new language name to the history.
        except (AttributeError, IndexError):  # There was no language_history defined... Let's create it.
            self.language_history = [old_language_name, "Multiple Languages"]

    def add_translators(self, translator_name):  # A function to add who translated what to the Ajo (append to list).

        try:
            if translator_name not in self.recorded_translators:  # The username isn't already in it.
                self.recorded_translators.append(translator_name)  # Add the username of the translator to the Ajo.
                # print("Added translator name")
        except AttributeError:  # There were no translators defined in the Ajo... Let's create it.
            self.recorded_translators = [translator_name]

    def reset(self, original_title):
        # A function that will completely reset it to the original specifications. Not intended to be used often.
        self.language_name = title_format(original_title)[3]
        self.status = "untranslated"
        self.is_identified = False

        if title_format(original_title)[2] in ['multiple', 'app']:
            is_multiple = True
        else:
            is_multiple = False

        provisional_data = converter(self.language_name)  # This is a temporary code
        self.is_supported = provisional_data[2]
        provisional_code = provisional_data[0]
        provisional_country = provisional_data[3]

        if is_multiple is False:
            self.type = "single"
            if len(provisional_code) == 2:  # ISO 639-1 language
                self.language_code_1 = provisional_code
                self.language_code_3 = ISO_639_3[ISO_639_1.index(provisional_code)]
                self.country_code = provisional_country
            elif len(provisional_code) == 3 or provisional_code == "unknown" and provisional_code != "app":
                # ISO 639-3 language or Unknown post.
                self.language_code_1 = None
                self.language_code_3 = provisional_code
                self.country_code = provisional_country
                if provisional_code == 'unknown':  # Fill in the special parameters for Unknown posts.
                    self.is_script = False
                    self.script_code = None
                    self.script_name = None
            elif len(provisional_code) == 4:  # It's a script
                self.language_code_1 = None
                self.language_code_3 = "unknown"
                self.is_script = True
                self.script_code = provisional_code
                self.script_name = lang_code_search(provisional_code, True)[0]
        elif is_multiple is True:
            # Resetting multiples here.
            self.type = "multiple"
            if title_format(original_title)[2] == 'multiple':
                self.language_code_1 = "multiple"
                self.language_code_3 = "multiple"
            if title_format(original_title)[2] == 'app':
                self.language_code_1 = "app"
                self.language_code_3 = "app"

    # noinspection PyAttributeOutsideInit,PyAttributeOutsideInit
    def update_reddit(self):  # Sets the flair properly on Reddit properly. No arguments taken.

        # Get the original submission object.
        original_submission = reddit.submission(self.id)
        code_tag = "[--]"  # Default, this should be changed by the functions below.
        self.output_oflair_css = None  # Reset this
        self.output_oflair_text = None

        # Code here to determine the output data... CSS first.
        if self.type == "single":  # This includes checks to make sure the content are strings, not lists.
            if self.is_supported is True and self.language_name != "Unknown" and self.language_name != "Generic" and self.language_name is not None:
                if self.language_code_1 is not None and isinstance(self.language_code_1, str):
                    code_tag = "[{}]".format(self.language_code_1.upper())
                    self.output_oflair_css = self.language_code_1
                elif self.language_code_3 is not None and isinstance(self.language_code_3, str):
                    # Supported three letter code
                    code_tag = "[{}]".format(self.language_code_3.upper())
                    self.output_oflair_css = self.language_code_3
            elif self.is_supported is False and self.language_name != "Unknown" and self.language_name != "Generic" and self.language_name is not None:  # It's not a supported language
                if self.language_code_1 is not None and isinstance(self.language_code_1, str):
                    code_tag = "[{}]".format(self.language_code_1.upper())
                    self.output_oflair_css = "generic"
                elif self.language_code_3 is not None and isinstance(self.language_code_3, str):
                    code_tag = "[{}]".format(self.language_code_3.upper())
                    self.output_oflair_css = "generic"
            elif self.language_name == "Unknown":  # It's an Unknown post.
                code_tag = "[?]"
                self.output_oflair_css = "unknown"
            elif self.language_name is None or self.language_name == "Generic" or self.language_name == "":
                # There is no language flair defined.
                code_tag = "[--]"
                self.output_oflair_css = "generic"
        else:  # Multiple post.
            code_tag = []

            if self.language_code_3 == "multiple":  # This is a multiple for all languages
                self.output_oflair_css = "multiple"
                code_tag = None  # Blank code tag, don't need it.
            elif self.language_code_3 == "app":  # This is an app request for all languages
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
                    code_tag = defined_multiple_flair_former(self.status)
                    # print(code_tag)

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
                self.output_oflair_text = self.language_name  # The default flair text is just the language name.
                if self.country_code is not None:  # There is a country code.
                    self.output_oflair_text = "{} {{{}}}".format(self.output_oflair_text, self.country_code)
                    # add the country code in brackets after the language name. It will disappear if translated.
                if self.language_name != "Unknown":
                    if self.is_identified:
                        self.output_oflair_text = "{} (Identified)".format(self.output_oflair_text)
                    if self.is_long:
                        self.output_oflair_text = "{} (Long)".format(self.output_oflair_text)
                else:  # This is for Unknown posts
                    if self.is_script is True:
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
        # Check the global template dictionary
        # If we have the css in the keys as a proper flair, then we can mark it with the new template.
        if self.output_oflair_css in POST_TEMPLATES.keys():
            output_template = POST_TEMPLATES[self.output_oflair_css]
            original_submission.flair.select(output_template, self.output_oflair_text)


def ajo_writer(new_ajo):
    """Function takes an Ajo Object, saves it to a DB."""

    ajo_id = str(new_ajo.id)
    created_time = new_ajo.created_utc
    cursor_ajo.execute("SELECT * FROM local_database WHERE id = '{}'".format(ajo_id))
    stored_ajo = cursor_ajo.fetchone()
    # print("Ajo to STORE")
    # print(new_ajo.__dict__)
    if stored_ajo is not None:  # There's already a stored entry
        stored_ajo = eval(stored_ajo[2])  # We only want the stored dict here.
        if new_ajo.__dict__ != stored_ajo:  # The dictionary representations are not the same
            representation = str(new_ajo.__dict__)  # Convert the dict of the Ajo into a string.
            representation = (representation,)  # Convert into a tuple of length one for insertion.
            update_command = "UPDATE local_database SET ajo = (?) WHERE id = '{}'".format(ajo_id)
            cursor_ajo.execute(update_command, representation)
            conn_ajo.commit()
            # print("Data updated.")
        else:
            # print("Data exists, is same.")
            pass
    else:  # This is a new entry, not in my files.
        representation = str(new_ajo.__dict__)
        ajo_to_store = (ajo_id, created_time, representation)
        cursor_ajo.execute("INSERT INTO local_database VALUES (?, ?, ?)", ajo_to_store)
        conn_ajo.commit()
    logger.debug("[ZW] === Wrote Ajo to local database. ===\n|")


def ajo_loader(ajo_id):
    """Function takes an id string and returns an Ajo object from a local database that matches that string.
    Returns None if there is no stored Ajo."""

    # Checks the database
    cursor_ajo.execute("SELECT * FROM local_database WHERE id = '{}'".format(ajo_id))
    new_ajo = cursor_ajo.fetchone()

    if new_ajo is None:  # We couldn't find a stored dict for it.
        return None
    else:  # We do have stored data.
        new_ajo_dict = eval(new_ajo[2])  # We only want the stored dict here.
        new_ajo = Ajo(new_ajo_dict)
        return new_ajo  # Note: the Ajo class can build itself from this dict.


'''POINTS TABULATING SYSTEM'''


def ziwen_points_retreiver(username):
    """Fetches the total number of points earned by a user in the current month.
    This is used with the messages routine to tell people how many points they have earned."""

    month_points = 0
    all_points = 0
    recorded_months = []
    to_post = ""

    current_time = time.time()
    month_string = datetime.datetime.fromtimestamp(current_time).strftime('%Y-%m')

    sql_s = "SELECT * FROM total_points WHERE username = '{}' AND month_year = '{}'".format(username, month_string)
    cursor_p.execute(sql_s)
    username_month_points_data = cursor_p.fetchall()  # Returns a list of lists.

    sql_un = "SELECT * FROM total_points WHERE username = '{}'".format(username)
    cursor_p.execute(sql_un)
    username_all_points_data = cursor_p.fetchall()

    # print(username_all_points_data)

    for data in username_month_points_data:  # Compile the monthly number of points the user has earned.
        month_points += data[3]

    for data in username_all_points_data:  # Compile the total number of points the user has earned.
        all_points += data[3]

    for data in username_all_points_data:  # Compile the total number of months that have been recorded. .
        recorded_months.append(data[0])
        recorded_months = sorted(list(set(recorded_months)))

    if all_points != 0:  # The user has points listed.
        first_line = ("You've earned **{} points** on r/translator this month.\n\n"
                      "You've earned **{} points** in total.\n\n")
        to_post += first_line.format(month_points, all_points)
        to_post += "Year/Month | Points | Number of Posts Participated\n-----------|--------|------------------"
    else:  # User has no points listed.
        to_post = ("You haven't earned any points on r/translator yet. "
                   "You can earn points by helping identify or translate requests in our community!")
        return to_post

    for month in recorded_months:  # Generate rows of data from the points data.
        recorded_month_points = 0
        scratchpad_posts = []

        command = "SELECT * FROM total_points  WHERE username = '{}' AND month_year = '{}'".format(username, month)
        cursor_p.execute(command)
        month_data = cursor_p.fetchall()
        for data in month_data:
            recorded_month_points += data[3]
            scratchpad_posts.append(data[4])

        recorded_posts = len(list(set(scratchpad_posts)))

        to_post += "\n{} | {} | {}".format(month, recorded_month_points, recorded_posts)

    return to_post


def point_worth_determiner(language_name):
    """This function takes a language name and determines the points worth for a translation for it. (the cap is 20)"""

    if " " in language_name:  # Wiki links need underscores instead of spaces.
        language_name = language_name.replace(" ", "_")
    elif "-" in language_name:  # The wiki does not support hyphens in urls.
        language_name = language_name.replace("-", "_")

    if language_name == "Unknown":
        return 4  # The multiplier for Unknown can be hard coded.

    # Code to check the cache first to see if we have a value already.
    final_point_value = CACHED_MULTIPLIERS.get(language_name)  # Looks for the dictionary key of the language name.

    if final_point_value is not None:  # It's cached.
        # print("@@ We found a value in the cache.")
        return final_point_value  # Return the multipler - no need to go to the wiki.
    else:  # Not found in the cache. Get from the wiki.
        overall_page = reddit.subreddit(SUBREDDIT).wiki[language_name.lower()]  # Fetch the wikipage.
        try:  # First see if this page actually exists
            overall_page_content = str(overall_page.content_md)
            last_month_data = overall_page_content.split('\n')[-1]
        except prawcore.exceptions.NotFound:  # There is no such wikipage.
            logger.debug("[ZW] Points determiner: The wiki page does not exist.")
            last_month_data = "2017 | 08 | [Example Link] | 1%"
            # Feed it dummy data if there's nothing... this language probably hasn't been done in a while.
        try:  # Try to get the percentage from the page
            total_percent = str(last_month_data.split(' | ')[3])[:-1]
            total_percent = float(total_percent)
        except IndexError:  # There's a page but there is something wrong with data entered.
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
        logger.debug("[ZW] Points determiner: Multiplier for {} is {}".format(language_name, final_point_value))

        # Add to the cached values, so we don't have to do this next time.
        CACHED_MULTIPLIERS.update({language_name: final_point_value})

        # Write data to the cache so that it can be retrieved later.
        current_zeit = time.time()
        month_string = datetime.datetime.fromtimestamp(current_zeit).strftime('%Y-%m')
        insert_data = (month_string, language_name, final_point_value)
        cursor_multiplier.execute("INSERT INTO multiplier_cache VALUES (?, ?, ?)", insert_data)
        conn_multiplier.commit()

    return final_point_value


def point_worth_cacher():
    """Simple routine that caches the most frequently used languages' points worth in a local database."""

    # These are the most common languages on the subreddit. Also in our sidebar.
    check_languages = ["Arabic", "Chinese", "French", "German", "Hebrew", "Hindi", "Italian", "Japanese",
                       "Korean", "Latin", "Polish", "Portuguese", "Russian", "Spanish", "Thai", "Vietnamese"]

    # Code to check the database file to see if the values are current.
    # It will transform the database info into a dictionary.
    
    # Get the year-month string.
    current_zeit = time.time()
    month_string = datetime.datetime.fromtimestamp(current_zeit).strftime('%Y-%m')
    
    # Select from the database the current months data if it exists.
    multiplier_command = "SELECT * from multiplier_cache WHERE month_year = '{}'"
    multiplier_command = multiplier_command.format(month_string)
    
    cursor_multiplier.execute(multiplier_command)
    multiplier_entries = cursor_multiplier.fetchall()
    # If not current, fetch new data and save it.
    # print(multiplier_entries)

    if len(multiplier_entries) != 0:  # We actually have cached data for this month.

        # Populate the dictionary format from our data
        for entry in multiplier_entries:
            multiplier_name = entry[1]
            multiplier_worth = int(entry[2])
            CACHED_MULTIPLIERS[multiplier_name] = multiplier_worth
    else:  # We don't have cached data so we will retrieve it from the wiki.

        # Delete everything from the cache (clearing out previous months' data as well)
        command = 'DELETE FROM multiplier_cache'
        cursor_multiplier.execute(command)
        conn_multiplier.commit()

        # Get the data for the common languages
        for language in check_languages:
        
            # Fetch the number of points it's worth.
            point_worth_determiner(language)

            # Write the data to the cache.
            conn_multiplier.commit()


def ziwen_points_tabulator(oid, oauthor, oflair_text, oflair_css, comment):
    """Function to save the points, given a post submission's stuff and comment.
    This is intended to be able to assess the points at the point of the comment's writing.
    The function is different from other points systems where points are calculated much later.
    """

    current_time = time.time()
    month_string = datetime.datetime.fromtimestamp(current_time).strftime('%Y-%m')

    points_status = []

    if oflair_css in ["meta", "art"]:
        return

    try:  # Check if user is deleted
        pauthor = comment.author.name
    except AttributeError:
        # Comment author is deleted
        return

    if pauthor == 'AutoModerator' or pauthor == 'translator-BOT':
        return  # Ignore these bots

    # Load the Ajo from the database. We will check against it to see if it's None later.

    translator_to_add = None

    pbody = comment.body.lower().strip()

    if pauthor == oauthor and not any(keyword in pbody for keyword in THANKS_KEYWORDS) and len(
            pbody) < 20:  # and process_this == False: # The author's comment, but not a thank you.
        # print("+ An OP comment. Skipping...")
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
        if '[' in oflair_text:
            language_tag = '[' + oflair_text.split("[")[1]
            language_name = converter(language_tag.lower()[1:-1])[1]
        elif '{' in oflair_text:  # Contains a bracket. Spanish {Mexico} (Identified)
            language_name = oflair_text.split("{")[0].strip()
        elif '(' in oflair_text:  # Contains a parantheses. Spanish (Identified)
            language_name = oflair_text.split("(")[0].strip()
        else:
            language_name = oflair_text

    try:
        language_multiplier = point_worth_determiner(converter(language_name)[1])
        # How much is this language worth? Obtain it from our wiki.
    except prawcore.exceptions.Redirect:  # The wiki doesn't have this.
        language_multiplier = 20
    logger.debug("[ZW] Points tabulator: {}, {} multiplier".format(language_name, str(language_multiplier)))

    final_translator = ""  # This is in case the commenter is not actually the translator
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
            logger.debug("[ZW] Points tabulator: Actual translator: u/{} for {}".format(final_translator, parent_post))
            final_translator_points += 3  # Give them a flat amount of points.
        except AttributeError:  # Parent is a post. Skip.
            logger.debug("[ZW] Points tabulator: Parent of this comment is a post.")

    if len(pbody) > 13 and oauthor != pauthor and '!translated' in pbody or '!doublecheck' in pbody:
        # This is a real translation.
        if len(pbody) < 60 and '!translated' in pbody and any(keyword in pbody for keyword in VERIFYING_KEYWORDS):
            # This should be a verification command. Someone's agreeing that another is right.
            parent_comment = comment.parent()
            try:  # Check if it's a comment:
                parent_post = parent_comment.parent_id
                final_translator = parent_comment.author.name
                logger.debug("[ZW] Points tabulator: Actual translator: u/{} for {}".format(final_translator, parent_post))
                final_translator_points += 1 + (1 * language_multiplier)
                points += 1  # Give the cleaner-upper a point.
            except AttributeError:  # Parent is a post.
                logger.debug("[ZW] Points tabulator: Parent of this comment is a post.")
        else:
            logger.debug("[ZW] Points tabulator: Seems to be a solid !translated comment by u/{}.".format(pauthor))
            translator_to_add = pauthor
            points += 1 + (1 * language_multiplier)
    elif len(pbody) < 13 and '!translated' in pbody:
        # It's marking someone else's translation as translated. We want to get the parent.
        logger.debug("[ZW] Points tabulator: This is a cleanup !translated comment by u/{}.".format(pauthor))
        parent_comment = comment.parent()
        try:  # Check if it's a comment:
            parent_post = parent_comment.parent_id
            final_translator = parent_comment.author.name
            logger.debug("[ZW] Points tabulator: Actual translator: u/{} for {}".format(final_translator, parent_post))
            final_translator_points += 1 + (1 * language_multiplier)
            if final_translator != pauthor:  # Make sure it isn't someone just calling it on their own here
                points += 1  # We give the person who called the !translated comment a point for cleaning up
        except AttributeError:  # Parent is a post.
            logger.debug("[ZW] Points tabulator: Parent of this comment is a post.")
        points += 1  # Give the cleaner-upper a point.
    elif len(pbody) > 13 and '!translated' in pbody and pauthor == oauthor:
        # The OP marked it !translated, but with a longer comment.
        logger.debug("[ZW] Points tabulator: This is a marked !translated comment by the OP u/{} for someone else?.".format(pauthor))
        parent_comment = comment.parent()
        try:  # Check if it's a comment:
            parent_post = parent_comment.parent_id
            final_translator = parent_comment.author.name
            if final_translator != oauthor:
                logger.debug("[ZW] Points tabulator: Actual translator: u/{} for {}".format(final_translator, parent_post))
                final_translator_points += 1 + (1 * language_multiplier)
        except AttributeError:  # Parent is a post.
            logger.debug("[ZW] Points tabulator: Parent of this comment is a post.")

    if len(pbody) > 120 and pauthor != oauthor:  # This is an especially long comment...But it's well regarded
        points += 1 + int(round(.25 * language_multiplier))

    if '!identify' in pbody:
        points += 3

    if "`" in pbody:
        points += 2

    if '!missing' in pbody:
        points += 2

    if '!claim' in pbody:
        points += 1

    if '!page' in pbody:
        points += 1

    if '!search' in pbody:
        points += 1

    if '!reference' in pbody:
        points += 1

    if any(keyword in pbody for keyword in THANKS_KEYWORDS) and pauthor == oauthor and len(
            pbody) < 20:  # The OP thanked someone. Who?
        logger.debug("[ZW] Points tabulator: Found an OP short thank you.")
        parent_comment = comment.parent()
        try:  # Check if it's a comment:
            parent_post = parent_comment.parent_id
            final_translator = parent_comment.author.name  # This is the person OP thanked.
            logger.debug("[ZW] Points tabulator: Actual translator: u/{} for {}".format(final_translator, parent_post))
            # Code here to check in the database if the person already got points.
            final_translator_points += 1 + (1 * language_multiplier)
            cursor_p.execute("SELECT * FROM total_points WHERE username = '{}' AND oid = '{}'".format(final_translator,
                                                                                                      oid))
            obtained_points = cursor_p.fetchall()
            # [('2017-09', 'dn9u1g0', 'davayrino', 2, '71bfh4'), ('2017-09', 'dn9u1g0', 'davayrino', 21, '71bfh4')

            for record in obtained_points:  # Go through
                recorded_points = record[3]  # The points for this particular record.
                recorded_post_id = record[4]  # The Reddit ID of the post.

                if recorded_points == final_translator_points and recorded_post_id == oid:
                    # The person has gotten the exact same amount of points here. Reset.
                    final_translator_points = 0  # Reset the points if that's the case. Person has gotten it before.

        except AttributeError:  # Parent is a post.
            logger.debug("[ZW] Points tabulator: Parent of this comment is a post. Never mind.")

    if any(pauthor in s for s in points_status):  # Check if author is already listed in our list.
        for i in range(len(points_status)):  # Add their points if so.
            if points_status[i][0] == pauthor:  # Get their username
                points_status[i][1] += points  # Add the running total of points
    else:
        points_status.append([pauthor, points])  # They're not in the list. Just add them.

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

    # print(points_status)
    for entry in points_status:
        logger.debug("[ZW] Points tabulator: Saved: {}".format(entry))
        # Need code to NOT write it if the points are 0
        if entry[1] != 0:
            cursor_p.execute(
                "INSERT INTO total_points VALUES ('" + month_string + "', '" + pid + "', '" + entry[0] + "', '" + str(
                    entry[1]) + "', '" + oid + "')")
            conn_p.commit()

    return points_status


'''USER COMMANDS STATISTIC SAVING'''


def user_statistics_writer(body_text, username):
    """
    Function that records which commands are written by whom, cumulatively, and stores it into an SQLite file.
    Takes the body text of their comment as an input.
    The database used is the same one as the points one, but on a different table.
    """

    # Properly format things.
    recorded_keywords = list(KEYWORDS)
    for nonwanted in ['!translate', '!translator']:  # These commands are never used on our subreddit.
        recorded_keywords.remove(nonwanted)
    if recorded_keywords[4] in body_text:
        body_text = body_text.replace(recorded_keywords[4], recorded_keywords[10])

    # Let's try and load any saved record of this
    sql_us = "SELECT * FROM total_commands WHERE username = '{}'".format(username)
    cursor_p.execute(sql_us)
    username_commands_data = cursor_p.fetchall()

    if len(username_commands_data) == 0:  # Not saved, create a new one
        commands_dictionary = {}
        already_saved = False
    else:  # There's data already for this username.
        already_saved = True
        commands_dictionary = eval(username_commands_data[0][1])  # We only want the stored dict here.

    # Process through the text and record the commands used.
    for keyword in recorded_keywords:
        if keyword in body_text:

            if keyword is '`':  # Since these come in pairs, we have to divide this in half.
                keyword_count = int((body_text.count(keyword) / 2))
            else:  # Regular command
                keyword_count = body_text.count(keyword)

            try:
                commands_dictionary[keyword] += keyword_count
            except KeyError:
                commands_dictionary[keyword] = keyword_count

    # Save to the database if there's stuff.
    if len(commands_dictionary.keys()) != 0 and not already_saved:  # This is a new username.
        to_store = (username, str(commands_dictionary))
        cursor_p.execute("INSERT INTO total_commands VALUES (?, ?)", to_store)
        conn_p.commit()
    elif len(commands_dictionary.keys()) != 0 and already_saved:  # This username exists. Update instead.
        to_store = (str(commands_dictionary),)
        update_command = "UPDATE total_commands SET commands = (?) WHERE username = '{}'".format(username)
        cursor_p.execute(update_command, to_store)
        conn_p.commit()
    else:
        logger.debug("[ZW] user_statistics_writer: No commands to write.")
        pass

    return


def user_statistics_loader(username):
    """
    Function that pairs with user_statistics_writer. Takes a username and looks up what commands they have
    been recorded as using.
    If they have data, it will return a nicely formatted table.
    """

    lines_to_post = []
    header = "Command | Times \n--------|------\n"

    sql_us = "SELECT * FROM total_commands WHERE username = '{}'".format(username)
    cursor_p.execute(sql_us)
    username_commands_data = cursor_p.fetchall()

    if len(username_commands_data) == 0:  # There is no data for this user.
        return None
    else:  # There's data
        commands_dictionary = eval(username_commands_data[0][1])  # We only want the stored dict here.

        for key, value in sorted(commands_dictionary.items()):
            command_type = key
            if command_type == '`':
                command_type = '`lookup`'
            formatted_line = "{} | {}".format(command_type, value)
            lines_to_post.append(formatted_line)

        # Format everything together
        to_post = header + "\n".join(lines_to_post)
        return to_post


'''POST FILTERING & TESTING FUNCTIONS'''


def is_mod(user):
    """A function that can tell us if a user is a moderator of the operating subreddit or not."""

    moderators = []
    for moderator in r.moderator():  # Get list of subreddit mods from r/translator.
        moderators.append(moderator.name.lower())
    if user.lower() in moderators:  # Person is a mod.
        return True
    else:
        return False  # Person is not a mod.


def css_check(css_class):
    """
    Function that checks if a CSS class is something that a command can act on. Returns True if it's good.
    Generally speaking we do not work with these two classes. Returns False if it's in either of these classes.
    """

    if css_class in ["meta", "community"]:
        return False
    else:
        return True


'''ERROR-CHECKING FUNCTIONS'''


def last_post_comment():
    """A simple function to get the last post/comment on r/translator for reference storage when there's an error."""

    # Some default values just in case.
    nowutc = time.time()
    s_format_time = c_format_time = str(datetime.datetime.fromtimestamp(nowutc).strftime("%Y-%m-%d [%I:%M:%S %p]"))
    cbody = ""
    slink = ""
    cpermalink = ""

    for submission in r.new(limit=1):  # Get the last posted post in the subreddit.
        sutc = submission.created_utc
        slink = 'https://www.reddit.com{}'.format(submission.permalink)
        s_format_time = str(datetime.datetime.fromtimestamp(sutc).strftime("%a, %b %d, %Y [%I:%M:%S %p]"))
    for comment in r.comments(limit=1):  # Get the last posted comment
        cbody = "              > {}".format(comment.body)

        cutc = comment.created_utc
        cpermalink = "https://www.reddit.com" + comment.permalink
        c_format_time = str(datetime.datetime.fromtimestamp(cutc).strftime("%a, %b %d, %Y [%I:%M:%S %p]"))

    if "\n" in cbody:
        cbody = cbody.replace("\n", "\n              > ")  # Nicely format each line to fit with our format.
    to_post_template = "Last post     |   {}:    {}\nLast comment  |   {}:    {}\n"
    to_post = to_post_template.format(s_format_time, slink, c_format_time, cpermalink)  # Format the text for inclusion
    to_post += cbody + "\n"
    return to_post


def filter_log_writer(filtered_title, ocreated, filter_type):
    """Simple function to write the titles of removed posts to a text file."""

    f = open(FILE_ADDRESS_FILTER, 'a+', encoding='utf-8')  # File address for the filter log, cumulative.
    filter_line_template = '\n{} | {} | {}'
    timestamp_utc = str(datetime.datetime.fromtimestamp(ocreated).strftime("%Y-%m-%d"))
    filter_line = filter_line_template.format(timestamp_utc, filtered_title, filter_type)
    f.write(filter_line)
    f.close()


def error_log(error_save_entry):
    """A function to SAVE errors to a log for later examination.
    This is more advanced than the basic version kept in _config, as it includes data about last post/comment.
    """

    f = open(FILE_ADDRESS_ERROR, 'a+', encoding='utf-8')  # File address for the error log, cumulative.
    existing_log = f.read()  # Get the data that already exists

    # If this error entry doesn't exist yet, let's save it.
    if error_save_entry not in existing_log:
        error_date = strftime("%Y-%m-%d [%I:%M:%S %p]")
        last_post_text = last_post_comment()  # Get the last post and comment as a string

        try:
            log_template = "\n-----------------------------------\n{} ({} {})\n{}\n{}"
            log_template_txt = log_template.format(error_date, BOT_NAME, VERSION_NUMBER,
                                                   last_post_text, error_save_entry)
            f.write(log_template_txt)
        except UnicodeEncodeError:  # Occasionally this may fail on Windows thanks to its crap Unicode support.
            logger.error("[ZW] Error_Log: Encountered a Unicode writing error.")
        f.close()


def retrieve_error_log():
    """A simple routine to GET the last two errors and counters and include them in a ping reply.
    Returns a string.
    """

    # Error stuff. Open the file.
    with open(FILE_ADDRESS_ERROR, "r", encoding='utf-8') as f:
        error_logs = f.read()

    # Obtain the last two errors that were recorded.
    penultimate_error = error_logs.split('------------------------------')[-2]
    penultimate_error = penultimate_error.replace("\n", "\n    ")  # Add indenting of four spaces
    last_error = error_logs.split('------------------------------')[-1]
    last_error = last_error.replace("\n", "\n    ")  # Add indenting

    # Return the last two errors only.
    ping_error_output = penultimate_error + "\n\n" + last_error

    # Counter stuff.
    with open(FILE_ADDRESS_COUNTER, "r", encoding='utf-8') as f_c:
        counter_logs = f_c.read()

    # current_day = strftime("%a, %b %d, %Y")
    current_day = strftime("%Y-%m-%d")

    counter_header = "Date | Type | Count\n-----|------|------\n"
    if current_day in counter_logs:
        today_counter = counter_header + current_day + counter_logs.split(current_day, 1)[1]
    else:  # Data for today hasn't been recorded yet. Return nothing.
        today_counter = counter_header + ""

    # Return what has been recorded for today_counter
    logging_output = "{}\n\n{}".format(today_counter, ping_error_output)

    return logging_output


def save_wiki(odate, otitle, oid, oflair_text, s_or_i, oflair_new):
    """
    A function that saves information to one of two wiki pages on the r/translator subreddit.
    "Saved" is for languages that do not have an associated CSS class.
    "Identified" is for languages that were changed with an !identify command.

    :param odate: Date of the post
    :param otitle: Title of the post
    :param oid: ID of the post
    :param oflair_text: the flair text
    :param s_or_i: True for saved, False for identified
    :param oflair_new: The new language category
    :return: Does not return anything.
    """

    oformat_date = datetime.datetime.fromtimestamp(int(odate)).strftime('%Y-%m-%d')

    if s_or_i:  # Means we should write to the 'saved' page:
        page_content = reddit.subreddit(SUBREDDIT).wiki["saved"]
        new_content = ("{} | [{}](https://redd.it/{}) | {}".format(oformat_date, otitle, oid, oflair_text))
        page_content_new = str(page_content.content_md) + '\n' + new_content
        # Adds this language entry to the 'saved page'
        page_content.edit(content=page_content_new, reason='Ziwen: updating the "Saved" page with a new link')
        logger.info("[ZW] Save_Wiki: Updated the 'saved' wiki page.")
    elif not s_or_i:  # Means we should write to the 'identified' page:
        page_content = reddit.subreddit(SUBREDDIT).wiki["identified"]
        new_content_template = "{} | [{}](https://redd.it/{}) | {} | {}"
        new_content = new_content_template.format(oformat_date, otitle, oid, oflair_text, oflair_new)
        # Log in the wiki for later reference
        page_content_new = str(page_content.content_md) + '\n' + new_content
        # Adds this month's entry to the data from the wikipage
        try:
            page_content.edit(content=page_content_new, reason='Ziwen: updating the "Identified" page with a new link')
        except prawcore.exceptions.TooLarge:  # The wikipage is too large.
            page_name = 'identified'
            message_subject = "[Notification] '{}' Wiki Page Full".format(page_name)
            message_template = MSG_WIKIPAGE_FULL.format(page_name)
            logger.warning("[ZW] Save_Wiki: The '{}' wiki page is full.".format(page_name))
            reddit.subreddit('translatorBOT').message(message_subject, message_template)
        logger.info("[ZW] Save_Wiki: Updated the 'identified' wiki page.")


def database_processed_cleaner():
    """Function that cleans up the database of processed comments and posts."""

    pruning_command = 'DELETE FROM oldcomments WHERE id NOT IN (SELECT id FROM oldcomments ORDER BY id DESC LIMIT ?)'
    cur.execute(pruning_command, [MAXPOSTS * 10])
    sql.commit()


'''MESSAGING FUNCTIONS'''


def months_elapsed():
    """Simple function that tells us how many months of statistics we should have
    This is used for assessing the average number of posts are for a given language and can be expected for notificatio
    """

    month_beginning = 24198  # This is the May 2016 month, when the redesign was implemented. No archive data before.
    current_toki = time.time()

    month_int = int(datetime.datetime.fromtimestamp(current_toki).strftime('%m'))  # EG 05
    year_int = int(datetime.datetime.fromtimestamp(current_toki).strftime('%Y'))  # EG 2017

    total_current_months = (year_int * 12) + month_int
    months_num = total_current_months - month_beginning

    return months_num


def language_frequency_wiki(language_name):
    """Function to check how many messages a person can expect for a subscription request."""

    lang_wiki_name = language_name.lower()  # This is the language wiki page
    lang_wiki_name = lang_wiki_name.replace(" ", "_")

    reply_str = ("For your reference, our [statistics](https://www.reddit.com/r/translator/wiki/{})"
                 " indicate that approximately **{} requests are made per {}** for {}.")

    lang_name_original = language_name
    per_month_lines_edit = []
    total_posts = []

    if " " in language_name:  # Wiki links need underscores instead of spaces.
        language_name = language_name.replace(" ", "_")

    overall_page = reddit.subreddit(SUBREDDIT).wiki[language_name.lower()]  # Fetch the wikipage.
    try:
        overall_page_content = str(overall_page.content_md)
    except (prawcore.exceptions.NotFound, prawcore.exceptions.BadRequest):  # There is no page for this language
        return None  # Exit with nothing.
    except prawcore.exceptions.Redirect:  # Tends to happen with "community" requests
        return None  # Exit with nothing.

    per_month_lines = overall_page_content.split("\n")  # Separate into lines.

    for line in per_month_lines[5:]:  # We omit the header of the page.
        work_line = line.split("(", 1)[0]  # We only want the first part, with month|year|total
        # Strip the formatting.
        work_line = work_line.replace("[", "")
        work_line = work_line.replace("]", "")
        work_line = work_line.replace(" ", "")
        per_month_lines_edit.append(work_line)

    for line in per_month_lines_edit:
        year_exist = re.search('^\d{4}', line)  # Test for the presence of a year
        if year_exist is not None:  # Just in case we have a header or blank line in this, let's strip it. Take only months.
            month_posts = int(line.split("|")[2])  # We take the number of posts here.
            total_posts.append(month_posts)  # add it to the list of post counts.
        else:
            per_month_lines_edit.remove(line)  # Take out this line that has no data

    months_with_data = len(per_month_lines_edit)  # The number of months we have data for the language.
    months_since = months_elapsed()  # Get the number of months since we started statistic keeping

    if months_with_data == months_since:  # We have data for every single month for the language.
        total_rate_posts = sum(total_posts[-6:])  # Add only the data for the last 6 months.
        months_calculate = 6  # Change the time frame to 6 months
        # We want to take only the last 6 months.
    else:
        total_rate_posts = sum(total_posts)
        months_calculate = months_since

    monthly_rate = round((total_rate_posts / months_calculate), 2)  # The average number of posts per month
    daily_rate = round((monthly_rate / 30), 2)  # The average number of posts per day
    yearly_rate = round((monthly_rate * 12), 2)  # The average number of posts per day

    # We add up the cumulative number of posts.
    total_posts = sum(total_posts)

    # A tuple that can be used by other programs.
    stats_package = (daily_rate, monthly_rate, yearly_rate, total_posts)

    # Here we try to determine the comment we should return as a string.

    if daily_rate >= 2:  # This is a pretty popular one, with a few requests a day.
        freq_string = reply_str.format(lang_wiki_name, str(daily_rate), "day", lang_name_original)
        return freq_string, stats_package
    elif 2 > daily_rate > 0.05:  # This is a frequent one, a few requests a month. But not the most.
        freq_string = reply_str.format(lang_wiki_name, str(monthly_rate), "month", lang_name_original)
        return freq_string, stats_package
    else:  # These are pretty infrequent languages. Maybe a few times a year at most.
        freq_string = reply_str.format(lang_wiki_name, str(yearly_rate), "year", lang_name_original)
        return freq_string, stats_package


# noinspection PyUnusedLocal
def is_valid_user(username):
    """Simple function that tests if a Redditor is valid. Will return False if non-existent or shadowbanned."""

    exists = True
    try:
        user = reddit.redditor(username).fullname
    except prawcore.exceptions.NotFound:
        exists = False
    return exists


def notify_list_pruner(username):
    """Function that removes deleted users from the notifications database.
    It performs a test, and if they don't exist, it will delete their entries from the SQLite database.
    """

    if is_valid_user(username):  # This user does exist
        return None
    else:  # User does not exist.
        final_codes = []

        # Fetch a list of what this user WAS subscribed to. (For the final error message)
        sql_cn = "SELECT * FROM notify_users WHERE username = '{}'".format(username)

        # We try to retrieve the languages the user is subscribed to.
        cursor.execute(sql_cn)
        all_subscriptions = cursor.fetchall()

        for subscription in all_subscriptions:
            final_codes.append(subscription[0])  # We only want the language codes (don't need the username).
        to_post = ", ".join(final_codes)  # Gather a list of the languages user WAS subscribed to

        sql_command = "DELETE FROM notify_users WHERE username = '{}'".format(username)
        cursor.execute(sql_command)
        conn.commit()
        logger.info("[ZW] Notify_List_Pruner: Deleted subscription information for u/{}.".format(username))

        return to_post  # Return the list of formerly subscribed languages


def translated_message(oauthor, opermalink):
    """Function to message requesters (OPs) that their post has been translated.
    This function does not return anything.
    """

    if oauthor != "translator-BOT":  # I don't want to message myself.
        translated_subject = '[Notification] Your request has been translated on r/translator!'
        translated_body = MSG_TRANSLATED.format(oauthor=oauthor, opermalink=opermalink) + BOT_DISCLAIMER
        reddit.redditor(oauthor).message(translated_subject, translated_body)

    logger.info("[ZW] Translated_Message: >> Messaged the OP u/" + oauthor + " about their translated post.")

    return


def regional_language_fetcher(targeted_language):
    """ Takes a code like "ar-LB" or ISO 639-3, fetches users for their equivalents too.
    Returns a list of usernames that match both criteria. This will also remove people who are on the broader list.
    This should also be able to work with unknown-specific notifications.
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

    sql_lc = "SELECT * FROM notify_users WHERE language_code = '{}'".format(targeted_language)
    cursor.execute(sql_lc)
    notify_targets = cursor.fetchall()

    if relevant_iso_code is not None:  # There is an equvalent code. Let's get the users from that too.
        sql_lc = "SELECT * FROM notify_users WHERE language_code = '{}'".format(relevant_iso_code)
        cursor.execute(sql_lc)
        notify_targets += cursor.fetchall()

    for target in notify_targets:
        username = target[1]  # Get the username.
        final_specific_usernames.append(username)

    final_specific_usernames = list(set(final_specific_usernames))  # Dedupe the final list.

    # Now we need to find the overall list's user names for the broader langauge (e.g. ar)
    broader_code = targeted_language.split("-")[0]  # Take only the language part (ar).
    sql_lc = "SELECT * FROM notify_users WHERE language_code = '{}'".format(broader_code)
    cursor.execute(sql_lc)
    all_notify_targets = cursor.fetchall()

    for target in all_notify_targets:
        all_broader_usernames.append(target[1])  # This creates a list of all the people signed up for the original.

    # print(final_specific_usernames)
    # print(all_broader_usernames)

    final_specific_determined = set(final_specific_usernames) - set(all_broader_usernames)
    final_specific_determined = list(final_specific_determined)

    return final_specific_determined


def notification_entry_checker(language_code, username):
    """Function that checks to see if there is a duplicate in the notifications database
    Returns TRUE if entry pair is in there, FALSE if not.
    """

    sql_nc = "SELECT * FROM notify_users WHERE language_code = '{}' and username = '{}'"
    sql_nc = sql_nc.format(language_code, username)
    cursor.execute(sql_nc)
    specific_entries = cursor.fetchall()
    # print(specific_entries)

    if len(specific_entries) > 0:  # There already is an entry.
        return True
    else:  # No entry.
        return False


def title_cleaner(otitle):
    """Simple function to replace problematic Markdown characters
    These characters can interfere with the display of Markdown links in notifications.
    """

    # Characters to prefix a backslash to.
    specific_characters = ['[', ']']

    for character in specific_characters:
        if character in otitle:
            otitle = otitle.replace(character, "\{}".format(character))

    return otitle


def notifier_history_checker(thing_to_send, majo_history):
    """Function checks against the language history of an ajo.
    This is to prevent people from getting more than one notification for the same post.
    """

    # Get the language name.
    language_name = converter(thing_to_send)[1]

    # We allow it to send if it's the last (and only) item in this history.
    if language_name in majo_history and language_name != majo_history[-1]:
        action = False
    else:
        action = True

    return action


def ziwen_notifier_most_recent():
    """ A function that grabs the usernames of people who have submitted to r/translator in the last 24 hours.
    Another function can check against this to make sure people aren't submitting too many.
    """

    most_recent = []
    current_vaqt = int(time.time())
    current_vaqt_day_ago = current_vaqt - 86400

    # 100 should be sufficient for the last day.
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

        # If the time of the post is after our limit, note it down.
        if ocreated > current_vaqt_day_ago:
            if oauthor != "translator-BOT":
                most_recent.append(oauthor)

    # Return the list
    return most_recent


def ziwen_notifier_over_frequency_checker(username):
    """ This function checks the username against a list of OPs from the last 24 hours.
    If the OP has posted more than the limit it will return True
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


def ziwen_notifier_limit_writer(username):
    """
    A function to record how many notifications a user has received. (e.g. kungming2, 12)
    Iterates by one each time it's called.
    The database should be cleared out monthly by a separate function.
    """

    # Fetch the data
    sql_lw = "SELECT * FROM notify_monthly_limit WHERE username = '{}'".format(username)
    cursor.execute(sql_lw)
    user_data = cursor.fetchall()

    # Parse it
    if len(user_data) == 0:  # No record
        num_notifications = 0
    else:  # There's data already for this username.
        num_notifications = user_data[0][1]  # Take the second part of the tuple in a list.

    current_notifications = num_notifications + 1

    # Write the changes to the database.
    if num_notifications == 0:  # Create a new record
        to_store = (username, current_notifications)
        cursor.execute("INSERT INTO notify_monthly_limit VALUES (?, ?)", to_store)
    else:  # Update an existing one.
        to_store = (current_notifications,)
        update_command = "UPDATE notify_monthly_limit SET received = (?) WHERE username = '{}'".format(username)
        cursor.execute(update_command, to_store)

    conn.commit()
    return


def ziwen_notifier_limit_over_checker(username, monthly_limit):
    """ Function that takes a username and checks if they're above the monthly limit.
    True if they're over the limit, False otherwise.
    """

    # Fetch the data
    sql_lw = "SELECT * FROM notify_monthly_limit WHERE username = '{}'".format(username)
    cursor.execute(sql_lw)
    user_data = cursor.fetchall()

    if len(user_data) == 0:  # No record, so it's okay to send.
        return False
    else:  # There's data already for this username.
        num_notifications = user_data[0][1]  # Take the second part of the tuple in a list.
        if num_notifications > monthly_limit:  # Over the limit
            return True
        else:
            return False


def ziwen_notifier_equalizer(notify_users_list, language_name, monthly_limit):
    """Function that equalizes out notifications for popular languages so that people can get fewer.
    No more than the monthly_limit on average.
    users_to_contact = (users_number * monthly_limit) / monthly_number_notifications
    This is primarily intended for languages which get a lot of monthly requests.
    """

    if notify_users_list is not None:
        users_number = len(notify_users_list)
    else:
        users_number = None

    if users_number is None:  # If there's no one signed up for, just return an empty list
        return []

    # Get the number of requests on average per month for a language
    try:
        if language_name == "Unknown":  # Hardcode Unknown frequency
            monthly_number_notifications = 240
        else:
            monthly_number_notifications = language_frequency_wiki(language_name)[1][1]
    except TypeError:  # If there are no statistics for this language, just set it to low.
        monthly_number_notifications = 1

    # Get the number of users we're going to randomly pick for this language
    users_to_contact = round(((users_number * monthly_limit) / monthly_number_notifications), 0)
    users_to_contact = int(users_to_contact)

    # There are more users to contact than the recommended amount. Randomize.
    if users_to_contact < users_number:
        notify_users_list = random.sample(notify_users_list, users_to_contact)

    # If there are more than fifty for a language...  Cut it down.
    if users_number > 50:
        notify_users_list = random.sample(notify_users_list, 50)  # Pick fifty people at random. Cut the list down.
        logger.info("[ZW] Notifier Equalizer: Over fifty people listed for {} notifications. Randomized.".format(language_name))

    # Alphabetize
    notify_users_list = sorted(notify_users_list, key=str.lower)

    return notify_users_list
    

def ziwen_notifier(suggested_css_text, otitle, opermalink, oauthor, is_wl):
    """This notifies people about posts they're subscribed to.
    is_wl is a boolean for whether it's a wronglanguage (now !identify) command.
    """

    notify_users_list = []
    post_type = "translation request"

    # Load the language_history from the Ajo for this.
    # Exception for dashed stuff for now and meta and community and multiple ones. (defined multiples will just go thru)
    if suggested_css_text not in ['Community', 'Meta', 'Multiple Languages', 'App'] and "-" not in suggested_css_text:

        # Load the Ajo to check against its history.
        mid = re.search('comments/(.*)/\w', opermalink).group(1)  # Get just the Reddit ID.
        majo = ajo_loader(mid)  # Load the Ajo

        # Checking...
        try:
            language_history = majo.language_history  # Load the history of languages this post has been in
            permission_to_proceed = notifier_history_checker(suggested_css_text, language_history)
        except AttributeError:
            permission_to_proceed = True

        # If it's detected that we may have sent notifications for this already, just end it with no new notifications.
        if permission_to_proceed is False:
            return

    # First we need to do a test to see if it's a specific code or not.
    if "-" not in suggested_css_text:  # This is a regular notification.
        language_code = converter(suggested_css_text)[0]
        language_name = converter(suggested_css_text)[1]
        if suggested_css_text == "Multiple Languages":  # Debug fix for the multiple ones.
            language_code = "multiple"
            language_name = "Multiple Languages"
        elif suggested_css_text in ["meta", "community"]:  # Debug fix for the meta & community ones.
            language_code = suggested_css_text
            language_name = suggested_css_text.title()
            post_type = "post"  # Since these are technically not language requests
    else:  # This is a specific code, we want to add the people only signed up for them.
        # Note, this only gets people who are specifically signed up for them, not
        language_code = suggested_css_text.split("-", 1)[0]  # We get the broader category here. (ar, unknown)
        language_name = converter(suggested_css_text)[1]
        if language_code == "unknown":  # Add a new script phrase
            language_name += " (script)"  # This is to distinguish script notifications
        regional_data = regional_language_fetcher(suggested_css_text)
        if len(regional_data) != 0:
            # print("Going to specific times here")
            notify_users_list += regional_data  # add the additional people to the notifications list.
            # print(notify_users_list)

    sql_lc = "SELECT * FROM notify_users WHERE language_code = '{}'".format(language_code)
    cursor.execute(sql_lc)
    notify_targets = cursor.fetchall()

    if len(notify_targets) == 0 and len(notify_users_list) == 0:  # If there's no one on the list, just continue
        return

    for target in notify_targets:  # This is a list of tuples.
        username = target[1]  # Get the user name, as the language is [0] (ar, kungming2)
        notify_users_list.append(username)

    notify_users_list = list(set(notify_users_list))  # eliminate duplicates

    # Code here to equalize data (see function above)
    notify_users_list = ziwen_notifier_equalizer(notify_users_list, language_name, NOTIFICATIONS_LIMIT)

    action_counter(len(notify_users_list), "Notifications")  # Write to the counter log how many we send
    otitle = title_cleaner(otitle)  # Clean up the title, prevent Markdown errors with square brackets

    for username in notify_users_list:
        if not is_wl:  # This is just the regular notification
            message = MSG_NOTIFY.format(username=username, language_name=language_name, post_type=post_type,
                                        otitle=otitle, opermalink=opermalink, oauthor=oauthor)
        else:  # This is from an !identify command.
            message = MSG_NOTIFY_IDENTIFY.format(username=username, language_name=language_name, post_type=post_type,
                                                 otitle=otitle, opermalink=opermalink, oauthor=oauthor)
        try:
            message_subject = '[Notification] New {} post on r/translator'.format(language_name)
            reddit.redditor(username).message(message_subject, message + BOT_DISCLAIMER + MSG_UNSUBSCRIBE_BUTTON)
            ziwen_notifier_limit_writer(username)  # Record that they have been messaged
        except praw.exceptions.APIException:  # If the user deleted their account...
            logger.info("[ZW] Notifier: An error occured while sending a message to u/{}. Removing...".format(username))
            notify_list_pruner(username)  # Remove the username from our database.

    logger.info("[ZW] Notifier: Sent notifications to {} users signed up for {}.".format(str(len(notify_users_list)),
                                                                                         language_name))


def ziwen_messages():
    """
    A system to process commands via the messaging system of Reddit.
    This system acts upon keywords included in the message's status.
    """

    messages = []
    messages += list(reddit.inbox.unread(limit=5))  # Fetch just the last five unread messages.

    for message in messages:
        mauthor = str(message.author)
        msubject = message.subject.lower()  # Convert to lowercase
        mbody = message.body

        if "subscribe" in msubject and "un" not in msubject:  # User wants to subscribe
            language_matches = mbody.rpartition(':')[-1].strip()
            # Here we process the actual message body, returns a string

            if "+" in language_matches:
                language_matches = language_matches.replace("+", " ")
            # Replace pluses in case the web browser / client leaves them in.

            if "," in language_matches:  # This is the regular syntax, comma split
                language_matches = language_matches.split(",")  # Turn it into a list
            elif "\n" in language_matches:  # This is for line breaks
                language_matches = language_matches.split("\n")  # Turn it into a list
            elif "/" in language_matches:  # This is for slashes.
                language_matches = language_matches.split("/")  # Turn it into a list
            else:  # This is for spaces.
                language_matches = language_matches.split(" ")  # Turn it into a list
            language_matches = [x.strip(' ') for x in language_matches]  # Remove extra spaces
            language_matches = [x for x in language_matches if x]  # Remove empty strings. This is now a list.

            final_match_codes = []  # This is the final determination of language codes for the database
            final_match_names = []
            for match in language_matches:
                converted_result = converter(match)  # This will return a tuple.
                if converted_result[3] is None and len(converted_result[0]) != 4:
                    # There is no country specific code and this is not a script.
                    match_code = converted_result[0]  # Should get the code from each
                elif len(converted_result[0]) == 4:  # This is a script
                    match_code = "unknown-{}".format(converted_result[0])  # This is the format for the database
                else:  # This is a language-COUNTRY combo
                    match_code = "{}-{}".format(converted_result[0], converted_result[3])  # language-Country

                if "multiple" in match.lower():
                    match_code = "multiple"
                    match_name = "Multiple Languages"
                elif 'meta' in match.lower():
                    match_code = "meta"
                    match_name = 'Meta'
                elif 'community' in match.lower():
                    match_code = "community"
                    match_name = 'Community'
                else:
                    match_name = converted_result[1]
                    if "unknown-" in match_code:
                        match_name += " (script)"  # This is to disambiguate Arabic from Arabic script, for example
                final_match_codes.append(match_code)
                final_match_names.append(match_name)
            logger.info("[ZW] Messages: New subscription request from u/{}.".format(mauthor))
            final_match_codes = list(filter(None, final_match_codes))  # Delete blank ones just in case.
            final_match_codes = [x for x in final_match_codes if x != 'en']
            # Remove English... We don't need to write that to the DB
            final_match_codes = list(set(final_match_codes))
            # remove duplicates for codes only, we keep the names so they don't get confused
            final_match_names = [x for x in final_match_names if x]
            # Remove any blank/unrecognized languages from the final list.

            if len(final_match_codes) == 0:
                
                no_process_msg = "Sorry, but I couldn't process the [language/language codes]"
                no_process_msg += "(https://www.reddit.com/r/translatorBOT/wiki/ziwen#wiki_language_codes.2Fnames_syntax) in your message. "
                no_process_msg += "Please double-check your message to make sure they're accurate and "
                no_process_msg += "[try again]({})."
            
                message.reply(no_process_msg.format(MSG_SUBSCRIBE_LINK) + BOT_DISCLAIMER)
                logger.info("[ZW] Messages: Subscription languages listed are not valid.")
            else:
                for code in final_match_codes:
                    # Here's some code to check if user already exists
                    # True if it's already there, False, if not.
                    is_there = notification_entry_checker(code, mauthor)
                    if is_there is False:  # There isn't already an entry for it in there
                        cursor.execute("INSERT INTO notify_users VALUES ('" + code + "', '" + mauthor + "')")
                        conn.commit()
                        # Try to get a custom thank you.
                if converter(final_match_codes[0])[1] in THANKS_WORDS:  # Do we have a thank you word for this lang?
                    thanks_phrase = THANKS_WORDS.get(converter(final_match_codes[0])[1])  # If we do let's choose it.
                else:  # Couldn't find an equivalent thank you in another language. Just choose english
                    thanks_phrase = "Thank you"

                main_body = thanks_phrase + "! You have been subscribed to notifications for **" + ", ".join(
                    final_match_names) + "** on r/translator."

                try:
                    freq_phrase = language_frequency_wiki(converter(final_match_codes[0])[1])[0] + "\n\n"
                    # How often this gets msg
                except TypeError:  # There are no statistics for it. The thing will return NONE
                    freq_phrase = ""  # Don't put anything.
                except prawcore.exceptions.BadRequest:  # eh, weird code... probably has a dash
                    freq_phrase = ""  # Don't put anything.

                message_body = "{}\n\n{}To see all your subscribed notifications, please click the 'Status' link below."
                message_body = message_body.format(main_body, freq_phrase)
                message.reply(message_body + BOT_DISCLAIMER + MSG_UNSUBSCRIBE_BUTTON)
                logger.info("[ZW] Messages: Added notification subscriptions for u/" + mauthor + ".")
                action_counter(len(final_match_codes), "Subscriptions")
        elif "unsubscribe" in msubject:  # User wants to unsubscribe
            logger.info("[ZW] Messages: New unsubscription request from u/{}.".format(mauthor))
            language_matches = mbody.rpartition(':')[-1]  # Here we process the actual message body, returns a string
            if 'all' in language_matches.lower()[0:5]:  # User wants to unsubscribe from everything.
                '''
                final_match_codes = []
                # Let's add code to see which ones they were first subscribed to.
                sql_stat = "SELECT * FROM notify_users WHERE username = '{}'".format(mauthor)
                # We try to retrieve the languages the user is subscribed to.
                cursor.execute(sql_stat)
                all_subscriptions = cursor.fetchall()  # Returns a list of lists, with both the code and the username.
                for subscription in all_subscriptions:
                    final_match_codes.append(subscription[0])  # We only want the language codes (no need the username).
                '''
                sql_del = "DELETE FROM notify_users WHERE username = '{}'".format(mauthor)
                cursor.execute(sql_del)
                conn.commit()
                
                # Format the all unsubscribe message
                all_unsub_msg = "You have been completely unsubscribed from all notifications on r/translator. "
                all_unsub_msg += "To resubscribe, please [click here]({}).".format(MSG_SUBSCRIBE_LINK)
                
                message.reply(all_unsub_msg + BOT_DISCLAIMER)
            else:  # Should return a list of specific languages the person doesn't want.
                language_matches = language_matches.split(",")  # Turn it into a list
                language_matches = [x.strip(' ') for x in language_matches]  # Remove extra spaces
                final_match_codes = []  # This is the final determination of language codes for the database
                final_match_names = []
                for match in language_matches:
                    converted_result = converter(match)  # This will return a tuple.
                    if converted_result[3] is None and len(converted_result[0]) != 4:
                        # There is no country specific code and this is not a script.
                        match_code = converted_result[0]  # Should get the code from each
                    elif len(converted_result[0]) == 4:  # This is a script
                        match_code = "unknown-{}".format(converted_result[0])  # This is the format for the database
                    else:  # This is a language-COUNTRY combo
                        match_code = "{}-{}".format(converted_result[0], converted_result[3])  # language-Country
                    if "multiple" in match.lower():
                        match_code = "multiple"
                    match_name = converted_result[1]
                    final_match_codes.append(match_code)
                    final_match_names.append(match_name)
                final_match_codes = list(filter(None, final_match_codes))  # Delete blank ones
                if len(final_match_codes) == 0:
                    # Format the error reply message
                    no_process_msg = "Sorry, but I couldn't process the [language/language codes]"
                    no_process_msg += "(https://www.reddit.com/r/translatorBOT/wiki/ziwen#wiki_language_codes.2Fnames_syntax) in your message. "
                    no_process_msg += "Please double-check your message to make sure they're accurate and "
                    no_process_msg += "[try again]({})."
                    message.reply(no_process_msg.format(MSG_SUBSCRIBE_LINK) + BOT_DISCLAIMER)
                    logger.info("[ZW] Messages: Unsubscription languages listed are invalid. Replied w/ more information.")
                else:
                    for code in final_match_codes:
                        sql_del = "DELETE FROM notify_users WHERE language_code = '{}' and username = '{}'"
                        sql_del = sql_del.format(code, mauthor)
                        cursor.execute(sql_del)
                        conn.commit()

                    # Join the list into a string, and fix that the curly braces could cause issues
                    final_match_string = ", ".join(final_match_names)

                    # Format the reply message.
                    unsub_msg = "You have been unsubscribed from notifications for **" + final_match_string + "** "
                    unsub_msg += "on r/translator. To resubscribe, please [click here](" + MSG_SUBSCRIBE_LINK + ")."

                    message.reply(unsub_msg + BOT_DISCLAIMER + MSG_UNSUBSCRIBE_BUTTON)
                    logger.info("[ZW] Messages: Removed notification subscriptions for u/" + mauthor + ".")
                    action_counter(len(final_match_codes), "Unsubscriptions")
        elif "ping" in msubject:
            logger.info("[ZW] Messages: New status check from u/" + mauthor + ".")
            to_post = "Ziwen is running nominally.\n\n"
            if is_mod(mauthor):  # New status check from moderators
                to_post += retrieve_error_log()  # Get the last two recorded error entries
                if len(to_post) > 10000:  # If the PM is too long, shorten it.
                    to_post = to_post[0:9750]
            else:  # Ping from a regular user.
                pass
            message.reply(to_post + BOT_DISCLAIMER)
            logger.info("[ZW] Messages: Replied with status information.")
        elif "status" in msubject:
            logger.info("[ZW] Messages: New status request from u/" + mauthor + ".")
            final_match_codes = []
            final_match_names = []
            sql_stat = "SELECT * FROM notify_users WHERE username = '{}'".format(mauthor)

            # We try to retrieve the languages the user is subscribed to.
            cursor.execute(sql_stat)
            all_subscriptions = cursor.fetchall()  # Returns a list of lists, with both the language code & the username
            for subscription in all_subscriptions:
                final_match_codes.append(subscription[0])  # We only want the language codes (don't need the username).

            # User is not subscribed to anything.
            if len(final_match_codes) == 0:
                no_subscribe_msg = ("Sorry, you're not currently subscribed to notifications for any [language posts]"
                                    "(https://www.reddit.com/r/translatorBOT/wiki/ziwen#wiki_language_codes.2Fnames_syntax) on r/translator. "
                                    "Would you like to [sign up]({})?")
                status_component = no_subscribe_msg.format(MSG_SUBSCRIBE_LINK)
            else:
                for code in final_match_codes:  # Convert the codes into names
                    converted_result = converter(code)  # This will return a tuple.
                    match_name = converted_result[1]  # Should get the name from each
                    if code == 'meta':
                        match_name = 'Meta'
                    elif code == 'community':
                        match_name = 'Community'
                    elif "unknown-" in code:  # For scripts
                        match_name += " (script)"
                    final_match_names.append(match_name)
                # De-dupe and sort the returned languages.
                final_match_names = list(set(final_match_names))  # Remove duplicates
                final_match_names = sorted(final_match_names, key=str.lower)  # Alphabetize

                # Format the message to send to the requester.
                status_message = "You're subscribed to notifications on r/translator for:\n\n* {}"
                status_component = status_message.format("\n* ".join(final_match_names))

            # Get the commands the user may have used before.
            user_commands_statistics_data = user_statistics_loader(mauthor)
            if user_commands_statistics_data is not None:
                commands_component = "\n\n### User Commands Statistics\n\n" + user_commands_statistics_data
            else:
                commands_component = ""

            # Compile the components together
            compilation = "### Notifications\n\n" + status_component + commands_component

            action_counter(1, "Status checks")
            message.reply(compilation + BOT_DISCLAIMER + MSG_UNSUBSCRIBE_BUTTON)
        elif "add" in msubject and is_mod(mauthor) is True:  # Mod manually adding people
            logger.info("[ZW] Messages: New username addition message from moderator u/{}.".format(mauthor))
            username = mbody.split("USERNAME:", 1)[1]
            username = username.split("LANGUAGES", 1)[0].strip()  # Get the username (no u/)
            language_matches = mbody.rpartition('LANGUAGES:')[-1].strip()
            if "," in language_matches:  # This is the regular syntax, comma split
                language_matches = language_matches.split(", ")  # Turn it into a list
            else:  # there were no commas. 
                language_matches = [language_matches]
            
            final_match_codes = []
            
            for match in language_matches:  # Process their relevant codes
                converted_result = converter(match)  # This will return a tuple.
                match_code = converted_result[0]  # Get just the code
                final_match_codes.append(match_code)
            for code in final_match_codes:  # Actually add the codes into the database
                cursor.execute("INSERT INTO notify_users VALUES ('" + code + "', '" + username + "')")
                conn.commit()
        
            final_match_codes_print = ", ".join(final_match_codes)
            addition_message = "Added the language codes **{}** for u/{} into the notifications database."
            message.reply(addition_message.format(final_match_codes_print, username))
        elif "remove" in msubject and is_mod(mauthor) is True:  # Mod manually removing people (ability to do remotely)
            logger.info("[ZW] Messages: New username removal message from moderator u/{}.".format(mauthor))
            username = mbody.split("USERNAME:", 1)[1].strip()

            final_match_codes = []

            sql_stat = "SELECT * FROM notify_users WHERE username = '{}'".format(username)

            # We try to retrieve the languages the user is subscribed to.
            cursor.execute(sql_stat)
            all_subscriptions = cursor.fetchall()  # Returns a list of lists, with both the code and the username.
            for subscription in all_subscriptions:
                final_match_codes.append(subscription[0])  # We only want the language codes (no need the username).

            # Actually delete from database
            cursor.execute("DELETE FROM notify_users WHERE username = '{}'".format(username))
            conn.commit()

            # Send a message back to the moderator confirming this.
            final_match_codes_print = ", ".join(final_match_codes)
            removal_message = "Removed the subscriptions for u/{} from the notifications database. (**{}**)"
            message.reply(removal_message.format(username, final_match_codes_print))
        elif "points" in msubject:
            logger.info("[ZW] Messages: New points status request from u/{}.".format(mauthor))

            # Get the user's points
            user_points_output = "### Points on r/translator" + ziwen_points_retreiver(mauthor)

            # Get the commands the user may have used before.
            user_commands_statistics_data = user_statistics_loader(mauthor)
            if user_commands_statistics_data is not None:
                commands_component = "\n\n### Commands Statistics\n\n" + user_commands_statistics_data
            else:
                commands_component = ""

            message.reply(user_points_output + commands_component + BOT_DISCLAIMER)
            action_counter(1, "Points checks")

        message.mark_read()  # Mark the message as read.


def get_latest_verified_thread():
    """Function to quickly get the Reddit ID of the latest verification thread on startup.
    This way, the ID of the thread does not need to be hardcoded into Ziwen.
    """

    verification_id = ""

    # Search for the latest verification thread.
    search_term = "title:verified flair:meta"

    # Note that even in testing ('trntest') we will still search r/translator for the thread.
    search_results = reddit.subreddit('translator').search(search_term, time_filter='year', sort='new', limit=1)

    # Iterate over the results to get the ID.
    for post in search_results:
        verification_id = post.id

    return verification_id


def verification_parser():
    """Function to collect requests for verified flairs."""

    submission = reddit.submission(id=VERIFIED_POST_ID)
    submission.comments.replace_more(limit=None)
    s_comments = list(submission.comments)
    for comment in s_comments:
        cid = comment.id
        c_body = comment.body
        try:
            c_author = comment.author.name
            c_author_string = "u/" + c_author
        except AttributeError:
            # Author is deleted. We don't care about this post.
            continue
        cur.execute('SELECT * FROM oldcomments WHERE ID=?', [cid])
        if cur.fetchone():
            # Post is already in the database
            continue
        cur.execute('INSERT INTO oldcomments VALUES(?)', [cid])
        sql.commit()

        comment.save()  # Saves the comment on Reddit so we know not to use it. (bot will not process saved comments)

        ocreated = int(comment.created_utc)
        osave = comment.saved  # Should be True if processed, False otherwise. 
        current_time = int(time.time())

        if current_time - ocreated >= 300:  # Comment is old let's not do it.
            continue

        if osave is True:  # Comment has been processed already. 
            continue

        c_body = c_body.replace('\n', '|')
        c_body = c_body.replace('||', '|')
        # print(c_body)

        components = c_body.split('|')
        components = list(filter(None, components))
        # print(components)
        try:
            language_name = components[0].strip()
            url_1 = components[1].strip()
            url_2 = components[2].strip()
            url_3 = components[3].strip()
        except IndexError:  # There must be something wrong with the verification comment.
            return  # Exit, don't do anything. 
            
        try:
            notes = components[4]
        except IndexError:  # No notes were listed.
            notes = ""
        entry = "| {} | {} | [1]({}), [2]({}), [3]({}) | {} |"
        entry = entry.format(c_author_string, language_name, url_1, url_2, url_3, notes)
        page_content = reddit.subreddit(SUBREDDIT).wiki["verification_log"]
        page_content_new = str(page_content.content_md) + '\n' + entry
        page_content.edit(content=page_content_new,
                          reason='updating the verification log with a new request from u/' + c_author)
        comment.reply(COMMENT_VERIFICATION_RESPONSE.format(c_author) + BOT_DISCLAIMER)
        logger.info('[ZW] Updated the verification log with a new request from u/' + c_author)


def page_translators(language_code, language_name, pauthor, otitle, opermalink, oauthor, is_nsfw):
    """ A function (the original one!) to page up to three users for a post's language.
    True for paging, False for doublecheck (deprecated as of May 2017)
    Paging now uses the same notification service. The CSV is deprecated."""

    sql_lc = "SELECT * FROM notify_users WHERE language_code = '{}'".format(language_code)
    cursor.execute(sql_lc)
    page_targets = cursor.fetchall()

    page_users_list = []

    for target in page_targets:  # This is a list of tuples.
        username = target[1]  # Get the user name, as the language is [0] (ar, kungming2)
        page_users_list.append(username)  # Add the username to the list.

    page_users_list = list(set(page_users_list))  # Remove duplicates
    page_users_list = [x for x in page_users_list if x != pauthor]  # Remove the caller if on there
    if len(page_users_list) > 3:  # If there are more than three people...
        page_users_list = random.sample(page_users_list, 3)  # Randomly pick 3

    if len(page_users_list) == 0:  # There is no one on the list for it.
        return None  # Exit, return none
    else:
        for target_username in page_users_list:
            # if is_page:
            message = MSG_PAGE.format(username=target_username, pauthor=pauthor, language_name=language_name,
                                      otitle=otitle, opermalink=opermalink, oauthor=oauthor,
                                      removal_link=MSG_REMOVAL_LINK.format(language_name=language_code))
            subject_line = '[Page] Message from r/translator regarding a {} post'.format(language_name)
            # Add on a NSFW warning if appropriate.
            if is_nsfw:
                message += MSG_NSFW_WARNING

            # Send the actual message. Delete the username if an error is encountered.
            try:
                reddit.redditor(str(target_username)).message(subject_line, message + BOT_DISCLAIMER)
                logger.info('[ZW] Paging: Messaged u/{} for a {} post.'.format(target_username, language_name))
            except praw.exceptions.APIException:  # There was an error... User probably does not exist anymore.
                logger.debug("[ZW] Paging: An error occured while sending a message to u/{}. Removing...".format(target_username))
                notify_list_pruner(target_username)  # Remove the username from our database.
        return True


def page_multiple_detector(pbody):
    """Function that checks to see if there are multiple page commands in a comment.
    This will return False if there's 0 or 1 !page results.
    Will return True if there's more than 1."""

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


'''CHARACTER/WORD LOOKUP FUNCTIONS'''


def ctext_search(character):
    """A simple seal script search from CTEXT that returns an image URL."""

    ctext_url = str("http://ctext.org/dictionary.pl?if=en&char=" + character)
    ctext_page = requests.get(ctext_url, headers=ZW_USERAGENT)
    tree = html.fromstring(ctext_page.content)  # now contains the whole HTML page
    seal_image = None
    images = tree.xpath("//img/@src")
    for image in images:
        if 'seal' in image:
            seal_image = "http://ctext.org/" + image
            return seal_image
    if seal_image is None:
        return None


def oc_search(character):
    """A simple routine that retrieves data from a CSV of Baxter-Sagart's reconstruction of Old Chinese"""

    # Main dictionary for readings
    mc_oc_readings = {}

    # Iterate over the CSV
    csv_file = csv.reader(open(FILE_ADDRESS_OLD_CHINESE, "rt", encoding="utf-8"), delimiter=",")
    for row in csv_file:
        my_character = row[0]

        mc_reading = (row[2:][0])  # It is normally returned as a list, so we need to convert into a string.
        oc_reading = (row[4:][0])
        if "(" in oc_reading:
            oc_reading = oc_reading.split('(', 1)[0]

        # Add the character as a key with the readings as a tuple
        mc_oc_readings[my_character] = (mc_reading.strip(), oc_reading.strip())

    # Check to see if I actually have the key in my dictionary.
    if character not in mc_oc_readings:  # Character not found.
        return None
    else:  # Character exists!
        character_data = mc_oc_readings[character]  # Get the tuple
        to_post = "\n**Middle Chinese** | \**{}*\n**Old Chinese** | \*{}*".format(character_data[0], character_data[1])
        return to_post


def zh_min_hak_pronunciation(character):
    """Function to get the Hokkien and Hakka (Sixian) pronunciations from the Taiwan MoE dictionary.
    This actually will accept either single-characters or multi-character words."""

    # Fetch Hokkien results
    min_page = requests.get("https://www.moedict.tw/'{}".format(character), headers=ZW_USERAGENT)
    min_tree = html.fromstring(min_page.content)  # now contains the whole HTML page

    # The annotation returns as a list, we want to take the first one.
    try:
        min_reading = min_tree.xpath('//ru[contains(@class,"rightangle") and contains(@order,"0")]/@annotation')[0]
        min_reading = "\n**Southern Min** | *{}*".format(min_reading)
    except IndexError:  # No character or word found.
        min_reading = ""

    # Fetch Hakka results (Sixian)
    hak_page = requests.get("https://www.moedict.tw/:{}".format(character), headers=ZW_USERAGENT)
    hak_tree = html.fromstring(hak_page.content)  # now contains the whole HTML page
    try:
        hak_reading = hak_tree.xpath('string(//span[contains(@data-reactid,"$0.6.2.1")])')

        if len(hak_reading) != 0:
            # Format the tones and words properly with superscript.
            hak_reading_new = []
            hak_reading = re.sub(r'(\d{1,4})([a-z])', r'\1 ', hak_reading)  # Add spaces between words.
            hak_reading = hak_reading.split(" ")
            for word in hak_reading:
                new_word = re.sub(r'([a-z])(\d)', r'\1^\2', word)
                hak_reading_new.append(new_word)
            hak_reading = " ".join(hak_reading_new)

            hak_reading = "\n**Hakka (Sixian)** | *{}*".format(hak_reading)
    except IndexError:  # No character or word found.
        hak_reading = ""

    # Combine them together.
    to_post = min_reading + hak_reading

    return to_post


def calligraphy_search(character):
    """A function to get an overall image of Chinese calligraphic search
    """

    character = simplify(character)

    # First get data from http://shufa.guoxuedashi.com (this will be included as a URL)
    unicode_assignment = hex(ord(character)).upper()[2:]  # Get the Unicode assignment (eg 738B)
    gx_url = 'http://shufa.guoxuedashi.com/{}/'.format(unicode_assignment)

    # Next get an image from Shufazidian
    formdata = {'sort': '7', 'wd': character}  # Form data to pass on to the POST system.
    try:
        rdata = requests.post("http://www.shufazidian.com/", data=formdata)
        tree = Bs(rdata.content, "lxml")
        tree = str(tree)
        tree = html.fromstring(tree)
    except requests.exceptions.ConnectionError:  # If there's a connection error, return None.
        return None

    images = tree.xpath("//img/@src")
    image_list = []
    complete_image = ""
    image_string = None

    if images is not None:
        for url in images:
            if len(url) < 20:  # We don't need short links.
                continue
            if "gif" in url:  # Or GIFs
                continue
            elif "http" not in url:
                url = "http://www.shufazidian.com/" + url
                image_list.append(url)
            else:
                image_list.append(url)

            if "shufa6" in url:  # We try to get the broader summation image
                fragment_1 = url.split('/1')[0]
                fragment_2 = url.split('/1')[1]
                complete_image = str(fragment_1 + fragment_2)

        if len(complete_image) != 0:
            logger.debug("[ZW] ZH-Calligraphy: There is a Chinese calligraphic image for " + character + ".")
            image_format = ("\n\n**Chinese Calligraphy Variants**: [{}]({}) (*[SFZD](http://www.shufazidian.com/)*, "
                            "*[GXDS]({})*)")
            image_string = image_format.format(character, complete_image, gx_url)
    else:
        image_string = None

    images = ctext_search(character)  # is there a seal script character we can get?
    if images is not None:
        seal_format = ("\n\n**Seal Script**: [{}]({}) (*[CTEXT](http://ctext.org/dictionary.pl?if=en&char={})*, "
                       "*[GXDS]({}5/)*)")
        seal_string = seal_format.format(character, images, character, gx_url)
    else:
        seal_string = ""

    if image_string is None:
        return None
    else:
        image_string += seal_string
        return image_string


def ja_calligraphy_search(character):  # Japanese calligraphic search
    try:
        eth_page = requests.get('http://www013.upp.so-net.ne.jp/santai/santai.htm', headers=ZW_USERAGENT)
        tree = html.fromstring(eth_page.content)  # now contains the whole HTML page
        page_url = tree.xpath('//a[contains(text(), "' + character + '")]/@href')
        page_url = "http://www013.upp.so-net.ne.jp/santai/" + str(page_url[0])

        if len(page_url) != 0:
            logger.debug("[ZW] JA-Calligraphy: There is a Japanese calligraphic image for " + character + ".")
            ja_calligraphy_format = "\n\n**Japanese Calligraphy Variants**: [{}]({}) "
            ja_calligraphy_format += "(*[Source](http://www013.upp.so-net.ne.jp/santai/santai.htm)*)"
            to_post = ja_calligraphy_format.format(character, page_url)
        else:
            return None
    except IndexError:  # This character does not exist.
        return None  # Return nothing since we have no results.
    return to_post


def zh_character_other_readings(character):  # A function to get non-Chinese pronunciations of characters

    to_post = []

    # Access the Chinese Character API at http://ccdb.hemiola.com/
    data_get = 'http://ccdb.hemiola.com/characters/string/{}?fields=kHangul,kKorean,kJapaneseKun,kJapaneseOn,kVietnamese'
    unicode_rep = requests.get(data_get.format(character))
    unicode_rep_json = unicode_rep.json()
    try:
        unicode_rep_jdict = unicode_rep_json[0]
    except IndexError:  # Don't really have the proper data.
        return None

    if 'kJapaneseKun' in unicode_rep_jdict and 'kJapaneseOn' in unicode_rep_jdict:
        ja_kun = unicode_rep_jdict['kJapaneseKun']
        ja_on = unicode_rep_jdict['kJapaneseOn']
        if ja_kun is not None or ja_on is not None:

            # Process the data, allowing for either of these to be None in value.
            if ja_kun is not None:
                ja_kun = ja_kun.lower() + " "  # A space is added since the kun appears first
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
    if 'kHangul' in unicode_rep_jdict and 'kKorean' in unicode_rep_jdict:
        ko_hangul = unicode_rep_jdict['kHangul']
        ko_latin = unicode_rep_jdict['kKorean']
        if ko_latin is not None and ko_hangul is not None:
            ko_latin = ko_latin.lower()
            ko_latin = ko_latin.replace(" ", ", ")  # Replace spaces with commas
            ko_hangul = ko_hangul.replace(" ", ", ")  # Replace spaces with commas
            ko_total = "{} / *{}*".format(ko_hangul, ko_latin)
            ko_string = "**Korean** | {}".format(ko_total)
            to_post.append(ko_string)
    if 'kVietnamese' in unicode_rep_jdict:
        vi_latin = unicode_rep_jdict['kVietnamese']
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
    """This function looks up a Chinese character's pronunciations and meanings."""
    
    multi_mode = False
    multi_character_dict = {}
    multi_character_list = list(character)
    
    if len(multi_character_list) > 1:  # Whether or not multiple characters are passed to this function
        multi_mode = True

    eth_page = requests.get('https://www.mdbg.net/chindict/chindict.php?page=chardict&cdcanoce=0&cdqchi=' + character,
                            headers=ZW_USERAGENT)
    tree = html.fromstring(eth_page.content)  # now contains the whole HTML page
    pronunciation = [div.text_content() for div in tree.xpath('//div[contains(@class,"pinyin")]')]
    cmn_pronunciation, yue_pronunciation = pronunciation[::2], pronunciation[1::2]
    
    if len(pronunciation) == 0:  # Check to not return anything if the entry is invalid
        to_post = "**There were no results for " + character + "**. Please check to make sure it is a valid Chinese "
        to_post += "character. Alternatively, it may be an uncommon variant that is not in online dictionaries."
        logger.info("[ZW] ZH-Character: No results for {}".format(character))
        return to_post
    
    if not multi_mode:  # Regular old-school character search for just one.
        cmn_pronunciation = ' / '.join(cmn_pronunciation)
        yue_pronunciation = tree.xpath('//a[contains(@onclick,"pronounce-jyutping")]/text()')
        yue_pronunciation = ' / '.join(yue_pronunciation)
        for i in range(0, 9):
            yue_pronunciation = yue_pronunciation.replace(str(i), "^%s " % str(i))
        meaning = tree.xpath('//div[contains(@class,"defs")]/text()')
        meaning = '/ '.join(meaning)
        meaning = meaning.strip()
        if tradify(character) == simplify(character):
            # print('The two versions of this character are identical.')
            lookup_line_1 = str('# [{0}](https://en.wiktionary.org/wiki/{0}#Chinese)'.format(character))
            lookup_line_1 += "\n\nLanguage | Pronunciation\n---------|--------------\n"
            lookup_line_1 += "**Mandarin** | *{}*\n**Cantonese** | *{}*"
            lookup_line_1 = lookup_line_1.format(cmn_pronunciation, yue_pronunciation[:-1])
        else:
            # print('The two versions of this character are not identical.')
            lookup_line_1 = '# [{0} ({1})](https://en.wiktionary.org/wiki/{0}#Chinese)'.format(tradify(character),
                                                                                               simplify(character))
            lookup_line_1 += "\n\nLanguage | Pronunciation\n---------|--------------\n"
            lookup_line_1 += "**Mandarin** | *{}*\n**Cantonese** | *{}*"
            lookup_line_1 = lookup_line_1.format(cmn_pronunciation, yue_pronunciation[:-1])

        # Hokkien and Hakka Data
        min_hak_data = zh_min_hak_pronunciation(tradify(character))
        lookup_line_1 += min_hak_data

        # Old Chinese
        try:  # Try to get old chinese data.
            ocmc_pronunciation = oc_search(tradify(character))
            if ocmc_pronunciation is not None:
                lookup_line_1 += ocmc_pronunciation
        except IndexError:  # There was an error; character has no old chinese entry
            lookup_line_1 = lookup_line_1

        # Other Language Readings
        other_readings_data = zh_character_other_readings(tradify(character))
        if other_readings_data is not None:
            lookup_line_1 += "\n" + other_readings_data

        calligraphy_image = calligraphy_search(character)
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
            character_url = 'https://www.mdbg.net/chindict/chindict.php?page=chardict&cdcanoce=0&cdqchi=' + wenzi
            new_eth_page = requests.get(character_url, headers=ZW_USERAGENT)
            new_tree = html.fromstring(new_eth_page.content)  # now contains the whole HTML page
            pronunciation = [div.text_content() for div in new_tree.xpath('//div[contains(@class,"pinyin")]')]
            cmn_pronunciation, yue_pronunciation = pronunciation[::2], pronunciation[1::2]

            # Format the pronunciation data
            cmn_pronunciation = "*" + ' '.join(cmn_pronunciation) + "*"
            yue_pronunciation = new_tree.xpath('//a[contains(@onclick,"pronounce-jyutping")]/text()')
            yue_pronunciation = ' '.join(yue_pronunciation)
            for i in range(0, 9):
                yue_pronunciation = yue_pronunciation.replace(str(i), "^%s " % str(i))
            yue_pronunciation = "*" + yue_pronunciation.strip() + "*"
            
            multi_character_dict[wenzi]["mandarin"] = cmn_pronunciation
            multi_character_dict[wenzi]["cantonese"] = yue_pronunciation
            
            # Format the meaning data.
            meaning = new_tree.xpath('//div[contains(@class,"defs")]/text()')
            meaning = '/ '.join(meaning)
            meaning = '"' + meaning.strip() + '."'
            multi_character_dict[wenzi]["meaning"] = meaning

            # Create a randomized wait time.
            wait_sec = random.randint(3, 12)
            time.sleep(wait_sec)
        
        # Now let's construct the table based on the data.
        for key in multi_character_list:  # Iterate over the characters in order
            character_data = multi_character_dict[key]
            if tradify(key) == simplify(key):  # Same character in both sets.
                duo_header += " | [{0}](https://en.wiktionary.org/wiki/{0}#Chinese)".format(key)
            else:
                duo_header += " | [{0} ({1})](https://en.wiktionary.org/wiki/{0}#Chinese)".format(tradify(key),
                                                                                                  simplify(key))
            duo_separator += "---|"
            duo_mandarin += " | {}".format(character_data["mandarin"])
            duo_cantonese += " | {}".format(character_data["cantonese"])
            duo_meaning += " | {}".format(character_data["meaning"])

        lookup_line_1 = duo_key + duo_header + duo_separator + duo_mandarin + duo_cantonese + duo_meaning

    # Format the dictionary links footer
    lookup_line_2 = ('\n\n\n^Information ^from '
                     '[^Unihan](http://www.unicode.org/cgi-bin/GetUnihanData.pl?codepoint={0}) ^| '
                     '[^CantoDict](http://www.cantonese.sheik.co.uk/dictionary/characters/{0}/) ^| '
                     '[^Chinese ^Etymology](http://hanziyuan.net/#{1}) ^| '
                     '[^CHISE](http://www.chise.org/est/view/char/{0}) ^| '
                     '[^CTEXT](http://ctext.org/dictionary.pl?if=en&char={1}) ^| '
                     '[^MDBG](https://www.mdbg.net/chindict/chindict.php?page=chardict&cdcanoce=0&cdqchi={0}) ^| '
                     '[^MFCCD](http://humanum.arts.cuhk.edu.hk/Lexis/lexi-mf/search.php?word={1})')
    lookup_line_2 = lookup_line_2.format(character, tradify(character))

    to_post = (lookup_line_1 + lookup_line_2)
    logger.info("[ZW] ZH-Character: Received lookup command for " + character + " in Chinese. Returned search results.")
    return to_post


def zh_word_alt_romanization(pinyin_string):
    """ Takes a pinyin with number item and returns Wade Giles and Yale romanization schemes.
    Example: ri4 guang1 becomes jih^4 kuang^1
    This is only used for zh_word at the moment. We don't deal with diacritics for this. Too complicated.
    """
    yale_list = []
    wadegiles_list = []

    # Get the corresponding pronunciations into a dictonary.
    corresponding_dict = {}
    csv_file = csv.reader(open(FILE_ADDRESS_ZH_ROMANIZATION, "rt", encoding="utf-8"), delimiter=",")
    for row in csv_file:
        pinyin_p, yale_p, wadegiles_p = row
        corresponding_dict[pinyin_p] = [yale_p.strip(), wadegiles_p.strip()]

    # Divide the string into syllables
    syllables = pinyin_string.split(' ')

    # Process each syllable.
    for syllable in syllables:
        tone = syllable[-1]
        syllable = syllable[:-1].lower()

        # Make exception for null tones
        if tone is not "5":  # Add tone as superscript
            yale_equiv = "{}^{}".format(corresponding_dict[syllable][0], tone)
            wadegiles_equiv = "{}^{}".format(corresponding_dict[syllable][1], tone)
        else:  # Null tone, no need to add a number.
            yale_equiv = "{}".format(corresponding_dict[syllable][0])
            wadegiles_equiv = "{}".format(corresponding_dict[syllable][1])
        yale_list.append(yale_equiv)
        wadegiles_list.append(wadegiles_equiv)

    # Reconstitute the equivalent parts into a string.
    yale_post = " ".join(yale_list)
    wadegiles_post = " ".join(wadegiles_list)

    return yale_post, wadegiles_post


def zh_word(word):  # Function to define Chinese words
    eth_page = requests.get('https://www.mdbg.net/chindict/chindict.php?page=worddict&wdrst=0&wdqb=c:' + word,
                            headers=ZW_USERAGENT)
    tree = html.fromstring(eth_page.content)  # now contains the whole HTML page
    word_exists = str(tree.xpath('//p[contains(@class,"nonprintable")]/strong/text()'))
    cmn_pronunciation = tree.xpath('//div[contains(@class,"pinyin")]/a/span/text()')
    cmn_pronunciation = cmn_pronunciation[0:len(word)]  # We only want the pronunciations to be as long as the input
    cmn_pronunciation = ''.join(
        cmn_pronunciation)  # We don't need a dividing character because pinyin says that words should be joined

    # Check to not return anything if the entry is invalid
    if 'No results found' in word_exists:
        to_post = zh_character(word)
        logger.debug("[ZW] ZH-Word: No results found for a multisyllabic word. Getting individual characters instead.")
        return to_post

    # Get alternate pinyin from a separate function. We get Wade Giles and Yale. Like 'Guan1 yin1 Pu2 sa4'
    try:
        py_split_pronunciation = tree.xpath('//div[contains(@class,"pinyin")]/a/@onclick')
        py_split_pronunciation = re.search(r"\|(...+)\'\)", py_split_pronunciation[0]).group(0)
        py_split_pronunciation = py_split_pronunciation.split("'", 1)[0][1:].strip()  # Format it nicely.
        alt_romanize = zh_word_alt_romanization(py_split_pronunciation)
    except IndexError:  # This likely means that the page does not contain that information.
        alt_romanize = ("---", "---")

    meaning = [div.text_content() for div in tree.xpath('//div[contains(@class,"defs")]')]
    meaning = [x for x in meaning if x != ' ']  # This removes any empty spaces that are in the list.
    meaning = [x for x in meaning if x != ', ']  # This removes any extraneous commas that are in the list
    meaning = '/ '.join(meaning)
    meaning = meaning.strip()
    yue_page = requests.get('http://cantonese.org/search.php?q=' + word, headers=ZW_USERAGENT)
    yue_tree = html.fromstring(yue_page.content)  # now contains the whole HTML page
    yue_pronunciation = yue_tree.xpath('//h3[contains(@class,"resulthead")]/small/strong//text()')
    yue_pronunciation = yue_pronunciation[0:(len(word) * 2)]  # This Len needs to be double because of the damn numbers
    yue_pronunciation = iter(yue_pronunciation)
    yue_pronunciation = [c + next(yue_pronunciation, '') for c in yue_pronunciation]

    # Combines the tones and the syllables together
    yue_pronunciation = ' '.join(yue_pronunciation)
    for i in range(0, 9):
        yue_pronunciation = yue_pronunciation.replace(str(i), "^%s " % str(i))  # Adds Markdown syntax
    yue_pronunciation = yue_pronunciation.strip()

    # Format the header appropriately.
    if tradify(word) == simplify(word):
        lookup_line_1 = str('# [{0}](https://en.wiktionary.org/wiki/{0}#Chinese)'.format(word))
    else:
        lookup_line_1 = '# [{0} ({1})](https://en.wiktionary.org/wiki/{0}#Chinese)'.format(tradify(word),
                                                                                           simplify(word))

    # Format the rest.
    lookup_line_1 += "\n\nLanguage | Pronunciation\n---------|--------------"
    readings_line = ("\n**Mandarin (Pinyin)** | *{}*\n**Mandarin (Wade-Giles)** | *{}*"
                     "\n**Mandarin (Yale)** | *{}*\n**Cantonese** | *{}*")
    readings_line = readings_line.format(cmn_pronunciation, alt_romanize[1], alt_romanize[0], yue_pronunciation)
    lookup_line_1 += readings_line

    # Add Hokkien and Hakka data.
    min_hak_data = zh_min_hak_pronunciation(tradify(word))
    lookup_line_1 += min_hak_data

    # Format the meaning line
    lookup_line_2 = str('\n\n**Meanings**: "' + meaning + '."')

    # Format the footer with the dictionary links.
    lookup_line_3 = '\n\n\n^Information ^from '
    lookup_line_3 += '[^CantoDict](http://www.cantonese.sheik.co.uk/dictionary/search/?searchtype=1&text={0}) ^| '
    lookup_line_3 += '[^Jukuu](http://jukuu.com/search.php?q={0}) ^| '
    lookup_line_3 += '[^MDBG](https://www.mdbg.net/chindict/chindict.php?page=worddict&wdrst=0&wdqb={0}) ^| '
    lookup_line_3 += '[^Yellowbridge](https://yellowbridge.com/chinese/dictionary.php?word={0}) ^| '
    lookup_line_3 += '[^Youdao](http://dict.youdao.com/w/eng/{0}/#keyfrom=dict2.index)'
    lookup_line_3 = lookup_line_3.format(word)

    # Combine everything together.
    to_post = (lookup_line_1 + lookup_line_2 + "\n\n" + lookup_line_3)
    logger.info("[ZW] ZH-Word: Received a lookup command for the word " + word + " in Chinese. Returned search results.")
    return to_post


def zh_chengyu(chengyu):  # Function to get Chinese information for Chinese chengyu.
    # Note: this is the second version. This version just adds supplementary Chinese information.

    headers = {'Content-Type': "text/html; charset=gb2312", 'f-type': 'chengyu'}
    chengyu = simplify(chengyu)  # This website only takes simplified chinese
    r_tree = None  # Placeholder...

    # Convert unicode into a string for the URL
    try:
        chengyu_gb = str(chengyu.encode('gb2312'))
        chengyu_gb = chengyu_gb.replace('\\x', "%").upper()[2:-1]

        search_link = 'http://cy.5156edu.com/serach.php?f_key={}&f_type=chengyu'
        search_link = search_link.format(chengyu_gb)
        # print(search_link)

        # We run a search on the site and see if there are results.
        results = requests.get(search_link.format(chengyu), headers=headers)
        results.encoding = "gb2312"
        r_tree = html.fromstring(results.text)  # now contains the whole HTML page
        chengyu_exists = r_tree.xpath('//td[contains(@bgcolor,"#B4D8F5")]/text()')
    except (UnicodeEncodeError, UnicodeDecodeError):  # There may be an issue with the conversion.
        chengyu_exists = ["", '找到 0 个成语']  # Tell it to exit later.

    if '找到 0 个成语' in chengyu_exists[1]:  # There are no results...
        to_post = zh_word(chengyu)
        logger.info("[ZW] ZH-Chengyu: No chengyu results found for {}.".format(chengyu))
        return to_post
    elif r_tree is not None:  # There are results.
        # Look through the results page.
        link_results = r_tree.xpath('//td[contains(@width,"20%")]/a')
        actual_link = link_results[0].attrib['href']
        actual_link = "http://cy.5156edu.com/" + actual_link

        # Get the data from the actual link
        eth_page = requests.get(actual_link)
        eth_page.encoding = "gb2312"
        tree = html.fromstring(eth_page.text)  # now contains the whole HTML page

        # Grab the data from the table.
        zh_data = tree.xpath('//td[contains(@colspan,"5")]/text()')

        chengyu_meaning = zh_data[1]
        chengyu_source = zh_data[2]

        # Format the data nicely to add to the zh_word output.
        cy_to_post = "\n\n**Chinese Meaning**: {}\n\n**Literary Source**: {}"
        cy_to_post = cy_to_post.format(chengyu_meaning, chengyu_source)

        # Now get zh_word info (we want to trash the last links though)
        zh_word_data = zh_word(chengyu)
        zh_word_data = zh_word_data.split("\n\n^Information", 1)[0].strip()
        cy_to_post = zh_word_data + cy_to_post

        # Form external links
        lookup_line_3 = '\n\n\n^Information ^from [^5156edu]({}) '.format(actual_link)
        lookup_line_3 += '^| [^18Dao](https://tw.18dao.net/成語詞典/{}) '.format(tradify(chengyu))
        lookup_line_3 += '^| [^MDBG](https://www.mdbg.net/chindict/chindict.php?page=worddict&wdqb={}) '.format(chengyu)
        lookup_line_3 += '^| [^Wiktionary](https://en.wiktionary.org/w/index.php?search={})'.format(tradify(chengyu))
        cy_to_post += lookup_line_3

        logger.info(">> Received a lookup command for the chengyu {} in Chinese. Returned search results.".format(chengyu))

        return cy_to_post


def ja_character(character):  # This function looks up a Japanese kanji's pronunciations and meanings

    is_kana = False
    multi_mode = False
    multi_character_dict = {}  # Dictionary to store the info we get.
    total_data = ""
    kana_test = re.search('[\u3040-\u309f]', character)  # Check to see if it's a kana. Will return none if it's kanji.

    multi_character_list = list(character)

    if len(multi_character_list) > 1:
        multi_mode = True

    if kana_test is not None:
        kana = kana_test.group(0)
        eth_page = requests.get('http://jisho.org/search/{}%20%23particle'.format(character), headers=ZW_USERAGENT)
        tree = html.fromstring(eth_page.content)  # now contains the whole HTML page
        meaning = tree.xpath('//span[contains(@class,"meaning-meaning")]/text()')
        meaning = ' / '.join(meaning)
        is_kana = True
        total_data = '# [{0}](https://en.wiktionary.org/wiki/{0}#Japanese)'.format(kana)
        total_data += " (*{}*)".format(romkan.to_hepburn(kana))
        total_data += '\n\n**Meanings**: "{}."'.format(meaning)
    else:
        if not multi_mode:
            # Regular old-school one character search.
            eth_page = requests.get('http://jisho.org/search/' + character + '%20%23kanji', headers=ZW_USERAGENT)
            tree = html.fromstring(eth_page.content)  # now contains the whole HTML page
            kun_reading = tree.xpath('//dl[contains(@class,"kun_yomi")]/dd/a/text()')
            meaning = tree.xpath('//div[contains(@class,"kanji-details__main-meanings")]/text()')
            meaning = '/ '.join(meaning)
            meaning = meaning.strip()
            if len(meaning) == 0:  # Check to not return anything if the entry is invalid
                to_post = ("There were no results for {}. Please check to make sure it is a valid Japanese "
                           "character or word.".format(character))
                logger.info("[ZW] JA-Character: No results for {}".format(character))
                return to_post
            if len(kun_reading) == 0:
                on_reading = tree.xpath('//*[@id="result_area"]/div/div[1]/div[2]/div/div[1]/div[2]/dl/dd/a/text()')
            else:
                on_reading = tree.xpath('//div[contains(@class,"kanji-details__main-readings")]/dl[2]/dd/a/text()')
            kun_chunk = ""
            for reading in kun_reading:
                kun_chunk_new = reading + ' (*' + romkan.to_hepburn(reading) + '*)'
                kun_chunk = kun_chunk + ', ' + kun_chunk_new
            on_chunk = ""
            for reading in on_reading:
                on_chunk_new = reading + ' (*' + romkan.to_hepburn(reading) + '*)'
                on_chunk = on_chunk + ', ' + on_chunk_new
            lookup_line_1 = '# [{0}](https://en.wiktionary.org/wiki/{0}#Japanese)\n\n'.format(character)
            lookup_line_1 += '**Kun-readings:** ' + kun_chunk[2:] + '\n\n**On-readings:** ' + on_chunk[2:]

            # Try to get a Japanese calligraphic image
            ja_calligraphy_image = ja_calligraphy_search(character)
            if ja_calligraphy_image is not None:
                lookup_line_1 = lookup_line_1 + ja_calligraphy_image

            # Try to get a Chinese calligraphic image
            calligraphy_image = calligraphy_search(character)
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

                eth_page = requests.get('http://jisho.org/search/' + moji + '%20%23kanji', headers=ZW_USERAGENT)
                tree = html.fromstring(eth_page.content)  # now contains the whole HTML page

                # Get the readings of the characters
                kun_reading = tree.xpath('//dl[contains(@class,"kun_yomi")]/dd/a/text()')
                if len(kun_reading) == 0:
                    on_reading = tree.xpath('//*[@id="result_area"]/div/div[1]/div[2]/div/div[1]/div[2]/dl/dd/a/text()')
                else:
                    on_reading = tree.xpath('//div[contains(@class,"kanji-details__main-readings")]/dl[2]/dd/a/text()')

                # Process and format the kun readings
                kun_chunk = []
                for reading in kun_reading:
                    kun_chunk_new = reading + ' (*' + romkan.to_hepburn(reading) + '*)'
                    # print(kun_chunk_new)
                    kun_chunk.append(kun_chunk_new)
                kun_chunk = ", ".join(kun_chunk)
                multi_character_dict[moji]["kun"] = kun_chunk

                # Process and format the on readings
                on_chunk = []
                for reading in on_reading:
                    on_chunk_new = reading + ' (*' + romkan.to_hepburn(reading) + '*)'
                    # print(on_chunk_new)
                    on_chunk.append(on_chunk_new)
                on_chunk = ", ".join(on_chunk)
                multi_character_dict[moji]["on"] = on_chunk

                meaning = tree.xpath('//div[contains(@class,"kanji-details__main-meanings")]/text()')
                meaning = '/ '.join(meaning)
                meaning = '"' + meaning.strip() + '."'
                multi_character_dict[moji]["meaning"] = meaning

            # Now let's construct our table based on the data we have.
            for key in multi_character_list:
                character_data = multi_character_dict[key]
                ooi_header += " | [{0}](https://en.wiktionary.org/wiki/{0}#Japanese)".format(key)
                ooi_separator += "---|"
                ooi_kun += " | {}".format(character_data["kun"])
                ooi_on += " | {}".format(character_data["on"])
                ooi_meaning += " | {}".format(character_data["meaning"])

            # Combine the data together.
            total_data = ooi_key + ooi_header + ooi_separator + ooi_kun + ooi_on + ooi_meaning

    if not is_kana:
        ja_to_post = "\n\n^Information ^from [^Jisho](http://jisho.org/search/{0}%20%23kanji) ^| "
        ja_to_post += "[^Goo ^Dictionary](https://dictionary.goo.ne.jp/word/en/{0}) ^| "
        ja_to_post += "[^Tangorin](http://tangorin.com/kanji/{0}) ^| [^Weblio ^EJJE](http://ejje.weblio.jp/content/{0})"
        ja_to_post = ja_to_post.format(character)
        lookup_line_3 = ja_to_post
    else:
        ja_to_post = "\n\n^Information ^from [^Jisho](http://jisho.org/search/{0}%20%23particle) ^| "
        ja_to_post += "[^Tangorin](http://tangorin.com/general/{0}%20particle) ^| "
        ja_to_post += "[^Weblio ^EJJE](http://ejje.weblio.jp/content/{0})"
        ja_to_post = ja_to_post.format(character)
        lookup_line_3 = ja_to_post

    to_post = total_data + lookup_line_3
    logger.info("[ZW] JA-Character: Received lookup command for " + character + " in Japanese. Returned search results.")

    return to_post


def ja_name(name):  # Function to get a Japanese surname (backup if a word search fails)
    eth_page = requests.get('https://myoji-yurai.net/searchResult.htm?myojiKanji=' + name, headers=ZW_USERAGENT)
    tree = html.fromstring(eth_page.content)  # now contains the whole HTML page
    ja_reading = tree.xpath('//div[contains(@class,"post")]/p/text()')
    ja_reading = str(ja_reading[0])[4:].split(",")
    if len(str(ja_reading)) <= 4:  # This indicates that it's blank. No results.
        return "Not a name."
    elif len(name) < 2:
        return "Not a name."
    else:
        furigana_chunk = ""
        for reading in ja_reading:
            furigana_chunk_new = reading + ' (*' + romkan.to_hepburn(reading).title() + '*)'
            furigana_chunk = furigana_chunk + ', ' + furigana_chunk_new
        lookup_line_1 = '# [{0}](https://en.wiktionary.org/wiki/{0}#Japanese)\n\n'.format(name)
        lookup_line_1 += '**Readings:** ' + furigana_chunk[2:]  # We return the formatted readings of this name
        lookup_line_2 = str('\n\n**Meanings**: "A Japanese surname."')
        lookup_line_3 = "\n\n\n^Information ^from [^Myoji](https://myoji-yurai.net/searchResult.htm?myojiKanji={0}) "
        lookup_line_3 += "^| [^Weblio ^EJJE](http://ejje.weblio.jp/content/{0})"
        lookup_line_3 = lookup_line_3.format(name)
        to_post = (lookup_line_1 + lookup_line_2 + "\n" + lookup_line_3)
        logger.info("[ZW] JA-Name: '{}' is a Japanese name. Returned search results.".format(name))
        return to_post


def ja_word_old(word):  # Function to define Japanese words
    eth_page = requests.get('http://jisho.org/search/"' + word + '"%23words', headers=ZW_USERAGENT)
    tree = html.fromstring(eth_page.content)  # now contains the whole HTML page
    word_exists = str(tree.xpath('//div[contains(@id,"no-matches")]/text()'))

    if "couldn't find" in word_exists:  # Check to not return anything if the entry is invalid
        logger.debug("[ZW] JA-Word: No results found for a Japanese word '{}'.".format(word))
        to_post = ja_name(word)  # Check to see if it's a name. Name has to be two characters or more.
        if "Not a name" in to_post:
            to_post = ja_character(word)
            logger.info("[ZW] JA-Word: No results found for a Japanese name. Getting individual character data.")
            return to_post
        else:
            logger.info("[ZW] JA-Word: Found a matching Japanese surname.")
            return to_post
    else:
        pattern = re.compile(r'[\u3040-\u30ff]')  # Checks to see if there's kana in there
        if pattern.findall(word):  # If there is kana, then take another reading
            reading_eth = requests.get('http://ejje.weblio.jp/content/{}'.format(word), headers=ZW_USERAGENT)
            reading_tree = html.fromstring(reading_eth.content)
            reading_content = [sup.text_content() for sup in reading_tree.xpath('//p[contains(@class,"jmdctYm")]')]
            query_content = reading_tree.xpath('//span[contains(@id,"h1Query")]/text()')
            if len(reading_content) == 0:
                reading_content = [span.text_content() for span in
                                   reading_tree.xpath('//span[contains(@id,"h1Query")]')]
            else:  # We do some processing to make sure we have a good result.
                reading_content = reading_content[0]
                try:
                    reading_content = reading_content.split("読み方：", 1)[1]
                except IndexError:  # Sometimes hiragana-only pages do not contain the necessary info
                    reading_content = "".join(query_content)

                if "、" in reading_content:  # More than one pronunciation. split it.
                    reading_content = [reading_content.split("、")[0]]
                else:
                    reading_content = [reading_content]
            reading = str(reading_content[0])
        else:
            reading = tree.xpath('//span[contains(@class,"furigana")]/span/text()')
            reading = ''.join(reading[0:len(word)])
        furigana_chunk = '{} (*{}*)'.format(reading, romkan.to_hepburn(reading))
        meaning = tree.xpath('//span[contains(@class,"meaning-meaning")]/text()')
        if len(meaning) > 1:
            del meaning[-1]  # Try to remove extraneous definitions from Wikipedia
            meaning = [x for x in meaning if x != '、']
        meaning = ' / '.join(meaning)
        meaning = meaning.strip()

        # Format the comment output
        lookup_line_1 = '# [{0}](https://en.wiktionary.org/wiki/{0}#Japanese)\n\n**Reading:** {1}'.format(word,
                                                                                                          furigana_chunk)
        lookup_line_2 = str('\n\n**Meanings**: "{}."'.format(meaning))
        lookup_line_3 = '\n\n^Information ^from ^[Jisho](http://jisho.org/search/{0}%23words) ^| '
        lookup_line_3 += '[^Kotobank](https://kotobank.jp/word/{0}) ^| '
        lookup_line_3 += '[^Tangorin](http://tangorin.com/general/{0}) ^| '
        lookup_line_3 += '[^Weblio ^EJJE](http://ejje.weblio.jp/content/{0})'
        lookup_line_3 = lookup_line_3.format(word)

        to_post = (lookup_line_1 + lookup_line_2 + "\n" + lookup_line_3)
        logger.info("[ZW] JA-Word: Received a lookup command for the word '{}' in Japanese.".format(word))
    return to_post


def ja_word(japanese_word):
    """
    A newer function that uses Jisho's unlisted API in order to return data from Jisho.org for Japanese words.
    See here for more information: https://jisho.org/forum/54fefc1f6e73340b1f160000-is-there-any-kind-of-search-api
    Keep in mind that the API is in many ways more limited than the actual search stack (e.g. no kanji results)
    """
    y_data = None

    # Fetch data from the API
    link_json = 'https://jisho.org/api/v1/search/words?keyword="{}"%20%23words'.format(japanese_word)
    word_data = requests.get(link_json)
    word_data = word_data.json()
    try:
        word_data = word_data['data'][0]
    except IndexError:  # It appears that this word doesn't exist.
        logger.debug("[ZW] JA-Word: No results found for a Japanese word '{}'.".format(japanese_word))
        to_post = ja_name(japanese_word)  # Check to see if it's a name. Name has to be two characters or more.
        if "Not a name" in to_post:
            to_post = ja_character(japanese_word)
            logger.info("[ZW] JA-Word: No results found for a Japanese name. Getting individual character data.")
            return to_post
        else:
            logger.info("[ZW] JA-Word: Found a matching Japanese surname.")
            return to_post

    # Format the data from the returned JSON.
    word_reading = word_data['japanese'][0]['reading']
    word_reading_chunk = '{} (*{}*)'.format(word_reading, romkan.to_hepburn(word_reading))
    word_meaning = word_data['senses'][0]['english_definitions']
    word_meaning = '"{}."'.format(', '.join(word_meaning))
    word_type = word_data['senses'][0]['parts_of_speech']
    word_type = '*{}*'.format(', '.join(word_type))

    # Construct the comment structure with the data.
    return_comment = ('# [{0}](https://en.wiktionary.org/wiki/{0}#Japanese)\n\n'
                      '##### {3}\n\n**Reading:** {1}\n\n**Meanings**: {2}')
    return_comment = return_comment.format(japanese_word, word_reading_chunk, word_meaning, word_type)

    # Check if yojijukugo.
    if len(japanese_word) == 4:
        y_data = ja_chengyu(japanese_word)
        if y_data is not None:  # If there's data, append it.
            logger.debug("[ZW] JA-Word: Yojijukugo data retrieved.")
            return_comment += y_data

    # Add the footer
    footer = ('\n\n^Information ^from ^[Jisho](http://jisho.org/search/{0}%23words) ^| '
              '[^Kotobank](https://kotobank.jp/word/{0}) ^| '
              '[^Tangorin](http://tangorin.com/general/{0}) ^| '
              '[^Weblio ^EJJE](http://ejje.weblio.jp/content/{0})')
    if y_data is not None:  # Add attribution for yojijukugo
        footer += ' ^| [^Yoji ^Jitenon](https://yoji.jitenon.jp/cat/search.php?getdata={0})'
    return_comment += footer.format(japanese_word)
    logger.info("[ZW] JA-Word: Received a lookup command for the word '{}' in Japanese.".format(japanese_word))

    return return_comment


def ja_chengyu(yojijukugo):
    """
    A newer rewrite of the yojijukugo function that has been changed to match the zh_chengyu function.
    That is, now its role is to grab a Japanese meaning and explanation in order to give some insight.
    For examples, see http://www.edrdg.org/projects/yojijukugo.html
    """

    # Fetch the page and its data.
    url_search = 'https://yoji.jitenon.jp/cat/search.php?getdata={}&search=part&page=1'.format(yojijukugo)
    eth_page = requests.get(url_search, headers=ZW_USERAGENT)
    tree = html.fromstring(eth_page.content)  # now contains the whole HTML page
    url = tree.xpath('//th[contains(@scope,"row")]/a/@href')

    if len(url) != 0:  # There's data. Get the url.
        url_entry = url[0]  # Get the actual url of the entry.
        entry_page = requests.get(url_entry, headers=ZW_USERAGENT)
        entry_tree = html.fromstring(entry_page.content)  # now contains the whole HTML page

        # Check to make sure the data is the same.
        entry_title = entry_tree.xpath('//h1/text()')[0]
        entry_title = entry_title.split('」', 1)[0][1:]  # Retrieve only the main title of the page.
        if entry_title != yojijukugo:  # If the data doesn't match
            logger.debug('[ZW] JA-Chengyu: The titles don\'t match.')
            return None

        # Format the data properly.
        row_data = [td.text_content() for td in entry_tree.xpath('//td')]
        y_meaning = row_data[1].strip()
        y_meaning = "\n\n**Japanese Explanation**: {}\n\n".format(y_meaning)
        logger.info('[ZW] JA-Chengyu: Retrieved information on {} from {}.'.format(yojijukugo, url_entry))

        # Add the literary source.
        y_source = row_data[2].strip()
        y_source = "**Literary Source**: {}".format(y_source)

        y_meaning += y_source
        return y_meaning
    else:
        return None


def ja_chengyu_old(chengyu):  # Function to define Japanese yojijukugo
    eth_page = requests.get('https://www.japandict.com/' + chengyu, headers=ZW_USERAGENT)
    tree = html.fromstring(eth_page.content)  # now contains the whole HTML page
    # print(eth_page.content)
    word_exists = str(tree.xpath('//*[@id="section1"]/div/div/h1/small/text()'))
    if "404" in str(word_exists[0]):  # Check to not return anything if the entry is invalid
        to_post = ja_word(chengyu)
        logger.debug("[ZW] JA-Chengyu: No results found for the four-syllable Japanese word '{}'.".format(chengyu))
        return to_post
    else:
        reading = tree.xpath('//*[@id="section2"]/div/div[1]/ul[1]/li/text()')
        # //*[@id="section2"]/div/div[1]/ul[1]/li/text()
        if len(reading) == 0:
            reading = tree.xpath('//*[@id="section2"]/div[1]/div[1]/ul[1]/a/text()')
        # print(reading)
        try:
            reading = str(reading[0]).strip()
        except IndexError:  # Unable to find the reading fo rthis
            to_post = ja_word(chengyu)  # Just return the character data then.
            logger.debug("[ZW] JA-Chengyu: Unable to get the readings... Getting individual character data instead.")
            return to_post
        furigana_chunk = reading + ' (*' + romkan.to_hepburn(reading) + '*)'
        meaning = tree.xpath('//*[@id="section2"]/div/div[1]/ul[2]/li/div[2]/text()')
        meaning = str(meaning[0]).strip()
        google_url = []
        for url in search(chengyu + ' yoji.jitenon.jp/yoji/', num=1, stop=1):
            if url == 'http://yoji.jitenon.jp/':
                continue
            elif 'yoji' not in url:
                continue
            else:
                google_url.append(url)
                # print(google_url)
        if len(google_url) != 0:
            try:
                ja_tree = html.parse(google_url[0])
                ja_page_header = [li.text_content() for li in ja_tree.xpath('//ol')]
                ja_page_header = ja_page_header[0].rsplit(">", 1)[1].strip()
                ja_page_header = ja_page_header.replace("「", "")
                ja_page_header = ja_page_header.replace("」", "")
                if ja_page_header == chengyu:  # The header string matched.
                    ja_content = [td.text_content() for td in ja_tree.xpath('//td')]
                    ja_meaning = ja_content[1]
                else:  # The header string did not match the input string.
                    ja_meaning = ""
            except OSError:  # Could not parse the page for some reason. Just leave the ja_meaning as blank.
                ja_meaning = ""
        else:
            ja_meaning = ""

        lookup_line_1 = '# [{0}](https://en.wiktionary.org/wiki/{0}#Japanese)\n\n**Readings:** {1}'
        lookup_line_1 = lookup_line_1.format(chengyu, furigana_chunk)
        if len(ja_meaning) >= 1:
            lookup_line_2 = str('\n\n**Meanings**: "' + meaning + '."\n\n**Japanese Explanation:** ' + ja_meaning)
            lookup_line_3 = '\n\n\n^Information ^from [^JapanDict](https://www.japandict.com/{0}) ^| '
            lookup_line_3 += '[^Jitenon]({1}) ^| [^Goo](http://dictionary.goo.ne.jp/leaf/idiom/{0}/m0u/) '
            lookup_line_3 += '^| [^Wiktionary](https://en.wiktionary.org/w/index.php?search={0})'
            lookup_line_3 = lookup_line_3.format(chengyu, google_url[0])
        else:
            lookup_line_2 = str('\n\n**Meanings**: "' + meaning + '."')
            lookup_line_3 = '\n\n\n^Information ^from [^JapanDict](https://www.japandict.com/{0}) ^| '
            lookup_line_3 += '[^Wiktionary](https://en.wiktionary.org/w/index.php?search={0})'
            lookup_line_3 = lookup_line_3.format(chengyu)
        to_post = (lookup_line_1 + lookup_line_2 + "\n" + lookup_line_3)
        logger.info("[ZW] JA-Chengyu: Received a yojijukugo lookup for " + chengyu + " in Japanese. Returned search results.")
        return to_post


def cjk_matcher(content_text):
    """A simple function to allow for compatibility with a greater number of CJK characters.
    This function can be expanded in the future to support more languages and be more robust.
    normal_returned_matches = re.findall('`([\u2E80-\u9FFF]+)`', content_text, re.DOTALL)
    Old routine, Normally will output a list with breakdowns."""

    # Making sure we only have stuff between the graves. 
    try:
        content_text = content_text.split("`", 1)[1]  # Delete stuff before
        content_text = content_text.rsplit('`', 1)[0]  # Delete stuff after
        content_text = "`{}`".format(content_text)  # Re-add the graves.
    except IndexError:  # Split improperly
        return []

    content_text = content_text.replace(" ", "``")  # Delete spaces, we don't need this for CJK.
    content_text = content_text.replace("\\", "")  # Delete slashes, since the redesign may introduce them.
    matches = re.findall('`([\u2E80-\u9FFF]+)`', content_text, re.DOTALL)
    # Regular CJK Unified Ideographs range with CJK Unified Ideographs Extension A
    b_matches = re.findall('`([\U00020000-\U0002EBEF]+)`', content_text, re.DOTALL)
    # CJK Unified Ideographs Extension B-F (obscure characters that do not have online sources)
    if len(b_matches) != 0:  # We found something in the B sets
        for match in b_matches:
            if not any(match in s for s in matches):  # Make sure the a match is not already in the regular set.
                matches.append(match)
    # print("Normal results: {}".format(normal_returned_matches))
    # print("Final:          {}".format(matches))
    if len(matches) != 0:
        return matches
    else:
        return []


def c_or_j_detector(word_list):
    """Takes a list of C/J words and outputs True if all are Chinese, False, if any are Japanese."""

    # A list that will store any Japanese characters we find.
    total_japanese = []

    # Iterate through the words to see if any are in hiragana or katakana.
    for word in word_list:

        hg_matches = re.findall('([\u3041-\u309f]+)', word, re.DOTALL)  # Hiragana
        if len(hg_matches) != 0:
            total_japanese.append(hg_matches[0])
        kk_matches = re.findall('([\u30a0-\u30ff]+)', word, re.DOTALL)  # Katakana
        if len(kk_matches) != 0:
            total_japanese.append(kk_matches[0])

    if len(total_japanese) == 0:  # There are no Japanese characters here.
        return True
    else:  # There are Japanese characters.
        return False


def other_language_matcher(content_text):
    """Looks for Korean or other text, returns it as a list."""

    try:
        content_text = content_text.split("`", 1)[1]  # Delete stuff before
        content_text = content_text.rsplit('`', 1)[0]  # Delete stuff after
        content_text = "`{}`".format(content_text)  # Re-add the graves.
    except IndexError:
        return []

    content_text = content_text.replace("\\", "")  # Delete slashes, since the redesign may introduce them.

    ko_matches = re.findall('`([\uac00-\ud7af]+)`', content_text, re.DOTALL)  # Checks if there's hangul there
    
    if len(ko_matches) == 0:  # No Korean matches found.
        # print("Conducting general regex.")
        no_ko_matches = re.findall('`([\w]+)`', content_text, re.DOTALL)
        # no_ko_matches += re.findall('`([\u0400-\u052f]+)`', content_text)
        # print(no_ko_matches)
        matches = no_ko_matches
    else:
        # print(ko_matches)
        matches = ko_matches

    return matches


def lookup_matcher(content_text, language_name):
    """
    :param content_text: The text of the comment to search.
    :param language_name: The language the post was originally in. If it's set to None, it'll just return everything
                          that's in between the graves. The None setting is used in edit_finder.
    :return: A dictionary indexing the lookup terms with a language. {'Japanese': ['高校', 'マレーシア']}
             None if there was no valid information found.

    Note that if the language_name is set to None the function returns a LIST not a DICTIONARY.
    """
    original_text = str(content_text)
    master_dictionary = {}
    language_mentions = (language_mention_search(content_text))

    # If there is an identification command, we wanna classify this as something else.
    # First we check to see if there is another Identification command here.
    if "!identify:" in original_text:
        language_name = converter(comment_info_parser(original_text, "!identify:")[0])[1]
    # Secondly we see if there's a language mentioned.
    elif language_mention_search(content_text) is not None:
        if len(language_mentions) == 1:
            language_name = language_mentions[0]
    else:
        pass

    # Work with the text and clean it up.
    try:
        content_text = content_text.split("`", 1)[1]  # Delete stuff before
        content_text = content_text.rsplit('`', 1)[0]  # Delete stuff after
        content_text = "`{}`".format(content_text)  # Re-add the graves.
    except IndexError:  # Split improperly
        return []
    content_text = content_text.replace(" ", "``")  # Delete spaces, we don't need this for CJK.
    content_text = content_text.replace("\\", "")  # Delete slashes, since the redesign may introduce them.
    matches = re.findall('`(.*?)`', content_text, re.DOTALL)

    # Tokenize, remove empty strings
    for match in matches:
        if " " in match:  # This match contains a space, so let's split it.
            new_matches = match.split()
            matches.remove(match)
            matches.append(new_matches)
    matches = [x for x in matches if x]
    combined_text = "".join(matches)  # A simple string to allow for quick detection of languages that fall in unicode
    zhja_true = re.findall('([\u2E80-\u9FFF]+)', combined_text, re.DOTALL)
    zh_b_true = re.findall('([\U00020000-\U0002EBEF]+)', combined_text, re.DOTALL)
    kana_true = re.findall('([\u3041-\u309f]+|[\u30a0-\u30ff]+)', combined_text, re.DOTALL)
    ko_true = re.findall('([\uac00-\ud7af]+)', combined_text, re.DOTALL)  # Checks if there's hangul there

    if language_name is None:
        return matches

    if zhja_true:  # Chinese or Japanese Characters were detected.
        zhja_temp_list = []
        for match in matches:
            zhja_matches = re.findall('([\u2E80-\u9FFF]+|[\U00020000-\U0002EBEF]+)', match, re.DOTALL)
            if zhja_matches:
                for selection in zhja_matches:
                    zhja_temp_list.append(selection)

        logger.debug("[ZW] Lookup_Matcher: Provisional: {}".format(zhja_temp_list))
        # Tokenize them.
        tokenized_list = []
        for item in zhja_temp_list:
            if len(item) >= 2:  # Longer than bisyllabic?
                if language_name is "Chinese" and not kana_true:
                    new_matches = zhja_tokenizer(simplify(item), "zh")
                elif language_name is "Japanese" or kana_true:
                    new_matches = zhja_tokenizer(item, "ja")
                else:
                    new_matches = [item]
                for new_word in new_matches:
                    tokenized_list.append(new_word)
            else:
                tokenized_list.append(item)

        if not kana_true:  # There's kana, so we'll mark this as Japanese.
            master_dictionary[language_name] = tokenized_list
        else:
            master_dictionary['Japanese'] = tokenized_list

    # There's text with Hangul, add it to the master dictionary with an Index of Korean.
    if ko_true:
        ko_temp_list = []
        for match in matches:
            ko_matches = re.findall('([\uac00-\ud7af]+)', match, re.DOTALL)
            if ko_matches:  # If it's actually containing data, let's append it.
                for selection in ko_matches:
                    ko_temp_list.append(selection)
        master_dictionary["Korean"] = ko_temp_list

    if not any([zhja_true, zh_b_true, kana_true, ko_true]) and matches:  # Nothing CJK-related. True if all are empty.
        other_temp_list = []
        for match in matches:
            other_temp_list.append(match)
        master_dictionary[language_name] = other_temp_list

    return master_dictionary


def ko_word(word):  # Function to define Korean words

    # To replace the meaning output from Naver.
    ko_word_types = {'[동사]': '[verb]', '[형용사]': '[adjective]', '[관형사]': '[determiner]', '[명사]': '[noun]',
                     '[대명사]': '[pronoun]', '[부사]': '[adverb]', '[조사]': '[particle]',
                     '[감탄사]': '[interjection]', '[수사]': '[number]'}

    eth_page = requests.get('http://endic.naver.com/search.nhn?sLn=kr&isOnlyViewEE=N&query=' + word, headers=ZW_USERAGENT)
    tree = html.fromstring(eth_page.content)  # now contains the whole HTML page
    word_exists = str(tree.xpath('//*[@id="content"]/div[2]/h4/text()'))

    if "없습니다" in word_exists:  # Check to not return anything if the entry is invalid
        to_post = str("> Sorry, but that Korean word doesn't look like anything to me.")
        return to_post
    else:
        hangul_romanization = _ko_romanizer.Romanizer(word).romanize()
        hangul_chunk = word + ' (*' + hangul_romanization + '*)'
        hanja = tree.xpath('//*[@id="content"]/div[2]/dl/dt[1]/span/text()')
        if len(hanja) != 0:
            hanja = ''.join(hanja)
            hanja = hanja.strip()
        meaning = tree.xpath('//*[@id="content"]/div[2]/dl/dd[1]/div/p[1]//text()')
        meaning = ' '.join(meaning)
        meaning = ' '.join(meaning.split())

        # Here we want to replace the korean parts of speech with the english equiv.
        for key, value in ko_word_types.items():
            if key in meaning:
                meaning = meaning.replace(key, value)

        if len(hanja) != 0:
            lookup_line_1 = '# [{0}](https://en.wiktionary.org/wiki/{0}#Korean)\n\n'.format(word)
            lookup_line_1 += '**Reading:** ' + hangul_chunk + ' (' + hanja + ')'
        else:
            lookup_line_1 = '# [{0}](https://en.wiktionary.org/wiki/{0}#Korean)\n\n'.format(word)
            lookup_line_1 += '**Reading:** ' + hangul_chunk
        lookup_line_2 = str('\n\n**Meanings**: "' + meaning + '."')
        lookup_line_3 = '\n\n\n^Information ^from ^[Naver](http://endic.naver.com/search.nhn?sLn=kr&isOnlyViewEE=N&query={0}) '
        lookup_line_3 += '^| ^[Daum](http://dic.daum.net/search.do?q={0}&dic=eng)'
        lookup_line_3 = lookup_line_3.format(word)

        to_post = (lookup_line_1 + lookup_line_2 + lookup_line_3)
        logger.info("[ZW] KO_Word: Received a word lookup for the word {} in Korean. Returned search results.".format(word))
        return to_post


def zhja_tokenizer(phrase, language):
    """Language should be 'zh' or 'ja'. Returns a list of tokenized words.
    This uses Jieba for Chinese and either Tinysegmenter or MeCab for Japanese.
    The live version should be using MeCab.
    """
    word_list = []
    final_list = []
    if language == 'zh':
        seg_list = jieba.cut(phrase, cut_all=False)
        for item in seg_list:
            word_list.append(item)
    elif language == 'ja':
        # We will dynamically change the segmenters / tokenizers based on the OS.
        # On Windows for testing we can use Tinysegmenter for compatibility.
        # But on Mac/Linux, we can use MeCab's dictionary instead for better (but not perfect) tokenizing.
        # See http://www.robfahey.co.uk/blog/japanese-text-analysis-in-python/ for more info.
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
            mt.parse(phrase)  # Per https://github.com/SamuraiT/mecab-python3/issues/3 to fix Unicode issue
            parsed = mt.parseToNode(phrase.strip())
            components = []

            while parsed:
                components.append(parsed.surface)
                # print(parsed.feature) This produces the parts of speech, e.g. 名詞,一般,*,*,*,*,風景,フウケイ,フーケイ
                parsed = parsed.next

            # Remove empty strings
            word_list = [x for x in components if x]
    for item in word_list:  # Get rid of punctuation and kana (for now)
        if language == 'ja':
            kana_test = None
            if len(item) == 1:  # If it's only a single kana...
                kana_test = re.search('[\u3040-\u309f]', item)
            if kana_test is None:
                if item not in "\.\!\/_,$%^*(+\"\']+|[+——！，。？、~@#￥%……&*（）：；《）《》“”()»〔〕「」％":
                    final_list.append(item)
        if language == 'zh':
            if item not in "\.\!\/_,$%^*(+\"\']+|[+——！，。？、~@#￥%……&*（）：；《）《》“”()»〔〕「」％":
                final_list.append(item)
    
    return final_list  # Returns a list of words / characters


def wiktionary_search_new(search_term, language_name):
    """ This is a general search function for Wiktionary.
    Updated and cleaned up to be better than the previous version.
    """

    parser = WiktionaryParser()
    try:
        word_info_list = parser.fetch(search_term, language_name)
    except TypeError:  # Doesn't properly exist, first check
        return None

    try:
        exist_test = word_info_list[0]['definitions']  # A simple second test to see if something really has definitions
    except IndexError:
        return None

    if exist_test:
        # Get the dictionary that is wrapped in the list.
        word_info = word_info_list[0]
    else:  # This information doesn't exist.
        return None

    # pp.pprint(word_info)
    # First, let's take care of the etymology section.
    post_etymology = word_info['etymology']
    if len(post_etymology) > 0:  # There's actual information:
        post_etymology = post_etymology.replace("\*", "*")
        post_etymology = "\n\n#### Etymology\n\n{}".format(post_etymology.strip())

    # Secondly, let's add a pronunciation section if we can.
    dict_pronunciations = word_info['pronunciations']
    pronunciations_ipa = ""
    pronunciations_audio = ""
    if len(dict_pronunciations.values()) > 0:  # There's actual information:
        if len(dict_pronunciations['text']) > 0:
            pronunciations_ipa = dict_pronunciations['text'][0].strip()
        else:
            pronunciations_ipa = ""
        if len(dict_pronunciations['audio']) > 0:
            pronunciations_audio = " ([Audio](https:{}))".format(dict_pronunciations['audio'][0])
        else:
            pronunciations_audio = ""
    if len(pronunciations_ipa + pronunciations_audio) > 0:
        post_pronunciations = "\n\n#### Pronunciations\n\n{}{}".format(pronunciations_ipa, pronunciations_audio)
    else:
        post_pronunciations = ""

    # Lastly, and most complicated, we deal with 'definitions', including
    # examples, partOfSpeech, text (includes the gender/meaning)
    # A different part of speech is given as its own thing.
    total_post_definitions = []

    if len(word_info['definitions']) > 0:
        separate_definitions = word_info['definitions']
        # If they are separate parts of speech they have different definitions.
        for dict_definitions in separate_definitions:

            # Deal with Examples
            if len(dict_definitions['examples']) > 0:
                examples_data = dict_definitions['examples']
                if len(examples_data) > 3:  # If there are a lot of examples, we only want the first three.
                    examples_data = examples_data[:2]
                post_examples = "* " + "\n* ".join(examples_data)
                post_examples = "\n\n**Examples:**\n\n{}".format(post_examples)
            else:
                post_examples = ""

            # Deal with parts of speech
            if len(dict_definitions['partOfSpeech']) > 0:
                post_part = dict_definitions['partOfSpeech'].strip()
            else:
                post_part = ""

            # Deal with gender/meaning
            if len(dict_definitions['text']) > 0:
                master_text = dict_definitions['text']
                if '\xa0' in master_text:  # This is a separator generally used to denote Gender.
                    master_text = master_text.replace('\xa0', ' ^')
                master_text_list = master_text.split('\n')
                master_text_list = [x for x in master_text_list if x]
                post_word_info = master_text_list[0]
                # print(master_text_list[1:])
                meanings_format = "* " + '\n* '.join(master_text_list[1:])
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
                post_definitions = "\n\n##### {}\n\n{}{}".format(info_header, post_total_info, post_examples)
                total_post_definitions.append(post_definitions)

    total_post_definitions = "\n" + "\n\n".join(total_post_definitions)

    # Put it all together.
    post_template = "# [{0}](https://en.wiktionary.org/wiki/{0}#{1}) ({1}){2}{3}{4}"
    post_template = post_template.format(search_term, language_name.title(), post_etymology, post_pronunciations,
                                         total_post_definitions)
    logger.info("[ZW] Looked up information for {} as a {} word..".format(search_term, language_name))

    return post_template


def bad_title_commenter(title_text, author):  # Title text, author of post, submission ID
    new_title = bad_title_reformat(title_text)  # Retrieve the reformed title from the routine in _languages
    new_url = new_title.replace(" ", "%20")  # replace spaces
    new_url = new_url.replace(")", "\)")  # replace closing parentheses
    new_url = new_url.replace(">", "%3E")  # replace caret with HTML code
    new_title = "`" + new_title + "`"  # add code marks

    # If the new title is for Unknown, let's add a text reminder
    if "[Unknown" in new_title:
        new_title += "\n* (If you know your request's language, replace `Unknown` with its name.)"

    return COMMENT_BAD_TITLE.format(author=author, new_url=new_url, new_title=new_title)


'''LANGUAGE REFERENCE FUNCTIONS'''


def other_reference(string_text):
    """Function to look up languages that might be dead and hence not on Ethnologue
    This is the second version of this function - streamlined to be more effective.
    """
    no_results_comment = ('Sorry, there were no valid results on [Ethnologue](https://www.ethnologue.com/) '
                          'or [MultiTree](http://multitree.org/) for "{}."'.format(string_text))
    multitree_link = None
    language_iso3 = None

    if len(string_text) == 3:  # If the input string is 3 characters, Ziwen assumes it's a ISO 639-3 code.
        multitree_link = 'http://multitree.org/codes/' + string_text
        language_iso3 = string_text
    elif len(string_text) >= 4:
        # If the input string is 4 or more characters, Ziwen runs a Google search to try and identify it.
        language_match = string_text.rpartition(':')[-1]
        google_url = []  # Runs a Google search on MultiTree
        for url in search(language_match + ' site:multitree.org/codes/', num=2, stop=2):
            google_url.append(url)
        if len(google_url) == 0:
            # MultiTree does not have any information on this code.
            multitree_link = None
        else:
            # MultiTree does have information on this code
            language_iso3 = google_url[0][-3:]  # Takes only the part of the URL that contains the ISO 639-3 code
            multitree_link = 'http://multitree.org/codes/' + language_iso3
    
    # Exit early if we have no results. 
    if multitree_link is None or language_iso3 is None:
        logger.info("[ZW] No results for the reference search term {} on Multitree.".format(string_text))
        return no_results_comment
    
    # By now we should have a MultiTree link and can get info from it.
    fetch_page = requests.get('http://multitree.org/codes/' + string_text, headers=ZW_USERAGENT)
    tree = html.fromstring(fetch_page.content)
    page_title = tree.xpath('//title/text()')
    if "We're sorry" in page_title:
        # MultiTree does not have any information on this code.
        logger.info("[ZW] other_reference: No results for the reference term {} on Multitree.".format(string_text))
        return no_results_comment  # Exit earlu
    else:  # We do have results.
        language_name = tree.xpath('//*[@id="code-info"]/div[1]/div[1]/span[2]/text()')
        alt_names = tree.xpath('//*[@id="code-info"]/div[1]/div[1]/span[6]/text()')
        language_classification = tree.xpath('//*[@id="code-info"]/div[1]/div[1]/span[14]/text()')
        lookup_line_1 = '\n**Language Name**: ' + language_name[0]
        lookup_line_1 += '\n\n**ISO 639-3 Code**: ' + language_iso3
        lookup_line_1 += '\n\n**Alternate Names**: ' + alt_names[0] + '\n\n**Classification**: ' + language_classification[0]
        
        # Fetch Wikipedia information, using the ISO code.
        wk_to_get = wikipedia.search("ISO_639:{}".format(language_iso3))[0]
        wk_page = wikipedia.page(title=wk_to_get, auto_suggest=True,
                                 redirect=True, preload=False)
        try:  # Try to get the first four sentences
            wk_summary = re.match(r'(?:[^.]+[.]){4}', wk_page.summary).group()  # + ".." Regex to get first four sen
            if len(wk_summary) < 500:  # This summary is too short.
                wk_summary = wk_page.summary[0:500].rsplit(".", 1)[0] + "."  # Take the first 500 chars, split.
        except AttributeError:  # Maybe too short of an article. Regex can't get that many.
            wk_summary = wk_page.summary

        if "\n" in wk_summary:  # Take out line breaks from the wikipedia summary.
            wk_summary = wk_summary.replace("\n", " ")
        
        wk_chunk = str('\n\n**[Wikipedia Entry](' + wk_page.url + ')**:\n\n> ' + wk_summary)
        lookup_line_2 = '\n\n\n^Information ^from ^[MultiTree]({}.html) ^| ' \
                        '[^Glottolog](http://glottolog.org/glottolog?iso={}) ^| [^Wikipedia]({})'
        lookup_line_2 = lookup_line_2.format(multitree_link, language_iso3, wk_page.url)
        
        to_post = str("## [{}]({})\n{}{}{}".format(language_name[0], multitree_link, lookup_line_1, wk_chunk, lookup_line_2))
        
        return to_post


def run_reference(language_match):  # Function to look up reference languages on Ethnologue
    language_iso3 = None  # default that doesn't match anything.
    count = len(language_match)

    # Code to check from the cache to see if we have that information stored first!
    check_code = converter(language_match)[0]

    # Regex to check if code is in the private use area qaa-qtz
    private_check = re.search('^q[a-t][a-z]$', check_code)
    if private_check is not None:  # This is a private use code. If it's None, it did not match.
        return  # Just exit.

    if len(check_code) != 0:   # There is actually a code from our converter for this.
        logger.debug("[ZW] Run_Reference Code: {}".format(check_code))
        sql_command = "SELECT * FROM language_cache WHERE language_code = '{}'".format(check_code)
        # We try to retrieve the language in question.
        zw_reference_cursor.execute(sql_command)
        reference_results = zw_reference_cursor.fetchall()

        if len(reference_results) != 0:  # We could find a cached value for this language
            reference_cached_info = reference_results[0][1]
            logger.debug("[ZW] Retrieved the cached reference information for {}.".format(language_match))
            return reference_cached_info

    if count <= 1:
        to_post = COMMENT_INVALID_REFERENCE
        return to_post
    elif count == 2:
        try:
            language_iso3 = ISO_639_3[ISO_639_1.index(language_match)]
        except ValueError:  # Not a valid 2-letter code.
            to_post = COMMENT_INVALID_REFERENCE
            return to_post
    elif count == 3:
        language_iso3 = language_match
        eth_page = requests.get('https://www.ethnologue.com/language/' + language_iso3, headers=ZW_USERAGENT)
        tree = html.fromstring(eth_page.content)  # now contains the whole HTML page
        # language_population = tree.xpath('//div[contains(@class,"field-population")]/div[2]/div/p/text()')
        language_exist = tree.xpath('//div[contains(@class,"view-display-id-page")]/div/text()')
        if 'Ethnologue has no page for' in str(language_exist):  # Check to see if the page exists at all
            to_post = other_reference(language_iso3)
            reference_to_store = (language_iso3, to_post)
            zw_reference_cursor.execute("INSERT INTO language_cache VALUES (?, ?)", reference_to_store)
            zw_reference_cache.commit()
            return to_post
        if language_iso3 in ISO_MACROLANGUAGES:  # If it's a macrolanguage let's take a look.
            # print("This is a macrolanguage.")
            macro_data = ISO_MACROLANGUAGES.get(language_iso3)
            language_iso3 = macro_data[0]  # Get the most popular language of the macro lang
            # tree = html.fromstring(eth_page.content)  # now contains the whole HTML page
            # language_population = tree.xpath('//div[contains(@class,"field-population")]/div[2]/div/p/text()')
    elif count >= 4:
        language_match = language_match.rpartition(':')[-1]
        google_url = []
        for url in search(language_match + ' site:ethnologue.com/language', num=2, stop=2):
            google_url.append(url)
        if len(google_url) == 0:
            to_post = other_reference(language_match)
            return to_post
        language_iso3 = google_url[0][-3:]
        eth_page = requests.get('https://www.ethnologue.com/language/' + language_iso3, headers=ZW_USERAGENT)
        tree = html.fromstring(eth_page.content)  # now contains the whole HTML page
        language_population = tree.xpath('//div[contains(@class,"field-population")]/div[2]/div/p/text()')
        language_exist = tree.xpath('//div[contains(@class,"view-display-id-page")]/div/text()')
        if 'Ethnologue has no page for' in str(language_exist):  # Check to see if the page exists at all
            to_post = other_reference(language_iso3)
            return to_post
        if 'macrolanguage' in str(language_population):  # If it's a macrolanguage take the second result
            language_iso3 = google_url[1][-3:]

    if language_iso3 is not None:
        eth_page = requests.get('https://www.ethnologue.com/language/' + language_iso3, headers=ZW_USERAGENT)
        tree = html.fromstring(eth_page.content)  # now contains the whole HTML page
        # This will create a list of the language:
        language_name = tree.xpath('//h1[@id="page-title"]/text()')
        alt_names = tree.xpath('//div[contains(@class,"alternate-names")]/div[2]/div/text()')
        language_population = tree.xpath('//div[contains(@class,"field-population")]/div[2]/div/p/text()')
        language_country = tree.xpath('//div[contains(@class,"a-language-of")]/div/div/h2/a/text()')
        language_location = tree.xpath('//div[contains(@class,"name-field-region")]/div[2]/div/p/text()')
        language_classification = tree.xpath('//div[contains(@class,"language-classification")]/div[2]/div/a/text()')
        language_writing = "".join(tree.xpath('//div[contains(@class,"name-field-writing")]/div[2]/div/p/text()'))
        language_writing = language_writing.replace(' , ', ', ')
        language_writing = language_writing.replace(' .', '.')
        if len(language_population) == 0:
            language_population = "---"
        if len(language_writing) == 0:
            language_writing = "---"
        if len(alt_names) == 0:
            alt_names = ["---"]
        if len(language_location) == 0:
            language_location = ["---"]

        eth_link = 'https://www.ethnologue.com/language/{}'.format(language_iso3)

        try:
            language_name = str(language_name[0])
        except IndexError:  # No page listed still
            to_post = COMMENT_INVALID_REFERENCE
            return to_post

        if "," in language_name:  # Try to reformat language names with a comma so that it looks better.
            # More consistent with our internal usage too.
            part_a, part_b = language_name.split(",")
            language_name = part_b.strip() + " " + part_a  # Reconstitute the name

        try:
            wk_page = wikipedia.page(title=language_name.split(',', 1)[0] + ' language', auto_suggest=True,
                                     redirect=True, preload=False)
            wk_link = wk_page.url
            try:  # Try to get the first four sentences
                wk_summary = re.match(r'(?:[^.]+[.]){4}', wk_page.summary).group()  # + ".." Regex to get first four sen
                if len(wk_summary) < 500:  # This summary is too short.
                    wk_summary = wk_page.summary[0:500].rsplit(".", 1)[0] + "."  # Take the first 500 chars, split.
            except AttributeError:  # Maybe too short of an article. Regex can't get that many.
                wk_summary = wk_page.summary
        except (wikipedia.exceptions.PageError, wikipedia.exceptions.DisambiguationError):  # Not found, use ISO 639-3
            # Since a name search doesn't work we need to use the wikipedia search function for this.
            wk_title = wikipedia.search(str("ISO_639:" + language_iso3))  # Returns a list, we need the first item
            wk_page = wikipedia.page(title=wk_title[0], auto_suggest=True, redirect=True, preload=False)
            wk_link = wk_page.url
            wk_summary = wk_page.summary

        if "\n" in wk_summary:  # Take out line breaks from the wikipedia summary.
            wk_summary = wk_summary.replace("\n", " ")

        try:
            if "," in language_classification[0]:  # This is part of an extended lang family. Indo-Eur, Germanic, etc.
                language_classification = str(language_classification[0]).split(',', 1)[0]
            else:  # Single only, like Japonic
                language_classification = str(language_classification[0])
        except IndexError:  # There may be an issue with this particular code.
            language_classification = "N/A"

        try:  # Try to get the link to the language family page.
            wf_page = wikipedia.page(title=language_classification + ' languages',
                                     auto_suggest=True, redirect=True, preload=False)
            wf_link = "[" + language_classification + "](" + wf_page.url + ")"
        except wikipedia.exceptions.PageError:
            wf_link = "[{0}](https://en.wikipedia.org/w/index.php?search={0} language family)".format(language_classification)

        lookup_line_1 = str('\n**Language Name**: ' + language_name + '\n\n')
        if language_iso3 in ISO_639_3:
            # Here we try to get the ISO 639-1 code if possible for inclusion, checking it against a list of ISO codes.
            language_iso1 = ISO_639_1[ISO_639_3.index(language_iso3)]  # Find the matching 639-1 code
            cache_code = language_iso1
            if converter(language_iso1)[1] in LANGUAGE_SUBREDDITS:  # The language name has a subreddit listed.
                language_subreddit = LANGUAGE_SUBREDDITS.get(converter(language_iso1)[1])[
                    0]  # Get the first value, which should be a language learning one.
                lookup_line_1a = "**Subreddit**: {}\n\n".format(language_subreddit)
                lookup_line_1a += "**ISO 639-1 Code**: {}\n\n".format(language_iso1)
            else:  # No subreddit listed.
                lookup_line_1a = "**ISO 639-1 Code**: {}\n\n".format(language_iso1)
                # print(lookup_line_1a)
        else:
            cache_code = language_iso3
            lookup_line_1a = ""  # Can't find a matching code, just return nothing.

        lookup_line_1b = str('**ISO 639-3 Code**: ' + language_iso3 + '\n\n**Alternate Names**: ' + alt_names[0])
        try:  # Temporary logging to figure out our issue, it'll log the next time something happens
            lookup_line_2 = str('\n\n**Population**: ' + language_population[0] + '\n\n**Location**: ' +
                                language_country[0] + '; ' + language_location[0] + '\n\n**Classification**: ' +
                                wf_link + '\n\n**Writing system**: ' + language_writing)
        except IndexError:
            error_log_basic(language_match, "Ziwen #REFERENCE")
            return COMMENT_INVALID_REFERENCE
        lookup_line_3 = str('\n\n**[Wikipedia Entry](' + wk_link + ')**:\n\n> ' + wk_summary)
        lookup_line_4 = str('\n^Information ^from ^[Ethnologue](' + eth_link +
                            ') ^| [^Glottolog](http://glottolog.org/glottolog?iso=' + language_iso3 +
                            ') ^| [^MultiTree](http://multitree.org/codes/' + language_iso3 +
                            '.html) ^| [^ScriptSource](http://scriptsource.org/cms/scripts/page.php?item_id=language_detail&key=' +
                            language_iso3 + ') ^| [^Wikipedia](' + wk_link + ')')
        to_post = str("## [" + language_name + "](" + eth_link + ")\n" + lookup_line_1 + lookup_line_1a +
                      lookup_line_1b + lookup_line_2 + lookup_line_3 + "\n\n" + lookup_line_4)

        reference_to_store = (cache_code, to_post)
        zw_reference_cursor.execute("INSERT INTO language_cache VALUES (?, ?)", reference_to_store)
        zw_reference_cache.commit()

        logger.info("[ZW] Retrieved and saved reference information about '{}' as a language.".format(language_match))

        return to_post


def reference_reformatter(original_entry):
    """Takes a reference string and tries to make it more compact and simple.
    The replacement for Unknown posts will use this abbreviated version.
    !reference will still return the full information, and it'll still be saved for Wenyuan to use.
    """

    # Divide the lines.
    original_lines = original_entry.split("\n\n")
    new_lines = []

    excluded_lines = ["Language Name", "Alternate Names", "Writing system", "Population"]

    # Go over the lines and delete ones we don't need
    for line in original_lines:
        if "##" in line and "]" in line:
            sole_language = line.split(']')[0]
            sole_language = sole_language.replace("[", "")
            line = sole_language

        if any(key in line for key in excluded_lines):
            continue

        new_lines.append(line)

    # Combine the lines into a new string.
    new_entry = "\n\n".join(new_lines)

    return new_entry


'''KOMENTO PROCESSOR'''


def get_submission_from_comment(comment_id):  # Returns the parent submission as an object from a comment ID
    main_comment = reddit.comment(id=comment_id)  # Convert ID into comment object.
    main_submission = main_comment.link_id[3:]  # Strip the t3_ from front. 
    main_submission = reddit.submission(id=main_submission)  # Get actual submission object. 
    return main_submission
    

def komento_analyzer(reddit_submission):
    # A function that returns a dictionary containing various things that Ziwen checks against. 
    try:
        oauthor = reddit_submission.author.name
    except AttributeError:
        return {}  # Changed from None, the idea is to return a null dictionary

    # Flatten the comments into a list.
    reddit_submission.comments.replace_more(limit=None)  # Replace all MoreComments with regular comments.
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
    
        # Check for OP Short thanks.
        if cauthor == oauthor and any(keyword in cbody for keyword in THANKS_KEYWORDS):
            results['op_thanks'] = True
            # This is thanks. Not short thanks for marking something translated.
        
        # Check for bot's own comments
        if cauthor == USERNAME:  # Comment is by the bot. 
            if "this is a crossposted translation request" in cbody:
                results['bot_xp_comment'] = cid
                # We want to get a few more values.
                op_match = comment.body.split(" at")[0]
                op_match = op_match.split("/")[1].strip()  # Get just the username
                results['bot_xp_op'] = op_match
                requester_match = comment.body.split("**Requester:**")[1]
                requester = requester_match.split("\n", 1)[0].strip()[2:]
                results['bot_xp_requester'] = requester
                original_post = comment.body.split("**Requester:**")[0]  # Split in half
                original_post_id = original_post.split("comments/")[1].strip()[0:6]  # Get just the post ID
                results['bot_xp_original_submission'] = original_post_id
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

                    if ori_comment_author == "translator-BOT" and "I've [crossposted]" in ori_comment.body:
                        results['bot_xp_original_comment'] = ori_comment.id
            elif "wiktionary" in cbody or "` doesn't look like anything" in cbody or "no results" in cbody or "couldn't find anything" in cbody:
                bot_replied_comments = []
                # We do need to modify this to accept more than one. 
                parent_lookup_comment = comment.parent()  # This is the comment with the actual lookup words.
                # print(parent_lookup_comment.id)
                parent_body = parent_lookup_comment.body
                parent_x_id = parent_lookup_comment.id
                # print(parent_x_id)
                if len(parent_body) != 0 and "[deleted]" not in parent_body:
                    # Now we want to create a list/dict linking the specific searches with their data.
                    lookup_results = lookup_matcher(parent_body, None)
                    '''
                    lookup_results = cjk_matcher(parent_body)
                    if len(lookup_results) == 0:  # There wasn't a CJ search. Maybe other?
                        lookup_results = other_language_matcher(parent_body)
                    '''
                    lookup_comments[cid] = lookup_results  # We add what specific things were searched
                    corresponding_comments[parent_lookup_comment.id] = lookup_results
                    parent_replies = parent_lookup_comment.replies

                    for reply in parent_replies:
                        # We need to double check why there are so many replies. 
                        if "Ziwen" in reply.body and reply.parent_id[3:] == parent_x_id:
                            bot_replied_comments.append(reply.id)
                    lookup_replies[parent_x_id] = bot_replied_comments
                    # print(lookup_replies[parent_x_id])
            elif "ethnologue" in cbody or "multitree" in cbody:
                results['bot_reference'] = cid
            elif "translation request tagged as 'unknown.'" in cbody:
                results['bot_unknown'] = cid
            elif "your translation request appears to be very long" in cbody:
                results['bot_long'] = cid
            elif "please+check+this+out" in cbody:  # This is the response to an invalid !identify command
                results['bot_invalid_code'] = cid
            elif "multiple defined languages" in cbody:
                results['bot_defined_multiple'] = cid
            elif "## Search results on r/translator" in cbody:
                results['bot_search'] = cid
            elif "they are working on a translation for this" in cbody:
                # Claim comment. we want to get a couple more values. 
                results['bot_claim_comment'] = cid
                
                claimer = re.search('(?<=u/)[\w-]+', cbody)  # Get the username of the claimer
                claimer = str(claimer.group(0)).strip()
                results['claim_user'] = claimer
                
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

                comment_datetime = datetime.datetime(num_year, num_month, num_day, num_hour, num_min, num_sec)
                utc_timestamp = calendar.timegm(comment_datetime.timetuple())  # Returns the time in UTC.
                time_difference = int(current_c_time - utc_timestamp)
                results['claim_time_diff'] = time_difference  # How long the thing has been claimed for.
        else:  # Processing comments by non-bot
            # Get a list of people who have contributed to helping. Unused at present.
            if KEYWORDS[3] in cbody or KEYWORDS[9] in cbody:
                list_of_translators.append(cauthor)

    if len(lookup_comments) != 0:  # We have lookup data
        results['bot_lookup'] = lookup_comments
        results['bot_lookup_correspond'] = corresponding_comments
        results['bot_lookup_replies'] = lookup_replies
    if len(list_of_translators) != 0:
        results['translators'] = list_of_translators
        
    return results  # This will be a dictionary with values. 


'''EDIT DETECTOR'''


def edit_finder():
    """A function to detect edits and changes of note in r/translator comments.
    comment_limit defines how many latest comments it will store in the cache."""

    comment_limit = 150

    comments = []
    comments += list(r.comments(limit=comment_limit))  # Only get the last comments.

    cleanup_database = False

    for comment in comments:

        current_time_com = time.time()

        cbody = comment.body
        cid = comment.id
        cedited = comment.edited  # Is a boolean
        ccreated = comment.created_utc

        time_diff = current_time_com - ccreated

        if time_diff > 3600 and cedited is False:  # The edit is older than an hour.
            continue

        # Strip punctuation to allow for safe SQL storage.
        cbody = cbody.replace("\n", " ")
        cbody = cbody.replace("\x00", " ")  # null character
        cbody = cbody.replace("(", " ")
        cbody = cbody.replace(")", " ")
        cbody = cbody.replace("[", " ")
        cbody = cbody.replace("]", " ")
        cbody = cbody.replace("'", " ")
        cbody = cbody.replace("\"", " ")

        # Let's retrieve any matching cbody in the cache.
        get_old_sql = "SELECT * FROM comment_cache WHERE id = '{}'".format(cid)  # Look for previous data for the com
        cursor_cache.execute(get_old_sql)
        old_matching_data = cursor_cache.fetchall()  # Returns a list that has a tuple.
        # print(old_matching_data)

        if len(old_matching_data) != 0:  # Test the stored data.
            force_change = False  # Way to override and force a change even if no difference in command.
            # old_cid = old_matching_data[0][0]
            old_cbody = old_matching_data[0][1]  # Retrieve the previously stored version of this.
            # print(old_cbody)
            # print(cbody)
            if cbody == old_cbody:  # The cached comment is the same as the current one.
                continue  # Do nothing.
            else:  # There is a change of some sort.
                logger.debug("[ZW] Edit Finder: An edit was detected. Saving...")
                
                if '`' in cbody:  # We detected a lookup change.
                    # First thing is compare the data in the two against what we have.
                    # total_matches = cjk_matcher(old_cbody) + other_language_matcher(old_cbody)
                    # Here we use the function to get a LIST of everything that's in between graves.
                    total_matches = lookup_matcher(old_cbody, None)
                    new_vars = komento_analyzer(get_submission_from_comment(cid))
                    # print(new_vars)
                    if 'bot_lookup_correspond' in new_vars:  # This will be a dictionary
                        new_overall_lookup_data = new_vars['bot_lookup_correspond']
                        if cid in new_overall_lookup_data:  # This comment is in our data
                            new_total_matches = new_overall_lookup_data[cid]
                            # Get the new matches
                            if set(new_total_matches) == set(total_matches):  # Are they the same?
                                # print("No change here!")
                                continue
                            else:
                                # print("There's a change.")
                                force_change = True
                    
                cleanup_database = True

                # Code to swap out the stored data.
                delete_command = "DELETE FROM comment_cache WHERE id = '{}'".format(cid)
                cursor_cache.execute(delete_command)
                cache_command = "INSERT INTO comment_cache VALUES ('" + cid + "', '" + cbody + "')"
                cursor_cache.execute(cache_command)
                conn_cache.commit()

                # We'll need code to edit the Ziwen file too IF there's a command that's new.
                # Now we want to delete from the old comments DB
                first_part = KEYWORDS[0:11]
                second_part = KEYWORDS[13:]

                main_keywords = first_part + second_part  # We want to omit crossposting ones
                
                for keyword in main_keywords:
                    if keyword in cbody and keyword not in old_cbody or force_change is True:
                        # This means the keyword is a NEW component of the edit
                        delete_comment_command = "DELETE FROM oldcomments WHERE id = '{}'".format(cid)
                        cur.execute(delete_comment_command)
                        sql.commit()
                        logger.debug("[ZW] Edit Finder: Removed the edited post from the comments database.")
        else:  # This is a comment that has not been stored.
            logger.debug("[ZW] Edit Finder: New comment to store. ")

            cleanup_database = True

            try:
                # Insert the comment into our cache.
                cache_command = "INSERT INTO comment_cache VALUES ('" + cid + "', '" + cbody + "')"
                cursor_cache.execute(cache_command)
                conn_cache.commit()
            except ValueError:  # Some sort of invalid character, don't write it.
                pass

    if cleanup_database:  # There's a need to clean it up.
        cleanup_command = 'DELETE FROM comment_cache WHERE id NOT IN (SELECT id FROM comment_cache ORDER BY id DESC LIMIT {})'
        cursor_cache.execute(cleanup_command.format(comment_limit))
        # Delete all but the last * comments.
        conn_cache.commit()
        
        
'''MAIN COMMANDS RUNTIME'''


def ziwen_posts():  # The main post filtering runtime for r/translator
    logger.debug('Fetching new r/{} posts...'.format(SUBREDDIT))

    current_time = int(time.time())  # This is the current time.

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
        opermalink = post.permalink  # This is the comments page, not the URL of an image
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
        cur.execute('SELECT * FROM oldposts WHERE ID=?', [oid])
        if cur.fetchone():
            # Post is already in the database
            logger.debug("[ZW] Posts: This post {} already exists in the processed database.".format(oid))
            continue
        cur.execute('INSERT INTO oldposts VALUES(?)', [oid])
        sql.commit()

        if css_check(oflair_css) is False and oflair_css is not None:
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

        if oflair_css in ["translated", "doublecheck", "missing", "inprogress"]:  # We don't want to mess with these
            continue  # Basically we only want to deal with untranslated posts

        # We're going to mark the original post author as someone different if it's a crosspost.
        if oauthor == "translator-BOT" and oflair_css != "community":
            komento_data = komento_analyzer(post)
            if 'bot_xp_comment' in komento_data:
                op_match = komento_data['bot_xp_op']
                oauthor = op_match

        if oauthor.lower() in GLOBAL_BLACKLIST:  # This user is on our blacklist. (not used much, more precautionary)
            post.mod.remove()
            action_counter(1, "Blacklisted posts")  # Write to the counter log
            logger.info("[ZW] Posts: Filtered a post out because its author u/{} is on my blacklist.".format(oauthor))
            continue

        if opost_age < CLAIM_PERIOD:  # If the post is younger than the claim period, we can act on it. (~8 hours)

            # If the post is under an hour, let's send notifications to people. Otherwise, we won't.
            # This is mainly for catching up with older posts - we want to process them but we don't want to send notes.
            if opost_age < 3600:
                okay_send = True
            else:
                okay_send = False

            returned_info = main_posts_filter(otitle)  # Applies a filtration test, see if it's okay. False if it is not

            if returned_info[0] is not False:  # Everything appears to be fine.
                otitle = returned_info[1]
                logger.info("[ZW] Posts: New post, {} by u/{}.".format(otitle, oauthor))
            else:  # This failed the test.

                # Remove this post, it failed all routines.
                post.mod.remove()
                post.reply(str(bad_title_commenter(title_text=otitle, author=oauthor)) + BOT_DISCLAIMER)

                # Write the title to the log.
                filter_num = returned_info[2]
                filter_log_writer(filtered_title=otitle, ocreated=ocreated, filter_type=filter_num)
                action_counter(1, "Removed posts")  # Write to the counter log
                logger.info("[ZW] Posts: Removed post that violated formatting guidelines. Title: {}".format(otitle))
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
                specific_sublanguage = title_data[7]  # This is a specific code, like ar-LB, unknown-cyrl
            except Exception as e_title:  # The title converter couldn't make sense of it. This should not happen.
                # Skip! This will result it in getting whatever AM gave it. (which may be nothing)
                # Send a message to let mods know
                title_error_entry = traceback.format_exc()
                error_log(title_error_entry + e_title)  # Save the error.

                # Report the post, so that mods know to take a look.
                fail_reason = ("(Ziwen) Crashed my title formatting routine. "
                               "Please check and assign this a language category.")
                post.report(fail_reason)
                logger.warning("[ZW] Posts: Title formatting routine crashed and encountered an exception.")

                continue  # Exit

            if suggested_source == suggested_target:  # If it's an English only post, filter it out.
                if "English" in suggested_source and "English" in suggested_target:
                    post.mod.remove()
                    post.reply(COMMENT_ENGLISH_ONLY.format(oauthor=oauthor))
                    filter_log_writer(filtered_title=otitle, ocreated=ocreated, filter_type="EE")
                    action_counter(1, "Removed posts")  # Write to the counter log
                    logger.info("[ZW] Posts: Removed an English-only post.")

            # We're going to consolidate the multiple updates into one Reddit push only.
            # This is a post that we have title data for.
            if suggested_css_text != "Generic":
                final_css_text = str(suggested_css_text)
                final_css_class = str(suggested_css)
                if "generic" in suggested_css:  # It's a supported language but not a supported flair.
                    # Write to the saved page
                    save_wiki(odate=ocreated, otitle=otitle, oid=oid, oflair_text=suggested_css_text, s_or_i=True,
                              oflair_new="")
            else:  # This is fully generic.
                # Set generic categories.
                final_css_text = "Generic"
                final_css_class = "generic"

                # Report the post, so that mods know to take a look.
                generic_reason = ("(Ziwen) Failed my title formatting routine. "
                                  "Please check and assign this a language category.")
                post.report(generic_reason)
                logger.info("[ZW] Posts: Title formatting routine couldn't make sense of '{}'.".format(otitle))

            # Check to see if we should add (Long) to the flair. There's a YouTube test and a text length test.
            if POSTS_KEYWORDS[0] in ourl or POSTS_KEYWORDS[1] in ourl:
                # This changes the CSS text to indicate if it's a long YouTube video
                try:  # Let's try to get the length of the video.
                    video_url = pafy.new(ourl)
                    # print(video_url)
                    if video_url.length > 300 and "t=" not in ourl:
                        # We make an exception if someone posts the exact timestamp
                        logger.info("[ZW] Posts: This is a long YouTube video.")
                        if final_css_text is not None:  # Let's leave None flair text alone
                            final_css_text += " (Long)"
                            post.reply(COMMENT_LONG + BOT_DISCLAIMER)
                except (ValueError, TypeError, UnicodeEncodeError, youtube_dl.utils.ExtractorError):
                    # The pafy routine cannot make sense of it.
                    logger.debug("[ZW] Posts: Unable to process this YouTube link.")
                else:
                    logger.warning("[ZW] Posts: Unable to process YouTube link at {}. Non-listed error.".format(ourl))
            if len(oselftext) > 1400:  # This changes the CSS text to indicate if it's a long wall of text
                logger.info("[ZW] Posts: This is a long piece of text.")
                if final_css_text is not None:  # Let's leave None flair text alone
                    final_css_text += " (Long)"
                    post.reply(COMMENT_LONG + BOT_DISCLAIMER)

            # This is a boolean. True if the user has posted too much and False if they haven't.
            user_posted_too_much = ziwen_notifier_over_frequency_checker(oauthor)

            # We don't want to send notifications if we're just testing. We also verify that user is not too extra.
            if MESSAGES_OKAY and okay_send and not user_posted_too_much:
                action_counter(1, "New posts")  # Write to the counter log
                if multiple_notifications is None and specific_sublanguage is None:  # This is a regular post.
                    ziwen_notifier(suggested_css_text, otitle, opermalink, oauthor, False)
                    # Now we notify people who are signed up on the list.
                elif multiple_notifications is not None and specific_sublanguage is None:
                    # This is a multiple post with a fixed number of languages or two non-English ones.
                    # Also called a "defined multiple language post"
                    # This part of the function also sends notifications if both languages are non-English
                    for notification in multiple_notifications:
                        multiple_language_text = converter(notification)[1]  # This is the language name for consistency
                        ziwen_notifier(multiple_language_text, otitle, opermalink, oauthor, False)
                    if final_css_class is "multiple":  # We wanna leave an advisory comment if it's a defined multiple
                        post.reply(COMMENT_DEFINED_MULTIPLE + BOT_DISCLAIMER)
                elif multiple_notifications is None and specific_sublanguage is not None:
                    # There is a specific subcategory for us to look at (ar-LB, unknown-cyrl) etc
                    # The notifier routine will be able to make sense of the hyphenated code.
                    # print("Specific sublanguage...")
                    ziwen_notifier(specific_sublanguage, otitle, opermalink, oauthor, False)
                    # Now we notify people who are signed up on the list.

            # If it's an unknown post, add an informative comment.
            if final_css_class == "unknown" and post.author.name != "translator-BOT":
                unknown_already = False
                if not unknown_already:
                    post.reply(COMMENT_UNKNOWN + BOT_DISCLAIMER)
                    logger.info("[ZW] Posts: Added the default 'Unknown' information comment. ")

            # Actually update the flair. Legacy version first.
            logger.info("[ZW] Posts: Set the post's flair to class '{}', with text '{}.'".format(final_css_class,
                                                                                                 final_css_text))
            # post.mod.flair(text=final_css_text, css_class=final_css_class)

            # New Redesign Version to update flair
            # Check the global template dictionary
            if final_css_class in POST_TEMPLATES.keys():
                output_template = POST_TEMPLATES[final_css_class]
                post.flair.select(output_template, final_css_text)

            # Finally, create an Ajo object and save it locally.
            if final_css_class not in ['meta', 'community']:
                pajo = Ajo(reddit.submission(id=post.id))  # Create an Ajo object, reload the post.
                ajo_writer(pajo)  # Save it to the local database


def ziwen_bot():  # The main runtime for r/translator
    logger.debug('Fetching new r/%s comments...' % SUBREDDIT)
    posts = []
    posts += list(r.comments(limit=MAXPOSTS))

    for post in posts:

        pid = post.id

        try:
            pauthor = post.author.name
        except AttributeError:
            # Author is deleted. We don't care about this post.
            continue

        if pauthor == USERNAME:  # Will not reply to my own comments
            continue

        cur.execute('SELECT * FROM oldcomments WHERE ID=?', [pid])
        if cur.fetchone():
            # Post is already in the database
            continue

        '''KEY ORIGINAL POST VARIABLES (NON-COMMENT) (o-)'''
        osubmission = post.submission  # Returns a submission object of the parent to work with
        oid = osubmission.id
        opermalink = osubmission.permalink
        otitle = osubmission.title
        oflair_text = osubmission.link_flair_text  # This is the linkflair text
        oflair_css = osubmission.link_flair_css_class  # This is the linkflair css class (lowercase)
        ocreated = post.created_utc  # Unix time when this post was created.
        osaved = post.saved  # We save verification requests so we don't work on them.
        requester = "Zamenhof"  # Dummy thing just to have data
        try:
            oauthor = osubmission.author.name  # Check to see if the author deleted their post already
        except AttributeError:  # No author found.
            continue

        if oid != VERIFIED_POST_ID:
            cur.execute('INSERT INTO oldcomments VALUES(?)', [pid])  # Enter it into the database of processed posts.
            sql.commit()

        pbody = post.body
        pbody_original = str(pbody)  # Create a copy with capitalization
        pbody = pbody.lower()

        # Calculate points for the person.
        if oflair_text is not None and osaved is not True:
            # We don't want to process it without the oflair text. Or if its vaerified comment 
            logger.debug("[ZW] Bot: Processing points for u/{}".format(pauthor))
            ziwen_points_tabulator(oid, oauthor, oflair_text, oflair_css, post)

        '''AJO CREATION'''
        # Create an Ajo object.
        if css_check(oflair_css) is True:

            # Check the database for the Ajo.
            oajo = ajo_loader(oid)

            if oajo is None:  # We couldn't find a stored dict, so we will generate it from the submission.
                logger.debug("[ZW] Bot: Couldn't find an AJO in the local database.")
                oajo = Ajo(osubmission)

            if oajo.is_bot_crosspost:
                komento_data = komento_analyzer(get_submission_from_comment(pid))
                if 'bot_xp_comment' in komento_data:
                    op_match = komento_data['bot_xp_op']
                    oauthor = op_match  # We're going to mark the original post author as someone different if crosspost.
                    requester = komento_data['bot_xp_requester']
        else:  # This is either a meta or a community post
            logger.debug("[ZW] Bot: Post appears to be either a meta or community post.")
            continue

        if not any(key.lower() in pbody for key in KEYWORDS) and not any(keyword in pbody for keyword in THANKS_KEYWORDS):
            # Does not contain our keyword
            logger.debug("[ZW] Bot: Post {} does not contain any operational keywords.".format(oid))
            continue

        if TESTING_MODE:  # This is a function to help stop the incessant commenting on older posts when testing
            current_time = int(time.time())  # This is the current time.
            if current_time - ocreated >= 3600:  # If the comment is older than an hour, ignore
                continue

        # Record to the counter with the keyword.
        for keyword in KEYWORDS:
            if keyword in pbody:
                action_counter(1, keyword)  # Write to the counter log

        '''REFERENCE COMMANDS (!identify, !page, !reference, !search, `lookup`)'''

        if KEYWORDS[4] in pbody or KEYWORDS[10] in pbody:  # This is the general !identify command

            determined_data = comment_info_parser(pbody, "!identify:")
            # This should return what was actually identified. Normally will be a Tuple or None
            if determined_data is None:  # The command is problematic. Wrong punctuation, not enough arguments
                logger.debug('[ZW] Bot: !identify data is invalid.')
                continue

            # Set some defaults just in case. These should be overwritten later.
            match_script = False
            language_code = ""
            language_name = ""

            # If it's not none, we got proper data.
            match = determined_data[0]
            advanced_mode = comment_info_parser(pbody, "!identify:")[1]
            language_country = None  # Default value
            original_language_name = str(oajo.language_name)  # Store the original language defined in the Ajo
            # This should return a boolean as to whether or not it's in advanced mode.

            logger.info("[ZW] Bot: COMMAND: !identify, from u/{}.".format(pauthor))

            if "+" not in match:  # This is just a regular single !identify command.
                if not advanced_mode:  # This is the regular results conversion
                    language_code = converter(match)[0]
                    language_name = converter(match)[1]
                    language_country = converter(match)[3]  # The country code for the language. Regularly none.
                    # is_supported = converter(match)[2]  # This tells us if it's a supported flair. Should be a boolean.
                    match_script = False
                elif advanced_mode:
                    if len(match) == 3:  # The advanced mode only accepts codes of a certain length.
                        language_data = lang_code_search(match, False)  # Run a search for the specific thing
                        language_code = match
                        language_name = language_data[0]
                        match_script = language_data[1]
                        if len(language_name) == 0:  # If there are no results from the advanced converter...
                            language_code = ""
                            # is_supported = False
                    elif len(match) == 4:  # This is a script, resets it to an Unknown state.
                        language_data = lang_code_search(match, True)  # Run a search for the specific script
                        if language_data is None:  # Probably an invalid script.
                            bad_script_reply = COMMENT_INVALID_SCRIPT + BOT_DISCLAIMER
                            post.reply(bad_script_reply.format(match))
                            logger.info("[ZW] Bot: But '{}' is not a valid script code. Skipping...".format(match))
                            continue
                        else:
                            language_code = match
                            language_name = language_data[0]
                            match_script = True
                            if len(language_name) == 0:  # If there are no results from the advanced converter...
                                language_code = ""
                    else:  # a catch all for advanced mode that ISN'T a 3 or 4-letter code.
                        post.reply(COMMENT_ADVANCED_IDENTIFY_ERROR + BOT_DISCLAIMER)
                        logger.info("[ZW] Bot: This is an invalid use of advanced !identify. Skipping this one...")
                        continue

                if not match_script:
                    if len(language_code) == 0:  # The converter didn't give us any results.
                        no_match_text = COMMENT_INVALID_CODE.format(match, opermalink)
                        post.reply(no_match_text + BOT_DISCLAIMER)
                        logger.info("[ZW] Bot: But '{}' has no match in the database. Skipping this...".format(match))
                        continue
                    elif len(language_code) != 0:  # This is a valid language.
                        # Insert code for updating country as well here.
                        if language_country is not None:  # There is a country code listed.
                            oajo.set_country(language_country)  # Add that code to the Ajo
                        else:  # There was no country listed, so let's reset the code to none.
                            oajo.set_country(None)
                        oajo.set_language(language_code, True)  # Set the language.
                        logger.info("[ZW] Bot: Changed flair to {}.".format(language_name))
                elif match_script:  # This is a script.
                    # if oflair_css == 'unknown':
                    # print(language_code)
                    oajo.set_script(language_code)
                    logger.info("[ZW] Bot: Changed flair to '{}', with an Unknown and script flair.".format(language_name))

                if not match_script and original_language_name != oajo.language_name or converter(oajo.language_name)[2] is False:
                    # Definitively a language. Let's archive this to the wiki.
                    # We've also made sure that it's not just a change of state.
                    save_wiki(odate=int(ocreated), otitle=otitle, oid=oid, oflair_text=original_language_name, s_or_i=False,
                              oflair_new=oajo.language_name)  # Write to the identified page
            else:  # This is an !identify command for multiple defined languages (e.g. !identify:ru+es+ja
                oajo.set_defined_multiple(match)
                logger.info("[ZW] Bot: Changed flair to a defined multiple one.")

            if KEYWORDS[3] not in pbody and KEYWORDS[9] not in pbody and MESSAGES_OKAY and oajo.status == "untranslated":
                # Just a check that we're not sending notifications AGAIN if the identified language is the same as orig
                # This makes sure that they're different languages. So !identify Chinese on Chinese won't send messages.
                if original_language_name != language_name:

                    if not match_script:  # This is not a script.
                        ziwen_notifier(language_name, otitle, opermalink, oauthor, True)
                        # Notify people on the list if the post hasn't already been marked as translated
                        # no use asking people to see something that's translated
                    else:  # This is a script... Adapt the proper format. (unknown-cyrl for example)
                        ziwen_notifier("unknown-{}".format(language_code), otitle, opermalink, oauthor, True)

            # Update the comments with the language reference comment
            if language_code not in ['unknown', "multiple", 'zxx', 'art', 'app'] and not match_script:

                komento_data = komento_analyzer(get_submission_from_comment(pid))

                if 'bot_unknown' in komento_data or 'bot_reference' in komento_data:

                    if 'bot_unknown' in komento_data:  # Previous Unknown template comment
                        unknown_default = komento_data['bot_unknown']
                        unknown_default = reddit.comment(id=unknown_default)
                        unknown_default.delete()  # Changed from remove
                        logger.debug(">> Deleted my default Unknown comment...")
                    if 'bot_invalid_code' in komento_data:
                        invalid_comment = komento_data['bot_invalid_code']
                        invalid_comment = reddit.comment(id=invalid_comment)
                        invalid_comment.delete()
                        logger.debug(">> Deleted my invalid code comment...")
                    if 'bot_reference' in komento_data:  # Previous reference template comment
                        previous_reference = komento_data['bot_reference']
                        previous_reference = reddit.comment(id=previous_reference)
                        previous_reference.delete()
                        logger.debug(">> Deleted my previous language reference comment...")

                    # Get the newest data
                    to_post = run_reference(language_code)
                    to_post = reference_reformatter(to_post)  # Simplify the information that's returned
                    if 'Ethnologue' in to_post or 'MultiTree' in to_post:
                        to_post = "*Another member of our community has identified your translation request as:*\n\n" + to_post
                        to_post += BOT_DISCLAIMER

                        # Add language reference data
                        osubmission.reply(to_post)
                        logger.info("[ZW] Bot: Added reference information for {}.".format(language_name))

        if KEYWORDS[0] in pbody:  # This is the basic paging !page function.

            logger.info("[ZW] Bot: COMMAND: !page, from u/{}.".format(pauthor))

            determined_data = comment_info_parser(pbody, "!page:")
            # This should return what was actually identified. Normally will be a Tuple or None
            if determined_data is None:  # The command is problematic. Wrong punctuation, not enough arguments
                logger.info('[ZW] Bot: >> !page data is invalid.')
                continue

            # CODE FOR A 14-DAY VERIFICATION SYSTEM
            poster = reddit.redditor(name=pauthor)
            current_time = int(time.time())
            if current_time - int(poster.created_utc) > 1209600:
                # checks to see if the user account is older than 14 days
                logger.debug("[ZW] Bot: > u/" + pauthor + "'s account is older than 14 days.")
            else:
                post.reply(COMMENT_PAGE_DISALLOWED.format(pauthor=pauthor) + BOT_DISCLAIMER)
                logger.info("[ZW] Bot: > However, u/" + pauthor + " is a new account. Replied to them and skipping...")
                continue

            if oflair_css == 'meta' or oflair_css == 'community':
                logger.debug("[ZW] Bot: > However, this is not a valid pageable post.")
                continue

            # Okay, it's valid, let's start processing data.
            page_results = page_multiple_detector(pbody)

            if page_results is None:  # There were no valid page results. (it is a placeholder)
                post.reply(COMMENT_NO_LANGUAGE.format(pauthor=pauthor, language_name="it",
                                                      language_code="") + BOT_DISCLAIMER)
                logger.info("[ZW] Bot: No one listed. Replied to the pager u/{} and skipping...".format(pauthor))
            else:  # There were results. Let's loop through them.
                for result in page_results:
                    language_code = result
                    language_name = converter(language_code)[1]

                    if post.submission.over_18:
                        is_nsfw = True
                    else:
                        is_nsfw = False

                    # Send a message via the paging system.
                    page_translators(language_code, language_name, pauthor, otitle, opermalink, oauthor, is_nsfw)

        if KEYWORDS[1] in pbody:  # This function returns data for character lookups with `character`.
            post_content = []
            logger.info("[ZW] Bot: COMMAND: `word` lookup, from u/{}.".format(pauthor))

            if pauthor == USERNAME:  # Don't respond to !search results from myself.
                continue

            if oflair_css in ['meta', 'community', 'missing']:
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
            komento_data = komento_analyzer(get_submission_from_comment(pid))
            if 'bot_lookup_correspond' in komento_data:  # This may have had a comment before.
                relevant_comments = komento_data['bot_lookup_correspond']

                # This returns a dictionary with the called comment as key. 
                for key in relevant_comments:
                    # print(key)
                    if key == pid:  # This is the key for our current comment.
                        # print("PREVIOUS RESPONSE FOUND")
                        if 'bot_lookup_replies' in komento_data:  # We try to find any corresponding bot replies
                            relevant_replies = komento_data['bot_lookup_replies']
                            # Previous replies will be a list
                            previous_responses = relevant_replies[pid]
                            for response in previous_responses:
                                earlier_comment = reddit.comment(id=response)
                                earlier_comment.delete()
                                logger.debug("[ZW] Bot: >>> Previous response deleted")
                                # We delete the earlier versions. 
            """
            # Manual MENTION override.
            # Note that the c_or_j_detector function will return FALSE if it detects any kana, kicking search to JA
            if c_or_j_detector(cj_matches) and 'chinese' in pbody or 'cantonese' in pbody or ':zh' in pbody:
                # Here we are making so you can call the command f/ other posts with keywords in the body of the comment
                search_language = "Chinese"
            elif 'japanese' in pbody or ':ja' in pbody:
                search_language = "Japanese"
            elif not c_or_j_detector(cj_matches):  # The detector found kana, so let's do Japanese.
                search_language = "Japanese"
            elif 'korean' in pbody or ':ko' in pbody:
                search_language = "Korean";"""

            if len(total_matches.keys()) == 0:
                # Checks to see if there's actually anything in between those two graves. 
                # If there's nothing, it skips it.
                logger.debug("[ZW] Bot: > Received a word lookup command, but found nothing. Skipping...")
                # We are just not going to reply if there is literally nothing found.
                continue

            for key, value in total_matches.items():
                if key in ['Chinese', 'Cantonese', 'Unknown', 'Classical Chinese', 'Han Characters', "Simplified Han",
                           "Traditional Han"]:
                    for match in total_matches[key]:
                        match_length = len(match)
                        if match_length not in (2, 3, 5, 6) and (match_length % 4) != 0:
                            to_post = zh_character(match)
                            post_content.append(to_post)
                        elif match_length in (2, 3, 5, 6):
                            find_word = str(match)
                            post_content.append(zh_word(find_word))
                        elif (match_length % 4) == 0:  # Has to be 8 (4 characters) because of Unicode?
                            find_chengyu = str(match)
                            search_term = simplify(
                                str(find_chengyu))  # Convert to simplify first because our dictionary uses simplified
                            try:
                                post_content.append(zh_chengyu(search_term))
                            except ConnectionRefusedError:  # If we have issues getting Chengyu
                                post_content.append(zh_word(search_term))  # Switch to just the term from zh_word

                        # Create a randomized wait time between requests.
                        wait_sec = random.randint(3, 12)
                        time.sleep(wait_sec)
                elif key in ['Japanese']:
                    for match in total_matches[key]:
                        match_length = len(str(match))
                        if match_length == 1:
                            to_post = ja_character(match)
                            post_content.append(to_post)
                        elif match_length > 1:
                            find_word = str(match)
                            post_content.append(ja_word(find_word))
                elif key in ['Korean']:
                    for match in total_matches[key]:
                        find_word = str(match)
                        post_content.append(ko_word(find_word))
                else:  # Wiktionary search
                    for match in total_matches[key]:
                        find_word = str(match)
                        wiktionary_results = wiktionary_search_new(find_word, key)
                        if wiktionary_results is not None:
                            post_content.append(wiktionary_results)

            # Join the content together.
            if len(post_content) > 0:  # If we have results lets post them
                # Join the resulting content together as a string.
                post_content = '\n\n'.join(post_content)
            else:  # No results, let's set it to None.
                post_content = None
                # For now we are simply not going to reply if there are no results.

            try:
                if post_content is not None:
                    post.reply(post_content + BOT_DISCLAIMER)
                    logger.info("[ZW] Bot: >> Looked up the term(s) in {}.".format(search_language))
                else:
                    logger.info("[ZW] Bot: >> No results found. Skipping...")
            except praw.exceptions.APIException:  # This means the comment is deleted.
                logger.debug("[ZW] Bot: >> Previous comment was deleted.")

        if KEYWORDS[7] in pbody:
            # the !reference command gets information from Ethnologue and other sources
            # to post as a reference
            determined_data = comment_info_parser(pbody, "!reference:")
            # This should return what was actually identified. Normally will be a Tuple or None
            if determined_data is None:  # The command is problematic. Wrong punctuation, not enough arguments
                logger.debug("[ZW] Bot: >> !reference data is invalid.")
                continue

            language_match = determined_data[0]
            logger.info("[ZW] Bot: COMMAND: !reference, from u/{}.".format(pauthor))
            post_content = run_reference(language_match)
            post.reply(post_content)
            logger.info("[ZW] Bot: Posted the reference results for '{}'.".format(language_match))

        if KEYWORDS[8] in pbody:  # The !search function looks for strings in other posts on r/translator

            determined_data = comment_info_parser(pbody, "!search:")
            # This should return what was actually identified. Normally will be a Tuple or None
            if determined_data is None:  # The command is problematic. Wrong punctuation, not enough arguments
                logger.debug("[ZW] Bot: >> !search data is invalid.")
                continue

            logger.info("[ZW] Bot: COMMAND: !search, from u/" + pauthor + ".")
            search_term = determined_data[0]

            google_url = []
            reddit_id = []
            reply_body = []

            for url in search(search_term + ' site:reddit.com/r/translator', num=4, stop=4):
                if 'comments' not in url:
                    continue
                google_url.append(url)
                oid = re.search('comments/(.*)/\w', url).group(1)
                reddit_id.append(oid)

            if len(google_url) == 0:

                post.reply(COMMENT_NO_RESULTS + BOT_DISCLAIMER)
                logger.info("[ZW] Bot: > There were no results for " + search_term + ". Moving on...")
                continue

            for oid in reddit_id:
                submission = reddit.submission(id=oid)
                s_title = submission.title
                s_date = datetime.datetime.fromtimestamp(submission.created).strftime('%Y-%m-%d')
                s_permalink = submission.permalink
                header_string = "#### [{}]({}) ({})\n\n".format(s_title, s_permalink, s_date)
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

                    if KEYWORDS[8] in comment.body.lower():  # This contains the !search string.
                        continue  # We don't want this.

                    # Format a comment body nicely.
                    c_body = comment.body

                    # Replace any keywords
                    for keyword in KEYWORDS:
                        c_body = c_body.replace(keyword, '')
                    c_body = str("\n> ".join(c_body.split("\n")))  # Indent the lines with Markdown >
                    c_votes = str(comment.score)  # Get the score of the comment

                    if search_term.lower() in c_body.lower():
                        comment_string = "##### Comment by u/" + c_author + " (+" + c_votes + "):\n\n>" + c_body
                        reply_body.append(comment_string)
                        continue
                    else:
                        continue
            reply_body = '\n\n'.join(reply_body)
            post.reply('## Search results on r/translator for "' + search_term + '":\n\n' + reply_body)
            logger.info("[ZW] Bot: > Posted my findings for the search term.")

        '''STATE COMMANDS (!doublecheck, !translated, !claim, !missing, short thanks)'''

        if KEYWORDS[9] in pbody:
            # !doublecheck function, it grabs the language list from the pre-existing flair of the post

            logger.info("[ZW] Bot: COMMAND: !doublecheck, from u/{}.".format(pauthor))

            if oflair_css in ['multiple', 'app']:
                # print(oajo.language_name)
                if isinstance(oajo.language_name, list):  # It is a defined multiple post.
                    # Try to see if there's data in the comment.
                    # If the comment is just the command, we take the parent comment and together check to see.
                    checked_text = str(pbody_original)
                    if len(pbody) < 12:  # This is just the command, so let's get the parent comment.
                        # Get the parent comment
                        parent_item = post.parent_id
                        if "t1" in parent_item:  # The parent is a comment
                            parent_comment = post.parent()
                            # Combine the two together.
                            checked_text = "{} {}".format(parent_comment.body, pbody_original)

                    comment_check = defined_multiple_comment_parser(checked_text, oajo.language_name)

                    # We have data, we can set the status as different in the flair.
                    if comment_check is not None:
                        # Start setting the flairs, from a list.
                        for language in comment_check[0]:
                            language_code = converter(language)[0]
                            oajo.set_status_multiple(language_code, "doublecheck")
                            logger.info("[ZW] Bot: > Marked {} in this defined multiple post as 'Needs Review.'".format(language))
                else:
                    logger.info("[ZW] Bot: > This is a general multiple post that is not eligible for status changes.")
            elif oflair_css in ['translated', 'meta', 'community', 'doublecheck']:
                logger.info("[ZW] Bot: > This post isn't eligible for double-checking. Skipping this one...")
                continue
            else:
                oajo.set_status("doublecheck")
                logger.info("[ZW] Bot: > Marked post as 'Needs Review.'")

            # Delete any claimed comment.
            komento_data = komento_analyzer(osubmission)
            if 'bot_claim_comment' in komento_data:
                claim_comment = komento_data['bot_claim_comment']
                claim_comment = reddit.comment(claim_comment)
                claim_comment.delete()

        if KEYWORDS[2] in pbody:  # This function picks up a !missing command and messages the OP about it.

            if not css_check(oflair_css):  # Basic check to see if this is something that can be acted on.
                continue

            logger.info("[ZW] Bot: COMMAND: !missing, from u/" + pauthor + ".")

            total_message = MSG_MISSING_ASSETS.format(oauthor=oauthor, opermalink=opermalink)
            reddit.redditor(oauthor).message('A message from r/translator regarding your translation request',
                                             total_message + BOT_DISCLAIMER)
            # Send a message to the OP about their post missing content.

            oajo.set_status("missing")
            logger.info("[ZW] Bot: > Marked a post by u/{} as missing assets and messaged them about it.".format(oauthor))

        if any(keyword in pbody for keyword in THANKS_KEYWORDS) and KEYWORDS[3] not in pbody and len(pbody) <= 20:
            # This processes simple thanks into translated, but leaves alone if it's an exception.
            # Has to be a short thanks, and not have !translated in the body.
            if oflair_css in ['meta', 'community', 'multiple', 'app']:
                continue

            if pauthor != oauthor:  # Is the author of the comment the author of the post?
                continue  # If not, continue, we don't care about this.

            # This should only be marked if it's untranslated. So it shouldn't affect
            if oajo.status is not "untranslated":
                continue

            # This should only be marked if it's not in an identified state, in case people respond to that command.
            if oajo.is_identified:
                continue

            exceptions_list = ['but', 'however', "no"]  # Did the OP have reservations?

            if any(exception in pbody for exception in exceptions_list):
                continue
            else:  # Okay, it really is a short thanks
                logger.info("[ZW] Bot: COMMAND: Short thanks from u/{}. Sending user a message...".format(pauthor))
                oajo.set_status("translated")
                reddit.redditor(oauthor).message('[Notification] A message regarding your translation request',
                                                 MSG_SHORT_THANKS_TRANSLATED.format(oauthor, opermalink) + BOT_DISCLAIMER)

        if KEYWORDS[14] in pbody:  # Claiming posts with the !claim command

            if oflair_css in ["translated", "doublecheck", "community", "meta", "multiple", "app"]:
                # We don't want to process these posts.
                continue

            if KEYWORDS[3] in pbody or KEYWORDS[9] in pbody:
                # This is for the scenario where someone edits their original claim comment with the translation
                # Then marks it as !translated or !doublecheck. We just want to ignore it then
                continue

            logger.info("[ZW] Bot: COMMAND: !claim, from u/" + pauthor + ".")
            current_time = int(time.time())
            utc_timestamp = datetime.datetime.utcfromtimestamp(current_time).strftime('%Y-%m-%d %H:%M:%S')
            claimed_already = False  # Boolean to see if it has been claimed as of now.

            komento_data = komento_analyzer(osubmission)

            if 'bot_claim_comment' in komento_data:  # Found an already claimed comment
                # claim_comment = komento_data['bot_claim_comment']
                claimer_name = komento_data['claim_user']
                remaining_time = komento_data['claim_time_diff']
                remaining_time_text = str(datetime.timedelta(seconds=remaining_time))
                if pauthor == claimer_name:  # If it's another claim by the same person listed...
                    post.reply("You've already claimed this post." + BOT_DISCLAIMER)
                    claimed_already = True
                    logger.info("[ZW] Bot: >> But this post is already claimed by the same user. Replied to claimer letting them know.")
                else:
                    post.reply(COMMENT_CURRENTLY_CLAIMED.format(claimer_name=claimer_name,
                                                                remaining_time=remaining_time_text) + BOT_DISCLAIMER)
                    claimed_already = True
                    logger.info("[ZW] Bot: >> But this post is already claimed. Replied to the claimer letting them know.")

            if not claimed_already:  # This has not yet been claimed. We can claim it for the user.
                oajo.set_status("inprogress")
                claim_note = osubmission.reply(COMMENT_CLAIM.format(claimer=pauthor, time=utc_timestamp,
                                                                    language_name=oajo.language_name) + BOT_DISCLAIMER)
                claim_note.mod.distinguish(sticky=True)  # Distinguish the bot's comment
                logger.info("[ZW] Bot: > Marked a post by u/{} as claimed and in progress.".format(oauthor))

        if KEYWORDS[3] in pbody:
            # This is a !translated function that messages people when their post has been translated.
            thanks_already = False
            translated_found = True

            logger.info("[ZW] Bot: COMMAND: !translated, from u/" + pauthor + ".")

            if oflair_css is None:  # If there is no CSS flair...
                oflair_css = 'generic'  # Give it a generic flair.

            if oflair_css in ['multiple', 'app']:
                if isinstance(oajo.language_name, list):  # It is a defined multiple post.
                    # Try to see if there's data in the comment.
                    # If the comment is just the command, we take the parent comment and together check to see.
                    checked_text = str(pbody_original)
                    if len(pbody) < 12:  # This is just the command, so let's get the parent comment.
                        # Get the parent comment
                        parent_item = post.parent_id
                        if "t1" in parent_item:  # The parent is a comment
                            parent_comment = post.parent()
                            # Combine the two together.
                            checked_text = "{} {}".format(parent_comment.body, pbody_original)

                    comment_check = defined_multiple_comment_parser(checked_text, oajo.language_name)

                    # We have data, we can set the status as different in the flair.
                    if comment_check is not None:
                        # Start setting the flairs, from a list.
                        for language in comment_check[0]:
                            language_code = converter(language)[0]
                            oajo.set_status_multiple(language_code, "translated")
                            logger.info("[ZW] Bot: > Marked {} in this defined multiple post as translated.".format(language))
                else:
                    logger.debug("[ZW] Bot: > This is a general multiple post that is not eligible for status changes.")
            elif oflair_css not in ["meta", "community", "translated"]:
                # Make sure we're not altering certain flairs.
                oajo.set_status("translated")
                logger.info("[ZW] Bot: > Marked post as translated.")

            komento_data = komento_analyzer(osubmission)

            if oajo.is_bot_crosspost is True:  # This is a crosspost, lets work some magic.
                if 'bot_xp_original_comment' in komento_data:
                    logger.debug("[ZW] Bot: >> Fetching original crosspost comment...")
                    original_comment = reddit.comment(komento_data['bot_xp_original_comment'])
                    original_comment_text = original_comment.body
                    original_comment_text = original_comment_text.split('---')[0].strip()
                    # We want to strip off the disclaimer
                    original_comment_text += "\n\n**Edit**: This crosspost has been marked as translated on r/translator." + BOT_DISCLAIMER
                    if "**Edit**" not in original_comment.body:  # Has this already been edited?
                        original_comment.edit(original_comment_text)
                        logger.debug("[ZW] Bot: >> Edited my original comment on the other subreddit to alert people.")

            if 'bot_long' in komento_data:  # Found a bot (Long) comment, delete it.
                long_comment = komento_data['bot_long']
                long_comment = reddit.comment(long_comment)
                long_comment.delete()
            if 'bot_claim_comment' in komento_data:  # Found an older claim comment, delete it.
                claim_comment = komento_data['bot_claim_comment']
                claim_comment = reddit.comment(claim_comment)
                claim_comment.delete()
            if 'op_thanks' in komento_data:  # OP has thanked someone in the thread before.
                thanks_already = True
                translated_found = False

            if translated_found and not thanks_already and oflair_css not in ['multiple', 'app']:
                if not TESTING_MODE and pauthor != oauthor:
                    translated_message(oauthor=oauthor, opermalink=opermalink)  # Sends them a notification message

        '''MODERATOR-ONLY COMMANDS (!delete, !reset, !note, !set)'''

        if KEYWORDS[13] in pbody:  # This is to allow OP or mods to !delete crossposts
            if not oajo.is_bot_crosspost:  # If this isn't actually a crosspost..
                continue
            else:  # This really is a crosspost.
                logger.info("[ZW] Bot: COMMAND: !delete from u/{}".format(pauthor))
                if pauthor == oauthor or pauthor == requester or is_mod(pauthor):
                    osubmission.mod.remove()  # We'll use remove for now -- can switch to delete() later.
                    logger.info("[ZW] Bot: >> Removed crosspost.")

        if KEYWORDS[15] in pbody:  # !reset command, to revert a post back to as if it were freshly processed

            if is_mod(pauthor) or pauthor == oauthor:  # Check if is a mod or the OP
                logger.info("[ZW] Bot: COMMAND: !reset, from user u/{}.".format(pauthor))
                oajo.reset(otitle)
                logger.info("[ZW] Bot: > Reset everything for the designated post.")
            else:
                continue

        if KEYWORDS[6] in pbody:
            # the !note command saves posts which are not CSS/template supported so they can be used as reference
            if not is_mod(pauthor):  # Check to see if the person calling this command is a moderator
                continue
            match = comment_info_parser(pbody, "!note:")[0]
            language_name = converter(match)[1]
            logger.info("[ZW] Bot: COMMAND: !note, from moderator u/{}.".format(pauthor))
            save_wiki(odate=int(ocreated), otitle=otitle, oid=oid, oflair_text=language_name, s_or_i=True,
                      oflair_new="")  # Write to the saved page

        if KEYWORDS[5] in pbody:
            # !set is a mod-accessible means of setting the post flair.
            # It removes the comment (through AM) so it looks like nothing happened.
            if not is_mod(pauthor):  # Check to see if the person calling this command is a moderator
                continue

            set_data = comment_info_parser(pbody, "!set:")

            if set_data is not None:  # We have data.
                match = set_data[0]
                reset_state = set_data[1]
            else:  # Invalid command (likely did not include a language)
                continue

            logger.info("[ZW] Bot: COMMAND: !set, from moderator u/{}.".format(pauthor))

            language_code = converter(match)[0]
            language_country = converter(match)[3]

            if language_country is not None:  # There is a country code listed.
                oajo.set_country(language_country)  # Add that code to the Ajo

            if reset_state:  # Advanced !set mode, we set it to untranslated.
                oajo.set_status('untranslated')

            if "+" not in set_data[0]:  # This is a standard !set
                # Set the language to the Ajo
                oajo.set_language(language_code)
                komento_data = komento_analyzer(get_submission_from_comment(pid))
                if 'bot_unknown' in komento_data:  # Delete previous Unknown template comment
                    unknown_default = komento_data['bot_unknown']
                    unknown_default = reddit.comment(id=unknown_default)
                    unknown_default.delete()  # Changed from remove
                    logger.debug("[ZW] Bot: >> Deleted my default Unknown comment...")
                logger.info("[ZW] Bot: > Updated the linkflair tag to '{}'.".format(language_code))
            else:  # This is a defined multiple !set
                oajo.set_defined_multiple(set_data[0])
                logger.info("[ZW] Bot: > Updated the post to a defined multiple one.")

        # Push the FINAL UPDATE TO REDDIT
        if oflair_css not in ["community", "meta"]:  # There's nothing to change for these
            oajo.update_reddit()  # Push all changes to the server
            ajo_writer(oajo)  # Write the Ajo to the local database
            logger.debug("[ZW] Bot: Ajo updated and saved to the local database.")
            user_statistics_writer(pbody, pauthor)  # Record data on user commands.
            logger.debug("[ZW] Bot: Recorded user commands in database.")


def progress_checker():  # This is to make sure in-progress posts don't linger.
    search_query = 'flair:"in progress"'  # Get the posts that are still marked as in progress
    search_results = r.search(search_query, time_filter='week', sort='new')
    for post in search_results:  # Now we process the ones that are stil marked as in progress to reset them.

        oflair_css = post.link_flair_css_class
        opermalink = post.permalink

        if oflair_css != 'inprogress':  # If it's not actually an inprogress one, let's skip it.
            continue
        else:
            suggested_css_text = post.link_flair_text.split(" ")[2]  # Will include brackets [KA]

        # Expand all the comments.
        post.comments.replace_more(limit=0)
        comments = post.comments

        for comment in comments:  # First we try to identify the claimer and time of claiming.
            if comment.author is None:  # Skip it if it's none.
                continue

            pbody = comment.body

            if '**Claimer:** u/' in pbody and comment.author.name == 'translator-BOT':
                # This is a claimed comment on a post that is still outstanding.
                current_time = time.time()
                claimed_time = pbody.split(" at ")[1]
                claimed_time = claimed_time.split(" UTC")[0]
                claimed_date = claimed_time.split(" ")[0]
                claimed_time = claimed_time.split(" ")[1]

                num_year = int(claimed_date.split("-")[0])
                num_month = int(claimed_date.split("-")[1])
                num_day = int(claimed_date.split("-")[2])

                num_hour = int(claimed_time.split(":")[0])
                num_min = int(claimed_time.split(":")[1])
                num_sec = int(claimed_time.split(":")[2])

                comment_datetime = datetime.datetime(num_year, num_month, num_day, num_hour, num_min, num_sec)
                utc_timestamp = calendar.timegm(comment_datetime.timetuple())  # Returns the time in UTC.
                time_difference = int(current_time - utc_timestamp)

                if time_difference > CLAIM_PERIOD:  # we want to switch this to determining time from the comment !claim.
                    comment.delete()  # Delete the claim comment of the bot
                    simple_css = suggested_css_text.lower()[1:-1]  # convert this into a simple css code
                    simple_css_tuple = converter(simple_css)  # Returns a tuple with Code, Name, Supported (boolean).
                    new_text = simple_css_tuple[1]
                    if not simple_css_tuple[2]:  # If this is not a supported language...
                        # post.mod.flair(text=new_text, css_class='generic')
                        output_template = POST_TEMPLATES["generic"]
                    else:  # This is a supported language. We use the flair template for it.
                        # post.mod.flair(text=new_text, css_class=simple_css)
                        output_template = POST_TEMPLATES[simple_css]

                    post.flair.select(output_template, new_text)
                    logger.info("[ZW] Progress Checker: >> Reset the flair of "
                                "{} due to the claim's expiration.".format(opermalink))


'''LESSER COMMANDS RUNTIMES'''


def cc_ref():  # The secondary runtime for the Chinese language subreddits
    multireddit = reddit.multireddit(USERNAME, 'chinese')
    posts = []
    posts += list(multireddit.comments(limit=MAXPOSTS))

    for post in posts:

        pid = post.id

        cur.execute('SELECT * FROM oldcomments WHERE ID=?', [pid])
        if cur.fetchone():
            # Post is already in the database
            continue

        pbody = post.body
        pbody = pbody.lower()

        if not any(key.lower() in pbody for key in KEYWORDS):
            # Does not contain our keyword
            continue

        cur.execute('INSERT INTO oldcomments VALUES(?)', [pid])
        sql.commit()

        if KEYWORDS[1] in pbody:
            post_content = []
            # This basically checks to make sure it's actually a Chinese/Japanese character.
            # It will return nothing if it is something else.
            matches = re.findall('`([\u2E80-\u9FFF]+)`', pbody,
                                 re.DOTALL)
            # match_length = len(str(matches))
            tokenized_list = []
            if len(matches) == 0:
                continue
            for match in matches:  # We are going to break this up
                if len(match) >= 2:  # Longer than bisyllabic?
                    new_matches = zhja_tokenizer(simplify(match), "zh")
                    for new_word in new_matches:
                        tokenized_list.append(new_word)
                else:
                    tokenized_list.append(match)
            for match in tokenized_list:
                match_length = len(str(match))
                if match_length != 2 and match_length != 3 and match_length != 5 and match_length != 6 and (
                            match_length % 4) != 0:
                    to_post = zh_character(match)
                    post_content.append(to_post)
                elif match_length == 2 or match_length == 3 or match_length == 5 or match_length == 6:
                    find_word = str(match)
                    post_content.append(zh_word(find_word))
                elif (match_length % 4) == 0:  # Has to be 8 (4 characters) because of Unicode?
                    find_chengyu = str(match)
                    search_term = simplify(
                        str(find_chengyu))  # Convert to simplify first because our dictionary uses simplified
                    post_content.append(zh_chengyu(search_term))
            post_content = '\n\n'.join(post_content)
            post.reply(post_content + BOT_DISCLAIMER)
            logger.info("[ZW] CC_REF: Replied to a lookup request for {} on a Chinese language subreddit.".format(tokenized_list))


def ziwen_startup():
    # A simple function to group together common activities that need to be run on an occasional basis.

    global GLOBAL_BLACKLIST
    GLOBAL_BLACKLIST = blacklist_checker_run_once()  # We populate our blacklist. We only need to fetch once at start.
    logger.debug("[ZW] # Current global blacklist retrieved: {} users".format(len(GLOBAL_BLACKLIST)))

    global POST_TEMPLATES
    POST_TEMPLATES = redesign_template_retriever()
    logger.debug("[ZW] # Current post templates retrieved: {} templates".format(len(POST_TEMPLATES.keys())))

    global VERIFIED_POST_ID
    VERIFIED_POST_ID = get_latest_verified_thread()  # Get the last verification thread's ID and store it.
    logger.debug("[ZW] # Current verification post found: https://redd.it/{}\n\n".format(VERIFIED_POST_ID))

    global ZW_USERAGENT
    ZW_USERAGENT = get_random_useragent()  # Pick a random useragent from our list.
    logger.debug("[ZW] # Current user agent: {}".format(ZW_USERAGENT))

    global MOST_RECENT_OP
    MOST_RECENT_OP = ziwen_notifier_most_recent()

    point_worth_cacher()  # Update the points cache
    logger.debug("[ZW] Points cache updated.")


'''INITIAL VARIABLE SET-UP'''
# We start the bot with a couple of routines to populate the data from our wiki.
CYCLES = 0
ziwen_startup()
logger.info("[ZW] Bot routine starting up...")


'''RUNNING THE BOT'''
# Below is the actual loop that runs the functions of the bot.
# For subreddits other than r/translator, it runs specific sub-functions instead of the whole thing.
while True:
    # noinspection PyBroadException
    try:
        # First it processes the titles of new posts
        ziwen_posts()
        # Then it checks for any edits to comments.
        edit_finder()
        # Next the bot runs all sub-functions on its main subreddit, r/translator
        ziwen_bot()
        # Then it checks its messages (generally for new subscription lookups)
        ziwen_messages()
        # Finally checks for posts that are in progress.
        progress_checker()

        if TESTING_MODE is False:  # Disable other subreddit functions if testing on r/trntest
            logger.debug("[ZW] Main: Searching other subreddits...")
            verification_parser()  # First the bot checks if there are any new requests for verification.
            cc_ref()  # Finally the bot runs searches on Chinese subreddits

        CYCLES += 1
    except Exception as e:  # Error catching routine
        error_entry = traceback.format_exc()
        if any(keyword in error_entry for keyword in CONNECTION_KEYWORDS):
            for keyword in CONNECTION_KEYWORDS:
                if keyword in error_entry:  # We want to print the precise error we have.
                    logger.debug("[ZW] Main: > Connection Error: {}".format(keyword))
        else:
            error_log(error_entry)  # Save the error to a log.
            logger.error("[ZW] Main: > Logged this error.")

    if CYCLES >= CLEANCYCLES:
        logger.debug('[ZW] Main: Cleaning database and updating blacklist...')
        database_processed_cleaner()  # Clean the comments that have been processed.
        ziwen_startup()  # Update the global variables again.
        CYCLES = 0  # Reset the number of cycles.

    logger.debug('Running again in %d seconds. \n' % WAIT)
    time.sleep(WAIT)