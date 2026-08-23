"""
Overpromising scoring dimension for Phase 2.

Flags aggressive guidance, unrealistic targets, "best quarter ever" claims
without numbers, promises of "significant upside" with no quantifiable driver,
and aspirational language presented as certainty.
"""

from src.scoring._llm_dimension_scorer import score_dimension_llm

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

_SCORE_KEY = "overpromising_score"
_USER_INSTRUCTION = (
    "Score management overpromising — whether management is making aggressive "
    "claims, unrealistic targets, or aspirational promises without evidence."
)


def _build_prompt(chunks: list[str]) -> str:
    """Build the user prompt from transcript chunks."""
    from src.scoring._llm_dimension_scorer import _build_user_prompt
    return _build_user_prompt(chunks, _USER_INSTRUCTION)


def score_overpromising_llm(chunks: list[str], model: str | None = None) -> dict:
    """Score overpromising using LLM API."""
    return score_dimension_llm(
        chunks,
        dimension_name="overpromising",
        system_prompt=OVERPROMISING_SYSTEM_PROMPT,
        score_key=_SCORE_KEY,
        user_prompt_instruction=_USER_INSTRUCTION,
        model=model,
    )


def score_transcript_overpromising(chunks: list[str], model: str | None = None) -> dict:
    """Full overpromising scoring using LLM on all chunks."""
    llm_result = score_overpromising_llm(chunks, model=model)
    return {
        "qa_detected": False,
        "chunks_used": len(chunks),
        "llm_result": llm_result,
    }
