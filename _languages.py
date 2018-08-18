# -*- coding: UTF-8 -*-
import csv
import re
import os
import string
import itertools

from fuzzywuzzy import fuzz  # fuzzywuzzy[speedup]

VERSION_NUMBER_LANGUAGES = "1.6.17"

# Access the CSV with ISO 639-3 and ISO 15924 data.
lang_script_directory = os.path.dirname(__file__)  # <-- absolute dir the script is in
lang_script_directory += "/Data/"  # Where the main files are kept.
FILE_ADDRESS_ISO_ALL = os.path.join(lang_script_directory, '_database_iso_codes.csv')

'''LANGUAGE CODE LISTS'''
# The following two lists are hard-coded codes that are the 120 languages and others supported on the subreddit.
# They have equivalent flairs in the CSS and icons (https://www.reddit.com/r/translator/wiki/linkflair).
SUPPORTED_CODES = ['af', 'sq', 'am', 'egy', 'ar', 'arc', 'hy', 'eu', 'be', 'bn', 'bs', 'bg', 'my', 'yue', 'ca', 'zh',
                   'hr', 'cs', 'da', 'nl', 'et', 'fi', 'fr', 'de', 'ka', 'el', 'gu', 'ht', 'he', 'hi', 'hu', 'is', 'id',
                   'ga', 'it', 'ja', 'kk', 'km', 'ko', 'ku', 'la', 'lv', 'lt', 'mg', 'ms', 'mr', 'mn', 'non', 'no',
                   'ps', 'fa', 'pl', 'pt', 'pa', 'ro', 'ru', 'sa', 'sc', 'gd', 'sr', 'si', 'sk', 'sl', 'so', 'es', 'sw',
                   'sv', 'tl', 'ta', 'te', 'th', 'bo', 'tr', 'uk', 'ur', 'uz', 'vi', 'cy', 'yi', 'zu', 'multiple',
                   'app', 'unknown', 'generic', 'art', 'ang', 'ban', 'ceb', 'haw', 'mk', 'ml', 'mt', 'ne', 'zxx',
                   'chr', 'co', 'cop', 'cu', 'eo', 'grc', 'iu', 'lo', 'nv', 'qu', 'xh', 'yo', 'az', 'br', 'dz', 'fo',
                   'jv', 'kl', 'kn', 'lb', 'li', 'ln', 'lzh', 'mi', 'om', 'ota', 'pi', 'syc', 'tg', 'tt', 'tw', 'ug']
SUPPORTED_LANGUAGES = ['Afrikaans', 'Albanian', 'Amharic', 'Ancient Egyptian', 'Arabic', 'Aramaic', 'Armenian',
                       'Basque', 'Belarusian', 'Bengali', 'Bosnian', 'Bulgarian', 'Burmese', 'Cantonese', 'Catalan',
                       'Chinese', 'Croatian', 'Czech', 'Danish', 'Dutch', 'Estonian', 'Finnish', 'French', 'German',
                       'Georgian', 'Greek', 'Gujarati', 'Haitian Creole', 'Hebrew', 'Hindi', 'Hungarian', 'Icelandic',
                       'Indonesian', 'Irish', 'Italian', 'Japanese', 'Kazakh', 'Khmer', 'Korean', 'Kurdish', 'Latin',
                       'Latvian', 'Lithuanian', 'Malagasy', 'Malay', 'Marathi', 'Mongolian', 'Norse', 'Norwegian',
                       'Pashto', 'Persian', 'Polish', 'Portuguese', 'Punjabi', 'Romanian', 'Russian', 'Sanskrit',
                       'Sardinian', 'Scottish Gaelic', 'Serbian', 'Sinhalese', 'Slovak', 'Slovene', 'Somali', 'Spanish',
                       'Swahili', 'Swedish', 'Tagalog', 'Tamil', 'Telugu', 'Thai', 'Tibetan', 'Turkish', 'Ukrainian',
                       'Urdu', 'Uzbek', 'Vietnamese', 'Welsh', 'Yiddish', 'Zulu', 'Multiple Languages', 'App',
                       'Unknown', 'Generic', 'Conlang', 'Anglo-Saxon', 'Balinese', 'Cebuano', 'Hawaiian', 'Macedonian',
                       'Malayalam', 'Maltese', 'Nepali', 'Nonlanguage', 'Cherokee', 'Corsican', 'Coptic',
                       'Old Church Slavonic', 'Esperanto', 'Ancient Greek', 'Inuktitut', 'Lao', 'Navajo', 'Quechua',
                       'Xhosa', 'Yoruba', 'Azerbaijani', 'Breton', 'Dzongkha', 'Faroese', 'Javanese', 'Kalaallisut',
                       'Kannada', 'Luxembourgish', 'Limburgish', 'Lingala', 'Classical Chinese', 'Maori', 'Oromo',
                       'Ottoman Turkish', 'Pali', 'Syriac', 'Tajik', 'Tatar', 'Twi', 'Uyghur']
# These are symbols used to indicate states in defined multiple posts.
DEFINED_MULTIPLE_LEGEND = {'⍉': 'missing', '¦': 'inprogress', '✓': 'doublecheck', '✔': 'translated'}

# These are two-letter and three-letter English words that can be confused for ISO language codes.
# We exclude them when processing the title.
ENGLISH_2_WORDS = ['As', 'He', 'My', 'It', 'Be', 'No', 'Am', 'So', 'Is', 'To', 'An', 'Or', 'Se', 'Br', 'Tw', 'El']
ENGLISH_3_WORDS = ['Abs', 'Abu',
                   'Aby', 'Ace', 'Act', 'Add', 'Ado', 'Ads', 'Aft', 'Age', 'Ago', 'Aid', 'Ail', 'Aim', 'Air',
                   'Ait', 'Ale', 'Amp', 'And', 'Ant', 'Ape', 'App', 'Apt', 'Arc', 'Are', 'Ark', 'Arm',
                   'Art', 'Ash', 'Ask', 'Asp', 'Ass', 'Ate', 'Auk', 'Awe', 'Awl', 'Awn', 'Axe', 'Azo', 'Baa', 'Bad',
                   'Bag', 'Bah', 'Bam', 'Ban', 'Bar', 'Bat', 'Bay', 'Bed', 'Bee', 'Beg', 'Bet', 'Bey', 'Bib', 'Bid',
                   'Big', 'Bin', 'Bio', 'Bit', 'Boa', 'Bob', 'Bod', 'Bog', 'Boo', 'Bop', 'Bot', 'Bow', 'Box', 'Boy',
                   'Bra', 'Bro', 'Bub', 'Bud', 'Bug', 'Bum', 'Bun', 'Bus', 'But', 'Buy', 'Bye', 'Cab', 'Cad', 'Cam',
                   'Can', 'Cap', 'Car', 'Cat', 'Caw', 'Cee', 'Cha', 'Chi', 'Cob', 'Cod', 'Cog', 'Com', 'Con', 'Coo',
                   'Cop', 'Cot', 'Cow', 'Cox', 'Coy', 'Cry', 'Cub', 'Cud', 'Cue', 'Cup', 'Cur', 'Cut', 'Dab', 'Dad',
                   'Dag', 'Dam', 'Day', 'Dee', 'Den', 'Dew', 'Dib', 'Did', 'Die', 'Dig', 'Dim', 'Din', 'Dip', 'Doc',
                   'Doe',
                   'Dog', 'Don', 'Doo', 'Dop', 'Dot', 'Dry', 'Dub', 'Dud', 'Due', 'Dug', 'Duh', 'Dun', 'Duo', 'Dux',
                   'Dye', 'Ear', 'Eat', 'Ebb', 'Eel', 'Egg', 'Ego', 'Eke', 'Elf', 'Elk', 'Elm', 'Emo', 'Emu', 'End',
                   'Eon', 'Era', 'Erg', 'Err', 'Etc',
                   'Eve', 'Ewe', 'Eye', 'Fab', 'Fad', 'Fag', 'Fan', 'Far', 'Far', 'Fat',
                   'Fax', 'Fay', 'Fed', 'Fee', 'Fen', 'Few', 'Fey', 'Fez', 'Fib', 'Fie', 'Fig', 'Fin', 'Fir', 'Fit',
                   'Fix', 'Fly', 'Fob', 'Foe', 'Fog', 'Fon', 'Fop', 'For', 'Fox', 'Fry', 'Fue', 'Fun', 'Fur', 'Gab',
                   'Gag', 'Gak', 'Gal', 'Gap', 'Gas', 'Gaw', 'Gay', 'Gee', 'Gel', 'Gem', 'Geo',
                   'Get', 'Gig', 'Gil', 'Gin',
                   'Git', 'Gnu', 'Gob', 'God', 'Goo', 'Got', 'Gum', 'Gun', 'Gut', 'Guy', 'Gym', 'Had', 'Hag', 'Hal',
                   'Han',
                   'Ham', 'Has', 'Hat', 'Hay', 'Hem', 'Hen', 'Her', 'Hew', 'Hex', 'Hey', 'Hid', 'Him', 'Hip', 'His',
                   'Hit', 'Hoe', 'Hog', 'Hop', 'Hot', 'How', 'Hoy', 'Hub', 'Hue', 'Hug', 'Hug', 'Huh', 'Hum', 'Hut',
                   'Ice', 'Ich',
                   'Ick', 'Icy', 'Ilk', 'Ill', 'Imp', 'Ink', 'Inn', 'Ion', 'Ire', 'Irk', 'Ism', 'Its', 'Jab',
                   'Jag', 'Jah', 'Jak', 'Jam', 'Jar', 'Jav', 'Jaw', 'Jay', 'Jem', 'Jet', 'Jew', 'Jib', 'Jig',
                   'Job', 'Joe', 'Jog', 'Jon', 'Jot', 'Joy', 'Jug', 'Jus', 'Jut', 'Keg', 'Key', 'Kid', 'Kin', 'Kit',
                   'Koa', 'Kob', 'Koi', 'Lab', 'Lad', 'Lag', 'Lap', 'Law', 'Lax', 'Lay', 'Lea', 'Led', 'Lee', 'Leg',
                   'Lei', 'Let', 'Lew', 'Lid', 'Lie', 'Lip', 'Lit', 'Lob', 'Log', 'Lol', 'Loo', 'Lop', 'Los',
                   'Lot', 'Low',
                   'Lug', 'Lux', 'Lye', 'Mac', 'Mad', 'Mag', 'Man', 'Mao', 'Map', 'Mar', 'Mat', 'Maw', 'Max', 'May',
                   'Men', 'Met', 'Mic', 'Mid', 'Min', 'Mit', 'Mix', 'Mob', 'Mod', 'Mog', 'Mom', 'Mon', 'Moo', 'Mop',
                   'Mow', 'Mud', 'Mug', 'Mum', 'Nab', 'Nag', 'Nap', 'Nay', 'Nee', 'Neo', 'Net', 'New', 'Nib', 'Nil',
                   'Nip', 'Nit', 'Nix', 'Nob', 'Nod', 'Nog', 'Non', 'Nor', 'Not',
                   'Now', 'Nub', 'Nun', 'Nut', 'Oaf', 'Oak',
                   'Oar', 'Oat', 'Odd', 'Ode', 'Off', 'Oft', 'Ohm', 'Oil', 'Old', 'Ole', 'Oma', 'One', 'Opt', 'Orb',
                   'Ore', 'Our', 'Out', 'Out', 'Ova', 'Owe', 'Owl', 'Own', 'Pac', 'Pad', 'Pal', 'Pan', 'Pap', 'Par',
                   'Pas',
                   'Pat', 'Paw', 'Pax', 'Pay', 'Pea', 'Pee', 'Peg', 'Pen', 'Pep', 'Per', 'Pet', 'Pew', 'Pls', 'Plz',
                   'Pic', 'Pie',
                   'Pig', 'Pin', 'Pip', 'Pit', 'Pix', 'Ply', 'Pod', 'Poe', 'Pog', 'Poi', 'Poo', 'Pop', 'Pot', 'Pow',
                   'Pox', 'Pre', 'Pro', 'Pry', 'Pub', 'Pud', 'Pug', 'Pun', 'Pup', 'Pus', 'Put', 'Pyx', 'Qat', 'Qua',
                   'Quo', 'Rad', 'Rag', 'Ram', 'Ran', 'Rap', 'Rat', 'Raw', 'Ray', 'Red', 'Rib', 'Rid', 'Rig', 'Rim',
                   'Rip', 'Rob', 'Roc', 'Rod', 'Roe', 'Rot', 'Row', 'Rub', 'Rue', 'Rug', 'Rum', 'Run', 'Rut', 'Rye',
                   'Sac', 'Sad', 'Sag', 'Sap', 'Sat', 'Saw', 'Sax', 'Say', 'Sea', 'Sec', 'See', 'Set', 'Sew', 'Sex',
                   'She', 'Shh',
                   'Shy', 'Sic', 'Sim', 'Sin', 'Sip', 'Sir', 'Sis', 'Sit', 'Six', 'Ski', 'Sky', 'Sly', 'Sob',
                   'Sod', 'Som', 'Son', 'Sop', 'Sot', 'Sow', 'Soy', 'Spa', 'Spy', 'Sty', 'Sub', 'Sue', 'Sum', 'Sun',
                   'Sun', 'Sup', 'Tab', 'Tad', 'Tag', 'Tam', 'Tan', 'Tae',
                   'Tap', 'Tar', 'Tat', 'Tax', 'Tea', 'Tee', 'Ten',
                   'The', 'Thx',
                   'Tic', 'Tie', 'Til', 'Tin', 'Tip', 'Tit', 'Toe', 'Toe', 'Tom', 'Ton', 'Too', 'Top', 'Tot',
                   'Tow', 'Toy', 'Try', 'Tub', 'Tug', 'Tui', 'Tut', 'Two', 'Txt', 'Ugh', 'Uke', 'Ump', 'Urn', 'Usa',
                   'Use',
                   'Van', 'Vat', 'Vee', 'Vet', 'Vex', 'Via', 'Vie', 'Vig', 'Vim', 'Voe', 'Vow', 'Wad', 'Wag', 'Wan',
                   'War', 'Was', 'Wax', 'Way', 'Web', 'Wed', 'Wee', 'Wel', 'Wen', 'Wet', 'Who', 'Why', 'Wig', 'Win',
                   'Wit',
                   'Wiz', 'Woe', 'Wog', 'Wok', 'Won', 'Woo', 'Wow', 'Wry', 'Wwi',
                   'Wye', 'Yak', 'Yam', 'Yap', 'Yaw', 'Yay',
                   'Yea', 'Yen', 'Yep', 'Yes', 'Yet', 'Yew', 'Yip', 'You', 'Yow', 'Yum', 'Yup', 'Zag', 'Zap', 'Zed',
                   'Zee', 'Zen', 'Zig', 'Zip', 'Zit', 'Zoa', 'Zoo']
# These are words that usually get recognized as something they're not due to Fuzzywuzzy. Let's ignore them.
FUZZ_IGNORE_WORDS = ["Javanese", "Japanese", "Romanization", "Romani", "Karen", "Morse", "Roman", "Scandinavian", "Latino",
                     "Latina", "Romanji", 'Romanized', 'Guarani', 'Here', 'Chopstick', 'Turks', 'Romany',
                     'Romanjin', 'Serial', 'Ancient Mayan', 'Cheese', 'Sorbian', 'Green', 'Orkish', 'Peruvian', 'Nurse',
                     'Maay', 'Canada', 'Kanada', 'Sumerian', "Classical Japanese", "Logo", "Sake", "Trail"]

# Title formatting words
ENGLISH_DASHES = ['English -', 'English-', '-English', '- English', '-Eng', 'Eng-', '- Eng', 'Eng -', 'ENGLISH-',
                  'ENGLISH -', 'EN-', 'ENG-', 'ENG -', '-ENG', '- ENG', '-ENGLISH', '- ENGLISH']
WRONG_BRACKETS = ["<", "〉", "›", "》", "»", "⟶", "\udcfe", "&gt;", "→", "←", "~"]
APP_WORDS = [" app ", "android", "game", "social network", " bot ", "crowdin", "localisation", "localize", "localise",
             "software", "crowdsourced", "localization", "addon", "add-on", "google play", 'an app', 'discord bot',
             'telegram bot', 'chatbot', "my app", 'firefox']

# The following dictionary is a list of common misspellings or alternate ways of saying what a supported language is.
# Everything should be in Title Case.
SUPPORTED_ALTERNATE = {'am': ['Ethiopian', 'Ethiopia', 'Ethopian', 'Ethiopic', 'Abyssinian',
                              'Amarigna', 'Amarinya', 'Amhara'],
                       'ar': ['Arab', 'Arabian', 'Arbic', 'Aribic', 'Arabe', 'Levantine', 'Arabish', 'Arabiic',
                              'Lebanese', 'Syrian', 'Yemeni', '3arabi', 'Msarabic', 'Moroccan', 'Arabizi', 'Tunisian'],
                       'az': ['Azeri'],
                       'be': ['Belarussian', 'Belorusian', 'Belorussian', 'Bielorussian', 'Byelorussian'],
                       'bn': ['Bangala', 'Bangla'], 'bo': ['Tibetic'], 'bs': ['Bosnien'],
                       'ca': ['Catalonian', 'Valencian', 'Catalán'],
                       'ceb': ['Cebu', 'Visaya', 'Bisaya', 'Visayan'], 'chr': ['Tsalagi'],
                       'co': ['Corsu', 'Corso', 'Corse'], 'cs': ['Bohemian', 'Čeština', 'Czechoslovakian'],
                       'cu': ['Slavonic', 'Church Slavonic', 'Old Slavic'],
                       'cy': ['Wales', 'Cymraeg', 'Gymraeg'], 'da': ['Dansk', 'Denmark', 'Rigsdansk'],
                       'de': ['Deutsch', 'Deutsche', 'Ger', 'Deutch', 'Bavarian', 'Kurrent', 'Austrian', 'Sütterlin',
                              'Plattdeutsch', "Suetterlin", 'Tedesco'],
                       'egy': ['Hieroglyphs', 'Hieroglyphic', 'Hieroglyphics', 'Hyroglifics', 'Egyptian Hieroglyphs',
                               'Egyptian Hieroglyph'], 'el': ['Hellenic', 'Greece', 'Hellas', 'Cypriot'],
                       'es': ['Espanol', 'Spainish', 'Mexican', 'Castilian', 'Español', 'Spain', 'Esp',
                              'Chilean', 'Castellano', 'Españo'],
                       'et': ['Eesti'], 'eu': ['Euska', 'Euskera' 'Euskerie', 'Euskara'],
                       'fa': ['Farsi', 'Iranian', 'Iran', 'Parsi'], 'fi': ['Finnic', 'Suomi', 'Finland'],
                       'fr': ['Francais', 'Français', 'Quebecois', 'France', 'Québécois'], 'ga': ['Gaeilge', 'Gaelic'],
                       'gd': ['Gaidhlig', 'Scottish Gaelic', 'Scots Gaelic'],
                       'grc': ['Koine', 'Doric', 'Attic', 'Byzantine Greek', 'Medieval Greek', 'Classic Greek',
                               'Classical Greek'], 'gu': ['Gujerathi', 'Gujerati', 'Gujrathi'],
                       'he': ['Israeli', 'Hebraic', 'Jewish'], 'hi': ['Hindustani', 'Hindī'],
                       'hr': ['Croation', 'Serbo-Croatian'],
                       'ht': ['Haitian', 'Kreyòl Ayisyen', 'Western Caribbean Creole', 'Kreyol'],
                       'hu': ['Magyar', 'Hungary'],
                       'id': ['Indonesia', 'Indo'],
                       'it': ['Italiano', 'Italiana', 'Italia', 'Italien', 'Italy'], 'iu': ['Inuit'],
                       'ja': ['Jap', 'Jpn', 'Japenese', 'Japaneese', 'Japanes', 'Katakana', 'Hiragana', 'Japaness',
                              'Romaji', 'Japneese', 'Japnese', 'Kanji', 'Japaese', 'Japn', 'Japonais', 'Romajin',
                              'Nihongo', 'Kenji', 'Romanji', 'Rōmaji', '日本語'],
                       'ka': ['Common Kartvelian', 'Kartvelian'],
                       'kk': ['Kazakhstan', "Kazak", 'Kaisak', 'Kosach'],
                       'km': ['Cambodian', 'Cambodia', 'Kampuchea'],
                       'ko': ['Korea', 'Hangul', 'Korian', 'Kor', 'Hanguk', 'Guk-Eo'],
                       'ku': ['Kurdi', 'Kurd'], 'la': ['Latina', 'Classical Roman'],
                       'lo': ['Laos', 'Laotian'],
                       'lt': ['Lithuania', 'Lietuviu', 'Litauische', 'Litewski', 'Litovskiy', 'Lith'],
                       'lzh': ['Literary Chinese', 'Literary Sinitic', 'Classical Sinitic', '文言文', '古文'],
                       'mg': ['Madagascar'], 'ms': ['Malaysia', 'Melayu', 'Malaysian'], 'mt': ['Malti'],
                       'my': ['Myanmar', 'Birmanie'], 'ne': ['Nepalese', "Nepal"],
                       'nl': ['Nederlands', 'Holland', 'Netherlands', 'Flemish'],
                       'no': ['Bokmal', 'Norsk', 'Nynorsk', 'Norweigian'], 'non': ['Nordic', 'Futhark', 'Viking'],
                       'nv': ['Navaho', 'Diné', 'Naabeehó'],
                       'pa': ['Panjabi', 'Punjab', 'Panjab'],
                       'pl': ['Polnish', 'Polnisch', 'Poland', 'Polisch', 'Polski'],
                       'ps': ['Pashtun', 'Pushto', 'Poshtu'],
                       'pt': ['Portugese', 'Portugues', 'Brazilian', 'Portugais',
                              'Brazil', 'Brazilians', 'Portugal', 'Português'],
                       'qu': ['Kichwa'],
                       'ru': ['Russain', 'Russin', 'Russion', 'Rus', 'Rusian', 'Ruski', 'ру́сский', 'Русский'],
                       'sa': ['Samskrit', 'Sandskrit'], 'sc': ['Sardu'],
                       'si': ['Sinhala', 'Sri Lanka', 'Sri Lankan'],
                       'sk': ['Slovakian', 'Slovakia'], 'sl': ['Slovenian', 'Slovenski'],
                       'so': ['Somalia', 'Somalian'], 'sq': ['Shqip', 'Shqipe', 'Tosk'], 'sr': ['Yugoslavian'],
                       'sv': ['Svenska', 'Swede', 'Sweedish', 'Swedisch', 'Swidish', 'Gutnish', 'Sweden'],
                       'sw': ['Kiswahili'], 'syc': ['Classical Syriac'], 'th': ['Thailand', 'Siamese', 'Bangkok'],
                       'tl': ['Filipino', 'Fillipino', 'Philipino', 'Philippines', 'Philippine', 'Phillipene',
                              'Phillipenes'],
                       'tr': ['Turkic', 'Turkce', 'Turkey', 'Türkçe'], 'uk': ['Ukranian', 'Ukraine'],
                       'ur': ['Pakistani', 'Pakistan'],
                       'vi': ['Vietnam', 'Viet', 'Chữ Nôm', 'Annamese'], 'xh': ['Isixhosa'], 'yi': ['Yidish'],
                       'yue': ['Cantonese Chinese', 'Chinese Cantonese', 'Canto', 'Taishanese', 'Guangzhou'],
                       'zh': ['Mandarin', 'Taiwanese', 'Chinease', 'Manderin', 'Zhongwen', '中文', '汉语', '漢語', '國語',
                              'Chinise', 'Chineese', 'Hanzi', 'Cinese', 'Mandrin', 'Mandarin Chinese', 'Taiwan',
                              'China', 'Chn', 'Pinyin', 'Beijinghua', 'Zhongguohua', 'Putonghua', 'Guanhua'],
                       'multiple': ['Various', 'Any', 'All', 'Multi', 'Multi-language', 'Many', 'Everything', 'Anything',
                                    'Every Language', 'Mul'],
                       'unknown': ['Unknown', 'Unkown', 'Unknow', 'Uknown', 'Unknon', 'Unsure', 'Asian', 'Asiatic',
                                   'Not Sure', "Don'T Know", 'Dont Know', 'No Idea', "I Don'T Know",
                                   'Unk', 'Idk', 'Undefined', "Source Language", "Mystery", "Native American",
                                   'Uncertain', "Indian", "Unidentified"],
                       'art': ['Artificial', 'Conlang', 'Constructed', 'Tengwar'],
                       'ang': ['Old English', 'Anglo Saxon', 'Anglosaxon', 'Anglisc'], 'ban': ['Bali'],
                       'haw': ["Hawai'Ian", "Hawaii", "Hawai'I"], 'mk': ['Macedonia'],
                       'zxx': ["Null", "None", "Nothing", "Gibberish", "Nonsense", 'Mojibake'],
                       'br': ['Brezhoneg', 'Berton'], 'dz': ['Bhutanese', 'Zongkhar'], 'fo': ['Faeroese'],
                       'jv': ['Djawa'], 'kl': ['Greenlandic'],
                       'lb': ['Letzeburgesch', 'Letzburgisch', 'Luxembourgeois', 'Luxemburgian', 'Luxemburgish'],
                       'li': ['Limburgan', 'Limburger', 'Limburgs', 'Limburgian', 'Limburgic'], 'mi': ['Māori'],
                       'om': ['Oromoo', 'Oromiffa', 'Oromifa', 'Oromos'], 'ota': ['Ottoman'], 'pi': ['Pāli'],
                       'ug': ['Uighur']}

# These are keywords that must be included in titles. If they don't include this, it'll be rejected and filtered out.
REQUIRED_KEYWORDS = ['>', "to English", "English to", "- Eng", "- English", "- EN", ">EN", "-Eng", "-English", "-EN",
                     "English-", "English -", "< English", "English <", "[Unknown]", "<English", "<english",
                     "< english", "to english", "english to", "ENG -", "ENG-", "~ English", "English ~", "[unknown]",
                     "english <", "English <", "English<", "English To", "To English", "To english", "english To",
                     "- english", "-english", "~ English", "English ~", "to Eng", "Eng to", "[Community]", "[Meta]",
                     "[META]"]
# Below are keywords used to help filtering the posts that come in, but not to remove them per se.
POSTS_KEYWORDS = ["youtube.com", "youtu.be", "to english", "english to"]

# Following lists are lists of ISO codes, in their ISO 639-1/3 equivalents and their names.
ISO_639_1 = ['ab', 'aa', 'af', 'ak', 'sq', 'am', 'ar', 'an', 'hy', 'as', 'av', 'ae', 'ay', 'az', 'bm', 'ba', 'eu', 'be',
             'bn', 'bh', 'bi', 'bs', 'br', 'bg', 'my', 'ca', 'ch', 'ce', 'ny', 'zh', 'cv', 'kw', 'co', 'cr', 'hr', 'cs',
             'da', 'dv', 'nl', 'dz', 'en', 'eo', 'et', 'ee', 'fo', 'fj', 'fi', 'fr', 'ff', 'gl', 'ka', 'de', 'el', 'gn',
             'gu', 'ht', 'ha', 'he', 'hz', 'hi', 'ho', 'hu', 'ia', 'id', 'ie', 'ga', 'ig', 'ik', 'io', 'is', 'it', 'iu',
             'ja', 'jv', 'kl', 'kn', 'kr', 'ks', 'kk', 'km', 'ki', 'rw', 'ky', 'kv', 'kg', 'ko', 'ku', 'kj', 'la', 'lb',
             'lg', 'li', 'ln', 'lo', 'lt', 'lu', 'lv', 'gv', 'mk', 'mg', 'ms', 'ml', 'mt', 'mi', 'mr', 'mh', 'mn', 'na',
             'nv', 'nb', 'nd', 'ne', 'ng', 'nn', 'no', 'ii', 'nr', 'oc', 'oj', 'cu', 'om', 'or', 'os', 'pa', 'pi', 'fa',
             'pl', 'ps', 'pt', 'qu', 'rm', 'rn', 'ro', 'ru', 'sa', 'sc', 'sd', 'se', 'sm', 'sg', 'sr', 'gd', 'sn', 'si',
             'sk', 'sl', 'so', 'st', 'es', 'su', 'sw', 'ss', 'sv', 'ta', 'te', 'tg', 'th', 'ti', 'bo', 'tk', 'tl', 'tn',
             'to', 'tr', 'ts', 'tt', 'tw', 'ty', 'ug', 'uk', 'ur', 'uz', 've', 'vi', 'vo', 'wa', 'cy', 'wo', 'fy', 'xh',
             'yi', 'yo', 'za', 'zu', 'egy', 'arc', 'yue', 'non', 'syc', 'lzh', 'ota', 'multiple', 'unknown']
ISO_639_3 = ['abk', 'aar', 'afr', 'aka', 'als', 'amh', 'arb', 'arg', 'hye', 'asm', 'ava', 'ave', 'ayr', 'azj', 'bam',
             'bak', 'eus', 'bel', 'ben', 'bho', 'bis', 'bos', 'bre', 'bul', 'mya', 'cat', 'cha', 'che', 'nya', 'cmn',
             'chv', 'cor', 'cos', 'crk', 'hrv', 'ces', 'dan', 'div', 'nld', 'dzo', 'eng', 'epo', 'ekk', 'ewe', 'fao',
             'fij', 'fin', 'fra', 'fuf', 'glg', 'kat', 'deu', 'ell', 'grn', 'guj', 'hat', 'hau', 'heb', 'her', 'hin',
             'hmo', 'hun', 'ina', 'ind', 'ile', 'gle', 'ibo', 'ipk', 'ido', 'isl', 'ita', 'ike', 'jpn', 'jav', 'kal',
             'kan', 'kau', 'kas', 'kaz', 'khm', 'kik', 'kin', 'kir', 'kom', 'kon', 'kor', 'ckb', 'kua', 'lat', 'ltz',
             'lug', 'lim', 'lin', 'lao', 'lit', 'lub', 'lvs', 'glv', 'mkd', 'bhr', 'zlm', 'mal', 'mlt', 'mri', 'mar',
             'mah', 'khk', 'nau', 'nav', 'nob', 'nde', 'npi', 'ndo', 'nno', 'nor', 'iii', 'nbl', 'oci', 'oji', 'chu',
             'orm', 'ori', 'oss', 'pan', 'pli', 'pes', 'pol', 'pst', 'por', 'que', 'roh', 'run', 'ron', 'rus', 'san',
             'sro', 'snd', 'sme', 'smo', 'sag', 'srp', 'gla', 'sna', 'sin', 'slk', 'slv', 'som', 'sot', 'spa', 'sun',
             'swh', 'ssw', 'swe', 'tam', 'tel', 'tgk', 'tha', 'tir', 'bod', 'tuk', 'tgl', 'tsn', 'ton', 'tur', 'tso',
             'tat', 'twi', 'tah', 'uig', 'ukr', 'urd', 'uzn', 'ven', 'vie', 'vol', 'wln', 'cym', 'wol', 'fry', 'xho',
             'yih', 'yor', 'zyb', 'zul', 'egy', 'arc', 'yue', 'non', 'syc', 'lzh', 'ota', 'multiple', 'unknown']
ISO_639_2B = {'alb': 'sq', 'arm': 'hy', 'baq': 'eu', 'tib': 'bo', 'bur': 'my', 'cze': 'cs',
              'chi': 'zh', 'wel': 'cy', 'ger': 'de', 'dut': 'nl', 'gre': 'el', 'per': 'fa',
              'fre': 'fr', 'geo': 'ka', 'ice': 'is', 'mac': 'mk', 'mao': 'mi', 'may': 'ms',
              'rum': 'ro', 'slo': 'sk'}
ISO_NAMES = ['Abkhaz', 'Afar', 'Afrikaans', 'Akan', 'Albanian', 'Amharic', 'Arabic', 'Aragonese', 'Armenian',
             'Assamese', 'Avar', 'Avestan', 'Aymara', 'Azerbaijani', 'Bambara', 'Bashkir', 'Basque', 'Belarusian',
             'Bengali', 'Bihari', 'Bislama', 'Bosnian', 'Breton', 'Bulgarian', 'Burmese', 'Catalan', 'Chamorro',
             'Chechen', 'Chichewa', 'Chinese', 'Chuvash', 'Cornish', 'Corsican', 'Cree', 'Croatian', 'Czech', 'Danish',
             'Dhivehi', 'Dutch', 'Dzongkha', 'English', 'Esperanto', 'Estonian', 'Ewe', 'Faroese', 'Fijian', 'Finnish',
             'French', 'Fula', 'Galician', 'Georgian', 'German', 'Greek', 'Guarani', 'Gujarati', 'Haitian Creole',
             'Hausa', 'Hebrew', 'Herero', 'Hindi', 'Hiri Motu', 'Hungarian', 'Interlingua', 'Indonesian', 'Interlingue',
             'Irish', 'Igbo', 'Inupiaq', 'Ido', 'Icelandic', 'Italian', 'Inuktitut', 'Japanese', 'Javanese',
             'Kalaallisut', 'Kannada', 'Kanuri', 'Kashmiri', 'Kazakh', 'Khmer', 'Kikuyu', 'Kinyarwanda', 'Kyrgyz',
             'Komi', 'Kongo', 'Korean', 'Kurdish', 'Kwanyama', 'Latin', 'Luxembourgish', 'Ganda', 'Limburgish',
             'Lingala', 'Lao', 'Lithuanian', 'Luba-Kasai', 'Latvian', 'Manx', 'Macedonian', 'Malagasy', 'Malay',
             'Malayalam', 'Maltese', 'Maori', 'Marathi', 'Marshallese', 'Mongolian', 'Nauruan', 'Navajo',
             'Norwegian Bokmal', 'North Ndebele', 'Nepali', 'Ndonga', 'Norwegian Nynorsk', 'Norwegian', 'Nuosu',
             'Southern Ndebele', 'Occitan', 'Ojibwe', 'Old Church Slavonic', 'Oromo', 'Oriya', 'Ossetian', 'Punjabi',
             'Pali', 'Persian', 'Polish', 'Pashto', 'Portuguese', 'Quechua', 'Romansh', 'Kirundi', 'Romanian',
             'Russian', 'Sanskrit', 'Sardinian', 'Sindhi', 'Northern Sami', 'Samoan', 'Sango', 'Serbian',
             'Scottish Gaelic', 'Shona', 'Sinhalese', 'Slovak', 'Slovene', 'Somali', 'Sotho', 'Spanish', 'Sundanese',
             'Swahili', 'Swati', 'Swedish', 'Tamil', 'Telugu', 'Tajik', 'Thai', 'Tigrinya', 'Tibetan', 'Turkmen',
             'Tagalog', 'Tswana', 'Tonga', 'Turkish', 'Tsonga', 'Tatar', 'Twi', 'Tahitian', 'Uyghur', 'Ukrainian',
             'Urdu', 'Uzbek', 'Venda', 'Vietnamese', 'Volapuk', 'Walloon', 'Welsh', 'Wolof', 'Frisian', 'Xhosa',
             'Yiddish', 'Yoruba', 'Zhuang', 'Zulu', 'Ancient Egyptian', 'Aramaic', 'Cantonese', 'Norse', 'Syriac',
             'Classical Chinese', 'Ottoman Turkish', 'Multiple Languages', 'Unknown']

# The following is a dictionary to add misspellings or alternate names for non-supported ISO 639-1 languages.
# Non-supported ISO 639-3 language names must be added to the CSV listed at the top of this file.
# The ISO 639-3 macro-languages are mapped to their biggest component languages.
# Some function category titles are irregular and are listed on the end (like "Multiple").
ISO_639_1_ALTERNATE = {'aa': ['Afaraf'], 'ab': ['Abxazo', 'Abkhazian'], 'ae': ['Avesta'],
                       'as': ['Asamiya', 'Asambe', 'Asami'], 'av': ['Avaro', 'Avaric'],
                       'bi': ['Bichelamar'],
                       'bh': ['Bhojpuri', 'Maithili', 'Magahi'], 'cv': ["Bulgar"],
                       'dv': ['Divehi', 'Maldivian', 'Divehli'],
                       'en': ['Ingles', 'Inggeris', 'Englisch', 'Inglese', 'Inglesa', 'Engrish', 'Enlighs', 'Engilsh',
                              'Enlish', 'Englishe', 'Engish', 'Engelish', 'Engliah', 'Englisg', 'England', 'Englsih',
                              'Englkish', 'Engilish', 'Enlglish', 'Englsh', 'Enghlish', 'Engligh', 'Englist', 'Engkish',
                              'Ensglish', 'Enhlish', 'Английский', 'английский', 'Inggris', 'Englische', '英語', '영어'
                              'Anglais', 'Engels', 'Engelsk', 'İngilizce', '英文'],
                       'ff': ['Fulah'], 'gl': ['Gallego'],
                       'gv': ['Gailck', 'Manx Gaelic'], 'ha': ['Haoussa', 'Hausawa'], 'ig': ['Ibo'],
                       'ik': ['Inupiat'], 'kg': ['Kikongo'], 'ki': ['Gikuyu'], 'kj': ['Kuanyama'],
                       'ks': ['Kacmiri', 'Kaschemiri', 'Keshur', 'Koshur'],
                       'ky': ['Kirghiz', 'Kirgiz'], 'lg': ['Kiganda'], 'nr': ['Isindebele'],
                       'ny': ['Chewa', 'Nyanja'], 'oj': ['Ojibwa'],
                       'os': ['Ossetic'], 'rn': ['Ikirundi'],
                       'rw': ['Ikinyarwanda', 'Orunyarwanda', 'Ruanda', 'Rwanda', 'Rwandan', 'Urunyaruanda'],
                       'ss': ['Swazi'], 'tn': ['Setswana'], 'to': ['Tongan'], 'vo': ['Volapük']}

# A manually populated dictionary that matches ISO macrolanguages with their most prominent consituent language
ISO_MACROLANGUAGES = {
    "aka": ("twi", ["fat", "twi"]),
    "ara": ("arb", ["aao", "abh", "abv", "acm", "acq", "acw", "acx", "acy", "adf", "aeb", "aec", "afb", "ajp", "apc",
                    "apd", "arb", "arq", "ars", "ary", "arz", "auz", "avl", "ayh", "ayl", "ayn", "ayp", "bbz", "pga",
                    "shu", "ssh"]),
    "aym": ("ayr", ["ayr", "ayc"]),
    "aze": ("azj", ["azj", "azb"]),
    "bal": ("bgp", ["bcc", "bgn", "bgp"]),
    "bik": ("bcl", ["bcl", "bhk", "bln", "bto", "cts", "fbl", "lbl", "rbl", "ubl"]),
    "bnc": ("lbk", ["ebk", "lbk", "obk", "rbk", "vbk"]),
    "bua": ("bxr", ["bxm", "bxr", "bxu"]),
    "chm": ("mhr", ["mhr", "mrj"]),
    "cre": ("crk", ["crj", "crk", "crl", "crm", "csw", "cwd"]),
    "del": ("umu", ["umu", "unm"]),
    "den": ("xsl", ["scs", "xsl"]),
    "din": ("dik", ["dib", "dik", "dip", "diw", "dks"]),
    "doi": ("dgo", ["dgo", "xnr"]),
    "est": ("ekk", ["ekk", "vro"]),
    "fas": ("pes", ["prs", "pes"]),
    "ful": ("fuf", ["ffm", "fub", "fuc", "fue", "fuf", "fuh", "fui", "fuq", "fuv"]),
    "gba": ("gbp", ["bdt", "gbp", "gbq", "gmm", "gso", "gya", "mdo"]),
    "gon": ("ggo", ["esg", "ggo", "gno", "wsg"]),
    "grb": ("grj", ["gbo", "gec", "grj", "grv", "gry"]),
    "grn": ("gug", ["gnw", "gug", "gui", "gun", "nhd"]),
    "hai": ("hdn", ["hax", "hdn"]),
    "hbs": ("hrv", ["bos", "hrv", "srp"]),
    "hmn": ("mww", ["blu", "cqd", "hea", "hma", "hmc", "hmd", "hme", "hmg", "hmh", "hmi", "hmj", "hml", "hmm", "hmp",
                    "hmq", "hms", "hmw", "hmy", "hmz", "hnj", "hrm", "huj", "mmr", "muq", "mww", "sfm"]),
    "iku": ("ike", ["ike", "ikt"]),
    "ipk": ("esi", ["esi", "esk"]),
    "jrb": ("aju", ["ajt", "aju", "jye", "yhd", "yud"]),
    "kau": ("knc", ["kby", "knc", "krt"]),
    "kln": ("niq", ["enb", "eyo", "niq", "oki", "pko", "sgc", "spy", "tec", "tuy"]),
    "kok": ("gom", ["gom", "knn"]),
    "kom": ("kpv", ["koi", "kpv"]),
    "kon": ("kng", ["kng", "kwy", "ldi"]),
    "kpe": ("gkp", ["gkp", "xpe"]),
    "kur": ("kmr", ["ckb", "kmr", "sdh"]),
    "lah": ("skr", ["hnd", "hno", "jat", "phr", "pmu", "pnb", "skr", "xhe"]),
    "lav": ("lvs", ["ltg", "lvs"]),
    "luy": ("lwg", ["bxk", "ida", "lkb", "lko", "lks", "lri", "lrm", "lsm", "lto", "lts", "lwg", "nle", "nyd", "rag"]),
    "man": ("mnk", ["emk", "mku", "mlq", "mnk", "msc", "mwk", "myq"]),
    "mlg": ("plt", ["bhr", "bjq", "bmm", "bzc", "msh", "plt", "skg", "tdx", "tkg", "txy", "xmv", "xmw"]),
    "mon": ("khk", ["khk", "mvf"]),
    "msa": ("zsm", ["bjn", "btj", "bve", "bvu", "coa", "dup", "hji", "ind", "jak", "jax", "kvb", "kvr", "kxd", "lce",
                    "lcf", "liw", "max", "meo", "mfa", "mfb", "min", "mly", "mqg", "msi", "mui", "orn", "ors", "pel",
                    "pse", "tmw", "urk", "vkk", "vkt", "xmm", "zlm", "zmi", "zsm"]),
    "mwr": ("rwr", ["dhd", "mtr", "mve", "rwr", "swv", "wry"]),
    "nep": ("npi", ["npi", "dty"]),
    "nor": ("nob", ["nno", "nob"]),
    "oji": ("ojb", ["ciw", "ojb", "ojc", "ojg", "ojs", "ojw", "otw"]),
    "ori": ("ory", ["ory", "spv"]),
    "orm": ("gaz", ["gaz", "gax", "hae", "orc"]),
    "pus": ("pst", ["pbt", "pbu", "pst"]),
    "que": ("quh", ["cqu", "qub", "qud", "quf", "qug", "quh", "quk", "qul", "qup", "qur", "qus", "quw", "qux", "quy",
                    "quz", "qva", "qvc", "qve", "qvh", "qvi", "qvj", "qvl", "qvm", "qvn", "qvo", "qvp", "qvs", "qvw",
                    "qvz", "qwa", "qwc", "qwh", "qws", "qxa", "qxc", "qxh", "qxl", "qxn", "qxo", "qxp", "qxr", "qxt",
                    "qxu", "qxw"]),
    "raj": ("mup", ["bgq", "gda", "gju", "hoj", "mup", "wbr"]),
    "rom": ("rmy", ["rmc", "rmf", "rml", "rmn", "rmo", "rmw", "rmy"]),
    "sqi": ("als", ["aae", "aat", "aln", "als"]),
    "srd": ("src", ["sdc", "sdn", "src", "sro"]),
    "swa": ("swh", ["swh", "swc"]),
    "syr": ("cld", ["aii", "cld"]),
    "tmh": ("ttq", ["taq", "thv", "thz", "ttq"]),
    "uzb": ("uzn", ["uzn", "uzs"]),
    "yid": ("ydd", ["ydd", "yih"]),
    "zap": ("zai", ["zaa", "zab", "zac", "zad", "zae", "zaf", "zai", "zam", "zao", "zaq", "zar", "zas", "zat", "zav",
                    "zaw", "zax", "zca", "zoo", "zpa", "zpb", "zpc", "zpd", "zpe", "zpf", "zpg", "zph", "zpi", "zpj",
                    "zpk", "zpl", "zpm", "zpn", "zpo", "zpp", "zpq", "zpr", "zps", "zpt", "zpu", "zpv", "zpw", "zpx",
                    "zpy", "zpz", "zsr", "ztc", "zte", "ztg", "ztl", "ztm", "ztn", "ztp", "ztq", "zts", "ztt", "ztu",
                    "ztx", "zty"]),
    "zha": ("zyb", ["ccx", "ccy", "zch", "zeh", "zgb", "zgm", "zgn", "zhd", "zhn", "zlj", "zln", "zlq", "zqe", "zyb",
                    "zyg", "zyj", "zyn", "zzj"]),
    "zho": ("cmn", ["cdo", "cjy", "cmn", "cpx", "czh", "czo", "gan", "hak", "hsn", "lzh", "mnp", "nan", "wuu", "yue"]),
    "zza": ("kiu", ["diq", "kiu"])}

# These are lists of language learning or country subreddits associated with a specific language.
# The language learning one should be the FIRST one in the list. The rest can be country or cultural ones.
# These subreddits are included in the language reference data.
LANGUAGE_SUBREDDITS = {"Afrikaans": ["r/afrikaans"], "Albanian": ["r/albanian"], "Amharic": ["r/amharic"],
                       "American Sign Language": ["r/asl"], "Ancient Egyptian": ["r/ancientegypt"],
                       "Ancient Greek": ["r/ancientgreek"],
                       "Arabic": ["r/learn_arabic", "r/arabic", "r/arabs", "r/learnarabic"],
                       "Aramaic": ["r/aramaic"], "Armenian": ["r/hayeren"], "Assamese": ["r/assam"],
                       "Avestan": ["r/avestan"], "Basque": ["r/basque"], "Belarusian": ["r/belarusian"],
                       "Bengali": ["r/bengalilanguage"],
                       "Breton": ["r/breton"], "Burmese": ["r/lanl_burmese"], "Cantonese": ["r/cantonese"],
                       "Catalan": ["r/catalan"], "Chechen": ["r/chechnya"],
                       "Chinese": ["r/chineselanguage", "r/chinese", "r/mandarin", "r/learnchinese"],
                       "Cornish": ["r/kernowek"], "Croatian": ["r/croatian"], "Danish": ["r/danishlanguage"],
                       "Czech": ["r/learnczech"], "Dutch": ["r/learndutch"], "English": ["r/englishlearning"],
                       "Esperanto": ["r/esperanto"], "Estonian": ["r/eesti"], "Faroese": ["r/faroese"],
                       "Finnish": ["r/learnfinnish"], "French": ["r/french", "r/france", "r/frenchimmersion"],
                       "German": ["r/german", "r/de", "r/germany"], "Greek": ["r/greek"], "Haitian Creole": ["r/haiti"],
                       "Hawaiian": ["r/learn_hawaiian"], "Hebrew": ["r/hebrew", "r/israel"], "Hindi": ["r/hindi"],
                       "Hungarian": ["r/hungarian", "r/hungary"], "Icelandic": ["r/learnicelandic"], "Ido": ["r/ido"],
                       "Indonesian": ["r/indonesian"], "Interlingua": ["r/interlingua"],
                       "Interlingue": ["r/interlingue"], "Inuktitut": ["r/inuktitut"], "Irish": ["r/gaeilge"],
                       "Italian": ["r/italianlearning"],
                       "Japanese": ["r/learnjapanese", "r/japan", "r/japanese", "r/nihongo"],
                       "Kalaallisut": ["r/kalaallisut"], "Kannada": ["r/kannada"], "Khmer": ["r/learnkhmer"],
                       "Klingon": ['r/tlhinganhol'],
                       "Korean": ["r/korean", "r/korea", "r/koreantranslate"], "Kyrgyz": ["r/learnkyrgyz"],
                       "Lao": ["r/laos"], "Latin": ["r/latin", "r/mylatintattoo", "r/latina"],
                       "Latvian": ["r/learnlatvian"], "Luxembourgish": ["r/luxembourg"], "Malagasy": ["r/madagascar"],
                       "Manx": ["r/gaelg"], "Maori": ["r/maori"], "Malay": ["r/bahasamelayu"],
                       "Malayalam": ['r/malayalam'], "Marathi": ["r/marathi"],
                       "Mongolian": ["r/mongolian"], "Norwegian": ["r/norsk"], "Occitan": ["r/occitan"],
                       "Pali": ["r/pali"], "Pashto": ["r/pashto"],
                       "Persian": ["r/farsi", "r/iran", "r/learnfarsi", "r/persian"],
                       "Polish": ["r/learnpolish", "r/poland"],
                       "Portuguese": ["r/portuguese", "r/portugal", "r/brazil"], "Punjabi": ["r/punjabi"],
                       "Quechua": ["r/learnquechua"], "Romanian": ["r/romanian"], "Russian": ["r/russian", "r/russia"],
                       "Sanskrit": ["r/sanskrit"], "Scottish Gaelic": ["r/gaidhlig"], " Serbian": ["r/serbian"],
                       "Sinhalese": ["r/sinhala"], "Spanish": ["r/spanish", "r/learnspanish", "r/argentina"],
                       "Swahili": ["r/swahili"], "Swedish": ["r/svenska", "r/sweden"], "Tagalog": ["r/tagalog"],
                       "Tamil": ["r/tamil"], "Telugu": ["r/telugu"], "Thai": ["r/learnthai", "r/thailand"],
                       "Tibetan": ["r/tibet", "r/tibetanlanguage"], "Turkish": ["r/turkishlearning", "r/turkey"],
                       "Ukrainian": ["r/ukrainian"], "Urdu": ["r/urdu"], "Uzbek": ["r/learn_uzbek"],
                       "Vietnamese": ["r/vietnamese", "r/vietnam", "r/learnvietnamese"], "Volapuk": ["r/volapuk"],
                       "Welsh": ["r/learnwelsh", "r/cymru", "r/wales"], "Yiddish": ["r/yiddish"]}

# Keywords used for thanks. This is included in the crosspost responses and the notifications sign ups.
THANKS_WORDS = {"Afrikaans": "Dankie", "Albanian": "Falemenderit", "Amharic": "አመሰግናለሁ", "Ancient Egyptian": "Dua",
                "Ancient Greek": "Ἐπαινῶ",
                "Anglo-Saxon": "Þancas", "Arabic": "ﺷﻜﺮﺍﹰ", "Aramaic": "Yishar", "Armenian": "մերսի",
                "Azerbaijani": "Təşəkkür edirəm",
                "Balinese": "Suksma", "Basque": "Eskerrik asko", "Belarusian": "Дзякуй", "Bengali": "ধন্যবাদ",
                "Bosnian": "Hvala", "Bulgarian": "благодаря", "Burmese": "Cè-zù tin-ba-deh", "Breton": "Trugarez",
                "Cantonese": "多謝",
                "Catalan": "Gràcies", "Cebuano": "Salamat", "Cherokee": "ᏩᏙ", "Chinese": "謝謝",
                "Coptic": 'Sephmot',
                "Corsican": "À ringraziavvi",
                "Croatian": "Hvala", "Czech": "Dík", "Danish": "Tak", "Dutch": "Dank u", "Esperanto": "Dankon",
                "Estonian": "Tänan", "Faroese": "Takk",
                "Finnish": "Kiitos", "French": "Merci", "German": "Danke", "Georgian": "გმადლობთ", "Greek": "Ευχαριστώ",
                "Gujarati": "ધન્યવાદ", "Haitian Creole": "Mesi", "Hawaiian": "Mahalo",
                "Hebrew": "תודה רבה", "Hindi": "धन्यवाद",
                "Hungarian": "Köszi", "Icelandic": "Takk", "Indonesian": "Terima kasih", "Inuktitut": "ᖁᔭᓇᐃᓐᓂ",
                "Irish": "Go raibh míle maith agat", "Italian": "Grazie", "Japanese": "ありがとう",
                "Kalaallisut": "Qujan", "Kazakh": "Рахмет",
                "Khmer": "ឣរគុណ", "Korean": "감사합니다", "Kurdish": "سوپاس", "Lao": "ຂອບໃຈ", "Latin": "Grātiās tibi agō",
                "Latvian": "Paldies", "Lithuanian": "Ačiū", "Macedonian": "Благодарам",
                "Malagasy": "Misaotra",
                "Malay": "Terima kasih", "Malayalam": "നന്ദി", "Maltese": "Grazzi", "Maori": "Kia ora",
                "Marathi": "आभारी आहे", "Mongolian": "Баярлалаа", "Navajo": "Ahéhee'",
                "Nepali": "धन्यवाद", "Norse": "Þakka",
                "Norwegian": "Takk", "Pashto": "مننه", "Persian": "ممنونم", "Polish": "Dzięki",
                "Portuguese": "Obrigado", "Punjabi": "ਧਨਵਾਦ", "Quechua": "Solpayki",
                "Romanian": "Mersi", "Russian": "Спаси́бо",
                "Sanskrit": "धन्यवादाः", "Sardinian": "Grazie", "Scottish Gaelic": "Tapadh leat", "Serbian": "Хвала",
                "Sinhalese": "Istuti", "Slovak": "Ďakujem", "Slovene": "Hvala", "Somali": "Mahadsanid",
                "Spanish": "Gracias", "Swahili": "Asante", "Swedish": "Tack", "Tagalog": "Salamat",
                "Tamil": "நன்றி", "Telugu": "ధన్యవాదములు", "Thai": "ขอบคุณ", "Tibetan": "ཐུགས་རྗེ་ཆེ་།",
                "Turkish": "Teşekkür ederim", "Ukrainian": "Дякую", "Urdu": "شكريه", "Uzbek": "Rahmat",
                "Vietnamese": "Cảm ơn", "Welsh": "Diolch", "Xhosa": "Ndiyabulela", "Yoruba": "O se",
                "Yiddish": "שכח", "Zulu": "Ngiyabonga"}

# An ISO 3166 list of countries and their equivalent codes and words. Used for determining regional dialects.
COUNTRY_LIST = [
    ("Afghanistan", "AF", "AFG", "004", ["Afghan", "Afghani"]),
    ("Albania", "AL", "ALB", "008"),
    ("Algeria", "DZ", "DZA", "012", ["Algerian", "Algerien"]),
    ("Andorra", "AD", "AND", "020", ["Andorran"]),
    ("Angola", "AO", "AGO", "024", ["Angolan"]),
    ("Anguilla", "AI", "AIA", "660"),
    ("Antigua and Barbuda", "AG", "ATG", "028"),
    ("Argentina", "AR", "ARG", "032", ["Argentinian", "Argentine"]),
    ("Armenia", "AM", "ARM", "051"),
    ("Aruba", "AW", "ABW", "533"),
    ("Australia", "AU", "AUS", "036", ["Australian", "Straya"]),
    ("Austria", "AT", "AUT", "040", ["Austrian", "Vienna", "Osterreich"]),
    ("Azerbaijan", "AZ", "AZE", "031"),
    ("Bahamas", "BS", "BHS", "044"),
    ("Bahrain", "BH", "BHR", "048", ["Bahrani"]),
    ("Bangladesh", "BD", "BGD", "050"),
    ("Barbados", "BB", "BRB", "052"),
    ("Belarus", "BY", "BLR", "112"),
    ("Belgium", "BE", "BEL", "056", ["Belgian", "Brussels", "Belgien"]),
    ("Belize", "BZ", "BLZ", "084"),
    ("Benin", "BJ", "BEN", "204"),
    ("Bermuda", "BM", "BMU", "060"),
    ("Bhutan", "BT", "BTN", "064"),
    ("Bolivia, Plurinational State of", "BO", "BOL", "068", ["Bolivian"]),
    ("Bosnia and Herzegovina", "BA", "BIH", "070"),
    ("Botswana", "BW", "BWA", "072"),
    ("Brazil", "BR", "BRA", "076", ["Brazilian", "Brasil", "Brazilien", "Brazillian"]),
    ("Brunei", "BN", "BRN", "096", ["Bruneian", "Darussalam"]),
    ("Bulgaria", "BG", "BGR", "100"),
    ("Burkina Faso", "BF", "BFA", "854"),
    ("Burundi", "BI", "BDI", "108"),
    ("Cambodia", "KH", "KHM", "116"),
    ("Cameroon", "CM", "CMR", "120"),
    ("Canada", "CA", "CAN", "124", ["Canadian", "Quebec", "Quebecois"]),
    ("Cabo Verde", "CV", "CPV", "132"),
    ("Cayman Islands", "KY", "CYM", "136"),
    ("Central African Republic", "CF", "CAF", "140"),
    ("Chad", "TD", "TCD", "148"),
    ("Chile", "CL", "CHL", "152", ["Chilean"]),
    ("China", "CN", "CHN", "156", ["Zhongguo"]),
    ("Colombia", "CO", "COL", "170", ["Colombian"]),
    ("Comoros", "KM", "COM", "174"),
    ("Congo", "CG", "COG", "178"),
    ("Congo, Democratic Republic of the", "CD", "COD", "180", ["Congolese"]),
    ("Cook Islands", "CK", "COK", "184"),
    ("Costa Rica", "CR", "CRI", "188", ["Costa Rican"]),
    ("Côte d'Ivoire", "CI", "CIV", "384", ["Ivory Coast"]),
    ("Croatia", "HR", "HRV", "191"),
    ("Cuba", "CU", "CUB", "192", ["Cuban", "Havana"]),
    ("Curaçao", "CW", "CUW", "531"),
    ("Cyprus", "CY", "CYP", "196", ["Cypriot"]),
    ("Czech Republic", "CZ", "CZE", "203", ["Czechia"]),
    ("Denmark", "DK", "DNK", "208"),
    ("Djibouti", "DJ", "DJI", "262"),
    ("Dominica", "DM", "DMA", "212"),
    ("Dominican Republic", "DO", "DOM", "214", ["Dominican"]),
    ("Ecuador", "EC", "ECU", "218", ["Ecuadorian"]),
    ("Egypt", "EG", "EGY", "818", ["Egyptian"]),
    ("El Salvador", "SV", "SLV", "222", ["El Salvadorian"]),
    ("Equatorial Guinea", "GQ", "GNQ", "226"),
    ("Eritrea", "ER", "ERI", "232"),
    ("Estonia", "EE", "EST", "233"),
    ("Ethiopia", "ET", "ETH", "231"),
    ("Faroe Islands", "FO", "FRO", "234"),
    ("Fiji", "FJ", "FJI", "242", ["Fijian"]),
    ("Finland", "FI", "FIN", "246", ["Finnish"]),
    ("France", "FR", "FRA", "250"),
    ("Gabon", "GA", "GAB", "266"),
    ("Gambia", "GM", "GMB", "270"),
    ("Georgia", "GE", "GEO", "268"),
    ("Germany", "DE", "DEU", "276"),
    ("Ghana", "GH", "GHA", "288"),
    ("Greece", "GR", "GRC", "300"),
    ("Greenland", "GL", "GRL", "304"),
    ("Grenada", "GD", "GRD", "308"),
    ("Guadeloupe", "GP", "GLP", "312"),
    ("Guam", "GU", "GUM", "316"),
    ("Guatemala", "GT", "GTM", "320", ["Guatemalan"]),
    ("Guernsey", "GG", "GGY", "831"),
    ("Guinea", "GN", "GIN", "324"),
    ("Guinea-Bissau", "GW", "GNB", "624"),
    ("Guyana", "GY", "GUY", "328", ["Guyanese"]),
    ("Haiti", "HT", "HTI", "332", ["Haitian"]),
    ("Holy See", "VA", "VAT", "336", ["Vatican"]),
    ("Honduras", "HN", "HND", "340", ["Honduran"]),
    ("Hong Kong", "HK", "HKG", "344"),
    ("Hungary", "HU", "HUN", "348"),
    ("Iceland", "IS", "ISL", "352"),
    ("India", "IN", "IND", "356", ["Indian"]),
    ("Indonesia", "ID", "IDN", "360"),
    ("Iran, Islamic Republic of", "IR", "IRN", "364"),
    ("Iraq", "IQ", "IRQ", "368", ["Iraqi", "Baghdad"]),
    ("Ireland", "IE", "IRL", "372", ["Irish", "Hiberno"]),
    ("Isle of Man", "IM", "IMN", "833"),
    ("Israel", "IL", "ISR", "376", ["Israeli"]),
    ("Italy", "IT", "ITA", "380"),
    ("Jamaica", "JM", "JAM", "388"),
    ("Japan", "JP", "JPN", "392"),
    ("Jordan", "JO", "JOR", "400", ["Jordanian"]),
    ("Kazakhstan", "KZ", "KAZ", "398"),
    ("Kenya", "KE", "KEN", "404", ["Kenyan"]),
    ("Kiribati", "KI", "KIR", "296"),
    ("North Korea", "KP", "PRK", "408", ["North Korean", "Dprk"]),
    ("South Korea", "KR", "KOR", "410", ["South Korean"]),
    ("Kuwait", "KW", "KWT", "414", ["Kuwaiti"]),
    ("Kyrgyzstan", "KG", "KGZ", "417"),
    ("Laos", "LA", "LAO", "418", ["Laotian"]),
    ("Latvia", "LV", "LVA", "428"),
    ("Lebanon", "LB", "LBN", "422", ["Lebanese", "Beirut"]),
    ("Lesotho", "LS", "LSO", "426"),
    ("Liberia", "LR", "LBR", "430"),
    ("Libya", "LY", "LBY", "434", ["Libyan", "Tripoli"]),
    ("Liechtenstein", "LI", "LIE", "438"),
    ("Lithuania", "LT", "LTU", "440"),
    ("Luxembourg", "LU", "LUX", "442"),
    ("Macao", "MO", "MAC", "446", ["Macau", "Aomen"]),
    ("Macedonia, the former Yugoslav Republic of", "MK", "MKD", "807"),
    ("Madagascar", "MG", "MDG", "450"),
    ("Malawi", "MW", "MWI", "454"),
    ("Malaysia", "MY", "MYS", "458", ["Malaysian", "Malaysien"]),
    ("Maldives", "MV", "MDV", "462"),
    ("Mali", "ML", "MLI", "466"),
    ("Malta", "MT", "MLT", "470", ["Maltese"]),
    ("Mauritania", "MR", "MRT", "478"),
    ("Mauritius", "MU", "MUS", "480"),
    ("Mexico", "MX", "MEX", "484", ["Mexican"]),
    ("Micronesia, Federated States of", "FM", "FSM", "583"),
    ("Moldova, Republic of", "MD", "MDA", "498", ["Moldovan"]),
    ("Monaco", "MC", "MCO", "492"),
    ("Mongolia", "MN", "MNG", "496"),
    ("Montenegro", "ME", "MNE", "499"),
    ("Morocco", "MA", "MAR", "504", ["Moroccan"]),
    ("Mozambique", "MZ", "MOZ", "508"),
    ("Myanmar", "MM", "MMR", "104"),
    ("Namibia", "NA", "NAM", "516", ["Namibian"]),
    ("Nauru", "NR", "NRU", "520"),
    ("Nepal", "NP", "NPL", "524"),
    ("Netherlands", "NL", "NLD", "528", ["Holland"]),
    ("New Zealand", "NZ", "NZL", "554", ["Kiwi", "New Zealander", "Aotearoa"]),
    ("Nicaragua", "NI", "NIC", "558", ["Nicaraguan"]),
    ("Niger", "NE", "NER", "562", ["Nigerien"]),
    ("Nigeria", "NG", "NGA", "566", ["Nigerian"]),
    ("Norway", "NO", "NOR", "578", ["Norwegian"]),
    ("Oman", "OM", "OMN", "512", ["Omani"]),
    ("Pakistan", "PK", "PAK", "586"),
    ("Palau", "PW", "PLW", "585"),
    ("Palestine, State of", "PS", "PSE", "275", ["Palestinian", "West Bank", "Gaza"]),
    ("Panama", "PA", "PAN", "591", ["Panaman"]),
    ("Papua New Guinea", "PG", "PNG", "598"),
    ("Paraguay", "PY", "PRY", "600", ["Paraguayan"]),
    ("Peru", "PE", "PER", "604", ["Peruvian", "Lima"]),
    ("Philippines", "PH", "PHL", "608"),
    ("Poland", "PL", "POL", "616"),
    ("Portugal", "PT", "PRT", "620"),
    ("Puerto Rico", "PR", "PRI", "630", ["Puerto Rican", "Boriqua"]),
    ("Qatar", "QA", "QAT", "634", ["Qatari"]),
    ("Romania", "RO", "ROU", "642"),
    ("Russia", "RU", "RUS", "643", ["Russian"]),
    ("Rwanda", "RW", "RWA", "646", ["Rwandan"]),
    ("Samoa", "WS", "WSM", "882"),
    ("San Marino", "SM", "SMR", "674"),
    ("Sao Tome and Principe", "ST", "STP", "678"),
    ("Saudi Arbia", "SA", "SAU", "682", ["Saudi", "Riyadh", "Jeddah", "Saudia"]),
    ("Senegal", "SN", "SEN", "686"),
    ("Serbia", "RS", "SRB", "688"),
    ("Seychelles", "SC", "SYC", "690"),
    ("Sierra Leone", "SL", "SLE", "694"),
    ("Singapore", "SG", "SGP", "702", ["Singaporean"]),
    ("Slovakia", "SK", "SVK", "703"),
    ("Slovenia", "SI", "SVN", "705"),
    ("Somalia", "SO", "SOM", "706", ["Somali", "Mogadishu"]),
    ("South Africa", "ZA", "ZAF", "710"),
    ("South Sudan", "SS", "SSD", "728"),
    ("Spain", "ES", "ESP", "724"),
    ("Sri Lanka", "LK", "LKA", "144", ["Ceylon"]),
    ("Sudan", "SD", "SDN", "729", ["Sudanese"]),
    ("Suriname", "SR", "SUR", "740", ["Surinamese"]),
    ("Swaziland", "SZ", "SWZ", "748"),
    ("Sweden", "SE", "SWE", "752", ["Swedish", "Svedish"]),
    ("Switzerland", "CH", "CHE", "756", ["Swiss", "Schweiz"]),
    ("Syria", "SY", "SYR", "760", ["Syrian", "Levant", "Al-sham"]),
    ("Taiwan, Province of China", "TW", "TWN", "158", ["Taiwanese", "Taipei"]),
    ("Tajikistan", "TJ", "TJK", "762"),
    ("Tanzania, United Republic of", "TZ", "TZA", "834", ["Tanzanian"]),
    ("Thailand", "TH", "THA", "764"),
    ("Timor-Leste", "TL", "TLS", "626", ["East Timor"]),
    ("Togo", "TG", "TGO", "768"),
    ("Tokelau", "TK", "TKL", "772"),
    ("Tonga", "TO", "TON", "776"),
    ("Trinidad and Tobago", "TT", "TTO", "780"),
    ("Tunisia", "TN", "TUN", "788", ["Tunisian"]),
    ("Turkey", "TR", "TUR", "792"),
    ("Turkmenistan", "TM", "TKM", "795"),
    ("Tuvalu", "TV", "TUV", "798"),
    ("Uganda", "UG", "UGA", "800", ["Ugandan"]),
    ("Ukraine", "UA", "UKR", "804", ["Ukrainian"]),
    ("United Arb Emirates", "AE", "ARE", "784", ["Dubai", "Abu Dhabi"]),
    ("United Kingdom", "GB", "GBR", "826", ["British", "England", "London"]),
    ("United Kingdom", "UK", "UKE", "826", ["British", "England", "London"]),
    ("United States", "US", "USA", "840", ["America", "Amerikaner", "American"]),
    ("Uruguay", "UY", "URY", "858", ["Uruguayan", "Montevideo"]),
    ("Uzbekistan", "UZ", "UZB", "860"),
    ("Vanuatu", "VU", "VUT", "548"),
    ("Venezuela", "VE", "VEN", "862", ["Venezuelan"]),
    ("Vietnam", "VN", "VNM", "704", ["Viet Nam"]),
    ("Kosovo", "XK", "XKK", "999", ["Kosovar"]),
    ("Yemen", "YE", "YEM", "887", ["Yemeni", "Sanaa"]),
    ("Zambia", "ZM", "ZMB", "894", ["Zambian"]),
    ("Zimbabwe", "ZW", "ZWE", "716")]

LANGUAGE_COUNTRY_ASSOCIATED = {
    "af": ["NA"],
    "ar": ["AE", "CY", "DZ", "BH", "DJ", "EG", "IL", "IQ", "JO", "KW", "LB", "LY", "MA", "ML", "OM", "PS", "SA", "SO",
           "SD", "SS",
           "SY", "TD", "TN", "YE"],
    "ay": ["PE", "CL", "BO"],
    "de": ["AT", "BE", "CH"],
    "el": ["CY"],
    # "en": ["AU", "GB", "US"],  # We do not use the regional language associations for English
    "es": ["MX", "VE", "AR", "BO", "CL", "CO", "CR", "CU", "DO", "EC", "SV", "GQ", "GT", "HN", "NI", "PA",
           "PY", "PE", "PR", "UY"],
    "fa": ["AF"],
    "ff": ["SN", "GM", "MR", "SL", "GN", "GW", "ML", "GH", "TG", "BJ", "BF", "NE", "SD", "TD", "CM", "CF", "NG"],
    "fr": ["BE", "CA", "CF", "CD", "DJ", "GQ", "HT", "ML", "NE", "SN", "CH", "TG"],
    "gn": ["PY", "AR", "BO"],
    "ha": ["NE", "NG", "TD"],
    "hi": ["FJ"],
    "kw": ["AO", "NA"],
    "ms": ["BN", "SG"],
    "nl": ["BE", "SR"],
    "om": ["ET", "KE"],
    "pt": ["AO", "BR", "MZ", "TL", "CV"],
    "ro": ["MD"],
    "sq": ["XK"],
    "sr": ["ME"],
    "sw": ["CD", "TZ", "KE", "UG"],
    "ta": ["SG"],
    "tr": ["CY"],
    "uz": ["AF"],
    "yue": ["HK", "MO"],
    "zh": ["TW"]
}
# For now we hard-code these specific languages and the countries in which their varieties are spoken.
ISO_DEFAULT_ASSOCIATED = ['af-ZA', 'sq-AL', 'am-ET', 'hy-AM', 'eu-ES', 'be-BY', 'bn-BD', 'bs-BA', 'my-MM', 'yue-HK',
                          'ca-ES', 'zh-CN', 'cs-CZ', 'da-DK', 'et-EE', 'ka-GE', 'el-GR', 'gu-IN', 'he-IL', 'hi-IN',
                          'hu-HU', 'ga-IE', 'ja-JP', 'kk-KZ', 'km-KH', 'ko-KR', 'ku-IQ', 'ms-MY', 'mr-IN', 'ps-AF',
                          'fa-IR', 'pa-PK', 'sr-RS', 'si-LK', 'sl-SI', 'sv-SE', 'tl-PH', 'ta-IN', 'te-IN', 'uk-UA',
                          'ur-PK', 'vi-VN', 'zu-ZA']
# A dictionary with languages as keys and country codes as values. 
ISO_LANGUAGE_COUNTRY_ASSOCIATED = {
    "ar-CY": "acy",
    "ar-DZ": "arq",
    "ar-BH": "abv",
    "ar-TD": "shu",
    "ar-EG": "arz",
    "ar-KW": "afb",
    "ar-IQ": "acm",
    "ar-AE": "afb",
    "ar-LB": "apc",
    "ar-SY": "apc",
    "ar-LY": "ayl",
    "ar-SA": "acw",
    "ar-OM": "acx",
    "ar-IL": "ajp",
    "ar-PS": "ajp",
    "ar-JO": "ajp",
    "ar-SD": "apd",
    "ar-TN": "aeb",
    "ay-PE": "ayc",
    "ay-CL": "ayr",
    "ay-BO": "ayr",
    "de-CH": "gsw",
    "fa-AF": "prs",
    "ff-SN": "fuc",
    "ff-GM": "fuc",
    "ff-MR": "fuc",
    "ff-SL": "fuf",
    "ff-GN": "fuf",
    "ff-GH": "ffm",
    "ff-ML": "ffm",
    "ff-BJ": "fue",
    "ff-TG": "fue",
    "ff-BF": "fuh",
    "ff-NE": "fuh",
    "ff-NG": "fuv",
    "ff-CM": "fub",
    "ff-TD": "fub",
    "ff-SD": "fub",
    "ff-CF": "fui",
    "gn-BO": "gui",
    "hi-FJ": "hif",
    "om-KE": "gax",
    "ms-BN": "kxd",
    "sw-CD": "swc",
    "uz-AF": "uzs",
    "sq-XK": "aln"
}
# Commonly confused country codes with language codes. (country code: language code)
# ONLY use ISO-3166 country codes that do not correspond to an ISO 639-1 code.
MISTAKE_ABBREVIATIONS = {'jp': 'ja', 'cz': 'cs', 'cn': 'zh', 'dk': 'da', 'gr': 'el', 
                         'kh': 'km', 'tj': 'tg', 'ua': 'uk', 'vn': 'vi'}


def fuzzy_text(word):  # A quick function that assesses misspellings of supported languages
    for language in SUPPORTED_LANGUAGES:
        closeness = fuzz.ratio(language, word)
        if closeness > 75:
            return str(language)


def alternate_search(searchfor, is_supported):  # Values should be a dictionary
    if is_supported:
        for k in SUPPORTED_ALTERNATE:
            for v in SUPPORTED_ALTERNATE[k]:
                if searchfor in v:
                    if v == searchfor:  # The two are exactly identical.
                        return k
                    else:
                        continue  # Try again
    elif not is_supported:
        for k in ISO_639_1_ALTERNATE:
            for v in ISO_639_1_ALTERNATE[k]:
                if searchfor in v:
                    return k
    return ""


def transbrackets_new(title):  # a simple function that takes a bracketed tag, moves it to the front

    if ']' in title:  # There is a defined end to this tag.
        bracketed_tag = re.search('\[(.+)\]', title)
        bracketed_tag = bracketed_tag.group(0)
        title_remainder = title.replace(bracketed_tag, "")
    else:  # No closing tag...
        bracketed_tag = title.split("[", 1)[1]
        title_remainder = title.replace(bracketed_tag, "")
        title_remainder = title_remainder[:-1]
        bracketed_tag = "[" + bracketed_tag + "]"  # enclose it

    # print(bracketed_tag)
    reformed_title = "{} {}".format(bracketed_tag, title_remainder)

    return reformed_title


def lang_code_search(search_term, script_search):
    # Returns a tuple: name of a code or a script, is it a script? (that's a boolean)
    codes_list = []
    names_list = []
    alternate_names_list = []  # List of alternate names for languages in ISO 639-3
    is_script = False

    if len(search_term) == 4:
        is_script = True

    csv_file = csv.reader(open(FILE_ADDRESS_ISO_ALL, "rt", encoding="utf-8"), delimiter=",")
    for row in csv_file:
        codes_list.append(row[0])
        names_list.append(row[2:][0])  # It is normally returned as a list, so we need to convert into a string.
        alternate_names_list.append(row[3:][0])

    if len(search_term) == 3:  # This is a ISO 639-3 code
        if search_term in codes_list:
            item_index = codes_list.index(search_term)
            item_name = names_list[item_index]
            # Since the first two rows are the language code and 639-1 code, we take it from the third.
            return item_name, is_script
        else:
            return "", False
    elif len(search_term) == 4 and script_search is True:  # This is a script
        if search_term in codes_list:
            item_index = codes_list.index(search_term)
            item_name = names_list[
                item_index]  # Since the first two rows are the language code and 639-1 code, we take it from the third.
            is_script = True
            return item_name, is_script
    elif len(search_term) > 3 and script_search is False:  # Probably a name, so let's get the code
        if search_term in names_list:  # The name is in the code list
            item_index = names_list.index(search_term)
            item_code = codes_list[item_index]
            item_code = str(item_code)
            if len(item_code) == 3:  # This is a language code
                return item_code, False
            else:  # probably a script, then
                return item_code, True
        else:  # No name was found, let's check alternates.
            item_code = ""
            for name in alternate_names_list:
                if ';' in name:  # There are multiple alternate names here
                    sorted_alternate = name.split('; ')
                else:
                    sorted_alternate = [name]  # Convert into an iterable list.

                for alternate in sorted_alternate:
                    if search_term == alternate.title().strip():  # We found an alternate
                        item_index = alternate_names_list.index(name)
                        item_code = str(codes_list[item_index])
                        break  # We're done. We can exit

            if len(item_code) == 3:
                return item_code, False
            elif len(item_code) == 4:
                return item_code, True
            else:  # No matches whatsoever, let's exit, returning blank.
                return "", False


def country_converter(text_input, abbreviations_okay=True):  # Function that detects a country name in a word given.
    # abbreviations_okay means it's okay to check the list for abbreviations.

    # Set default values
    country_code = ""
    country_name = ""

    if len(text_input) <= 1:  # Too short, can't return anything for this.
        pass
    elif len(text_input) == 2 and abbreviations_okay is True:  # This is only two letters long
        text_input = text_input.upper()  # Convert to upper case
        for country in COUNTRY_LIST:
            # print(country[1])
            if text_input == country[1]:  # Matches exactly
                country_code = text_input
                country_name = country[0]
    elif len(text_input) == 3 and abbreviations_okay is True:  # three letters long code
        text_input = text_input.upper()  # Convert to upper case
        for country in COUNTRY_LIST:
            # print(country[1])
            if text_input == country[2]:  # Matches exactly
                country_code = country[1]
                country_name = country[0]
    else:  # It's longer than three, probably a name. Or abbreviations are disabled.
        text_input = text_input.title()
        for country in COUNTRY_LIST:
            if text_input == country[0]:  # It's an exact match
                country_code = country[1]
                country_name = country[0]
                return country_code, country_name  # Exit the loop, we're done. 
            elif text_input in country[0] and len(text_input) >= 3:
                country_code = country[1]
                country_name = country[0]

        if country_code == "" and country_name == "":  # Still nothing
            # Now we check against a list of associated words per country.
            for country in COUNTRY_LIST:
                try:
                    country_keywords = country[4]  # These are keywords associated with it. 
                    for keyword in country_keywords:
                        if text_input.title() == keyword:  # A Match!
                            country_code = country[1]
                            country_name = country[0]
                except IndexError:
                    # No keywords associated with this country. 
                    pass

    if "," in country_name:  # There's a comma.
        country_name = country_name.split(",")[0].strip()
        # Take first part if there's a comma (Taiwan, Province of China)

    return country_code, country_name


def converter(language):
    """A function that can tell us if a language is supported.
    Returns a tuple with Code, Name, Supported (boolean), country (if present).
    This is one of the most commonly used functions."""

    # Set default values
    supported = False
    language_code = ""
    language_name = ""
    country_name = ""
    regional_case = False
    is_script = False
    country_code = None
    targeted_language = str(language)

    if "-" in language and "Anglo" not in language:  # There's a hyphen... probably a special code.
        broader_code = targeted_language.split("-")[0]  # Take only the language part (ar).
        specific_code = targeted_language.split("-")[1]  # Get the specific code.
        if len(specific_code) <= 1:  # If it's just a letter it cannot be valid.
            language = broader_code
            specific_code = None
    else:  # Normal code
        broader_code = specific_code = None

    # Special code added to process codes with - in it.
    if specific_code is not None:  # special code (unknown-cyrl / ar-LB).
        # This takes a code and returns a name ar-LB becomes Arabic <Lebanon> and unknown-CYRL becomes Cyrillic (Script)
        if broader_code == "unknown":  # This is going to be a script.
            try:
                language = lang_code_search(specific_code, script_search=True)[0]  # Get the script name.
                is_script = True
            except TypeError:  # Not a valid code. 
                pass
        else:  # This should be a language code with a country code.
            regional_case = True
            country_code = country_converter(specific_code, True)[0].upper()
            country_name = country_converter(country_code, True)[1]
            language = broader_code
            if ("{}-{}".format(language, country_code) in ISO_DEFAULT_ASSOCIATED or
                    country_code.lower() == language.lower()):  # Something like de-DE or zh-CN
                regional_case = False
                country_code = None
                # We don't want to mark the default countries as too granular ones.
            if len(country_name) == 0:  # There's no valid country from the converter. Reset it.
                language = targeted_language  # Redefine the language as the original (pre-split)
                regional_case = False
                country_code = None
    elif "{" in language and len(language) > 3:  # This may have a country tag. Let's be sure to remove it.
        regional_case = True
        country_name = language.split("{")[1]
        country_name = country_name[:-1]
        country_code = country_converter(country_name)[0]
        language = language.split("{")[0]  # Get just the language. 

    # Make a special exemption for COUNTRY CODES because people keep messing that up.
    for key, value in MISTAKE_ABBREVIATIONS.items():
        if len(language) == 2 and language.lower() == key:
            # If it's the same, let's replace it with the proper one.
            language = value
            continue

    # We also want to help convert ISO 639-2B codes (there are twenty of them)
    for key, value in ISO_639_2B.items():
        if len(language) == 3 and language.lower() == key:
            # If it's the same, let's replace it with the proper one.
            language = value
            continue

    # Start processing the string.
    if len(language) < 2:
        language_code = ""
        language_name = ""
        supported = False
    if len(language) == 2 and language.lower() in SUPPORTED_CODES:
        language_code = language.lower()
        language_name = SUPPORTED_LANGUAGES[SUPPORTED_CODES.index(language.lower())]
        supported = True
    elif len(language) == 2 and language.lower() not in SUPPORTED_CODES:
        try:
            language_code = language.lower()
            language_name = ISO_NAMES[ISO_639_1.index(language.lower())]
        except ValueError:  # Code is not ISO 639-1
            language_code = ""  # Just give blank ones.
            language_name = ""
        supported = False
    elif len(language) == 3 and language.lower() in SUPPORTED_CODES:
        language_code = language.lower()
        language_name = SUPPORTED_LANGUAGES[SUPPORTED_CODES.index(language.lower())]
        supported = True
    elif len(language) > 2 and language.lower() not in SUPPORTED_CODES and not is_script:
        language_name = language.title()
        try:  # First we check to see if it's name of a supported language
            try:
                language_code = SUPPORTED_CODES[SUPPORTED_LANGUAGES.index(language_name)]
                language_name = language_name
                supported = True
            except ValueError:  # Could not find a valid standard name for this language.
                try:  # Supported Misspelling?
                    language_code = alternate_search(searchfor=language_name, is_supported=True)
                    language_name = SUPPORTED_LANGUAGES[SUPPORTED_CODES.index(language_code)]
                    supported = True
                except ValueError:  # Try to use fuzzy matching
                    if language_name not in FUZZ_IGNORE_WORDS:  # We want to ignore some words that are misinterpreted
                        fuzzy_result = fuzzy_text(language_name)
                        language_code = SUPPORTED_CODES[SUPPORTED_LANGUAGES.index(fuzzy_result)]
                        language_name = fuzzy_result
                        supported = True
                    else:
                        raise ValueError  # Cause a fault so it kicks it down
        except ValueError:  # Okay, so it's not a name of a language that's supported.
            try:  # Next we check to see if it's in one of our non-supported languages, using regular names.
                language_code = ISO_639_1[ISO_NAMES.index(language.title())]
                if len(language_code) != 0:  # If it finds something, check back to see if it's a supported language.
                    try:
                        language_code = SUPPORTED_CODES[SUPPORTED_LANGUAGES.index(language.title())]
                        supported = True
                    except ValueError:
                        pass
            except ValueError:
                # Next we see if it's another misspelling for a non-supported language.
                try:
                    language_code = alternate_search(searchfor=language_name, is_supported=False)
                    language_name = ISO_NAMES[ISO_639_1.index(language_code)]
                    supported = False
                except ValueError:
                    if len(language_name) == 3:
                        # If it's a three-letter code passed by the title function, we assume it's a proper code...
                        # Lastly, we check to see if it's one of our ISO 639-3 languages set.

                        language_code = language.lower()
                        if language_code in ISO_639_3:  # This is a code with 639-1 equiv.
                            language_code = ISO_639_1[ISO_639_3.index(language_code)]
                            # print(language_code)
                            language_name = ISO_NAMES[ISO_639_1.index(language_code)]
                            # We fetch the ISO 639-1 equivalent. 
                            if language_code in SUPPORTED_CODES:  # Is a supported lang. 
                                supported = True
                            else:
                                supported = False
                        elif language_code in ['mis', 'und', 'mul', 'qnp']:  # These are special codes that we reassign
                            supported = True
                            if language_code == "mul":
                                language_code = "multiple"
                                language_name = "Multiple Languages"
                            elif language_code in ['mis', 'und', 'qnp']:  # These are assigned to "unknown"
                                language_code = "unknown"
                                language_name = "Unknown"
                        else:
                            language_name = lang_code_search(language_code, False)[0]
                            supported = False
                            if len(language_name) == 0:  # There was no match as the function above returns an empty str
                                language_code = ""
                    else:  # Otherwise it's a name for an ISO 639-3 language?
                        # Now we check DB to see if it's a name for an ISO 639-3 language
                        # Note: We use capwords() because it can account for quotes. 
                        iso_data = lang_code_search(string.capwords(language_name), False)
                        language_code = iso_data[0]
                        if len(language_code) == 0:  # There was no match
                            language_name = ""
                        else:  # There was a match.
                            returned_language_name = language_name  # Default value is the same.
                            if len(language_code) == 3:
                                returned_language_name = lang_code_search(language_code, False)[0]
                            elif len(language_code) == 4:  # Script
                                returned_language_name = lang_code_search(language_code, True)[0]
                            # Get the language name as returned by the converter for THAT CODE
                            if language_name != returned_language_name:
                                # The entered language name is an alternate name
                                # So we want to return the defined name as in the ISO file.
                                language_name = returned_language_name
                            supported = False  # Anything that didn't match the supported codes is not supported.
    elif len(language) > 2 and language.lower() in SUPPORTED_CODES and not is_script:
        # Basically for Multiple, App, and Unknown posts
        language_code = language.lower()
        try:
            language_name = SUPPORTED_LANGUAGES[SUPPORTED_CODES.index(language_code)]
            supported = True
        except ValueError:
            language_code = ""
            language_name = ""
            supported = False
    elif is_script:  # This is a script.
        language_code = specific_code
        language_name = language

    if "<" in language_name:  # Strip the brackets from ISO 639-3 languages.
        language_name = language_name.split("<")[0].strip()  # Remove the country name in brackets

    if len(language_code) == 0:  # There's no valid language so let's reset the country values.
        country_code = None
    elif regional_case and len(country_name) != 0 and len(language_code) != 0:  # This was for a specific language area.
        language_name += " {" + country_name + "}"

    return language_code, language_name, supported, country_code


def country_validator(word_list, language_list):
    """Takes a list of words, check for a country and a matching language.
    If nothing is found it just returns None.
    If something is found, returns tuple (lang-COUNTRY, ISO 639-3 code)"""

    # Set default values
    detected_word = {}
    all_detected_countries = []
    final_word_list = []

    if len(word_list) > 0:  # There are actually words to process.
        if " " in word_list[-1]:  # There's a space in the last word list from additive function in the title routine
            word_list = word_list[:-1]  # Take the last one out. It'll be processed again later anyway.
    else:
        return None  # There's nothing we can process.

    if 2 < len(word_list) <= 4:  # There's more than two words. [Swiss, German, Geneva]
        for L in range(0, len(word_list) + 1):  # Get all possible combinations.
            for subset in itertools.combinations(word_list, L):
                if len(subset) > 1:  # What we want are varying word combinations.
                    # This is useful for getting countries that have more than one word (Costa Rica)
                    final_word_list.append(" ".join(subset))  # Join the words together as a string for searching.

    final_word_list += word_list

    for word in final_word_list:
        results = country_converter(text_input=word, abbreviations_okay=False)
        if results[0] != "":  # The converter got nothing
            detected_word[word] = results[0]
            all_detected_countries.append(results[0])  # add the country code

    if len(detected_word) != 0:
        for language in language_list:

            language_code = converter(language)[0]
            # print("Language code: {}".format(language_code))

            if language_code in LANGUAGE_COUNTRY_ASSOCIATED:  # There's a language assoc. 
                check_countries = LANGUAGE_COUNTRY_ASSOCIATED.get(language_code)
                # Fetch the list of countries associated with that language. 
                # print("Checked countries: " + str(check_countries))

                lang_country_combined = None
                relevant_iso_code = None

                for country in check_countries:
                    # print(country)
                    if country in all_detected_countries:  # country is listed.
                        lang_country_combined = "{}-{}".format(language_code, country)
                        # print("Found a language country pair. {}".format(lang_country_combined))
                        if lang_country_combined in ISO_LANGUAGE_COUNTRY_ASSOCIATED:
                            # This means there is an ISO 639-3 code for this that we wanna use
                            relevant_iso_code = ISO_LANGUAGE_COUNTRY_ASSOCIATED.get(lang_country_combined)
                            # print(relevant_iso_code)
                        else:
                            relevant_iso_code = None
                return lang_country_combined, relevant_iso_code
            else:
                return None  # We did not find anything in our database match xx-XX. 
    else:
        return None


def comment_info_parser(pbody, command):
    """A function that takes a comment and looks for actable information like languages or words to lookup
    IMPORTANT: The command part MUST include the colon (:), or else it will fail."""

    advanced_mode = False
    longer_search = False
    match = ""

    if 'id:' in pbody:  # Legacy compatibility
        pbody = pbody.replace("id:", "identify:")

    if '\n' in pbody:  # Replace linebreaks
        pbody = pbody.replace("\n", " ")

    if ": " in pbody:  # Fix in case there's a space after the colon
        pbody = pbody.replace(": ", ":")
    elif ":[" in pbody:  # There are square brackets in here... let's replace them
        for character in ['[', ']']:
            pbody = pbody.replace(character, '"')  # Change them to quotes.

    if ":unknown-" in pbody:  # Special syntax in case someone tries to use this way...
        script_code = pbody.split(":unknown-", 1)[1][0:4]  # This is a bit of a hack but w/e
        if len(script_code) == 4:  # Truly script code
            pbody = pbody.replace(":unknown-", ":{}! ".format(script_code))
        else:  # Let's not put it into advanced mode otherwise.
            pbody = pbody.replace(":unknown-", ":{} ".format(script_code))

    if command in pbody:  # Check to see the command and test the remainder.
        pbody_test = pbody.split(command)[1]
        if "!" in pbody_test[:5]:
            match = re.search(':(.*?)!', pbody)
            match = str(match.group(0))[1:-1].lower()  # Trim the punctuation, convert to string
            if " " not in match and "\n" not in match:  # This is actually an advanced one.
                advanced_mode = True
            else:  # Maybe stacked two commands
                advanced_mode = False
        elif '"' in pbody_test[:2]:  # There's a quotation mark close by. Longer search?
            try:
                match = re.search(':\"(.*?)\"', pbody)
                match = str(match.group(0))[1:-1].title()
                match = match.replace('"', '')  # Replace extra quote marks.
                longer_search = True
            except AttributeError:  # Error for some reason.
                pass

    if not longer_search:  # There are no quotes
        if advanced_mode is not True:
            if command in pbody:  # there is a language specified
                match = re.search('(?<=' + command + ')[\w\-<^\'+]+', pbody)
                try:
                    match = str(match.group(0)).lower().strip()
                except AttributeError:  # There's no match... probably because of punctuation. Invalid match.
                    return None  # Exit, we can't do anything.
                # If there's a < in the string, check to make sure it's a cross post command.
                if command not in ['!translate:', '!translator:']:  # If it's not a crosspost...
                    match = match.replace("<", "")  # Take out the bracket
                # Code to double check if it's a script... even without the second! if it is, return as such
                if len(match) == 4:  # This is four characters long
                    language_name = lang_code_search(match, True)  # Run a search for the specific script
                    
                    # It found a script name, and the name is not the name of a language
                    if language_name is not None and match.title() not in ISO_NAMES:
                        advanced_mode = True  # Return it as an advanced mode.
                return match, advanced_mode
            else:
                return None
        elif advanced_mode is True:
            return match, advanced_mode
    elif longer_search:
        return match, advanced_mode


def english_fuzz(word):  # A quick function that detects if a word is likely to be "English"
    word = word.title()
    closeness = fuzz.ratio("English", word)
    if closeness > 70:  # Very likely
        return True
    else:  # Unlikely
        return False


def replace_bad_english_typing(title):  # Function that will replace a misspelling for English
    title = re.sub(r"""
                   [,.;@#?!&$()“”’"•]+  # Accept one or more copies of punctuation
                   \ *           # plus zero or more copies of a space,
                   """,
                   " ",  # and replace it with a single space
                   title, flags=re.VERBOSE)
    title_words = title.split(" ")  # Split the sentence into words.
    title_words = [str(word) for word in title_words]

    for word in title_words:
        e_result = english_fuzz(word)
        if e_result is True:  # This word is a misspelling of "English"
            title = title.replace(word, "English")  # Replace the offending word

    return title  # Return the title, now cleaned up.


def language_mention_search(search_paragraph):
    """Returns a list of identified language names from a text. Useful for Wiktionary search and title formatting."""

    matches = re.findall(r'\b[A-Z][a-z]+', search_paragraph)
    language_name_matches = []
    
    for match in matches:
        if len(match) > 3:  # We explicitly DO NOT want to match ISO 639-3 codes.
            converter_result = converter(match)
            language_code = converter_result[0]
            language_name = converter_result[1]
            
            # We do a quick check to make sure it's not some obscure ISO 639-3 language.
            if len(language_code) == 3 and language_code not in SUPPORTED_CODES:
                proceed = False
            else:
                proceed = True
            
            if len(language_name) != 0 and proceed is True:  # The result is not blank.
                language_name_matches.append(language_name)
        else:
            continue
            
    language_name_matches = [x for x in language_name_matches if x != '']  # remove blanks
    language_name_matches = list(set(language_name_matches))  # remove duplicates
    to_post = language_name_matches
    
    if len(to_post) == 0:  # If it matches nothing... UPDATE
        return None
    else:
        return to_post


def bad_title_reformat(title_text):
    """Function that takes a badly formatted title and makes it okay. Returns a proper one."""

    listed_languages = language_mention_search(title_text.title())
    if listed_languages is not None:  # We have some results.
        listed_languages = [x for x in listed_languages if x != 'English']
        listed_languages = [x for x in listed_languages if x != 'Multiple Languages']
        listed_languages = [x for x in listed_languages if x != 'Nonlanguage']

    if listed_languages is None or len(listed_languages) == 0 or listed_languages[0] not in SUPPORTED_LANGUAGES:
        # We couldn't find a language mentioned in the title.
        new_language = "Unknown"  # We want to only return stuff for supported since there can be false
    else:
        new_language = listed_languages[0]

    if "[" in title_text and "]" in title_text:
        # If it already has a tag let's take it out.
        title_text = title_text.split("]")[1].strip()

    if str("to " + new_language) in title_text or str("in " + new_language) in title_text or "from English" in title_text:
        new_tag = "[English > {}] ".format(new_language)
    else:
        new_tag = "[{} > English] ".format(new_language)
    new_title = new_tag + title_text.strip()

    if len(new_title) >= 300:  # There is a hard limit on reddit title lengths
        new_title = new_title[0:299]  # Shorten it.

    return new_title


def detect_languages_reformat(title_text):
    """This function tries to salvage a badly formatted title and render it better for the title routine."""

    title_words_selected = {}  # Create a dictionary
    new_title_text = ""
    language_check = last_language = None
    title_words = re.compile('\w+').findall(title_text)

    title_words_reversed = list(reversed(title_words))

    for word in title_words[:7]:

        if word.lower() == "to":
            continue

        language_check = language_mention_search(word.title())
        if language_check is not None:
            # print(word)
            title_words_selected[word] = language_check[0]

    for word in title_words_reversed[-7:]:

        language_check = language_mention_search(word.title())  # Check to see if there are languages in the title
        if language_check is not None:  # There are languages mentioned
            last_language = language_check[0]  # this is the last language mentioned
            break

    if language_check is None or len(title_words_selected) == 0:
        return None

    for key in sorted(title_words_selected.keys()):
        if str(key) == title_words[0]:
            new_title_text = title_text.replace(key, "[" + title_words_selected[key])

    for key in sorted(title_words_selected.keys()):
        # print(title_words_selected[key])
        if title_words_selected[key] == last_language:
            # print("yes")
            new_title_text = new_title_text.replace(key, title_words_selected[
                key] + "] ")  # add a bracket to the last found language

    if " to " in new_title_text:
        new_title_text = new_title_text.replace(" to ", " > ")
    elif " into " in new_title_text:
        new_title_text = new_title_text.replace(" into ", " > ")

    if new_title_text != "":
        return new_title_text
    else:
        return None


def app_multiple_definer(title_text):
    """This function takes in a title text and returns a boolean as to whether it should be given the 'App' code"""

    title_text = title_text.lower()
    if any(keyword in title_text for keyword in APP_WORDS):
        return True  # Yes, this should be an app.
    else:
        return False  # No it's not.


def multiple_language_script_assessor(language_list):
    """A function that takes a list of languages/scripts and determines if it is actually all multiple languages
    Returns True if everything is Okay"""

    multiple_status = True
    
    for language in language_list:
        code = converter(language)[0]
        if len(code) == 4:  # This is a script
            language_list.remove(language)
            multiple_status = False
        else:  # This is just a language.
            multiple_status = True
    
    if multiple_status is True:  # Everything is a language
        return multiple_status
    else:  # There were scripts. 
        return language_list


def both_non_english_detector(source_language, target_language):
    """Takes two lists and returns the languages for notifying or None if there's nothing to return."""

    all_languages = list(set(source_language + target_language))

    if "English" in all_languages:  # English is in here, so it CAN'T be what we're looking for.
        return None

    if len(all_languages) <= 1:
        return None
    else:
        return all_languages


def determine_title_direction(source_languages_list, target_languages_list):
    """Function takes two language lists and determines what the direction of the request is.
    Used in Ajos."""

    # Create local lists to avoid changing the main function's lists
    source_languages_local = list(source_languages_list)
    target_languages_local = list(target_languages_list)

    # Quick function to determine the direction of a title.
    # Expected output as strings: english_to, english_from, english_both, english_none
    # Exception to be made for languages with 'English' in their name like "Middle English"
    # Otherwise it will always return 'english_both'
    if all('English' in item for item in source_languages_local) and len(source_languages_local) > 1:
        source_languages_local.remove('English')
    elif all('English' in item for item in target_languages_local) and len(target_languages_local) > 1:
        target_languages_local.remove('English')

    if 'English' in source_languages_local and 'English' in target_languages_local:  # It's in both
        combined_list = source_languages_local + target_languages_local
        if len(list(combined_list)) >= 3:  # It's pretty long
            if len(source_languages_local) >= 2:
                source_languages_local.remove('English')
            elif len(target_languages_local) >= 2:
                target_languages_local.remove('English')

    if 'English' in source_languages_local and 'English' not in target_languages_local:
        return 'english_from'
    elif 'English' in target_languages_local and 'English' not in source_languages_local:
        return 'english_to'
    elif 'English' in target_languages_local and 'English' in source_languages_local:
        return 'english_both'
    else:
        return 'english_none'


def final_title_salvager(d_source_languages, d_target_languages):
    """This function takes two list of languages and tries to salvage SOMETHING out of them."""

    all_languages = d_source_languages + d_target_languages  # Combine the two
    all_languages = [x for x in all_languages if x not in ["Generic", "English"]]  # Remove the generic ones.

    if len(all_languages) is None:  # No way of saving this.
        return None
    else:  # We can get a last language classification
        try:
            salvaged_css = converter(all_languages[0])[0]
            salvaged_css_text = converter(all_languages[0])[1]
            return salvaged_css, salvaged_css_text
        except IndexError:
            return None


def title_format(title, display_process=False):
    # Function to help format a title. It should return a tuple with lists: 
    # Source languages, target languages, CSS class, CSS text, and title.
    # display_process is a boolean that allows us to see the steps taken.

    source_language = target_language = country_suffix_code = ""  # Set defaults
    final_css = "generic"
    final_code_tag = final_css.title()

    has_country = False
    notify_languages = None

    # Strip cross-post formatting, which happens at the end.
    if "(x-post" in title:
        title = title.split("(x-post")[0].strip()

    for spelling in ISO_639_1_ALTERNATE['en']:  # Replace typos or misspellings in the title for English.
        if spelling in title.title():  # Misspelling is in the title.
            title = title.replace(spelling, "English")

    if 'english' in title:
        title = title.replace("english", "English")

    if "Old English" in title:  # Small tweak to ensure Old English works properly. We convert it to "Anglo-Saxon"
        title = title.replace("Old English", "Anglosaxon")
    elif "Anglo-Saxon" in title:
        title = title.replace("Anglo-Saxon", "Anglosaxon")
    elif "Scots Gaelic" in title:
        title = title.replace("Scots Gaelic", "Scottish Gaelic")

    # Let's replace any problematic characters or formatting early.
    if any(keyword in title for keyword in WRONG_BRACKETS):  # Fix for some Unicode bracket-looking thingies.
        for keyword in WRONG_BRACKETS:
            title = title.replace(keyword, " > ")

    if ">" not in title and " to " in title.lower():
        title = title.replace(" To ", " to ")
        title = title.replace(" TO ", " to ")
        title = title.replace(" tO ", " to ")

    # if "(" in title and "[" not in title: # Replacing parantheses with brackets
    #    title = title.split('(', 1)[-1]
    #    title = title.replace("("," [ ")
    #    print(title)
    # elif ")" in title and "]" not in title:
    #    title = title.replace(")"," ] ")

    if "]" not in title and "[" not in title and re.match("\((.+(>| to ).+)\)", title):
        # This is for cases where we have no square brackets but we have a > or " to " between parantheses instead.
        # print("Replacing parantheses...")
        title = title.replace("(", "[", 1)  # We only want to replace the first occurence.
        title = title.replace(")", "]", 1)
    elif "]" not in title and "[" not in title and re.match("{(.+(>| to ).+)}", title):
        # This is for cases where we have no square brackets but we have a > or " to " between curly braces instead.
        # print("Replacing braces...")
        title = title.replace("{", "[", 1)  # We only want to replace the first occurence.
        title = title.replace("}", "]", 1)

    if "]" not in title and "[" not in title:  # Otherwise try to salvage it and reformat it.
        reformat_example = detect_languages_reformat(title)
        if reformat_example is not None:
            title = reformat_example

    # Some regex magic
    # Replace things like [Language] >/- [language]
    title = re.sub(r'(\]\s*[>\\-]\s*\[)', " > ", title)
    # title = re.sub(r'(\]\s{0,}(>|-)\s{0,}\[)', " > ", title)

    # Code for taking out the country (most likely from cross-posts)
    if "{" in title and "}" in title and "[" in title:  # Probably has a country name in it.
        has_country = True
        country_suffix_name = re.search(r"{(\D+)}", title)
        country_suffix_name = country_suffix_name.group(1)  # Get the Country name only
        country_suffix_code = country_converter(country_suffix_name)[0]
        if len(country_suffix_code) != 0:  # There was a good country code.
            # Now we want to take out the country from the title.
            title_first = title.split("{", 1)[0].strip()
            title_second = title.split("}", 1)[1]
            title = title_first + title_second
    elif "{" in title and "[" not in title:  # Probably a malformed tag. let's fix it.
        title = title.replace("{", "[")
        title = title.replace("}", "]")

    # Adapting for "English -" type situations
    if "-" in title[0:20]:
        if any(keyword in title.title() for keyword in ENGLISH_DASHES):
            title = title.replace("-", " > ")

    if "[" in title and "[" not in title[0:10]:
        # There's a bracketed part, but it's not at the beginning, so it's probably at the end.
        # Let's transpose it.
        title = transbrackets_new(title.strip())

    if "]" not in title and "English." in title:
        title = title.replace("English.", "English] ")
        title = "[" + title

    if "_" in title:  # Let's replace underscores with proper spaces.
        title = title.replace("_", " ")

    if "-" in title[0:25]:  # Let's replace dashes with proper spaces. Those that still remain after conversion
        hyphen_match = re.search('((?:\w+-)+\w+)', title)  # Try to match a hyphenated word (Puyo-Paekche)
        if hyphen_match is not None:
            hyphen_match = hyphen_match.group(0)
            hyphen_match_name = converter(hyphen_match)[1]  # Check to see if it's a valid language name
            if len(hyphen_match_name) == 0:  # No language match found, let's replace the dash with a space.
                title = title.replace("-", " ")

    for character in ["&", "+", "/", "\\", "|"]:
        if character in title:  # Straighten out punctuation.
            title = title.replace(character, " {} ".format(character))

    for compound in [">>>", ">>", "> >"]:
        if compound in title:
            title = title.replace(compound, " > ")

    if ">" in title and "English" in title and "]" not in title and "[" not in title:
        # This is to help solve cases where people forget to put the brackets.
        title = title.replace("English", "English]")
        title = "[" + title

    if ">" not in title:
        if "- Eng" in title[0:25] or "-Eng" in title[0:25]:
            # People sometimes use a dash instead of a bracket.
            title = title.replace("-", " > ")
        if " into " in title[0:30]:
            title = title.replace("into", ">")

    if "KR " in title.upper()[0:10]:  # KR is technically Kanuri but no one actually means it to be
        title = title.replace("KR ", "Korean ")
    
    # If all people write is [Unknown], account for that, and just send it back right away.
    if "[Unknown]" in title.title():
        actual_title = title.split("]", 1)[1]
        return ['Unknown'], ['English'], "unknown", "Unknown", actual_title, title, None, None, 'english_to'
    elif "???" in title[0:5] or "??" in title[0:4] or "?" in title[0:3]:
        # This is if the first few characters are just question marks...
        if "]" in title:
            actual_title = title.split("]")[1]
            return ['Unknown'], ['English'], "unknown", "Unknown", actual_title, title, None, None, 'english_to'
        else:
            return ['Unknown'], ['English'], "unknown", "Unknown", "", title, None, None, 'english_to'

    if display_process is True:
        print("\n## Title as Processed:")
        print(title)

    if ">" in title:
        source_language = title.split('>')[0]
    elif " to " in title.lower()[0:50] and ">" not in title:
        source_language = title.split(' to ')[0]
    elif "-" in title and ">" not in title and "to" not in title[0:50]:
        source_language = title.split('-')[0]
    elif "<" in title and ">" not in title:
        source_language = title.split('>')[0]

    # for character in source_language:
    #    if character == "-" or character == "/" or character == "[" or character == "("  or character == "." or character == "?" or character == ",":
    #        source_language = source_language.replace(character," ")
    source_language = re.sub(r"""
                           [,.;@#?!&$()\[\]/“”’"•]+  # Accept one or more copies of punctuation
                           \ *           # plus zero or more copies of a space,
                           """,
                             " ",  # and replace it with a single space
                             source_language, flags=re.VERBOSE)
    # print(source_language)
    source_language = source_language.title()
    source_language = source_language_original = source_language.split()  # Convert it from a string to a list

    # If there are two or three words only in source language, concatenate them to see if there's another that exists...
    # (e.g. American Sign Language)
    if len(source_language) >= 2:
        source_language.append(" ".join(source_language))

    source_language = [x for x in source_language if
                       x not in ENGLISH_2_WORDS]  # Remove two letter words that can be misconstrued as ISO codes
    source_language = [x for x in source_language if
                       x not in ENGLISH_3_WORDS]  # Remove three letter words that can be misconstrued as ISO codes

    if display_process is True:
        print("\n## Source Language Strings:")
        print(source_language)

    d_source_languages = []  # Account for misspellings
    for language in source_language:
        if "Eng" in language.title() and len(language) <= 8:  # If it's just English, we can assign it already.
            language = "English"
        converter_search = converter(language)[1]
        if converter_search != "":  # Try to get only the valid languages. Delete anything that isn't a language.
            d_source_languages.append(converter_search)
    d_source_languages = list(set(d_source_languages))  # Remove duplicates
    if len(d_source_languages) == 0:  # If we are unable to find a source language, leave it blank
        d_source_languages = ['Generic']

    processed_title = title

    if display_process is True:
        print("\n## Final Determined Source Languages:")
        print(d_source_languages)

    # Start processing TARGET languages
    if ">" in title:
        title = title[title.find(">") + 1:]
        target_language = title.split(']', 1)[0]  # Split it at the tag boundary and take the first part.
        for character in target_language:
            if character == "/" or character == "+" or character == "]" or character == ")" or character == "." or character == ":":
                target_language = target_language.replace(character, " ")
            elif character == ",":  # Comma, we want to be conservative and only do this for proper titles
                target_language = target_language.replace(character, " , ")
    elif " to " in title.lower() and ">" not in title:
        title = title[title.find(" to ") + 1:]
        target_language = title.split(']', 1)[0]  # Split it at the tag boundary and take the first part.
        for character in target_language:
            if character == "," or character == "/" or character == "+" or character == "]" or character == ")" or character == "." or character == ":":
                target_language = target_language.replace(character, " ")
    elif "-" in title and ">" not in title and " to " not in title:
        title = title[title.find("-") + 1:]
        target_language = title.split(']', 1)[0]  # Split it at the tag boundary and take the first part.
        for character in target_language:
            if character == "," or character == "/" or character == "+" or character == "]" or character == ")" or character == "." or character == ":":
                target_language = target_language.replace(character, " ")
    elif "<" in title and ">" not in title and " to " not in title:
        title = title[title.find("-") + 1:]
        target_language = title.split(']', 1)[0]  # Split it at the tag boundary and take the first part.
        for character in target_language:
            if character == "," or character == "/" or character == "]" or character == ")" or character == "." or character == ":":
                target_language = target_language.replace(character, " ")

    # Segment to split with commas...
    # Something like [English > Old English, German, French] where's it's clearly defined.
    # We're not putting this in now but something to think for the future perhaps...

    # Replace punctuation in the string. Not yet divided.
    target_language = re.sub(r"""
                           [,.;@#?!&$()“”’"\[•]+  # Accept one or more copies of punctuation
                           \ *           # plus zero or more copies of a space,
                           """,
                             " ",  # and replace it with a single space
                             target_language, flags=re.VERBOSE)

    target_language = target_language.split()  # Divide into words

    target_language = [x.title() for x in target_language]
    # Check for a hyphenated word.. like Puyo-Paekche

    if len(target_language) >= 2:  # If there are more words, we'll also process the whole string.
        target_language.append(" ".join(target_language))
    # target_language = [x for x in target_language if x != "&"]
    target_language = target_language_original = [x.strip() for x in target_language]  # Take away white space

    # target_language_nostrip = target_language  # This is used to check later if we can get a more specific result

    # Account for English words that are also ISO codes, in malformed titles. It'll remove it from the list. Should be okay with full names.
    target_language = [x for x in target_language if x not in ENGLISH_2_WORDS]
    target_language = [x for x in target_language if
                       x not in ENGLISH_3_WORDS]  # Remove three letter words that can be misconstrued as ISO codes

    if display_process is True:
        print("\n## Target Language Strings:")
        print(target_language)

    d_target_languages = []  # Account for misspellings

    for language in target_language:
        converter_target_search = converter(language)[1]
        if converter_target_search != "":  # Try to get only the valid languages. Delete anything that isn't a language.
            d_target_languages.append(converter_target_search)
    d_target_languages = list(set(d_target_languages))  # Remove duplicates (Like "Mandarin Chinese")
    if len(d_target_languages) == 0:  # If we are unable to find a target language, leave it blank
        d_target_languages = ['Generic']

    # If there's more than 1, and english is in both of them, then take out english!
    if all('English' in item for item in d_target_languages) and len(d_target_languages) >= 2 and 'English' in d_target_languages:
        d_target_languages.remove("English")

    if display_process is True:
        print("\n## Final Determined Target Languages:")
        print(d_target_languages)

    both_test_languages = both_non_english_detector(d_source_languages, d_target_languages)
    if both_test_languages is not None:  # Check to see if there are two non-English things
        notify_languages = both_test_languages
    # By this point, we have the source and target languages broken up into two separate lists.
    # Now we determine what CSS class to give this post.

    # print("Final source: " + str(d_source_languages))
    # print("Final target: " + str(d_target_languages))

    if "English" in d_target_languages and 'English' not in d_source_languages:
        # If the target language is English, we want to give it a source language CSS.
        if len(d_source_languages) >= 2:  # Prioritize other than Unknown/English, take it out.
            # print("We reached here")
            if "Unknown" in d_source_languages or "English" in d_source_languages or "Multiple Languages" in d_source_languages:
                # We want to allow the guess to be the CSS.
                d_source_languages_m = [x for x in d_source_languages if x != 'Unknown' and x != 'English'
                                        and x != 'Multiple Languages']
                if len(d_source_languages_m) == 0:  # Uh-oh, we deleted everything.
                    d_source_languages_m = list(d_source_languages)
            else:
                d_source_languages_m = list(d_source_languages)

            complete_override = False  # Defaults
            complete_source = ""

            # Do we have a language that is a complete match? (e.g. Tunisian Arabic)
            for language in d_source_languages_m:  # Is the complete match in the languages list?

                if language == source_language[-1]:  # It matches!
                    complete_override = True
                    complete_source = language
                    continue

            if not complete_override:
                final_css = converter(str(d_source_languages_m[0]))[0]
            elif complete_override:  # Override.
                final_css = converter(complete_source)[0]
        else:  # every other case
            final_css = converter(str(d_source_languages[0]))[0]
    elif "English" in d_source_languages and 'English' not in d_target_languages:
        # If the source language is English, we want to give it a target language CSS.
        final_css = converter(str(d_target_languages[0]))[0]
        if len(d_target_languages) > 1:
            # We do a test to see if there's a specific target, e.g. Egyptian Arabic
            joined_target = target_language[-1]  # Get the last full string.
            joined_target_data = converter(joined_target)
            if len(joined_target_data[0]) != 0:  # The converter actually found a specific language code for this.
                final_css = joined_target_data[0]
                d_target_languages = [joined_target_data[1]]
    elif 'English' in d_source_languages and 'English' in d_target_languages:
        # English is in both areas here.
        combined_total = list(set(d_source_languages + d_target_languages))
        combined_total.remove('English')
        if len(combined_total) > 0:  # There's still a Non English item here
            final_css = converter(combined_total[0])[0]
        else:
            final_css = 'en'  # Obviously it was just English
        '''
        else:  # English is not any of them. Take the source language.
            final_css = converter(str(d_source_languages[0]))[0]
        '''

    # Check to see if there is an "or" in the target languages
    test_chunk = title.split(']', 1)[0]  # Split it at the tag boundary and take the first part.
    if " or " in test_chunk.lower() and len(d_target_languages) < 6:  # See if there are languages considered optional
        type_o = True  # Type O means that in this sort of case we should really be taking the default
    else:
        type_o = False

    # Check for the direction.
    direction = determine_title_direction(d_source_languages, d_target_languages)

    if len(d_target_languages) >= 2:  # Test to see if it has multiple target languages
        is_multiple_test = list(d_target_languages)
        for name in ['English', "Multiple Languages"]:  # We want to remove these to see if there really is many targets
            if name in d_target_languages:
                is_multiple_test.remove(name)
        
        script_check = multiple_language_script_assessor(is_multiple_test)  # Check to see if there's a script here
        
        if script_check is not True:  # There appears to be a script in our "multiple" selection.
            is_multiple_test = script_check
            
        if len(is_multiple_test) >= 2 and 'English' not in d_target_languages:
            # Looks like it really does have more than two non-English target languages.
            final_css = "multiple"  # Then we assign it the "multiple" CSS
            notify_languages = d_target_languages
            # Put notify_languages here

    language_country = None

    if not has_country:  # There isn't a country digitally in the source language part.
        # print("Checking for regions...")
        # Now we check for regional variations.
        source_country_data = country_validator(source_language_original, d_source_languages)
        target_country_data = country_validator(target_language_original, d_target_languages)

        if source_country_data is not None or target_country_data is not None:  # There's data from the country detector
            if source_country_data is not None:
                language_country = source_country_data[0]  # Data like en-US
                language_country_code = source_country_data[1]  # The ISO 639-3 code if exists
                if len(d_source_languages) == 1 and language_country_code is not None and \
                        "English" in d_target_languages:
                    # There is only one source language. Let's replace it with the determined one.
                    # This is also assuming English is the target language.
                    d_source_languages = [converter(language_country_code)[1]]
                    final_css = language_country_code  # Change it to the ISO 639-3 code
                    # final_css_text = d_source_languages[0]
                    # print(d_source_languages)
                elif "English" not in d_target_languages and language_country is not None:
                    # Situations where both are non-English
                    final_css = language_country.split("-", 1)[0]  # Just take the language code.
            elif target_country_data is not None:
                language_country = target_country_data[0]  # Data like en-US
                language_country_code = target_country_data[1]  # The ISO 639-3 code if exists
                if len(d_target_languages) == 1 and language_country_code is not None and \
                        "English" in d_source_languages:
                    # There is only one source language. Let's replace it with the determined one.
                    # This is also assuming English is the target language.
                    d_target_languages = [converter(language_country_code)[1]]
                    final_css = language_country_code  # Change it to the ISO 639-3 code
                    # print(d_target_languages)
                elif "English" not in d_source_languages and language_country is not None:
                    # Situations where both are non-English
                    final_css = language_country.split("-", 1)[0]
    else:  # There was already a country listed above. 
        # print("Region already noted...")
        if len(country_suffix_code) != 0 and len(final_css) == 2 or len(final_css) == 3:
            language_country = "{}-{}".format(final_css, country_suffix_code)

    if len(final_css) != 4:  # This is not a script
        final_css_text = converter(final_css)[1]  # Get the flair text for inclusion.
        if language_country is not None and len(language_country) != 0 and \
                language_country not in ISO_LANGUAGE_COUNTRY_ASSOCIATED and final_css != "multiple":
            # There is a country suffix to include, let's add it to the flair. Not if it's its own langauge code though
            final_css_text += " {{{}}}".format(language_country[-2:])  # Add the country code to the output flair
    else:  # This is a script
        final_css_text = "{} (Script)".format(lang_code_search(final_css, True)[0])
        language_country = "unknown-{}".format(final_css)  # Returns a category like unknown-cyrl for notifications

    if notify_languages is not None:  # This is multiple with defined langauges.
        # print(notify_languages)
        # print(final_css)
        if len(notify_languages) >= 2 and final_css == "multiple":  # Format Multiple Languages with language tags too!
            multiple_code_tag = []
            for language in notify_languages:
                multiple_code_tag.append(converter(language)[0].upper())  # Get the code from the name
                multiple_code_tag = sorted(multiple_code_tag)  # Alphabetize
                if 'MULTIPLE' in multiple_code_tag:
                    multiple_code_tag.remove("MULTIPLE")
                if 'UNKNOWN' in multiple_code_tag:
                    multiple_code_tag.remove("UNKNOWN")
                multiple_code_tag_string = ", ".join(multiple_code_tag)  # This gives us the string without brackets. 
                # The limit for link flair text is 64 characters. we need to trim. 
                if len(multiple_code_tag_string) > 34:
                    # print("Too long")
                    multiple_code_tag_short = []
                    for tag in multiple_code_tag:
                        if len(", ".join(multiple_code_tag_short)) <= 30:
                            multiple_code_tag_short.append(tag)
                        else:
                            continue
                    multiple_code_tag = multiple_code_tag_short
                final_code_tag = " [" + ", ".join(multiple_code_tag) + "]"
            final_css_text = final_css_text + final_code_tag

    if type_o is True and final_css == "multiple":  # This is one where the target languages may not be what we want MULTIPLE.
        if "English" in d_source_languages:  # The source is English, so let's choose a target css
            final_css = converter(d_target_languages[0])[0]
            final_css_text = d_target_languages[0]  # we will send the multiple notifications, just in case.
        else:  # English is in the targets, so let's take the source.
            final_css = converter(d_source_languages[0])[0]
            final_css_text = d_source_languages[0]  # Just the name
            notify_languages = None  # Clear the notifications, we don't need them for this one.

    # print(final_css_text)

    if final_css not in SUPPORTED_CODES and len(final_css) != 4:  # It's not a supported css and also not a language
        final_css = "generic"  # If we don't have link flair for it, give it a generic linkflair
    elif len(final_css) == 4:  # It's a script code
        final_css = "unknown"

    # Now we try to get the title. Not really important, but could be useful in the future.
    actual_title = ""

    if "]" in title:
        actual_title = str(title.split(']', 1)[1]).strip()
    elif "English" in title and "]" not in title:
        actual_title = str(title.split('English', 1)[1]).strip()

    if actual_title != "":  # Try to properly format the "real title"
        if "]" in actual_title[:1]:
            actual_title = actual_title[1:].strip()
        elif ")" in actual_title[:1]:
            actual_title = actual_title[1:].strip()
        elif ">" in actual_title[:1]:
            actual_title = actual_title[1:].strip()
        elif "," in actual_title[:1]:
            actual_title = actual_title[1:].strip()
        elif "." in actual_title[:1]:
            actual_title = actual_title[1:].strip()
        elif ":" in actual_title[:1]:
            actual_title = actual_title[1:].strip()

    # We calculate whether or not this is an app. This is only applicable to Multiple posts
    if final_css == "multiple":
        app_yes = app_multiple_definer(actual_title)
        if app_yes:  # It looks like it's an app.
            final_css = 'app'
            final_css_text = final_css_text.replace("Multiple Languages", "App")
            if d_target_languages == ['Multiple Languages']:
                d_target_languages = ['App']

    # Our final attempt to wring something proper out of something that is all generic
    if final_css == "generic" and final_css_text == "Generic":
        salvaged_data = final_title_salvager(d_source_languages, d_target_languages)
        if salvaged_data is not None:
            final_css = salvaged_data[0]
            final_css_text = salvaged_data[1]

    return d_source_languages, d_target_languages, final_css, final_css_text, \
        actual_title, processed_title, notify_languages, language_country, direction


def main_posts_filter(otitle):  # A functionized filter for title filtering.
    # Decoupled from ziwen_posts in order to be more easily maintained
    post_okay = True
    filter_reason = None

    if not any(keyword in otitle for keyword in REQUIRED_KEYWORDS):
        # This is the same thing as AM's content_rule #1. The title does not contain any of our keywords.
        # But first, we'll try to salvage the title into something we can work with.
        otitle = replace_bad_english_typing(otitle)  # This replaces any bad words for "English"
        # The function below would allow for a lot looser rules
        '''
        otitle = bad_title_reformat(otitle)
        if "[Unknown > English]" in otitle:  # The title was too generic, we ain't doing it.
            print("> Filtered a post out due to incorrect title format. content_rule #1")
            post_okay = False
        '''
        if not any(keyword in otitle for keyword in REQUIRED_KEYWORDS):  # Try again
            filter_reason = '1'
            print("> Filtered a post out due to incorrect title format. Rule: #" + filter_reason)
            post_okay = False
    elif ">" not in otitle:  # Try to take out titles that bury the lede.
        if POSTS_KEYWORDS[2] in otitle.lower() or POSTS_KEYWORDS[3] in otitle.lower():
            if POSTS_KEYWORDS[2] not in otitle.lower()[0:30] and POSTS_KEYWORDS[3] not in otitle.lower()[0:30]:
                # This means the "to english" part is probably all the way at the end. Take it out.
                filter_reason = '1A'
                print("> Filtered a post out due to incorrect title format. Rule: #" + filter_reason)
                post_okay = False  # Since it's a bad post title, we don't need to process it anymore.

            # Added a rule 1B, basically this checks for super short things like 'Translation to English'
            # This should only activate if 1A is not triggered.
            if len(otitle) < 35 and filter_reason is None and '[' not in otitle:

                # Find a list of languages that are listed
                listed_languages = language_mention_search(otitle.title())

                # Remove English, we don't need that.
                if listed_languages is not None:
                    listed_languages = [x for x in listed_languages if x != 'English']

                # If there's no listed language, then we can filter it out.
                if listed_languages is None or len(listed_languages) == 0:
                    filter_reason = '1B'
                    post_okay = False
                    print("> Filtered a post out due to not including a valid language. Rule: #" + filter_reason)
    if ">" in otitle and "]" not in otitle and ">" not in otitle[0:50]:
        # If people tack on the languages as an afterthought, it can be hard to process.
        filter_reason = '2'
        print("> Filtered a post out due to incorrect title format. Rule: #" + filter_reason)
        post_okay = False

    if post_okay is True:
        return post_okay, otitle, filter_reason
    else:  # This title failed the test.
        return post_okay, None, filter_reason
