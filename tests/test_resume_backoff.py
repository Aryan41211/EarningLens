"""Tests for the transient-failure backoff in resume_sweep.

A sweep spans days of rolling quota, so it has to outlive a provider outage.
The first version retried on a fixed 60s and gave up after 4 stalls, tolerating
four minutes of downtime; a real Groq outage outlasted that and ended a plan at
7 of 11 with 23 hours of budget unspent.
"""

import importlib.util
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_RUNNER = os.path.join(os.path.dirname(__file__), "..", "scripts", "resume_sweep.py")


def _load():
    spec = importlib.util.spec_from_file_location("resume_sweep", os.path.abspath(_RUNNER))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_backoff_doubles():
    backoff = _load().transient_backoff
    assert backoff(1, 60, 600) == 60
    assert backoff(2, 60, 600) == 120
    assert backoff(3, 60, 600) == 240
    assert backoff(4, 60, 600) == 480


def test_backoff_flattens_at_cap():
    backoff = _load().transient_backoff
    assert backoff(5, 60, 600) == 600
    assert backoff(20, 60, 600) == 600


def test_backoff_never_exceeds_cap():
    backoff = _load().transient_backoff
    assert all(backoff(n, 60, 600) <= 600 for n in range(1, 40))


def test_backoff_handles_a_zero_or_negative_stall_count():
    backoff = _load().transient_backoff
    assert backoff(0, 60, 600) == 60
    assert backoff(-1, 60, 600) == 60


def test_default_settings_outlast_a_realistic_outage():
    """8 stalls of capped exponential backoff must cover a long outage.

    The regression this guards: at the old fixed 60s x 4 the window was four
    minutes, and a genuine outage walked straight through it.
    """
    backoff = _load().transient_backoff
    total = sum(backoff(n, 60, 600) for n in range(1, 9))
    assert total >= 45 * 60, f"only tolerates {total / 60:.0f} min of downtime"
