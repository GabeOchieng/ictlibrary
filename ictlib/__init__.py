"""ictlib — a clean, tested library of ICT (Inner Circle Trader) primitives.

Grounded in the ict-knowledge-library concept definitions, ictlib detects the
building blocks of ICT price analysis — swings, market-structure breaks
(BOS/CHoCH/MSS), displacement, fair value gaps, order blocks, liquidity pools
and sweeps, killzones and OTE — from OHLCV candles.

Higher-level tools (signal scanner, backtester, live bot) build on top of the
:func:`analyze` snapshot rather than re-implementing the primitives.

Quick start
-----------
    from ictlib import analyze, scan
    from ictlib.data import load_csv

    candles = load_csv("sample_data/EUR_USD_M15.csv")
    a = analyze(candles)
    print(a.summary())
    for sig in scan(a):
        print(sig.direction, sig.entry, sig.stop, sig.score, sig.reasons)
"""

from .models import (
    Candle, Swing, StructureEvent, FVG, OrderBlock, LiquidityPool, Sweep,
    DealingRange, Breaker, RejectionBlock, VolumeImbalance,
    SessionRange, AsianRange, IPDALevels,
    TurtleSoup, CRTSetup, QuarterlyContext, TFRead, MTFContext, Unicorn,
    Signal, to_jsonable,
)
from .analysis import Analysis, analyze
from .scanner import scan, scan_candles
from .risk import RiskParams, position_size, r_multiple, size_signal
from .backtest import backtest, BacktestResult, Trade
from .mtf import multi_timeframe_bias, resample_tf
from .setups import classify_models, find_unicorns
from . import concepts

__version__ = "0.8.0"

__all__ = [
    "Candle", "Swing", "StructureEvent", "FVG", "OrderBlock",
    "LiquidityPool", "Sweep", "DealingRange", "Breaker", "RejectionBlock",
    "VolumeImbalance", "SessionRange", "AsianRange", "IPDALevels",
    "TurtleSoup", "CRTSetup", "QuarterlyContext", "TFRead", "MTFContext",
    "Unicorn", "Signal", "to_jsonable",
    "Analysis", "analyze", "scan", "scan_candles", "concepts",
    "RiskParams", "position_size", "r_multiple", "size_signal",
    "backtest", "BacktestResult", "Trade",
    "multi_timeframe_bias", "resample_tf",
    "classify_models", "find_unicorns",
    "__version__",
]
