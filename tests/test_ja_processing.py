import re
from code.ja_processing import JapaneseProcessor


headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
}


def test_init():
    JapaneseProcessor(headers)


def test_ja_character():
    out = JapaneseProcessor(headers).ja_character("街")
    # after quote_code there is a random hash, so get rid of it
    modified_out = re.sub(r"quote_code=.*?\)", "quote_code=)", out)

    assert modified_out in [
        '# [街](https://en.wiktionary.org/wiki/街#Japanese)\n\n**Kun-readings:** まち (*machi*)\n\n**On-readings:** ガイ (*gai*), カイ (*kai*)\n\n**Chinese Calligraphy Variants**: [街](https://wxapp.shufazidian.com/shufa6/s9b100bd534df46ef67d1d106fade55ce.jpg) (*[SFZD](http://www.shufazidian.com/)*, *[SFDS](http://www.sfds.cn/8857/)*, *[YTZZD](https://dict.variants.moe.edu.tw/variants/rbt/word_attribute.rbt?quote_code=)*)\n\n**Meanings**: "boulevard, street, town."\n\n^Information ^from [^(Jisho)](https://jisho.org/search/街%20%23kanji) ^| [^(Goo Dictionary)](https://dictionary.goo.ne.jp/word/en/街) ^| [^(Tangorin)](https://tangorin.com/kanji/街) ^| [^(Weblio EJJE)](https://ejje.weblio.jp/content/街)',
        '# [街](https://en.wiktionary.org/wiki/街#Japanese)\n\n**Kun-readings:** まち (*machi*)\n\n**On-readings:** ガイ (*gai*), カイ (*kai*)\n\n**Chinese Calligraphy Variants**: [街](https://wxapp.shufazidian.com/shufa6/s9b100bd534df46ef67d1d106fade55ce.jpg) (*[SFZD](http://www.shufazidian.com/)*, *[SFDS](http://www.sfds.cn/8857/)*, *[YTZZD](https://dict.variants.moe.edu.tw/variants/rbt/query_by_standard_tiles.rbt?command=clear)*)\n\n**Meanings**: "boulevard, street, town."\n\n^Information ^from [^(Jisho)](https://jisho.org/search/街%20%23kanji) ^| [^(Goo Dictionary)](https://dictionary.goo.ne.jp/word/en/街) ^| [^(Tangorin)](https://tangorin.com/kanji/街) ^| [^(Weblio EJJE)](https://ejje.weblio.jp/content/街)',
    ]


def test_multiple_ja_characters():
    assert (
        JapaneseProcessor(headers).ja_character("中川")
        == '# 中川\n\nCharacter  | [中](https://en.wiktionary.org/wiki/中#Japanese) | [川](https://en.wiktionary.org/wiki/川#Japanese)\n---|---|---|\n**Kun-readings** | なか (*naka*), うち (*uchi*), あた.る (*ata.ru*) | かわ (*kawa*)\n**On-readings**  | チュウ (*chuu*) | セン (*sen*)\n**Meanings**  | "in, inside, middle, mean, center." | "stream, river, river or three-stroke river radical (no. 47)."\n\n^Information ^from [^(Jisho)](https://jisho.org/search/中川%20%23kanji) ^| [^(Goo Dictionary)](https://dictionary.goo.ne.jp/word/en/中川) ^| [^(Tangorin)](https://tangorin.com/kanji/中川) ^| [^(Weblio EJJE)](https://ejje.weblio.jp/content/中川)'
    )


def test_ja_word():
    assert (
        JapaneseProcessor(headers).ja_word("病気")
        == "# [病気](https://en.wiktionary.org/wiki/病気#Japanese)\n\n##### *Noun, Noun which may take the genitive case particle 'no'*\n\n**Reading:** びょうき (*byouki*)\n\n**Meanings**: \"illness (usu. excluding minor ailments, e.g. common cold), disease, sickness.\"\n\n^Information ^from ^[Jisho](https://jisho.org/search/病気%23words) ^| [^Kotobank](https://kotobank.jp/word/病気) ^| [^Tangorin](https://tangorin.com/general/病気) ^| [^(Weblio EJJE)](https://ejje.weblio.jp/content/病気)"
    )


def test_ja_sound():
    assert (
        JapaneseProcessor(headers).ja_word("トプトプ")
        == "# [トプトプ](https://en.wiktionary.org/wiki/トプトプ#Japanese)\n\n##### *Sound effect*\n\n**Reading:** トプトプ (*toputopu*)\n\n**English Equivalent**: \\*pour\\*\n\n**Explanation**: SFX for pouring something liquid. \n\n\n^Information ^from [^SFX ^Dictionary](http://thejadednetwork.com/sfx/browse/topu_topu/)"
    )


def test_surname():
    assert (
        JapaneseProcessor(headers).ja_word("穂村")
        == "# [穂村](https://en.wiktionary.org/wiki/穂村#Japanese)\n\n**Readings:** ほむら (*homura*)\n\n**Meanings**: A Japanese surname.\n\n\n\n^Information ^from [^Myoji](https://myoji-yurai.net/searchResult.htm?myojiKanji=穂村) ^| [^Weblio ^EJJE](https://ejje.weblio.jp/content/穂村)"
    )
