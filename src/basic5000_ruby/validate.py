from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

from basic5000_ruby.data import load_sentences
from basic5000_ruby.html import PAGE_SIZE, chunk_sentences
from basic5000_ruby.ruby import RubyPart, RubySentence, generate_all_sentences


LONG_SOUND_MARK = "ー"


def main() -> None:
    """生成済みHTMLとルビ生成結果を検証する。"""

    project_root = Path.cwd()
    source_path = project_root / "hiho_clone" / "jsut_hiho" / "basic5000.txt"
    site_dir = project_root / "site"

    sentences = load_sentences(source_path)
    ruby_sentences = generate_all_sentences(sentences)
    validate_ruby_sentences(ruby_sentences)
    validate_site(site_dir, ruby_sentences)
    print(f"site の {len(ruby_sentences)} 文を検証しました。")


@dataclass(frozen=True)
class ParsedRow:
    """HTMLから読み取った台本行を表す。"""

    identifier: str
    text: str
    reading: str
    visible_text: str


class ScriptPageParser(HTMLParser):
    """台本ページの行データを読み取るHTMLパーサー。"""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[ParsedRow] = []
        self._current_identifier: str | None = None
        self._current_text: str | None = None
        self._current_reading: str | None = None
        self._current_visible_parts: list[str] = []
        self._inside_row = False
        self._inside_sentence_cell = False
        self._inside_rt = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_dict = _attrs_to_dict(attrs)
        if tag == "tr":
            if "data-id" in attr_dict:
                self._current_identifier = attr_dict["data-id"]
                self._current_text = _require_attr(attr_dict, "data-text")
                self._current_reading = _require_attr(attr_dict, "data-reading")
                self._current_visible_parts = []
                self._inside_row = True
        if tag == "td" and self._inside_row and attr_dict.get("class") == "sentence":
            self._inside_sentence_cell = True
        if tag == "rt" and self._inside_row:
            self._inside_rt = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "rt":
            self._inside_rt = False
        if tag == "td" and self._inside_sentence_cell:
            self._inside_sentence_cell = False
        if tag == "tr" and self._inside_row:
            if self._current_identifier is None or self._current_text is None or self._current_reading is None:
                raise ValueError("台本行の属性が不足しています。")
            self.rows.append(
                ParsedRow(
                    identifier=self._current_identifier,
                    text=self._current_text,
                    reading=self._current_reading,
                    visible_text="".join(self._current_visible_parts).strip(),
                )
            )
            self._current_identifier = None
            self._current_text = None
            self._current_reading = None
            self._current_visible_parts = []
            self._inside_row = False
            self._inside_sentence_cell = False
            self._inside_rt = False

    def handle_data(self, data: str) -> None:
        if self._inside_sentence_cell and not self._inside_rt:
            self._current_visible_parts.append(data)


def validate_ruby_sentences(sentences: list[RubySentence]) -> None:
    """ルビ生成結果が本文と読みを復元でき、かなにルビやルビ読みの長音記号が残らないか検証する。"""

    ruby_errors: list[str] = []
    reading_errors: list[str] = []
    for sentence in sentences:
        text = "".join(part.text for part in sentence.parts)
        if text != sentence.text:
            raise ValueError(f"{sentence.identifier} のルビ部品から本文を復元できません。")
        reading = "".join(part.reading for part in sentence.parts)
        if reading != sentence.reading:
            raise ValueError(f"{sentence.identifier} のルビ部品から読みを復元できません。")
        ruby_errors.extend(_validate_ruby_base_text(sentence))
        reading_errors.extend(_validate_ruby_reading_text(sentence))

    if len(ruby_errors) != 0:
        raise ValueError("ルビ本文にかなが含まれています。\n" + "\n".join(ruby_errors))
    if len(reading_errors) != 0:
        raise ValueError("ルビ読みに長音記号が含まれています。\n" + "\n".join(reading_errors))


def _validate_ruby_reading_text(sentence: RubySentence) -> list[str]:
    reading_errors: list[str] = []
    for part in sentence.parts:
        if not isinstance(part, RubyPart):
            continue
        if LONG_SOUND_MARK not in part.reading:
            continue
        reading_errors.append(f"{sentence.identifier}: 本文「{part.text}」、読み「{part.reading}」、全文「{sentence.text}」")
    return reading_errors


def _validate_ruby_base_text(sentence: RubySentence) -> list[str]:
    ruby_errors: list[str] = []
    for part in sentence.parts:
        if not isinstance(part, RubyPart):
            continue
        kana_text = _extract_kana(part.text)
        if len(kana_text) == 0:
            continue
        ruby_errors.append(f"{sentence.identifier}: 本文「{part.text}」、かな「{kana_text}」、読み「{part.reading}」")
    return ruby_errors


def _extract_kana(text: str) -> str:
    kana_characters: list[str] = []
    for character in text:
        if _is_kana(character):
            kana_characters.append(character)
    return "".join(kana_characters)


def _is_kana(character: str) -> bool:
    # NOTE: 「ヶ」は漢字相当として扱うため、かな検出から除外する。
    if character == "ヶ":
        return False
    return "\u3040" <= character <= "\u30FF" or "\uFF66" <= character <= "\uFF9D"


def validate_site(site_dir: Path, ruby_sentences: list[RubySentence]) -> None:
    """site配下の生成済みHTMLを検証する。"""

    if not (site_dir / "index.html").is_file():
        raise ValueError("site/index.html がありません。")
    if not (site_dir / "assets" / "style.css").is_file():
        raise ValueError("site/assets/style.css がありません。")
    all_page_path = site_dir / "all" / "index.html"
    if not all_page_path.is_file():
        raise ValueError("site/all/index.html がありません。")

    sentence_pages = chunk_sentences(ruby_sentences)
    total_pages = len(sentence_pages)
    numeric_page_dirs = sorted(int(path.name) for path in site_dir.iterdir() if path.is_dir() and path.name.isdecimal())
    expected_page_dirs = list(range(1, total_pages + 1))
    if numeric_page_dirs != expected_page_dirs:
        raise ValueError("site配下のページ番号ディレクトリが期待値と一致しません。")

    for page_number, page_sentences in enumerate(sentence_pages, start=1):
        page_path = site_dir / str(page_number) / "index.html"
        if not page_path.is_file():
            raise ValueError(f"{page_path} がありません。")
        rows = _parse_rows(page_path)
        if len(rows) != PAGE_SIZE:
            raise ValueError(f"{page_path} の文数が {PAGE_SIZE} ではありません。")
        _validate_rows(page_path, rows, page_sentences)

    all_rows = _parse_rows(all_page_path)
    if len(all_rows) != len(ruby_sentences):
        raise ValueError("site/all/index.html の文数が5000ではありません。")
    _validate_rows(all_page_path, all_rows, ruby_sentences)


def _parse_rows(page_path: Path) -> list[ParsedRow]:
    parser = ScriptPageParser()
    parser.feed(page_path.read_text(encoding="utf-8"))
    parser.close()
    return parser.rows


def _validate_rows(page_path: Path, rows: list[ParsedRow], sentences: list[RubySentence]) -> None:
    if len(rows) != len(sentences):
        raise ValueError(f"{page_path} の行数が期待値と一致しません。")

    for row, sentence in zip(rows, sentences, strict=True):
        if row.identifier != sentence.identifier:
            raise ValueError(f"{page_path} のID {row.identifier} は {sentence.identifier} である必要があります。")
        if row.text != sentence.text:
            raise ValueError(f"{row.identifier} のdata-textが本文と一致しません。")
        if row.visible_text != sentence.text:
            raise ValueError(f"{row.identifier} の表示本文を復元できません。")
        if row.reading != sentence.reading:
            raise ValueError(f"{row.identifier} のdata-readingが読みと一致しません。")


def _attrs_to_dict(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
    attr_dict: dict[str, str] = {}
    for key, value in attrs:
        if value is None:
            raise ValueError(f"{key} 属性に値がありません。")
        attr_dict[key] = value
    return attr_dict


def _require_attr(attrs: dict[str, str], key: str) -> str:
    if key not in attrs:
        raise ValueError(f"{key} 属性がありません。")
    return attrs[key]
