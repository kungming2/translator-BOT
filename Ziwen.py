#!/usr/bin/env python3
"""
Ziwen is the main active component of u/translator-BOT, servicing r/translator and other communities.

Ziwen posts comments and sends messages and also moderates and keeps r/translator organized. It also provides community
members with useful reference information and enforces the community's formatting guidelines.
"""

import datetime
import os
import re
import sqlite3  # For processing and accessing the databases.
import sys
import time
import traceback  # For documenting errors that are encountered.
from typing import Dict, List

import praw  # Simple interface to the Reddit API that also handles rate limiting of requests.
import prawcore  # The base module praw for error logging.
import psutil
from mafan import simplify

from _config import (
    BOT_DISCLAIMER,
    FILE_ADDRESS_AJO_DB,
    FILE_ADDRESS_CACHE,
    FILE_ADDRESS_ERROR,
    FILE_ADDRESS_FILTER,
    FILE_ADDRESS_MAIN,
    KEYWORDS,
    THANKS_KEYWORDS,
    action_counter,
    get_random_useragent,
    logger,
    time_convert_to_string,
)
from _language_consts import MAIN_LANGUAGES
from _languages import (
    VERSION_NUMBER_LANGUAGES,
    bad_title_reformat,
    converter,
    language_mention_search,
    main_posts_filter,
    title_format,
)
from _login import PASSWORD, USERNAME, ZIWEN_APP_ID, ZIWEN_APP_SECRET
from _responses import (
    COMMENT_BAD_TITLE,
    COMMENT_DEFINED_MULTIPLE,
    COMMENT_ENGLISH_ONLY,
    COMMENT_LONG,
    COMMENT_UNKNOWN,
    COMMENT_VERIFICATION_RESPONSE,
    MSG_SHORT_THANKS_TRANSLATED,
)
from Ajo import Ajo, ajo_loader, ajo_writer
from notifier import record_activity_csv, ziwen_messages, ziwen_notifier
from zh_processing import zh_character, zh_word
from Ziwen_command_processor import KeywordInputTuple, ZiwenCommandProcessor
from Ziwen_helper import (
    CORRECTED_SUBREDDIT,
    MESSAGES_OKAY,
    TESTING_MODE,
    css_check,
    komento_analyzer,
    komento_submission_from_comment,
    lookup_matcher,
    lookup_zhja_tokenizer,
    record_to_wiki,
)

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

# This is how many posts Ziwen will retrieve all at once. PRAW can download 100 at a time.
MAXPOSTS = 100
# This is how many seconds Ziwen will wait between cycles. The bot is completely inactive during this time.
WAIT = 30
# After this many cycles, the bot will clean its database, keeping only the latest (CLEANCYCLES * MAXPOSTS) items.
CLEANCYCLES = 90
# How long do we allow people to `!claim` a post? This is defined in seconds.
CLAIM_PERIOD = 28800

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

logger.info("Startup: Accessing SQL databases...")

# This connects to the local cache used for detecting edits and the multiplier cache for points.
conn_cache = sqlite3.connect(FILE_ADDRESS_CACHE)
cursor_cache = conn_cache.cursor()

# This connects to the main database, including notifications, points, and past processed data.
conn_main = sqlite3.connect(FILE_ADDRESS_MAIN)
cursor_main = conn_main.cursor()

# This connects to the database for Ajos, objects that the bot generates for posts.
conn_ajo = sqlite3.connect(FILE_ADDRESS_AJO_DB)
cursor_ajo = conn_ajo.cursor()

# Connecting to the Reddit API via OAuth.
logger.info(f"Startup: Logging in as u/{USERNAME}...")
reddit = praw.Reddit(
    client_id=ZIWEN_APP_ID,
    client_secret=ZIWEN_APP_SECRET,
    password=PASSWORD,
    user_agent=USER_AGENT,
    username=USERNAME,
)
subredditHelper = reddit.subreddit(CORRECTED_SUBREDDIT)
logger.info(
    f"Startup: Initializing {BOT_NAME} {VERSION_NUMBER} for r/{CORRECTED_SUBREDDIT} with languages module {VERSION_NUMBER_LANGUAGES}."
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
    for template in subredditHelper.flair.link_templates:
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
    posts = list(subredditHelper.new(limit=100))

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
            f"Points determiner: {language_name} value in the cache: {final_point_value}"
        )
        return final_point_value  # Return the multipler - no need to go to the wiki.
    # Not found in the cache. Get from the wiki.
    # Fetch the wikipage.
    overall_page = reddit.subreddit(CORRECTED_SUBREDDIT).wiki[language_name.lower()]
    try:  # First see if this page actually exists
        overall_page_content = str(overall_page.content_md)
        last_month_data = overall_page_content.rsplit("\n", maxsplit=1)[-1]
    except prawcore.exceptions.NotFound:  # There is no such wikipage.
        logger.debug("Points determiner: The wiki page does not exist.")
        last_month_data = "2017 | 08 | [Example Link] | 1%"
        # Feed it dummy data if there's nothing... this language probably hasn't been done in a while.
    try:  # Try to get the percentage from the page
        total_percent = str(last_month_data.split(" | ")[3])[:-1]
        total_percent = float(total_percent)
    except IndexError:
        # There's a page but there is something wrong with data entered.
        logger.debug("Points determiner: There was a second error.")
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
        f"Points determiner: Multiplier for {language_name} is {final_point_value}"
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
            language_name = converter(language_tag.lower()[1:-1]).language_name
        elif "{" in oflair_text:  # Contains a bracket. Spanish {Mexico} (Identified)
            language_name = oflair_text.split("{")[0].strip()
        elif "(" in oflair_text:  # Contains a parantheses. Spanish (Identified)
            language_name = oflair_text.split("(")[0].strip()
        else:
            language_name = oflair_text

    try:
        language_multiplier = points_worth_determiner(
            converter(language_name).language_name
        )
        # How much is this language worth? Obtain it from our wiki.
    except prawcore.exceptions.Redirect:  # The wiki doesn't have this.
        language_multiplier = 20
    logger.debug(
        f"Points tabulator: {language_name}, {str(language_multiplier)} multiplier"
    )

    # This is in case the commenter is not actually the translator
    final_translator = ""
    final_translator_points = 0  # Same here.

    points = 0  # base number of points
    pid = comment.id  # comment ID for recording.
    # pscore = comment.score # We can't use this in live mode because comments are processed in real-time

    if "+" in pbody and len(pbody) < 3:  # Just a flat add  of points.
        logger.debug("Points tabulator: This is a flat point add.")
        parent_comment = comment.parent()  # Get the comment parent.
        try:  # Check if it's a comment:
            parent_post = parent_comment.parent_id
            final_translator = parent_comment.author.name
            logger.debug(
                f"Points tabulator: Actual translator: u/{final_translator} for {parent_post}"
            )
            final_translator_points += 3  # Give them a flat amount of points.
        except AttributeError:  # Parent is a post. Skip.
            logger.debug("Points tabulator: Parent of this comment is a post.")

    if (
        len(pbody) > 13 and oauthor != pauthor and KEYWORDS.translated in pbody
    ) or KEYWORDS.doublecheck in pbody:
        # This is a real translation.
        if (
            len(pbody) < 60
            and KEYWORDS.translated in pbody
            and any(keyword in pbody for keyword in VERIFYING_KEYWORDS)
        ):
            # This should be a verification command. Someone's agreeing that another is right.
            parent_comment = comment.parent()
            try:  # Check if it's a comment:
                parent_post = parent_comment.parent_id
                final_translator = parent_comment.author.name
                logger.debug(
                    f"Points tabulator: Actual translator: u/{final_translator}, {parent_post}"
                )
                final_translator_points += 1 + (1 * language_multiplier)
                points += 1  # Give the cleaner-upper a point.
            except AttributeError:  # Parent is a post.
                logger.debug("Points tabulator: Parent of this comment is a post.")
        else:
            logger.debug(
                f"Points tabulator: Seems to be a solid !translated comment by u/{pauthor}."
            )
            translator_to_add = pauthor
            points += 1 + (1 * language_multiplier)
    elif len(pbody) < 13 and KEYWORDS.translated in pbody:
        # It's marking someone else's translation as translated. We want to get the parent.
        logger.debug(
            f"Points tabulator: This is a cleanup !translated comment by u/{pauthor}."
        )
        parent_comment = comment.parent()
        try:  # Check if it's a comment:
            parent_post = parent_comment.parent_id
            final_translator = parent_comment.author.name
            logger.debug(
                f"Points tabulator: Actual translator: u/{final_translator} for {parent_post}"
            )
            final_translator_points += 1 + (1 * language_multiplier)
            if final_translator != pauthor:
                # Make sure it isn't someone just calling it on their own here
                points += 1  # We give the person who called the !translated comment a point for cleaning up
        except AttributeError:  # Parent is a post.
            logger.debug("Points tabulator: Parent of this comment is a post.")
        points += 1  # Give the cleaner-upper a point.
    elif len(pbody) > 13 and KEYWORDS.translated in pbody and pauthor == oauthor:
        # The OP marked it !translated, but with a longer comment.
        logger.debug(
            f"Points tabulator: A !translated comment by the OP u/{pauthor} for someone else?."
        )
        parent_comment = comment.parent()
        try:  # Check if it's a comment:
            parent_post = parent_comment.parent_id
            final_translator = parent_comment.author.name
            if final_translator != oauthor:
                logger.debug(
                    f"Points tabulator: Actual translator: u/{final_translator}, {parent_post}"
                )
                final_translator_points += 1 + (1 * language_multiplier)
        except AttributeError:  # Parent is a post.
            logger.debug("Points tabulator: Parent of this comment is a post.")

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
        logger.debug("Points tabulator: Found an OP short thank you.")
        parent_comment = comment.parent()
        try:  # Check if it's a comment:
            parent_post = parent_comment.parent_id
            final_translator = (
                parent_comment.author.name
            )  # This is the person OP thanked.
            logger.debug(
                f"Points tabulator: Actual translator: u/{final_translator} for {parent_post}"
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
                "Points tabulator: Parent of this comment is a post. Never mind."
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
        logger.debug(f"Points tabulator: Saved: {entry}")
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

    for submission in subredditHelper.new(limit=1):
        # Get the last posted post in the subreddit.
        sutc = submission.created_utc
        slink = f"https://www.reddit.com{submission.permalink}"
        s_format_time = str(
            datetime.datetime.fromtimestamp(sutc).strftime(
                "%a, %b %d, %Y [%I:%M:%S %p]"
            )
        )
    for comment in subredditHelper.comments(limit=1):  # Get the last posted comment
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
                logger.error("Error_Log: Encountered a Unicode writing error.")


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
        logger.debug("messaging_user_statistics_writer: No commands to write.")


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
        comments = list(subredditHelper.comments(limit=comment_limit))
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
                f"Edit Finder: Comment '{cid}' was previously stored in the cache."
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
                f"Edit Finder: An edit for comment '{cid}' was detected. Processing..."
            )
            cleanup_database = True

            # We detected a possible `lookup` change, where the words looked up are now different.
            if "`" in cbody:
                # First thing is compare the data in a lookup comment against what we have.

                # Here we use the lookup_matcher function to get a LIST of everything that used to be in the graves.
                total_matches = lookup_matcher(old_cbody, None)

                # Then we get data from Komento, specifically looking for its version of results.
                new_vars = komento_analyzer(
                    reddit, komento_submission_from_comment(reddit, cid)
                )
                new_overall_lookup_data = new_vars.get("bot_lookup_correspond", {})
                if cid in new_overall_lookup_data:
                    # This comment is in our data
                    new_total_matches = new_overall_lookup_data[cid]
                    # Get the new matches
                    # Are they the same?
                    if set(new_total_matches) == set(total_matches):
                        logger.debug(
                            f"Edit-Finder: No change found for lookup comment '{cid}'."
                        )
                        continue
                    logger.debug(
                        f"Edit-Finder: Change found for lookup comment '{cid}'."
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
                            f"Edit Finder: New command {keyword} detected for comment '{cid}'."
                        )
                        force_change = True

                if force_change:
                    # Delete the comment from the processed database to force it to update and reprocess.
                    delete_comment_command = "DELETE FROM oldcomments WHERE id = ?"
                    cursor_main.execute(delete_comment_command, (cid,))
                    conn_main.commit()
                    logger.debug(
                        f"Edit Finder: Removed edited comment `{cid}` from processed database."
                    )

        else:  # This is a comment that has not been stored.
            logger.debug(f"Edit Finder: New comment '{cid}' to store in the cache.")
            cleanup_database = True

            try:
                # Insert the comment into our cache.
                cache_command = "INSERT INTO comment_cache VALUES (?, ?)"
                new_tuple = (cid, cbody)
                cursor_cache.execute(cache_command, new_tuple)
                conn_cache.commit()
            except ValueError:  # Some sort of invalid character, don't write it.
                logger.debug(
                    f"Edit Finder: ValueError when inserting comment `{cid}` into cache."
                )

    if cleanup_database:  # There's a need to clean it up.
        cleanup = "DELETE FROM comment_cache WHERE id NOT IN (SELECT id FROM comment_cache ORDER BY id DESC LIMIT ?)"
        cursor_cache.execute(cleanup, (comment_limit,))

        # Delete all but the last comment_limit comments.
        conn_cache.commit()
        logger.debug("Edit Finder: Cleaned up the edited comments cache.")


"""
POSTS FILTERING & TESTING FUNCTIONS

This is the main routine to check for incoming posts, assign them the appropriate category, and activate notifications.
The function also removes posts that don't match the formatting guidelines.
"""


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
    logger.debug(f"Fetching new r/{CORRECTED_SUBREDDIT} posts at {current_time}.")

    # We get the last 80 new posts. Changed from the deprecated `submissions` method.
    # This should allow us to retrieve stuff from up to a day in case of power outages or moving.
    posts = list(subredditHelper.new(limit=80))
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
                f"Posts: This post {oid} already exists in the processed database."
            )
            continue
        cursor_main.execute("INSERT INTO oldposts VALUES(?)", [oid])
        conn_main.commit()

        if not css_check(oflair_css) and oflair_css is not None:
            # If it's a Meta or Community post (that's what css_check does), just alert those signed up for it.
            suggested_css_text = oflair_css
            logger.info(f"Posts: New {suggested_css_text.title()} post.")

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
            komento_data = komento_analyzer(reddit, post)
            if "bot_xp_comment" in komento_data:
                op_match = komento_data["bot_xp_op"]
                oauthor = op_match

        if oauthor.lower() in GLOBAL_BLACKLIST:
            # This user is on our blacklist. (not used much, more precautionary)
            post.mod.remove()
            action_counter(1, "Blacklisted posts")  # Write to the counter log
            logger.info(
                f"Posts: Filtered a post out because its author u/{oauthor} is on my blacklist."
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
                logger.info(f"Posts: New post, {otitle} by u/{oauthor}.")
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
                    f"Posts: Removed post that violated formatting guidelines. Title: {otitle}"
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
                    "Posts: Title formatting routine crashed and encountered an exception."
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
                logger.info("Posts: Removed an English-only post.")

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
                        reddit=reddit,
                        subreddit=CORRECTED_SUBREDDIT,
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
                    f"Posts: Title formatting routine couldn't make sense of '{otitle}'."
                )

            if len(oselftext) > 1400:
                # This changes the CSS text to indicate if it's a long wall of text
                logger.info("Posts: This is a long piece of text.")
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
                        multiple_language_text = converter(notification).language_name
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
                    )

            # If it's an unknown post, add an informative comment.
            if final_css_class == "unknown" and post.author.name != "translator-BOT":
                post.reply(COMMENT_UNKNOWN + BOT_DISCLAIMER)
                logger.info("Posts: Added the default 'Unknown' information comment.")

            # Actually update the flair. Legacy version first.
            logger.info(
                f"Posts: Set flair to class '{final_css_class}' and text '{final_css_text}.'"
            )

            # New Redesign Version to update flair
            # Check the global template dictionary
            if final_css_class in POST_TEMPLATES.keys():
                output_template = POST_TEMPLATES[final_css_class]
                post.flair.select(output_template, final_css_text)
                logger.debug("Posts: Flair template selected for post.")

            # Finally, create an Ajo object and save it locally.
            if final_css_class not in ["meta", "community"]:
                # Create an Ajo object, reload the post.
                pajo = Ajo(reddit.submission(id=post.id), POST_TEMPLATES, USER_AGENT)
                if len(contacted) != 0:  # We have a list of notified users.
                    pajo.add_notified(contacted)
                # Save it to the local database
                ajo_writer(pajo, cursor_ajo, conn_ajo)
                logger.debug(
                    "Posts: Created Ajo for new post and saved to local database."
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

    logger.debug(f"Fetching new r/{CORRECTED_SUBREDDIT} comments...")
    comments = []
    try:
        comments += list(subredditHelper.comments(limit=MAXPOSTS))
    except prawcore.exceptions.ServerError:  # Server issues.
        return

    for comment in comments:
        pid = comment.id

        try:
            pauthor = comment.author.name
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
        osubmission = comment.submission
        oid = osubmission.id
        opermalink = osubmission.permalink
        otitle = osubmission.title
        oflair_text = osubmission.link_flair_text  # This is the linkflair text
        # This is the linkflair css class (lowercase)
        oflair_css = osubmission.link_flair_css_class
        ocreated = comment.created_utc  # Unix time when this comment was created.
        # We save verification requests so we don't work on them.
        osaved = comment.saved
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

        pbody = comment.body
        pbody_original = str(pbody)  # Create a copy with capitalization
        pbody = pbody.lower()

        # Calculate points for the person.
        if oflair_text is not None and osaved is not True and oauthor is not None:
            # We don't want to process it without the oflair text. Or if its verified comment
            logger.debug(f"Bot: Processing points for u/{pauthor}")
            points_tabulator(oid, oauthor, oflair_text, oflair_css, comment)

        """AJO CREATION"""
        # Create an Ajo object.
        if css_check(oflair_css):
            # Check the database for the Ajo.
            oajo = ajo_loader(oid, cursor_ajo, POST_TEMPLATES, reddit)

            if oajo is None:
                # We couldn't find a stored dict, so we will generate it from the submission.
                logger.debug("Bot: Couldn't find an AJO in the local database.")
                oajo = Ajo(osubmission, POST_TEMPLATES, USER_AGENT)

            if oajo.is_bot_crosspost:
                komento_data = komento_analyzer(
                    reddit, komento_submission_from_comment(reddit, pid)
                )
                if "bot_xp_comment" in komento_data:
                    op_match = komento_data["bot_xp_op"]
                    oauthor = op_match  # We're going to mark the original post author as another if it's a crosspost.
                    requester = komento_data["bot_xp_requester"]
        else:  # This is either a meta or a community post
            logger.debug("Bot: Post appears to be either a meta or community post.")
            continue

        if not any(key in pbody for key in KEYWORDS) and not any(
            phrase in pbody for phrase in THANKS_KEYWORDS
        ):
            # Does not contain our keyword
            logger.debug(f"Bot: Post {oid} does not contain any operational keywords.")
            continue

        if TESTING_MODE and current_time - ocreated >= 3600:
            # This is a function to help stop the incessant commenting on older posts when testing
            # If the comment is older than an hour, ignore
            continue

        # Record to the counter with the keyword.
        for keyword in KEYWORDS:
            if keyword in pbody:
                action_counter(1, keyword)  # Write to the counter log

        # We move the exit point if there is no author here. Since !restore relies on there being no author.
        if oauthor is None:
            logger.info("Bot: >> Author is deleted or non-existent.")
            oauthor = "deleted"

        processor = ZiwenCommandProcessor(
            ZW_USERAGENT,
            reddit,
            cursor_main,
            cursor_ajo,
            conn_main,
            POST_TEMPLATES,
            pbody,
            pauthor,
            comment,
            oflair_css,
            otitle,
            opermalink,
            oauthor,
            oajo,
            osubmission,
            oid,
            ocreated,
            pid,
            pbody_original,
            requester,
        )

        relevant_keywords = {
            KEYWORDS.page: processor.process_page,
            KEYWORDS.back_quote: processor.process_backquote,
            KEYWORDS.missing: processor.process_missing,
            KEYWORDS.translated: processor.process_translated,
            KEYWORDS.id: processor.process_id,
            KEYWORDS.set: processor.process_set,
            KEYWORDS.note: processor.process_note,
            KEYWORDS.reference: processor.process_reference,
            KEYWORDS.search: processor.process_search,
            KEYWORDS.doublecheck: processor.process_doublecheck,
            KEYWORDS.identify: processor.process_id,
            # KEYWORDS.translate:,
            # KEYWORDS.translator:,
            KEYWORDS.delete: processor.process_delete,
            KEYWORDS.claim: processor.process_claim,
            KEYWORDS.reset: processor.process_reset,
            KEYWORDS.long: processor.process_long,
            KEYWORDS.restore: processor.process_restore,
        }

        for keyword, func in relevant_keywords.items():
            if keyword in pbody:
                command_name = keyword
                if keyword == KEYWORDS.back_quote:
                    command_name = "`lookup`"
                logger.info(f"Bot: COMMAND: {command_name}, from u/{pauthor}.")
                func()

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
                f"Bot: COMMAND: Short thanks from u/{pauthor}. Sending user a message..."
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

        # Push the FINAL UPDATE TO REDDIT
        if oflair_css not in ["community", "meta"]:
            # There's nothing to change for these
            oajo.update_reddit()  # Push all changes to the server
            # Write the Ajo to the local database
            ajo_writer(oajo, cursor_ajo, conn_ajo)
            logger.info(f"Bot: Ajo for {oid} updated and saved to the local database.")
            # Record data on user commands.
            messaging_user_statistics_writer(pbody, pauthor)
            logger.debug("Bot: Recorded user commands in database.")


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
        language_code = converter(language_name).language_code
        thanks_phrase = MAIN_LANGUAGES.get(language_code, {}).get("thanks", "Thank you")

        # Form the entry for the verification log.
        entry = f"| {c_author_string} | {language_name} | [1]({url_1}), [2]({url_2}), [3]({url_3}) | {notes} |"
        page_content = reddit.subreddit(CORRECTED_SUBREDDIT).wiki["verification_log"]
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
            f"Updated the verification log with a new request from u/{c_author}"
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
    search_results = subredditHelper.search(
        search_query, time_filter="month", sort="new"
    )

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
                "progress_checker: Couldn't find an Ajo in the local database. Loading from Reddit."
            )
            oajo = Ajo(post, POST_TEMPLATES, USER_AGENT)

        # Process the post and get some data out of it.
        komento_data = komento_analyzer(reddit, post)
        if "claim_time_diff" in komento_data:
            # Get the time difference between its claimed time and now.
            time_difference = komento_data["claim_time_diff"]
            if time_difference > CLAIM_PERIOD:
                # This means the post is older than the claim time period.
                # Delete my advisory notice.
                claim_notice = reddit.comment(id=komento_data["bot_claim_comment"])
                claim_notice.delete()  # Delete the notice comment.
                logger.info(
                    f"progress_checker: Post exceeded the claim time period. Reset. {opermalink}"
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
                    f"CC_REF: Replied to lookup request for {tokenized_list} "
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
        f"# Current post templates retrieved: {len(POST_TEMPLATES.keys())} templates"
    )

    global VERIFIED_POST_ID
    # Get the last verification thread's ID and store it.
    VERIFIED_POST_ID = maintenance_get_verified_thread()
    if len(VERIFIED_POST_ID):
        logger.info(
            f"# Current verification post found: https://redd.it/{VERIFIED_POST_ID}\n\n"
        )
    else:
        logger.error("# No current verification post found!")

    global ZW_USERAGENT
    ZW_USERAGENT = get_random_useragent()  # Pick a random useragent from our list.
    logger.debug(f"# Current user agent: {ZW_USERAGENT}")

    global GLOBAL_BLACKLIST
    # We download the blacklist of users.
    GLOBAL_BLACKLIST = maintenance_blacklist_checker()
    logger.debug(f"# Current global blacklist retrieved: {len(GLOBAL_BLACKLIST)} users")

    global MOST_RECENT_OP
    MOST_RECENT_OP = maintenance_most_recent()

    points_worth_cacher()  # Update the points cache
    logger.debug("# Points cache updated.")

    maintenance_database_processed_cleaner()  # Clean the comments that have been processed.


"""INITIAL VARIABLE SET-UP"""

# We start the bot with a couple of routines to populate the data from our wiki.
ziwen_maintenance()
logger.info("Bot routine starting up...")


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
            ziwen_messages(reddit, cursor_main, conn_main)
            # Finally checks for posts that are still claimed and 'in progress.'
            progress_checker()

            # Record API usage limit.
            probe = reddit.redditor(USERNAME).created_utc
            used_calls = reddit.auth.limits["used"]

            # Record memory usage at the end of an isochronism.
            mem_num = psutil.Process(os.getpid()).memory_info().rss
            mem_usage = f"Memory usage: {mem_num / (1024 * 1024):.2f} MB."
            logger.info(f"Run complete. Calls used: {used_calls}. {mem_usage}")

            # Disable these functions if just testing on r/trntest.
            if not TESTING_MODE:
                logger.debug("Main: Searching other subreddits.")
                verification_parser()  # The bot checks if there are any new requests for verification.
                cc_ref()  # Finally the bot runs lookup searches on Chinese subreddits.

        except Exception as e:  # The bot encountered an error/exception.
            logger.error(
                f"Main: Encounted error {e}. {traceback.print_tb(e.__traceback__)}"
            )
            # Format the error text.
            error_entry = traceback.format_exc()
            record_error_log(error_entry)  # Save the error to a log.
            logger.error("Main: > Logged this error. Ended run.")
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
            logger.info(f"Main: Run complete. {elapsed_time:.2f} minutes.\n")
    except KeyboardInterrupt:  # Manual termination of the script with Ctrl-C.
        logger.info("Manual user shutdown.")
        sys.exit()
else:
    logger.info("Main: Running as imported module.")
