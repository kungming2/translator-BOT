import re
from code.zh_processing import ZhProcessor


def test_init():
    ZhProcessor({})


def test_zh_character():
    out = ZhProcessor({}).zh_character("你")
    # after quote_code there is a random hash, so get rid of it
    modified_out = re.sub(r"quote_code=.*?\)", "quote_code=)", out)
    print(repr(modified_out))
    assert modified_out in [
        '# [你](https://en.wiktionary.org/wiki/你#Chinese)\n\nLanguage | Pronunciation\n---------|--------------\n**Mandarin** | *nǐ*\n**Cantonese** | *nei^(5)*\n**Southern Min** | *lí*\n**Hakka (Sixian)** | *n^(11)*\n\n**Chinese Calligraphy Variants**: [你](https://wxapp.shufazidian.com/shufa6/55da59052b21471ce7f1652afd24f5016.jpg) (*[SFZD](http://www.shufazidian.com/)*, *[SFDS](http://www.sfds.cn/4F60/)*, *[YTZZD](https://dict.variants.moe.edu.tw/variants/rbt/word_attribute.rbt?quote_code=)*)\n\n**Meanings**: "you, second person pronoun."\n\n\n^Information ^from [^(Unihan)](https://www.unicode.org/cgi-bin/GetUnihanData.pl?codepoint=你) ^| [^(CantoDict)](https://www.cantonese.sheik.co.uk/dictionary/characters/你/) ^| [^(Chinese Etymology)](https://hanziyuan.net/#你) ^| [^(CHISE)](https://www.chise.org/est/view/char/你) ^| [^(CTEXT)](https://ctext.org/dictionary.pl?if=en&char=你) ^| [^(MDBG)](https://www.mdbg.net/chinese/dictionary?page=worddict&wdrst=1&wdqb=你) ^| [^(MoE DICT)](https://www.moedict.tw/\'你) ^| [^(MFCCD)](https://humanum.arts.cuhk.edu.hk/Lexis/lexi-mf/search.php?word=你)',
        '# [你](https://en.wiktionary.org/wiki/你#Chinese)\n\nLanguage | Pronunciation\n---------|--------------\n**Mandarin** | *nǐ*\n**Cantonese** | *nei^(5)*\n**Southern Min** | *lí*\n**Hakka (Sixian)** | *n^(11)*\n\n**Chinese Calligraphy Variants**: [你](https://wxapp.shufazidian.com/shufa6/55da59052b21471ce7f1652afd24f5016.jpg) (*[SFZD](http://www.shufazidian.com/)*, *[SFDS](http://www.sfds.cn/4F60/)*, *[YTZZD](https://dict.variants.moe.edu.tw/variants/rbt/query_by_standard_tiles.rbt?command=clear)*)\n\n**Meanings**: "you, second person pronoun."\n\n\n^Information ^from [^(Unihan)](https://www.unicode.org/cgi-bin/GetUnihanData.pl?codepoint=你) ^| [^(CantoDict)](https://www.cantonese.sheik.co.uk/dictionary/characters/你/) ^| [^(Chinese Etymology)](https://hanziyuan.net/#你) ^| [^(CHISE)](https://www.chise.org/est/view/char/你) ^| [^(CTEXT)](https://ctext.org/dictionary.pl?if=en&char=你) ^| [^(MDBG)](https://www.mdbg.net/chinese/dictionary?page=worddict&wdrst=1&wdqb=你) ^| [^(MoE DICT)](https://www.moedict.tw/\'你) ^| [^(MFCCD)](https://humanum.arts.cuhk.edu.hk/Lexis/lexi-mf/search.php?word=你)',
    ]


def test_zh_word():
    assert (
        ZhProcessor({}).zh_word("螃蟹")
        == '# [螃蟹](https://en.wiktionary.org/wiki/螃蟹#Chinese)\n\nLanguage | Pronunciation\n---------|--------------\n**Mandarin** (Pinyin) | *pángxiè*\n**Mandarin** (Wade-Giles) | *p\'ang^(2) hsieh^(4)*\n**Mandarin** (Yale) | *pang^(2) sye^(4)*\n**Cantonese** | *pong^(4)   haai^(5)*\n\n**Meanings**: "crab  / CL: 隻｜只."\n\n\n\n\n^Information ^from [^CantoDict](https://www.cantonese.sheik.co.uk/dictionary/search/?searchtype=1&text=螃蟹) ^| [^MDBG](https://www.mdbg.net/chinese/dictionary?page=worddict&wdrst=0&wdqb=c:螃蟹) ^| [^Yellowbridge](https://yellowbridge.com/chinese/dictionary.php?word=螃蟹) ^| [^Youdao](https://dict.youdao.com/w/eng/螃蟹/#keyfrom=dict2.index)'
    )
