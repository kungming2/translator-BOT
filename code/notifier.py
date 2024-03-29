#!/usr/bin/env python3

"""
NOTIFICATIONS SYSTEM

Paging functions, which are a subset of the notifications system, has the prefix `notifier_page`.
These functions all relate to Ziwen's notifications - that is, the database of individuals who are on Ziwen's list for 
languages. 

The two main functions are: `ziwen_notifier`, the actual function that sends messages to people.
                            `ziwen_messages`, the function that proccesses incoming messages to the bot.
"""

import csv
import json
import random
import re
import time
from code._config import (
    BOT_DISCLAIMER,
    FILE_ADDRESS_ACTIVITY,
    FILE_ADDRESS_ALL_STATISTICS,
    FILE_ADDRESS_ERROR,
    KEYWORDS,
    NOTIFICATIONS_LIMIT,
    action_counter,
    logger,
    time_convert_to_string,
)
from code._language_consts import ISO_LANGUAGE_COUNTRY_ASSOCIATED, MAIN_LANGUAGES
from code._languages import comment_info_parser, convert, language_list_splitter
from code._responses import (
    MSG_CANNOT_PROCESS,
    MSG_LANGUAGE_FREQUENCY,
    MSG_NO_POINTS,
    MSG_NO_SUBSCRIPTIONS,
    MSG_NOTIFY,
    MSG_NOTIFY_IDENTIFY,
    MSG_NSFW_WARNING,
    MSG_PAGE,
    MSG_REMOVAL_LINK,
    MSG_SUBSCRIBE,
    MSG_SUBSCRIBE_LINK,
    MSG_UNSUBSCRIBE_ALL,
    MSG_UNSUBSCRIBE_BUTTON,
)
from code.Ajo import ajo_loader
from code.Ziwen_helper import CORRECTED_SUBREDDIT, ZiwenConfig
from datetime import datetime
from sqlite3 import Cursor
from typing import Any, Dict, List, Tuple

import praw  # Simple interface to the Reddit API that also handles rate limiting of requests.
import prawcore


def messaging_is_valid_user(username: str, reddit: praw.Reddit) -> bool:
    """
    Simple function that tests if a Redditor is a valid user. Used to keep the notifications database clean.
    Note that `AttributeError` is returned if a user is *suspended* by Reddit.

    :param username: The username of a Reddit user.
    :return exists: A boolean. False if non-existent or shadowbanned, True if a regular user.
    """

    try:
        reddit.redditor(username).fullname
    except (prawcore.exceptions.NotFound, AttributeError):
        # AttributeError is thrown if suspended user.
        return False

    return True


def notifier_list_pruner(username: str, config: ZiwenConfig) -> None | str:
    """
    Function that removes deleted users from the notifications database.
    It performs a test, and if they don't exist, it will delete their entries from the SQLite database.

    :param username: The username of a Reddit user.
    :return: None if the user does not exist, a string containing their last subscribed languages otherwise.
    """

    if messaging_is_valid_user(username, config.reddit):  # This user does exist
        return None
    # User does not exist.

    # Fetch a list of what this user WAS subscribed to. (For the final error message)
    # We try to retrieve the languages the user is subscribed to.
    config.cursor_main.execute(
        "SELECT language_code FROM notify_users WHERE username = ?", (username,)
    )
    all_subscriptions = config.cursor_main.fetchall()

    # Remove the user from the database.
    config.cursor_main.execute(
        "DELETE FROM notify_users WHERE username = ?", (username,)
    )
    config.conn_main.commit()
    logger.info(
        f"notifier_list_pruner: Deleted subscription information for u/{username}."
    )

    # We only want the language codes (don't need the username).
    final_codes = [subscription["language_code"] for subscription in all_subscriptions]
    # Gather a list of the languages user WAS subscribed to
    return ", ".join(final_codes)  # Return the list of formerly subscribed languages


def notifier_duplicate_checker(
    language_code: str, username: str, cursor_main: Cursor
) -> bool:
    """
    Function that checks to see if there is a duplicate entry in the notifications database. That is, there is a user
    who is signed up for this specific language code.

    :param language_code: The language code the user may be signed up for.
    :param username: The username of a Reddit user.
    :return: True if entry pair is in there (the user is signed up for this language), False if not.
    """

    cursor_main.execute(
        "SELECT COUNT(*) AS user_count FROM notify_users WHERE language_code = ? and username = ?",
        (language_code, username),
    )
    specific_entries = cursor_main.fetchone()
    return specific_entries["user_count"] > 0  # There already is an entry.


def notifier_language_list_editor(
    language_list: List[str],
    username: str,
    config: ZiwenConfig,
    mode: str = "insert",
) -> None:
    """
    Function that will change the notifications database. It can insert or delete entries for a particular username.

    :param language_list: A list of language codes to insert.
    :param username: The Reddit username of the person whose entries we're changing or updating.
    :param mode: `insert` adds languages for the username, `delete` obviously removes them. `purge` removes all.
    :return: Nothing.
    """

    # If there's nothing in the list, exit.
    if mode == "purge":  # We want to delete everything for this user.
        config.cursor_main.execute(
            "DELETE FROM notify_users WHERE username = ?", (username,)
        )
        config.conn_main.commit()
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
            is_there = notifier_duplicate_checker(code, username, config.cursor_main)

            sql_package = (code, username)
            if not is_there and mode == "insert":  # No entry, and we want to insert.
                config.cursor_main.execute(
                    "INSERT INTO notify_users VALUES (? , ?)", sql_package
                )
                config.conn_main.commit()
            elif is_there and mode == "delete":
                # There is an entry, and we want to delete.
                config.cursor_main.execute(
                    "DELETE FROM notify_users WHERE language_code = ? and username = ?",
                    sql_package,
                )
                config.conn_main.commit()


def load_statistics_data(language_code: str) -> Dict[str, Any]:
    """
    Function that loads the language statistics dictionary from our saved JSON file.

    :param language_code: Any language code.
    :return: The language dictionary if it exists. None otherwise.
    """

    # Open the file
    with open(FILE_ADDRESS_ALL_STATISTICS, encoding="utf-8") as f:
        stats_data = json.load(f)
        return stats_data.get(language_code)


def messaging_language_frequency_table(language_list: List[str]) -> str:
    """
    This is a function that supercedes `messaging_language_frequency` and can generate a table given a list of language
    codes about the relative frequency for language notifications.
    """

    formatted_lines = []
    header = "| Language Name | Average Number of Posts | Per |\n|-----------|-----:|:----|\n"

    # Iterate over the language codes.
    for code in language_list:
        language_name = convert(code).language_name

        # Retrieve stored data.
        language_data = load_statistics_data(code)
        if language_data is not None:
            # There is historical statistics for this language.
            daily_rate = language_data["rate_daily"]
            monthly_rate = language_data["rate_monthly"]
            yearly_rate = language_data["rate_yearly"]
            link = language_data["permalink"]

            # Here we try to determine which comment we should return as a line.
            if daily_rate >= 2:
                # This is a pretty popular one, with a few requests a day.
                frequency = "day"
                rate = daily_rate
            elif 2 > daily_rate > 0.05:
                # This is a frequent one, a few requests a month. But not the most.
                frequency = "month"
                rate = monthly_rate
            else:  # These are pretty infrequent languages. Maybe a few times a year at most.
                frequency = "year"
                rate = yearly_rate

            # Combine the lines together as a message.
            new_line = f"| [{language_name}]({link}) | {rate} posts / | {frequency} |"
        else:  # We have not received data for this language.
            new_line = f"| {language_name} | No recorded statistics | --- |"

        # Add the line to our list.
        formatted_lines.append(new_line)

    # Format everything.
    return header + "\n".join(formatted_lines)


def record_activity_csv(
    data_tuple: Tuple[str, str, str | int | None, str, float]
) -> None:
    """
    Function that writes tuples of data to a CSV. It can be used for
    various things, but the first part should be activity type, then
    the date and time. This is written to FILE_ADDRESS_ACTIVITY.
    :param data_tuple: Package of data we want to insert.
    :return:
    """
    with open(
        FILE_ADDRESS_ACTIVITY, mode="a", newline="", encoding="utf-8"
    ) as csv_file:
        data_writer = csv.writer(
            csv_file, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL
        )
        data_writer.writerow(data_tuple)


def fetch_users_to_notify(cursor_main: Cursor, language_code: str):
    cursor_main.execute(
        "SELECT username FROM notify_users WHERE language_code = ?", (language_code,)
    )
    return cursor_main.fetchall()


def notifier_page_translators(
    language_code: str,
    language_name: str,
    pauthor: str,
    otitle: str,
    opermalink: str,
    oauthor: str,
    is_nsfw: bool,
    config: ZiwenConfig,
) -> List[str] | None:
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
    page_targets = fetch_users_to_notify(config.cursor_main, language_code)

    page_users_list = [target["username"] for target in page_targets]

    page_users_list = list(set(page_users_list))  # Remove duplicates
    # Remove the caller if on there
    page_users_list = [x for x in page_users_list if x != pauthor]
    if len(page_users_list) > number_to_page:  # If there are more than the number...
        page_users_list = random.sample(page_users_list, number_to_page)

    if len(page_users_list) == 0:  # There is no one on the list for it.
        return None  # Exit, return None.
    for target_username in page_users_list:
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
            config.reddit.redditor(str(target_username)).message(
                subject=subject_line, message=message + BOT_DISCLAIMER
            )
            logger.info(
                f"Paging: Messaged u/{target_username} for a {language_name} post."
            )
        except (
            praw.exceptions.APIException
        ):  # There was an error... User probably does not exist anymore.
            logger.debug(
                f"Paging: Error occurred sending message to u/{target_username}. Removing..."
            )
            # Remove the username from our database.
            notifier_list_pruner(target_username, config)

    return page_users_list


def notifier_page_multiple_detector(pbody: str) -> List[str]:
    """
    Function that checks to see if there are multiple page commands in a comment.

    :param pbody: The text body of the comment we're checking.
    :return: None if there are no valid paging languages or if there's 0 or 1 !page results.
             Will return the paged languages if there's more than 1.
    """

    # Returns a number of pages detected in a single comment.
    num_count_pages = pbody.count(KEYWORDS.page)

    if num_count_pages < 1:
        return None
    # There are one or more page languages.
    new_matches = []

    page_chunks = pbody.split(KEYWORDS.page)[1:]
    page_chunks = [KEYWORDS.page + s for s in page_chunks]

    for chunk in page_chunks:
        try:
            new_match = comment_info_parser(chunk, KEYWORDS.page)[0]
            new_matches.append(new_match)
        except TypeError:
            continue

    initial_matches = []
    for match in new_matches:
        match_code = convert(match).language_code
        if len(match_code) != 0:  # This is a valid language code.
            initial_matches.append(match_code)

    # We need code in case we don't have valid data for one.
    return initial_matches or None


class ZiwenNotifier:
    def __init__(self, config: ZiwenConfig) -> None:
        self.config = config

    def __messaging_months_elapsed(self) -> int:
        """
        Simple function that tells us how many months of statistics we have, since May 2016, when the redesign started.
        This is used for assessing the average number of posts are for a given language and can be expected for
        notifications.

        :return months_num: The number of months since May 2017, as an integer.
        """

        month_beginning = 24198  # This is the May 2016 month, when the redesign was implemented. No archive data before.
        current_time = time.time()

        month_int = int(datetime.fromtimestamp(current_time).strftime("%m"))  # EG 05
        year_int = int(datetime.fromtimestamp(current_time).strftime("%Y"))  # EG 2017

        total_current_months = (year_int * 12) + month_int
        return total_current_months - month_beginning  # months num

    def __messaging_language_frequency(
        self, language_name: str
    ) -> Tuple[str, Tuple[float, float, float, int]] | None:
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

        # Fetch the wikipage.
        overall_page = self.config.reddit.subreddit(CORRECTED_SUBREDDIT).wiki[
            language_name.lower()
        ]
        try:
            overall_page_content = str(overall_page.content_md)
        except (
            prawcore.exceptions.NotFound,
            prawcore.exceptions.BadRequest,
            KeyError,
            praw.exceptions.RedditAPIException,
            prawcore.exceptions.Redirect,  # Tends to happen with "community" requests
        ):
            # There is no page for this language
            return None  # Exit with nothing.

        per_month_lines = overall_page_content.split("\n")  # Separate into lines.

        for line in per_month_lines[5:]:  # We omit the header of the page.
            # We only want the first part, with month|year|total
            work_line = line.split("(", 1)[0]
            # Strip the formatting.
            for character in "[] ":
                work_line = work_line.replace(character, "")
            per_month_lines_edit.append(work_line)

        # Only get the ones that have a year in them
        per_month_lines_edit = [x for x in per_month_lines_edit if "20" in x]

        for row in per_month_lines_edit:
            month_posts = int(row.split("|")[2])  # We take the number of posts here.
            total_posts.append(month_posts)  # add it to the list of post counts.

        # The number of months we have data for the language.
        months_with_data = len(per_month_lines_edit)
        # Get the number of months since we started statistic keeping
        months_since = self.__messaging_months_elapsed()

        if months_with_data == months_since:
            # We have data for every single month for the language.
            # We want to take only the last 6 months.
            months_calculate = 6  # Change the time frame to 6 months
            # Add only the data for the last 6 months.
            total_rate_posts = sum(total_posts[-1 * months_calculate :])
        else:
            total_rate_posts = sum(total_posts)
            months_calculate = months_since

        # The average number of posts per month
        monthly_rate = round((total_rate_posts / months_calculate), 2)
        # The average number of posts per day
        daily_rate = round((monthly_rate / 30), 2)
        # The average number of posts per year
        yearly_rate = round((monthly_rate * 12), 2)

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
        if daily_rate > 0.05:
            # This is a frequent one, a few requests a month. But not the most.
            freq_string = MSG_LANGUAGE_FREQUENCY.format(
                lang_wiki_name, str(monthly_rate), "month", lang_name_original
            )
            return freq_string, stats_package
        # These are pretty infrequent languages. Maybe a few times a year at most.
        freq_string = MSG_LANGUAGE_FREQUENCY.format(
            lang_wiki_name, str(yearly_rate), "year", lang_name_original
        )
        return freq_string, stats_package

    def __notifier_regional_language_fetcher(self, targeted_language: str) -> List[str]:
        """
        Takes a code like "ar-LB" or an ISO 639-3 code, fetches notifications users for their equivalents too.
        Returns a list of usernames that match both criteria. This will also remove people who are on the broader list.
        This should also be able to work with unknown-specific notifications.

        :param targeted_language: The language code for a regional language or an ISO 639-3 code.
        :return final_specific_determined: A list of users who have signed up for both a broader language (like Arabic)
                                        and the specific regional one (like ar-LB).
        """

        relevant_iso_code = None
        cursor_main = self.config.cursor_main

        if "-" in targeted_language:  # This is a ITR code. ar-LB
            relevant_iso_code = ISO_LANGUAGE_COUNTRY_ASSOCIATED.get(targeted_language)
        else:  # It's an ISO code.
            relevant_iso_code = targeted_language
            for lang_country, language_code in ISO_LANGUAGE_COUNTRY_ASSOCIATED.items():
                if language_code == relevant_iso_code:
                    targeted_language = lang_country

        notify_targets = fetch_users_to_notify(cursor_main, targeted_language)

        if relevant_iso_code is not None:
            # There is an equvalent code. Let's get the users from that too.
            notify_targets += fetch_users_to_notify(cursor_main, relevant_iso_code)

        # Get the usernames.
        final_specific_usernames = {target["username"] for target in notify_targets}

        # Now we need to find the overall list's user names for the broader langauge (e.g. ar)
        # Take only the language part (ar).
        broader_code = targeted_language.split("-")[0]
        all_notify_targets = fetch_users_to_notify(cursor_main, broader_code)

        # This creates a list of all the people signed up for the original.
        all_broader_usernames = {target["username"] for target in all_notify_targets}

        return list(final_specific_usernames - all_broader_usernames)

    def __notifier_limit_writer(
        self,
        username: str,
        language_code: str,
        num_notifications: int = 1,
    ) -> None:
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
        self.config.cursor_main.execute(
            "SELECT received FROM notify_monthly_limit WHERE username = ?", (username,)
        )
        user_data = self.config.cursor_main.fetchone()

        # Parse the user's data. Load it if it exists.
        if user_data is not None:  # There's a record.
            # Take the stored dictionary.
            monthly_limit_dictionary = user_data["received"]
            # Convert the string to a proper dictionary.
            monthly_limit_dictionary = eval(monthly_limit_dictionary)

        # Write the changes to the database.
        if language_code not in monthly_limit_dictionary and user_data is None:
            # Create a new record, user doesn't exist.
            # Define the key and its value.
            monthly_limit_dictionary[language_code] = num_notifications

            # Write to the database.
            to_store = (username, str(monthly_limit_dictionary))
            self.config.cursor_main.execute(
                "INSERT INTO notify_monthly_limit VALUES (?, ?)", to_store
            )
        else:  # Update an existing one.
            # Attempt to update the dictionary value.
            if language_code in monthly_limit_dictionary:
                monthly_limit_dictionary[language_code] += num_notifications
            else:
                monthly_limit_dictionary[language_code] = num_notifications

            # Write to the database.
            to_store = (str(monthly_limit_dictionary), username)
            self.config.cursor_main.execute(
                "UPDATE notify_monthly_limit SET received = ? WHERE username = ?",
                to_store,
            )

        # Commit changes.
        self.config.conn_main.commit()

    def __notifier_title_cleaner(self, otitle: str) -> str:
        """
        Simple function to replace problematic Markdown characters like `[` or `]` that can mess up links.
        These characters can interfere with the display of Markdown links in notifications.

        :param otitle: The title of a Reddit post.
        :return otitle: The cleaned-up version of the same title with the problematic characters escaped w/ backslashes.
        """

        # Characters to prefix a backslash to.
        specific_characters = "[]"

        for character in specific_characters:
            if character in otitle:
                otitle = otitle.replace(character, r"\{}".format(character))

        return otitle

    def __notifier_equalizer(
        self, notify_users_list: List[str], language_name: str
    ) -> List[str]:
        """
        Function that equalizes out notifications for popular languages so that people can get fewer.
        No more than the NOTIFICATIONS_LIMIT on average.
        users_to_contact = (users_number * NOTIFICATIONS_LIMIT) / monthly_number_notifications
        This is primarily intended for languages which get a lot of monthly requests.

        :param notify_users_list: The full list of users on the notification list for this language.
        :param language_name: The name of the language.
        :return: A list containing a list of users to message.
        """

        # If there are more users than this number, randomize and pick this number's amount of users.
        limit_number = 30

        users_number = len(notify_users_list) if notify_users_list is not None else None

        if users_number is None:
            # If there's no one signed up for, just return an empty list
            return []

        # Get the number of requests on average per month for a language
        try:
            if language_name == "Unknown":  # Hardcode Unknown frequency
                monthly_number_notifications = 260
            else:
                frequency_data = self.__messaging_language_frequency(language_name)
                if frequency_data:
                    monthly_number_notifications = frequency_data[1][1]
                else:  # No results for this.
                    monthly_number_notifications = 1
        except TypeError:
            # If there are no statistics for this language, just set it to low.
            monthly_number_notifications = 1

        # Get the number of users we're going to randomly pick for this language
        if monthly_number_notifications == 0:
            users_to_contact = limit_number
        else:
            users_to_contact = round(
                ((users_number * NOTIFICATIONS_LIMIT) / monthly_number_notifications), 0
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
                f"Notifier Equalizer: {limit_number}+ people for {language_name} notifications. Randomized."
            )

        # Alphabetize
        return sorted(notify_users_list, key=str.lower)

    def ziwen_notifier(
        self,
        suggested_css_text: str,
        otitle: str,
        opermalink: str,
        oauthor: str,
        is_identify: bool,
    ) -> List[str]:
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
        post_type = "translation request"

        # We don't want to send testing messages.
        if "trntest" in opermalink:
            return []

        # Load the language_history from the Ajo for this.
        # Exception for dashed stuff for now and meta and community and multiple ones. (defined multiples will just go thru)
        contacted = []
        if (
            suggested_css_text not in ["Community", "Meta", "Multiple Languages", "App"]
            and "-" not in suggested_css_text
        ):
            # Load the Ajo to check against its history.
            # Get just the Reddit ID.
            mid = re.search(r"comments/(.*)/\w", opermalink).group(1)
            # Load the Ajo
            majo = ajo_loader(mid, self.config)

            # Checking the language history and the user history of the particular submission.
            try:
                # Load the history of languages this post has been in
                language_history = majo.language_history
                # Load the people who have been contacted before.
                contacted = majo.notified
                logger.debug(f"Ziwen Notifier: Already contacted {contacted}")

                language_name = convert(suggested_css_text).language_name

                # We allow it to send if it's the last (and only) item in this history.
                permission_to_proceed = not (
                    language_name in language_history
                    and language_name != language_history[-1]
                )
            except AttributeError:
                permission_to_proceed = True

            # If it's detected that we may have sent notifications for this already, just end it with no new notifications.
            if not permission_to_proceed:
                return []

        notify_users_list = []
        # First we need to do a test to see if it's a specific code or not.
        if "-" not in suggested_css_text:  # This is a regular notification.
            converted_language = convert(suggested_css_text)
            language_code = converted_language.language_code
            language_name = converted_language.language_name
            if suggested_css_text == "Multiple Languages":
                # Debug fix for the multiple ones.
                language_code = "multiple"
                language_name = "Multiple Languages"
            elif suggested_css_text in ["meta", "community"]:
                # Here we have code to make sure that only mods and the bot send notifications for meta/community posts.
                if not self.config.is_mod(oauthor):
                    # This OP is not a mod. Don't send notifications.
                    return []  # Exit.

                # Debug fix for the meta & community ones.
                language_code = suggested_css_text
                language_name = suggested_css_text.title()
                post_type = "post"  # Since these are technically not language requests
        else:  # This is a specific code, we want to add the people only signed up for them.
            # Note, this only gets people who are specifically signed up for them, not
            # We get the broader category here. (ar, unknown)
            language_code = suggested_css_text.split("-", 1)[0]
            language_name = convert(suggested_css_text).language_name
            if language_code == "unknown":  # Add a new script phrase
                # This is to distinguish script notifications
                language_name += " (Script)"
            regional_data = self.__notifier_regional_language_fetcher(
                suggested_css_text
            )
            if len(regional_data) != 0:
                # add the additional people to the notifications list.
                notify_users_list += regional_data

        notify_targets = fetch_users_to_notify(self.config.cursor_main, language_code)

        if len(notify_targets) == 0 and len(notify_users_list) == 0:
            # If there's no one on the list, just continue
            return []

        notify_users_list.extend(target["username"] for target in notify_targets)

        # Remove the usernames of users already contacted about this post.
        notify_users_list = list(set(notify_users_list) - set(contacted))

        # Code here to equalize data (see function above)
        notify_users_list = self.__notifier_equalizer(notify_users_list, language_name)

        # Write to the counter log how many we send
        action_counter(len(notify_users_list), "Notifications")
        # Clean up the title, prevent Markdown errors with square brackets
        otitle = self.__notifier_title_cleaner(otitle)

        # Exit if there is nothing to send.
        if len(notify_users_list) == 0:
            return []

        messaging_start = time.time()
        for username in notify_users_list:
            # Is from an !identify command.
            cur_message = MSG_NOTIFY if not is_identify else MSG_NOTIFY_IDENTIFY
            message = cur_message.format(
                username=username,
                language_name=language_name,
                post_type=post_type,
                otitle=otitle,
                opermalink=opermalink,
                oauthor=oauthor,
            )
            try:
                self.config.reddit.redditor(username).message(
                    subject=f"[Notification] New {language_name} post on r/translator",
                    message=message + BOT_DISCLAIMER + MSG_UNSUBSCRIBE_BUTTON,
                )
                # Record that they have been messaged
                self.__notifier_limit_writer(username, language_code)
            except praw.exceptions.APIException:  # If the user deleted their account...
                logger.info(
                    f"Notifier: An error occured while sending a message to u/{username}. Removing..."
                )
                # Remove the username from our database.
                notifier_list_pruner(username, self.config)

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
            f"Notifier: Sent notifications to {len(notify_users_list)} users signed up for {language_name}."
        )

        return notify_users_list


class ZiwenMessageProcessor:
    def __init__(
        self, config: ZiwenConfig, message: praw.reddit.models.Message
    ) -> None:
        self.config = config
        self.message = message
        self.mbody = message.body
        self.mauthor = str(message.author)

    def __messaging_user_statistics_loader(self) -> str | None:
        """
        Function that pairs with messaging_user_statistics_writer. Takes a username and looks up what commands they have
        been recorded as using.
        If they have data, it will return a nicely formatted table. Since the notifications data is also recorded in the
        same database, this function will also format the data in that dictionary and integrate it into the table.

        :param username: The username of a Reddit user.
        :return: None if the user has no data (no commands that they called), a sorted table otherwise.
        """

        # Get commands data.
        self.config.cursor_main.execute(
            "SELECT commands FROM total_commands WHERE username = ?", (self.mauthor,)
        )
        username_commands_data = self.config.cursor_main.fetchone()

        # Get notifications data.
        self.config.cursor_main.execute(
            "SELECT received FROM notify_monthly_limit WHERE username = ?",
            (self.mauthor,),
        )
        notifications_commands_data = self.config.cursor_main.fetchone()
        commands_lines_to_post = []
        # Iterate over commands data.
        if username_commands_data is None:  # There is no data for this user.
            commands_lines_to_post = None
        else:  # There's data. Get the data and format it line-by-line.
            commands_dictionary = eval(username_commands_data["commands"])
            # We only want the stored dict here.
            for command_type, value in sorted(commands_dictionary.items()):
                if command_type != "Notifications":  # This is a regular command.
                    if command_type == KEYWORDS.back_quote:
                        command_type = "`lookup`"
                    formatted_line = f"| {command_type} | {value} |"
                    commands_lines_to_post.append(formatted_line)

        notifications_lines_to_post = None
        # Iterate over notifications data. Get the dictionary of notifications that were sent.
        if notifications_commands_data is not None:
            notifications_lines_to_post = []
            notification_dict = eval(notifications_commands_data["received"])
            for language_code, notification_num in sorted(notification_dict.items()):
                formatted_line = (
                    f"| Notifications (`{language_code}`) | {notification_num} |"
                )
                # Reform it as a string from a list.
                notifications_lines_to_post.append(formatted_line)

        if username_commands_data is None and notifications_commands_data is None:
            # Absolutely no information.
            return None
        # Format everything together. Convert None to blank list.
        if commands_lines_to_post is None:
            commands_lines_to_post = []
        if notifications_lines_to_post is None:
            notifications_lines_to_post = []
        return "| Command | Times |\n|---------|-------|\n" + "\n".join(
            commands_lines_to_post + notifications_lines_to_post
        )

    def __points_retreiver(self) -> str:
        """
        Fetches the total number of points earned by a user in the current month.
        This is used with the messages routine to tell people how many points they have earned.

        :param username: The username of a Reddit user as a string.
        :return to_post: A string containing information on how many points the user has received on r/translator.
        """

        current_time = time.time()
        month_string = datetime.fromtimestamp(current_time).strftime("%Y-%m")

        self.config.cursor_main.execute(
            "SELECT points FROM total_points WHERE username = ? AND month_year = ?",
            (self.mauthor, month_string),
        )
        # Returns a list of lists.
        username_month_points_data = self.config.cursor_main.fetchall()

        self.config.cursor_main.execute(
            "SELECT points, oid, month_year FROM total_points WHERE username = ?",
            (self.mauthor,),
        )
        username_all_points_data = self.config.cursor_main.fetchall()

        # Compile the monthly number of points the user has earned.
        month_points = sum(data["points"] for data in username_month_points_data)
        # Compile the total number of points the user has earned.
        all_points = 0
        # Compile the total number of posts participated.
        recorded_posts = set()
        # Compile the total number of months that have been recorded. .
        recorded_months = set()
        for data in username_all_points_data:
            all_points += data["points"]
            recorded_posts.add(data["oid"])
            recorded_months.add(data["month_year"])

        recorded_posts_count = len(recorded_posts)
        to_post = ""
        if all_points != 0:  # The user has points listed.
            to_post += (
                f"You've earned **{month_points} points** on r/translator this month.\n\n"
                f"You've earned **{all_points} points** in total and participated in **{recorded_posts_count} posts**.\n\n"
            )
            to_post += "Year/Month | Points | Number of Posts Participated\n-----------|--------|------------------"
        else:  # User has no points listed.
            return MSG_NO_POINTS

        # Generate rows of data from the points data.
        for month in sorted(recorded_months):
            self.config.cursor_main.execute(
                "SELECT points, oid FROM total_points WHERE username = ? AND month_year = ?",
                (self.mauthor, month),
            )
            month_data = self.config.cursor_main.fetchall()

            recorded_month_points = 0
            scratchpad_posts = set()
            for data in month_data:
                recorded_month_points += data["points"]
                scratchpad_posts.add(data["oid"])

            to_post += f"\n{month} | {recorded_month_points} | {len(scratchpad_posts)}"
        # Add a summary row for the totals.
        to_post += f"\n*Total* | {all_points} | {recorded_posts_count}"

        return to_post

    def __record_retrieve_error_log(self) -> str:
        """
        A simple routine to GET the last two errors and counters and include them in a ping reply.

        :return logging_output: A formatted string using Markdown's indenting syntax for code (four spaces per line).
        """

        # Error stuff. Open the file.
        with open(FILE_ADDRESS_ERROR, encoding="utf-8") as f:
            error_logs = f.read()

        # Obtain the last two errors that were recorded.
        penultimate_error = error_logs.split("------------------------------")[-2]
        # Add indenting of four spaces
        penultimate_error = penultimate_error.replace("\n", "\n    ")
        last_error = error_logs.split("------------------------------")[-1]
        last_error = last_error.replace("\n", "\n    ")  # Add indenting

        # Return the last two errors only.
        ping_error_output = penultimate_error + "\n\n" + last_error

        # Return what has been recorded for today_counter
        return f"\n\n{ping_error_output}"

    def process_subscribe(self):
        # User wants to subscribe to language notifications.
        logger.info(f"Messages: New subscription request from u/{self.mauthor}.")

        # This gets a list of language codes from the message body.
        language_matches = language_list_splitter(self.mbody)

        if language_matches is None:  # There are no valid codes to subscribe.
            # Reply to user.
            self.message.reply(
                MSG_CANNOT_PROCESS.format(MSG_SUBSCRIBE_LINK) + BOT_DISCLAIMER
            )
            logger.info("Messages: Subscription languages listed are not valid.")
        else:  # There are valid codes. Let's insert them into our database and reply with a confirmation message.
            # Insert the relevant codes.
            notifier_language_list_editor(
                language_matches, self.mauthor, self.config, "insert"
            )

            # Get the language names of those codes.
            final_match_names = [
                convert(code).language_name for code in language_matches
            ]

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
            self.message.reply(main_body + BOT_DISCLAIMER + MSG_UNSUBSCRIBE_BUTTON)
            logger.info(
                f"Messages: Added notification subscriptions for u/{self.mauthor}."
            )
            action_counter(len(language_matches), "Subscriptions")

    def process_unsubscribe(self):
        # User wants to unsubscribe from notifications.
        logger.info(f"Messages: New unsubscription request from u/{self.mauthor}.")

        # This gets a list of language codes from the message body.
        language_matches = language_list_splitter(self.mbody)

        # Iterate over the results.
        if language_matches is None:
            # There are no valid codes to unsubscribe them from.
            # Format the error reply message.
            self.message.reply(
                MSG_CANNOT_PROCESS.format(MSG_SUBSCRIBE_LINK) + BOT_DISCLAIMER
            )

            # Forward the message to my creator.
            self.config.reddit.redditor("kungming2").message(
                subject=f"Unsubscribe Attempt: u/{self.mauthor}",
                message=f"Forwarded message:\n\n---\n\n{self.mbody}",
            )
            logger.info(
                "Messages: Unsubscription languages listed are invalid. Replied w/ more info."
            )
        elif "all" in language_matches:
            # User wants to unsubscribe from everything.
            # Delete the user from the database.
            notifier_language_list_editor(
                language_matches, self.mauthor, self.config, "purge"
            )

            # Send the reply.
            self.message.reply(
                MSG_UNSUBSCRIBE_ALL.format("all", MSG_SUBSCRIBE_LINK) + BOT_DISCLAIMER
            )
            action_counter(1, "Unsubscriptions")
        else:  # Should return a list of specific languages the person doesn't want.
            # Delete the relevant codes.
            notifier_language_list_editor(
                language_matches, self.mauthor, self.config, "delete"
            )
            # Get the language names of those codes.
            final_match_names = [
                convert(code).language_name for code in language_matches
            ]

            # Join the list into a string that is bulleted.
            bullet_list = "\n* ".join(final_match_names)

            # Format the reply message.
            self.message.reply(
                MSG_UNSUBSCRIBE_ALL.format(bullet_list, MSG_SUBSCRIBE_LINK)
                + BOT_DISCLAIMER
                + MSG_UNSUBSCRIBE_BUTTON
            )
            logger.info(
                f"Messages: Removed notification subscriptions for u/{self.mauthor}."
            )
            action_counter(len(language_matches), "Unsubscriptions")

    def process_ping(self):
        logger.info(f"Messages: New status check from u/{self.mauthor}.")
        to_post = "Ziwen is running nominally.\n\n"

        # Determine if user is a moderator.
        if self.config.is_mod(self.mauthor):  # New status check from moderators.
            # Get the last two recorded error entries for debugging.
            to_post += self.__record_retrieve_error_log()
            if len(to_post) > 10000:  # If the PM is too long, shorten it.
                to_post = to_post[0:9750]

        # Reply to user.
        self.message.reply(to_post + BOT_DISCLAIMER)
        logger.info("Messages: Replied with ping call.")

    def process_status(self):
        logger.info(f"Messages: New status request from u/{self.mauthor}.")

        # We try to retrieve the languages the user is subscribed to.
        self.config.cursor_main.execute(
            "SELECT language_code FROM notify_users WHERE username = ?",
            (self.mauthor,),
        )
        # Returns a list of lists w/ the language code & the username
        all_subscriptions = self.config.cursor_main.fetchall()
        final_match_codes = [
            subscription["language_code"] for subscription in all_subscriptions
        ]

        # User is not subscribed to anything.
        if len(final_match_codes) == 0:
            status_component = MSG_NO_SUBSCRIPTIONS.format(MSG_SUBSCRIBE_LINK)
        else:
            final_match_names = []
            for code in final_match_codes:  # Convert the codes into names
                converted_result = convert(code)  # This will return a tuple.
                # Should get the name from each
                match_name = converted_result.language_name
                if code == "meta":
                    match_name = "Meta"
                elif code == "community":
                    match_name = "Community"
                elif "unknown-" in code:  # For scripts
                    match_name += " (Script)"
                final_match_names.append(match_name)

            # De-dupe and sort the returned languages.
            # Alphabetize
            final_match_names = sorted(set(final_match_names), key=str.lower)

            # Format the message to send to the requester.
            status_message = (
                "You're subscribed to notifications on r/translator for:\n\n* {}"
            )
            status_component = status_message.format("\n* ".join(final_match_names))

        # Get the commands the user may have used before.
        user_commands_statistics_data = self.__messaging_user_statistics_loader()
        if user_commands_statistics_data is not None:
            commands_component = (
                "\n\n### User Commands Statistics\n\n" + user_commands_statistics_data
            )
        else:
            commands_component = ""

        # Compile the components together
        compilation = "### Notifications\n\n" + status_component + commands_component

        action_counter(1, "Status checks")
        self.message.reply(compilation + BOT_DISCLAIMER + MSG_UNSUBSCRIBE_BUTTON)

    def process_add(self):
        if not self.config.is_mod(self.mauthor):
            return
        # Mod manually adding people to the notifications database.
        logger.info(
            f"Messages: New username addition message from moderator u/{self.mauthor}."
        )

        # Get the username of the user we want to add to the database.
        add_username = self.mbody.split("USERNAME:", 1)[1]
        # Get the username (no u/)
        add_username = add_username.split("LANGUAGES", 1)[0].strip()

        # Split off the languages part.
        language_component = self.mbody.rpartition("LANGUAGES:")[-1].strip()

        # This gets a list of language codes from the message body.
        language_matches = language_list_splitter(language_component)

        if language_matches is not None:
            # In case the moderators' addition string is incomprehensible.
            # Insert the relevant codes.
            notifier_language_list_editor(
                language_matches, add_username, self.config, "insert"
            )

            # Reply to moderator.
            match_codes_print = ", ".join(language_matches)
            addition_message = (
                f"Added the language codes **{match_codes_print}** for u/{add_username}"
                " into the notifications database."
            )

            self.message.reply(addition_message)

    def process_remove(self):
        if not self.config.is_mod(self.mauthor):
            return
        # Mod manually removing people from the notifications database.
        logger.info(
            f"Messages: New username removal message from moderator u/{self.mauthor}."
        )

        # Get the username of the user we want to add to the database.
        remove_username = self.mbody.split("USERNAME:", 1)[1].strip()

        # We try to retrieve the languages the user is subscribed to.
        self.config.cursor_main.execute(
            "SELECT language_code FROM notify_users WHERE username = ?",
            (remove_username,),
        )
        all_subscriptions = (
            self.config.cursor_main.fetchall()
        )  # Returns a list of lists with both the code and the username.
        subscribed_codes = [
            subscription["language_code"] for subscription in all_subscriptions
        ]

        # Actually delete the username from database.
        notifier_language_list_editor([], remove_username, self.config, "purge")

        # Send a message back to the moderator confirming this.
        final_match_codes_print = ", ".join(subscribed_codes)
        removal_message = f"Removed the subscriptions for u/{remove_username} from the notifications database. (**{final_match_codes_print}**)"
        self.message.reply(removal_message)

    def process_points(self):
        logger.info(f"Messages: New points status request from u/{self.mauthor}.")
        # Get the user's points
        user_points_output = (
            "### Points on r/translator\n\n" + self.__points_retreiver()
        )

        # Get the commands the user may have used before.
        user_commands_statistics_data = self.__messaging_user_statistics_loader()
        commands_component = (
            ""
            if user_commands_statistics_data is None
            else ("\n\n### Commands Statistics\n\n" + user_commands_statistics_data)
        )

        self.message.reply(user_points_output + commands_component + BOT_DISCLAIMER)
        action_counter(1, "Points checks")


def ziwen_messages(config: ZiwenConfig):
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
    messages = list(config.reddit.inbox.unread(limit=5))
    for message in messages:
        processor = ZiwenMessageProcessor(config, message)
        message.mark_read()  # Mark the message as read.
        # not dictionary since unsubscribe must come before subscribe
        keyword_mapping = [
            ("unsubscribe", processor.process_unsubscribe),
            ("subscribe", processor.process_subscribe),
            ("ping", processor.process_ping),
            ("status", processor.process_status),
            ("add", processor.process_add),
            ("remove", processor.process_remove),
            ("points", processor.process_points),
        ]
        msubject = message.subject.lower()  # Convert to lowercase
        for keyword, func in keyword_mapping:
            if keyword in msubject:
                func()
                break
