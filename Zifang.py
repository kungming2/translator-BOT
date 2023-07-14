#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""
Zifang is a new addition to help Ziwen with some ancillary tasks.
"""
import sys
import time
import traceback

import praw
import wikipedia
import yaml

from _languages import *
from _config import *
from _responses import *

'''
UNIVERSAL VARIABLES

These variables (all denoted by UPPERCASE names) are variables used by many functions in Ziwen. These are important
as they define many of the basic functions of the bot.
'''

BOT_NAME = 'Zifang'
VERSION_NUMBER = '0.80'
USER_AGENT = ('{} {}, another assistant for r/translator. '
              'Written and maintained by u/kungming2.'.format(BOT_NAME, VERSION_NUMBER))
SUBREDDIT = "translator"

CLOSE_OUT_AGE = 7  # Age of posts (in days) that we inform people about.
CLOSE_OUT_COMMENTS_MINIMUM = 5
DUPLICATES_AGE = 4  # Age of posts (in hours) that we check for duplicates.
DUPLICATE_CONFIDENCE = 85  # Similarity level of posts to mark as duplicates.
NUMERICAL_SIMILARITY = 20  # How close we want the numbers to be together.

'''KEYWORDS LISTS'''
KEYWORDS = []  # for future use with !bot
ZF_DISCLAIMER = BOT_DISCLAIMER.replace('Ziwen', 'Zifang')

# Connecting to the Reddit API via OAuth.
logger.info('[ZF] Startup: Logging in as u/{}...'.format(USERNAME))
reddit = praw.Reddit(client_id=ZIFANG_APP_ID, client_secret=ZIFANG_APP_SECRET, password=PASSWORD,
                     user_agent=USER_AGENT, username=USERNAME)
r = reddit.subreddit(SUBREDDIT)
logger.info('[ZF] Startup: Initializing {} {} for r/{} with languages module {}.'.format(BOT_NAME,
                                                                                         VERSION_NUMBER,
                                                                                         SUBREDDIT,
                                                                                         VERSION_NUMBER_LANGUAGES))


def record_error_log(error_save_entry):
    """
    A function to SAVE errors to a log for later examination.
    This is more advanced than the basic version kept in _config, as it includes data about last post/comment.

    :param error_save_entry: The traceback text that we want saved to the log.
    :return: Nothing.
    """

    f = open(FILE_ADDRESS_ERROR, 'a+', encoding='utf-8')  # File address for the error log, cumulative.
    existing_log = f.read()  # Get the data that already exists

    # If this error entry doesn't exist yet, let's save it.
    if error_save_entry not in existing_log:
        error_date = strftime("%Y-%m-%d [%I:%M:%S %p]")

        try:
            log_template = "\n-----------------------------------\n{} ({} {})\n{}\n{}"
            log_template_txt = log_template.format(error_date, BOT_NAME, VERSION_NUMBER,
                                                   error_save_entry)
            f.write(log_template_txt)
        except UnicodeEncodeError:  # Occasionally this may fail on Windows thanks to its crap Unicode support.
            logger.error("[ZF] Error_Log: Encountered a Unicode writing error.")
        f.close()

    return


def is_mod(username):
    """Checks if the user is a moderator of the subreddit."""
    mod_list = r.moderator()
    mod_list = [x.name.lower() for x in mod_list]
    print(mod_list)

    if username in mod_list:
        return True
    else:
        return False


'''CLOSEOUT ROUTINE'''


def wiki_access(post_ids, retrieve=False):
    """
    This function either adds an ID of a post or just gets what's stored
    on the wikipage back.
    """
    wiki_page = reddit.subreddit('translatorBOT').wiki['zifang_config']
    processed_data = wiki_page.content_md
    previous_ids = yaml.safe_load(processed_data)  # Convert YAML text into a Python list.

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
        wiki_page.edit(content=str(merged),
                       reason=f'Updating with new IDs ({diff_ids[0:2]}...).')
        logger.info(f"[ZF]: Updated Zifang configuration page with new IDs.")
    else:
        logger.debug(f"[ZF]: No new IDs.")

    return


def closeout(list_posts):
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
            post.author.name.lower()
        except AttributeError:  # No use mailing to non-existent people.
            continue

        # Check the time difference in days. If it exceeds our limit,
        # skip.
        time_delta = (current_time - post.created_utc) / 86400
        if time_delta < CLOSE_OUT_AGE:
            continue

        # Exclude posts that would otherwise count as translated.
        post_flair = post.link_flair_text.lower()
        if any(keyword in post_flair for keyword in ["translated", "review", "meta", "community"]):
            continue

        # Skip if we've already seen this post before.
        if post.id in previous_posts:
            continue

        if int(post.num_comments) >= CLOSE_OUT_COMMENTS_MINIMUM:
            actionable_posts.append(post)

    logger.info(f"[ZF]: > There are {len(actionable_posts)} posts to message "
                f"their author for.")

    # Send the person a message regarding their post.
    for post in actionable_posts:
        language = re.sub(r'\([^)]*\)', '', post.link_flair_text)
        if "[" in language:  # Generally for defined multiple tags.
            language = language.split('[')[0].strip()
        time_delta = round((current_time - post.created_utc) / 86400, 1)
        subject_line = ZF_CLOSING_OUT_SUBJECT.format(language=language)
        closeout_message = ZF_CLOSING_OUT_MESSAGE.format(author=post.author.name,
                                                         days=time_delta,
                                                         language=language,
                                                         permalink=post.permalink,
                                                         num_comments=post.num_comments)
        closeout_message += ZF_DISCLAIMER

        try:
            post.author.message(subject_line, closeout_message)
        except praw.exceptions.APIException:
            pass
        else:
            logger.info(f"[ZF]: >> Messaged u/{post.author} about closing out their post at {post.permalink}.")

    # Save to the wikipage.
    actionable_posts_ids = [x.id for x in actionable_posts]
    if actionable_posts:
        wiki_access(actionable_posts_ids)
        logger.debug(f"[ZF]: > Saved post IDs to the wikipage.")

    return


'''DUPLICATE DETECTOR'''


def fetch_removal_reasons(subreddit):
    """
    Fetches the removal reasons present on a subreddit.
    :param subreddit: Name of the subreddit.
    :return: `None` if there's nothing, a list otherwise.
    """
    reasons = {}
    i = 1

    for removal_reason in reddit.subreddit(subreddit).mod.removal_reasons:
        reasons[i] = (removal_reason.title, removal_reason.id,
                      removal_reason.message)
        i += 1

    if reasons:
        return reasons
    else:
        return


def search_removal_reasons(reasons_dict, prompt):
    """Takes a removal reasons dictionary generated by
    `fetch_removal_reasons()` and allows for us to only grab it once
    from the site. Then, you can run a search amongst the reasons for
    it and get the specific removal reason ID."""
    reason_id = None

    for key, (entry, entry_id, description) in reasons_dict.items():
        if prompt.lower().strip() in entry.lower():
            reason_id = entry_id
            break

    if reason_id is not None:
        return reason_id
    else:
        return None


def calculate_similarity(strings):
    """Assesses several strings and returns a probability (out of 100)
    on how similar they are."""
    similarity_scores = []

    # Iterate over each pair of strings
    for i in range(len(strings)):
        for j in range(i+1, len(strings)):
            similarity_score = fuzz.token_sort_ratio(strings[i], strings[j])
            similarity_scores.append(similarity_score)

    # Average out.
    similarity_score = sum(similarity_scores) / len(similarity_scores)

    return similarity_score


def numerical_sequence(strings):
    """
    Assesses titles to see if they are likely related but differ purely
    based on numbers.
    :param strings: Titles to look at.
    :return:
    """
    numbers = []
    pattern = r'\s(\d+)'  # Regular expression pattern to match one or more digits preceded by a space

    for string in strings:
        matches = re.findall(pattern, string)
        matches = [int(x) for x in matches]
        if matches:
            numbers.append(matches)

    # Exit early if no numbers were detected.
    if not numbers:
        logger.info(f">>> [ZF]: No numbers found in these titles. Skipping...")
        return False

    # Go through the differences.
    logger.info(f">>> [ZF]: Numbers found in the titles were: {numbers}")
    total_sums = [sum(x) for x in numbers]
    differences = [total_sums[i + 1] - total_sums[i] for i in range(len(total_sums) - 1)]
    average_difference = sum(differences) / len(differences)

    logger.info(f">>> [ZF]: The numerical sequence difference is {average_difference}.")

    # If the average difference in numbers between the titles is lower
    # than our threshold, return `False`, telling the other function
    # NOT to remove it.
    if average_difference == 0:
        return True
    elif average_difference < NUMERICAL_SIMILARITY:
        return False
    else:
        return True


def duplicate_detector(list_posts):
    """
    Function that takes a list of posts, and assesses it for any
    possible duplicates.

    :param list_posts: A list of Reddit PRAW submissions.
    :return: A list of Reddit IDs to remove, or `None`.
    """
    author_list = {}
    titles = {}
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
            logger.info(f"[ZF] > The post `{post.id}` has already been "
                        "approved by a moderator.")
            continue

        # Exempt moderators.
        if is_mod(post_author):
            logger.info(f"[ZF] > The post `{post.id}` was posted by "
                        "a moderator.")
            continue

        if post_author in author_list:
            author_list[post_author] += 1
            titles[post_author].append((post.title.lower(), post.id))
        else:
            author_list[post_author] = 1
            titles[post_author] = [(post.title.lower(), post.id)]

    # Filter out key-value pairs with a value of 1, then
    # sort the dictionary by the largest values in descending order
    final_dict = {key: value for key, value in author_list.items() if value != 1}
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
            logger.info(f"[ZF] >> Posts  by u/{author} pass the "
                        "numerical similarity calculator. Skipped.")
            continue

        # Calculate how similar these posts are.
        similarity_index = round(calculate_similarity(author_titles), 2)
        logger.info(f"[ZF] > The posts by u/{author} have a similarity index of {similarity_index}.")
        if similarity_index >= DUPLICATE_CONFIDENCE:
            author_post_ids = [t[1] for t in author_data]
            author_post_ids.sort()  # Oldest post will be first.

            actionable_posts += author_post_ids[1:]
            logger.info(f"[ZF] >> Added posts `{author_post_ids[1:]} for removal.")

    if actionable_posts:
        return actionable_posts

    return


'''WIKIPEDIA DETECTOR (COMMENTS'''


def extract_text_within_curly_braces(text):
    """Gets text from between curly braces."""
    pattern = r'\{{([^}}]+)\}'  # Regex pattern to match text within curly braces
    matches = re.findall(pattern, text)
    return matches


def wikipedia_lookup(terms, language="English"):
    """
    Basic function to look up terms on Wikipedia.
    :param terms: A list of strings to look up.
    :param language: Which Wikipedia language to look up in.
    :return: A properly formatted paragraph of entries if there are
             results, otherwise `None`.
    """
    entries = []
    entry_format = '\n**[{term}]({link})**\n\n> {summary}\n\n'

    # Code for searching non-English Wikipedia, currently not needed.
    if language is not "English":
        lang_code = converter(language)[0]
        wikipedia.set_lang(lang_code)

    # Look up the terms and format them appropriately.
    for term in terms[:5]:  # Limit to five terms.
        term_entry = None
        term = re.sub(r'[^\w\s]', '', term)  # Strip punctuation.
        logger.info(f"[ZF]: > Now searching for '{term}'...")

        # By default, turn off auto suggest.
        try:
            term_summary = wikipedia.summary(term, auto_suggest=False,
                                             redirect=True, sentences=3)
        except (wikipedia.exceptions.DisambiguationError, wikipedia.exceptions.PageError):
            # No direct matches, try auto suggest.
            try:
                term_summary = wikipedia.summary(term.strip(),
                                                 sentences=3)
                term_entry = wikipedia.page(term).url
            except (wikipedia.exceptions.DisambiguationError, wikipedia.exceptions.PageError):
                # Still no dice.
                logger.info(f"[ZF]: >> Unable to resolve '{term}' on Wikipedia. Skipping.")
                continue  # Exit.

        # Clean up the text for the entry.
        term_format = term.replace(' ', '_')
        if '\n' in term_summary:
            term_summary = term_summary.split('\n')[0].strip()
        if '==' in term_summary:
            term_summary = term_summary.split('==')[0].strip()
        if not term_entry:
            term_entry = f'https://en.wikipedia.org/wiki/{term_format}'
        term_entry = term_entry.replace(')', '\)')

        # Form the entry text.
        entry = entry_format.format(term=term,
                                    link=term_entry,
                                    summary=term_summary)
        entries.append(entry)
        logger.info(f"[ZF]: >> Information for '{term}' retrieved.")

    if entries:
        body_text = '\n'.join(entries)
        logger.info(f"[ZF]: > Wikpedia entry data obtained.")
        action_counter(len(entries), "Wikipedia lookup")
        return body_text
    else:
        return


'''MAIN RUNTIME'''


def zifang_posts():
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
            dupe_post.mod.remove(reason_id=search_removal_reasons(REMOVAL_REASONS, 'duplicate'),
                                 mod_note=f"Posted duplicate at {dupe_post.id}")
            bot_reply = dupe_post.reply(ZF_DUPLICATE_COMMENT.format(author=dupe_post.author.name,
                                                                    permalink=dupe_post.permalink) + ZF_DISCLAIMER)
            bot_reply.mod.distinguish()  # Distinguish the bot's comment.
        action_counter(len(duplicate_data), "Removed duplicate")
        wiki_access(duplicate_data)  # Add them to the wiki.

    # Check for close-out.
    closeout(posts)

    return


def zifang_comments(comment_limit=200):
    """
    :param comment_limit: How many past comments should the bot look.

    Currently acts as a Wikipedia lookup bot.
    :return: Nothing
    """
    comments = []
    acted_comments = []
    previous_ids = wiki_access(None, retrieve=True)

    comments += list(r.comments(limit=comment_limit))
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

            author_tag = (f"*u/{op} (OP), the following Wikipedia pages "
                          "may be of interest to your request.*\n\n")
            comment.reply(author_tag + wp_info + ZF_DISCLAIMER)
            logger.info(f"[ZF] >> Replied with Wikipedia page information for "
                        f"the OP u/{op} on post `{post_id}`.")
            acted_comments.append(comment.id)

    # Save the relevant comment IDs to the wikipage.
    wiki_access(acted_comments)

    return


# */10 * * * *
if __name__ == "__main__":
    try:
        REMOVAL_REASONS = fetch_removal_reasons(SUBREDDIT)
        zifang_posts()
        zifang_comments()
    except Exception as e:  # The bot encountered an error/exception.
        logger.error(f"[ZF] Main: Encounted error {e}.")
        # Format the error text.
        error_entry = traceback.format_exc()
        record_error_log(error_entry)  # Save the error to a log.
        logger.error("[ZF] Main: > Logged this error. Ended run.")
    except KeyboardInterrupt:  # Manual termination of the script with Ctrl-C.
        logger.info('Manual user shutdown.')
        sys.exit()
