"""Tests for the Diamond pattern and Venom model."""

from datetime import datetime, timedelta, timezone

from ictlib.models import Candle
from ictlib.setups import find_diamonds, classify_models
from ictlib.concepts.sessions import pre_open_range


def test_classify_models_venom():
    m = classify_models(killzone="NY AM", sb_window=False,
                        sweep_killzone="NY AM", bias_aligned=True,
                        has_fvg=True, venom=True)
    assert "Venom" in m


def test_pre_open_range():
    # 08:00-09:30 NY (EDT) = 12:00-13:30 UTC
    base = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)
    cs = [
        Candle(base, 1.0800, 1.0830, 1.0795, 1.0820),                    # high 1.0830
        Candle(base + timedelta(minutes=30), 1.0820, 1.0825, 1.0780, 1.0800),  # low 1.0780
        Candle(base + timedelta(minutes=60), 1.0800, 1.0810, 1.0795, 1.0805),
        Candle(base + timedelta(minutes=120), 1.0805, 1.0815, 1.0800, 1.0810),  # 10:00 NY, outside
    ]
    por = pre_open_range(cs)
    assert por is not None
    assert por.high == 1.0830 and por.low == 1.0780


def test_find_diamonds():
    # a fake analysis with a BSL and SSL sweep close together, then an MSS break
    from ictlib.models import Sweep, StructureEvent
    TS = datetime(2026, 1, 1, tzinfo=timezone.utc)

    class A:
        sweeps = [
            Sweep(5, TS, "BSL", 1.09, 1.091, 1.089, 0.7, 2),
            Sweep(8, TS, "SSL", 1.08, 1.079, 1.081, 0.7, 3),
        ]
        events = [StructureEvent(12, TS, "MSS", "bull", 1.088, 6, True, True)]

    diamonds = find_diamonds(A(), window=20)
    assert len(diamonds) == 1
    assert diamonds[0]["break_index"] == 12 and diamonds[0]["direction"] == "bull"


def test_no_diamond_without_both_sides():
    from ictlib.models import Sweep, StructureEvent
    TS = datetime(2026, 1, 1, tzinfo=timezone.utc)

    class A:
        sweeps = [Sweep(5, TS, "BSL", 1.09, 1.091, 1.089, 0.7, 2)]  # only BSL
        events = [StructureEvent(12, TS, "MSS", "bull", 1.088, 6, True, True)]

    assert find_diamonds(A()) == []
