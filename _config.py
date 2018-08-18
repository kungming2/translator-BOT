#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
# Universal Information for r/translator bots to use

import os
import sys
import random
import logging
import json
from time import strftime

# Check to see which OS we're running on and change it dynamically. Needed for dependent files. 
if sys.platform == "linux":  # Linux
    TESTING_MODE = False
    SUBREDDIT = "translator"
    TARGET_FOLDER = "/home/pi/Box/Data Backup/{}"
elif sys.platform == "win32":  # Windows
    TESTING_MODE = True
    SUBREDDIT = "trntest"
    TARGET_FOLDER = "C:/Users/qinzh/Desktop/Box/Data Backup/{}"
else:  # sys.platform == "darwin":     # macOS
    TESTING_MODE = True
    SUBREDDIT = "trntest"
    TARGET_FOLDER = "/Users/qzlau/Desktop/Box/Data Backup/{}"

# Set up the directories
script_directory = os.path.dirname(__file__)  # Fetch the absolute directory the script is in.
script_directory += "/Data/"  # Where the main files are kept.
SOURCE_FOLDER = script_directory
    
# Ziwen database files
FILE_ADDRESS_CREDENTIALS = os.path.join(script_directory, "_login.json")
FILE_ADDRESS_PROCESSED = os.path.join(script_directory, "_database_processed.db")
FILE_ADDRESS_AJO_DB = os.path.join(script_directory, '_database_ajo.db')
FILE_ADDRESS_NOTIFY = os.path.join(script_directory, "_database_notify.db")
FILE_ADDRESS_POINTS = os.path.join(script_directory, "_database_points.db")
FILE_ADDRESS_REFERENCE = os.path.join(script_directory, "_database_reference.db")
FILE_ADDRESS_OLD_CHINESE = os.path.join(script_directory, "_database_old_chinese.csv")
FILE_ADDRESS_ZH_ROMANIZATION = os.path.join(script_directory, "_database_romanization_chinese.csv")
FILE_ADDRESS_MECAB = os.path.join(script_directory, "mecab-ipadic-neologd")  # Folder where MeCab dict files are

# Ziwen SQLite3 cache files
FILE_ADDRESS_COMMENT_CACHE = os.path.join(script_directory, "_cache_comment.db")
FILE_ADDRESS_MULTIPLIER_CACHE = os.path.join(script_directory, "_cache_multiplier.db")

# Ziwen Markdown output files
FILE_ADDRESS_ERROR = os.path.join(script_directory, "_log_error.md")
FILE_ADDRESS_COUNTER = os.path.join(script_directory, "_log_counter.md")
FILE_ADDRESS_FILTER = os.path.join(script_directory, "_log_filter.md")
FILE_ADDRESS_EVENTS = os.path.join(script_directory, "_log_events.md")

# Wenyuan Markdown output files
FILE_ADDRESS_STATISTICS = os.path.join(script_directory, "wy_statistics_output.md")
FILE_ADDRESS_TITLE_LOG = os.path.join(script_directory, "wy_title_test_output.md")
FILE_ADDRESS_WEEKLY_CHALLENGE = os.path.join(script_directory, "wy_weekly_challenge.md")

# Huiban database files
FILE_ADDRESS_NOTIFY_EXCHANGE = os.path.join(script_directory, "hb_exchangelist.db")
FILE_ADDRESS_HUIBAN_OLDPOSTS = os.path.join(script_directory, "hb_processed.db")

# These are keywords in errors thrown from Internet connection problems. We don't need to log those.
CONNECTION_KEYWORDS = ["socket.timeout", "ssl.SSLError", "ServerError", "400 HTTP", "socket.gaierror", "404 HTTP",
                       "Errno 113", "CertificateError", "Error 503", "ProtocolError", "ConnectionRefusedError",
                       "503 HTTP response", ' 404 HTTP response', '504 HTTP response', '200 HTTP response',
                       '403 HTTP response', '401 HTTP response', "500", "502 HTTP response"]
# Testing subreddits for the bot. (mostly for Ziwen Streamer)
TESTING_SUBREDDITS = ["r/testingground4bots", "r/test", "r/andom"]

# Footers for the comments that the bots make.
BOT_DISCLAIMER = ("\n\n---\n^Ziwen: ^a ^bot ^for ^r/translator ^| "
                  "^[Documentation](https://www.reddit.com/r/translatorBOT/wiki/ziwen) ^| "
                  "^[FAQ](https://www.reddit.com/r/translatorBOT/wiki/faq) ^| "
                  "^[Feedback](https://www.reddit.com/r/translatorBOT)")
BOT_DISCLAIMER_EXCHANGE = ("\n\n---\n^Huiban: ^a ^bot ^for ^r/LanguageSwap ^| "
                           "^[Contact](https://www.reddit.com/message/compose/?to=kungming2&subject=About+Huiban+Bot)")

# User agents for web access functions. Update every few months as necessary.
USERAGENTS_STORED = ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.84 Safari/537.36",
                     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36",
                     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.90 Safari/537.36",
                     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.79 Safari/537.36",
                     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.88 Safari/537.36",
                     "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.94 Safari/537.36",
                     "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.36",
                     "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/64.0.3282.186 Safari/537.36",
                     "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.139 Safari/537.36",
                     "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.181 Safari/537.36"]

'''DEFINING LOGIN INFO'''


def credentials_loader():
    """
    A simple function that takes the login credentials in a JSON file and converts them to global variables to use.
    """

    # Access the JSON file with the credentials.
    f = open(FILE_ADDRESS_CREDENTIALS, 'r', encoding='utf-8')
    login_data = f.read()
    f.close()

    # Convert the JSON data into a dictionary.
    login_data = json.loads(login_data)

    # Declare them.
    globals().update(login_data)

    return


credentials_loader()

''' LOGGING '''

# Logging code, defining the basic logger.
logformatter = '%(levelname)s: %(asctime)s - %(message)s'
logging.basicConfig(format=logformatter, level=logging.INFO)  # By default only show INFO or higher levels.
logger = logging.getLogger(__name__)

# Define Logging handler (file to write to with formatting.)
# Example use: logger.info("Okay")
handler = logging.FileHandler(FILE_ADDRESS_EVENTS)
handler.setLevel(logging.INFO)  # Change this level for debugging or to display more information.
handler_format = logging.Formatter(logformatter, datefmt="%Y-%m-%d [%I:%M:%S %p]")
handler.setFormatter(handler_format)
logger.addHandler(handler)

''' UNIVERSAL FUNCTIONS SHARED BY COMPONENTS '''


def get_random_useragent():
    """
    Simple function that chooses a random user-agent string for use in `requests` from the list above.
    It outputs a dictionary.
    """

    # Select a random one from the list.
    random_ua = random.choice(USERAGENTS_STORED)
    accept_string = "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    headers = {'User-Agent': random_ua, 'Accept': accept_string}

    return headers


def error_log_basic(entry, bot_version):
    """
    A function to save errors to a log for later examination.
    This one is more basic and does not include the last comments or submission text.
    The advantage is that it can be shared between different routines, as it does not depend on PRAW.
    """
    f = open(FILE_ADDRESS_ERROR, 'a+', encoding='utf-8')  # File address for the error log, cumulative.
    current_entries = f.read()

    if entry not in current_entries:
        error_date_format = strftime("%Y-%m-%d [%I:%M:%S %p]")
        f.write("\n-----------------------------------\n{} ({})\n{}".format(error_date_format, bot_version, entry))
        f.close()


def action_counter(messages_number, action_type):
    """
    Function takes in a number and an action type and writes it to a file.

    :param messages_number: The number of actions to record. Typically 1, but more for some (like notifications)
    :param action_type: The type of action, as a string. Usually a command.
    :return: This function does not return anything.
    """

    try:
        new_messages_number = int(messages_number)  # Make sure it's an integer
    except ValueError:  # This is not a valid integer
        return

    if new_messages_number == 0:  # There's nothing to add. Don't do anything.
        return

    current_day = strftime("%Y-%m-%d")
    current_test = "{} | {}".format(strftime("%Y-%m-%d"), action_type)  # The current day as a formatted string

    f = open(FILE_ADDRESS_COUNTER, 'r+', encoding='utf-8')  # Open the file for reading.
    current_logs_lines = f.read()  # Take the file's current contents
    f.close()  # Close the file

    if current_test in current_logs_lines:  # This day has been recorded.

        first_part = current_logs_lines.split(current_test)[0]  # This is the part preceding our entry
        second_part = current_logs_lines.split(current_test)[1]  # Includes number of entry and after

        active_line = second_part.split("\n", 1)[0]  # The line our number is on
        try:  # If there's stuff after the current line
            second_part_after = second_part.split("\n", 1)[1]  # This is the content after our entry. One piece.
            # print(second_part_after)
        except IndexError:  # This must be end of file. Return nothing.
            second_part_after = ""

        latest_before = active_line.split(" | ")[0]  # Mostly spaces for proper formatting.
        last_recorded_number = int(active_line.split(" | ")[-1])  # The last counter for this particular item.
        new_recorded_total = last_recorded_number + new_messages_number  # The final total for today

        new_entry = "{}{} | {}".format(current_test, latest_before,
                                       str(new_recorded_total))  # The formatted line for writing.
        if second_part_after != "":  # This is not end of file.
            new_logs_lines = "{}{}\n{}".format(first_part, new_entry, second_part_after)  # Reconstitute the file.
        else:
            new_logs_lines = "{}{}{}".format(first_part, new_entry, second_part_after)  # Reconstitute the file
    else:  # This action type has NOT been recorded yet today. Start from 0.
        new_recorded_total = new_messages_number
        new_entry = "\n{} | {} | {}".format(current_day, action_type.ljust(27),
                                            str(new_recorded_total))  # Format the last line as an entry.
        new_logs_lines = current_logs_lines + new_entry

    open(FILE_ADDRESS_COUNTER, "w", encoding='utf-8').close()  # Delete the contents

    f = open(FILE_ADDRESS_COUNTER, 'w', encoding='utf-8')  # Last open for writing the contents.
    f.write(new_logs_lines)
    f.close()
    return
