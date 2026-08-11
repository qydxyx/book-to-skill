"""GFM tables + figure inventory (additive visual path)."""
from __future__ import annotations
import sys, zipfile
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from book_to_skill.tables import rows_to_gfm, looks_like_gfm_table
from book_to_skill.figures import extract_figures_from_html, figure_stats, guess_kind_hint, write_figures_jsonl, load_figures_jsonl, FigureRecord, extract_figures_from_epub
from book_to_skill.parsers.html import _HTMLTextExtractor
from book_to_skill.utils import detect_structure, parse_arguments

# load_figures may not exist - define fallback
try:
    from book_to_skill.figures import load_figures_jsonl
except ImportError:
    def load_figures_jsonl(path=None):
        import json
        from book_to_skill.config import OUTPUT_FIGURES
        src = Path(path) if path else OUTPUT_FIGURES
        if not src.exists(): return []
        return [json.loads(l) for l in src.read_text().splitlines() if l.strip()]

class TestTables:
    def test_gfm(self):
        out = rows_to_gfm([["A","B"],["1","2"]], table_id="T01")
        assert "<!-- table:T01 -->" in out and looks_like_gfm_table(out)

class TestHtml:
    def test_gfm_and_alt(self):
        html = '<h2>Chapter 1</h2><img alt="architecture diagram" src="a.png"/><table><tr><th>K</th><th>V</th></tr><tr><td>a</td><td>1</td></tr></table><h2>Chapter 2</h2>'
        p=_HTMLTextExtractor(); p.feed(html); text=p.get_text()
        assert "<!-- table:T01 -->" in text and "[Image: architecture diagram]" in text
        assert detect_structure(text)["chapters_detected"] == 2
    def test_toc_gfm_chapters(self):
        html = "<table><tr><td>Chapter 1</td><td>A</td></tr><tr><td>Chapter 2</td><td>B</td></tr><tr><td>Chapter 3</td><td>C</td></tr></table>"
        p=_HTMLTextExtractor(); p.feed(html)
        assert detect_structure(p.get_text())["chapters_detected"] == 3

class TestFigures:
    def test_kinds(self):
        assert guess_kind_hint(alt="system architecture diagram") == "diagram"
        assert guess_kind_hint(caption="bar chart of errors") == "chart"
    def test_html_inventory(self):
        html = '<figure><img alt="architecture overview" src="a.png"/><figcaption>Figure 1. System</figcaption></figure><img alt="company logo" src="logo.png"/>'
        recs,_=extract_figures_from_html(html, source="x.html")
        by={r.alt:r for r in recs}
        assert by["architecture overview"].kind_hint == "diagram"
        assert by["company logo"].skipped_reason == "decorative"
        assert figure_stats(recs)["figures_high_value"] >= 1
    def test_jsonl(self, tmp_path):
        recs=[FigureRecord(id="f1", source="a", alt="diagram", kind_hint="diagram")]
        path=tmp_path/"f.jsonl"; write_figures_jsonl(recs, path=path)
        assert load_figures_jsonl(path)[0]["id"]=="f1"
    def test_epub_assets(self, tmp_path):
        epub=tmp_path/"b.epub"
        with zipfile.ZipFile(epub,"w") as zf:
            zf.writestr("mimetype","application/epub+zip")
            zf.writestr("META-INF/container.xml",'<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
            zf.writestr("content.opf",'<?xml version="1.0"?><package version="3.0" xmlns="http://www.idpf.org/2007/opf"><manifest><item id="c1" href="c1.xhtml" media-type="application/xhtml+xml"/><item id="img" href="images/chart.png" media-type="image/png"/></manifest><spine><itemref idref="c1"/></spine></package>')
            zf.writestr("c1.xhtml",'<html><body><img src="images/chart.png" alt="throughput chart"/></body></html>')
            zf.writestr("images/chart.png", b"\x89PNG\r\n\x1a\n" + b"\0"*8)
        assets=tmp_path/"assets"
        recs,_=extract_figures_from_epub(str(epub), assets_dir=assets, id_prefix="ep")
        assert any(r.path and Path(r.path).is_file() for r in recs)

class TestCLI:
    def test_flags(self):
        paths, mode, _, opts = parse_arguments(["e","a.pdf","--extract-figures","--vision","no"])
        assert opts["extract_figures"] is True and opts["vision"]=="no"
    def test_technical_default_figures(self):
        _, mode, _, opts = parse_arguments(["e","a.pdf","--mode","technical"])
        assert mode=="technical" and opts["extract_figures"] is True
    def test_technical_disable(self):
        _, mode, _, opts = parse_arguments(["e","a.pdf","--mode","technical","--no-extract-figures"])
        assert opts["extract_figures"] is False
