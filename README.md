# About

**Ziwén (子文)** is a Reddit bot that handles real-time commands for r/translator, the largest translation community on the website. 

It posts comments and sends messages under the username u/translator-BOT. Ziwen moderates and keeps r/translator organized, provides community members with useful reference information, and crossposts translation requests from elsewhere on Reddit.

# Documentation

Documentation for Ziwen's various commands can be found **[here](https://www.reddit.com/r/translatorBOT/wiki/ziwen)**. 

#### Modules

* `_config.py`
* `_languages.py`
* `_responses.py`
* `Ziwen.py`
* `Ziwen_Streamer.py`

# Technical Info

Ziwen is written in Python 3 and utilizes [PRAW](https://github.com/praw-dev/praw) to connect to Reddit. The bot also uses [SQLite3](https://www.sqlite.org/index.html) and [Markdown](https://daringfireball.net/projects/markdown/syntax) to store data in its `Data` folder. 

#### Reference Databases

Ziwen uses various databases to provide language reference and lookup information, including but not limited to: 

* [5156edu](http://cy.5156edu.com/)
* [Babelcarp](http://www.panix.com/~perin/babelcarp/)
* [Baxter-Sagart Reconstruction of Old Chinese](http://ocbaxtersagart.lsait.lsa.umich.edu/)
* [Chinese Character Web API](http://ccdb.hemiola.com/)
* [CC-CANTO](https://www.cantonese.org/)
* [CC-CEDICT](https://cc-cedict.org/)
* [Chinese Text Project](https://ctext.org/)
* [Ethnologue](http://ethnologue.com/)
* [Jisho](http://jisho.org/)
* [Jitenon](https://yoji.jitenon.jp/)
* [MultiTree](http://multitree.org/)
* [NAVER](https://endic.naver.com/?sLn=en)
* [SFX Translations](http://thejadednetwork.com/sfx/)
* [Shufazidian  书法字典](http://www.shufazidian.com/)
* [Soothill-Lewis](http://mahajana.net/en/library/texts/a-dictionary-of-chinese-buddhist-terms)
* [Unihan](http://unicode.org/charts/unihan.html)
* [Wiktionary](https://www.wiktionary.org/)

# Feedback

Feedback for Ziwen should be posted as a text post over at [r/translatorBOT](https://www.reddit.com/r/translatorBOT/). Users are more than welcome to file a pull request if they would like to add a new feature or fix a bug. 