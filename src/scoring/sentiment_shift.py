"""
Sentiment shift scoring dimension for Phase 2.

Detects changes in management tone/attitude compared to what would be expected.
Sudden drops in positive language, increased hedging where confidence was high before,
defensive posture — all are red flags.
"""

import json
import logging

from config import LLM_API_KEY, LLM_API_BASE_URL, LLM_MODEL_NAME

logger = logging.getLogger("earningslens")


# ---- LLM Scoring ----

SENTIMENT_SHIFT_SYSTEM_PROMPT = """You are an analyst evaluating management tone shifts during earnings calls.

Your task: score sentiment shift on a 1-10 scale based on these definitions:

1-3 (STABLE): Consistent positive or neutral tone throughout. No sudden drops in confidence. Language is steady and assured.
4-6 (MODERATE SHIFT): Some sections show hedging or defensiveness. Mixed signals — confident in prepared remarks but cautious in Q&A, or vice versa. A few areas where tone drops unexpectedly.
7-9 (SIGNIFICANT SHIFT): Clear negative tone change. Defensive language, hedging, or pessimism in key areas compared to the overall transcript. Management sounds like they are walking back previous optimism.
10 (EXTREME SHIFT): Entire transcript reads as defensive, pessimistic, or crisis-mode. Pervasive negative tone throughout.

Look for these specific patterns:
- Confident language in prepared remarks but hedging in Q&A (or vice versa)
- Sudden drops in positive language (e.g., "excited" → "cautiously optimistic")
- Defensive responses to straightforward questions
- Increased use of qualifiers ("generally", "broadly speaking", "in terms of")
- Pessimistic language where optimism was expected (e.g., after a good quarter)
- Management contradicting or softening their own prepared statements
- Tone inconsistency between different speakers from the same company

You MUST return ONLY valid JSON. No explanation, no markdown, no backticks.
Format:
{"sentiment_shift_score": <int 1-10>, "supporting_quotes": ["quote 1", "quote 2", "quote 3"]}

Each supporting_quote must be an exact verbatim sentence or short paragraph from the transcript that demonstrates the sentiment shift. Maximum 3 quotes."""  # noqa: E501


def _build_prompt(chunks: list[str]) -> str:
    """Build the user prompt from transcript chunks."""
    transcript_text = "\n\n".join(chunks)
    return (
        "Below is an earnings call transcript (or a section of one). "
        "Score management sentiment shift — how much the tone/attitude changes "
        "within the transcript or compared to what you would expect given the context.\n\n"
        "TRANSCRIPT:\n\n"
        f"{transcript_text}"
    )


def score_sentiment_shift_llm(chunks: list[str], model: str = None) -> dict:
    """Score sentiment shift using LLM API."""
    if not LLM_API_KEY or not LLM_API_BASE_URL:
        logger.warning("LLM not configured (missing API_KEY or API_BASE_URL). Returning empty.")
        return {"sentiment_shift_score": None, "supporting_quotes": [], "error": "LLM not configured"}

    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("openai package not installed. Run: pip install openai")
        return {"sentiment_shift_score": None, "supporting_quotes": [], "error": "openai not installed"}

    used_model = model or LLM_MODEL_NAME
    client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_API_BASE_URL)

    logger.info("Calling LLM sentiment_shift scoring — model=%s, chunks=%d", used_model, len(chunks))
    response = client.chat.completions.create(
        model=used_model,
        messages=[
            {"role": "system", "content": SENTIMENT_SHIFT_SYSTEM_PROMPT},
            {"role": "user", "content": _build_prompt(chunks)},
        ],
        temperature=0.1,
        max_tokens=800,
    )

    raw: str = response.choices[0].message.content or ""
    logger.debug("LLM raw response (sentiment_shift): %s", raw[:500])

    usage = getattr(response, "usage", None)
    usage_dict = None
    if usage is not None:
        usage_dict = {
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
        }

    try:
        parsed = json.loads(raw or "")
    except json.JSONDecodeError:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("LLM returned invalid JSON (sentiment_shift): %s", raw[:300])
            return {"sentiment_shift_score": None, "supporting_quotes": [], "raw_response": raw, "error": "Invalid JSON from LLM"}

    if not isinstance(parsed.get("sentiment_shift_score"), (int, float)):
        return {"sentiment_shift_score": None, "supporting_quotes": [], "raw_response": raw, "error": "Missing sentiment_shift_score"}

    score = max(1, min(10, round(parsed["sentiment_shift_score"])))
    quotes = parsed.get("supporting_quotes", [])[:3]

    return {
        "sentiment_shift_score": score,
        "supporting_quotes": quotes,
        "raw_response": raw,
        "usage": usage_dict,
    }


def score_transcript_sentiment_shift(chunks: list[str]) -> dict:
    """Full sentiment shift scoring using LLM on all chunks."""
    llm_result = score_sentiment_shift_llm(chunks)
    return {
        "qa_detected": False,
        "chunks_used": len(chunks),
        "llm_result": llm_result,
    }
