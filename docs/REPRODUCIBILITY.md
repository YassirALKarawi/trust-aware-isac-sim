# Reproducibility Guide

This document explains how to regenerate every numerical result reported in the paper from the simulator. Each experiment is seeded deterministically from the `master_seed` parameter in `src/config.py`.

---

## System requirements

- Python 3.10 or later
- NumPy 1.24 or later
- SciPy 1.10 or later
- Matplotlib 3.7 or later (for optional plot regeneration)
- ~500 MB RAM
- No GPU or quantum-hardware dependency

---

## Single-run smoke test

```bash
python src/controller.py
```

Runs the full framework for 20 slots and prints the final utility. Expected output: utility in the 0.50–0.65 range depending on the random draw from the seeded anomaly process. Total runtime ~30 seconds.

---

## Paper-scale experiments

### Baseline comparison (Table 3, Table 4, Fig. 2)

```bash
python src/run_baseline.py
```

Runs all six baselines (Static ISAC, Reactive, DT only, DT+QA, DT+Trust, Full Proposed) over 3 Monte Carlo realisations of 200 slots each. Writes `results/baseline.json`. Total runtime ~3 minutes.

### Anomaly-rate sweep (Fig. 6)

```bash
python -c "from run_all import exp_anomaly_sweep; from config import SimConfig; import json
cfg = SimConfig(n_slots=120)
r = exp_anomaly_sweep(cfg, n_mc=2)
with open('results/anomaly_sweep.json', 'w') as f: json.dump(r, f, indent=2)"
```

Sweeps attack rate p ∈ {0, 0.005, 0.01, 0.02, 0.04, 0.06, 0.08, 0.10}. Total runtime ~8 minutes.

### Twin-delay sweep (Fig. 7)

```bash
python -c "from run_all import exp_twin_delay; from config import SimConfig; import json
cfg = SimConfig(n_slots=150)
r = exp_twin_delay(cfg, n_mc=2)
with open('results/twin_delay.json', 'w') as f: json.dump(r, f, indent=2)"
```

Sweeps τ_sync ∈ {1, 2, 4, 6, 8, 10} slots. Total runtime ~6 minutes.

### Shortlist-size sensitivity (Fig. 11)

```bash
python -c "from run_all import exp_shortlist_size; from config import SimConfig; import json
cfg = SimConfig(n_slots=150)
r = exp_shortlist_size(cfg, n_mc=2)
with open('results/shortlist_size.json', 'w') as f: json.dump(r, f, indent=2)"
```

Sweeps M_s ∈ {1, 2, 4, 6, 8, 10, 12, 15, 20, 30}. Total runtime ~4 minutes.

### Trust transient (Fig. 12)

```bash
python -c "from run_all import exp_trust_transient; from config import SimConfig; import json
cfg = SimConfig(n_slots=500)
r = exp_trust_transient(cfg)
with open('results/trust_transient.json', 'w') as f: json.dump(r, f, indent=2)"
```

Runs 500 slots with an attack burst from slot 200 to slot 300. Total runtime ~1 minute.

### Full experiment suite

```bash
python src/run_all.py
```

Runs every experiment above plus the scalability sweeps. Total runtime ~30 minutes.

---

## Regenerating the aggregated summary

After any subset of experiments has been run, the consolidated summary in the paper's Results section can be regenerated with:

```bash
python src/synthesize.py
```

This reads every JSON under `results/` and prints a compact summary of the numbers that appear in the paper.

---

## Extending the experiment scale

For publication-grade confidence intervals (±1%), increase the Monte Carlo count and slot count:

```python
# In src/run_all.py, change main() to:
cfg_main = SimConfig(n_slots=2000)   # ~10x default
results["baseline"] = exp_baseline(cfg_main, n_mc=10)
results["anomaly_sweep"] = exp_anomaly_sweep(cfg_main, n_mc=10)
# ...
```

Total runtime scales approximately linearly: 10x MC × 10x slots ≈ 50 hours on a single CPU core.

---

## Deterministic seeding

Every random draw in the simulator traces to the `master_seed` parameter. Monte Carlo realisation `k` uses seed `master_seed + 1000*k`. Within one realisation, the channel bank, mobility, clutter, anomaly injector, digital twin, trust process, and screener all share the same Generator instance, so results are bit-identical on reruns with the same NumPy version.

To reproduce the paper's exact numbers, keep `master_seed = 20260417` and use NumPy 2.x.
