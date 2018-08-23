#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

"""A Python file containing most of the long-form comments and messages that all r/translator bots use."""

'''ZIWEN RESPONSES'''

# An addition to the bot footer that contains a link to check status and to unsubscribe from notifications.
MSG_UNSUBSCRIBE_BUTTON = (" ^| ^[Points](https://www.reddit.com/message/compose?to=translator-BOT&subject=Points"
                          "&message=%23%23+How+many+points+have+I+earned?) ^| ^[Status](https://www.reddit.com/message/"
                          "compose?to=translator-BOT&subject=Status&message=%23%23+What+languages+am+I+subscribed+to?) ^| "
                          "^[Unsubscribe](https://www.reddit.com/message/compose?to=translator-BOT&subject=Unsubscribe"
                          "&message=%23%23+Please+unsubscribe+me+from+the+following+languages.%0A%23%23+List+language+"
                          "codes+or+names+after+the+colon+below+and+separate+languages+with+commas.+%28List+ALL+to+"
                          "completely+unsubscribe%29%0ALANGUAGES%3A+ALL)")

# An addition to the notifications message about NSFW content
MSG_NSFW_WARNING = "\n\n(Just FYI, this *is* an NSFW post.)"
MSG_SUBSCRIBE_LINK = 'https://www.reddit.com/message/compose?to=translator-BOT&subject=Subscribe&message=%23%23+Sign+up+for+notifications+about+new+requests+for+your+language%21%0A%23%23+List+language+codes+or+names+after+the+colon+below+and+separate+languages+with+commas.%0A%23%23+You+can+sign+up+for+one+language+or+as+many+as+you%27d+like.%0ALANGUAGES%3A+'
MSG_REMOVAL_LINK = "https://www.reddit.com/message/compose?to=translator-BOT&subject=Unsubscribe&message=%23%23+Please+unsubscribe+me+from+the+following+languages.%0ALANGUAGES%3A+{language_name}"
MSG_NO_SUBSCRIPTIONS = ("Sorry, you're not currently subscribed to notifications for any [language posts]"
                        "(https://www.reddit.com/r/translatorBOT/wiki/ziwen#wiki_language_codes.2Fnames_syntax) on r/translator. "
                        "Would you like to [sign up]({})?")
MSG_CANNOT_PROCESS = ("Sorry, but I couldn't process the [language/language codes]"
                      "(https://www.reddit.com/r/translatorBOT/wiki/ziwen#wiki_language_codes.2Fnames_syntax) "
                      "in your message. Please double-check your message to make sure they're accurate and "
                      "[try again]({}).")
MSG_PAGE = '''
Hey there u/{username},

You've been paged by u/{pauthor} to take a look at a possible {language_name} request. Can you check it out?

**[{otitle}]({opermalink})** posted by *u/{oauthor}*.

Feel free to disregard the post or [message Ziwen]({removal_link}) if you wish to unsubscribe from {language_name}.
'''
MSG_MISSING_ASSETS = '''
Hey there u/{oauthor},

Another community member has marked **[your post]({opermalink})** as missing assets (text, images, etc) to be translated. 

Please update your post with content, or delete it and resubmit it with the material you want translated.

You can re-open your translation request by commenting `!reset` on your post. 
'''
MSG_TRANSLATED = '''
Hey there u/{oauthor},

Another redditor on r/translator has marked **[your post]({opermalink})** as translated. 
If your request has been fulfilled, please leave a comment thanking the translator!

*P.S. We encourage you to keep your post up as a useful resource for other people.*
'''
MSG_SHORT_THANKS_TRANSLATED = '''
Hey there u/{0},

Thanks for submitting to r/translator! It looks like you left a short "thank you" comment on **[your post]({1})**. Consequently, I've automatically marked your request as translated. 

If this in error, please comment `!reset` on your post or message the r/translator moderators [here](https://www.reddit.com/message/compose?to=r/translator&subject=Please+reset+this+post&message=https://www.reddit.com{1}). Thank you.
'''
MSG_NOTIFY = '''
Hey there u/{username},

There's a new {language_name} {post_type}:

**[{otitle}]({opermalink})** posted by u/{oauthor}.
'''
MSG_NOTIFY_IDENTIFY = '''
Hey there u/{username},

A {post_type} has been newly identified as {language_name}:

**[{otitle}]({opermalink})** posted by u/{oauthor}.
'''
MSG_WIKIPAGE_FULL = ("The [{0} wiki page](https://www.reddit.com/r/translatorBOT/wiki/{0}) seems to be full. "
                     "Please archive some of the older entries on that page.")

# A comment that is added to long YouTube videos or long text posts.
COMMENT_LONG = ("**Your translation request appears to be very long.** It may take a while for a translator to respond. "
                "Consider narrowing the scope of your request or asking for a synopsis or summary instead.\n\n*Note: "
                "Your post has NOT been removed. "
                "This is merely an automated advisory notice and no action is required on your part.*")
# A comment that is added to new accounts who attempt to use !page.
COMMENT_PAGE_DISALLOWED = ("Hey, u/{pauthor}, thanks for using my paging service. "
                           "However, your account needs to be 14 days or older to use the service.")
COMMENT_NO_LANGUAGE = ("Hey, u/{pauthor}, thanks for using my paging service. Unfortunately, we don't have anyone on "
                       "file for {language_name}.\n\nIf someone else is reading this and knows {language_name}, please "
                       "[sign up for notifications for that language](https://www.reddit.com/message/compose?to="
                       "translator-BOT&subject=Subscribe&message=%23%23+Sign+up+for+notifications+about+new+requests+"
                       "for+your+language%21%0ALANGUAGES%3A+{language_code}) "
                       "if you would like to be notified for future posts for it!")
COMMENT_NO_RESULTS = "Sorry, but that doesn't look like anything to me."
# A comment that is posted when someone attempts to call the bot on r/translation.
COMMENT_R_TRANSLATION = ("Hey there u/{pauthor}, it looks like you tried to call me on r/translation. "
                         "Unfortunately, I can only process user commands over at r/translator.")
COMMENT_ENGLISH_ONLY = '''
Hey there u/{oauthor},

* Your post above has been automatically removed because does not appear to be a request for a translation. 
There are more focused communities for English-only requests.

---

**Our Recommendations**

* Answers on English language learning, English video transcriptions, or word explanations: **r/EnglishLearning** or **r/Grammar**
* Proofreading of written English content: **r/Proofreading** (please note their sidebar rules for submissions.)
* Decipherment of illegible handwriting: **r/handwriting** 

* If you're requesting the *review of a translation*, please include the source language name and its original text in your resubmitted post to r/translator. 
'''
COMMENT_BAD_TITLE = '''
Hey there, u/{author}!
    
We're happy to help you translate your request, but this post has been automatically removed because:
    
* It appears that the title is not properly formatted according to our subreddit's guidelines.
* Proper title formatting helps keep our community organized and allows our translators to access relevant requests. 

---

**What should you do now?**

* [Try resubmitting your request with the suggested title text below](https://www.reddit.com/r/translator/submit?title={new_url}):
* {new_title}
* Should you need more information, please read r/translator's [formatting guidelines](https://www.reddit.com/r/translator/wiki/request-guidelines#wiki_how_should_i_submit_requests_for_translations.3F).
'''
COMMENT_CLAIM = '''
**Claimer:** u/{claimer} at {time} UTC

*The user above has indicated that they are working on a translation for this {language_name} request.*

*This post will revert to an unclaimed state if it is not marked as 'Needs Review' or 'Translated' within 8 hours.*
'''
COMMENT_CURRENTLY_CLAIMED = '''
This post has already been claimed by u/{claimer_name}. Their in-progress claim will expire in {remaining_time}.
'''
COMMENT_UNKNOWN = '''
**It looks like you have submitted a translation request tagged as 'Unknown.'** 

* Other community members may help you recategorize your post with the `!identify:` or the `!page:` commands.
* Please refrain from posting short 'thank you' comments until your request has been fully translated.
* Do *not* delete your post if it is identified as another language. We will automatically find people who can help you!

*Note: Your post has NOT been removed. This is merely an automated advisory notice.*
'''
COMMENT_DEFINED_MULTIPLE = """
**It looks like you have submitted a translation request for multiple defined languages.** 

* Translators can use the `!translated` and `!doublecheck` status commands on this post by including the language name and command in their comment.
* For example, if one is making a French translation, please include `French` and the command in the text. 
* This post's flair will automatically update to reflect the state of its requested languages.

*Note: Your post has NOT been removed. This is merely an automated advisory notice.*
"""
COMMENT_ADVANCED_IDENTIFY_ERROR = '''
Sorry, but [advanced *!identify* commands](https://www.reddit.com/r/translatorBOT/wiki/ziwen#wiki_advanced_.21identify) require either a [three-letter ISO 639-3](https://en.wikipedia.org/wiki/List_of_ISO_639-3_codes) or [four-letter ISO 15924 code](https://en.wikipedia.org/wiki/ISO_15924#List_of_codes).

Here are some common ISO 15924 codes:

Script | Code 
-------|-----
Arabic | *Arab*
Cyrillic | *Cyrl*
Devanagari | *Deva*
Han Characters | *Hani*
Hebrew | *Hebr*
Latin | *Latn*
Nastaliq | *Aran*
'''
COMMENT_VERIFICATION_RESPONSE = "Thanks, u/{}. I've taken note of your verification request."
COMMENT_INVALID_REFERENCE = ("Sorry, but that doesn't look like anything to me. "
                             "Please enter a valid ISO 639-1 code, ISO 639-3 code, or language name to look up.")
COMMENT_INVALID_CODE = ("Sorry, but `{0}` doesn't look like anything to me. Would you like to [send my creator a "
                        "message about it?](https://www.reddit.com/message/compose?to=%2Fr%2FtranslatorBOT&subject="
                        "Identification+for+'{0}'&message=%5BPlease+check+this+out+%5D%28{1}%29%21)")
COMMENT_INVALID_SCRIPT = ("Sorry, but the script code `{}` doesn't look like anything to me. Please "
                          "[see here](https://en.wikipedia.org/wiki/ISO_15924#List_of_codes) for a list of "
                          "valid ISO 15924 codes.")


'''WENYUAN RESPONSES'''

WY_THREAD_BODY = '''
Here are the posts from the last week still marked as "Unknown." Please help identify them if you can!

Date | Title         | Author 
:----|---------------|--------
{unknown_content}

*Please make any identifications on the individual request pages.*
'''
WY_MOD_NOTIFICATION_MESSAGE = '''
##### Routine Tasks

 Task | Status
------|-------
[Actions Update](https://www.reddit.com/r/translatorBOT/wiki/actions) | {}
[Status Update](https://www.reddit.com/r/translatorBOT/wiki/status) | {}
File Backup | {}

##### Operations

{}

{}

##### Status Summary

{}

---

###### Completed in {}.
'''
WY_NEW_HEADER = '''
## {language_name} ({language_family}) ![](%%statistics-h%%)
*[Statistics](https://www.reddit.com/r/translator/wiki/statistics) for r/translator \
provided by [Wenyuan](https://www.reddit.com/r/translatorBOT/wiki/wenyuan)*

Year | Month | Total Requests | Percent of All Requests | Untranslated Requests | Translation Percentage | RI | View Translated Requests
-----|-------|------|------|------|------|----|------'''
WY_STATUS_UPDATE = '''
### Due to {reason}, the bot will be down until around:

# [{utc_time} UTC](https://www.timeanddate.com/worldclock/fixedtime.html?iso={url_time}&msg=Ziwen+will+be+back+at+...)

During this time period the command monitoring, reference lookup, and crossposting functions will not be available.

This status post will be deleted when the bot is back online. Thanks for your patience!
'''
WY_FULL_RETRIEVAL_DATA = '''

Info                                    | #
----------------------------------------|-----------
Total number of processed posts         | {} posts
Number of non-supported CSS posts       | {} posts
Number of regional language posts       | {} posts
Number of problematic posts             | {} posts
Overall accuracy                        | {}%
Supported posts percentage              | {}%
Average processing time per post        | {} seconds
Total elapsed time                      | {} seconds
'''


'''ZIWEN STREAMER RESPONSES'''

ZWS_COMMENT_XPOST = '''
**OP:** u/{original_author} at {subreddit} ([Link]({cpermalink}))

**Requester:** u/{requester}

*This is a crossposted translation request and all images/text remain © of the OP. Either user listed above can comment* `!delete` *to remove this post if they wish.*

*Please post any translations or commands here on r/translator.*
'''
ZWS_COMMENT_ALREADY_POSTED = "It appears that this link has already been posted as a translation request."
ZWS_COMMENT_XPOST_THANKS = ("{}. I've [crossposted](https://www.reddit.com/r/translatorBOT/wiki/ziwen#wiki_cross-posting) "
                            "this link as a [{} translation request here]({}).")
ZWS_COMMENT_WRONG_SUBREDDIT = "Sorry, but did you mean r/translator?\n\n^(Note: I can't detect edits.)"
ZWS_COMMENT_ENGLISH_ONLY = ('It appears that this is an English-only "translation" crosspost request. English-only '
                            'posts are better suited for r/EnglishLearning.')
ZWS_COMMENT_WRONG_XPOST_COMMENT = ("It appears that you're trying to crosspost a comment for translation, but your "
                                   "command is in reply to a submission.")
