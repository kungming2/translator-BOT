from code._languages import (
    convert,
    ConverterTuple,
    main_posts_filter,
    title_format,
    TitleTuple,
)


def test_converter():
    assert convert("English") == ConverterTuple(
        language_code="en", language_name="English", supported=False, country_code=None
    )


def test_title_format1():
    assert title_format("[English < Chinese] my friend sent this to me") == TitleTuple(
        source_languages=["English"],
        target_languages=["Chinese"],
        final_css="zh",
        final_css_text="Chinese",
        actual_title="my friend sent this to me",
        processed_title="[English  >  Chinese] my friend sent this to me",
        notify_languages=None,
        language_country=None,
        direction="english_from",
    )


def test_title_format2():
    assert title_format("[eng > zh] my friend sent this to me") == TitleTuple(
        source_languages=["English"],
        target_languages=["Chinese"],
        final_css="zh",
        final_css_text="Chinese",
        actual_title="my friend sent this to me",
        processed_title="[eng > zh] my friend sent this to me",
        notify_languages=None,
        language_country=None,
        direction="english_from",
    )


# bad title
def test_main_posts_filter_bad_title1():
    assert main_posts_filter("hello") == (False, None, "1")


# good title
def test_main_posts_filter_bad_title2():
    test_str = "[eng > zh] hi"
    assert main_posts_filter(test_str) == (True, test_str, None)
