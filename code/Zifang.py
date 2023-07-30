#!/usr/bin/env python3
"""
Zifang is a new addition to help Ziwen with some ancillary tasks.
"""
import re
import sys
import time
import traceback
from code._config import (
    BOT_DISCLAIMER,
    FILE_ADDRESS_ERROR,
    SUBREDDIT,
    action_counter,
    logger,
)
from code._languages import VERSION_NUMBER_LANGUAGES, converter
from code._login import PASSWORD, USERNAME, ZIFANG_APP_ID, ZIFANG_APP_SECRET
from code._responses import (
    ZF_CLOSING_OUT_MESSAGE,
    ZF_CLOSING_OUT_SUBJECT,
    ZF_DUPLICATE_COMMENT,
)
from collections import defaultdict
from itertools import combinations
from typing import Dict, List

import praw
import wikipedia
import yaml
from rapidfuzz import fuzz

"""
UNIVERSAL VARIABLES

These variables (all denoted by UPPERCASE names) are variables used by many functions in Ziwen. These are important
as they define many of the basic functions of the bot.
"""

BOT_NAME = "Zifang"
VERSION_NUMBER = "0.80"
USER_AGENT = (
    f"{BOT_NAME} {VERSION_NUMBER}, another assistant for r/translator. "
    "Written and maintained by u/kungming2."
)

CLOSE_OUT_AGE = 7  # Age of posts (in days) that we inform people about.
CLOSE_OUT_COMMENTS_MINIMUM = 5
DUPLICATES_AGE = 4  # Age of posts (in hours) that we check for duplicates.
DUPLICATE_CONFIDENCE = 85  # Similarity level of posts to mark as duplicates.
NUMERICAL_SIMILARITY = 20  # How close we want the numbers to be together.

ZF_DISCLAIMER = BOT_DISCLAIMER.replace("Ziwen", "Zifang")

# Connecting to the Reddit API via OAuth.
logger.info(f"Startup: Logging in as u/{USERNAME}...")
reddit = praw.Reddit(
    client_id=ZIFANG_APP_ID,
    client_secret=ZIFANG_APP_SECRET,
    password=PASSWORD,
    user_agent=USER_AGENT,
    username=USERNAME,
)
r = reddit.subreddit(SUBREDDIT)
logger.info(
    f"Startup: Initializing {BOT_NAME} {VERSION_NUMBER} for r/{SUBREDDIT} with languages module {VERSION_NUMBER_LANGUAGES}."
)


# TODO merge this with the similar function in Ziwen
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

            try:
                log_template_txt = f"\n-----------------------------------\n{error_date} ({BOT_NAME} {VERSION_NUMBER})\n{error_save_entry}"
                f.write(log_template_txt)
            except UnicodeEncodeError:
                # Occasionally this may fail on Windows thanks to its crap Unicode support.
                logger.error("Error_Log: Encountered a Unicode writing error.")


def is_mod(username: str) -> bool:
    """Checks if the user is a moderator of the subreddit."""
    mod_list = [x.name.lower() for x in r.moderator()]

    return username in mod_list


"""CLOSEOUT ROUTINE"""


def wiki_access(post_ids: None | List[str], retrieve: bool = False) -> None | List[str]:
    """
    This function either adds an ID of a post or just gets what's stored
    on the wikipage back.
    """
    wiki_page = reddit.subreddit("translatorBOT").wiki["zifang_config"]
    processed_data = wiki_page.content_md
    # Convert YAML text into a Python list.
    previous_ids: List[str] = yaml.safe_load(processed_data)

    # In rare cases where the configuration page has no data.
    if previous_ids is None:
        previous_ids = []

    if retrieve:
        return previous_ids

    # Otherwise, merge the two lists.
    merged = previous_ids + post_ids
    diff_ids = list(set(previous_ids) - set(post_ids))
    merged = list(set(merged))[:1500]
    merged.sort()  # Sort with oldest IDs first.

    # Edit the wikipage if there's changed data.
    if merged != previous_ids:
        wiki_page.edit(
            content=str(merged), reason=f"Updating with new IDs ({diff_ids[0:2]}...)."
        )
        logger.info("[ZF]: Updated Zifang configuration page with new IDs.")
    else:
        logger.debug("[ZF]: No new IDs.")


def closeout(list_posts: List[praw.reddit.models.Submission]) -> None:
    """
    The function assesses older posts to see if their creator should be
    reminded to close out their post. It operates off of two criteria:

    1. It has a minimum of X comments from other people.
    2. It has a minimum of X comments from the author.

    :param list_posts: A list of Reddit PRAW submissions.
    :return:
    """
    current_time = int(time.time())
    actionable_posts = []
    previous_posts = wiki_access(None, retrieve=True)

    # Compile a list of posts that we can take action on.
    for post in list_posts:
        try:
            post.author.name
        except AttributeError:  # No use mailing to non-existent people.
            continue

        # Check the time difference in days. If it exceeds our limit,
        # skip.
        time_delta = (current_time - post.created_utc) / 86400
        if time_delta < CLOSE_OUT_AGE:
            continue

        # Exclude posts that would otherwise count as translated.
        post_flair = post.link_flair_text.lower()
        if any(
            keyword in post_flair
            for keyword in ["translated", "review", "meta", "community"]
        ):
            continue

        # Skip if we've already seen this post before.
        if post.id in previous_posts:
            continue

        if int(post.num_comments) >= CLOSE_OUT_COMMENTS_MINIMUM:
            actionable_posts.append(post)

    logger.info(
        f"[ZF]: > There are {len(actionable_posts)} posts to message "
        "their author for."
    )

    # Send the person a message regarding their post.
    for post in actionable_posts:
        language = re.sub(r"\([^)]*\)", "", post.link_flair_text)
        if "[" in language:  # Generally for defined multiple tags.
            language = language.split("[")[0].strip()
        time_delta = round(time_delta, 1)
        subject_line = ZF_CLOSING_OUT_SUBJECT.format(language=language)
        closeout_message = ZF_CLOSING_OUT_MESSAGE.format(
            author=post.author.name,
            days=time_delta,
            language=language,
            permalink=post.permalink,
            num_comments=post.num_comments,
        )
        closeout_message += ZF_DISCLAIMER

        try:
            post.author.message(subject_line, closeout_message)
        except praw.exceptions.APIException:
            pass
        else:
            logger.info(
                f"[ZF]: >> Messaged u/{post.author} about closing out their post at {post.permalink}."
            )

    # Save to the wikipage.
    actionable_posts_ids = [x.id for x in actionable_posts]
    if actionable_posts:
        wiki_access(actionable_posts_ids)
        logger.debug("[ZF]: > Saved post IDs to the wikipage.")


"""DUPLICATE DETECTOR"""


def fetch_removal_reasons(subreddit: str) -> Dict[int, tuple] | None:
    """
    Fetches the removal reasons present on a subreddit.
    :param subreddit: Name of the subreddit.
    :return: `None` if there's nothing, a list otherwise.
    """

    reasons = [
        (removal_reason.title, removal_reason.id, removal_reason.message)
        for removal_reason in reddit.subreddit(subreddit).mod.removal_reasons
    ]

    if reasons:
        return {index + 1: value for index, value in enumerate(reasons)}


def search_removal_reasons(reasons_dict: Dict[int, tuple] | None, prompt: str) -> str:
    """Takes a removal reasons dictionary generated by
    `fetch_removal_reasons()` and allows for us to only grab it once
    from the site. Then, you can run a search amongst the reasons for
    it and get the specific removal reason ID."""
    if not reasons_dict:
        return ""

    for entry, entry_id, _description in reasons_dict.values():
        if prompt.lower().strip() in entry.lower():
            return entry_id


def calculate_similarity(strings: List[str]) -> float:
    """Assesses several strings and returns a probability (out of 100)
    on how similar they are."""
    similarity_scores = []

    # Iterate over each pair of strings
    similarity_scores = [
        fuzz.token_sort_ratio(strings[i], strings[j])
        for i, j in combinations(range(len(strings)), 2)
    ]

    # Average out.
    return sum(similarity_scores) / len(similarity_scores)


def numerical_sequence(strings: List[str]) -> bool:
    """
    Assesses titles to see if they are likely related but differ purely
    based on numbers.
    :param strings: Titles to look at.
    :return:
    """
    numbers = []
    pattern = r"\s(\d+)"  # Regular expression pattern to match one or more digits preceded by a space

    for string in strings:
        matches = re.findall(pattern, string)
        matches = [int(x) for x in matches]
        if matches:
            numbers.append(matches)

    # Exit early if no numbers were detected.
    if not numbers:
        logger.info(">>> [ZF]: No numbers found in these titles. Skipping...")
        return False

    # Go through the differences.
    logger.info(f">>> [ZF]: Numbers found in the titles were: {numbers}")
    total_sums = [sum(x) for x in numbers]
    differences = [b - a for a, b in zip(total_sums, total_sums[1:])]
    average_difference = sum(differences) / len(differences)

    logger.info(f">>> [ZF]: The numerical sequence difference is {average_difference}.")

    # If the average difference in numbers between the titles is lower
    # than our threshold, return `False`, telling the other function
    # NOT to remove it.
    return average_difference == 0 or average_difference >= NUMERICAL_SIMILARITY


def duplicate_detector(
    list_posts: List[praw.reddit.models.Submission],
) -> List[str] | None:
    """
    Function that takes a list of posts, and assesses it for any
    possible duplicates.

    :param list_posts: A list of Reddit PRAW submissions.
    :return: A list of Reddit IDs to remove, or `None`.
    """
    author_list = defaultdict(int)
    titles = defaultdict(list)
    actionable_posts = []
    current_time = int(time.time())

    # Compile sets of posts by the same author.
    for post in list_posts:
        try:
            post_author = post.author.name.lower()
        except AttributeError:
            continue

        # Check the time difference in hours. If it exceeds our limit,
        # skip.
        time_delta = (current_time - post.created_utc) / 3600
        if time_delta > DUPLICATES_AGE:
            continue

        # Check if the post is already approved.
        if post.approved:
            logger.info(
                f"> The post `{post.id}` has already been " "approved by a moderator."
            )
            continue

        # Exempt moderators.
        if is_mod(post_author):
            logger.info(f"> The post `{post.id}` was posted by a moderator.")
            continue

        author_list[post_author] += 1
        titles[post_author].append((post.title.lower(), post.id))

    # Filter out key-value pairs with a value of 1, then
    # sort the dictionary by the largest values in descending order
    final_dict = dict(filter(lambda item: item[1] != 1, author_list.items()))
    final_dict = dict(sorted(final_dict.items(), key=lambda x: x[1], reverse=True))

    # Process the potential duplicates by the same author.
    # The dictionary is indexed by username, with a list of posts.
    for author in final_dict.keys():
        author_data = titles[author]
        author_titles = [t[0] for t in author_data]

        # Pass it to the numerical sequence similarity calculator first.
        # False means don't remove it, True means the normal processing
        # rules can apply.
        numerical_similiarity = numerical_sequence(author_titles)
        if not numerical_similiarity:
            logger.info(
                f">> Posts  by u/{author} pass the "
                "numerical similarity calculator. Skipped."
            )
            continue

        # Calculate how similar these posts are.
        similarity_index = round(calculate_similarity(author_titles), 2)
        logger.info(
            f"> The posts by u/{author} have a similarity index of {similarity_index}."
        )
        if similarity_index >= DUPLICATE_CONFIDENCE:
            author_post_ids = [t[1] for t in author_data]
            author_post_ids.sort()  # Oldest post will be first.

            actionable_posts += author_post_ids[1:]
            logger.info(f">> Added posts `{author_post_ids[1:]} for removal.")

    if actionable_posts:
        return actionable_posts


"""WIKIPEDIA DETECTOR (COMMENTS"""


def extract_text_within_curly_braces(text: str) -> List[str]:
    """Gets text from between curly braces."""
    pattern = r"\{{([^}}]+)\}"  # Regex pattern to match text within curly braces
    matches = re.findall(pattern, text)
    return matches


def wikipedia_lookup(terms: List[str], language: str = "English") -> str | None:
    """
    Basic function to look up terms on Wikipedia.
    :param terms: A list of strings to look up.
    :param language: Which Wikipedia language to look up in.
    :return: A properly formatted paragraph of entries if there are
             results, otherwise `None`.
    """
    entries = []

    # Code for searching non-English Wikipedia, currently not needed.
    if language != "English":
        lang_code = converter(language).language_code
        wikipedia.set_lang(lang_code)

    # Look up the terms and format them appropriately.
    for term in terms[:5]:  # Limit to five terms.
        term_entry = None
        term = re.sub(r"[^\w\s]", "", term)  # Strip punctuation.
        logger.info(f"[ZF]: > Now searching for '{term}'...")

        # By default, turn off auto suggest.
        try:
            term_summary = wikipedia.summary(
                term, auto_suggest=False, redirect=True, sentences=3
            )
        except (
            wikipedia.exceptions.DisambiguationError,
            wikipedia.exceptions.PageError,
        ):
            # No direct matches, try auto suggest.
            try:
                term_summary = wikipedia.summary(term.strip(), sentences=3)
                term_entry = wikipedia.page(term).url
            except (
                wikipedia.exceptions.DisambiguationError,
                wikipedia.exceptions.PageError,
            ):
                # Still no dice.
                logger.info(
                    f"[ZF]: >> Unable to resolve '{term}' on Wikipedia. Skipping."
                )
                continue  # Exit.

        # Clean up the text for the entry.
        term_format = term.replace(" ", "_")
        if "\n" in term_summary:
            term_summary = term_summary.split("\n")[0].strip()
        if "==" in term_summary:
            term_summary = term_summary.split("==")[0].strip()
        if not term_entry:
            term_entry = f"https://en.wikipedia.org/wiki/{term_format}"
        term_entry = term_entry.replace(")", r"\)")

        # Form the entry text.
        entries.append(f"\n**[{term}]({term_entry})**\n\n> {term_summary}\n\n")
        logger.info(f"[ZF]: >> Information for '{term}' retrieved.")

    if entries:
        body_text = "\n".join(entries)
        logger.info("[ZF]: > Wikpedia entry data obtained.")
        action_counter(len(entries), "Wikipedia lookup")
        return body_text


"""MAIN RUNTIME"""


def zifang_posts(removal_reasons: Dict[int, tuple] | None) -> None:
    """
    Currently, does two things:

    * Check for duplicate posts in a short period of time.
    * Check for posts that match the age at which point we want
      to notify people to close out their posts.

    :return: Nothing.
    """
    posts = []

    # Get the last posts that we can get. With the API limit of 1000,
    # that should be approximately more than a week's worth of posts.

    posts += list(r.new(limit=None))
    posts.reverse()  # Reverse it so that we start processing the older ones first. Newest ones last.

    # Check for duplicates.
    duplicate_data = duplicate_detector(posts)
    # If we do have duplicates, remove them and reply.
    if duplicate_data:
        for dupe_id in duplicate_data:
            dupe_post = reddit.submission(dupe_id)
            dupe_post.mod.remove(
                reason_id=search_removal_reasons(removal_reasons, "duplicate"),
                mod_note=f"Posted duplicate at {dupe_post.id}",
            )
            bot_reply = dupe_post.reply(
                ZF_DUPLICATE_COMMENT.format(
                    author=dupe_post.author.name, permalink=dupe_post.permalink
                )
                + ZF_DISCLAIMER
            )
            bot_reply.mod.distinguish()  # Distinguish the bot's comment.
        action_counter(len(duplicate_data), "Removed duplicate")
        wiki_access(duplicate_data)  # Add them to the wiki.

    # Check for close-out.
    closeout(posts)


def zifang_comments(comment_limit: int = 200) -> None:
    """
    :param comment_limit: How many past comments should the bot look.

    Currently acts as a Wikipedia lookup bot.
    :return: Nothing
    """
    acted_comments = []
    previous_ids = wiki_access(None, retrieve=True)

    comments = list(r.comments(limit=comment_limit))
    comments.reverse()  # Reverse it so that we start processing the older ones first. Newest ones last.

    # Look for search terms.
    for comment in comments:
        try:
            comment_author = comment.author.name
        except AttributeError:
            continue  # Comment author is deleted.

        # Do not act on my own comments.
        if comment_author == USERNAME:
            continue

        if comment.id in previous_ids:
            logger.debug(f"[ZF]: > Comment `{comment.id}` has already been processed.")
            continue

        # Continue if there are no matches.
        matches = extract_text_within_curly_braces(comment.body)
        if not matches:
            continue

        # Retrieve Wikipedia lookup information.
        wp_info = wikipedia_lookup(matches)
        if wp_info:
            try:
                op = comment.submission.author.name
                post_id = comment.submission.id
            except AttributeError:
                continue  # No author to notify.

            author_tag = (
                f"*u/{op} (OP), the following Wikipedia pages "
                "may be of interest to your request.*\n\n"
            )
            comment.reply(author_tag + wp_info + ZF_DISCLAIMER)
            logger.info(
                ">> Replied with Wikipedia page information for "
                f"the OP u/{op} on post `{post_id}`."
            )
            acted_comments.append(comment.id)

    # Save the relevant comment IDs to the wikipage.
    wiki_access(acted_comments)


# */10 * * * *
if __name__ == "__main__":
    try:
        zifang_posts(fetch_removal_reasons(SUBREDDIT))
        zifang_comments()
    except Exception as e:  # The bot encountered an error/exception.
        logger.error(f"Main: Encounted error {e}.")
        # Format the error text.
        error_entry = traceback.format_exc()
        record_error_log(error_entry)  # Save the error to a log.
        logger.error("Main: > Logged this error. Ended run.")
    except KeyboardInterrupt:  # Manual termination of the script with Ctrl-C.
        logger.info("Manual user shutdown.")
        sys.exit()
