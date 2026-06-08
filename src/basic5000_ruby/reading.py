from unicodedata import category


LONG_SOUND_MARK = "ー"
LONG_SOUND_VOWELS: dict[str, str] = {
    **dict.fromkeys("あかがさざただなはばぱまやらわぁゃゎ", "あ"),
    **dict.fromkeys("いきぎしじちぢにひびぴみりぃ", "い"),
    **dict.fromkeys("うくぐすずつづぬふぶぷむゆるゔぅゅ", "う"),
    **dict.fromkeys("えけげせぜてでねへべぺめれぇ", "い"),
    **dict.fromkeys("おこごそぞとどのほぼぽもよろをぉょ", "う"),
}


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

    replaced_characters: list[str] = []
    for character in text:
        if character != LONG_SOUND_MARK:
            replaced_characters.append(character)
            continue
        if len(replaced_characters) == 0:
            replaced_characters.append(character)
            continue
        previous_character = replaced_characters[-1]
        if previous_character not in LONG_SOUND_VOWELS:
            replaced_characters.append(character)
            continue
        replaced_characters.append(LONG_SOUND_VOWELS[previous_character])
    return "".join(replaced_characters)


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
