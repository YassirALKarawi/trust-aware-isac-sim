"""
Baseline comparison runner.
Runs all five methods on identical traces and aggregates results.
"""
import numpy as np
import json
import time
from pathlib import Path

from config import SimConfig
from controller import ISACController, BASELINE_FLAGS


def run_method(cfg: SimConfig, method_name: str, seed: int, n_slots: int) -> dict:
    """Run one method on one MC realisation with a specific master seed."""
    rng = np.random.default_rng(seed)
    flags = BASELINE_FLAGS[method_name]
    ctrl = ISACController(cfg, flags, rng, tag=method_name)
    hist = ctrl.run(n_slots, verbose=False)
    return {
        "method": method_name,
        "seed": seed,
        "utility":       [m.utility for m in hist],
        "rate_bps_mean": [m.rate_bps_mean for m in hist],
        "rate_bps_total":[m.rate_bps_total for m in hist],
        "p_d_mean":      [m.p_d_mean for m in hist],
        "trust":         [m.trust for m in hist],
        "eps_dt":        [m.eps_dt for m in hist],
        "energy_norm":   [m.energy_norm for m in hist],
        "accuracy_mean": [m.accuracy_mean for m in hist],
        "latency_ms":    [m.control_latency_ms for m in hist],
    }


def aggregate(results: list, burn_in: int = 50) -> dict:
    """Aggregate per-method results over MC runs, discarding a burn-in period."""
    summary = {}
    by_method = {}
    for r in results:
        by_method.setdefault(r["method"], []).append(r)
    for method, runs in by_method.items():
        means = {}
        for key in ["utility", "rate_bps_mean", "rate_bps_total", "p_d_mean",
                   "trust", "eps_dt", "energy_norm", "accuracy_mean", "latency_ms"]:
            stacked = np.array([r[key][burn_in:] for r in runs])
            means[key + "_mean"] = float(stacked.mean())
            means[key + "_std"]  = float(stacked.mean(axis=1).std())
        summary[method] = means
    return summary


def format_table(summary: dict) -> str:
    """Render a text-mode baseline table in the order used in the paper."""
    order = ["static", "reactive", "dt_only", "dt_qa", "full"]
    display = {
        "static":   "Static ISAC",
        "reactive": "Reactive",
        "dt_only":  "DT only",
        "dt_qa":    "DT+QA (no Sec)",
        "full":     "Full Proposed",
    }
    lines = []
    lines.append(f"{'Method':<20} {'Rate(Mbps)':>13} {'Pd':>7} {'Trust':>7} {'Energy':>7} {'Utility':>9}")
    lines.append("-" * 72)
    for m in order:
        if m not in summary: continue
        s = summary[m]
        rate_tot = s["rate_bps_total_mean"] / 1e6
        rate_std = s["rate_bps_total_std"] / 1e6
        lines.append(
            f"{display[m]:<20} {rate_tot:>6.1f}±{rate_std:<4.1f} "
            f"{s['p_d_mean_mean']:>7.3f} {s['trust_mean']:>7.3f} "
            f"{s['energy_norm_mean']:>7.3f} {s['utility_mean']:>9.3f}"
        )
    return "\n".join(lines)


def main():
    cfg = SimConfig(n_slots=300)
    n_mc = 3
    methods = ["static", "reactive", "dt_only", "dt_qa", "full"]

    print(f"=== Baseline comparison ===")
    print(f"n_slots per run: {cfg.n_slots}, MC runs per method: {n_mc}")
    print(f"Methods: {methods}\n")

    t0 = time.perf_counter()
    results = []
    for mc in range(n_mc):
        seed = cfg.master_seed + 1000 * mc
        print(f"[MC {mc+1}/{n_mc}] seed={seed}")
        for m in methods:
            t_m = time.perf_counter()
            res = run_method(cfg, m, seed, cfg.n_slots)
            results.append(res)
            dt_s = time.perf_counter() - t_m
            # Use tail utility for quick feedback
            u_tail = float(np.mean(res["utility"][-50:]))
            print(f"  {m:<12s}  utility_tail={u_tail:.3f}  ({dt_s:.1f}s)")

    total_wall = time.perf_counter() - t0
    print(f"\n=== Total wall time: {total_wall:.1f}s ===\n")

    summary = aggregate(results)
    print(format_table(summary))

    # Persist to JSON
    out = Path("/home/claude/sim/results_baseline.json")
    out.write_text(json.dumps(summary, indent=2))
    print(f"\nSummary written to: {out}")


if __name__ == "__main__":
    main()
