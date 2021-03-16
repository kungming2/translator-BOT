#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

"""A collection of database sets and language functions that all r/translator bots use."""

import csv
import re
import os
import itertools

from rapidfuzz import fuzz  # Switched to rapidfuzz

VERSION_NUMBER_LANGUAGES = "1.7.17"

# Access the CSV with ISO 639-3 and ISO 15924 data.
lang_script_directory = os.path.dirname(__file__)  # <-- absolute dir the script is in
lang_script_directory += "/Data/"  # Where the main files are kept.
FILE_ADDRESS_ISO_ALL = os.path.join(lang_script_directory, '_database_iso_codes.csv')

'''LANGUAGE CODE LISTS'''
# These are symbols used to indicate states in defined multiple posts. The last two are currently used.
DEFINED_MULTIPLE_LEGEND = {'⍉': 'missing', '¦': 'inprogress', '✓': 'doublecheck', '✔': 'translated'}

# This is our main dictionary for languages.
MAIN_LANGUAGES = {
    "aa": {
        'supported': False,
        'name': 'Afar',
        'language_code_3': 'aar',
        'alternate_names': ['Afaraf'],
        'thanks': "Gadda ge"
    },
    "ab": {
        'supported': False,
        'name': 'Abkhaz',
        'language_code_3': 'abk',
        'alternate_names': ['Abxazo', 'Abkhazian'],
        'thanks': "Иҭабуп"
    },
    "acm": {
        'supported': True,
        'name': 'Mesopotamian Arabic',
        'language_code_3': 'acm',
        'alternate_names': ['Baghdadi', 'Furati']
    },
    "ae": {
        'supported': False,
        'name': 'Avestan',
        'language_code_3': 'ave',
        'alternate_names': ['Avesta'],
        'subreddits': ["r/avestan"]
    },
    "aeb": {
        'supported': True,
        'name': 'Tunisian Arabic',
        'language_code_3': 'aeb',
        'alternate_names': ['Tunisian Darija']
    },
    "af": {
        'supported': True,
        'name': 'Afrikaans',
        'language_code_3': 'afr',
        'alternate_names': None,
        'countries_default': 'ZA',
        'countries_associated': ['NA'],
        'subreddits': ['r/afrikaans'],
        'thanks': "Dankie"
    },
    "ak": {
        'supported': False,
        'name': 'Akan',
        'language_code_3': 'aka',
        'alternate_names': None,
        'thanks': "Meda wo ase"
    },
    "am": {
        'supported': True,
        'name': 'Amharic',
        'language_code_3': 'amh',
        'alternate_names': ['Ethiopian', 'Ethiopia', 'Ethopian', 'Ethiopic', 'Abyssinian', 'Amarigna', 'Amarinya',
                            'Amhara'],
        'countries_default': 'ET',
        'subreddits': ["r/amharic"],
        'thanks': "አመሰግናለሁ"
    },
    "an": {
        'supported': False,
        'name': 'Aragonese',
        'language_code_3': 'arg',
        'alternate_names': None,
        'thanks': "Gracias"
    },
    "ang": {
        'supported': True,
        'name': 'Anglo-Saxon',
        'language_code_3': 'ang',
        'alternate_names': ['Old English', 'Anglo Saxon', 'Anglosaxon', 'Anglisc'],
        'thanks': "Þancas"
    },
    'app': {
        'language_code_3': 'app',
        'name': 'App',
        'supported': True,
        'alternate_names': None
    },
    "ar": {
        'supported': True,
        'name': 'Arabic',
        'language_code_3': 'arb',
        'alternate_names': ['Arab', 'Arabian', 'Arbic', 'Aribic', 'Arabe', 'Levantine', 'Arabish', 'Arabiic',
                            'Lebanese', 'Syrian', 'Yemeni', '3arabi', 'Msarabic', 'Moroccan', 'Arabizi', 'Tunisian',
                            'Algerian', '3rabi'],
        'countries_associated': ['AE', 'CY', 'DZ', 'BH', 'DJ', 'EG', 'IL', 'IQ', 'JO', 'KW', 'LB', 'LY', 'MA', 'ML',
                                 'OM', 'PS', 'SA', 'SO', 'SD', 'SS', 'SY', 'TD', 'TN', 'YE'],
        'subreddits': ["r/learn_arabic", "r/arabic", "r/arabs", "r/learnarabic"],
        'thanks': "ﺷﻜﺮﺍﹰ"
    },
    'arc': {
        'alternate_names': None,
        'name': 'Aramaic',
        'supported': True,
        'language_code_3': 'arc',
        'subreddits': ["r/aramaic"],
        'thanks': "Yishar"
    },
    "arq": {
        'supported': True,
        'name': 'Algerian Arabic',
        'language_code_3': 'arq',
        'alternate_names': ['Algerian']
    },
    'art': {
        'language_code_3': 'art',
        'name': 'Conlang',
        'supported': True,
        'alternate_names': ['Artificial', 'Conlang', 'Constructed', 'Tengwar'],
        'thanks': "There is no word for 'thank you' in Dothraki"
    },
    "ary": {
        'supported': True,
        'name': 'Moroccan Arabic',
        'language_code_3': 'ary',
        'alternate_names': ['Maghrebi Arabic', 'Maghribi'],
        'thanks': " شكرا بزاف"
    },
    "arz": {
        'supported': True,
        'name': 'Egyptian Arabic',
        'language_code_3': 'arz',
        'alternate_names': ['Massry', 'Masri'],
        'thanks': "متشكّرين"
    },
    "as": {
        'supported': False,
        'name': 'Assamese',
        'language_code_3': 'asm',
        'alternate_names': ['Asamiya', 'Asambe', 'Asami'],
        'thanks': "ধন্যবাদ"
    },
    "ase": {
        'supported': True,
        'name': 'American Sign Language',
        'language_code_3': 'ase',
        'alternate_names': ['Asl', 'American Signed English', 'Ameslan']
    },
    "av": {
        'supported': False,
        'name': 'Avar',
        'language_code_3': 'ava',
        'alternate_names': ['Avaro', 'Avaric'],
        'thanks': " Баркала"
    },
    "ay": {
        'supported': False,
        'name': 'Aymara',
        'language_code_3': 'ayr',
        'alternate_names': None,
        'countries_associated': ['PE', 'CL', 'BO'],
        'thanks': "Juspajaraña"
    },
    "az": {
        'supported': True,
        'name': 'Azerbaijani',
        'language_code_3': 'azj',
        'alternate_names': ['Azeri'],
        'thanks': "Təşəkkür edirəm"
    },
    "ba": {
        'supported': False,
        'name': 'Bashkir',
        'language_code_3': 'bak',
        'alternate_names': None,
        'thanks': "рәхмәт"
    },
    "ban": {
        'supported': True,
        'name': 'Balinese',
        'language_code_3': 'ban',
        'alternate_names': ['Bali'],
        'thanks': "Suksma"
    },
    "be": {
        'supported': True,
        'name': 'Belarusian',
        'language_code_3': 'bel',
        'alternate_names': ['Belarussian', 'Belorusian', 'Belorussian', 'Bielorussian', 'Byelorussian'],
        'countries_default': 'BY',
        'subreddits': ["r/belarusian"],
        'thanks': "Дзякуй"
    },
    "bg": {
        'supported': True,
        'name': 'Bulgarian',
        'language_code_3': 'bul',
        'alternate_names': None,
        'thanks': "благодаря"
    },
    "bh": {
        'supported': False,
        'name': 'Bihari',
        'language_code_3': 'bho',
        'alternate_names': ['Bhojpuri', 'Maithili', 'Magahi'],
        'thanks': 'धन्वाद'
    },
    "bi": {
        'supported': False,
        'name': 'Bislama',
        'language_code_3': 'bis',
        'alternate_names': ['Bichelamar'],
        'thanks': "Tangkyu"
    },
    "bm": {
        'supported': False,
        'name': 'Bambara',
        'language_code_3': 'bam',
        'alternate_names': None,
        'thanks': "I ni ce"
    },
    "bn": {
        'supported': True,
        'name': 'Bengali',
        'language_code_3': 'ben',
        'alternate_names': ['Bangala', 'Bangla'],
        'countries_default': 'BD',
        'subreddits': ["r/bengalilanguage"],
        'thanks': "ধন্যবাদ"
    },
    "bo": {
        'supported': True,
        'name': 'Tibetan',
        'language_code_3': 'bod',
        'language_code_2b': 'tib',
        'alternate_names': ['Tibetic'],
        'subreddits': ["r/tibet", "r/tibetanlanguage"],
        'thanks': "ཐུགས་རྗེ་ཆེ་།"
    },
    "br": {
        'supported': True,
        'name': 'Breton',
        'language_code_3': 'bre',
        'alternate_names': ['Brezhoneg', 'Berton'],
        'subreddits': ["r/breton"],
        'thanks': "Trugarez"
    },
    "bs": {
        'supported': True,
        'name': 'Bosnian',
        'language_code_3': 'bos',
        'alternate_names': ['Bosnien'],
        'countries_default': 'BA',
        'thanks': "Hvala"
    },
    "ca": {
        'supported': True,
        'name': 'Catalan',
        'language_code_3': 'cat',
        'alternate_names': ['Catalonian', 'Valencian', 'Catalán'],
        'countries_default': 'ES',
        'subreddits': ["r/catalan"],
        'thanks': "Gràcies"
    },
    "ce": {
        'supported': False,
        'name': 'Chechen',
        'language_code_3': 'che',
        'alternate_names': None,
        'subreddits': ["r/chechnya"],
        'thanks': "Баркалла"
    },
    "ceb": {
        'supported': True,
        'name': 'Cebuano',
        'language_code_3': 'ceb',
        'alternate_names': ['Cebu', 'Visaya', 'Bisaya', 'Visayan'],
        'thanks': "Salamat"
    },
    "ch": {
        'supported': False,
        'name': 'Chamorro',
        'language_code_3': 'cha',
        'alternate_names': None,
        'thanks': "Si yu'os ma'åse'"
    },
    "chr": {
        'supported': True,
        'name': 'Cherokee',
        'language_code_3': 'chr',
        'alternate_names': ['Tsalagi', 'ᏣᎳᎩ'],
        'thanks': "ᏩᏙ"
    },
    "co": {
        'supported': True,
        'name': 'Corsican',
        'language_code_3': 'cos',
        'alternate_names': ['Corsu', 'Corso', 'Corse'],
        'thanks': "À ringraziavvi"
    },
    "cop": {
        'supported': True,
        'name': 'Coptic',
        'language_code_3': 'cop',
        'alternate_names': None,
        'thanks': 'Sephmot'
    },
    "cr": {
        'supported': False,
        'name': 'Cree',
        'language_code_3': 'crk',
        'alternate_names': None,
        'thanks': 'ᐊᕀᐦᐊᕀ'
    },
    "cs": {
        'supported': True,
        'name': 'Czech',
        'language_code_3': 'ces',
        'language_code_2b': 'cze',
        'alternate_names': ['Bohemian', 'Čeština', 'Czechoslovakian'],
        'countries_default': 'CZ',
        'mistake_abbreviation': 'cz',
        'subreddits': ["r/learnczech"],
        'thanks': "Dík"
    },
    "cu": {
        'supported': True,
        'name': 'Old Church Slavonic',
        'language_code_3': 'chu',
        'alternate_names': ['Slavonic', 'Church Slavonic', 'Old Slavic', 'Church Slavic']
    },
    "cv": {
        'supported': False,
        'name': 'Chuvash',
        'language_code_3': 'chv',
        'alternate_names': ['Bulgar'],
        'thanks': "Тав"
    },
    "cy": {
        'supported': True,
        'name': 'Welsh',
        'language_code_3': 'cym',
        'language_code_2b': 'wel',
        'alternate_names': ['Wales', 'Cymraeg', 'Gymraeg'],
        'subreddits': ["r/learnwelsh", "r/cymru", "r/wales"],
        'thanks': "Diolch"
    },
    "da": {
        'supported': True,
        'name': 'Danish',
        'language_code_3': 'dan',
        'alternate_names': ['Dansk', 'Denmark', 'Rigsdansk'],
        'countries_default': 'DK',
        'mistake_abbreviation': 'dk',
        'subreddits': ["r/danishlanguage"],
        'thanks': "Tak"
    },
    "de": {
        'supported': True,
        'name': 'German',
        'language_code_3': 'deu',
        'language_code_2b': 'ger',
        'alternate_names': ['Deutsch', 'Deutsche', 'Ger', 'Deutch', 'Kurrent', 'Austrian', 'Sütterlin',
                            'Plattdeutsch', 'Suetterlin', 'Tedesco'],
        'countries_associated': ['AT', 'BE', 'CH'],
        'subreddits': ["r/german", "r/de", "r/germany"],
        'thanks': "Danke"
    },
    "dv": {
        'supported': False,
        'name': 'Dhivehi',
        'language_code_3': 'div',
        'alternate_names': ['Divehi', 'Maldivian', 'Divehli'],
        'thanks': "ޝުކުރިއްޔާ"
    },
    "dz": {
        'supported': True,
        'name': 'Dzongkha',
        'language_code_3': 'dzo',
        'alternate_names': ['Bhutanese', 'Zongkhar'],
        'thanks': "བཀའ་དྲིན་ཆེ་ལགས།"
    },
    "ee": {
        'supported': False,
        'name': 'Ewe',
        'language_code_3': 'ewe',
        'alternate_names': None,
        'thanks': "Akpe"
    },
    'egy': {
        'alternate_names': ['Hieroglyphs', 'Hieroglyphic', 'Hieroglyphics', 'Hyroglifics', 'Egyptian Hieroglyphs',
                            'Egyptian Hieroglyph'],
        'name': 'Ancient Egyptian',
        'supported': True,
        'language_code_3': 'egy',
        'subreddits': ["r/ancientegypt"],
        'thanks': "Dua"
    },
    "el": {
        'supported': True,
        'name': 'Greek',
        'language_code_3': 'ell',
        'language_code_2b': 'gre',
        'alternate_names': ['Hellenic', 'Greece', 'Hellas', 'Cypriot', 'Modern Greek'],
        'countries_default': 'GR',
        'countries_associated': ['CY'],
        'mistake_abbreviation': 'gr',
        'subreddits': ["r/greek"],
        'thanks': "Ευχαριστώ"
    },
    "en": {
        'supported': False,
        'name': 'English',
        'language_code_3': 'eng',
        'alternate_names': ['Ingles', 'Inggeris', 'Englisch', 'Inglese', 'Inglesa', 'Engrish', 'Enlighs', 'Engilsh',
                            'Enlish', 'Englishe', 'Engish', 'Engelish', 'Engliah', 'Englisg', 'Englsih', 'Englkish',
                            'Engilish', 'Enlglish', 'Englsh', 'Enghlish', 'Engligh', 'Englist', 'Engkish', 'Ensglish',
                            'Enhlish', 'Английский', 'Inggris', 'Englische', '英語', '영어', 'Anglais', 'Engels',
                            'Engelsk', 'İngilizce', '英文'],
        'subreddits': ["r/englishlearning"]
    },
    "eo": {
        'supported': True,
        'name': 'Esperanto',
        'language_code_3': 'epo',
        'alternate_names': None,
        'subreddits': ["r/esperanto"],
        'thanks': "Dankon"
    },
    "es": {
        'supported': True,
        'name': 'Spanish',
        'language_code_3': 'spa',
        'alternate_names': ['Espanol', 'Spainish', 'Mexican', 'Castilian', 'Español', 'Spain', 'Esp', 'Chilean',
                            'Castellano', 'Españo'],
        'countries_associated': ['MX', 'VE', 'AR', 'BO', 'CL', 'CO', 'CR', 'CU', 'DO', 'EC', 'SV', 'GQ', 'GT', 'HN',
                                 'NI', 'PA', 'PY', 'PE', 'PR', 'UY'],
        'subreddits': ["r/spanish", "r/learnspanish", "r/argentina"],
        'thanks': "Gracias"
    },
    "et": {
        'supported': True,
        'name': 'Estonian',
        'language_code_3': 'ekk',
        'alternate_names': ['Eesti'],
        'countries_default': 'EE',
        'subreddits': ["r/eesti"],
        'thanks': "Tänan"
    },
    "eu": {
        'supported': True,
        'name': 'Basque',
        'language_code_3': 'eus',
        'language_code_2b': 'baq',
        'alternate_names': ['Euska', 'EuskeraEuskerie', 'Euskara'],
        'countries_default': 'ES',
        'subreddits': ["r/basque"],
        'thanks': "Eskerrik asko"
    },
    "fa": {
        'supported': True,
        'name': 'Persian',
        'language_code_3': 'pes',
        'language_code_2b': 'per',
        'alternate_names': ['Farsi', 'Iranian', 'Iran', 'Parsi', 'Farse', 'Farci'],
        'countries_default': 'IR',
        'countries_associated': ['AF'],
        'subreddits': ["r/farsi", "r/iran", "r/learnfarsi", "r/persian"],
        'thanks': "ممنونم"
    },
    "ff": {
        'supported': False,
        'name': 'Fula',
        'language_code_3': 'fuf',
        'alternate_names': ['Fulah'],
        'countries_associated': ['SN', 'GM', 'MR', 'SL', 'GN', 'GW', 'ML', 'GH', 'TG', 'BJ', 'BF', 'NE', 'SD', 'TD',
                                 'CM', 'CF', 'NG']
    },
    "fi": {
        'supported': True,
        'name': 'Finnish',
        'language_code_3': 'fin',
        'alternate_names': ['Finnic', 'Suomi', 'Finland'],
        'subreddits': ["r/learnfinnish"],
        'thanks': "Kiitos"
    },
    "fj": {
        'supported': False,
        'name': 'Fijian',
        'language_code_3': 'fij',
        'alternate_names': None,
        'thanks': "Vinaka"
    },
    "fo": {
        'supported': True,
        'name': 'Faroese',
        'language_code_3': 'fao',
        'alternate_names': ['Faeroese'],
        'subreddits': ["r/faroese"],
        'thanks': "Takk"
    },
    "fr": {
        'supported': True,
        'name': 'French',
        'language_code_3': 'fra',
        'language_code_2b': 'fre',
        'alternate_names': ['Francais', 'Français', 'Quebecois', 'France', 'Québécois'],
        'countries_associated': ['BE', 'CA', 'CF', 'CD', 'DJ', 'GQ', 'HT', 'ML', 'NE', 'SN', 'CH', 'TG'],
        'subreddits': ["r/french", "r/france", "r/frenchimmersion"],
        'thanks': "Merci"
    },
    "fy": {
        'supported': False,
        'name': 'Frisian',
        'language_code_3': 'fry',
        'alternate_names': None,
        'thanks': "Tankewol"
    },
    "ga": {
        'supported': True,
        'name': 'Irish',
        'language_code_3': 'gle',
        'alternate_names': ['Gaeilge', 'Gaelic'],
        'countries_default': 'IE',
        'subreddits': ["r/gaeilge"],
        'thanks': "Go raibh míle maith agat"
    },
    "gd": {
        'supported': True,
        'name': 'Scottish Gaelic',
        'language_code_3': 'gla',
        'alternate_names': ['Gaidhlig', 'Scottish Gaelic', 'Scots Gaelic'],
        'subreddits': ["r/gaidhlig"],
        'thanks': "Tapadh leat"
    },
    "generic": {
        'supported': True,
        'name': 'Generic',
        'language_code_3': 'generic',
        'alternate_names': None
    },
    "gl": {
        'supported': False,
        'name': 'Galician',
        'language_code_3': 'glg',
        'alternate_names': ['Gallego'],
        'thanks': "Grazas"
    },
    "gn": {
        'supported': False,
        'name': 'Guarani',
        'language_code_3': 'grn',
        'alternate_names': None,
        'countries_associated': ['PY', 'AR', 'BO'],
        'thanks': "Aguyje"
    },
    "grc": {
        'supported': True,
        'name': 'Ancient Greek',
        'language_code_3': 'grc',
        'alternate_names': ['Koine', 'Doric', 'Attic', 'Byzantine Greek', 'Medieval Greek', 'Classic Greek',
                            'Classical Greek', 'Koine Greek', 'Greek Koine'],
        'subreddits': ["r/ancientgreek"],
        'thanks': "Ἐπαινῶ"
    },
    "gsw": {
        'supported': True,
        'name': 'Swiss German',
        'language_code_3': 'gsw',
        'alternate_names': ['Schweizerdeutsch', 'Schwyzerdütsch'],
        'thanks': "Merci"
    },
    "gu": {
        'supported': True,
        'name': 'Gujarati',
        'language_code_3': 'guj',
        'alternate_names': ['Gujerathi', 'Gujerati', 'Gujrathi'],
        'countries_default': 'IN',
        'thanks': "ધન્યવાદ"
    },
    "gv": {
        'supported': False,
        'name': 'Manx',
        'language_code_3': 'glv',
        'alternate_names': ['Gailck', 'Manx Gaelic'],
        'subreddits': ["r/gaelg"],
        'thanks': "Gura mie ayd"
    },
    "ha": {
        'supported': False,
        'name': 'Hausa',
        'language_code_3': 'hau',
        'alternate_names': ['Haoussa', 'Hausawa'],
        'countries_associated': ['NE', 'NG', 'TD'],
        'thanks': "Na gode"
    },
    "haw": {
        'supported': True,
        'name': 'Hawaiian',
        'language_code_3': 'haw',
        'alternate_names': ["Hawai'Ian", "Hawaii", "Hawai'I"],
        'subreddits': ["r/learn_hawaiian"],
        'thanks': "Mahalo"
    },
    "he": {
        'supported': True,
        'name': 'Hebrew',
        'language_code_3': 'heb',
        'alternate_names': ['Israeli', 'Hebraic', 'Jewish'],
        'countries_default': 'IL',
        'subreddits': ["r/hebrew", "r/israel"],
        'thanks': "תודה רבה"
    },
    "hi": {
        'supported': True,
        'name': 'Hindi',
        'language_code_3': 'hin',
        'alternate_names': ['Hindustani', 'Hindī'],
        'countries_default': 'IN',
        'countries_associated': ['FJ'],
        'subreddits': ["r/hindi"],
        'thanks': "धन्यवाद"
    },
    "ho": {
        'supported': False,
        'name': 'Hiri Motu',
        'language_code_3': 'hmo',
        'alternate_names': None,
        'thanks': "Tanikiu"
    },
    "hr": {
        'supported': True,
        'name': 'Croatian',
        'language_code_3': 'hrv',
        'alternate_names': ['Croation', 'Serbo-Croatian', 'Hrvatski'],
        'subreddits': ["r/croatian"],
        'thanks': "Hvala"
    },
    "ht": {
        'supported': True,
        'name': 'Haitian Creole',
        'language_code_3': 'hat',
        'alternate_names': ['Haitian', 'Kreyòl Ayisyen', 'Kreyol'],
        'subreddits': "r/haiti",
        'thanks': "Mesi"
    },
    "hu": {
        'supported': True,
        'name': 'Hungarian',
        'language_code_3': 'hun',
        'alternate_names': ['Magyar', 'Hungary'],
        'countries_default': 'HU',
        'subreddits': ["r/hungarian", "r/hungary"],
        'thanks': "Köszi"
    },
    "hy": {
        'supported': True,
        'name': 'Armenian',
        'language_code_3': 'hye',
        'language_code_2b': 'arm',
        'alternate_names': None,
        'countries_default': 'AM',
        'subreddits': ["r/hayeren"],
        'thanks': "մերսի"
    },
    "hz": {
        'supported': False,
        'name': 'Herero',
        'language_code_3': 'her',
        'alternate_names': None,
        'thanks': "Okuhepa"
    },
    "ia": {
        'supported': False,
        'name': 'Interlingua',
        'language_code_3': 'ina',
        'alternate_names': None,
        'subreddits': ["r/interlingua"],
        'thanks': "Gratias"
    },
    "id": {
        'supported': True,
        'name': 'Indonesian',
        'language_code_3': 'ind',
        'alternate_names': ['Indonesia', 'Indo'],
        'subreddits': ["r/indonesian"],
        'thanks': "Terima kasih"
    },
    "ie": {
        'supported': False,
        'name': 'Interlingue',
        'language_code_3': 'ile',
        'alternate_names': None,
        'subreddits': ["r/interlingue"],
        'thanks': "Mersi"
    },
    "ig": {
        'supported': False,
        'name': 'Igbo',
        'language_code_3': 'ibo',
        'alternate_names': ['Ibo'],
        'thanks': "Ịmela"
    },
    "ii": {
        'supported': False,
        'name': 'Nuosu',
        'language_code_3': 'iii',
        'alternate_names': None,
        'thanks': "Kax sha w"
    },
    "ik": {
        'supported': False,
        'name': 'Inupiaq',
        'language_code_3': 'ipk',
        'alternate_names': ['Inupiat', 'Iñupiaq'],
        'thanks': "Quyanaq"
    },
    "io": {
        'supported': False,
        'name': 'Ido',
        'language_code_3': 'ido',
        'alternate_names': None,
        'subreddits': ["r/ido"],
        'thanks': "Danko"
    },
    "is": {
        'supported': True,
        'name': 'Icelandic',
        'language_code_3': 'isl',
        'language_code_2b': 'ice',
        'alternate_names': None,
        'subreddits': ["r/learnicelandic", "r/iceland"],
        'thanks': "Takk"
    },
    "it": {
        'supported': True,
        'name': 'Italian',
        'language_code_3': 'ita',
        'alternate_names': ['Italiano', 'Italiana', 'Italia', 'Italien', 'Italy'],
        'subreddits': ["r/italianlearning", "r/italy"],
        'thanks': "Grazie"
    },
    "iu": {
        'supported': True,
        'name': 'Inuktitut',
        'language_code_3': 'ike',
        'alternate_names': ['Inuit'],
        'subreddits': ["r/inuktitut"],
        'thanks': "ᖁᔭᓇᐃᓐᓂ"
    },
    "ja": {
        'supported': True,
        'name': 'Japanese',
        'language_code_3': 'jpn',
        'alternate_names': ['Jap', 'Jpn', 'Japenese', 'Japaneese', 'Japanes', 'Katakana', 'Hiragana', 'Japaness',
                            'Romaji', 'Japneese', 'Japnese', 'Kanji', 'Japaese', 'Japonais', 'Romajin',
                            'Nihongo', 'Kenji', 'Romanji', 'Rōmaji', '日本語', 'Japones', 'Japonés', 'Japnese',
                            'Japanase', 'Japanesse'],
        'countries_default': 'JP',
        'mistake_abbreviation': 'jp',
        'subreddits': ["r/learnjapanese", "r/japan", "r/japanese", "r/nihongo", "r/kanji", "r/japanlife"],
        'thanks': "ありがとう"
    },
    "jv": {
        'supported': True,
        'name': 'Javanese',
        'language_code_3': 'jav',
        'alternate_names': ['Djawa'],
        'thanks': "Trim"
    },
    "ka": {
        'supported': True,
        'name': 'Georgian',
        'language_code_3': 'kat',
        'language_code_2b': 'geo',
        'alternate_names': ['Kartvelian'],
        'countries_default': 'GE',
        'thanks': "გმადლობთ"
    },
    "kg": {
        'supported': False,
        'name': 'Kongo',
        'language_code_3': 'kon',
        'alternate_names': ['Kikongo']
    },
    "ki": {
        'supported': False,
        'name': 'Kikuyu',
        'language_code_3': 'kik',
        'alternate_names': ['Gikuyu']
    },
    "kj": {
        'supported': False,
        'name': 'Kwanyama',
        'language_code_3': 'kua',
        'alternate_names': ['Kuanyama'],
        'thanks': "Tangi"
    },
    "kk": {
        'supported': True,
        'name': 'Kazakh',
        'language_code_3': 'kaz',
        'alternate_names': ['Kazakhstan', 'Kazak', 'Kaisak', 'Kosach', 'Kazakhstani'],
        'countries_default': 'KZ',
        'thanks': "Рахмет"
    },
    "kl": {
        'supported': True,
        'name': 'Kalaallisut',
        'language_code_3': 'kal',
        'alternate_names': ['Greenlandic'],
        'subreddits': ["r/kalaallisut"],
        'thanks': "Qujan"
    },
    "km": {
        'supported': True,
        'name': 'Khmer',
        'language_code_3': 'khm',
        'alternate_names': ['Cambodian', 'Cambodia', 'Kampuchea', 'Central Khmer'],
        'countries_default': 'KH',
        'mistake_abbreviation': 'kh',
        'subreddits': ["r/learnkhmer"],
        'thanks': "ឣរគុណ"
    },
    "kn": {
        'supported': True,
        'name': 'Kannada',
        'language_code_3': 'kan',
        'alternate_names': None,
        'subreddits': ["r/kannada"],
        'thanks': "ಧನ್ಯವಾದಗಳು"
    },
    "ko": {
        'supported': True,
        'name': 'Korean',
        'language_code_3': 'kor',
        'alternate_names': ['Korea', 'Hangul', 'Korian', 'Kor', 'Hanguk', 'Guk-Eo', 'Hangeul', 'Hanguel', '한국어'],
        'countries_default': 'KR',
        'subreddits': ["r/korean", "r/korea", "r/koreantranslate"],
        'thanks': "감사합니다"
    },
    "kr": {
        'supported': False,
        'name': 'Kanuri',
        'language_code_3': 'kau',
        'alternate_names': None
    },
    "ks": {
        'supported': False,
        'name': 'Kashmiri',
        'language_code_3': 'kas',
        'alternate_names': ['Kacmiri', 'Kaschemiri', 'Keshur', 'Koshur']
    },
    "ku": {
        'supported': True,
        'name': 'Kurdish',
        'language_code_3': 'ckb',
        'alternate_names': ['Kurdi', 'Kurd', 'Kurmanji'],
        'countries_default': 'IQ',
        'thanks': "سوپاس"
    },
    "kv": {
        'supported': False,
        'name': 'Komi',
        'language_code_3': 'kom',
        'alternate_names': None,
        'thanks': "Аттьӧ"
    },
    "kw": {
        'supported': False,
        'name': 'Cornish',
        'language_code_3': 'cor',
        'alternate_names': None,
        'subreddits': ["r/kernowek"],
        'thanks': "Meur ras"
    },
    "ky": {
        'supported': False,
        'name': 'Kyrgyz',
        'language_code_3': 'kir',
        'alternate_names': ['Kirghiz', 'Kirgiz'],
        'subreddits': ["r/learnkyrgyz"],
        'thanks': "Рахмат"
    },
    "la": {
        'supported': True,
        'name': 'Latin',
        'language_code_3': 'lat',
        'alternate_names': ['Latina', 'Classical Roman'],
        'subreddits': ["r/latin", "r/mylatintattoo", "r/latina"],
        'thanks': "Grātiās tibi agō"
    },
    "lb": {
        'supported': True,
        'name': 'Luxembourgish',
        'language_code_3': 'ltz',
        'alternate_names': ['Letzeburgesch', 'Letzburgisch', 'Luxembourgeois', 'Luxemburgian', 'Luxemburgish'],
        'subreddits': ["r/luxembourg"],
        'thanks': "Merci"
    },
    "lg": {
        'supported': False,
        'name': 'Ganda',
        'language_code_3': 'lug',
        'alternate_names': ['Kiganda'],
        'thanks': "Weebale"
    },
    "li": {
        'supported': True,
        'name': 'Limburgish',
        'language_code_3': 'lim',
        'alternate_names': ['Limburgan', 'Limburger', 'Limburgs', 'Limburgian', 'Limburgic'],
        'thanks': "Danke"
    },
    "ln": {
        'supported': True,
        'name': 'Lingala',
        'language_code_3': 'lin',
        'alternate_names': None,
        'thanks': "Botondi"
    },
    "lo": {
        'supported': True,
        'name': 'Lao',
        'language_code_3': 'lao',
        'alternate_names': ['Laos', 'Laotian'],
        'subreddits': ["r/laos"],
        'thanks': "ຂອບໃຈ"
    },
    "lt": {
        'supported': True,
        'name': 'Lithuanian',
        'language_code_3': 'lit',
        'alternate_names': ['Lithuania', 'Lietuviu', 'Litauische', 'Litewski', 'Litovskiy', 'Lith'],
        'thanks': "Ačiū"
    },
    "lu": {
        'supported': False,
        'name': 'Luba-Kasai',
        'language_code_3': 'lub',
        'alternate_names': ['Luba-Katanga']
    },
    "lv": {
        'supported': True,
        'name': 'Latvian',
        'language_code_3': 'lvs',
        'alternate_names': None,
        'subreddits': ["r/learnlatvian"],
        'thanks': "Paldies"
    },
    'lzh': {
        'alternate_names': ['Literary Chinese', 'Literary Sinitic', 'Classical Sinitic', '文言文', '古文'],
        'name': 'Classical Chinese',
        'supported': True,
        'language_code_3': 'lzh',
        'subreddits': ["r/classicalchinese"],
        'thanks': "謝"
    },
    "mg": {
        'supported': True,
        'name': 'Malagasy',
        'language_code_3': 'mlg',
        'alternate_names': ['Madagascar'],
        'subreddits': ["r/madagascar"],
        'thanks': "Misaotra"
    },
    "mh": {
        'supported': False,
        'name': 'Marshallese',
        'language_code_3': 'mah',
        'alternate_names': None
    },
    "mi": {
        'supported': True,
        'name': 'Maori',
        'language_code_3': 'mri',
        'language_code_2b': 'mao',
        'alternate_names': ['Māori'],
        'subreddits': ["r/maori"],
        'thanks': "Kia ora"
    },
    "mk": {
        'supported': True,
        'name': 'Macedonian',
        'language_code_3': 'mkd',
        'language_code_2b': 'mac',
        'alternate_names': ['Macedonia'],
        'thanks': "Благодарам"
    },
    "ml": {
        'supported': True,
        'name': 'Malayalam',
        'language_code_3': 'mal',
        'alternate_names': None,
        'subreddits': ['r/malayalam'],
        'thanks': "നന്ദി"
    },
    "mn": {
        'supported': True,
        'name': 'Mongolian',
        'language_code_3': 'khk',
        'alternate_names': None,
        'subreddits': ["r/mongolian"],
        'thanks': "Баярлалаа"
    },
    "mr": {
        'supported': True,
        'name': 'Marathi',
        'language_code_3': 'mar',
        'alternate_names': None,
        'countries_default': 'IN',
        'subreddits': ["r/marathi"],
        'thanks': "आभारी आहे"
    },
    "ms": {
        'supported': True,
        'name': 'Malay',
        'language_code_3': 'zlm',
        'language_code_2b': 'may',
        'alternate_names': ['Malaysia', 'Melayu', 'Malaysian'],
        'countries_default': 'MY',
        'countries_associated': ['BN', 'SG'],
        'subreddits': ["r/bahasamelayu"],
        'thanks': "Terima kasih"
    },
    "mt": {
        'supported': True,
        'name': 'Maltese',
        'language_code_3': 'mlt',
        'alternate_names': ['Malti'],
        'thanks': "Grazzi"
    },
    'multiple': {
        'language_code_3': 'multiple',
        'alternate_names': ['Various', 'Any', 'All', 'Multi', 'Multi-language', 'Many', 'Everything',
                            'Anything', 'Every Language', 'Mul'],
        'name': 'Multiple Languages',
        'supported': True
    },
    "my": {
        'supported': True,
        'name': 'Burmese',
        'language_code_3': 'mya',
        'language_code_2b': 'bur',
        'alternate_names': ['Myanmar', 'Birmanie'],
        'countries_default': 'MM',
        'subreddits': ["r/lanl_burmese"],
        'thanks': "ကျေးဇူးတင်ပါတယ်"
    },
    "na": {
        'supported': False,
        'name': 'Nauruan',
        'language_code_3': 'nau',
        'alternate_names': ['Nauru'],
        'thanks': "Itûba"
    },
    "nap": {
        'supported': True,
        'name': 'Neapolitan',
        'language_code_3': 'nap',
        'alternate_names': ['Napulitano', 'Napolitano']
    },
    "nb": {
        'supported': False,
        'name': 'Norwegian Bokmal',
        'language_code_3': 'nob',
        'alternate_names': None,
        'thanks': "Takk"
    },
    "nd": {
        'supported': False,
        'name': 'Northern Ndebele',
        'language_code_3': 'nde',
        'alternate_names': ['North Ndebele'],
        'thanks': "Ngiyabonga"
    },
    "ne": {
        'supported': True,
        'name': 'Nepali',
        'language_code_3': 'npi',
        'alternate_names': ['Nepalese', 'Nepal'],
        'thanks': "धन्यवाद"
    },
    "ng": {
        'supported': False,
        'name': 'Ndonga',
        'language_code_3': 'ndo',
        'alternate_names': None
    },
    "nl": {
        'supported': True,
        'name': 'Dutch',
        'language_code_3': 'nld',
        'language_code_2b': 'dut',
        'alternate_names': ['Nederlands', 'Holland', 'Netherlands', 'Flemish'],
        'countries_associated': ['BE', 'SR'],
        'subreddits': ["r/learndutch"],
        'thanks': "Dank u"
    },
    "nn": {
        'supported': False,
        'name': 'Norwegian Nynorsk',
        'language_code_3': 'nno',
        'alternate_names': None,
        'thanks': "Takk"
    },
    "no": {
        'supported': True,
        'name': 'Norwegian',
        'language_code_3': 'nor',
        'alternate_names': ['Bokmal', 'Norsk', 'Nynorsk', 'Norway', 'Norweigian'],
        'subreddits': ["r/norsk", "r/norway"],
        'thanks': "Takk"
    },
    'non': {
        'alternate_names': ['Nordic', 'Futhark', 'Viking'],
        'name': 'Norse',
        'supported': True,
        'language_code_3': 'non',
        'thanks': "Þakka"
    },
    "nr": {
        'supported': False,
        'name': 'Southern Ndebele',
        'language_code_3': 'nbl',
        'alternate_names': ['Isindebele', 'South Ndebele'],
        'thanks': "Ngiyabonga"
    },
    "nv": {
        'supported': True,
        'name': 'Navajo',
        'language_code_3': 'nav',
        'alternate_names': ['Navaho', 'Diné', 'Naabeehó'],
        'thanks': "Ahéhee'"
    },
    "ny": {
        'supported': False,
        'name': 'Chichewa',
        'language_code_3': 'nya',
        'alternate_names': ['Chewa', 'Nyanja'],
        'thanks': "Zikomo"
    },
    "oc": {
        'supported': False,
        'name': 'Occitan',
        'language_code_3': 'oci',
        'alternate_names': None,
        'subreddits': ["r/occitan"],
        'thanks': "Mercés"
    },
    "oj": {
        'supported': False,
        'name': 'Ojibwe',
        'language_code_3': 'oji',
        'alternate_names': ['Ojibwa'],
        'thanks': "Miigwech"
    },
    "om": {
        'supported': True,
        'name': 'Oromo',
        'language_code_3': 'orm',
        'alternate_names': ['Oromoo', 'Oromiffa', 'Oromifa', 'Oromos'],
        'countries_associated': ['ET', 'KE'],
        'thanks': "Galatoomi"
    },
    "or": {
        'supported': False,
        'name': 'Oriya',
        'language_code_3': 'ori',
        'alternate_names': ['Odia'],
        'thanks': "ଧନ୍ୟବାଦ୍"
    },
    "os": {
        'supported': False,
        'name': 'Ossetian',
        'language_code_3': 'oss',
        'alternate_names': ['Ossetic'],
        'thanks': "Бузныг"
    },
    'ota': {
        'alternate_names': ['Ottoman'],
        'name': 'Ottoman Turkish',
        'supported': True,
        'language_code_3': 'ota'
    },
    "pa": {
        'supported': True,
        'name': 'Punjabi',
        'language_code_3': 'pan',
        'alternate_names': ['Panjabi', 'Punjab', 'Panjab'],
        'countries_default': 'PK',
        'subreddits': ["r/punjabi"],
        'thanks': "ਧਨਵਾਦ"
    },
    "pi": {
        'supported': True,
        'name': 'Pali',
        'language_code_3': 'pli',
        'alternate_names': ['Pāli'],
        'subreddits': ["r/pali"]
    },
    "pl": {
        'supported': True,
        'name': 'Polish',
        'language_code_3': 'pol',
        'alternate_names': ['Polnish', 'Polnisch', 'Poland', 'Polisch', 'Polski'],
        'subreddits': ["r/learnpolish", "r/poland"],
        'thanks': "Dzięki"
    },
    "ps": {
        'supported': True,
        'name': 'Pashto',
        'language_code_3': 'pst',
        'alternate_names': ['Pashtun', 'Pushto', 'Poshtu'],
        'countries_default': 'AF',
        'subreddits': ["r/pashto"],
        'thanks': "مننه"
    },
    "pt": {
        'supported': True,
        'name': 'Portuguese',
        'language_code_3': 'por',
        'alternate_names': ['Portugese', 'Portugues', 'Brazilian', 'Portugais', 'Brazil', 'Brazilians', 'Portugal',
                            'Português'],
        'countries_associated': ['AO', 'BR', 'MZ', 'TL', 'CV'],
        'subreddits': ["r/portuguese", "r/portugal", "r/brazil"],
        'thanks': "Obrigado"
    },
    "qu": {
        'supported': True,
        'name': 'Quechua',
        'language_code_3': 'que',
        'alternate_names': ['Kichwa'],
        'subreddits': ["r/learnquechua"],
        'thanks': "Solpayki"
    },
    "rm": {
        'supported': False,
        'name': 'Romansh',
        'language_code_3': 'roh',
        'alternate_names': None,
        'thanks': "Grazia"
    },
    "rn": {
        'supported': False,
        'name': 'Kirundi',
        'language_code_3': 'run',
        'alternate_names': ['Ikirundi', 'Rundi', 'Urundi', 'Hima'],
        'thanks': "Urakoze"
    },
    "ro": {
        'supported': True,
        'name': 'Romanian',
        'language_code_3': 'ron',
        'language_code_2b': 'rum',
        'alternate_names': None,
        'countries_associated': ['MD'],
        'subreddits': ["r/romanian"],
        'thanks': "Mersi"
    },
    "ru": {
        'supported': True,
        'name': 'Russian',
        'language_code_3': 'rus',
        'alternate_names': ['Russain', 'Russin', 'Russion', 'Rus', 'Rusian', 'Ruski', 'ру́сский', 'Русский'],
        'subreddits': ["r/russian", "r/russia"],
        'thanks': "Спаси́бо"
    },
    "rw": {
        'supported': False,
        'name': 'Kinyarwanda',
        'language_code_3': 'kin',
        'alternate_names': ['Ikinyarwanda', 'Orunyarwanda', 'Ruanda', 'Rwanda', 'Rwandan', 'Urunyaruanda'],
        'thanks': "Murakoze"
    },
    "sa": {
        'supported': True,
        'name': 'Sanskrit',
        'language_code_3': 'san',
        'alternate_names': ['Samskrit', 'Sandskrit'],
        'subreddits': ["r/sanskrit"],
        'thanks': "धन्यवादाः"
    },
    "sc": {
        'supported': True,
        'name': 'Sardinian',
        'language_code_3': 'sro',
        'alternate_names': ['Sardu'],
        'thanks': "Grazie"
    },
    "scn": {
        'supported': True,
        'name': 'Sicilian',
        'language_code_3': 'scn',
        'alternate_names': ['Siciliano', 'Sicilianu', 'Siculu'],
        'thanks': "Grazij"
    },
    "sd": {
        'supported': False,
        'name': 'Sindhi',
        'language_code_3': 'snd',
        'alternate_names': None,
        'thanks': "Mehrbani"
    },
    "se": {
        'supported': False,
        'name': 'Northern Sami',
        'language_code_3': 'sme',
        'alternate_names': None,
        'thanks': "Giitu"
    },
    "sg": {
        'supported': False,
        'name': 'Sango',
        'language_code_3': 'sag',
        'alternate_names': None,
        'thanks': "Singîla"
    },
    "si": {
        'supported': True,
        'name': 'Sinhalese',
        'language_code_3': 'sin',
        'alternate_names': ['Sinhala', 'Sri Lanka', 'Sri Lankan'],
        'countries_default': 'LK',
        'subreddits': ["r/sinhala"],
        'thanks': "Istuti"
    },
    "sk": {
        'supported': True,
        'name': 'Slovak',
        'language_code_3': 'slk',
        'language_code_2b': 'slo',
        'alternate_names': ['Slovakian', 'Slovakia'],
        'thanks': "Ďakujem"
    },
    "sl": {
        'supported': True,
        'name': 'Slovene',
        'language_code_3': 'slv',
        'alternate_names': ['Slovenian', 'Slovenski'],
        'countries_default': 'SI',
        'thanks': "Hvala"
    },
    "sm": {
        'supported': False,
        'name': 'Samoan',
        'language_code_3': 'smo',
        'alternate_names': None,
        'thanks': "Fa'afetai"
    },
    "sn": {
        'supported': False,
        'name': 'Shona',
        'language_code_3': 'sna',
        'alternate_names': None,
        'thanks': "Waita zvako"
    },
    "so": {
        'supported': True,
        'name': 'Somali',
        'language_code_3': 'som',
        'alternate_names': ['Somalia', 'Somalian'],
        'thanks': "Mahadsanid"
    },
    "sq": {
        'supported': True,
        'name': 'Albanian',
        'language_code_3': 'als',
        'language_code_2b': 'alb',
        'alternate_names': ['Shqip', 'Shqipe', 'Tosk'],
        'countries_default': 'AL',
        'countries_associated': ['XK'],
        'subreddits': ["r/albanian"],
        'thanks': "Falemenderit"
    },
    "sr": {
        'supported': True,
        'name': 'Serbian',
        'language_code_3': 'srp',
        'alternate_names': ['Yugoslavian'],
        'countries_default': 'RS',
        'countries_associated': ['ME'],
        'subreddits': ["r/serbian"],
        'thanks': "Хвала"
    },
    "ss": {
        'supported': False,
        'name': 'Swati',
        'language_code_3': 'ssw',
        'alternate_names': ['Swazi'],
        'thanks': "Ngiyabonga"
    },
    "st": {
        'supported': False,
        'name': 'Sotho',
        'language_code_3': 'sot',
        'alternate_names': None,
        'thanks': "Ke a leboha"
    },
    "su": {
        'supported': False,
        'name': 'Sundanese',
        'language_code_3': 'sun',
        'alternate_names': None,
        'thanks': "Nuhun"
    },
    "sv": {
        'supported': True,
        'name': 'Swedish',
        'language_code_3': 'swe',
        'alternate_names': ['Svenska', 'Swede', 'Sweedish', 'Swedisch', 'Swidish', 'Gutnish', 'Sweden'],
        'countries_default': 'SE',
        'subreddits': ["r/svenska", "r/sweden"],
        'thanks': "Tack"
    },
    "sw": {
        'supported': True,
        'name': 'Swahili',
        'language_code_3': 'swh',
        'alternate_names': ['Kiswahili'],
        'countries_associated': ['CD', 'TZ', 'KE', 'UG'],
        'subreddits': ["r/swahili"],
        'thanks': "Asante"
    },
    'syc': {
        'alternate_names': ['Classical Syriac'],
        'name': 'Syriac',
        'supported': True,
        'language_code_3': 'syc'
    },
    "ta": {
        'supported': True,
        'name': 'Tamil',
        'language_code_3': 'tam',
        'alternate_names': None,
        'countries_default': 'IN',
        'countries_associated': ['SG'],
        'subreddits': ["r/tamil"],
        'thanks': "நன்றி"
    },
    "te": {
        'supported': True,
        'name': 'Telugu',
        'language_code_3': 'tel',
        'alternate_names': ['Tegulu'],
        'countries_default': 'IN',
        'subreddits': ["r/telugu"],
        'thanks': "ధన్యవాదములు"
    },
    "tg": {
        'supported': True,
        'name': 'Tajik',
        'language_code_3': 'tgk',
        'alternate_names': None,
        'mistake_abbreviation': 'tj',
        'thanks': "Рахмат"
    },
    "th": {
        'supported': True,
        'name': 'Thai',
        'language_code_3': 'tha',
        'alternate_names': ['Thailand', 'Siamese', 'Bangkok', 'Thi', 'Thia'],
        'subreddits': ["r/learnthai", "r/thailand"],
        'thanks': "ขอบคุณ"
    },
    "ti": {
        'supported': False,
        'name': 'Tigrinya',
        'language_code_3': 'tir',
        'alternate_names': None,
        'thanks': "የቐንየለይ"
    },
    "tk": {
        'supported': False,
        'name': 'Turkmen',
        'language_code_3': 'tuk',
        'alternate_names': None,
        'thanks': "Sag boluň"
    },
    "tl": {
        'supported': True,
        'name': 'Tagalog',
        'language_code_3': 'tgl',
        'alternate_names': ['Filipino', 'Fillipino', 'Philipino', 'Philippines', 'Philippine', 'Phillipene',
                            'Phillipenes'],
        'countries_default': 'PH',
        'subreddits': ["r/tagalog"],
        'thanks': "Salamat"
    },
    "tn": {
        'supported': False,
        'name': 'Tswana',
        'language_code_3': 'tsn',
        'alternate_names': ['Setswana'],
        'thanks': "Ke itumetse"
    },
    "to": {
        'supported': False,
        'name': 'Tonga',
        'language_code_3': 'ton',
        'alternate_names': ['Tongan'],
        'thanks': "Mālō"
    },
    "tr": {
        'supported': True,
        'name': 'Turkish',
        'language_code_3': 'tur',
        'alternate_names': ['Turkic', 'Turkce', 'Turkey', 'Türkçe'],
        'countries_associated': ['CY'],
        'subreddits': ["r/turkishlearning", "r/turkey"],
        'thanks': "Teşekkür ederim"
    },
    "ts": {
        'supported': False,
        'name': 'Tsonga',
        'language_code_3': 'tso',
        'alternate_names': None,
        'thanks': "Ndza nkhensa"
    },
    "tt": {
        'supported': True,
        'name': 'Tatar',
        'language_code_3': 'tat',
        'alternate_names': None,
        'thanks': "Räxmät"
    },
    "tw": {
        'supported': True,
        'name': 'Twi',
        'language_code_3': 'twi',
        'alternate_names': None,
        'thanks': "Meda wo ase"
    },
    "ty": {
        'supported': False,
        'name': 'Tahitian',
        'language_code_3': 'tah',
        'alternate_names': None,
        'thanks': "Māuruuru"
    },
    "ug": {
        'supported': True,
        'name': 'Uyghur',
        'language_code_3': 'uig',
        'alternate_names': ['Uighur'],
        'thanks': "رەھمەت سىزگە"
    },
    "uk": {
        'supported': True,
        'name': 'Ukrainian',
        'language_code_3': 'ukr',
        'alternate_names': ['Ukranian', 'Ukraine'],
        'countries_default': 'UA',
        'mistake_abbreviation': 'ua',
        'subreddits': ["r/ukrainian"],
        'thanks': "Дякую"
    },
    'unknown': {
        'language_code_3': 'unknown',
        'alternate_names': ['Unknown', 'Unkown', 'Unknow', 'Uknown', 'Unknon', 'Unsure', 'Asian', 'Asiatic',
                            'Not Sure', "Don'T Know", 'Dont Know', 'No Idea', "I Don'T Know", 'Unk', 'Idk',
                            'Undefined', 'Source Language', 'Mystery', 'Native American', 'Uncertain', 'Indian',
                            'Unidentified'],
        'name': 'Unknown',
        'supported': True
    },
    "ur": {
        'supported': True,
        'name': 'Urdu',
        'language_code_3': 'urd',
        'alternate_names': ['Pakistani', 'Pakistan'],
        'countries_default': 'PK',
        'subreddits': ["r/urdu"],
        'thanks':  "شكريه"
    },
    "uz": {
        'supported': True,
        'name': 'Uzbek',
        'language_code_3': 'uzn',
        'alternate_names': None,
        'countries_associated': ['AF'],
        'subreddits': ["r/learn_uzbek"],
        'thanks': "Rahmat"
    },
    "ve": {
        'supported': False,
        'name': 'Venda',
        'language_code_3': 'ven',
        'alternate_names': None,
        'thanks': "Ndo livhuwa"
    },
    "vi": {
        'supported': True,
        'name': 'Vietnamese',
        'language_code_3': 'vie',
        'alternate_names': ['Vietnam', 'Viet', 'Chữ Nôm', 'Annamese'],
        'countries_default': 'VN',
        'mistake_abbreviation': 'vn',
        'subreddits': ["r/vietnamese", "r/vietnam", "r/learnvietnamese"],
        'thanks': "Cảm ơn"
    },
    "vo": {
        'supported': False,
        'name': 'Volapuk',
        'language_code_3': 'vol',
        'alternate_names': ['Volapük'],
        'subreddits': ["r/volapuk"],
        'thanks': "Danö"
    },
    "wa": {
        'supported': False,
        'name': 'Walloon',
        'language_code_3': 'wln',
        'alternate_names': None,
        'thanks': "Grâce"
    },
    "wo": {
        'supported': False,
        'name': 'Wolof',
        'language_code_3': 'wol',
        'alternate_names': None,
        'thanks': 'Jai-rruh-jef'
    },
    "xh": {
        'supported': True,
        'name': 'Xhosa',
        'language_code_3': 'xho',
        'alternate_names': ['Isixhosa'],
        'thanks': "Ndiyabulela"
    },
    "yi": {
        'supported': True,
        'name': 'Yiddish',
        'language_code_3': 'ydd',
        'alternate_names': ['Yidish'],
        'subreddits': ["r/yiddish"],
        'thanks':  "שכח"
    },
    "yo": {
        'supported': True,
        'name': 'Yoruba',
        'language_code_3': 'yor',
        'alternate_names': None,
        'thanks': "O se"
    },
    'yue': {
        'alternate_names': ['Cantonese Chinese', 'Chinese Cantonese', 'Canto', 'Taishanese', 'Guangzhou'],
        'name': 'Cantonese',
        'supported': True,
        'language_code_3': 'yue',
        'countries_default': 'HK',
        'countries_associated': ['MO'],
        'subreddits': ["r/cantonese"],
        'thanks': "多謝"
    },
    "za": {
        'supported': False,
        'name': 'Zhuang',
        'language_code_3': 'zyb',
        'alternate_names': None
    },
    "zh": {
        'supported': True,
        'name': 'Chinese',
        'language_code_3': 'cmn',
        'language_code_2b': 'chi',
        'alternate_names': ['Mandarin', 'Taiwanese', 'Chinease', 'Manderin', 'Zhongwen', '中文', '汉语', '漢語',
                            '國語', 'Chinise', 'Chineese', 'Hanzi', 'Cinese', 'Mandrin', 'Mandarin Chinese', 'Mandirin',
                            'Taiwan', 'China', 'Chn', 'Pinyin', 'Beijinghua', 'Zhongguohua', 'Putonghua', 'Guanhua',
                            'Bronze Script', 'Seal Script', 'Mandaring'],
        'countries_default': 'CN',
        'countries_associated': ['TW'],
        'mistake_abbreviation': 'cn',
        'subreddits': ["r/chineselanguage", "r/chinese", "r/mandarin", "r/learnchinese"],
        'thanks': "謝謝"
    },
    "zu": {
        'supported': True,
        'name': 'Zulu',
        'language_code_3': 'zul',
        'alternate_names': ['Isizulu', 'Isi Zulu'],
        'countries_default': 'ZA',
        'thanks': "Ngiyabonga"
    },
    'zxx': {
        'alternate_names': ["Null", "None", "Nothing", "Gibberish", "Nonsense", 'Mojibake', 'Drunk'],
        'name': 'Nonlanguage',
        'supported': True,
        'language_code_3': 'zxx'
    },
}

# These are two-letter and three-letter English words that can be confused for ISO language codes.
# We exclude them when processing the title. When adding new ones, add them in title case.
ENGLISH_2_WORDS = ['Am', 'An', 'As', 'Be', 'Br', 'El', 'He', 'Is', 'It', 'My', 'No', 'Or', 'Se', 'So', 'To', 'Tw']
ENGLISH_3_WORDS = ['Abs', 'Abu',
                   'Aby', 'Ace', 'Act', 'Add', 'Ado', 'Ads', 'Aft', 'Age', 'Ago', 'Aid', 'Ail', 'Aim', 'Air',
                   'Ait', 'Aka', 'Ale', 'Amp', 'And', 'Ant', 'Ape', 'App', 'Apt', 'Arc', 'Are', 'Ark', 'Arm',
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
                   'Eon', 'Era', 'Erg', 'Err', 'Ese', 'Etc',
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
                   'Men', 'Met', 'Mex',
                   'Mic', 'Mid', 'Min', 'Mit', 'Mix', 'Mob', 'Mod', 'Mog', 'Mom', 'Mon', 'Moo', 'Mop',
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
                   'Tap', 'Tar', 'Tat', 'Tax', 'Tea', 'Tee', 'Ten', 'The', 'Thx',
                   'Tic', 'Tie', 'Til', 'Tin', 'Tip', 'Tit', 'Toe', 'Toe', 'Tom', 'Ton', 'Too', 'Top', 'Tot',
                   'Tow', 'Toy', 'Try', 'Tub', 'Tug', 'Tui', 'Tut', 'Two', 'Txt', 'Ugh', 'Uke', 'Ump', 'Urn', 'Usa',
                   'Use',
                   'Van', 'Vat', 'Vee', 'Vet', 'Vex', 'Via', 'Vie', 'Vig', 'Vim', 'Voe', 'Vow', 'Wad', 'Wag', 'Wan',
                   'War', 'Was', 'Wax', 'Way', 'Web', 'Wed', 'Wee', 'Wel', 'Wen', 'Wet', 'Who', 'Why', 'Wig', 'Win',
                   'Wit', 'Wiz', 'Woe', 'Wog', 'Wok', 'Won', 'Woo', 'Wow', 'Wry', 'Wwi',
                   'Wye', 'Yak', 'Yam', 'Yap', 'Yaw', 'Yay',
                   'Yea', 'Yen', 'Yep', 'Yes', 'Yet', 'Yew', 'Yip', 'You', 'Yow', 'Yum', 'Yup', 'Zag', 'Zap', 'Zed',
                   'Zee', 'Zen', 'Zig', 'Zip', 'Zit', 'Zoa', 'Zoo']
# These are English words that usually get erroneously recognized as a language due to Fuzzywuzzy. Let's ignore them.
FUZZ_IGNORE_WORDS = ['Ancient Mayan', 'Archaic', 'Base', 'Canada', 'Cheese', 'Chopstick', 'Classical Japanese', 
                     'Creek', 'Dish', 'Green', 'Guarani', 'Here', 'Horse', 'Japanese', 'Javanese', 'Japanese -',
                     'Kanada', 'Karen', 'Latina', 'Ladin',
                     'Ladino', 'Latino', 'Lmao', 'Logo', 'Maay', 'Major', 'Mardi', 'Maria', 'Mario', 'Morse', 'Nosey', 'Nurse',
                     'Orkish', 'Past', 'Person', 'Peruvian', 'Prussian', 'Roman', 'Romani',
                     'Romanization', 'Romanized', 'Romanji',
                     'Romanjin', 'Romany', 'Sake', 'Scandinavian', 'Serial', 'Sorbian', 'Sumerian', 'Syrian Arabic', 'Titan',
                     'Trail', 'Trench', 'Turks',]

# Title formatting words.
ENGLISH_DASHES = ['English -', 'English-', '-English', '- English', '-Eng', 'Eng-', '- Eng', 'Eng -', 'ENGLISH-',
                  'ENGLISH -', 'EN-', 'ENG-', 'ENG -', '-ENG', '- ENG', '-ENGLISH', '- ENGLISH']
WRONG_DIRECTIONS = ["<", "〉", "›", "》", "»", "⟶", "\udcfe", "&gt;", "→", "←", "~"]
WRONG_BRACKETS_LEFT = ['［', '〚', '【 ', '〔', '〖', '⟦', '｟', '《']
WRONG_BRACKETS_RIGHT = ['］', '〛', '】', '〕', '〗', '⟧', '｠', '》']
APP_WORDS = [' app ', ' bot ', 'add-on', 'addon', 'an app', 'android', 'chatbot', 'crowdin', 'crowdsourced',
             'discord bot', 'firefox', 'game', 'google play', 'localisation', 'localise', 'localization', 'localize',
             'my app', 'social network', 'software', 'telegram bot']

# A manually populated dictionary that matches ISO macrolanguages with their most prominent consituent language.
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
CJK_LANGUAGES = {"Chinese": ['Chinese', 'Min Dong Chinese', 'Classical Chinese', 'Jinyu Chinese', 'Mandarin Chinese',
                             'Pu-Xian Chinese', 'Huizhou Chinese', 'Min Zhong Chinese', 'Gan Chinese', 'Hakka Chinese',
                             'Xiang Chinese', 'Min Bei Chinese', 'Min Nan Chinese', 'Wu Chinese', 'Yue Chinese',
                             'Cantonese', 'Late Middle Chinese', 'Old Chinese', 'Hani', 'Hanb', 'Hans', 'Hant',
                             "Traditional Han", "Simplified Han", "Han Characters", 'Unknown'],
                 "Japanese": ['Japanese', 'Old Japanese', 'Northern Amami-Oshima', 'Southern Amami-Oshima', 'Kikai',
                              'Toku-No-Shima', 'Kunigami', 'Oki-No-Erabu', 'Central Okinawan', 'Yoron', 'Miyako',
                              'Yaeyama', 'Yonaguni', 'Hira', 'Jpan', 'Kana'],
                 "Korean": ['Korean', 'Middle Korean', 'Old Korean', 'Jejueo', 'Hang', 'Kore']}


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
    ("Hong Kong", "HK", "HKG", "344", ["Honk Kong"]),
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


def language_lists_generator():
    """
    A routine that creates a bunch of the old lists that used to power `converter()`

    :return: Nothing, but it declares a bunch of global variables.
    """

    global SUPPORTED_CODES, SUPPORTED_LANGUAGES, ISO_DEFAULT_ASSOCIATED, ISO_639_1, ISO_639_2B, ISO_639_3, ISO_NAMES, \
        MISTAKE_ABBREVIATIONS, LANGUAGE_COUNTRY_ASSOCIATED

    SUPPORTED_CODES = []
    SUPPORTED_LANGUAGES = []
    ISO_DEFAULT_ASSOCIATED = []
    ISO_639_1 = []
    ISO_639_2B = {}
    ISO_639_3 = []
    ISO_NAMES = []
    MISTAKE_ABBREVIATIONS = {}
    LANGUAGE_COUNTRY_ASSOCIATED = {}

    for language_code, language_module in MAIN_LANGUAGES.items():

        ISO_639_1.append(language_code)
        ISO_639_3.append(language_module['language_code_3'])
        ISO_NAMES.append(language_module['name'])
        if 'alternate_names' in language_module:
            if language_module['alternate_names'] is not None:
                for item in language_module['alternate_names']:
                    ISO_NAMES.append(item)

        if language_module['supported']:
            SUPPORTED_CODES.append(language_code)
            SUPPORTED_LANGUAGES.append(language_module['name'])

        if 'countries_default' in language_module:
            ISO_DEFAULT_ASSOCIATED.append("{}-{}".format(language_code, language_module['countries_default']))

        if 'countries_associated' in language_module:
            LANGUAGE_COUNTRY_ASSOCIATED[language_code] = language_module['countries_associated']

        if 'mistake_abbreviation' in language_module:
            MISTAKE_ABBREVIATIONS[language_module['mistake_abbreviation']] = language_code

        if 'language_code_2b' in language_module:
            ISO_639_2B[language_module['language_code_2b']] = language_code

    return


# Form the lists from the dictionary that are needed for compatibility.
language_lists_generator()


def fuzzy_text(word):
    """
    A quick function that assesses misspellings of supported languages. For example, 'Chinnsse' will be returned as
    'Chinese." The closeness ratio can be adjusted to make this more or less sensitive.
    A higher ratio means stricter, and a lower ratio means less strict. 

    :param word: Any word.
    :return: If the word seems to be close to a supported language, return the likely match.
    """

    for language in SUPPORTED_LANGUAGES:
        closeness = fuzz.ratio(language, word)

        if closeness > 75 and language != 'Javanese':
            return str(language)

    return None


def language_name_search(search_term):
    """
    Function that searches for a language name or its mispellings/alternate names. It will only return the code if it's
    an *exact* match. There's a separate module in `fuzzy_text` above and in `converter` that will take care of
    misspellings or other issues for the main supported languages.

    :param search_term: The term we're looking to check, most likely a language name.
    :return: The equivalent language code if found, a blank string otherwise.
    """

    for key in MAIN_LANGUAGES:
        if search_term == MAIN_LANGUAGES[key]['name']:
            return key
        elif MAIN_LANGUAGES[key]['alternate_names'] is not None:
            for alternate_name in MAIN_LANGUAGES[key]['alternate_names']:
                if search_term == alternate_name:
                    return key
        else:
            continue

    return ""


def transbrackets_new(title):
    """
    A simple function that takes a bracketed tag and moves the bracketed component to the front.
    It will also work if the bracketed section is in the middle of the sentence.

    :param title: A title which has the bracketed tag at the end, or in the middle.
    :return: The transposed title, with the tag properly at the front.
    """

    if ']' in title:  # There is a defined end to this tag.
        bracketed_tag = re.search(r'\[(.+)\]', title)
        bracketed_tag = bracketed_tag.group(0)
        title_remainder = title.replace(bracketed_tag, "")
    else:  # No closing tag...
        bracketed_tag = title.split("[", 1)[1]
        title_remainder = title.replace(bracketed_tag, "")
        title_remainder = title_remainder[:-1]
        bracketed_tag = "[" + bracketed_tag + "]"  # enclose it

    reformed_title = "{} {}".format(bracketed_tag, title_remainder)

    return reformed_title


def lang_code_search(search_term, script_search):
    """
    Returns a tuple: name of a code or a script, is it a script? (that's a boolean)

    :param search_term: The term we're looking for.
    :param script_search: A boolean that can narrow down our search to just ISO 15925 script codes.
    :return:
    """

    master_dict = {}
    is_script = False

    if len(search_term) == 4:
        is_script = True

    csv_file = csv.reader(open(FILE_ADDRESS_ISO_ALL, "rt", encoding="utf-8"), delimiter=",")
    for row in csv_file:
        # We have a master dictionary. Index by code. Tuple has: (language name, language name (lower), alt names lower)
        master_dict[row[0]] = (row[2:][0], row[2:][0].lower(), row[3:][0].lower())

    if len(search_term) == 3:  # This is a ISO 639-3 code
        if search_term.lower() in master_dict:
            item_name = master_dict[search_term.lower()][0]
            # Since the first two rows are the language code and 639-1 code, we take it from the third.
            return item_name, is_script
        else:
            return "", False
    elif len(search_term) == 4 and script_search is True:  # This is a script
        if search_term.lower() in master_dict:
            # Since the first two rows are the language code and 639-1 code, we take it from the third row.
            item_name = master_dict[search_term.lower()][0]
            is_script = True
            return item_name, is_script
    elif len(search_term) > 3:  # Probably a name, so let's get the code
        item_code = ""
        for key, value in master_dict.items():
            if search_term.lower() == value[1]:
                if len(key) == 3 and not script_search:  # This is a language code
                    item_code = key
                elif len(key) == 4:
                    item_code = key
                    is_script = True
                return item_code, is_script

        # No name was found, let's check alternates.
        for key, value in master_dict.items():
            if ';' in value[2]:  # There are multiple alternate names here
                sorted_alternate = value[2].split('; ')
            else:
                sorted_alternate = [value[2]]  # Convert into an iterable list.

            if search_term.lower() in sorted_alternate:
                if len(key) == 3:  # This is a language code
                    item_code = key
                elif len(key) == 4:
                    item_code = key
                    is_script = True
                return item_code, is_script

    return "", False


def iso639_3_to_iso639_1(specific_code):
    """
    Function to get the equivalent ISO 639-1 code from an ISO 639-3 code if it exists.

    :param specific_code: An ISO 639-3 code.
    :return:
    """

    for key, value in MAIN_LANGUAGES.items():
        module_iso3 = value['language_code_3']
        if specific_code == module_iso3:
            return key

    return None


def country_converter(text_input, abbreviations_okay=True):
    """
    Function that detects a country name in a given word.

    :param text_input: Any string.
    :param abbreviations_okay: means it's okay to check the list for abbreviations, like MX or GB.
    :return:
    """

    # Set default values
    country_code = ""
    country_name = ""

    if len(text_input) <= 1:  # Too short, can't return anything for this.
        pass
    elif len(text_input) == 2 and abbreviations_okay is True:  # This is only two letters long
        text_input = text_input.upper()  # Convert to upper case
        for country in COUNTRY_LIST:
            if text_input == country[1]:  # Matches exactly
                country_code = text_input
                country_name = country[0]
    elif len(text_input) == 3 and abbreviations_okay is True:  # three letters long code
        text_input = text_input.upper()  # Convert to upper case
        for country in COUNTRY_LIST:
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


def converter(input_text):
    """
    A function that can convert between language names and codes, and also parse additional data.
    This is one of the most crucial components of Ziwen and is very commonly used.

    :param input_text: Any string that may be a language name or code.
    :return: A tuple with Code, Name, Supported (boolean), country (if present).
    """

    # Set default values
    supported = False
    language_code = ""
    language_name = ""
    country_name = ""
    regional_case = False
    is_script = False
    country_code = None
    targeted_language = str(input_text)

    # There's a hyphen... probably a special code.
    if "-" in input_text and "Anglo" not in input_text:
        broader_code = targeted_language.split("-")[0]  # Take only the language part (ar).
        specific_code = targeted_language.split("-")[1]  # Get the specific code.
        if len(specific_code) <= 1:  # If it's just a letter it cannot be valid.
            input_text = broader_code
            specific_code = None
    else:  # Normal code
        broader_code = specific_code = None

    # Special code added to process codes with - in it.
    if specific_code is not None:  # special code (unknown-cyrl / ar-LB).
        # This takes a code and returns a name ar-LB becomes Arabic <Lebanon> and unknown-CYRL becomes Cyrillic (Script)
        if broader_code == "unknown":  # This is going to be a script.
            try:
                input_text = lang_code_search(specific_code, script_search=True)[0]  # Get the script name.
                is_script = True
            except TypeError:  # Not a valid code. 
                pass
        else:  # This should be a language code with a country code.
            regional_case = True
            country_code = country_converter(specific_code, True)[0].upper()
            country_name = country_converter(country_code, True)[1]
            input_text = broader_code
            if ("{}-{}".format(input_text, country_code) in ISO_DEFAULT_ASSOCIATED or
                    country_code.lower() == input_text.lower()):  # Something like de-DE or zh-CN
                regional_case = False
                country_code = None
                # We don't want to mark the default countries as too granular ones.
            if len(country_name) == 0:  # There's no valid country from the converter. Reset it.
                input_text = targeted_language  # Redefine the language as the original (pre-split)
                regional_case = False
                country_code = None
    elif "{" in input_text and len(input_text) > 3:  # This may have a country tag. Let's be sure to remove it.
        regional_case = True
        country_name = input_text.split("{")[1]
        country_name = country_name[:-1]
        country_code = country_converter(country_name)[0]
        input_text = input_text.split("{")[0]  # Get just the language.

    # Make a special exemption for COUNTRY CODES because people keep messing that up.
    for key, value in MISTAKE_ABBREVIATIONS.items():
        if len(input_text) == 2 and input_text.lower() == key:
            # If it's the same, let's replace it with the proper one.
            input_text = value
            continue

    # We also want to help convert ISO 639-2B codes (there are twenty of them)
    for key, value in ISO_639_2B.items():
        if len(input_text) == 3 and input_text.lower() == key:
            # If it's the same, let's replace it with the proper one.
            input_text = value
            continue

    # Convert and reassign special-reserved ISO 639-3 codes to their r/translator equivalents.
    if input_text in ['mis', 'und', 'mul', 'qnp']:  # These are special codes that we reassign
        supported = True
        if input_text == "mul":
            input_text = "multiple"
        elif input_text in ['mis', 'und', 'qnp']:  # These are assigned to "unknown"
            input_text = "unknown"

    # Start processing the string.
    if len(input_text) < 2:  # This is too short.
        language_code = ""
        language_name = ""
    elif is_script:  # This is a script.
        language_code = specific_code
        language_name = input_text
    elif input_text.lower() in ISO_639_1:  # Everything below is accessing languages. This is a ISO 639-1 code.
        language_code = input_text.lower()
        language_name = MAIN_LANGUAGES[language_code]['name']
        supported = MAIN_LANGUAGES[language_code]['supported']
    elif len(input_text) == 3 and input_text.lower() in ISO_639_3:  # This is equivalent to a supported one, eg 'cmn'.
        for key, value in MAIN_LANGUAGES.items():
            if input_text.lower() == value['language_code_3']:
                language_code = key
                language_name = MAIN_LANGUAGES[language_code]['name']
                supported = MAIN_LANGUAGES[language_code]['supported']
    elif len(input_text) == 3 and len(language_name_search(input_text.title())) != 0:  # This is three letters and name.
        language_code = language_name_search(input_text.title())  # An example of this is 'Any'.
        language_name = MAIN_LANGUAGES[language_code]['name']
    elif len(input_text) == 3 and input_text.lower() not in ISO_639_3:  # This may be a non-supported ISO 639-3 code.
        results = lang_code_search(input_text, False)[0]  # Consult the CSV file.
        if len(results) != 0:  # We found a matching language name.
            language_code = input_text.lower()
            language_name = results
    elif len(input_text) > 3:  # Not a code, let's look for names.
        if input_text.title() in ISO_NAMES:  # This is a defined language with a name.
            language_code = language_name_search(input_text.title())  # This searches both regular and alternate names.
            language_name = MAIN_LANGUAGES[language_code]['name']
            supported = MAIN_LANGUAGES[language_code]['supported']
        elif input_text.title() not in ISO_NAMES:
            if input_text.title() not in FUZZ_IGNORE_WORDS:
                # No name found. Apply fuzzy matching.
                fuzzy_result = fuzzy_text(input_text.title().strip())
            else:
                fuzzy_result = None

            if fuzzy_result is not None:  # We found a language that this is close to in spelling.
                language_code = language_name_search(fuzzy_result.title())
                language_name = str(fuzzy_result)
                supported = MAIN_LANGUAGES[language_code]['supported']
            else:  # No fuzzy match. Now we're going to check if it's the name of an ISO 639-3 language or script.
                total_results = lang_code_search(input_text, False)
                specific_results = total_results[0]
                if len(specific_results) != 0:
                    language_code = specific_results
                    language_name = lang_code_search(language_code, total_results[1])[0]
                    if language_code in MAIN_LANGUAGES:
                        supported = MAIN_LANGUAGES[language_code]['supported']
                elif len(specific_results) == 0 and len(input_text) == 4:  # This is a script code.
                    script_results = lang_code_search(input_text, True)[0]
                    if len(script_results) != 0:
                        language_name = script_results
                        language_code = lang_code_search(script_results, True)[0]

    # We are re-enabling using < > to denote country names in certain ISO 639-3 languages.
    # if "<" in language_name:  # Strip the brackets from ISO 639-3 languages.
    #    language_name = language_name.split("<")[0].strip()  # Remove the country name in brackets

    if len(language_code) == 0:  # There's no valid language so let's reset the country values.
        country_code = None
    elif regional_case and len(country_name) != 0 and len(language_code) != 0:  # This was for a specific language area.
        language_name += " {" + country_name + "}"

    return language_code, language_name, supported, country_code


def country_validator(word_list, language_list):
    """
    Takes a list of words, check for a country and a matching language. This allows us to find combinations like de-AT.

    :param word_list: A list of words that may contain a country name.
    :param language_list: A list of words that may contain a language name.

    :return: If nothing is found it just returns None.
    :return: If something is found, returns tuple (lang-COUNTRY, ISO 639-3 code).
    """

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
    """
    A function that takes a comment and looks for actable information like languages or words to lookup.
    This drives commands that take a language variable, like `!identify:` or `!translate:`.
    IMPORTANT: The command part MUST include the colon (:), or else it will fail.

    :param pbody: Any text that contains a Ziwen command.
    :param command: The command we want to parse. For example, `!identify:`.
    :return: Returns a tuple. The first part is the string that the command should act on. The second part is whether or
             not it qualifies for "advanced mode" as part of `!identify`. This means it has an additional `!` after
             the language name or code.
    """

    advanced_mode = False
    longer_search = False
    match = ""

    if '!id:' in pbody:  # Allows for a synonym
        pbody = pbody.replace("!id:", "!identify:")

    if '\n' in pbody:  # Replace linebreaks
        pbody = pbody.replace("\n", " ")

    command_w_space = command + " "
    if command_w_space in pbody:  # Fix in case there's a space after the colon
        pbody = pbody.replace(command_w_space, command)
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
            match = re.search(command + '(.*?)!', pbody)
            match = str(match.group(1)).lower()  # Convert it to a string.
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

    if not longer_search:  # There are no quotes, so this is for just one word.
        if advanced_mode is not True:
            if command in pbody:  # there is a language specified
                match = re.search('(?<=' + command + r')[\w\-<^\'+]+', pbody)
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


def english_fuzz(word):
    """
    A quick function that detects if a word is likely to be "English." Used in replace_bad_english_typing below.

    :param word: Any word.
    :return: A boolean. True if it's likely to be a misspelling of the word 'English', false otherwise.
    """

    word = word.title()
    closeness = fuzz.ratio("English", word)
    if closeness > 70:  # Very likely
        return True
    else:  # Unlikely
        return False


def replace_bad_english_typing(title):
    """
    Function that will replace a misspelling for English, so that it can still pass the title filter routine.

    :param title: A post title on r/translator, presumably one with a misspelling.
    :return: The post title but with any words that were mispellings of 'English' replaced.
    """

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
            title = title.replace(word, "English")  # Replace the offending word with the proper spelling.

    return title  # Return the title, now cleaned up.


def language_mention_search(search_paragraph):
    """
    Returns a list of identified language names from a text. Useful for Wiktionary search and title formatting.
    This function only looks for more common languages; there are too many ISO 639-3 languages (about 7800 of them),
    many of which have names that match English words.

    :param search_paragraph: The text that we're going to look for a language name in.
    :return to_post: None if nothing found; a list of language names found otherwise.
    """

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
    """
    Function that takes a badly formatted title and makes it okay. It searches for a language name in the title text.
    If it finds a language name, then it creates a language tag to it and adds it to the original title.
    If no language name is found, then the default of "Unknown" is added to the title.
    This function is used when filtering out posts that violate the guidelines; the user is given this reformatted title
    as an option they can use to resubmit.

    :param title_text: A problematic Reddit post title that does not match the formatting guidelines.
    :return new_title: A reformatted title that adheres to the community's guidelines.
    """

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

    if len(new_title) >= 300:  # There is a hard limit on Reddit title lengths
        new_title = new_title[0:299]  # Shorten it.

    return new_title


def detect_languages_reformat(title_text):
    """
    This function tries to salvage a badly formatted title and render it better for the title routine.
    For example, the title may be: `English to Chinese Lorem Ipsum`. This function can take that and reformat it to
    make more sense: `[English > Chinese] Lorem Ipsum`

    :param title_text: The title to evaluate and reformat.
    :return: None if it is unable to make sense of it, a reformatted title otherwise.
    """

    title_words_selected = {}  # Create a dictionary
    new_title_text = ""
    language_check = last_language = None
    title_words = re.compile(r'\w+').findall(title_text)

    title_words_reversed = list(reversed(title_words))

    for word in title_words[:7]:

        if word.lower() == "to":
            continue

        language_check = language_mention_search(word.title())
        if language_check is not None:
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
        if title_words_selected[key] == last_language:
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
    """
    This function takes in a title text and returns a boolean as to whether it should be given the 'App' code.
    This is only applicable for 'multiple' posts.

    :param title_text: A title of a Reddit post to evaluate. This will one that would otherwise be a "Multiple" post.
    :return: True if it *should* be given the 'App' code, False otherwise.
    """

    title_text = title_text.lower()
    if any(keyword in title_text for keyword in APP_WORDS):
        return True  # Yes, this should be an app post.
    else:
        return False  # No it's not.


def multiple_language_script_assessor(language_list):
    """
    A function that takes a list of languages/scripts and determines if it is actually all multiple languages.

    :param language_list: A list of languages and possibly scripts.
    :return: True if everything is on the list is a language, False if there are in fact script codes in the list.
    """

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
    """
    This function evaluates two lists of languages: One list is source languages, one list is target languages.
    Its purpose is to evaluate if it is a true request for two non-English requests (e.g. [French > Catalan])
    If it detects "English" in both lists, though, then it's not a true non-English request since the user can accept
    English as one of their options.
    The importance of this is because Ziwen will send notifications to both languages if the request is non-English.

    :param source_language: A list of source language names for a post.
    :param target_language: A list of target language names for a post.
    :return: A list of the languages for notifying, or None if there's nothing to return.
    """

    all_languages = list(set(source_language + target_language))

    if "English" in all_languages:  # English is in here, so it CAN'T be what we're looking for.
        return None

    if len(all_languages) <= 1:
        return None
    else:
        return all_languages


def determine_title_direction(source_languages_list, target_languages_list):
    """
    Function takes two language lists and determines what the direction of the request is.
    This statistic is stored in Ajos and Wenyuan uses it for statistics as well.

    :param source_languages_list: A list of languages that are determined to be the source.
    :param target_languages_list: A list of languages that are determined to be the target.
    :return: One of four variables: (english_from, english_to, english_both, english_none)
    """

    # Create local lists to avoid changing the main function's lists
    source_languages_local = list(source_languages_list)
    target_languages_local = list(target_languages_list)

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
    """
    This function takes two list of languages and tries to salvage SOMETHING out of them. This is used for titles
    that are just plain incomprehensible and is a last-ditch function by title_format() below.

    :param d_source_languages: A list of languages that are determined to be the source.
    :param d_target_languages: A list of languages that are determined to be the target.
    :return: None if it's unable to comprehend the list of languages. A tuple with a CSS code and text otherwise.
    """

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
    """
    This is the main function to help format a title and to determine information from it.
    The creation of Ajos relies on this process, and the flair and flair text that's assigned to an incoming post is
    also determined by this central function.

    This is also a rather unruly function because it's probably the function that been added to and extended the most.

    :param display_process: is a boolean that allows us to see the steps taken (a sort of debug mode, Wenyuan uses it).
    :param title: The title of the r/translator post to evaluate.
    :return: d_source_languages: A list of languages that the function determines are the source.
             d_target_languages: A list of languages that the function determines are the target.
             final_css: The determination of what CSS code the title should get (usually the language's code).
             final_css_text: The determination of what CSS text the title should get (usually the language name).
             actual_title: The title of the post minus its language tag.
             processed_title: The title of the post as processed by the routine (including modifications by other
                              functions listed above).
             notify_languages: (optional) If there are more languages to notify for than just the main one.
             language_country: (optional) A country specified for the language, e.g. Brazil for Portuguese.
             direction: What translation direction (relative to English) the post is for.
    """

    source_language = target_language = country_suffix_code = ""  # Set defaults
    final_css = "generic"
    final_code_tag = final_css.title()

    has_country = False
    notify_languages = None

    # Strip cross-post formatting, which happens at the end.
    if "(x-post" in title:
        title = title.split("(x-post")[0].strip()

    for spelling in MAIN_LANGUAGES['en']['alternate_names']:  # Replace typos or misspellings in the title for English.
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

    # Let's replace any problematic characters or formatting early. Especially those that are important to splitting.
    if any(keyword in title for keyword in WRONG_DIRECTIONS):  # Fix for some Unicode arrow-looking thingies
        for keyword in WRONG_DIRECTIONS:
            title = title.replace(keyword, " > ")
    if any(keyword in title for keyword in WRONG_BRACKETS_LEFT):  # Fix for some Unicode left bracket-looking thingies
        for keyword in WRONG_BRACKETS_LEFT:
            title = title.replace(keyword, " [")
    if any(keyword in title for keyword in WRONG_BRACKETS_RIGHT):  # Fix for some Unicode right bracket-looking thingies
        for keyword in WRONG_BRACKETS_RIGHT:
            title = title.replace(keyword, "] ")

    if ">" not in title and " to " in title.lower():
        title = title.replace(" To ", " to ")
        title = title.replace(" TO ", " to ")
        title = title.replace(" tO ", " to ")

    if "]" not in title and "[" not in title and re.match(r"\((.+(>| to ).+)\)", title):
        # This is for cases where we have no square brackets but we have a > or " to " between parantheses instead.
        # print("Replacing parantheses...")
        title = title.replace("(", "[", 1)  # We only want to replace the first occurence.
        title = title.replace(")", "]", 1)
    elif "]" not in title and "[" not in title and re.match(r"{(.+(>| to ).+)}", title):
        # This is for cases where we have no square brackets but we have a > or " to " between curly braces instead.
        # print("Replacing braces...")
        title = title.replace("{", "[", 1)  # We only want to replace the first occurence.
        title = title.replace("}", "]", 1)

    if "]" not in title and "[" not in title:  # Otherwise try to salvage it and reformat it.
        reformat_example = detect_languages_reformat(title)
        if reformat_example is not None:
            title = reformat_example

    # Some regex magic, replace things like [Language] >/- [language]
    title = re.sub(r'(\]\s*[>\\-]\s*\[)', " > ", title)

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
        hyphen_match = re.search(r'((?:\w+-)+\w+)', title)  # Try to match a hyphenated word (Puyo-Paekche)
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

    if "KR " in title.upper()[0:10]:  # KR is technically Kanuri but no one actually means it to be Kanuri.
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

    source_language = re.sub(r"""
                           [,.;@#?!&$()\[\]/“”’"•]+  # Accept one or more copies of punctuation
                           \ *           # plus zero or more copies of a space,
                           """,
                             " ",  # and replace it with a single space
                             source_language, flags=re.VERBOSE)
    source_language = source_language.title()
    source_language = source_language_original = source_language.split()  # Convert it from a string to a list

    # If there are two or three words only in source language, concatenate them to see if there's another that exists...
    # (e.g. American Sign Language)
    if len(source_language) >= 2:
        if source_language[1].strip() != "-":
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

    language_country = None

    if not has_country:  # There isn't a country digitally in the source language part.
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


def language_list_splitter(list_string):
    """
    A function to help split up lists of codes or names of languages with different delimiters.
    An example would be a string like `ar, latin, yi` or `ko+lo`. This function will be able to split it no matter what.

    :param: A possible list of languages as a string.
    :return: A list of language codes that were determined from the string. None if there are no valid ones found.
    """

    final_codes = []

    if 'LANGUAGES:' in list_string:  # Remove colon, partition the part we need.
        list_string = list_string.rpartition('LANGUAGES:')[-1].strip()
    else:
        list_string = list_string.strip()  # Remove spaces.

    # Set delimiters and divide. Delimiters: `+`, `,`, `/`, `\n`, ` `. The space is the last resort.
    standard_delimiters = ['+', '\n', '/', ':', ';']
    for character in standard_delimiters:  # Iterate over our list.
        if character in list_string:
            list_string = list_string.replace(character, ',')

    # Special case if there's only spaces - check to see if the whole thing
    if ',' not in list_string and ' ' in list_string:
        # Assess whether the whole thing is a multi-word language itself.
        all_match = converter(list_string)[0]
        if len(all_match) == 0:  # No match
            temporary_list = list_string.split(' ')  # Separate by spaces
        else:  # There is a match.
            temporary_list = [all_match]

    else:
        # Get the individual elements with a first pass.
        temporary_list = list_string.split(',')

    temporary_list = [x.strip() for x in temporary_list if x]  # Remove blank strings.
    utility_codes = ['meta', 'community']
    # Clean up and get the codes.
    for item in temporary_list:
        item = item.lower()  # Remove spaces.

        # Get the code.
        converted_data = converter(item)

        if converted_data[3] is None:  # This has no country data attached to it.
            code = converted_data[0]
        else:
            code = "{}-{}".format(converted_data[0], converted_data[3])

        if len(code) != 0 and item != 'all':
            final_codes.append(code)
        elif item == 'all':  # This is to help process 'all' unsubscription requests.
            final_codes.append(item)
        elif item in utility_codes:
            final_codes.append(item)

    # Remove duplicates and alphabetize.
    final_codes = list(set(final_codes))
    final_codes = sorted(final_codes, key=str.lower)

    if len(final_codes) == 0:
        return None
    else:
        return final_codes


def main_posts_filter_required_keywords():
    """
    This function takes the language name list and a series of okay words for English and generates a list of keywords
    that we can use to enforce the formatting requirements. This is case-insensitive and also allows more flexibility
    for non-English requests.

    :return: A dictionary with two keys: `total`, and `to_phrases`.
    """

    possible_strings = {'total': [], 'to_phrases': []}

    # Create a master list of words for "English"
    words_for_english = ['english', 'en', 'eng', 'englisch', 'англи́йский', '英語', '英文']

    # Create a list of connecting words between languages.
    words_connection = [">", "to", "<", "〉", "›", "》", "»", "⟶", "→", "~"]

    # Add to the list combinations with 'English' that are allowed.
    for word in words_for_english:
        for connector in words_connection:
            temporary_list = [" {} {}".format(connector, word), "{} {} ".format(word, connector)]

            if connector != "to":
                temporary_list.append("{}{}".format(connector, word))
                temporary_list.append("{}{}".format(word, connector))
            else:
                possible_strings['to_phrases'] += temporary_list
            possible_strings['total'] += temporary_list

    # Add to the list combinations with language names that are allowed.
    for language in SUPPORTED_LANGUAGES:
        language_lower = language.lower()
        for connector in words_connection:
            temporary_list = [" {} {}".format(connector, language_lower), "{} {} ".format(language_lower, connector)]

            if connector != "to":
                temporary_list.append("{}{}".format(connector, language_lower))
                temporary_list.append("{}{}".format(language_lower, connector))
            else:
                possible_strings['to_phrases'] += temporary_list
            possible_strings['total'] += temporary_list

    # Add to the list combinations with just dashes.
    added_hyphens = []
    for item in ENGLISH_DASHES:
        added_hyphens.append(item.lower())
    added_hyphens = list(sorted(added_hyphens))

    # Function tags.
    possible_strings['total'] += ['>', '[unknown]', '[community]', '[meta]']
    possible_strings['total'] += added_hyphens

    # Remove false matches. These often get through even though they should not be allowed.
    bad_matches = ['ch to ', 'en to ', ' to en', ' to me', ' to mi', ' to my', ' to mr', ' to kn']
    possible_strings['to_phrases'] = [x for x in possible_strings['to_phrases'] if x not in bad_matches]
    possible_strings['total'] = [x for x in possible_strings['total'] if x not in bad_matches]

    return possible_strings


def main_posts_filter(otitle):
    """
    A functionized filter for title filtering (removing posts that don't match the formatting guidelines).
    This was decoupled from ziwen_posts in order to be more easily maintained and to allow Wenyuan to use it.

    :param otitle: Any potential or actual r/translator post title.
    :return: post_okay: A boolean determining whether the post fits the community formatting guidelines.
             otitle: A currently unused variable that would potentially allow this function to change the title text.
             filter_reason: If the post violates the rules, the filter_reason is a one/two-letter code indicating
                            what particular formatting rule it violated.
                            1: The title contained none of the required keywords.
                            1A: The title contained a string like "to English" but it was not in the first part of it.
                            1B: The title was super short and generic. (e.g. 'Translation to English')
                            2: The title contained the important symbol `>` but it was randomly somewhere in the title.
                            EE: (not activated here) English-only post. (e.g. 'English > English')
    """

    post_okay = True
    filter_reason = None

    # Obtain a list of keywords that we will allow.
    main_keywords = main_posts_filter_required_keywords()
    mandatory_keywords = main_keywords['total']
    to_phrases_keywords = main_keywords['to_phrases']

    if not any(keyword in otitle.lower() for keyword in mandatory_keywords):
        # This is the same thing as AM's content_rule #1. The title does not contain any of our keywords.
        # But first, we'll try to salvage the title into something we can work with.
        otitle = replace_bad_english_typing(otitle)  # This replaces any bad words for "English"

        # The function below would allow for a lot looser rules but is currently unused.
        '''
        otitle = bad_title_reformat(otitle)
        if "[Unknown > English]" in otitle:  # The title was too generic, we ain't doing it.
            print("> Filtered a post out due to incorrect title format. content_rule #1")
            post_okay = False
        '''

        if not any(keyword in otitle.lower() for keyword in mandatory_keywords):  # Try again
            filter_reason = '1'
            print("[L] Main_Posts_Filter: > Filtered a post with an incorrect title format. Rule: #" + filter_reason)
            post_okay = False
    elif ">" not in otitle:  # Try to take out titles that bury the lede.

        if any(phrase in otitle.lower() for phrase in to_phrases_keywords):

            if not any(phrase in otitle.lower()[:25] for phrase in to_phrases_keywords):
                # This means the "to LANGUAGE" part is probably all the way at the end. Take it out.
                filter_reason = '1A'
                print("[L] Main_Posts_Filter: > Filtered a post with an incorrect title format. Rule: #" + filter_reason)
                post_okay = False  # Since it's a bad post title, we don't need to process it anymore.

            # Added a Rule 1B, basically this checks for super short things like 'Translation to English'
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
                    print("[L] Main_Posts_Filter: > Filtered a post with no valid language. Rule: #" + filter_reason)
    if ">" in otitle and "]" not in otitle and ">" not in otitle[0:50]:
        # If people tack on the languages as an afterthought, it can be hard to process.
        filter_reason = '2'
        print("[L] Main_Posts_Filter: > Filtered a post out due to incorrect title format. Rule: #" + filter_reason)
        post_okay = False

    if post_okay is True:
        return post_okay, otitle, filter_reason
    else:  # This title failed the test.
        return post_okay, None, filter_reason
