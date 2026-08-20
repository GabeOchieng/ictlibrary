"""Typed data model for the ICT concept-detection library.

Everything downstream — the concept detectors, the scanner, the visualiser —
speaks in these dataclasses. The core engine deliberately depends on nothing
outside the standard library so it is portable and trivially testable.

Every price-level field carries the exact ICT definition it comes from in its
docstring / comment, cross-referenced to the ict-knowledge-library concept file.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


# --------------------------------------------------------------------------- #
# Candle
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Candle:
    """A single OHLCV bar. ``ts`` is always timezone-aware UTC."""

    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    complete: bool = True

    def __post_init__(self) -> None:
        if self.ts.tzinfo is None:
            raise ValueError("Candle.ts must be timezone-aware (UTC)")

    # -- geometry helpers used throughout the detectors -------------------- #
    @property
    def range(self) -> float:
        return self.high - self.low

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def body_high(self) -> float:
        return max(self.open, self.close)

    @property
    def body_low(self) -> float:
        return min(self.open, self.close)

    @property
    def upper_wick(self) -> float:
        return self.high - self.body_high

    @property
    def lower_wick(self) -> float:
        return self.body_low - self.low

    @property
    def midpoint(self) -> float:
        return (self.high + self.low) / 2.0

    @property
    def is_bull(self) -> bool:
        return self.close > self.open

    @property
    def is_bear(self) -> bool:
        return self.close < self.open


# --------------------------------------------------------------------------- #
# Market-structure primitives
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Swing:
    """A confirmed fractal pivot (concepts/01-market-structure/swing-high|low)."""

    index: int
    ts: datetime
    price: float
    kind: str  # "high" | "low"
    width: int = 2


@dataclass(frozen=True)
class StructureEvent:
    """A break of market structure.

    kind  : "BOS"  continuation break (concepts/01-market-structure/bos-*)
            "CHoCH" first counter-trend break (concepts/01-market-structure/choch-*)
            "MSS"  a CHoCH *with displacement + FVG* (concepts/01-market-structure/mss)
    """

    index: int          # candle whose close broke the level
    ts: datetime
    kind: str           # "BOS" | "CHoCH" | "MSS"
    direction: str      # "bull" | "bear"
    level: float        # the swing price that was broken
    swing_index: int    # index of the swing pivot that was broken
    has_fvg: bool = False
    has_displacement: bool = False


# --------------------------------------------------------------------------- #
# PD arrays
# --------------------------------------------------------------------------- #
@dataclass
class FVG:
    """Fair Value Gap — a 3-candle imbalance (concepts/06-fair-value-gaps).

    bullish (BISI): L[n+1] > H[n-1]   region = [H[n-1], L[n+1]]
    bearish (SIBI): H[n+1] < L[n-1]   region = [H[n+1], L[n-1]]
    """

    index: int          # middle candle n
    ts: datetime
    direction: str      # "bull" | "bear"
    low: float
    high: float
    has_displacement: bool = False
    mitigated: bool = False
    mitigated_index: Optional[int] = None
    pd_side: Optional[str] = None   # "premium" | "discount" | "equilibrium"

    @property
    def ce(self) -> float:
        """Consequent encroachment — the 50% of the gap; ICT's primary entry."""
        return (self.low + self.high) / 2.0

    @property
    def size(self) -> float:
        return self.high - self.low


@dataclass
class OrderBlock:
    """Order Block — last opposite candle before a structure-breaking
    displacement (concepts/07-order-blocks/order-block-criteria).

    Body is used (open/close), not the full range. ``mt`` is the mean threshold.
    """

    index: int
    ts: datetime
    direction: str      # "bull" | "bear"
    low: float          # body low
    high: float         # body high
    event_index: int    # the structure break this OB gave rise to
    mitigated: bool = False
    mitigated_index: Optional[int] = None
    pd_side: Optional[str] = None   # "premium" | "discount" | "equilibrium"

    @property
    def mt(self) -> float:
        return (self.low + self.high) / 2.0


# --------------------------------------------------------------------------- #
# PD arrays — dealing range, premium / discount, equilibrium
# --------------------------------------------------------------------------- #
@dataclass
class DealingRange:
    """The reference frame for premium/discount (concepts/05-pd-arrays/dealing-range).

    Bounded by the most recent unbroken long-term high/low on the timeframe.
    EQ (equilibrium) is the 50% midpoint — THE reference for classifying every
    PD array (concepts/27-equilibrium/dealing-range-equilibrium).
    """

    top: float          # LTH_ext
    bottom: float       # LTL_ext
    top_index: int
    bottom_index: int
    top_degree: str = "STH"    # STH | ITH | LTH | RANGE (fallback)
    bottom_degree: str = "STL"

    @property
    def eq(self) -> float:
        return (self.top + self.bottom) / 2.0

    @property
    def size(self) -> float:
        return self.top - self.bottom

    def contains(self, price: float) -> bool:
        return self.bottom <= price <= self.top

    def classify(self, price: float, tol_frac: float = 0.005) -> str:
        """premium (above EQ) / discount (below EQ) / equilibrium (within tol)."""
        tol = self.size * tol_frac
        if price > self.eq + tol:
            return "premium"
        if price < self.eq - tol:
            return "discount"
        return "equilibrium"

    def depth(self, price: float) -> float:
        """Signed depth from EQ: +1 at the high (deep premium), -1 at the low
        (deep discount), 0 at EQ. |depth| == 0.79 is the OTE 0.79 level."""
        eq = self.eq
        if price >= eq:
            span = self.top - eq
            return (price - eq) / span if span else 0.0
        span = eq - self.bottom
        return -(eq - price) / span if span else 0.0


# --------------------------------------------------------------------------- #
# Breaker / rejection blocks and volume imbalance (more PD arrays)
# --------------------------------------------------------------------------- #
@dataclass
class Breaker:
    """A failed order block that flipped polarity
    (concepts/08-breaker-blocks/breaker-block).

    ``direction`` is the NEW polarity: "bull" = the flipped zone is support,
    "bear" = resistance. The zone is the original OB body.
    """

    index: int          # original OB candle
    ts: datetime
    direction: str      # new polarity: "bull" | "bear"
    low: float          # OB body low
    high: float         # OB body high
    ob_index: int
    break_index: int    # candle that closed through the OB body with displacement
    retested: bool = False
    retested_index: Optional[int] = None
    pd_side: Optional[str] = None

    @property
    def mt(self) -> float:
        return (self.low + self.high) / 2.0


@dataclass
class RejectionBlock:
    """A long-wick rejection at a key level
    (concepts/19-rejection-blocks/rejection-block).

    The rejected WICK is the zone (not the body). ``direction`` "bull" = long
    lower wick rejecting down (support), "bear" = long upper wick rejecting up.
    """

    index: int
    ts: datetime
    direction: str      # "bull" | "bear"
    low: float          # zone low  (wick region)
    high: float         # zone high (wick region)
    wick_pct: float
    mitigated: bool = False
    mitigated_index: Optional[int] = None
    pd_side: Optional[str] = None

    @property
    def tip(self) -> float:
        """The rejected extreme (wick tip) — the SL anchor."""
        return self.low if self.direction == "bull" else self.high


@dataclass
class VolumeImbalance:
    """A body-vs-body gap (concepts/06-fair-value-gaps/volume-imbalance).

    bullish VI: O_n > C_{n-1}  → zone [C_{n-1}, O_n]
    bearish VI: O_n < C_{n-1}  → zone [O_n, C_{n-1}]
    Wicks may overlap — this is what distinguishes a VI from a strict FVG.
    """

    index: int          # candle n (gapped from n-1)
    ts: datetime
    direction: str      # "bull" | "bear"
    low: float
    high: float
    mitigated: bool = False
    mitigated_index: Optional[int] = None
    pd_side: Optional[str] = None

    @property
    def ce(self) -> float:
        return (self.low + self.high) / 2.0

    @property
    def size(self) -> float:
        return self.high - self.low


# --------------------------------------------------------------------------- #
# Liquidity
# --------------------------------------------------------------------------- #
@dataclass
class LiquidityPool:
    """Resting liquidity (concepts/02-liquidity).

    kind  : "BSL" buy-side (above price, at highs) | "SSL" sell-side (below, at lows)
    label : "swing" | "EQH" | "EQL"
    """

    kind: str
    price: float
    index: int          # anchor swing index
    label: str = "swing"
    members: list[int] = field(default_factory=list)
    swept: bool = False
    swept_index: Optional[int] = None


@dataclass
class SessionRange:
    """The high/low of a trading session's most recent occurrence
    (concepts/15-sessions). Session bounds are resting liquidity pools."""

    name: str
    high: float
    low: float
    high_index: int
    low_index: int
    start_index: int
    end_index: int

    @property
    def eq(self) -> float:
        return (self.high + self.low) / 2.0

    @property
    def size(self) -> float:
        return self.high - self.low


@dataclass
class AsianRange:
    """The Asia-session range and its extension targets
    (concepts/14-asian-range). London/NY delivery typically sweeps one bound
    (the Judas swing) then expands toward multiples of the range size."""

    high: float
    low: float
    high_index: int
    low_index: int
    start_index: int
    end_index: int
    swept_side: Optional[str] = None   # "high" | "low" | None

    @property
    def eq(self) -> float:
        return (self.high + self.low) / 2.0

    @property
    def size(self) -> float:
        return self.high - self.low

    def projections(self, multiples=(0.5, 1.0, 1.5, 2.0)) -> dict:
        """Extension targets above (from high) and below (from low)."""
        out = {}
        for m in multiples:
            out[f"up_{m}x"] = self.high + m * self.size
            out[f"down_{m}x"] = self.low - m * self.size
        return out


@dataclass
class IPDALevels:
    """IPDA 20/40/60-day lookback reference highs/lows
    (concepts/23-ipda). The untaken extremes price is drawn toward."""

    levels: dict           # {"20_high": price, "20_low": price, ...}
    days_used: int
    lookbacks: tuple = (20, 40, 60)


@dataclass
class TurtleSoup:
    """A named failed-breakout / swing-failure pattern
    (concepts/20-turtle-soup). A sweep of a level that immediately reverses
    with displacement — the price-action mirror of a liquidity sweep."""

    index: int          # the sweep candle
    ts: datetime
    direction: str      # "bull" (failed bearish breakout) | "bear"
    level: float
    confirm_index: int  # bar where the reversal displacement confirmed
    pd_side: Optional[str] = None


@dataclass
class CRTSetup:
    """Candle Range Theory setup (concepts/21-crt).

    NOTE: CRT is *community-attributed*, not ICT-original — ICT stated it is
    "based on my ideas but not my concept". Included for completeness.
    A later bar sweeps one bound of a HTF reference candle and closes back
    inside; the target is the opposite bound."""

    ref_start: int
    ref_end: int
    ref_high: float
    ref_low: float
    direction: str      # "bull" (low swept -> target high) | "bear"
    sweep_index: int
    target: float


@dataclass
class QuarterlyContext:
    """Quarterly Theory / Power-of-Three time context
    (concepts/22-quarterly-theory, concepts/12-power-of-three).

    Daily quarters map to the AMD-X phases: Q1 accumulation, Q2 manipulation,
    Q3 distribution, Q4 continuation/reversal."""

    tdo: Optional[float] = None            # True Day Open (00:00 NY price)
    tdo_index: Optional[int] = None
    daily_quarter: Optional[str] = None    # "Q1".."Q4"
    phase: Optional[str] = None            # accumulation | manipulation | ...
    price_vs_tdo: Optional[str] = None     # premium | discount | at


@dataclass(frozen=True)
class Sweep:
    """Liquidity sweep / raid (concepts/02-liquidity/liquidity-sweep).

    BSL: high>level AND close<level AND (high-close) > 0.6*range
    SSL: low<level  AND close>level AND (close-low) > 0.6*range
    """

    index: int
    ts: datetime
    kind: str           # "BSL" | "SSL"  (the side that was swept)
    level: float
    extreme: float      # the wick extreme that took the liquidity
    close: float
    wick_pct: float
    pool_index: int


# --------------------------------------------------------------------------- #
# Signal (produced by the scanner that sits on top of the primitives)
# --------------------------------------------------------------------------- #
@dataclass
class Signal:
    direction: str      # "long" | "short"
    ts: datetime
    index: int
    entry: float
    entry_zone: tuple[float, float]
    stop: float
    targets: list[float]
    reasons: list[str]
    score: int
    killzone: Optional[str] = None

    @property
    def risk(self) -> float:
        return abs(self.entry - self.stop)

    @property
    def rr(self) -> Optional[float]:
        if not self.targets or self.risk == 0:
            return None
        return abs(self.targets[0] - self.entry) / self.risk


# --------------------------------------------------------------------------- #
# JSON helpers
# --------------------------------------------------------------------------- #
def _iso(v):
    if isinstance(v, datetime):
        return v.astimezone(timezone.utc).isoformat()
    return v


def to_jsonable(obj):
    """Recursively convert dataclasses / datetimes into JSON-serialisable data."""
    if hasattr(obj, "__dataclass_fields__"):
        d = {}
        for k, v in asdict(obj).items():
            d[k] = to_jsonable(v)
        # include computed props that callers care about
        for prop in ("ce", "size", "mt", "rr", "risk"):
            if hasattr(obj, prop):
                try:
                    d[prop] = to_jsonable(getattr(obj, prop))
                except Exception:
                    pass
        return d
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    return _iso(obj)
