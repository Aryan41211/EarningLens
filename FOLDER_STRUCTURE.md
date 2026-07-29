# FOLDER_STRUCTURE.md

| Path | Responsibility |
|---|---|
| `config.py` | Single source of truth: paths, constants, filename regex, chunking/validation thresholds, scoring dimensions, LLM config |
| `src/extraction/pdf_extractor.py` | PyMuPDF text extraction (`[PAGE_BREAK]`-joined pages) + filename metadata parser |
| `src/extraction/chunker.py` | Paragraph-aware chunking targeting ~600 words; speaker-label fallback; sentence-boundary sub-splitting; never splits mid-sentence |
| `src/utils/text_cleaning.py` | Boilerplate stripping (page numbers, headers/footers, disclaimers, URLs; TCS/INFY-specific patterns) |
| `src/utils/logging.py` | Structured logging: DEBUG+ to file, INFO+ to console |
| `src/storage/db.py` | SQLite schema (`transcripts`, `scoring_runs`) + CRUD; deletes stale chunks before re-insert |
| `src/scoring/` | Phase 2 LLM scoring engine — currently only `evasiveness.py` implemented |
| `src/scoring/evasiveness.py` | Dual-method scoring: deterministic keyword matching + LLM call via Groq |
| `src/trends/metrics.py` | Phase 3 stubs: QoQ delta, rolling averages, trend labels, drop detection — all `NotImplementedError` |
| `src/dashboard/` | Phase 4 — empty `__init__.py`, Streamlit app not started |
| `scripts/run_phase1.py` | Orchestrates the full extraction → clean → chunk → store pipeline |
| `scripts/run_evasiveness_test.py` | Manual Phase 2 runner: scores a company across all quarters |
| `scripts/_*.py` | Research/validation scripts (token analysis, chunk-window validation, quote cross-referencing, DB status) — not user-facing, underscore-prefixed by convention |
| `tests/test_extraction.py` | Filename parsing, text cleaning, chunk sizing |
| `tests/test_scoring.py` | Keyword matching, Q&A detection, mocked LLM scoring |
| `data/raw_pdfs/` | Dropzone for input PDFs (gitignored, never committed) |
| `data/processed/` | Cleaned text output for manual inspection |
| `data/earningslens.db` | SQLite database (gitignored) |
| `data/earningslens.log` | Structured log file (gitignored) |
| `data/findings/findings.md` | Template for a verified trend-to-stock-move case study |
| `notebooks/reading-notes.md` | Manual transcript reading notes — intended to become the labeled test set for Phase 2 evaluation |
| `.github/workflows/test.yml` | CI: `pytest tests/ -v` on every push/PR, Python 3.11, Ubuntu |
| `.env` | API keys and model config (gitignored — see PROJECT_MEMORY.md for a flagged exposure risk) |

## Naming convention

Input PDFs must match `COMPANY_Q<n>_<year>.pdf`, validated against
`^([A-Za-z0-9&]+)_(Q[1-4])_(\d{4})$` in `config.py`. Non-conforming files are
skipped/rejected — see `PROJECT_MEMORY.md` known issues for the tradeoffs of
this rigidity.
