# About

**Ziwén (子文)** is a Reddit bot that handles real-time commands for r/translator, the largest translation community on the website. 

It posts comments and sends messages under the username u/translator-BOT. Ziwen moderates and keeps r/translator organized, provides community members with useful reference information, and crossposts translation requests from elsewhere on Reddit.

# Documentation

Documentation for Ziwen's various commands can be found **[here](https://www.reddit.com/r/translatorBOT/wiki/ziwen)**. 

#### Modules

* `_config.py` - a file containing connections to the bot's databases and credentials.
* `_languages.py` - a file containing basic language data and functions.
* `_responses.py` - a file containing all the long-form message and comment templates used by the bot.
* `Ziwen.py` - the main runtime of the bot.
* `Ziwen_Streamer.py` - the live "streaming" component of the bot. Run independently, it allows users to crosspost from anywhere on Reddit.

#### Bot Data Files

The bulk of Ziwen's data is stored in three SQLite3 files:

* `_cache_main.db` contains the temporary caches of the bot, including the cache for comment edits and language multipliers for points.
* `_database_ajo` stores the Ajos of the bot (see below) indexed by their post ID.
* `_database_main.db` stores everything else, including the database of user notifications, points, and items that have already been processed.

# Technical Info

Ziwen is written in Python 3 and utilizes [PRAW](https://github.com/praw-dev/praw) to connect to Reddit. The bot also uses [SQLite3](https://www.sqlite.org/index.html) and [Markdown](https://daringfireball.net/projects/markdown/syntax) to store data in its `Data` folder. 

### Ajo Objects

Each r/translator post that Ziwen processes is stored locally as an *Ajo* object (from Esperanto *aĵo*, meaning "thing"). This allows the bot to keep track of information that would otherwise be lost as the post changes. Below are some examples.

#### Single-Language Ajo

    {
        'output_oflair_text': 'Needs Review [JA]',
        'language_code_1': 'ja',
        'created_utc': 1534953367,
        'is_long': False,
        'output_oflair_css': 'doublecheck',
        'author': 'right8',
        'country_code': None,
        'status': 'doublecheck',
        'type': 'single',
        'language_history': ['Chinese', 'Japanese'],
        'language_code_3': 'jpn',
        'title_original': '[Chinese > English] Found under a bronze statue of the Buddha. Meaning?',
        'time_delta': {'doublecheck': 1534960329},
        'recorded_translators': ['kungming2'],
        'is_supported': True,
        'title': 'Found under a bronze statue of the Buddha. Meaning?',
        'is_identified': True,
        'original_source_language_name': 'Chinese',
        'is_bot_crosspost': False,
        'language_name': 'Japanese',
        'direction': 'english_to',
        'original_target_language_name': 'English',
        'id': '99eint'
    }

#### Multiple-Language Ajo

    {
        'original_source_language_name': 'English',
        'language_code_3': ['fin', 'fra', 'hrv', 'jpn', 'nld', 'nor'],
        'title': 'Great Lion',
        'recorded_translators': ['Cyntex-', 'T-a-r-a-x', 'tobiasvl', 'Rootriver'],
        'created_utc': 1534478920,
        'original_target_language_name': ['Finnish', 'French', 'Norwegian', 'Croatian', 'Dutch', 'Japanese'],
        'title_original': '[English > French, Japanese, Croatian, Dutch, Finnish, Norwegian] Great Lion',
        'output_oflair_text': 'Multiple Languages [FI✔, FR✔, HR, JA✔, NL✔, NO✔]',
        'language_history': ['Multiple Languages'],
        'output_oflair_css': 'multiple',
        'language_name': ['Finnish', 'French', 'Croatian', 'Japanese', 'Dutch', 'Norwegian'],
        'country_code': None,
        'is_long': False,
        'direction': 'english_from',
        'status': {'fi': 'translated', 
                   'ja': 'translated',
                   'fr': 'translated',
                   'no': 'translated',
                   'hr': 'untranslated',
                   'nl': 'translated'},
        'type': 'multiple',
        'is_supported': True,
        'is_bot_crosspost': False,
        'author': 'PrinceTanglemane',
        'language_code_1': ['fi', 'fr', 'hr', 'ja', 'nl', 'no'],
        'is_identified': False,
        'id': '97z6rg'
    }

### Reference Databases

Ziwen uses various databases to provide language reference and lookup information, including but not limited to: 

* [5156edu](http://cy.5156edu.com/)
* [Babelcarp](http://www.panix.com/~perin/babelcarp/)
* [Baxter-Sagart Reconstruction of Old Chinese](http://ocbaxtersagart.lsait.lsa.umich.edu/)
* [Chinese Character Web API](http://ccdb.hemiola.com/)
* [CC-CANTO](https://www.cantonese.org/)
* [CC-CEDICT](https://cc-cedict.org/)
* [Chinese Text Project](https://ctext.org/)
* [Ethnologue](http://ethnologue.com/)
* [Jinmei Kanji Jisho 人名漢字辞典](http://kanji.reader.bz/)
* [Jisho](http://jisho.org/)
* [Jitenon](https://yoji.jitenon.jp/)
* [MultiTree](http://multitree.org/)
* [NAVER](https://endic.naver.com/?sLn=en)
* [SFX Translations](http://thejadednetwork.com/sfx/)
* [Shufazidian  书法字典](http://www.shufazidian.com/)
* [Soothill-Lewis](http://mahajana.net/en/library/texts/a-dictionary-of-chinese-buddhist-terms)
* [Unihan](http://unicode.org/charts/unihan.html)
* [Wikipedia](https://www.wikipedia.org/)
* [Wiktionary](https://www.wiktionary.org/)

# Feedback

Feedback for Ziwen should be posted as a text post over at [r/translatorBOT](https://www.reddit.com/r/translatorBOT/). Users are more than welcome to file a pull request if they would like to add a new feature or fix a bug. 
