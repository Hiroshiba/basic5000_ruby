from pathlib import Path

from basic5000_ruby.data import load_sentences
from basic5000_ruby.html import STYLE_CSS, chunk_sentences, render_all_page, render_index_page, render_script_page
from basic5000_ruby.ruby import generate_all_sentences
from basic5000_ruby.validate import validate_ruby_sentences, validate_site


def main() -> None:
    """site配下に静的HTMLを生成する。"""

    project_root = Path.cwd()
    build(project_root)


def build(project_root: Path) -> None:
    """指定したリポジトリ直下で静的HTMLを生成する。"""

    source_path = project_root / "hiho_clone" / "jsut_hiho" / "basic5000.txt"
    site_dir = project_root / "site"

    sentences = load_sentences(source_path)
    ruby_sentences = generate_all_sentences(sentences)
    validate_ruby_sentences(ruby_sentences)

    sentence_pages = chunk_sentences(ruby_sentences)
    total_pages = len(sentence_pages)
    site_dir.mkdir(exist_ok=True)
    assets_dir = site_dir / "assets"
    assets_dir.mkdir(exist_ok=True)
    (assets_dir / "style.css").write_text(f"{STYLE_CSS}\n", encoding="utf-8")
    (site_dir / ".nojekyll").write_text("", encoding="utf-8")
    (site_dir / "index.html").write_text(render_index_page(total_pages, len(ruby_sentences)), encoding="utf-8")
    all_dir = site_dir / "all"
    all_dir.mkdir(exist_ok=True)
    (all_dir / "index.html").write_text(render_all_page(total_pages, sentence_pages), encoding="utf-8")

    for page_number, page_sentences in enumerate(sentence_pages, start=1):
        page_dir = site_dir / str(page_number)
        page_dir.mkdir(exist_ok=True)
        page_html = render_script_page(page_number, total_pages, page_sentences)
        (page_dir / "index.html").write_text(page_html, encoding="utf-8")

    validate_site(site_dir, ruby_sentences)
    print(f"site に {total_pages} ページ、{len(ruby_sentences)} 文を生成しました。")
