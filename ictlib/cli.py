"""Command-line entry point for the ICT scanner / visualiser.

Examples
--------
    # scan a CSV and print signals
    python -m ictlib.cli --csv sample_data/EUR_USD_M15.csv

    # pull live forex from OANDA (needs OANDA_API_KEY)
    python -m ictlib.cli --oanda --instrument EUR_USD --granularity M15 --count 300

    # render the annotated chart to HTML
    python -m ictlib.cli --csv sample_data/EUR_USD_M15.csv --html chart.html

    # emit JSON for downstream tooling
    python -m ictlib.cli --csv sample_data/EUR_USD_M15.csv --json
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import List

from .models import Candle, to_jsonable
from .analysis import analyze
from .scanner import scan


def _load(args) -> List[Candle]:
    if args.oanda:
        from .data import OandaClient
        client = OandaClient(api_key=args.api_key, env=args.env)
        return client.get_candles(args.instrument, args.granularity, args.count)
    if args.csv:
        from .data import load_csv
        return load_csv(args.csv)
    raise SystemExit("Provide --csv PATH or --oanda")


def _print_report(analysis, signals, instrument, granularity) -> None:
    su = analysis.summary()
    print(f"\n=== ICT scan: {instrument or 'series'} {granularity} ===")
    print(f"bias={su['bias']}  killzone={su['killzone'] or '-'}  bars={su['candles']}")
    print(f"structure={su['structure_events']}  "
          f"FVG={su['unmitigated_fvgs']}/{su['fvgs']} open  "
          f"OB={su['unmitigated_obs']}/{su['order_blocks']} open  "
          f"sweeps={su['sweeps']}")

    if not signals:
        print("\nno signals at min score")
        return
    print(f"\n{len(signals)} signal(s):")
    for s in signals:
        rr = f"{s.rr:.2f}" if s.rr else "—"
        tgt = ", ".join(f"{t:.5f}" for t in s.targets) or "—"
        print(f"\n  [{s.direction.upper()}] score {s.score}  "
              f"{s.ts.strftime('%Y-%m-%d %H:%M')}  ({s.killzone or 'no KZ'})")
        print(f"    entry {s.entry:.5f}  zone {s.entry_zone[0]:.5f}-{s.entry_zone[1]:.5f}")
        print(f"    stop  {s.stop:.5f}  target {tgt}  RR {rr}")
        for r in s.reasons:
            print(f"      · {r}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ictlib", description="ICT signal scanner")
    src = p.add_argument_group("data source")
    src.add_argument("--csv", help="path to an OHLCV CSV file")
    src.add_argument("--oanda", action="store_true", help="pull from OANDA v20")
    src.add_argument("--instrument", default="EUR_USD")
    src.add_argument("--granularity", default="M15")
    src.add_argument("--count", type=int, default=300)
    src.add_argument("--api-key", default=None, help="OANDA token (or OANDA_API_KEY)")
    src.add_argument("--env", default=None, help="practice|live (or OANDA_ENV)")

    cfg = p.add_argument_group("detection")
    cfg.add_argument("--swing-width", type=int, default=2)
    cfg.add_argument("--min-score", type=int, default=2)

    out = p.add_argument_group("output")
    out.add_argument("--html", help="write annotated chart to this HTML path")
    out.add_argument("--json", action="store_true", help="emit JSON to stdout")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    candles = _load(args)
    if not candles:
        print("no candles loaded", file=sys.stderr)
        return 1

    analysis = analyze(candles, swing_width=args.swing_width)
    signals = scan(analysis, min_score=args.min_score)

    if args.json:
        print(json.dumps({
            "summary": analysis.summary(),
            "signals": [to_jsonable(s) for s in signals],
        }, indent=2))
    else:
        _print_report(analysis, signals, args.instrument, args.granularity)

    if args.html:
        from .viz import render_html
        render_html(analysis, args.html, title=f"ICT Concept Map — {args.instrument}",
                    instrument=args.instrument, granularity=args.granularity,
                    signals=signals)
        print(f"\nchart written to {args.html}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
