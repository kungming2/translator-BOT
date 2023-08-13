from code._languages import (
    bad_title_reformat,
    convert,
    ConverterTuple,
    country_converter,
    language_list_splitter,
    main_posts_filter,
    title_format,
    TitleTuple,
)


def test_converter1():
    assert convert("English") == ConverterTuple(
        language_code="en", language_name="English", supported=False, country_code=None
    )


def test_converter2():
    assert convert("unknown-bopo") == ConverterTuple(
        language_code="bopo",
        language_name="Bopomofo",
        supported=False,
        country_code=None,
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


def test_title_format3():
    assert title_format(
        "[eng > zh, German, French] my friend sent this to me"
    ) == TitleTuple(
        source_languages=["English"],
        target_languages=["Chinese", "French", "German"],
        final_css="multiple",
        final_css_text="Multiple Languages [DE, FR, ZH]",
        actual_title="my friend sent this to me",
        processed_title="[eng > zh, German, French] my friend sent this to me",
        notify_languages=["Chinese", "French", "German"],
        language_country=None,
        direction="english_from",
    )


def test_title_format4():
    assert title_format("my friend sent this chinese to me") == TitleTuple(
        source_languages=["Chinese"],
        target_languages=["Generic"],
        final_css="zh",
        final_css_text="Chinese",
        actual_title="",
        processed_title="my friend sent this chinese to me",
        notify_languages=["Chinese", "Generic"],
        language_country=None,
        direction="english_none",
    )


def test_title_format_no_language():
    assert title_format("my friend sent this to me") == TitleTuple(
        source_languages=["Generic"],
        target_languages=["Generic"],
        final_css="generic",
        final_css_text="Generic",
        actual_title="",
        processed_title="my friend sent this to me",
        notify_languages=None,
        language_country=None,
        direction="english_none",
    )


# bad title
def test_main_posts_filter_bad_title1():
    assert main_posts_filter("hello") == (False, None, "1")


# good title
def test_main_posts_filter_bad_title2():
    test_str = "[eng > zh] hi"
    assert main_posts_filter(test_str) == (True, test_str, None)


def test_main_posts_filter_bad_title3():
    assert main_posts_filter("[eng to zh] hi") == (True, "[eng to zh] hi", None)


def test_main_posts_filter_bad_title4():
    assert main_posts_filter("translation to english") == (False, None, "1B")


def test_country_converter1():
    assert country_converter("china") == ("CN", "China")


def test_country_converter2():
    assert country_converter("cn") == ("CN", "China")


def test_country_converter3():
    assert country_converter("cn", False) == ("", "")


def test_bad_title_reformat():
    assert (
        "[Unknown > English] Hello need help to translate this"
        == bad_title_reformat("Hello need help to translate this")
    )


def test_language_list_splitter():
    assert ["ko", "zh"] == language_list_splitter("ko+zh")
