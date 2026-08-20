"""Generate a deterministic EUR/USD M15 sample that contains a textbook ICT
long setup: a sell-side liquidity sweep, a bullish MSS (displaced CHoCH that
leaves an FVG), a retrace into the FVG, then expansion toward buy-side liquidity.

Run:  python examples/generate_sample.py
Writes sample_data/EUR_USD_M15.csv and prints the detected analysis + signals.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from ictlib.models import Candle
from ictlib.data import save_csv
from ictlib.analysis import analyze
from ictlib.scanner import scan
from ictlib.sample_setups import LONG_SETUP

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _c(rows):
    """rows: list of (open, high, low, close). Times step 15m from a base that
    lands the setup inside the NY AM killzone (10:00 NY = 14:00 UTC in EDT)."""
    base = datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc)  # 06:00 NY
    out = []
    for i, (o, h, l, c) in enumerate(rows):
        out.append(Candle(base + timedelta(minutes=15 * i), o, h, l, c, 1000))
    return out


def main():
    candles = _c(LONG_SETUP)
    out = os.path.join(HERE, "sample_data", "EUR_USD_M15.csv")
    save_csv(out, candles)
    print(f"wrote {len(candles)} candles -> {out}")

    a = analyze(candles)
    print("\nsummary:", a.summary())
    print("\nstructure events:")
    for e in a.events:
        print(f"  idx{e.index} {e.kind} {e.direction} @ {e.level:.5f} "
              f"disp={e.has_displacement} fvg={e.has_fvg}")
    print("\nsweeps:")
    for s in a.sweeps:
        print(f"  idx{s.index} {s.kind} level {s.level:.5f} wick {s.wick_pct*100:.0f}%")
    print("\nFVGs:")
    for f in a.fvgs:
        print(f"  idx{f.index} {f.direction} {f.low:.5f}-{f.high:.5f} "
              f"mit={f.mitigated}")

    sigs = scan(a, min_score=2)
    print(f"\n{len(sigs)} signal(s):")
    for s in sigs:
        print(f"  {s.direction} score={s.score} entry={s.entry:.5f} "
              f"stop={s.stop:.5f} targets={[round(t,5) for t in s.targets]}")
        for r in s.reasons:
            print(f"    - {r}")


if __name__ == "__main__":
    main()
