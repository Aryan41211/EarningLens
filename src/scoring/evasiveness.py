"""
Evasiveness scoring dimension for Phase 2.

Two components:
  A) Deterministic keyword-matching on dodge phrases
  B) LLM-based scoring on Q&A section chunks only

(B) has two shapes, chosen by prompt version:
  v1/v2 — the whole Q&A is batched by word count and the batch verdicts are
          averaged. Measured to destroy the scorer's range (KNOWN_ISSUES.md
          BLOCKER-6).
  v3    — the Q&A is split into individual analyst exchanges, each is scored
          independently, and the aggregation into a transcript score happens
          here in code where it is named and testable.
"""

import re
import json
import logging
from collections import Counter
from typing import Callable

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
    r"(?:first\s+question\s+from\s+the\s+line\s+of|"
    r"we'?ll\s+take\s+our\s+first\s+question|"
    r"we\s+have\s+(?:our|a)\s+first\s+question|"
    r"first\s+question\s+is\s+from\s+the\s+line\s+of)",
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


EVASIVENESS_SYSTEM_PROMPT_V2 = """You are an analyst evaluating how directly management answers analyst questions during an earnings call.

Score evasiveness 1-10. Higher means more evasive.

THE CENTRAL DISTINCTION

Not answering is not the same as evading. Separate two things:

  (a) Does management give the substance asked for?
  (b) If not, do they say plainly why not?

A clear, reasoned decline is NOT evasive. "We don't disclose segment margins"
or "we don't give quarterly guidance, only annual" states a policy and leaves
the analyst correctly informed about what they will and won't get. Score these
LOW (2-4) even though the question went unanswered.

What IS evasive is the appearance of an answer that carries no information:
restating prepared remarks, answering a different question, retreating to
process ("we are evaluating"), or a stream of qualifiers that commits to
nothing. The analyst leaves unable to tell whether an answer was given.

Ask of each non-answer: could a listener state the reason it was not answered?
If yes, that is a boundary. If no, that is a dodge.

SCALE

1-2  Consistently direct. Specific numbers, timelines and metrics.
3-4  Mostly direct. Some things declined, but the reason is stated each time.
     A guidance range with the reasoning behind it belongs here, not higher.
5-6  Mixed. Real answers on some questions, unexplained deflection on others.
7-8  Mostly deflection. Repeated non-answers with no reason offered; prepared
     remarks recycled in place of a response.
9-10 Near-total. Almost nothing asked for is provided or explained.

USE THE WHOLE SCALE. A genuinely transparent call is a 2, not a 5. Do not
cluster in the middle to be safe — a score that is never low and never high
carries no information.

WEIGH THE WHOLE Q&A, NOT THE WORST MOMENT

Judge the proportion of questions handled well against those deflected. One
sharp refusal in an otherwise open call is not a high score. Recurring
deflection across many questions is, even if each instance is polite.

DO NOT PENALISE

- Declining with a stated reason or a consistent disclosure policy
- Ranges and scenarios that come with the reasoning behind them
- Genuine uncertainty that is named as uncertainty ("we don't know yet, it
  depends on X") — this is candour, not evasion
- Brevity, bluntness or an abrupt manner. Tone is not evasiveness. A curt but
  informative answer scores LOW; a warm, fluent answer that says nothing
  scores HIGH.

Judge only management's answers. Ignore the moderator and the analysts' own
questions.

You MUST return ONLY valid JSON. No explanation, no markdown, no backticks.
Format:
{"evasiveness_score": <int 1-10>, "supporting_quotes": ["quote 1", "quote 2", "quote 3"]}

Each supporting_quote must be an exact verbatim sentence from the transcript that best justifies the score. Maximum 3 quotes."""  # noqa: E501


EVASIVENESS_SYSTEM_PROMPT_V3 = """You are an analyst judging how directly management answered analyst questions on an earnings call.

You will be given several numbered exchanges. Each one is a single analyst question and the answer management gave it. Score EACH EXCHANGE ON ITS OWN, 1-10, higher meaning more evasive. Do not blend them into one verdict and do not let a bad exchange raise the score of a good one.

WHAT YOU ARE JUDGING

Only management's answer. Ignore the moderator, ignore how the analyst phrased the question, and ignore whether the question was fair.

THE TEST

After this answer, does the analyst have the thing they asked for?

  - They have it, or enough of it to act on          -> LOW
  - They do not have it, but they were told plainly
    why not, or when they will get it                -> MIDDLE
  - They do not have it, and no reason was offered   -> HIGH

The middle band is the important one. Refusing to disclose something is not the same as pretending to answer. A stated boundary leaves the analyst correctly informed about what they will and will not get; a bare refusal leaves them with nothing, and an answer-shaped non-answer leaves them unsure they were even refused.

ANCHORS

1-2   Direct. Specific numbers, dates, mechanisms or causes. The question is
      answered on its own terms, even if the answer is short or blunt.
3-4   Substantive but partial. Most of what was asked is given, or the missing
      part is declined with a reason stated in the same breath - a disclosure
      policy, a timing constraint, an uncertainty that is named as such.
5-6   Half an answer. Real content on one part of the question while another
      part is left untouched, or a direction given with nothing to size it.
7-8   Non-answer. A refusal with no reason, prepared remarks recycled in place
      of a response, a pivot to a different question, or process talk
      ("we are evaluating", "we will come back to you") standing in for
      substance.
9-10  Nothing at all. The question is declined or talked past, no reason is
      offered, and the answer does not engage with what was asked.

USE THE WHOLE SCALE. Most calls contain some exchanges that are genuinely 1-2 and some that are genuinely 8-9. If every exchange you score lands on 5 or 6, you are not scoring - you are hedging, and a score that is never low and never high carries no information.

DO NOT PENALISE

- Brevity or bluntness. Tone is not evasiveness. A curt but informative answer
  is LOW; a warm, fluent answer that says nothing is HIGH.
- Genuine uncertainty that is named as uncertainty ("we do not know yet, it
  depends on X"). That is candour.
- Declining consistently with a stated disclosure policy.

You MUST return ONLY valid JSON. No explanation, no markdown, no backticks.
Format:
{"exchange_scores": [{"exchange": <the number shown in [EXCHANGE n]>, "evasiveness_score": <int 1-10>, "quote": "<exact verbatim sentence from management's answer that best justifies the score>"}]}

Return one entry for every exchange you were given, using the exact numbers shown."""  # noqa: E501


# ---- Q&A segmentation into individual exchanges (v3) ----

# Every transcript in the corpus routes questions through a moderator who names
# the next analyst, so the moderator's turn is the one reliable boundary between
# exchanges. Measured across all 11 transcripts on 2026-08-25: 10-18 exchanges
# each, median ~400 words, retaining ~99% of Q&A words.
#
# The INFY-only phrase "next question is from the line of" was rejected as the
# marker: it appears 11-13 times per INFY transcript and 0-2 times per TCS one,
# so it would have silently produced a single giant "exchange" for most of TCS.
_MODERATOR_TURN = re.compile(r"(?:^|\s)Moderator\s*:", re.IGNORECASE)

# Below this, a segment is a stray fragment -- a "Thank you." sign-off or a
# page-footer artefact -- not a question worth spending a score on.
_MIN_EXCHANGE_WORDS = 40


def split_qa_into_exchanges(
    chunks: list[str], min_words: int = _MIN_EXCHANGE_WORDS
) -> list[str]:
    """Split Q&A chunks into individual question-and-answer exchanges.

    Chunks are joined before splitting because chunking is word-count based and
    routinely cuts through the middle of an exchange -- segmenting per chunk
    would inherit exactly the arbitrary boundaries this is meant to remove.
    """
    qa_text = "\n\n".join(chunks)
    segments: list[str] = []
    last = 0
    for match in _MODERATOR_TURN.finditer(qa_text):
        segment = qa_text[last:match.start()].strip()
        if segment:
            segments.append(segment)
        last = match.start()
    tail = qa_text[last:].strip()
    if tail:
        segments.append(tail)
    return [s for s in segments if len(s.split()) >= min_words]


# ---- Aggregating per-exchange scores into a transcript score ----
#
# This is the step that decides whether the scorer has any range, so it is
# explicit, named and swappable rather than an averaging line buried in the
# transport layer (KNOWN_ISSUES.md BLOCKER-6).
#
# The default is WORST3_MEAN, for two reasons that point the same way:
#
#   1. It is what the product claims. EarningsLens exists to surface red flags.
#      A call with two flat refusals among fifteen candid answers is a call
#      worth flagging, and any mean over fifteen buries it.
#   2. It is the only aggregate commensurable with the labels. The human review
#      in notebooks/reading-notes.md scored each transcript from THREE
#      supporting quotes -- the three the v1 model surfaced as most evasive --
#      not from the whole call. So the label is already a worst-few statistic.
#      Comparing a whole-call mean against it was measuring two different
#      quantities, which is part of why evasiveness-v2 correlates negatively.
#
# Read the second reason as a warning as much as a justification: choosing an
# aggregator that matches how the labels were built makes the comparison valid,
# but it does NOT make a good score on those labels out-of-sample evidence.
# See EVALUATION.md section 1.5.
#
# Every per-exchange score is persisted, so any of these can be re-measured
# offline against new labels without spending another day of quota.

def _mean(values: list[int]) -> float:
    return sum(values) / len(values)


def _worst_n_mean(values: list[int], n: int) -> float:
    return _mean(sorted(values, reverse=True)[:n])


AGGREGATORS: dict[str, Callable[[list[int]], float]] = {
    "worst3_mean": lambda v: _worst_n_mean(v, 3),
    "worst2_mean": lambda v: _worst_n_mean(v, 2),
    "max": lambda v: float(max(v)),
    "mean": _mean,
    "median": lambda v: float(sorted(v)[len(v) // 2]) if len(v) % 2
    else _mean(sorted(v)[len(v) // 2 - 1:len(v) // 2 + 1]),
    # Share of exchanges that are outright non-answers (the 7+ band), mapped
    # onto 1-10. Range-preserving by construction, and severity-blind on
    # purpose, as a contrast to the order statistics above.
    "dodge_rate": lambda v: 1.0 + 9.0 * (len([s for s in v if s >= 7]) / len(v)),
}

DEFAULT_AGGREGATOR = "worst3_mean"


def aggregate_exchange_scores(
    scores: list[int], method: str = DEFAULT_AGGREGATOR
) -> int | None:
    """Reduce per-exchange scores to one transcript score, clamped to 1-10."""
    if method not in AGGREGATORS:
        raise ValueError(
            f"Unknown aggregator {method!r}. Available: {', '.join(sorted(AGGREGATORS))}"
        )
    if not scores:
        return None
    return max(1, min(10, round(AGGREGATORS[method](scores))))


def score_evasiveness_llm(
    chunks: list[str], model: str | None = None, prompt_version: str | None = None
) -> dict:
    """Score evasiveness using LLM API. Only Q&A chunks should be passed in."""
    from src.scoring._llm_dimension_scorer import score_dimension_llm
    from src.scoring.prompts import get_prompt

    system_prompt, _ = get_prompt("evasiveness", prompt_version)
    return score_dimension_llm(
        chunks,
        dimension_name="evasiveness",
        system_prompt=system_prompt,
        score_key="evasiveness_score",
        user_prompt_instruction=(
            "Score management evasiveness — whether they are dodging questions, "
            "giving non-answers, pivoting to prepared remarks, or otherwise avoiding "
            "direct answers to analyst questions."
        ),
        model=model,
    )


def score_evasiveness_per_exchange(
    qa_chunks: list[str],
    model: str | None = None,
    prompt_version: str | None = None,
    aggregator: str = DEFAULT_AGGREGATOR,
) -> dict:
    """Score each analyst exchange separately, then aggregate (v3).

    Returns the same keys the batch path returns -- `evasiveness_score`,
    `supporting_quotes`, `raw_response` -- so the storage layer needs no
    special case. `raw_response` is JSON rather than raw model text, because
    the per-exchange scores are the expensive part of the run and must survive
    in a form something can read back without regex.
    """
    from src.scoring._exchange_scorer import score_exchanges_llm
    from src.scoring.prompts import get_prompt

    system_prompt, resolved = get_prompt("evasiveness", prompt_version)
    exchanges = split_qa_into_exchanges(qa_chunks)
    if not exchanges:
        return {
            "evasiveness_score": None,
            "supporting_quotes": [],
            "error": "Q&A section could not be split into exchanges",
        }

    result = score_exchanges_llm(
        exchanges,
        dimension_name="evasiveness",
        system_prompt=system_prompt,
        score_key="evasiveness_score",
        model=model,
    )

    entries = result.get("exchange_scores", [])
    scores = [e["evasiveness_score"] for e in entries]
    aggregate = aggregate_exchange_scores(scores, aggregator)

    if aggregate is not None and len(entries) < result.get("exchanges_total", 0):
        # Same reasoning as the batch path: a shrunk divisor makes a partial
        # score look complete. Say so.
        logger.warning(
            "  evasiveness scored %d of %d exchange(s) - the aggregate covers "
            "only the scored ones",
            len(entries), result["exchanges_total"],
        )

    # The exchanges the aggregator actually acted on, so the evidence shown to
    # a reader matches the number produced.
    top = sorted(entries, key=lambda e: e["evasiveness_score"], reverse=True)[:3]

    payload = {
        "prompt_version": resolved,
        "aggregator": aggregator,
        "aggregate_score": aggregate,
        "exchanges_total": result.get("exchanges_total", len(exchanges)),
        "exchanges_scored": len(entries),
        "exchange_scores": entries,
        "raw_model_responses": result.get("raw_response", ""),
    }

    return {
        "evasiveness_score": aggregate,
        "supporting_quotes": [e["quote"] for e in top if e.get("quote")][:3],
        "raw_response": json.dumps(payload, ensure_ascii=False),
        "usage": result.get("usage"),
        "aggregator": aggregator,
        "exchange_scores": entries,
        "exchanges_total": result.get("exchanges_total", len(exchanges)),
        "exchanges_scored": len(entries),
        **({"error": result["error"]} if result.get("error") else {}),
    }


# ---- Combined scoring ----

# Versions that score one exchange at a time rather than one word-count batch.
PER_EXCHANGE_VERSIONS = {"evasiveness-v3"}


def score_transcript_evasiveness(
    chunks: list[str],
    model: str | None = None,
    prompt_version: str | None = None,
    aggregator: str = DEFAULT_AGGREGATOR,
) -> dict:
    """Full evasiveness scoring: keyword count + Q&A detection + LLM score.
    Keyword matching is restricted to Q&A chunks only to avoid
    safe-harbor boilerplate false positives in prepared remarks.

    The prompt version chooses the LLM strategy: v3 scores each analyst
    exchange separately, v1/v2 batch the Q&A by word count.
    """
    from src.scoring.prompts import resolve_version

    resolved = resolve_version("evasiveness", prompt_version)

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

    if resolved in PER_EXCHANGE_VERSIONS:
        llm_result = score_evasiveness_per_exchange(
            qa_chunks, model=model, prompt_version=resolved, aggregator=aggregator
        )
    else:
        llm_result = score_evasiveness_llm(qa_chunks, model=model, prompt_version=resolved)

    return {
        "keyword_result": kw_result,
        "qa_detected": True,
        "qa_boundary_chunk_index": qa_start,
        "qa_chunks_used": len(qa_chunks),
        "llm_result": llm_result,
    }
