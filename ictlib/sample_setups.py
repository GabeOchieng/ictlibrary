"""Canonical hand-authored candle setups used by the example generator and the
test-suite. Each is a list of (open, high, low, close) tuples.

LONG_SETUP: a textbook ICT long — early swing high (future BSL), a bearish leg
that builds sell-side liquidity, a sweep of that SSL, then a bullish MSS
(displaced CHoCH leaving an FVG), a retrace into the FVG/OB, and expansion into
the buy-side liquidity above.
"""

LONG_SETUP = [
    (1.08300, 1.08360, 1.08260, 1.08340),
    (1.08340, 1.08520, 1.08320, 1.08500),
    (1.08500, 1.08800, 1.08470, 1.08760),   # idx2 swing-high ~1.0880 (BSL)
    (1.08760, 1.08780, 1.08560, 1.08600),
    (1.08600, 1.08640, 1.08420, 1.08460),
    (1.08460, 1.08660, 1.08440, 1.08640),   # idx5 lower swing-high ~1.0866
    (1.08640, 1.08660, 1.08380, 1.08400),
    (1.08400, 1.08440, 1.08240, 1.08280),   # bearish displacement -> BOS down
    (1.08280, 1.08320, 1.08200, 1.08230),
    (1.08230, 1.08260, 1.08180, 1.08220),   # idx9 swing-low ~1.0818 (SSL)
    (1.08220, 1.08340, 1.08200, 1.08320),
    (1.08320, 1.08360, 1.08210, 1.08240),   # idx11 equal-low ~1.0821 (EQL)
    (1.08240, 1.08300, 1.08205, 1.08270),
    (1.08270, 1.08300, 1.08060, 1.08260),   # idx13 SSL sweep (long lower wick)
    (1.08280, 1.08300, 1.08250, 1.08290),   # idx14 (n-1)
    (1.08290, 1.08720, 1.08280, 1.08700),   # idx15 (n) bullish displacement -> MSS
    (1.08560, 1.08760, 1.08540, 1.08720),   # idx16 (n+1) leaves bullish FVG
    (1.08720, 1.08740, 1.08420, 1.08480),   # idx17 retrace into FVG / OB
    (1.08480, 1.08620, 1.08450, 1.08600),
    (1.08600, 1.08820, 1.08560, 1.08800),   # idx19 expansion toward BSL
    (1.08800, 1.08900, 1.08760, 1.08840),   # idx20 sweeps old high (target)
    (1.08840, 1.08860, 1.08700, 1.08740),
    (1.08740, 1.08780, 1.08640, 1.08680),
]
