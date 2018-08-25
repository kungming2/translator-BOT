#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""
Ziwen Streamer [ZWS] is a separate component of Ziwen that monitors *all* Reddit commands for certain keywords.
Its primary responsibilities are to watch for crossposting commands and mentions of the subreddit.

Ziwen Streamer is much simpler than the main routine and does not rely on any local databases, and it also has a
separate app ID key than the main one with which it connects to Reddit.
"""

import datetime
import time
import traceback

import praw
import prawcore

# Import local components.
from _config import *
from _responses import *
from _languages import *

# Dynamically change which subreddit to crosspost to.
if sys.platform == "linux":  # Linux
    SUBREDDIT = "translator"
else:  # Windows, testing.
    SUBREDDIT = 'trntest'


'''KEYWORDS LISTS'''
# The keywords Ziwen Streamer watches for.
STREAMER_KEYWORDS = ['!translate', '!translator', 'r/translate', 'r/translator']
# These are keywords we DON'T want to match for r/translate correction. Mostly Internet TLDs and one subreddit.
EXCLUDED_DETECT_KEYWORDS = ['.fr', '.ar', '.cr', '.gr', '.ir', '.nr', '.tr', '.kr', 'r/translater']
# These are subreddits to ignore when tracking mentions of r/translator.
EXCLUDED_MENTION_SUBREDDITS = ["r/translator", "r/translatorbot"]
# These are users to ignore when tracking mentions of r/translator.
EXCLUDED_MENTION_USERS = ["AutoModerator", "translator-BOT", "kungming2", "ImagesOfNetwork", "TrendingCommenterBot",
                          "TotesMessenger", "sneakpeekbot", "ContentForager", "transcribot", "SmallSubBot"]

BOT_NAME = 'Ziwen Streamer'
VERSION_NUMBER = '1.1.20'
USER_AGENT = ('{} {}, a runtime to watch comments on Reddit for reposting translation requests to r/translator. '
              'Written and maintained by u/kungming2.'.format(BOT_NAME, VERSION_NUMBER))


'''CONNECTING TO REDDIT'''
logger.info('[ZWS] Startup: Logging in as u/{}...'.format(USERNAME))
reddit = praw.Reddit(client_id=ZIWEN_STREAMER_APP_ID,
                     client_secret=ZIWEN_STREAMER_APP_SECRET, password=PASSWORD,
                     user_agent=USER_AGENT, username=USERNAME)
r = reddit.subreddit(SUBREDDIT)
logger.info('[ZWS] Startup: Initializing {} {} for r/{} with languages module {}.'.format(BOT_NAME, VERSION_NUMBER,
                                                                                          SUBREDDIT,
                                                                                          VERSION_NUMBER_LANGUAGES))


def first_user_check(username):
    """
    A function that conducts a quick check as to whether someone posted on r/translator before.

    :return: Returns True if they have, False if they have not.
    """

    past_subreddits = []

    try:
        for submission in reddit.redditor(username).submissions.new(limit=200):
            # Check the last two hundred submissions of a user, see if they have submitted to our sub before.
            ssubreddit = submission.subreddit_name_prefixed[2:]  # Get the raw name of the subreddit.
            past_subreddits.append(ssubreddit)
            if ssubreddit == "translator":
                return True
            else:
                continue
        if "translator" not in past_subreddits:
            return False
    except prawcore.exceptions.NotFound:
        return False


def is_user_mod(username, subreddit_name):
    """
    This function checks to see if a user is a moderator in the sub they posted in.

    :param username: The username of the person.
    :param subreddit_name: The subreddit in which they posted a comment.
    :return: True if they are a moderator, False if they are not.
    """

    moderators_list = []  # Make a list of the subreddit moderators.

    for moderator in reddit.subreddit(subreddit_name).moderator():
        moderators_list.append(moderator.name.lower())

    if username.lower() in moderators_list:
        return True
    else:
        return False


def blacklist_checker(b_username, b_subreddit):
    """
    This is a function that checks if a user or subreddit is blacklisted.
    Blacklisted users are users who have abused the crossposting function or the subreddit's rules.
    Blacklisted subreddits are subreddits where use of crossposting commands would cause problems.
    (e.g. r/duckduckgo, as !translate is a DuckDuckGo command)

    :param b_username: The username we're checking against.
    :param b_subreddit: The subreddit we're checking against.
    :return: True if it matches *either* criterion.
    """

    b_username = b_username.lower()
    b_subreddit = b_subreddit.lower()

    blacklist_page = reddit.subreddit("translatorBOT").wiki["blacklist"]  # Retrieve the page.
    overall_page_content = str(blacklist_page.content_md)
    usernames_raw = overall_page_content.split("####")[1]
    usernames_raw = usernames_raw.split("\n")[2].strip()  # Get just the usernames.
    subreddits_raw = overall_page_content.split("####")[2]
    subreddits_raw = subreddits_raw.split("\n")[2].strip()  # Get just the subreddits.
    blacklist_usernames = usernames_raw.split(", ")
    blacklist_usernames = [item.lower() for item in blacklist_usernames]  # Convert to lowercase.

    blacklist_subreddits = subreddits_raw.split(", ")
    blacklist_subreddits = [item.lower() for item in blacklist_subreddits]

    if b_username in blacklist_usernames:
        return True

    if b_subreddit in blacklist_subreddits:
        return True
    else:
        return False


def streamer_duplicate_checker(post_author, original_title):
    """
    Function to check if something has been submitted by the bot for a crosspost to r/translator before.
    This is meant to work with both text-only (self) posts and link posts.

    :param post_author: The post's original author (that is, not the bot).
    :param original_title: The original title of the post.
    :return: True if this post has been posted before, and False if it hasn't.
    """
    
    # A list where we put the titles of things that match. 
    matching_list = []
    fuzz_values = []
    
    # Conduct a search checking the author of this post. 
    # Generally the author posts in a similar time period. 
    search_query = "author:{} OR author:translator-BOT NOT flair:community NOT flair:meta".format(post_author)
    search_results = r.search(search_query, sort='new', time_filter='week', limit=3)
    
    # If there are results, we add them to the list. 
    for result in search_results:
        rtitle = result.title
        
        # If there are brackets in the result titles let's remove them for a more accurate fuzz ratio.
        if "]" in rtitle:
            rtitle = re.sub("\[[^)]*\]", "", rtitle).strip()
        
        # Add the title to the list (sans brackets)
        matching_list.append(rtitle)
    
    # There are items that match my criteria.
    if len(matching_list) > 0:
        
        # Iterate over the titles, compare them to the original title to see how close they are.
        for title in matching_list:
            closeness = fuzz.ratio(original_title, title)
            # print(closeness)
            fuzz_values.append(closeness)
        
        # If there's something over 80 fuzz value, it's probably a match.
        if max(fuzz_values) > 80:
            return True
        else:
            return False
    else:
        return False


def ziwen_streamer():
    """
    The main monitoring function for Ziwen Streamer. It was split off from the main runtime to enable independent
    crossposting from anywhere on Reddit.
    This function also watches for mentions of the subreddit as an in-house self-written version of r/Sub_Notifications.
    Ziwen Streamer also posts corrections if people accidentally link to r/translate instead, as it is a subreddit that
    is frequently mistaken for r/translator (and redirects there).

    :return: Nothing.
    """

    logger.info("[ZWS] Streamer routine starting up...")

    for comment in reddit.subreddit('all').stream.comments():  # Watching the stream...

        pbody = comment.body.lower()

        if not any(key.lower() in pbody for key in STREAMER_KEYWORDS):
            # Does not contain our keyword
            continue

        if STREAMER_KEYWORDS[2] in pbody:  # for r/translate checks...
            if any(key.lower() in pbody for key in EXCLUDED_DETECT_KEYWORDS):
                # Contains an UNWANTED KEYWORD:
                continue

        oid = comment.link_id[3:]  # Get the six-character submission ID of the comment.
        cid = comment.id
        cpermalink = comment.permalink  # Get the direct link to the comment.

        osubmission = reddit.submission(id=oid)  # Returns a submission object to work with
        opermalink = osubmission.permalink
        oreddit = osubmission.subreddit_name_prefixed  # Returns in the format r/SUBREDDIT
        ois_self = osubmission.is_self  # Is it a text only post?
        otitle = original_title = osubmission.title
        # outc = osubmission.created_utc  # When the post was created.
        is_valid = True
        reverse_mode = False

        try:
            pauthor = comment.author.name
        except AttributeError:
            # Author is deleted. We don't care about this post.
            continue

        if pauthor == USERNAME:
            # Don't reply to yourself, bot!
            continue

        if 'r/translator' == oreddit:  # If the cross-posting thing is called on r/translator itself... Skip.
            continue

        # ADD CHECK FOR COMMANDS THAT ARE LONGER AND NOT EXACT (say !translateme, or !translators)
        if STREAMER_KEYWORDS[0] in pbody or STREAMER_KEYWORDS[1] in pbody:
            if '!translate' in pbody and "!translate:" not in pbody:
                accurate_test = pbody.split("!translate", 1)[1]
                if accurate_test == "" or accurate_test[0] == " ":
                    is_valid = True
                else:
                    is_valid = False
            elif '!translator:' in pbody and "!translator:" not in pbody:  # There is no specific crosspost.
                accurate_test = pbody.split("!translator", 1)[1]
                if accurate_test == "" or accurate_test[0] == " ":
                    is_valid = True
                else:
                    is_valid = False

        if not is_valid:  # This looks like it's a longer comment.
            continue  # Skip it.

        try:
            oauthor = osubmission.author.name  # Check to see if the author of the original post exists
        except AttributeError:  # The author does not exist.
            continue

        # Check if the username or the subreddit is on the blacklist. True if the user is on the blacklist.
        blacklist_requester_test = blacklist_checker(b_username=pauthor.lower(), b_subreddit=oreddit.lower())
        blacklist_op_test = blacklist_checker(b_username=oauthor.lower(), b_subreddit=oreddit.lower()) 
        
        # If either are on the blacklist (that is, either are True), skip.
        if blacklist_requester_test or blacklist_op_test:
            if STREAMER_KEYWORDS[2] not in pbody and pauthor != "AutoModerator":  # Exclude r/translate mentions
                # print("> User or subreddit is on my blacklist. See link at https://redd.it/{}.".format(oid))
                logger.info("[ZWS] > User/subreddit is blacklisted. See https://www.reddit.com{}.".format(opermalink))
                continue

        if '!translated' in pbody:  # Let's not cross post if it's an accidental use of this command.
            if 'trntest' not in opermalink:  # No need to note test commands.
                logger.info("[ZWS] > This is probably an accidental use of an r/translator command outside the "
                            "subreddit at https://www.reddit.com{}\n".format(opermalink))
            continue

        if ois_self:
            if "[removed]" in osubmission.selftext:  # If it's removed... Skip
                continue

        if "[" in otitle and "]" in otitle:
            # If it's a cross-post from certain other subreddits (like r/translation), it may have a tag. Take it out.
            otitle = re.sub("\[[^)]*\]", "", otitle).strip()  # Take the tag out through regex.

        if oreddit in TESTING_SUBREDDITS and SUBREDDIT != "trntest":  # This is a subreddit we don't need to note.
            continue

        if STREAMER_KEYWORDS[0] in pbody or STREAMER_KEYWORDS[1] in pbody:
            parent_comment_mode = False
            parent_comment_text = None

            # The new spoiler syntax is something we want to avoid.
            if ">!trans" in pbody:
                logger.info("[ZWS] Crosspost request seems to be a spoiler syntax comment. See {}".format(opermalink))
                continue

            logger.info("[ZWS] COMMAND: Crosspost request from u/{} on {} at {}".format(pauthor, oreddit, opermalink))
            if '!translate:' in pbody or '!translator:' in pbody:  # Try to get the language if it's mentioned
                match_data = None

                if STREAMER_KEYWORDS[0] in pbody:
                    match_data = comment_info_parser(pbody, '!translate:')
                elif STREAMER_KEYWORDS[1] in pbody:
                    match_data = comment_info_parser(pbody, '!translator:')

                if match_data is not None:  # We found a language included.
                    match = match_data[0]  # Get the data from the parser.

                    if "<" in match:  # This is a request to translate the other way (English > Greek)
                        match = match.replace("<", "")
                        reverse_mode = True
                    if "^" in match:
                        match = match.replace("^", "")
                        parent_comment_mode = True

                    if '`' in match:
                        match = match.replace("`", "")  # Delete grave accents if they exist in the match
                    if '.' in match:
                        match = match.replace(".", "")  # Delete periods if they exist
                    if ',' in match:
                        match = match.replace(",", "")  # Delete commas if they exist
                    if ':' in match:
                        match = match.replace(":", "")  # Delete colons if they exist
                else:  # If nothing else, we classify it as Unknown.
                    match = "Unknown"

                language_name = converter(match)[1]

                if not reverse_mode:  # Regular mode, translate to English is more popular.
                    new_title = "[{} > English] {}".format(language_name, otitle)
                else:  # Translate to another language from English.
                    new_title = "[English > {}] {}".format(language_name, otitle)

                    logger.info("[ZWS] > The requested crosspost is for '{}'.".format(language_name))
                if language_name == "":  # Couldn't find anything. Let's choose to post it as Unknown.
                    logger.info("[ZWS] >> Couldn't determine the language name. Posting as 'Unknown.'")
                    language_name = "Unknown"
                    new_title = "[Unknown > English] {}".format(otitle)
            else:  # There is no inherent language included in the command.
                if '!translate^' in pbody or '!translator^' in pbody:
                    parent_comment_mode = True

                returned_languages = language_mention_search(original_title.title())
                # Will be a list of detected languages. Let's see if one is in the title.
                if returned_languages is not None:  # There is a language detected in the title of the post.
                    returned_languages = [x for x in returned_languages if x != "English"]
                    # But we don't want English to be a part of this.
                else:  # Leave it blank
                    returned_languages = []

                if len(returned_languages) > 0:  # If there's actually a detected language in the title...
                    language_name = returned_languages[0]
                    new_title = "[" + language_name + " > English] " + otitle  # + " (x-post " + oreddit + ")"
                else:
                    # Can't find a language in the title.
                    # Let's check source against a hard list of language subreddits, or call it unknown.
                    keys = [key for key, value in LANGUAGE_SUBREDDITS.items() if
                            oreddit.lower() in value]  # check to see if subreddit is in our list.

                    if len(keys) != 0:  # We have a match.
                        language_name = keys[0]  # Get the language name as the key of the dictionary listing
                        logger.info("[ZWS] >> Post is on {}. Classifying as {}.".format(oreddit, language_name))
                        new_title = "[" + language_name + " > English] " + otitle
                    else:
                        new_title = "[Unknown > English] " + otitle  # + " (x-post " + oreddit + ")"
                        language_name = "Unknown"

            if len(new_title) > 299:  # If the title is too long and will bump up against the limit, shorten it.
                new_title = new_title[0:296] + "..."

            if new_title is "[English > English] ":  # For some reason, the cross-post is just English
                comment.reply(ZWS_COMMENT_ENGLISH_ONLY + BOT_DISCLAIMER)
                continue

            # Test to see if it was previously posted. True if it was, False if it wasn't.
            posted_before = streamer_duplicate_checker(oauthor, otitle)

            # If this is a request to cross-post a comment... (!translate:ar^) We want to format it nicer.
            if parent_comment_mode:
                parent_item = comment.parent_id
                if "t1" in parent_item:  # The parent is a comment
                    parent_comment = comment.parent()
                    parent_comment_text = parent_comment.body
                    cpermalink += '?context=1'  # This allows for the wholle link to be seen in context
                    oauthor = parent_comment.author.name  # Change the author to the parent commentor
                    new_title = new_title.split("]", 1)[0] + "] Comment from {}".format(oreddit)  # Change the title
                else:  # The parent of this comment is a post.
                    comment.reply(ZWS_COMMENT_WRONG_XPOST_COMMENT + BOT_DISCLAIMER)
                    continue

            # If it hasn't been posted before, go ahead. 
            if not posted_before and not parent_comment_mode:  # Regular submission
                cross_post = osubmission.crosspost(SUBREDDIT, title=new_title, send_replies=False)
            elif not posted_before and parent_comment_mode and parent_comment_text is not None:
                # We want to crosspost the parent comment, using its text as a new post.
                cross_post = r.submit(title=new_title, selftext=parent_comment_text, send_replies=False)
            else:
                comment.reply(ZWS_COMMENT_ALREADY_POSTED + BOT_DISCLAIMER)
                logger.info("[ZWS] >> Text has already been posted. Skipping...")
                continue
            
            # Get the permalink for the new crosspost.
            xlink = cross_post.permalink

            # Add a comment to the r/translator page detailing the info.
            detail_comment = ZWS_COMMENT_XPOST.format(original_author=oauthor, subreddit=oreddit,
                                                      cpermalink=cpermalink, requester=pauthor)
            cross_post_note = cross_post.reply(detail_comment + BOT_DISCLAIMER)

            # Distinguish the comment and make it nice and green.
            cross_post_note.mod.distinguish(how="yes", sticky=False)

            # Write to the action log.
            action_counter(1, "Crosspost")
            logger.info("[ZWS] > Cross-posted to r/" + SUBREDDIT + ".")

            # Find native-language thanks and such.
            if language_name in THANKS_WORDS:  # Do we have a thank you word for this?
                thanks_phrase = THANKS_WORDS.get(language_name)  # Get the custom thank you phrase.
                try:
                    comment.reply(ZWS_COMMENT_XPOST_THANKS.format(thanks_phrase, language_name, xlink) + BOT_DISCLAIMER)
                    # Put the reply last in case of ban
                    logger.debug("[ZWS] >> Replied with a custom confirmation comment to the requester.")
                except praw.exceptions.APIException:  # The comment was deleted
                    logger.error("[ZWS] >> The original command appears to have been deleted.")
            else:
                try:
                    thanks_phrase = "Thank you"
                    comment.reply(ZWS_COMMENT_XPOST_THANKS.format(thanks_phrase, language_name, xlink) + BOT_DISCLAIMER)
                    # Put the reply last in case of ban
                    logger.debug("[ZWS] >> Replied with a confirmation comment to the requester.")
                except praw.exceptions.APIException:  # The comment was deleted
                    logger.error("[ZWS] >> The original command appears to have been deleted.")
            logger.info("[ZWS] >> Added a comment crediting the OP u/" + oauthor + ".")
        elif STREAMER_KEYWORDS[2] in pbody:  # Someone accidentally referenced r/translate instead (this is a redirect).
            # Double check to make sure it's actually a mistaken link to our subreddit.
            # Run a regex search to see if it's a right and proper mention.
            check = re.search(r"(?:\b|\s+|/)(r/translate(?:\s|\b))", pbody)
            if check is not None:
                act_on = True
                logger.info("[ZWS] > r/translate reference detected at https://www.reddit.com/{}.".format(opermalink))
            else:
                act_on = False

            if not act_on:  # No triggers were made. Don't do anything.
                continue
            else:
                if "r/translator" not in pbody:
                    # Just in case they also mentioned the proper subreddit.
                    time.sleep(180)  # Wait for 3-minutes in case of edit
                    print(">> Waiting 3 minutes for possible edits...")
                    new_comment = reddit.comment(cid)
                    new_comment = new_comment.body.lower()
                    if "r/translator" not in new_comment:
                        try:
                            comment.reply(ZWS_COMMENT_WRONG_SUBREDDIT)
                            logger.info("[ZWS] >> Posted a correction reply.\n")
                        except praw.exceptions.APIException:  # The comment had been deleted.
                            logger.info("[ZWS] >> Original mention comment has been deleted. Skipping...")
        elif STREAMER_KEYWORDS[3] in pbody:
            # Someone mentioned our subreddit!

            if pauthor in EXCLUDED_MENTION_USERS:  # This is a user we don't need to note.
                continue

            if oreddit.lower() in EXCLUDED_MENTION_SUBREDDITS:  # This is a subreddit we don't need to note.
                continue

            test_chunk = pbody.split("r/translator", 1)[0]  # Double check to make sure it's actually a sub link.
            act_on = False

            if test_chunk == "":
                act_on = True
            elif test_chunk[-1] == "/" or test_chunk[-1] == " ":
                act_on = True

            if not act_on:
                continue

            logger.info("[ZWS] > r/translator reference detected at https://www.reddit.com/{}.".format(opermalink))
            clink = comment.permalink
            screated = comment.created_utc
            s_format_created = str(datetime.datetime.fromtimestamp(screated).strftime("%Y-%m-%d [%I:%M:%S %p]"))
            has_posted_before = first_user_check(pauthor)

            try:
                is_mod_data = is_user_mod(username=pauthor, subreddit_name=oreddit[2:])
                # Check if the user is a moderator of said sub
            except prawcore.exceptions.Redirect:  # Invalid subreddit name for some reason
                is_mod_data = False

            if is_mod_data:
                pauthor += " (mod)"

            if oauthor == pauthor:
                pauthor += " (OP)"

            otitle = otitle.replace("|", "-")  # Replace pipes, they can be problematic. 
            page_content = reddit.subreddit("translatorBOT").wiki["mentions"]
            new_content_template = "{} | {} | u/{} | {} | [{}]({}) | [Link]({})"
            new_content = (new_content_template.format(s_format_created, oreddit, pauthor, has_posted_before, otitle,
                                                       opermalink, clink))

            # Adds this language entry to the 'mentions page'
            page_content_new = str(page_content.content_md) + '\n' + new_content
            try:
                page_content.edit(content=page_content_new, reason='Ziwen: updating "mentions" page with a new link')
            except prawcore.exceptions.TooLarge:  # The wikipage is too large.
                page_name = "mentions"
                message_subject = "[Notification] '{}' Wiki Page Full".format(page_name.title())
                message_template = MSG_WIKIPAGE_FULL.format(page_name)
                logger.error(MSG_WIKIPAGE_FULL.format(page_name))
                reddit.subreddit('translatorBOT').message(message_subject, message_template)

            action_counter(1, "Subreddit reference")
            logger.info("[ZWS] >> Saved to the 'mentions' page.\n")

    return


'''RUNNING THE BOT'''

# This is the actual loop that runs the top-level functions of the bot.

while True:

    # noinspection PyBroadException
    try:

        # Run the actual streamer routine.
        ziwen_streamer()

    except Exception as e:  # The bot encountered an error/exception.

        # Format the error text.
        error_entry = traceback.format_exc()
        error_date = strftime("%a, %b %d, %Y [%I:%M:%S %p]")

        # Exclude saving the error if it's just a connection problem.
        if any(keyword in error_entry for keyword in CONNECTION_KEYWORDS):  # Bot will not log common connection issues
            logger.debug("[ZWS] Connection Error: {}".format(error_entry))
        else:  # Error is not a connection error, we want to save that.

            # Write the error to the log.
            logger.error("[ZWS] Runtime Error: {}".format(error_entry))
            bot_version = "{} {}".format(BOT_NAME, VERSION_NUMBER)
            error_log_basic(error_entry, bot_version)

        time.sleep(10)  # Pause the system briefly.
        print("# Restarting at {}...".format(error_date))
