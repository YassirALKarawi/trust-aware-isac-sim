# Reproducibility Guide

This document explains how to regenerate every numerical result reported in the
paper from the simulator. Each experiment is seeded deterministically from the
`master_seed` parameter in `src/config.py`.

---

## System requirements

| Component | Minimum version | Notes |
|---|---|---|
| Python | 3.10 | `|` union types, `match` statements used in the codebase |
| NumPy | 1.24 | Default RNG (`Generator`) is used throughout |
| SciPy | 1.10 | Optional; used only for a handful of statistical helpers |
| Matplotlib | 3.7 | Optional; required only for `tools/make_figures.py` |
| RAM | ~500 MB | Peak at `n_users = 100, n_slots = 500` |
| GPU / quantum HW | — | None required. The VQC scorer is a classical surrogate. |

---

## Deterministic seeding

Every random draw in the simulator traces to the `master_seed` parameter.
Monte-Carlo realisation `k` uses seed `master_seed + 1000·k`. Within one
realisation, the channel bank, mobility, clutter, anomaly injector, digital
twin, trust process, and screener all share the same NumPy `Generator`
instance, so results are **bit-identical** on reruns with the same NumPy
version.

To reproduce the paper's exact numbers, keep `master_seed = 20260417` and use
NumPy 2.x.

---

## Single-run smoke test

```bash
python src/controller.py
```

Runs the full framework for 20 slots and prints the final utility. Expected
output: utility in the 0.50–0.65 range depending on the random draw from the
seeded anomaly process. Runtime ≈ 30 s.

---

## Paper-scale experiments

### Baseline comparison (Table 3, Table 4, Fig. 2)

```bash
python src/run_baseline.py
```

Runs all six baselines (Static ISAC, Reactive, DT only, DT+QA, DT+Trust,
Full Proposed) over 3 Monte-Carlo realisations of 200 slots each. Writes
`results/baseline.json`. Runtime ≈ 3 min.

### Anomaly-rate sweep (Fig. 6)

```bash
python -c "
from src.run_all import exp_anomaly_sweep
from src.config import SimConfig
import json
cfg = SimConfig(n_slots=120)
r = exp_anomaly_sweep(cfg, n_mc=2)
json.dump(r, open('results/anomaly_sweep.json', 'w'), indent=2)
"
```

Sweeps attack rate p ∈ {0, 0.005, 0.01, 0.02, 0.04, 0.06, 0.08, 0.10}.
Runtime ≈ 8 min.

### Twin-delay sweep (Fig. 7)

```bash
python -c "
from src.run_all import exp_twin_delay
from src.config import SimConfig
import json
cfg = SimConfig(n_slots=150)
r = exp_twin_delay(cfg, n_mc=2)
json.dump(r, open('results/twin_delay.json', 'w'), indent=2)
"
```

Sweeps τ_sync ∈ {1, 2, 4, 6, 8, 10} slots. Runtime ≈ 6 min.

### Shortlist-size sensitivity (Fig. 11)

```bash
python -c "
from src.run_all import exp_shortlist_size
from src.config import SimConfig
import json
cfg = SimConfig(n_slots=150)
r = exp_shortlist_size(cfg, n_mc=2)
json.dump(r, open('results/shortlist_size.json', 'w'), indent=2)
"
```

Sweeps M_s ∈ {1, 2, 4, 6, 8, 10, 12, 15, 20, 30}. Runtime ≈ 4 min.

### Trust transient (Fig. 12)

```bash
python -c "
from src.run_all import exp_trust_transient
from src.config import SimConfig
import json
cfg = SimConfig(n_slots=500)
r = exp_trust_transient(cfg)
json.dump(r, open('results/trust_transient.json', 'w'), indent=2)
"
```

Runs 500 slots with an attack burst from slot 200 to slot 300. Runtime ≈ 1 min.

### Full experiment suite

```bash
python src/run_all.py
```

Runs every experiment above plus the scalability sweeps. Runtime ≈ 30 min.

---

## Regenerating the aggregated summary

After any subset of experiments has been run, the consolidated summary can be
regenerated with:

```bash
python src/synthesize.py
```

This reads every JSON under `results/` and prints a compact summary of the
numbers that appear in the paper.

---

## Regenerating the figures

Two equivalent paths are provided:

```bash
# A — publication-grade (requires matplotlib)
python tools/make_figures.py
#   → writes PNG + PDF for every figure into figures/

# B — zero external dependencies (stdlib only)
python tools/build_figures.py
#   → writes SVG for every figure into figures/
```

Both paths consume the same JSON under `results/` and produce a visually
equivalent figure set.

---

## Extending the experiment scale

For publication-grade confidence intervals (±1 %), increase the Monte-Carlo
count and slot count:

```python
# In src/run_all.py, change main() to:
cfg_main = SimConfig(n_slots=2000)            # ~10× default
results["baseline"]      = exp_baseline(cfg_main, n_mc=10)
results["anomaly_sweep"] = exp_anomaly_sweep(cfg_main, n_mc=10)
# ...
```

Total runtime scales approximately linearly: 10× MC × 10× slots ≈ 50 h on a
single CPU core.
