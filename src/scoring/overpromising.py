"""
Overpromising scoring dimension for Phase 2.

Flags aggressive guidance, unrealistic targets, "best quarter ever" claims
without numbers, promises of "significant upside" with no quantifiable driver,
and aspirational language presented as certainty.
"""

import json
import logging

from config import LLM_API_KEY, LLM_API_BASE_URL, LLM_MODEL_NAME

logger = logging.getLogger("earningslens")


# ---- LLM Scoring ----

OVERPROMISING_SYSTEM_PROMPT = """You are an analyst evaluating management overpromising during earnings calls.

Your task: score overpromising on a 1-10 scale based on these definitions:

1-3 (CONSERVATIVE): Realistic targets backed by numbers. Hedged appropriately. Data-driven statements. Management acknowledges risks honestly.
4-6 (MODERATE): Some aspirational language but generally grounded. A few unchecked claims. Most statements have some basis in data.
7-9 (HIGH): Aggressive targets without numbers. "Significant upside" / "best quarter" language without evidence. Multiple unchecked promises. Aspirational language presented as certainty.
10 (EXTREME): Pervasive overpromising. Every statement is aspirational with no evidence. Complete disconnect between claims and reality.

Look for these specific patterns:
- "Best quarter ever" / "record performance" without specific numbers
- "Significant upside" / "massive opportunity" with no quantifiable driver
- "We will grow" without specifying by how much or what the baseline is
- Aspirational language presented as certainty ("will" instead of "could" or "aims to")
- Growth targets that are dramatically above industry averages without explanation
- Promises of margin expansion without detailing the levers
- "Multiple levers" / "multiple growth drivers" without naming them
- Ignoring or dismissing analyst questions about risks
- Comparing current performance to historical peaks without acknowledging the gap
- Language that implies inevitability of positive outcomes

You MUST return ONLY valid JSON. No explanation, no markdown, no backticks.
Format:
{"overpromising_score": <int 1-10>, "supporting_quotes": ["quote 1", "quote 2", "quote 3"]}

Each supporting_quote must be an exact verbatim sentence or short paragraph from the transcript that demonstrates the overpromising. Maximum 3 quotes."""  # noqa: E501


def _build_prompt(chunks: list[str]) -> str:
    """Build the user prompt from transcript chunks."""
    transcript_text = "\n\n".join(chunks)
    return (
        "Below is an earnings call transcript (or a section of one). "
        "Score management overpromising — whether management is making aggressive "
        "claims, unrealistic targets, or aspirational promises without evidence.\n\n"
        "TRANSCRIPT:\n\n"
        f"{transcript_text}"
    )


def score_overpromising_llm(chunks: list[str], model: str = None) -> dict:
    """Score overpromising using LLM API."""
    if not LLM_API_KEY or not LLM_API_BASE_URL:
        logger.warning("LLM not configured (missing API_KEY or API_BASE_URL). Returning empty.")
        return {"overpromising_score": None, "supporting_quotes": [], "error": "LLM not configured"}

    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("openai package not installed. Run: pip install openai")
        return {"overpromising_score": None, "supporting_quotes": [], "error": "openai not installed"}

    used_model = model or LLM_MODEL_NAME
    client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_API_BASE_URL)

    logger.info("Calling LLM overpromising scoring — model=%s, chunks=%d", used_model, len(chunks))
    response = client.chat.completions.create(
        model=used_model,
        messages=[
            {"role": "system", "content": OVERPROMISING_SYSTEM_PROMPT},
            {"role": "user", "content": _build_prompt(chunks)},
        ],
        temperature=0.1,
        max_tokens=800,
    )

    raw: str = response.choices[0].message.content or ""
    logger.debug("LLM raw response (overpromising): %s", raw[:500])

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
            logger.warning("LLM returned invalid JSON (overpromising): %s", raw[:300])
            return {"overpromising_score": None, "supporting_quotes": [], "raw_response": raw, "error": "Invalid JSON from LLM"}

    if not isinstance(parsed.get("overpromising_score"), (int, float)):
        return {"overpromising_score": None, "supporting_quotes": [], "raw_response": raw, "error": "Missing overpromising_score"}

    score = max(1, min(10, round(parsed["overpromising_score"])))
    quotes = parsed.get("supporting_quotes", [])[:3]

    return {
        "overpromising_score": score,
        "supporting_quotes": quotes,
        "raw_response": raw,
        "usage": usage_dict,
    }


def score_transcript_overpromising(chunks: list[str]) -> dict:
    """Full overpromising scoring using LLM on all chunks."""
    llm_result = score_overpromising_llm(chunks)
    return {
        "qa_detected": False,
        "chunks_used": len(chunks),
        "llm_result": llm_result,
    }
