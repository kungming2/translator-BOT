import calendar
import datetime
import re
import sys
import time
from typing import Dict, List

import jieba  # Segmenter for Mandarin Chinese.
import MeCab  # Advanced segmenter for Japanese.
import praw  # Simple interface to the Reddit API that also handles rate limiting of requests.
import prawcore  # The base module praw for error logging.
import tinysegmenter  # Basic segmenter for Japanese; not used on Windows.
from mafan import simplify

from _config import FILE_ADDRESS_MECAB, KEYWORDS, SUBREDDIT, THANKS_KEYWORDS, logger
from _language_consts import CJK_LANGUAGES
from _languages import comment_info_parser, converter, language_mention_search
from _login import USERNAME
from _responses import MSG_WIKIPAGE_FULL

CORRECTED_SUBREDDIT = SUBREDDIT
TESTING_MODE = False
# A boolean that enables the bot to send messages. Used for testing.
MESSAGES_OKAY = True
if len(sys.argv) > 1:  # This is a new startup with additional parameters for modes.
    specific_mode = sys.argv[1].lower()
    if specific_mode == "test":
        TESTING_MODE = True
        CORRECTED_SUBREDDIT = "trntest"
        MESSAGES_OKAY = False
        logger.info(
            f"Startup: Starting up in TESTING MODE for r/{CORRECTED_SUBREDDIT}..."
        )


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
    subreddit: str,
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
        page_content = reddit.subreddit(subreddit).wiki["saved"]
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
        page_content = reddit.subreddit(subreddit).wiki["identified"]
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
            reddit.subreddit("translatorBOT").message(message_subject, message_template)
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
):
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
        language_name = converter(parsed_data).language_name
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


def is_mod(reddit: praw.reddit, user: str) -> bool:
    """
    A function that can tell us if a user is a moderator of the operating subreddit (r/translator) or not.

    :param user: The Reddit username of an individual.
    :return: True if the user is a moderator, False otherwise.
    """
    # Get list of subreddit mods from r/translator.
    r = reddit.subreddit(CORRECTED_SUBREDDIT)
    moderators = [moderator.name.lower() for moderator in r.moderator()]
    return user.lower() in moderators
