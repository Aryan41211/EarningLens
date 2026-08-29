"""Smoke and regression tests for the Phase 4 Streamlit dashboard.

The dashboard had no test coverage at all, which is how its Raw Data tab came
to ignore the variant selector that the rest of the page respects -- showing a
reader the quotes one model gave for a score a different model produced. That
is the BLOCKER-2 failure mode surviving inside the fix for BLOCKER-2.

Streamlit is an optional dependency (the `[dashboard]` extra), so these
skip cleanly when it is absent.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

pytest.importorskip("streamlit", reason="dashboard extras not installed")
pytest.importorskip("plotly", reason="dashboard extras not installed")

from streamlit.testing.v1 import AppTest  # noqa: E402

import config  # noqa: E402
from src.storage.db import init_db, store_score, store_transcript  # noqa: E402

APP = os.path.join(os.path.dirname(__file__), "..", "src", "dashboard", "app.py")


def _chunk0_id(conn, quarter, year):
    return conn.execute(
        "SELECT id FROM transcripts WHERE quarter=? AND year=? AND chunk_index=0",
        (quarter, year),
    ).fetchone()[0]


@pytest.fixture
def two_variant_db(tmp_path, monkeypatch):
    """One TCS series scored by two models, with per-variant quotes.

    The quotes are deliberately distinguishable: whichever variant the sidebar
    selects, only that variant's quotes may appear.
    """
    db = tmp_path / "dash.db"
    conn = init_db(str(db))
    for i, (q, y) in enumerate([("Q1", 2024), ("Q2", 2024), ("Q3", 2024)]):
        store_transcript(conn, "TCS", q, y, [f"chunk text {i}"], "TCS.pdf")
        tid = _chunk0_id(conn, q, y)
        store_score(conn, tid, "evasiveness", 5, ["OLD MODEL QUOTE"],
                    "old-model", "evasiveness-v1", "{}")
        store_score(conn, tid, "evasiveness", 3 + i, ["PINNED MODEL QUOTE"],
                    "pinned-model", "evasiveness-v2", "{}")
    conn.close()
    monkeypatch.setattr(config, "DB_PATH", db)
    return db


@pytest.fixture
def empty_db(tmp_path, monkeypatch):
    db = tmp_path / "empty.db"
    init_db(str(db)).close()
    monkeypatch.setattr(config, "DB_PATH", db)
    return db


def _run(**kwargs):
    return AppTest.from_file(APP, default_timeout=120, **kwargs).run()


class TestDashboardRuns:
    def test_renders_with_scores(self, two_variant_db):
        at = _run()
        assert not at.exception
        assert len(at.tabs) == 4

    def test_empty_database_is_an_honest_empty_state(self, empty_db):
        """A fresh deploy has no database; it must say so, not traceback."""
        at = _run()
        assert not at.exception
        assert any("No scores" in w.value for w in at.warning)


class TestVariantSelection:
    """Selecting a variant must filter every panel, quotes included."""

    def _select_variant(self, at, needle):
        selector = at.sidebar.selectbox[0]
        match = [o for o in selector.options if needle in o]
        assert match, f"no variant option containing {needle!r} in {selector.options}"
        return selector.select(match[0]).run()

    def test_selector_lists_every_variant(self, two_variant_db):
        options = _run().sidebar.selectbox[0].options
        assert any("old-model" in o for o in options)
        assert any("pinned-model" in o for o in options)

    def test_quotes_follow_the_selected_variant(self, two_variant_db):
        at = self._select_variant(_run(), "pinned-model")
        assert not at.exception
        rendered = " ".join(m.value for m in at.markdown)
        assert "PINNED MODEL QUOTE" in rendered
        assert "OLD MODEL QUOTE" not in rendered

    def test_quotes_follow_the_other_variant_too(self, two_variant_db):
        at = self._select_variant(_run(), "old-model")
        assert not at.exception
        rendered = " ".join(m.value for m in at.markdown)
        assert "OLD MODEL QUOTE" in rendered
        assert "PINNED MODEL QUOTE" not in rendered

    def test_a_single_variant_reports_no_contamination(self, two_variant_db):
        at = self._select_variant(_run(), "pinned-model")
        assert not any("not comparable" in e.value for e in at.error)

    def test_all_variants_reports_contamination(self, two_variant_db):
        at = _run()
        assert any("not comparable" in e.value for e in at.error)
