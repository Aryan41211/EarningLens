
# EarningsLens

AI system that reads Indian company earnings call transcripts and scores
management credibility across 5 dimensions, quarter over quarter, to warn
retail investors before red flags turn into stock price crashes.

[![Tests](https://github.com/Aryan41211/EarningLens/actions/workflows/test.yml/badge.svg)](https://github.com/Aryan41211/EarningLens/actions/workflows/test.yml)

## Status: Phase 1 (PDF extraction + storage) — in progress
[CHANGELOG](CHANGELOG.md) · [ARCHITECTURE](ARCHITECTURE.md)

## Project Structure

```
earningslens/
├── .github/workflows/     # CI: GitHub Actions runs tests on every push
├── ARCHITECTURE.md        # End-to-end data flow, design decisions, tradeoffs
├── config.py              # All paths and constants - single source of truth
├── data/
│   ├── raw_pdfs/          # Drop downloaded transcript PDFs here
│   ├── earningslens.db    # SQLite DB (created automatically, gitignored)
│   └── earningslens.log   # Structured log file (DEBUG+; gitignored)
├── src/
│   ├── extraction/        # PDF -> text -> clean -> chunks (Phase 1)
│   ├── storage/           # SQLite schema + CRUD (Phase 1)
│   ├── scoring/           # LLM scoring engine (Phase 2, not built yet)
│   ├── dashboard/         # Streamlit dashboard (Phase 3, not built yet)
│   └── utils/             # Logging, shared text cleaning helpers
├── scripts/
│   └── run_phase1.py      # Orchestrates extraction -> storage
└── tests/
    └── test_extraction.py
```

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in LLM API key when you get to Phase 2
```

## Running Phase 1

1. Rename your downloaded transcript PDFs to: `COMPANY_Q<n>_<year>.pdf`
   (e.g. `TCS_Q1_2025.pdf`, `INFY_Q3_2024.pdf`)
2. Put them in `data/raw_pdfs/`
3. Run:
   ```bash
   python scripts/run_phase1.py
   ```
4. Check `data/earningslens.db` for the extracted, chunked transcripts.

## Design rules

- Each module in `src/` does one job. Extraction never touches SQLite.
  Storage never touches PyMuPDF.
- `config.py` is the only place paths/constants live.
- No LangChain, LangGraph, or vector DBs — this project doesn't need them.
- `scripts/` only orchestrates; real logic always lives in `src/`.
- Structured logging via Python's `logging` module. Always use `logger`, never `print`.

## Notes & Findings

- [notebooks/reading-notes.md](notebooks/reading-notes.md) — Manual reading notes from 5+ transcripts; becomes the labeled test set for validating LLM scores in Phase 2.
- [data/findings/findings.md](data/findings/findings.md) — The single demonstrable example where trend detection would have flagged a company before a stock move; empty template awaiting a real case.

