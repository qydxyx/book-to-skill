<h1 align="center">book-to-skill</h1>

<p align="center">
  <strong>Turn books and docs into structured agent skills</strong> — frameworks, tables, figures, and charts your agent loads on demand (Copilot CLI, Amp, Claude Code).
</p>

<p align="center">
  <em>Improved fork of <a href="https://github.com/virgiliojr94/book-to-skill">virgiliojr94/book-to-skill</a> — with thanks to the original author and contributors.</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Agent_Skills-Open_Standard-blueviolet?style=for-the-badge" alt="Agent Skills standard">
  <img src="https://img.shields.io/badge/PDF%20%E2%80%A2%20EPUB%20%E2%80%A2%20DOCX%20%E2%80%A2%20MD%20%E2%80%A2%20HTML%20%E2%80%A2%20RTF%20%E2%80%A2%20MOBI-supported-green?style=for-the-badge" alt="Formats supported">
  <img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" alt="MIT License">
</p>

**24×–51× fewer tokens** than dumping a book into context ([how measured](docs/performance.md#the-discovery-loop-tax)).

1. **Point** — `/book-to-skill ./my-book.pdf` (file, folder, or glob)
2. **Distill** — frameworks, rules, anti-patterns, chapters, **markdown tables**, optional **figure inventory**
3. **Query** — `/my-book replication` loads only the relevant chapter (and figure notes when present)

---

## What it generates

Installs a skill under your agent’s skills dir (`~/.claude/skills/`, `~/.copilot/skills/`, or `~/.agents/skills/`):

| Output                                          | Role                                                            |
| ----------------------------------------------- | --------------------------------------------------------------- |
| `SKILL.md`                                      | Core models + chapter index (\~4K tokens)                       |
| `chapters/ch01-*.md` …                          | On-demand chapters: frameworks, tables, key figures (\~1K each) |
| `glossary.md` / `patterns.md` / `cheatsheet.md` | Terms, techniques, decision tables                              |

Extraction workdir (technical mode) also writes:

| Artifact                    | Role                                                                           |
| --------------------------- | ------------------------------------------------------------------------------ |
| `full_text.txt`             | Text + **GFM tables** (`<!-- table:Tnn -->`) + image/caption markers           |
| `figures.jsonl` + `assets/` | Figure inventory (kind, caption, alt, path) and copied binaries when available |
| `metadata.json`             | Size stats, `figures_high_value`, `multimodal_recommended`                     |

---

## Tables, figures & charts

- **Tables** — HTML / DOCX / Docling PDF / TSV grids → GFM with stable `<!-- table:Tnn -->` markers; feed chapter Reference Tables and `cheatsheet.md`.
- **Figures** — `--extract-figures` (default in `--mode technical`) → `figures.jsonl` + `assets/` (HTML/DOCX/EPUB; PDF often caption-only). Kind hints: chart, diagram, screenshot, table, photo. Decorative logos/icons skipped.
- **Charts & diagrams** — values/topology need a **multimodal** host model. Text-only keeps tables + captions/alt/OCR, discloses gaps, never invents numbers. Visual notes are **additive** to author-precise prose.

```bash
python3 scripts/extract.py ./guide.pdf --mode technical
python3 scripts/extract.py ./book.epub --extract-figures --vision ask
python3 scripts/extract.py ./book.pdf --mode technical --no-extract-figures
```

---

## Beyond books

Any structured prose you reopen often: internal docs, design systems, paper clusters, RFCs/specs. Multi-source fold-in is supported ([usage](docs/usage.md)).

---

## Install

```bash
git clone https://github.com/qydxyx/book-to-skill.git ~/.claude/skills/book-to-skill
# Copilot CLI: ~/.copilot/skills/ · Amp / cross-agent: ~/.agents/skills/
```

Hosts, optional extractors, standalone CLI → [docs/install.md](docs/install.md)

### Requirements (short)

```bash
python3 scripts/extract.py --check   # what’s installed + how to install missing tools
```

| Need                                  | Tool                                                   |
| ------------------------------------- | ------------------------------------------------------ |
| PDF prose                             | `pdftotext` / `pypdf` / `pdfminer.six`                 |
| PDF technical (tables, code, figures) | `docling`                                              |
| EPUB / HTML                           | `ebooklib` + `beautifulsoup4` (stdlib fallbacks exist) |
| DOCX / RTF                            | `python-docx` / `striprtf` (stdlib/regex fallbacks)    |
| MOBI/AZW                              | Calibre `ebook-convert`                                |
| Scanned PDF                           | OCR first: `ocrmypdf input.pdf output.pdf`             |

TXT / Markdown / RST / AsciiDoc need no extras. The skill asks technical vs text-heavy and picks the extractor.

---

## How it works & docs

**Extractor** (Python: document → text, tables, figures, metadata) + **generator** (agent follows `SKILL.md`). Chapters stay on disk until needed.

| Doc                                  |                                      |
| ------------------------------------ | ------------------------------------ |
| [How it works](docs/how-it-works.md) | Pipeline, modes, budgets             |
| [Usage](docs/usage.md)               | Full / analyze / fold-in             |
| [FAQ](docs/faq.md)                   | vs context dump, RAG, scans, visuals |
| [Performance](docs/performance.md)   | Discovery-loop tax                   |
| [Architecture](docs/architecture.md) | Component map                        |
| [Changelog](CHANGELOG.md)            | Releases                             |

```
book-to-skill/
├── SKILL.md                 # generator spec
├── scripts/extract.py
├── book_to_skill/           # extractor (tables.py, figures.py, parsers/)
├── tools/                   # discovery_tax, validate_skill
├── tests/ · docs/
```

---

## Credits

This project is based on **[virgiliojr94/book-to-skill](https://github.com/virgiliojr94/book-to-skill)** by [virgiliojr94](https://github.com/virgiliojr94) and contributors. Thank you for the original design, extractor, and Agent Skills workflow — this fork builds on that foundation with stronger **tables, figures, and chart** handling (GFM tables, figure inventory, multimodal-aware distillation).

Upstream: https://github.com/virgiliojr94/book-to-skill

## Copyright

Ships **no book content**. Local extraction; you supply files you may use. Output is structured notes, not a verbatim copy — don’t redistribute skills of third-party copyrighted books. MIT covers this repo’s code and skill definition only.

## License

MIT (same as upstream)
