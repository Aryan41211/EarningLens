# Changelog

All notable changes to this project will be documented in this format.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased] — Phase 1: PDF Extraction + Storage

### Added
- **PDF extraction** (`src/extraction/pdf_extractor.py`): PyMuPDF-based text extraction with page/line tracking
- **Text cleaning** (`src/extraction/cleaner.py`): Header/footer removal, whitespace normalization, speaker-label normalization (e.g., "Management:", "Analyst:")
- **Smart chunking** (`src/extraction/chunker.py`): Speaker-aware chunking with configurable overlap; preserves speaker labels and page/line metadata
- **SQLite storage** (`src/storage/db.py`): Schema with tables for `transcripts`, `chunks`, and `metadata`; CRUD operations with upsert support
- **Config module** (`config.py`): Single source of truth for paths (raw_pdfs, processed, DB), chunking params, and filename parsing regex
- **Orchestration script** (`scripts/run_phase1.py`): End-to-end pipeline — discovers PDFs in `data/raw_pdfs/`, extracts → cleans → chunks → stores in `data/earningslens.db`
- **Extraction tests** (`tests/test_extraction.py`): Unit tests for PDF extraction, cleaning, and chunking logic

### Schema (Phase 1)
```sql
CREATE TABLE transcripts (
    id INTEGER PRIMARY KEY,
    company TEXT NOT NULL,
    quarter TEXT NOT NULL,
    year INTEGER NOT NULL,
    filename TEXT UNIQUE NOT NULL,
    total_pages INTEGER,
    total_chars INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE chunks (
    id INTEGER PRIMARY KEY,
    transcript_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    speaker TEXT,
    text TEXT NOT NULL,
    start_page INTEGER,
    end_page INTEGER,
    start_char INTEGER,
    end_char INTEGER,
    FOREIGN KEY (transcript_id) REFERENCES transcripts(id)
);

CREATE INDEX idx_chunks_transcript ON chunks(transcript_id);
```

### Filename convention enforced
`COMPANY_Q<n>_<year>.pdf` (e.g., `TCS_Q1_2025.pdf`, `INFY_Q3_2024.pdf`)

---

## [Unreleased] — Phase 2: Intelligence Engine (Scoring)

*Planned — not started*

### Planned
- LLM-based scoring engine (`src/scoring/`) for 5 dimensions:
  1. Evasiveness
  2. Sentiment shift
  3. Overpromising
  4. Complexity spike
  5. Forward guidance vagueness
- Prompt templates with few-shot examples (seeded from `notebooks/reading-notes.md`)
- Scoring pipeline: chunk-level → transcript-level aggregation
- Labeled test set creation from manual reading notes
- Measured metrics (precision/recall/F1) against labeled set — **no estimated numbers**

---

## [Unreleased] — Phase 3: Cross-Quarter Comparison (Trends)

*Planned — not started*

### Planned
- Trend computation (`src/trends/`): quarter-over-quarter deltas, rolling windows, anomaly detection
- Alerting thresholds (config-driven)
- Single demonstrable finding documented in `data/findings/findings.md`

---

## [Unreleased] — Phase 4: Dashboard & Packaging

*Planned — not started*

### Planned
- Streamlit dashboard (`src/dashboard/`): company selector, quarter timeline, 5-dimension score charts, trend alerts
- Exportable report (PDF/Markdown) per company
- `data/findings/findings.md` populated with one real, verifiable case study
- README + CHANGELOG finalized for portfolio/demo