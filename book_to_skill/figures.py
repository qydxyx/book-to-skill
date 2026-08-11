"""Figure inventory: deterministic asset/caption capture. No VLM calls."""
from __future__ import annotations
import json, re, shutil, zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET
from book_to_skill.config import OUTPUT_ASSETS, OUTPUT_FIGURES

_CAPTION_RE = re.compile(r"^\s*(?:figure|fig\.?|exhibit|图|圖|図)\s*[-.:]?\s*\d+", re.I)
_CHART = re.compile(r"\b(chart|graph|plot|histogram|scatter|trend)\b", re.I)
_DIAG = re.compile(r"\b(diagram|architecture|flowchart|pipeline|schema|uml|sequence)\b", re.I)
_SCREEN = re.compile(r"\b(screenshot|screen shot|ui|mockup|wireframe)\b", re.I)
_TABLE = re.compile(r"\b(table|matrix|comparison)\b", re.I)
_DECOR = re.compile(r"\b(logo|icon|spacer|bullet|ornament|decoration|cover)\b", re.I)
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".tif", ".tiff"}

@dataclass
class FigureRecord:
    id: str
    source: str
    path: str | None = None
    page: int | str | None = None
    anchor: str | None = None
    caption: str = ""
    alt: str = ""
    nearby_heading: str = ""
    kind_hint: str = "unknown"
    ocr_text: str = ""
    skipped_reason: str = ""
    extra: dict = field(default_factory=dict)
    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v not in ("", None, {}, [])}

def guess_kind_hint(*, alt="", caption="", nearby_heading="") -> str:
    blob = " ".join(p for p in (alt, caption, nearby_heading) if p)
    if not blob.strip():
        return "unknown"
    if _TABLE.search(blob): return "table"
    if _CHART.search(blob): return "chart"
    if _DIAG.search(blob): return "diagram"
    if _SCREEN.search(blob): return "screenshot"
    if _DECOR.search(blob): return "photo"
    if _CAPTION_RE.match(caption or alt or ""): return "diagram"
    return "unknown"

def is_likely_decorative(rec: FigureRecord) -> bool:
    blob = " ".join(p for p in (rec.alt, rec.caption, rec.nearby_heading) if p)
    if _DECOR.search(blob):
        return True
    name = (rec.path or rec.anchor or "").lower()
    if not rec.alt and not rec.caption:
        return any(t in name for t in ("logo", "icon", "spacer", "bullet", "ornament", "cover"))
    return False

def ensure_assets_dir(base: Path | None = None) -> Path:
    root = Path(base) if base is not None else OUTPUT_ASSETS
    root.mkdir(parents=True, exist_ok=True)
    return root

def write_figures_jsonl(records: Iterable[FigureRecord], path: Path | None = None) -> Path:
    out = Path(path) if path is not None else OUTPUT_FIGURES
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(r.to_dict(), ensure_ascii=False) for r in records]
    out.write_text(("\n".join(lines) + ("\n" if lines else "")), encoding="utf-8")
    return out

def figure_stats(records: list) -> dict:
    by_kind, high = {}, 0
    for rec in records:
        if isinstance(rec, FigureRecord):
            kind = rec.kind_hint or "unknown"
            deco = is_likely_decorative(rec) or rec.skipped_reason == "decorative"
        else:
            kind = rec.get("kind_hint") or "unknown"
            deco = rec.get("skipped_reason") == "decorative"
        by_kind[kind] = by_kind.get(kind, 0) + 1
        if kind in {"chart", "diagram", "screenshot", "table"} and not deco:
            high += 1
    return {"figures_total": len(records), "figures_high_value": high, "figures_by_kind": by_kind}

def summarize_figures_for_metadata(records: list[FigureRecord]) -> dict:
    s = figure_stats(records)
    s.update({
        "figures_jsonl": str(OUTPUT_FIGURES),
        "figures_assets_dir": str(OUTPUT_ASSETS),
        "multimodal_recommended": s["figures_high_value"] > 0,
    })
    return s

def _copy_bytes(data: bytes, dest: Path) -> str:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return str(dest)

def extract_figures_from_html(raw_html: str, *, source: str, assets_dir: Path | None = None,
                              id_prefix: str = "fig", start_index: int = 1, base_dir: Path | None = None):
    records, idx, nearby = [], start_index, ""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(raw_html, "html.parser")
        for el in soup.find_all(["h1","h2","h3","h4","h5","h6","img","figure"]):
            name = el.name.lower()
            if name.startswith("h"):
                nearby = el.get_text(" ", strip=True); continue
            if name == "figure":
                img = el.find("img"); cap = el.find("figcaption")
                alt = (img.get("alt") or "").strip() if img else ""
                src = (img.get("src") or "").strip() if img else ""
                caption = cap.get_text(" ", strip=True) if cap else ""
            else:
                if el.find_parent("figure") is not None:
                    continue
                alt = (el.get("alt") or "").strip(); src = (el.get("src") or "").strip(); caption = ""
            path = None
            if assets_dir and src and not src.lower().startswith(("http://","https://","data:")):
                cand = (base_dir / src).resolve() if base_dir else Path(src)
                try:
                    if cand.is_file() and cand.suffix.lower() in _IMAGE_EXTS:
                        dest = assets_dir / f"{id_prefix}-{idx:03d}{cand.suffix.lower()}"
                        shutil.copy2(cand, dest); path = str(dest)
                except OSError:
                    path = None
            rec = FigureRecord(id=f"{id_prefix}-{idx:03d}", source=source, path=path, anchor=src or None,
                              alt=alt, caption=caption, nearby_heading=nearby,
                              kind_hint=guess_kind_hint(alt=alt, caption=caption, nearby_heading=nearby))
            if is_likely_decorative(rec):
                rec.skipped_reason = "decorative"
            records.append(rec); idx += 1
        return records, idx
    except ImportError:
        pass
    for m in re.finditer(r"<img\b([^>]*)/?>", raw_html, flags=re.I):
        attrs = m.group(1)
        alt_m = re.search(r"\balt\s*=\s*(['\"])(.*?)\1", attrs, flags=re.I|re.S)
        src_m = re.search(r"\bsrc\s*=\s*(['\"])(.*?)\1", attrs, flags=re.I|re.S)
        alt = (alt_m.group(2) if alt_m else "").strip()
        src = (src_m.group(2) if src_m else "").strip()
        rec = FigureRecord(id=f"{id_prefix}-{idx:03d}", source=source, anchor=src or None, alt=alt,
                          kind_hint=guess_kind_hint(alt=alt))
        if is_likely_decorative(rec):
            rec.skipped_reason = "decorative"
        records.append(rec); idx += 1
    return records, idx

def extract_figures_from_docx(docx_path: str, *, assets_dir: Path | None = None, id_prefix="fig", start_index=1):
    records, idx, path = [], start_index, Path(docx_path)
    try:
        with zipfile.ZipFile(path) as zf:
            caps = []
            try:
                root = ET.fromstring(zf.read("word/document.xml"))
                ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
                for p in root.iter(f"{ns}p"):
                    line = "".join(t.text for t in p.iter(f"{ns}t") if t.text).strip()
                    if line and _CAPTION_RE.match(line):
                        caps.append(line)
            except Exception:
                caps = []
            for media_name in sorted(n for n in zf.namelist() if n.startswith("word/media/")):
                ext = Path(media_name).suffix.lower()
                if ext not in _IMAGE_EXTS:
                    continue
                caption = caps.pop(0) if caps else ""
                alt = Path(media_name).stem.replace("_"," ").replace("-"," ")
                dest = None
                if assets_dir is not None:
                    dest = _copy_bytes(zf.read(media_name), assets_dir / f"{id_prefix}-{idx:03d}{ext}")
                rec = FigureRecord(id=f"{id_prefix}-{idx:03d}", source=str(path), path=dest, anchor=media_name,
                                  alt=alt, caption=caption, kind_hint=guess_kind_hint(alt=alt, caption=caption))
                if is_likely_decorative(rec):
                    rec.skipped_reason = "decorative"
                records.append(rec); idx += 1
    except (zipfile.BadZipFile, OSError, KeyError):
        return records, idx
    return records, idx

def extract_figures_from_epub(epub_path: str, *, assets_dir: Path | None = None, id_prefix="fig", start_index=1):
    records, idx, path = [], start_index, Path(epub_path)
    try:
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            for name in sorted(names):
                ext = Path(name).suffix.lower()
                if ext not in _IMAGE_EXTS:
                    continue
                dest = None
                if assets_dir is not None:
                    dest = _copy_bytes(zf.read(name), assets_dir / f"{id_prefix}-{idx:03d}{ext}")
                alt = Path(name).stem.replace("_"," ").replace("-"," ")
                rec = FigureRecord(id=f"{id_prefix}-{idx:03d}", source=str(path), path=dest, anchor=name, alt=alt,
                                  kind_hint=guess_kind_hint(alt=alt))
                if is_likely_decorative(rec):
                    rec.skipped_reason = "decorative"
                records.append(rec); idx += 1
            for name in names:
                if not name.endswith((".html",".xhtml",".htm")):
                    continue
                try:
                    raw = zf.read(name).decode("utf-8", errors="replace")
                except Exception:
                    continue
                html_recs, idx = extract_figures_from_html(raw, source=f"{path}#{name}", assets_dir=None,
                                                           id_prefix=id_prefix, start_index=idx)
                existing = {r.anchor for r in records if r.anchor}
                for rec in html_recs:
                    if rec.anchor in existing and not rec.caption and not rec.alt:
                        continue
                    # enrich matching asset alt/caption
                    for r in records:
                        if r.anchor and rec.anchor and (r.anchor.endswith(rec.anchor) or rec.anchor.endswith(Path(r.anchor).name)):
                            if rec.alt and not r.alt: r.alt = rec.alt
                            if rec.caption and not r.caption: r.caption = rec.caption
                            r.kind_hint = guess_kind_hint(alt=r.alt, caption=r.caption)
                            if is_likely_decorative(r): r.skipped_reason = "decorative"
                            break
                    else:
                        records.append(rec)
    except (zipfile.BadZipFile, OSError):
        return records, idx
    return records, idx


def load_figures_jsonl(path=None):
    import json
    src = Path(path) if path is not None else OUTPUT_FIGURES
    if not src.exists():
        return []
    out = []
    for line in src.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out
