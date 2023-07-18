#!/usr/bin/env python3

"""Universal functions and variables for r/translator bots to use."""

import datetime
import json
import logging
import os
import random
from time import strftime

# Set up the directories based on the current location of the bots.
script_directory = os.path.dirname(
    os.path.realpath(__file__)
)  # Fetch the absolute directory the script is in.
script_directory += "/Data/"  # Where the main files are kept.
SOURCE_FOLDER = script_directory

# A number that defines the soft number of notifications an individual will get in a month *per language*.
NOTIFICATIONS_LIMIT = 100
SUBREDDIT = "translator"

# Ziwen main database files (either static files or files that will be written to).
FILE_ADDRESS_CREDENTIALS = os.path.join(script_directory, "_login.json")
FILE_ADDRESS_UA = os.path.join(script_directory, "_ua.json")
FILE_ADDRESS_ALL_STATISTICS = os.path.join(script_directory, "_statistics.json")
FILE_ADDRESS_AJO_DB = os.path.join(script_directory, "_database_ajo.db")
FILE_ADDRESS_MAIN = os.path.join(script_directory, "_database_main.db")

# Ziwen SQLite3 cache file (cache file data is generated as the bot runs and is volatile).
FILE_ADDRESS_CACHE = os.path.join(script_directory, "_cache_main.db")

# Ziwen language database files (reference files for language-related functions).
FILE_ADDRESS_OLD_CHINESE = os.path.join(script_directory, "_database_old_chinese.csv")
FILE_ADDRESS_ZH_ROMANIZATION = os.path.join(
    script_directory, "_database_romanization_chinese.csv"
)
FILE_ADDRESS_ZH_BUDDHIST = os.path.join(
    script_directory, "_database_buddhist_chinese.md"
)
FILE_ADDRESS_ZH_CCCANTO = os.path.join(script_directory, "_database_cccanto.md")
FILE_ADDRESS_MECAB = os.path.join(
    script_directory, "mecab-ipadic-neologd"
)  # Folder where MeCab dict files are

# Ziwen output files (text files for saving information).
FILE_ADDRESS_ERROR = os.path.join(script_directory, "_log_error.md")
FILE_ADDRESS_COUNTER = os.path.join(script_directory, "_log_counter.json")
FILE_ADDRESS_FILTER = os.path.join(script_directory, "_log_filter.md")
FILE_ADDRESS_EVENTS = os.path.join(script_directory, "_log_events.md")
FILE_ADDRESS_ACTIVITY = os.path.join(script_directory, "_log_activity.csv")

# Wenyuan Markdown output files (text files for saving information).
FILE_ADDRESS_STATISTICS = os.path.join(script_directory, "wy_statistics_output.md")
FILE_ADDRESS_TITLE_LOG = os.path.join(script_directory, "wy_title_test_output.md")
FILE_ADDRESS_WEEKLY_CHALLENGE = os.path.join(script_directory, "wy_weekly_challenge.md")
FILE_ADDRESS_PORT = os.path.join(script_directory, "wy_port.json")

# Huiban database files (unused for now).
FILE_ADDRESS_NOTIFY_EXCHANGE = os.path.join(script_directory, "hb_exchangelist.db")
FILE_ADDRESS_HUIBAN_OLDPOSTS = os.path.join(script_directory, "hb_processed.db")

# These are the commands on r/translator.
KEYWORDS = [
    "!page:",
    "`",
    "!missing",
    "!translated",
    "!id:",
    "!set:",
    "!note:",
    "!reference:",
    "!search:",
    "!doublecheck",
    "!identify:",
    "!translate",
    "!translator",
    "!delete",
    "!claim",
    "!reset",
    "!long",
    "!restore",
]

# These are keywords in errors thrown from Internet connection problems. We don't need to log those.
# CONNECTION_KEYWORDS = ['200 HTTP', '400 HTTP', '401 HTTP', '403 HTTP', '404 HTTP', '404 HTTP', '500 HTTP', '502 HTTP',
#                       '503 HTTP', '504 HTTP', 'CertificateError', 'ConnectionRefusedError', 'Errno 113', 'Error 503',
#                       'ProtocolError', 'ServerError', 'socket.gaierror', 'socket.timeout', 'ssl.SSLError']
CONNECTION_KEYWORDS = []

# Testing subreddits for the bot. (mostly to test Ziwen Streamer's crossposting function)
TESTING_SUBREDDITS = ["testingground4bots", "test", "andom"]

# Footers for the comments that the bots make.
BOT_DISCLAIMER = (
    "\n\n---\n^(Ziwen: a bot for r / translator) ^| "
    "^[Documentation](https://www.reddit.com/r/translatorBOT/wiki/ziwen) ^| "
    "^[FAQ](https://www.reddit.com/r/translatorBOT/wiki/faq) ^| "
    "^[Feedback](https://www.reddit.com/r/translatorBOT)"
)
BOT_DISCLAIMER_EXCHANGE = (
    "\n\n---\n^Huiban: ^a ^bot ^for ^r/LanguageSwap ^| "
    "^[Contact](https://www.reddit.com/message/compose/?to=kungming2&subject=About+Huiban+Bot)"
)


"""DEFINING LOGIN CREDENTIALS"""


def credentials_loader():
    """
    A simple function that takes the login credentials in a JSON file and converts them to global variables to use.
    The keys for the variables are the same as the ones used elsewhere in these scripts (e.g. USERNAME).

    :param: None
    :return: This function declares the variables it reads from the JSON file as global variables in Python.
    """

    # Access the JSON file with the credentials.
    f = open(FILE_ADDRESS_CREDENTIALS, encoding="utf-8")
    login_data = f.read()
    f.close()

    # Convert the JSON data into a dictionary.
    login_data = json.loads(login_data)

    # Declare the variables.
    globals().update(login_data)


# Load the credentials from the JSON file.
credentials_loader()

""" LOGGING """

# Logging code, defining the basic logger.
logformatter = "%(levelname)s: %(asctime)s [%(filename)s:%(lineno)d]- %(message)s"
logging.basicConfig(
    format=logformatter, level=logging.INFO
)  # By default only show INFO or higher levels.
logger = logging.getLogger(__name__)

# Define the logging handler (the file to write to with formatting.)
handler = logging.FileHandler(FILE_ADDRESS_EVENTS)
handler.setLevel(
    logging.INFO
)  # Change this level for debugging or to display more information.
handler_format = logging.Formatter(logformatter, datefmt="%Y-%m-%d [%I:%M:%S %p]")
handler.setFormatter(handler_format)
logger.addHandler(handler)

""" UNIVERSAL FUNCTIONS SHARED BY COMPONENTS """


def get_random_useragent():
    """
    Simple function that chooses items for use in `requests` from the list above.

    :param: None.
    :return: It outputs a dictionary.
    """

    # Load the JSON file
    f = open(FILE_ADDRESS_UA, encoding="utf-8")
    ua_data = f.read()
    f.close()

    # Convert the JSON data into a dictionary.
    ua_data = json.loads(ua_data)
    ua_stored = ua_data["ua"]

    # Select a random one from the list.
    random_ua = random.choice(ua_stored)
    accept_string = "text/html,application/json,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    headers = {"User-Agent": random_ua, "Accept": accept_string}

    return headers


def error_log_basic(entry, bot_version):
    """
    A function to save errors to a log for later examination.
    This one is more basic and does not include the last comments or submission text.
    The advantage is that it can be shared between different routines, as it does not depend on PRAW.

    :param entry: The text we wish to include in the error log entry. Typically this is the traceback.
    :param bot_version: The version of the script that's writing this error entry (e.g. Ziwen, Wenyuan).
    :return: Nothing.
    """

    # Open the file for the error log in appending mode.
    f = open(FILE_ADDRESS_ERROR, "a+", encoding="utf-8")
    current_entries = f.read()

    # If this hasn't already been recorded, add it.
    if entry not in current_entries:
        error_date_format = strftime("%Y-%m-%d [%I:%M:%S %p]")
        f.write(
            "\n-----------------------------------\n{} ({})\n{}".format(
                error_date_format, bot_version, entry
            )
        )
        f.close()


def action_counter(messages_number, action_type):
    """
    Function takes in a number and an action type and writes it to a file.

    :param messages_number: The number of actions to record. Typically 1, but more for some (like notifications).
    :param action_type: The type of action, as a string. Usually a command.
    :return: This function does not return anything.
    """

    try:
        new_messages_number = int(messages_number)  # Make sure it's an integer
    except ValueError:  # This is not a valid integer
        return

    if new_messages_number == 0:  # There's nothing to add. Don't do anything.
        return

    # Convert !id: into its full synonym for consistency.
    if action_type == "!id:":
        action_type = "!identify:"

    # Format the current day as a string.
    current_day = strftime("%Y-%m-%d")

    # Open the file for reading and access its content.
    f = open(FILE_ADDRESS_COUNTER, "r+", encoding="utf-8")
    current_actions_dict = json.loads(f.read())  # Take the file's current contents
    f.close()  # Close the file

    if current_day in current_actions_dict:  # This day has been recorded.
        if action_type in current_actions_dict[current_day]:
            current_actions_dict[current_day][action_type] += new_messages_number
        else:
            current_actions_dict[current_day][action_type] = new_messages_number
    else:  # This day hasn't been recorded.
        current_actions_dict[current_day] = {action_type: new_messages_number}

    with open(os.path.join(FILE_ADDRESS_COUNTER), "w", encoding="utf-8") as fp:
        json.dump(current_actions_dict, fp, sort_keys=True, indent=4)


def load_statistics_data(language_code):
    """
    Function that loads the language statistics dictionary from our saved JSON file.

    :param language_code: Any language code.
    :return: The language dictionary if it exists. None otherwise.
    """

    # Open the file
    f = open(FILE_ADDRESS_ALL_STATISTICS, encoding="utf-8")
    stats_data = f.read()
    f.close()

    # Convert the JSON data into a dictionary.
    stats_data = json.loads(stats_data)
    if language_code in stats_data:
        specific_data = stats_data[language_code]
    else:  # This language code does not exist as a key.
        specific_data = None

    return specific_data


def time_convert_to_string(unix_integer):
    """Converts a UNIX integer into a time formatted according to
    ISO 8601 for UTC time.

    :param unix_integer: Any UNIX time number.
    """
    i = int(unix_integer)
    utc_time = datetime.datetime.fromtimestamp(i, tz=datetime.timezone.utc).isoformat()[
        :19
    ]
    utc_time = f"{utc_time}Z"

    return utc_time
