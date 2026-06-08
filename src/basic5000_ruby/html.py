from html import escape
from itertools import batched

from basic5000_ruby.ruby import PlainPart, RubyPart, RubySentence


PAGE_SIZE = 100
TITLE = "BASIC5000ルビ付き台本"
STYLE_CSS = """
:root {
  color: #232323;
  background: #fafafa;
  line-height: 1.7;
}

body {
  margin: 0;
}

a {
  color: #0b65a3;
}

header,
footer {
  box-sizing: border-box;
  width: 100%;
  margin: 0 auto;
  padding: 24px;
}

main {
  box-sizing: border-box;
  width: 100%;
  margin: 0 auto;
  padding: 24px;
}

.script-main {
  padding: 16px 8px 24px;
}

.index-main {
  padding-top: 8px;
  width: 100%;
}

header {
  border-bottom: 1px solid #d8d8d8;
}

.index-header {
  border-bottom: 0;
  padding-bottom: 8px;
}

.index-main section:first-child h2 {
  margin-top: 0;
}

h1 {
  margin: 0 0 8px;
  font-size: 2rem;
  line-height: 1.25;
}

h2 {
  margin: 32px 0 12px;
  font-size: 1.25rem;
}

p {
  margin: 0 0 12px;
}

.page-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(5rem, 1fr));
  gap: 8px;
  margin: 20px 0;
}

.page-card {
  display: block;
  padding: 6px 10px;
  border: 1px solid #cfcfcf;
  border-radius: 4px;
  text-align: center;
  text-decoration: none;
  background: #ffffff;
}

.single-link {
  display: flex;
  margin: 20px 0;
}

.single-link .page-card {
  min-width: 8rem;
}

.pager {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 20px 0;
}

.page-navigation {
  display: grid;
  gap: 8px;
  margin: 20px 0;
}

.page-navigation .pager {
  margin: 0;
}

.pager a,
.pager span {
  min-width: 2.4rem;
  padding: 6px 10px;
  border: 1px solid #cfcfcf;
  border-radius: 4px;
  text-align: center;
  text-decoration: none;
  background: #ffffff;
}

.pager .current {
  color: #ffffff;
  border-color: #1f6f43;
  background: #1f6f43;
}

.pager .disabled {
  color: #7a7a7a;
  background: #eeeeee;
}

.script-table {
  width: 100%;
  border-collapse: collapse;
  background: #ffffff;
}

.script-table th,
.script-table td {
  padding: 16px 12px 12px;
  border: 1px solid #d6d6d6;
  vertical-align: top;
}

.script-table th {
  background: #f0f3f5;
  text-align: left;
  font-weight: 600;
}

.script-table .number-header,
.script-table .number-cell {
  box-sizing: border-box;
  width: 4.5rem;
  white-space: nowrap;
  text-align: center;
}

.script-section {
  margin: 0 0 32px;
}

.script-main > h2 {
  margin: 0 0 8px;
}

.script-section h2 {
  margin: 24px 0 8px;
}

.sentence {
  font-size: 1.18rem;
}

rt {
  font-size: 0.72em;
}

footer {
  border-top: 1px solid #d8d8d8;
  color: #4f4f4f;
  font-size: 0.95rem;
}

@media (max-width: 640px) {
  header,
  main,
  footer {
    padding: 16px;
  }

  h1 {
    font-size: 1.5rem;
  }

  .script-table th,
  .script-table td {
    display: block;
    width: auto;
  }

  .script-table .number-header,
  .script-table .number-cell {
    width: auto;
  }

  .script-table tr {
    display: block;
    border-bottom: 1px solid #d6d6d6;
  }
}
""".strip()


def chunk_sentences(sentences: list[RubySentence]) -> list[list[RubySentence]]:
    """ルビ生成済み文をページ単位に分割する。"""

    return [list(chunk) for chunk in batched(sentences, PAGE_SIZE)]


def render_index_page(total_pages: int, total_sentences: int) -> str:
    """トップページHTMLを生成する。"""

    page_links = _render_index_page_links(total_pages)
    return _document(
        stylesheet_path="assets/style.css",
        body=f"""
<header class="index-header">
  <h1>{escape(TITLE)}</h1>
  <p>JSUT BASIC5000の漢字仮名交じり文にルビを付けた台本ページです。</p>
</header>
<main class="index-main">
  <section>
    <h2>全文表示</h2>
    <p>{total_sentences}文を全文表示します。印刷に便利です。</p>
    <nav class="single-link" aria-label="全文表示"><a class="page-card" href="./all/">0001-5000</a></nav>
  </section>
  <section>
    <h2>100文表示</h2>
    <p>100文ずつ表示します。</p>
  {page_links}
  </section>
</main>
{_render_footer()}
""",
    )


def render_script_page(page_number: int, total_pages: int, sentences: list[RubySentence]) -> str:
    """台本ページHTMLを生成する。"""

    first_number = sentences[0].number
    last_number = sentences[-1].number
    bottom_pager = _render_bottom_pager(page_number, total_pages)
    table_html = _render_script_table(sentences)
    return _document(
        stylesheet_path="../assets/style.css",
        body=f"""
<header>
  <h1>{escape(TITLE)}</h1>
</header>
<main class="script-main">
  <h2>{first_number:04d}-{last_number:04d}</h2>
  {table_html}
  {bottom_pager}
</main>
{_render_footer()}
""",
    )


def render_all_page(total_pages: int, sentence_pages: list[list[RubySentence]]) -> str:
    """全件一覧ページHTMLを生成する。"""

    page_links = _render_all_page_links(total_pages)
    sections = "\n".join(_render_script_section(page_number, page_sentences) for page_number, page_sentences in enumerate(sentence_pages, start=1))
    return _document(
        stylesheet_path="../assets/style.css",
        body=f"""
<header>
  <h1>{escape(TITLE)} 全件一覧</h1>
  <nav class="page-grid" aria-label="見出しへ移動">{page_links}</nav>
</header>
<main class="script-main">
{sections}
  <nav class="single-link" aria-label="トップへ戻る"><a class="page-card" href="../">トップへ</a></nav>
</main>
{_render_footer()}
""",
    )


def _render_script_section(page_number: int, sentences: list[RubySentence]) -> str:
    first_number = sentences[0].number
    last_number = sentences[-1].number
    table_html = _render_script_table(sentences)
    return f"""
  <section class="script-section" id="page-{page_number}">
    <h2>{first_number:04d}-{last_number:04d}</h2>
    {table_html}
  </section>
"""


def _render_script_table(sentences: list[RubySentence]) -> str:
    rows = "\n".join(_render_sentence_row(sentence) for sentence in sentences)
    return f"""<table class="script-table">
    <thead>
      <tr>
        <th class="number-header" scope="col">番号</th>
        <th scope="col">本文</th>
      </tr>
    </thead>
    <tbody>
{rows}
    </tbody>
  </table>"""


def _document(stylesheet_path: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(TITLE)}</title>
  <link rel="stylesheet" href="{escape(stylesheet_path)}">
</head>
<body>
{body}
</body>
</html>
"""


def _render_sentence_row(sentence: RubySentence) -> str:
    sentence_html = "".join(_render_part(part) for part in sentence.parts)
    return f"""      <tr data-id="{escape(sentence.identifier)}" data-text="{escape(sentence.text)}" data-reading="{escape(sentence.reading)}">
        <th class="number-cell" scope="row">{sentence.number:04d}</th>
        <td class="sentence">{sentence_html}</td>
      </tr>"""


def _render_part(part: PlainPart | RubyPart) -> str:
    if isinstance(part, PlainPart):
        return escape(part.text)
    if isinstance(part, RubyPart):
        return f"<ruby>{escape(part.text)}<rt>{escape(part.reading)}</rt></ruby>"
    raise TypeError("未知のルビ部品です。")


def _render_bottom_pager(page_number: int, total_pages: int) -> str:
    previous_link = _render_nav_link("前へ", f"../{page_number - 1}/", page_number != 1)
    next_link = _render_nav_link("次へ", f"../{page_number + 1}/", page_number != total_pages)
    top_link = _render_nav_link("トップへ", "../", True)
    page_links = _render_page_links(total_pages, page_number, "../")
    return f'<div class="page-navigation" aria-label="ページ移動"><nav class="pager" aria-label="前後のページ">{previous_link}{next_link}{top_link}</nav><nav class="pager" aria-label="ページ一覧">{page_links}</nav></div>'


def _render_nav_link(label: str, href: str, enabled: bool) -> str:
    if enabled:
        return f'<a href="{escape(href)}">{escape(label)}</a>'
    return f'<span class="disabled">{escape(label)}</span>'


def _render_page_links(total_pages: int, current_page: int, prefix: str) -> str:
    links: list[str] = []
    for page_number in range(1, total_pages + 1):
        label = _page_link_label(page_number)
        if page_number == current_page:
            links.append(f'<span class="current" aria-current="page">{label}</span>')
        else:
            links.append(f'<a href="{escape(prefix)}{page_number}/">{label}</a>')
    return "".join(links)


def _render_index_page_links(total_pages: int) -> str:
    links: list[str] = []
    for page_number in range(1, total_pages + 1):
        label = _page_link_label(page_number)
        links.append(
            f'<a class="page-card" href="./{page_number}/">{label}</a>'
        )
    return f'<nav class="page-grid" aria-label="台本ページ一覧">{"".join(links)}</nav>'


def _render_all_page_links(total_pages: int) -> str:
    links: list[str] = []
    for page_number in range(1, total_pages + 1):
        label = _page_link_label(page_number)
        links.append(
            f'<a class="page-card" href="#page-{page_number}">{label}</a>'
        )
    return "".join(links)


def _page_link_label(page_number: int) -> str:
    first_number = (page_number - 1) * PAGE_SIZE + 1
    return f"{first_number:04d}-"


def _render_footer() -> str:
    return """
<footer>
  <p>出典: <a href="https://sites.google.com/site/shinnosuketakamichi/publication/jsut">JSUT</a>、<a href="https://tyc.rei-yumesaki.net/material/minnade-jsut/">みんなで作るJSUTコーパスbasic5000</a></p>
  <p><a href="https://github.com/Hiroshiba/basic5000_ruby">GitHubリポジトリ</a></p>
</footer>
"""
