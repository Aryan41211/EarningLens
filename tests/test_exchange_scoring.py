"""Tests for per-exchange scoring (evasiveness-v3).

v3 exists because of KNOWN_ISSUES.md BLOCKER-6: v1/v2 hand a ~2000-word window
to the model, ask it to judge the whole call, and average the windows. Measured
on the 7 evasiveness-v2 transcripts, the model's per-window verdicts span 3-8
and every stored average is 5 or 6.

So the behaviour these tests protect is not "does it return a number" but
"does the number still have range". `TestRangeIsPreserved` is the point of the
file; the rest keeps the machinery around it honest.

Every LLM call here is mocked. A test that reaches the network is a bug in the
test (KNOWN_ISSUES.md HIGH-1).
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.scoring._exchange_scorer import (  # noqa: E402
    build_exchange_prompt,
    parse_exchange_scores,
)
from src.scoring.evasiveness import (  # noqa: E402
    AGGREGATORS,
    DEFAULT_AGGREGATOR,
    aggregate_exchange_scores,
    score_transcript_evasiveness,
    split_qa_into_exchanges,
)


def _exchange(speaker: str, words: int = 60) -> str:
    return f"{speaker}: " + " ".join(["word"] * words)


def _qa_text(n: int) -> list[str]:
    """A Q&A section with n moderator-delimited exchanges."""
    parts = []
    for i in range(n):
        parts.append(
            f"Moderator:\nNext question is from the line of Analyst {i}.\n"
            + _exchange(f"Analyst {i}", 30)
            + "\n"
            + _exchange("Management", 40)
        )
    return parts


class TestSegmentation:
    def test_splits_on_each_moderator_turn(self):
        assert len(split_qa_into_exchanges(_qa_text(5))) == 5

    def test_joins_chunks_before_splitting(self):
        """Chunking is word-count based and cuts through exchanges.

        Segmenting per chunk would inherit exactly the arbitrary boundaries v3
        exists to remove.
        """
        one_exchange = "Moderator:\nNext question.\n" + _exchange("Mgmt", 80)
        halfway = len(one_exchange) // 2
        split_across_chunks = [one_exchange[:halfway], one_exchange[halfway:]]
        assert len(split_qa_into_exchanges(split_across_chunks)) == 1

    def test_keeps_text_before_the_first_moderator_turn(self):
        chunks = [_exchange("Mgmt", 60) + "\n\nModerator:\nNext.\n" + _exchange("Mgmt", 60)]
        assert len(split_qa_into_exchanges(chunks)) == 2

    def test_drops_fragments_below_the_word_floor(self):
        """A 'Thank you.' sign-off is not a question worth spending a score on."""
        chunks = ["Moderator:\nThanks.", "Moderator:\n" + _exchange("Mgmt", 80)]
        assert len(split_qa_into_exchanges(chunks)) == 1

    def test_is_case_insensitive_about_the_marker(self):
        chunks = ["MODERATOR:\n" + _exchange("Mgmt", 60), "moderator:\n" + _exchange("Mgmt", 60)]
        assert len(split_qa_into_exchanges(chunks)) == 2

    def test_empty_input_yields_nothing(self):
        assert split_qa_into_exchanges([]) == []

    def test_no_moderator_still_yields_the_whole_section(self):
        """TCS transcripts do not use the INFY 'next question' phrasing; the
        segmenter must not silently return nothing when a marker is absent."""
        assert len(split_qa_into_exchanges([_exchange("Mgmt", 200)])) == 1


class TestAggregators:
    def test_default_is_worst3_mean(self):
        assert DEFAULT_AGGREGATOR == "worst3_mean"

    def test_worst3_mean_uses_the_three_highest(self):
        assert aggregate_exchange_scores([1, 1, 1, 8, 9, 10], "worst3_mean") == 9

    def test_worst3_mean_handles_fewer_than_three(self):
        assert aggregate_exchange_scores([4, 8], "worst3_mean") == 6

    def test_mean_is_available_for_comparison(self):
        assert aggregate_exchange_scores([1, 1, 1, 8, 9, 10], "mean") == 5

    def test_max(self):
        assert aggregate_exchange_scores([2, 9, 3], "max") == 9

    def test_median_odd_and_even(self):
        assert aggregate_exchange_scores([1, 5, 9], "median") == 5
        assert aggregate_exchange_scores([1, 3, 7, 9], "median") == 5

    def test_dodge_rate_maps_share_of_non_answers_onto_the_scale(self):
        assert aggregate_exchange_scores([1, 1, 1, 1], "dodge_rate") == 1
        assert aggregate_exchange_scores([9, 9, 9, 9], "dodge_rate") == 10
        assert aggregate_exchange_scores([1, 1, 9, 9], "dodge_rate") == 6

    def test_result_is_clamped_to_the_scale(self):
        for method in AGGREGATORS:
            assert 1 <= aggregate_exchange_scores([10] * 5, method) <= 10
            assert 1 <= aggregate_exchange_scores([1] * 5, method) <= 10

    def test_empty_scores_give_no_score_rather_than_zero(self):
        assert aggregate_exchange_scores([], "worst3_mean") is None

    def test_unknown_aggregator_names_the_available_ones(self):
        with pytest.raises(ValueError, match="worst3_mean"):
            aggregate_exchange_scores([5], "geometric_vibes")


class TestRangeIsPreserved:
    """The regression this whole version exists to prevent.

    Two transcripts whose exchanges differ sharply must not collapse onto the
    same score. Averaging is what did that, so it is the contrast case.
    """

    CANDID = [1, 2, 1, 3, 2, 1, 2, 4, 1, 2, 3, 1]
    EVASIVE = [8, 9, 7, 8, 2, 9, 8, 3, 9, 7, 8, 9]

    def test_mean_flattens_the_two_towards_each_other(self):
        candid = aggregate_exchange_scores(self.CANDID, "mean")
        evasive = aggregate_exchange_scores(self.EVASIVE, "mean")
        assert evasive - candid < 6

    def test_the_default_aggregator_keeps_them_apart(self):
        candid = aggregate_exchange_scores(self.CANDID, DEFAULT_AGGREGATOR)
        evasive = aggregate_exchange_scores(self.EVASIVE, DEFAULT_AGGREGATOR)
        assert candid <= 3
        assert evasive >= 8

    def test_a_few_flat_refusals_are_not_buried_by_many_good_answers(self):
        """The product claim is red flags, and a mean of fifteen hides two."""
        mostly_fine = [1] * 13 + [9, 9]
        assert aggregate_exchange_scores(mostly_fine, "mean") <= 3
        assert aggregate_exchange_scores(mostly_fine, DEFAULT_AGGREGATOR) >= 6


class TestPromptConstruction:
    def test_numbers_are_global_not_per_request(self):
        prompt = build_exchange_prompt(["a", "b"], start_index=7)
        assert "[EXCHANGE 7]" in prompt
        assert "[EXCHANGE 8]" in prompt

    def test_tells_the_model_not_to_renumber(self):
        assert "renumber" in build_exchange_prompt(["a"], 1)


class TestParsing:
    KEY = "evasiveness_score"

    def test_parses_the_documented_shape(self):
        raw = json.dumps({"exchange_scores": [
            {"exchange": 1, "evasiveness_score": 7, "quote": "q1"},
            {"exchange": 2, "evasiveness_score": 2, "quote": "q2"},
        ]})
        assert parse_exchange_scores(raw, self.KEY) == [(1, 7, "q1"), (2, 2, "q2")]

    def test_accepts_a_bare_list(self):
        raw = json.dumps([{"exchange": 3, "evasiveness_score": 5}])
        assert parse_exchange_scores(raw, self.KEY) == [(3, 5, "")]

    def test_accepts_a_plain_score_key(self):
        raw = json.dumps({"exchange_scores": [{"exchange": 1, "score": 6}]})
        assert parse_exchange_scores(raw, self.KEY) == [(1, 6, "")]

    def test_strips_markdown_fences(self):
        raw = '```json\n{"exchange_scores": [{"exchange": 1, "evasiveness_score": 4}]}\n```'
        assert parse_exchange_scores(raw, self.KEY) == [(1, 4, "")]

    def test_clamps_out_of_range_scores(self):
        raw = json.dumps({"exchange_scores": [
            {"exchange": 1, "evasiveness_score": 99},
            {"exchange": 2, "evasiveness_score": -4},
        ]})
        assert parse_exchange_scores(raw, self.KEY) == [(1, 10, ""), (2, 1, "")]

    def test_salvages_entries_from_a_truncated_response(self):
        """Responses run long exactly when there is more to say, so dropping a
        cut-off one biases the result (same reasoning as HIGH-4)."""
        raw = (
            '{"exchange_scores": [{"exchange": 1, "evasiveness_score": 8, "quote": "a"}, '
            '{"exchange": 2, "evasiveness_score": 3, "quote": "b"}, {"exchange": 3, "eva'
        )
        assert parse_exchange_scores(raw, self.KEY) == [(1, 8, "a"), (2, 3, "b")]

    def test_booleans_are_not_read_as_numbers(self):
        raw = json.dumps({"exchange_scores": [{"exchange": True, "evasiveness_score": True}]})
        assert parse_exchange_scores(raw, self.KEY) == []

    def test_unparseable_response_yields_nothing(self):
        assert parse_exchange_scores("the model apologises profusely", self.KEY) == []

    def test_ordered_by_exchange_number(self):
        raw = json.dumps({"exchange_scores": [
            {"exchange": 5, "evasiveness_score": 1},
            {"exchange": 2, "evasiveness_score": 9},
        ]})
        assert [e[0] for e in parse_exchange_scores(raw, self.KEY)] == [2, 5]


def _mock_response(content):
    choice = MagicMock()
    choice.message.content = content
    choice.finish_reason = "stop"
    response = MagicMock()
    response.choices = [choice]
    response.usage.prompt_tokens = 100
    response.usage.completion_tokens = 20
    response.usage.total_tokens = 120
    return response


def _reload_with_env():
    import importlib

    import config
    importlib.reload(config)
    import src.scoring._exchange_scorer as scorer
    importlib.reload(scorer)
    return scorer


class TestScoreExchangesLLM:
    ENV = {"LLM_API_KEY": "test-key", "LLM_API_BASE_URL": "https://test.api",
           "LLM_MODEL_NAME": "test-model"}

    @patch.dict("os.environ", ENV)
    @patch("openai.OpenAI", autospec=True)
    def test_returns_one_score_per_exchange(self, mock_openai):
        scorer = _reload_with_env()
        payload = json.dumps({"exchange_scores": [
            {"exchange": 1, "evasiveness_score": 2, "quote": "a"},
            {"exchange": 2, "evasiveness_score": 9, "quote": "b"},
        ]})
        client = MagicMock()
        client.chat.completions.create.return_value = _mock_response(payload)
        mock_openai.return_value = client

        result = scorer.score_exchanges_llm(
            [_exchange("Mgmt", 20), _exchange("Mgmt", 20)],
            dimension_name="evasiveness",
            system_prompt="sys",
            score_key="evasiveness_score",
        )
        assert [e["evasiveness_score"] for e in result["exchange_scores"]] == [2, 9]
        assert result["exchanges_total"] == 2
        assert result["usage"]["total_tokens"] == 120

    @patch.dict("os.environ", ENV)
    @patch("openai.OpenAI", autospec=True)
    def test_ignores_exchange_numbers_the_model_invented(self, mock_openai):
        scorer = _reload_with_env()
        payload = json.dumps({"exchange_scores": [
            {"exchange": 1, "evasiveness_score": 5},
            {"exchange": 42, "evasiveness_score": 10},
        ]})
        client = MagicMock()
        client.chat.completions.create.return_value = _mock_response(payload)
        mock_openai.return_value = client

        result = scorer.score_exchanges_llm(
            [_exchange("Mgmt", 20)],
            dimension_name="evasiveness",
            system_prompt="sys",
            score_key="evasiveness_score",
        )
        assert [e["exchange"] for e in result["exchange_scores"]] == [1]

    @patch.dict("os.environ", ENV)
    @patch("openai.OpenAI", autospec=True)
    def test_a_skipped_exchange_is_reported_not_hidden(self, mock_openai, caplog):
        scorer = _reload_with_env()
        payload = json.dumps({"exchange_scores": [{"exchange": 1, "evasiveness_score": 4}]})
        client = MagicMock()
        client.chat.completions.create.return_value = _mock_response(payload)
        mock_openai.return_value = client

        with caplog.at_level("WARNING", logger="earningslens"):
            result = scorer.score_exchanges_llm(
                [_exchange("Mgmt", 20), _exchange("Mgmt", 20)],
                dimension_name="evasiveness",
                system_prompt="sys",
                score_key="evasiveness_score",
            )
        assert len(result["exchange_scores"]) == 1
        assert result["exchanges_total"] == 2
        assert "no score for exchange(s) 2" in caplog.text

    @patch.dict("os.environ", ENV)
    @patch("openai.OpenAI", autospec=True)
    def test_nothing_parseable_is_an_error_not_a_score(self, mock_openai):
        scorer = _reload_with_env()
        client = MagicMock()
        client.chat.completions.create.return_value = _mock_response("sorry!")
        mock_openai.return_value = client

        result = scorer.score_exchanges_llm(
            [_exchange("Mgmt", 20)],
            dimension_name="evasiveness",
            system_prompt="sys",
            score_key="evasiveness_score",
        )
        assert result["exchange_scores"] == []
        assert "error" in result

    @patch.dict("os.environ", {"LLM_API_KEY": "", "LLM_API_BASE_URL": ""})
    def test_unconfigured_returns_an_error_without_calling_out(self):
        scorer = _reload_with_env()
        result = scorer.score_exchanges_llm(
            ["x"], dimension_name="evasiveness",
            system_prompt="sys", score_key="evasiveness_score",
        )
        assert result["error"] == "LLM not configured"


class TestVersionDispatch:
    """The prompt version chooses the scorer, not just the wording."""

    QA = ["Moderator:\nfirst question from the line of X.\n" + _exchange("Mgmt", 80)]

    @patch("src.scoring.evasiveness.score_evasiveness_per_exchange")
    def test_v3_routes_to_the_per_exchange_scorer(self, mock_per_exchange):
        mock_per_exchange.return_value = {"evasiveness_score": 7, "supporting_quotes": []}
        result = score_transcript_evasiveness(self.QA, prompt_version="evasiveness-v3")
        assert mock_per_exchange.called
        assert result["llm_result"]["evasiveness_score"] == 7

    @patch("src.scoring.evasiveness.score_evasiveness_llm")
    def test_v2_still_routes_to_the_batch_scorer(self, mock_batch):
        mock_batch.return_value = {"evasiveness_score": 5, "supporting_quotes": []}
        score_transcript_evasiveness(self.QA, prompt_version="evasiveness-v2")
        assert mock_batch.called

    @patch("src.scoring.evasiveness.score_evasiveness_llm")
    def test_default_still_routes_to_the_batch_scorer(self, mock_batch):
        mock_batch.return_value = {"evasiveness_score": 5, "supporting_quotes": []}
        score_transcript_evasiveness(self.QA)
        assert mock_batch.called


class TestPerExchangeResultShape:
    """Storage must not need a special case for v3."""

    @patch("src.scoring._exchange_scorer.score_exchanges_llm")
    def test_exposes_the_keys_the_storage_layer_reads(self, mock_scorer):
        from src.scoring.evasiveness import score_evasiveness_per_exchange

        mock_scorer.return_value = {
            "exchange_scores": [
                {"exchange": 1, "evasiveness_score": 2, "quote": "low"},
                {"exchange": 2, "evasiveness_score": 9, "quote": "high"},
                {"exchange": 3, "evasiveness_score": 8, "quote": "alsohigh"},
            ],
            "exchanges_total": 3,
            "raw_response": "{}",
            "usage": None,
        }
        result = score_evasiveness_per_exchange(_qa_text(3), prompt_version="evasiveness-v3")

        assert result["evasiveness_score"] == 6  # worst3 mean of 9, 8, 2
        assert result["supporting_quotes"] == ["high", "alsohigh", "low"]
        assert isinstance(result["raw_response"], str)

    @patch("src.scoring._exchange_scorer.score_exchanges_llm")
    def test_raw_response_keeps_every_exchange_score(self, mock_scorer):
        """A sweep costs days of quota, so the per-exchange scores have to
        survive in a form something can read back without regex."""
        from src.scoring.evasiveness import score_evasiveness_per_exchange

        entries = [{"exchange": i, "evasiveness_score": i, "quote": ""} for i in range(1, 6)]
        mock_scorer.return_value = {
            "exchange_scores": entries, "exchanges_total": 5,
            "raw_response": "{}", "usage": None,
        }
        result = score_evasiveness_per_exchange(_qa_text(5), prompt_version="evasiveness-v3")
        stored = json.loads(result["raw_response"])

        assert stored["aggregator"] == DEFAULT_AGGREGATOR
        assert stored["prompt_version"] == "evasiveness-v3"
        assert [e["evasiveness_score"] for e in stored["exchange_scores"]] == [1, 2, 3, 4, 5]
        assert stored["exchanges_scored"] == 5

    @patch("src.scoring._exchange_scorer.score_exchanges_llm")
    def test_aggregator_is_selectable_without_rescoring(self, mock_scorer):
        from src.scoring.evasiveness import score_evasiveness_per_exchange

        entries = [{"exchange": i, "evasiveness_score": s, "quote": ""}
                   for i, s in enumerate([1, 1, 1, 9, 9, 9], start=1)]
        mock_scorer.return_value = {
            "exchange_scores": entries, "exchanges_total": 6,
            "raw_response": "{}", "usage": None,
        }
        by_mean = score_evasiveness_per_exchange(
            _qa_text(6), prompt_version="evasiveness-v3", aggregator="mean")
        by_worst = score_evasiveness_per_exchange(
            _qa_text(6), prompt_version="evasiveness-v3", aggregator="worst3_mean")
        assert by_mean["evasiveness_score"] == 5
        assert by_worst["evasiveness_score"] == 9

    def test_unsplittable_qa_is_an_error_not_a_score(self):
        from src.scoring.evasiveness import score_evasiveness_per_exchange

        result = score_evasiveness_per_exchange([], prompt_version="evasiveness-v3")
        assert result["evasiveness_score"] is None
        assert "error" in result


class TestReAggregationFromStorage:
    """Per-exchange scores must survive a round trip through the database.

    That round trip is the whole reason they are stored: a sweep costs about a
    day of free-tier budget (BLOCKER-4), so every aggregation question has to
    be answerable offline afterwards.
    """

    def _db(self, tmp_path, payloads):
        from src.storage.db import init_db, store_score, store_transcript

        conn = init_db(str(tmp_path / "agg.db"))
        for i, (version, payload) in enumerate(payloads):
            quarter = f"Q{(i % 4) + 1}"
            store_transcript(conn, "TCS", quarter, 2024 + i // 4, ["chunk"], "TCS.pdf")
            tid = conn.execute(
                "SELECT id FROM transcripts WHERE quarter=? AND year=? AND chunk_index=0",
                (quarter, 2024 + i // 4),
            ).fetchone()[0]
            store_score(conn, tid, "evasiveness", 5, [], "m", version, payload)
        return conn

    def _payload(self, scores):
        return json.dumps({
            "prompt_version": "evasiveness-v3",
            "aggregator": DEFAULT_AGGREGATOR,
            "exchanges_total": len(scores),
            "exchanges_scored": len(scores),
            "exchange_scores": [
                {"exchange": i, "evasiveness_score": s, "quote": ""}
                for i, s in enumerate(scores, start=1)
            ],
        })

    def test_reads_back_every_exchange_score(self, tmp_path):
        from scripts.compare_aggregators import load_exchange_scores

        conn = self._db(tmp_path, [("evasiveness-v3", self._payload([1, 5, 9]))])
        rows, skipped = load_exchange_scores(conn, "evasiveness", "evasiveness-v3", None)
        conn.close()
        assert skipped == 0
        assert rows[0][3] == [1, 5, 9]

    def test_skips_v2_rows_that_hold_no_exchange_scores(self, tmp_path):
        """A v1/v2 row holds one blended score and cannot be re-aggregated."""
        from scripts.compare_aggregators import load_exchange_scores

        conn = self._db(tmp_path, [
            ("evasiveness-v2", "raw model text, not json"),
            ("evasiveness-v2", json.dumps({"evasiveness_score": 6})),
        ])
        rows, skipped = load_exchange_scores(conn, "evasiveness", "evasiveness-v2", None)
        conn.close()
        assert rows == []
        assert skipped == 2

    def test_a_stored_sweep_can_be_re_aggregated_without_rescoring(self, tmp_path):
        """The end-to-end promise: same stored data, different transcript scores."""
        from scripts.compare_aggregators import load_exchange_scores

        conn = self._db(tmp_path, [
            ("evasiveness-v3", self._payload([1, 1, 1, 1, 9, 9, 9])),
            ("evasiveness-v3", self._payload([4, 4, 4, 4, 4, 4, 4])),
        ])
        rows, _ = load_exchange_scores(conn, "evasiveness", "evasiveness-v3", None)
        conn.close()

        by_mean = [aggregate_exchange_scores(s, "mean") for *_, s in rows]
        by_worst = [aggregate_exchange_scores(s, "worst3_mean") for *_, s in rows]
        # Averaging calls a call with three flat refusals the same as a uniformly
        # mediocre one. The default aggregator does not.
        assert by_mean[0] == by_mean[1]
        assert by_worst[0] > by_worst[1]
