from unittest.mock import MagicMock
import praw

from code.Ziwen_helper import ZiwenConfig


def test_ziwenconfig_init():
    ZiwenConfig(MagicMock(praw.Reddit), MagicMock(praw.reddit.models.SubredditHelper))
