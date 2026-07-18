# EarningsLens Architecture

## End-to-End Data Flow

```
data/raw_pdfs/      ──►  src/extraction/pdf_extractor.py   ──►  raw text
       │                                                              │
       │                                                    src/extraction/cleaner.py
       │                                                              │
       │                                                     clean text (no boilerplate)
       │                                                              │
       │                                                    src/extraction/chunker.py
       │                                                              │
       │                                                    ~600-word chunks
       │                                                              │
       └──────────────────────────►  src/storage/db.py  ◄─────────────┘
                                            │
                                     data/earningslens.db
                                     (transcripts table)
                                            │
                               ──►  src/scoring/ (Phase 2)
                                     LLM prompt + per-dimension scoring
                                            │
                                     data/earningslens.db
                                     (scores table + scoring_runs table)
                                            │
                               ──►  src/trends/ (Phase 3)
                                     cross-quarter aggregation
                                            │
                               ──►  src/dashboard/ (Phase 4)
                                     Streamlit dashboard
```

## Phase Map

| Phase | What it does | Status |
|-------|-------------|--------|
| 1 — Extraction | PDF → clean text → chunks → SQLite | Functional, not validated end-to-end |
| 2 — Scoring | LLM-based scoring across 5 dimensions via prompt | Not started |
| 3 — Trends | Cross-quarter aggregation, spike detection, alerting | Not started |
| 4 — Dashboard | Streamlit UI with company selector, sparklines, drill-down | Not started |

## Why SQLite instead of PostgreSQL

PostgreSQL solves concurrent writer workloads, network-accessible databases,
and terabyte-scale storage. This project has none of those requirements:

- Single-user (the developer runs the pipeline on one machine).
- Dataset is a few hundred transcripts at most. A SQLite file easily holds all
  extracted text, scores, and metadata.
- Zero operational overhead. No installation, no daemon, no connection pooling.

SQLite is the right choice until this project genuinely needs concurrent writes
or a network-accessible database — which, realistically, it never will.

## Why no Vector Database

Vector databases serve similarity search over embeddings (RAG, semantic search).
This project doesn't need either:

- Scoring is done by prompting an LLM with chunk text directly. No retrieval step.
- The "search" use case is filtering by company/quarter/year, which SQL handles
  natively with indexed columns.
- Adding a vector DB would introduce a second storage system for no benefit.

## Why no LangChain / LangGraph

LangChain and LangGraph are orchestration frameworks for complex LLM chains
and agent loops. This project's LLM interaction is a single prompt → score
per chunk:

- No chain-of-thought decomposition.
- No tool-calling.
- No multi-step agent reasoning.
- No conditional branching between LLM calls.

A direct `requests.post()` or `openai` client call is simpler, faster to debug,
and removes an entire dependency surface (version mismatches, abstractions that
leak, prompt template quirks). The scoring module will use the `openai` Python
package directly with a well-structured prompt.

## Scoring Dimensions

All five dimensions are defined in `config.py`:

1. **evasiveness** — LLM-based. Measures non-answers, deflection, overly vague responses.
2. **sentiment_shift** — LLM-based. Detects tone changes compared to previous quarters.
3. **overpromising** — LLM-based. Flags aggressive guidance, unrealistic targets.
4. **complexity_spike** — Rule + LLM hybrid. Uses Flesch readability (rule) + LLM judgment on jargon density.
5. **forward_guidance_vagueness** — LLM-based. Scores how specific/measurable forward-looking statements are.

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| `config.py` as single source of truth | Every path, regex, and constant lives here. No module hardcodes a path. |
| Extraction never touches storage | `src/extraction/` returns text. `src/storage/` persists it. They don't import each other. |
| `scripts/` only orchestrates | Scripts sequence calls. Real logic lives in `src/`. |
| `python-dotenv` at startup | Environment variables loaded once in `config.py`. No hardcoded secrets. |
| Structured logging to file + console | `data/earningslens.log` at DEBUG level, console at INFO. Makes debugging API calls feasible. |
| `scoring_runs` metadata table | Every LLM call is recorded with model name, prompt version, and raw JSON response. Enables auditing when scores change. |
| Filename-bound metadata | Company, quarter, year parsed from filename convention `COMPANY_Q<n>_<year>.pdf`. Consistent naming is a precondition. |
| Paragraph-aware chunking | Chunks respect paragraph boundaries. No sentence is split mid-way. Each chunk is self-contained for scoring. |
| PDF extraction validation | Extractions below 50 words are rejected with a logged warning. The pipeline continues with remaining files. |

## What is NOT in this architecture

- **Authentication / Authorization** — single-user research tool.
- **Vector Database** — no retrieval or RAG use case.
- **LangChain / LangGraph** — single-prompt scoring, no orchestration needed.
- **MLflow / Model Registry** — model choice is a config variable, not a tracking problem.
- **Message Queues** — pipeline is batch, not stream.
- **Docker / Kubernetes** — one Python script on one machine.
- **PostgreSQL** — SQLite covers the data volume.


soihfsioh 