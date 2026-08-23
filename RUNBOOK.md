# RUNBOOK.md

Operational reference: exact commands, in order, with what to check after each
and what to do when something goes wrong. `DEVELOPMENT_GUIDE.md` covers setting
up a dev environment; this file covers running the pipeline.

Commands assume the repo root as working directory and PowerShell or bash on
Windows. Every path comes from `config.py`.

---

## 0. Preconditions

```bash
pip install -r requirements.txt
pip install -r requirements-dashboard.txt   # only needed for Phase 4
cp .env.example .env                        # then fill it in
```

`.env` must contain all three values — a missing key or base URL makes every
scoring call return `{"error": "LLM not configured"}` and store nothing, with
only a WARNING in the log:

```
LLM_API_KEY=<groq key>
LLM_API_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL_NAME=llama-3.3-70b-versatile
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

> **Warning — read before re-running.** `store_transcript()` deletes and
> re-inserts chunks, which assigns new rowids. Because `scores.transcript_id`
> points at the first chunk's rowid, re-running this script **silently orphans
> every existing score** (`KNOWN_ISSUES.md` HIGH-2). Back up
> `data/earningslens.db` first, and plan to re-score afterwards.

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
python scripts/run_all_scoring.py --model llama-3.3-70b-versatile
```

`--skip-existing` skips a transcript only when **all five** dimensions are
present, so a partially-scored transcript is re-scored in full.

### Cost and time

A full sweep is 11 transcripts × 5 dimensions × ~4–5 batches ≈ **250 requests**
of roughly 2,500 tokens each. On Groq's free tier (8000 TPM) the built-in
backoff paces this; budget 20–40 minutes and do not run two sweeps
concurrently.

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

> **Currently broken** — `ModuleNotFoundError: No module named 'config'`
> (`KNOWN_ISSUES.md` BLOCKER-1). Until the `sys.path` line is added, reach the
> same numbers through the dashboard or directly:
>
> ```python
> import sqlite3
> from src.trends.metrics import load_scores_from_db, compute_trend_label
> print(compute_trend_label(load_scores_from_db(sqlite3.connect("data/earningslens.db"))))
> ```

When reading the output, remember two live defects: QoQ deltas ignore calendar
gaps (INFY's "quarter-over-quarter" jumps span up to six quarters), and rows are
ordered by period with companies interleaved.

---

## 4. Dashboard (Phase 4)

```bash
streamlit run src/dashboard/app.py
```

Opens on `http://localhost:8501`. Tabs: Scores, Trends, Alerts, Raw Data.

It reads the DB at startup only — restart after a scoring run. If it shows
"No scores found in database", the `scores` table is empty or every score has
been orphaned by a re-ingest (§ 1).

Treat the Alerts tab with suspicion until BLOCKER-2 is fixed: its current top
alert is a model-switch artifact, not a management signal.

---

## 5. Tests

```bash
python -m pytest tests/ -q          # 70 tests
python -m pytest tests/test_trends.py -v
```

Expect **1 failure** on a machine with a populated `.env`:
`test_sentiment_shift_score_key_in_result` makes a real API call
(`KNOWN_ISSUES.md` HIGH-1). CI passes only because it has no API key. Until
that is fixed, a clean local run needs the key temporarily unset.

Type checking is configured but not wired into CI:

```bash
mypy src/
```

---

## 6. Troubleshooting

| Symptom | Cause | Action |
|---|---|---|
| `ModuleNotFoundError: No module named 'config'` | Script missing the `sys.path.insert` prelude | Run from repo root; only `run_trends.py` is affected |
| Every score is `None`, log says "LLM not configured" | `LLM_API_KEY` or `LLM_API_BASE_URL` empty | Fill `.env`; `config.py` reads it at import time |
| `Rate limited ... retrying in Ns` | Groq free-tier TPM | Expected; backoff handles it. Persistent failure → lower `_BATCH_TARGET_WORDS` |
| "LLM returned invalid JSON" | Model emitted prose or an unstripped reasoning block | Check `scores.raw_llm_response`; some models need `<think>` stripping, which is already handled — a new pattern means a new model |
| Dashboard shows no data after scoring | Orphaned scores from a re-ingest, or the app was not restarted | Restart; then check for orphans (§ 7) |
| A transcript scored 1–2 chunks | Extraction or cleaning failure | Inspect `data/processed/<name>.txt`; a new publisher may need boilerplate patterns |
| Filename rejected | Does not match `COMPANY_Q<n>_<year>.pdf` | Rename; the regex has no fallback |

---

## 7. Health checks

```bash
# orphaned scores (should be 0)
python -c "import sqlite3; c=sqlite3.connect('data/earningslens.db'); print(c.execute('SELECT COUNT(*) FROM scores s LEFT JOIN transcripts t ON s.transcript_id=t.id WHERE t.id IS NULL').fetchone())"

# coverage: how many of the 5 dimensions each transcript has
python -c "import sqlite3; c=sqlite3.connect('data/earningslens.db'); [print(r) for r in c.execute('SELECT t.company,t.year,t.quarter,COUNT(DISTINCT s.dimension) FROM transcripts t JOIN scores s ON s.transcript_id=t.id GROUP BY t.company,t.year,t.quarter ORDER BY t.company,t.year,t.quarter')]"

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
