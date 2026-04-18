"""
Build all result figures as standalone SVG files from the JSON data
in `results/`. No external dependencies — only the stdlib.

Run:
    python tools/build_figures.py
"""
from __future__ import annotations

import json
from pathlib import Path

from svg_plot import bar_plot, line_plot, time_series, PALETTE

ROOT = Path(__file__).resolve().parent.parent
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
    "static": "#7f8c8d",
    "reactive": "#95a5a6",
    "dt_only": "#3498db",
    "dt_qa": "#27ae60",
    "dt_trust": "#8e44ad",
    "full": "#c0392b",
}


# ---------- 1. Baseline bar chart (utility / rate / Pd) ---------------------
def fig_baseline():
    b = load("baseline_v2")
    if not b:
        return
    order = ["static", "reactive", "dt_only", "dt_qa", "dt_trust", "full"]
    groups = [METHOD_LABEL[m] for m in order]

    utility = [b[m]["utility_mean"] for m in order]
    rate_mbps = [b[m]["rate_bps_total_mean"] / 1e6 for m in order]
    pd = [b[m]["p_d_mean_mean"] for m in order]

    svg = bar_plot(
        groups,
        [
            {"name": "Utility (unitless)", "values": utility, "color": "#1f4e79"},
            {"name": "Detection P_d", "values": pd, "color": "#27ae60"},
            {"name": "Rate / 200 Mbps", "values": [r / 200 for r in rate_mbps],
             "color": "#c0392b"},
        ],
        title="Baseline comparison — Utility, Detection, Normalised Rate",
        y_label="Value",
    )
    (FIGS / "fig_baseline_bars.svg").write_text(svg)


# ---------- 2. Anomaly-rate sweep ------------------------------------------
def fig_anomaly_sweep():
    a = load("anomaly_sweep_v2")
    if not a:
        return
    cols = ["static", "dt_only", "dt_qa", "full"]
    rates = sorted(float(k) for k in a[cols[0]].keys())
    series = []
    for m in cols:
        series.append({
            "name": METHOD_LABEL[m],
            "color": METHOD_COLOR[m],
            "x": rates,
            "y": [a[m][str(r) if str(r) in a[m] else f"{r}"]["utility_mean"]
                  if str(r) in a[m] else a[m][f"{r}"]["utility_mean"]
                  for r in rates],
        })
    peak_full = max(series[-1]["y"])
    peak_idx = series[-1]["y"].index(peak_full)
    svg = line_plot(
        series,
        title="Utility vs. Anomaly-Injection Rate",
        x_label="Per-slot anomaly probability  p",
        y_label="Mean utility  (0–1)",
        annotations=[{"x": rates[peak_idx],
                      "y": peak_full,
                      "text": f"Full peak = {peak_full:.3f}"}],
    )
    (FIGS / "fig_anomaly_sweep.svg").write_text(svg)


# ---------- 3. Twin delay sweep --------------------------------------------
def fig_twin_delay():
    td = load("twin_delay")
    if not td:
        return
    cols = ["dt_only", "dt_qa", "full"]
    taus = sorted(int(k) for k in td[cols[0]].keys())
    series = []
    for m in cols:
        series.append({
            "name": METHOD_LABEL[m],
            "color": METHOD_COLOR[m],
            "x": taus,
            "y": [td[m][str(t)]["utility_mean"] for t in taus],
        })
    svg = line_plot(
        series,
        title="Robustness to Digital-Twin Synchronisation Delay",
        x_label="Synchronisation delay  τ  (slots)",
        y_label="Mean utility",
    )
    (FIGS / "fig_twin_delay.svg").write_text(svg)


# ---------- 4. Shortlist size ----------------------------------------------
def fig_shortlist_size():
    ss = load("shortlist_size")
    if not ss:
        return
    sizes = sorted(int(k) for k in ss.keys())
    utility = [ss[str(s)]["utility_mean"] for s in sizes]
    latency = [ss[str(s)]["latency_ms_mean"] for s in sizes]

    # two-axis style: plot utility on primary, latency scaled on same axis
    latency_scaled = [l / max(latency) * max(utility) for l in latency]
    svg = line_plot(
        [
            {"name": "Utility  (left scale)", "x": sizes, "y": utility,
             "color": "#1f4e79"},
            {"name": "Latency  (normalised)", "x": sizes, "y": latency_scaled,
             "color": "#c0392b", "dashed": True},
        ],
        title="Quantum-Assisted Shortlist Size  —  Utility vs. Latency",
        x_label="Shortlist size  M_s",
        y_label="Normalised value",
    )
    (FIGS / "fig_shortlist_size.svg").write_text(svg)


# ---------- 5. Trust transient ---------------------------------------------
def fig_trust_transient():
    tt = load("trust_transient")
    if not tt:
        return
    traces = []
    for m in ("full", "dt_only"):
        traces.append({
            "name": METHOD_LABEL[m],
            "color": METHOD_COLOR[m],
            "y": tt[m]["trust"],
        })
    svg = time_series(
        traces,
        title="Trust Recovery Transient  —  attack burst, slots 200–300",
        x_label="Slot index",
        y_label="Trust  T(t)",
        shaded_regions=[{"x0": 200, "x1": 300, "label": "attack burst"}],
        y_min_override=0.0, y_max_override=1.0,
    )
    (FIGS / "fig_trust_transient.svg").write_text(svg)


# ---------- 6. Scalability (users) -----------------------------------------
def fig_scalability_users():
    su = load("scalability_users")
    if not su:
        return
    methods = ["static", "dt_only", "full"]
    common = sorted(set.intersection(*[set(int(k) for k in su[m].keys())
                                       for m in methods]))
    series = []
    for m in methods:
        series.append({
            "name": METHOD_LABEL[m],
            "color": METHOD_COLOR[m],
            "x": common,
            "y": [su[m][str(u)]["utility_mean"] for u in common],
        })
    svg = line_plot(
        series,
        title="Scalability vs. Number of Users",
        x_label="Users  U",
        y_label="Mean utility",
    )
    (FIGS / "fig_scalability_users.svg").write_text(svg)


# ---------- 7. Scalability (targets) ---------------------------------------
def fig_scalability_targets():
    st = load("scalability_targets")
    if not st:
        return
    methods = ["static", "dt_only", "full"]
    Ks = sorted(int(k) for k in st["static"].keys())
    series = []
    for m in methods:
        series.append({
            "name": METHOD_LABEL[m],
            "color": METHOD_COLOR[m],
            "x": Ks,
            "y": [st[m][str(k)]["utility_mean"] for k in Ks],
        })
    svg = line_plot(
        series,
        title="Scalability vs. Number of Targets",
        x_label="Targets  K",
        y_label="Mean utility",
    )
    (FIGS / "fig_scalability_targets.svg").write_text(svg)


# ---------- 8. Pareto (energy vs utility) ----------------------------------
def fig_pareto():
    b = load("baseline_v2")
    if not b:
        return
    methods = ["static", "reactive", "dt_only", "dt_qa", "dt_trust", "full"]
    # represent each method as a single point (energy, utility)
    # plus reference points to trace the Pareto frontier-ish envelope
    pts = [(b[m]["energy_norm_mean"], b[m]["utility_mean"], m) for m in methods]
    # build a synthetic "frontier" by sorting
    pts_sorted = sorted(pts, key=lambda p: p[0])
    series = [{
        "name": "Method operating points",
        "x": [p[0] for p in pts_sorted],
        "y": [p[1] for p in pts_sorted],
        "color": "#1f4e79", "dashed": True,
    }]
    # annotate each point
    ann = [{"x": p[0], "y": p[1], "text": METHOD_LABEL[p[2]]} for p in pts_sorted]
    svg = line_plot(
        series,
        title="Energy–Utility Pareto View",
        x_label="Normalised energy  E / E_max",
        y_label="Mean utility",
        annotations=ann,
    )
    (FIGS / "fig_pareto.svg").write_text(svg)


if __name__ == "__main__":
    fig_baseline()
    fig_anomaly_sweep()
    fig_twin_delay()
    fig_shortlist_size()
    fig_trust_transient()
    fig_scalability_users()
    fig_scalability_targets()
    fig_pareto()
    print(f"Wrote {len(list(FIGS.glob('*.svg')))} SVG figures to {FIGS}")
