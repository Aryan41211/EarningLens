# PROJECT_MEMORY.md

_A running log of history, known issues, technical debt, and risks — the
"what happened and why" file. Update this rather than letting context get
lost across sessions._

## Git history summary

- **Jul 12, 2026** — Initial commit (README only), then same-day bootstrap
  commit scaffolding the entire Phase 1 skeleton (config, extraction
  pipeline, SQLite storage, trend stubs, first test, `requirements.txt`).
- **Jul 12–17** — Phase 1 maturation: PDF validation, boilerplate cleanup,
  chunking, stale-chunk deduplication, ~30 commits.
- **~Jul 18–19** — Infrastructure: `.gitignore`, GitHub Actions CI,
  structured logging, `ARCHITECTURE.md`, `CHANGELOG.md`, `scoring_runs`
  table added.
- **Jul 19–25** — Phase 2 work: evasiveness dimension (keyword + LLM),
  scoring tests, CLI runner script. Noisy stretch of repeated
  `fix(config): validate environment loading` commits (20+) during LLM
  config debugging.
- **Jul 25–26** — Several generic "Updated project" commits adding
  research/validation scripts (`_db_status.py`, `_find_q2_2023_quotes.py`,
  `_validate_chunk_window.py`, `_analyze_qa_boilerplate.py`).
- Single branch (`main`), single remote (`origin/main`) throughout.

> **Verified defects now live in `KNOWN_ISSUES.md`** (rewritten 2026-08-23 from
> a live audit of the code and database). The lists below are kept for the
> historical/architectural context they carry; where the two disagree,
> `KNOWN_ISSUES.md` is measured and this file is remembered.

## Known issues

- **Filename rigidity**: any PDF not matching `COMPANY_Q<n>_<year>.pdf` is
  rejected outright — no fallback for variant naming.
- **Q&A detection false negatives**: current regex patterns are tuned to
  common Indian earnings-call phrasing; different moderator/host styles may
  not be caught.
- **Keyword false positives risk**: boilerplate patterns are TCS/INFY-tuned;
  onboarding new companies may need additional pattern tuning.
- **`scores` table exists but 4 of 5 dimensions unvalidated**: per-dimension
  scores are stored in the `scores` table, but only evasiveness has been
  validated against real transcripts. The other 4 dimensions have zero
  production validation.
- **Extraction not fully end-to-end verified**: nobody has confirmed exact
  expected chunk counts across all 11 PDFs against the pipeline output.
- **Stray artifacts**: an old `cleaner.py` wrapper was removed in favor of
  direct imports from `text_cleaning.py`, but a corresponding
  `__pycache__` artifact may still linger — harmless but worth a clean.
- **`.deepeval` directory exists but is empty** — suggests an evaluation
  framework was scaffolded but never actually set up.

## Technical debt

_Refreshed 2026-08-23. Struck items were resolved in the audit; see
`KNOWN_ISSUES.md` for the status table._

**Open**

- **Evasiveness scoring does not reproduce human judgement** — Spearman 0.10
  against 11 labels. The prompt cannot tell a reasoned refusal from a dodge.
  This is the substantive problem the project now has (`EVALUATION.md`).
- **`scores` mixes four models**, so no stored series is yet valid. Detected
  and announced, but the data still needs a single-model sweep (BLOCKER-2/4).
- **A full re-scoring sweep costs ~5 days of free-tier quota** (BLOCKER-4).
- 4 of 5 dimensions have 1–5 data points and no human review at all.
- No `pyproject.toml`, `.pre-commit-config.yaml`, or `.editorconfig`.
- CI is single-config (no matrix testing, no coverage reporting).

**Resolved**

- ~~`src/trends/metrics.py` functions are stubs~~ — implemented `d2f7a99`;
  the CLI that wrapped them, which had never once run, fixed `a1e05ca`.
- ~~`scores.transcript_id` is a chunk rowid; a Phase 1 re-run orphans every
  score~~ — identity columns added and backfilled `20c5842`.
- ~~No evaluation harness, and the labels are prose not numbers~~ — harness
  built `918b8dd`; the labels turned out to exist all along `1ddea00`.
- ~~`config.COMPANIES` declared but unused~~ — removed `6732851`.
- ~~No type checking configured~~ — mypy runs in CI, `scripts/` byte-compiled.

## Risks

- **Security — previously flagged, resolved**: git history was checked for
  API key exposure (T0). No `.env` was ever committed and no actual key
  values appear in git history. The `.env` file is properly gitignored.
- **Groq free-tier rate limits** could bottleneck batch scoring once more
  transcripts or dimensions are added.
- **Single point of failure on Q&A regex detection** — see Known Issues.
- **Evaluation run, result negative.** Evasiveness scores measured against the
  11 human labels fail all four targets, most importantly Spearman 0.10 — the
  model barely ranks transcripts in the human's order. Do not treat any current
  score as accurate. See `EVALUATION.md` § 0.
- **Model drift inside the data.** Scores were produced across at least three
  models over several sessions with no re-scoring in between. INFY Q1 2024
  evasiveness reads 6 in the review notes and 2 in the DB today. Any analysis
  written against the current DB will be wrong in ways that look plausible.
- **Commit history noise** makes `git log` a weak tool for understanding
  intent during this period — rely on this file and `ROADMAP.md`/
  `PROJECT_STATUS.md` instead of archaeology through commits where possible.

## Source note

This documentation set was reconstructed from two independent AI-generated
project understanding reports (dated ~Jul 26, 2026), which disagreed on a
few minor specifics (exact dodge-phrase count, project name spelling). Where
they conflicted, this doc set picked the more consistent/detailed version
and flagged the rest as `TODO: verify` inline in the relevant file. Treat
this whole set as a first draft to be corrected against the actual codebase.
