# DEVELOPMENT_GUIDE.md

## Setup

```bash
git clone https://github.com/Aryan41211/EarningLens && cd EarningLens
pip install -e ".[dev,dashboard]"
cp .env.example .env       # fill in LLM_API_KEY, LLM_API_BASE_URL, LLM_MODEL_NAME
pre-commit install         # optional, but cheap
```

`requirements.txt` and `requirements-dashboard.txt` remain for anyone who
prefers them; `pyproject.toml` is the source of truth for dependencies.

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

CI (`.github/workflows/test.yml`) runs on every push/PR against Python 3.11 and
3.12: `pytest`, `mypy src/`, a byte-compile of `scripts/`, and a smoke test of
the console scripts. Every LLM call in the suite is mocked.

Tool configuration lives in `pyproject.toml` (`[tool.pytest.ini_options]`,
`[tool.mypy]`) — `mypy.ini` was folded into it.

## Deployment

Still a local batch tool, not a service — no Docker, no Kubernetes, no cloud
deployment, and CI tests rather than ships. What changed is that "clone →
pip install → run" is now a real, verified path rather than an aspiration:

```bash
pip install -e ".[dashboard]"
earningslens-score --dry-run
```

CI installs the package the same way and smoke-tests the console scripts on
Python 3.11 and 3.12, so a broken `pyproject.toml` or a dead entry point fails
there instead of on someone's machine.

**Packaging note.** The distribution installs top-level `src`, `scripts` and
`config`, which is not how a package bound for PyPI should be laid out. It is
deliberate: every module imports `from config import ...` and `from src.x
import ...`, and `PROJECT_RULES.md` pins `config.py` at the root. Renaming to a
real `earningslens/` package would touch every import and every doc for no
benefit to a single-user tool in its own venv. If this is ever published, that
rename is the first thing to do.

## Debug/analysis scripts

The `scripts/_*.py` research scripts were removed in `31c5449`; their findings
survive in `EXPERIMENTS.md`. `scripts/check_db_status.py` is the surviving
ad-hoc DB inspector — not a supported CLI, and the only place `print()` is
acceptable.

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
