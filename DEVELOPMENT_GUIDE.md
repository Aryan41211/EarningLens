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

See **`RUNBOOK.md`** — it has the full command reference, cost estimates,
health checks, and troubleshooting. The short version:

```bash
python scripts/run_phase1.py                 # ingest
python scripts/run_all_scoring.py --dry-run  # always dry-run first
python scripts/run_all_scoring.py            # score
python scripts/run_trends.py                 # trends (currently broken)
streamlit run src/dashboard/app.py           # dashboard
```

## Testing

```bash
pytest tests/ -v
```

70 tests. **One fails locally** if `.env` has a real API key:
`test_sentiment_shift_score_key_in_result` is missing its mock and attempts a
live request (`KNOWN_ISSUES.md` HIGH-1). CI passes only because it has no key —
so a green badge does not currently guarantee a green local run.

CI (`.github/workflows/test.yml`) runs the same command on every push/PR against
Python 3.11 on Ubuntu. Every other LLM call in the suite is mocked.

`mypy.ini` is configured but not wired into CI; run `mypy src/` by hand.

## Deployment

None planned. This is a local batch tool, not a service:

- No Docker, no Kubernetes
- No cloud deployment
- CI exists for testing only, not for shipping anything
- The "deployment" is: clone → `pip install` → run scripts locally

## Debug/analysis scripts

The `scripts/_*.py` research scripts were removed in `31c5449`; their findings
survive in `EXPERIMENTS.md`. One ad-hoc script, `check_evasiveness.py`, still
sits in the repo root and should be moved into `scripts/` or deleted.

## Before starting new work

1. Read `KNOWN_ISSUES.md` — two blockers are open and one of them makes every
   trend number suspect.
2. Check `PROJECT_STATUS.md` for phase state and `ROADMAP.md` for the ordered
   next steps.
3. `PROJECT_RULES.md` holds the non-negotiables, including that Phase N+1 work
   shouldn't start until Phase N is tested and green. All four phases have
   shipped code; none has passed that bar yet, so the current work is
   *finishing* phases, not adding them.
4. Update the affected doc in the same commit as the behaviour change. This doc
   set has drifted from the code more than once.
