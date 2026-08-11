"""GFM table helpers for structure-preserving extraction."""
from __future__ import annotations
import re

_MD_SEPARATOR_RE = re.compile(r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*:?-{3,}:?\s*\|?\s*$")

def escape_cell(text: str) -> str:
    return (text or "").replace("\n", " ").replace("\r", " ").replace("|", "\\|").strip()

def rows_to_gfm(rows: list[list[str]], *, table_id: str | None = None) -> str:
    cleaned = []
    for row in rows:
        cells = [escape_cell(c) for c in row]
        if any(cells):
            cleaned.append(cells)
    if not cleaned:
        return ""
    width = max(len(r) for r in cleaned)
    normalized = [r + [""] * (width - len(r)) for r in cleaned]
    header, body = normalized[0], normalized[1:]
    lines = []
    if table_id:
        lines.append(f"<!-- table:{table_id} -->")
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join(["---"] * width) + " |")
    for row in body:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)

def tab_rows_to_gfm(lines: list[str], *, table_id: str | None = None) -> str:
    return rows_to_gfm([ln.split("\t") for ln in lines if ln.strip()], table_id=table_id)

def looks_like_gfm_table(text: str) -> bool:
    return any(_MD_SEPARATOR_RE.match(ln) for ln in text.splitlines())

def next_table_id(counter: list[int]) -> str:
    counter[0] += 1
    return f"T{counter[0]:02d}"
