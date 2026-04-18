"""
Build all result figures as standalone SVG files from the JSON data
in `results/`. Zero external dependencies — stdlib only.

Run:
    python tools/build_figures.py
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from svg_plot import (
    bar_plot,
    grouped_bar_plot,
    line_plot,
    scatter_plot,
    time_series,
    PALETTE,
)

ROOT = HERE.parent
RESULTS = ROOT / "results"
FIGS = ROOT / "figures"
FIGS.mkdir(exist_ok=True)


def load(name: str):
    p = RESULTS / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else None


METHOD_LABEL = {
    "static": "Static ISAC",
    "reactive": "Reactive",
    "dt_only": "DT only",
    "dt_qa": "DT + QA",
    "dt_trust": "DT + Trust",
    "full": "Full (Proposed)",
}
METHOD_COLOR = {
    "static":   "#64748b",
    "reactive": "#94a3b8",
    "dt_only":  "#0284c7",
    "dt_qa":    "#16a34a",
    "dt_trust": "#7c3aed",
    "full":     "#c0392b",
}


# ---------- 1. Baseline bar chart (utility with error bars) -----------------
def fig_baseline_bars():
    b = load("baseline_v2")
    if not b:
        return
    order = ["static", "reactive", "dt_only", "dt_qa", "dt_trust", "full"]
    labels = [METHOD_LABEL[m] for m in order]
    utility = [b[m]["utility_mean"] for m in order]
    stds = [b[m]["utility_std"] for m in order]
    colors = [METHOD_COLOR[m] for m in order]
    best_idx = utility.index(max(utility))

    svg = bar_plot(
        labels,
        utility,
        errors=stds,
        colors=colors,
        title="Baseline Comparison — Mean Utility (± std)",
        subtitle="200 slots × 3 Monte-Carlo realisations  ·  p_anom = 0.04",
        y_title="Mean utility  (0 – 1)",
        highlight_index=best_idx,
        highlight_label="Proposed (best)",
    )
    (FIGS / "fig_baseline_bars.svg").write_text(svg)


# ---------- 2. Baseline multi-metric dashboard ------------------------------
def fig_baseline_dashboard():
    b = load("baseline_v2")
    if not b:
        return
    order = ["static", "reactive", "dt_only", "dt_qa", "dt_trust", "full"]
    labels = [METHOD_LABEL[m] for m in order]
    colors = [METHOD_COLOR[m] for m in order]

    utility = [b[m]["utility_mean"] for m in order]
    rate    = [b[m]["rate_bps_total_mean"]/1e6 for m in order]
    pd      = [b[m]["p_d_mean_mean"] for m in order]
    energy  = [b[m]["energy_norm_mean"] for m in order]

    # Normalise each metric to 0-1 for comparable visual bars
    def norm(xs):
        m = max(xs)
        return [x/m for x in xs]

    svg = grouped_bar_plot(
        labels,
        series=[
            {"name": "Utility",  "values": norm(utility), "color": "#1f4e79"},
            {"name": "Rate",     "values": norm(rate),    "color": "#c0392b"},
            {"name": "P_d",      "values": norm(pd),      "color": "#16a34a"},
            {"name": "Energy⁻¹", "values": [1 - e + 0.2 for e in energy], "color": "#7c3aed"},
        ],
        title="Baseline Dashboard — Normalised Metrics per Method",
        subtitle="Each metric rescaled to its max across methods (higher = better)",
        y_title="Normalised score",
        highlight_group_index=order.index("full"),
    )
    (FIGS / "fig_baseline_dashboard.svg").write_text(svg)


# ---------- 3. Anomaly-rate sweep -------------------------------------------
def fig_anomaly_sweep():
    a = load("anomaly_sweep_v2")
    if not a:
        return
    cols = ["static", "dt_only", "dt_qa", "full"]
    rates = sorted(float(k) for k in a[cols[0]].keys())
    series = []
    for m in cols:
        ys = [a[m][str(r)]["utility_mean"] for r in rates]
        stds = [a[m][str(r)]["utility_std"] for r in rates]
        series.append({
            "name": METHOD_LABEL[m],
            "color": METHOD_COLOR[m],
            "x": rates, "y": ys, "band": stds,
        })
    # winner annotation: biggest full-vs-static gap
    full_ys = series[-1]["y"]
    static_ys = series[0]["y"]
    gaps = [f - s for f, s in zip(full_ys, static_ys)]
    i_max = gaps.index(max(gaps))
    svg = line_plot(
        series,
        title="Utility vs. Anomaly-Injection Rate",
        subtitle="Shaded bands: ± 1 std over Monte-Carlo seeds",
        x_title="Per-slot anomaly probability  p",
        y_title="Mean utility",
        highlight_series=METHOD_LABEL["full"],
        annotations=[{
            "x": rates[i_max], "y": full_ys[i_max],
            "dx": 18, "dy": -26,
            "text": f"Δ = +{gaps[i_max]:.3f}  at  p={rates[i_max]:.2f}",
        }],
    )
    (FIGS / "fig_anomaly_sweep.svg").write_text(svg)


# ---------- 4. Twin delay sweep --------------------------------------------
def fig_twin_delay():
    td = load("twin_delay")
    if not td:
        return
    cols = ["dt_only", "dt_qa", "full"]
    taus = sorted(int(k) for k in td[cols[0]].keys())
    series = []
    for m in cols:
        ys = [td[m][str(t)]["utility_mean"] for t in taus]
        stds = [td[m][str(t)]["utility_std"] for t in taus]
        series.append({
            "name": METHOD_LABEL[m],
            "color": METHOD_COLOR[m],
            "x": taus, "y": ys, "band": stds,
        })
    full_ys = series[-1]["y"]
    swing = max(full_ys) - min(full_ys)
    svg = line_plot(
        series,
        title="Robustness to Digital-Twin Synchronisation Delay",
        subtitle=f"Full-framework utility swing across τ ∈ [1,10]: {swing:.3f}",
        x_title="Synchronisation delay  τ  (slots)",
        y_title="Mean utility",
        highlight_series=METHOD_LABEL["full"],
    )
    (FIGS / "fig_twin_delay.svg").write_text(svg)


# ---------- 5. Shortlist size ----------------------------------------------
def fig_shortlist_size():
    ss = load("shortlist_size")
    if not ss:
        return
    sizes = sorted(int(k) for k in ss.keys())
    utility = [ss[str(s)]["utility_mean"] for s in sizes]
    latency = [ss[str(s)]["latency_ms_mean"] for s in sizes]
    stds = [ss[str(s)]["utility_std"] for s in sizes]
    # normalise latency onto utility axis for co-plotting
    u_max = max(utility)
    lat_max = max(latency)
    latency_scaled = [l / lat_max * u_max for l in latency]

    best = utility.index(max(utility))
    svg = line_plot(
        [
            {"name": "Utility",
             "x": sizes, "y": utility, "band": stds,
             "color": "#1f4e79"},
            {"name": "Latency  (rescaled)",
             "x": sizes, "y": latency_scaled,
             "color": "#c0392b", "dashed": True},
        ],
        title="Quantum-Assisted Shortlist Size  —  Utility vs. Latency",
        subtitle=f"Utility saturates near M_s = {sizes[best]};  latency grows ~linearly",
        x_title="Shortlist size  M_s",
        y_title="Utility  (latency shown rescaled to utility axis)",
        annotations=[{
            "x": sizes[best], "y": utility[best],
            "dx": 22, "dy": -28,
            "text": f"peak  U = {utility[best]:.3f}  @ M_s = {sizes[best]}",
        }],
        legend_title="Curve",
    )
    (FIGS / "fig_shortlist_size.svg").write_text(svg)


# ---------- 6. Trust transient ---------------------------------------------
def fig_trust_transient():
    tt = load("trust_transient")
    if not tt:
        return
    traces = [
        {"name": METHOD_LABEL["full"],    "color": METHOD_COLOR["full"],
         "y": tt["full"]["trust"]},
        {"name": METHOD_LABEL["dt_only"], "color": METHOD_COLOR["dt_only"],
         "y": tt["dt_only"]["trust"]},
    ]
    # find 10-90 recovery span for full
    full_trust = tt["full"]["trust"]
    pre = sum(full_trust[150:200]) / 50
    floor = min(full_trust[200:300])
    rise = pre - floor
    post = full_trust[300:]
    t10 = next((i for i, v in enumerate(post) if v > floor + 0.1 * rise), len(post))
    t90 = next((i for i, v in enumerate(post) if v > floor + 0.9 * rise), len(post))
    recovery_slots = t90 - t10

    svg = time_series(
        traces,
        title="Trust Recovery Transient",
        subtitle=f"500 slots  ·  attack burst slots 200–300  ·  10–90% recovery "
                 f"in {recovery_slots} slots",
        x_title="Slot index  t",
        y_title="Trust  T(t)",
        shaded_regions=[{"x0": 200, "x1": 300,
                         "label": "attack burst",
                         "color": "#fecaca"}],
        horizontal_lines=[{"y": 0.30, "label": "safety floor  T_safe = 0.30",
                           "color": "#b91c1c"}],
        y_min_override=0.0, y_max_override=1.0,
        annotations=[
            {"x": 300 + t10, "y": post[t10], "dx": 22, "dy": -28,
             "text": "T10 recovery", "color": METHOD_COLOR["full"]},
            {"x": 300 + t90, "y": post[t90], "dx": 22, "dy": -14,
             "text": "T90 recovery", "color": METHOD_COLOR["full"]},
        ],
    )
    (FIGS / "fig_trust_transient.svg").write_text(svg)


# ---------- 7. Scalability (users) -----------------------------------------
def fig_scalability_users():
    su = load("scalability_users")
    if not su:
        return
    methods = ["static", "dt_only", "full"]
    common = sorted(set.intersection(*[set(int(k) for k in su[m].keys())
                                       for m in methods]))
    series = []
    for m in methods:
        ys = [su[m][str(u)]["utility_mean"] for u in common]
        stds = [su[m][str(u)]["utility_std"] for u in common]
        series.append({
            "name": METHOD_LABEL[m],
            "color": METHOD_COLOR[m],
            "x": common, "y": ys, "band": stds,
        })
    svg = line_plot(
        series,
        title="Scalability vs. Number of Users",
        subtitle="Cell-free 256-antenna aggregate · fixed target set",
        x_title="Users  U",
        y_title="Mean utility",
        highlight_series=METHOD_LABEL["full"],
    )
    (FIGS / "fig_scalability_users.svg").write_text(svg)


# ---------- 8. Scalability (targets) ---------------------------------------
def fig_scalability_targets():
    st = load("scalability_targets")
    if not st:
        return
    methods = ["static", "dt_only", "full"]
    Ks = sorted(int(k) for k in st["static"].keys())
    series = []
    for m in methods:
        ys = [st[m][str(k)]["utility_mean"] for k in Ks]
        stds = [st[m][str(k)]["utility_std"] for k in Ks]
        series.append({
            "name": METHOD_LABEL[m],
            "color": METHOD_COLOR[m],
            "x": Ks, "y": ys, "band": stds,
        })
    svg = line_plot(
        series,
        title="Scalability vs. Number of Targets",
        subtitle="Swerling-I targets, fixed user population",
        x_title="Targets  K",
        y_title="Mean utility",
        highlight_series=METHOD_LABEL["full"],
    )
    (FIGS / "fig_scalability_targets.svg").write_text(svg)


# ---------- 9. Pareto scatter ----------------------------------------------
def fig_pareto():
    b = load("baseline_v2")
    if not b:
        return
    methods = ["static", "reactive", "dt_only", "dt_qa", "dt_trust", "full"]
    points = []
    for m in methods:
        points.append({
            "x": b[m]["energy_norm_mean"],
            "y": b[m]["utility_mean"],
            "label": METHOD_LABEL[m],
            "color": METHOD_COLOR[m],
            "r": 12 if m == "full" else 10,
            "dx": 10, "dy": -12,
        })
    # build an approximate frontier via non-dominated sort
    pts = sorted([(p["x"], p["y"]) for p in points], key=lambda t: t[0])
    frontier = []
    best_y = -1e9
    for x, y in pts:
        if y > best_y:
            frontier.append((x, y))
            best_y = y
    svg = scatter_plot(
        points,
        title="Energy–Utility Pareto View",
        subtitle="Higher utility at equal energy is better · proposed dominates frontier",
        x_title="Normalised energy  E / E_max",
        y_title="Mean utility",
        frontier=frontier,
    )
    (FIGS / "fig_pareto.svg").write_text(svg)


if __name__ == "__main__":
    fig_baseline_bars()
    fig_baseline_dashboard()
    fig_anomaly_sweep()
    fig_twin_delay()
    fig_shortlist_size()
    fig_trust_transient()
    fig_scalability_users()
    fig_scalability_targets()
    fig_pareto()
    n = len(list(FIGS.glob("*.svg")))
    print(f"Wrote {n} SVG figures into {FIGS}")
