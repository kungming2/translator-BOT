#!/usr/bin/env python3

"""
AJO CLASS/FUNCTIONS

The basic unit of Ziwen's functions is not an individual Reddit post on r/translator per se, but rather, an Ajo.
An Ajo class (from Esperanto aĵo, meaning 'thing') is constructed from a Reddit post but is saved locally and contains 
additional information that cannot be stored on Reddit's system. 
In Ziwen, changes to a post's language, state, etc. are made first to the Ajo. Then a function within the class can
determine its flair, flair text, and template. 

Note: Wenyuan (as of version 3.0) also uses Ajos for its statistics-keeping.

External Ajo-specific/related functions are all prefixed with `ajo` in their name. The Ajo class itself contains several
class functions.
"""

import csv
import re
from code._config import STATUS_KEYWORDS, logger
from code._language_consts import MAIN_LANGUAGES
from code._languages import (
    FILE_ADDRESS_ISO_ALL,
    app_multiple_definer,
    convert,
    country_converter,
    lang_code_search,
    language_mention_search,
    title_format,
)
from code.Ziwen_helper import ZiwenConfig
from typing import Dict, List

import praw  # Simple interface to the Reddit API that also handles rate limiting of requests.


class Ajo:
    """
    A equivalent of a post on r/translator. Used as an object for Ziwen and Wenyuan to work with for
    consistency with languages and to store extra data.

    The process is: Submission > Ajo (changes made to it) > Ajo.update().
    After a submission has been turned into an Ajo, Ziwen will only work with the Ajo unless it has to update Reddit's
    flair.

    Attributes:

        id: A Reddit submission that forms the base of this class.
        created_utc: The Unix time that the item was created.
        author: The Reddit username of the creator. [deleted] if not found.
        author_messaged: A boolean that marks whether or not the creator has been messaged that their post has been
                         translated.

        type: single, multiple

        country_code: The ISO 3166-2 code of a country associated with the language. None by default.
        language_name: The English name of the post's language, rendered as a string
                       (Note: Unknown, Nonlanguage, and Conlang posts, etc. count as a language_name)
        language_code_1: The ISO 639-1 code of a post's language, rendered as a string. None if non-existent.
        language_code_3: The ISO 639-3 code of a post's language, rendered as a string.
        language_history: The different names the post has been classified as, stored as a list (in sequence)

        status: The current situation of the post. untranslated, translated, needs review, in progress, or missing.
        title: The title of the post, minus the language tag part. Defaults to the reg. title if it's not determinable.
        title_original: The exact Reddit title of the post.
        script_name: The type of script it's classified as (None normally)
        script_code: Corresponding code

        is_supported: Boolean of whether this is a supported CSS class or not.
        is_bot_crosspost: Is it a crosspost from u/translator-BOT?

        is_identified: Is it a changed class?
        is_long: Is it a long post?
        is_script: Is it an Unknown post whose script has been identified?

        original_source_language_name: The ORIGINAL source language(s) it was classified as.
        original_target_language_name: The ORIGINAL target language(s) it was classified as.
        direction: Is the submission to/from English, both/neither.

        output_oflair_css: The CSS class that it should be flaired as.
        output_oflair_text: The text that accompanies it.

        parent_crosspost: If it's a crosspost, what's the original one.

        time_delta:  The time between the initial submission time and it being marked. This is a dictionary.

        Example of an output for flair is German (Identified/Script) (Long)
    """

    # noinspection PyUnboundLocalVariable
    def __init__(
        self,
        reddit_submission: Dict[any, any] | praw.reddit.models.Submission,
        post_templates: Dict[str, str],
    ):
        # This takes a Reddit Submission object and generates info from it.
        if isinstance(reddit_submission, dict):  # Loaded from a file?
            logger.debug("Ajo: Loaded Ajo from local database.")
            for key in reddit_submission:
                setattr(self, key, reddit_submission[key])
        else:  # This is loaded from reddit.
            logger.debug("Ajo: Getting Ajo from Reddit.")
            self.id = reddit_submission.id  # The base Reddit submission ID.
            self.created_utc = int(reddit_submission.created_utc)

            # Create some empty variables that can be used later.
            self.recorded_translators = []
            self.notified = []
            self.time_delta = {}
            self.author_messaged = False
            self.post_templates = post_templates

            # try:
            title_data = title_format(reddit_submission.title)

            try:  # Check if user is deleted
                self.author = reddit_submission.author.name
            except AttributeError:
                # Comment author is deleted
                self.author = "[deleted]"

            self.type = (
                "multiple"
                if reddit_submission.link_flair_css_class in ["multiple", "app"]
                else "single"
            )

            # oflair_text is an internal variable used to mimic the linkflair text.
            if reddit_submission.link_flair_text is None:  # There is no linkflair text.
                oflair_text = "Generic"
                self.is_identified = (
                    self.is_long
                ) = self.is_script = self.is_bot_crosspost = self.is_supported = False
            else:
                self.is_long = "(Long)" in reddit_submission.link_flair_text

                if reddit_submission.link_flair_css_class == "unknown":
                    # Check to see if there is a script classified.
                    if "(Script)" in reddit_submission.link_flair_text:
                        self.is_script = True
                        self.script_name = (
                            oflair_text
                        ) = reddit_submission.link_flair_text.split("(")[0].strip()
                        self.script_code = ajo_retrieve_script_code(self.script_name)
                    else:
                        self.is_script = False
                        self.script_name = self.script_code = None
                        oflair_text = "Unknown"
                    self.is_identified = False
                else:
                    if "(Identified)" in reddit_submission.link_flair_text:
                        self.is_identified = True
                        oflair_text = reddit_submission.link_flair_text.split("(")[
                            0
                        ].strip()
                    else:
                        self.is_identified = False
                        if "(" in reddit_submission.link_flair_text:  # Contains (Long)
                            oflair_text = reddit_submission.link_flair_text.split("(")[
                                0
                            ].strip()
                        else:
                            oflair_text = reddit_submission.link_flair_text

            if title_data is not None:
                self.direction = title_data.direction

                # The source language data is converted into a list. If it's just one, let's make it a string.
                # Take the only item
                self.original_source_language_name = (
                    title_data.source_languages[0]
                    if len(title_data.source_languages) == 1
                    else title_data.source_languages
                )
                self.original_target_language_name = (
                    title_data.target_languages[0]
                    if len(title_data.target_languages) == 1
                    else title_data.target_languages
                )
                if len(title_data.actual_title) != 0:
                    # Were we able to determine a title?
                    self.title = title_data.actual_title
                    self.title_original = reddit_submission.title
                else:
                    self.title = self.title_original = reddit_submission.title

                if "{" in reddit_submission.title and "}" in reddit_submission.title:
                    # likely contains a country name
                    country_suffix_name = re.search(r"{(\D+)}", reddit_submission.title)
                    # Get the Country name only
                    country_suffix_name = country_suffix_name.group(1)
                    # Get the code (e.g. CH for Swiss)
                    self.country_code = country_converter(country_suffix_name)[0]
                elif (
                    title_data.language_country is not None
                    and len(title_data.language_country) <= 6
                ):
                    # There is included code from title routine
                    country_suffix = title_data.language_country.split("-", 1)[1]
                    self.country_code = country_suffix
                else:
                    self.country_code = None

            if self.type == "single":
                if "[" not in oflair_text:  # Does not have a language tag. e.g., [DE]
                    if "{" in oflair_text:
                        # Has a country tag in the flair, so let's take that out.
                        country_suffix_name = re.search(r"{(\D+)}", oflair_text)
                        # Get the Country name only
                        country_suffix_name = country_suffix_name.group(1)
                        self.country_code = country_converter(country_suffix_name)[0]
                        # Now we want to take out the country from the title.
                        title_first = oflair_text.split("{", 1)[0].strip()
                        title_second = oflair_text.split("}", 1)[1]
                        oflair_text = title_first + title_second

                    converter_data = convert(oflair_text)
                    self.language_history = []  # Create an empty list.

                    if reddit_submission.link_flair_css_class != "unknown":
                        # Regular thing
                        self.language_name = converter_data.language_name
                        self.language_history.append(converter_data.language_name)
                    else:
                        self.language_name = "Unknown"
                        self.language_history.append("Unknown")
                    if len(converter_data.language_code) == 2:
                        self.language_code_1 = converter_data.language_code
                    else:
                        self.language_code_3 = converter_data.language_code

                    self.is_supported = converter_data.supported

                    if (
                        len(converter_data.language_code) == 2
                    ):  # Find the matching ISO 639-3 code.
                        self.language_code_3 = MAIN_LANGUAGES[
                            converter_data.language_code
                        ]["language_code_3"]
                    else:
                        self.language_code_1 = None
                else:  # Does have a language tag.
                    language_tag = reddit_submission.link_flair_text.split("[")[1][
                        :-1
                    ].lower()  # Get the characters

                    if language_tag not in ["?", "--"]:
                        # Non-generic versions
                        converter_data = convert(language_tag)
                        self.language_name = converter_data.language_name
                        self.is_supported = converter_data.supported
                        if len(language_tag) == 2:
                            self.language_code_1 = language_tag
                            self.language_code_3 = MAIN_LANGUAGES[language_tag][
                                "language_code_3"
                            ]
                        elif len(language_tag) == 3:
                            self.language_code_1 = None
                            self.language_code_3 = language_tag
                    else:  # Either a tag for an unknown post or a generic one
                        if language_tag == "?":
                            # Unknown post that has still been processed.
                            self.language_name = "Unknown"
                            self.language_code_1 = None
                            self.language_code_3 = "unknown"
                            self.is_supported = True
                        elif language_tag == "--":  # Generic post
                            self.language_name = None
                            self.language_code_1 = None
                            self.language_code_3 = "generic"
                            self.is_supported = False
            elif self.type == "multiple":
                # If it's a multiple type, let's put the language names etc as lists.
                self.is_supported = True
                self.language_history = []

                # Handle DEFINED MULTIPLE posts.
                if "[" in reddit_submission.link_flair_text:
                    # There is a list of languages included in the flair
                    # Return their names from the code.
                    # test_list_string = "Multiple Languages [DE, FR]"
                    multiple_languages = []
                    # Get just the codes
                    actual_list = reddit_submission.link_flair_text.split("[")[1][:-1]
                    # Take out the spaces in the tag.
                    actual_list = actual_list.replace(" ", "")

                    # Code to replace the special status symbols... Not fully sure how it interfaces with the rest
                    for keyword in STATUS_KEYWORDS.values():
                        if keyword.symbol in actual_list:
                            actual_list = actual_list.replace(keyword.symbol, "")

                    new_code_list = actual_list.split(",")  # Convert to a list

                    for code in new_code_list:  # We wanna convert them to list of names
                        code = code.lower()  # Convert to lowercase.
                        code = "".join(re.findall("[a-zA-Z]+", code))
                        multiple_languages.append(
                            convert(code).language_name
                        )  # Append the names of the languages.
                else:
                    # Get the languages that this is for. Will be a list or None.
                    multiple_languages = title_data.notify_languages

                # Handle REGULAR MULTIPLE
                if multiple_languages is None:  # This is a catch-all multiple case
                    if reddit_submission.link_flair_css_class == "multiple":
                        self.language_code_1 = self.language_code_3 = "multiple"
                        self.language_name = "Multiple Languages"
                        self.language_history.append("Multiple Languages")
                    elif reddit_submission.link_flair_css_class == "app":
                        self.language_code_1 = self.language_code_3 = "app"
                        self.language_name = "App"
                        self.language_history.append("App")
                elif multiple_languages is not None:
                    self.language_code_1 = []
                    self.language_code_3 = []
                    self.language_name = []
                    self.language_history.append("Multiple Languages")
                    for language in multiple_languages:  # Start creating the lists.
                        self.language_name.append(language)
                        multi_language_code = convert(language).language_code
                        if len(multi_language_code) == 2:
                            self.language_code_1.append(multi_language_code)
                            self.language_code_3.append(
                                MAIN_LANGUAGES[convert(language).language_code][
                                    "language_code_3"
                                ]
                            )
                        elif len(multi_language_code) == 3:
                            self.language_code_1.append(None)
                            self.language_code_3.append(multi_language_code)

            flair_set = [keyword.name for keyword in STATUS_KEYWORDS]
            if reddit_submission.link_flair_css_class in flair_set:
                self.status = reddit_submission.link_flair_css_class
            elif reddit_submission.link_flair_css_class in ["app", "multiple"]:
                # It's a generic one.
                if isinstance(self.language_code_3, str):
                    self.status = "untranslated"
                elif multiple_languages is not None:  # This is a defined multiple
                    #  Construct a status dictionary.(we could also use multiple_languages)
                    # Get just the codes
                    actual_list = reddit_submission.link_flair_text.split("[")[1][:-1]
                    # Pass it to dictionary constructor
                    self.status = ajo_defined_multiple_flair_assessor(actual_list)
            else:
                self.status = "untranslated"

            try:
                # Check to see if this is a bot crosspost.
                original_post_id = reddit_submission.crosspost_parent
                crossposter = reddit_submission.author.name
                if crossposter == "translator-BOT":
                    self.is_bot_crosspost = True
                    self.parent_crosspost = original_post_id[3:]
                else:
                    self.is_bot_crosspost = False
            except AttributeError:  # It's not a crosspost.
                self.is_bot_crosspost = False
        self.output_oflair_css = None
        self.output_oflair_text = None

    def __eq__(self, other):
        """
        Two Ajos are defined as the same if the dictionary representation of their contents match.

        :param other: The other Ajo we are comparing against.
        :return: A boolean. True if their dictionary contents match, False otherwise.
        """

        return self.__dict__ == other.__dict__

    def set_status(self, new_status: str):
        """
        Change the status/state of the Ajo - a status like translated, doublecheck, etc.

        :param new_status: The new status for the Ajo to have, defined as a string.
        """
        self.status = new_status

    def set_status_multiple(self, status_language_code, new_status):
        """
        Similar to `set_status` but changes the status of a defined multiple post. This function does this by writing
        its status as a dictionary instead, keyed by the language.

        :param status_language_code: The language code (e.g. `zh`) we want to define the status for.
        :param new_status: The new status for that language code.
        """
        if (
            isinstance(self.status, dict)
            and self.status[status_language_code] != "translated"
        ):
            # Make sure it's something we can actually update
            # Once something's marked as translated stay there.
            self.status[status_language_code] = new_status

    def set_long(self, new_long: bool):
        """
        Change the `is_long` boolean of the Ajo, a variable that defines whether it's considered a long post.
        Moderators can call this function with the command `!long`.

        :param new_long: A boolean on whether the post is considered long. True if it is, False otherwise.
        :return:
        """
        self.is_long = new_long

    def set_author_messaged(self, is_messaged: bool) -> None:
        """
        Change the `author_messaged` boolean of the Ajo, a variable that notes whether the OP of the post has been
        messaged that it's been translated.

        :param is_messaged: A boolean on whether the author has been messaged. True if they have, False otherwise.
        :return:
        """
        self.author_messaged = is_messaged

    def set_country(self, new_country_code: str) -> None:
        """
        A function that allows us to change the country code in the Ajo. Country codes are generally optional for Ajos,
        but they can be defined to provide more granular detail (e.g. `de-AO`).

        :param new_country_code: The country code (as a two-letter ISO 3166-1 alpha-2 code) the Ajo should be set as.
        """

        if new_country_code is not None:
            new_country_code = new_country_code.upper()

        self.country_code = new_country_code

    def set_language(self, new_language_code, new_is_identified=False):
        """
        This changes the language of the Ajo. It accepts a language code as well as an identification boolean.
        The boolean is False by default.

        :param new_language_code: The new language code to set the Ajo as.
        :param new_is_identified: Whether or not the `is_identified` boolean of the Ajo should be set to True.
                                  For example, `!identify` commands will set `is_identified` to True, but
                                  moderator `!set` commands won't. Ajos with `is_identified` as True will have
                                  "(Identified)" appended to their flair text.
        :return:
        """

        old_language_name = str(self.language_name)

        if new_language_code not in ["multiple", "app"]:
            # This is just a single type of language.
            self.type = "single"
            if len(new_language_code) == 2:
                self.language_name = convert(new_language_code).language_name
                self.language_code_1 = new_language_code
                self.language_code_3 = MAIN_LANGUAGES[new_language_code][
                    "language_code_3"
                ]
                self.is_supported = convert(new_language_code).supported
            elif len(new_language_code) == 3:
                self.language_name = convert(new_language_code).language_name
                self.language_code_1 = None
                self.language_code_3 = new_language_code

                # Check to see if this is a supported language.
                self.is_supported = (
                    MAIN_LANGUAGES[new_language_code]["supported"]
                    if new_language_code in MAIN_LANGUAGES
                    else False
                )
            elif new_language_code == "unknown":  # Reset everything
                self.language_name = "Unknown"
                self.language_code_1 = (
                    self.is_script
                ) = self.script_code = self.script_name = None
                self.language_code_3 = "unknown"
                self.is_supported = True
        elif new_language_code in ["multiple", "app"]:  # For generic multiples (all)
            if new_language_code == "multiple":
                self.language_name = "Multiple Languages"
                self.language_code_1 = self.language_code_3 = "multiple"
                self.status = "untranslated"
                self.type = "multiple"
            elif new_language_code == "app":
                self.language_name = "App"
                self.language_code_1 = self.language_code_3 = "app"
                self.status = "untranslated"
                self.type = "multiple"

        try:
            # We do a check here to make sure we are not including the same thing twice.
            # This is to avoid something like ['Unknown', 'Chinese', 'Chinese']
            if self.language_history[-1] != self.language_name:
                # Add the new language name to the history.
                self.language_history.append(self.language_name)
        except (AttributeError, IndexError):
            # There was no language_history defined... Let's create it.
            self.language_history = [old_language_name, self.language_name]

        self.is_identified = new_is_identified

    def set_script(self, new_script_code):
        """
        Change the script (ISO 15924) of the Ajo, assuming it is an Unknown post. This will also now reset the
        flair to Unknown.

        :param new_script_code: A four-letter ISO 15924 code.
        :return:
        """

        self.language_name = "Unknown"
        self.language_code_1 = None
        self.language_code_3 = "unknown"
        self.is_supported = True
        self.is_script = True
        self.script_code = new_script_code
        # Get the name of the script
        self.script_name = lang_code_search(new_script_code, True)[0]

    def set_defined_multiple(self, new_language_codes):
        """
        This is a function that sets the language of an Ajo to a defined Multiple one.
        Example: Multiple Languages [AR, KM, VI]

        :param new_language_codes: A string of language names or codes, where each element is separated by a `+`.
                                   Example: arabic+khmer+vi
        :return:
        """

        self.type = "multiple"
        old_language_name = str(self.language_name)

        # Divide into a list.
        set_languages_raw = new_language_codes.split("+")
        set_languages_raw = sorted(set_languages_raw, key=str.lower)

        # Set some default values up.
        set_languages_processed_codes = []
        self.status = {}  # self
        self.language_name = []  # self
        self.language_code_1 = []
        self.language_code_3 = []

        # Iterate through to get a master list.
        for language in set_languages_raw:
            converted_language = convert(language)
            code = converted_language.language_code
            name = converted_language.language_name
            if len(code) != 0 and len(name) != 0:
                set_languages_processed_codes.append(code)
                self.language_name.append(name)
                self.status[code] = "untranslated"

        # Evaluate the length of the potential string
        languages_tag_string = ", ".join(set_languages_processed_codes)

        # The limit for link flair text is 64 characters. we need to trim it so that it'll fit the flair.
        if len(languages_tag_string) > 34:
            languages_tag_short = []
            for tag in set_languages_processed_codes:
                if len(", ".join(languages_tag_short)) <= 30:
                    languages_tag_short.append(tag)
            set_languages_processed_codes = list(languages_tag_short)

        # Now we have code to generate a list of language codes ISO 639-1 and 3.
        for code in set_languages_processed_codes:
            if len(code) == 2:
                self.language_code_1.append(code)  # self
                code_3 = MAIN_LANGUAGES[code]["language_code_3"]
                self.language_code_3.append(code_3)
            elif len(code) == 3:
                self.language_code_3.append(code)
                self.language_code_1.append(None)

        try:
            # We do a check here to make sure we are not including the same thing twice.
            # This is to avoid something like ['Unknown', 'Chinese', 'Chinese']
            if self.language_history[-1] != self.language_name:
                # Add the new language name to the history.
                self.language_history.append("Multiple Languages")
        except (AttributeError, IndexError):
            # There was no language_history defined... Let's create it.
            self.language_history = [old_language_name, "Multiple Languages"]

    def set_time(self, status: str, moment: int) -> None:
        """
        This function creates or updates a dictionary, marking times when the status/state of the Ajo changed.
        This updates a dictionary where it is keyed by status and contains Unix times of the changes.

        :param status: The status that it was changed to. Translated, for example.
        :param moment: The Unix UTC time when the action was taken. It should be an integer.
        :return:
        """

        try:
            # We check here to make sure the dictionary exists.
            working_dictionary = self.time_delta
        except (
            AttributeError,
            NameError,
        ):  # There was no time_delta defined... Let's create it.
            working_dictionary = {}

        if status not in working_dictionary:
            # This status hasn't been recorded. Create it as a key in the dictionary.
            working_dictionary[status] = moment

        self.time_delta = working_dictionary

    def add_translators(self, translator_name: str) -> None:
        """
        A function to add the username of who translated what to the Ajo of a post (by appending their name to list).
        This allows Ziwen to keep track of translators and contributors.

        :param translator_name: The name of the individual who made the translation.
        :return:
        """

        try:
            if translator_name not in self.recorded_translators:
                # The username isn't already in it.
                self.recorded_translators.append(translator_name)
                # Add the username of the translator to the Ajo.
                logger.debug(f"Ajo: Added translator name u/{translator_name}.")
        except AttributeError:
            # There were no translators defined in the Ajo... Let's create it.
            self.recorded_translators = [translator_name]

    def add_notified(self, notified_list: List[str]) -> None:
        """
        A function to add usernames of who has been notified by the bot of a post.
        This allows Ziwen to make sure it doesn't contact people more than once for a post.

        :param notified_list: A LIST of usernames who have been contacted regarding a post.
        :return:
        """
        try:
            for name in notified_list:
                if name not in self.notified:
                    self.notified.append(name)
                    logger.debug(f"Ajo: Added notified name u/{name}.")
        except AttributeError:  # There were no notified users defined in the Ajo.
            self.notified = notified_list

    def reset(self, original_title: str) -> None:
        """
        A function that will completely reset it to the original specifications. Not intended to be used often.
        Moderators and OPs can call this with `!reset` to make Ziwen reprocess its flair and languages.

        :param original_title: The title of the post.
        :return:
        """

        formatted_title = title_format(original_title)
        self.language_name = formatted_title.final_css_text
        self.status = "untranslated"
        self.time_delta = {}  # Clear this dictionary.
        self.is_identified = False

        provisional_data = convert(self.language_name)  # This is a temporary code
        provisional_code = provisional_data.language_code
        self.is_supported = provisional_data.supported
        provisional_country = provisional_data.country_code

        if not formatted_title.final_css in ["multiple", "app"]:
            self.type = "single"
            if len(provisional_code) == 2:  # ISO 639-1 language
                self.language_code_1 = provisional_code
                self.language_code_3 = MAIN_LANGUAGES[provisional_code][
                    "language_code_3"
                ]
                self.country_code = provisional_country
            elif (
                len(provisional_code) == 3
                or provisional_code == "unknown"
                and provisional_code != "app"
            ):
                # ISO 639-3 language or Unknown post.
                self.language_code_1 = None
                self.language_code_3 = provisional_code
                self.country_code = provisional_country
                if provisional_code == "unknown":
                    # Fill in the special parameters for Unknown posts.
                    self.is_script = False
                    self.script_code = None
                    self.script_name = None
            elif len(provisional_code) == 4:  # It's a script
                self.language_code_1 = None
                self.language_code_3 = "unknown"
                self.is_script = True
                self.script_code = provisional_code
                self.script_name = lang_code_search(provisional_code, True)[0]
        else:
            # Resetting multiples here.
            self.type = "multiple"
            self.language_code_1 = self.language_code_3 = formatted_title.final_css

    # noinspection PyAttributeOutsideInit,PyAttributeOutsideInit
    def update_reddit(self, reddit: praw.Reddit) -> None:
        """
        Sets the flair properly on Reddit. No arguments taken.
        It collates all the attributes and decides what flair
        to give it, then selects the appropriate template for it.

        :return:
        """

        # Get the original submission object.
        original_submission = reddit.submission(self.id)
        code_tag = "[--]"  # Default, this should be changed by the functions below.
        self.output_oflair_css = None  # Reset this
        self.output_oflair_text = None

        # Code here to determine the output data... CSS first.
        unq_types = ["Unknown", "Generic"]
        if self.type == "single":
            # This includes checks to make sure the content are strings, not lists.
            if (
                self.is_supported
                and self.language_name not in unq_types
                and self.language_name is not None
            ):
                if self.language_code_1 is not None and isinstance(
                    self.language_code_1, str
                ):
                    code_tag = f"[{self.language_code_1.upper()}]"
                    self.output_oflair_css = self.language_code_1
                elif self.language_code_3 is not None and isinstance(
                    self.language_code_3, str
                ):
                    # Supported three letter code
                    code_tag = f"[{self.language_code_3.upper()}]"
                    self.output_oflair_css = self.language_code_3
            elif (
                not self.is_supported
                and self.language_name not in unq_types
                and self.language_name is not None
            ):
                # It's not a supported language
                if self.language_code_1 is not None and isinstance(
                    self.language_code_1, str
                ):
                    code_tag = f"[{self.language_code_1.upper()}]"
                    self.output_oflair_css = "generic"
                elif self.language_code_3 is not None and isinstance(
                    self.language_code_3, str
                ):
                    code_tag = f"[{self.language_code_3.upper()}]"
                    self.output_oflair_css = "generic"
            elif self.language_name == "Unknown":  # It's an Unknown post.
                code_tag = "[?]"
                self.output_oflair_css = "unknown"
                print(f">>> Update Reddit: Unknown post `{self.id}`.")
            elif (
                self.language_name is None
                or self.language_name == "Generic"
                or self.language_name == ""
            ):
                # There is no language flair defined.
                code_tag = "[--]"
                self.output_oflair_css = "generic"
        else:  # Multiple post.
            code_tag = []

            if (
                self.language_code_3 == "multiple"
            ):  # This is a multiple for all languages
                self.output_oflair_css = "multiple"
                code_tag = None  # Blank code tag, don't need it.
            elif (
                self.language_code_3 == "app"
            ):  # This is an app request for all languages
                self.output_oflair_css = "app"
                code_tag = None  # Blank code tag, don't need it.
            else:  # This is a defined multiple post.
                # Check to see if we should give this an 'app' classification.
                real_title = title_format(original_submission.title).actual_title
                app_yes = app_multiple_definer(real_title)

                self.output_oflair_css = "app" if app_yes else "multiple"

                # If the status tag is a dictionary, then give it a proper tag.
                if isinstance(self.status, dict):
                    code_tag = ajo_defined_multiple_flair_former(self.status)

        if self.type == "single":
            # Code to determine the output flair text.
            for status in STATUS_KEYWORDS:
                if self.status == status.name:
                    self.output_oflair_css = self.status
                    self.output_oflair_text = f"{status.description} {code_tag}"
                    break
            else:  # It's an untranslated language
                # The default flair text is just the language name.
                self.output_oflair_text = self.language_name
                if self.country_code is not None:  # There is a country code.
                    self.output_oflair_text = (
                        f"{self.output_oflair_text} {{{self.country_code}}}"
                    )
                    # add the country code in brackets after the language name. It will disappear if translated.
                if self.language_name != "Unknown":
                    if self.is_identified:
                        self.output_oflair_text = (
                            f"{self.output_oflair_text} (Identified)"
                        )
                    if self.is_long:
                        self.output_oflair_text = f"{self.output_oflair_text} (Long)"
                elif self.is_script:
                    # This is for Unknown posts
                    print(
                        f">>> Update Reddit: Is `{self.id}` script? `{self.is_script}`."
                    )
                    self.output_oflair_text = self.script_name + " (Script)"
        else:  # Flair text for multiple posts
            if code_tag is None:
                self.output_oflair_text = convert(self.output_oflair_css).language_name
            else:
                self.output_oflair_text = (
                    f"App {code_tag}"
                    if self.output_oflair_css == "app"
                    else f"Multiple Languages {code_tag}"
                )

        # Actually push the updated text to the server
        # original_submission.mod.flair(text=self.output_oflair_text, css_class=self.output_oflair_css)

        # Push the updated text to the server (redesign version)
        # Check the global template dictionary.
        # If we have the css in the keys as a proper flair, then we can mark it with the new template.
        if self.output_oflair_css in self.post_templates.keys():
            output_template = self.post_templates[self.output_oflair_css]
            logger.info(
                f"Update Reddit: Template for CSS `{self.output_oflair_css}` is `{output_template}`."
            )
            original_submission.flair.select(
                flair_template_id=output_template, text=self.output_oflair_text
            )
            logger.info(
                f"Set post `{self.id}` to CSS `{self.output_oflair_css}` and text `{self.output_oflair_text}`."
            )


def ajo_writer(new_ajo: Ajo, config: ZiwenConfig) -> None:
    """
    Function takes an Ajo object and saves it to a local database.

    :param new_ajo: An Ajo object that should be saved to the database.
    :return: Nothing.
    """

    created_time = new_ajo.created_utc
    representation = str(new_ajo.__dict__)
    ajo_to_store = (new_ajo.id, created_time, representation)
    config.cursor_ajo.execute(
        """
        INSERT INTO local_database(id, created_time, ajo) VALUES (?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET ajo = excluded.ajo
    """,
        ajo_to_store,
    )

    config.conn_ajo.commit()

    if config.cursor_ajo.rowcount == 1:
        logger.debug(
            "ajo_writer: New Ajo added or existing Ajo updated in the database."
        )
    else:
        logger.debug("ajo_writer: Ajo exists, but no change in data.")
    logger.debug("ajo_writer: Wrote Ajo to local database.")


def ajo_loader(ajo_id, config: ZiwenConfig) -> Ajo | None:
    """
    This function takes an ID string and returns an Ajo object from a local database that matches that string.
    This ID is the same as the ID of the Reddit post it's associated with.

    :param ajo_id: ID of the Reddit post/Ajo that's desired.
    :return: None if there is no stored Ajo, otherwise it will return the Ajo itself (not a dictionary).
    """

    # Checks the database
    config.cursor_ajo.execute("SELECT ajo FROM local_database WHERE id = ?", (ajo_id,))
    new_ajo = config.cursor_ajo.fetchone()

    if new_ajo is None:  # We couldn't find a stored dict for it.
        logger.debug("ajo_loader: No local Ajo stored.")
        return None
    # We do have stored data.
    new_ajo_dict = eval(new_ajo["ajo"])  # We only want the stored dict here.
    new_ajo = Ajo(new_ajo_dict, config.post_templates)
    logger.debug("ajo_loader: Loaded Ajo from local database.")
    return new_ajo  # Note: the Ajo class can build itself from this dict.


def ajo_defined_multiple_flair_assessor(flairtext):
    """
    A routine that evaluates a defined multiple flair text and its statuses as a dictionary.
    It can make sense of the symbols that are associated with various states of a post.

    :param flairtext: The flair text of a defined multiple post. (e.g. `Multiple Languages [CS, DE✔, HU✓, IT, NL✔]`)
    :return final_language_codes: A dictionary keyed by language and their respective states (translated, claimed, etc)
    """

    final_language_codes = {}
    flairtext = flairtext.lower()

    languages_list = flairtext.split(", ")

    for language in languages_list:
        # Get just the language code.
        language_code = " ".join(re.findall("[a-zA-Z]+", language))

        if len(language_code) != len(language):
            # There's a difference - maybe a symbol
            final_language_codes.update(
                {
                    language_code: status_keywords_tuple.name
                    for status_keywords_tuple in STATUS_KEYWORDS.values()
                    if status_keywords_tuple.symbol in language
                }
            )
        else:  # No difference, must be untranslated.
            final_language_codes[language_code] = "untranslated"

    return final_language_codes


def iso639_3_to_iso639_1(specific_code: str) -> None | str:
    """
    Function to get the equivalent ISO 639-1 code from an ISO 639-3 code if it exists.

    :param specific_code: An ISO 639-3 code.
    :return:
    """

    for key, value in MAIN_LANGUAGES.items():
        module_iso3 = value["language_code_3"]
        if specific_code == module_iso3:
            return key


def ajo_defined_multiple_flair_former(flairdict) -> str:
    """
    Takes a dictionary of defined multiple statuses and returns a string.
    To be used with the ajo_defined_multiple_flair_assessor() function above.

    :param flairdict: A dictionary keyed by language and their respective states.
    :return output_text: A string for use in the flair text. (e.g. `Multiple Languages [CS, DE✔, HU✓, IT, NL✔]`)
    """

    output_text = []

    for language, status in flairdict.items():
        # Try to get the ISO 639-1 if possible
        language_code = iso639_3_to_iso639_1(language) or language  # No ISO 639-1 code

        symbol = ""
        for status_keywords_tuple in STATUS_KEYWORDS.values():
            if status_keywords_tuple.symbol == status:
                symbol = status_keywords_tuple.name
                break

        output_text.append(f"{language_code.upper()}{symbol}")

    output_text = ", ".join(sorted(output_text))  # Create a string.
    return f"[{output_text}]"


def ajo_defined_multiple_comment_parser(pbody, language_names_list):
    """
    Takes a comment and a list of languages and looks for commands and language names.
    This allows for defined multiple posts to have separate statuses for each language.
    We don't keep English though.

    :param pbody: The text of a comment on a defined multiple post we're searching for.
    :param language_names_list: The languages defined in the post (e.g. [CS, DE✔, HU✓, IT, NL✔])
    :return: None if none found, otherwise a tuple with the language name that was detected and its status.
    """

    detected_status = None

    # Look for language names.
    detected_languages = language_mention_search(pbody)

    # Remove English if detected.
    if detected_languages is not None and "English" in detected_languages:
        detected_languages.remove("English")

    if detected_languages is None or len(detected_languages) == 0:
        return None

    # We only want to keep the ones defined in the spec.
    detected_languages = list(
        filter(lambda language: language in language_names_list, detected_languages)
    )

    # If there are none left then we return None
    if len(detected_languages) == 0:
        return None

    for keyword, detected_status in STATUS_KEYWORDS.items():
        if keyword in pbody:
            return detected_languages, detected_status.name


def ajo_retrieve_script_code(script_name: str) -> str | None:
    with open(FILE_ADDRESS_ISO_ALL, encoding="utf-8") as csv_file:
        csv_reader = csv.DictReader(csv_file, delimiter=",")
        for row in csv_reader:
            # This is a script code (the others are 3 characters).
            if len(row["ISO 639-3"]) == 4 and script_name == row["Language Name"]:
                return row["ISO 639-3"]
