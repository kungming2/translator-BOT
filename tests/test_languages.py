from code._languages import convert, ConverterTuple


def test_converter():
    assert convert("English") == ConverterTuple(
        language_code="en", language_name="English", supported=False, country_code=None
    )
