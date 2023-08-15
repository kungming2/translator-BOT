import calendar
import re
import sqlite3
import sys
from time import time
from code._config import (
    FILE_ADDRESS_AJO_DB,
    FILE_ADDRESS_CACHE,
    FILE_ADDRESS_MAIN,
    FILE_ADDRESS_MECAB,
    KEYWORDS,
    SUBREDDIT,
    THANKS_KEYWORDS,
    get_random_useragent,
    logger,
)
from code._language_consts import CJK_LANGUAGES
from code._languages import comment_info_parser, convert, language_mention_search
from code._login import USERNAME
from code._responses import MSG_WIKIPAGE_FULL
from datetime import datetime
from typing import Any, Dict, List

import jieba  # Segmenter for Mandarin Chinese.
import MeCab  # Advanced segmenter for Japanese.
import praw  # Simple interface to the Reddit API that also handles rate limiting of requests.
import prawcore  # The base module praw for error logging.
import tinysegmenter  # Basic segmenter for Japanese; not used on Windows.
from mafan import simplify

CORRECTED_SUBREDDIT = SUBREDDIT
TESTING_MODE = False
# A boolean that enables the bot to send messages. Used for testing.
MESSAGES_OKAY = True
# This is how many posts Ziwen will retrieve all at once. PRAW can download 100 at a time.
MAXPOSTS = 100
# How long do we allow people to `!claim` a post? This is defined in seconds.
CLAIM_PERIOD = 28800

if len(sys.argv) > 1:  # This is a new startup with additional parameters for modes.
    if sys.argv[1].lower() == "test":
        TESTING_MODE = True
        CORRECTED_SUBREDDIT = "trntest"
        MESSAGES_OKAY = False
        logger.info(
            f"Startup: Starting up in TESTING MODE for r/{CORRECTED_SUBREDDIT}..."
        )


# for stateful variables used outside this module for easy access
class ZiwenConfig:
    def __init__(
        self,
        reddit: praw.Reddit,
        subreddit_helper: praw.reddit.models.SubredditHelper,
    ):
        # This connects to the local cache used for detecting edits and the multiplier cache for points.
        self.conn_cache = sqlite3.connect(FILE_ADDRESS_CACHE)
        self.conn_cache.row_factory = sqlite3.Row
        self.cursor_cache = self.conn_cache.cursor()

        # This connects to the main database, including notifications, points, and past processed data.
        self.conn_main = sqlite3.connect(FILE_ADDRESS_MAIN)
        self.conn_main.row_factory = sqlite3.Row
        self.cursor_main = self.conn_main.cursor()

        # This connects to the database for Ajos, objects that the bot generates for posts.
        self.conn_ajo = sqlite3.connect(FILE_ADDRESS_AJO_DB)
        self.conn_ajo.row_factory = sqlite3.Row
        self.cursor_ajo = self.conn_ajo.cursor()
        self.reddit = reddit
        self.subreddit_helper = subreddit_helper
        self.post_templates = {}
        self.verified_post_id = None
        self.zw_useragent = {}
        self.global_blacklist = []
        self.most_recent_op = []
        # A cache for language multipliers, generated each instance of running.
        # Allows us to access the wiki less and speed up the process.
        self.cached_multipliers: Dict[str, int] = {}

    def is_mod(self, user: str) -> bool:
        """
        A function that can tell us if a user is a moderator of the operating subreddit (r/translator) or not.

        :param user: The Reddit username of an individual.
        :return: True if the user is a moderator, False otherwise.
        """
        # Get list of subreddit mods from r/translator.
        moderators = [
            moderator.name.lower() for moderator in self.subreddit_helper.moderator()
        ]
        return user.lower() in moderators

    """
    MAINTENANCE FUNCTIONS

    These functions are run at Ziwen's startup and also occasionally in order to refresh their information. Most of them
    fetch data from r/translator itself or r/translatorBOT for internal variables.

    Maintenance functions are all prefixed with `maintenance` in their name.
    """

    def maintenance_template_retriever(self) -> Dict[str, str]:
        """
        Function that retrieves the current flairs available on the subreddit and returns a dictionary.
        Dictionary is keyed by the old css_class, with the long-form template ID as a value per key.
        Example: 'cs': XXXXXXXX

        :return new_template_ids: A dictionary containing all the templates on r/translator.
        :return: An empty dictionary if it cannot find the templates for some reason.
        """

        new_template_ids = {}

        # Access the templates on the subreddit.
        for template in self.subreddit_helper.flair.link_templates:
            css_associated_code = template["css_class"]
            new_template_ids[css_associated_code] = template["id"]

        # Return a dictionary, if there's data, otherwise return an empty dictionary.
        return new_template_ids if len(new_template_ids) != 0 else {}

    def maintenance_most_recent(self) -> List[str]:
        """
        A function that grabs the usernames of people who have submitted to r/translator in the last 24 hours.
        Another function can check against this to make sure people aren't submitting too many.

        :return most_recent: A list of usernames that have recently submitted to r/translator. Duplicates will be on there.
        """

        # Define the time parameters (24 hours earlier from present)
        most_recent = []
        current_time_day_ago = int(time()) - 86400

        # 100 should be sufficient for the last day, assuming a monthly total of 3000 posts.
        posts = list(self.subreddit_helper.new(limit=100))

        # Process through them - we really only care about the username and the time.
        for post in posts:
            ocreated = int(post.created_utc)  # Unix time when this post was created.

            try:
                oauthor = post.author.name
            except AttributeError:
                # Author is deleted. We don't care about this post.
                continue

            # If the time of the post is after our limit, add it to our list.
            if ocreated > current_time_day_ago and oauthor != "translator-BOT":
                most_recent.append(oauthor)

        # Return the list
        return most_recent

    def maintenance_get_verified_thread(self) -> str | None:
        """
        Function to quickly get the Reddit ID of the latest verification thread on startup.
        This way, the ID of the thread does not need to be hardcoded into Ziwen.

        :return verification_id: The Reddit ID of the newest verification thread as a string.
        """

        # Search for the latest verification thread.
        search_term = "title:verified AND flair:meta"

        # Note that even in testing ('trntest') we will still search r/translator for the thread.
        search_results = self.reddit.subreddit("translator").search(
            search_term, time_filter="year", sort="new", limit=1
        )

        # Iterate over the results generator to get the ID.
        verification_id = None
        for post in search_results:
            verification_id = post.id

        return verification_id

    def maintenance_blacklist_checker(self) -> List[str]:
        """
        A start-up function that runs once and gets blacklisted usernames from the wiki of r/translatorBOT.
        Blacklisted users are those who have abused the subreddit functions on r/translator but are not banned.
        This is an anti-abuse system, and it also disallows them from crossposting with Ziwen Streamer.

        :return blacklist_usernames: A list of usernames on the blacklist, all in lowercase.
        """

        # Retrieve the page.
        blacklist_page = self.reddit.subreddit("translatorBOT").wiki["blacklist"]
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

    def maintenance_database_processed_cleaner(self) -> None:
        """
        Function that cleans up the database of processed comments, but not posts (yet).

        :return: Nothing.
        """

        pruning_command = "DELETE FROM oldcomments WHERE id NOT IN (SELECT id FROM oldcomments ORDER BY id DESC LIMIT ?)"
        self.cursor_main.execute(pruning_command, [MAXPOSTS * 10])
        self.conn_main.commit()

    """
    POINTS TABULATING SYSTEM

    Ziwen has a live points system (meaning it calculates users' points as they make their comments) to help users keep
    track of their contributions to the community. The points system is not as public as some other communities that have
    points bots, but is instead meant to be more private. A summary table to the months' contributors is posted by Wenyuan
    at the start of every month.

    Points-related functions are all prefixed with `points` in their name. 
    """

    def points_worth_determiner(self, language_name: str) -> int:
        """
        This function takes a language name and determines the points worth for a translation for it. (the cap is 20)

        :param language_name: The name of the language we want to know the points worth for.
        :return final_point_value: The points value for the language expressed as an integer.
        """
        for spacing in " -":  # The wiki does not support dashes or underscores in urls.
            if spacing in language_name:
                language_name = language_name.replace(spacing, "_")

        if language_name == "Unknown":
            return 4  # The multiplier for Unknown can be hard coded.

        # Code to check the cache first to see if we have a value already.
        # Look for the dictionary key of the language name.
        final_point_value = self.cached_multipliers.get(language_name)

        if final_point_value is not None:  # It's cached.
            logger.debug(
                f"Points determiner: {language_name} value in the cache: {final_point_value}"
            )
            return (
                final_point_value  # Return the multipler - no need to go to the wiki.
            )
        # Not found in the cache. Get from the wiki.
        # Fetch the wikipage.
        overall_page = self.reddit.subreddit(CORRECTED_SUBREDDIT).wiki[
            language_name.lower()
        ]
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
            total_percent = 1.0

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
        self.cached_multipliers.update({language_name: final_point_value})

        # Write data to the cache so that it can be retrieved later.
        current_time = time()
        month_string = datetime.fromtimestamp(current_time).strftime("%Y-%m")
        insert_data = (month_string, language_name, final_point_value)
        self.cursor_cache.execute(
            "INSERT INTO multiplier_cache VALUES (?, ?, ?)", insert_data
        )
        self.conn_cache.commit()

        return final_point_value

    def points_worth_cacher(self) -> None:
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
        current_time = time()
        month_string = datetime.fromtimestamp(current_time).strftime("%Y-%m")

        # Select from the database the current months data if it exists.
        multiplier_command = "SELECT * from multiplier_cache WHERE month_year = ?"
        self.cursor_cache.execute(multiplier_command, (month_string,))
        multiplier_entries = self.cursor_cache.fetchall()
        # If not current, fetch new data and save it.

        if len(multiplier_entries) != 0:  # We actually have cached data for this month.
            # Populate the dictionary format from our data
            for entry in multiplier_entries:
                multiplier_name = entry[1]
                multiplier_worth = int(entry[2])
                self.cached_multipliers[multiplier_name] = multiplier_worth
        else:  # We don't have cached data so we will retrieve it from the wiki.
            # Delete everything from the cache (clearing out previous months' data as well)
            command = "DELETE FROM multiplier_cache"
            self.cursor_cache.execute(command)
            self.conn_cache.commit()

            # Get the data for the common languages
            for language in check_languages:
                # Fetch the number of points it's worth.
                self.points_worth_determiner(language)

                # Write the data to the cache.
                self.conn_cache.commit()

    def ziwen_maintenance(self) -> None:
        """
        A simple top-level function to group together common activities that need to be run on an occasional basis.
        This is usually activated after almost a hundred cycles to update information.

        :return: Nothing.
        """

        self.post_templates = self.maintenance_template_retriever()
        logger.debug(
            f"# Current post templates retrieved: {len(self.post_templates.keys())} templates"
        )

        # Get the last verification thread's ID and store it.
        self.verified_post_id = self.maintenance_get_verified_thread()
        if len(self.verified_post_id):
            logger.info(
                f"# Current verification post found: https://redd.it/{self.verified_post_id}\n\n"
            )
        else:
            logger.error("# No current verification post found!")
        # Pick a random useragent from our list.
        self.zw_useragent = get_random_useragent()
        logger.debug(f"# Current user agent: {self.zw_useragent}")

        # We download the blacklist of users.
        self.global_blacklist = self.maintenance_blacklist_checker()
        logger.debug(
            f"# Current global blacklist retrieved: {len(self.global_blacklist)} users"
        )

        self.most_recent_op = self.maintenance_most_recent()

        self.points_worth_cacher()  # Update the points cache
        logger.debug("# Points cache updated.")

        self.maintenance_database_processed_cleaner()  # Clean the comments that have been processed.


def css_check(css_class: str) -> bool:
    """
    Function that checks if a CSS class is something that a command can act on.

    :param css_class: The css_class of the post.
    :return: True if the post is something than can be worked with, False if it's in either of the defined two classes.
    """

    return css_class not in ["meta", "community"]


def record_to_wiki(
    odate: int,
    otitle: str,
    oid: str,
    oflair_text: str,
    s_or_i: bool,
    oflair_new: str,
    reddit: praw.Reddit,
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

    oformat_date = datetime.fromtimestamp(int(odate)).strftime("%Y-%m-%d")

    if s_or_i:  # Means we should write to the 'saved' page:
        page_content = reddit.subreddit(CORRECTED_SUBREDDIT).wiki["saved"]
        new_content = (
            f"| {oformat_date} | [{otitle}](https://redd.it/{oid}) | {oflair_text} |"
        )
        page_content_new = str(page_content.content_md) + "\n" + new_content
        # Adds this language entry to the 'saved page'
        page_content.edit(
            content=page_content_new,
            reason='Ziwen: updating the "Saved" page with a new link',
        )
        logger.info("Save_Wiki: Updated the 'saved' wiki page.")
    else:  # Means we should write to the 'identified' page:
        page_content = reddit.subreddit(CORRECTED_SUBREDDIT).wiki["identified"]
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
            logger.warning(f"Save_Wiki: The '{page_name}' wiki page is full.")
            reddit.subreddit("translatorBOT").message(
                subject=message_subject, message=message_template
            )
        logger.info("Save_Wiki: Updated the 'identified' wiki page.")


def komento_submission_from_comment(
    reddit: praw.Reddit, comment_id: str
) -> praw.reddit.models.Submission:
    """
    Returns the parent submission as an object from a comment ID.

    :param comment_id: The Reddit ID for the comment, expressed as a string.
    :return: Returns the PRAW Submission object of the parent post.
    """

    main_comment = reddit.comment(id=comment_id)  # Convert ID into comment object.
    main_submission = main_comment.link_id[3:]  # Strip the t3_ from front.
    # Get actual PRAW submission object.
    return reddit.submission(id=main_submission)


"""
KOMENTO ANALYZER

Similar to the Ajo in its general purpose, a Komento object (which is a dictionary) provides anchors and references
for the bot to check its own output and commands as well.

Komento-related functions are all prefixed with `komento` in their name. 
"""


def komento_analyzer(
    reddit: praw.Reddit, reddit_submission: praw.reddit.models.Submission
) -> dict[str, Any]:
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

                current_c_time = time()
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

                comment_datetime = datetime(
                    num_year, num_month, num_day, num_hour, num_min, num_sec
                )
                # Returns the time in UTC.
                utc_timestamp = calendar.timegm(comment_datetime())
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
            #
            # if sys.platform == "darwin":  # Different location of the dictionary files,
            #     mecab_directory = "/usr/local/lib/mecab/dic/mecab-ipadic-neologd"
            # else:
            #     mecab_directory = "/usr/lib/mecab/dic/mecab-ipadic-neologd"
            mecab_tagger = MeCab.Tagger(f"r'-d {FILE_ADDRESS_MECAB}'")
            # Per https://github.com/SamuraiT/mecab-python3/issues/3 to fix Unicode issue
            mecab_tagger.parse(phrase)
            parsed = mecab_tagger.parseToNode(phrase.strip())
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
        language_name = convert(parsed_data).language_name
    # Secondly we see if there's a language mentioned.
    elif (
        language_mention_search(content_text) is not None
        and len(language_mentions) == 1
    ):
        language_name = language_mentions[0]

    # Work with the text and clean it up.
    try:
        # Delete stuff before
        content_text = content_text.split(KEYWORDS.back_quote, 1)[1]
        # Delete stuff after
        content_text = content_text.rsplit(KEYWORDS.back_quote, 1)[0]
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
        logger.debug(f"Lookup_Matcher: Provisional: {zhja_temp_list}")

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
