from sqlite3 import Connection, Cursor
from unittest.mock import MagicMock
import praw

from code.Ziwen_helper import ZiwenConfig


def test_ziwenconfig_init():
    conn_cache = MagicMock(Connection)
    cursor_cache = MagicMock(Cursor)
    conn_main = MagicMock(Connection)
    cursor_main = MagicMock(Cursor)
    conn_ajo = MagicMock(Connection)
    cursor_ajo = MagicMock(Cursor)
    reddit = MagicMock(praw.Reddit)
    subreddit_helper = MagicMock(praw.reddit.models.SubredditHelper)
    ZiwenConfig(
        conn_cache,
        cursor_cache,
        conn_main,
        cursor_main,
        conn_ajo,
        cursor_ajo,
        reddit,
        subreddit_helper,
    )
