"""
Sentiment shift scoring dimension for Phase 2.

Detects changes in management tone/attitude compared to what would be expected.
Sudden drops in positive language, increased hedging where confidence was high before,
defensive posture — all are red flags.
"""

from src.scoring._llm_dimension_scorer import score_dimension_llm

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

_SCORE_KEY = "sentiment_shift_score"
_USER_INSTRUCTION = (
    "Score management sentiment shift — how much the tone/attitude changes "
    "within the transcript or compared to what you would expect given the context."
)


def _build_prompt(chunks: list[str]) -> str:
    """Build the user prompt from transcript chunks."""
    from src.scoring._llm_dimension_scorer import _build_user_prompt
    return _build_user_prompt(chunks, _USER_INSTRUCTION)


def score_sentiment_shift_llm(chunks: list[str], model: str = None) -> dict:
    """Score sentiment shift using LLM API."""
    return score_dimension_llm(
        chunks,
        dimension_name="sentiment_shift",
        system_prompt=SENTIMENT_SHIFT_SYSTEM_PROMPT,
        score_key=_SCORE_KEY,
        user_prompt_instruction=_USER_INSTRUCTION,
        model=model,
    )


def score_transcript_sentiment_shift(chunks: list[str]) -> dict:
    """Full sentiment shift scoring using LLM on all chunks."""
    llm_result = score_sentiment_shift_llm(chunks)
    return {
        "qa_detected": False,
        "chunks_used": len(chunks),
        "llm_result": llm_result,
    }
