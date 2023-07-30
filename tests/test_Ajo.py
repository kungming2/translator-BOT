from code.Ajo import Ajo
from unittest.mock import MagicMock
import praw


def test_init():
    reddit_submission = MagicMock(praw.reddit.models.Submission)
    reddit_submission.id = "123"
    reddit_submission.created_utc = 1.0
    reddit_submission.title = "hello"
    reddit_submission.link_flair_css_class = ""
    reddit_submission.link_flair_text = ""
    Ajo(reddit_submission, {})
