import datetime
import random
import re
import time
from code._config import BOT_DISCLAIMER, KEYWORDS, logger
from code._language_consts import CJK_LANGUAGES, ISO_MACROLANGUAGES, MAIN_LANGUAGES
from code._languages import comment_info_parser, convert, lang_code_search
from code._login import USERNAME
from code._responses import (
    COMMENT_ADVANCED_IDENTIFY_ERROR,
    COMMENT_CLAIM,
    COMMENT_CURRENTLY_CLAIMED,
    COMMENT_INVALID_CODE,
    COMMENT_INVALID_REFERENCE,
    COMMENT_INVALID_SCRIPT,
    COMMENT_NO_LANGUAGE,
    COMMENT_NO_RESULTS,
    COMMENT_PAGE_DISALLOWED,
    MSG_MISSING_ASSETS,
    MSG_RESTORE_LINK_FAIL,
    MSG_RESTORE_NOT_ELIGIBLE,
    MSG_RESTORE_TEXT_FAIL,
    MSG_RESTORE_TEXT_TEMPLATE,
    MSG_TRANSLATED,
)
from code.Ajo import Ajo, ajo_defined_multiple_comment_parser
from code.ja_processing import JapaneseProcessor
from code.notifier import (
    notifier_page_multiple_detector,
    notifier_page_translators,
    ziwen_notifier,
)
from code.zh_processing import zh_character, zh_word
from code.Ziwen_helper import (
    MESSAGES_OKAY,
    ZiwenConfig,
    css_check,
    komento_analyzer,
    komento_submission_from_comment,
    lookup_matcher,
    record_to_wiki,
)

import googlesearch
import praw
import requests
from lxml import html
from wiktionaryparser import WiktionaryParser


class ZiwenCommandProcessor:
    def __init__(
        self,
        pbody: str,
        pauthor: str,
        comment: praw.reddit.models.Comment,
        oflair_css: str,
        otitle: str,
        opermalink: str,
        oauthor: str,
        oajo: Ajo,
        osubmission: praw.reddit.models.Submission,
        oid: str,
        ocreated: float,
        pid: str,
        pbody_original: str,
        requester: str,
        config: ZiwenConfig,
    ) -> None:
        self.pbody = pbody
        self.pauthor = pauthor
        self.comment = comment
        self.oflair_css = oflair_css
        self.otitle = otitle
        self.opermalink = opermalink
        self.oauthor = oauthor
        self.oajo = oajo
        self.osubmission = osubmission
        self.oid = oid
        self.ocreated = ocreated
        self.pid = pid
        self.pbody_original = pbody_original
        self.requester = requester
        # from config
        self.config = config
        self.zw_useragent = config.zw_useragent
        self.reddit = config.reddit
        self.cursor_main = config.cursor_main
        self.cursor_ajo = config.cursor_ajo
        self.conn_main = config.conn_main
        self.post_templates = config.post_templates

    def __lookup_wiktionary_search(
        self, search_term: str, language_name: str
    ) -> str | None:
        """
        This is a general lookup function for Wiktionary, updated and
        cleaned up to be better than the previous version.
        This function is used for all non-CJK languages.
        Using 0.0.97.

        :param search_term: The word we're looking for information.
        :param language_name: Name of the language we're looking up the word in.
        :return post_template: None if it can't find anything, a formatted string for comments otherwise.
        """
        language_name = language_name.title()
        parser = WiktionaryParser()
        try:
            word_info_list = parser.fetch(search_term, language_name)
        except (TypeError, AttributeError):  # Doesn't properly exist, first check
            return None

        try:
            # A simple second test to see if something really has definitions
            exist_test = word_info_list[0]["definitions"]
        except IndexError:
            return None

        if exist_test:
            # Get the dictionary that is wrapped in the list.
            word_info = word_info_list[0]
        else:  # This information doesn't exist.
            return None

        # Do a check to see if the Wiktionary page exists, to prevent
        # accidental returns of English stuff. It checks to see if a header
        # exists in that language. If it doesn't then it will return None.
        test_wikt_link = f"https://en.wiktionary.org/wiki/{search_term}#{language_name}"
        test_page = requests.get(test_wikt_link, headers=self.zw_useragent)
        test_tree = html.fromstring(
            test_page.content
        )  # now contains the whole HTML page
        test_language = test_tree.xpath(
            f'string(//span[contains(@id,"{language_name}")])'
        )
        if language_name == test_language:
            logger.info("This word exists in its proper language on Wiktionary.")
        else:
            logger.info(
                "This word does NOT exist in its proper language on Wiktionary."
            )
            return None

        # First, let's take care of the etymology section.
        post_etymology = word_info["etymology"]
        if len(post_etymology) > 0:  # There's actual information:
            post_etymology = post_etymology.replace(r"\*", "*")
            post_etymology = f"\n\n#### Etymology\n\n{post_etymology.strip()}"

        # Secondly, let's add a pronunciation section if we can.
        dict_pronunciations = word_info["pronunciations"]
        pronunciations_ipa = ""
        pronunciations_audio = ""
        if len(dict_pronunciations.values()) > 0:  # There's actual information:
            if len(dict_pronunciations["text"]) > 0:
                pronunciations_ipa = dict_pronunciations["text"][0].strip()
            else:
                pronunciations_ipa = ""
            if len(dict_pronunciations["audio"]) > 0:
                pronunciations_audio = (
                    f" ([Audio](https:{dict_pronunciations['audio'][0]}))"
                )
            else:
                pronunciations_audio = ""
        if len(pronunciations_ipa + pronunciations_audio) > 0:
            post_pronunciations = (
                f"\n\n#### Pronunciations\n\n{pronunciations_ipa}{pronunciations_audio}"
            )
        else:
            post_pronunciations = ""

        # Lastly, and most complicated, we deal with 'definitions', including
        # examples, partOfSpeech, text (includes the gender/meaning)
        # A different part of speech is given as its own thing.
        total_post_definitions = []

        if len(word_info["definitions"]) > 0:
            separate_definitions = word_info["definitions"]
            # If they are separate parts of speech they have different definitions.
            for dict_definitions in separate_definitions:
                # Deal with Examples
                if len(dict_definitions["examples"]) > 0:
                    examples_data = dict_definitions["examples"]
                    if len(examples_data) > 3:
                        # If there are a lot of examples, we only want the first three.
                        examples_data = examples_data[:3]
                    post_examples = "* " + "\n* ".join(examples_data)
                    post_examples = f"\n\n**Examples:**\n\n{post_examples}"
                else:
                    post_examples = ""

                # Deal with parts of speech
                if len(dict_definitions["partOfSpeech"]) > 0:
                    post_part = dict_definitions["partOfSpeech"].strip()
                else:
                    post_part = ""

                # Deal with gender/meaning
                if len(dict_definitions["text"]) > 0:
                    master_text_list = dict_definitions["text"]
                    master_text_list = [
                        x.replace("\xa0", " ^") for x in master_text_list if x
                    ]
                    master_text_list = [x for x in master_text_list if x]
                    print(master_text_list)
                    post_word_info = master_text_list[0]

                    meanings_format = "* " + "\n* ".join(master_text_list[1:])
                    post_meanings = f"\n\n*Meanings*:\n\n{meanings_format}"
                    post_total_info = post_word_info + post_meanings
                else:
                    post_total_info = ""

                # Combine definitions as a format.
                if len(post_examples + post_part) > 0:
                    # Use the part of speech as a header if known
                    info_header = post_part.title() if post_part else "Information"
                    post_definitions = (
                        f"\n\n##### {info_header}\n\n{post_total_info}{post_examples}"
                    )
                    total_post_definitions.append(post_definitions)

        total_post_definitions = "\n" + "\n\n".join(total_post_definitions)

        # Put it all together.
        post_template = "# [{0}](https://en.wiktionary.org/wiki/{0}#{1}) ({1}){2}{3}{4}"
        post_template = post_template.format(
            search_term,
            language_name,
            post_etymology,
            post_pronunciations,
            total_post_definitions,
        )
        logger.info(
            f"Looked up information for {search_term} as a {language_name} word.."
        )

        return post_template

    def __messaging_translated_message(self) -> None:
        """
        Function to message requesters (OPs) that their post has been translated.

        :param oauthor: The OP of the post, listed as a Reddit username.
        :param opermalink: The permalink of the post that the OP had made.
        :return: Nothing.
        """

        if self.oauthor != "translator-BOT":  # I don't want to message myself.
            translated_subject = (
                "[Notification] Your request has been translated on r/translator!"
            )
            translated_body = (
                MSG_TRANSLATED.format(oauthor=self.oauthor, opermalink=self.opermalink)
                + BOT_DISCLAIMER
            )
            try:
                self.reddit.redditor(self.oauthor).message(
                    subject=translated_subject, message=translated_body
                )
            except praw.exceptions.APIException:  # User doesn't allow for messages.
                pass

        logger.info(
            f"__messaging_translated_message: >> Messaged the OP u/{self.oauthor} "
            "about their translated post."
        )

    def __reference_search(self, lookup_term: str) -> None | str:
        """
        Function to look up reference languages on Ethnologue and Wikipedia.
        This also searches MultiTree (no longer a separate function)
        for languages which may be constructed or dead.
        Due to web settings the live search function of this has been
        disabled.

        :param lookup_term: The language code or text we're looking for.
        :return: A formatted string regardless of whether it found an appropriate match or None.
        """

        # Regex to check if code is in the private use area qaa-qtz
        private_check = re.search("^q[a-t][a-z]$", lookup_term)
        if private_check is not None:
            # This is a private use code. If it's None, it did not match.
            return None  # Just exit.

        # Get the language code (specifically the ISO 639-3 one)
        language_code = convert(lookup_term).language_code
        language_lookup_code = str(language_code)
        if len(language_code) == 2:  # This appears to be an ISO 639-1 code.
            # Get the ISO 639-3 version.
            language_code = MAIN_LANGUAGES[language_code]["language_code_3"]
        if len(language_code) == 4:  # This is a script code.
            return None

        # Correct for macrolanguages. There is frequently no data for their broad codes.
        if language_code in ISO_MACROLANGUAGES:
            # We replace the macrolanguage with the most frequent individual language code. (e.g. 'zho' becomes 'cmn'.)
            language_code = ISO_MACROLANGUAGES[language_code][0]

        # Now we check the database to see if it has data.
        if len(language_code) != 0:  # There's a valid code here.
            logger.info(f"__reference_search Code: {language_lookup_code}")
            self.cursor_main.execute(
                "SELECT language_data FROM language_cache WHERE language_code = ?",
                (language_lookup_code,),
            )
            reference_results = self.cursor_main.fetchone()

            if reference_results is not None:
                # We found a cached value for this language
                reference_cached_info = reference_results["language_data"]
                logger.info(
                    f"Reference: Retrieved the cached reference information for {language_lookup_code}."
                )
                return reference_cached_info

    # This is the basic paging !page function.
    def process_page(self):
        determined_data = comment_info_parser(self.pbody, KEYWORDS.page)
        # This should return what was actually identified. Normally will be a Tuple or None
        if determined_data is None:
            # The command is problematic. Wrong punctuation, not enough arguments
            logger.info("Bot: >> !page data is invalid.")
            return

        # CODE FOR A 14-DAY VERIFICATION SYSTEM
        poster = self.reddit.redditor(name=self.pauthor)
        current_time = int(time.time())
        if current_time - int(poster.created_utc) > 1209600:
            # checks to see if the user account is older than 14 days
            logger.debug(f"Bot: > u/{self.pauthor}'s account is older than 14 days.")
        else:
            self.comment.reply(
                COMMENT_PAGE_DISALLOWED.format(pauthor=self.pauthor) + BOT_DISCLAIMER
            )
            logger.info(
                f"Bot: > However, u/{self.pauthor} is a new account. Replied to them and skipping..."
            )
            return

        if self.oflair_css in ["meta", "community"]:
            logger.debug("Bot: > However, this is not a valid pageable post.")
            return

        # Okay, it's valid, let's start processing data.
        page_results = notifier_page_multiple_detector(self.pbody)

        if page_results is None:
            # There were no valid page results. (it is a placeholder)
            self.comment.reply(
                COMMENT_NO_LANGUAGE.format(
                    pauthor=self.pauthor, language_name="it", language_code=""
                )
                + BOT_DISCLAIMER
            )
            logger.info(
                f"Bot: No one listed. Replied to the pager u/{self.pauthor} and skipping..."
            )
        else:  # There were results. Let's loop through them.
            for result in page_results:
                language_code = result
                language_name = convert(language_code).language_name

                is_nsfw = bool(self.comment.submission.over_18)

                # Send a message via the paging system.
                paged_users = notifier_page_translators(
                    language_code,
                    language_name,
                    self.pauthor,
                    self.otitle,
                    self.opermalink,
                    self.oauthor,
                    is_nsfw,
                    self.config,
                )
                if paged_users is not None:
                    # Add the notified users to the list.
                    self.oajo.add_notified(paged_users)

    """RESTORE COMMAND"""

    # This is the `!restore` command, which can try and check Pushshift data. It can be triggered if user deleted it
    # This command is allowed to be used by people who have either translated the piece or who were notified
    # about it. This is to help resolve the big issue of people deleting their posts.
    def process_restore(self):
        if self.oauthor is not None:
            return

        # This is a link post, we can't retrieve that.
        if not self.osubmission.is_self:
            # Reply and let them know this only works on text-only posts.
            self.comment.reply(MSG_RESTORE_LINK_FAIL + BOT_DISCLAIMER)
            logger.info(f"Bot: {KEYWORDS.restore} request is for a link post. Skipped.")
            return

        try:
            eligible_people = self.oajo.notified
        except AttributeError:
            # Since this is a new attribute it's possible older Ajos don't have it.
            logger.error("Bot: Error retrieving notified list from Ajo.")
            eligible_people = []
        try:  # Get the people who are eligible to check for this.
            eligible_people += self.oajo.recorded_translators
        except AttributeError:
            logger.error("Bot: Error in retrieving recorded translators list from Ajo.")
            return

        # The person asking for a restore isn't eligible for it.
        if self.pauthor not in eligible_people and not self.config.is_mod(self.pauthor):
            # mods should be able to call it.
            logger.info(
                f"Bot: u/{self.pauthor} is not eligible to make a !restore request for this."
            )
            self.comment.reply(MSG_RESTORE_NOT_ELIGIBLE + BOT_DISCLAIMER)
            return
        # Format a search query to Pushshift.
        search_query = (
            f"https://api.pushshift.io/reddit/search/submission/?ids={self.oid}"
        )
        retrieved_data = requests.get(search_query).json()

        if "data" in retrieved_data:  # We've got some data.
            returned_submission = retrieved_data["data"][0]
            original_title = f"> **{returned_submission['title']}**\n\n"
            original_text = returned_submission["selftext"]
            if len(original_text.strip()) > 0:  # We have text.
                original_text = "> " + original_text.strip().replace("\n", "\n > ")
            else:  # The retrieved text is of zero length.
                original_text = "> *It appears this text-only post had no text.*"
            original_text = original_title + original_text
        else:
            # Tell them we were not able to get any proper data.
            subject_line = "[Notification] About your !restore request"
            try:
                self.reddit.redditor(self.pauthor).message(
                    subject=subject_line,
                    message=MSG_RESTORE_TEXT_FAIL.format(self.opermalink),
                )
            except praw.exceptions.APIException:
                pass
            else:
                logger.info(
                    f"Bot: Replied to u/{self.pauthor} with message, "
                    "unable to retrieve data."
                )
            return

        # Actually send them the message, including the original text.
        subject_line = "[Notification] Restored text for your !restore request"
        try:
            self.reddit.redditor(self.pauthor).message(
                subject=subject_line,
                message=MSG_RESTORE_TEXT_TEMPLATE.format(self.opermalink, original_text)
                + BOT_DISCLAIMER,
            )
        except praw.exceptions.APIException:
            pass
        else:
            logger.info(f"Bot: Replied to u/{self.pauthor} with restored text.")

    def process_id(self):
        # This is the general !identify command (synonym: !id)
        determined_data = comment_info_parser(self.pbody, KEYWORDS.identify)
        # This should return what was actually identified. Normally will be a tuple or None.
        if determined_data is None:
            # The command is problematic. Wrong punctuation, not enough arguments
            logger.debug(f"Bot: {KEYWORDS.identify} data is invalid.")
            return

        # Set some defaults just in case. These should be overwritten later.
        match_script = False
        language_code = ""
        language_name = ""

        # If it's not none, we got proper data.
        match = determined_data[0]
        advanced_mode = determined_data[1]
        language_country = None  # Default value
        # Store the original language defined in the Ajo
        o_language_name = str(self.oajo.language_name)
        # This should return a boolean whether it's in advanced mode.

        logger.info(f"Bot: COMMAND: {KEYWORDS.id}, from u/{self.pauthor}.")
        logger.info(f"Bot: {KEYWORDS.id} data is: {determined_data}")

        if "+" not in match:  # This is just a regular single !identify command.
            if not advanced_mode:  # This is the regular results conversion
                language_converter = convert(match)
                language_code = language_converter.language_code
                language_name = language_converter.language_name
                # The country code for the language. Regularly none.
                language_country = language_converter.country_code
                match_script = False
            elif advanced_mode:
                if len(match) == 3:
                    # The advanced mode only accepts codes of a certain length.
                    language_data = lang_code_search(match, False)
                    # Run a search for the specific thing
                    language_code = match
                    language_name = language_data[0]
                    match_script = language_data[1]
                    if len(language_name) == 0:
                        # If there are no results from the advanced converter...
                        language_code = ""
                        # is_supported = False
                elif len(match) == 4:
                    # This is a script, resets it to an Unknown state.
                    language_data = lang_code_search(match, True)
                    # Run a search for the specific script
                    logger.info(f"Bot: Returned script data is for {language_data}.")
                    if language_data is None:  # Probably an invalid script.
                        bad_script_reply = COMMENT_INVALID_SCRIPT + BOT_DISCLAIMER
                        self.comment.reply(bad_script_reply.format(match))
                        logger.info(
                            f"Bot: But '{match}' is not a valid script code. Skipping..."
                        )
                        return
                    language_code = match
                    language_name = language_data[0]
                    match_script = True
                    logger.info(
                        f"Bot: This is a script post with code `{language_code}`."
                    )
                    if len(language_name) == 0:
                        # If there are no results from the advanced converter...
                        language_code = ""
                else:  # a catch-all for advanced mode that ISN'T a 3 or 4-letter code.
                    self.comment.reply(COMMENT_ADVANCED_IDENTIFY_ERROR + BOT_DISCLAIMER)
                    logger.info(
                        "Bot: This is an invalid use of advanced !identify. Skipping this one..."
                    )
                    return

            if not match_script:
                if len(language_code) == 0:
                    # The converter didn't give us any results.
                    no_match_text = COMMENT_INVALID_CODE.format(match, self.opermalink)
                    try:
                        self.comment.reply(no_match_text + BOT_DISCLAIMER)
                    except praw.exceptions.APIException:
                        # Comment has been deleted.
                        pass
                    logger.info(
                        f"Bot: But '{match}' has no match in the database. Skipping this..."
                    )
                    return
                if len(language_code) != 0:  # This is a valid language.
                    # Insert code for updating country as well here.
                    if language_country is not None:
                        # There is a country code listed.
                        # Add that code to the Ajo
                        self.oajo.set_country(language_country)
                    else:  # There was no country listed, so let's reset the code to none.
                        self.oajo.set_country(None)
                    self.oajo.set_language(language_code, True)  # Set the language.
                    logger.info(f"Bot: Changed flair to {language_name}.")
            elif match_script:  # This is a script.
                self.oajo.set_script(language_code)
                logger.info(
                    f"Bot: Changed flair to '{language_name}', with an Unknown+script flair."
                )

            if (
                not match_script
                and o_language_name != self.oajo.language_name
                or not convert(self.oajo.language_name).supported
            ):
                # Definitively a language. Let's archive this to the wiki.
                # We've also made sure that it's not just a change of state, and write to the `identified` page.
                record_to_wiki(
                    odate=int(self.oid),
                    otitle=self.otitle,
                    oid=self.oid,
                    oflair_text=o_language_name,
                    s_or_i=False,
                    oflair_new=self.oajo.language_name,
                    user=self.pauthor,
                    reddit=self.reddit,
                )
        else:  # This is an !identify command for multiple defined languages (e.g. !identify:ru+es+ja
            self.oajo.set_defined_multiple(match)
            logger.info("Bot: Changed flair to a defined multiple one.")

        if (
            KEYWORDS.translated not in self.pbody
            and KEYWORDS.doublecheck not in self.pbody
            and self.oajo.status == "untranslated"
        ):
            # Just a check that we're not sending notifications AGAIN if the identified language is the same as orig
            # This makes sure that they're different languages. So !identify:Chinese on Chinese won't send messages.
            if o_language_name != language_name and MESSAGES_OKAY:
                contacted = ziwen_notifier(
                    f"unknown-{language_code}" if match_script else language_name,
                    self.otitle,
                    self.opermalink,
                    self.oauthor,
                    True,
                    self.config,
                )
                # Notify people on the list if the post hasn't already been marked as translated
                # no use asking people to see something that's translated
                # Add those who have been contacted to the notified list.
                self.oajo.add_notified(contacted)

        # Update the comments with the language reference comment
        if (
            language_code not in ["unknown", "multiple", "zxx", "art", "app"]
            and not match_script
        ):
            komento_data = komento_analyzer(
                self.reddit, komento_submission_from_comment(self.reddit, self.oid)
            )

            if "bot_unknown" in komento_data:
                # Previous Unknown template comment
                unknown_default = komento_data["bot_unknown"]
                unknown_default = self.reddit.comment(id=unknown_default)
                unknown_default.delete()  # Changed from remove
                logger.debug(">> Deleted my default Unknown comment...")
            if "bot_invalid_code" in komento_data:
                invalid_comment = komento_data["bot_invalid_code"]
                invalid_comment = self.reddit.comment(id=invalid_comment)
                invalid_comment.delete()
                logger.debug(">> Deleted my invalid code comment...")
            if "bot_reference" in komento_data:
                # Previous reference template comment
                previous_reference = komento_data["bot_reference"]
                previous_reference = self.reddit.comment(id=previous_reference)
                previous_reference.delete()
                logger.debug(">> Deleted my previous language reference comment...")

    def chinese_matches(self, match, post_content, _key):
        match_length = len(match)
        if match_length == 1:  # Single-character
            to_post = zh_character(match, self.zw_useragent)
            post_content.append(to_post)
        elif match_length >= 2:  # A word or a phrase
            find_word = str(match)
            post_content.append(zh_word(find_word, self.zw_useragent))

        # Create a randomized wait time between requests.
        wait_sec = random.randint(3, 12)
        time.sleep(wait_sec)

    def japanese_matches(self, match, post_content, _key):
        match_length = len(str(match))
        processor = JapaneseProcessor(self.zw_useragent)
        if match_length == 1:
            to_post = processor.ja_character(match)
            post_content.append(to_post)
        elif match_length > 1:
            find_word = str(match)
            post_content.append(processor.ja_word(find_word))

    def korean_matches(self, match, post_content, _key):
        find_word = str(match)
        post_content.append(self.__lookup_wiktionary_search(find_word, "Korean"))

    def other_matches(self, match, post_content, key):
        find_word = str(match)
        wiktionary_results = self.__lookup_wiktionary_search(find_word, key)
        if wiktionary_results is not None:
            post_content.append(wiktionary_results)

    def process_backquote(self):
        # This function returns data for character lookups with `character`.
        if (
            self.pauthor == USERNAME  # Don't respond to !search results from myself.
            or self.oflair_css in ["meta", "community", "missing"]
            or self.oajo.language_name is None
        ):
            return

        if not isinstance(self.oajo.language_name, str):
            # Multiple post?
            search_language = self.oajo.language_name[0]
        else:
            search_language = self.oajo.language_name

        # A dictionary keyed by language and search terms. Built in tokenizers.
        total_matches = lookup_matcher(self.pbody, search_language)

        if len(total_matches.keys()) == 0:
            # Checks to see if there's actually anything in between those two graves.
            # If there's nothing, it skips it.
            logger.debug(
                "Bot: > Received a word lookup command, but found nothing. Skipping..."
            )
            # We are just not going to reply if there is literally nothing found.
            return

        # This section allows for the deletion of previous responses if the content changes.
        komento_data = komento_analyzer(
            self.reddit, komento_submission_from_comment(self.reddit, self.oid)
        )
        if "bot_lookup_correspond" in komento_data:
            # This may have had a comment before.
            relevant_comments = komento_data["bot_lookup_correspond"]

            # This returns a dictionary with the called comment as key.
            for key in relevant_comments:
                if key == self.oid and "bot_lookup_replies" in komento_data:
                    # This is the key for our current comment.
                    # We try to find any corresponding bot replies
                    relevant_replies = komento_data["bot_lookup_replies"]
                    # Previous replies will be a list
                    previous_responses = relevant_replies[self.oid]
                    for response in previous_responses:
                        earlier_comment = self.reddit.comment(id=response)
                        earlier_comment.delete()
                        logger.debug("Bot: >>> Previous response deleted")
                        # We delete the earlier versions.

        limit_num_matches = 5
        logger.info(f"Bot: >> Determined Lookup Dictionary: {total_matches}")
        post_content = []

        for key in total_matches.keys():
            process_func = self.other_matches
            cur_lang = None
            for lang, func in {
                "Chinese": self.chinese_matches,
                "Japanese": self.japanese_matches,
                "Korean": self.korean_matches,
            }.items():
                if key in CJK_LANGUAGES[lang]:
                    process_func = func
                    cur_lang = lang
                    break
            logger.info(
                f"Bot: >> Conducting lookup search in {cur_lang}."
                if cur_lang
                else "Bot: >> Conducting Wiktionary lookup search."
            )
            for match in total_matches[key][:limit_num_matches]:
                process_func(match, post_content, key)

        # Join the content together.
        if post_content:  # If we have results lets post them
            # Join the resulting content together as a string.
            post_content = "\n\n".join(post_content)
        else:  # No results, let's set it to None.
            post_content = None
            # For now we are simply not going to reply if there are no results.

        try:
            if post_content is not None:
                author_tag = (
                    f"*u/{self.oauthor} (OP), the following lookup results "
                    "may be of interest to your request.*\n\n"
                )
                self.comment.reply(author_tag + post_content + BOT_DISCLAIMER)
                logger.info(f"Bot: >> Looked up the term(s) in {search_language}.")
            else:
                logger.info("Bot: >> No results found. Skipping...")
        except praw.exceptions.APIException:  # This means the comment is deleted.
            logger.debug("Bot: >> Previous comment was deleted.")

    def process_reference(self):
        # the !reference command gets information from Ethnologue, Wikipedia, and other sources
        # to post as a reference
        determined_data = comment_info_parser(self.pbody, KEYWORDS.reference)
        # This should return what was actually identified. Normally will be a Tuple or None
        if determined_data is None:
            # The command is problematic. Wrong punctuation, not enough arguments
            logger.debug("Bot: >> !reference data is invalid.")
            return

        language_match = determined_data[0]
        post_content = self.__reference_search(language_match)
        if post_content is None:
            # There was no good data. We return the invalid comment.
            post_content = COMMENT_INVALID_REFERENCE
        self.comment.reply(post_content)
        logger.info(f"Bot: Posted the reference results for '{language_match}'.")

    # The !search function looks for strings in other posts on r/translator
    def process_search(self):
        determined_data = comment_info_parser(self.pbody, f"{KEYWORDS.search}:")
        # This should return what was actually identified. Normally will be a Tuple or None
        if determined_data is None:
            # The command is problematic. Wrong punctuation, not enough arguments
            logger.debug(f"Bot: >> {KEYWORDS.search} data is invalid.")
            return

        search_term = determined_data[0]

        google_url = []
        reddit_id = []
        reply_body = []

        for url in googlesearch.search(
            search_term + " site:reddit.com/r/translator", num=4, stop=4
        ):
            if "comments" not in url:
                continue
            google_url.append(url)
            oid = re.search(r"comments/(.*)/\w", url).group(1)
            reddit_id.append(oid)

        if len(google_url) == 0:
            self.comment.reply(COMMENT_NO_RESULTS + BOT_DISCLAIMER)
            logger.info(f"Bot: > There were no results for {search_term}. Moving on...")
            return

        for oid in reddit_id:
            submission = self.reddit.submission(id=oid)
            s_title = submission.title
            s_date = datetime.datetime.fromtimestamp(submission.created).strftime(
                "%Y-%m-%d"
            )
            s_permalink = submission.permalink
            header_string = f"#### [{s_title}]({s_permalink}) ({s_date})\n\n"
            reply_body.append(header_string)
            submission.comments.replace_more(limit=None)
            s_comments = submission.comments.list()

            for comment in s_comments:
                try:
                    c_author = comment.author.name
                except AttributeError:
                    # Author is deleted. We don't care about this comment.
                    continue

                if c_author == USERNAME:  # I posted this comment.
                    continue
                # This contains the !search string.
                if KEYWORDS.search in comment.body.lower():
                    continue  # We don't want this.

                # Format a comment body nicely.
                c_body = comment.body

                # Replace any keywords
                for keyword in KEYWORDS:
                    c_body = c_body.replace(keyword, "")
                c_body = str("\n> ".join(c_body.split("\n")))
                # Indent the lines with Markdown >
                c_votes = str(comment.score)  # Get the score of the comment

                if search_term.lower() in c_body.lower():
                    comment_string = (
                        f"##### Comment by u/{c_author} (+{c_votes}):\n\n>{c_body}"
                    )
                    reply_body.append(comment_string)
                    continue

        reply_body = "\n\n".join(reply_body[:6])
        # Limit it to 6 responses. To avoid excessive length.
        self.comment.reply(
            f'## Search results on r/translator for "{search_term}":\n\n{reply_body}'
        )
        logger.info("Bot: > Posted my findings for the search term.")

    # asking for reviews of one's work.
    def process_doublecheck(self):
        current_time = int(time.time())
        if self.oajo.type == "multiple":
            if isinstance(self.oajo.language_name, list):
                # It is a defined multiple post.
                # Try to see if there's data in the comment.
                # If the comment is just the command, we take the parent comment and together check to see.
                checked_text = str(self.pbody_original)
                if len(self.pbody) < 12:
                    # This is just the command, so let's get the parent comment.
                    # Get the parent comment
                    parent_item = self.comment.parent_id
                    if "t1" in parent_item:  # The parent is a comment
                        parent_comment = self.comment.parent()
                        # Combine the two together.
                        checked_text = f"{parent_comment.body} {self.pbody_original}"

                comment_check = ajo_defined_multiple_comment_parser(
                    checked_text, self.oajo.language_name
                )

                # We have data, we can set the status as different in the flair.
                if comment_check is not None:
                    # Start setting the flairs, from a list.
                    for language in comment_check[0]:
                        language_code = convert(language).language_code
                        self.oajo.set_status_multiple(language_code, "doublecheck")
                        logger.info(
                            f"Bot: > {language} in defined multiple post for doublechecking"
                        )
            else:
                logger.info(
                    "Bot: > This is a general multiple post that is not eligible for status changes."
                )
        elif self.oflair_css in ["translated", "meta", "community", "doublecheck"]:
            logger.info(
                "Bot: > This post isn't eligible for double-checking. Skipping this one..."
            )
            return
        else:
            self.oajo.set_status("doublecheck")
            self.oajo.set_time("doublecheck", current_time)
            logger.info("Bot: > Marked post as 'Needs Review.'")

        # Delete any claimed comment.
        komento_data = komento_analyzer(self.reddit, self.osubmission)
        if "bot_claim_comment" in komento_data:
            claim_comment = komento_data["bot_claim_comment"]
            claim_comment = self.reddit.comment(claim_comment)
            claim_comment.delete()

    # Picks up a !missing command and messages the OP about it.
    def process_missing(self):
        current_time = int(time.time())
        if not css_check(self.oflair_css):
            # Basic check to see if this is something that can be acted on.
            return
        total_message = MSG_MISSING_ASSETS.format(
            oauthor=self.oauthor, opermalink=self.opermalink
        )
        try:
            self.reddit.redditor(self.oauthor).message(
                subject="A message from r/translator regarding your translation request",
                message=total_message + BOT_DISCLAIMER,
            )
        except praw.exceptions.APIException:
            pass
        # Send a message to the OP about their post missing content.

        self.oajo.set_status("missing")
        self.oajo.set_time("missing", current_time)
        logger.info(
            f"Bot: > Marked a post by u/{self.oauthor} as missing assets and messaged them."
        )

    def process_claim(self):
        # Claiming posts with the !claim command
        if self.oflair_css in [
            "translated",
            "doublecheck",
            "community",
            "meta",
            "multiple",
            "app",
        ]:
            # We don't want to process these posts.
            return
        # ignore when someone edits their claim with translated or doublecheck
        if KEYWORDS.translated in self.pbody or KEYWORDS.doublecheck in self.pbody:
            return

        current_time = int(time.time())
        utc_timestamp = datetime.datetime.utcfromtimestamp(current_time).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        claimed_already = False  # Boolean to see if it has been claimed as of now.

        komento_data = komento_analyzer(self.reddit, self.osubmission)

        if "bot_claim_comment" in komento_data:  # Found an already claimed comment
            # claim_comment = komento_data['bot_claim_comment']
            claimer_name = komento_data["claim_user"]
            remaining_time = komento_data["claim_time_diff"]
            remaining_time_text = str(datetime.timedelta(seconds=remaining_time))
            if self.pauthor == claimer_name:
                # If it's another claim by the same person listed...
                self.comment.reply("You've already claimed this post." + BOT_DISCLAIMER)
                claimed_already = True
                logger.info(
                    "Bot: >> But this post is already claimed by them. Replied to them."
                )
            else:
                self.comment.reply(
                    COMMENT_CURRENTLY_CLAIMED.format(
                        claimer_name=claimer_name,
                        remaining_time=remaining_time_text,
                    )
                    + BOT_DISCLAIMER
                )
                claimed_already = True
                logger.info(
                    "Bot: >> But this post is already claimed. Replied to the claimer about it."
                )

        if not claimed_already:
            # This has not yet been claimed. We can claim it for the user.
            self.oajo.set_status("inprogress")
            self.oajo.set_time("inprogress", current_time)
            claim_note = self.osubmission.reply(
                COMMENT_CLAIM.format(
                    claimer=self.pauthor,
                    time=utc_timestamp,
                    language_name=self.oajo.language_name,
                )
                + BOT_DISCLAIMER
            )
            claim_note.mod.distinguish(sticky=True)  # Distinguish the bot's comment
            logger.info(
                f"Bot: > Marked a post by u/{self.oauthor} as claimed and in progress."
            )

    # This is a !translated function that messages people when their post has been translated.
    def process_translated(
        self,
    ):
        current_time = int(time.time())  # This is the current time.
        thanks_already = False
        translated_found = True

        if self.oflair_css is None:  # If there is no CSS flair...
            self.oflair_css = "generic"  # Give it a generic flair.

        if self.oajo.type == "multiple":
            if isinstance(self.oajo.language_name, list):
                # It is a defined multiple post.
                # Try to see if there's data in the comment.
                # If the comment is just the command, we take the parent comment and together check to see.
                checked_text = str(self.pbody_original)
                if len(self.pbody) < 12:
                    # This is just the command, so let's get the parent comment.
                    # Get the parent comment
                    parent_item = self.comment.parent_id
                    if "t1" in parent_item:  # The parent is a comment
                        parent_comment = self.comment.parent()
                        # Combine the two together.
                        checked_text = f"{parent_comment.body} {self.pbody_original}"

                comment_check = ajo_defined_multiple_comment_parser(
                    checked_text, self.oajo.language_name
                )

                # We have data, we can set the status as different in the flair.
                if comment_check is not None:
                    # Start setting the flairs, from a list.
                    for language in comment_check[0]:
                        language_code = convert(language).language_code
                        self.oajo.set_status_multiple(language_code, "translated")
                        logger.info(
                            f"Bot: > Marked {language} in this defined multiple post as done."
                        )
            else:
                logger.debug(
                    "Bot: > This is a general multiple post that is not eligible for status changes."
                )
        elif self.oflair_css not in ["meta", "community", "translated"]:
            # Make sure we're not altering certain flairs.
            self.oajo.set_status("translated")
            self.oajo.set_time("translated", current_time)
            logger.info("Bot: > Marked post as translated.")

        komento_data = komento_analyzer(self.reddit, self.osubmission)

        if self.oajo.is_bot_crosspost and "bot_xp_original_comment" in komento_data:
            logger.debug("Bot: >> Fetching original crosspost comment...")
            original_comment = self.reddit.comment(
                komento_data["bot_xp_original_comment"]
            )
            original_comment_text = original_comment.body

            # We want to strip off the disclaimer
            original_comment_text = original_comment_text.split("---")[0].strip()

            # Add the edited text
            edited_header = "\n\n**Edit**: This crosspost has been marked as translated on r/translator."
            original_comment_text += edited_header + BOT_DISCLAIMER
            if "**Edit**" not in original_comment.body:
                # Has this already been edited?
                original_comment.edit(original_comment_text)
                logger.debug(
                    "Bot: >> Edited my original comment on the other subreddit to alert people."
                )

        if "bot_long" in komento_data:  # Found a bot (Long) comment, delete it.
            long_comment = komento_data["bot_long"]
            long_comment = self.reddit.comment(long_comment)
            long_comment.delete()
        if "bot_claim_comment" in komento_data:
            # Found an older claim comment, delete it.
            claim_comment = komento_data["bot_claim_comment"]
            claim_comment = self.reddit.comment(claim_comment)
            claim_comment.delete()
        if "op_thanks" in komento_data:
            # OP has thanked someone in the thread before.
            thanks_already = True
            translated_found = False

        if (
            translated_found
            and not thanks_already
            and self.oflair_css not in ["multiple", "app"]
        ):
            # First we check to see if the author has already been recorded as getting a message.
            messaged_already = getattr(self.oajo, "author_messaged", False)

            # If the commentor is not the author of the post and they have not been messaged, we can tell them.
            if self.pauthor != self.oauthor and not messaged_already:
                # Sends them notification msg
                self.__messaging_translated_message()
                self.oajo.set_author_messaged(True)

    def process_delete(self):
        # This is to allow OP or mods to !delete crossposts
        if not self.oajo.is_bot_crosspost:  # If this isn't actually a crosspost..
            return
        # This really is a crosspost.
        if (
            self.pauthor == self.oauthor
            or self.pauthor == self.requester
            or self.config.is_mod(self.pauthor)
        ):
            self.osubmission.mod.remove()  # We'll use remove for now -- can switch to delete() later.
            logger.info("Bot: >> Removed crosspost.")

    def process_reset(self):
        # !reset command, to revert a post back to as if it were freshly processed
        if self.config.is_mod(self.pauthor) or self.pauthor == self.oauthor:
            # Check if user is a mod or the OP.
            self.oajo.reset(self.otitle)
            logger.info("Bot: > Reset everything for the designated post.")

    # !long command, for mods to mark a post as long for translators.
    def process_long(self):
        if not self.config.is_mod(self.pauthor):
            return
        # This command works as a flip switch. It changes the state to the opposite.
        current_status = self.oajo.is_long
        new_status = not current_status

        # Delete any long informational comment.
        komento_data = komento_analyzer(
            self.reddit, komento_submission_from_comment(self.reddit, self.oid)
        )
        if "bot_long" in komento_data:
            long_comment = self.reddit.comment(id=komento_data["bot_long"])
            long_comment.delete()
            logger.debug("Bot: Deleted my default long comment...")

        # Set the status
        self.oajo.set_long(new_status)
        logger.info(f"Bot: Changed the designated post's long state to '{new_status}.'")

    # the !note command saves posts which are not CSS/template supported so they can be used as reference.
    # This is now rarely used.
    def process_note(self):
        if not self.config.is_mod(self.pauthor):
            # Check to see if the person calling this command is a moderator
            return
        match = comment_info_parser(self.pbody, KEYWORDS.note)[0]
        language_name = convert(match).language_name
        # Write to the saved page
        record_to_wiki(
            odate=int(self.oid),
            otitle=self.otitle,
            oid=self.oid,
            oflair_text=language_name,
            s_or_i=True,
            oflair_new="",
            reddit=self.reddit,
        )

    def process_set(self):
        # !set is a mod-accessible means of setting the post flair.
        # It removes the comment (through AM) so it looks like nothing happened.
        if not self.config.is_mod(self.pauthor):
            # Check to see if the person calling this command is a moderator
            return

        set_data = comment_info_parser(self.pbody, KEYWORDS.set)

        if set_data is not None:  # We have data.
            match = set_data[0]
            reset_state = set_data[1]
        else:  # Invalid command (likely did not include a language)
            return

        language_converter = convert(match)
        language_code = language_converter.language_code
        language_name = language_converter.language_name
        language_country = language_converter.country_code

        if language_country is not None:  # There is a country code listed.
            self.oajo.set_country(language_country)  # Add that code to the Ajo

        if reset_state:  # Advanced !set mode, we set it to untranslated.
            self.oajo.set_status("untranslated")

        if "+" not in set_data[0]:  # This is a standard !set
            # Set the language to the Ajo
            self.oajo.set_language(language_code)
            komento_data = komento_analyzer(
                self.reddit, komento_submission_from_comment(self.reddit, self.oid)
            )
            if "bot_unknown" in komento_data:
                # Delete previous Unknown template comment
                unknown_default = komento_data["bot_unknown"]
                unknown_default = self.reddit.comment(id=unknown_default)
                unknown_default.delete()  # Changed from remove
                logger.debug("Bot: >> Deleted my default Unknown comment...")
            logger.info(f"Bot: > Updated the linkflair tag to '{language_code}'.")
        else:  # This is a defined multiple !set
            self.oajo.set_defined_multiple(set_data[0])
            logger.info("Bot: > Updated the post to a defined multiple one.")

        # Message the mod who called it.
        set_msg = f"The [post]({self.opermalink}) has been set to the language code `{language_code}` (`{language_name}`)."
        self.reddit.redditor(self.pauthor).message(
            subject="[Notification] !set command successful", message=set_msg
        )
