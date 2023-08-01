from sqlite3 import Connection, Cursor
from unittest.mock import MagicMock, patch
import praw
import pytest
from code.Ajo import Ajo

from code.Ziwen_helper import ZiwenConfig
from code.notifier import ZiwenNotifier, ziwen_messages


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


def test_ziwen_notifier(mock_config):
    notifier = ZiwenNotifier(mock_config)

    mock_config.cursor_main.fetchall.return_value = [
        {"username": "mem1"},
        {"username": "mem2"},
    ]
    mock_config.cursor_main.fetchone.return_value = None
    with patch(
        "code.notifier.ajo_loader", side_effect=lambda mid, loader: MagicMock(Ajo)
    ), patch.object(
        notifier, "_ZiwenNotifier__messaging_language_frequency", return_value=None
    ), patch(
        "code.notifier.action_counter"
    ):
        assert notifier.ziwen_notifier(
            "chinese",
            "my title",
            "https://www.reddit.com/r/translator/comments/15f3gts/japaneseenglish_my_friend_was_looking_to_buy_this/jue1gdz/",
            "author",
            True,
        ) == ["mem1", "mem2"]


def generate_subscribe_mock_message():
    mock_message = MagicMock()
    mock_message.author = "example_author"
    mock_message.subject = "SUBSCRIBE"
    mock_message.body = "chinese"
    yield mock_message


def test_ziwen_message_subscribe(mock_config):
    mock_config.reddit.inbox = MagicMock(praw.reddit.models.Inbox)
    mock_config.reddit.inbox.unread.return_value = generate_subscribe_mock_message()
    mock_config.cursor_main.fetchone.return_value = {"user_count": 0}
    with patch("code.notifier.action_counter"):
        ziwen_messages(mock_config)
    mock_config.cursor_main.execute.assert_called_with(
        "INSERT INTO notify_users VALUES (? , ?)", ("zh", "example_author")
    )


def generate_unsubscribe_mock_message():
    mock_message = MagicMock()
    mock_message.author = "example_author"
    mock_message.subject = "UNSUBSCRIBE"
    mock_message.body = "chinese"
    yield mock_message


def test_ziwen_message_unsubscribe(mock_config):
    mock_config.reddit.inbox = MagicMock(praw.reddit.models.Inbox)
    mock_config.reddit.inbox.unread.return_value = generate_unsubscribe_mock_message()
    mock_config.cursor_main.fetchone.return_value = {"user_count": 1}
    with patch("code.notifier.action_counter"):
        ziwen_messages(mock_config)
    mock_config.cursor_main.execute.assert_called_with(
        "DELETE FROM notify_users WHERE language_code = ? and username = ?",
        ("zh", "example_author"),
    )
