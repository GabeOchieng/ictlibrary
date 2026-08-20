"""Visualisation: render a candle series + all detected ICT primitives as a
self-contained, theme-aware HTML candlestick chart (inline SVG, no external
dependencies — it opens in any browser and works as a Claude Artifact).

Each primitive becomes a toggleable overlay layer:
    candles · swings · FVGs · order blocks · liquidity pools · sweeps ·
    structure (BOS/CHoCH/MSS) · signals
"""

from __future__ import annotations

import html
from datetime import timezone
from typing import List, Optional

from .analysis import Analysis
from .models import Signal


# palette (works on both themes; backgrounds are theme-swapped in CSS)
C_BULL = "#26a69a"
C_BEAR = "#ef5350"
C_OB_BULL = "#2962ff"
C_OB_BEAR = "#ff9800"
C_SWEEP = "#ab47bc"
C_BOS = "#8e9aa6"
C_CHOCH = "#ff9800"
C_MSS = "#ffca28"
C_ENTRY = "#ffca28"


def _fmt_price(v: float) -> str:
    return f"{v:.5f}"


def render_html(
    analysis: Analysis,
    path: str,
    *,
    title: str = "ICT Concept Map",
    instrument: str = "",
    granularity: str = "",
    signals: Optional[List[Signal]] = None,
    max_candles: int = 220,
) -> str:
    """Render ``analysis`` to a standalone HTML file at ``path``. Returns path."""
    candles = analysis.candles
    if not candles:
        raise ValueError("no candles to render")

    # window to the last ``max_candles`` bars but keep original indices
    start = max(0, len(candles) - max_candles)
    view = list(range(start, len(candles)))

    # ---- geometry -------------------------------------------------------- #
    # Adaptive candle spacing: with few bars, widen the slots so the chart
    # stays landscape and fits in one frame; with many bars, tighten toward a
    # floor (the page caps height so the whole series fits vertically).
    n_view = len(view)
    slot = max(6.5, min(22.0, 1100.0 / max(n_view, 1)))
    mL, mR, mT, mB = 8.0, 78.0, 14.0, 30.0
    plot_w = n_view * slot
    W = plot_w + mL + mR
    H = 440.0
    plot_h = H - mT - mB

    lows = [candles[i].low for i in view]
    highs = [candles[i].high for i in view]
    extra = [p.price for p in analysis.pools]
    if signals:
        for s in signals:
            extra += [s.entry, s.stop, *s.targets, *s.entry_zone]
    pmin = min(lows + extra) if extra else min(lows)
    pmax = max(highs + extra) if extra else max(highs)
    pad = (pmax - pmin) * 0.06 or (pmax * 0.001)
    pmin -= pad
    pmax += pad

    def x_of(idx: int) -> float:
        return mL + (idx - start) * slot + slot / 2.0

    def y_of(price: float) -> float:
        return mT + (pmax - price) / (pmax - pmin) * plot_h

    def right_edge() -> float:
        return mL + plot_w

    parts: List[str] = []
    parts.append(f'<svg viewBox="0 0 {W:.0f} {H:.0f}" '
                 f'preserveAspectRatio="xMinYMid meet" class="chart" '
                 f'role="img" aria-label="{html.escape(title)}">')

    # ---- price grid ------------------------------------------------------ #
    parts.append('<g class="grid">')
    for k in range(7):
        p = pmin + (pmax - pmin) * k / 6
        y = y_of(p)
        parts.append(f'<line x1="{mL:.1f}" y1="{y:.1f}" x2="{right_edge():.1f}" '
                     f'y2="{y:.1f}" class="gridline"/>')
        parts.append(f'<text x="{right_edge()+4:.1f}" y="{y+3:.1f}" '
                     f'class="axis">{_fmt_price(p)}</text>')
    # sparse time axis — keep labels at least ~5 slots apart so they never collide
    n = len(view)
    step = max(n // 8, int(46 / slot) + 1, 1)
    for k in range(0, n, step):
        idx = view[k]
        t = candles[idx].ts.astimezone(timezone.utc)
        parts.append(f'<text x="{x_of(idx):.1f}" y="{H-8:.1f}" '
                     f'class="axis time" text-anchor="middle">'
                     f'{t.strftime("%m-%d %H:%M")}</text>')
    parts.append('</g>')

    # ---- dealing range: premium / discount bands + EQ (drawn first) ----- #
    dr = analysis.dealing_range
    if dr is not None:
        yt, ye, yb = y_of(dr.top), y_of(dr.eq), y_of(dr.bottom)
        parts.append('<g data-layer="pd">')
        # premium band (above EQ) tinted bearish, discount band tinted bullish
        parts.append(f'<rect x="{mL:.1f}" y="{yt:.1f}" width="{plot_w:.1f}" '
                     f'height="{max(ye-yt,1):.1f}" fill="{C_BEAR}" fill-opacity="0.05"/>')
        parts.append(f'<rect x="{mL:.1f}" y="{ye:.1f}" width="{plot_w:.1f}" '
                     f'height="{max(yb-ye,1):.1f}" fill="{C_BULL}" fill-opacity="0.05"/>')
        # EQ line
        parts.append(f'<line x1="{mL:.1f}" y1="{ye:.1f}" x2="{right_edge():.1f}" '
                     f'y2="{ye:.1f}" stroke="var(--muted)" stroke-width="1" '
                     f'stroke-dasharray="7 4"/>')
        parts.append(f'<text x="{mL+3:.1f}" y="{ye-3:.1f}" class="tag" '
                     f'fill="var(--muted)">EQ {_fmt_price(dr.eq)}</text>')
        # range bounds
        for price, deg in ((dr.top, dr.top_degree), (dr.bottom, dr.bottom_degree)):
            yy = y_of(price)
            parts.append(f'<line x1="{mL:.1f}" y1="{yy:.1f}" x2="{right_edge():.1f}" '
                         f'y2="{yy:.1f}" stroke="var(--muted)" stroke-width="0.8" '
                         f'stroke-opacity="0.6"/>')
            parts.append(f'<text x="{mL+3:.1f}" y="{yy-3:.1f}" class="tag" '
                         f'fill="var(--muted)">{deg}</text>')
        parts.append('</g>')

    # ---- session ranges -------------------------------------------------- #
    if analysis.session_ranges:
        parts.append('<g data-layer="sessions">')
        for sr in analysis.session_ranges:
            x1 = x_of(max(sr.start_index, start))
            x2 = x_of(min(sr.end_index, len(candles) - 1))
            yh, yl = y_of(sr.high), y_of(sr.low)
            for yy in (yh, yl):
                parts.append(f'<line x1="{x1:.1f}" y1="{yy:.1f}" x2="{x2:.1f}" '
                             f'y2="{yy:.1f}" stroke="var(--muted)" stroke-width="0.8" '
                             f'stroke-opacity="0.55" stroke-dasharray="2 2"/>')
            parts.append(f'<text x="{x1+2:.1f}" y="{yh-2:.1f}" class="tag" '
                         f'fill="var(--muted)">{html.escape(sr.name)}</text>')
        parts.append('</g>')

    # ---- Asian range + projections -------------------------------------- #
    ar = analysis.asian_range
    if ar is not None:
        parts.append('<g data-layer="asian">')
        x1 = x_of(max(ar.start_index, start))
        yh, yl = y_of(ar.high), y_of(ar.low)
        parts.append(f'<rect x="{x1:.1f}" y="{yh:.1f}" width="{right_edge()-x1:.1f}" '
                     f'height="{max(yl-yh,1):.1f}" fill="{C_MSS}" fill-opacity="0.06" '
                     f'stroke="{C_MSS}" stroke-opacity="0.6" stroke-dasharray="4 3"/>')
        parts.append(f'<text x="{x1+2:.1f}" y="{yh-2:.1f}" class="tag" '
                     f'fill="{C_MSS}">Asia</text>')
        for name, price in ar.projections().items():
            yy = y_of(price)
            parts.append(f'<line x1="{x1:.1f}" y1="{yy:.1f}" x2="{right_edge():.1f}" '
                         f'y2="{yy:.1f}" stroke="{C_MSS}" stroke-width="0.7" '
                         f'stroke-opacity="0.4" stroke-dasharray="1 3"/>')
            parts.append(f'<text x="{right_edge()+4:.1f}" y="{yy+3:.1f}" class="tag" '
                         f'fill="{C_MSS}">{name}</text>')
        parts.append('</g>')

    # ---- IPDA lookback levels ------------------------------------------- #
    if analysis.ipda and analysis.ipda.levels:
        parts.append('<g data-layer="ipda">')
        seen = set()
        for key, price in analysis.ipda.levels.items():
            r = round(price, 6)
            if r in seen:
                continue
            seen.add(r)
            yy = y_of(price)
            parts.append(f'<line x1="{mL:.1f}" y1="{yy:.1f}" x2="{right_edge():.1f}" '
                         f'y2="{yy:.1f}" stroke="{C_OB_BEAR}" stroke-width="0.8" '
                         f'stroke-opacity="0.5" stroke-dasharray="6 4"/>')
            # offset from the left edge so it clears the dealing-range degree labels
            parts.append(f'<text x="{mL+64:.1f}" y="{yy-2:.1f}" class="tag" '
                         f'fill="{C_OB_BEAR}">IPDA {html.escape(key)}</text>')
        parts.append('</g>')

    # ---- CRT reference candles (community-attributed) ------------------- #
    if analysis.crt_setups:
        parts.append('<g data-layer="crt">')
        for cr in analysis.crt_setups:
            if cr.ref_end < start:
                continue
            x1 = x_of(max(cr.ref_start, start))
            x2 = x_of(cr.sweep_index if cr.sweep_index >= start else cr.ref_end)
            yt, yb = y_of(cr.ref_high), y_of(cr.ref_low)
            parts.append(f'<rect x="{x1:.1f}" y="{yt:.1f}" width="{max(x2-x1,slot):.1f}" '
                         f'height="{max(yb-yt,1):.1f}" fill="none" stroke="{C_OB_BULL}" '
                         f'stroke-opacity="0.4" stroke-dasharray="2 3"/>')
        parts.append('</g>')

    # ---- True Day Open --------------------------------------------------- #
    q = analysis.quarterly
    if q is not None and q.tdo is not None:
        parts.append('<g data-layer="tdo">')
        yy = y_of(q.tdo)
        parts.append(f'<line x1="{mL:.1f}" y1="{yy:.1f}" x2="{right_edge():.1f}" '
                     f'y2="{yy:.1f}" stroke="var(--fg)" stroke-width="0.9" '
                     f'stroke-opacity="0.5" stroke-dasharray="8 3"/>')
        parts.append(f'<text x="{mL+120:.1f}" y="{yy-2:.1f}" class="tag" '
                     f'fill="var(--fg)">TDO {_fmt_price(q.tdo)}</text>')
        parts.append('</g>')

    # ---- Turtle Soup markers -------------------------------------------- #
    if analysis.turtle_soups:
        parts.append('<g data-layer="turtle">')
        for ts in analysis.turtle_soups:
            if ts.index < start:
                continue
            x = x_of(ts.index)
            y = y_of(ts.level)
            up = ts.direction == "bull"
            yb = y + 12 if up else y - 12
            parts.append(f'<circle cx="{x:.1f}" cy="{yb:.1f}" r="4" fill="none" '
                         f'stroke="{C_SWEEP}" stroke-width="1.4"/>')
            parts.append(f'<text x="{x:.1f}" y="{yb+3:.1f}" class="tag" '
                         f'fill="{C_SWEEP}" text-anchor="middle">TS</text>')
        parts.append('</g>')

    # ---- liquidity pools (draw first, behind candles) ------------------- #
    parts.append('<g data-layer="pools">')
    for p in analysis.pools:
        if p.index < start:
            xs = mL
        else:
            xs = x_of(p.index)
        y = y_of(p.price)
        col = C_BEAR if p.kind == "BSL" else C_BULL
        is_eq = p.label in ("EQH", "EQL")
        wdt = 1.6 if is_eq else 0.9
        dash = "1 0" if is_eq else "4 3"
        cls = "swept" if p.swept else ""
        tag = p.label if is_eq else p.kind  # EQH/EQL, else BSL/SSL
        parts.append(f'<line class="pool {cls}" x1="{xs:.1f}" y1="{y:.1f}" '
                     f'x2="{right_edge():.1f}" y2="{y:.1f}" stroke="{col}" '
                     f'stroke-width="{wdt}" stroke-dasharray="{dash}"/>')
        # tag sits at the pool's origin (left) so it never collides with the axis
        parts.append(f'<text x="{xs+3:.1f}" y="{y-2:.1f}" '
                     f'class="tag" fill="{col}">{tag}</text>')
    parts.append('</g>')

    # ---- FVGs ------------------------------------------------------------ #
    parts.append('<g data-layer="fvg">')
    for f in analysis.fvgs:
        x1 = x_of(max(f.index - 1, start))
        end_idx = f.mitigated_index if f.mitigated_index else len(candles) - 1
        x2 = x_of(min(end_idx, len(candles) - 1))
        yt, yb = y_of(f.high), y_of(f.low)
        col = C_BULL if f.direction == "bull" else C_BEAR
        op = 0.09 if f.mitigated else 0.20
        parts.append(f'<rect class="fvg" x="{x1:.1f}" y="{yt:.1f}" '
                     f'width="{max(x2-x1,slot):.1f}" height="{max(yb-yt,1):.1f}" '
                     f'fill="{col}" fill-opacity="{op}" stroke="{col}" '
                     f'stroke-opacity="0.5" stroke-dasharray="3 2">'
                     f'<title>{f.direction} FVG {_fmt_price(f.low)}-'
                     f'{_fmt_price(f.high)} CE {_fmt_price(f.ce)}'
                     f'{" (mitigated)" if f.mitigated else ""}</title></rect>')
    parts.append('</g>')

    # ---- order blocks ---------------------------------------------------- #
    parts.append('<g data-layer="ob">')
    for o in analysis.order_blocks:
        x1 = x_of(o.index)
        end_idx = o.mitigated_index if o.mitigated_index else len(candles) - 1
        x2 = x_of(min(end_idx, len(candles) - 1))
        yt, yb = y_of(o.high), y_of(o.low)
        col = C_OB_BULL if o.direction == "bull" else C_OB_BEAR
        op = 0.08 if o.mitigated else 0.16
        parts.append(f'<rect class="ob" x="{x1:.1f}" y="{yt:.1f}" '
                     f'width="{max(x2-x1,slot):.1f}" height="{max(yb-yt,1):.1f}" '
                     f'fill="{col}" fill-opacity="{op}" stroke="{col}" '
                     f'stroke-opacity="0.6">'
                     f'<title>{o.direction} OB {_fmt_price(o.low)}-'
                     f'{_fmt_price(o.high)} MT {_fmt_price(o.mt)}'
                     f'{" (mitigated)" if o.mitigated else ""}</title></rect>')
    parts.append('</g>')

    # ---- breaker blocks (flipped OBs) ----------------------------------- #
    parts.append('<g data-layer="breakers">')
    for b in analysis.breakers:
        x1 = x_of(b.break_index)
        end_idx = b.retested_index if b.retested_index else len(candles) - 1
        x2 = x_of(min(end_idx, len(candles) - 1))
        yt, yb = y_of(b.high), y_of(b.low)
        col = C_BULL if b.direction == "bull" else C_BEAR
        parts.append(f'<rect class="brk" x="{x1:.1f}" y="{yt:.1f}" '
                     f'width="{max(x2-x1,slot):.1f}" height="{max(yb-yt,1):.1f}" '
                     f'fill="{col}" fill-opacity="0.10" stroke="{col}" '
                     f'stroke-width="1.3" stroke-dasharray="2 2">'
                     f'<title>{b.direction} breaker {_fmt_price(b.low)}-'
                     f'{_fmt_price(b.high)} (flipped OB)</title></rect>')
        parts.append(f'<text x="{x1+2:.1f}" y="{yt-2:.1f}" class="tag" '
                     f'fill="{col}">BRK</text>')
    parts.append('</g>')

    # ---- rejection blocks (wick zones) ---------------------------------- #
    parts.append('<g data-layer="rejection">')
    for rb in analysis.rejection_blocks:
        if rb.index < start:
            continue
        x = x_of(rb.index)
        yt, yb = y_of(rb.high), y_of(rb.low)
        col = C_BULL if rb.direction == "bull" else C_BEAR
        parts.append(f'<rect x="{x-slot*0.55:.1f}" y="{yt:.1f}" '
                     f'width="{slot*1.1:.1f}" height="{max(yb-yt,1):.1f}" '
                     f'fill="{col}" fill-opacity="0.22" stroke="{col}" '
                     f'stroke-opacity="0.7" stroke-width="0.8">'
                     f'<title>{rb.direction} rejection block '
                     f'(wick {rb.wick_pct*100:.0f}%)</title></rect>')
    parts.append('</g>')

    # ---- volume imbalances (body gaps) ---------------------------------- #
    parts.append('<g data-layer="vi">')
    for vi in analysis.volume_imbalances:
        if vi.index < start:
            continue
        x = x_of(vi.index)
        yt, yb = y_of(vi.high), y_of(vi.low)
        col = C_BULL if vi.direction == "bull" else C_BEAR
        parts.append(f'<rect x="{x-slot*0.45:.1f}" y="{yt:.1f}" '
                     f'width="{slot*0.9:.1f}" height="{max(yb-yt,1):.1f}" '
                     f'fill="{col}" fill-opacity="0.30">'
                     f'<title>{vi.direction} volume imbalance '
                     f'{_fmt_price(vi.low)}-{_fmt_price(vi.high)}</title></rect>')
    parts.append('</g>')

    # ---- candles --------------------------------------------------------- #
    parts.append('<g data-layer="candles">')
    bw = slot * 0.62
    for idx in view:
        c = candles[idx]
        x = x_of(idx)
        col = C_BULL if c.close >= c.open else C_BEAR
        parts.append(f'<line x1="{x:.1f}" y1="{y_of(c.high):.1f}" x2="{x:.1f}" '
                     f'y2="{y_of(c.low):.1f}" stroke="{col}" stroke-width="1"/>')
        yo, yc = y_of(c.open), y_of(c.close)
        yt = min(yo, yc)
        hgt = max(abs(yc - yo), 0.8)
        parts.append(f'<rect x="{x-bw/2:.1f}" y="{yt:.1f}" width="{bw:.1f}" '
                     f'height="{hgt:.1f}" fill="{col}">'
                     f'<title>{c.ts.strftime("%Y-%m-%d %H:%M")} UTC  '
                     f'O {_fmt_price(c.open)} H {_fmt_price(c.high)} '
                     f'L {_fmt_price(c.low)} C {_fmt_price(c.close)}</title></rect>')
    parts.append('</g>')

    # ---- swings ---------------------------------------------------------- #
    parts.append('<g data-layer="swings">')
    for s in analysis.swings:
        if s.index < start:
            continue
        x, y = x_of(s.index), y_of(s.price)
        col = C_BEAR if s.kind == "high" else C_BULL
        dy = -5 if s.kind == "high" else 5
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.4" fill="{col}">'
                     f'<title>swing {s.kind} {_fmt_price(s.price)}</title></circle>')
    parts.append('</g>')

    # ---- sweeps ---------------------------------------------------------- #
    parts.append('<g data-layer="sweeps">')
    for sw in analysis.sweeps:
        if sw.index < start:
            continue
        x, y = x_of(sw.index), y_of(sw.extreme)
        up = sw.kind == "BSL"
        tip = y - 8 if up else y + 8
        parts.append(f'<path d="M{x-4:.1f},{y:.1f} L{x+4:.1f},{y:.1f} '
                     f'L{x:.1f},{tip:.1f} Z" fill="{C_SWEEP}">'
                     f'<title>{sw.kind} sweep of {_fmt_price(sw.level)} '
                     f'(wick {sw.wick_pct*100:.0f}%)</title></path>')
    parts.append('</g>')

    # ---- structure events ------------------------------------------------ #
    parts.append('<g data-layer="structure">')
    for ev in analysis.events:
        if ev.index < start:
            continue
        x = x_of(ev.index)
        y = y_of(ev.level)
        col = {"BOS": C_BOS, "CHoCH": C_CHOCH, "MSS": C_MSS}[ev.kind]
        parts.append(f'<line x1="{x:.1f}" y1="{mT:.1f}" x2="{x:.1f}" '
                     f'y2="{H-mB:.1f}" stroke="{col}" stroke-width="0.7" '
                     f'stroke-opacity="0.5" stroke-dasharray="2 3"/>')
        parts.append(f'<text x="{x:.1f}" y="{mT+10:.1f}" class="ev" '
                     f'fill="{col}" text-anchor="middle">{ev.kind}</text>'
                     f'<title>{ev.kind} {ev.direction} @ {_fmt_price(ev.level)}</title>')
    parts.append('</g>')

    # ---- Unicorn zones --------------------------------------------------- #
    if analysis.unicorns:
        parts.append('<g data-layer="unicorn">')
        for u in analysis.unicorns:
            if u.index < start:
                continue
            x1 = x_of(u.index)
            yt, yb = y_of(u.high), y_of(u.low)
            parts.append(f'<rect x="{x1:.1f}" y="{yt:.1f}" width="{right_edge()-x1:.1f}" '
                         f'height="{max(yb-yt,1):.1f}" fill="{C_ENTRY}" fill-opacity="0.10" '
                         f'stroke="{C_ENTRY}" stroke-width="1.4" stroke-dasharray="1 0"/>')
            parts.append(f'<text x="{x1+3:.1f}" y="{yt-2:.1f}" class="tag" '
                         f'fill="{C_ENTRY}">🦄 Unicorn</text>')
        parts.append('</g>')

    # ---- signals --------------------------------------------------------- #
    parts.append('<g data-layer="signals">')
    for s in (signals or []):
        x = x_of(s.index)
        zt, zb = y_of(max(s.entry_zone)), y_of(min(s.entry_zone))
        parts.append(f'<rect x="{x:.1f}" y="{zt:.1f}" width="{right_edge()-x:.1f}" '
                     f'height="{max(zb-zt,1):.1f}" fill="{C_ENTRY}" '
                     f'fill-opacity="0.12"/>')
        for price, col, lab in ((s.entry, C_ENTRY, "entry"),
                                (s.stop, C_BEAR, "stop"),
                                *[(t, C_BULL, "target") for t in s.targets]):
            yy = y_of(price)
            parts.append(f'<line x1="{x:.1f}" y1="{yy:.1f}" x2="{right_edge():.1f}" '
                         f'y2="{yy:.1f}" stroke="{col}" stroke-width="1.1" '
                         f'stroke-dasharray="5 3"/>')
        arrow = "▲" if s.direction == "long" else "▼"
        label = f'{arrow} {s.direction.upper()} score {s.score}'
        if s.models:
            label += f' · {s.models[0]}'
        parts.append(f'<text x="{x+3:.1f}" y="{zt-3:.1f}" class="sig" '
                     f'fill="{C_ENTRY}">{html.escape(label)}</text>')
    parts.append('</g>')

    parts.append('</svg>')
    svg = "\n".join(parts)

    # ---- legend + summary ----------------------------------------------- #
    layers = [
        ("candles", "Candles", "var(--fg)"),
        ("pd", "Premium / Discount", C_MSS),
        ("swings", "Swings", C_BULL),
        ("structure", "BOS / CHoCH / MSS", C_MSS),
        ("fvg", "Fair Value Gaps", C_BULL),
        ("ob", "Order Blocks", C_OB_BULL),
        ("breakers", "Breakers", C_BULL),
        ("rejection", "Rejection Blocks", C_BEAR),
        ("vi", "Volume Imbalance", C_BULL),
        ("sessions", "Session Ranges", "var(--muted)"),
        ("asian", "Asian Range", C_MSS),
        ("ipda", "IPDA Levels", C_OB_BEAR),
        ("tdo", "True Day Open", "var(--fg)"),
        ("turtle", "Turtle Soup", C_SWEEP),
        ("crt", "CRT ranges", C_OB_BULL),
        ("pools", "Liquidity Pools", C_BEAR),
        ("sweeps", "Sweeps", C_SWEEP),
        ("unicorn", "Unicorn zones", C_ENTRY),
        ("signals", "Signals", C_ENTRY),
    ]
    legend = "".join(
        f'<label class="leg"><input type="checkbox" checked data-toggle="{lid}">'
        f'<span class="dot" style="background:{col}"></span>{name}</label>'
        for lid, name, col in layers
    )

    su = analysis.summary()
    head = " · ".join([
        f'<b>{html.escape(instrument or "series")}</b>',
        html.escape(granularity) if granularity else "",
        f'bias <b>{su["bias"]}</b>',
        f'price <b>{su["price_state"] or "—"}</b>',
        f'killzone <b>{su["killzone"] or "—"}</b>',
        f'PO3 <b>{su.get("phase") or "—"}</b>',
        f'{su["candles"]} bars',
    ])
    stats = " · ".join([
        f'{su["structure_events"]} structure',
        f'{su["unmitigated_fvgs"]}/{su["fvgs"]} FVG open',
        f'{su["unmitigated_obs"]}/{su["order_blocks"]} OB open',
        f'{su["sweeps"]} sweeps',
        f'{len(signals or [])} signals',
    ])

    doc = _PAGE.format(
        title=html.escape(title),
        head=head,
        stats=stats,
        legend=legend,
        svg=svg,
    )
    with open(path, "w") as fh:
        fh.write(doc)
    return path


def render_equity_html(result, path: str, *, title: str = "Backtest Equity") -> str:
    """Render a backtest equity curve (cumulative R) to a standalone HTML file."""
    curve = result.equity_curve
    stats = result.stats()
    if not curve:
        curve = [0.0]

    W, H = 900.0, 380.0
    mL, mR, mT, mB = 54.0, 20.0, 20.0, 34.0
    pw, ph = W - mL - mR, H - mT - mB
    n = len(curve)
    ymin = min(0.0, min(curve))
    ymax = max(0.0, max(curve))
    if ymax == ymin:
        ymax += 1.0

    def x_of(i):
        return mL + (i / max(n - 1, 1)) * pw

    def y_of(v):
        return mT + (ymax - v) / (ymax - ymin) * ph

    parts = [f'<svg viewBox="0 0 {W:.0f} {H:.0f}" class="chart" role="img" '
             f'aria-label="{html.escape(title)} equity curve">']
    # gridlines
    for k in range(5):
        v = ymin + (ymax - ymin) * k / 4
        y = y_of(v)
        parts.append(f'<line x1="{mL}" y1="{y:.1f}" x2="{mL+pw:.1f}" y2="{y:.1f}" '
                     f'class="gridline"/>')
        parts.append(f'<text x="{mL-6:.1f}" y="{y+3:.1f}" class="axis" '
                     f'text-anchor="end">{v:.1f}R</text>')
    # zero baseline
    y0 = y_of(0.0)
    parts.append(f'<line x1="{mL}" y1="{y0:.1f}" x2="{mL+pw:.1f}" y2="{y0:.1f}" '
                 f'stroke="var(--muted)" stroke-width="1" stroke-dasharray="4 3"/>')
    # area + line
    pts = " ".join(f"{x_of(i):.1f},{y_of(v):.1f}" for i, v in enumerate(curve))
    up = curve[-1] >= 0
    col = C_BULL if up else C_BEAR
    parts.append(f'<polyline points="{mL:.1f},{y0:.1f} {pts} {x_of(n-1):.1f},{y0:.1f}" '
                 f'fill="{col}" fill-opacity="0.10" stroke="none"/>')
    parts.append(f'<polyline points="{pts}" fill="none" stroke="{col}" '
                 f'stroke-width="2"/>')
    for i, v in enumerate(curve):
        parts.append(f'<circle cx="{x_of(i):.1f}" cy="{y_of(v):.1f}" r="2.6" '
                     f'fill="{col}"><title>trade {i+1}: {v:.2f}R cumulative</title></circle>')
    parts.append(f'<text x="{x_of(n-1):.1f}" y="{y_of(curve[-1])-8:.1f}" '
                 f'class="sig" fill="{col}" text-anchor="end">{curve[-1]:.2f}R</text>')
    parts.append('</svg>')

    def stat(label, value):
        return (f'<div class="stat"><div class="v">{value}</div>'
                f'<div class="k">{label}</div></div>')

    if stats.get("trades", 0):
        cards = "".join([
            stat("trades", stats["trades"]),
            stat("win rate", f'{stats["win_rate"]*100:.0f}%'),
            stat("total", f'{stats["total_r"]:+.2f}R'),
            stat("expectancy", f'{stats["expectancy_r"]:+.2f}R'),
            stat("profit factor", stats["profit_factor"]),
            stat("max DD", f'{stats["max_drawdown_r"]:.2f}R'),
        ])
    else:
        cards = stat("trades", 0)

    doc = _EQUITY_PAGE.format(title=html.escape(title), cards=cards,
                             svg="\n".join(parts))
    with open(path, "w") as fh:
        fh.write(doc)
    return path


_EQUITY_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{ --bg:#f7f8fa; --panel:#fff; --fg:#1a2027; --muted:#5b6672;
    --line:#e3e7ec; --border:#d7dde3; }}
  @media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
    --bg:#0e1116; --panel:#161b22; --fg:#e6edf3; --muted:#8b949e;
    --line:#222c37; --border:#2a333d; }} }}
  :root[data-theme="dark"] {{ --bg:#0e1116; --panel:#161b22; --fg:#e6edf3;
    --muted:#8b949e; --line:#222c37; --border:#2a333d; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--fg);
    font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }}
  .wrap {{ max-width:940px; margin:0 auto; padding:22px 18px 32px; }}
  h1 {{ font-size:16px; margin:0 0 14px; font-weight:600; }}
  .stats {{ display:flex; flex-wrap:wrap; gap:10px; margin-bottom:16px; }}
  .stat {{ background:var(--panel); border:1px solid var(--border);
    border-radius:9px; padding:10px 14px; min-width:92px; }}
  .stat .v {{ font-size:19px; font-weight:600; font-variant-numeric:tabular-nums; }}
  .stat .k {{ font-size:11px; color:var(--muted); text-transform:uppercase;
    letter-spacing:.06em; margin-top:2px; }}
  svg.chart {{ width:100%; height:auto; background:var(--panel);
    border:1px solid var(--border); border-radius:10px; }}
  .gridline {{ stroke:var(--line); stroke-width:0.6; }}
  text.axis {{ fill:var(--muted); font-size:10px; font-variant-numeric:tabular-nums; }}
  text.sig {{ font-size:13px; font-weight:700; }}
  footer {{ color:var(--muted); font-size:11px; margin-top:14px; }}
</style></head><body>
<div class="wrap">
  <h1>{title}</h1>
  <div class="stats">{cards}</div>
  {svg}
  <footer>Cumulative R across closed trades. Walk-forward, no lookahead.
  Educational — not financial advice.</footer>
</div></body></html>
"""


_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{
    --bg:#f7f8fa; --panel:#ffffff; --fg:#1a2027; --muted:#5b6672;
    --line:#e3e7ec; --border:#d7dde3;
  }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      --bg:#0e1116; --panel:#161b22; --fg:#e6edf3; --muted:#8b949e;
      --line:#222c37; --border:#2a333d;
    }}
  }}
  :root[data-theme="dark"] {{
    --bg:#0e1116; --panel:#161b22; --fg:#e6edf3; --muted:#8b949e;
    --line:#222c37; --border:#2a333d;
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--fg);
    font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }}
  header {{ padding:14px 18px 6px; }}
  h1 {{ font-size:15px; margin:0 0 4px; font-weight:600; }}
  .sub {{ color:var(--muted); font-size:13px; }}
  .stats {{ color:var(--muted); font-size:12px; margin-top:2px; }}
  .legend {{ display:flex; flex-wrap:wrap; gap:6px 14px; padding:8px 18px 12px; }}
  .leg {{ display:inline-flex; align-items:center; gap:6px; font-size:12.5px;
    color:var(--fg); cursor:pointer; user-select:none; }}
  .leg input {{ accent-color:#2962ff; }}
  .dot {{ width:11px; height:11px; border-radius:2px; display:inline-block; }}
  .wrap {{ overflow-x:auto; padding:0 10px 18px; }}
  svg.chart {{ display:block; margin:0 auto; width:auto; height:auto;
    max-width:100%; max-height:82vh;
    background:var(--panel); border:1px solid var(--border); border-radius:8px; }}
  .gridline {{ stroke:var(--line); stroke-width:0.6; }}
  text.axis {{ fill:var(--muted); font-size:9px; }}
  text.tag {{ font-size:8.5px; font-weight:600; }}
  text.ev {{ font-size:8px; font-weight:700; }}
  text.sig {{ font-size:10px; font-weight:700; }}
  .pool.swept {{ stroke-opacity:0.35; }}
  footer {{ color:var(--muted); font-size:11px; padding:0 18px 20px; }}
  code {{ background:var(--line); padding:1px 4px; border-radius:3px; }}
</style>
</head>
<body>
<header>
  <h1>{title}</h1>
  <div class="sub">{head}</div>
  <div class="stats">{stats}</div>
</header>
<div class="legend">{legend}</div>
<div class="wrap">{svg}</div>
<footer>ICT primitives detected by <code>ictlib</code>. Hover any element for
details · toggle layers above. Educational tool — not financial advice.</footer>
<script>
  document.querySelectorAll('input[data-toggle]').forEach(function(cb){{
    cb.addEventListener('change', function(){{
      var g = document.querySelector('[data-layer="'+cb.dataset.toggle+'"]');
      if (g) g.style.display = cb.checked ? '' : 'none';
    }});
  }});
</script>
</body>
</html>
"""
