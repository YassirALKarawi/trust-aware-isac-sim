"""
Professional-grade pure-Python SVG plotting library (zero dependencies).

Designed for publication-ready figures: gradients, drop shadows, confidence
bands, error bars, winner highlighting, minor gridlines, and annotated
callouts — all rendered directly to SVG without matplotlib.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


# ---------- style tokens ----------------------------------------------------

PALETTE = [
    "#1f4e79",  # deep blue
    "#c0392b",  # crimson
    "#27ae60",  # emerald
    "#8e44ad",  # purple
    "#e67e22",  # tangerine
    "#16a085",  # teal
    "#34495e",  # slate
    "#d4a017",  # mustard
]

INK = "#0f172a"
MUTED = "#475569"
GRID_MAJOR = "#e2e8f0"
GRID_MINOR = "#f1f5f9"
PANEL_FILL = "#fdfefe"
PAGE_FILL = "#ffffff"
ACCENT = "#0f766e"

FONT = "'Inter','Segoe UI','Helvetica Neue',Arial,sans-serif"


# ---------- common SVG primitives ------------------------------------------

def _defs() -> str:
    """Shared filters, gradients, markers reused across figures."""
    return """
<defs>
  <filter id="panelShadow" x="-5%" y="-5%" width="110%" height="115%">
    <feGaussianBlur in="SourceAlpha" stdDeviation="2.2"/>
    <feOffset dx="0" dy="2"/>
    <feComponentTransfer><feFuncA type="linear" slope="0.18"/></feComponentTransfer>
    <feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <filter id="pointShadow" x="-50%" y="-50%" width="200%" height="200%">
    <feGaussianBlur in="SourceAlpha" stdDeviation="1.4"/>
    <feOffset dx="0" dy="1"/>
    <feComponentTransfer><feFuncA type="linear" slope="0.35"/></feComponentTransfer>
    <feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <marker id="mArrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
    <path d="M0,0 L10,5 L0,10 z" fill="#0f172a"/>
  </marker>
</defs>
"""


def _grad(stop0: str, stop1: str, ident: str, direction: str = "v") -> str:
    if direction == "v":
        attrs = 'x1="0" x2="0" y1="0" y2="1"'
    else:
        attrs = 'x1="0" x2="1" y1="0" y2="0"'
    return (
        f'<linearGradient id="{ident}" {attrs}>'
        f'<stop offset="0" stop-color="{stop0}"/>'
        f'<stop offset="1" stop-color="{stop1}"/>'
        f'</linearGradient>'
    )


def _nice_ticks(lo: float, hi: float, target: int = 6) -> list[float]:
    if hi <= lo:
        return [lo]
    span = hi - lo
    raw = span / max(1, target)
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        step = m * mag
        if raw <= step:
            break
    start = math.floor(lo / step) * step
    ticks = []
    v = start
    while v <= hi + 1e-9:
        if v >= lo - 1e-9:
            ticks.append(round(v, 10))
        v += step
    return ticks


def _fmt(v: float, short: bool = False) -> str:
    if abs(v) >= 1e9:
        return f"{v/1e9:.1f}G"
    if abs(v) >= 1e6:
        return f"{v/1e6:.1f}M"
    if abs(v) >= 1e3:
        return f"{v/1e3:.0f}k"
    if v == 0:
        return "0"
    if abs(v) < 1:
        return f"{v:.2f}" if short else f"{v:.3f}"
    if v == int(v):
        return f"{int(v)}"
    return f"{v:.2f}"


# ---------- axes ------------------------------------------------------------

@dataclass
class Axes:
    x0: float
    y0: float
    w: float
    h: float
    x_min: float
    x_max: float
    y_min: float
    y_max: float

    def sx(self, x: float) -> float:
        if self.x_max == self.x_min:
            return self.x0
        return self.x0 + (x - self.x_min) / (self.x_max - self.x_min) * self.w

    def sy(self, y: float) -> float:
        if self.y_max == self.y_min:
            return self.y0 + self.h
        return self.y0 + self.h - (y - self.y_min) / (self.y_max - self.y_min) * self.h


# ---------- canvas builder --------------------------------------------------

class Canvas:
    def __init__(self, width: int, height: int, title: str = "", subtitle: str = ""):
        self.w = width
        self.h = height
        self.parts: list[str] = []
        self.parts.append(
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
            f'width="{width}" height="{height}" font-family="{FONT}" '
            f'role="img" aria-label="{title}">'
        )
        self.parts.append(_defs())
        self.parts.append(f'<rect width="100%" height="100%" fill="{PAGE_FILL}"/>')
        if title:
            self.parts.append(
                f'<text x="{width/2}" y="36" text-anchor="middle" font-size="20" '
                f'font-weight="800" fill="{INK}">{title}</text>'
            )
        if subtitle:
            self.parts.append(
                f'<text x="{width/2}" y="60" text-anchor="middle" font-size="13" '
                f'fill="{MUTED}">{subtitle}</text>'
            )

    def add(self, s: str) -> None:
        self.parts.append(s)

    def finalize(self) -> str:
        self.parts.append("</svg>")
        return "\n".join(self.parts)


def _frame(ax: Axes, x_ticks, y_ticks, x_labels, y_labels,
           x_title: str, y_title: str, minor_density: int = 3) -> str:
    out = []
    # panel
    out.append(
        f'<g filter="url(#panelShadow)">'
        f'<rect x="{ax.x0}" y="{ax.y0}" width="{ax.w}" height="{ax.h}" '
        f'fill="{PANEL_FILL}" stroke="#cbd5e1" stroke-width="1"/>'
        f'</g>'
    )
    # minor grid (horizontal) — between major y ticks
    for i in range(len(y_ticks) - 1):
        span = y_ticks[i+1] - y_ticks[i]
        for m in range(1, minor_density):
            yv = y_ticks[i] + m * span / minor_density
            y = ax.sy(yv)
            out.append(
                f'<line x1="{ax.x0}" y1="{y:.1f}" x2="{ax.x0+ax.w}" y2="{y:.1f}" '
                f'stroke="{GRID_MINOR}" stroke-width="0.6"/>'
            )
    # major horizontal grid
    for yt, lbl in zip(y_ticks, y_labels):
        y = ax.sy(yt)
        out.append(
            f'<line x1="{ax.x0}" y1="{y:.1f}" x2="{ax.x0+ax.w}" y2="{y:.1f}" '
            f'stroke="{GRID_MAJOR}" stroke-width="1"/>'
        )
        out.append(
            f'<text x="{ax.x0-10}" y="{y+4:.1f}" text-anchor="end" '
            f'fill="{MUTED}" font-size="11">{lbl}</text>'
        )
    # major vertical grid
    for xt, lbl in zip(x_ticks, x_labels):
        x = ax.sx(xt)
        out.append(
            f'<line x1="{x:.1f}" y1="{ax.y0}" x2="{x:.1f}" y2="{ax.y0+ax.h}" '
            f'stroke="{GRID_MAJOR}" stroke-width="1"/>'
        )
        out.append(
            f'<text x="{x:.1f}" y="{ax.y0+ax.h+18}" text-anchor="middle" '
            f'fill="{MUTED}" font-size="11">{lbl}</text>'
        )
    # axis titles
    if x_title:
        out.append(
            f'<text x="{ax.x0+ax.w/2}" y="{ax.y0+ax.h+44}" text-anchor="middle" '
            f'fill="{INK}" font-size="13" font-weight="600">{x_title}</text>'
        )
    if y_title:
        out.append(
            f'<text transform="translate({ax.x0-52},{ax.y0+ax.h/2}) rotate(-90)" '
            f'text-anchor="middle" fill="{INK}" font-size="13" '
            f'font-weight="600">{y_title}</text>'
        )
    return "".join(out)


def _legend(items: list[tuple[str, str, str]], x: float, y: float,
            title: str = "") -> str:
    """items: list of (label, color, kind). kind in {line, bar, band, star}."""
    pad = 10
    row_h = 22
    width = 180
    height = pad*2 + (row_h * len(items)) + (22 if title else 0)
    out = [
        f'<g filter="url(#panelShadow)">'
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="8" '
        f'fill="#ffffff" stroke="#cbd5e1"/>'
        f'</g>'
    ]
    cy = y + pad + 8
    if title:
        out.append(
            f'<text x="{x+pad}" y="{cy}" fill="{INK}" font-size="12" '
            f'font-weight="700">{title}</text>'
        )
        cy += 18
    for label, color, kind in items:
        mx = x + pad + 8
        if kind == "line":
            out.append(
                f'<line x1="{x+pad}" y1="{cy-4}" x2="{x+pad+22}" y2="{cy-4}" '
                f'stroke="{color}" stroke-width="2.6"/>'
                f'<circle cx="{mx+3}" cy="{cy-4}" r="3.5" fill="#ffffff" '
                f'stroke="{color}" stroke-width="2"/>'
            )
        elif kind == "bar":
            out.append(
                f'<rect x="{x+pad}" y="{cy-10}" width="22" height="10" '
                f'fill="{color}" rx="2"/>'
            )
        elif kind == "band":
            out.append(
                f'<rect x="{x+pad}" y="{cy-10}" width="22" height="10" '
                f'fill="{color}" opacity="0.35" rx="2"/>'
                f'<line x1="{x+pad}" y1="{cy-5}" x2="{x+pad+22}" y2="{cy-5}" '
                f'stroke="{color}" stroke-width="2"/>'
            )
        elif kind == "star":
            out.append(_star(mx+3, cy-5, 7, color))
        out.append(
            f'<text x="{x+pad+32}" y="{cy}" fill="{INK}" '
            f'font-size="12">{label}</text>'
        )
        cy += row_h
    return "".join(out)


def _star(cx: float, cy: float, r: float, fill: str) -> str:
    pts = []
    for i in range(10):
        ang = -math.pi/2 + i * math.pi / 5
        radius = r if i % 2 == 0 else r * 0.45
        pts.append(f"{cx + radius*math.cos(ang):.1f},{cy + radius*math.sin(ang):.1f}")
    return f'<polygon points="{" ".join(pts)}" fill="{fill}" stroke="#ffffff" stroke-width="1"/>'


# ---------- high-level plots ------------------------------------------------

def bar_plot(
    groups: list[str],
    values: list[float],
    *,
    errors: list[float] | None = None,
    colors: list[str] | None = None,
    title: str = "",
    subtitle: str = "",
    y_title: str = "",
    highlight_index: int | None = None,
    highlight_label: str = "best",
    width: int = 900,
    height: int = 520,
) -> str:
    """Single-metric bar plot with optional error bars and winner highlight."""
    n = len(groups)
    y_max = max(v + (errors[i] if errors else 0) for i, v in enumerate(values))
    y_max *= 1.22
    y_min = 0.0
    if min(values) < 0:
        y_min = min(values) * 1.1

    canv = Canvas(width, height, title=title, subtitle=subtitle)
    # gradients per bar
    grads = []
    bar_colors = colors or [PALETTE[i % len(PALETTE)] for i in range(n)]
    for i, c in enumerate(bar_colors):
        grads.append(_grad(c, _darken(c, 0.22), f"barGrad{i}"))
    canv.add("<defs>" + "".join(grads) + "</defs>")

    ax = Axes(x0=90, y0=90, w=width-220, h=height-170,
              x_min=0, x_max=n, y_min=y_min, y_max=y_max)
    y_ticks = _nice_ticks(y_min, y_max, 6)
    x_ticks = [i + 0.5 for i in range(n)]
    canv.add(_frame(ax, x_ticks, y_ticks, groups, [_fmt(v) for v in y_ticks],
                    "", y_title))

    bar_w = ax.w / n * 0.62
    for i, v in enumerate(values):
        cx = ax.x0 + (i + 0.5) * ax.w / n
        xs = cx - bar_w / 2
        ys = ax.sy(v)
        h = ax.sy(y_min) - ys
        canv.add(
            f'<rect x="{xs:.1f}" y="{ys:.1f}" width="{bar_w:.1f}" height="{h:.1f}" '
            f'fill="url(#barGrad{i})" stroke="{_darken(bar_colors[i], 0.3)}" '
            f'stroke-width="1" rx="3"/>'
        )
        # error bar
        if errors and errors[i] > 0:
            e = errors[i]
            y_top = ax.sy(v + e)
            y_bot = ax.sy(max(y_min, v - e))
            cap = 9
            canv.add(
                f'<g stroke="{INK}" stroke-width="1.4" fill="none">'
                f'<line x1="{cx:.1f}" y1="{y_top:.1f}" x2="{cx:.1f}" y2="{y_bot:.1f}"/>'
                f'<line x1="{cx-cap/2:.1f}" y1="{y_top:.1f}" x2="{cx+cap/2:.1f}" y2="{y_top:.1f}"/>'
                f'<line x1="{cx-cap/2:.1f}" y1="{y_bot:.1f}" x2="{cx+cap/2:.1f}" y2="{y_bot:.1f}"/>'
                f'</g>'
            )
        # label above
        canv.add(
            f'<text x="{cx:.1f}" y="{ys-10:.1f}" text-anchor="middle" '
            f'fill="{INK}" font-size="11" font-weight="700">{_fmt(v)}</text>'
        )
        # highlight
        if highlight_index == i:
            canv.add(_star(cx, ys-30, 9, "#f59e0b"))
            canv.add(
                f'<text x="{cx:.1f}" y="{ys-44:.1f}" text-anchor="middle" '
                f'fill="#b45309" font-size="11" font-weight="700">{highlight_label}</text>'
            )
    return canv.finalize()


def grouped_bar_plot(
    groups: list[str],
    series: list[dict],
    *,
    title: str = "",
    subtitle: str = "",
    y_title: str = "",
    width: int = 980,
    height: int = 540,
    highlight_group_index: int | None = None,
) -> str:
    """series: [{name, values, color}]. All series share the same groups."""
    n_groups = len(groups)
    n_series = len(series)
    all_vals = [v for s in series for v in s["values"]]
    y_max = max(all_vals) * 1.18
    y_min = 0.0

    canv = Canvas(width, height, title=title, subtitle=subtitle)
    grads = []
    for i, s in enumerate(series):
        grads.append(_grad(s["color"], _darken(s["color"], 0.25), f"gb{i}"))
    canv.add("<defs>" + "".join(grads) + "</defs>")

    ax = Axes(x0=90, y0=90, w=width-230, h=height-170,
              x_min=0, x_max=n_groups, y_min=y_min, y_max=y_max)
    y_ticks = _nice_ticks(y_min, y_max, 6)
    x_ticks = [i + 0.5 for i in range(n_groups)]
    canv.add(_frame(ax, x_ticks, y_ticks, groups, [_fmt(v) for v in y_ticks],
                    "", y_title))

    group_w = ax.w / n_groups
    gap = group_w * 0.14
    bar_w = (group_w - gap) / n_series * 0.9

    for g in range(n_groups):
        if highlight_group_index == g:
            # subtle highlight of the group
            canv.add(
                f'<rect x="{ax.x0 + g*group_w + gap/3:.1f}" y="{ax.y0}" '
                f'width="{group_w-2*gap/3:.1f}" height="{ax.h}" '
                f'fill="#fef3c7" opacity="0.55" rx="6"/>'
            )

    for i, s in enumerate(series):
        for g, v in enumerate(s["values"]):
            x = ax.x0 + g * group_w + gap/2 + i * bar_w + i*2
            ys = ax.sy(v)
            h = ax.sy(y_min) - ys
            canv.add(
                f'<rect x="{x:.1f}" y="{ys:.1f}" width="{bar_w:.1f}" height="{h:.1f}" '
                f'fill="url(#gb{i})" stroke="{_darken(s["color"], 0.3)}" '
                f'stroke-width="0.8" rx="2"/>'
            )
            canv.add(
                f'<text x="{x+bar_w/2:.1f}" y="{ys-4:.1f}" text-anchor="middle" '
                f'fill="{INK}" font-size="9.5" font-weight="600">{_fmt(v, short=True)}</text>'
            )

    legend_items = [(s["name"], s["color"], "bar") for s in series]
    canv.add(_legend(legend_items, ax.x0 + ax.w + 22, ax.y0 + 8, "Series"))
    return canv.finalize()


def line_plot(
    series: list[dict],
    *,
    title: str = "",
    subtitle: str = "",
    x_title: str = "",
    y_title: str = "",
    width: int = 940,
    height: int = 540,
    y_min_override: float | None = None,
    y_max_override: float | None = None,
    annotations: list[dict] | None = None,
    highlight_series: str | None = None,
    horizontal_lines: list[dict] | None = None,
    shaded_x_regions: list[dict] | None = None,
    legend_title: str = "Method",
) -> str:
    """series: [{name, x, y, color, band? (list of half-widths), dashed?}]."""
    xs_all = [v for s in series for v in s["x"]]
    ys_all = [v for s in series for v in s["y"]]
    bands_present = any("band" in s for s in series)
    if bands_present:
        for s in series:
            if "band" in s:
                ys_all += [y + b for y, b in zip(s["y"], s["band"])]
                ys_all += [y - b for y, b in zip(s["y"], s["band"])]
    x_min, x_max = min(xs_all), max(xs_all)
    y_min = y_min_override if y_min_override is not None else min(ys_all)
    y_max = y_max_override if y_max_override is not None else max(ys_all)
    span = y_max - y_min
    if y_min_override is None:
        y_min -= 0.05 * span
    if y_max_override is None:
        y_max += 0.10 * span

    canv = Canvas(width, height, title=title, subtitle=subtitle)
    ax = Axes(x0=90, y0=90, w=width-240, h=height-170,
              x_min=x_min, x_max=x_max, y_min=y_min, y_max=y_max)
    x_ticks = _nice_ticks(x_min, x_max, 7)
    y_ticks = _nice_ticks(y_min, y_max, 6)
    canv.add(_frame(ax, x_ticks, y_ticks,
                    [_fmt(v, short=True) for v in x_ticks],
                    [_fmt(v) for v in y_ticks], x_title, y_title))

    # horizontal reference lines
    if horizontal_lines:
        for hl in horizontal_lines:
            y = ax.sy(hl["y"])
            color = hl.get("color", "#b91c1c")
            canv.add(
                f'<line x1="{ax.x0}" y1="{y:.1f}" x2="{ax.x0+ax.w}" y2="{y:.1f}" '
                f'stroke="{color}" stroke-width="1.5" stroke-dasharray="5 3"/>'
                f'<text x="{ax.x0+ax.w-6}" y="{y-5:.1f}" text-anchor="end" '
                f'fill="{color}" font-size="11" font-weight="600">{hl["label"]}</text>'
            )

    # shaded x regions
    if shaded_x_regions:
        for reg in shaded_x_regions:
            x0 = ax.sx(reg["x0"])
            x1 = ax.sx(reg["x1"])
            color = reg.get("color", "#fee2e2")
            canv.add(
                f'<rect x="{x0:.1f}" y="{ax.y0}" width="{x1-x0:.1f}" height="{ax.h}" '
                f'fill="{color}" opacity="0.7"/>'
            )
            if reg.get("label"):
                canv.add(
                    f'<text x="{(x0+x1)/2:.1f}" y="{ax.y0+16}" text-anchor="middle" '
                    f'fill="#991b1b" font-size="12" font-weight="700">{reg["label"]}</text>'
                )

    # bands first (so they sit under the lines)
    for i, s in enumerate(series):
        color = s.get("color", PALETTE[i % len(PALETTE)])
        if "band" in s and s["band"]:
            pts_top = [(ax.sx(x), ax.sy(y + b)) for x, y, b in zip(s["x"], s["y"], s["band"])]
            pts_bot = [(ax.sx(x), ax.sy(y - b)) for x, y, b in zip(s["x"], s["y"], s["band"])]
            poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts_top + list(reversed(pts_bot)))
            canv.add(f'<polygon points="{poly}" fill="{color}" opacity="0.14"/>')

    # lines + markers
    for i, s in enumerate(series):
        color = s.get("color", PALETTE[i % len(PALETTE)])
        dashed = 'stroke-dasharray="6,4"' if s.get("dashed") else ""
        pts = " ".join(f"{ax.sx(x):.1f},{ax.sy(y):.1f}" for x, y in zip(s["x"], s["y"]))
        emphasis = highlight_series == s.get("name")
        sw = 3.2 if emphasis else 2.4
        canv.add(
            f'<polyline points="{pts}" fill="none" stroke="{color}" '
            f'stroke-width="{sw}" {dashed} stroke-linejoin="round" '
            f'stroke-linecap="round"/>'
        )
        for x, y in zip(s["x"], s["y"]):
            r = 5 if emphasis else 4
            canv.add(
                f'<circle cx="{ax.sx(x):.1f}" cy="{ax.sy(y):.1f}" r="{r}" '
                f'fill="#ffffff" stroke="{color}" stroke-width="2.2" '
                f'filter="url(#pointShadow)"/>'
            )

    # annotations
    if annotations:
        for a in annotations:
            x = ax.sx(a["x"])
            y = ax.sy(a["y"])
            dx = a.get("dx", 20)
            dy = a.get("dy", -25)
            canv.add(
                f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x+dx:.1f}" y2="{y+dy:.1f}" '
                f'stroke="{INK}" stroke-width="1"/>'
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="none" '
                f'stroke="{INK}" stroke-width="1.5"/>'
            )
            # label box
            txt = a["text"]
            tw = max(60, 7.5 * len(txt) + 12)
            canv.add(
                f'<rect x="{x+dx-4:.1f}" y="{y+dy-14:.1f}" width="{tw}" height="20" '
                f'rx="4" fill="#ffffff" stroke="{INK}" stroke-width="0.8"/>'
                f'<text x="{x+dx+tw/2-4:.1f}" y="{y+dy:.1f}" text-anchor="middle" '
                f'fill="{INK}" font-size="11" font-weight="600">{txt}</text>'
            )

    legend_items = []
    for i, s in enumerate(series):
        color = s.get("color", PALETTE[i % len(PALETTE)])
        kind = "band" if "band" in s else "line"
        legend_items.append((s["name"], color, kind))
    canv.add(_legend(legend_items, ax.x0 + ax.w + 22, ax.y0 + 8, legend_title))
    return canv.finalize()


def time_series(
    traces: list[dict],
    *,
    title: str = "",
    subtitle: str = "",
    x_title: str = "",
    y_title: str = "",
    width: int = 1000,
    height: int = 500,
    shaded_regions: list[dict] | None = None,
    horizontal_lines: list[dict] | None = None,
    y_min_override: float | None = None,
    y_max_override: float | None = None,
    annotations: list[dict] | None = None,
) -> str:
    n = max(len(t["y"]) for t in traces)
    ys_all = [v for t in traces for v in t["y"]]
    y_min = y_min_override if y_min_override is not None else min(ys_all)
    y_max = y_max_override if y_max_override is not None else max(ys_all)

    canv = Canvas(width, height, title=title, subtitle=subtitle)
    ax = Axes(x0=90, y0=90, w=width-240, h=height-170,
              x_min=0, x_max=n-1, y_min=y_min, y_max=y_max)
    x_ticks = _nice_ticks(0, n-1, 8)
    y_ticks = _nice_ticks(y_min, y_max, 6)
    canv.add(_frame(ax, x_ticks, y_ticks,
                    [_fmt(v, short=True) for v in x_ticks],
                    [_fmt(v) for v in y_ticks], x_title, y_title))

    if shaded_regions:
        for reg in shaded_regions:
            x0 = ax.sx(reg["x0"])
            x1 = ax.sx(reg["x1"])
            color = reg.get("color", "#fecaca")
            canv.add(
                f'<rect x="{x0:.1f}" y="{ax.y0}" width="{x1-x0:.1f}" height="{ax.h}" '
                f'fill="{color}" opacity="0.55"/>'
            )
            if reg.get("label"):
                canv.add(
                    f'<text x="{(x0+x1)/2:.1f}" y="{ax.y0+18}" text-anchor="middle" '
                    f'fill="#7f1d1d" font-size="12" font-weight="700">{reg["label"]}</text>'
                )

    if horizontal_lines:
        for hl in horizontal_lines:
            y = ax.sy(hl["y"])
            color = hl.get("color", "#b91c1c")
            canv.add(
                f'<line x1="{ax.x0}" y1="{y:.1f}" x2="{ax.x0+ax.w}" y2="{y:.1f}" '
                f'stroke="{color}" stroke-width="1.5" stroke-dasharray="5 3"/>'
                f'<text x="{ax.x0+ax.w-6}" y="{y-5:.1f}" text-anchor="end" '
                f'fill="{color}" font-size="11" font-weight="600">{hl["label"]}</text>'
            )

    for i, t in enumerate(traces):
        color = t.get("color", PALETTE[i % len(PALETTE)])
        pts = " ".join(f"{ax.sx(k):.1f},{ax.sy(v):.1f}"
                       for k, v in enumerate(t["y"]))
        canv.add(
            f'<polyline points="{pts}" fill="none" stroke="{color}" '
            f'stroke-width="2.0" stroke-linejoin="round"/>'
        )

    if annotations:
        for a in annotations:
            x = ax.sx(a["x"])
            y = ax.sy(a["y"])
            dx = a.get("dx", 20)
            dy = a.get("dy", -25)
            canv.add(
                f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x+dx:.1f}" y2="{y+dy:.1f}" '
                f'stroke="{INK}" stroke-width="1"/>'
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="{a.get("color","#0f172a")}" '
                f'stroke="#ffffff" stroke-width="2"/>'
            )
            txt = a["text"]
            tw = max(60, 7.5 * len(txt) + 12)
            canv.add(
                f'<rect x="{x+dx-4:.1f}" y="{y+dy-14:.1f}" width="{tw}" height="20" '
                f'rx="4" fill="#ffffff" stroke="{INK}" stroke-width="0.8"/>'
                f'<text x="{x+dx+tw/2-4:.1f}" y="{y+dy:.1f}" text-anchor="middle" '
                f'fill="{INK}" font-size="11" font-weight="600">{txt}</text>'
            )

    legend_items = [(t["name"], t.get("color", PALETTE[i % len(PALETTE)]), "line")
                    for i, t in enumerate(traces)]
    canv.add(_legend(legend_items, ax.x0 + ax.w + 22, ax.y0 + 8, "Trace"))
    return canv.finalize()


def scatter_plot(
    points: list[dict],
    *,
    title: str = "",
    subtitle: str = "",
    x_title: str = "",
    y_title: str = "",
    width: int = 940,
    height: int = 540,
    frontier: list[tuple[float, float]] | None = None,
) -> str:
    """points: [{x, y, label, color}]."""
    xs = [p["x"] for p in points]
    ys = [p["y"] for p in points]
    x_span = max(xs) - min(xs)
    y_span = max(ys) - min(ys)
    x_min = min(xs) - 0.08 * x_span - 1e-6
    x_max = max(xs) + 0.08 * x_span + 1e-6
    y_min = min(ys) - 0.12 * y_span
    y_max = max(ys) + 0.14 * y_span

    canv = Canvas(width, height, title=title, subtitle=subtitle)
    ax = Axes(x0=100, y0=90, w=width-240, h=height-170,
              x_min=x_min, x_max=x_max, y_min=y_min, y_max=y_max)
    x_ticks = _nice_ticks(x_min, x_max, 6)
    y_ticks = _nice_ticks(y_min, y_max, 6)
    canv.add(_frame(ax, x_ticks, y_ticks,
                    [_fmt(v, short=True) for v in x_ticks],
                    [_fmt(v) for v in y_ticks], x_title, y_title))

    if frontier:
        pts = " ".join(f"{ax.sx(x):.1f},{ax.sy(y):.1f}" for x, y in frontier)
        canv.add(
            f'<polyline points="{pts}" fill="none" stroke="#0f766e" '
            f'stroke-width="2" stroke-dasharray="6 4" opacity="0.65"/>'
        )

    for p in points:
        x = ax.sx(p["x"])
        y = ax.sy(p["y"])
        color = p.get("color", PALETTE[0])
        r = p.get("r", 10)
        canv.add(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{color}" '
            f'stroke="#ffffff" stroke-width="2" filter="url(#pointShadow)"/>'
        )
        if p.get("label"):
            dx = p.get("dx", 12)
            dy = p.get("dy", -12)
            canv.add(
                f'<text x="{x+dx:.1f}" y="{y+dy:.1f}" font-size="11" '
                f'font-weight="600" fill="{INK}">{p["label"]}</text>'
            )
    return canv.finalize()


# ---------- utils -----------------------------------------------------------

def _darken(hex_color: str, amount: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r = max(0, int(r * (1 - amount)))
    g = max(0, int(g * (1 - amount)))
    b = max(0, int(b * (1 - amount)))
    return f"#{r:02x}{g:02x}{b:02x}"


def _lighten(hex_color: str, amount: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r = min(255, int(r + (255 - r) * amount))
    g = min(255, int(g + (255 - g) * amount))
    b = min(255, int(b + (255 - b) * amount))
    return f"#{r:02x}{g:02x}{b:02x}"
