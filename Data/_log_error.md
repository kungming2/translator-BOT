-----------------------------------
2018-03-04 [11:24:09 AM] (Ziwen 1.7.S) [RESOLVED, KOMENTO RETURNS EMPTY DICT NOW]
Last post     |   Sun, Mar 04, 2018 [11:22:55 AM]:    https://www.reddit.com/r/translator/comments/81zugl/telugu_writtentelugu_spoken/
Last comment  |   Sun, Mar 04, 2018 [11:23:13 AM]:    https://www.reddit.com/r/translator/comments/81zu5u//dv6e0lq
              >    That's Japanese.
              > 
              > !identify:ja

Traceback (most recent call last):
  File "/home/pi/Desktop/Bots/Ziwen.py", line 4766, in <module>
    ziwen_bot()
  File "/home/pi/Desktop/Bots/Ziwen.py", line 3915, in ziwen_bot
    if 'bot_unknown' in komento_data or 'bot_reference' in komento_data:
TypeError: argument of type 'NoneType' is not iterable

-----------------------------------
2018-03-09 [11:41:39 AM] (Ziwen 1.7.T) [RESOLVED, NULL CHARACTER REPLACED, VALUEERROR CHECK ADDED]
Last post     |   Fri, Mar 09, 2018 [11:31:44 AM]:    https://www.reddit.com/r/translator/comments/839evu/english_french_italian_spanish_japanese_brazilian/
Last comment  |   Fri, Mar 09, 2018 [11:41:09 AM]:    https://www.reddit.com/r/translator/comments/838mjl//dvg3ies
              >    Its urdu
              > Transliteration: Guarantee-shudha Chakoo
              > Guaranteed dagger (Chakoo=چاقو)

Traceback (most recent call last):
  File "/home/pi/Desktop/Bots/Ziwen.py", line 4771, in <module>
    edit_finder()
  File "/home/pi/Desktop/Bots/Ziwen.py", line 3521, in edit_finder
    cursor_cache.execute(cache_command)
ValueError: the query contains a null character
