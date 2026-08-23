"""Prompt registry and version integrity.

A score is only comparable to another produced by the same
(model_name, prompt_version) pair. `prompt_version` was previously hardcoded as
f"{dimension}-v1" at the single call site, so editing a prompt left every new
score still stamped "v1" — incomparable scores looked comparable, and the
comparability guard in src/trends/metrics.py could not see it.

Versions now live beside the prompts they name, and `tests/test_prompts.py`
pins a checksum per version: editing a prompt without bumping its version fails
the suite. That makes the rule mechanical rather than remembered.

To revise a prompt:
  1. add the new text as a new constant
  2. register it here under a new version string
  3. update the checksum in tests/test_prompts.py
  4. re-score the whole dimension — never append to a series (SCORING_METHODOLOGY.md section 7)
"""

import hashlib

from src.scoring.complexity_spike import COMPLEXITY_SPIKE_SYSTEM_PROMPT
from src.scoring.evasiveness import (
    EVASIVENESS_SYSTEM_PROMPT,
    EVASIVENESS_SYSTEM_PROMPT_V2,
)
from src.scoring.forward_guidance_vagueness import FORWARD_GUIDANCE_VAGUENESS_SYSTEM_PROMPT
from src.scoring.overpromising import OVERPROMISING_SYSTEM_PROMPT
from src.scoring.sentiment_shift import SENTIMENT_SHIFT_SYSTEM_PROMPT

# dimension -> {version: prompt text}
PROMPTS: dict[str, dict[str, str]] = {
    "evasiveness": {
        "evasiveness-v1": EVASIVENESS_SYSTEM_PROMPT,
        "evasiveness-v2": EVASIVENESS_SYSTEM_PROMPT_V2,
    },
    "sentiment_shift": {"sentiment_shift-v1": SENTIMENT_SHIFT_SYSTEM_PROMPT},
    "complexity_spike": {"complexity_spike-v1": COMPLEXITY_SPIKE_SYSTEM_PROMPT},
    "overpromising": {"overpromising-v1": OVERPROMISING_SYSTEM_PROMPT},
    "forward_guidance_vagueness": {
        "forward_guidance_vagueness-v1": FORWARD_GUIDANCE_VAGUENESS_SYSTEM_PROMPT
    },
}

# The version used when none is requested. Deliberately still v1 for
# evasiveness: v2 exists but is unproven, and silently switching would
# invalidate the existing series without anyone choosing to.
DEFAULT_VERSIONS: dict[str, str] = {
    "evasiveness": "evasiveness-v1",
    "sentiment_shift": "sentiment_shift-v1",
    "complexity_spike": "complexity_spike-v1",
    "overpromising": "overpromising-v1",
    "forward_guidance_vagueness": "forward_guidance_vagueness-v1",
}


def available_versions(dimension: str) -> list[str]:
    """Versions registered for a dimension, oldest first."""
    return list(PROMPTS[dimension])


def resolve_version(dimension: str, version: str | None = None) -> str:
    """Validate a requested version, or return the dimension's default."""
    if dimension not in PROMPTS:
        raise ValueError(f"Unknown dimension: {dimension}")
    if version is None:
        return DEFAULT_VERSIONS[dimension]
    if version not in PROMPTS[dimension]:
        raise ValueError(
            f"Unknown prompt version {version!r} for {dimension}. "
            f"Available: {', '.join(available_versions(dimension))}"
        )
    return version


def get_prompt(dimension: str, version: str | None = None) -> tuple[str, str]:
    """Return (prompt_text, resolved_version)."""
    resolved = resolve_version(dimension, version)
    return PROMPTS[dimension][resolved], resolved


def prompt_checksum(dimension: str, version: str) -> str:
    """Stable short hash of a prompt's text, used to detect silent edits."""
    text = PROMPTS[dimension][version]
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
