"""
Publication-grade figure generator (matplotlib).

Produces PNG + PDF versions of every figure in `figures/` from the JSON data
in `results/`. Intended for users who have matplotlib installed; see
`tools/build_figures.py` for a zero-dependency SVG fallback that ships with
the repository.

Run:
    python tools/make_figures.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib as mpl
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
FIGS = ROOT / "figures"
FIGS.mkdir(exist_ok=True)

mpl.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 12,
    "axes.titlesize": 14,
    "axes.titleweight": "bold",
    "axes.labelsize": 12,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.color": "#e5e7eb",
    "grid.linewidth": 0.8,
    "legend.frameon": False,
    "savefig.bbox": "tight",
    "savefig.dpi": 160,
})

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


def load(name):
    p = RESULTS / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else None


def _wall_clock_ms(entry):
    return entry.get("simulator_wall_clock_ms_mean",
                     entry.get("latency_ms_mean", 0.0))


def save(fig, name):
    for ext in ("png", "pdf"):
        fig.savefig(FIGS / f"{name}.{ext}")
    plt.close(fig)


def fig_baseline():
    b = load("baseline_v2")
    if not b:
        return
    order = ["static", "reactive", "dt_only", "dt_qa", "dt_trust", "full"]
    labels = [METHOD_LABEL[m] for m in order]
    utility = [b[m]["utility_mean"] for m in order]
    stds = [b[m]["utility_std"] for m in order]
    colors = [METHOD_COLOR[m] for m in order]

    fig, ax = plt.subplots(figsize=(9, 4.8))
    x = np.arange(len(order))
    ax.bar(x, utility, yerr=stds, color=colors, capsize=4, edgecolor="black",
           linewidth=0.7)
    for xi, ui in zip(x, utility):
        ax.text(xi, ui + 0.02, f"{ui:.3f}", ha="center", fontsize=10,
                fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=15, ha="right")
    ax.set_ylabel("Mean utility")
    # Active-trust markers (asterisk on bars whose trust_semantics is
    # nominal_default). See docs/PAPER_CODE_ALIGNMENT_AUDIT.md §2.
    for xi, m in zip(x, order):
        if b[m].get("trust_semantics") == "nominal_default":
            ax.text(xi, 0.02, "*", ha="center", fontsize=14, color="#111827",
                    fontweight="bold")
    full_gain = (b["full"]["utility_mean"] - b["dt_qa"]["utility_mean"]) \
                 / b["dt_qa"]["utility_mean"] * 100
    ax.set_title(f"Baseline comparison  —  Full vs. strongest baseline (DT+QA): "
                 f"+{full_gain:.1f}%")
    ax.set_ylim(0, max(utility) * 1.18)
    fig.text(0.01, 0.01,
             "*  trust value is a nominal default, not an active Bayesian-EWMA posterior",
             fontsize=8, color="#374151")
    save(fig, "fig_baseline_bars")


def fig_anomaly():
    a = load("anomaly_sweep_v2")
    if not a:
        return
    cols = ["static", "dt_only", "dt_qa", "full"]
    rates = sorted(float(k) for k in a[cols[0]].keys())
    fig, ax = plt.subplots(figsize=(9, 4.8))
    for m in cols:
        ys = [a[m][str(r)]["utility_mean"] for r in rates]
        ax.plot(rates, ys, "-o", color=METHOD_COLOR[m], label=METHOD_LABEL[m],
                linewidth=2.2, markersize=6)
    ax.set_xlabel("Per-slot anomaly probability  p")
    ax.set_ylabel("Mean utility")
    ax.set_title("Utility vs. Anomaly Rate")
    ax.legend(loc="lower left")
    save(fig, "fig_anomaly_sweep")


def fig_twin_delay():
    td = load("twin_delay")
    if not td:
        return
    cols = ["dt_only", "dt_qa", "full"]
    taus = sorted(int(k) for k in td[cols[0]].keys())
    fig, ax = plt.subplots(figsize=(9, 4.8))
    for m in cols:
        ys = [td[m][str(t)]["utility_mean"] for t in taus]
        ax.plot(taus, ys, "-o", color=METHOD_COLOR[m], label=METHOD_LABEL[m],
                linewidth=2.2, markersize=6)
    ax.set_xlabel("Synchronisation delay τ (slots)")
    ax.set_ylabel("Mean utility")
    ax.set_title("Robustness to Twin Synchronisation Delay")
    ax.legend()
    save(fig, "fig_twin_delay")


def fig_shortlist():
    ss = load("shortlist_size")
    if not ss:
        return
    sizes = sorted(int(k) for k in ss.keys())
    utility = [ss[str(s)]["utility_mean"] for s in sizes]
    latency = [_wall_clock_ms(ss[str(s)]) for s in sizes]
    fig, ax1 = plt.subplots(figsize=(9, 4.8))
    ax1.plot(sizes, utility, "-o", color="#1f4e79", label="Utility", linewidth=2.2)
    ax1.set_xlabel("Shortlist size M_s")
    ax1.set_ylabel("Utility", color="#1f4e79")
    ax1.tick_params(axis="y", labelcolor="#1f4e79")

    ax2 = ax1.twinx()
    ax2.plot(sizes, latency, "--s", color="#c0392b",
             label="Simulator wall-clock (ms)", linewidth=2.0)
    ax2.set_ylabel("Simulator wall-clock (ms)", color="#c0392b")
    ax2.tick_params(axis="y", labelcolor="#c0392b")
    ax2.grid(False)
    ax1.set_title("Quantum-Assisted Shortlist Size Sensitivity  "
                  "(utility plateaus near M_s ≈ 10–20)")
    save(fig, "fig_shortlist_size")


def fig_trust_transient():
    tt = load("trust_transient")
    if not tt:
        return
    fig, ax = plt.subplots(figsize=(10, 4.6))
    for m in ("full", "dt_only"):
        ax.plot(tt[m]["trust"], color=METHOD_COLOR[m], label=METHOD_LABEL[m],
                linewidth=2)
    ax.axvspan(200, 300, color="#fde2e4", alpha=0.7, label="attack burst")
    ax.axhline(0.30, color="#c0392b", linestyle=":", linewidth=1,
               label="T_safe = 0.30")
    ax.set_xlabel("Slot index")
    ax.set_ylabel("Trust T(t)")
    ax.set_ylim(0, 1.05)
    ax.set_title("Trust Recovery Transient (500 slots)")
    ax.legend(loc="lower right")
    save(fig, "fig_trust_transient")


def fig_scalability_users():
    su = load("scalability_users")
    if not su:
        return
    methods = ["static", "dt_only", "full"]
    common = sorted(set.intersection(*[set(int(k) for k in su[m].keys())
                                       for m in methods]))
    fig, ax = plt.subplots(figsize=(9, 4.8))
    for m in methods:
        ys = [su[m][str(u)]["utility_mean"] for u in common]
        ax.plot(common, ys, "-o", color=METHOD_COLOR[m], label=METHOD_LABEL[m],
                linewidth=2.2)
    ax.set_xlabel("Number of users U")
    ax.set_ylabel("Mean utility")
    ax.set_title("Scalability vs. Users")
    ax.legend()
    save(fig, "fig_scalability_users")


def fig_scalability_targets():
    st = load("scalability_targets")
    if not st:
        return
    methods = ["static", "dt_only", "full"]
    Ks = sorted(int(k) for k in st["static"].keys())
    fig, ax = plt.subplots(figsize=(9, 4.8))
    for m in methods:
        ys = [st[m][str(k)]["utility_mean"] for k in Ks]
        ax.plot(Ks, ys, "-o", color=METHOD_COLOR[m], label=METHOD_LABEL[m],
                linewidth=2.2)
    ax.set_xlabel("Number of targets K")
    ax.set_ylabel("Mean utility")
    ax.set_title("Scalability vs. Targets")
    ax.legend()
    save(fig, "fig_scalability_targets")


def fig_pareto():
    b = load("baseline_v2")
    if not b:
        return
    methods = ["static", "reactive", "dt_only", "dt_qa", "dt_trust", "full"]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    for m in methods:
        ax.scatter(b[m]["energy_norm_mean"], b[m]["utility_mean"],
                   s=150, color=METHOD_COLOR[m], edgecolor="black",
                   label=METHOD_LABEL[m], zorder=3)
        ax.annotate(METHOD_LABEL[m],
                    (b[m]["energy_norm_mean"], b[m]["utility_mean"]),
                    xytext=(6, 6), textcoords="offset points", fontsize=10)
    ax.set_xlabel("Normalised energy E / E_max")
    ax.set_ylabel("Mean utility")
    ax.set_title("Energy–Utility Pareto View")
    ax.legend(loc="lower left", fontsize=10)
    save(fig, "fig_pareto")


if __name__ == "__main__":
    fig_baseline()
    fig_anomaly()
    fig_twin_delay()
    fig_shortlist()
    fig_trust_transient()
    fig_scalability_users()
    fig_scalability_targets()
    fig_pareto()
    n = len(list(FIGS.glob("*.png")))
    print(f"Wrote {n} PNG/PDF figure pairs to {FIGS}")
