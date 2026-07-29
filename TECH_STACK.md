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
| `pytest` | Test runner |
| Streamlit | *Planned* for Phase 4 dashboard — not yet added |

> TODO: confirm exact `requirements.txt` pinned versions — not visible in
> source notes.

## LLM / AI components

- **Model**: `llama-3.3-70b-versatile` served via **Groq** at
  `https://api.groq.com/openai/v1` (OpenAI-compatible chat completions)
- **Temperature**: 0.1 (near-deterministic)
- **Prompting**: single system prompt + user prompt per chunk, no
  multi-step/agentic reasoning
- **Output**: JSON with a 1–10 score and up to 3 supporting quotes;
  markdown-fence stripping and score clamping on parse
- **Deterministic complement**: dodge-phrase keyword matching (count varies
  40–65 across notes — TODO: verify exact list length in
  `src/scoring/evasiveness.py`) restricted to Q&A chunks only

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
