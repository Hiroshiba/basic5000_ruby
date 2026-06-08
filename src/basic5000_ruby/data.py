from dataclasses import dataclass
from pathlib import Path
import re


TOTAL_SENTENCE_COUNT = 5000
FIELD_PATTERN = re.compile(r"^  ([a-z0-9_]+): (.*)$")
IDENTIFIER_PATTERN = re.compile(r"^(BASIC5000_(\d{4})):$")


@dataclass(frozen=True)
class Sentence:
    """BASIC5000の1文を表す。"""

    identifier: str
    number: int
    text: str
    kana: str


def load_sentences(path: Path) -> list[Sentence]:
    """basic5000.txtからBASIC5000の文を読み込む。"""

    records: list[Sentence] = []
    current_identifier: str | None = None
    current_fields: dict[str, str] = {}

    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        identifier_match = IDENTIFIER_PATTERN.fullmatch(line)
        if identifier_match is not None:
            if current_identifier is not None:
                records.append(_create_sentence(current_identifier, current_fields))
            current_identifier = identifier_match.group(1)
            current_fields = {}
            continue

        field_match = FIELD_PATTERN.fullmatch(line)
        if field_match is None:
            raise ValueError(f"{path}:{line_number} の形式を解析できません。")
        if current_identifier is None:
            raise ValueError(f"{path}:{line_number} にIDより前のフィールドがあります。")

        key = field_match.group(1)
        value = field_match.group(2)
        if key in current_fields:
            raise ValueError(f"{current_identifier} の {key} が重複しています。")
        current_fields[key] = value

    if current_identifier is None:
        raise ValueError(f"{path} にBASIC5000のデータがありません。")

    records.append(_create_sentence(current_identifier, current_fields))
    _validate_sentences(records)
    return records


def _create_sentence(identifier: str, fields: dict[str, str]) -> Sentence:
    missing_fields = [field_name for field_name in ("text_level2", "kana_level3") if field_name not in fields]
    if len(missing_fields) != 0:
        missing_text = "、".join(missing_fields)
        raise ValueError(f"{identifier} に {missing_text} がありません。")

    number_text = identifier.removeprefix("BASIC5000_")
    return Sentence(
        identifier=identifier,
        number=int(number_text),
        text=fields["text_level2"],
        kana=fields["kana_level3"],
    )


def _validate_sentences(sentences: list[Sentence]) -> None:
    if len(sentences) != TOTAL_SENTENCE_COUNT:
        raise ValueError(f"BASIC5000の件数が {len(sentences)} 件です。5000件である必要があります。")

    for expected_number, sentence in enumerate(sentences, start=1):
        expected_identifier = f"BASIC5000_{expected_number:04d}"
        if sentence.identifier != expected_identifier:
            raise ValueError(f"{sentence.identifier} は {expected_identifier} である必要があります。")
        if sentence.number != expected_number:
            raise ValueError(f"{sentence.identifier} の番号が {expected_number} ではありません。")
