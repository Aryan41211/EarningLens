"""
Shared LLM scoring function for non-evasiveness dimensions.

All 4 dimensions (sentiment_shift, complexity_spike, overpromising,
forward_guidance_vagueness) follow the same pattern:
check config -> call LLM -> parse JSON -> clamp score -> return dict.
This module extracts that common logic, parameterized by prompt and score key.
"""

import json
import logging

logger = logging.getLogger("earningslens")


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
    """Try to parse LLM response as JSON, handling markdown fences.
    Returns parsed dict or None on failure."""
    try:
        result: dict = json.loads(raw or "")
        return result
    except (json.JSONDecodeError, ValueError):
        pass
    cleaned = raw.strip()
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

    Args:
        chunks: Transcript text chunks.
        dimension_name: Human-readable name for logging (e.g. "sentiment_shift").
        system_prompt: The system prompt defining scoring criteria.
        score_key: The JSON key for the score (e.g. "sentiment_shift_score").
        user_prompt_instruction: Instruction text for the user prompt.
        model: Optional model override.
        temperature: LLM temperature (default 0.1).
        max_tokens: Max tokens for LLM response (default 800).

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

    logger.info("Calling LLM %s scoring — model=%s, chunks=%d", dimension_name, used_model, len(chunks))
    response = client.chat.completions.create(
        model=used_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": _build_user_prompt(chunks, user_prompt_instruction)},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )

    raw: str = response.choices[0].message.content or ""
    logger.debug("LLM raw response (%s): %s", dimension_name, raw[:500])

    usage_dict = _extract_usage(response)

    parsed = _parse_llm_json(raw, score_key)
    if parsed is None:
        logger.warning("LLM returned invalid JSON (%s): %s", dimension_name, raw[:300])
        return {score_key: None, "supporting_quotes": [], "raw_response": raw, "error": "Invalid JSON from LLM"}

    if not isinstance(parsed.get(score_key), (int, float)):
        return {score_key: None, "supporting_quotes": [], "raw_response": raw, "error": f"Missing {score_key}"}

    score = max(1, min(10, round(parsed[score_key])))
    quotes = parsed.get("supporting_quotes", [])[:3]

    return {
        score_key: score,
        "supporting_quotes": quotes,
        "raw_response": raw,
        "usage": usage_dict,
    }
