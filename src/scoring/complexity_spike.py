"""
Complexity spike scoring dimension for Phase 2.

Measures sudden increases in jargon density, sentence complexity,
nested qualifiers, and obfuscation through language. A spike in
complexity often signals management trying to obscure deteriorating fundamentals.
"""

import json
import logging

from config import LLM_API_KEY, LLM_API_BASE_URL, LLM_MODEL_NAME

logger = logging.getLogger("earningslens")


# ---- LLM Scoring ----

COMPLEXITY_SPIKE_SYSTEM_PROMPT = """You are an analyst evaluating language complexity in earnings calls.

Your task: score complexity spike on a 1-10 scale based on these definitions:

1-3 (LOW complexity): Clear, simple language. Short sentences. Plain English. Numbers given directly. No unexplained jargon.
4-6 (MODERATE complexity): Some jargon but generally understandable. Occasional long sentences. A few acronyms that are industry-standard.
7-9 (HIGH complexity): Heavy jargon, nested qualifiers ("broadly speaking, generally, in terms of"), sentences exceeding 40 words, acronyms without explanation, deliberately roundabout phrasing.
10 (EXTREME complexity): Deliberately obfuscated. Nearly impossible to extract clear meaning. Language seems designed to confuse.

Look for these specific patterns:
- Sudden increase in jargon density (technical terms used without explanation)
- Nested qualifiers: "broadly speaking, generally, in terms of, so to speak"
- Sentences longer than 40 words with multiple clauses
- Acronyms used without first spelling them out
- Passive voice used to obscure who is responsible
- Circumlocution: saying in 20 words what could be said in 5
- "Management speak" that sounds impressive but says nothing
- Repeated use of hedging phrases layered on top of each other
- Contrast between simple language in early sections vs complex language later (a spike)

You MUST return ONLY valid JSON. No explanation, no markdown, no backticks.
Format:
{"complexity_spike_score": <int 1-10>, "supporting_quotes": ["quote 1", "quote 2", "quote 3"]}

Each supporting_quote must be an exact verbatim sentence or short paragraph from the transcript that demonstrates the complexity. Maximum 3 quotes."""  # noqa: E501


def _build_prompt(chunks: list[str]) -> str:
    """Build the user prompt from transcript chunks."""
    transcript_text = "\n\n".join(chunks)
    return (
        "Below is an earnings call transcript (or a section of one). "
        "Score the language complexity — whether management is using clear, simple "
        "language or obfuscating through jargon, nested qualifiers, and convoluted phrasing.\n\n"
        "TRANSCRIPT:\n\n"
        f"{transcript_text}"
    )


def score_complexity_spike_llm(chunks: list[str], model: str = None) -> dict:
    """Score complexity spike using LLM API."""
    if not LLM_API_KEY or not LLM_API_BASE_URL:
        logger.warning("LLM not configured (missing API_KEY or API_BASE_URL). Returning empty.")
        return {"complexity_spike_score": None, "supporting_quotes": [], "error": "LLM not configured"}

    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("openai package not installed. Run: pip install openai")
        return {"complexity_spike_score": None, "supporting_quotes": [], "error": "openai not installed"}

    used_model = model or LLM_MODEL_NAME
    client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_API_BASE_URL)

    logger.info("Calling LLM complexity_spike scoring — model=%s, chunks=%d", used_model, len(chunks))
    response = client.chat.completions.create(
        model=used_model,
        messages=[
            {"role": "system", "content": COMPLEXITY_SPIKE_SYSTEM_PROMPT},
            {"role": "user", "content": _build_prompt(chunks)},
        ],
        temperature=0.1,
        max_tokens=800,
    )

    raw: str = response.choices[0].message.content or ""
    logger.debug("LLM raw response (complexity_spike): %s", raw[:500])

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
            logger.warning("LLM returned invalid JSON (complexity_spike): %s", raw[:300])
            return {"complexity_spike_score": None, "supporting_quotes": [], "raw_response": raw, "error": "Invalid JSON from LLM"}

    if not isinstance(parsed.get("complexity_spike_score"), (int, float)):
        return {"complexity_spike_score": None, "supporting_quotes": [], "raw_response": raw, "error": "Missing complexity_spike_score"}

    score = max(1, min(10, round(parsed["complexity_spike_score"])))
    quotes = parsed.get("supporting_quotes", [])[:3]

    return {
        "complexity_spike_score": score,
        "supporting_quotes": quotes,
        "raw_response": raw,
        "usage": usage_dict,
    }


def score_transcript_complexity_spike(chunks: list[str]) -> dict:
    """Full complexity spike scoring using LLM on all chunks."""
    llm_result = score_complexity_spike_llm(chunks)
    return {
        "qa_detected": False,
        "chunks_used": len(chunks),
        "llm_result": llm_result,
    }
