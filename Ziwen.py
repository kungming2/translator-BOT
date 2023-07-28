#!/usr/bin/env python3
"""
Ziwen [ZW] is the main active component of u/translator-BOT, servicing r/translator and other communities.

Ziwen posts comments and sends messages and also moderates and keeps r/translator organized. It also provides community
members with useful reference information and enforces the community's formatting guidelines.
"""

import calendar
import datetime
import os
import random
import re
import sqlite3  # For processing and accessing the databases.
import time
import traceback  # For documenting errors that are encountered.
import sys
from typing import Dict, List

import praw  # Simple interface to the Reddit API that also handles rate limiting of requests.
import prawcore  # The base module praw for error logging.

import jieba  # Segmenter for Mandarin Chinese.
import MeCab  # Advanced segmenter for Japanese.
import tinysegmenter  # Basic segmenter for Japanese; not used on Windows.

import googlesearch
import psutil
import requests

from korean_romanizer.romanizer import Romanizer
from lxml import html
from mafan import simplify
from wiktionaryparser import WiktionaryParser

from Ajo import Ajo, ajo_defined_multiple_comment_parser, ajo_writer, ajo_loader
from _languages import (
    VERSION_NUMBER_LANGUAGES,
    language_mention_search,
    converter,
    bad_title_reformat,
    comment_info_parser,
    title_format,
    lang_code_search,
    main_posts_filter,
)
from _language_consts import (
    MAIN_LANGUAGES,
    ISO_MACROLANGUAGES,
    CJK_LANGUAGES,
)
from _login import USERNAME, ZIWEN_APP_ID, ZIWEN_APP_SECRET, PASSWORD
from _config import (
    FILE_ADDRESS_CACHE,
    logger,
    KEYWORDS,
    SUBREDDIT,
    FILE_ADDRESS_FILTER,
    BOT_DISCLAIMER,
    FILE_ADDRESS_ERROR,
    FILE_ADDRESS_MAIN,
    FILE_ADDRESS_AJO_DB,
    FILE_ADDRESS_MECAB,
    action_counter,
    time_convert_to_string,
    get_random_useragent,
)
from _responses import (
    COMMENT_ADVANCED_IDENTIFY_ERROR,
    COMMENT_BAD_TITLE,
    COMMENT_CLAIM,
    COMMENT_CURRENTLY_CLAIMED,
    COMMENT_DEFINED_MULTIPLE,
    COMMENT_PAGE_DISALLOWED,
    COMMENT_UNKNOWN,
    COMMENT_NO_LANGUAGE,
    COMMENT_NO_RESULTS,
    COMMENT_ENGLISH_ONLY,
    COMMENT_INVALID_REFERENCE,
    COMMENT_INVALID_CODE,
    COMMENT_INVALID_SCRIPT,
    COMMENT_VERIFICATION_RESPONSE,
    COMMENT_LONG,
    MSG_RESTORE_TEXT_TEMPLATE,
    MSG_RESTORE_LINK_FAIL,
    MSG_RESTORE_TEXT_FAIL,
    MSG_RESTORE_NOT_ELIGIBLE,
    MSG_MISSING_ASSETS,
    MSG_WIKIPAGE_FULL,
    MSG_SHORT_THANKS_TRANSLATED,
    MSG_TRANSLATED,
)
from ja_processing import ja_character, ja_word
from notifier import (
    notifier_over_frequency_checker,
    notifier_page_multiple_detector,
    notifier_page_translators,
    record_activity_csv,
    ziwen_messages,
    ziwen_notifier,
)
from zh_processing import zh_character, zh_word

"""
UNIVERSAL VARIABLES

These variables (all denoted by UPPERCASE names) are variables used by many functions in Ziwen. These are important
as they define many of the basic functions of the bot.
"""

BOT_NAME = "Ziwen"
VERSION_NUMBER = "1.8.27"
USER_AGENT = (
    f"{BOT_NAME} {VERSION_NUMBER}, a notifications messenger, general commands monitor, and moderator for r/translator. "
    "Written and maintained by u/kungming2."
)
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

"""KEYWORDS LISTS"""
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
CACHED_MULTIPLIERS: Dict[str, int] = {}


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
        logger.info(f"[ZW] Startup: Starting up in TESTING MODE for r/{SUBREDDIT}...")

# Connecting to the Reddit API via OAuth.
logger.info(f"[ZW] Startup: Logging in as u/{USERNAME}...")
reddit = praw.Reddit(
    client_id=ZIWEN_APP_ID,
    client_secret=ZIWEN_APP_SECRET,
    password=PASSWORD,
    user_agent=USER_AGENT,
    username=USERNAME,
)
r = reddit.subreddit(SUBREDDIT)
logger.info(
    f"[ZW] Startup: Initializing {BOT_NAME} {VERSION_NUMBER} for r/{SUBREDDIT} with languages module {VERSION_NUMBER_LANGUAGES}."
)

"""
MAINTENANCE FUNCTIONS

These functions are run at Ziwen's startup and also occasionally in order to refresh their information. Most of them
fetch data from r/translator itself or r/translatorBOT for internal variables.

Maintenance functions are all prefixed with `maintenance` in their name.
"""


def maintenance_template_retriever() -> Dict[str, str]:
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
    return new_template_ids if len(new_template_ids.keys()) != 0 else {}


def maintenance_most_recent() -> List[str]:
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
    posts = list(r.new(limit=100))

    # Process through them - we really only care about the username and the time.
    for post in posts:
        ocreated = int(post.created_utc)  # Unix time when this post was created.

        try:
            oauthor = post.author.name
        except AttributeError:
            # Author is deleted. We don't care about this post.
            continue

        # If the time of the post is after our limit, add it to our list.
        if ocreated > current_vaqt_day_ago and oauthor != "translator-BOT":
            most_recent.append(oauthor)

    # Return the list
    return most_recent


def maintenance_get_verified_thread() -> str | None:
    """
    Function to quickly get the Reddit ID of the latest verification thread on startup.
    This way, the ID of the thread does not need to be hardcoded into Ziwen.

    :return verification_id: The Reddit ID of the newest verification thread as a string.
    """

    # Search for the latest verification thread.
    search_term = "title:verified AND flair:meta"

    # Note that even in testing ('trntest') we will still search r/translator for the thread.
    search_results = reddit.subreddit("translator").search(
        search_term, time_filter="year", sort="new", limit=1
    )

    # Iterate over the results generator to get the ID.
    verification_id = None
    for post in search_results:
        verification_id = post.id

    return verification_id


def maintenance_blacklist_checker() -> List[str]:
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


def maintenance_database_processed_cleaner() -> None:
    """
    Function that cleans up the database of processed comments, but not posts (yet).

    :return: Nothing.
    """

    pruning_command = "DELETE FROM oldcomments WHERE id NOT IN (SELECT id FROM oldcomments ORDER BY id DESC LIMIT ?)"
    cursor_main.execute(pruning_command, [MAXPOSTS * 10])
    conn_main.commit()


"""
KOMENTO ANALYZER

Similar to the Ajo in its general purpose, a Komento object (which is a dictionary) provides anchors and references
for the bot to check its own output and commands as well.

Komento-related functions are all prefixed with `komento` in their name. 
"""


def komento_submission_from_comment(comment_id: str) -> praw.reddit.models.Submission:
    """
    Returns the parent submission as an object from a comment ID.

    :param comment_id: The Reddit ID for the comment, expressed as a string.
    :return: Returns the PRAW Submission object of the parent post.
    """

    main_comment = reddit.comment(id=comment_id)  # Convert ID into comment object.
    main_submission = main_comment.link_id[3:]  # Strip the t3_ from front.
    # Get actual PRAW submission object.
    return reddit.submission(id=main_submission)


def komento_analyzer(reddit_submission: praw.reddit.models.Submission):
    """
    A function that returns a dictionary containing various things that Ziwen checks against. It indexes comments with
    specific keys in the dictionary so that Ziwen can access them directly and easily.

    :param reddit_submission:
    :return: A dictionary with keyed values according to the bot's and user comments.
    """

    try:
        oauthor = reddit_submission.author.name
    except AttributeError:
        return {}  # Changed from None, the idea is to return an empty dictionary

    # Flatten the comments into a list.
    # Replace all MoreComments with regular comments.
    reddit_submission.comments.replace_more(limit=None)
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
                # Get just the post ID
                original_post_id = original_post.split("comments/")[1].strip()[0:6]
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
                # This is the comment with the actual lookup words.
                parent_lookup_comment = comment.parent()

                parent_body = parent_lookup_comment.body
                parent_x_id = parent_lookup_comment.id

                if len(parent_body) != 0 and "[deleted]" not in parent_body:
                    # Now we want to create a list/dict linking the specific searches with their data.
                    lookup_results = lookup_matcher(parent_body, None)
                    # We add what specific things were searched
                    lookup_comments[cid] = lookup_results
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
            elif "please+check+this+out" in cbody:
                # This is the response to an invalid !identify command
                results["bot_invalid_code"] = cid
            elif "multiple defined languages" in cbody:
                results["bot_defined_multiple"] = cid
            elif "## Search results on r/translator" in cbody:
                results["bot_search"] = cid
            elif "they are working on a translation for this" in cbody:
                # Claim comment. we want to get a couple more values.
                results["bot_claim_comment"] = cid
                # Get the username of the claimer
                claimer = re.search(r"(?<=u/)[\w-]+", cbody)
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
                # Returns the time in UTC.
                utc_timestamp = calendar.timegm(comment_datetime.timetuple())
                time_difference = int(current_c_time - utc_timestamp)
                # How long the thing has been claimed for.
                results["claim_time_diff"] = time_difference
        elif KEYWORDS.translated in cbody or KEYWORDS.doublecheck in cbody:
            # Processing comments by non-bot
            # Get a list of people who have contributed to helping. Unused at present.
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


def points_worth_determiner(language_name: str) -> int:
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
    # Look for the dictionary key of the language name.
    final_point_value = CACHED_MULTIPLIERS.get(language_name)

    if final_point_value is not None:  # It's cached.
        logger.debug(
            f"[ZW] Points determiner: {language_name} value in the cache: {final_point_value}"
        )
        return final_point_value  # Return the multipler - no need to go to the wiki.
    # Not found in the cache. Get from the wiki.
    # Fetch the wikipage.
    overall_page = reddit.subreddit(SUBREDDIT).wiki[language_name.lower()]
    try:  # First see if this page actually exists
        overall_page_content = str(overall_page.content_md)
        last_month_data = overall_page_content.rsplit("\n", maxsplit=1)[-1]
    except prawcore.exceptions.NotFound:  # There is no such wikipage.
        logger.debug("[ZW] Points determiner: The wiki page does not exist.")
        last_month_data = "2017 | 08 | [Example Link] | 1%"
        # Feed it dummy data if there's nothing... this language probably hasn't been done in a while.
    try:  # Try to get the percentage from the page
        total_percent = str(last_month_data.split(" | ")[3])[:-1]
        total_percent = float(total_percent)
    except IndexError:
        # There's a page but there is something wrong with data entered.
        logger.debug("[ZW] Points determiner: There was a second error.")
        total_percent = float(1)

    # Calculate the point multiplier.
    # The precise formula here is: (1/percentage)*35
    try:
        raw_point_value = 35 * (1 / total_percent)
        final_point_value = int(round(raw_point_value))
    except ZeroDivisionError:  # In case the total_percent is 0 for whatever reason.
        final_point_value = 20
    final_point_value = min(final_point_value, 20)
    logger.debug(
        f"[ZW] Points determiner: Multiplier for {language_name} is {final_point_value}"
    )

    # Add to the cached values, so we don't have to do this next time.
    CACHED_MULTIPLIERS.update({language_name: final_point_value})

    # Write data to the cache so that it can be retrieved later.
    current_zeit = time.time()
    month_string = datetime.datetime.fromtimestamp(current_zeit).strftime("%Y-%m")
    insert_data = (month_string, language_name, final_point_value)
    cursor_cache.execute("INSERT INTO multiplier_cache VALUES (?, ?, ?)", insert_data)
    conn_cache.commit()

    return final_point_value


def points_worth_cacher() -> None:
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


def points_tabulator(
    oid: str,
    oauthor: str,
    oflair_text: str,
    oflair_css: str,
    comment: praw.reddit.models.Submission,
) -> None:
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

    if pauthor in ["AutoModerator", "translator-BOT"]:
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
            return
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
        f"[ZW] Points tabulator: {language_name}, {str(language_multiplier)} multiplier"
    )

    # This is in case the commenter is not actually the translator
    final_translator = ""
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
                f"[ZW] Points tabulator: Actual translator: u/{final_translator} for {parent_post}"
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
                    f"[ZW] Points tabulator: Actual translator: u/{final_translator}, {parent_post}"
                )
                final_translator_points += 1 + (1 * language_multiplier)
                points += 1  # Give the cleaner-upper a point.
            except AttributeError:  # Parent is a post.
                logger.debug("[ZW] Points tabulator: Parent of this comment is a post.")
        else:
            logger.debug(
                f"[ZW] Points tabulator: Seems to be a solid !translated comment by u/{pauthor}."
            )
            translator_to_add = pauthor
            points += 1 + (1 * language_multiplier)
    elif len(pbody) < 13 and "!translated" in pbody:
        # It's marking someone else's translation as translated. We want to get the parent.
        logger.debug(
            f"[ZW] Points tabulator: This is a cleanup !translated comment by u/{pauthor}."
        )
        parent_comment = comment.parent()
        try:  # Check if it's a comment:
            parent_post = parent_comment.parent_id
            final_translator = parent_comment.author.name
            logger.debug(
                f"[ZW] Points tabulator: Actual translator: u/{final_translator} for {parent_post}"
            )
            final_translator_points += 1 + (1 * language_multiplier)
            if final_translator != pauthor:
                # Make sure it isn't someone just calling it on their own here
                points += 1  # We give the person who called the !translated comment a point for cleaning up
        except AttributeError:  # Parent is a post.
            logger.debug("[ZW] Points tabulator: Parent of this comment is a post.")
        points += 1  # Give the cleaner-upper a point.
    elif len(pbody) > 13 and "!translated" in pbody and pauthor == oauthor:
        # The OP marked it !translated, but with a longer comment.
        logger.debug(
            f"[ZW] Points tabulator: A !translated comment by the OP u/{pauthor} for someone else?."
        )
        parent_comment = comment.parent()
        try:  # Check if it's a comment:
            parent_post = parent_comment.parent_id
            final_translator = parent_comment.author.name
            if final_translator != oauthor:
                logger.debug(
                    f"[ZW] Points tabulator: Actual translator: u/{final_translator}, {parent_post}"
                )
                final_translator_points += 1 + (1 * language_multiplier)
        except AttributeError:  # Parent is a post.
            logger.debug("[ZW] Points tabulator: Parent of this comment is a post.")

    if len(pbody) > 120 and pauthor != oauthor:
        # This is an especially long comment...But it's well regarded
        points += 1 + int(round(0.25 * language_multiplier))

    keyword_points = {
        KEYWORDS.identify: 3,
        KEYWORDS.id: 3,
        KEYWORDS.back_quote: 2,
        KEYWORDS.missing: 2,
        KEYWORDS.claim: 1,
        KEYWORDS.page: 1,
        KEYWORDS.search: 1,
        KEYWORDS.reference: 1,
    }

    for keyword, point in keyword_points.items():
        if keyword in pbody:
            points += point

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
                f"[ZW] Points tabulator: Actual translator: u/{final_translator} for {parent_post}"
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

    if any(pauthor in s for s in points_status):
        # Check if author is already listed in our list.
        for point_status in points_status:  # Add their points if so.
            if point_status[0] == pauthor:  # Get their username
                point_status[1] += points  # Add the running total of points
    else:
        # They're not in the list. Just add them.
        points_status.append([pauthor, points])

    if final_translator_points != 0:  # If we have another person's score to put in...
        points_status.append([final_translator, final_translator_points])
        translator_to_add = final_translator

    if points == 0 and final_translator_points == 0:
        return

    # Code to strip out any points = 0
    points_status = [x for x in points_status if x[1] != 0]

    if translator_to_add is not None:  # We can record this information in the Ajo.
        cajo = ajo_loader(oid, cursor_ajo, POST_TEMPLATES, reddit)
        if cajo is not None:
            cajo.add_translators(translator_to_add)  # Add the name to the Ajo.
            ajo_writer(cajo, cursor_ajo, conn_ajo)

    for entry in points_status:
        logger.debug(f"[ZW] Points tabulator: Saved: {entry}")
        # Need code to NOT write it if the points are 0
        if entry[1] != 0:
            addition_command = "INSERT INTO total_points VALUES (?, ?, ?, ?, ?)"
            addition_tuple = (month_string, pid, entry[0], str(entry[1]), oid)
            cursor_main.execute(addition_command, addition_tuple)
            conn_main.commit()


"""
RECORDING FUNCTIONS

This is a collection of functions that record information for Ziwen. Some write to a local Markdown file, while others
may write to the wiki of r/translator.

Recording functions are all prefixed with `record` in their name.
"""


def record_filter_log(filtered_title: str, ocreated: float, filter_type: str) -> None:
    """
    Simple function to write the titles of removed posts to an external text file as an entry in a Markdown table.

    :param filtered_title: The title that violated the community formatting guidelines.
    :param ocreated: The Unix time when the post was created.
    :param filter_type: The specific rule the post violated (e.g. 1, 1A, 1B, 2, EE).
    :return: Nothing.
    """

    # Access the file.
    # File address for the filter log, cumulative.
    with open(FILE_ADDRESS_FILTER, "a+", encoding="utf-8") as f:
        # Format the new line.
        timestamp_utc = str(
            datetime.datetime.fromtimestamp(ocreated).strftime("%Y-%m-%d")
        )
        # Write the new line.
        f.write(f"\n{timestamp_utc} | {filtered_title} | {filter_type}")


def record_last_post_comment() -> str:
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
        slink = f"https://www.reddit.com{submission.permalink}"
        s_format_time = str(
            datetime.datetime.fromtimestamp(sutc).strftime(
                "%a, %b %d, %Y [%I:%M:%S %p]"
            )
        )
    for comment in r.comments(limit=1):  # Get the last posted comment
        cbody = f"              > {comment.body}"

        cutc = comment.created_utc
        cpermalink = "https://www.reddit.com" + comment.permalink
        c_format_time = str(
            datetime.datetime.fromtimestamp(cutc).strftime(
                "%a, %b %d, %Y [%I:%M:%S %p]"
            )
        )

    if "\n" in cbody:
        # Nicely format each line to fit with our format.
        cbody = cbody.replace("\n", "\n              > ")

    return f"Last post     |   {s_format_time}:    {slink}\nLast comment  |   {c_format_time}:    {cpermalink}\n{cbody}\n"


def record_error_log(error_save_entry: str) -> None:
    """
    A function to SAVE errors to a log for later examination.
    This is more advanced than the basic version kept in _config, as it includes data about last post/comment.

    :param error_save_entry: The traceback text that we want saved to the log.
    :return: Nothing.
    """

    # File address for the error log, cumulative.
    with open(FILE_ADDRESS_ERROR, "a+", encoding="utf-8") as f:
        existing_log = f.read()  # Get the data that already exists

        # If this error entry doesn't exist yet, let's save it.
        if error_save_entry not in existing_log:
            error_date = time.strftime("%Y-%m-%d [%I:%M:%S %p]")
            # Get the last post and comment as a string
            last_post_text = record_last_post_comment()

            try:
                f.write(
                    f"\n-----------------------------------\n{error_date} ({BOT_NAME} {VERSION_NUMBER})\n{last_post_text}\n{error_save_entry}"
                )
            except UnicodeEncodeError:
                # Occasionally this may fail on Windows thanks to its crap Unicode support.
                logger.error("[ZW] Error_Log: Encountered a Unicode writing error.")


def record_to_wiki(
    odate: int,
    otitle: str,
    oid: str,
    oflair_text: str,
    s_or_i: bool,
    oflair_new: str,
    user: str | None = None,
) -> None:
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
        new_content = (
            f"| {oformat_date} | [{otitle}](https://redd.it/{oid}) | {oflair_text} |"
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
        new_content = f"{oformat_date} | [{otitle}](https://redd.it/{oid}) | {oflair_text} | {oflair_new} | u/{user}"
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
            message_subject = f"[Notification] '{page_name}' Wiki Page Full"
            message_template = MSG_WIKIPAGE_FULL.format(page_name)
            logger.warning(f"[ZW] Save_Wiki: The '{page_name}' wiki page is full.")
            reddit.subreddit("translatorBOT").message(message_subject, message_template)
        logger.info("[ZW] Save_Wiki: Updated the 'identified' wiki page.")


"""
MESSAGING FUNCTIONS

These are functions that are used in messages to users but are not necessarily part of the notifications system. The 
notifications system, however, may still use these functions.

These non-notifier functions are all prefixed with `messaging` in their name.
"""


def messaging_user_statistics_writer(body_text: str, username: str) -> None:
    """
    Function that records which commands are written by whom, cumulatively, and stores it into an SQLite file.
    Takes the body text of their comment as an input.
    The database used is the main one but with a different table.

    :param body_text: The content of a comment, likely containing r/translator commands.
    :param username: The username of a Reddit user.
    :return: Nothing.
    """

    # Properly format things.
    if KEYWORDS.id in body_text:
        body_text = body_text.replace(KEYWORDS.id, KEYWORDS.identify)

    # Let's try and load any saved record of this
    sql_us = "SELECT * FROM total_commands WHERE username = ?"
    cursor_main.execute(sql_us, (username,))
    username_commands_data = cursor_main.fetchall()

    if len(username_commands_data) == 0:  # Not saved, create a new one
        commands_dictionary = {}
        already_saved = False
    else:  # There's data already for this username.
        already_saved = True
        # We only want the stored dict here.
        commands_dictionary = eval(username_commands_data[0][1])

    # Process through the text and record the commands used.
    for keyword in [
        key for key in KEYWORDS if key not in [KEYWORDS.translate, KEYWORDS.translator]
    ]:
        if keyword in body_text:
            if keyword == "`":
                # Since these come in pairs, we have to divide this in half.
                keyword_count = int(body_text.count(keyword) / 2)
            else:  # Regular command
                keyword_count = body_text.count(keyword)

            if keyword in commands_dictionary:
                commands_dictionary[keyword] += keyword_count
            else:
                commands_dictionary[keyword] = keyword_count

    # Save to the database if there's stuff.
    if len(commands_dictionary.keys()) != 0 and not already_saved:
        # This is a new username.
        to_store = (username, str(commands_dictionary))
        cursor_main.execute("INSERT INTO total_commands VALUES (?, ?)", to_store)
        conn_main.commit()
    elif len(commands_dictionary.keys()) != 0 and already_saved:
        # This username exists. Update instead.
        update_command = "UPDATE total_commands SET commands = ? WHERE username = ?"
        cursor_main.execute(update_command, (str(commands_dictionary), username))
        conn_main.commit()
    else:
        logger.debug("[ZW] messaging_user_statistics_writer: No commands to write.")


def messaging_translated_message(oauthor: str, opermalink: str) -> None:
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
        f"[ZW] messaging_translated_message: >> Messaged the OP u/{oauthor} "
        "about their translated post."
    )


# General Lookup Functions
def lookup_cjk_matcher(content_text: str) -> List[str]:
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
        content_text = f"`{content_text}`"  # Re-add the graves.
    except IndexError:  # Split improperly
        return []

    # Delete spaces, we don't need this for CJK.
    content_text = content_text.replace(" ", "``")
    # Delete slashes, since the redesign may introduce them.
    content_text = content_text.replace("\\", "")

    # Regular expression to match both CJK Unified Ideographs and Extension B-F
    regex = "`([\u2E80-\u9FFF\U00020000-\U0002EBEF]+)`"
    matches = re.findall(regex, content_text, re.DOTALL)
    return matches if len(matches) != 0 else []


def lookup_matcher(
    content_text: str, language_name: str | None
) -> List[str] | Dict[str, str]:
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
    if KEYWORDS.identify in original_text:
        # Parse the data from the command.
        parsed_data = comment_info_parser(original_text, KEYWORDS.identify)[0]

        # Code to help make sense of CJK script codes if they're identified.
        language_keys = ["Chinese", "Japanese", "Korean"]
        for key in language_keys:
            if len(parsed_data) == 4 and parsed_data.title() in CJK_LANGUAGES[key]:
                parsed_data = key

        # Set the language name to the identified language.
        language_name = converter(parsed_data)[1]
    # Secondly we see if there's a language mentioned.
    elif (
        language_mention_search(content_text) is not None
        and len(language_mentions) == 1
    ):
        language_name = language_mentions[0]

    # Work with the text and clean it up.
    try:
        content_text = content_text.split("`", 1)[1]  # Delete stuff before
        content_text = content_text.rsplit("`", 1)[0]  # Delete stuff after
        content_text = f"`{content_text}`"  # Re-add the graves.
    except IndexError:  # Split improperly
        return []
    # Delete spaces, we don't need this for CJK.
    content_text = content_text.replace(" ", "``")
    # Delete slashes, since the redesign may introduce them.
    content_text = content_text.replace("\\", "")
    matches = re.findall("`(.*?)`", content_text, re.DOTALL)

    # Tokenize, remove empty strings
    for match in matches:
        if " " in match:  # This match contains a space, so let's split it.
            new_matches = match.split()
            matches.remove(match)
            matches.append(new_matches)
    matches = [x for x in matches if x]

    # A simple string to allow for quick detection of languages that fall in Unicode.
    combined_text = "".join(matches)
    zhja_true = re.findall("([\u2E80-\u9FFF]+)", combined_text, re.DOTALL)
    zh_b_true = re.findall("([\U00020000-\U0002EBEF]+)", combined_text, re.DOTALL)
    kana_true = re.findall(
        "([\u3041-\u309f]+|[\u30a0-\u30ff]+)", combined_text, re.DOTALL
    )
    # Checks if there's hangul there
    ko_true = re.findall("([\uac00-\ud7af]+)", combined_text, re.DOTALL)

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
        logger.debug(f"[ZW] Lookup_Matcher: Provisional: {zhja_temp_list}")

        # Tokenize them.
        tokenized_list = []
        for item in zhja_temp_list:
            if len(item) >= 2:  # Longer than bisyllabic?
                if language_name == "Chinese" and not kana_true:
                    new_matches = lookup_zhja_tokenizer(simplify(item), "zh")
                elif language_name == "Japanese" or kana_true:
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
    all_cjk = list(CJK_LANGUAGES.values())

    # For all other languages.
    # Nothing CJK-related. True if all are empty.
    # Making sure we don't return Latin words in CJK.
    if len(zhja_true + zh_b_true + kana_true + ko_true) == 0 and (
        len(matches) != 0 and language_name not in all_cjk
    ):
        # De-dupe
        master_dictionary[language_name] = [
            i for n, i in enumerate(matches) if i not in matches[:n]
        ]

    return master_dictionary


def lookup_zhja_tokenizer(phrase: str, language: str):
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
            mt = MeCab.Tagger(f"r'-d {FILE_ADDRESS_MECAB}'")
            # Per https://github.com/SamuraiT/mecab-python3/issues/3 to fix Unicode issue
            mt.parse(phrase)
            parsed = mt.parseToNode(phrase.strip())
            components = []

            while parsed:
                components.append(parsed.surface)
                # Note: `parsed.feature` produces the parts of speech, e.g. 名詞,一般,*,*,*,*,風景,フウケイ,フーケイ
                parsed = parsed.next

            # Remove empty strings
            word_list = [x for x in components if x]

    punctuation_string = r"\.\!\/_,$%^*(+\"\']+|[+——！，。？、~@#￥%……&*（）：；《）《》“”()»〔〕「」％"
    for item in word_list:  # Get rid of punctuation and kana (for now)
        if language == "ja":
            kana_test = None
            if len(item) == 1:  # If it's only a single kana...
                kana_test = re.search("[\u3040-\u309f]", item)
            if kana_test is None and item not in punctuation_string:
                final_list.append(item)
        if language == "zh" and item not in punctuation_string:
            final_list.append(item)

    return final_list  # Returns a list of words / characters


def lookup_wiktionary_search(search_term: str, language_name: str) -> str | None:
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
    test_wikt_link = f"https://en.wiktionary.org/wiki/{search_term}#{language_name}"
    test_page = requests.get(test_wikt_link, headers=ZW_USERAGENT)
    test_tree = html.fromstring(test_page.content)  # now contains the whole HTML page
    test_language = test_tree.xpath(f'string(//span[contains(@id,"{language_name}")])')
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
        post_etymology = f"\n\n#### Etymology\n\n{post_etymology.strip()}"

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
            pronunciations_audio = (
                f" ([Audio](https:{dict_pronunciations['audio'][0]}))"
            )
        else:
            pronunciations_audio = ""
    if len(pronunciations_ipa + pronunciations_audio) > 0:
        post_pronunciations = (
            f"\n\n#### Pronunciations\n\n{pronunciations_ipa}{pronunciations_audio}"
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
                if len(examples_data) > 3:
                    # If there are a lot of examples, we only want the first three.
                    examples_data = examples_data[:3]
                post_examples = "* " + "\n* ".join(examples_data)
                post_examples = f"\n\n**Examples:**\n\n{post_examples}"
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
                post_meanings = f"\n\n*Meanings*:\n\n{meanings_format}"
                post_total_info = post_word_info + post_meanings
            else:
                post_total_info = ""

            # Combine definitions as a format.
            if len(post_examples + post_part) > 0:
                # Use the part of speech as a header if known
                info_header = post_part.title() if post_part else "Information"
                post_definitions = (
                    f"\n\n##### {info_header}\n\n{post_total_info}{post_examples}"
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
        f"[ZW] Looked up information for {search_term} as a {language_name} word.."
    )

    return post_template


"""
LANGUAGE REFERENCE FUNCTIONS

These are functions that retrieve reference information about languages. 

All reference functions are prefixed with `reference` in their name.
"""


def reference_search(lookup_term: str) -> None | str:
    """
    Function to look up reference languages on Ethnologue and Wikipedia.
    This also searches MultiTree (no longer a separate function)
    for languages which may be constructed or dead.
    Due to web settings the live search function of this has been
    disabled.

    :param lookup_term: The language code or text we're looking for.
    :return: A formatted string regardless of whether it found an appropriate match or None.
    """

    # Regex to check if code is in the private use area qaa-qtz
    private_check = re.search("^q[a-t][a-z]$", lookup_term)
    if private_check is not None:
        # This is a private use code. If it's None, it did not match.
        return None  # Just exit.

    # Get the language code (specifically the ISO 639-3 one)
    language_code = converter(lookup_term)[0]
    language_lookup_code = str(language_code)
    if len(language_code) == 2:  # This appears to be an ISO 639-1 code.
        # Get the ISO 639-3 version.
        language_code = MAIN_LANGUAGES[language_code]["language_code_3"]
    if len(language_code) == 4:  # This is a script code.
        return None

    # Correct for macrolanguages. There is frequently no data for their broad codes.
    if language_code in ISO_MACROLANGUAGES:
        # We replace the macrolanguage with the most frequent individual language code. (e.g. 'zho' becomes 'cmn'.)
        language_code = ISO_MACROLANGUAGES[language_code][0]

    # Now we check the database to see if it has data.
    if len(language_code) != 0:  # There's a valid code here.
        logger.info(f"[ZW] reference_search Code: {language_lookup_code}")
        sql_command = "SELECT * FROM language_cache WHERE language_code = ?"
        cursor_main.execute(sql_command, (language_lookup_code,))
        reference_results = cursor_main.fetchone()

        if reference_results is not None:  # We found a cached value for this language
            reference_cached_info = reference_results[1]
            logger.info(
                f"[ZW] Reference: Retrieved the cached reference information for {language_lookup_code}."
            )
            return reference_cached_info


def reference_reformatter(original_entry: str) -> str:
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
        if any(key in line for key in excluded_lines):
            continue

        if "##" in line and "]" in line:
            sole_language = line.split("]")[0]
            sole_language = sole_language.replace("[", "")
            line = sole_language

        new_lines.append(line)

    # Combine the lines into a new string.
    return "\n\n".join(new_lines)


"""
EDIT FINDER

This is a single function that helps detect changes in r/translator comments, especially checking for the addition of 
commands are changes in the content that's looked up. 
"""


def edit_finder() -> None:
    """
    A top-level function to detect edits and changes of note in r/translator comments, including commands and
    lookup items. `comment_limit` defines how many of the latest comments it will store in the cache.

    :param: Nothing.
    :return: Nothing.
    """

    comment_limit = 150

    # Fetch the comments from Reddit.
    try:
        # Only get the last `comment_limit` comments.
        comments = list(r.comments(limit=comment_limit))
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
        # Returns a list that contains a tuple (comment ID, comment text).
        old_matching_data = cursor_cache.fetchall()

        # Has this comment has previously been stored? Let's check it.
        if len(old_matching_data) != 0:
            logger.debug(
                f"[ZW] Edit Finder: Comment '{cid}' was previously stored in the cache."
            )

            # Define a way to override and force a change even if there is no difference in detected commands.
            force_change = False

            # Retrieve the previously stored text for this comment.
            old_cbody = old_matching_data[0][1]

            # Test the new retrieved text with the old one.
            if cbody == old_cbody:  # The cached comment is the same as the current one.
                continue  # Do nothing.
            # There is a change of some sort.
            logger.debug(
                f"[ZW] Edit Finder: An edit for comment '{cid}' was detected. Processing..."
            )
            cleanup_database = True

            # We detected a possible `lookup` change, where the words looked up are now different.
            if "`" in cbody:
                # First thing is compare the data in a lookup comment against what we have.

                # Here we use the lookup_matcher function to get a LIST of everything that used to be in the graves.
                total_matches = lookup_matcher(old_cbody, None)

                # Then we get data from Komento, specifically looking for its version of results.
                new_vars = komento_analyzer(komento_submission_from_comment(cid))
                new_overall_lookup_data = new_vars.get("bot_lookup_correspond", {})
                if cid in new_overall_lookup_data:
                    # This comment is in our data
                    new_total_matches = new_overall_lookup_data[cid]
                    # Get the new matches
                    # Are they the same?
                    if set(new_total_matches) == set(total_matches):
                        logger.debug(
                            f"[ZW] Edit-Finder: No change found for lookup comment '{cid}'."
                        )
                        continue
                    logger.debug(
                        f"[ZW] Edit-Finder: Change found for lookup comment '{cid}'."
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
                # Iterate through the command keywords to see what's new.
                for keyword in [key for key in KEYWORDS if key != KEYWORDS.translator]:
                    if keyword in cbody and keyword not in old_cbody:
                        # This means the keyword is a NEW addition to the edited comment.
                        logger.debug(
                            f"[ZW] Edit Finder: New command {keyword} detected for comment '{cid}'."
                        )
                        force_change = True

                if force_change:
                    # Delete the comment from the processed database to force it to update and reprocess.
                    delete_comment_command = "DELETE FROM oldcomments WHERE id = ?"
                    cursor_main.execute(delete_comment_command, (cid,))
                    conn_main.commit()
                    logger.debug(
                        f"[ZW] Edit Finder: Removed edited comment `{cid}` from processed database."
                    )

        else:  # This is a comment that has not been stored.
            logger.debug(
                f"[ZW] Edit Finder: New comment '{cid}' to store in the cache."
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
                    f"[ZW] Edit Finder: ValueError when inserting comment `{cid}` into cache."
                )

    if cleanup_database:  # There's a need to clean it up.
        cleanup = "DELETE FROM comment_cache WHERE id NOT IN (SELECT id FROM comment_cache ORDER BY id DESC LIMIT ?)"
        cursor_cache.execute(cleanup, (comment_limit,))

        # Delete all but the last comment_limit comments.
        conn_cache.commit()
        logger.debug("[ZW] Edit Finder: Cleaned up the edited comments cache.")


"""
POSTS FILTERING & TESTING FUNCTIONS

This is the main routine to check for incoming posts, assign them the appropriate category, and activate notifications.
The function also removes posts that don't match the formatting guidelines.
"""


def is_mod(user: str) -> bool:
    """
    A function that can tell us if a user is a moderator of the operating subreddit (r/translator) or not.

    :param user: The Reddit username of an individual.
    :return: True if the user is a moderator, False otherwise.
    """
    # Get list of subreddit mods from r/translator.
    moderators = [moderator.name.lower() for moderator in r.moderator()]
    return user.lower() in moderators


def css_check(css_class: str) -> bool:
    """
    Function that checks if a CSS class is something that a command can act on.

    :param css_class: The css_class of the post.
    :return: True if the post is something than can be worked with, False if it's in either of the defined two classes.
    """

    return css_class not in ["meta", "community"]


def bad_title_commenter(title_text: str, author: str) -> str:
    """
    This function takes a filtered title and constructs a comment that contains a suggested new title for the user to
    use and a resubmit link that has that new title filled in automatically. This streamlines the process of
    resubmitting a post to r/translator.

    :param title_text: The filtered title that did not contain the required keywords for the community.
    :param author: The OP of the post.
    :return: A formatted comment that `ziwen_posts` can reply to the post with.
    """

    # Retrieve the reformed title from the routine in _languages
    new_title = bad_title_reformat(title_text)
    new_url = new_title.replace(" ", "%20")  # replace spaces
    new_url = new_url.replace(")", r"\)")  # replace closing parentheses
    new_url = new_url.replace(">", "%3E")  # replace caret with HTML code
    new_title = "`" + new_title + "`"  # add code marks

    # If the new title is for Unknown, let's add a text reminder
    if "[Unknown" in new_title:
        new_title += "\n* (If you know your request's language, replace `Unknown` with its name.)"

    return COMMENT_BAD_TITLE.format(author=author, new_url=new_url, new_title=new_title)


def ziwen_posts() -> None:
    """
    The main top-level post filtering runtime for r/translator.
    It removes posts that do not meet the subreddit's guidelines.
    It also assigns flair to posts, saves them as Ajos, and determines what to pass to the notifications system.

    :return: Nothing.
    """

    current_time = int(time.time())  # This is the current time.
    logger.debug(f"[ZW] Fetching new r/{SUBREDDIT} posts at {current_time}.")

    # We get the last 80 new posts. Changed from the deprecated `submissions` method.
    # This should allow us to retrieve stuff from up to a day in case of power outages or moving.
    posts = list(r.new(limit=80))
    posts.reverse()  # Reverse it so that we start processing the older ones first. Newest ones last.

    for post in posts:
        # Anything that needs to happen every loop goes here.
        oid = post.id
        otitle = post.title
        # ourl = post.url
        # This is the comments page, not the URL of an image
        opermalink = post.permalink
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
                f"[ZW] Posts: This post {oid} already exists in the processed database."
            )
            continue
        cursor_main.execute("INSERT INTO oldposts VALUES(?)", [oid])
        conn_main.commit()

        if not css_check(oflair_css) and oflair_css is not None:
            # If it's a Meta or Community post (that's what css_check does), just alert those signed up for it.
            suggested_css_text = oflair_css
            logger.info(f"[ZW] Posts: New {suggested_css_text.title()} post.")

            # Assign it a specific template that exists.
            if oflair_css in POST_TEMPLATES.keys():
                output_template = POST_TEMPLATES[oflair_css]
                post.flair.select(output_template, suggested_css_text.title())

            # We want to exclude the Identification Threads
            if "Identification Thread" not in otitle:
                ziwen_notifier(
                    suggested_css_text,
                    otitle,
                    opermalink,
                    oauthor,
                    False,
                    POST_TEMPLATES,
                    reddit,
                    cursor_ajo,
                    cursor_main,
                    conn_main,
                    is_mod,
                )

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

        if oauthor.lower() in GLOBAL_BLACKLIST:
            # This user is on our blacklist. (not used much, more precautionary)
            post.mod.remove()
            action_counter(1, "Blacklisted posts")  # Write to the counter log
            logger.info(
                "[ZW] Posts: Filtered a post out because its author u/{} is on my blacklist.".format(
                    oauthor
                )
            )
            continue

        if opost_age < CLAIM_PERIOD:
            # If the post is younger than the claim period, we can act on it. (~8 hours)
            # If the post is under an hour, let's send notifications to people. Otherwise, we won't.
            # This is mainly for catching up with older posts - we want to process them but we don't want to send notes.
            okay_send = opost_age < 3600

            # Applies a filtration test, see if it's okay. False if it is not
            returned_info = main_posts_filter(otitle)

            if returned_info[0] is not False:  # Everything appears to be fine.
                otitle = returned_info[1]
                logger.info(f"[ZW] Posts: New post, {otitle} by u/{oauthor}.")
            else:  # This failed the test.
                # Remove this post, it failed all routines.
                post.mod.remove()
                post.reply(
                    str(bad_title_commenter(title_text=otitle, author=oauthor))
                    + BOT_DISCLAIMER
                )

                # Write the title to the log.
                filter_num = returned_info[2]
                record_filter_log(otitle, ocreated, filter_num)
                action_counter(1, "Removed posts")  # Write to the counter log
                logger.info(
                    f"[ZW] Posts: Removed post that violated formatting guidelines. Title: {otitle}"
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
                # This is a specific code, like ar-LB, unknown-cyrl
                specific_sublanguage = title_data[7]
            except Exception as e_title:
                # The title converter couldn't make sense of it. This should not happen.
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
                and "English" in suggested_source
                and "English" in suggested_target
            ):
                # If it's an English only post, filter it out.
                post.mod.remove()
                post.reply(COMMENT_ENGLISH_ONLY.format(oauthor=oauthor))
                record_filter_log(otitle, ocreated, "EE")
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
                        odate=int(ocreated),
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
                    f"[ZW] Posts: Title formatting routine couldn't make sense of '{otitle}'."
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
            if len(oselftext) > 1400:
                # This changes the CSS text to indicate if it's a long wall of text
                logger.info("[ZW] Posts: This is a long piece of text.")
                if final_css_text is not None and post.author.name != USERNAME:
                    # Let's leave None flair text alone
                    final_css_text += " (Long)"
                    post.reply(COMMENT_LONG + BOT_DISCLAIMER)

            # True if the user has posted too much.
            user_posted_too_much = MOST_RECENT_OP.count(oauthor) > 4

            # We don't want to send notifications if we're just testing. We also verify that user is not too extra.
            # A placeholder variable that normally contains a list of users notified.
            contacted = []
            if MESSAGES_OKAY and okay_send and not user_posted_too_much:
                action_counter(1, "New posts")  # Write to the counter log
                if multiple_notifications is not None and specific_sublanguage is None:
                    # This is a multiple post with a fixed number of languages or two non-English ones.
                    # Also called a "defined multiple language post"
                    # This part of the function also sends notifications if both languages are non-English
                    for notification in multiple_notifications:
                        # This is the language name for consistency
                        multiple_language_text = converter(notification)[1]
                        contacted = ziwen_notifier(
                            multiple_language_text,
                            otitle,
                            opermalink,
                            oauthor,
                            False,
                            POST_TEMPLATES,
                            reddit,
                            cursor_ajo,
                            cursor_main,
                            conn_main,
                            is_mod,
                        )
                    if final_css_class == "multiple":
                        # We wanna leave an advisory comment if it's a defined multiple
                        post.reply(COMMENT_DEFINED_MULTIPLE + BOT_DISCLAIMER)
                elif multiple_notifications is None:
                    # if it is a specific sublanguage, then
                    # there is a specific subcategory for us to look at (ar-LB, unknown-cyrl) etc
                    # The notifier routine will be able to make sense of the hyphenated code.
                    # Now we notify people who are signed up on the list.
                    contacted = ziwen_notifier(
                        suggested_css_text
                        if specific_sublanguage is None
                        else specific_sublanguage,
                        otitle,
                        opermalink,
                        oauthor,
                        False,
                        POST_TEMPLATES,
                        reddit,
                        cursor_ajo,
                        cursor_main,
                        conn_main,
                        is_mod,
                    )

            # If it's an unknown post, add an informative comment.
            if final_css_class == "unknown" and post.author.name != "translator-BOT":
                post.reply(COMMENT_UNKNOWN + BOT_DISCLAIMER)
                logger.info(
                    "[ZW] Posts: Added the default 'Unknown' information comment."
                )

            # Actually update the flair. Legacy version first.
            logger.info(
                f"[ZW] Posts: Set flair to class '{final_css_class}' and text '{final_css_text}.'"
            )

            # New Redesign Version to update flair
            # Check the global template dictionary
            if final_css_class in POST_TEMPLATES.keys():
                output_template = POST_TEMPLATES[final_css_class]
                post.flair.select(output_template, final_css_text)
                logger.debug("[ZW] Posts: Flair template selected for post.")

            # Finally, create an Ajo object and save it locally.
            if final_css_class not in ["meta", "community"]:
                # Create an Ajo object, reload the post.
                pajo = Ajo(reddit.submission(id=post.id), POST_TEMPLATES, USER_AGENT)
                if len(contacted) != 0:  # We have a list of notified users.
                    pajo.add_notified(contacted)
                # Save it to the local database
                ajo_writer(pajo, cursor_ajo, conn_ajo)
                logger.debug(
                    "[ZW] Posts: Created Ajo for new post and saved to local database."
                )


"""
MAIN COMMANDS RUNTIME

This is the main routine that processes commands from r/translator users.
"""


def ziwen_bot() -> None:
    """
    This is the main runtime for r/translator that checks for keywords and commands.

    :return: Nothing.
    """

    logger.debug(f"Fetching new r/{SUBREDDIT} comments...")
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
        # Returns a submission object of the parent to work with
        osubmission = post.submission
        oid = osubmission.id
        opermalink = osubmission.permalink
        otitle = osubmission.title
        oflair_text = osubmission.link_flair_text  # This is the linkflair text
        # This is the linkflair css class (lowercase)
        oflair_css = osubmission.link_flair_css_class
        ocreated = post.created_utc  # Unix time when this post was created.
        osaved = post.saved  # We save verification requests so we don't work on them.
        requester = "Zamenhof"  # Dummy thing just to have data
        current_time = int(time.time())  # This is the current time.

        try:
            # Check to see if the submission author deleted their post already
            oauthor = osubmission.author.name
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
            # We don't want to process it without the oflair text. Or if its verified comment
            logger.debug(f"[ZW] Bot: Processing points for u/{pauthor}")
            points_tabulator(oid, oauthor, oflair_text, oflair_css, post)

        """AJO CREATION"""
        # Create an Ajo object.
        if css_check(oflair_css):
            # Check the database for the Ajo.
            oajo = ajo_loader(oid, cursor_ajo, POST_TEMPLATES, reddit)

            if oajo is None:
                # We couldn't find a stored dict, so we will generate it from the submission.
                logger.debug("[ZW] Bot: Couldn't find an AJO in the local database.")
                oajo = Ajo(osubmission, POST_TEMPLATES, USER_AGENT)

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

        if not any(key in pbody for key in KEYWORDS) and not any(
            phrase in pbody for phrase in THANKS_KEYWORDS
        ):
            # Does not contain our keyword
            logger.debug(
                f"[ZW] Bot: Post {oid} does not contain any operational keywords."
            )
            continue

        if TESTING_MODE and current_time - ocreated >= 3600:
            # This is a function to help stop the incessant commenting on older posts when testing
            # If the comment is older than an hour, ignore
            continue

        # Record to the counter with the keyword.
        for keyword in KEYWORDS:
            if keyword in pbody:
                action_counter(1, keyword)  # Write to the counter log

        """RESTORE COMMAND"""

        # This is the `!restore` command, which can try and check Pushshift data. It can be triggered if user deleted it
        if KEYWORDS.restore in pbody and oauthor is None:
            # This command is allowed to be used by people who have either translated the piece or who were notified
            # about it. This is to help resolve the big issue of people deleting their posts.
            logger.info(f"[ZW] Bot: COMMAND: {KEYWORDS.restore}, from u/{pauthor}.")

            # This is a link post, we can't retrieve that.
            if not osubmission.is_self:
                # Reply and let them know this only works on text-only posts.
                post.reply(MSG_RESTORE_LINK_FAIL + BOT_DISCLAIMER)
                logger.info(
                    f"[ZW] Bot: {KEYWORDS.restore} request is for a link post. Skipped."
                )
                continue

            try:  # Get the people who are eligible to check for this.
                try:
                    eligible_people = oajo.notified
                except AttributeError:
                    # Since this is a new attribute it's possible older Ajos don't have it.
                    logger.error("[ZW] Bot: Error retrieving notified list from Ajo.")
                    eligible_people = []
                eligible_people += oajo.recorded_translators
            except AttributeError:
                logger.error(
                    "[ZW] Bot: Error in retrieving recorded translators list from Ajo."
                )
                continue

            # The person asking for a restore isn't eligible for it.
            if pauthor not in eligible_people and not is_mod(pauthor):
                # mods should be able to call it.
                logger.info(
                    f"[ZW] Bot: u/{pauthor} is not eligible to make a !restore request for this."
                )
                post.reply(MSG_RESTORE_NOT_ELIGIBLE + BOT_DISCLAIMER)
                continue
            # Format a search query to Pushshift.
            search_query = (
                f"https://api.pushshift.io/reddit/search/submission/?ids={oid}"
            )
            retrieved_data = requests.get(search_query).json()

            if "data" in retrieved_data:  # We've got some data.
                returned_submission = retrieved_data["data"][0]
                original_title = f"> **{returned_submission['title']}**\n\n"
                original_text = returned_submission["selftext"]
                if len(original_text.strip()) > 0:  # We have text.
                    original_text = "> " + original_text.strip().replace("\n", "\n > ")
                else:  # The retrieved text is of zero length.
                    original_text = "> *It appears this text-only post had no text.*"
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
                        f"[ZW] Bot: Replied to u/{pauthor} with message, "
                        "unable to retrieve data."
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
                logger.info(f"[ZW] Bot: Replied to u/{pauthor} with restored text.")

        # We move the exit point if there is no author here. Since !restore relies on there being no author.
        if oauthor is None:
            logger.info("[ZW] Bot: >> Author is deleted or non-existent.")
            oauthor = "deleted"

        """REFERENCE COMMANDS (!identify, !page, !reference, !search, `lookup`)"""
        if KEYWORDS.id in pbody or KEYWORDS.identify in pbody:
            # This is the general !identify command (synonym: !id)
            determined_data = comment_info_parser(pbody, KEYWORDS.identify)
            # This should return what was actually identified. Normally will be a tuple or None.
            if determined_data is None:
                # The command is problematic. Wrong punctuation, not enough arguments
                logger.debug(f"[ZW] Bot: {KEYWORDS.identify} data is invalid.")
                continue

            # Set some defaults just in case. These should be overwritten later.
            match_script = False
            language_code = ""
            language_name = ""

            # If it's not none, we got proper data.
            match = determined_data[0]
            advanced_mode = determined_data[1]
            language_country = None  # Default value
            # Store the original language defined in the Ajo
            o_language_name = str(oajo.language_name)
            # This should return a boolean whether it's in advanced mode.

            logger.info(f"[ZW] Bot: COMMAND: {KEYWORDS.id}, from u/{pauthor}.")
            logger.info(f"[ZW] Bot: {KEYWORDS.id} data is: {determined_data}")

            if "+" not in match:  # This is just a regular single !identify command.
                if not advanced_mode:  # This is the regular results conversion
                    language_code = converter(match)[0]
                    language_name = converter(match)[1]
                    language_country = converter(match)[
                        3
                    ]  # The country code for the language. Regularly none.
                    match_script = False
                elif advanced_mode:
                    if len(match) == 3:
                        # The advanced mode only accepts codes of a certain length.
                        language_data = lang_code_search(match, False)
                        # Run a search for the specific thing
                        language_code = match
                        language_name = language_data[0]
                        match_script = language_data[1]
                        if len(language_name) == 0:
                            # If there are no results from the advanced converter...
                            language_code = ""
                            # is_supported = False
                    elif len(match) == 4:
                        # This is a script, resets it to an Unknown state.
                        language_data = lang_code_search(match, True)
                        # Run a search for the specific script
                        logger.info(
                            f"[ZW] Bot: Returned script data is for {language_data}."
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
                        language_code = match
                        language_name = language_data[0]
                        match_script = True
                        logger.info(
                            f"[ZW] Bot: This is a script post with code `{language_code}`."
                        )
                        if len(language_name) == 0:
                            # If there are no results from the advanced converter...
                            language_code = ""
                    else:  # a catch-all for advanced mode that ISN'T a 3 or 4-letter code.
                        post.reply(COMMENT_ADVANCED_IDENTIFY_ERROR + BOT_DISCLAIMER)
                        logger.info(
                            "[ZW] Bot: This is an invalid use of advanced !identify. Skipping this one..."
                        )
                        continue

                if not match_script:
                    if len(language_code) == 0:
                        # The converter didn't give us any results.
                        no_match_text = COMMENT_INVALID_CODE.format(match, opermalink)
                        try:
                            post.reply(no_match_text + BOT_DISCLAIMER)
                        except praw.exceptions.APIException:
                            # Comment has been deleted.
                            pass
                        logger.info(
                            f"[ZW] Bot: But '{match}' has no match in the database. Skipping this..."
                        )
                        continue
                    if len(language_code) != 0:  # This is a valid language.
                        # Insert code for updating country as well here.
                        if language_country is not None:
                            # There is a country code listed.
                            # Add that code to the Ajo
                            oajo.set_country(language_country)
                        else:  # There was no country listed, so let's reset the code to none.
                            oajo.set_country(None)
                        oajo.set_language(language_code, True)  # Set the language.
                        logger.info(f"[ZW] Bot: Changed flair to {language_name}.")
                elif match_script:  # This is a script.
                    oajo.set_script(language_code)
                    logger.info(
                        f"[ZW] Bot: Changed flair to '{language_name}', with an Unknown+script flair."
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
                KEYWORDS.translated not in pbody
                and KEYWORDS.doublecheck not in pbody
                and oajo.status == "untranslated"
            ):
                # Just a check that we're not sending notifications AGAIN if the identified language is the same as orig
                # This makes sure that they're different languages. So !identify:Chinese on Chinese won't send messages.
                if o_language_name != language_name and MESSAGES_OKAY:
                    contacted = ziwen_notifier(
                        f"unknown-{language_code}" if match_script else language_name,
                        otitle,
                        opermalink,
                        oauthor,
                        True,
                        POST_TEMPLATES,
                        reddit,
                        cursor_ajo,
                        cursor_main,
                        conn_main,
                        is_mod,
                    )
                    # Notify people on the list if the post hasn't already been marked as translated
                    # no use asking people to see something that's translated
                    # Add those who have been contacted to the notified list.
                    oajo.add_notified(contacted)

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
        if KEYWORDS.page in pbody:  # This is the basic paging !page function.
            logger.info(f"[ZW] Bot: COMMAND: {KEYWORDS.page}, from u/{pauthor}.")

            determined_data = comment_info_parser(pbody, "!page:")
            # This should return what was actually identified. Normally will be a Tuple or None
            if determined_data is None:
                # The command is problematic. Wrong punctuation, not enough arguments
                logger.info("[ZW] Bot: >> !page data is invalid.")
                continue

            # CODE FOR A 14-DAY VERIFICATION SYSTEM
            poster = reddit.redditor(name=pauthor)
            current_time = int(time.time())
            if current_time - int(poster.created_utc) > 1209600:
                # checks to see if the user account is older than 14 days
                logger.debug(
                    f"[ZW] Bot: > u/{pauthor}'s account is older than 14 days."
                )
            else:
                post.reply(
                    COMMENT_PAGE_DISALLOWED.format(pauthor=pauthor) + BOT_DISCLAIMER
                )
                logger.info(
                    f"[ZW] Bot: > However, u/{pauthor} is a new account. Replied to them and skipping..."
                )
                continue

            if oflair_css in ["meta", "community"]:
                logger.debug("[ZW] Bot: > However, this is not a valid pageable post.")
                continue

            # Okay, it's valid, let's start processing data.
            page_results = notifier_page_multiple_detector(pbody)

            if page_results is None:
                # There were no valid page results. (it is a placeholder)
                post.reply(
                    COMMENT_NO_LANGUAGE.format(
                        pauthor=pauthor, language_name="it", language_code=""
                    )
                    + BOT_DISCLAIMER
                )
                logger.info(
                    f"[ZW] Bot: No one listed. Replied to the pager u/{pauthor} and skipping..."
                )
            else:  # There were results. Let's loop through them.
                for result in page_results:
                    language_code = result
                    language_name = converter(language_code)[1]

                    is_nsfw = bool(post.submission.over_18)

                    # Send a message via the paging system.
                    paged_users = notifier_page_translators(
                        language_code,
                        language_name,
                        pauthor,
                        otitle,
                        opermalink,
                        oauthor,
                        is_nsfw,
                        reddit,
                        cursor_main,
                        conn_main,
                    )
                    if paged_users is not None:
                        # Add the notified users to the list.
                        oajo.add_notified(paged_users)

        if KEYWORDS.back_quote in pbody:
            # This function returns data for character lookups with `character`.
            post_content = []
            logger.info(f"[ZW] Bot: COMMAND: `lookup`, from u/{pauthor}.")

            if pauthor == USERNAME:  # Don't respond to !search results from myself.
                continue

            if oflair_css in ["meta", "community", "missing"]:
                continue

            if oajo.language_name is None:
                continue
            if not isinstance(oajo.language_name, str):
                # Multiple post?
                search_language = oajo.language_name[0]
            else:
                search_language = oajo.language_name

            # A dictionary keyed by language and search terms. Built in tokenizers.
            total_matches = lookup_matcher(pbody, search_language)

            # This section allows for the deletion of previous responses if the content changes.
            komento_data = komento_analyzer(komento_submission_from_comment(pid))
            if "bot_lookup_correspond" in komento_data:
                # This may have had a comment before.
                relevant_comments = komento_data["bot_lookup_correspond"]

                # This returns a dictionary with the called comment as key.
                for key in relevant_comments:
                    if key == pid and "bot_lookup_replies" in komento_data:
                        # This is the key for our current comment.
                        # We try to find any corresponding bot replies
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
            logger.info(f"[ZW] Bot: >> Determined Lookup Dictionary: {total_matches}")

            def processChinese(match, post_content):
                match_length = len(match)
                if match_length == 1:  # Single-character
                    to_post = zh_character(match, ZW_USERAGENT)
                    post_content.append(to_post)
                elif match_length >= 2:  # A word or a phrase
                    find_word = str(match)
                    post_content.append(zh_word(find_word, ZW_USERAGENT))

                # Create a randomized wait time between requests.
                wait_sec = random.randint(3, 12)
                time.sleep(wait_sec)

            def processJapanese(match, post_content):
                match_length = len(str(match))
                if match_length == 1:
                    to_post = ja_character(match, ZW_USERAGENT)
                    post_content.append(to_post)
                elif match_length > 1:
                    find_word = str(match)
                    post_content.append(ja_word(find_word, ZW_USERAGENT))

            def processKorean(match, post_content):
                find_word = str(match)
                post_content.append(lookup_wiktionary_search(find_word, "Korean"))

            def processOther(match, post_content):
                find_word = str(match)
                wiktionary_results = lookup_wiktionary_search(find_word, key)
                if wiktionary_results is not None:
                    post_content.append(wiktionary_results)

            for key in total_matches.keys():
                processFunc = processOther
                cur_lang = None
                for lang, func in {
                    "Chinese": processChinese,
                    "Japanese": processJapanese,
                    "Korean": processKorean,
                }.items():
                    if key in CJK_LANGUAGES[lang]:
                        processFunc = func
                        cur_lang = lang
                        break
                logger.info(
                    f"[ZW] Bot: >> Conducting lookup search in {cur_lang}."
                    if cur_lang
                    else "[ZW] Bot: >> Conducting Wiktionary lookup search."
                )
                for match in total_matches[key][:limit_num_matches]:
                    processFunc(match, post_content)

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
                        f"*u/{oauthor} (OP), the following lookup results "
                        "may be of interest to your request.*\n\n"
                    )
                    post.reply(author_tag + post_content + BOT_DISCLAIMER)
                    logger.info(
                        f"[ZW] Bot: >> Looked up the term(s) in {search_language}."
                    )
                else:
                    logger.info("[ZW] Bot: >> No results found. Skipping...")
            except praw.exceptions.APIException:  # This means the comment is deleted.
                logger.debug("[ZW] Bot: >> Previous comment was deleted.")

        if KEYWORDS.reference in pbody:
            # the !reference command gets information from Ethnologue, Wikipedia, and other sources
            # to post as a reference
            determined_data = comment_info_parser(pbody, "!reference:")
            # This should return what was actually identified. Normally will be a Tuple or None
            if determined_data is None:
                # The command is problematic. Wrong punctuation, not enough arguments
                logger.debug("[ZW] Bot: >> !reference data is invalid.")
                continue

            language_match = determined_data[0]
            logger.info(f"[ZW] Bot: COMMAND: {KEYWORDS.reference}, from u/{pauthor}.")
            post_content = reference_search(language_match)
            if post_content is None:
                # There was no good data. We return the invalid comment.
                post_content = COMMENT_INVALID_REFERENCE
            post.reply(post_content)
            logger.info(
                f"[ZW] Bot: Posted the reference results for '{language_match}'."
            )

        # The !search function looks for strings in other posts on r/translator
        if KEYWORDS.search in pbody:
            determined_data = comment_info_parser(pbody, f"{KEYWORDS.search}:")
            # This should return what was actually identified. Normally will be a Tuple or None
            if determined_data is None:
                # The command is problematic. Wrong punctuation, not enough arguments
                logger.debug(f"[ZW] Bot: >> {KEYWORDS.search} data is invalid.")
                continue

            logger.info(f"[ZW] Bot: COMMAND: {KEYWORDS.search}, from u/{pauthor}.")
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
                    f"[ZW] Bot: > There were no results for {search_term}. Moving on..."
                )
                continue

            for oid in reddit_id:
                submission = reddit.submission(id=oid)
                s_title = submission.title
                s_date = datetime.datetime.fromtimestamp(submission.created).strftime(
                    "%Y-%m-%d"
                )
                s_permalink = submission.permalink
                header_string = f"#### [{s_title}]({s_permalink}) ({s_date})\n\n"
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
                    # This contains the !search string.
                    if KEYWORDS.search in comment.body.lower():
                        continue  # We don't want this.

                    # Format a comment body nicely.
                    c_body = comment.body

                    # Replace any keywords
                    for keyword in KEYWORDS:
                        c_body = c_body.replace(keyword, "")
                    c_body = str("\n> ".join(c_body.split("\n")))
                    # Indent the lines with Markdown >
                    c_votes = str(comment.score)  # Get the score of the comment

                    if search_term.lower() in c_body.lower():
                        comment_string = (
                            f"##### Comment by u/{c_author} (+{c_votes}):\n\n>{c_body}"
                        )
                        reply_body.append(comment_string)
                        continue

            reply_body = "\n\n".join(reply_body[:6])
            # Limit it to 6 responses. To avoid excessive length.
            post.reply(
                f'## Search results on r/translator for "{search_term}":\n\n{reply_body}'
            )
            logger.info("[ZW] Bot: > Posted my findings for the search term.")

        """STATE COMMANDS (!doublecheck, !translated, !claim, !missing, short thanks)"""

        # asking for reviews of one's work.
        if KEYWORDS.doublecheck in pbody:
            logger.info(f"[ZW] Bot: COMMAND: {KEYWORDS.doublecheck}, from u/{pauthor}.")

            if oajo.type == "multiple":
                if isinstance(oajo.language_name, list):
                    # It is a defined multiple post.
                    # Try to see if there's data in the comment.
                    # If the comment is just the command, we take the parent comment and together check to see.
                    checked_text = str(pbody_original)
                    if len(pbody) < 12:
                        # This is just the command, so let's get the parent comment.
                        # Get the parent comment
                        parent_item = post.parent_id
                        if "t1" in parent_item:  # The parent is a comment
                            parent_comment = post.parent()
                            # Combine the two together.
                            checked_text = f"{parent_comment.body} {pbody_original}"

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
                                f"[ZW] Bot: > {language} in defined multiple post for doublechecking"
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
        # Picks up a !missing command and messages the OP about it.
        if KEYWORDS.missing in pbody:
            if not css_check(oflair_css):
                # Basic check to see if this is something that can be acted on.
                continue

            logger.info(f"[ZW] Bot: COMMAND: {KEYWORDS.missing}, from u/{pauthor}.")

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
                f"[ZW] Bot: > Marked a post by u/{oauthor} as missing assets and messaged them."
            )

        if (
            any(keyword in pbody for keyword in THANKS_KEYWORDS)
            and KEYWORDS.translated not in pbody
            and len(pbody) <= 20
        ):
            # This processes simple thanks into translated, but leaves alone if it's an exception.
            # Has to be a short thanks, and not have !translated in the body.
            if oflair_css in ["meta", "community", "multiple", "app", "generic"]:
                continue

            if pauthor != oauthor:
                # Is the author of the comment the author of the post?
                continue  # If not, continue, we don't care about this.

            # This should only be marked if it's untranslated. So it shouldn't affect
            if oajo.status != "untranslated":
                continue

            # This should only be marked if it's not in an identified state, in case people respond to that command.
            if oajo.is_identified:
                continue

            exceptions_list = ["but", "however", "no"]  # Did the OP have reservations?
            if any(exception in pbody for exception in exceptions_list):
                continue
            # Okay, it really is a short thanks
            logger.info(
                f"[ZW] Bot: COMMAND: Short thanks from u/{pauthor}. Sending user a message..."
            )
            oajo.set_status("translated")
            oajo.set_time("translated", current_time)
            short_msg = (
                MSG_SHORT_THANKS_TRANSLATED.format(oauthor, opermalink) + BOT_DISCLAIMER
            )
            try:
                reddit.redditor(oauthor).message(
                    "[Notification] A message about your translation request",
                    short_msg,
                )
            except praw.exceptions.APIException:  # Likely shadowbanned.
                pass

        if KEYWORDS.claim in pbody:  # Claiming posts with the !claim command
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
            # ignore when someone edits their claim with translated or doublecheck
            if KEYWORDS.translated in pbody or KEYWORDS.doublecheck in pbody:
                continue

            logger.info(f"[ZW] Bot: COMMAND: {KEYWORDS.claim}, from u/{pauthor}.")
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
                if pauthor == claimer_name:
                    # If it's another claim by the same person listed...
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

            if not claimed_already:
                # This has not yet been claimed. We can claim it for the user.
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
                    f"[ZW] Bot: > Marked a post by u/{oauthor} as claimed and in progress."
                )

        if KEYWORDS.translated in pbody:
            # This is a !translated function that messages people when their post has been translated.
            thanks_already = False
            translated_found = True

            logger.info(f"[ZW] Bot: COMMAND: {KEYWORDS.translated}, from u/{pauthor}.")

            if oflair_css is None:  # If there is no CSS flair...
                oflair_css = "generic"  # Give it a generic flair.

            if oajo.type == "multiple":
                if isinstance(oajo.language_name, list):
                    # It is a defined multiple post.
                    # Try to see if there's data in the comment.
                    # If the comment is just the command, we take the parent comment and together check to see.
                    checked_text = str(pbody_original)
                    if len(pbody) < 12:
                        # This is just the command, so let's get the parent comment.
                        # Get the parent comment
                        parent_item = post.parent_id
                        if "t1" in parent_item:  # The parent is a comment
                            parent_comment = post.parent()
                            # Combine the two together.
                            checked_text = f"{parent_comment.body} {pbody_original}"

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
                                f"[ZW] Bot: > Marked {language} in this defined multiple post as done."
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

            if oajo.is_bot_crosspost and "bot_xp_original_comment" in komento_data:
                logger.debug("[ZW] Bot: >> Fetching original crosspost comment...")
                original_comment = reddit.comment(
                    komento_data["bot_xp_original_comment"]
                )
                original_comment_text = original_comment.body

                # We want to strip off the disclaimer
                original_comment_text = original_comment_text.split("---")[0].strip()

                # Add the edited text
                edited_header = "\n\n**Edit**: This crosspost has been marked as translated on r/translator."
                original_comment_text += edited_header + BOT_DISCLAIMER
                if "**Edit**" not in original_comment.body:
                    # Has this already been edited?
                    original_comment.edit(original_comment_text)
                    logger.debug(
                        "[ZW] Bot: >> Edited my original comment on the other subreddit to alert people."
                    )

            if "bot_long" in komento_data:  # Found a bot (Long) comment, delete it.
                long_comment = komento_data["bot_long"]
                long_comment = reddit.comment(long_comment)
                long_comment.delete()
            if "bot_claim_comment" in komento_data:
                # Found an older claim comment, delete it.
                claim_comment = komento_data["bot_claim_comment"]
                claim_comment = reddit.comment(claim_comment)
                claim_comment.delete()
            if "op_thanks" in komento_data:
                # OP has thanked someone in the thread before.
                thanks_already = True
                translated_found = False

            if (
                translated_found
                and not thanks_already
                and oflair_css not in ["multiple", "app"]
            ):
                # First we check to see if the author has already been recorded as getting a message.
                messaged_already = getattr(oajo, "author_messaged", False)

                # If the commentor is not the author of the post and they have not been messaged, we can tell them.
                if pauthor != oauthor and not messaged_already:
                    # Sends them notification msg
                    messaging_translated_message(oauthor=oauthor, opermalink=opermalink)
                    oajo.set_author_messaged(True)

        """MODERATOR-ONLY COMMANDS (!delete, !reset, !note, !set)"""

        if KEYWORDS.delete in pbody:
            # This is to allow OP or mods to !delete crossposts
            if not oajo.is_bot_crosspost:  # If this isn't actually a crosspost..
                continue
            # This really is a crosspost.
            logger.info(f"[ZW] Bot: COMMAND: {KEYWORDS.delete} from u/{pauthor}")
            if pauthor == oauthor or pauthor == requester or is_mod(pauthor):
                osubmission.mod.remove()  # We'll use remove for now -- can switch to delete() later.
                logger.info("[ZW] Bot: >> Removed crosspost.")

        if KEYWORDS.reset in pbody:
            # !reset command, to revert a post back to as if it were freshly processed
            if is_mod(pauthor) or pauthor == oauthor:
                # Check if user is a mod or the OP.
                logger.info(
                    f"[ZW] Bot: COMMAND: {KEYWORDS.reset}, from user u/{pauthor}."
                )
                oajo.reset(otitle)
                logger.info("[ZW] Bot: > Reset everything for the designated post.")
            else:
                continue

        if KEYWORDS.long in pbody and is_mod(pauthor):
            # !long command, for mods to mark a post as long for translators.
            logger.info(f"[ZW] Bot: COMMAND: {KEYWORDS.long}, from mod u/{pauthor}.")

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
                f"[ZW] Bot: Changed the designated post's long state to '{new_status}.'"
            )

        if KEYWORDS.note in pbody:
            # the !note command saves posts which are not CSS/template supported so they can be used as reference.
            # This is now rarely used.
            if not is_mod(pauthor):
                # Check to see if the person calling this command is a moderator
                continue
            match = comment_info_parser(pbody, "!note:")[0]
            language_name = converter(match)[1]
            logger.info(
                f"[ZW] Bot: COMMAND: {KEYWORDS.note}, from moderator u/{pauthor}."
            )
            record_to_wiki(
                odate=int(ocreated),
                otitle=otitle,
                oid=oid,
                oflair_text=language_name,
                s_or_i=True,
                oflair_new="",
            )  # Write to the saved page

        if KEYWORDS.set in pbody:
            # !set is a mod-accessible means of setting the post flair.
            # It removes the comment (through AM) so it looks like nothing happened.
            if not is_mod(pauthor):
                # Check to see if the person calling this command is a moderator
                continue

            set_data = comment_info_parser(pbody, "!set:")

            if set_data is not None:  # We have data.
                match = set_data[0]
                reset_state = set_data[1]
            else:  # Invalid command (likely did not include a language)
                continue

            logger.info(
                f"[ZW] Bot: COMMAND: {KEYWORDS.set}, from moderator u/{pauthor}."
            )

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
                if "bot_unknown" in komento_data:
                    # Delete previous Unknown template comment
                    unknown_default = komento_data["bot_unknown"]
                    unknown_default = reddit.comment(id=unknown_default)
                    unknown_default.delete()  # Changed from remove
                    logger.debug("[ZW] Bot: >> Deleted my default Unknown comment...")
                logger.info(
                    f"[ZW] Bot: > Updated the linkflair tag to '{language_code}'."
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
        if oflair_css not in ["community", "meta"]:
            # There's nothing to change for these
            oajo.update_reddit()  # Push all changes to the server
            # Write the Ajo to the local database
            ajo_writer(oajo, cursor_ajo, conn_ajo)
            logger.info(
                f"[ZW] Bot: Ajo for {oid} updated and saved to the local database."
            )
            # Record data on user commands.
            messaging_user_statistics_writer(pbody, pauthor)
            logger.debug("[ZW] Bot: Recorded user commands in database.")


def verification_parser() -> None:
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
            c_author_string = f"u/{c_author}"
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

        if current_time - ocreated >= 300 or osave:
            # Comment is too old, or has been processed already
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
        except (IndexError, AttributeError):
            # There must be something wrong with the verification comment.
            return  # Exit, don't do anything.

        try:
            notes = components[4]
        except IndexError:  # No notes were listed.
            notes = ""

        # Try and get a native language thank-you from our main language dictionary.
        language_code = converter(language_name)[0]
        thanks_phrase = MAIN_LANGUAGES.get(language_code, {}).get("thanks", "Thank you")

        # Form the entry for the verification log.
        entry = f"| {c_author_string} | {language_name} | [1]({url_1}), [2]({url_2}), [3]({url_3}) | {notes} |"
        page_content = reddit.subreddit(SUBREDDIT).wiki["verification_log"]
        page_content_new = str(page_content.content_md) + "\n" + entry

        # Update the verification log.
        page_content.edit(
            content=page_content_new,
            reason=f"Updating the verification log with a new request from u/{c_author}",
        )

        # Reply to the commenter, report so that moderators can take a look.
        comment.reply(
            COMMENT_VERIFICATION_RESPONSE.format(thanks_phrase, c_author)
            + BOT_DISCLAIMER
        )
        comment.report(f"Ziwen: Please check verification request from u/{c_author}.")
        logger.info(
            f"[ZW] Updated the verification log with a new request from u/{c_author}"
        )


def progress_checker() -> None:
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

    for post in search_results:
        # Now we process the ones that are stil marked as in progress to reset them.
        # Variable Creation
        oid = post.id
        oflair_css = post.link_flair_css_class
        opermalink = post.permalink

        if oflair_css is None or oflair_css != "inprogress":
            # If it's not actually an in progress one, let's skip it.
            continue

        # Load its Ajo.
        # First check the local database for the Ajo.
        oajo = ajo_loader(oid, cursor_ajo, POST_TEMPLATES, reddit)
        if oajo is None:
            # We couldn't find a stored dict, so we will generate it from the submission.
            logger.debug(
                "[ZW] progress_checker: Couldn't find an Ajo in the local database. Loading from Reddit."
            )
            oajo = Ajo(post, POST_TEMPLATES, USER_AGENT)

        # Process the post and get some data out of it.
        komento_data = komento_analyzer(post)
        if "claim_time_diff" in komento_data:
            # Get the time difference between its claimed time and now.
            time_difference = komento_data["claim_time_diff"]
            if time_difference > CLAIM_PERIOD:
                # This means the post is older than the claim time period.
                # Delete my advisory notice.
                claim_notice = reddit.comment(id=komento_data["bot_claim_comment"])
                claim_notice.delete()  # Delete the notice comment.
                logger.info(
                    f"[ZW] progress_checker: Post exceeded the claim time period. Reset. {opermalink}"
                )

                # Update the Ajo.
                oajo.set_status("untranslated")
                oajo.update_reddit()  # Push all changes to the server
                # Write the Ajo to the local database
                ajo_writer(oajo, cursor_ajo, conn_ajo)


"""LESSER RUNTIMES"""


def cc_ref() -> None:
    """
    This is a secondary runtime for Chinese language subreddits. The subreddits the bot monitors are contained in a
    multireddit called 'chinese'. It provides character and word lookup for them, same results as the
    ones on r/translator.

    :return: Nothing.
    """

    multireddit = reddit.multireddit(USERNAME, "chinese")
    posts = list(multireddit.comments(limit=MAXPOSTS))

    for post in posts:
        pid = post.id

        cursor_main.execute("SELECT * FROM oldcomments WHERE ID=?", [pid])
        if cursor_main.fetchone():
            # Post is already in the database
            continue

        pbody = post.body
        pbody = pbody.lower()

        if not any(key in pbody for key in KEYWORDS):
            # Does not contain our keyword
            continue

        cursor_main.execute("INSERT INTO oldcomments VALUES(?)", [pid])
        conn_main.commit()

        if KEYWORDS.back_quote in pbody:
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
                    tokenized_list.extend(lookup_zhja_tokenizer(simplify(match), "zh"))
                else:
                    tokenized_list.append(match)
            for match in tokenized_list:
                match_length = len(str(match))
                if match_length == 1:
                    to_post = zh_character(match, ZW_USERAGENT)
                    post_content.append(to_post)
                elif match_length >= 2:
                    find_word = str(match)
                    post_content.append(zh_word(find_word, ZW_USERAGENT))

            post_content = "\n\n".join(post_content)
            if len(post_content) > 10000:  # Truncate only if absolutely necessary.
                post_content = post_content[:9900]
            try:
                post.reply(post_content + BOT_DISCLAIMER)
                logger.info(
                    f"[ZW] CC_REF: Replied to lookup request for {tokenized_list} "
                    "on a Chinese subreddit."
                )
            except praw.exceptions.RedditAPIException:
                post.reply(
                    "Sorry, but the character data you've requested"
                    "exceeds the amount Reddit allows for a comment."
                )


def ziwen_maintenance() -> None:
    """
    A simple top-level function to group together common activities that need to be run on an occasional basis.
    This is usually activated after almost a hundred cycles to update information.

    :return: Nothing.
    """

    global POST_TEMPLATES
    POST_TEMPLATES = maintenance_template_retriever()
    logger.debug(
        f"[ZW] # Current post templates retrieved: {len(POST_TEMPLATES.keys())} templates"
    )

    global VERIFIED_POST_ID
    # Get the last verification thread's ID and store it.
    VERIFIED_POST_ID = maintenance_get_verified_thread()
    if len(VERIFIED_POST_ID):
        logger.info(
            f"[ZW] # Current verification post found: https://redd.it/{VERIFIED_POST_ID}\n\n"
        )
    else:
        logger.error("[ZW] # No current verification post found!")

    global ZW_USERAGENT
    ZW_USERAGENT = get_random_useragent()  # Pick a random useragent from our list.
    logger.debug(f"[ZW] # Current user agent: {ZW_USERAGENT}")

    global GLOBAL_BLACKLIST
    # We download the blacklist of users.
    GLOBAL_BLACKLIST = maintenance_blacklist_checker()
    logger.debug(
        f"[ZW] # Current global blacklist retrieved: {len(GLOBAL_BLACKLIST)} users"
    )

    global MOST_RECENT_OP
    MOST_RECENT_OP = maintenance_most_recent()

    points_worth_cacher()  # Update the points cache
    logger.debug("[ZW] # Points cache updated.")

    maintenance_database_processed_cleaner()  # Clean the comments that have been processed.


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
            ziwen_messages(reddit, cursor_main, conn_main, is_mod)
            # Finally checks for posts that are still claimed and 'in progress.'
            progress_checker()

            # Record API usage limit.
            probe = reddit.redditor(USERNAME).created_utc
            used_calls = reddit.auth.limits["used"]

            # Record memory usage at the end of an isochronism.
            mem_num = psutil.Process(os.getpid()).memory_info().rss
            mem_usage = f"Memory usage: {mem_num / (1024 * 1024):.2f} MB."
            logger.info(f"[ZW] Run complete. Calls used: {used_calls}. {mem_usage}")

            # Disable these functions if just testing on r/trntest.
            if not TESTING_MODE:
                logger.debug("[ZW] Main: Searching other subreddits.")
                verification_parser()  # The bot checks if there are any new requests for verification.
                cc_ref()  # Finally the bot runs lookup searches on Chinese subreddits.

        except Exception as e:  # The bot encountered an error/exception.
            logger.error(
                f"[ZW] Main: Encounted error {e}. {traceback.print_tb(e.__traceback__)}"
            )
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
            logger.info(f"[ZW] Main: Run complete. {elapsed_time:.2f} minutes.\n")
    except KeyboardInterrupt:  # Manual termination of the script with Ctrl-C.
        logger.info("Manual user shutdown.")
        sys.exit()
else:
    logger.info("[ZW] Main: Running as imported module.")
