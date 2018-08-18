#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import calendar
import datetime
import pprint
import shutil
import sqlite3
import textwrap
import time
import traceback

import praw  # A simple interface to the Reddit API that also handles rate limiting of requests
import prawcore
import requests
import wikipedia
from google import search
from lxml import html

from _config import *
from _languages import *  # Import all the languages
from _responses import *

BOT_NAME = 'Wenyuan'
VERSION_NUMBER = '3.0.20'
USER_AGENT = '{} {}, a statistics routine for r/translator. Maintained by u/kungming2.'.format(BOT_NAME, VERSION_NUMBER)
# Choose either r/translator or r/trntest for testing.
SUBREDDIT = "translator"

pp = pprint.PrettyPrinter(indent=4)

WAIT = 3600

'''BOT CONFIGURATION'''
IMAGE_KEYWORDS = ['imgur', 'i.redd.it', 'photobucket', 'gyazo', 'tinypic', 'facebook.com/photo', 'i.reddituploads']
VIDEO_KEYWORDS = ['youtube', 'vimeo', 'liveleak', 'dailymotion', 'streamable', 'xhamster', 'vid.me', 'youtu.be',
                  'pornhub', 'v.redd.it']
AUDIO_KEYWORDS = ['spotify', 'vocaroo', 'soundcloud', 'clyp.it', 'picosong']
TRANSLATED_TAGS = ['translated', 'multiple', '?', '--', 'doublecheck']
UTILITY_CODES = ['Conlang', 'Nonlanguage', 'Unknown', 'App', 'Multiple Languages', 'Generic']


def worldpopulation():
    """Grab the world's population in .json format by using a GET request
    Credit: https://github.com/Logicmn/World-Population-Bot
    """
    x = requests.get('http://api.population.io:80/1.0/population/World/today-and-tomorrow/')
    world = x.json()
    worldpop = world['total_population']
    today = worldpop[0]
    todaypop = int(today['population'])  # Convert the population to an integer
    todaypop = int(round(todaypop / 1000000))
    logger.debug("[WY] worldpopulation: Retrieved world population of {}.".format(todaypop))

    return todaypop


# Get a live world population count from the World Population API
WORLD_POP = worldpopulation()  # Define the global world population used for the RI calculation.
ZW_USERAGENT = get_random_useragent()

print('\n|======================Logging in as u/translator-BOT...======================|')

reddit = praw.Reddit(client_id=WENYUAN_APP_ID,
                     client_secret=WENYUAN_APP_SECRET, password=PASSWORD,
                     user_agent=USER_AGENT, username=USERNAME)
r = reddit.subreddit(SUBREDDIT)

# This connects the bot with the run_reference cache for Wenyuan/Ziwen
# We store language data here for the run_reference command as a cache
zw_reference_cache = sqlite3.connect(FILE_ADDRESS_REFERENCE)
zw_reference_cursor = zw_reference_cache.cursor()
# This connects the bot with the database of points
conn_p = sqlite3.connect(FILE_ADDRESS_POINTS)  
cursor_p = conn_p.cursor()
# This connects the bot with the database of users signed up for notifications
conn = sqlite3.connect(FILE_ADDRESS_NOTIFY)
cursor = conn.cursor()
# Local storage for Ajos
conn_ajo = sqlite3.connect(FILE_ADDRESS_AJO_DB)  # This connects the bot with the database of Ajos
cursor_ajo = conn_ajo.cursor()

print('|=============================================================================|')
print('  Initializing {} {} for r/translator...\n'.format(BOT_NAME, VERSION_NUMBER))
print('  with languages module {}'.format(VERSION_NUMBER_LANGUAGES))
print('|=============================================================================|')


def data_validator():
    """A simple function that checks the databases to verify that they're up-to-date.
    It displays a warning if some of the databases may need to be redownloaded.
    """
    
    to_warn = False
    hours_difference = 24 * 60 * 60
    
    # Check the Points database
    current_now = time.time()
    month_year = datetime.datetime.fromtimestamp(current_now).strftime('%Y-%m')
    sql_command = "SELECT * FROM total_points WHERE month_year = '{}'".format(month_year)
    cursor_p.execute(sql_command)
    username_month_points_data = cursor_p.fetchall()  # Returns a list of lists.
    
    # If there's no data from the last or current month's points...
    if len(username_month_points_data) == 0:  
        to_warn = True

    # Check the notification database
    sql_command = "SELECT * FROM notify_users"
    cursor.execute(sql_command)
    all_subscriptions = cursor.fetchall()
    
    # If there's little data from notifications database
    if len(all_subscriptions) <= 10:  
        to_warn = True
    
    # Check the Ajo database
    most_recent_time = 1000000000  # Really small value compared to the regular dates.
    cursor_ajo.execute("SELECT * FROM local_database")
    stored_ajos = cursor_ajo.fetchall()

    for ajo in stored_ajos:
        time_created = int(ajo[1])  # Get the UTC time it was created.
        if most_recent_time < time_created:
            most_recent_time = time_created
    
    # Get the time difference
    time_difference = current_now - most_recent_time
    if time_difference > hours_difference:
        to_warn = True
    
    if to_warn:  # Notify that the files may need updating.
        print('| Note: The database files (Ajo, Notifications, Reference, Points) may need to be '
              '\n| updated to their latest versions.')
    
    return


data_validator()


'''STATUS UPDATES'''


def bot_status_update():
    """
    A simple function that posts a status update of the bot to its profile at u/translator-BOT.
    """

    time_format = '%Y-%m-%d'
    thread_title = 'Ziwen Status Update — {timestamp}'
    title = thread_title.format(timestamp=time.strftime(time_format))
    reason = input("\n> Reason: Due to ...")
    offline_time = input("> Enter the number of hours the bot will be offline: ")
    offline_time_secs = int(offline_time) * 3600
    current_function_time = int(time.time())
    offline_time_end = int(current_function_time + offline_time_secs)
    utc_time = datetime.datetime.utcfromtimestamp(offline_time_end)
    url_time = utc_time.strftime('%Y%m%dT%H%M')
    body = WY_STATUS_UPDATE.format(reason=reason, utc_time=utc_time, url_time=url_time)
    submission = reddit.subreddit("u_translator-BOT").submit(title=title, selftext=body, send_replies=False)
    submission.mod.sticky()
    logger.info("[WY] bot_status_update: Submitted a status update to my profile.")
    return


def bot_status_delete():
    """
    This function deletes all previous status posts on the bot's profile.
    :return: Nothing.
    """

    for result in reddit.subreddit("u_translator-BOT").new(limit=50):
        if "Status Update" in result.title:
            status_target = reddit.submission(id=result.id)
            status_target.delete()
            logger.debug("\n>> Deleted the last status update.")

    logger.info("[WY] bot_status_delete: Deleted all status updates.")

    return


def del_comments():
    TESTING_SUBREDDITS.append('trntest')  # Add trntest too.
    for comment in reddit.redditor(USERNAME).comments.new(limit=125):
        if comment.subreddit in TESTING_SUBREDDITS:
            print("r/{}".format(comment.subreddit))
            print(comment.body.split('\n', 1)[0][:79])
            comment.delete()
            print("> Deleted.")


def del_submissions():
    TESTING_SUBREDDITS.append('trntest')  # Add trntest too.
    for submission in reddit.redditor(USERNAME).submissions.new(limit=25):
        if submission.subreddit in TESTING_SUBREDDITS:
            print(submission.title)
            submission.delete()
            print("> Deleted.")


def weekly_challenge_poster():
    """
    Function to take a preformed file for the weekly translation challenge and post it as a stickied post.
    """

    with open(FILE_ADDRESS_WEEKLY_CHALLENGE, "r", encoding="utf-8") as f:
        weekly_challenge_md = f.read()

    weekly_title = '[English > Any] Weekly Translation Challenge — {}'
    current_tempo = time.time()
    timestamp_utc = str(datetime.datetime.fromtimestamp(current_tempo).strftime("%Y-%m-%d"))
    weekly_title = weekly_title.format(timestamp_utc)

    # Submit this file.
    submission = r.submit(title=weekly_title, selftext=weekly_challenge_md, send_replies=False)
    submission.mod.sticky(bottom=False)
    logger.info("[WY] weekly_challenge_poster: Submitted the weekly challenge to r/translator.")
    return


'''INFO GETTING ROUTINES'''


def seconds_till_next_hour():  # Function to determine seconds until the next hour to act.
    time_of_the_hour = 5  # At 12:05
    time_of_the_hour *= 60
    # The time of the hour we want this to operate

    current_waktu = int(time.time())  # Returns the Unix timestamp of now.
    waktu_string = strftime('%Y:%m:%d:%H')

    next_time = int(time.mktime(datetime.datetime.strptime(waktu_string, "%Y:%m:%d:%H").timetuple()))
    next_time = next_time + 3600  # Add an hour.

    seconds_remaining = time_of_the_hour + next_time - current_waktu

    return seconds_remaining  # Returns the number of second remaining as an integer


def notify_list_statistics_calculator():
    """
    Function to gather statistics on the state of our notifications.
    :return: A tuple containing various datasets for use.
    """

    sql_command = "SELECT * FROM notify_users"
    cursor.execute(sql_command)
    all_subscriptions = cursor.fetchall()

    header = "\n\nLanguage | Subscribers\n-----|-----\n"
    all_lang_codes = []
    format_lines = []

    for subscription in all_subscriptions:
        all_lang_codes.append(subscription[0])  # Add the language code to the database.

    all_lang_codes = list(set(all_lang_codes))

    for code in all_lang_codes:
        code_cmd = "SELECT * FROM notify_users WHERE language_code = '{}'".format(code)
        cursor.execute(code_cmd)
        code_subscriptions = cursor.fetchall()
        code_num = len(code_subscriptions)
        name = converter(code)[1]
        if len(name) == 0:  # Meta and Community Codes
            name = code.title()
        format_lines.append("{} | {}".format(name, str(code_num)))

    format_lines = list(sorted(format_lines))  # Alphabetize

    unique_lang = len(format_lines)
    total_subscriptions = len(all_subscriptions)
    if unique_lang != 0:
        average_per = total_subscriptions / unique_lang
    else:
        average_per = 0

    dupe_subs = set([x for x in all_subscriptions if all_subscriptions.count(x) > 1])  # subscribers listed twice

    if len(dupe_subs) == 0:
        dupe_subs = None  # If there's nothing in the set, then just give it None.

    line_1 = "\n* Unique languages in database:       {} languages".format(str(unique_lang))
    line_2 = "\n* Total subscriptions in database:    {} subscribers".format(str(total_subscriptions))
    line_3 = "\n* Average subscriptions per language: {} subscribers".format(str(round(average_per, 2)))

    overall_data = line_1 + line_2 + line_3
    total_table = header + "\n".join(format_lines)
    logger.info("[WY] notify_list_statistics_calculator: {}".format(line_2))

    # Calculate against the ISO 639-1 Chart to see which we don't have.
    missing_codes = []
    iso_sorted = list(sorted(ISO_639_1, key=str.lower))  # Sort the ISO list by alphabetical order
    ignore_codes = ["bh", "en", "nn"]
    for listing in iso_sorted:  # Iterate through the codes.
        if all_lang_codes.count(listing) == 0 and len(listing) == 2 and listing not in ignore_codes:
            line = "{} | {}".format(listing, converter(listing)[1],)
            missing_codes.append(line)
    missing_codes_num = len(missing_codes)

    missing_codes_format = "\n### No Subscribers ({} languages)\nCode | Language\n---|----\n".format(missing_codes_num)
    missing_codes_format += "\n".join(missing_codes)

    return overall_data, total_table, dupe_subs, missing_codes_format


def notify_list_dedupe():
    """
    Function to remove duplicate entries from the notifications database
    The way it works is it takes a list of duplicates, deletes them, then re-adds them
    Thus it does not preserve *when* someone signs up for a language.
    I've since added a function to Ziwen that checks against adding duplicates so this is kind of deprecated.
    """
    
    notify_total_data = notify_list_statistics_calculator()
    duplicated_data = notify_total_data[2]
    
    for datum in duplicated_data:  # Each entry is a tuple: (lang_code, username)
        lang_code = datum[0]
        username = datum[1]
        command = "DELETE FROM notify_users WHERE language_code = '{}' AND username = '{}'"
        command = command.format(lang_code, username)
        cursor.execute(command)
        cursor.execute("INSERT INTO notify_users VALUES (?, ?)", datum)
        conn.commit()
        print("Deduped... " + str(datum))


def full_retrieval():
    """
    Retrieve a set amount of posts from r/translator and run them through the title routine
    Useful for testing changes to the converter() or title_format() function.
    """

    current_function_time = time.time()

    all_title_text = []

    posts = []
    posts_display = []
    posts_problematic = []
    posts_non_css = []
    posts_multiple = []
    posts_regional = []
    processed_times = []

    posts += list(r.new(limit=1000))  # Unfortunately we can no longer fetch stuff from earlier.

    header = "\nSource | Target | CSS | CSS Text | Post Title | Actual Title |"
    header += "Author | Processed Title | Lang/Ctry | Direction\n---|---|---|---|---|---|---|---|---|---\n"

    for post in posts:

        if ">" not in post.title:
            if "english" not in post.title.lower()[0:25]:
                continue

        if post.link_flair_css_class is not None:
            if "meta" in post.link_flair_css_class or "community" in post.link_flair_css_class:
                continue
        try:
            post_time = time.time()
            title_display = post.title
            if "|" in title_display:
                title_display = title_display.replace("|", "\|")  # replace problematic characters
            if "]" in title_display:
                title_display = title_display.replace("]", "\]")  # replace problematic characters
            if "[" in title_display:
                title_display = title_display.replace("[", "\[")  # replace problematic characters
            if ")" in title_display:
                title_display = title_display.replace(")", "\)")  # replace problematic characters
            if "(" in title_display:
                title_display = title_display.replace("(", "\(")  # replace problematic characters
            if "`" in title_display:
                title_display = title_display.replace("`", "\`")  # replace problematic characters

            data = title_format(post.title)
            source = ", ".join(data[0])
            target = ", ".join(data[1])
            try:
                author = "[u/" + post.author.name + "](https://www.reddit.com/user/" + post.author.name + ")"
            except AttributeError:
                author = "UNKNOWN"
            link = "https://redd.it/" + post.id
            css = data[2]
            css_text = data[3]
            title_real = data[4]
            title_processed = data[5]
            country_language = data[7]
            direction = data[8]

            entry = "{} | {} | {} | {} | [{}]({}) | {} | {} | {} | {} | {}"
            entry = entry.format(source, target, css, css_text, title_display, link, title_real, author,
                                 title_processed, country_language, direction)
            all_title_text.append(title_real)
            posts_display.append(entry)
            if css == "generic":  # Check to see if something is given both Generic classifications.
                if css_text == "Generic":
                    posts_problematic.append(entry)
                elif css_text != "Generic":
                    posts_non_css.append(entry)
            elif css in ['multiple', 'app']:
                posts_multiple.append(entry)

            if country_language is not None:  # Let's record the regional combos
                posts_regional.append(entry)
            elapsed_time = time.time() - post_time
            processed_times.append(elapsed_time)
        except UnboundLocalError:  # Problematic ones that fail conversion get this marker
            entry = " !!! | ---  | ---  | ---  | **{}** | ---  ".format(post.title)
            error_entry_title = traceback.format_exc()
            error_log_basic(error_entry_title, "Wenyuan {}".format(VERSION_NUMBER))  # Print error.
            posts_display.append(entry)
            posts_problematic.append(entry)

    # Format all
    posts_display = "\n".join(posts_display)
    posts_problematic_display = "\n".join(posts_problematic)
    total_output = header + posts_display
    if len(posts_non_css) is not 0:
        total_output += "\n\n## Non-Supported CSS Posts\n\n" + header + "\n".join(posts_non_css)
    if len(posts_regional) is not 0:
        total_output += "\n\n## Language/Country Regional Posts\n\n" + header + "\n".join(posts_regional)
    if len(posts_multiple) is not 0:
        total_output += "\n\n## Multiple/App Posts\n\n" + header + "\n".join(posts_multiple)
    if len(posts_problematic) is not 0:
        total_output += "\n\n## Problematic Posts\n\n" + header + posts_problematic_display
    print(total_output)

    # print(" ".join(all_title_text))

    accuracy_raw = 100 * (1 - float(len(posts_problematic) / len(posts)))
    accuracy = round(accuracy_raw, 4)
    supported_raw = 100 * (1 - float(len(posts_non_css) / len(posts)))
    supported = round(supported_raw, 4)
    elapsed_duration = (time.time() - current_function_time)

    # Calculate the final data
    final_tally = WY_FULL_RETRIEVAL_DATA.format(
        len(posts),
        len(posts_non_css),
        len(posts_regional),
        len(posts_problematic),
        str(accuracy),
        str(supported),
        round(sum(processed_times) / len(posts), 4),
        round(elapsed_duration, 2)
    )

    # Write the info to a text file.
    permission = input("\n> Would you like to write the retrieved titles to a text file? Type 'y' or 'n': ")

    if permission == "y":
        f = open(FILE_ADDRESS_TITLE_LOG, 'w', encoding="utf-8")  # File address for the error log, cumulative.
        f.write(total_output + final_tally)
        f.close()
        print(">> Saved.")
    else:
        print(">> Did not write to text file.")

    # Print out how long it took.
    print(final_tally)


def month_points_summary(month_year):
    """
    A function that gathers the people who have points in a given month.
    """

    point_limit = 75  # The bot will not format results for users with less than this amount.

    usernames = []
    usernames_w_points = []
    to_post = "\nUsername | Points in {0} | Total Cumulative Points | Participated Posts in {0}\n-----------|--------|-------|------".format(
        month_year)

    sql_command = "SELECT * FROM total_points WHERE month_year = '{}'".format(month_year)
    cursor_p.execute(sql_command)
    username_month_points_data = cursor_p.fetchall()  # Returns a list of lists.

    for data in username_month_points_data:
        usernames.append(data[2])  # add each user name to a list of usernames.

    usernames = list(set(usernames))  # Remove duplicates, this is now a list of usernames.
    usernames = sorted(usernames, key=str.lower)  # alphabetize the list.

    for name in usernames:
        recorded_month_points = 0
        recorded_total_points = 0
        scratchpad_posts = []

        command = "SELECT * FROM total_points  WHERE username = '{}' AND month_year = '{}'".format(name, month_year)
        cursor_p.execute(command)
        month_data = cursor_p.fetchall()

        command_total = "SELECT * FROM total_points  WHERE username = '{}'".format(name)
        cursor_p.execute(command_total)
        total_data = cursor_p.fetchall()

        for data in month_data:
            recorded_month_points += data[3]
            scratchpad_posts.append(data[4])

        for data in total_data:
            recorded_total_points += data[3]

        recorded_posts = len(list(set(scratchpad_posts)))
        if recorded_month_points < point_limit:  # No need to record these low-point users
            continue
        usernames_w_points.append((name, recorded_month_points, recorded_posts, recorded_total_points))

    usernames_w_points = sorted(usernames_w_points, key=lambda x: x[1],
                                reverse=True)  # Sort by the people with the most points first

    for name in usernames_w_points:
        username_line = "\nu\/{} | {} | {} | {} posts".format(name[0], str(name[1]), str(name[3]), str(name[2]))
        to_post += username_line

    return to_post


'''UPDATING TABLES'''


def wiki_lang_page_searcher():  # Function to search the wiki for language pages for stats, return it as a dict.

    language_pages = []

    ignore_pages = ["toolbox", "overall_statistics", "verified", "ziwen", "wenyuan", "verification_log", "usernotes",
                    "userflair", "tattoos", "statistics", "rules", "request-guidelines", "redirects", "old_statistics",
                    "linkflair", "language_faqs", "index", "identification", "getverified", "graphic_assets", "index"]

    for wikipage in reddit.subreddit(SUBREDDIT).wiki:  # We can safely avoid these pages.

        if wikipage.name in ignore_pages:
            continue

        wpermalink = "http://www.reddit.com/r/translator/wiki/{}".format(wikipage.name)
        wname = wikipage.name.title()
        wname = wname.replace("_", " ")

        if " 20" not in wname and "Config/" not in wname:
            wcontent = wikipage.content_md
        else:
            continue

        if "![](%%statistics-h%%)" in wcontent:
            # print(wname)
            language_pages.append("[{}]({})".format(wname, wpermalink))
            # print(wikipage)
            # pp.pprint(vars(wikipage))
        else:
            continue

    return language_pages


def statistics_table_former():  # Takes a list of language wiki links and formats as a table.
    language_pages = wiki_lang_page_searcher()
    total_length = len(language_pages)
    remainder = total_length % 8

    language_pages_main = language_pages[:(total_length-remainder)]  # The bulk of the table, in columns of 8
    if remainder != 0:  # There actually is a remainder.
        language_pages_remainder = language_pages[-remainder:]
        # This is the remainder, which we have to format different.
    else:
        language_pages_remainder = None

    to_post = "\n| | | | | | | | |\n|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|\n"
    row_template = "| {} | {} | {} | {} | {} | {} | {} | {} |\n"
    for i in range(0, len(language_pages_main), 8):  # Begin formatting the main rows.
        to_post += row_template.format(language_pages_main[i], language_pages_main[i+1], language_pages_main[i+2],
                                       language_pages_main[i + 3], language_pages_main[i+4], language_pages_main[i+5],
                                       language_pages_main[i + 6], language_pages_main[i + 7],)

    if language_pages_remainder is not None:
        to_post += " | ".join(language_pages_remainder)

    return to_post


def statistics_page_updater(language_table):  # Takes a formatted language table and updates the main statistics page

    statistics_page = reddit.subreddit(SUBREDDIT).wiki["statistics"]
    statistics_page_content = statistics_page.content_md

    anchor_1 = "\n### [Individual Language Statistics](https://www.reddit.com/r/translator/wiki/linkflair)"
    anchor_2 = "\n### Wenyuan"

    statistics_page_former = statistics_page_content.split(anchor_1)[0]
    statistics_page_latter = statistics_page_content.split(anchor_2)[1]

    new_content = statistics_page_former + anchor_1 + language_table + anchor_2 + statistics_page_latter

    statistics_page.edit(content=new_content, reason='Updating the language statistics main table.')
    print("> Statistics table updated.")


def other_translated(linkflair):
    """
    Simple function to help note down weird/malformed tags. This is only used in the deprecated statistics calculator.
    Cerbo does not needs to use this as it relies on Ajos instead.
    :param linkflair: The linkflair of the tag. For example, 'Translated [--]'
    :return: Whether the tag is supported and the language thereof.
    """

    is_supported = False

    if "Translated" in linkflair and "[" not in linkflair:
        # Here we take care of flair text that DOES NOT have a language tag.
        is_supported = False
        translated_tag = "--"
        return is_supported, translated_tag
    elif "Review" in linkflair and "[" not in linkflair:
        # Here we take care of flair text that DOES NOT have a language tag.
        is_supported = False
        translated_tag = "--"
        return is_supported, translated_tag

    translated_tag = linkflair.split(' ')[1]
    if "Review" in translated_tag:
        translated_tag = linkflair.split(' ')[2]  # account for "Needs Review", which has an extra space
    elif "Assets" in translated_tag:
        translated_tag = linkflair.split(' ')[2]  # account for "Missing Assets", which has an extra space
    elif "Progress" in translated_tag:
        translated_tag = linkflair.split(' ')[2]  # account for "In Progress", which has an extra space
    translated_tag = translated_tag[1:-1].lower()  # Remove square brackets

    if translated_tag in TRANSLATED_TAGS:
        # If it's a translated tag which is not supposed to be there at all! E.g. `Translated [?]`
        is_supported = False
        return is_supported, translated_tag

    if translated_tag not in SUPPORTED_CODES:
        is_supported = False
    elif translated_tag in SUPPORTED_CODES:
        is_supported = True

    return is_supported, translated_tag


def other_reference(string_text):
    """
    Function to look up languages that might be dead and hence not on Ethnologue
    This is the second version of this function - streamlined to be more effective.
    """

    no_results_comment = 'Sorry, there were no valid results on [Ethnologue](https://www.ethnologue.com/) or [MultiTree](http://multitree.org/) for "{}."'.format(
        string_text)
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
        logger.info("[ZW] No results for the reference search term {} on Multitree.".format(string_text))
        return no_results_comment  # Exit earlu
    else:  # We do have results.
        language_name = tree.xpath('//*[@id="code-info"]/div[1]/div[1]/span[2]/text()')
        alt_names = tree.xpath('//*[@id="code-info"]/div[1]/div[1]/span[6]/text()')
        language_classification = tree.xpath('//*[@id="code-info"]/div[1]/div[1]/span[14]/text()')
        lookup_line_1 = '\n**Language Name**: ' + language_name[0]
        lookup_line_1 += '\n\n**ISO 639-3 Code**: ' + language_iso3
        lookup_line_1 += '\n\n**Alternate Names**: ' + alt_names[0] + '\n\n**Classification**: ' + \
                         language_classification[0]

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

        to_post = str(
            "## [{}]({})\n{}{}{}".format(language_name[0], multitree_link, lookup_line_1, wk_chunk, lookup_line_2))

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

    if len(check_code) != 0:  # There is actually a code from our converter for this.
        print(">> Reference Code: {}".format(check_code))
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
            # tree = html.fromstring(eth_page.content)  # now contains the whole HTML page
            # language_population = tree.xpath('//div[contains(@class,"field-population")]/div[2]/div/p/text()')

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
            wf_link = "[{0}](https://en.wikipedia.org/w/index.php?search={0} language family)".format(
                language_classification)

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


def wenyuan_cache_fetcher(language_code):  # small function to fetch language reference data from Ziwen's cache
    sql_command = "SELECT * FROM language_cache WHERE language_code = '{}'".format(language_code)
    # We try to see if the cache has this language. 
    zw_reference_cursor.execute(sql_command)
    sql_result = zw_reference_cursor.fetchall()

    try:
        reference_body = sql_result[0][1]  # This is the main reference data for this language
    except IndexError:  # The entry for this language does not exist?
        return None

    # Get the language population string.
    try:
        language_population = reference_body.split("**Population**: ", 1)[1]
        language_population = language_population.split("\n", 1)[0]
        # print(language_population)
    except IndexError:  # Looks like it's a MultiTree entry, or no speakers
        language_population = "No known"

    if "Total users" in language_population and "No known" not in language_population:
        # There's a listing of how many in total countries
        language_population = language_population.split("all countries: ", 1)[1]
        language_population = language_population.split(' ', 1)[0]
        for character in [',', '.', ';', '(', ':']:  # Take out punctuation
            language_population = language_population.replace(character, '')
        language_population = int(language_population)
    elif "No known" in language_population:  # Nobody speaks this.
        language_population = 0
    else:  # For all other cases, take the first number
        language_population = language_population.replace(',', '')
        # print("++ " + language_population)
        language_population = [int(s) for s in language_population.split() if s.isdigit()]
        language_population = int(language_population[0])  # Get the first population number

    # Retrieve the language family name.
    language_family = reference_body.split("**Classification**: ", 1)[1]
    language_family = language_family.split("\n", 1)[0]
    if "[" in language_family and ")" in language_family:  # This is a Markdown link
        language_family = re.search(r"\[(\D+)\]", language_family)
        language_family = language_family.group(1)
    else:
        if "(" in language_family:
            language_family = language_family.split("(", 1)[0]
        language_family = language_family.strip()
    language_family = language_family.title()  # Capitalize it.
    # print(language_family)

    return language_family, language_population  # Pass the information back to the main


def other_statistics_calculator():
    rex = reddit.subreddit('excel')

    current_aika = int(time.time())
    earliest_time = 2000000000

    oid = []
    oflair_css = []
    ois_self = []
    ourl = []
    otitle = []

    for result in rex.new(limit=1000):
        if result.created_utc < earliest_time:
            earliest_time = int(result.created_utc)
        oid.append(result.id)
        oflair_css.append(result.link_flair_css_class)
        if result.is_self:
            ois_self.append(result.is_self)
        ourl.append(result.url)
        otitle.append(result.title)

    complete_total = len(oid)
    waitingonop_total = oflair_css.count("waitingonop")
    solved_total = oflair_css.count("solvedcase")
    not_solved_total = oflair_css.count("notsolvedcase")
    abandoned_total = oflair_css.count('abandoned')
    template_total = oflair_css.count('template')
    discussioncase_total = oflair_css.count('discussioncase')
    paidservice_total = oflair_css.count('paidservice')
    protip_total = oflair_css.count('protip')
    challenge_total = oflair_css.count('challenge')
    solvedpoint_total = oflair_css.count('solvedpoint')
    solved_total += (solvedpoint_total + challenge_total)
    solved_percentage = str("{0:.0f}%".format((solved_total + waitingonop_total) / complete_total * 100))

    subs = rex.subscribers
    subs = str("{:,}".format(subs))

    hours_since = round((current_aika - earliest_time) / 3600, 2)
    current_year = int(datetime.datetime.fromtimestamp(current_aika).strftime('%Y'))
    current_month = int(datetime.datetime.fromtimestamp(current_aika).strftime('%m'))
    days_in_month = int(calendar.monthrange(current_year, current_month)[1])
    estimated_total_posts = int((complete_total / hours_since) * days_in_month * 24)

    earliest_time_formatted = datetime.datetime.fromtimestamp(earliest_time).strftime('%Y-%m-%d [%H:%M:%S]')
    current_aika_formatted = datetime.datetime.fromtimestamp(current_aika).strftime('%Y-%m-%d [%H:%M:%S]')

    page_content = "\n\n## Data from {} to {}".format(earliest_time_formatted, current_aika_formatted)

    header_1 = "\n\n## Statistics for r/excel ({} subscribers)\n".format(subs)
    header_1 += "\nCategory               | Post Count \n-----------------------|---------------------"
    line_1 = ("\nUnsolved posts         | {}".format(not_solved_total))
    line_2 = ("\nAbandoned posts        | {}".format(abandoned_total))
    line_3 = ("\nWaiting on OP posts    | {}".format(waitingonop_total))
    line_4 = ("\nSolved posts           | {}".format(solved_total))
    line_5 = ("\nTemplate posts         | {}".format(template_total))
    line_6 = ("\nDiscussion posts       | {}".format(discussioncase_total))
    line_7 = ("\nPaid service posts     | {}".format(paidservice_total))
    line_8 = ("\nProtip posts           | {}".format(protip_total))
    line_9 = ("\n**Total posts**        | **{}**".format(complete_total))
    line_9 += ("\n**Estimated total**    | **{}**".format(estimated_total_posts))
    line_10 = ("\n**Overall percentage** | **{} solved**".format(solved_percentage))

    page_content += header_1 + line_1 + line_2 + line_3 + line_4 + line_5 + line_6 + line_7 + line_8 + line_9 + line_10

    # SUBREDDIT SEARCH #1A
    rt = reddit.subreddit('translation')
    subs = rt.subscribers
    subs = str("{:,}".format(subs))

    oid = []

    for result in rt.new(limit=250):
        if result.created_utc > earliest_time:
            oid.append(result.id)

    complete_total = len(oid)

    header_2 = "\n\n## Statistics for r/translation ({} subscribers)\n".format(subs)
    header_2 += "\n**Total posts:** {}".format(complete_total)
    page_content += header_2

    return page_content


def language_single_ad():
    title_string = "Please help us with {language_name} translation requests on Reddit!"

    ad_string = '''
    {greeting}, redditors of r/{subreddit_name}!

    I'm u/kungming2, a mod over at r/translator. We're working to make our multilingual community *the* universal place on Reddit to go for a translation, no matter what language people may be looking for. 

    **Would anyone be interested in helping translate any future {language_name} language requests on r/translator?** You don't even need to subscribe to our subreddit itself, and most of our requests are pretty simple and don't require advanced knowledge of the language. {frequency}

    **We have a [notifications system](https://www.reddit.com/r/translatorBOT/wiki/ziwen#wiki_notifications) that only sends you a message when a {language_name} request comes in.** Just send a message to our subreddit bot at the link below.

    ### >> [Get {language_name} translation notifications](https://www.reddit.com/message/compose?to=translator-BOT&subject=Subscribe&message=%23%23+Sign+up+for+notifications+about+new+requests+for+your+language%21%0ALANGUAGES%3A+{language_name}) <<

    You can unsubscribe from those messages at any time, and you'll be helping out redditors in need. {thank_you}!

    ---

    ^(Mods, hopefully this post is okay! Apologies if it isn't.)
    '''

    returned_template = '''
    ---
    {title_string}
    ---

    {ad_string}

    '''

    frequency_0 = ""
    frequency_1 = "We usually get a request for the language very occasionally, once every few months or so."
    frequency_2 = "We usually get a request for the language occasionally, once every couple months or so."
    frequency_3 = "We usually get a request for the language a couple times every few months."

    greeting = input("\nPlease enter the beginning greeting phrase, or 'd' for default: ")
    if greeting == "d":
        greeting = "Hello"
    subreddit_name = input("Please enter the subreddit name (no r/): ")
    language_name = input("Please enter the language name: ")
    frequency = input("Please enter the frequency (0, 1, 2, 3): ")
    thank_you = input("Please enter the thank you phrase, or 'd' for default: ")
    if thank_you == "d":
        thank_you = "Thanks"

    if frequency == "0":
        frequency = frequency_0
    if frequency == "1":
        frequency = frequency_1
    elif frequency == "2":
        frequency = frequency_2
    elif frequency == "3":
        frequency = frequency_3

    title_formatted = title_string.format(language_name=language_name)
    ad_formatted = ad_string.format(greeting=greeting, subreddit_name=subreddit_name,
                                    language_name=language_name, frequency=frequency,
                                    thank_you=thank_you)

    return textwrap.dedent(returned_template.format(title_string=title_formatted, ad_string=ad_formatted))


# noinspection PyUnusedLocal
def statistics_calculator(daily_mode=False):

    current_chronos = time.time()
    earliest_time = 2000000000

    specific_month_mode = False

    print('\n+=============================================================================+')
    print('|---------------------Initializing Pingzi sub-routine...----------------------|')
    print('+=============================================================================+')

    '''TIME PLACEHOLDERS'''
    i_year = int(datetime.datetime.fromtimestamp(current_chronos).strftime('%Y'))
    i_month = int(datetime.datetime.fromtimestamp(current_chronos).strftime('%m'))
    current_days = int(calendar.monthrange(i_year, i_month)[1])
    display_month_name = datetime.datetime.fromtimestamp(current_chronos).strftime('%B')

    high_ri = float(2)
    high_ri_language = low_ri_language = ""
    low_ri = float(1)
    lang_entries = 0
    diag_overall_written = False  # By default this is false, the overall statistics page has not been written to

    '''RECORDED CATEGORIES'''
    oid = []
    oflair_css = []
    oflair_text = []
    oover_18 = []
    ois_self = []
    ourl = []
    oimage = []
    ovideo = []
    oaudio = []
    otitle = []
    oxpost = []
    odirection = []
    other_noted_posts = []
    other_tags = []
    specific_multiple_languages = []
    general_multiple_languages = 0

    for result in r.new(limit=1000):  # Changed from the old submissions routine.

        if result.created_utc < earliest_time:
            earliest_time = int(result.created_utc)

        oid.append(result.id)
        oflair_css.append(result.link_flair_css_class)
        odirection.append(title_format(result.title)[8])
        if result.link_flair_text is not None and "(" in result.link_flair_text:
            # try:
            converted_tag = result.link_flair_text.split("(")[0].strip()  # Remove the (Identified) or (Long) tag
            oflair_text.append(converted_tag)
            # except:
            #   converted_tag = result.link_flair_text
            #   oflair_text.append(converted_tag)
        else:
            converted_tag = result.link_flair_text
            oflair_text.append(converted_tag)
        if result.link_flair_css_class in ["translated", "doublecheck", "missing"]:
            # try:
            process_tag = other_translated(converted_tag)  # Returns supported boolean, language code
            # except:
            #    print("> Error converting language tag. Post is at https://redd.it/{}".format(result.id))
            if not process_tag[0]:
                if converter(process_tag[1])[1] == "":
                    other_noted_posts.append(
                        "{} | {} | [Link](https://redd.it/{})".format(str(converter(process_tag[1])[1]),
                                                                      process_tag[1],
                                                                      result.id))
                    other_tags.append(process_tag[1])
                else:  # This is a non CSS supported language.
                    other_tags.append(process_tag[1])  # Should be a regular language
        elif result.link_flair_css_class == "generic":
            if converted_tag is not None:
                converted_tag = converter(converted_tag)
                other_tags.append(converted_tag[0])
        elif result.link_flair_css_class == "multiple" or result.link_flair_css_class == "app":
            if "[" in result.link_flair_text:  # This is a defined multiple. 
                multiple_languages = result.link_flair_text
                multiple_languages = multiple_languages.split("[", 1)[1]  # Get the tags (delete stuff from front)
                multiple_languages = multiple_languages.split("]", 1)[0]  # Get the tags (delete stuff from the back)
                multiple_languages = multiple_languages.split(", ")
                for language in multiple_languages:  # It's now a list. attach the individual languages.
                    # We don't have code to process statuses yet.
                    # So here we just get the letters.
                    language = " ".join(re.findall("[a-zA-Z]+", language))
                    specific_multiple_languages.append(language.lower())
            else:  # This is a general ALL multiple request
                general_multiple_languages += 1
        if result.over_18:
            oover_18.append(result.over_18)
        if result.is_self:
            ois_self.append(result.is_self)
        ourl.append(result.url)
        otitle.append(result.title)
        if result.author is not None:
            if result.author.name == 'translator-BOT' and result.link_flair_css_class not in ["meta", "community"]:
                # Search for cross posts
                oxpost.append(result.id)

    for url in ourl:
        for keyword in VIDEO_KEYWORDS:
            if keyword in url:
                ovideo.append(url)
        for keyword in AUDIO_KEYWORDS:
            if keyword in url:
                oaudio.append(url)
        for keyword in IMAGE_KEYWORDS:
            if keyword in url:
                oimage.append(url)
            elif ".jpg" in url.lower()[-4:] or ".png" in url.lower()[-4:]:
                oimage.append(url)
    oimage = list(set(oimage))  # remove duplicates

    # complete_total is the total amount of ALL posts.
    complete_total = len(oid)

    # Process the "other" post categories. 
    other_total = 0
    for css in ['meta', 'community', 'art', 'zxx', 'unknown']:
        other_total += oflair_css.count(css)

    # Get the number of multiple posts.
    multiple_total = oflair_css.count("multiple")
    multiple_total += oflair_css.count("app")

    # True Total is the number of posts that can be marked as translated.
    true_total = complete_total - other_total - multiple_total

    # States
    trans_total = oflair_css.count("translated")
    review_total = oflair_css.count("doublecheck")
    missing_total = oflair_css.count("missing")
    in_progress_total = oflair_css.count("inprogress")
    trans_not_total = complete_total - trans_total - review_total - other_total - missing_total - in_progress_total

    # Calculate the final percentage
    translated_percentage = str("{0:.0f}%".format((trans_total + review_total) / true_total * 100))

    text_posts_total = len(ois_self)
    nsfw_total = len(oover_18)
    video_total = len(ovideo)
    audio_total = len(oaudio)
    image_total = len(oimage)
    xpost_total = len(oxpost)

    header_1 = "\n## Overall Statistics\nCategory               | Post Count \n" \
               "-----------------------|---------------------"
    # General statistics for use in the monthly post itself and the "overall statistics" page
    line_1 = "\n*Single-Language*      | "
    line_1 += ("\nUntranslated requests  | {}".format(trans_not_total))
    line_2 = "\nRequests missing assets| {}".format(missing_total)
    line_2 += "\nRequests in progress   | {}".format(in_progress_total)
    line_2 += ("\nRequests needing review| {}".format(review_total))
    line_3 = ("\nTranslated requests    | {}".format(trans_total))
    line_3 += ("\nOther requests         | {}".format(other_total))
    line_3 += "\n                       | "
    line_4 = "\n*Multiple-Language*    | {}".format(multiple_total)
    line_4 += "\n-----------------------|--------------------- "
    line_5 = ("\n**Total posts**        | **{}**".format(complete_total))
    line_6 = ("\n**Overall percentage** | **{} translated**".format(translated_percentage))
    line_7 = "\n-----------------------|--------------------- "
    line_8 = ("\n*Link posts*           | *{} ({}%)*".format(true_total - text_posts_total, round(
        ((true_total - text_posts_total) / true_total) * 100), 2))
    line_9 = (
        "\n*Text (self) posts*    | *{} ({}%)*".format(text_posts_total,
                                                       round((text_posts_total / true_total) * 100), 2))
    line_9 += ("\n*Bot crossposts*       | *{}*".format(xpost_total))
    line_10 = ("\n*Image posts*          | *{}*".format(image_total))
    line_11 = ("\n*Video posts*          | *{}*".format(video_total))
    line_12 = ("\n*Audio posts*          | *{}*".format(audio_total))
    line_13 = ("\n*NSFW posts*           | *{}*".format(nsfw_total))

    # Let's try to estimate here.
    earliest_time_formatted = datetime.datetime.fromtimestamp(earliest_time).strftime('%Y-%m-%d [%H:%M:%S]')
    current_chronos_formatted = datetime.datetime.fromtimestamp(current_chronos).strftime('%Y-%m-%d [%H:%M:%S]')
    date_range = "\n\n## Data from {} to {}".format(earliest_time_formatted, current_chronos_formatted)

    user_submitted_total = complete_total - oflair_css.count("meta") - oflair_css.count("community")
    # Convert into the days for the present month.
    hours_since = round((current_chronos - earliest_time) / 3600, 2)
    estimated_month_total = int((user_submitted_total / hours_since) * current_days * 24)

    line_14 = ("\n**Est. month total**   | **{}**".format(estimated_month_total))
    page_content = (header_1 + line_1 + line_2 + line_3 + line_4 + line_5 + line_6 + line_14 + line_7 +
                    line_8 + line_9 + line_10 + line_11 + line_12 + line_13)

    print(page_content)  # Print the abbreviated data we have now.

    month_page_content_noimg = "# [" + str(display_month_name) + " " + str(i_year) + \
                               "](https://www.reddit.com/r/translator/wiki/" + str(i_month) + "_" + str(i_year) + \
                               ") \n*[Statistics](https://www.reddit.com/r/translator/wiki/statistics)" \
                               " for r/translator provided " \
                               "by [Wenyuan](https://www.reddit.com/r/translatorBOT/wiki/wenyuan)* \n \n" + page_content
    # This one omits the image (for a post, not the wiki)

    month_lang_page_content = []
    month_family_page_content = []
    function_page_content = []
    plot_names = []  # For the plot names
    plot_nums = []  # For the plot numbers
    plot_colors = []  # For the plot colors
    plot_family = []
    plot_family_nums = []
    plot_family_colors = []

    other_tags_nodup = list(set(other_tags))  # Remove duplicates
    other_tags_nodup.sort()
    # other_tags_nodup.remove("multiple")

    language_list = [
        ["Afrikaans", "af", "Indo-European", "7", "rgb(15, 46, 91)", True],
        ["Albanian", "sq", "Indo-European", "5.4", "rgb(53, 146, 249)", True],
        ["Amharic", "am", "Afro-Asiatic", "37", "rgb(227, 158, 68)", True],
        ["Ancient Egyptian", "egy", "Afro-Asiatic", "0", "rgb(237, 171, 55)", True],
        ["Ancient Greek", "grc", "Indo-European", "0", "rgb(91, 145, 204)", True],
        ["Anglo-Saxon", "ang", "Indo-European", "0", "rgb(15, 46, 91)", True],
        ["Arabic", "ar", "Afro-Asiatic", "420", "rgb(227, 159, 67)", True],
        ["Aramaic", "arc", "Afro-Asiatic", "0", "rgb(227, 159, 67)", True],
        ["Armenian", "hy", "Indo-European", "5.4", "rgb(28, 74, 122)", True],
        ["Basque", "eu", "Language Isolate", "0.72", "rgb(188, 153, 123)", True],
        ["Balinese", "ban", "Austronesian", "3.3", "rgb(129, 49, 131)", True],
        ["Belarusian", "be", "Indo-European", "3.2", "rgb(82, 145, 193)", True],
        ["Bengali", "bn", "Indo-European", "210", "rgb(44, 73, 127)", True],
        ["Bosnian", "bs", "Indo-European", "3", "rgb(82, 145, 193)", True],
        ["Bulgarian", "bg", "Indo-European", "9", "rgb(82, 145, 193)", True],
        ["Burmese", "my", "Sino-Tibetan", "33", "rgb(27, 58, 25)", True],
        ["Cantonese", "yue", "Sino-Tibetan", "80", "rgb(120, 173, 63)", True],
        ["Catalan", "ca", "Indo-European", "4", "rgb(40, 86, 165)", True],
        ["Cebuano", "ceb", "Austronesian", "21", "rgb(161, 83, 159)", True],
        ["Cherokee", "chr", "Iroquoian", ".0123", "rgb(234, 221, 105)", True],
        ["Chinese", "zh", "Sino-Tibetan", "1120", "rgb(120, 173, 63)", True],
        ["Coptic", "cop", "Afro-Asiatic", "0", "rgb(227, 159, 67)", True],
        ["Corsican", "co", "Indo-European", ".2", "rgb(40, 86, 165)", True],
        ["Croatian", "hr", "Indo-European", "5.6", "rgb(82, 145, 193)", True],
        ["Czech", "cs", "Indo-European", "10.6", "rgb(82, 145, 193)", True],
        ["Danish", "da", "Indo-European", "5.5", "rgb(15, 46, 91)", True],
        ["Dutch", "nl", "Indo-European", "23", "rgb(15, 46, 91)", True],
        ["Esperanto", "eo", "Constructed", "2.01", "rgb(163, 196, 164)", True],
        ["Estonian", "et", "Uralic", "1.1", "rgb(63, 50, 34)", True],
        ["Finnish", "fi", "Uralic", "5.4", "rgb(63, 50, 34)", True],
        ["French", "fr", "Indo-European", "148", "rgb(40, 86, 165)", True],
        ["German", "de", "Indo-European", "95", "rgb(15, 46, 91)", True],
        ["Georgian", "ka", "Kartvelian", "4.3", "rgb(151, 204, 210)", True],
        ["Greek", "el", "Indo-European", "13", "rgb(91, 145, 204)", True],
        ["Gujarati", "gu", "Indo-European", "49", "rgb(44, 73, 127)", True],
        ["Haitian Creole", "ht", "Creole", "10", "rgb(163, 179, 198)", True],
        ["Hawaiian", "haw", "Austronesian", ".026", "rgb(161, 83, 159)", True],
        ["Hebrew", "he", "Afro-Asiatic", "9", "rgb(227, 159, 67)", True],
        ["Hindi", "hi", "Indo-European", "260", "rgb(44, 73, 127)", True],
        ["Hungarian", "hu", "Uralic", "13", "rgb(56, 38, 16)", True],
        ["Icelandic", "is", "Indo-European", ".33", "rgb(15, 46, 91)", True],
        ["Indonesian", "id", "Austronesian", "43", "rgb(129, 49, 131)", True],
        ["Inuktitut", "iu", "Eskimo-Aleut", ".034", "rgb(234, 221, 105)", True],
        ["Irish", "ga", "Indo-European", ".14", "rgb(51, 132, 192)", True],
        ["Italian", "it", "Indo-European", "65", "rgb(40, 86, 165)", True],
        ["Japanese", "ja", "Japonic", "120", "rgb(237, 70, 47)", True],
        ["Kazakh", "kk", "Turkic", "11", "rgb(157, 143, 89)", True],
        ["Khmer", "km", "Austroasiatic", "16", "rgb(188, 167, 10)", True],
        ["Korean", "ko", "Language Isolate", "75", "rgb(188, 153, 123)", True],
        ["Kurdish", "ku", "Indo-European", "25", "rgb(44, 73, 127)", True],
        ["Lao", "lo", "Tai-Kadai", "3.87", "rgb(178, 88, 143)", True],
        ["Latin", "la", "Indo-European", "0", "rgb(40, 86, 165)", True],
        ["Latvian", "lv", "Indo-European", "1.75", "rgb(82, 145, 193)", True],
        ["Lithuanian", "lt", "Indo-European", "3", "rgb(82, 145, 193)", True],
        ["Macedonian", "mk", "Indo-European", "2", "rgb(82, 145, 193)", True],
        ["Malagasy", "mg", "Austronesian", "18", "rgb(161, 83, 159)", True],
        ["Malay", "ms", "Austronesian", "19", "rgb(129, 49, 131)", True],
        ["Malayalam", "ml", "Dravidian", "38", "rgb(161, 144, 196)", True],
        ["Maltese", "mt", "Afro-Asiatic", ".52", "rgb(227, 159, 67)", True],
        ["Marathi", "mr", "Indo-European", "73", "rgb(44, 73, 127)", True],
        ["Mongolian", "mn", "Mongolic", "5.2", "rgb(146, 104, 40)", True],
        ["Navajo", "nv", "Na-Dene", ".169", "rgb(234, 221, 105)", True],
        ["Nepali", "ne", "Indo-European", "17", "rgb(44, 73, 127)", True],
        ["Norse", "non", "Indo-European", "0", "rgb(15, 46, 91)", True],
        ["Norwegian", "no", "Indo-European", "5", "rgb(15, 46, 91)", True],
        ["Old Church Slavonic", "cu", "Indo-European", "0", "rgb(82, 145, 193)", True],
        ["Pashto", "ps", "Indo-European", "50", "rgb(44, 73, 127)", True],
        ["Persian", "fa", "Indo-European", "60", "rgb(44, 73, 127)", True],
        ["Polish", "pl", "Indo-European", "55", "rgb(82, 145, 193)", True],
        ["Portuguese", "pt", "Indo-European", "215", "rgb(40, 86, 165)", True],
        ["Punjabi", "pa", "Indo-European", "100", "rgb(44, 73, 127)", True],
        ["Quechua", "qu", "Quechuan", "9", "rgb(234, 221, 105)", True],
        ["Romanian", "ro", "Indo-European", "24", "rgb(40, 86, 165)", True],
        ["Russian", "ru", "Indo-European", "150", "rgb(82, 145, 193)", True],
        ["Sanskrit", "sa", "Indo-European", "0", "rgb(44, 73, 127)", True],
        ["Sardinian", "sc", "Indo-European", "1", "rgb(40, 86, 165)", True],
        ["Scottish Gaelic", "gd", "Indo-European", ".06", "rgb(51, 132, 192)", True],
        ["Serbian", "sr", "Indo-European", "8.7", "rgb(82, 145, 193)", True],
        ["Sinhalese", "si", "Indo-European", "16", "rgb(44, 73, 127)", True],
        ["Slovak", "sk", "Indo-European", "5.2", "rgb(82, 145, 193)", True],
        ["Slovene", "sl", "Indo-European", "2.5", "rgb(82, 145, 193)", True],
        ["Somali", "so", "Afro-Asiatic", "17", "rgb(202, 141, 72)", True],
        ["Spanish", "es", "Indo-European", "470", "rgb(40, 86, 165)", True],
        ["Swahili", "sw", "Niger-Congo", "15", "rgb(57, 137, 132)", True],
        ["Swedish", "sv", "Indo-European", "9.2", "rgb(15, 46, 91)", True],
        ["Tagalog", "tl", "Austronesian", "28", "rgb(161, 83, 159)", True],
        ["Tamil", "ta", "Dravidian", "70", "rgb(161, 144, 196)", True],
        ["Telugu", "te", "Dravidian", "75", "rgb(161, 144, 196)", True],
        ["Thai", "th", "Tai-Kadai", "40", "rgb(178, 88, 143)", True],
        ["Tibetan", "bo", "Sino-Tibetan", "1.2", "rgb(27, 58, 25)", True],
        ["Turkish", "tr", "Turkic", "88", "rgb(134, 126, 68)", True],
        ["Ukrainian", "uk", "Indo-European", "30", "rgb(82, 145, 193)", True],
        ["Urdu", "ur", "Indo-European", "65", "rgb(44, 73, 127)", True],
        ["Uzbek", "uz", "Turkic", "27", "rgb(132, 123, 72)", True],
        ["Vietnamese", "vi", "Austroasiatic", "75", "rgb(204, 194, 68)", True],
        ["Welsh", "cy", "Indo-European", ".7", "rgb(51, 132, 192)", True],
        ["Xhosa", "xh", "Niger-Congo", "19", "rgb(57, 137, 132)", True],
        ["Yiddish", "yi", "Indo-European", "1.5", "rgb(15, 46, 91)", True],
        ["Yoruba", "yo", "Niger-Congo", "20", "rgb(57, 137, 132)", True],
        ["Zulu", "zu", "Niger-Congo", "12", "rgb(57, 137, 132)", True]
    ]

    lf_list = [  # Name, ISO 639-5 code, initial count, color, link
        ["Afro-Asiatic", "afa", 0, "rgb(227, 159, 67)",
         "[Afro-Asiatic](https://en.wikipedia.org/wiki/Afroasiatic_languages)"],
        ["Algonquian", "alg", 0, "rgb(234, 221, 105)",
         "[Algonquian](https://en.wikipedia.org/wiki/Algonquian_languages)"],
        ["Austroasiatic", "aav", 0, "rgb(188, 167, 10)",
         "[Austroasiatic](https://en.wikipedia.org/wiki/Austroasiatic_languages)"],
        ["Austronesian", "map", 0, "rgb(129, 49, 131)",
         "[Austronesian](https://en.wikipedia.org/wiki/Austronesian_languages)"],
        ["Aymaran", "aym", 0, "rgb(234, 221, 105)", "[Aymaran](https://en.wikipedia.org/wiki/Aymaran_languages)"],
        ["Constructed", "con", 0, "rgb(0, 0, 0)", "[Constructed](https://en.wikipedia.org/wiki/Constructed_language)"],
        ["Creole", "crp", 0, "rgb(163, 179, 198)", "[Creole/Pidgin](https://en.wikipedia.org/wiki/Creole_language)"],
        ["Dravidian", "dra", 0, "rgb(161, 144, 196)", "[Dravidian](https://en.wikipedia.org/wiki/Dravidian_languages)"],
        ["Eskimo-Aleut", "esx", 0, "rgb(234, 221, 105)",
         "[Eskimo-Aleut](https://en.wikipedia.org/wiki/Eskimo%E2%80%93Aleut_languages)"],
        ["Hmong-Mien", "hmx", 0, "rgb(182, 214, 111)",
         "[Hmong-Mien](https://en.wikipedia.org/wiki/Hmong%E2%80%93Mien_languages)"],
        ["Indo-European", "ine", 0, "rgb(15, 46, 91)",
         "[Indo-European](https://en.wikipedia.org/wiki/Indo-European_languages)"],
        ["Iroquoian", "iro", 0, "rgb(188, 153, 123)", "[Iroquoian](https://en.wikipedia.org/wiki/Iroquoian_languages)"],
        ["Japonic", "jpx", 0, "rgb(237, 70, 47)", "[Japonic](https://en.wikipedia.org/wiki/Japonic_languages)"],
        ["Kartvelian", "cau", 0, "rgb(151, 204, 210)",
         "[Kartvelian](https://en.wikipedia.org/wiki/Kartvelian_languages)"],
        ["Language Isolate", "lni", 0, "rgb(188, 153, 123)",
         "[Language Isolate](https://en.wikipedia.org/wiki/Language_isolate)"],
        ["Mayan", "myn", 0, "rgb(188, 153, 123)", "[Mayan](https://en.wikipedia.org/wiki/Mayan_languages)"],
        ["Muskogean", "mus", 0, "rgb(188, 153, 123)", "[Muskogean](https://en.wikipedia.org/wiki/Muskogean_languages)"],
        ["Mongolic", "xgn", 0, "rgb(146, 104, 40)", "[Mongolic](https://en.wikipedia.org/wiki/Mongolic_languages)"],
        ["Na-Dene", "xnd", 0, "rgb(234, 221, 105)", "[Na-Dene](https://en.wikipedia.org/wiki/Na-Dene_languages)"],
        ["Niger-Congo", "nic", 0, "rgb(57, 137, 132)",
         "[Niger-Congo](https://en.wikipedia.org/wiki/Niger%E2%80%93Congo_languages)"],
        ["Nilo-Saharan", "ssa", 0, "rgb(57, 137, 132)",
         "[Nilo-Saharan](https://en.wikipedia.org/wiki/Nilo-Saharan_languages)"],
        ["Northeast Caucasian", "ccn", 0, "rgb(245, 151, 142)",
         "[Northeast Caucasian](https://en.wikipedia.org/wiki/Northeast_Caucasian_languages)"],
        ["Northwest Caucasian", "ccw", 0, "rgb(245, 151, 142)",
         "[Northwest Caucasian](https://en.wikipedia.org/wiki/Northwest_Caucasian_languages)"],
        ["Quechuan", "qwe", 0, "rgb(234, 221, 105)", "[Quechuan](https://en.wikipedia.org/wiki/Quechuan_languages)"],
        ["Sign language", "sgn", 0, "rgb(0, 0, 0)", "[Sign languages](https://en.wikipedia.org/wiki/Sign_languages)"],
        ["Siouan-Catawban", "sio", 0, "rgb(234, 221, 105)",
         "[Siouan-Catawban](https://en.wikipedia.org/wiki/Siouan_languages)"],
        ["Sino-Tibetan", "sit", 0, "rgb(120, 173, 63)",
         "[Sino-Tibetan](https://en.wikipedia.org/wiki/Sino-Tibetan_languages)"],
        ["Tai-Kadai", "tai", 0, "rgb(178, 88, 143)",
         "[Tai-Kadai](https://en.wikipedia.org/wiki/Tai%E2%80%93Kadai_languages)"],
        ["Trans-New Guinea", "ngf", 0, "rgb(0, 0, 0)",
         "[Trans-New Guinea](https://en.wikipedia.org/wiki/Trans%E2%80%93New_Guinea_languages)"],
        ["Tungusic", "tuw", 0, "rgb(146, 104, 40)", "[Tungusic](https://en.wikipedia.org/wiki/Tungusic_languages)"],
        ["Tupian", "tup", 0, "rgb(234, 221, 105)", "[Tupian](https://en.wikipedia.org/wiki/Tupian_languages)"],
        ["Turkic", "trk", 0, "rgb(134, 126, 68)", "[Turkic](https://en.wikipedia.org/wiki/Turkic_languages)"],
        ["Uralic", "urj", 0, "rgb(56, 38, 16)", "[Uralic](https://en.wikipedia.org/wiki/Uralic_languages)"],
        ["Uto-Aztecan", "azc", 0, "rgb(188, 153, 123)",
         "[Uto-Aztecan](https://en.wikipedia.org/wiki/Uto-Aztecan_languages)"]
    ]

    for tag in other_tags_nodup:  # These are language codes. We're integrating the other languages into supported ones.
        # print(tag)
        if tag != "?" and tag != "--" and tag is not None and tag != "":
            # try:

            sql_result = wenyuan_cache_fetcher(tag)

            if sql_result is not None:  # We could find a cached value for this language
                reference_info = sql_result
            else:  # We don't have a cached value. Let's run it.
                run_reference(tag)
                reference_info = wenyuan_cache_fetcher(tag)

            if reference_info is not None:  # We have data for it.
                lang_fam = reference_info[0]  # Get the language family.
                rep_index = float(reference_info[1] / 1000000)  # Get the REP index from the population.
            else:  # No data for it... Maybe Ethnologue is blocked? Just give it N/A
                lang_fam = "N/A"
                rep_index = "N/A"

            other_entry = [converter(tag)[1], tag, lang_fam, rep_index, "rgb(153, 153, 153)", False]
            language_list.append(other_entry)
            # print(other_entry)

    language_list.sort(key=lambda z: z[0])  # Sort our language list by alphabetically by name

    # Process the data for defined multiple languages.
    specific_multiple_languages_dedupe = list(set(specific_multiple_languages))  # Dedupe, only the ones we want.
    specific_multiple_languages_dedupe = sorted(specific_multiple_languages_dedupe, key=str.lower)  # Alphabetize
    specific_multiple_languages_dict = {}

    header_multiple = "\n\n### Multiple-Language/App Requests\n\n"
    # Here we add back all the ALL multiple language requests
    specific_multiple_languages_format = header_multiple + "* For any language:       {}".format(str(general_multiple_languages))
    specific_multiple_languages_format += "\n* For defined languages: {}".format(str(multiple_total - general_multiple_languages))
    specific_multiple_languages_format += "\n* *The count for defined 'Multiple' requests are listed under* #M *in the table above.*"

    for language in specific_multiple_languages_dedupe:  # We are trying to build an overview of multiple requests
        times_count = specific_multiple_languages.count(language)
        language_name = converter(language)[1]
        if times_count >= 1 and len(language_name) > 0:  # There was more than one here.
            specific_multiple_languages_dict[language_name] = str(times_count)
    # pp.pprint(specific_multiple_languages_dict)
    '''
    mul_sorted = sorted(specific_multiple_languages_dict.keys(), key=lambda x: x.lower())
    for item in mul_sorted:  # Now we recreate the list with language names instead of codes, add it to the output
        item_format = item.ljust(13)
        specific_multiple_languages_format.append("{} | {}".format(item_format, specific_multiple_languages_dict[item]))
    '''

    print("\n\n### Single-Language Requests")  # Header
    print("Language                   | Language Family     | Total Requests | Percent of All Requests"
          " | Untranslated Requests | Translation Percentage | #M | RI     ")
    print("---------------------------|---------------------|----------------|-------------------------"
          "|-----------------------|------------------------|----|-------")

    for item in language_list:
        language_name = item[0]  # Take the language name
        language_code = item[1]  # Take the language code
        language_family = item[2]  # This is the language family
        language_share = item[3]  # The number of native speakers (in millions) - 0 means it's a dead language
        language_color = item[4]  # Color shading for Plot.ly
        lang_support = item[5]  # Is this a supported language on the subreddit?

        base_all_link = '/r/translator/search?q=flair:"{}"+OR+flair:"[{}]"&sort=new&restrict_sr=on'
        base_all_link = base_all_link.format(language_name, language_code.upper())
        # The search URL for all language entries for a given language
        base_all_link = base_all_link.replace(" ", "+")  # Replace spaces with pluses

        underscore_name = language_name
        if len(language_name) == 0:  # Blank language for some reason
            continue

        for character in [" ", "-"]:  # We want to replace these characters that don't play well with the wiki URL.
            if character in language_name:
                underscore_name = underscore_name.replace(character, "_")
                base_all_link = base_all_link.replace(character, "_")  

        untranslated_total = oflair_css.count(language_code)
        if untranslated_total == 0:
            untranslated_total += oflair_text.count(language_name)

        translated_code_total = oflair_text.count("Translated [" + language_code.upper() + "]")
        translated_code_total += oflair_text.count("Needs Review [" + language_code.upper() + "]")

        if int(untranslated_total + translated_code_total) == 0:  # If there are 100% no results...
            continue

        total = untranslated_total + translated_code_total
        lang_entries += 1

        t_wiki_link = "https://www.reddit.com/r/translator/wiki/{}".format(underscore_name)  # r/translator wiki link
        wk_link = "https://en.wikipedia.org/wiki/ISO_639:{}".format(language_code)  # Wikipedia link

        if language_name in specific_multiple_languages_dict:  # Get the number of multiple entries.
            multiple_count = specific_multiple_languages_dict[language_name]
            # Remove this from the entry
            del specific_multiple_languages_dict[language_name]
        else:
            multiple_count = 0

        if lang_support is False and specific_month_mode is True:
            # Check to see if this wiki page exists for non CSS-supported language. We can create it.
            try:  # Test for a valid wiki page.
                new_lang_page = len(r.wiki[underscore_name.lower()].content_md)
                new_lang_page = True
                # new_lang_page = r.wiki[underscore_name.lower()]
                # new_lang_page = len(new_lang_page.content_md)
            except (prawcore.exceptions.NotFound, prawcore.exceptions.Redirect):  # Create it otherwise.
                new_lang_page = False

            if new_lang_page is not True:
                r.wiki.create(name=underscore_name.lower(),
                              content=WY_NEW_HEADER.format(language_name=language_name, language_family=language_family),
                              reason="Creating a new statistics wiki page for {}".format(language_name))

        lang_short_percent = round(((total / true_total) * 100), 2)
        rep_index = "---"
        translated_ratio = "0"

        if translated_code_total == 0 and untranslated_total == 0:
            # total in this case is still the old title search, should be transitioned in the future
            continue
        if language_share != "N/A":
            if total == 0 and untranslated_total >= 1:
                world_index = float(language_share) / WORLD_POP
                translated_ratio = "0"
                if world_index == 0:
                    rep_index = "---"
                else:
                    rep_index = str(round(((untranslated_total / true_total) / world_index), 2))
            if total >= 1 and language_share != "0":
                world_index = float(language_share) / WORLD_POP
                if world_index == 0:
                    rep_index = "---"
                else:
                    rep_index = str(round(((total / true_total) / world_index), 2))
                    translated_ratio = int(round(100 - ((untranslated_total / total) * 100), 2))
            if total >= 1 and language_share == "0":
                translated_ratio = int(round(100 - ((untranslated_total / total) * 100), 2))
        else:
            rep_index = "---"
            if total >= 1:
                translated_ratio = int(round(100 - ((untranslated_total / total) * 100), 2))
            else:
                translated_ratio = "0"

        if rep_index != "---" and float(rep_index) <= low_ri and language_name != 'English':
            low_ri = float(rep_index)
            low_ri_language = language_name
        if rep_index != "---" and float(rep_index) >= high_ri:
            high_ri = float(rep_index)
            high_ri_language = language_name

        for family in lf_list:
            if language_family == family[0]:
                family[2] += total
                continue

        # Code here to format the entry lines properly
        # language_entry is the format for the WIKIPAGE
        # month_lang_entry is the format for the overall and monthly data page
        # display_entry is the format that appears in the terminal.

        # Format for the wiki page
        language_entry_format = "{} | {} | [{}]({}) | {}% | {} | {}% | {} | ---"
        language_entry = language_entry_format.format(i_month, i_year, total, base_all_link, lang_short_percent,
                                                      untranslated_total, translated_ratio, rep_index)

        month_lang_entry_format = "[{}]({}) | {} | [{}]({}) | {}% | {} | {}% | {!s} | {} | [WP]({})"
        month_lang_entry = month_lang_entry_format.format(language_name, t_wiki_link, language_family, total,
                                                          base_all_link, lang_short_percent, untranslated_total,
                                                          translated_ratio, multiple_count, rep_index, wk_link)

        display_entry_format = "{} | {} | {} | {}% | {} | {}% | {} | {}"
        display_entry = display_entry_format.format(language_name.ljust(26), language_family.ljust(19),
                                                    str(total).ljust(14), str(lang_short_percent).ljust(22),
                                                    str(untranslated_total).ljust(21), str(translated_ratio).ljust(21),
                                                    str(multiple_count).ljust(2), rep_index)

        print(display_entry)  # Display the language row in the terminal

        if specific_month_mode:  # If we are recording a specific month, write to wiki. 
            # underscore_name = underscore_name.replace(" ", "_")
            page_content = r.wiki[underscore_name.lower()]  # Fetches the wiki page for the language
            # page_content = r.get_wiki_page(SUBREDDIT,underscore_name)
            month_year_chunk = "{} | {} | ".format(i_month, i_year)
            try:
                if month_year_chunk not in str(page_content.content_md):
                    # Checks to see if there's an entry for the month
                    page_content_new = str(page_content.content_md) + '\n' + language_entry
                    # Adds this month's entry to the data from the wikipage
                    page_content.edit(content=page_content_new,
                                      reason='Updating with data from {}'.format(month_year_chunk))
            except prawcore.exceptions.NotFound:  # Problem with the WikiPage
                print("ISSUE: " + underscore_name)
        month_lang_page_content.append(month_lang_entry)
        # Add the language row to the overall data.

        # Plot.ly Code
        plot_names.append(language_name)
        plot_nums.append(total)
        plot_colors.append(language_color)

    ri_included_text = '''
    
    The most over-represented language during this {time_period} was **{high_language}** with an RI of **{high_ri}**.
    
    The most under-represented language during this {time_period} was **{low_language}** with an RI of **{low_ri}**.
    '''

    if specific_month_mode:
        ri_text = textwrap.dedent(ri_included_text.format(time_period="month", high_language=high_ri_language, high_ri=high_ri,
                                  low_language=low_ri_language, low_ri=low_ri))
        print(ri_text)
    else:
        ri_text = textwrap.dedent(ri_included_text.format(time_period="time period", high_language=high_ri_language, high_ri=high_ri,
                                  low_language=low_ri_language, low_ri=low_ri))
        print(ri_text)

    # Insert direction table
    direction_tags = ['english_to', 'english_from', 'english_none']
    direction_header = "\n\n###### Translation Directions\n\n* **To English**:       %s (%s)\n"
    direction_header += "* **From English**:     %s (%s)\n* **Both Non-English**: %s (%s)"
    direction_counter = []
    for tag in direction_tags:
        direction_count = odirection.count(tag)
        if direction_count > 0:
            direction_percentage = round((direction_count / complete_total) * 100, 2)
            direction_percentage = str(direction_percentage) + "%"
            direction_counter.append(direction_count)
            direction_counter.append(direction_percentage)
    direction_header = direction_header % tuple(direction_counter)
    print(direction_header)

    # Plot.ly additions
    plot_names.append("Other")
    plot_nums.append(len(other_tags_nodup))
    plot_colors.append("rgb(153, 153, 153)")

    header_1a = "\n\n### Language Families   \nLanguage Family      | Total Requests | Percent of All Requests" \
                "\n---------------------|----------------|------------------------"
    print(header_1a)

    # Process the data for language families.
    for family in lf_list:
        if family[2] != 0:
            month_family_entry = str(family[4] + " | " + str(family[2]) + " | ")
            month_family_entry += str(round(((family[2] / true_total) * 100), 2)) + "%"
            month_family_page_content.append(month_family_entry)
            display_family_entry = family[0].ljust(20) + " | " + str(family[2]).ljust(14)
            display_family_entry += " | " + str(round(((family[2] / true_total) * 100), 2)) + "%"
            print(display_family_entry)
            plot_family.append(family[0])
            plot_family_nums.append(family[2])
            plot_family_colors.append(family[3])

    month_family_page_content = ('\n'.join(map(str, month_family_page_content)))

    # Process Other Data here
    other_flair_list = ["app", 'multiple', "community", "art", "meta", "zxx", "unknown"]

    header_3 = "\n\n#### Other Single-Language Requests/Posts\n\nCategory | Total Posts  \n------------|---------------\n"
    print(header_3)

    for flair in other_flair_list:
        total = oflair_css.count(flair)
        if total == 0:
            continue

        if flair in SUPPORTED_CODES:
            flair_name = SUPPORTED_LANGUAGES[SUPPORTED_CODES.index(flair)]  # Get the proper name of the flair.
        else:
            flair_name = flair.title()

        if flair in ["app", "unknown", "multiple", "art", 'zxx']:
            if specific_month_mode:  # If it's time to edit the pages...
                if len(flair) == 3:
                    page_content = r.wiki[flair_name.lower()]  # Fetches the wiki page for the language
                else:
                    page_content = r.wiki[flair.lower()]
                month_year_chunk = "{} | {} | ".format(i_month, i_year)
                if month_year_chunk not in str(page_content.content_md):
                    lang_short_percent = round((total / complete_total) * 100, 2)
                    language_entry = str("{} | {} | {} | {}%".format(i_month, i_year, total, lang_short_percent))
                    # Format for the wiki page
                    page_content_new = str(page_content.content_md) + '\n' + language_entry
                    # Adds this month's entry to the data from the wikipage
                    page_content.edit(content=page_content_new,
                                      reason='Updating page with latest data from ' + month_year_chunk)
                    # This edits the wikipage for that language

        if flair in ["art", "zxx", "unknown"]:
            # These are codes that don't have the same css and name
            if flair != "unknown":
                other_tag_num = "[{}]".format(flair.upper())
            else:
                other_tag_num = "[?]"

            oflair_text_other = [x for x in oflair_text if x is not None]
            for flairtext in oflair_text_other:
                if oflair_text is not None and other_tag_num in flairtext:
                    total += 1

        search_link = 'https://www.reddit.com/r/translator/search?q=flair:%22{}%22+OR+flair:%22%5B{}%5D%22&sort=new&restrict_sr=on'
        search_link = search_link.format(flair_name, converter(flair_name)[0].upper())

        if flair not in ['app', 'multiple']:
            function_page_entry = str("{} | [{}]({}) ".format(flair_name.ljust(11), str(total), search_link))
            print(function_page_entry)
            function_page_content.append(function_page_entry)
        # else:
        # function_page_entry = str("{} | {} ".format(flair_name.ljust(11), str(total).ljust(11)))
        # Plot.ly additions
        plot_names.append(flair.title())
        plot_nums.append(total)
        plot_colors.append("rgb(153, 153, 153)")

    # Add code to handle a situation where there are no other Multiple additional requests
    if len(specific_multiple_languages_dict.items()) != 0:  # There are actually other Multiple languages not on above
        specific_multiple_languages_format += "\n\n###### Additional Requests\n"
        for key, value in sorted(specific_multiple_languages_dict.items()):
            if len(value) > 0 and len(key) != 0:  # Make sure there's actually a value here.
                specific_multiple_languages_format += "\n* {}".format(key)

    print(specific_multiple_languages_format)

    overall_notify_data = "\n\n###### Notifications Database\n"
    overall_notify_data += notify_list_statistics_calculator()[0]  # Gather data for notifications database
    print(overall_notify_data)

    formatted_content = ('\n'.join(map(str, month_lang_page_content)))
    formatted_content += ri_text + direction_header
    function_page_content = ('\n'.join(map(str, function_page_content)))
    function_page_content = overall_notify_data + header_3 + function_page_content
    function_page_content += specific_multiple_languages_format

    header_2 = "\n\n### Single-Language Requests\nLanguage | Language Family | Total Requests | Percent of All Requests " \
               "| Untranslated Requests | Translation Percentage | #M | RI | Wikipedia Link" + '\n' + "------|------|" \
               "-------|-----|---|-----------------------|---------|------|-------- \n"

    other_noted_posts = list(set(other_noted_posts))
    other_noted_posts.sort()

    if len(other_noted_posts) != 0:
        print("\n\nName | Code | Links\n-----|------|-------")
        # Here we print some posts of interests that we want to fix. Hopefully there won't be too many of them.
        for post in other_noted_posts:
            if " |" in post[0:2]:
                print(post)

    elapsed_duration = (time.time() - RECORD_DURATION)  # How long did the process take? We end here.
    formatted_elapsed_duration = divmod(elapsed_duration, 60)  # Returns it as minutes and seconds

    if not daily_mode:
        print('\n+=============================================================================+')
        print('|-------------------------User Input Functions--------------------------------|')
        print('+=============================================================================+')

        if len(other_noted_posts) != 0:
            user_input = input("\nWould you like to edit the noted posts listed above? Enter y/n: ")  # Create a Plot?
            if user_input == 'y':
                for post in other_noted_posts:
                    if " |" in post[0:2]:
                        oid = post[-7:-1]  # Get back to six character ID
                        submission = reddit.submission(id=oid)
                        oflair_text = submission.link_flair_text
                        oauthor = submission.author.name
                        otitle = submission.title
                        comments = submission.comments.list()

                        header_4 = str("## " + otitle + " by u/" + oauthor + " - https://redd.it/" + oid)
                        print('=' * len(header_4))
                        print(header_4)
                        print('=' * len(header_4))
                        for comment in comments:
                            if comment.author is None:
                                continue
                            elif comment.author.name == "translator-BOT" or comment.author.name == "AutoModerator":
                                continue
                            print("\n### u/" + comment.author.name)
                            print("\n>>> " + comment.body)
                            print("\n------------------------------------------------")
                        new_css = input("\nEnter the new CSS flair, or type 'n' to skip: ")
                        new_css = str(new_css)
                        if new_css != "n":
                            if "Translated" in oflair_text:
                                oflair_text = "Translated [" + converter(new_css)[0].upper() + "]"
                                submission.mod.flair(text=oflair_text, css_class='translated')
                            elif "Needs Review" in oflair_text:
                                oflair_text = "Needs Review [" + converter(new_css)[0].upper() + "]"
                                submission.mod.flair(text=oflair_text, css_class='doublecheck')
                            elif "Missing" in oflair_text:
                                oflair_text = "Missing [" + converter(new_css)[0].upper() + "]"
                                submission.mod.flair(text=oflair_text, css_class='missing')
                            print("> Changed the post's flair to " + oflair_text + ".")
                        elif new_css == "n":
                            continue
            else:
                print("> Did not edit any noted posts.")

    new_page_content = (month_page_content_noimg + header_1a + "\n" + month_family_page_content + header_2
                        + formatted_content + function_page_content)

    if not daily_mode:
        user_input = input("\nWould you like to write the results to a text file? Enter y/n: ")  # Write to file?
        if user_input == 'y':
            # Write to the output file
            f = open(FILE_ADDRESS_STATISTICS, 'w')  # File address for the output file (mirrors the monthly entry/post)
            f.write(date_range + "\n\n" + new_page_content)
            f.close()
        else:
            print("> Did not write to a text file.")

        if specific_month_mode:  # This chunk of code writes to the specific month stats page
            new_lang_page = r.wiki["{}_{}".format(i_month, i_year)]

            try:
                page_exist = len(new_lang_page.content_md)
            except prawcore.exceptions.NotFound:  # There is no wiki page for this.
                page_exist = False

            if page_exist:
                print("> There is already a monthly statistics page for this month.")
            else:
                print("> Creating a new monthly statistics page.")
                r.wiki.create(name="{}_{}".format(i_month, i_year), content=new_page_content,
                              reason='Updating specific monthly stats page with latest OVERALL data from ' + str(
                                  i_month) + '/' + str(i_year))
            # month_wiki_page = r.wiki.create[i_month + "_" + i_year] # Get the wiki page. Need code for edit vs.create
            # month_wiki_page.edit(content=new_page_content,
            #                      reason='Updating specific monthly stats page with latest OVERALL data from
            #                      '+str(i_month)+'/'+str(i_year))
            post_title = "[META] r/translator Statistics — {} {}".format(display_month_name, str(i_year))
            post_post = input(
                "\nWould you like to post a text post to r/translator with the statistics from this month? Enter y/n: ")
            if post_post == 'y':
                monthly_post = r.submit(title=post_title, selftext=new_page_content,
                                        send_replies=True)  # Submits a text post to the subreddit
                monthly_post.mod.sticky(state=True, bottom=True)  # Stickies the post to the front page.
                monthly_post.mod.distinguish()  # Distinguishes the post
                print("Created a monthly entry page for the last month and posted a text post.")
                
                if i_month != "01":  # January would reset so...
                    points_use_month = str(int(i_month))
                    if len(points_use_month) < 2:  # It's possible that this doesn't work properly without a leading zero?
                        points_use_month = "0" + points_use_month
                else:  # It's January. Get the month and year from last.
                    points_use_month = "12"
                    i_year = str(int(i_year) - 1)
                month_use_string = "{}-{}".format(i_year, points_use_month)
                points_summary = month_points_summary(month_use_string)
                points_comment = monthly_post.reply(points_summary)  # actually post a reply.
                points_comment.mod.distinguish(sticky=True)  # Distinguish the comment.
                print(">> Also added a comment with the points data.")
            else:
                print("> Did not post anything.")

    print('\n+=============================================================================+')
    print('|----------------------------------Summary------------------------------------|')
    print('+=============================================================================+')
    print("Start date and time (local)             | " + str(
        datetime.datetime.fromtimestamp(float(earliest_time)).strftime('%Y-%m-%d [%I:%M:%S %p]')))
    print("End date and time   (local)             | " + str(
        datetime.datetime.fromtimestamp(float(current_chronos)).strftime('%Y-%m-%d [%I:%M:%S %p]')))
    print("Ran in month-specific mode              | " + str(specific_month_mode))
    print("Subreddit wiki set for editing          | " + "r/" + SUBREDDIT)
    print("Edited overall statistics page          | " + str(diag_overall_written))
    print("Languages with translation requests     | " + str(lang_entries))
    print("Elapsed time                            | %d minutes %02d seconds" % formatted_elapsed_duration)

    return date_range + "\n\n" + new_page_content


def sidebar_update():

    # This is the current time.
    current_function_time = int(time.time())
    print("\n")
    print(datetime.datetime.fromtimestamp(current_function_time).strftime('%Y-%m-%d %H:%M:%S'))

    sidebar_bit = twenty_four_hours()
    print(sidebar_bit)

    if len(sidebar_bit) == 0:
        logger.warning("[WY] Sidebar updating routine encountered an error. (No posts in the last 24H)")
    elif len(sidebar_bit) != 0:
        settings = r.mod.settings()
        sidebar_contents = settings['description']
        new_sidebar_contents = sidebar_contents[:sidebar_contents.rfind('\n')]
        new_sidebar_contents += sidebar_bit
        r.mod.update(description=new_sidebar_contents, key_color='#222222')
        # print(">> Updated the sidebar with the latest statistics from the last 24 hours.")
        logger.debug("[WY] Updated the sidebar with the latest statistics from the last 24 hours.")
    else:
        return

        
'''CERBO (WENYUAN 3.0)'''


def cerbo_individual(language_name, ajos_in_period):
    # Language Name - the name of the language
    # Ajos in period - all the ajos in the period we want to analyze.

    # Format some links that we use.
    language_code = converter(language_name)[0]
    wikipedia_link = "[WP](https://en.wikipedia.org/wiki/ISO_639:{})".format(language_code)

    underscore_name = language_name.replace(" ", "_").lower()
    underscore_name = underscore_name.replace("'", "_")
    sub_wiki_link = "[{}](https://www.reddit.com/r/translator/wiki/{})".format(language_name, underscore_name)

    # Get the language family data.
    cache_data = wenyuan_cache_fetcher(language_code)
    try:
        language_family = cache_data[0]
        language_population = cache_data[1]
    except TypeError:  # We don't have data in database for this.
        language_population = 0
        language_family = "N/A"

    # Process through the Ajos for this language.
    language_statuses = []

    for ajo in ajos_in_period:
        if ajo["language_name"] == language_name:
            language_statuses.append(ajo["status"])

    # Count the statistics for this particular language
    total_count = len(language_statuses)
    translated_count = language_statuses.count("translated")
    doublecheck_count = language_statuses.count("doublecheck")
    untranslated_count = language_statuses.count("untranslated") + language_statuses.count(
        "missing") + language_statuses.count("inprogress")

    # Calculate percentages
    percent_of_requests = round((total_count / len(ajos_in_period)) * 100, 2)
    translation_percentage = int(((translated_count + doublecheck_count) / total_count) * 100)

    # Calculate RI
    if language_population != 0:  # Not a dead language
        language_share = language_population / 1000000  # In millions
        world_index = round((float(language_share) / WORLD_POP), 16)
        world_index *= 100
        rep_index = str(round((percent_of_requests / world_index), 2))
    else:
        rep_index = "---"

    return total_count, language_family, percent_of_requests, untranslated_count, translation_percentage, rep_index, sub_wiki_link, wikipedia_link


def cerbo_defined_multiple_unpacker(input_dict):  # A simple function to split defined multiple ajos

    output_dicts = []
    output_languages = input_dict["language_name"]

    for language in output_languages:
        code = converter(language)[0]

        temporary_dict = dict(input_dict)
        temporary_dict["language_name"] = language
        # Code for status matching.
        temporary_status_dict = input_dict['status']
        temporary_dict["type"] = 'single'
        temporary_dict["status"] = temporary_status_dict[code]
        temporary_dict["id"] = "{}_{}".format(input_dict["id"], code)
        output_dicts.append(temporary_dict)

    return output_dicts


def cerbo_wiki_editor(language_name, language_family, wiki_language_line,
                      month_year_chunk):  # A function that writes to the specific wiki page for the thing.

    # Format the name nicely.
    underscore_name = language_name.lower()
    underscore_name = underscore_name.replace(" ", "_")
    underscore_name = underscore_name.replace("'", "_")

    # Fetch the wikipage for the language.
    page_content = r.wiki[underscore_name]  # Get it.

    # Actually start adding data to the language's page.
    if language_name not in UTILITY_CODES:  # Regular languages
        try:
            if month_year_chunk not in str(page_content.content_md):  # This month has not been recorded on the wiki.
                # Checks to see if there's an entry for the month
                page_content_new = str(page_content.content_md) + wiki_language_line
                # Adds this month's entry to the data from the wikipage
                page_content.edit(content=page_content_new,
                                  reason='Updating with data from {}'.format(month_year_chunk))
                print("> Updated wiki entry for {} in {}.".format(language_name, month_year_chunk))
            else:  # Entry already exists
                print("> Wiki entry exists for {} in {}.".format(language_name, month_year_chunk))
        except prawcore.exceptions.NotFound:
            # Problem with the WikiPage... it doesn't exist.

            # Create a new wikipage.
            template_content = WY_NEW_HEADER.format(language_name=language_name, language_family=language_family)
            r.wiki.create(name=underscore_name, content=template_content,
                          reason="Creating a new statistics wiki page for {}".format(language_name))
            print("> Created a new wiki page for {}.".format(language_name))
            # Adds this month's entry to the data from the wikipage
            page_content_new = template_content + wiki_language_line
            page_content.edit(content=page_content_new, reason='Updating with data from {}'.format(month_year_chunk))
            print("> Updated wiki entry for {} in {}.".format(language_name, month_year_chunk))
    else:
        # Code for editing utility pages (app, unknown, etc.)
        if month_year_chunk not in str(page_content.content_md):
            page_content_new = str(page_content.content_md) + wiki_language_line
            page_content.edit(content=page_content_new, reason='Updating with data from {}'.format(month_year_chunk))
            print("> Updated wiki function entry for {} in {}.".format(language_name, month_year_chunk))
        else:  # Entry already exists
            print("> Wiki function entry exists for {} in {}.".format(language_name, month_year_chunk))
    return


def cerbo_other_posts_fetcher(start_time, end_time):
    """
    Function that determines the number of Meta and Community posts on r/translator during a particular time period.
    Returns an integer of "other posts" that can be integrated into cerbo results.
    """
    number_of_posts = 0

    for item in reddit.subreddit('translator').search('flair:Meta OR flair:Community', sort='new', time_filter="year"):
        icreated_utc = item.created_utc

        if end_time >= icreated_utc >= start_time:
            number_of_posts += 1

    return number_of_posts


def cerbo_identifications_collater(relevant_ajos):
    """ A function that is used to process various statistics related to the "Language History" of posts during a time.
    language_history is an attribute of Ajo objects that details the language history of a post. ['Japanese', 'Chinese']
    The local caching of Ajos is what allows this to be possible. Reddit itself does not save this information.
    
    This function returns a nice Markdown string of the information it has obtained and a dictionary containing data.
    
    :param relevant_ajos is a list of Ajos as dictionaries passed to the function by the cerbo() function. 
    """
    
    # A value used to restrict how many results are displayed. If a count is lower it will be omitted.
    limit_cutoff = 4
    
    # Changes Values (default)
    highest_num_changes = 2  # Default number that will be changed by the function below. 
    highest_changes = ""
    
    # Identified Values
    dict_identified = {}
    posts_identified_total = 0
    list_identified_as = []
    identified_to_post = []
    
    # Mixed-up Values
    list_mixed_up = []
    dict_mixed_up = {}
    mixed_up_to_post = []
    
    # Iterate over the Ajos.
    for ajo in relevant_ajos:
        individual_history = ajo['language_history']
        changes = len(individual_history)
        
        # We don't care about posts that are for just one language.
        if changes < 2:
            continue
        
        # We find the post that has undergone the most changes in identifications.
        if changes > highest_num_changes:
            highest_num_changes = changes
            highest_changes = ("\n\nThe [request with the most identifications](https://redd.it/{}) underwent {} "
                               "category changes ({}).".format(ajo['id'], changes, " → ".join(individual_history)))
            
        # Render a list of the languages most frequently from "Identified"
        if individual_history[0] is "Unknown" and changes >= 2:
            final_identified_language = individual_history[-1]  # Take the last language in the list.
            if final_identified_language is not "Unknown":
                posts_identified_total += 1
                list_identified_as.append(final_identified_language)
        elif individual_history[0] not in ["Unknown", "Generic"] and changes >= 2:  
            # For languages that did not start as 'Unknown' but were misidentified (Mixed up)
            list_mixed_up.append("Submitted as {}, actually {}".format(individual_history[0], individual_history[-1]))
        
    # Process the 'Identified' list, render it as a list with languages and counts.
    list_identified_master = list(set(list_identified_as))

    for language in list_identified_master:
        dict_identified[language] = list_identified_as.count(language)    
    for key in sorted(dict_identified, key=dict_identified.get, reverse=True):
        language_total_posts = cerbo_individual(key, relevant_ajos)[0]
        identified_number = dict_identified[key]
        percentage = round((identified_number / posts_identified_total) * 100, 2)
        # Here we set an artificial limit so that the list isn't too long.
        if identified_number >= limit_cutoff:
            misidentification_percentage = round((identified_number / language_total_posts) * 100, 2)
            identified_to_post.append("{} | {} | {}% | {}%".format(key, identified_number, percentage, misidentification_percentage))
    identified_header = ("\n\n##### 'Unknown' Identifications\n\n"
                         "Language | Requests Identified | Percentage of Total 'Unknown' Posts"
                         " | 'Unknown' Misidentification Percentage\n---|---|---|---\n")
    identified_to_post = identified_header + '\n'.join(identified_to_post)
    
    # Process the Mixed Up Statistics
    list_mixed_up_master = list(set(list_mixed_up))
    for combination in list_mixed_up_master:
        dict_mixed_up[combination] = list_mixed_up.count(combination)
    for key in sorted(dict_mixed_up, key=dict_mixed_up.get, reverse=True):
        combination_number = dict_mixed_up[key]
        if combination_number >= limit_cutoff:
            mixed_up_to_post.append("{} | {}".format(key, combination_number))  
    mixed_up_header = "\n\n##### Commonly Misidentified Language Pairs\n\nLanguage Pair | Requests Identified\n---|---\n"
    mixed_up_to_post = mixed_up_header + '\n'.join(mixed_up_to_post)
    
    final_to_post = identified_to_post + mixed_up_to_post + highest_changes
    
    return final_to_post, dict_identified


def cerbo(input_date, edit_wiki=False):  # The brain behind Wenyuan 3.0, using Ajos

    # Make some date calculations
    if input_date != "p":  # If a specific month is given, Wenyuan will retrieve the results for that.
        specific_month_mode = True

        # Let's get the Unix time of the start of the month
        month_number, year_number = input_date.split('/')
        month_number = int(month_number)
        year_number = int(year_number)

        month_days_number = int(calendar.monthrange(int(year_number), int(month_number))[1])
        start_date = datetime.datetime(year=year_number, month=month_number, day=1, hour=0, minute=0, second=1)
        start_date = calendar.timegm(start_date.timetuple())
        end_date = datetime.datetime(year=year_number, month=month_number, day=month_days_number, hour=23, minute=59,
                                     second=59)
        end_date = calendar.timegm(end_date.timetuple())
        print("\nStart: {}, End: {}\n".format(start_date, end_date))

        # Get the English name of the month for print later
        month_english_name = datetime.date(1900, int(month_number), 1).strftime('%B')
    else:  # This will call the Pingzi loop.
        specific_month_mode = False

        month_number = int(
            datetime.date.today().month - 1)  # Returns the last month, in number form (e.g. 10 for October)
        if month_number == 0:
            month_number = 12  # Account for January
        year_number = int(datetime.date.today().year)  # Returns the year in number form
        month_english_name = datetime.date(1900, int(month_number), 1).strftime('%B')

        end_date = time.time()
        start_date = end_date - 2592000

    # Access the AJO Database
    cursor_ajo.execute("SELECT * FROM local_database")
    stored_ajos = cursor_ajo.fetchall()

    # The Ajos we want to work on will be stored in this list.
    relevant_ajos = []
    languages_list = []  # THE MASTER LIST
    languages_family_dict = {}

    for ajo in stored_ajos:

        time_created = int(ajo[1])  # Get the UTC time it was created.
        if end_date >= time_created >= start_date:  # This is the right age to act on.

            actual_ajo = eval(ajo[2])  # Convert the string into a proper dictionary
            relevant_ajos.append(actual_ajo)  # Add it to our list.

            if type(actual_ajo["language_name"]) == str:
                languages_list.append(actual_ajo["language_name"])
            else:  # It's a list
                for name in actual_ajo["language_name"]:
                    languages_list.append(name)

            # Function here to break apart defined multiple posts.
            if actual_ajo["type"] == "multiple":
                if type(actual_ajo["language_name"]) == list:  # It's a defined multiple
                    defined_data = cerbo_defined_multiple_unpacker(actual_ajo)
                    # Add the split ajos to the main one.
                    relevant_ajos += defined_data
                    # Remove the original one.
                    relevant_ajos.remove(actual_ajo)

    # Clean up our master list of represented languages here.
    languages_list = [x for x in languages_list if x]  # Remove blanks
    languages_list = list(set(languages_list))  # Remove duplicates
    languages_list.sort()  # Alphabetize

    # Some BROAD Variables for each section to use...
    if month_number < 10:  # Add on a leading zero
        month_year_chunk = "0{} | {} | ".format(month_number, year_number)
        month_year_underscore_chunk = "0{}_{}".format(month_number, year_number)
        month_number = str("0{}".format(month_number))
    else:
        month_year_chunk = "{} | {} | ".format(month_number, year_number)
        month_year_underscore_chunk = "{}_{}".format(month_number, year_number)
    master_count = len(relevant_ajos)
    identification_data = cerbo_identifications_collater(relevant_ajos)
    language_individual_lines = []
    other_individual_lines = []

    # Compile and format our topmost header.
    topmost_section = "# [{} {}](https://www.reddit.com/r/translator/wiki/{}) ".format(month_english_name, year_number,
                                                                                       month_year_underscore_chunk)
    if specific_month_mode:
        topmost_image = '![](%%statistics-h%%)'
    else:
        topmost_image = ""
    topmost_section += ("{}\n*[Statistics](https://www.reddit.com/r/translator/wiki/statistics) for r/translator "
                        "provided by [Wenyuan]"
                        "(https://www.reddit.com/r/translatorBOT/wiki/wenyuan)*".format(topmost_image))

    # Compile and format the Single Languages Data.
    single_languages_section = ("\n\n### Single-Language Requests"
                                "\nLanguage | Language Family | Total Requests | Percent of All Requests "
                                "| Untranslated Requests | Translation Percentage | Identified from 'Unknown' | "
                                "RI | Wikipedia Link\n-----|-----|------|-----|---|-----|---|---|-----")
    for language in languages_list:
        if language not in UTILITY_CODES:

            language_code = converter(language)[0]
            language_line_data = cerbo_individual(language, relevant_ajos)

            # Basic data assignments
            total_posts = language_line_data[0]
            language_family = language_line_data[1]
            percent_of_all = language_line_data[2]
            untranslated_posts = language_line_data[3]
            translation_percentage = language_line_data[4]
            if language in identification_data[1]:
                unknown_identified_posts = identification_data[1][language]  # Retrieve this data from a dictionary
            else:
                unknown_identified_posts = 0
            rep_index = language_line_data[5]

            sub_wiki_link = language_line_data[6]
            wikipedia_link = language_line_data[7]
            search_link = '[{}](/r/translator/search?q=flair:"{}"+OR+flair:"[{}]"&sort=new&restrict_sr=on)'.format(
                total_posts, language, language_code.upper())
            search_link = search_link.replace(" ", "_")

            # Populate the language family data for later.
            if language_family in languages_family_dict:
                languages_family_dict[language_family] += total_posts
            else:
                languages_family_dict[language_family] = total_posts

            # Properly format each line of data.
            line_template = "\n{} | {} | {} | {}% | {} | {}% | {} | {} | {}"
            language_line = line_template.format(sub_wiki_link, language_family, search_link, percent_of_all,
                                                 untranslated_posts, translation_percentage, unknown_identified_posts,
                                                 rep_index, wikipedia_link)
            single_languages_section += language_line

            # Properly format the wiki lines of data.
            wiki_line_template = '\n{} | {} | {} | {}% | {} | {}% | {} | ---'
            wiki_line = wiki_line_template.format(month_number, year_number, search_link, percent_of_all,
                                                  untranslated_posts, translation_percentage, rep_index)
            language_individual_lines.append((language, language_family, wiki_line))

    # Get the Identifications Data.
    identification_section = identification_data[0]

    # Compile and format the Language Families Data.
    families_section = "\n\n### Language Families\nLanguage Family | Total Requests | Percent of All Requests"
    families_section += "\n----|----|----"
    for key in sorted(languages_family_dict.keys()):
        families_number = languages_family_dict[key]
        families_percentage = round((families_number / master_count) * 100, 2)
        families_line_template = "\n{} | {} | {}%"
        families_section += families_line_template.format(key, families_number, families_percentage)

    # Compile and format the first OVERALL summary section.
    overall_section = "\n\n## Overall Statistics\nCategory | Post Count "
    overall_section += "\n----|----\n*Single-Language* | "
    overall_statuses = []
    multiple_count = 0
    multiple_app_count = 0
    # other_count = 0
    for ajo in relevant_ajos:  # Quick count of statuses and relevant information we need.
        if ajo['type'] == "single":
            overall_statuses.append(ajo['status'])
        else:
            if ajo['language_name'] == "App":
                multiple_app_count += 1
            elif ajo['language_name'] == "Multiple Languages":
                multiple_count += 1

        # if ajo['language_name'] in ['Conlang', 'Generic', 'Nonlanguage', 'Unknown']:
        #    other_count += 1
    overall_section += "\nUntranslated requests | {}".format(overall_statuses.count("untranslated"))
    overall_section += "\nRequests missing assets | {}".format(overall_statuses.count("missing"))
    overall_section += "\nRequests in progress | {}".format(overall_statuses.count("inprogress"))
    overall_section += "\nRequests needing review | {}".format(overall_statuses.count("doublecheck"))
    overall_section += "\nTranslated requests | {}".format(overall_statuses.count("translated"))
    overall_section += "\n | \n*Multiple-Language* | {}\n---|---".format(multiple_count + multiple_app_count)
    overall_section += "\n**Total posts** | **{}**".format(master_count)
    translated_percent = int(overall_statuses.count("translated")) + int(overall_statuses.count("doublecheck"))
    translated_percent = int(round((translated_percent / master_count) * 100, 0))
    overall_section += "\n**Overall percentage** | **{}% translated**".format(translated_percent)
    overall_section += "\n*Represented languages* | *{}*".format(len(languages_list))
    overall_section += "\n*Meta/Community Posts* | *{}*".format(cerbo_other_posts_fetcher(start_date, end_date))

    # Compile and format the translation directions section
    directions = []
    for ajo in relevant_ajos:
        if ajo['type'] == "single":
            directions.append(ajo['direction'])
    directions_section = "\n\n##### Translation Direction\n"
    english_to_percent = round((directions.count("english_to") / master_count) * 100, 2)
    directions_section += "\n* **To English**: {} ({}%)".format(directions.count("english_to"), english_to_percent)
    english_from_percent = round((directions.count("english_from") / master_count) * 100, 2)
    directions_section += "\n* **From English**: {} ({}%)".format(directions.count("english_from"),
                                                                  english_from_percent)
    english_none_percent = round((directions.count("english_none") / master_count) * 100, 2)
    directions_section += "\n* **Both Non-English**: {} ({}%)".format(directions.count("english_none"),
                                                                      english_none_percent)

    # Compile and format the notifications data section
    overall_notify_data = "\n\n##### Notifications Database\n"
    overall_notify_data += notify_list_statistics_calculator()[0]  # Gather data for notifications database

    # Compile and format the other single-language data section
    other_section = '\n\n#### Other Single-Language Requests/Posts'
    other_section += '\n\nCategory | Total Posts\n---|---'
    other_posts = []
    for code in ["art", "generic", "zxx", "unknown"]:
        flair_name = SUPPORTED_LANGUAGES[SUPPORTED_CODES.index(code)]  # Get the proper name of the flair.
        for ajo in relevant_ajos:
            if ajo['language_name'] == flair_name:
                other_posts.append(flair_name)
    other_master_list = list(set(other_posts))  # Indexed
    for other_name in other_master_list:
        other_code = converter(other_name)[0].upper()
        other_name_count = other_posts.count(other_name)
        other_line = "\n{0} | [{1}](https://www.reddit.com/r/translator/search?q=flair:%22{0}%22+OR+flair:%22{2}%22&sort=new&restrict_sr=on)".format(
            other_name, other_name_count, other_code)
        other_section += other_line

        # Format lines for the wiki.
        other_percentage = int(round((other_name_count / master_count) * 100, 2))
        other_wiki_template = "\n{0}[{1}](https://www.reddit.com/r/translator/search?q=flair:%22{2}%22+OR+flair:%22{3}%22&sort=new&restrict_sr=on) | {4}%"
        other_wiki_line = other_wiki_template.format(month_year_chunk, other_name_count, other_name, other_code,
                                                     other_percentage)
        other_individual_lines.append((other_name, "", other_wiki_line))

    # Compile and format the other multiple-language data section
    multiple_section = "\n\n### Multiple-Language/App Requests\n"
    multiple_section += "\n* For any language: {}".format(multiple_count)
    multiple_section += "\n* For apps in any language: {}".format(multiple_app_count)
    multiple_section += "\n* *The count for defined 'Multiple' requests are integrated into the table above.*"

    # Combine the sections together.
    master_format_data = (topmost_section + overall_section + families_section + single_languages_section + 
                          directions_section + identification_section + overall_notify_data + other_section +
                          multiple_section)
    f = open(FILE_ADDRESS_STATISTICS, 'w', encoding='utf-8')  # Address for the output file (mirrors the monthly entry)
    f.write(master_format_data)
    f.close()

    if edit_wiki is True and specific_month_mode is True:  # Wiki editing is enabled.

        # Edit the Wiki for Individual Pages
        for line in language_individual_lines:
            cerbo_wiki_editor(line[0], line[1], line[2], month_year_chunk)  # Pass it to the editing function.

        # Edit the Wiki for Other Function Pages
        for line in other_individual_lines:
            if line[0] in UTILITY_CODES[0:3]:
                cerbo_wiki_editor(line[0], line[1], line[2], month_year_chunk)  # Pass it to the editing function.

        # Edit the Wiki for Multiple / App pages
        multiple_percentage = round((multiple_count / master_count) * 100, 2)
        multiple_wiki_template = "\n{0}[{1}](https://www.reddit.com/r/translator/search?q=flair:%22{2}%22&sort=new&restrict_sr=on) | {3}%"
        multiple_wiki_line = multiple_wiki_template.format(month_year_chunk, multiple_count, "multiple",
                                                           multiple_percentage)
        cerbo_wiki_editor("multiple", "", multiple_wiki_line, month_year_chunk)
        multiple_app_percentage = round((multiple_app_count / master_count) * 100, 2)
        multiple_app_wiki_template = "\n{0}[{1}](https://www.reddit.com/r/translator/search?q=flair:%22{2}%22&sort=new&restrict_sr=on) | {3}%"
        multiple_app_wiki_line = multiple_app_wiki_template.format(month_year_chunk, multiple_app_count, "App",
                                                                   multiple_app_percentage)
        cerbo_wiki_editor("app", "", multiple_app_wiki_line, month_year_chunk)

        # Edit the Wiki for the Summary Page (example: 02_2018)
        summary_page = r.wiki["{}".format(month_year_underscore_chunk)]
        try:  # Check to see if the page already exists.
            page_exist = len(summary_page.content_md)
        except prawcore.exceptions.NotFound:  # There is no wiki page for this.
            page_exist = False
        if page_exist:
            print("> There is already a monthly statistics page for this month.")
        else:
            print("> Creating a new monthly statistics page.")
            r.wiki.create(name="{}".format(month_year_underscore_chunk), content=master_format_data,
                          reason="Creating a statistics summary page for {}".format(month_year_underscore_chunk))

        # Editing the overall_statistics page
        ov_month = "[{}](https://www.reddit.com/r/translator/wiki/{})".format(month_year_chunk.split(" ", 1)[0],
                                                                              month_year_underscore_chunk)
        ov_month_year_chunk = ov_month + month_year_chunk[2:]
        overall_statistics_template = "\n{}{} | {} | {} | {} | **{}** | **{}%**"
        overall_statistics_line = overall_statistics_template.format(ov_month_year_chunk,
                                                                     overall_statuses.count("untranslated"),
                                                                     overall_statuses.count("doublecheck"),
                                                                     overall_statuses.count("translated"), "---",
                                                                     master_count, translated_percent)
        overall_statistics_page = r.wiki["overall_statistics"]  # Fetches the wiki page for the overall data
        overall_content = overall_statistics_page.content_md

        if ov_month_year_chunk not in overall_content:  # We have not edited the overall statistics page before.
            overall_content += overall_statistics_line
            overall_statistics_page.edit(content=overall_content,
                                         reason="Updating the overall statistics page with data from {}.".format(
                                             month_year_underscore_chunk))
            print("> Edited and updated the overall statistics page.")
        else:
            print("> This month's data already exists on the overall statistics page.")

    return master_format_data


def post_monthly_statistics(month_year):
    """
    Routine to post the statistics post at the start of the month.
    This was split from the regular statistic routine in order to provide checking functionalities against previous
    versions of the post and to also allow inclusion of custom text.
    """

    # Split the date apart. Get some date variables.
    month_number, year_number = month_year.split('/')
    month_english_name = datetime.date(1900, int(month_number), 1).strftime('%B')

    # Generate the post title.
    post_title = "[META] r/translator Statistics — {} {}".format(month_english_name, year_number)

    # Format the statistics post.
    new_page_content = cerbo(month_year, edit_wiki=True)

    # Conduct a search check to see if there's already been a post.
    previous_stats_post_check = []
    for submission in r.search('title:"{}"'.format(post_title), sort='new', time_filter='year'):
        previous_stats_post_check.append(submission.id)
    if len(previous_stats_post_check) == 0:
        okay_to_post = True
    else:
        okay_to_post = False

    # There's no prior content. We can submit.
    if okay_to_post:

        # Check to see if there's a specific text we wanna include in the post.
        monthly_commentary = input("Do you want to include a note in the monthly post? Type the note or 's' to skip. ")
        if monthly_commentary.lower() != "s":
            part_1, part_2 = new_page_content.split('## Overall Statistics')
            new_page_content = "{}{}\n\n## Overall Statistics{}".format(part_1, monthly_commentary, part_2)

        monthly_post = r.submit(title=post_title, selftext=new_page_content,
                                send_replies=True)  # Submits a text post to the subreddit
        monthly_post.mod.sticky(state=True, bottom=True)  # Stickies the post to the front page.
        monthly_post.mod.distinguish()  # Distinguishes the post
        logger.info("[WY] Created a monthly entry page for the last month and posted a text post.")

        if month_number != "01":  # January would reset so...
            points_use_month = str(int(month_number))
            if len(points_use_month) < 2:  # It's possible that this doesn't work properly without a leading zero?
                points_use_month = "0" + points_use_month
        else:  # It's January. Get the month and year from last.
            points_use_month = "12"
            year_number = str(int(year_number) - 1)

        # Format the points comment.
        month_use_string = "{}-{}".format(year_number, points_use_month)
        points_summary = month_points_summary(month_use_string)
        points_comment = monthly_post.reply(points_summary)  # actually post a reply.
        points_comment.mod.distinguish(sticky=True)  # Distinguish the comment.
        print(">> Also added a comment with the points data.")
    else:
        previous_post = previous_stats_post_check[0]
        print("> It seems that there is already a statistics post for this month at https:redd.it/{}.".format(previous_post))

    return


'''TIMED ROUTINES'''


def log_trimmer():
    """
    This function preserves the last X number of entries in the events log to prevent it from getting too large.
    """

    lines_to_keep = 4000  # How many lines we wish to preserve

    f = open(FILE_ADDRESS_EVENTS, "r", encoding='utf-8')
    events_logs = f.read()
    f.close()

    lines_entries = events_logs.split('\n')

    if len(lines_entries) > lines_to_keep:  # If there are more lines, truncate it.
        lines_entries = lines_entries[(-1*lines_to_keep):]
        lines_entries = "\n".join(lines_entries)
        f = open(FILE_ADDRESS_EVENTS, "w", encoding='utf-8')
        f.write(lines_entries)
        f.close()

    logger.debug("[WY] Trimmed the events log to keep the last {} entries.".format(lines_to_keep))
    return


def status_updater():
    current_moment = time.time()
    year_month = datetime.datetime.fromtimestamp(current_moment).strftime('%Y-%m')

    # pingzi_update = statistics_calculator(daily_mode=True)
    pingzi_update = cerbo(input_date='p')
    users_update = month_points_summary(year_month)

    wiki_page = reddit.subreddit("translatorBOT").wiki["status"]
    page_content_new = '# Status\n\n{}\n\n##Points Summary\n\n{}'.format(pingzi_update, users_update)
    wiki_page.edit(content=page_content_new, reason='Ziwen: updating "status" page with the latest information')
    logger.info("[WY] status_updater: Saved to the 'status' page.")

    # Get the overall summary (the first table)
    overall_summary = pingzi_update.split('### Language Families', 1)[0]
    overall_summary = overall_summary.split('## Overall Statistics', 1)[1].strip()

    # We can add code here to get the monthly estimate
    overall_total = overall_summary.split('**Total posts** | ', 1)[1]
    overall_total = overall_total.split()[0]
    overall_total = int(overall_total.replace("**", ""))  # This will be the 30-day average as an int.

    daily_average = overall_total / 30
    now = datetime.datetime.now()
    days_in_current_month = calendar.monthrange(now.year, now.month)[1]  # Get the number of days in the current month
    estimated_month_total = int(round(daily_average * days_in_current_month, 0))

    overall_summary += "\n**Estimated total** | **{}**".format(estimated_month_total)

    return overall_summary


def unknown_thread():  # Simple function to post the Weekly unknown thread
    thread_title = '[META] Weekly "Unknown" Identification Thread — {timestamp}, Week {week_no}'
    time_format = '%Y-%m-%d'
    item_format = '{date_string} | **[{title}]({permalink})** | u/{author} '
    unknown_title = []
    unknown_id = []
    unknown_content = []

    # Define the week number for the title
    end_time = time.time()
    current_week = str(datetime.datetime.fromtimestamp(end_time).strftime('%U'))

    # Retrieve data from the last week
    for item in r.search('flair:"Unknown"', sort='new', time_filter="week"):
        if item.link_flair_css_class == "unknown":
            unknown_title.append(item.title)
            unknown_id.append(item.id)
            date_num = int(item.created)
            line = item_format.format(
                title=item.title[:180],
                date_string=datetime.datetime.fromtimestamp(date_num).strftime('%Y-%m-%d'),
                permalink='http://redd.it/%s' % item.id,
                author=item.author,
            )
            unknown_content.append(line)
    unknown_content = '\n'.join(unknown_content)

    if len(unknown_content) == 0:
        logger.debug("[WY] unknown_thread: There were no Unknown posts.")
        permission_granted = 'n'
    else:
        permission_granted = 'y'  # Automatically given since this runs by itself now.

    # Form the data
    title = thread_title.format(timestamp=time.strftime(time_format), week_no=current_week)
    body = WY_THREAD_BODY.format(unknown_content=unknown_content)

    if permission_granted == 'y':
        print("\n" + unknown_content)
        submission = r.submit(title=title, selftext=body, send_replies=False)
        submission.mod.distinguish()  # Distinguishes the weekly post
        logger.info("[WY] unknown_thread: Posted the weekly 'Unknown' thread to r/" + SUBREDDIT + ".")
    else:
        logger.info("[WY] unknown_thread: Did not post the weekly 'Unknown' thread. ")


def daily_backup():
    current = time.time()
    value = datetime.datetime.fromtimestamp(current)
    folder_name = value.strftime('%Y-%m-%d')

    if not os.path.isdir(TARGET_FOLDER[:-2]):  # Check to see if Box is mounted.
        logger.error("[WY] daily_backup: >> It appears that the backup service may not be mounted.")
        return False

    if os.path.isdir(TARGET_FOLDER.format(folder_name)):  # There is a folder with today's date.
        logger.info("[WY] daily_backup: >> Data has already been backed up for today.")
    else:
        # Initiate backup
        copy_target_folder = TARGET_FOLDER.format(folder_name)
        os.makedirs(copy_target_folder)
        src_files = os.listdir(SOURCE_FOLDER)
        for file_name in src_files:
            to_backup = True

            # Exclude certain files from being backed up daily. These are files that don't change or can rebuild.
            exclude_keywords = [".csv", "wy_", "_cache", "hb_", ".py", ".json"]
            for keyword in exclude_keywords:
                if keyword in file_name:
                    to_backup = False

            if to_backup:
                full_file_name = os.path.join(SOURCE_FOLDER, file_name)
                if os.path.isfile(full_file_name):  # The file exists
                    try:
                        shutil.copy(full_file_name, copy_target_folder)
                    except OSError:  # Copying error. Skip it.
                        pass
        logger.info("[WY] daily_backup: >> Daily backup created.")

        # Clean up earlier files.
        backup_files = os.listdir(TARGET_FOLDER[:-2])
        archive_target_folder = TARGET_FOLDER.format("_ARCHIVED/")

        for file_name in backup_files:
            if file_name == "_ARCHIVED" or file_name == folder_name:  # If it's today's backup or archive, do nothing.
                continue
            else:
                full_file_name = os.path.join(TARGET_FOLDER[:-2], file_name)
                shutil.move(full_file_name, archive_target_folder)
        logger.info("[WY] daily_backup: >> Earlier backups moved.")
        return True


def action_counter_uploader():  # A quick routine that checks if it's right to post the daily action counters.
    with open(FILE_ADDRESS_COUNTER, "r", encoding='utf-8') as f:
        counter_logs = f.read()

    wiki_page = reddit.subreddit("translatorBOT").wiki["actions"]
    page_content_new = '# Actions Log\n\n' + counter_logs  # Adds this language entry to the 'mentions page'
    try:
        wiki_page.edit(content=page_content_new, reason='Wenyuan: updating "actions" page with the latest counters')
    except prawcore.exceptions.TooLarge:  # The wikipage is too large.
        message_subject = "[Notification] 'Actions' Wiki Page Full"
        message_template = "The [actions wiki page](https://www.reddit.com/r/translatorBOT/wiki/actions) "
        message_template += "seems to be full. Please archive some of the older entries on that page."
        reddit.subreddit('translatorBOT').message(message_subject, message_template)

    logger.info("[WY] >> Saved to the 'actions' page.")
    return


def error_log_count():  # Function that counts how many entries are in the log.

    # Access the error log.
    with open(FILE_ADDRESS_ERROR, "r", encoding='utf-8') as f:
        error_logs = f.read()

    # Get the number of entries in the log.
    total_entries = error_logs.split('------------------------------')
    total_entries = [x for x in total_entries if x]  # Remove empty strings. This is now a list.
    num_entries = len(total_entries)

    # Get the last entry and its time.
    last_entry = total_entries[-1]
    last_entry_lines = last_entry.split('\n')
    last_entry_time = last_entry_lines[1]

    # Format it for output.
    formatted_template = "##### Operations\n\n"
    formatted_template += "* **Error log entries**: {}\n* **Last entry on**: {}"
    formatted_template = formatted_template.format(num_entries, last_entry_time)
    logger.debug("[WY] error_log_count: There were {} entries in the general error log.".format(num_entries))

    return formatted_template


def filter_log_tabulator():  # A function to calculate the filtration rate of bad titles.

    # Current day stamp.
    current = time.time()
    value = datetime.datetime.fromtimestamp(current)
    d_year = int(value.strftime('%Y'))
    d_month = int(value.strftime('%m'))
    d_day = int(value.strftime('%d'))
    d_now = datetime.date(d_year, d_month, d_day)

    # Open the filter log file.
    with open(FILE_ADDRESS_FILTER, "r", encoding='utf-8') as f:
        filter_logs = f.read()

    total_entries = filter_logs.split("\n")[2:]
    total_count = len(total_entries)

    # Get the first date and format as an object.
    first_date = total_entries[0].split("|")[0].strip()
    first_date = first_date.split("-")
    e_year = int(first_date[0])
    e_month = int(first_date[1])
    e_day = int(first_date[2])
    e_time = datetime.date(e_year, e_month, e_day)

    # Calculate the difference.
    delta = d_now - e_time
    days_elapsed = delta.days
    rate_per_day = total_count / days_elapsed
    rate_per_day = round(rate_per_day, 2)

    filter_string = "\n* **Filter rate**: {}/day".format(rate_per_day)
    logger.debug("[WY] filter_log_tabulator: The average number of filtered posts is {}/day.".format(rate_per_day))

    return filter_string


def get_editable_tags():
    """
    A small function that gets posts that have temporary tags still, or no tags at all.
    These temporary tags are [?] and [--]. They should be assigned proper languages.
    """

    header = "\n##### Entries"
    list_ids = []

    # Get the last 1000 entries, process them.
    for submission in r.new(limit=1000):
        # Add also if there is no link flair text.
        if submission.link_flair_text is None:
            list_ids.append(submission.id)

        # If it contains the placeholder codes...
        if "[?]" in submission.link_flair_text or "[--]" in submission.link_flair_text:
            list_ids.append(submission.id)

    # Alphabetize (oldest first)
    list_ids = list(sorted(list_ids))
    logger.debug("[WY] get_editable_tags: There are {} posts that have temporary tags.".format(len(list_ids)))

    # Collate the list of IDs together.
    if len(list_ids) != 0:
        binding_string = "\n* https://redd.it/"
        formatted_output = binding_string.join(list_ids)
        formatted_output = header + binding_string + formatted_output
    else:
        formatted_output = ""

    return formatted_output


def clear_notify_monthly_limit():
    """
    Function that clears out the monthly limit of notification limits. Used monthly and sparingly.
    :return: Nothing.
    """

    # First we want to get the number of notifications and transfer it.
    command_retrieve = "SELECT * FROM notify_monthly_limit"
    cursor.execute(command_retrieve)
    all_user_data = cursor.fetchall()  # This returns a list with tuples, e.g. (kungming2, 23)
    username_list = {}

    # Store the data in a dictionary. ({'kungming2': 2})
    for entry in all_user_data:
        username_list[entry[0]] = entry[1]

    # Initiate the transfer over to the other database.
    for username, value in username_list.items():

        # Check to see if user already has an entry. (taken from ZW user_statistics_writer)
        sql_us = "SELECT * FROM total_commands WHERE username = '{}'".format(username)
        cursor_p.execute(sql_us)
        username_commands_data = cursor_p.fetchall()

        if len(username_commands_data) == 0:  # Not saved, create a new one
            commands_dictionary = {'Notifications': 0}
            already_saved = False
        else:  # There's data already for this username.
            already_saved = True
            commands_dictionary = eval(username_commands_data[0][1])  # We only want the stored dict here.

        # Add the Notifications amount to the dictionary's value.
        commands_dictionary['Notifications'] += value

        if not already_saved:  # This is a new user to store.
            to_store = (username, str(commands_dictionary))
            cursor_p.execute("INSERT INTO total_commands VALUES (?, ?)", to_store)
            conn_p.commit()
        else:  # Update the dictionary
            to_store = (str(commands_dictionary),)
            update_command = "UPDATE total_commands SET commands = (?) WHERE username = '{}'".format(username)
            cursor_p.execute(update_command, to_store)
            conn_p.commit()

    # Command that wipes the monthly limits that were recorded.
    command = 'DELETE from notify_monthly_limit'
    cursor.execute(command)
    conn.commit()
    logger.info("[WY] clear_notify_monthly_limit: Monthly notification limit cleared.")

    return


def twenty_four_hours():
    current_jikan = time.time()
    upper_boundary = current_jikan - 86400  # The boundary 24 hours ago that we start calculating from.

    statuses = []

    cursor_ajo.execute("SELECT * FROM local_database")
    stored_ajos = cursor_ajo.fetchall()

    for ajo in stored_ajos:
        time_created = int(ajo[1])  # Get the UTC time it was created.
        if time_created >= upper_boundary:  # This is the right age to act on.
            actual_ajo = eval(ajo[2])  # Convert the string into a proper dictionary
            statuses.append(actual_ajo['status'])

    posts_translated = statuses.count("translated")
    posts_review = statuses.count("doublecheck")
    posts_untranslated = statuses.count("untranslated")

    complete_total = len(statuses)

    translated_percentage = round(((posts_translated + posts_review) / complete_total) * 100)
    to_post_template = "\n### Last 24H: ✗: **{}** ✓: **{}** ✔: **{}** ({}%)"
    to_post = to_post_template.format(posts_untranslated, posts_review, posts_translated, translated_percentage)
    logger.debug("[WY] twenty_four_hours: {}".format(to_post))

    return to_post


'''TIMERS'''


def weekly_unknown_timer():  # A quick routine that checks if it's right to post the Unknown thread.

    current = time.time()
    tvalue = datetime.datetime.fromtimestamp(current)
    today_date = tvalue.strftime('%Y-%m-%d')

    # Get the week number as a string.
    current_week = str(datetime.datetime.fromtimestamp(current).strftime('%U'))
    current_weekday = str(datetime.datetime.fromtimestamp(current).strftime('%A'))  # Get the weekday (Wednesday)

    # Get the hour (24-hour) as a zero padded digit.
    current_hour = int(datetime.datetime.fromtimestamp(current).strftime('%H'))

    if current_weekday == "Wednesday" and 8 <= current_hour <= 9:  # Post in the morning of Wednesday.
        logger.debug("[WY] weekly_unknown_timer: Time to post the weekly Unknown thread.")
    else:
        # print("> Not time yet.")
        return

    # Conduct a quick search to see if it's been posted before.
    search_query = 'title:"Identification Thread" title:{} Week {}'.format(today_date, current_week)
    search_results = r.search(search_query, sort='new', syntax='lucene', time_filter="month")
    search_total = len(list(search_results))  # Check if any results. If the thing has been posted, it'll return 1.

    if search_total == 0:  # The unknown thread has *not* been posted before.
        unknown_thread()
        logger.info("[WY] weekly_unknown_timer: Weekly 'Unknown' thread posted.")
    else:
        logger.debug("[WY] weekly_unknown_timer: The thread has been posted already. Skipping...")
        return


# noinspection PyBroadException,PyPep8
def master_timer():  # The timer to rule all other timers.

    current = time.time()
    tvalue = datetime.datetime.fromtimestamp(current)
    today_date = tvalue.strftime('%Y-%m-%d')
    date_only = tvalue.strftime('%d')

    # Get the hour (24-hour) as a zero padded digit.
    current_hour = int(datetime.datetime.fromtimestamp(current).strftime('%H'))

    if current_hour == 0:  # Update it after midnight.
        # print("> Time to perform administrative duties.")
        logger.info("[WY] master_timer: Daily administrative routine begun.")
    else:
        # print("> Not time yet.")
        return

    # noinspection PyPep8
    try:
        action_counter_uploader()  # Update the action counters.
        ac_success = "Success"
        logger.info("[WY] master_timer: Action counter uploading successful.")
    except Exception as em:
        action_entry = traceback.format_exc()
        action_entry += str(em)
        error_log_basic(action_entry, "Wenyuan Administration #ACTION")
        ac_success = "Failure"
        logger.error("[WY] master_timer: Action counter uploading error.")

    try:
        summary_data = status_updater()  # Process some statistics.
        su_success = "Success"
        logger.info("[WY] Statistics status posting successful.")
    except Exception as em:
        status_entry = traceback.format_exc()
        status_entry += str(em)
        error_log_basic(status_entry, "Wenyuan Administration #STATUS")
        su_success = "Failure"
        summary_data = ''
        logger.error("[WY] master_timer: Statistics status posting error.")

    try:
        db_success = daily_backup()  # Backup the database of files.
        if db_success:
            db_success = "Success"
            logger.info("[WY] master_timer: Database backup successful.")
        else:
            db_success = "Failure"
            logger.warning("[WY] master_timer: Database backup failure.")
    except PermissionError:
        db_success = "Failure"
        logger.warning("[WY] master_timer: Database backup failure (due to permission error).")
    except Exception as em:
        backup_entry = traceback.format_exc()
        backup_entry += str(em)
        error_log_basic(backup_entry, "Wenyuan Administration #BACKUP")
        db_success = "Failure"
        logger.error("[WY] master_timer: Database backup error.")

    elapsed_duration = (time.time() - current)  # How long did the process take? We end here.
    formatted_elapsed_duration = divmod(elapsed_duration, 60)  # Returns it as minutes and seconds
    formatted_elapsed_duration = str("%d:%02d" % formatted_elapsed_duration)  # Format it as a nice string

    error_log_data = error_log_count()
    filter_log_data = filter_log_tabulator()
    error_log_data += filter_log_data  # Add them together.

    entries_data = get_editable_tags()
    log_trimmer()  # Trim the events log

    # Message the mod.
    message_subject = '[Notification] Maintenance completed for the beginning of {}'.format(today_date)
    message_body = WY_MOD_NOTIFICATION_MESSAGE.format(ac_success, su_success, db_success, error_log_data,
                                                      entries_data, summary_data, formatted_elapsed_duration)
    reddit.redditor('kungming2').message(message_subject, message_body)
    logger.info("[WY] master_timer: Daily administrative routine completed.")

    # Code for a monthly routine (on the fifth of a month to allow for statistics to be updated)
    if int(date_only) == 5:
        clear_notify_monthly_limit()
        reddit.redditor('kungming2').message("[Notification] Maintenance on notification limit database", "Cleared.")
        logger.info("[WY] master_timer: Cleared the notifications limits cache.")


COMMAND_DISPLAY = '''
\nWenyuan's core search can retrieve detailed data from 06/2016. It can retrieve limited data between 09/2011 - 05/2016.
Version 2.0 and above is designed to work with Ziwen's tagging system for translated posts, effective 03/2017 and after.

      +-------------------------------------------------------------+
      | Command | Function                                          |
      |-------------------------------------------------------------|
      | ?       | Post the weekly unknown thread.                   |
      |-------------------------------------------------------------|
      | a       | Format a request to other language subreddits.    |
      |-------------------------------------------------------------|
      | q       | Post a bot status update.                         |
      | w       | Delete bot status updates.                        |
      | e       | Post the weekly translation challenge.            |
      |-------------------------------------------------------------|
      | t       | Delete test comments.                             |
      | y       | Delete test submissions.                          |
      | ------------------------------------------------------------|
      | c       | Test command information parsing.                 |
      | v       | Test converter data for a string.                 |
      | b       | Test title testing data for one title.            |
      | n       | Test main filtering process for one title.        |
      | m       | Test bulk title testing data.                     |
      |-------------------------------------------------------------|
      | u       | Retrieve comparative data from other subs.        |
      |-------------------------------------------------------------|
      | i       | Retrieve notifications data.                      |
      | o       | Retrieve user points for a month.                 |
      | p       | Retrieve post statistics.                         |
      |-------------------------------------------------------------|
      | loop    | Begin the hourly monitoring loop.                 |
      | table   | Update the statistics table with links.           |
      | post    | Post the monthly statistics post.                 |
      |-------------------------------------------------------------|
      | x       | Quit Wenyuan.                                     |
      +-------------------------------------------------------------+
'''


while True:
    print(COMMAND_DISPLAY)
    input_function = input("\n      Please enter your selection: ")
    input_function = str(input_function).lower()
    RECORD_DURATION = time.time()  # Begins recording how long the process is taking.
    if input_function == 'x':
        break
    elif input_function == "?":
        unknown_thread()
    elif input_function == "a":
        print(language_single_ad())
    elif input_function == "q":
        bot_status_update()
    elif input_function == "w":
        bot_status_delete()
    elif input_function == "e":
        weekly_challenge_poster()
    elif input_function == "t":
        del_comments()
    elif input_function == "y":
        del_submissions()
    elif input_function == "c":  # For testing comments with commands
        test_command_mode = True
        while test_command_mode is True:
            command_test = input("\n      Please enter the comment with a command to test: ")
            if command_test == "x":
                test_command_mode = False
                break
            print("\n      1) !identify: 2) !translate: 3) !reference: 4) !search: 5) !page: ")
            command_type = input("\n      Please enter the command (including the ':'): ")
            if command_type == "1":
                command_type = "!identify:"
            elif command_type == "2":
                command_type = "!translate:"
            elif command_type == "3":
                command_type = "!reference:"
            elif command_type == "4":
                command_type = "!search:"
            elif command_type == "5":
                command_type = "!page:"
            command_data = comment_info_parser(command_test, command_type)
            print("\n")
            pp.pprint(command_data)
    elif input_function == "v":
        test_title_mode = True
        while test_title_mode is True:
            title_test = input("\n      Please enter the string to test: ")
            if title_test == "x":
                test_title_mode = False
                break
            title_test = converter(title_test)
            print("\n")
            pp.pprint(title_test)
    elif input_function == "b" or "[" in input_function:
        test_title_mode = True
        while test_title_mode is True:
            title_test = input("\n      Please enter the title to test: ")
            if title_test == "x":
                test_title_mode = False
                break
            title_test = title_format(title_test, display_process=True)
            print("\n")
            pp.pprint(title_test)
    elif input_function == "n":
        test_title_mode = True
        while test_title_mode is True:
            title_test = input("\n      Please enter the title to test through the filter: ")
            if title_test == "x":
                test_title_mode = False
                break
            title_test = main_posts_filter(title_test)
            print("\nResult: {}\nReason: {}".format(title_test[0], title_test[2]))
    elif input_function == "m":
        full_retrieval()
    elif input_function == "u":
        print(other_statistics_calculator())
    elif input_function == "i":
        notify_data = notify_list_statistics_calculator()
        print(notify_data[0])
        print(notify_data[1])
        print(notify_data[3])
        print("\n\n### Duplicates\n")
        pp.pprint(notify_data[2])  # Duplicates
        if notify_data[2] is not None:  # There are duplicates
            notify_list_dedupe()  # Run the deduper.
    elif input_function == "o":
        current_time = time.time()
        month_string = datetime.datetime.fromtimestamp(current_time).strftime('%Y-%m')
        points_month = input("\n      Please enter a month (MM/YYYY) to retrieve, or 'p' for the current month: ")
        if points_month == "p":
            print(month_points_summary(month_string))
        else:
            month_num = points_month.split("/")[0]
            year_num = points_month.split("/")[1]
            month_string = "{}-{}".format(year_num, month_num)
            print(month_points_summary(month_string))
    elif input_function == "p":
        stats_type = input("\n      Please enter the type of statistics routine to use: 'p', 2.0 'c', 3.0: ")
        if stats_type == "p":
            statistics_calculator(daily_mode=False)  # Old Reddit way, limited to 1000 posts max.
        elif stats_type == "c":
            searched_month = input("\n      Please enter a month (MM/YYYY) to retrieve, or 'p' for the last 30 days: ")
            returned_data = cerbo(input_date=searched_month, edit_wiki=False)
            print(returned_data)
    elif input_function == "table":  # Update the stats page table
        temp_results = statistics_table_former()
        statistics_page_updater(temp_results)
    elif input_function == "loop":  # The Ziwen Hourly loop
        ziwen_hourly_status = True
        while ziwen_hourly_status:
            # noinspection PyBroadException
            try:
                sidebar_update()
                master_timer()
                weekly_unknown_timer()
            except Exception as e:
                error_entry = traceback.format_exc()
                print(error_entry)  # Print error.
                bot_version = "{} {}".format(BOT_NAME, VERSION_NUMBER)
                if any(keyword in error_entry for keyword in CONNECTION_KEYWORDS):
                    # Bot will not log common connection issues
                    print("### There was a connection error.")
                else:
                    error_log_basic(error_entry, bot_version)  # Write the error to the log.
            WAIT = seconds_till_next_hour()  # Fetch the custom amount of seconds remaining till the next run.
            time_left = divmod(WAIT, 60)
            print('> Running again in {}:{}. \n'.format(time_left[0], time_left[1]))
            time.sleep(WAIT)
    elif input_function == "post":
        ready_to_post = input("\n      Which month's statistics would you like to post? (Enter MM/YYYY:) ")
        post_monthly_statistics(ready_to_post)
    # elif "/" in input_function and len(input_function) <= 7:
    #     statistics_calculator(input_function)
    else:
        continue
