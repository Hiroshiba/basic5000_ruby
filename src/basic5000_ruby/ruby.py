from dataclasses import dataclass
from difflib import SequenceMatcher

import pyopenjtalk

from basic5000_ruby.data import Sentence
from basic5000_ruby.reading import (
    has_ruby_target,
    is_ruby_target_character,
    katakana_to_hiragana,
    normalize_segment_reading,
    replace_nobashi,
)


READING_ONLY_PUNCTUATIONS = {"、", "。", "，", "．"}
LONG_SOUND_MARK = "ー"
LONG_SOUND_REPLACEMENT_CHARACTERS = {"あ", "い", "う", "え", "お"}


@dataclass(frozen=True)
class PlainPart:
    """ルビを付けない本文部分を表す。"""

    text: str
    reading: str


@dataclass(frozen=True)
class RubyPart:
    """ルビを付ける本文部分を表す。"""

    text: str
    reading: str


@dataclass(frozen=True)
class RubySentence:
    """ルビ生成済みの1文を表す。"""

    identifier: str
    number: int
    text: str
    reading: str
    parts: tuple[PlainPart | RubyPart, ...]


@dataclass(frozen=True)
class _FrontendToken:
    surface: str
    reading: str
    helper_start: int
    helper_end: int


@dataclass(frozen=True)
class _RawFrontendToken:
    frontend_surface: str
    reading: str
    surface_start: int
    surface_end: int
    helper_start: int
    helper_end: int


@dataclass(frozen=True)
class _ReadingToken:
    surface: str
    raw_reading: str


# NOTE: jsut_hiho の読みが本文表記と食い違う2件だけ、本文を変えずにJSUT読みを優先する。
READING_PART_EXCEPTIONS: dict[tuple[str, str], tuple[PlainPart | RubyPart, ...]] = {
    # NOTE: basic5000.txt は「汚らわしい」に対して「けがわらしー」としており、「らわ」と「わら」が一致しない。
    ("汚らわしい", "けがわらしい"): (
        RubyPart(text="汚", reading="けが"),
        PlainPart(text="らわしい", reading="わらしい"),
    ),
    # NOTE: basic5000.txt は「儲ける」に対して「もーけた」としており、活用形が本文と一致しない。
    ("儲ける", "もうけた"): (
        RubyPart(text="儲", reading="もう"),
        PlainPart(text="ける", reading="けた"),
    ),
}


@dataclass(frozen=True)
class _AlignedPart:
    text: str
    raw_reading: str
    is_ruby: bool
    cost: int


def generate_all_sentences(sentences: list[Sentence]) -> list[RubySentence]:
    """BASIC5000全体のルビを生成する。"""

    return [generate_sentence(sentence) for sentence in sentences]


def generate_sentence(sentence: Sentence) -> RubySentence:
    """1文のルビを生成する。"""

    frontend_tokens = _run_frontend(sentence.text)
    reading_tokens = _assign_readings(sentence, frontend_tokens)

    parts: list[PlainPart | RubyPart] = []
    for token in reading_tokens:
        parts.extend(_create_parts(token.surface, token.raw_reading))

    text = "".join(part.text for part in parts)
    if text != sentence.text:
        raise ValueError(f"{sentence.identifier} の本文復元結果がtext_level2と一致しません。")

    reading = "".join(part.reading for part in parts)
    return RubySentence(
        identifier=sentence.identifier,
        number=sentence.number,
        text=sentence.text,
        reading=reading,
        parts=tuple(parts),
    )


def _run_frontend(text: str) -> list[_FrontendToken]:
    frontend_results = pyopenjtalk.run_frontend(text)
    raw_tokens: list[_RawFrontendToken] = []
    surface_position = 0
    helper_position = 0

    for result in frontend_results:
        frontend_surface = _require_frontend_field(result, "string")
        pron = _require_frontend_field(result, "pron")
        reading = _frontend_reading(frontend_surface, pron)
        raw_tokens.append(
            _RawFrontendToken(
                frontend_surface=frontend_surface,
                reading=reading,
                surface_start=surface_position,
                surface_end=surface_position + len(frontend_surface),
                helper_start=helper_position,
                helper_end=helper_position + len(reading),
            )
        )
        surface_position += len(frontend_surface)
        helper_position += len(reading)

    frontend_text = "".join(token.frontend_surface for token in raw_tokens)
    matcher = SequenceMatcher(None, frontend_text, text, autojunk=False)
    opcodes = matcher.get_opcodes()
    tokens = _assign_surfaces(text, raw_tokens, opcodes)

    restored_text = "".join(token.surface for token in tokens)
    if restored_text != text:
        raise ValueError(f"pyopenjtalkの表層文字列を本文へ対応付けできません。本文は {text} です。")

    return tokens


def _assign_surfaces(
    text: str,
    raw_tokens: list[_RawFrontendToken],
    opcodes: list[tuple[str, int, int, int, int]],
) -> list[_FrontendToken]:
    tokens: list[_FrontendToken] = []
    token_groups = _surface_token_groups(raw_tokens, opcodes)

    for token_group in token_groups:
        group_start = token_group[0].surface_start
        group_end = token_group[-1].surface_end
        text_start, text_end = _target_range_for_helper_range("本文", opcodes, group_start, group_end)
        surface = text[text_start:text_end]
        if len(surface) == 0:
            raise ValueError("pyopenjtalkの表層文字列を本文へ対応付けできません。")
        tokens.append(
            _FrontendToken(
                surface=surface,
                reading="".join(token.reading for token in token_group),
                helper_start=token_group[0].helper_start,
                helper_end=token_group[-1].helper_end,
            )
        )

    return tokens


def _surface_token_groups(
    raw_tokens: list[_RawFrontendToken],
    opcodes: list[tuple[str, int, int, int, int]],
) -> list[list[_RawFrontendToken]]:
    group_ranges: list[tuple[int, int]] = []

    for tag, helper_start, helper_end, _text_start, _text_end in opcodes:
        if tag == "equal":
            continue
        if tag == "delete":
            token_indexes = _overlapping_surface_token_indexes(raw_tokens, helper_start, helper_end)
            if len(token_indexes) == 0:
                raise ValueError("本文へ対応しないpyopenjtalk形態素がありません。")
            range_start = max(0, token_indexes[0] - 1)
            range_end = min(len(raw_tokens), token_indexes[-1] + 2)
            if range_start == token_indexes[0] and range_end == token_indexes[-1] + 1:
                raise ValueError("pyopenjtalkの表層文字列に本文へ対応しない孤立範囲があります。")
            group_ranges.append((range_start, range_end))
            continue
        if tag == "insert":
            token_index = _surface_insertion_token_index(raw_tokens, helper_start)
            group_ranges.append((token_index, token_index + 1))
            continue
        if tag != "replace":
            raise ValueError(f"本文差分に未知の種別 {tag} があります。")

        token_indexes = _overlapping_surface_token_indexes(raw_tokens, helper_start, helper_end)
        if len(token_indexes) == 0:
            raise ValueError("本文差分を対応付けるpyopenjtalk形態素がありません。")
        if len(token_indexes) > 1:
            group_ranges.append((token_indexes[0], token_indexes[-1] + 1))

    merged_ranges = _merge_ranges(group_ranges)
    groups: list[list[_RawFrontendToken]] = []
    token_index = 0
    range_index = 0
    while token_index < len(raw_tokens):
        if range_index < len(merged_ranges) and token_index == merged_ranges[range_index][0]:
            range_start, range_end = merged_ranges[range_index]
            groups.append(raw_tokens[range_start:range_end])
            token_index = range_end
            range_index += 1
        else:
            groups.append([raw_tokens[token_index]])
            token_index += 1
    return groups


def _overlapping_surface_token_indexes(
    raw_tokens: list[_RawFrontendToken],
    helper_start: int,
    helper_end: int,
) -> list[int]:
    return [
        token_index
        for token_index, token in enumerate(raw_tokens)
        if token.surface_start < helper_end and token.surface_end > helper_start
    ]


def _surface_insertion_token_index(raw_tokens: list[_RawFrontendToken], helper_start: int) -> int:
    for token_index, token in enumerate(raw_tokens):
        if token.surface_start <= helper_start < token.surface_end:
            return token_index
        if helper_start == token.surface_start:
            return token_index
    if helper_start == raw_tokens[-1].surface_end:
        return len(raw_tokens) - 1
    raise ValueError("本文の挿入差分を対応付けるpyopenjtalk形態素がありません。")


def _merge_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if len(ranges) == 0:
        return []

    sorted_ranges = sorted(ranges)
    merged_ranges = [sorted_ranges[0]]
    for range_start, range_end in sorted_ranges[1:]:
        previous_start, previous_end = merged_ranges[-1]
        if range_start <= previous_end:
            merged_ranges[-1] = (previous_start, max(previous_end, range_end))
        else:
            merged_ranges.append((range_start, range_end))
    return merged_ranges


def _require_frontend_field(result: dict[str, str], field_name: str) -> str:
    if field_name not in result:
        raise ValueError(f"pyopenjtalkの結果に {field_name} がありません。")
    value = result[field_name]
    if not isinstance(value, str):
        raise TypeError(f"pyopenjtalkの {field_name} が文字列ではありません。")
    return value


def _frontend_reading(surface: str, pron: str) -> str:
    if pron != "*":
        return katakana_to_hiragana(pron).replace("’", "")
    if has_ruby_target(surface):
        raise ValueError(f"{surface} の読みをpyopenjtalkから取得できません。")
    return katakana_to_hiragana(surface)


def _assign_readings(sentence: Sentence, frontend_tokens: list[_FrontendToken]) -> list[_ReadingToken]:
    raw_helper_reading = "".join(token.reading for token in frontend_tokens)
    helper_reading = replace_nobashi(raw_helper_reading)
    target_reading = _normalize_target_reading(raw_helper_reading, sentence.kana)
    matcher = SequenceMatcher(None, helper_reading, target_reading, autojunk=False)
    opcodes = matcher.get_opcodes()
    token_groups = _reading_token_groups(frontend_tokens, opcodes, target_reading)

    reading_tokens: list[_ReadingToken] = []
    for token_group in token_groups:
        target_start, target_end = _target_range_for_helper_range(
            sentence.identifier,
            opcodes,
            token_group[0].helper_start,
            token_group[-1].helper_end,
        )
        reading_tokens.append(
            _ReadingToken(
                surface="".join(token.surface for token in token_group),
                raw_reading=target_reading[target_start:target_end],
            )
        )

    reading_tokens = _merge_empty_ruby_target_readings(reading_tokens)
    reading_tokens = _merge_unalignable_reading_tokens(reading_tokens)
    restored_reading = "".join(token.raw_reading for token in reading_tokens)
    if restored_reading != target_reading:
        raise ValueError(f"{sentence.identifier} の読み対応付けがkana_level3と一致しません。")
    return reading_tokens


def _normalize_target_reading(helper_reading: str, target_reading: str) -> str:
    helper_characters = _helper_characters_by_target_index(helper_reading, target_reading)
    reading_characters: list[str] = []
    for target_index, target_character in enumerate(target_reading):
        if target_character == LONG_SOUND_MARK:
            helper_character = helper_characters.get(target_index)
            if helper_character is not None and helper_character in LONG_SOUND_REPLACEMENT_CHARACTERS:
                reading_characters.append(helper_character)
                continue
        reading_characters.append(target_character)
    return replace_nobashi("".join(reading_characters))


def _helper_characters_by_target_index(helper_reading: str, target_reading: str) -> dict[int, str]:
    matcher = SequenceMatcher(None, helper_reading, target_reading, autojunk=False)
    helper_characters: dict[int, str] = {}
    for tag, helper_start, helper_end, target_start, target_end in matcher.get_opcodes():
        if tag == "equal" or tag == "replace":
            if helper_end - helper_start != target_end - target_start:
                continue
            for offset in range(helper_end - helper_start):
                helper_characters[target_start + offset] = helper_reading[helper_start + offset]
            continue
        if tag == "delete" or tag == "insert":
            continue
        raise ValueError(f"読み差分に未知の種別 {tag} があります。")
    return helper_characters


def _merge_empty_ruby_target_readings(reading_tokens: list[_ReadingToken]) -> list[_ReadingToken]:
    merged_tokens: list[_ReadingToken] = []
    token_index = 0

    while token_index < len(reading_tokens):
        token = reading_tokens[token_index]
        if len(token.raw_reading) != 0 or not has_ruby_target(token.surface):
            merged_tokens.append(token)
            token_index += 1
            continue

        previous_is_target = len(merged_tokens) != 0 and has_ruby_target(merged_tokens[-1].surface)
        next_is_target = token_index + 1 < len(reading_tokens) and has_ruby_target(reading_tokens[token_index + 1].surface)
        if previous_is_target and next_is_target:
            previous_token = merged_tokens[-1]
            next_token = reading_tokens[token_index + 1]
            left_token = _ReadingToken(
                surface=f"{previous_token.surface}{token.surface}",
                raw_reading=previous_token.raw_reading,
            )
            right_token = _ReadingToken(
                surface=f"{token.surface}{next_token.surface}",
                raw_reading=next_token.raw_reading,
            )
            left_can_create_parts = _can_create_parts(left_token)
            right_can_create_parts = _can_create_parts(right_token)
            if left_can_create_parts == right_can_create_parts:
                raise ValueError(f"{token.surface} の空読みを左右どちらのルビ対象へ対応させるか決定できません。")
            if left_can_create_parts:
                merged_tokens[-1] = left_token
                token_index += 1
                continue
            merged_tokens.append(right_token)
            token_index += 2
            continue
        if previous_is_target:
            previous_token = merged_tokens[-1]
            merged_tokens[-1] = _ReadingToken(
                surface=f"{previous_token.surface}{token.surface}",
                raw_reading=previous_token.raw_reading,
            )
            token_index += 1
            continue
        if next_is_target:
            next_token = reading_tokens[token_index + 1]
            merged_tokens.append(
                _ReadingToken(
                    surface=f"{token.surface}{next_token.surface}",
                    raw_reading=next_token.raw_reading,
                )
            )
            token_index += 2
            continue
        raise ValueError(f"{token.surface} の読みがありません。")

    return merged_tokens


def _merge_unalignable_reading_tokens(reading_tokens: list[_ReadingToken]) -> list[_ReadingToken]:
    merged_tokens: list[_ReadingToken] = []
    token_index = 0

    while token_index < len(reading_tokens):
        token = reading_tokens[token_index]
        if _can_create_parts(token):
            merged_tokens.append(token)
            token_index += 1
            continue
        if token_index + 1 >= len(reading_tokens):
            _create_parts(token.surface, token.raw_reading)

        next_token = reading_tokens[token_index + 1]
        merged_token = _ReadingToken(
            surface=f"{token.surface}{next_token.surface}",
            raw_reading=f"{token.raw_reading}{next_token.raw_reading}",
        )
        if _can_create_parts(merged_token):
            merged_tokens.append(merged_token)
            token_index += 2
            continue
        _create_parts(token.surface, token.raw_reading)

    return merged_tokens


def _can_create_parts(token: _ReadingToken) -> bool:
    try:
        _create_parts(token.surface, token.raw_reading)
    except ValueError:
        return False
    return True


def _reading_token_groups(
    frontend_tokens: list[_FrontendToken],
    opcodes: list[tuple[str, int, int, int, int]],
    target_reading: str,
) -> list[list[_FrontendToken]]:
    group_ranges: list[tuple[int, int]] = []

    for tag, helper_start, helper_end, target_start, target_end in opcodes:
        if tag == "equal":
            continue
        if tag == "insert":
            if _is_reading_only_punctuation_text(target_reading[target_start:target_end]):
                continue
            group_ranges.append(_reading_insertion_group_range(frontend_tokens, helper_start))
            continue
        if tag != "replace" and tag != "delete":
            raise ValueError(f"読み差分に未知の種別 {tag} があります。")

        token_indexes = _overlapping_reading_token_indexes(frontend_tokens, helper_start, helper_end)
        if len(token_indexes) > 1:
            group_ranges.append((token_indexes[0], token_indexes[-1] + 1))

    merged_ranges = _merge_ranges(group_ranges)
    groups: list[list[_FrontendToken]] = []
    token_index = 0
    range_index = 0
    while token_index < len(frontend_tokens):
        if range_index < len(merged_ranges) and token_index == merged_ranges[range_index][0]:
            range_start, range_end = merged_ranges[range_index]
            groups.append(frontend_tokens[range_start:range_end])
            token_index = range_end
            range_index += 1
        else:
            groups.append([frontend_tokens[token_index]])
            token_index += 1
    return groups


def _overlapping_reading_token_indexes(
    frontend_tokens: list[_FrontendToken],
    helper_start: int,
    helper_end: int,
) -> list[int]:
    return [
        token_index
        for token_index, token in enumerate(frontend_tokens)
        if token.helper_start < helper_end and token.helper_end > helper_start
    ]


def _reading_insertion_group_range(frontend_tokens: list[_FrontendToken], helper_start: int) -> tuple[int, int]:
    previous_indexes = [token_index for token_index, token in enumerate(frontend_tokens) if token.helper_end == helper_start]
    next_indexes = [token_index for token_index, token in enumerate(frontend_tokens) if token.helper_start == helper_start]

    if len(previous_indexes) != 0 and len(next_indexes) != 0:
        previous_index = previous_indexes[-1]
        next_index = next_indexes[0]
        if frontend_tokens[next_index].surface == "ー" and next_index + 1 < len(frontend_tokens):
            return previous_index, next_index + 2
        if frontend_tokens[previous_index].surface == "ー" and previous_index > 0:
            return previous_index - 1, next_index + 1
        return previous_index, next_index + 1
    if len(previous_indexes) != 0:
        token_index = previous_indexes[-1]
        return token_index, token_index + 1
    if len(next_indexes) != 0:
        token_index = next_indexes[0]
        return token_index, token_index + 1

    for token_index, token in enumerate(frontend_tokens):
        if token.helper_start < helper_start < token.helper_end:
            return token_index, token_index + 1
    raise ValueError("読みの挿入差分を対応付けるpyopenjtalk形態素がありません。")


def _target_range_for_helper_range(
    identifier: str,
    opcodes: list[tuple[str, int, int, int, int]],
    helper_start: int,
    helper_end: int,
) -> tuple[int, int]:
    target_starts: list[int] = []
    target_ends: list[int] = []

    for tag, opcode_helper_start, opcode_helper_end, opcode_target_start, opcode_target_end in opcodes:
        if tag == "insert":
            if helper_start <= opcode_helper_start < helper_end:
                target_starts.append(opcode_target_start)
                target_ends.append(opcode_target_end)
            continue

        overlap_start = max(helper_start, opcode_helper_start)
        overlap_end = min(helper_end, opcode_helper_end)
        if overlap_start >= overlap_end:
            continue

        if tag == "equal":
            target_start = opcode_target_start + overlap_start - opcode_helper_start
            target_end = opcode_target_start + overlap_end - opcode_helper_start
        elif tag == "delete":
            target_start = opcode_target_start
            target_end = opcode_target_start
        elif tag == "replace":
            if helper_start > opcode_helper_start or helper_end < opcode_helper_end:
                raise ValueError(f"{identifier} の読み差分がpyopenjtalkの形態素境界をまたいでいます。")
            target_start = opcode_target_start
            target_end = opcode_target_end
        else:
            raise ValueError(f"{identifier} の読み差分に未知の種別 {tag} があります。")

        target_starts.append(target_start)
        target_ends.append(target_end)

    if len(target_starts) == 0:
        raise ValueError(f"{identifier} の読み範囲を対応付けできません。")
    return min(target_starts), max(target_ends)


def _create_parts(surface: str, raw_reading: str) -> list[PlainPart | RubyPart]:
    exception_key = (surface, raw_reading)
    if exception_key in READING_PART_EXCEPTIONS:
        return list(READING_PART_EXCEPTIONS[exception_key])

    reading_prefix_parts: list[PlainPart | RubyPart] = []
    reading_suffix_parts: list[PlainPart | RubyPart] = []
    core_raw_reading = raw_reading

    while len(core_raw_reading) != 0 and core_raw_reading[0] in READING_ONLY_PUNCTUATIONS and not surface.startswith(core_raw_reading[0]):
        reading_prefix_parts.append(PlainPart(text="", reading=core_raw_reading[0]))
        core_raw_reading = core_raw_reading[1:]

    while len(core_raw_reading) != 0 and core_raw_reading[-1] in READING_ONLY_PUNCTUATIONS and not surface.endswith(core_raw_reading[-1]):
        reading_suffix_parts.insert(0, PlainPart(text="", reading=core_raw_reading[-1]))
        core_raw_reading = core_raw_reading[:-1]

    if len(core_raw_reading) == 0 and has_ruby_target(surface):
        raise ValueError(f"{surface} の読みがありません。")
    if len(core_raw_reading) == 0:
        return [*reading_prefix_parts, PlainPart(text=surface, reading=""), *reading_suffix_parts]

    if not has_ruby_target(surface):
        return [
            *reading_prefix_parts,
            PlainPart(text=surface, reading=normalize_segment_reading(surface, core_raw_reading)),
            *reading_suffix_parts,
        ]

    parts: list[PlainPart | RubyPart] = [*reading_prefix_parts]
    parts.extend(_split_surface_reading(surface, core_raw_reading))
    parts.extend(reading_suffix_parts)
    return parts


def _split_surface_reading(surface: str, raw_reading: str) -> list[PlainPart | RubyPart]:
    alignments = _align_surface_reading(surface, raw_reading)
    if len(alignments) == 0:
        raise ValueError(f"本文「{surface}」と読み「{raw_reading}」を対応付けできません。")
    if len(alignments) != 1:
        raise ValueError(f"本文「{surface}」と読み「{raw_reading}」の対応が一意に決まりません。")

    parts: list[PlainPart | RubyPart] = []
    for aligned_part in alignments[0]:
        if len(aligned_part.text) == 0:
            parts.append(PlainPart(text="", reading=aligned_part.raw_reading))
            continue
        reading = normalize_segment_reading(aligned_part.text, aligned_part.raw_reading)
        if aligned_part.is_ruby:
            parts.append(RubyPart(text=aligned_part.text, reading=reading))
        else:
            parts.append(PlainPart(text=aligned_part.text, reading=reading))
    return parts


def _align_surface_reading(surface: str, raw_reading: str) -> tuple[tuple[_AlignedPart, ...], ...]:
    if len(surface) == 0:
        raise ValueError("表層文字列が空です。")
    if not _has_plain_split_character(surface):
        return ((_AlignedPart(text=surface, raw_reading=raw_reading, is_ruby=True, cost=0),),)

    alignments = _align_surface_reading_from(surface, raw_reading, 0, 0)
    merged_alignments = tuple(dict.fromkeys(_merge_aligned_parts(alignment) for alignment in alignments))
    if len(merged_alignments) == 0:
        return ()

    minimum_cost = min(_alignment_cost(alignment) for alignment in merged_alignments)
    return tuple(alignment for alignment in merged_alignments if _alignment_cost(alignment) == minimum_cost)


def _align_surface_reading_from(
    surface: str,
    raw_reading: str,
    surface_index: int,
    reading_index: int,
) -> tuple[tuple[_AlignedPart, ...], ...]:
    if surface_index == len(surface):
        if reading_index == len(raw_reading):
            return ((),)
        if raw_reading[reading_index] in READING_ONLY_PUNCTUATIONS:
            suffix_alignments = _align_surface_reading_from(surface, raw_reading, surface_index, reading_index + 1)
            return tuple(
                (_AlignedPart(text="", raw_reading=raw_reading[reading_index], is_ruby=False, cost=0), *suffix_alignment)
                for suffix_alignment in suffix_alignments
            )
        return ()

    if (
        reading_index < len(raw_reading)
        and raw_reading[reading_index] in READING_ONLY_PUNCTUATIONS
        and surface[surface_index] != raw_reading[reading_index]
        and not _can_plain_character_consume(surface[surface_index], raw_reading[reading_index])
    ):
        suffix_alignments = _align_surface_reading_from(surface, raw_reading, surface_index, reading_index + 1)
        return tuple(
            (_AlignedPart(text="", raw_reading=raw_reading[reading_index], is_ruby=False, cost=0), *suffix_alignment)
            for suffix_alignment in suffix_alignments
        )

    character = surface[surface_index]
    if _is_ruby_base_character(character):
        return _align_ruby_base_run(surface, raw_reading, surface_index, reading_index)
    return _align_plain_character(surface, raw_reading, surface_index, reading_index)


def _align_ruby_base_run(
    surface: str,
    raw_reading: str,
    surface_index: int,
    reading_index: int,
) -> tuple[tuple[_AlignedPart, ...], ...]:
    run_end = _ruby_base_run_end(surface, surface_index)
    run_text = surface[surface_index:run_end]
    alignments: list[tuple[_AlignedPart, ...]] = []

    for reading_end in range(reading_index + 1, len(raw_reading) + 1):
        run_reading = raw_reading[reading_index:reading_end]
        if _has_reading_only_punctuation(run_reading):
            continue
        suffix_alignments = _align_surface_reading_from(surface, raw_reading, run_end, reading_end)
        for suffix_alignment in suffix_alignments:
            alignments.append((_AlignedPart(text=run_text, raw_reading=run_reading, is_ruby=True, cost=0), *suffix_alignment))

    return tuple(alignments)


def _align_plain_character(
    surface: str,
    raw_reading: str,
    surface_index: int,
    reading_index: int,
) -> tuple[tuple[_AlignedPart, ...], ...]:
    character = surface[surface_index]
    candidates = _plain_character_reading_candidates(character)
    alignments: list[tuple[_AlignedPart, ...]] = []

    for candidate in candidates:
        next_reading_index = reading_index + len(candidate)
        if next_reading_index > len(raw_reading):
            continue
        if not raw_reading.startswith(candidate, reading_index):
            continue
        suffix_alignments = _align_surface_reading_from(surface, raw_reading, surface_index + 1, next_reading_index)
        for suffix_alignment in suffix_alignments:
            alignments.append(
                (
                    _AlignedPart(
                        text=character,
                        raw_reading=candidate,
                        is_ruby=False,
                        cost=_plain_character_reading_cost(character, candidate),
                    ),
                    *suffix_alignment,
                )
            )

    return tuple(alignments)


def _merge_aligned_parts(alignment: tuple[_AlignedPart, ...]) -> tuple[_AlignedPart, ...]:
    if len(alignment) == 0:
        return ()

    merged_parts = [alignment[0]]
    for part in alignment[1:]:
        previous_part = merged_parts[-1]
        if previous_part.is_ruby == part.is_ruby and len(previous_part.text) != 0 and len(part.text) != 0:
            merged_parts[-1] = _AlignedPart(
                text=f"{previous_part.text}{part.text}",
                raw_reading=f"{previous_part.raw_reading}{part.raw_reading}",
                is_ruby=previous_part.is_ruby,
                cost=previous_part.cost + part.cost,
            )
        else:
            merged_parts.append(part)
    return tuple(merged_parts)


def _alignment_cost(alignment: tuple[_AlignedPart, ...]) -> int:
    cost = sum(part.cost for part in alignment)
    for previous_part, current_part in zip(alignment, alignment[1:], strict=False):
        if previous_part.is_ruby and not current_part.is_ruby and len(current_part.raw_reading) != 0:
            if previous_part.raw_reading.endswith(current_part.raw_reading):
                cost += 1
    return cost


def _has_plain_split_character(text: str) -> bool:
    for character in text:
        if not _is_ruby_base_character(character):
            return True
    return False


def _ruby_base_run_end(text: str, start: int) -> int:
    end = start
    while end < len(text) and _is_ruby_base_character(text[end]):
        end += 1
    return end


def _is_ruby_base_character(character: str) -> bool:
    return is_ruby_target_character(character)


def _plain_character_reading_candidates(character: str) -> tuple[str, ...]:
    base_reading = _plain_character_reading(character)
    if base_reading is None:
        raise ValueError(f"ルビ対象ではない文字 {character} の読みを決定できません。")

    candidates = [base_reading]
    if character in {"は", "ハ"}:
        candidates.append("わ")
    if character in {"へ", "ヘ"}:
        candidates.append("え")
    if character in {"を", "ヲ"}:
        candidates.append("お")
    if character in {"ぢ", "ヂ"}:
        candidates.append("じ")
    if character in {"づ", "ヅ"}:
        candidates.append("ず")
    if character in {"あ", "い", "う", "え", "お", "ア", "イ", "ウ", "エ", "オ"}:
        candidates.append("ー")
    if character == "ー":
        candidates.extend(LONG_SOUND_REPLACEMENT_CHARACTERS)
        candidates.append("、")
    if _is_optional_reading_character(character):
        candidates.append("")
    return tuple(dict.fromkeys(candidates))


def _plain_character_reading_cost(character: str, reading: str) -> int:
    base_reading = _plain_character_reading(character)
    if base_reading is None:
        raise ValueError(f"ルビ対象ではない文字 {character} の読みを決定できません。")
    if reading == base_reading:
        return 0
    if character == "ー" and reading in LONG_SOUND_REPLACEMENT_CHARACTERS:
        return 0
    if character == "ー" and reading == "、":
        return 0
    if _is_optional_reading_character(character) and len(reading) == 0:
        return 1
    if reading in _plain_character_reading_candidates(character):
        return 1
    raise ValueError(f"{character} の読み {reading} は候補にありません。")


def _can_plain_character_consume(character: str, reading: str) -> bool:
    if _is_ruby_base_character(character):
        return False
    return reading in _plain_character_reading_candidates(character)


def _has_reading_only_punctuation(text: str) -> bool:
    for character in text:
        if character in READING_ONLY_PUNCTUATIONS:
            return True
    return False


def _is_reading_only_punctuation_text(text: str) -> bool:
    if len(text) == 0:
        raise ValueError("読み差分が空です。")
    for character in text:
        if character not in READING_ONLY_PUNCTUATIONS:
            return False
    return True


def _plain_character_reading(character: str) -> str | None:
    if "\u3040" <= character <= "\u309F":
        return character
    if "\u30A0" <= character <= "\u30FF":
        return katakana_to_hiragana(character)
    if character in {"、", "。", "・", "，", "．", "！", "？", " ", "　"}:
        return character
    return None


def _is_optional_reading_character(character: str) -> bool:
    return character in {"、", "。", "・", "，", "．", "！", "？", " ", "　"}
