from unicodedata import category


NOBASHI_REPLACEMENTS = (
    ("あー", "ああ"),
    ("かー", "かあ"),
    ("がー", "があ"),
    ("さー", "さあ"),
    ("ざー", "ざあ"),
    ("たー", "たあ"),
    ("だー", "だあ"),
    ("なー", "なあ"),
    ("はー", "はあ"),
    ("ばー", "ばあ"),
    ("ぱー", "ぱあ"),
    ("まー", "まあ"),
    ("やー", "やあ"),
    ("らー", "らあ"),
    ("きゃー", "きゃあ"),
    ("ぎゃー", "ぎゃあ"),
    ("しゃー", "しゃあ"),
    ("じゃー", "じゃあ"),
    ("ちゃー", "ちゃあ"),
    ("ぢゃー", "ぢゃあ"),
    ("にゃー", "にゃあ"),
    ("ひゃー", "ひゃあ"),
    ("びゃー", "びゃあ"),
    ("ぴゃー", "ぴゃあ"),
    ("みゃー", "みゃあ"),
    ("りゃー", "りゃあ"),
    ("いー", "いい"),
    ("きー", "きい"),
    ("ぎー", "ぎい"),
    ("しー", "しい"),
    ("じー", "じい"),
    ("ちー", "ちい"),
    ("ぢー", "ぢい"),
    ("にー", "にい"),
    ("ひー", "ひい"),
    ("びー", "びい"),
    ("ぴー", "ぴい"),
    ("みー", "みい"),
    ("りー", "りい"),
    ("うー", "うう"),
    ("くー", "くう"),
    ("ぐー", "ぐう"),
    ("しー", "しう"),
    ("じー", "じう"),
    ("つー", "つう"),
    ("づー", "づう"),
    ("ぬー", "ぬう"),
    ("ふー", "ふう"),
    ("ぶー", "ぶう"),
    ("ぷー", "ぷう"),
    ("むー", "むう"),
    ("ゆー", "ゆう"),
    ("るー", "るう"),
    ("きゅー", "きゅう"),
    ("ぎゅー", "ぎゅう"),
    ("しゅー", "しゅう"),
    ("じゅー", "じゅう"),
    ("ちゅー", "ちゅう"),
    ("ぢゅー", "ぢゅう"),
    ("にゅー", "にゅう"),
    ("ひゅー", "ひゅう"),
    ("びゅー", "びゅう"),
    ("ぴゅー", "ぴゅう"),
    ("みゅー", "みゅう"),
    ("りゅー", "りゅう"),
    ("えー", "えい"),
    ("けー", "けい"),
    ("げー", "げい"),
    ("せー", "せい"),
    ("ぜー", "ぜい"),
    ("てー", "てい"),
    ("でー", "でい"),
    ("ねー", "ねい"),
    ("へー", "へい"),
    ("べー", "べい"),
    ("ぺー", "ぺい"),
    ("めー", "めい"),
    ("れー", "れい"),
    ("おー", "おう"),
    ("こー", "こう"),
    ("ごー", "ごう"),
    ("そー", "そう"),
    ("ぞー", "ぞう"),
    ("とー", "とう"),
    ("どー", "どう"),
    ("のー", "のう"),
    ("ほー", "ほう"),
    ("ぼー", "ぼう"),
    ("ぽー", "ぽう"),
    ("もー", "もう"),
    ("よー", "よう"),
    ("ろー", "ろう"),
    ("きょー", "きょう"),
    ("ぎょー", "ぎょう"),
    ("しょー", "しょう"),
    ("じょー", "じょう"),
    ("ちょー", "ちょう"),
    ("ぢょー", "ぢょう"),
    ("にょー", "にょう"),
    ("ひょー", "ひょう"),
    ("びょー", "びょう"),
    ("ぴょー", "ぴょう"),
    ("みょー", "みょう"),
    ("りょー", "りょう"),
)


def katakana_to_hiragana(text: str) -> str:
    """カタカナを平仮名に変換する。"""

    converted_characters: list[str] = []
    for character in text:
        codepoint = ord(character)
        if 0x30A1 <= codepoint <= 0x30F6:
            converted_characters.append(chr(codepoint - 0x60))
        elif character == "ヷ":
            converted_characters.append("ゔぁ")
        elif character == "ヸ":
            converted_characters.append("ゔぃ")
        elif character == "ヹ":
            converted_characters.append("ゔぇ")
        elif character == "ヺ":
            converted_characters.append("ゔぉ")
        else:
            converted_characters.append(character)
    return "".join(converted_characters)


def replace_nobashi(text: str) -> str:
    """長音記号を読みやすい平仮名に戻す。"""

    replaced_text = text
    for before, after in NOBASHI_REPLACEMENTS:
        replaced_text = replaced_text.replace(before, after)
    return replaced_text


def normalize_segment_reading(surface: str, reading: str) -> str:
    """表層文字列に合わせて読みを平仮名へ正規化する。"""

    if len(surface) == 0:
        raise ValueError("表層文字列が空です。")

    normalized_reading = replace_nobashi(katakana_to_hiragana(reading))
    first_character = surface[0]
    if normalized_reading.startswith("おう") and first_character in {"多", "大", "覆"}:
        normalized_reading = f"おお{normalized_reading[2:]}"
    if normalized_reading.startswith("とう") and first_character == "通":
        normalized_reading = f"とお{normalized_reading[2:]}"
    return normalized_reading


def has_ruby_target(text: str) -> bool:
    """ルビを付ける対象文字を含むか判定する。"""

    for character in text:
        if is_ruby_target_character(character):
            return True
    return False


def is_ruby_target_character(character: str) -> bool:
    """漢字相当文字、数字、アルファベットか判定する。"""

    return is_kanji(character) or character in {"々", "ヶ"} or is_digit(character) or is_latin(character)


def is_kanji(character: str) -> bool:
    """漢字か判定する。"""

    codepoint = ord(character)
    return (
        0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0xF900 <= codepoint <= 0xFAFF
        or 0x20000 <= codepoint <= 0x2EBEF
    )


def is_digit(character: str) -> bool:
    """数字か判定する。"""

    return category(character) == "Nd"


def is_latin(character: str) -> bool:
    """ラテン文字か判定する。"""

    codepoint = ord(character)
    return 0x0041 <= codepoint <= 0x005A or 0x0061 <= codepoint <= 0x007A or 0xFF21 <= codepoint <= 0xFF3A or 0xFF41 <= codepoint <= 0xFF5A
