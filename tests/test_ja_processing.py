import re
from code.ja_processing import JapaneseProcessor


def test_init():
    JapaneseProcessor({})


def test_ja_character():
    out = JapaneseProcessor({}).ja_character("街")
    # after quote_code there is a random hash, so get rid of it
    modified_out = re.sub(r"quote_code=.*?\)", "quote_code=)", out)

    assert modified_out in [
        '# [街](https://en.wiktionary.org/wiki/街#Japanese)\n\n**Kun-readings:** まち (*machi*)\n\n**On-readings:** ガイ (*gai*), カイ (*kai*)\n\n**Chinese Calligraphy Variants**: [街](https://wxapp.shufazidian.com/shufa6/s9b100bd534df46ef67d1d106fade55ce.jpg) (*[SFZD](http://www.shufazidian.com/)*, *[SFDS](http://www.sfds.cn/8857/)*, *[YTZZD](https://dict.variants.moe.edu.tw/variants/rbt/word_attribute.rbt?quote_code=)*)\n\n**Meanings**: "boulevard, street, town."\n\n^Information ^from [^(Jisho)](https://jisho.org/search/街%20%23kanji) ^| [^(Goo Dictionary)](https://dictionary.goo.ne.jp/word/en/街) ^| [^(Tangorin)](https://tangorin.com/kanji/街) ^| [^(Weblio EJJE)](https://ejje.weblio.jp/content/街)',
        '# [街](https://en.wiktionary.org/wiki/街#Japanese)\n\n**Kun-readings:** まち (*machi*)\n\n**On-readings:** ガイ (*gai*), カイ (*kai*)\n\n**Chinese Calligraphy Variants**: [街](https://wxapp.shufazidian.com/shufa6/s9b100bd534df46ef67d1d106fade55ce.jpg) (*[SFZD](http://www.shufazidian.com/)*, *[SFDS](http://www.sfds.cn/8857/)*, *[YTZZD](https://dict.variants.moe.edu.tw/variants/rbt/query_by_standard_tiles.rbt?command=clear)*)\n\n**Meanings**: "boulevard, street, town."\n\n^Information ^from [^(Jisho)](https://jisho.org/search/街%20%23kanji) ^| [^(Goo Dictionary)](https://dictionary.goo.ne.jp/word/en/街) ^| [^(Tangorin)](https://tangorin.com/kanji/街) ^| [^(Weblio EJJE)](https://ejje.weblio.jp/content/街)',
    ]


def test_ja_word():
    assert (
        JapaneseProcessor({}).ja_word("病気")
        == "# [病気](https://en.wiktionary.org/wiki/病気#Japanese)\n\n##### *Noun, Noun which may take the genitive case particle 'no'*\n\n**Reading:** びょうき (*byouki*)\n\n**Meanings**: \"illness (usu. excluding minor ailments, e.g. common cold), disease, sickness.\"\n\n^Information ^from ^[Jisho](https://jisho.org/search/病気%23words) ^| [^Kotobank](https://kotobank.jp/word/病気) ^| [^Tangorin](https://tangorin.com/general/病気) ^| [^(Weblio EJJE)](https://ejje.weblio.jp/content/病気)"
    )
