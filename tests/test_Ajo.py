from code.Ajo import Ajo, AjoLanguageInfo
from unittest.mock import MagicMock
import praw
import pickle


def test_init():
    reddit_submission = MagicMock(praw.reddit.models.Submission)
    reddit_submission.id = "123"
    reddit_submission.created_utc = 1.0
    reddit_submission.title = "hello"
    reddit_submission.link_flair_css_class = ""
    reddit_submission.link_flair_text = ""
    Ajo().init_from_submission(reddit_submission, {})


def test_ajo_language_info_init():
    AjoLanguageInfo()


serialized_str = "{'created_utc': 1515795465, 'direction': 'english_from', 'is_long': False, 'language_name': 'Italian', 'original_source_language_name': 'English', 'status': 'translated', 'id': '7q07n6', 'original_target_language_name': 'Italian', 'is_identified': False, 'country_code': None, 'output_oflair_css': 'translated', 'output_oflair_text': 'Translated [IT]', 'title_original': '[English > Italian] \"Body Mind & Soul\"', 'language_code_1': 'it', 'is_bot_crosspost': False, 'is_supported': True, 'type': 'single', 'language_code_3': 'ita', 'title': '\"Body Mind  &  Soul\"'}"

repr_str = "{'output_oflair_css': 'translated', 'output_oflair_text': 'Translated [IT]', 'ajo_language_info': {'is_multiple': False, 'language_code_1': 'it', 'language_code_3': 'ita', 'language_name': 'Italian', 'country_code': None, 'language_history': [], 'is_supported': True}, 'created_utc': 1515795465, 'direction': 'english_from', 'is_long': False, 'original_source_language_name': 'English', 'status': 'translated', 'id': '7q07n6', 'original_target_language_name': 'Italian', 'is_identified': False, 'title_original': '[English > Italian] \"Body Mind & Soul\"', 'is_bot_crosspost': False, 'type': 'single', 'title': '\"Body Mind  &  Soul\"'}"


def test_ajo_from_str():
    ajo_dict = eval(serialized_str)
    test_ajo = Ajo().init_from_values(ajo_dict)
    assert repr(test_ajo) == repr_str


def test_ajo_reserialize():
    ajo_dict = eval(serialized_str)
    test_ajo = Ajo().init_from_values(ajo_dict)
    made_from_test_ajo = eval(repr(test_ajo))
    assert (
        repr(test_ajo) == repr(Ajo().init_from_values(made_from_test_ajo)) == repr_str
    )


def test_ajo_reset():
    ajo_dict = eval(serialized_str)
    test_ajo = Ajo().init_from_values(ajo_dict)
    test_ajo.reset(test_ajo.title)
    assert test_ajo.status == "untranslated"
    assert test_ajo.is_identified == False


def test_ajo_set_script():
    ajo_dict = eval(serialized_str)
    test_ajo = Ajo().init_from_values(ajo_dict)
    test_ajo.set_script("hira")
    assert test_ajo.script_code == "hira"
    assert test_ajo.script_name == "Hiragana"


pickled_data = "{'output_oflair_css': None, 'output_oflair_text': None, 'id': '15122fm', 'created_utc': 1689500594, 'recorded_translators': [], 'notified': [], 'time_delta': {}, 'author_messaged': False, 'post_templates': {}, 'author': 'your_average_bear', 'ajo_language_info': {'is_multiple': True, 'language_code_1': ['it', 'ru', 'uz'], 'language_code_3': ['ita', 'rus', 'uzn'], 'language_name': ['Italian', 'Russian', 'Uzbek'], 'country_code': None, 'language_history': ['Multiple Languages'], 'is_supported': True}, 'is_long': False, 'is_identified': False, 'direction': 'english_none', 'original_source_language_name': 'Unknown', 'original_target_language_name': 'Chinese', 'title': 'hi', 'title_original': '[unknown > chinese] hi', 'status': {'it': 'untranslated', 'ru': 'translated', 'uz': 'untranslated'}, 'is_bot_crosspost': False}"


def test_ajo_from_reddit_pickle():
    with open("tests/pickle_test_data/reddit_submission.pickle", "rb") as f:
        data = pickle.loads(f.read())
        my_ajo = Ajo.init_from_submission(data, {})
        assert repr(my_ajo) == pickled_data
