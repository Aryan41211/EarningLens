# DEVELOPMENT_GUIDE.md

## Setup

```bash
git clone <repo-url>
cd earningslens
pip install -r requirements.txt
cp .env.example .env   # fill in LLM_API_KEY, LLM_API_BASE_URL, LLM_MODEL_NAME
```

> ⚠️ Never commit a real key into `.env`. If one has ever been committed
> (even briefly), rotate it — deleting the line later does not remove it
> from git history. See `PROJECT_MEMORY.md`.

## Running the pipeline

```bash
# Phase 1 — drop PDFs into data/raw_pdfs/ named COMPANY_Q<n>_<year>.pdf
python scripts/run_phase1.py

# Phase 2 — manual evasiveness scoring for one company across all quarters
python scripts/run_evasiveness_test.py TCS
```

Phase 1 will: discover PDFs → parse filename metadata → extract text →
validate (≥50 words) → clean boilerplate → write inspection copy to
`data/processed/` → chunk (~600 words) → store to SQLite.

Phase 2 will: load chunks → detect Q&A boundary → run keyword matching →
call the LLM on Q&A chunks → persist to `scoring_runs`.

## Testing

```bash
pytest tests/ -v
```

CI (`.github/workflows/test.yml`) runs the same command on every push/PR
against Python 3.11 on Ubuntu. All LLM calls in tests are mocked — no
network calls happen in CI.

## Deployment

None planned. This is a local batch tool, not a service:

- No Docker, no Kubernetes
- No cloud deployment
- CI exists for testing only, not for shipping anything
- The "deployment" is: clone → `pip install` → run scripts locally

## Debug/analysis scripts

`scripts/_*.py` (underscore-prefixed) are ad-hoc, not part of the supported
CLI surface — used for things like token-cost estimation, chunk-window
validation, and DB status checks. See `EXPERIMENTS.md` for what they found.

## Before starting new work

Check `PROJECT_STATUS.md` for current phase state and `PROJECT_RULES.md`
for the constraint that Phase N+1 work shouldn't start until Phase N is
tested and green.
