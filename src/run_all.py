"""
Comprehensive experiment runner.

Executes every scenario needed by the paper in one batch, saves raw time
series and aggregated summaries to JSON for downstream analysis.
"""
import json
import time
from pathlib import Path
from dataclasses import asdict, replace
import numpy as np

from config import SimConfig
from controller import ISACController, BASELINE_FLAGS, ControllerFlags, STATIC_ACTION
from baselines import BASELINE_ORDER, BASELINE_TRUST_SEMANTICS


# Canonical in-repo results directory. Overrideable via environment if needed.
OUT_DIR = Path(__file__).resolve().parent.parent / "results"
OUT_DIR.mkdir(exist_ok=True)


def run_one(cfg: SimConfig, flags: ControllerFlags, seed: int,
            tag: str = "run") -> dict:
    """Execute one method on one MC realisation."""
    rng = np.random.default_rng(seed)
    ctrl = ISACController(cfg, flags, rng, tag=tag)
    hist = ctrl.run(cfg.n_slots)
    return {
        "utility":        [m.utility for m in hist],
        "rate_bps_mean":  [m.rate_bps_mean for m in hist],
        "rate_bps_total": [m.rate_bps_total for m in hist],
        "p_d_mean":       [m.p_d_mean for m in hist],
        "trust":          [m.trust for m in hist],
        "eps_dt":         [m.eps_dt for m in hist],
        "energy_norm":    [m.energy_norm for m in hist],
        "accuracy_mean":  [m.accuracy_mean for m in hist],
        "latency_ms":     [m.control_latency_ms for m in hist],
    }


def aggregate(runs: list, burn_in: int = 50, method_key: str = None) -> dict:
    """
    Mean and std over MC runs after burn-in.

    When `method_key` is one of the canonical baseline keys, the returned
    dict is additionally stamped with `trust_semantics` and a
    `simulator_wall_clock_ms_*` alias for the latency fields. See
    `docs/PAPER_CODE_ALIGNMENT_AUDIT.md` §2–§3.
    """
    out = {}
    for key in ["utility", "rate_bps_mean", "rate_bps_total", "p_d_mean",
                "trust", "eps_dt", "energy_norm", "accuracy_mean", "latency_ms"]:
        stacked = np.array([r[key][burn_in:] for r in runs])
        out[key + "_mean"] = float(stacked.mean())
        out[key + "_std"]  = float(stacked.mean(axis=1).std())
    out["simulator_wall_clock_ms_mean"] = out["latency_ms_mean"]
    out["simulator_wall_clock_ms_std"]  = out["latency_ms_std"]
    if method_key in BASELINE_TRUST_SEMANTICS:
        out["trust_semantics"] = BASELINE_TRUST_SEMANTICS[method_key]
    return out


# ============================================================
# Experiment 1: Baseline comparison across all five methods
# ============================================================
def exp_baseline(cfg: SimConfig, n_mc: int = 3) -> dict:
    print("\n=== Experiment 1: Baseline comparison ===")
    methods = BASELINE_ORDER
    summary = {}
    for m in methods:
        print(f"  {m}...", end="", flush=True)
        t0 = time.perf_counter()
        runs = []
        for mc in range(n_mc):
            seed = cfg.master_seed + 1000 * mc
            runs.append(run_one(cfg, BASELINE_FLAGS[m], seed, tag=m))
        summary[m] = aggregate(runs, method_key=m)
        print(f" done ({time.perf_counter()-t0:.1f}s)  util={summary[m]['utility_mean']:.3f}")
    return summary


# ============================================================
# Experiment 2: Anomaly-rate sweep
# ============================================================
def exp_anomaly_sweep(cfg: SimConfig, n_mc: int = 2) -> dict:
    print("\n=== Experiment 2: Anomaly-rate sweep ===")
    rates = [0.0, 0.005, 0.01, 0.02, 0.04, 0.06, 0.08]
    methods = ["static", "dt_only", "dt_qa", "full"]
    summary = {m: {} for m in methods}
    for p in rates:
        print(f"  p_anom={p:.3f}")
        for m in methods:
            flags = replace(BASELINE_FLAGS[m], p_anomaly=p)
            runs = []
            for mc in range(n_mc):
                seed = cfg.master_seed + 100 * mc
                runs.append(run_one(cfg, flags, seed, tag=f"{m}_p{p}"))
            summary[m][str(p)] = aggregate(runs, method_key=m)
            print(f"    {m:<10s} util={summary[m][str(p)]['utility_mean']:.3f}")
    return summary


# ============================================================
# Experiment 3: Twin-delay sweep
# ============================================================
def exp_twin_delay(cfg: SimConfig, n_mc: int = 2) -> dict:
    print("\n=== Experiment 3: Twin-delay sweep ===")
    taus = [1, 2, 4, 6, 8, 10]
    methods = ["dt_only", "dt_qa", "full"]
    summary = {m: {} for m in methods}
    for tau in taus:
        print(f"  tau_sync={tau} slots")
        for m in methods:
            flags = replace(BASELINE_FLAGS[m], tau_sync_slots=tau)
            runs = []
            for mc in range(n_mc):
                seed = cfg.master_seed + 100 * mc
                runs.append(run_one(cfg, flags, seed, tag=f"{m}_tau{tau}"))
            summary[m][str(tau)] = aggregate(runs, method_key=m)
            print(f"    {m:<10s} util={summary[m][str(tau)]['utility_mean']:.3f}")
    return summary


# ============================================================
# Experiment 4: Shortlist-size sensitivity
# ============================================================
def exp_shortlist_size(cfg: SimConfig, n_mc: int = 2) -> dict:
    print("\n=== Experiment 4: Shortlist-size sensitivity ===")
    sizes = [1, 2, 4, 6, 8, 10, 12, 15, 20, 30]
    summary = {}
    for M_s in sizes:
        flags = replace(BASELINE_FLAGS["full"], n_shortlist=M_s)
        runs = []
        for mc in range(n_mc):
            seed = cfg.master_seed + 100 * mc
            runs.append(run_one(cfg, flags, seed, tag=f"full_Ms{M_s}"))
        summary[str(M_s)] = aggregate(runs, method_key="full")
        print(f"  M_s={M_s:>2d}  util={summary[str(M_s)]['utility_mean']:.3f}  "
              f"latency={summary[str(M_s)]['latency_ms_mean']:.2f}ms")
    return summary


# ============================================================
# Experiment 5: Trust-recovery transient under anomaly onset
# ============================================================
def exp_trust_transient(cfg: SimConfig) -> dict:
    """
    Run a specific trace with anomaly onset at t=200, cleared at t=300.
    Record per-slot trust and utility for Full and DT-only.
    """
    print("\n=== Experiment 5: Trust-recovery transient ===")
    # We need deterministic anomaly onset; override by running with p=0 then
    # manually injecting during controller ticks. For simplicity run a burst
    # scenario where p spikes mid-run.
    methods = ["full", "dt_only"]
    summary = {}
    for m in methods:
        print(f"  {m}...")
        rng = np.random.default_rng(cfg.master_seed)
        flags = replace(BASELINE_FLAGS[m], p_anomaly=0.0)
        ctrl = ISACController(cfg, flags, rng, tag=m)
        trust_series = []
        utility_series = []
        for t in range(cfg.n_slots):
            # Inject anomaly burst 200..300
            if 200 <= t < 300:
                ctrl.anomaly.p_anom = 0.6
                if ctrl.anomaly.remaining == 0:
                    ctrl.anomaly.remaining = 1
                    ctrl.anomaly.active = "mixed"
            else:
                ctrl.anomaly.p_anom = 0.0
            sm = ctrl.run_slot(t)
            trust_series.append(sm.trust)
            utility_series.append(sm.utility)
        summary[m] = {"trust": trust_series, "utility": utility_series}
    return summary


# ============================================================
# Experiment 6: Scalability in user count
# ============================================================
def exp_scalability_users(base_cfg: SimConfig, n_mc: int = 2) -> dict:
    print("\n=== Experiment 6: User-count scalability ===")
    U_values = [10, 20, 40, 60, 80]
    methods = ["static", "dt_only", "full"]
    ckpt_path = OUT_DIR / "scalability_users.partial.json"
    # Load any prior partial checkpoint
    if ckpt_path.exists():
        summary = json.loads(ckpt_path.read_text())
    else:
        summary = {m: {} for m in methods}
    for U in U_values:
        cfg = replace(base_cfg, n_users=U, n_slots=120)
        print(f"  U={U}")
        for m in methods:
            if str(U) in summary.get(m, {}):
                print(f"    {m:<10s} cached util={summary[m][str(U)]['utility_mean']:.3f}")
                continue
            runs = []
            for mc in range(n_mc):
                seed = cfg.master_seed + 100 * mc
                runs.append(run_one(cfg, BASELINE_FLAGS[m], seed, tag=f"{m}_U{U}"))
            summary.setdefault(m, {})[str(U)] = aggregate(runs, method_key=m)
            ckpt_path.write_text(json.dumps(summary, indent=2))
            print(f"    {m:<10s} util={summary[m][str(U)]['utility_mean']:.3f}")
    return summary


# ============================================================
# Experiment 7: Scalability in target count
# ============================================================
def exp_scalability_targets(base_cfg: SimConfig, n_mc: int = 2) -> dict:
    print("\n=== Experiment 7: Target-count scalability ===")
    K_values = [2, 5, 10, 15, 20]
    methods = ["static", "dt_only", "full"]
    ckpt_path = OUT_DIR / "scalability_targets.partial.json"
    if ckpt_path.exists():
        summary = json.loads(ckpt_path.read_text())
    else:
        summary = {m: {} for m in methods}
    for K in K_values:
        cfg = replace(base_cfg, n_targets=K, n_slots=120)
        print(f"  K={K}")
        for m in methods:
            if str(K) in summary.get(m, {}):
                print(f"    {m:<10s} cached util={summary[m][str(K)]['utility_mean']:.3f}")
                continue
            runs = []
            for mc in range(n_mc):
                seed = cfg.master_seed + 100 * mc
                runs.append(run_one(cfg, BASELINE_FLAGS[m], seed, tag=f"{m}_K{K}"))
            summary.setdefault(m, {})[str(K)] = aggregate(runs, method_key=m)
            ckpt_path.write_text(json.dumps(summary, indent=2))
            print(f"    {m:<10s} util={summary[m][str(K)]['utility_mean']:.3f}  "
                  f"Pd={summary[m][str(K)]['p_d_mean_mean']:.3f}")
    return summary


# ============================================================
# Main
# ============================================================
def main():
    t_start = time.perf_counter()
    cfg_main = SimConfig(n_slots=250)

    print(f"Experiment suite start — {cfg_main.n_slots} slots, master seed {cfg_main.master_seed}")

    results = {}

    results["baseline"]           = exp_baseline(cfg_main, n_mc=3)
    results["anomaly_sweep"]      = exp_anomaly_sweep(cfg_main, n_mc=2)
    results["twin_delay"]         = exp_twin_delay(cfg_main, n_mc=2)
    results["shortlist_size"]     = exp_shortlist_size(cfg_main, n_mc=2)
    results["trust_transient"]    = exp_trust_transient(replace(cfg_main, n_slots=500))
    results["scalability_users"]  = exp_scalability_users(cfg_main, n_mc=2)
    results["scalability_targets"]= exp_scalability_targets(cfg_main, n_mc=2)

    total_s = time.perf_counter() - t_start
    print(f"\n=== All experiments complete in {total_s/60:.1f} min ===")

    # Write both the monolithic all_results.json (convenience) and the
    # per-experiment files consumed by tools/build_figures.py and
    # tools/make_figures.py. Filenames match the README "Mapping results ↔
    # paper" table.
    (OUT_DIR / "all_results.json").write_text(json.dumps(results, indent=2))
    (OUT_DIR / "baseline.json").write_text(
        json.dumps(results["baseline"], indent=2))
    (OUT_DIR / "anomaly_sweep.json").write_text(
        json.dumps(results["anomaly_sweep"], indent=2))
    (OUT_DIR / "twin_delay.json").write_text(
        json.dumps(results["twin_delay"], indent=2))
    (OUT_DIR / "shortlist_size.json").write_text(
        json.dumps(results["shortlist_size"], indent=2))
    (OUT_DIR / "trust_transient.json").write_text(
        json.dumps(results["trust_transient"], indent=2))
    (OUT_DIR / "scalability_users.json").write_text(
        json.dumps(results["scalability_users"], indent=2))
    (OUT_DIR / "scalability_targets.json").write_text(
        json.dumps(results["scalability_targets"], indent=2))
    print(f"Saved: {OUT_DIR}")

    # Quick summary print
    print("\n--- BASELINE SUMMARY ---")
    for m, s in results["baseline"].items():
        print(f"  {m:<10s}  util={s['utility_mean']:.3f}±{s['utility_std']:.3f}  "
              f"rate={s['rate_bps_total_mean']/1e6:.1f}Mbps  "
              f"Pd={s['p_d_mean_mean']:.3f}  "
              f"trust={s['trust_mean']:.3f}  "
              f"energy={s['energy_norm_mean']:.3f}  "
              f"lat={s['latency_ms_mean']:.2f}ms")


if __name__ == "__main__":
    main()
