"""
Minimal pure-Python SVG plotting helpers (zero external dependencies).

The simulator in `src/` uses matplotlib for publication-grade figures
(see `tools/make_figures.py`). This module is a lightweight fallback so the
repository can ship ready-made figures even when matplotlib is not installed.

Every helper returns an SVG string. A small consistent visual style is applied
across all plots so the generated assets look like a coherent figure set.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence


# -------- style -------------------------------------------------------------

PALETTE = [
    "#1f4e79",  # deep blue
    "#c0392b",  # crimson
    "#27ae60",  # emerald
    "#8e44ad",  # purple
    "#e67e22",  # orange
    "#16a085",  # teal
    "#7f8c8d",  # slate
]

GRID_COLOR = "#e5e7eb"
AXIS_COLOR = "#1f2937"
TEXT_COLOR = "#111827"
BG_COLOR = "#ffffff"
FONT = "'Inter','Segoe UI','Helvetica Neue',Arial,sans-serif"


@dataclass
class Axes:
    x0: float = 80.0
    y0: float = 60.0
    w: float = 720.0
    h: float = 420.0
    x_min: float = 0.0
    x_max: float = 1.0
    y_min: float = 0.0
    y_max: float = 1.0

    def sx(self, x: float) -> float:
        if self.x_max == self.x_min:
            return self.x0
        return self.x0 + (x - self.x_min) / (self.x_max - self.x_min) * self.w

    def sy(self, y: float) -> float:
        if self.y_max == self.y_min:
            return self.y0 + self.h
        return self.y0 + self.h - (y - self.y_min) / (self.y_max - self.y_min) * self.h


def _nice_ticks(lo: float, hi: float, n: int = 5) -> list[float]:
    if hi <= lo:
        return [lo]
    span = hi - lo
    import math
    raw = span / n
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


def _fmt(v: float) -> str:
    if abs(v) >= 1e6:
        return f"{v/1e6:.1f}M"
    if abs(v) >= 1e3:
        return f"{v/1e3:.0f}k"
    if abs(v) < 1 and v != 0:
        return f"{v:.2f}"
    if v == int(v):
        return f"{int(v)}"
    return f"{v:.2f}"


def _svg_open(width: int, height: int, title: str = "") -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" font-family="{FONT}" '
        f'font-size="14" role="img" aria-label="{title}">\n'
        f'<rect width="100%" height="100%" fill="{BG_COLOR}"/>\n'
    )


def _title(text: str, x: float, y: float, size: int = 18, weight: str = "700") -> str:
    return (
        f'<text x="{x}" y="{y}" text-anchor="middle" '
        f'font-size="{size}" font-weight="{weight}" fill="{TEXT_COLOR}">{text}</text>\n'
    )


def _axes_frame(ax: Axes, x_label: str, y_label: str,
                x_ticks: Sequence[float], y_ticks: Sequence[float],
                x_tick_labels: Sequence[str] | None = None,
                y_tick_labels: Sequence[str] | None = None) -> str:
    out = []
    # panel background
    out.append(
        f'<rect x="{ax.x0}" y="{ax.y0}" width="{ax.w}" height="{ax.h}" '
        f'fill="#fbfcfe" stroke="{AXIS_COLOR}" stroke-width="1.2"/>\n'
    )
    # horizontal grid
    y_labels = y_tick_labels if y_tick_labels is not None else [_fmt(v) for v in y_ticks]
    for yt, lbl in zip(y_ticks, y_labels):
        y = ax.sy(yt)
        out.append(
            f'<line x1="{ax.x0}" y1="{y:.1f}" x2="{ax.x0+ax.w}" y2="{y:.1f}" '
            f'stroke="{GRID_COLOR}" stroke-width="1"/>\n'
        )
        out.append(
            f'<text x="{ax.x0-8}" y="{y+4:.1f}" text-anchor="end" '
            f'fill="{TEXT_COLOR}" font-size="12">{lbl}</text>\n'
        )
    # vertical grid
    x_labels = x_tick_labels if x_tick_labels is not None else [_fmt(v) for v in x_ticks]
    for xt, lbl in zip(x_ticks, x_labels):
        x = ax.sx(xt)
        out.append(
            f'<line x1="{x:.1f}" y1="{ax.y0}" x2="{x:.1f}" y2="{ax.y0+ax.h}" '
            f'stroke="{GRID_COLOR}" stroke-width="1"/>\n'
        )
        out.append(
            f'<text x="{x:.1f}" y="{ax.y0+ax.h+18}" text-anchor="middle" '
            f'fill="{TEXT_COLOR}" font-size="12">{lbl}</text>\n'
        )
    # axis labels
    out.append(
        f'<text x="{ax.x0+ax.w/2}" y="{ax.y0+ax.h+42}" text-anchor="middle" '
        f'fill="{TEXT_COLOR}" font-size="13" font-weight="600">{x_label}</text>\n'
    )
    out.append(
        f'<text transform="translate({ax.x0-52},{ax.y0+ax.h/2}) rotate(-90)" '
        f'text-anchor="middle" fill="{TEXT_COLOR}" font-size="13" '
        f'font-weight="600">{y_label}</text>\n'
    )
    return "".join(out)


def _legend(items: Sequence[tuple[str, str]], x: float, y: float) -> str:
    out = []
    for i, (label, color) in enumerate(items):
        ly = y + i * 22
        out.append(
            f'<rect x="{x}" y="{ly-10}" width="22" height="4" fill="{color}" rx="2"/>\n'
            f'<circle cx="{x+11}" cy="{ly-8}" r="4" fill="{color}"/>\n'
            f'<text x="{x+32}" y="{ly-4}" fill="{TEXT_COLOR}" font-size="12">{label}</text>\n'
        )
    return "".join(out)


# ---- public plot builders --------------------------------------------------

def line_plot(
    series: list[dict],
    *,
    title: str,
    x_label: str,
    y_label: str,
    width: int = 880,
    height: int = 520,
    x_log: bool = False,
    y_min_override: float | None = None,
    y_max_override: float | None = None,
    annotations: list[dict] | None = None,
    shaded_regions: list[dict] | None = None,
) -> str:
    """series: list of {name, x, y, color?, dashed?}."""
    import math
    xs_all: list[float] = []
    ys_all: list[float] = []
    for s in series:
        xs_all.extend(s["x"])
        ys_all.extend(s["y"])

    if x_log:
        x_min = min(xs_all)
        x_max = max(xs_all)
        x_tr = math.log10
    else:
        x_min = min(xs_all)
        x_max = max(xs_all)
        x_tr = lambda v: v
    y_min = y_min_override if y_min_override is not None else min(ys_all)
    y_max = y_max_override if y_max_override is not None else max(ys_all)
    span = y_max - y_min
    y_min -= 0.06 * span
    y_max += 0.08 * span

    ax = Axes(
        x0=90, y0=70, w=width-210, h=height-140,
        x_min=x_tr(x_min), x_max=x_tr(x_max), y_min=y_min, y_max=y_max,
    )

    out = [_svg_open(width, height, title)]
    out.append(_title(title, width/2, 30))

    if x_log:
        raw_ticks = _nice_ticks(math.log10(x_min), math.log10(x_max), 5)
        x_ticks_pos = raw_ticks
        x_tick_labels = [_fmt(10**t) for t in raw_ticks]
    else:
        x_ticks_pos = _nice_ticks(x_min, x_max, 6)
        x_tick_labels = [_fmt(v) for v in x_ticks_pos]

    y_ticks = _nice_ticks(y_min, y_max, 6)
    out.append(_axes_frame(ax, x_label, y_label, x_ticks_pos, y_ticks, x_tick_labels))

    # shaded regions
    if shaded_regions:
        for reg in shaded_regions:
            x0 = ax.sx(x_tr(reg["x0"]))
            x1 = ax.sx(x_tr(reg["x1"]))
            color = reg.get("color", "#fde2e4")
            label = reg.get("label", "")
            out.append(
                f'<rect x="{x0:.1f}" y="{ax.y0}" width="{x1-x0:.1f}" height="{ax.h}" '
                f'fill="{color}" opacity="0.55"/>\n'
            )
            if label:
                out.append(
                    f'<text x="{(x0+x1)/2:.1f}" y="{ax.y0+14}" text-anchor="middle" '
                    f'fill="#7f1d1d" font-size="12" font-weight="700">{label}</text>\n'
                )

    # series lines
    for i, s in enumerate(series):
        color = s.get("color", PALETTE[i % len(PALETTE)])
        dashed = s.get("dashed", False)
        pts = " ".join(
            f"{ax.sx(x_tr(x)):.1f},{ax.sy(y):.1f}"
            for x, y in zip(s["x"], s["y"])
        )
        dash_attr = 'stroke-dasharray="6,4"' if dashed else ""
        out.append(
            f'<polyline points="{pts}" fill="none" stroke="{color}" '
            f'stroke-width="2.5" {dash_attr}/>\n'
        )
        for x, y in zip(s["x"], s["y"]):
            out.append(
                f'<circle cx="{ax.sx(x_tr(x)):.1f}" cy="{ax.sy(y):.1f}" r="3.5" '
                f'fill="#ffffff" stroke="{color}" stroke-width="2"/>\n'
            )

    # legend
    legend_items = [(s["name"], s.get("color", PALETTE[i % len(PALETTE)]))
                    for i, s in enumerate(series)]
    out.append(_legend(legend_items, ax.x0 + ax.w + 24, ax.y0 + 16))

    # annotations
    if annotations:
        for a in annotations:
            x = ax.sx(x_tr(a["x"]))
            y = ax.sy(a["y"])
            out.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="none" '
                f'stroke="#111827" stroke-width="1.5"/>\n'
                f'<text x="{x+10:.1f}" y="{y-10:.1f}" fill="#111827" '
                f'font-size="12" font-weight="600">{a["text"]}</text>\n'
            )

    out.append("</svg>\n")
    return "".join(out)


def bar_plot(
    groups: list[str],
    series: list[dict],
    *,
    title: str,
    y_label: str,
    width: int = 880,
    height: int = 520,
    value_labels: bool = True,
) -> str:
    """Grouped bar plot. series: list of {name, values (aligned to groups), color?}."""
    n_groups = len(groups)
    n_series = len(series)
    ys_all = [v for s in series for v in s["values"]]
    y_min = min(0, min(ys_all))
    y_max = max(ys_all)
    y_max *= 1.18

    ax = Axes(x0=90, y0=70, w=width-210, h=height-140, y_min=y_min, y_max=y_max)

    out = [_svg_open(width, height, title)]
    out.append(_title(title, width/2, 30))

    # axis frame (x-ticks will be group centres)
    group_w = ax.w / n_groups
    bar_gap = group_w * 0.12
    bar_w = (group_w - bar_gap) / n_series
    x_tick_pos = [i + 0.5 for i in range(n_groups)]
    ax.x_min = 0
    ax.x_max = n_groups

    y_ticks = _nice_ticks(y_min, y_max, 6)
    out.append(_axes_frame(ax, "", y_label, x_tick_pos, y_ticks, groups))

    for i, s in enumerate(series):
        color = s.get("color", PALETTE[i % len(PALETTE)])
        for g, v in enumerate(s["values"]):
            xs = ax.x0 + g * group_w + bar_gap/2 + i * bar_w
            ys = ax.sy(v)
            h = ax.sy(y_min) - ys
            out.append(
                f'<rect x="{xs:.1f}" y="{ys:.1f}" width="{bar_w-2:.1f}" height="{h:.1f}" '
                f'fill="{color}" rx="2"/>\n'
            )
            if value_labels:
                out.append(
                    f'<text x="{xs + (bar_w-2)/2:.1f}" y="{ys-4:.1f}" '
                    f'text-anchor="middle" fill="{TEXT_COLOR}" font-size="11" '
                    f'font-weight="600">{_fmt(v)}</text>\n'
                )

    legend_items = [(s["name"], s.get("color", PALETTE[i % len(PALETTE)]))
                    for i, s in enumerate(series)]
    out.append(_legend(legend_items, ax.x0 + ax.w + 24, ax.y0 + 16))
    out.append("</svg>\n")
    return "".join(out)


def time_series(
    traces: list[dict],
    *,
    title: str,
    x_label: str,
    y_label: str,
    width: int = 960,
    height: int = 460,
    shaded_regions: list[dict] | None = None,
    y_min_override: float | None = None,
    y_max_override: float | None = None,
) -> str:
    """Time-series with many samples. traces: list of {name, y, color?}."""
    n = max(len(t["y"]) for t in traces)
    ys_all = [v for t in traces for v in t["y"]]
    y_min = y_min_override if y_min_override is not None else min(ys_all)
    y_max = y_max_override if y_max_override is not None else max(ys_all)
    span = y_max - y_min
    y_min -= 0.05 * span
    y_max += 0.08 * span

    ax = Axes(x0=90, y0=70, w=width-210, h=height-140,
              x_min=0, x_max=n-1, y_min=y_min, y_max=y_max)

    out = [_svg_open(width, height, title)]
    out.append(_title(title, width/2, 30))

    x_ticks = _nice_ticks(0, n-1, 8)
    y_ticks = _nice_ticks(y_min, y_max, 6)
    out.append(_axes_frame(ax, x_label, y_label, x_ticks, y_ticks))

    if shaded_regions:
        for reg in shaded_regions:
            x0 = ax.sx(reg["x0"])
            x1 = ax.sx(reg["x1"])
            color = reg.get("color", "#fde2e4")
            label = reg.get("label", "")
            out.append(
                f'<rect x="{x0:.1f}" y="{ax.y0}" width="{x1-x0:.1f}" height="{ax.h}" '
                f'fill="{color}" opacity="0.6"/>\n'
            )
            if label:
                out.append(
                    f'<text x="{(x0+x1)/2:.1f}" y="{ax.y0+16}" text-anchor="middle" '
                    f'fill="#7f1d1d" font-size="12" font-weight="700">{label}</text>\n'
                )

    for i, t in enumerate(traces):
        color = t.get("color", PALETTE[i % len(PALETTE)])
        pts = " ".join(
            f"{ax.sx(k):.1f},{ax.sy(v):.1f}"
            for k, v in enumerate(t["y"])
        )
        out.append(
            f'<polyline points="{pts}" fill="none" stroke="{color}" '
            f'stroke-width="2" opacity="0.95"/>\n'
        )

    legend_items = [(t["name"], t.get("color", PALETTE[i % len(PALETTE)]))
                    for i, t in enumerate(traces)]
    out.append(_legend(legend_items, ax.x0 + ax.w + 24, ax.y0 + 16))
    out.append("</svg>\n")
    return "".join(out)
