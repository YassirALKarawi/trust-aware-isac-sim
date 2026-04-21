"""
Baseline comparison runner.

Runs all six canonical methods (see `src/baselines.py`) on identical traces
and aggregates results into `results/baseline.json`. This is the single
script that reproduces the numbers in the README baseline table.

Schema notes
------------
- `trust_semantics` is stamped per method ("active" / "nominal_default").
  See `docs/PAPER_CODE_ALIGNMENT_AUDIT.md` §2.
- `simulator_wall_clock_ms_*` replaces the historical `latency_ms_*` fields,
  but the old keys are written as aliases for back-compat with existing
  figure builders. See §3 of the audit.
"""
import numpy as np
import json
import time
from pathlib import Path

from config import SimConfig
from controller import ISACController, BASELINE_FLAGS
from baselines import (BASELINE_ORDER, BASELINE_DISPLAY,
                        BASELINE_TRUST_SEMANTICS)


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


_KEYS = ("utility", "rate_bps_mean", "rate_bps_total", "p_d_mean",
         "trust", "eps_dt", "energy_norm", "accuracy_mean", "latency_ms")


def aggregate(results: list, burn_in: int = 50) -> dict:
    """Aggregate per-method results over MC runs, discarding a burn-in period."""
    summary = {}
    by_method = {}
    for r in results:
        by_method.setdefault(r["method"], []).append(r)
    for method, runs in by_method.items():
        means = {}
        for key in _KEYS:
            stacked = np.array([r[key][burn_in:] for r in runs])
            means[key + "_mean"] = float(stacked.mean())
            means[key + "_std"]  = float(stacked.mean(axis=1).std())
        # Expose wall-clock latency under an unambiguous name and keep the
        # legacy alias so existing figure builders continue to work. See
        # docs/PAPER_CODE_ALIGNMENT_AUDIT.md §3.
        means["simulator_wall_clock_ms_mean"] = means["latency_ms_mean"]
        means["simulator_wall_clock_ms_std"]  = means["latency_ms_std"]
        # Stamp trust semantics so readers cannot conflate an active
        # posterior with a nominal default. See audit §2.
        means["trust_semantics"] = BASELINE_TRUST_SEMANTICS.get(method, "unknown")
        summary[method] = means
    return summary


def format_table(summary: dict) -> str:
    """Render a text-mode baseline table in the order used in the paper."""
    lines = []
    lines.append(
        f"{'Method':<20} {'Rate(Mbps)':>13} {'Pd':>7} "
        f"{'Trust':>14} {'Energy':>7} {'Utility':>9} {'SimWall(ms)':>12}"
    )
    lines.append("-" * 94)
    for m in BASELINE_ORDER:
        if m not in summary:
            continue
        s = summary[m]
        rate_tot = s["rate_bps_total_mean"] / 1e6
        rate_std = s["rate_bps_total_std"] / 1e6
        # Mark nominal-default trust entries so a reader can't confuse them
        # with a measured posterior.
        trust_str = f"{s['trust_mean']:>7.3f}"
        if s.get("trust_semantics") == "nominal_default":
            trust_str = f"{s['trust_mean']:.3f} (nom)"
        lines.append(
            f"{BASELINE_DISPLAY[m]:<20} {rate_tot:>6.1f}±{rate_std:<4.1f} "
            f"{s['p_d_mean_mean']:>7.3f} {trust_str:>14s} "
            f"{s['energy_norm_mean']:>7.3f} {s['utility_mean']:>9.3f} "
            f"{s['simulator_wall_clock_ms_mean']:>12.1f}"
        )
    return "\n".join(lines)


def main():
    cfg = SimConfig(n_slots=300)
    n_mc = 3
    methods = BASELINE_ORDER  # all six

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
            u_tail = float(np.mean(res["utility"][-50:]))
            print(f"  {m:<12s}  utility_tail={u_tail:.3f}  ({dt_s:.1f}s)")

    total_wall = time.perf_counter() - t0
    print(f"\n=== Total wall time: {total_wall:.1f}s ===\n")

    summary = aggregate(results)
    print(format_table(summary))
    print("\n  'nom' marks methods whose trust value is a nominal default,")
    print("  not an active Bayesian-EWMA posterior. See baselines.py.")

    # Persist to the canonical results path inside the repo.
    out_dir = Path(__file__).resolve().parent.parent / "results"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / "baseline.json"
    out.write_text(json.dumps(summary, indent=2))
    print(f"\nSummary written to: {out}")


if __name__ == "__main__":
    main()
