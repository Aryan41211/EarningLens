"""
Evasiveness scoring dimension for Phase 2.

Two components:
  A) Deterministic keyword-matching on dodge phrases
  B) LLM-based scoring on Q&A section chunks only
"""

import re
import json
import logging
from collections import Counter

from config import LLM_API_KEY, LLM_API_BASE_URL, LLM_MODEL_NAME

logger = logging.getLogger("earningslens")


# ---- (A) Deterministic Keyword Matching ----

DODGE_PHRASES = [
    "going forward",
    "as I mentioned",
    "as previously stated",
    "we remain committed",
    "remain committed to",
    "at this point",
    "at this stage",
    "we continue to believe",
    "continue to believe",
    "difficult to comment",
    "difficult to say",
    "too early to say",
    "too early to comment",
    "cannot speculate",
    "not in a position to",
    "not able to comment",
    "no specific guidance",
    "we are optimistic",
    "we remain optimistic",
    "we do not provide",
    "we don't provide",
    "wait and watch",
    "wait and see",
    "in due course",
    "in the fullness of time",
    "no further update",
    "nothing to add",
    "nothing further to add",
    "as and when",
    "we are evaluating",
    "we continue to evaluate",
    "we will evaluate",
    "it would be premature",
    "premature to",
    "it remains to be seen",
    "time will tell",
    "let me come back",
    "I would not like to",
    "we are not in a position",
    "we don't want to get into",
    "we cannot quantify",
    "not really quantified",
]


def score_evasiveness_keywords(chunks: list[str]) -> dict:
    """Scan chunks for dodge phrases. Returns counts and matched phrases."""
    matches = []
    total_count = 0

    for phrase in DODGE_PHRASES:
        pat = re.compile(re.escape(phrase), re.IGNORECASE)
        for chunk in chunks:
            for m in pat.finditer(chunk):
                start = max(0, m.start() - 40)
                end = min(len(chunk), m.end() + 40)
                context = chunk[start:end].replace("\n", " ").strip()
                matches.append((phrase, context))
                total_count += 1

    freq = Counter(p for p, _ in matches)
    return {
        "total_count": total_count,
        "matched_phrases": [{"phrase": p, "context": c} for p, c in matches],
        "frequency": {k: v for k, v in freq.most_common()},
    }


# ---- Q&A Detection ----

Q_A_MARKER_PATTERN = re.compile(
    r"(?:first question from the line of|we'?ll take our first question|"
    r"we have (?:our|a) first question|first question is from the line of)",
    re.IGNORECASE,
)


def find_qa_start_index(chunks: list[str]) -> int:
    """Return the chunk index where Q&A begins, or -1 if not found.
    Uses the phrase 'first question from the line of' which appears
    consistently across TCS and INFY transcripts."""
    for i, chunk in enumerate(chunks):
        if Q_A_MARKER_PATTERN.search(chunk):
            return i
    return -1


# ---- (B) LLM Scoring ----

EVASIVENESS_SYSTEM_PROMPT = """You are an analyst evaluating management credibility during earnings calls.

Your task: score evasiveness on a 1-10 scale based on these definitions:

1-3 (LOW evasiveness): Direct answers. Specific numbers, timelines, metrics given.
4-6 (MODERATE evasiveness): Generally direct but with some hedging. Some specifics provided.
7-9 (HIGH evasiveness): Repeated deflection. Vague language, no specifics, repeated non-answers.
10 (EXTREME): Every answer dodged. Complete refusal to engage with specific questions.

Beware of these evasion patterns:
- Repeating prepared remarks instead of answering the question
- "Going forward" / "as I mentioned" / "we remain committed" without specifics
- "Too early to say" / "cannot speculate" / "difficult to comment" on straightforward questions
- Redirecting to generic positive statements when asked about problems
- Answering a different question than was asked
- Giving process answers ("we are evaluating") instead of substance

You MUST return ONLY valid JSON. No explanation, no markdown, no backticks.
Format:
{"evasiveness_score": <int 1-10>, "supporting_quotes": ["quote 1", "quote 2", "quote 3"]}

Each supporting_quote must be an exact verbatim sentence or short paragraph from the transcript that demonstrates the evasion. Maximum 3 quotes."""  # noqa: E501


def _build_qa_prompt(chunks: list[str]) -> str:
    """Build the user prompt from Q&A chunks, preserving speaker labels."""
    transcript_text = "\n\n".join(chunks)
    return (
        "Below is the Q&A section of an earnings call transcript. "
        "Each chunk begins with the speaker's name followed by a colon.\n\n"
        "Score management evasiveness based on how directly management answers "
        "the analysts' questions. Focus on management responses (speakers with names "
        "like Krithivasan, Seksaria, Lakkad, Parekh, Roy — not analyst names or Moderator).\n\n"
        "TRANSCRIPT:\n\n"
        f"{transcript_text}"
    )


def score_evasiveness_llm(chunks: list[str], model: str = None) -> dict:
    """Score evasiveness using LLM API. Only Q&A chunks should be passed in."""
    if not LLM_API_KEY or not LLM_API_BASE_URL:
        logger.warning("LLM not configured (missing API_KEY or API_BASE_URL). Returning empty.")
        return {"evasiveness_score": None, "supporting_quotes": [], "error": "LLM not configured"}

    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("openai package not installed. Run: pip install openai")
        return {"evasiveness_score": None, "supporting_quotes": [], "error": "openai not installed"}

    used_model = model or LLM_MODEL_NAME
    client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_API_BASE_URL)

    logger.info("Calling LLM evasiveness scoring — model=%s, chunks=%d", used_model, len(chunks))
    response = client.chat.completions.create(
        model=used_model,
        messages=[
            {"role": "system", "content": EVASIVENESS_SYSTEM_PROMPT},
            {"role": "user", "content": _build_qa_prompt(chunks)},
        ],
        temperature=0.1,
        max_tokens=800,
    )

    raw = response.choices[0].message.content
    logger.debug("LLM raw response: %s", raw[:500])

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("LLM returned invalid JSON: %s", raw[:300])
            return {"evasiveness_score": None, "supporting_quotes": [], "raw_response": raw, "error": "Invalid JSON from LLM"}

    if not isinstance(parsed.get("evasiveness_score"), (int, float)):
        return {"evasiveness_score": None, "supporting_quotes": [], "raw_response": raw, "error": "Missing evasiveness_score"}

    score = max(1, min(10, round(parsed["evasiveness_score"])))
    quotes = parsed.get("supporting_quotes", [])[:3]

    return {
        "evasiveness_score": score,
        "supporting_quotes": quotes,
        "raw_response": raw,
    }


# ---- Combined scoring ----

def score_transcript_evasiveness(chunks: list[str]) -> dict:
    """Full evasiveness scoring: keyword count + Q&A detection + LLM score.
    Keyword matching is restricted to Q&A chunks only to avoid
    safe-harbor boilerplate false positives in prepared remarks."""
    qa_start = find_qa_start_index(chunks)
    if qa_start == -1:
        kw_result = score_evasiveness_keywords([])
        return {
            "keyword_result": kw_result,
            "qa_detected": False,
            "qa_chunks_used": 0,
            "llm_result": {"evasiveness_score": None, "message": "No Q&A section found"},
        }

    qa_chunks = chunks[qa_start:]
    kw_result = score_evasiveness_keywords(qa_chunks)
    llm_result = score_evasiveness_llm(qa_chunks)

    return {
        "keyword_result": kw_result,
        "qa_detected": True,
        "qa_boundary_chunk_index": qa_start,
        "qa_chunks_used": len(qa_chunks),
        "llm_result": llm_result,
    }