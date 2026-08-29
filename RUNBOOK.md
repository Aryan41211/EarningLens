# RUNBOOK.md

Operational reference: exact commands, in order, with what to check after each
and what to do when something goes wrong. `DEVELOPMENT_GUIDE.md` covers setting
up a dev environment; this file covers running the pipeline.

Commands assume the repo root as working directory and PowerShell or bash on
Windows. Every path comes from `config.py`.

---

## 0. Preconditions

```bash
pip install -e ".[dev,dashboard]"
cp .env.example .env                        # then fill it in
```

`pyproject.toml` is the single source of truth for dependencies — there are no
`requirements*.txt` files to drift from it. `.[dev]` adds the test tooling
(pytest, mypy, pre-commit); `.[dashboard]` adds the Phase 4 dashboard
(streamlit, plotly).

`.env` must contain all three values — a missing key or base URL makes every
scoring call return `{"error": "LLM not configured"}` and store nothing, with
only a WARNING in the log:

```
LLM_API_KEY=<groq key>
LLM_API_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL_NAME=openai/gpt-oss-120b
```

Confirm the model is actually reachable before scoring — provider model names
get retired, and a stale one 404s every call:

```bash
python scripts/check_models.py
```

`.env` is gitignored. If a key ever lands in a commit, rotate it — deleting the
line later does not remove it from history.

---

## 1. Ingest transcripts (Phase 1)

```bash
# 1. Name PDFs COMPANY_Q<n>_<year>.pdf and drop them in data/raw_pdfs/
python scripts/run_phase1.py
```

Per PDF: parse filename metadata → extract text → reject if under 50 words →
strip boilerplate → write a copy to `data/processed/` for inspection → chunk to
~600 words → store.

**Check afterwards:**

```bash
python -c "import sqlite3; c=sqlite3.connect('data/earningslens.db'); print(c.execute('SELECT company,quarter,year,COUNT(*),SUM(word_count) FROM transcripts GROUP BY company,quarter,year ORDER BY company,year,quarter').fetchall())"
```

Expect ~16–18 chunks and ~8,000–9,000 words per transcript. A transcript with
2 chunks means extraction or cleaning failed — read `data/processed/<name>.txt`
before scoring it.

> Re-running is safe: chunks are deleted and re-inserted, but scores carry
> their own `(company, quarter, year)` and survive the rowid change. Backing up
> `data/earningslens.db` first is still cheap insurance (§ 8) — the scores in it
> cost real API calls.

---

## 2. Score transcripts (Phase 2)

Always dry-run first — it costs nothing and tells you the call count:

```bash
python scripts/run_all_scoring.py --dry-run
```

Then:

```bash
python scripts/run_all_scoring.py                        # everything
python scripts/run_all_scoring.py --company TCS          # one company
python scripts/run_all_scoring.py --company INFY --year 2024
python scripts/run_all_scoring.py --skip-existing        # only transcripts missing all 5
python scripts/run_all_scoring.py --model openai/gpt-oss-120b
```

`--skip-existing` skips a transcript only when **all five** dimensions are
present, so a partially-scored transcript is re-scored in full.

### Cost and time

A full sweep is 11 transcripts × 5 dimensions × ~4–5 batches ≈ **250 requests**
of roughly 2,500 tokens each. On Groq's free tier (8000 TPM) the built-in
backoff paces this; budget 20–40 minutes and do not run two sweeps
concurrently.

### Budget: a full sweep does not fit in one day

Measured: ~20,000 tokens per dimension-score. Groq's free tier caps **tokens
per day at 200,000**. So a full 11 x 5 sweep is ~1.1M tokens — about five days
of quota (`KNOWN_ISSUES.md` BLOCKER-4). `--dry-run` prints the estimate:

```
Dimension-scores to produce: 55
Estimated tokens: ~1,100,000 (5.5 days of free-tier budget)
```

Scope the run to what fits, and build one *complete* series rather than five
partial ones — an incomplete series is worth nothing to the trend layer:

```bash
# one dimension across every transcript (~180k tokens, fits one day)
python scripts/run_all_scoring.py --dimension evasiveness --skip-scored
```

`--skip-scored` skips transcripts already scored **on the target model at the
prompt version this run would write**, so this command is the resume command
too: run it again after a quota exhaustion and it picks up exactly where it
stopped, never re-paying for finished work. Exit 3 means the budget is spent;
everything already written is kept. Safe to run on a loop or a scheduler — a
run with no budget costs one small failed call.

The prompt version is part of that check, not a detail. Matching on model alone
would treat a transcript scored at `evasiveness-v1` as finished during a v2
sweep, step over exactly the transcripts still needing work, and leave
permanent holes in the v2 series — silently, because a skip is not an error.

### Finishing a sweep unattended

The daily cap is a **rolling 24-hour window**, not a midnight reset, so
capacity frees up gradually as older usage ages out. `resume_sweep.py` turns
that into an unattended run: it calls the scorer, and on exit 3 waits and
retries until the sweep completes.

```bash
python scripts/resume_sweep.py --dimension evasiveness \
    --prompt-version evasiveness-v2 --wait-minutes 18 --max-hours 20
```

Ctrl-C at any point; scores already written are durable. A dimension across all
11 transcripts costs ~220k tokens, so expect roughly a full day of quota for
one dimension — the runner just removes the need to babysit it.

### Comparing two prompt versions properly

A prompt comparison needs **both** versions on the **same** transcripts and the
**same** model, so it takes two sweeps. Chain them with `&&` — the ordering is
the point. If v1 starts before v2 finishes, the day's quota is split across two
incomplete series and neither becomes a valid one:

```bash
python scripts/resume_sweep.py --dimension evasiveness \
    --prompt-version evasiveness-v2 --wait-minutes 18 --max-hours 24 && \
python scripts/resume_sweep.py --dimension evasiveness \
    --prompt-version evasiveness-v1 --wait-minutes 18 --max-hours 24 && \
python scripts/run_evaluation.py --dimension evasiveness \
    --compare evasiveness-v1 --compare evasiveness-v2
```

Roughly 360k tokens end to end, about 1.8 days of free-tier quota. The
comparison prints an IN-SAMPLE banner and restricts itself to transcripts
scored under both versions; read `EVALUATION.md` § 1.5 before quoting any of it.

### The rule that matters

**Do not mix models.** Every score in a dimension must come from one
`(model, prompt_version)` pair or the trend layer produces nonsense
(`SCORING_METHODOLOGY.md` § 4). Verify after every sweep:

```sql
SELECT dimension, model_name, prompt_version, COUNT(*)
FROM scores GROUP BY dimension, model_name, prompt_version;
```

More than one row per dimension means the series is invalid — re-score the
dimension with a single pinned model rather than patching individual rows.

### Single-transcript inspection

```bash
python scripts/run_validation_sample.py --company TCS --year 2025 --quarter Q1
```

Prints all five scores with supporting quotes and raw responses for manual
review.

---

## 3. Trends (Phase 3)

```bash
python scripts/run_trends.py                # all companies
python scripts/run_trends.py --company TCS
python scripts/run_trends.py --json
```

### Pick one comparable series

The `scores` table holds several `(model, prompt_version)` variants per
transcript. With no filter, the newest row per transcript wins, so a single
trend line can straddle a model switch. Hold both constant:

```bash
python scripts/run_trends.py \
    --model openai/gpt-oss-120b --prompt-version evasiveness-v2
```

The header echoes the restriction, and the contamination banner is evaluated
against the slice you selected — so a clean slice prints no banner. List what
variants exist:

```bash
sqlite3 data/earningslens.db \
  "SELECT model_name, prompt_version, COUNT(*) FROM scores GROUP BY 1,2;"
```

`--strict` exits 2 instead of printing trends built on scores that span more
than one model:

```bash
python scripts/run_trends.py --strict
```

A dimension with no scores in the selected slice is labelled `NO DATA`, not
`STABLE`. `STABLE` is a claim about the company; treat `NO DATA` as "nothing
was measured here".

Deltas are gap-aware: a delta is blank unless the two quarters are actually
adjacent, and a rolling 3-quarter average is blank unless its window covers
three consecutive quarters. A blank where you expected a number usually means a
missing quarter, not a missing score.

---

## 4. Dashboard (Phase 4)

```bash
streamlit run src/dashboard/app.py
```

Opens on `http://localhost:8501`. Tabs: Scores, Trends, Alerts, Raw Data.

It reads the DB at startup only — restart after a scoring run. If it shows
"No scores found in database", the `scores` table is empty.

Use the sidebar **Score variant** selector to pin one
`(model, prompt_version)`. "All variants (newest per transcript)" is the old
behaviour and mixes models; selecting a specific variant turns the display into
a real series and confirms it with a green note in the sidebar.

If the dimensions on show span more than one model, a red banner appears on the
Scores, Trends, and Alerts tabs naming the offenders. Do not read a delta while
that banner is showing — it is partly measuring the model change.

To serve it beyond localhost, see section 10.

---

## 5. Tests

```bash
python -m pytest tests/ -q          # 252 tests (measured 2026-08-29)
python -m pytest tests/test_trends.py -v
```

All 92 pass offline — every LLM call in the suite is mocked. If a test ever
reaches the network, that is a bug in the test, not an environment problem:
four tests once passed only because an earlier test left `LLM_API_KEY` blank
process-wide, and failed the moment they were run individually. Run a single
test standalone when you suspect this:

```bash
python -m pytest tests/test_scoring_dimensions.py::test_sentiment_shift_score_key_in_result -q
```

Type checking runs in CI and locally:

```bash
mypy src/
```

---

## 6. Troubleshooting

| Symptom | Cause | Action |
|---|---|---|
| `ModuleNotFoundError: No module named 'config'` | A script is missing the `sys.path.insert` prelude | Add it, as every script in `scripts/` has |
| `404 ... model does not exist or you do not have access` | The pinned model was retired by the provider | `python scripts/check_models.py`, pin a reachable one, then **re-score the whole series** |
| Every score is `None`, log says "LLM not configured" | `LLM_API_KEY` or `LLM_API_BASE_URL` empty | Fill `.env`; `config.py` reads it at import time |
| `Rate limited ... retrying in Ns` | Groq free-tier TPM | Expected; backoff handles it. Persistent failure → lower `_BATCH_TARGET_WORDS` |
| "LLM returned invalid JSON" | Model emitted prose or an unstripped reasoning block | Check `scores.raw_llm_response`; some models need `<think>` stripping, which is already handled — a new pattern means a new model |
| Dashboard shows no data after scoring | The app was not restarted, or the sweep stored nothing | Restart; then check coverage (§ 7) |
| A transcript scored 1–2 chunks | Extraction or cleaning failure | Inspect `data/processed/<name>.txt`; a new publisher may need boilerplate patterns |
| Filename rejected | Does not match `COMPANY_Q<n>_<year>.pdf` | Rename; the regex has no fallback |

---

## 7. Health checks

```bash
# scores missing their identity (should be 0)
python -c "import sqlite3; c=sqlite3.connect('data/earningslens.db'); print(c.execute('SELECT COUNT(*) FROM scores WHERE company IS NULL').fetchone())"

# coverage: how many of the 5 dimensions each transcript has (5 is complete)
python -c "import sqlite3; c=sqlite3.connect('data/earningslens.db'); [print(r) for r in c.execute('SELECT company,year,quarter,COUNT(DISTINCT dimension) FROM scores GROUP BY company,year,quarter ORDER BY company,year,quarter')]"

# model mixing (one row per dimension is the only healthy state)
python -c "import sqlite3; c=sqlite3.connect('data/earningslens.db'); [print(r) for r in c.execute('SELECT dimension,model_name,COUNT(*) FROM scores GROUP BY dimension,model_name')]"
```

Logs: `data/earningslens.log` (DEBUG and above; console shows INFO and above).

---

## 8. Backup

The database is gitignored and is the only place scores live — re-creating them
costs a full LLM sweep. Before any schema change or re-ingest:

```bash
cp data/earningslens.db data/earningslens.db.bak-$(date +%Y%m%d)
```

`data/processed/` is committed and can rebuild the chunk text without touching
the source PDFs; the scores cannot be rebuilt from anything but the API.

---

## 9. Scoring with evasiveness-v3 (per-exchange)

v3 scores each analyst exchange separately instead of averaging word-count
windows. It is **registered but unmeasured** — no transcript has been scored
with it. See KNOWN_ISSUES.md BLOCKER-6 for why it exists.

```bash
# Costs ~220k tokens, about 1.1 days of free-tier budget. Same as a v2 sweep.
python scripts/run_all_scoring.py --dimension evasiveness \
    --prompt-version evasiveness-v3

# Resume after the daily quota resets:
python scripts/run_all_scoring.py --dimension evasiveness \
    --prompt-version evasiveness-v3 --skip-scored
```

Then read the result **without spending any more quota**:

```bash
# Re-aggregates the stored per-exchange scores under every aggregator and
# measures each against the labels. Makes no LLM calls.
earningslens-aggregators

# The evaluation gate, on the v3 slice:
python scripts/run_evaluation.py --dimension evasiveness \
    --model openai/gpt-oss-120b --prompt-version evasiveness-v3
```

What to look for in `earningslens-aggregators`:

| Column | Meaning |
|---|---|
| `spread` | max transcript score minus min. **Near 0 is the BLOCKER-6 failure** — an aggregate that cannot rank anything. |
| `Spearman` | does it order transcripts like the reviewer did? |

- **Spread near 0 under every aggregator** → the model is not discriminating at
  the exchange level either. The rubric, not the aggregation, is the problem.
- **Healthy spread, Spearman still negative** → v3 separates transcripts but
  disagrees with the reviewer. Suspect the rubric, and read HIGH-10 before
  concluding anything: the labels score three quotes, not the whole call.

Do not pick the best-scoring aggregator and call it validated. Those 11 labels
informed v2's design and the v3 default was chosen to match how they were
built — that is selection on the test set (EVALUATION.md § 1.5).

The per-exchange scores are stored in `scores.raw_llm_response` as JSON, so any
aggregation question can be re-answered later for free:

```bash
python -c "
import json, sqlite3
c = sqlite3.connect('data/earningslens.db')
for co, q, y, raw in c.execute(\"SELECT company,quarter,year,raw_llm_response FROM scores WHERE prompt_version='evasiveness-v3'\"):
    p = json.loads(raw)
    print(co, q, y, [e['evasiveness_score'] for e in p['exchange_scores']])
"
```

### The full evasiveness-v3 campaign, end to end

These are the exact commands to run the unmeasured `evasiveness-v3` sweep,
re-aggregate it, and re-run the gate. Everything but step 3 (the sweep) is free
and offline. This is the path that decides whether v3 clears BLOCKER-6.

1. Set the key (new shells, or put it in the gitignored `.env`):
   ```bash
   setx LLM_API_KEY "sk-..."
   ```

2. Preview the cost without burning quota:
   ```bash
   python scripts/run_all_scoring.py --dimension evasiveness \
       --prompt-version evasiveness-v3 --dry-run
   # -> 11 scores, ~220,000 tokens, ~1.1 days of free-tier budget
   ```

3. Run the v3 sweep. Resume after a daily reset with `--skip-scored` (never
   re-pays finished work), or let `earningslens-resume` run it unattended:
   ```bash
   python scripts/run_all_scoring.py --dimension evasiveness \
       --prompt-version evasiveness-v3
   python scripts/resume_sweep.py --dimension evasiveness \
       --prompt-version evasiveness-v3 --wait-minutes 18 --max-hours 20
   ```

4. Aggregate + measure, no LLM calls:
   ```bash
   earningslens-aggregators --dimension evasiveness --prompt-version evasiveness-v3
   ```
   Read `spread` and `Spearman`:
   - spread ~ 0 under every aggregator -> the model does not discriminate at the
     exchange level either -> the rubric, not the aggregation, is the problem.
   - healthy spread, Spearman still negative -> v3 separates transcripts but
     disagrees with the reviewer -> suspect the rubric and read HIGH-10: the
     labels score three quotes, not the whole call.

5. Run the gate on the v3 slice:
   ```bash
   python scripts/run_evaluation.py --dimension evasiveness \
       --model openai/gpt-oss-120b --prompt-version evasiveness-v3
   ```

6. The likely real blocker is HIGH-10, not the model. Each label scores three
   selected quotes while the LLM scores the whole call. Signal that the labels
   are incommensurable -> have a reviewer score a whole call (or the same
   exchanges v3 scores) so the comparison is apples-to-apples. This is human
   work; do not fabricate labels.

7. Ship only on exit 0 (all four targets met in EVALUATION.md § 3.2). Until
   then the tool is for looking at data, not for credibility claims. `--no-gate`
   is for exploration, never a release step.

---

## 10. Deployment

### Before you deploy anything: the release gate

```bash
python scripts/run_evaluation.py --dimension evasiveness --against reviewed
echo $?
```

`0` means every target in EVALUATION.md § 3.2 was met. **Anything else means the
scores are not fit to present as a credibility signal.** Today this exits `3`
— see KNOWN_ISSUES.md BLOCKER-6. Exit codes:

| Code | Meaning |
|---|---|
| 0 | all four targets met |
| 1 | could not evaluate (no labels, no scores, no overlap) |
| 2 | refused — the requested slice spans several models |
| 3 | evaluated, and a target was missed or could not be measured |

`--against reviewed` reads `notebooks/labels.csv` only, so it needs no database
and reproduces on any checkout. That is the form CI runs. To gate on the live
database instead, name the slice:

```bash
python scripts/run_evaluation.py --dimension evasiveness     --model openai/gpt-oss-120b --prompt-version evasiveness-v2
```

Use `--no-gate` for exploratory runs. Never in a release step.

**A failing gate does not block deploying the dashboard as a tool** — the
trends, the raw quotes and the comparability banners are all honest. It blocks
presenting the scores as a validated credibility measure. Deploy it to look at
data, not to draw conclusions from it.

### Run the dashboard in Docker

```bash
docker build -t earningslens .
docker run --rm -p 8501:8501 -v "$PWD/data:/app/data" earningslens
```

Then open `http://localhost:8501`.

- **The volume mount carries the database.** `data/*.db` is gitignored and kept
  out of the image on purpose (`.dockerignore`), because it is data rebuilt by
  scoring, not part of the build. Without the mount the dashboard starts and
  says it has no scores.
- **The mounted directory must be writable by uid 10001.** `init_db()` opens
  the database read-write to apply schema migrations.
- **The image holds no API key.** `.env` is excluded from the build context, and
  the container never scores — it only reads. Nothing to leak, nothing to pass
  in.
- `$PORT` is honoured if the host assigns one (Render, Fly, Cloud Run).
- Health endpoint: `/_stcore/health`, also wired to Docker's `HEALTHCHECK`.

### Scoring is a host job, not a container job

Sweeps need `LLM_API_KEY` and burn provider quota against a per-day cap
(BLOCKER-4). Run them with `scripts/run_all_scoring.py` on the host as in
section 2, then restart the container to pick up the new database.

### What CI checks

| Job | Runs on | Checks |
|---|---|---|
| `test` | every push/PR | pytest, mypy, `compileall scripts/`, every console script starts |
| `image` | every push/PR | the image builds, holds no `.env` or `LLM_API_KEY`, and serves a healthy dashboard |
| `release-gate` | `workflow_dispatch` and `v*` tags | the evaluation gate above |
| `image-publish` | `workflow_dispatch` and `v*` tags, after `release-gate` | builds and pushes `aryankondekar/earningslens` to Docker Hub as `{version}` and `latest` |

The published image is `aryankondekar/earningslens` and comes only from this
project's own Dockerfile — nothing pre-existing is reused or pulled in. Both
`release-gate`-dependent jobs (`release-gate`, `image-publish`) are kept
off ordinary pushes for the same reason — while BLOCKER-6 is open `release-gate`
fails and `image-publish` is skipped, so CI topology, not convention, stops a
pre-evaluation image from being published.

Secrets to configure for publishing:
`DOCKERHUB_USERNAME` (the Docker Hub account owning `aryankondekar/earningslens`) and
`DOCKERHUB_TOKEN` (a fine-grained write token).
