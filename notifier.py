#!/usr/bin/env python3

"""
NOTIFICATIONS SYSTEM

Paging functions, which are a subset of the notifications system, has the prefix `notifier_page`.
"""

import random
import time
import praw  # Simple interface to the Reddit API that also handles rate limiting of requests.
import prawcore
from _responses import (
    MSG_NSFW_WARNING,
    MSG_PAGE,
    MSG_REMOVAL_LINK,
    MSG_LANGUAGE_FREQUENCY,
)
from _config import logger, BOT_DISCLAIMER
from _language_consts import ISO_LANGUAGE_COUNTRY_ASSOCIATED
from _languages import converter, comment_info_parser
from datetime import datetime


def messaging_is_valid_user(username, reddit):
    """
    Simple function that tests if a Redditor is a valid user. Used to keep the notifications database clean.
    Note that `AttributeError` is returned if a user is *suspended* by Reddit.

    :param username: The username of a Reddit user.
    :return exists: A boolean. False if non-existent or shadowbanned, True if a regular user.
    """

    try:
        reddit.redditor(username).fullname
    except (
        prawcore.exceptions.NotFound,
        AttributeError,
    ):  # AttributeError is thrown if suspended user.
        return False

    return True


def messaging_months_elapsed():
    """
    Simple function that tells us how many months of statistics we have, since May 2016, when the redesign started.
    This is used for assessing the average number of posts are for a given language and can be expected for
    notifications.

    :return months_num: The number of months since May 2017, as an integer.
    """

    month_beginning = 24198  # This is the May 2016 month, when the redesign was implemented. No archive data before.
    current_toki = time.time()

    month_int = int(datetime.fromtimestamp(current_toki).strftime("%m"))  # EG 05
    year_int = int(datetime.fromtimestamp(current_toki).strftime("%Y"))  # EG 2017

    total_current_months = (year_int * 12) + month_int
    months_num = total_current_months - month_beginning

    return months_num


def messaging_language_frequency(language_name, reddit, subreddit):
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

    overall_page = reddit.subreddit(subreddit).wiki[
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


def notifier_list_pruner(username, reddit, cursor_main, conn_main):
    """
    Function that removes deleted users from the notifications database.
    It performs a test, and if they don't exist, it will delete their entries from the SQLite database.

    :param username: The username of a Reddit user.
    :return: None if the user does not exist, a string containing their last subscribed languages otherwise.
    """

    if messaging_is_valid_user(username, reddit):  # This user does exist
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


def notifier_regional_language_fetcher(targeted_language, cursor_main):
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


def notifier_duplicate_checker(language_code, username, cursor_main):
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
    return len(specific_entries) > 0  # There already is an entry.


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
    return not (language_name in majo_history and language_name != majo_history[-1])


def notifier_over_frequency_checker(username, most_recent_op):
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
    frequency = most_recent_op.count(username)

    # return if they have exceeded the limit.
    return frequency > limit


def notifier_limit_writer(
    username, language_code, cursor_main, conn_main, num_notifications=1
):
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


def notifier_equalizer(
    notify_users_list, language_name, monthly_limit, reddit, subreddit
):
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

    users_number = len(notify_users_list) if notify_users_list is not None else None

    if (
        users_number is None
    ):  # If there's no one signed up for, just return an empty list
        return []

    # Get the number of requests on average per month for a language
    try:
        if language_name == "Unknown":  # Hardcode Unknown frequency
            monthly_number_notifications = 260
        else:
            frequency_data = messaging_language_frequency(
                language_name, reddit, subreddit
            )
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
                f"[Page] Message from r/translator regarding a {language_name} post"
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
                    target_username, reddit, cursor_main, conn_main
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


def notifier_language_list_editer(
    language_list, username, cursor_main, conn_main, mode="insert"
):
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
            elif code == "en":  # Skip inserting English.
                continue

            # Check to see if user is already in our database.
            is_there = notifier_duplicate_checker(code, username, cursor_main)

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
