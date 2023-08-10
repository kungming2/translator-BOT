import time
from unittest.mock import MagicMock, patch
import praw
from code.Ziwen import edit_comment_processor, points_tabulator


@patch("code.Ziwen.config")
def test_points_tabulator(mocked_config_instance):
    mocked_config_instance.points_worth_determiner.return_value = 1

    comment = MagicMock(spec=praw.reddit.models.Comment)
    comment.id = "123"
    comment.author = MagicMock()
    comment.author.name = "author"
    comment.body = "!identify: chinese"
    points_tabulator("oid", "oauthor", "flair text", "css", comment)

    mocked_config_instance.cursor_main.execute.assert_called_with(
        "INSERT INTO total_points VALUES (?, ?, ?, ?, ?)",
        ("2023-08", "123", "author", "3", "oid"),
    )


@patch("code.Ziwen.config")
def test_edit_comment_processor(mocked_config_instance):
    comment = MagicMock(spec=praw.reddit.models.Comment)
    comment.body = "body"
    comment.id = "123"
    comment.edited = True
    comment.created_utc = time.time() - 5
    edit_comment_processor(comment)
    mocked_config_instance.cursor_cache.execute.assert_called_with(
        "INSERT INTO comment_cache VALUES (?, ?)", ("123", "body")
    )
