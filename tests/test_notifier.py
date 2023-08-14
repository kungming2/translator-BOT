from sqlite3 import Connection, Cursor
from unittest.mock import MagicMock, patch
import praw
import pytest
from code.Ajo import Ajo

from code.Ziwen_helper import ZiwenConfig
from code.notifier import ZiwenMessageProcessor, ZiwenNotifier, ziwen_messages
from code._config import BOT_DISCLAIMER
from code._responses import MSG_UNSUBSCRIBE_BUTTON


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


@patch("code.notifier.action_counter")
def test_ziwen_notifier(mock_config):
    notifier = ZiwenNotifier(mock_config)

    mock_config.cursor_main.fetchall.return_value = [
        {"username": "mem1"},
        {"username": "mem2"},
    ]
    mock_config.cursor_main.fetchone.return_value = None
    with patch("code.notifier.ajo_loader", return_value=MagicMock(Ajo)), patch.object(
        notifier, "_ZiwenNotifier__messaging_language_frequency", return_value=None
    ):
        assert notifier.ziwen_notifier(
            "chinese",
            "my title",
            "https://www.reddit.com/r/translator/comments/15f3gts/japaneseenglish_my_friend_was_looking_to_buy_this/jue1gdz/",
            "author",
            True,
        ) == ["mem1", "mem2"]


def generate_mock_message(message):
    mock_message = MagicMock(praw.reddit.models.Message)
    mock_message.author = "example_author"
    mock_message.subject = message
    mock_message.body = "chinese"
    return mock_message


@patch("code.notifier.action_counter")
def test_ziwen_messages_ping(mock_config):
    mock_config.is_mod.return_value = False
    mock_message = generate_mock_message("PING")
    mock_config.reddit.inbox.unread.return_value = [mock_message]
    ziwen_messages(mock_config)
    mock_message.reply.assert_called_with(
        "Ziwen is running nominally.\n\n" + BOT_DISCLAIMER
    )


# ZiwenMessageProcessor tests
def test_message_ping(mock_config):
    mock_config.is_mod.return_value = False
    mock_message = generate_mock_message("PING")
    processor = ZiwenMessageProcessor(mock_config, mock_message)
    processor.process_ping()
    mock_message.reply.assert_called_with(
        "Ziwen is running nominally.\n\n" + BOT_DISCLAIMER
    )


@patch("code.notifier.action_counter")
def test_ziwen_message_subscribe(mock_config):
    mock_message = generate_mock_message("SUBSCRIBE")
    mock_config.cursor_main.fetchone.return_value = {"user_count": 0}
    processor = ZiwenMessageProcessor(mock_config, mock_message)
    processor.process_subscribe()
    mock_config.cursor_main.execute.assert_called_with(
        "INSERT INTO notify_users VALUES (? , ?)", ("zh", "example_author")
    )


@patch("code.notifier.action_counter")
def test_message_unsubscribe(mock_config):
    mock_message = generate_mock_message("UNSUBSCRIBE")
    mock_config.cursor_main.fetchone.return_value = {"user_count": 1}
    processor = ZiwenMessageProcessor(mock_config, mock_message)
    processor.process_unsubscribe()
    mock_config.cursor_main.execute.assert_called_with(
        "DELETE FROM notify_users WHERE language_code = ? and username = ?",
        ("zh", "example_author"),
    )


@patch("code.notifier.action_counter")
def test_message_status(mock_config):
    mock_message = generate_mock_message("STATUS")
    # response for each time fetchone is called
    mock_config.cursor_main.fetchone.side_effect = [
        {
            "commands": "{'!doublecheck': 4, '!page:': 1, '!search:': 15, '!translated': 354, '!identify:': 192, '`': 150, '!missing': 11, '!set:': 31, '!claim': 1, '!reset': 10}"
        },
        {"received": '{"ja": 6, "zh": 4}'},
    ]
    processor = ZiwenMessageProcessor(mock_config, mock_message)
    processor.process_status()
    mock_message.reply.assert_called_with(
        "### Notifications\n\nSorry, you're not currently subscribed to notifications for any [language posts](https://www.reddit.com/r/translatorBOT/wiki/ziwen#wiki_language_codes.2Fnames_syntax) on r/translator. Would you like to [sign up](https://www.reddit.com/message/compose?to=translator-BOT&subject=Subscribe&message=%23%23+Sign+up+for+notifications+about+new+requests+for+your+language%21%0A%23%23+List+language+codes+or+names+after+the+colon+below+and+separate+languages+with+commas.%0A%23%23+You+can+sign+up+for+one+language+or+as+many+as+you%27d+like.%0ALANGUAGES%3A+)?\n\n### User Commands Statistics\n\n| Command | Times |\n|---------|-------|\n| !claim | 1 |\n| !doublecheck | 4 |\n| !identify: | 192 |\n| !missing | 11 |\n| !page: | 1 |\n| !reset | 10 |\n| !search: | 15 |\n| !set: | 31 |\n| !translated | 354 |\n| `lookup` | 150 |\n| Notifications (`ja`) | 6 |\n| Notifications (`zh`) | 4 |"
        + BOT_DISCLAIMER
        + MSG_UNSUBSCRIBE_BUTTON
    )
