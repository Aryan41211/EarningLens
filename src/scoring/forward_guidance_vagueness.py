"""
Forward guidance vagueness scoring dimension for Phase 2.

Scores how specific and measurable forward-looking statements are.
Vague guidance ("we remain optimistic", "well positioned", "multiple levers")
without numbers, timelines, or specific metrics is a red flag.
"""

from src.scoring._llm_dimension_scorer import score_dimension_llm

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

_SCORE_KEY = "forward_guidance_vagueness_score"
_USER_INSTRUCTION = (
    "Score forward guidance vagueness — whether management provides specific, "
    "measurable forward-looking statements or vague platitudes without substance."
)


def _build_prompt(chunks: list[str]) -> str:
    """Build the user prompt from transcript chunks."""
    from src.scoring._llm_dimension_scorer import _build_user_prompt
    return _build_user_prompt(chunks, _USER_INSTRUCTION)


def score_forward_guidance_vagueness_llm(chunks: list[str], model: str | None = None) -> dict:
    """Score forward guidance vagueness using LLM API."""
    return score_dimension_llm(
        chunks,
        dimension_name="forward_guidance_vagueness",
        system_prompt=FORWARD_GUIDANCE_VAGUENESS_SYSTEM_PROMPT,
        score_key=_SCORE_KEY,
        user_prompt_instruction=_USER_INSTRUCTION,
        model=model,
    )


def score_transcript_forward_guidance_vagueness(chunks: list[str]) -> dict:
    """Full forward guidance vagueness scoring using LLM on all chunks."""
    llm_result = score_forward_guidance_vagueness_llm(chunks)
    return {
        "qa_detected": False,
        "chunks_used": len(chunks),
        "llm_result": llm_result,
    }
