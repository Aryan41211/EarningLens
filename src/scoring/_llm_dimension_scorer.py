"""
Shared LLM scoring function for non-evasiveness dimensions.

All 4 dimensions (sentiment_shift, complexity_spike, overpromising,
forward_guidance_vagueness) follow the same pattern:
check config -> call LLM -> parse JSON -> clamp score -> return dict.
This module extracts that common logic, parameterized by prompt and score key.

Handles Groq free-tier 8000 TPM limit by batching chunks and retrying on rate limits.
"""

import json
import logging
import re
import time

logger = logging.getLogger("earningslens")

# ~2000 words ≈ 2500 tokens, safe for 8000 TPM limit with system prompt overhead
_BATCH_TARGET_WORDS = 2000
_MAX_RETRIES = 5
_INITIAL_BACKOFF = 2.0


def _batch_chunks(chunks: list[str], target_words: int = _BATCH_TARGET_WORDS) -> list[list[str]]:
    """Group chunks into batches that fit within TPM limits."""
    if not chunks:
        # An empty transcript must never become a batch of zero chunks that
        # still reaches the LLM as "TRANSCRIPT:\n\n" -- the model would simply
        # guess. Callers should treat this as "nothing to score", not an empty
        # API call.
        return []
    batches: list[list[str]] = []
    current_batch: list[str] = []
    current_words = 0

    for chunk in chunks:
        chunk_words = len(chunk.split())
        if current_batch and current_words + chunk_words > target_words:
            batches.append(current_batch)
            current_batch = [chunk]
            current_words = chunk_words
        else:
            current_batch.append(chunk)
            current_words += chunk_words

    if current_batch:
        batches.append(current_batch)

    return batches if batches else [chunks]


def _strip_thinking_tags(text: str) -> str:
    """Strip <think>...</think> blocks from model responses."""
    return re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL).strip()


def _build_user_prompt(chunks: list[str], instruction: str) -> str:
    """Build the user prompt from transcript chunks."""
    transcript_text = "\n\n".join(chunks)
    return (
        f"Below is an earnings call transcript (or a section of one). "
        f"{instruction}\n\n"
        f"TRANSCRIPT:\n\n"
        f"{transcript_text}"
    )


def _parse_llm_json(raw: str) -> dict | None:
    """Try to parse LLM response as JSON, handling markdown fences and thinking tags.
    Returns parsed dict or None on failure."""
    cleaned = _strip_thinking_tags(raw)
    try:
        result: dict = json.loads(cleaned or "")
        return result
    except (json.JSONDecodeError, ValueError):
        pass
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
    try:
        result2: dict = json.loads(cleaned)
        return result2
    except (json.JSONDecodeError, ValueError):
        return None


_QUOTED_STRING_RE = re.compile(r'"(?:[^"\\]|\\.)*"')


def _finish_reason(response) -> str | None:
    """Why the model stopped. 'length' means the response was cut off."""
    choices = getattr(response, "choices", None) or []
    if not choices:
        return None
    return getattr(choices[0], "finish_reason", None)


def _salvage_truncated_json(raw: str, score_key: str) -> dict | None:
    """Recover a score from a response cut off by the token limit.

    The model emits the score before its supporting quotes, so a response
    truncated inside the quote list still carries a usable score. Dropping the
    whole batch instead would bias the aggregate, because truncation happens
    when the quotes run long -- which is not independent of what is being
    scored. Returns None if no score is recoverable.
    """
    cleaned = _strip_thinking_tags(raw)
    match = re.search(rf'"{re.escape(score_key)}"\s*:\s*(-?\d+(?:\.\d+)?)', cleaned)
    if match is None:
        return None
    try:
        score = float(match.group(1))
    except ValueError:
        return None

    # Keep only the quote strings that closed before the cutoff.
    quotes: list[str] = []
    _, _, after = cleaned.partition('"supporting_quotes"')
    for found in _QUOTED_STRING_RE.finditer(after):
        try:
            quotes.append(json.loads(found.group(0)))
        except ValueError:
            continue

    return {score_key: score, "supporting_quotes": quotes}


def _extract_usage(response) -> dict | None:
    """Extract token usage from OpenAI response."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    return {
        "prompt_tokens": getattr(usage, "prompt_tokens", None),
        "completion_tokens": getattr(usage, "completion_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
    }


class DailyQuotaExhausted(RuntimeError):
    """The provider's tokens-per-day budget is spent.

    Distinct from a per-minute rate limit: backing off cannot clear it within a
    run, so retrying only burns time. Raised so callers can stop the sweep
    instead of grinding through every remaining dimension.
    """


# A per-minute limit clears in seconds; anything longer is a daily budget and
# waiting it out inside a run is not sensible.
_MAX_SENSIBLE_WAIT = 120.0

_RETRY_AFTER_PATTERN = re.compile(r"(?:try again|retry) in ([\dhms.]+)", re.IGNORECASE)


def _parse_retry_after(error_str: str) -> float | None:
    """Extract the provider's suggested wait, in seconds, if it gave one.

    Groq formats these as '23m46.032s', '7m39.648s', or '4.5s', phrased as
    either "try again in ..." or "retry in ...".
    """
    match = _RETRY_AFTER_PATTERN.search(error_str)
    if not match:
        return None
    raw = match.group(1)
    parts = re.findall(r"([\d.]+)([hms])", raw)
    if not parts:
        return None
    scale = {"h": 3600.0, "m": 60.0, "s": 1.0}
    return sum(float(value) * scale[unit] for value, unit in parts)


def _call_llm_with_retry(client, *, model, messages, temperature, max_tokens, dimension_name):
    """Call the LLM, backing off on per-minute rate limits.

    A tokens-per-day exhaustion is raised immediately as DailyQuotaExhausted
    rather than retried: the reset is typically 20+ minutes away, so the retry
    budget is spent for nothing and the real cause ends up buried under
    generic 'rate limited' warnings.
    """
    backoff = _INITIAL_BACKOFF
    for attempt in range(_MAX_RETRIES):
        try:
            return client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as e:
            error_str = str(e)
            # A 413 is a request-shape / payload error, not a rate limit: it
            # will not clear after a wait, so retrying through the backoff loop
            # would burn the whole budget for nothing and mislabel the cause as
            # "Rate limited". Anything else naming a rate limit is retried.
            is_rate_limit = "rate_limit" in error_str or "429" in error_str
            if not is_rate_limit:
                raise

            wait = _parse_retry_after(error_str)
            is_daily = "tokens per day" in error_str.lower() or "TPD" in error_str
            if is_daily or (wait is not None and wait > _MAX_SENSIBLE_WAIT):
                raise DailyQuotaExhausted(
                    f"Provider token budget exhausted while scoring {dimension_name}. "
                    f"Resets in about {wait / 60:.0f} minutes. " if wait else
                    f"Provider token budget exhausted while scoring {dimension_name}. "
                ) from e

            if attempt < _MAX_RETRIES - 1:
                pause = wait if wait is not None else backoff
                logger.warning(
                    "    Rate limited on %s (attempt %d/%d), retrying in %.1fs...",
                    dimension_name, attempt + 1, _MAX_RETRIES, pause,
                )
                time.sleep(pause)
                backoff = min(backoff * 2, 60)
            else:
                raise


def _score_single_batch(
    client, *, chunks, dimension_name, system_prompt, score_key,
    user_prompt_instruction, model, temperature, max_tokens,
):
    """Score a single batch of chunks. Returns the parsed result dict."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": _build_user_prompt(chunks, user_prompt_instruction)},
    ]

    logger.info(
        "  Calling LLM %s — model=%s, chunks=%d, ~%d words",
        dimension_name, model, len(chunks), sum(len(c.split()) for c in chunks),
    )

    response = _call_llm_with_retry(
        client,
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        dimension_name=dimension_name,
    )

    raw: str = response.choices[0].message.content or ""
    usage_dict = _extract_usage(response)

    parsed = _parse_llm_json(raw)
    if parsed is None:
        parsed = _salvage_truncated_json(raw, score_key)
        if parsed is None:
            logger.warning("  LLM returned invalid JSON (%s): %s", dimension_name, raw[:200])
            return None, raw, usage_dict
        if _finish_reason(response) == "length":
            logger.warning(
                "  %s response hit the token limit; recovered the score, quotes may be incomplete",
                dimension_name,
            )
        else:
            logger.warning(
                "  %s response was not valid JSON; recovered the score from a partial response",
                dimension_name,
            )

    if not isinstance(parsed.get(score_key), (int, float)):
        return None, raw, usage_dict

    score = max(1, min(10, round(parsed[score_key])))
    quotes = parsed.get("supporting_quotes", [])[:3]
    return {score_key: score, "supporting_quotes": quotes}, raw, usage_dict


def score_dimension_llm(
    chunks: list[str],
    *,
    dimension_name: str,
    system_prompt: str,
    score_key: str,
    user_prompt_instruction: str,
    model: str | None = None,
    temperature: float = 0.1,
    max_tokens: int = 1600,
) -> dict:
    """Score a transcript dimension using LLM API.

    Handles large transcripts by batching chunks to stay within TPM limits.
    Aggregates scores across batches (average).

    The average is known to destroy the scorer's range -- see the comment beside
    it and KNOWN_ISSUES.md BLOCKER-6. `batch_scores` in the returned dict is the
    unaggregated evidence.

    Returns:
        Dict with score_key, supporting_quotes, raw_response, usage, batch_scores,
        and optionally error.
    """
    from config import LLM_API_KEY, LLM_API_BASE_URL, LLM_MODEL_NAME

    if not LLM_API_KEY or not LLM_API_BASE_URL:
        logger.warning("LLM not configured (missing API_KEY or API_BASE_URL). Returning empty.")
        return {score_key: None, "supporting_quotes": [], "error": "LLM not configured"}

    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("openai package not installed. Run: pip install openai")
        return {score_key: None, "supporting_quotes": [], "error": "openai not installed"}

    used_model = model or LLM_MODEL_NAME
    client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_API_BASE_URL)

    batches = _batch_chunks(chunks)
    logger.info("Scoring %s — %d chunks in %d batch(es)", dimension_name, len(chunks), len(batches))

    all_scores = []
    all_quotes = []
    all_raw = []
    all_usage = []

    for i, batch in enumerate(batches):
        if len(batches) > 1:
            logger.info("  Batch %d/%d", i + 1, len(batches))

        result, raw, usage = _score_single_batch(
            client,
            chunks=batch,
            dimension_name=dimension_name,
            system_prompt=system_prompt,
            score_key=score_key,
            user_prompt_instruction=user_prompt_instruction,
            model=used_model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        all_raw.append(raw)
        if usage:
            all_usage.append(usage)

        if result is not None:
            all_scores.append(result[score_key])
            all_quotes.extend(result.get("supporting_quotes", []))

    if not all_scores:
        return {
            score_key: None,
            "supporting_quotes": [],
            "raw_response": "\n---\n".join(all_raw),
            "error": "No valid scores from any batch",
        }

    avg_score = max(1, min(10, round(sum(all_scores) / len(all_scores))))

    # The averaging step above is the project's largest measured source of lost
    # signal, so it announces itself rather than hiding in raw_llm_response.
    #
    # Each batch is ~2000 words of Q&A that the model is asked to judge as if it
    # were the whole call, and those per-batch verdicts genuinely spread: across
    # the 7 evasiveness-v2 transcripts scored on 2026-08-25 they ranged 3 to 8.
    # Averaging 3-5 of them collapses that to 5 or 6 every single time -- the
    # stored scores for all 7 transcripts were 5, 5, 5, 6, 6, 6, 6. A mean of
    # several noisy whole-call judgements has a narrower distribution than the
    # judgements themselves, by construction, and a scorer whose output spans
    # one point cannot rank anything.
    #
    # This is logged, not fixed. Re-checked against the human labels, no
    # alternative aggregator (max, median, p75, top-2 mean) turns the negative
    # rank correlation positive, so swapping the operator would invalidate the
    # stored series under SCORING_METHODOLOGY.md section 7 and buy nothing
    # measurable. The real fix is to stop asking a fragment to judge the whole
    # -- see KNOWN_ISSUES.md BLOCKER-6.
    spread = max(all_scores) - min(all_scores) if len(all_scores) > 1 else 0
    if spread >= 4:
        logger.warning(
            "  %s batch scores span %s (%d-%d) but average to %d - the aggregate "
            "discards most of that range (KNOWN_ISSUES.md BLOCKER-6)",
            dimension_name, spread, min(all_scores), max(all_scores), avg_score,
        )

    # A dropped batch silently shrinks the divisor, so the score stops being an
    # average over the whole transcript. Say so rather than letting a partial
    # score look complete.
    if len(all_scores) < len(batches):
        logger.warning(
            "  %s scored from %d of %d batch(es) — %d produced no usable score",
            dimension_name,
            len(all_scores),
            len(batches),
            len(batches) - len(all_scores),
        )

    combined_usage = None
    if all_usage:
        combined_usage = {
            "prompt_tokens": sum(u.get("prompt_tokens", 0) or 0 for u in all_usage),
            "completion_tokens": sum(u.get("completion_tokens", 0) or 0 for u in all_usage),
            "total_tokens": sum(u.get("total_tokens", 0) or 0 for u in all_usage),
        }

    return {
        score_key: avg_score,
        "supporting_quotes": all_quotes[:3],
        "raw_response": "\n---\n".join(all_raw),
        "usage": combined_usage,
        "batches_used": len(all_scores),
        "batches_total": len(batches),
        # Kept so callers can see what the average threw away without having to
        # regex it back out of raw_response.
        "batch_scores": list(all_scores),
        "batch_score_spread": spread,
    }
