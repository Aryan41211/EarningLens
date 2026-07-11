# Changelog

All notable changes to this project will be documented in this format.
Based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased] — Phase 1: PDF Extraction + Storage (in progress)

### Added
- `config.py` — Centralized paths, constants, filename pattern, chunking target, scoring dimensions
- `src/extraction/pdf_extractor.py` — PyMuPDF-based text extraction with `[PAGE_BREAK]` markers; filename metadata parser (`COMPANY_Q<n>_<year>.pdf`)
- `src/extraction/cleaner.py` — Boilerplate removal (page numbers, confidentiality, disclaimers, URLs); whitespace normalization
- `src/extraction/chunker.py` — Paragraph-aware chunking targeting ~600 words, never splits mid-paragraph
- `src/storage/db.py` — SQLite schema (`transcripts` table with company, quarter, year, chunk_index, chunk_text, word_count, source_file, extracted_at); CRUD (init, store, fetch by company/quarter/year)
- `scripts/run_phase1.py` — Orchestrates full pipeline: discovers PDFs in `data/raw_pdfs/`, extracts → cleans → chunks → stores; writes cleaned text to `data/processed/` for inspection
- `tests/test_extraction.py` — Unit tests for filename parsing, boilerplate cleaning, chunk size compliance
- `requirements.txt` — PyMuPDF, pytest

### Fixed
- Filename parser now raises `ValueError` with clear message for non-conforming PDFs (skip-and-continue in runner)

### Notes
- Phase 1 is **functional but not yet validated end-to-end** — run `python scripts/run_phase1.py` after dropping PDFs in `data/raw_pdfs/`

---

## [Unreleased] — Phase 2: Intelligence Engine (LLM Scoring)

*Planned — not started*

### To be added
- `src/scoring/` — LLM-based scoring across 5 dimensions (evasiveness, sentiment shift, overpromising, complexity spike, forward guidance vagueness)
- Prompt templates + few-shot examples derived from `notebooks/reading-notes.md`
- Scored chunks stored in new `scores` table (FK to transcripts)
- Evaluation harness against manual labels

---

## [Unreleased] — Phase 3: Cross-Quarter Comparison (Trend Detection)

*Planned — not started*

### To be added
- `src/trends/` — Time-series aggregation per company/dimension
- Trend metrics: slope, spike detection, quarter-over-quarter delta
- Alerting thresholds (configurable)
- `data/findings/findings.md` — First verified case study

---

## [Unreleased] — Phase 4: Dashboard (Streamlit)

*Planned — not started*

### To be added
- `src/dashboard/` — Streamlit app
- Company selector, quarter timeline, dimension sparklines
- Drill-down to chunk-level quotes driving scores
- Exportable finding cards