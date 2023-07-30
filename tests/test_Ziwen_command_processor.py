from sqlite3 import Connection, Cursor
from unittest.mock import MagicMock
from code.Ziwen_command_processor import ZiwenCommandProcessor
from code.Ajo import Ajo
import praw

from code.Ziwen_helper import ZiwenConfig


def test_init():
    comment = MagicMock(praw.reddit.models.Comment)
    ajo = MagicMock(Ajo)
    submission = MagicMock(praw.reddit.models.Submission)
    config = MagicMock(ZiwenConfig)
    config.zw_useragent = {}
    config.reddit = MagicMock(praw.Reddit)
    config.cursor_main = MagicMock(Cursor)
    config.cursor_ajo = MagicMock(Cursor)
    config.conn_main = MagicMock(Connection)
    config.post_templates = {}
    ZiwenCommandProcessor(
        "",
        "",
        comment,
        "",
        "",
        "",
        "",
        ajo,
        submission,
        "",
        0,
        "",
        "",
        "",
        config,
    )
