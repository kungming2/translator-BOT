import random
from code._config import get_random_useragent


def test_get_random_useragent():
    random.seed(42)
    assert (
        get_random_useragent()["User-Agent"]
        == "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.131 Safari/537.36"
    )
