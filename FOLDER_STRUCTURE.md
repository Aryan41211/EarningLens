# FOLDER_STRUCTURE.md

| Path | Responsibility |
|---|---|
| `config.py` | Single source of truth: paths, constants, filename regex, chunking/validation thresholds, scoring dimensions, LLM config |
| `src/extraction/pdf_extractor.py` | PyMuPDF text extraction (`[PAGE_BREAK]`-joined pages) + filename metadata parser |
| `src/extraction/chunker.py` | Paragraph-aware chunking targeting ~600 words; speaker-label fallback; sentence-boundary sub-splitting; never splits mid-sentence |
| `src/utils/text_cleaning.py` | Boilerplate stripping (page numbers, headers/footers, disclaimers, URLs; TCS/INFY-specific patterns) |
| `src/utils/logging.py` | Structured logging: DEBUG+ to file, INFO+ to console |
| `src/storage/db.py` | SQLite schema (`transcripts`, `scoring_runs`, `scores`) + CRUD; deletes stale chunks before re-insert. Note `transcripts` is a *chunks* table — see `KNOWN_ISSUES.md` HIGH-2 |
| `src/scoring/` | Phase 2 LLM scoring engine — all 5 dimension modules |
| `src/scoring/evasiveness.py` | Dual-method scoring: 42 dodge phrases (Q&A chunks only) + LLM call. Reference pattern for the other four |
| `src/scoring/_llm_dimension_scorer.py` | Shared LLM path: ~2000-word batching, exponential-backoff retry, `<think>` stripping, JSON parsing, 1–10 clamping. All 5 dimensions route through it |
| `src/scoring/sentiment_shift.py`, `complexity_spike.py`, `overpromising.py`, `forward_guidance_vagueness.py` | LLM-only dimensions — each is a system prompt plus thin delegation to the shared scorer |
| `src/scoring/__init__.py` | Orchestrator; the only file importing both scoring and storage |
| `src/trends/metrics.py` | Phase 3 — QoQ deltas, rolling 3-quarter averages, IMPROVING/STABLE/DETERIORATING labels, biggest-drop detection. Implemented; see `KNOWN_ISSUES.md` HIGH-3 / MEDIUM-1 for two correctness caveats |
| `src/dashboard/app.py` | Phase 4 Streamlit app — Scores / Trends / Alerts / Raw Data tabs |
| `scripts/run_phase1.py` | Orchestrates the full extraction → clean → chunk → store pipeline |
| `scripts/run_all_scoring.py` | Phase 2 runner for all 5 dimensions; `--company`, `--year`, `--dry-run`, `--skip-existing`, `--model` |
| `scripts/run_evasiveness_test.py` | Manual evasiveness runner: scores one company across all quarters |
| `scripts/run_validation_sample.py` | One transcript through all 5 dimensions, printed for human review |
| `scripts/run_trends.py` | Phase 3 CLI — **currently crashes on import**, see `KNOWN_ISSUES.md` BLOCKER-1 |
| `check_evasiveness.py` | Ad-hoc DB query script left in the repo root — violates the `scripts/` and no-`print` rules; should be moved or deleted |
| `tests/test_extraction.py` | Filename parsing, text cleaning, chunk sizing |
| `tests/test_scoring.py` | Keyword matching, Q&A detection, mocked LLM scoring |
| `tests/test_scoring_dimensions.py` | The 4 LLM-only dimensions, DB CRUD |
| `tests/test_trends.py` | QoQ deltas, rolling averages, trend labels, drop detection |
| `tests/test_integration.py` | End-to-end scoring pipeline with a mocked LLM |
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
