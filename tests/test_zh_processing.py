import re
from code.zh_processing import ZhProcessor


def test_init():
    ZhProcessor({})


def test_zh_character():
    out = ZhProcessor({}).zh_character("你")
    # after quote_code there is a random hash, so get rid of it
    modified_out = re.sub(r"quote_code=.*?\)", "quote_code=)", out)
    assert modified_out in [
        '# [你](https://en.wiktionary.org/wiki/你#Chinese)\n\nLanguage | Pronunciation\n---------|--------------\n**Mandarin** | *nǐ*\n**Cantonese** | *nei^(5)*\n**Southern Min** | *lí*\n**Hakka (Sixian)** | *n^(11)*\n\n**Chinese Calligraphy Variants**: [你](https://wxapp.shufazidian.com/shufa6/55da59052b21471ce7f1652afd24f5016.jpg) (*[SFZD](http://www.shufazidian.com/)*, *[SFDS](http://www.sfds.cn/4F60/)*, *[YTZZD](https://dict.variants.moe.edu.tw/variants/rbt/word_attribute.rbt?quote_code=)*)\n\n**Meanings**: "you, second person pronoun."\n\n\n^Information ^from [^(Unihan)](https://www.unicode.org/cgi-bin/GetUnihanData.pl?codepoint=你) ^| [^(CantoDict)](https://www.cantonese.sheik.co.uk/dictionary/characters/你/) ^| [^(Chinese Etymology)](https://hanziyuan.net/#你) ^| [^(CHISE)](https://www.chise.org/est/view/char/你) ^| [^(CTEXT)](https://ctext.org/dictionary.pl?if=en&char=你) ^| [^(MDBG)](https://www.mdbg.net/chinese/dictionary?page=worddict&wdrst=1&wdqb=你) ^| [^(MoE DICT)](https://www.moedict.tw/\'你) ^| [^(MFCCD)](https://humanum.arts.cuhk.edu.hk/Lexis/lexi-mf/search.php?word=你)',
        '# [你](https://en.wiktionary.org/wiki/你#Chinese)\n\nLanguage | Pronunciation\n---------|--------------\n**Mandarin** | *nǐ*\n**Cantonese** | *nei^(5)*\n**Southern Min** | *lí*\n**Hakka (Sixian)** | *n^(11)*\n\n**Chinese Calligraphy Variants**: [你](https://wxapp.shufazidian.com/shufa6/55da59052b21471ce7f1652afd24f5016.jpg) (*[SFZD](http://www.shufazidian.com/)*, *[SFDS](http://www.sfds.cn/4F60/)*, *[YTZZD](https://dict.variants.moe.edu.tw/variants/rbt/query_by_standard_tiles.rbt?command=clear)*)\n\n**Meanings**: "you, second person pronoun."\n\n\n^Information ^from [^(Unihan)](https://www.unicode.org/cgi-bin/GetUnihanData.pl?codepoint=你) ^| [^(CantoDict)](https://www.cantonese.sheik.co.uk/dictionary/characters/你/) ^| [^(Chinese Etymology)](https://hanziyuan.net/#你) ^| [^(CHISE)](https://www.chise.org/est/view/char/你) ^| [^(CTEXT)](https://ctext.org/dictionary.pl?if=en&char=你) ^| [^(MDBG)](https://www.mdbg.net/chinese/dictionary?page=worddict&wdrst=1&wdqb=你) ^| [^(MoE DICT)](https://www.moedict.tw/\'你) ^| [^(MFCCD)](https://humanum.arts.cuhk.edu.hk/Lexis/lexi-mf/search.php?word=你)',
    ]


def test_zh_word1():
    assert (
        ZhProcessor({}).zh_word("螃蟹")
        == '# [螃蟹](https://en.wiktionary.org/wiki/螃蟹#Chinese)\n\nLanguage | Pronunciation\n---------|--------------\n**Mandarin** (Pinyin) | *pángxiè*\n**Mandarin** (Wade-Giles) | *p\'ang^(2) hsieh^(4)*\n**Mandarin** (Yale) | *pang^(2) sye^(4)*\n**Cantonese** | *pong^(4)   haai^(5)*\n\n**Meanings**: "crab  / CL: 隻｜只."\n\n\n\n\n^Information ^from [^CantoDict](https://www.cantonese.sheik.co.uk/dictionary/search/?searchtype=1&text=螃蟹) ^| [^MDBG](https://www.mdbg.net/chinese/dictionary?page=worddict&wdrst=0&wdqb=c:螃蟹) ^| [^Yellowbridge](https://yellowbridge.com/chinese/dictionary.php?word=螃蟹) ^| [^Youdao](https://dict.youdao.com/w/eng/螃蟹/#keyfrom=dict2.index)'
    )


def test_zh_word2():
    assert (
        ZhProcessor({}).zh_word("佛陀")
        == '# [佛陀](https://en.wiktionary.org/wiki/佛陀#Chinese)\n\nLanguage | Pronunciation\n---------|--------------\n**Mandarin** (Pinyin) | *Fótuó*\n**Mandarin** (Wade-Giles) | *fo^(2) t\'o^(2)*\n**Mandarin** (Yale) | *fwo^(2) two^(2)*\n**Cantonese** | *fat^(6)   to^(4)*\n\n**Meanings**: "Buddha (a person who has attained Buddhahood, or specifically Siddhartha Gautama)."\n\n**Buddhist Meanings**: "v. 佛 There are numerous monks from India and Central Asia bearing this as part of their names." ([Soothill-Hodous](https://mahajana.net/en/library/texts/a-dictionary-of-chinese-buddhist-terms))\n\n\n\n\n^Information ^from [^CantoDict](https://www.cantonese.sheik.co.uk/dictionary/search/?searchtype=1&text=佛陀) ^| [^MDBG](https://www.mdbg.net/chinese/dictionary?page=worddict&wdrst=0&wdqb=c:佛陀) ^| [^Yellowbridge](https://yellowbridge.com/chinese/dictionary.php?word=佛陀) ^| [^Youdao](https://dict.youdao.com/w/eng/佛陀/#keyfrom=dict2.index)'
    )


def test_zh_word3():
    assert (
        ZhProcessor({}).zh_word("为所欲为")
        == '# [為所欲為 (为所欲为)](https://en.wiktionary.org/wiki/為所欲為#Chinese)\n\nLanguage | Pronunciation\n---------|--------------\n**Mandarin** (Pinyin) | *wéisuǒyùwéi*\n**Mandarin** (Wade-Giles) | *wei^(2) so^(3) yü^(4) wei^(2)*\n**Mandarin** (Yale) | *wei^(2) swo^(3) yu^(4) wei^(2)*\n**Cantonese** | *wai^(4)   so^(2)   juk^(6)   wai^(4)*\n\n**Meanings**: "to do whatever one pleases."\n\n**Chinese Meaning**: 为：做。本指做自己想做的事。后指想干什么就干什么。\n\n**Literary Source**: 宋・司马光《资治通鉴・周威烈王二十三年》：“以子之才，臣事赵孟，必得近幸。子乃为所欲为，顾不易耶？” ([5156edu](http://cy.51bc.net/html4/11194.html), [18Dao](https://tw.18dao.net/成語詞典/為所欲為))\n\n\n\n\n^Information ^from [^CantoDict](https://www.cantonese.sheik.co.uk/dictionary/search/?searchtype=1&text=为所欲为) ^| [^MDBG](https://www.mdbg.net/chinese/dictionary?page=worddict&wdrst=0&wdqb=c:为所欲为) ^| [^Yellowbridge](https://yellowbridge.com/chinese/dictionary.php?word=为所欲为) ^| [^Youdao](https://dict.youdao.com/w/eng/为所欲为/#keyfrom=dict2.index)'
    )
