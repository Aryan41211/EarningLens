# SCORING_METHODOLOGY.md

How a transcript becomes five numbers, and the conditions under which those
numbers may be compared to each other. `ARCHITECTURE.md` covers where the code
lives; this file covers what the scoring actually means.

---

## 1. The scale

Every dimension uses the same 1–10 scale, and **higher is always worse** for
management credibility. This is what lets the trend layer treat all five
uniformly: a rising line is always a deteriorating signal.

| Band | Reading |
|---|---|
| 1–3 | Clean — direct, specific, grounded |
| 4–6 | Moderate — some hedging, partial specifics |
| 7–9 | Strong red flag — pervasive pattern |
| 10 | Extreme — the behaviour dominates the transcript |

Scores are clamped to `[1, 10]` and rounded to an integer in
`_llm_dimension_scorer.py`. A dimension that fails to parse stores nothing —
never a 0, never a default — so an absent row means "not scored", not "clean".

---

## 2. The five dimensions

| Dimension | What it detects | Method | Input scope |
|---|---|---|---|
| `evasiveness` | Dodges, non-answers, pivots to prepared remarks | Keyword matching **+** LLM | Q&A chunks only |
| `sentiment_shift` | Tone change: confident → hedged, optimistic → defensive | LLM only | All chunks |
| `complexity_spike` | Jargon density, nested qualifiers, obfuscation | LLM only | All chunks |
| `overpromising` | Aggressive targets, aspiration stated as certainty | LLM only | All chunks |
| `forward_guidance_vagueness` | Guidance with no numbers, timelines, or metrics | LLM only | All chunks |

Exactly five. Adding a sixth is a hard rule violation (`PROJECT_RULES.md`).

### Why evasiveness is scoped to Q&A only

Prepared remarks contain standard safe-harbour and forward-looking-statement
boilerplate that trips the dodge-phrase list — "going forward", "we remain
committed" — producing false positives on language that is legally required
rather than evasive. Evasiveness is a property of *answers*, so only the Q&A
section is scored. The boundary is found by `find_qa_start_index()`, four
regexes matching variants of "first question from the line of".

The other four dimensions describe the whole call and use every chunk.

### The deterministic half of evasiveness

`DODGE_PHRASES` holds **42** phrases. `score_evasiveness_keywords()` returns
counts, per-phrase frequency, and ±40 characters of context per hit. It is a
*diagnostic*, not a score: nothing in the pipeline converts keyword counts into
the stored score, and the human review found the correlation is weak — one
transcript had 19 keyword hits and a moderate score, another had 2 hits and the
same score. Treat the keyword output as evidence to read, not as a signal.

---

## 3. The LLM call

| Setting | Value | Where |
|---|---|---|
| Endpoint | Groq, OpenAI-compatible (`LLM_API_BASE_URL`) | `.env` |
| Temperature | 0.1 | `_llm_dimension_scorer.py` |
| `max_tokens` | 800 | `_llm_dimension_scorer.py` |
| Output | JSON: score + up to 3 verbatim supporting quotes | system prompt |
| Batch size | ~2000 words per request | `_BATCH_TARGET_WORDS` |
| Retry | 5 attempts, exponential backoff 2s → 60s, on 413/429/rate_limit | `_call_llm_with_retry` |

Response handling, in order: strip `<think>...</think>` blocks (some models emit
them), attempt `json.loads`, strip markdown fences and retry, validate the score
key is numeric, clamp to 1–10, keep at most 3 quotes.

### Batching and its consequence

A full transcript is ~8,000–9,000 words, well past the free-tier 8000 TPM limit,
so chunks are grouped into ~2000-word batches — typically 4–5 requests per
dimension per transcript. Each batch is scored independently and the batch
scores are **averaged**, then re-clamped and rounded.

This has an effect worth stating plainly: **the stored score is a mean of
independent partial judgments, not one judgment of the whole call.** Averaging
pulls scores toward the middle, which is consistent with the observed
distribution — 9 of 11 evasiveness scores land in the 4–6 band, none below 4,
none above 8. A dimension that is genuinely extreme in one section of a call is
diluted by the batches where it is absent.

Supporting quotes are concatenated across batches and truncated to the first 3,
so the stored quotes come from whichever batches happened to run first — they
are not the three strongest pieces of evidence in the transcript.

### Why not windowing

Sending only "first 3 + last 2" chunks was tested and rejected: it discarded
evasion evidence sitting in the middle of the Q&A. Full coverage, batched, is
the accepted cost. See `EXPERIMENTS.md`.

---

## 4. Comparability — the rule that makes trends valid

**A score is only comparable to another score produced by the same
`(model_name, prompt_version)` pair.**

Both fields are recorded on every row of `scores`, and nothing currently
enforces the rule. The database today holds evasiveness scores from three
different models, and the dashboard's top alert is a pure artifact of that mix
(`KNOWN_ISSUES.md` BLOCKER-2). Measured evidence of the size of the effect:
INFY Q1 2024 scored 6 under `llama-3.3-70b-versatile` and 2 under
`openai/gpt-oss-20b` — same chunks, same `evasiveness-v1` prompt.

Practical rules:

1. Pin one model in `.env` and score a full sweep with it. Do not mix models
   inside a dimension, ever.
2. Bump `prompt_version` whenever a system prompt changes. It is currently
   hard-coded as `f"{dimension}-v1"` in both runners — change the prompt and
   the version stops meaning anything.
3. Changing a model or a prompt invalidates the whole series for that
   dimension. Re-score everything; do not append.
4. Before reading any trend, check the slice is single-model:

```sql
SELECT dimension, model_name, prompt_version, COUNT(*)
FROM scores GROUP BY dimension, model_name, prompt_version;
```

---

## 5. What a score is not

- **Not calibrated.** No score has been checked against a human number. The
  only human review rated the LLM's accuracy at 4.6/10 on average
  (`EVALUATION.md`).
- **Not a measure of intent.** The prompt cannot distinguish "refusing to
  disclose, with a stated policy reason" from "dodging". The human reviewer
  repeatedly made that distinction; the model does not.
- **Not tone-aware.** A blunt refusal and a courteous one with reasons receive
  the same treatment.
- **Not stable across models.** See above.
- **Not yet known to be stable across runs.** Self-consistency at temperature
  0.1 has never been measured. Until it is, the `±1.5` trend thresholds in
  `src/trends/metrics.py` are unjustified — they may sit entirely inside the
  model's own noise.
- **Not a trading signal.** `data/findings/findings.md` is still empty by
  design; no score has ever been linked to a price move.

---

## 6. Audit trail

Every stored score keeps the raw LLM response (`scores.raw_llm_response`), and
`scoring_runs` keeps a parallel record with model, prompt version, and timestamp.
Any score can be traced back to the exact text the model returned. Keep it that
way — it is the only reason the model-mixing problem above was diagnosable
after the fact.

---

## 7. Changing the methodology

Anything in this file that changes must be recorded as a version bump:

| Change | Requires |
|---|---|
| Editing a system prompt | new `prompt_version`, full re-score of that dimension |
| Switching model | full re-score of every affected dimension |
| Changing `_BATCH_TARGET_WORDS` | full re-score — batch boundaries change the averaged result |
| Changing chunk size (`CHUNK_TARGET_WORDS`) | full re-ingest **and** re-score |
| Changing the 1–10 scale or band definitions | full re-score, and existing human labels become invalid |

Nothing here is enforced by tooling today. That is itself a gap — see
`ROADMAP.md`.
