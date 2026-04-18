"""
Quick test: run all methods in CLEAN conditions (no anomalies) to confirm
the full framework's adaptive advantage is real.
"""
import numpy as np
import time
from config import SimConfig
from controller import ISACController, BASELINE_FLAGS, ControllerFlags

cfg = SimConfig(n_slots=200, p_anomaly_per_slot=0.0)
methods = ["static", "reactive", "dt_only", "dt_qa", "full"]
n_mc = 2

print("=== Clean-conditions test (p_anomaly = 0) ===")
print(f"{cfg.n_slots} slots, {n_mc} MC runs\n")

by_method = {m: [] for m in methods}
for mc in range(n_mc):
    seed = cfg.master_seed + 1000 * mc
    for m in methods:
        rng = np.random.default_rng(seed)
        flags = BASELINE_FLAGS[m]
        # Force zero anomaly for this test
        flags_clean = ControllerFlags(
            use_digital_twin=flags.use_digital_twin,
            use_quantum_screen=flags.use_quantum_screen,
            use_trust_gate=flags.use_trust_gate,
            use_security_trust=flags.use_security_trust,
            fixed_action=flags.fixed_action,
            reactive_mode=flags.reactive_mode,
            p_anomaly=0.0,
        )
        t0 = time.perf_counter()
        ctrl = ISACController(cfg, flags_clean, rng, tag=m)
        hist = ctrl.run(cfg.n_slots)
        u_tail = np.mean([h.utility for h in hist[50:]])
        rate_tail = np.mean([h.rate_bps_total for h in hist[50:]]) / 1e6
        pd_tail = np.mean([h.p_d_mean for h in hist[50:]])
        by_method[m].append((u_tail, rate_tail, pd_tail))
        print(f"  MC{mc+1} {m:<10s} util={u_tail:.3f} rate={rate_tail:.1f}Mbps Pd={pd_tail:.3f}  ({time.perf_counter()-t0:.1f}s)")

print(f"\n{'Method':<12s} {'Utility':>9s} {'Rate(Mbps)':>12s} {'Pd':>7s}")
print('-' * 44)
for m in methods:
    us = [x[0] for x in by_method[m]]
    rs = [x[1] for x in by_method[m]]
    ps = [x[2] for x in by_method[m]]
    print(f"{m:<12s} {np.mean(us):>9.3f} {np.mean(rs):>12.1f} {np.mean(ps):>7.3f}")
