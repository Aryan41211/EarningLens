# TECH_STACK.md

## Language & runtime

- Python 3.11 (CI runs on `ubuntu-latest`)
- No web framework — this is a batch CLI pipeline, not a service

## Core libraries

| Library | Used for |
|---|---|
| PyMuPDF (`fitz`) | PDF text extraction |
| `openai` (SDK) | Chat completions client — points at Groq's OpenAI-compatible endpoint |
| `python-dotenv` | Loads `.env` at `config.py` import time |
| `sqlite3` (stdlib) | Persistence |
| `pandas` | Trend DataFrames (Phase 3) |
| `pytest` | Test runner |
| Streamlit + Plotly | Phase 4 dashboard — in `requirements-dashboard.txt` |

Pinned with compatible-release constraints:

```
# requirements.txt
pymupdf>=1.28.0,<2.0     pandas>=2.2.2,<3.0      pytest>=8.3.3,<9.0
python-dotenv>=1.2.1,<2.0                        openai>=2.44.0,<3.0

# requirements-dashboard.txt (optional)
streamlit>=1.56.0,<2.0   plotly>=6.7.0,<7.0
```

`mypy.ini` exists (targeting Python 3.12) but is not run in CI.

## LLM / AI components

- **Model**: configured via `LLM_MODEL_NAME`. Three have been used against the
  live DB — `llama-3.3-70b-versatile`, `openai/gpt-oss-20b`, `allam-2-7b` — and
  their scores are **not comparable** (`SCORING_METHODOLOGY.md` § 4). Pin one.
  **`llama-3.3-70b-versatile` has since been retired by Groq and now 404s**,
  so the currently configured value does not work at all
  (`KNOWN_ISSUES.md` BLOCKER-3).
- **Endpoint**: **Groq** at `https://api.groq.com/openai/v1`
  (OpenAI-compatible chat completions)
- **Temperature**: 0.1 (near-deterministic; run-to-run spread never measured)
- **Prompting**: one system prompt + one user prompt per batch, no
  multi-step/agentic reasoning
- **Batching**: ~2000 words per request to fit the free-tier 8000 TPM limit;
  batch scores are averaged into the stored score
- **Output**: JSON with a 1–10 score and up to 3 supporting quotes;
  `<think>` stripping, markdown-fence stripping, and 1–10 clamping on parse
- **Deterministic complement**: **42** dodge phrases in
  `src/scoring/evasiveness.py`, matched on Q&A chunks only (measured, not
  estimated — earlier docs said 63)

## Database

SQLite, single file at `data/earningslens.db`, no separate schema/migration
files — schema is created inline in `init_db()`. Full schema in
`DATASETS.md`.

## External services

| Service | Purpose | Notes |
|---|---|---|
| Groq API | LLM inference | Free tier — may rate-limit batch scoring across many transcripts |
| GitHub Actions | CI | `pytest tests/ -v` on every push/PR |

## Explicitly excluded from the stack

No LangChain/LangGraph, no vector database, no RAG/retrieval, no
PostgreSQL, no Docker/Kubernetes, no message queue, no MLflow, no
authentication layer. Rationale in `PROJECT_RULES.md`.

## Configuration

Everything lives in `config.py`:
- Paths: `PROJECT_ROOT`, `DATA_DIR`, `RAW_PDFS_DIR`, `PROCESSED_DIR`,
  `DB_PATH`, `LOG_PATH`
- Filename regex: `^([A-Za-z0-9&]+)_(Q[1-4])_(\d{4})$`
- `CHUNK_TARGET_WORDS = 600`
- `MIN_EXTRACTED_WORDS = 50`
- LLM: `LLM_API_KEY`, `LLM_API_BASE_URL`, `LLM_MODEL_NAME` (from `.env`)
- `COMPANIES = ["TCS", "INFY", "WIPRO", "HDFCBANK"]` (currently declared but
  not enforced anywhere in the pipeline — see PROJECT_MEMORY.md tech debt)
- 5 fixed scoring dimensions (see `PROJECT_RULES.md`)
