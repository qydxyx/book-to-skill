from __future__ import annotations

import html.parser
from book_to_skill.parsers.text import read_text_file
from book_to_skill.tables import next_table_id, rows_to_gfm


class _HTMLTextExtractor(html.parser.HTMLParser):
    """stdlib HTML → text with GFM tables and image alt/caption markers."""

    SKIP_TAGS = {"script", "style", "head"}
    # table/tr/td/th handled by table state machine
    BLOCK_TAGS = frozenset({
        "address", "article", "aside", "blockquote", "br", "dd", "details",
        "div", "dl", "dt", "fieldset", "figcaption", "figure", "footer",
        "form", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hgroup", "hr",
        "li", "main", "nav", "ol", "p", "pre", "section", "ul",
    })

    def __init__(self):
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth = 0
        self._pending = ""
        self._in_table = 0
        self._table_rows: list[list[str]] = []
        self._current_row: list[str] | None = None
        self._current_cell: list[str] | None = None
        self._table_counter = [0]
        self._in_figcaption = 0
        self._figcaption_parts: list[str] = []

    def _mark(self, separator: str) -> None:
        if separator == "\n" or not self._pending:
            self._pending = separator

    def _flush_pending_for(self, data: str) -> None:
        if self._pending:
            if not data.strip():
                return
            if self._parts:
                self._parts.append(self._pending)
            self._pending = ""
        self._parts.append(data)

    def _attrs_dict(self, attrs) -> dict[str, str]:
        return {k.lower(): (v or "") for k, v in attrs}

    def _emit_image(self, attrs) -> None:
        ad = self._attrs_dict(attrs)
        alt = (ad.get("alt") or "").strip()
        src = (ad.get("src") or "").strip()
        label = alt or (src.rsplit("/", 1)[-1] if src else "image")
        self._mark("\n")
        self._flush_pending_for(f"[Image: {label}]")
        self._mark("\n")

    def _flush_table(self) -> None:
        rows = self._table_rows
        self._table_rows = []
        self._current_row = None
        self._current_cell = None
        if not rows:
            return
        gfm = rows_to_gfm(rows, table_id=next_table_id(self._table_counter))
        if not gfm:
            return
        if self._parts and not str(self._parts[-1]).endswith("\n"):
            self._parts.append("\n")
        self._pending = ""
        if self._parts:
            self._parts.append("\n")
        self._parts.append(gfm)
        self._parts.append("\n")
        self._mark("\n")

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "table":
            self._in_table += 1
            if self._in_table == 1:
                self._table_rows = []
            self._mark("\n")
            return
        if tag == "tr" and self._in_table:
            self._current_row = []
            return
        if tag in {"td", "th"} and self._in_table:
            self._current_cell = []
            return
        if tag == "img":
            ad = self._attrs_dict(attrs)
            alt = (ad.get("alt") or "").strip()
            if self._current_cell is not None:
                if alt:
                    self._current_cell.append(alt)
            else:
                self._emit_image(attrs)
            return
        if tag == "figcaption":
            self._in_figcaption += 1
            self._mark("\n")
            return
        if tag in self.BLOCK_TAGS:
            self._mark("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP_TAGS:
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag in {"td", "th"} and self._in_table:
            cell_text = "".join(self._current_cell or []).strip()
            if self._current_row is not None:
                self._current_row.append(cell_text)
            self._current_cell = None
            return
        if tag == "tr" and self._in_table:
            if self._current_row is not None and any(c.strip() for c in self._current_row):
                self._table_rows.append(self._current_row)
            self._current_row = None
            return
        if tag == "table" and self._in_table:
            self._in_table -= 1
            if self._in_table == 0:
                self._flush_table()
            return
        if tag == "figcaption" and self._in_figcaption:
            self._in_figcaption -= 1
            caption = "".join(self._figcaption_parts).strip()
            self._figcaption_parts = []
            if caption:
                self._mark("\n")
                self._flush_pending_for(f"[Caption: {caption}]")
                self._mark("\n")
            return
        if tag in self.BLOCK_TAGS:
            self._mark("\n")

    def handle_data(self, data):
        if self._skip_depth:
            return
        if self._current_cell is not None:
            self._current_cell.append(data)
            return
        if self._in_figcaption:
            self._figcaption_parts.append(data)
        if self._pending:
            if not data.strip():
                return
            if self._parts:
                self._parts.append(self._pending)
            self._pending = ""
        self._parts.append(data)

    def get_text(self) -> str:
        if self._in_table and self._table_rows:
            self._flush_table()
        return "".join(self._parts)


def _bs4_extract(raw_html: str) -> str:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(raw_html, "html.parser")
    for element in soup(["script", "style", "head"]):
        element.decompose()
    table_counter = [0]
    for table in list(soup.find_all("table")):
        rows = []
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"], recursive=False)]
            if not cells:
                cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
            if any(cells):
                rows.append(cells)
        gfm = rows_to_gfm(rows, table_id=next_table_id(table_counter)) if rows else ""
        table.replace_with(soup.new_string("\n" + gfm + "\n" if gfm else ""))
    for img in list(soup.find_all("img")):
        alt = (img.get("alt") or "").strip()
        src = (img.get("src") or "").strip()
        label = alt or (src.rsplit("/", 1)[-1] if src else "image")
        img.replace_with(soup.new_string(f"\n[Image: {label}]\n"))
    for capt in list(soup.find_all("figcaption")):
        text = capt.get_text(" ", strip=True)
        if text:
            capt.replace_with(soup.new_string(f"\n[Caption: {text}]\n"))
        else:
            capt.decompose()
    return soup.get_text(separator="\n")


def extract_html_content(raw_html: str) -> str:
    try:
        return _bs4_extract(raw_html)
    except ImportError:
        parser = _HTMLTextExtractor()
        parser.feed(raw_html)
        return parser.get_text()


def extract_html_file(path: str) -> str | None:
    raw = read_text_file(path)
    if raw is None:
        return None
    return extract_html_content(raw)
