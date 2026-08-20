"""End-to-end scanner tests on the canonical setups."""

from ictlib.analysis import analyze
from ictlib.scanner import scan, scan_candles
from ictlib.sample_setups import LONG_SETUP

from _helpers import candles


def test_long_setup_produces_signal():
    a = analyze(candles(LONG_SETUP))
    sigs = scan(a, min_score=2)
    assert sigs, "expected at least one signal on the long setup"
    s = sigs[0]
    assert s.direction == "long"
    # entry sits inside its own zone; stop is below entry for a long
    lo, hi = s.entry_zone
    assert lo <= s.entry <= hi
    assert s.stop < s.entry
    # sweep + MSS are always present; confluence pushes score up
    assert s.score >= 3
    assert any("sweep" in r for r in s.reasons)
    assert any("MSS" in r for r in s.reasons)


def test_scan_candles_convenience():
    sigs = scan_candles(candles(LONG_SETUP), min_score=2)
    assert sigs and sigs[0].direction == "long"


def test_min_score_filters():
    a = analyze(candles(LONG_SETUP))
    assert scan(a, min_score=99) == []


def test_signal_is_jsonable():
    from ictlib.models import to_jsonable
    import json
    a = analyze(candles(LONG_SETUP))
    s = scan(a)[0]
    json.dumps(to_jsonable(s))  # must not raise
