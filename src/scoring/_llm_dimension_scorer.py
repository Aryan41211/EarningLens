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


def _parse_llm_json(raw: str, score_key: str) -> dict | None:
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


def _call_llm_with_retry(client, *, model, messages, temperature, max_tokens, dimension_name):
    """Call LLM with exponential backoff on rate limit errors."""
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
            is_rate_limit = "413" in error_str or "rate_limit" in error_str or "429" in error_str
            if is_rate_limit and attempt < _MAX_RETRIES - 1:
                logger.warning(
                    "    Rate limited on %s (attempt %d/%d), retrying in %.1fs...",
                    dimension_name, attempt + 1, _MAX_RETRIES, backoff,
                )
                time.sleep(backoff)
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

    parsed = _parse_llm_json(raw, score_key)
    if parsed is None:
        logger.warning("  LLM returned invalid JSON (%s): %s", dimension_name, raw[:200])
        return None, raw, usage_dict

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
    max_tokens: int = 800,
) -> dict:
    """Score a transcript dimension using LLM API.

    Handles large transcripts by batching chunks to stay within TPM limits.
    Aggregates scores across batches (average).

    Returns:
        Dict with score_key, supporting_quotes, raw_response, usage, and optionally error.
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
    }
