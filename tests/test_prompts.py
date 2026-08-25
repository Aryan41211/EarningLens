"""Prompt registry and version-integrity tests.

The checksums below pin each prompt's text to its declared version. Editing a
prompt without registering a new version fails these tests on purpose.

That matters because `prompt_version` is what the comparability guard and the
evaluation harness use to decide whether two scores may be compared. Before
this, the version was hardcoded as f"{dimension}-v1" at the storage call site,
so a prompt could be rewritten and every new score would still claim to be v1 —
incomparable scores looking comparable, with nothing able to detect it.

If a test here fails after an intentional edit:
  1. register the new text under a NEW version in src/scoring/prompts.py
  2. add its checksum below
  3. re-score the whole dimension — never append (SCORING_METHODOLOGY.md section 7)
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import SCORE_DIMENSIONS
from src.scoring.prompts import (
    DEFAULT_VERSIONS,
    PROMPTS,
    available_versions,
    get_prompt,
    prompt_checksum,
    resolve_version,
)

# version -> sha256[:16] of the prompt text
PINNED_CHECKSUMS = {
    "evasiveness-v1": "da8e0d5b62db48e9",
    "evasiveness-v2": "61907d99214e7576",
    "evasiveness-v3": "f305dbd1d3222b03",
    "sentiment_shift-v1": "e2ba8b7b902a57ad",
    "complexity_spike-v1": "452fe8203a617903",
    "overpromising-v1": "72db460f23494d1c",
    "forward_guidance_vagueness-v1": "5c69ac6888270559",
}


class TestRegistry:
    def test_every_dimension_is_registered(self):
        assert set(PROMPTS) == set(SCORE_DIMENSIONS)

    def test_every_dimension_has_a_default(self):
        assert set(DEFAULT_VERSIONS) == set(SCORE_DIMENSIONS)

    def test_defaults_point_at_registered_versions(self):
        for dimension, version in DEFAULT_VERSIONS.items():
            assert version in PROMPTS[dimension]

    def test_version_names_are_prefixed_by_their_dimension(self):
        """A bare 'v2' in the scores table would be ambiguous across dimensions."""
        for dimension, versions in PROMPTS.items():
            for version in versions:
                assert version.startswith(f"{dimension}-"), version

    def test_prompts_are_substantial(self):
        for dimension, versions in PROMPTS.items():
            for version, text in versions.items():
                assert len(text) > 200, f"{version} looks truncated"
                assert "valid JSON" in text, f"{version} must demand JSON output"
                assert f"{dimension}_score" in text, f"{version} must name its score key"


class TestResolution:
    def test_none_resolves_to_default(self):
        assert resolve_version("evasiveness") == DEFAULT_VERSIONS["evasiveness"]

    def test_explicit_version_is_honoured(self):
        assert resolve_version("evasiveness", "evasiveness-v2") == "evasiveness-v2"

    def test_unknown_version_raises_with_the_available_ones(self):
        with pytest.raises(ValueError, match="evasiveness-v1"):
            resolve_version("evasiveness", "evasiveness-v99")

    def test_unknown_dimension_raises(self):
        with pytest.raises(ValueError, match="Unknown dimension"):
            resolve_version("charisma")

    def test_get_prompt_returns_text_and_resolved_version(self):
        text, version = get_prompt("evasiveness", "evasiveness-v2")
        assert version == "evasiveness-v2"
        assert text == PROMPTS["evasiveness"]["evasiveness-v2"]

    def test_v1_and_v2_are_different_text(self):
        v1, _ = get_prompt("evasiveness", "evasiveness-v1")
        v2, _ = get_prompt("evasiveness", "evasiveness-v2")
        assert v1 != v2

    def test_evasiveness_default_is_still_v1(self):
        """v2 is unproven. Switching the default silently would invalidate the
        existing series without anyone choosing to."""
        assert DEFAULT_VERSIONS["evasiveness"] == "evasiveness-v1"


class TestChecksums:
    """Editing a prompt without bumping its version must fail."""

    def test_every_registered_version_is_pinned(self):
        registered = {v for versions in PROMPTS.values() for v in versions}
        assert registered == set(PINNED_CHECKSUMS), (
            "A prompt version is registered but not pinned (or vice versa). "
            "Add its checksum to PINNED_CHECKSUMS."
        )

    @pytest.mark.parametrize("dimension", sorted(PROMPTS))
    def test_prompt_text_matches_its_pinned_checksum(self, dimension):
        for version in available_versions(dimension):
            actual = prompt_checksum(dimension, version)
            assert actual == PINNED_CHECKSUMS[version], (
                f"{version} text changed but the version did not.\n"
                f"  expected {PINNED_CHECKSUMS[version]}, got {actual}\n"
                "Register the new text as a NEW version and re-score the "
                "dimension; do not silently edit a version that has scores."
            )


class TestV2AddressesMeasuredFailures:
    """v2 exists to fix specific failures the human review measured.

    These are not style checks — each maps to a documented disagreement in
    EVALUATION.md section 1.2.
    """

    def _v2(self):
        return get_prompt("evasiveness", "evasiveness-v2")[0].lower()

    def test_separates_reasoned_refusal_from_dodging(self):
        text = self._v2()
        assert "reason" in text and "policy" in text

    def test_tells_the_model_not_to_penalise_tone(self):
        assert "tone is not evasiveness" in self._v2()

    def test_pushes_against_mid_scale_clustering(self):
        """LLM scores spanned 4-7 while human scores spanned 2-9."""
        assert "whole scale" in self._v2()

    def test_asks_for_proportion_not_worst_moment(self):
        assert "proportion" in self._v2()


class TestV3ScoresOneExchangeAtATime:
    """v3 exists to change the unit of judgement, not just the wording.

    v1/v2 ask a ~2000-word window to judge the whole call and then average the
    windows, which was measured to flatten every transcript to 5 or 6
    (KNOWN_ISSUES.md BLOCKER-6). v3 asks about one analyst exchange at a time.
    """

    def _v3(self):
        return get_prompt("evasiveness", "evasiveness-v3")[0].lower()

    def test_scores_each_exchange_independently(self):
        text = self._v3()
        assert "each exchange on its own" in text
        assert "do not blend them" in text

    def test_demands_the_indexed_output_shape_the_parser_expects(self):
        """The parser matches scores back to exchanges by number."""
        text = get_prompt("evasiveness", "evasiveness-v3")[0]
        assert '"exchange_scores"' in text
        assert '"exchange"' in text
        assert '"evasiveness_score"' in text

    def test_keeps_the_reasoned_decline_distinction(self):
        """The one thing v2 got right, confirmed against the human review."""
        text = self._v3()
        assert "refusing to disclose something is not the same" in text

    def test_still_pushes_against_mid_scale_clustering(self):
        assert "use the whole scale" in self._v3()

    def test_still_tells_the_model_not_to_penalise_tone(self):
        assert "tone is not evasiveness" in self._v3()

    def test_default_is_not_v3(self):
        """v3 is unmeasured. Switching the default would silently invalidate
        the existing series -- the same rule that kept the default at v1 when
        v2 landed."""
        assert DEFAULT_VERSIONS["evasiveness"] != "evasiveness-v3"
