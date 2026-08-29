"""Per-exchange LLM scoring: one score per analyst question, not per transcript.

Why this exists (KNOWN_ISSUES.md BLOCKER-6)
-------------------------------------------
`_llm_dimension_scorer.score_dimension_llm()` splits a transcript into
~2000-word batches, asks each batch to judge the *whole call*, and averages the
verdicts. Two things go wrong:

1. The batch is not a meaningful unit. It starts and ends mid-question, so the
   model is asked to judge a call from an arbitrary window of it.
2. Averaging destroys the range. Measured on the 7 evasiveness-v2 transcripts,
   per-batch verdicts span 3-8 and every stored average is 5 or 6. A mean of N
   noisy judgements is narrower than the judgements themselves, by
   construction, and a scorer whose output spans one point cannot rank
   anything.

This module scores the unit management is actually judged on: one analyst's
question and the answer it received. Several exchanges still travel in one
request -- the free-tier TPM ceiling has not moved -- but the model returns a
*separate* score per exchange rather than one blended number, and the
aggregation into a transcript score happens in code, where it is explicit,
testable, and changeable without re-spending quota.

Every per-exchange score is kept. That is the point: a sweep costs ~5 days of
free-tier budget (BLOCKER-4), so the expensive part must be paid once and every
aggregation question answered offline afterwards.

The retry, quota and JSON-recovery helpers are shared with the batch scorer
rather than duplicated -- this module changes the unit of judgement, not the
transport.
"""

import json
import logging
import re

from src.scoring._llm_dimension_scorer import (
    DailyQuotaExhausted,  # noqa: F401  (re-exported: callers catch it from here)
    _batch_chunks,
    _call_llm_with_retry,
    _extract_usage,
    _finish_reason,
    _parse_llm_json,
    _strip_thinking_tags,
)

logger = logging.getLogger("earningslens")

# Words of transcript per request. Matches the batch scorer's ceiling, which is
# set by the free tier's 8000 TPM limit rather than by anything about quality.
_BATCH_TARGET_WORDS = 2000

# Output budget. Each exchange costs roughly a score, an index and a short
# quote; the floor covers the JSON scaffolding itself.
_TOKENS_PER_EXCHANGE = 250
_MIN_OUTPUT_TOKENS = 500
_MAX_OUTPUT_TOKENS = 6000


def _output_budget(n_exchanges: int) -> int:
    """Token allowance for a request carrying n_exchanges."""
    return max(
        _MIN_OUTPUT_TOKENS,
        min(_MAX_OUTPUT_TOKENS, 300 + _TOKENS_PER_EXCHANGE * n_exchanges),
    )


def build_exchange_prompt(exchanges: list[str], start_index: int) -> str:
    """Number the exchanges so scores can be matched back to them.

    The numbering is global across the transcript, not per request, so a score
    always points at the same exchange regardless of how the batching fell.
    """
    blocks = [
        f"[EXCHANGE {start_index + i}]\n{text.strip()}"
        for i, text in enumerate(exchanges)
    ]
    return (
        "Below are numbered question-and-answer exchanges from the Q&A section "
        "of an earnings call. Each begins with the moderator handoff, then an "
        "analyst question, then management's answer.\n\n"
        "Score EVERY exchange listed, independently. Return one entry per "
        "exchange, using the exact [EXCHANGE n] numbers shown - do not "
        "renumber them, skip any, or invent numbers that are not listed.\n\n"
        + "\n\n".join(blocks)
    )


# Matches one flat JSON object carrying an "exchange" key. Used only as a
# salvage path, so it deliberately does not try to handle nesting.
_SCORE_ENTRY_RE = re.compile(r'\{[^{}]*?"exchange"\s*:\s*\d+[^{}]*?\}', re.DOTALL)


def _coerce_entry(entry: object, score_key: str) -> tuple[int, int, str] | None:
    """Pull (exchange index, clamped score, quote) out of one parsed entry."""
    if not isinstance(entry, dict):
        return None
    index = entry.get("exchange")
    score = entry.get(score_key, entry.get("score"))
    # bool is an int subclass; True would otherwise read as exchange 1.
    if isinstance(index, bool) or isinstance(score, bool):
        return None
    if not isinstance(index, (int, float)) or not isinstance(score, (int, float)):
        return None
    quote = entry.get("quote") or entry.get("supporting_quote") or ""
    return int(index), max(1, min(10, round(score))), str(quote)


def parse_exchange_scores(raw: str, score_key: str) -> list[tuple[int, int, str]]:
    """Recover per-exchange scores from a model response.

    Falls back to a regex sweep over individual objects, which survives a
    response cut off inside the list. Same reasoning as the batch scorer's
    salvage path (KNOWN_ISSUES.md HIGH-4): dropping a whole request biases the
    result, because responses run long exactly when there is more to say.
    """
    parsed = _parse_llm_json(raw)
    entries: list = []
    if isinstance(parsed, dict):
        for key in ("exchange_scores", "exchanges", "scores", "results"):
            value = parsed.get(key)
            if isinstance(value, list):
                entries = value
                break
    elif isinstance(parsed, list):
        entries = parsed

    found: dict[int, tuple[int, int, str]] = {}
    for entry in entries:
        coerced = _coerce_entry(entry, score_key)
        if coerced is not None:
            found[coerced[0]] = coerced

    if not found:
        for match in _SCORE_ENTRY_RE.finditer(_strip_thinking_tags(raw)):
            try:
                coerced = _coerce_entry(json.loads(match.group(0)), score_key)
            except ValueError:
                continue
            if coerced is not None:
                found[coerced[0]] = coerced

    return [found[i] for i in sorted(found)]


def score_exchanges_llm(
    exchanges: list[str],
    *,
    dimension_name: str,
    system_prompt: str,
    score_key: str,
    model: str | None = None,
    temperature: float = 0.1,
) -> dict:
    """Score each exchange independently. Returns per-exchange scores, unaggregated.

    Returns a dict with:
        exchange_scores  [{"exchange": i, score_key: n, "quote": str}, ...]
        exchanges_total  how many were sent
        raw_response     every raw model response, joined
        usage            summed token usage
        error            present only when nothing could be scored
    """
    from config import LLM_API_BASE_URL, LLM_API_KEY, LLM_MODEL_NAME

    if not LLM_API_KEY or not LLM_API_BASE_URL:
        logger.warning("LLM not configured (missing API_KEY or API_BASE_URL). Returning empty.")
        return {
            "exchange_scores": [],
            "exchanges_total": len(exchanges),
            "error": "LLM not configured",
        }

    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("openai package not installed. Run: pip install openai")
        return {
            "exchange_scores": [],
            "exchanges_total": len(exchanges),
            "error": "openai not installed",
        }

    if not exchanges:
        return {"exchange_scores": [], "exchanges_total": 0, "error": "no exchanges to score"}

    used_model = model or LLM_MODEL_NAME
    client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_API_BASE_URL)

    batches = _batch_chunks(exchanges, _BATCH_TARGET_WORDS)
    logger.info(
        "Scoring %s per exchange - %d exchange(s) in %d request(s)",
        dimension_name, len(exchanges), len(batches),
    )

    scored: dict[int, tuple[int, int, str]] = {}
    all_raw: list[str] = []
    all_usage: list[dict] = []
    next_index = 1

    for batch_number, batch in enumerate(batches, start=1):
        first_index = next_index
        expected = set(range(first_index, first_index + len(batch)))
        next_index += len(batch)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": build_exchange_prompt(batch, first_index)},
        ]
        response = _call_llm_with_retry(
            client,
            model=used_model,
            messages=messages,
            temperature=temperature,
            max_tokens=_output_budget(len(batch)),
            dimension_name=dimension_name,
        )
        raw: str = response.choices[0].message.content or ""
        all_raw.append(raw)
        usage = _extract_usage(response)
        if usage:
            all_usage.append(usage)

        # Ignore numbers the model invented for exchanges it was never given.
        kept = [entry for entry in parse_exchange_scores(raw, score_key) if entry[0] in expected]
        for index, score, quote in kept:
            scored[index] = (index, score, quote)

        missing = sorted(expected - {entry[0] for entry in kept})
        if missing:
            # Never silent: an exchange the model declined to score is an
            # exchange missing from the aggregate, which moves it.
            logger.warning(
                "  %s request %d/%d returned no score for exchange(s) %s%s",
                dimension_name, batch_number, len(batches),
                ", ".join(str(m) for m in missing),
                " (response hit the token limit)"
                if _finish_reason(response) == "length" else "",
            )

    if not scored:
        return {
            "exchange_scores": [],
            "exchanges_total": len(exchanges),
            "raw_response": "\n---\n".join(all_raw),
            "error": "No valid exchange scores from any request",
        }

    combined_usage = None
    if all_usage:
        combined_usage = {
            "prompt_tokens": sum(u.get("prompt_tokens", 0) or 0 for u in all_usage),
            "completion_tokens": sum(u.get("completion_tokens", 0) or 0 for u in all_usage),
            "total_tokens": sum(u.get("total_tokens", 0) or 0 for u in all_usage),
        }

    return {
        "exchange_scores": [
            {"exchange": index, score_key: score, "quote": quote}
            for index, score, quote in (scored[key] for key in sorted(scored))
        ],
        "exchanges_total": len(exchanges),
        "raw_response": "\n---\n".join(all_raw),
        "usage": combined_usage,
    }
