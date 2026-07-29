"""
Forward guidance vagueness scoring dimension for Phase 2.

Scores how specific and measurable forward-looking statements are.
Vague guidance ("we remain optimistic", "well positioned", "multiple levers")
without numbers, timelines, or specific metrics is a red flag.
"""

import json
import logging

from config import LLM_API_KEY, LLM_API_BASE_URL, LLM_MODEL_NAME

logger = logging.getLogger("earningslens")


# ---- LLM Scoring ----

FORWARD_GUIDANCE_VAGUENESS_SYSTEM_PROMPT = """You are an analyst evaluating forward guidance specificity during earnings calls.

Your task: score forward guidance vagueness on a 1-10 scale based on these definitions:

1-3 (SPECIFIC): Clear forward guidance with numbers, timelines, and measurable targets. Examples: "Revenue growth of 8-10% in FY26", "Operating margin expansion of 50-100 bps", "We expect to close 3 large deals by Q2".
4-6 (MODERATE): Some specific guidance mixed with vague statements. General direction given but lacks precision. A few numbers but many gaps.
7-9 (VAGUE): "We remain optimistic", "well positioned", "multiple levers" — no numbers, no timeline, no specificity. Sounds positive but says nothing concrete.
10 (EXTREME): Zero forward-looking specificity. Only platitudes and generalities. "We are confident in our strategy" without any substance.

Look for these specific patterns:
- "We remain optimistic" without explaining what drives the optimism
- "Well positioned" / "strong positioning" without specifying for what
- "Multiple levers" / "multiple growth drivers" without naming them
- "We expect improvement" without quantifying by how much
- "Significant opportunity" without defining the market size or timeline
- "We are on track" without specifying what track or what the destination is
- "Continued momentum" without metrics to back it up
- Forward-looking statements that could apply to any company in any quarter
- Absence of specific revenue, margin, or growth targets
- Vague timelines: "over the next few quarters", "in the medium term", "going forward"
- "We will share more details later" / "stay tuned" as a substitute for actual guidance

You MUST return ONLY valid JSON. No explanation, no markdown, no backticks.
Format:
{"forward_guidance_vagueness_score": <int 1-10>, "supporting_quotes": ["quote 1", "quote 2", "quote 3"]}

Each supporting_quote must be an exact verbatim sentence or short paragraph from the transcript that demonstrates the vagueness. Maximum 3 quotes."""  # noqa: E501


def _build_prompt(chunks: list[str]) -> str:
    """Build the user prompt from transcript chunks."""
    transcript_text = "\n\n".join(chunks)
    return (
        "Below is an earnings call transcript (or a section of one). "
        "Score forward guidance vagueness — whether management provides specific, "
        "measurable forward-looking statements or vague platitudes without substance.\n\n"
        "TRANSCRIPT:\n\n"
        f"{transcript_text}"
    )


def score_forward_guidance_vagueness_llm(chunks: list[str], model: str = None) -> dict:
    """Score forward guidance vagueness using LLM API."""
    if not LLM_API_KEY or not LLM_API_BASE_URL:
        logger.warning("LLM not configured (missing API_KEY or API_BASE_URL). Returning empty.")
        return {"forward_guidance_vagueness_score": None, "supporting_quotes": [], "error": "LLM not configured"}

    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("openai package not installed. Run: pip install openai")
        return {"forward_guidance_vagueness_score": None, "supporting_quotes": [], "error": "openai not installed"}

    used_model = model or LLM_MODEL_NAME
    client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_API_BASE_URL)

    logger.info("Calling LLM forward_guidance_vagueness scoring — model=%s, chunks=%d", used_model, len(chunks))
    response = client.chat.completions.create(
        model=used_model,
        messages=[
            {"role": "system", "content": FORWARD_GUIDANCE_VAGUENESS_SYSTEM_PROMPT},
            {"role": "user", "content": _build_prompt(chunks)},
        ],
        temperature=0.1,
        max_tokens=800,
    )

    raw: str = response.choices[0].message.content or ""
    logger.debug("LLM raw response (forward_guidance_vagueness): %s", raw[:500])

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
            logger.warning("LLM returned invalid JSON (forward_guidance_vagueness): %s", raw[:300])
            return {"forward_guidance_vagueness_score": None, "supporting_quotes": [], "raw_response": raw, "error": "Invalid JSON from LLM"}

    if not isinstance(parsed.get("forward_guidance_vagueness_score"), (int, float)):
        return {"forward_guidance_vagueness_score": None, "supporting_quotes": [], "raw_response": raw, "error": "Missing forward_guidance_vagueness_score"}

    score = max(1, min(10, round(parsed["forward_guidance_vagueness_score"])))
    quotes = parsed.get("supporting_quotes", [])[:3]

    return {
        "forward_guidance_vagueness_score": score,
        "supporting_quotes": quotes,
        "raw_response": raw,
        "usage": usage_dict,
    }


def score_transcript_forward_guidance_vagueness(chunks: list[str]) -> dict:
    """Full forward guidance vagueness scoring using LLM on all chunks."""
    llm_result = score_forward_guidance_vagueness_llm(chunks)
    return {
        "qa_detected": False,
        "chunks_used": len(chunks),
        "llm_result": llm_result,
    }
