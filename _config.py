#!/usr/bin/env python3

"""Universal functions and variables for r/translator bots to use."""

import datetime
import json
import logging
import os
import random
from enum import StrEnum
from time import strftime
from typing import Dict

# Set up the directories based on the current location of the bots.
# Fetch the absolute directory the script is in.
script_directory = os.path.dirname(os.path.realpath(__file__))
script_directory += "/Data/"  # Where the main files are kept.

# A number that defines the soft number of notifications an individual will get in a month *per language*.
NOTIFICATIONS_LIMIT = 100
SUBREDDIT = "translator"

# Ziwen main database files (either static files or files that will be written to).
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
# Folder where MeCab dict files are
FILE_ADDRESS_MECAB = os.path.join(script_directory, "mecab-ipadic-neologd")

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

# These are the words that count as a 'short thanks' from the OP.
# If a message includes them, the bot won't message them asking them to thank the translator.
THANKS_KEYWORDS = [
    "thank",
    "thanks",
    "tyvm",
    "tysm",
    "thx",
    "danke",
    "arigato",
    "gracias",
    "appreciate",
    "solved",
]

# These are the commands on r/translator.
keywords_dict = {
    "page": "!page:",
    "back_quote": "`",
    "missing": "!missing",
    "translated": "!translated",
    "id": "!id:",
    "set": "!set:",
    "note": "!note:",
    "reference": "!reference:",
    "search": "!search:",
    "doublecheck": "!doublecheck",
    "identify": "!identify:",
    "translate": "!translate",
    "translator": "!translator",
    "delete": "!delete",
    "claim": "!claim",
    "reset": "!reset",
    "long": "!long",
    "restore": "!restore",
}
KEYWORDS = StrEnum("StrEnum", keywords_dict)

STATUS_KEYWORDS = {
    KEYWORDS.missing: KEYWORDS.missing.name,
    KEYWORDS.claim: "inprogress",
    KEYWORDS.doublecheck: KEYWORDS.doublecheck.name,
    KEYWORDS.translated: KEYWORDS.translated.name,
}

# These are symbols used to indicate states in defined multiple posts. The last two are currently used.
DEFINED_MULTIPLE_LEGEND: Dict[str, str] = {
    "⍉": KEYWORDS.missing.name,
    "¦": "inprogress",
    "✓": KEYWORDS.doublecheck.name,
    "✔": KEYWORDS.translated.name,
}
INVERSE_MULTIPLE_LEGEND = {value: key for key, value in DEFINED_MULTIPLE_LEGEND.items()}

# Testing subreddits for the bot. (mostly to test Ziwen Streamer's crossposting function)
# TESTING_SUBREDDITS = ["testingground4bots", "test", "andom"]

# Footers for the comments that the bots make.
# BOT_DISCLAIMER_EXCHANGE = (
#     "\n\n---\n^Huiban: ^a ^bot ^for ^r/LanguageSwap ^| "
#     "^[Contact](https://www.reddit.com/message/compose/?to=kungming2&subject=About+Huiban+Bot)"
# )
BOT_DISCLAIMER = (
    "\n\n---\n^(Ziwen: a bot for r / translator) ^| "
    "^[Documentation](https://www.reddit.com/r/translatorBOT/wiki/ziwen) ^| "
    "^[FAQ](https://www.reddit.com/r/translatorBOT/wiki/faq) ^| "
    "^[Feedback](https://www.reddit.com/r/translatorBOT)"
)

""" LOGGING """

# Logging code, defining the basic logger.
logformatter = "%(levelname)s: %(asctime)s [%(filename)s:%(lineno)d]- %(message)s"
# By default only show INFO or higher levels.
logging.basicConfig(format=logformatter, level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the logging handler (the file to write to with formatting.)
handler = logging.FileHandler(FILE_ADDRESS_EVENTS)
# Change this level for debugging or to display more information.
handler.setLevel(logging.INFO)
handler_format = logging.Formatter(logformatter, datefmt="%Y-%m-%d [%I:%M:%S %p]")
handler.setFormatter(handler_format)
logger.addHandler(handler)

""" UNIVERSAL FUNCTIONS SHARED BY COMPONENTS """


def get_random_useragent() -> Dict[str, str]:
    """
    Simple function that chooses items for use in `requests` from the list above.

    :param: None.
    :return: It outputs a dictionary.
    """

    # Load the JSON file
    with open(FILE_ADDRESS_UA, encoding="utf-8") as f:
        ua_data = json.load(f)
        ua_stored = ua_data["ua"]

        # Select a random one from the list.
        random_ua = random.choice(ua_stored)
        accept_string = "text/html,application/json,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        return {"User-Agent": random_ua, "Accept": accept_string}  # headers


def action_counter(messages_number: int, action_type: str) -> None:
    """
    Function takes in a number and an action type and writes it to a file.

    :param messages_number: The number of actions to record. Typically 1, but more for some (like notifications).
    :param action_type: The type of action, as a string. Usually a command.
    :return: This function does not return anything.
    """

    if messages_number == 0:  # There's nothing to add. Don't do anything.
        return

    # Convert !id: into its full synonym for consistency.
    if action_type == KEYWORDS.id:
        action_type = KEYWORDS.identify

    # Format the current day as a string.
    current_day = strftime("%Y-%m-%d")

    # Open the file for reading and access its content.
    with open(FILE_ADDRESS_COUNTER, "a+", encoding="utf-8") as f:
        current_actions_dict = json.load(f)
        if current_day in current_actions_dict:  # This day has been recorded.
            if action_type in current_actions_dict[current_day]:
                current_actions_dict[current_day][action_type] += messages_number
            else:
                current_actions_dict[current_day][action_type] = messages_number
        else:  # This day hasn't been recorded.
            current_actions_dict[current_day] = {action_type: messages_number}
            json.dump(current_actions_dict, f, sort_keys=True, indent=4)


def time_convert_to_string(unix_integer) -> str:
    """Converts a UNIX integer into a time formatted according to
    ISO 8601 for UTC time.

    :param unix_integer: Any UNIX time number.
    """
    i = int(unix_integer)
    utc_time = datetime.datetime.fromtimestamp(i, tz=datetime.timezone.utc).isoformat()[
        :19
    ]
    return f"{utc_time}Z"
