"""
Scoring orchestrator — runs all 5 dimensions and stores results.

This is the only file in src/scoring/ that imports both scoring modules
and storage. Individual dimension modules do NOT import db.py.
"""

import logging
from typing import Callable

from src.scoring.evasiveness import score_transcript_evasiveness
from src.scoring.sentiment_shift import score_transcript_sentiment_shift
from src.scoring.complexity_spike import score_transcript_complexity_spike
from src.scoring.overpromising import score_transcript_overpromising
from src.scoring.forward_guidance_vagueness import score_transcript_forward_guidance_vagueness
from src.scoring._llm_dimension_scorer import DailyQuotaExhausted
from src.scoring.prompts import resolve_version
from src.storage.db import store_score
from config import LLM_MODEL_NAME

logger = logging.getLogger("earningslens")

# Each scorer takes the chunk list and returns a result dict.
DIMENSION_MODULES: dict[str, Callable[..., dict]] = {
    "evasiveness": score_transcript_evasiveness,
    "sentiment_shift": score_transcript_sentiment_shift,
    "complexity_spike": score_transcript_complexity_spike,
    "overpromising": score_transcript_overpromising,
    "forward_guidance_vagueness": score_transcript_forward_guidance_vagueness,
}

# Each module returns a different key for the score. This maps dimension name
# to the key used in that module's return dict.
SCORE_KEY_MAP: dict[str, str] = {
    "evasiveness": "evasiveness_score",
    "sentiment_shift": "sentiment_shift_score",
    "complexity_spike": "complexity_spike_score",
    "overpromising": "overpromising_score",
    "forward_guidance_vagueness": "forward_guidance_vagueness_score",
}


def score_transcript_all(
    conn,
    transcript_id: int,
    chunks: list[str],
    model: str | None = None,
    dimensions: list[str] | None = None,
    prompt_versions: dict[str, str] | None = None,
) -> dict:
    """Run the scoring dimensions against chunks and store results.

    Args:
        conn: SQLite connection.
        transcript_id: The transcripts.id for this transcript.
        chunks: List of chunk texts (all chunks for the transcript).
        model: Optional LLM model override.
        dimensions: Which dimensions to score. Defaults to all five. Narrowing
            this is how a complete series for one dimension can be built inside
            a constrained token budget — a full sweep costs roughly five times
            as much (see KNOWN_ISSUES.md BLOCKER-4).
        prompt_versions: Optional {dimension: version} override. Defaults come
            from src.scoring.prompts.DEFAULT_VERSIONS. The version actually
            used is what gets stored, so a score can always be traced to the
            exact prompt that produced it.

    Returns:
        dict mapping dimension name -> {"score", "error", "result"}. `score` is
        None when the dimension failed; `error` carries why.
    """
    selected = dimensions or list(DIMENSION_MODULES)
    unknown = [d for d in selected if d not in DIMENSION_MODULES]
    if unknown:
        raise ValueError(f"Unknown dimension(s): {', '.join(unknown)}")

    # Resolve up front so an unknown version fails before any tokens are spent.
    requested = prompt_versions or {}
    versions = {d: resolve_version(d, requested.get(d)) for d in selected}
    # The model actually used, so the model_name we record matches the model
    # that produced the score. Recording the requested override while the
    # scorer silently fell back to the configured default is what made the
    # existing `scores` rows untrustworthy.
    used_model = model or LLM_MODEL_NAME or "unknown"

    results: dict[str, dict] = {}
    for dimension in selected:
        scorer = DIMENSION_MODULES[dimension]
        logger.info("Scoring dimension=%s for transcript_id=%d", dimension, transcript_id)

        try:
            result = scorer(chunks, model=model, prompt_version=versions[dimension])
        except DailyQuotaExhausted:
            # No point continuing: every remaining dimension will fail the same
            # way. Let the caller stop and report honestly.
            logger.error("    %s: provider token budget exhausted - stopping", dimension)
            results[dimension] = {"score": None, "error": "daily quota exhausted", "result": None}
            raise
        except Exception as e:
            logger.error("    %s error: %s", dimension, e)
            results[dimension] = {"score": None, "error": str(e), "result": None}
            continue

        # Some dimensions nest the LLM payload under "llm_result"; others return
        # it flat. Accept both so callers do not have to know which is which.
        score_key = SCORE_KEY_MAP[dimension]
        llm_result = result.get("llm_result", result)
        score_value = llm_result.get(score_key)
        quotes = llm_result.get("supporting_quotes", [])
        raw = llm_result.get("raw_response", "")

        if score_value is None:
            error = llm_result.get("error") or "no score returned"
            logger.warning(
                "    %s: FAILED (%s) for transcript_id=%d",
                dimension, error, transcript_id,
            )
            results[dimension] = {"score": None, "error": error, "result": result}
            continue

        store_score(
            conn,
            transcript_id,
            dimension,
            score_value,
            quotes,
            used_model,
            versions[dimension],
            raw,
        )
        logger.info("    %s: %d/10", dimension, score_value)
        results[dimension] = {"score": score_value, "error": None, "result": result}

    return results
