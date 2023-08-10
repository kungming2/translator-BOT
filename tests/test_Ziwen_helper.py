from unittest.mock import MagicMock
import praw

from code.Ziwen_helper import ZiwenConfig, lookup_matcher


def test_ziwenconfig_init():
    ZiwenConfig(MagicMock(praw.Reddit), MagicMock(praw.reddit.models.SubredditHelper))


def test_lookup_matcher1():
    assert lookup_matcher("`嫁狗随狗`", None) == ["嫁狗随狗"]


def test_lookup_matcher2():
    assert lookup_matcher("`你好吗`", "Chinese") == {"Chinese": ["你好", "吗"]}


def test_lookup_matcher3():
    assert lookup_matcher("!identify: chinese \n `你好吗`", "Spanish") == {
        "Chinese": ["你好", "吗"]
    }


def test_lookup_matcher4():
    assert lookup_matcher("!identify: spanish \n `me llamo`", "Chinese") == {
        "Spanish": ["me", "llamo"]
    }
