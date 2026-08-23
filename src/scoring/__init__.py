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
from src.storage.db import store_score

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


def score_transcript_all(conn, transcript_id: int, chunks: list[str], model: str | None = None) -> dict:
    """Run all 5 dimensions against chunks and store results in the scores table.

    Args:
        conn: SQLite connection.
        transcript_id: The transcripts.id for this transcript.
        chunks: List of chunk texts (all chunks for the transcript).
        model: Optional LLM model override.

    Returns:
        dict mapping dimension name -> score result dict.
    """
    results = {}
    for dimension, scorer in DIMENSION_MODULES.items():
        logger.info("Scoring dimension=%s for transcript_id=%d", dimension, transcript_id)
        result = scorer(chunks)

        # Extract score from the dimension-specific result key
        score_key = SCORE_KEY_MAP[dimension]
        llm_result = result.get("llm_result", result)
        score_value = llm_result.get(score_key)
        quotes = llm_result.get("supporting_quotes", [])
        raw = llm_result.get("raw_response", "")

        if score_value is not None:
            store_score(
                conn,
                transcript_id,
                dimension,
                score_value,
                quotes,
                model or "unknown",
                f"{dimension}-v1",
                raw,
            )
            logger.info("Stored %s score=%d for transcript_id=%d", dimension, score_value, transcript_id)
        else:
            logger.warning(
                "No score returned for dimension=%s transcript_id=%d — error=%s",
                dimension, transcript_id, llm_result.get("error", "unknown"),
            )

        results[dimension] = result

    return results
