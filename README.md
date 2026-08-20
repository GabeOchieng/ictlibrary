# ictlib — an ICT concept-detection library

A clean, tested, dependency-light Python library that detects the core
**Inner Circle Trader (ICT)** price-action concepts from OHLCV candles, and
renders them on an annotated chart. It is the foundation the higher-level tools
— a signal **scanner** (included), a backtester, or a live bot — all build on.

Every detector is grounded in the concept definitions from the
[ict-knowledge-library](https://github.com/SrsBlack/ict-knowledge-library):
the formulas in that wiki are reproduced verbatim in each module's docstring.

> ⚠️ Educational tool. Nothing here is financial advice. ICT concepts are
> discretionary ideas; detection thresholds are quantified approximations.

---

## What it detects

| Concept | Module | Rule (from the knowledge library) |
|---|---|---|
| **Swing highs/lows** | `concepts/structure.py` | n-bar fractal: `H_n > H_{n±1..w}`; STH/ITH/LTH hierarchy |
| **BOS / CHoCH** | `concepts/structure.py` | close beyond last opposite swing; continuation vs first reversal |
| **MSS** | `concepts/structure.py` | a CHoCH **with displacement + FVG in the break** |
| **Dealing range + equilibrium** | `concepts/pd_arrays.py` | bounds = recent LTH/LTL; `EQ = (LTH+LTL)/2` |
| **Premium / discount** | `concepts/pd_arrays.py` | above EQ = premium (sell-side), below = discount (buy-side); signed depth where `0.79` = OTE |
| **Displacement** | `concepts/displacement.py` | `body ≥ 1.5×avg`, `body/range ≥ 0.70`, `opp_wick/range ≤ 0.20` |
| **Fair Value Gap** | `concepts/fvg.py` | bull `L_{n+1} > H_{n-1}`, bear `H_{n+1} < L_{n-1}`; CE = midpoint |
| **Order Block** | `concepts/order_blocks.py` | last opposite candle before a structure-breaking displacement; body = MT zone |
| **Breaker Block** | `concepts/breaker_blocks.py` | a failed OB that flips polarity (close through body + displacement) |
| **Rejection Block** | `concepts/rejection_blocks.py` | long wick (≥60%) rejecting a key level; the wick is the zone |
| **Volume Imbalance** | `concepts/imbalance.py` | body-vs-body gap `O_n ≠ C_{n-1}` (wicks may overlap) |
| **Liquidity pools** | `concepts/liquidity.py` | BSL/SSL at swings; EQH/EQL clusters within a pip tolerance |
| **Liquidity sweep** | `concepts/liquidity.py` | wick beyond pool + close back inside + ≥60% wick |
| **Killzones** | `concepts/killzones.py` | NY-time windows (Asia, London, NY AM/PM) + silver bullet, DST-aware |
| **Session ranges** | `concepts/sessions.py` | NY-time session map; most-recent session high/low |
| **Asian range** | `concepts/asian_range.py` | Asia-session high/low, Judas-sweep side, 0.5–2× projections |
| **IPDA lookback** | `concepts/ipda.py` | 20/40/60 trading-day reference highs/lows |
| **Turtle Soup** | `concepts/turtle_soup.py` | failed breakout = sweep + confirming reversal displacement |
| **Quarterly Theory / PO3** | `concepts/quarterly.py` | True Day Open, daily quarters → AMD phases |
| **CRT** *(community)* | `concepts/crt.py` | HTF candle-range sweep → opposite bound (non-ICT-original) |
| **HTF bias (multi-TF)** | `mtf.py` | top-down bias across resampled H1/H4/D; drives setup side |
| **Named models** | `setups.py` | 2022 Model, Silver Bullet, Judas Swing, Unicorn (composed) |
| **OTE** | `concepts/ote.py` | 0.62–0.79 retracement band of a measured leg |

Each detector marks **state** where the concept has it: FVGs and order blocks
track whether they are still *unmitigated*; pools track whether they've been *swept*.

---

## Install & run

```bash
pip install -r requirements.txt        # only 'requests' (OANDA) + pytest are needed
python -m pytest                        # 22 tests, all green

# generate the offline sample and scan it (no API key required)
python examples/generate_sample.py
python -m ictlib.cli --csv sample_data/EUR_USD_M15.csv

# render the annotated chart (self-contained HTML, opens in any browser)
python -m ictlib.cli --csv sample_data/EUR_USD_M15.csv --html chart.html

# emit JSON for downstream tooling
python -m ictlib.cli --csv sample_data/EUR_USD_M15.csv --json
```

### Live data

**OANDA** (forex):
```bash
export OANDA_API_KEY="your-token"
export OANDA_ENV="practice"      # or "live"
python -m ictlib.cli --oanda --instrument EUR_USD --granularity M15 --count 300 --html eurusd.html
```

**Alpaca** (US stocks + crypto):
```bash
export APCA_API_KEY_ID="your-key"
export APCA_API_SECRET_KEY="your-secret"
python -m ictlib.cli --alpaca --instrument AAPL --granularity M15            # stocks
python -m ictlib.cli --alpaca --asset crypto --instrument BTC/USD --granularity H1
```

### Multi-timeframe HTF bias

```bash
# read a top-down H1+H4 bias and only keep signals aligned with it
python -m ictlib.cli --csv data.csv --htf H1,H4 --require-htf
```
```python
a = analyze(candles, htf_timeframes=[60, 240])   # minutes
a.mtf.bias          # aggregate bullish / bearish / neutral
a.mtf.reads         # per-timeframe [TFRead(H4, ...), TFRead(H1, ...)]
scan(a, require_htf_alignment=True)               # drop counter-bias signals
```

---

## Library API

```python
from ictlib import analyze, scan
from ictlib.data import load_csv          # or: from ictlib.data import OandaClient

candles = load_csv("sample_data/EUR_USD_M15.csv")

a = analyze(candles)                       # one snapshot with every primitive
print(a.summary())                         # bias, killzone, counts
a.swings, a.events, a.fvgs, a.order_blocks, a.pools, a.sweeps
a.unmitigated_fvgs, a.unmitigated_obs, a.open_pools

for sig in scan(a):                        # signals built on the primitives
    print(sig.direction, sig.entry, sig.stop, sig.targets, sig.score)
    print(sig.reasons)                     # the confluence that fired

from ictlib.viz import render_html
render_html(a, "chart.html", instrument="EUR_USD", signals=scan(a))
```

Everything is a plain dataclass and JSON-serialisable via `ictlib.to_jsonable`.

---

## The scanner setup (v1)

The included scanner encodes the classic ICT reversal:

1. A **liquidity sweep** runs a pool of stops beyond a high/low.
2. An **MSS** (displaced CHoCH leaving an FVG) fires the *other* way — the
   algorithm's signature to reverse.
3. **Entry** = the FVG left by that MSS (consequent encroachment) or the order
   block behind it (mean threshold).
4. **Stop** beyond the sweep extreme; **targets** = the draw-on-liquidity set
   (the IPDA reference set: liquidity pools + session/Asian-range extremes +
   IPDA 20/40/60-day levels), nearest first.

Confluences add to a score: active killzone, HTF bias aligned, entry inside the
OTE band, whether a dense EQH/EQL pool was the one swept, and — per ICT's
premium/discount discipline — whether the entry sits on the correct side of the
dealing-range equilibrium (longs at a discount, shorts at a premium). Entries on
the wrong side of EQ are flagged rather than silently scored.

Each signal is also **classified into named ICT models** (`setups.py`) it
satisfies — *ICT 2022 Model*, *Silver Bullet*, *Judas Swing* — and a *Unicorn*
zone (breaker + nested FVG + HTF bias + prior sweep) overlapping the entry adds
conviction. `signal.models` carries the matched names.

---

## Backtesting & risk

```python
from ictlib import backtest, RiskParams
from ictlib.data import load_csv

candles = load_csv("sample_data/EUR_USD_M15_backtest.csv")
res = backtest(candles, instrument="EUR_USD",
               risk=RiskParams(equity=10_000, risk_pct=0.01),
               min_score=2, entry_mode="limit")
print(res.stats())        # trades, win_rate, total_r, expectancy_r, profit_factor, max_drawdown_r
print(res.equity_curve)   # cumulative R per closed trade
```

The backtester is **walk-forward**: at each bar it re-analyses only the candles
seen so far (no lookahead), registers newly-confirmed signals, and simulates
fills/stops/targets bar-by-bar — stop checked before target (worst case),
pending limit entries expire, results reported in R multiples.

```bash
# from the CLI, with an equity-curve chart
python -m ictlib.cli --csv sample_data/EUR_USD_M15_backtest.csv --backtest \
    --instrument EUR_USD --min-score 2 --equity-html equity.html
```

Position sizing follows `risk_$ / sl_distance` with per-instrument pip values
(`ictlib.risk`). `size_signal(signal, pip)` attaches lots + per-target R to any
signal.

> Backtests run on the bundled data are **synthetic and illustrative** — a
> demonstration of the machinery, not a strategy result. Point it at real OANDA
> history to evaluate the setup.

## Architecture

```
                 data (OANDA / CSV)  ->  List[Candle]
                                             |
             ┌───────────────────────────────┴───────────────────────────────┐
             |                     concepts/  (pure primitives)               |
             |  structure · displacement · fvg · order_blocks · liquidity     |
             |  killzones · ote                                               |
             └───────────────────────────────┬───────────────────────────────┘
                                              |
                        analyze()  ->  Analysis  (one snapshot of all primitives)
                                              |
                     ┌────────────────────────┼────────────────────────┐
                     |                         |                        |
                 scan() -> Signal        viz.render_html()        (backtester /
              (confluence scoring)     annotated HTML chart        live bot — next)
```

The primitive layer never imports the scanner or the visualiser, so a
backtester or a live bot can sit beside the scanner on the same `Analysis`
object without duplicating any detection logic.

---

## Layout

```
ictlib/
  models.py            Candle + every primitive as a typed dataclass
  analysis.py          analyze() -> Analysis snapshot
  scanner.py           scan() -> signals (sweep -> MSS -> FVG/OB)
  risk.py              position sizing, R-multiples, partial schedules
  backtest.py          walk-forward backtester -> stats + equity curve
  viz.py               render_html() chart + render_equity_html() equity curve
  cli.py               python -m ictlib.cli
  sample_setups.py     canonical hand-authored setups (shared by demo + tests)
  concepts/            structure, displacement, fvg, order_blocks,
                       breaker_blocks, rejection_blocks, imbalance,
                       liquidity, pd_arrays, sessions, asian_range, ipda,
                       turtle_soup, quarterly, crt, killzones, ote
  mtf.py               multi-timeframe HTF bias (resample + top-down read)
  data/                oanda.py (forex), alpaca.py (stocks/crypto), csv_loader.py
examples/              generate_sample.py, rendered chart
sample_data/           EUR_USD_M15.csv
tests/                 22 deterministic tests
```

## Roadmap

- [x] **PD arrays** — dealing range, equilibrium, premium/discount classification.
- [x] **Breaker & rejection blocks, volume imbalance** — the rest of the PD-array family.
- [x] **Sessions, Asian range, IPDA lookback** — time-based draw-on-liquidity levels.
- [x] **Risk management + walk-forward backtester** — position sizing, R-multiples, equity curve.
- [x] **Turtle Soup, Quarterly Theory / PO3, CRT** — named patterns + time-fractal phases.
- [x] **Multi-timeframe HTF bias** — top-down bias across resampled timeframes.
- [x] **Alpaca data source** + **HistData loader** — stocks/crypto and real historical files.
- [x] **Named models** — ICT 2022 Model, Silver Bullet, Judas Swing, Unicorn, NDOG/NWOG.
- [x] **PD-array variants** — inversion FVG, BPR, nested FVG, propulsion block, liquidity void.
- [x] **SMT divergence + intermarket (DXY) + news blackout** — the data-dependent trio.
- [x] **Reward:risk** — SD-projection targets + structural-stop mode (configurable).
- [x] **Refinements** — fib body-anchoring, mitigation lifecycle, stop-run variants,
      90-min cycle, reclaimed OBs, Diamond + Venom models.
- [ ] Live/paper execution adapter. (Zircon model omitted — demo-stage, unconfirmed.)
