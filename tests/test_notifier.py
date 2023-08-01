from sqlite3 import Connection, Cursor
from unittest.mock import MagicMock
import praw
import pytest

from code.Ziwen_helper import ZiwenConfig
from code.notifier import ZiwenMessages, ZiwenNotifier


@pytest.fixture
def mock_config():
    config = MagicMock(ZiwenConfig)
    config.zw_useragent = {}
    config.reddit = MagicMock(praw.Reddit)
    config.cursor_main = MagicMock(Cursor)
    config.cursor_ajo = MagicMock(Cursor)
    config.conn_main = MagicMock(Connection)
    config.post_templates = {}
    return config


def test_init_ziwen_notifier(mock_config):
    ZiwenNotifier(mock_config)


def test_init_ziwen_messages(mock_config):
    ZiwenMessages(mock_config)
