from sqlite3 import Connection, Cursor
from unittest.mock import MagicMock, patch

import pytest
from code.Ziwen_command_processor import ZiwenCommandProcessor
from code.Ajo import Ajo, AjoLanguageInfo
import praw

from code.Ziwen_helper import ZiwenConfig


@pytest.fixture
def mock_comment():
    return MagicMock(praw.reddit.models.Comment)


@pytest.fixture
def mock_ajo():
    ajo = MagicMock(Ajo)
    ajo.ajo_language_info = MagicMock(AjoLanguageInfo)
    ajo.ajo_language_info.language_name = ""
    return ajo


@pytest.fixture
def mock_submission():
    return MagicMock(praw.reddit.models.Submission)


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


def test_init(mock_comment, mock_ajo, mock_submission, mock_config):
    ZiwenCommandProcessor(
        "",
        "",
        mock_comment,
        "",
        "",
        "",
        "",
        mock_ajo,
        mock_submission,
        0,
        0,
        "",
        "",
        "",
        mock_config,
    )


# test reset
reset_test_cases = [
    (True, "test title", "diff_guy", "submitter_guy", True),  # Moderator case
    (False, "test title", "diff_guy", "submitter_guy", False),  # Not a moderator case
    # Submitter is commenter case
    (False, "test title", "submitter_guy", "submitter_guy", True),
]


@pytest.mark.parametrize(
    "is_mod, otitle, oauthor, pauthor, reset_called", reset_test_cases
)
def test_process_reset(
    mock_comment,
    mock_ajo,
    mock_submission,
    mock_config,
    is_mod,
    otitle,
    pauthor,
    oauthor,
    reset_called,
):
    mock_config.is_mod.return_value = is_mod

    processor = ZiwenCommandProcessor(
        "",
        pauthor,
        mock_comment,
        "",
        otitle,
        "",
        oauthor,
        mock_ajo,
        mock_submission,
        0,
        0,
        "",
        "",
        "",
        mock_config,
    )

    processor.process_reset()

    if reset_called:
        mock_ajo.reset.assert_called_once_with(otitle)
    else:
        mock_ajo.reset.assert_not_called()


long_test_cases = [
    (True, True, True),
    (True, True, False),
    (False, False, False),
]


@pytest.mark.parametrize("is_mod, set_long_called, is_long", long_test_cases)
def test_process_long(
    mock_comment,
    mock_ajo,
    mock_submission,
    mock_config,
    is_mod,
    set_long_called,
    is_long,
):
    mock_config.is_mod.return_value = is_mod
    mock_ajo.is_long = is_long

    processor = ZiwenCommandProcessor(
        "",
        "",
        mock_comment,
        "",
        "",
        "",
        "",
        mock_ajo,
        mock_submission,
        0,
        0,
        "",
        "",
        "",
        mock_config,
    )

    processor.process_long()

    if set_long_called:
        mock_ajo.set_long.assert_called_once_with(not is_long)
    else:
        mock_ajo.set_long.assert_not_called()


def test_process_missing(mock_comment, mock_ajo, mock_submission, mock_config):
    with patch("code.Ziwen_command_processor.css_check") as mock_css_check:
        mock_css_check.return_value = True
        processor = ZiwenCommandProcessor(
            "",
            "",
            mock_comment,
            "",
            "",
            "",
            "",
            mock_ajo,
            mock_submission,
            "",
            0,
            "",
            "",
            "",
            mock_config,
        )
        processor.process_missing()
        # the changes are later pushed to reddit with `update_reddit`
        mock_ajo.set_status.assert_called_once_with("missing")


def test_process_doublecheck(mock_comment, mock_ajo, mock_submission, mock_config):
    mock_ajo.type = "single"
    processor = ZiwenCommandProcessor(
        "",
        "",
        mock_comment,
        "",
        "",
        "",
        "",
        mock_ajo,
        mock_submission,
        0,
        0,
        "",
        "",
        "",
        mock_config,
    )
    processor.process_doublecheck()
    # the changes are later pushed to reddit with `update_reddit`
    mock_ajo.set_status.assert_called_once_with("doublecheck")


def test_process_id(mock_comment, mock_ajo, mock_submission, mock_config):
    mock_ajo.type = "single"
    mock_ajo.status = ""
    with patch("code.Ziwen_command_processor.record_to_wiki") as notifier_patch:
        notifier_patch.return_value = []
        processor = ZiwenCommandProcessor(
            "!identify: chinese",
            "",
            mock_comment,
            "",
            "",
            "",
            "",
            mock_ajo,
            mock_submission,
            0,
            0,
            "",
            "",
            "",
            mock_config,
        )
        processor.process_id()
        # the changes are later pushed to reddit with `update_reddit`
        mock_ajo.set_language.assert_called_once_with("zh", True)


def test_process_claim(mock_comment, mock_ajo, mock_submission, mock_config):
    mock_ajo.language_name = ""
    processor = ZiwenCommandProcessor(
        "",
        "",
        mock_comment,
        "",
        "",
        "",
        "",
        mock_ajo,
        mock_submission,
        0,
        0,
        "",
        "",
        "",
        mock_config,
    )
    processor.process_claim()
    # the changes are later pushed to reddit with `update_reddit`
    mock_ajo.set_status.assert_called_once_with("inprogress")
