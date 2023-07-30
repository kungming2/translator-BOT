from sqlite3 import Cursor
from unittest.mock import MagicMock
from Ziwen_command_processor import ZiwenCommandProcessor
import Ajo
import praw


def test_init():
    reddit = MagicMock(praw.Reddit)
    cursor_main = MagicMock(Cursor)
    cursor_ajo = MagicMock(Cursor)
    comment = MagicMock(praw.reddit.models.Comment)
    ajo = MagicMock(Ajo)
    submission = MagicMock(praw.reddit.models.Submission)
    ZiwenCommandProcessor(
        {},
        "",
        reddit,
        cursor_main,
        cursor_ajo,
        {},
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
    )
