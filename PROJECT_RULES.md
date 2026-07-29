# PROJECT_RULES.md

Hard constraints for this project. These are enforced by convention/review,
not by tooling — anyone (human or agent) working on this repo should treat
them as non-negotiable unless the user explicitly asks to change one.

## Architecture constraints

| Rule | Rationale |
|---|---|
| SQLite, not PostgreSQL | Single-user, small dataset — zero ops overhead |
| No vector DB | No retrieval use case — scoring is direct prompt + chunk |
| No RAG | Same as above — nothing to retrieve against |
| No LangChain / LangGraph | Single prompt → score per chunk; no agent loop or chain needed; direct OpenAI-compatible client is simpler to debug |
| No internal REST API | This is a batch CLI tool, not a service |
| `config.py` is the single source of truth | Every path/constant lives there; no module defines its own |
| Modules isolated by responsibility | Extraction never imports storage; storage never imports PyMuPDF; scoring never imports extraction |
| Scripts orchestrate only | Business logic lives in `src/`, never in `scripts/` |

## Scoring constraints

| Rule | Rationale |
|---|---|
| Exactly 5 scoring dimensions | Fixed checklist: evasiveness, sentiment shift, overpromising, complexity spike, forward guidance vagueness. No additions without explicit request. |
| Keyword matching restricted to Q&A chunks only | Prepared remarks trigger false positives via standard safe-harbor/forward-looking-statement boilerplate — validated in `EXPERIMENTS.md` |
| No chunk windowing for LLM scoring | Empirically validated that windowing (e.g. "first 3 + last 2" chunks) drops evidence — see `EXPERIMENTS.md` |
| Temperature 0.1 | Near-deterministic scoring for reproducibility |

## Data constraints

| Rule | Rationale |
|---|---|
| Filename convention `COMPANY_Q<n>_<year>.pdf` enforced by regex | Simpler than embedded metadata scanning; tradeoff is zero flexibility for variant naming (see `PROJECT_MEMORY.md` known issues) |
| Paragraph-aware chunking, never mid-sentence | Keeps chunks self-contained and coherent for LLM scoring |
| Minimum 50 extracted words to accept a PDF | Prevents empty/corrupt extractions from polluting the DB |
| Raw LLM responses always persisted | Full audit trail — model, prompt version, raw JSON — even before a clean `scores` table exists |

## Process constraints

| Rule | Rationale |
|---|---|
| Sequential phase progression | Do not start Phase N+1 until Phase N is implemented and its tests pass |
| No `print()` in `src/` | Use the structured logger everywhere in production code |
| Conventional Commits style | `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:` |

## Security rule (added, not in original notes but should be a standing rule)

- Never commit real secrets (API keys, tokens) into the repo — not even
  temporarily. `.env` must stay gitignored. If a secret is ever exposed in
  git history, rotate it immediately rather than just deleting the line.
