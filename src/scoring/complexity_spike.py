"""
Complexity spike scoring dimension for Phase 2.

Measures sudden increases in jargon density, sentence complexity,
nested qualifiers, and obfuscation through language. A spike in
complexity often signals management trying to obscure deteriorating fundamentals.
"""

from src.scoring._llm_dimension_scorer import score_dimension_llm

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

_SCORE_KEY = "complexity_spike_score"
_USER_INSTRUCTION = (
    "Score the language complexity — whether management is using clear, simple "
    "language or obfuscating through jargon, nested qualifiers, and convoluted phrasing."
)


def _build_prompt(chunks: list[str]) -> str:
    """Build the user prompt from transcript chunks."""
    from src.scoring._llm_dimension_scorer import _build_user_prompt
    return _build_user_prompt(chunks, _USER_INSTRUCTION)


def score_complexity_spike_llm(chunks: list[str], model: str | None = None) -> dict:
    """Score complexity spike using LLM API."""
    return score_dimension_llm(
        chunks,
        dimension_name="complexity_spike",
        system_prompt=COMPLEXITY_SPIKE_SYSTEM_PROMPT,
        score_key=_SCORE_KEY,
        user_prompt_instruction=_USER_INSTRUCTION,
        model=model,
    )


def score_transcript_complexity_spike(chunks: list[str]) -> dict:
    """Full complexity spike scoring using LLM on all chunks."""
    llm_result = score_complexity_spike_llm(chunks)
    return {
        "qa_detected": False,
        "chunks_used": len(chunks),
        "llm_result": llm_result,
    }
