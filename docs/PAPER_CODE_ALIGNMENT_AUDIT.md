# Paper ↔ Code Alignment Audit

**Scope.** This document audits internal consistency between `src/*.py`, the
committed JSON artefacts under `results/`, the figures under `figures/`, and
the paper-facing text in `README.md` and `docs/*.md`. Its purpose is to make
every claim traceable to a reproducible simulator output and to flag claims
that are aspirational, projected, or illustrative.

This is the input to the follow-up remediation documented in
[`FINAL_ALIGNMENT_STATUS.md`](FINAL_ALIGNMENT_STATUS.md); see that file for the
resulting canonical paper snapshot.

> **Rule of precedence adopted throughout:** CODE / SIMULATOR OUTPUT >
> DOCS / README CLAIMS. When a discrepancy exists, the repo will downgrade
> the claim rather than invent a number.

---

## 1. Baseline methods — names, flags, JSON presence

### 1.1 Implemented in code (source of truth: `src/controller.py:483`)

| Key in `BASELINE_FLAGS` | `use_digital_twin` | `use_quantum_screen` | `use_trust_gate` | `use_security_trust` | fixed action | Paper label |
|---|:-:|:-:|:-:|:-:|:-:|---|
| `static`   | ✗ | ✗ | ✗ | ✗ | `STATIC_ACTION` | Static ISAC |
| `reactive` | ✗ | ✗ | ✗ | ✗ | 3-preset selector | Reactive |
| `dt_only`  | ✓ | ✗ | ✗ | ✓ | — | DT only |
| `dt_qa`    | ✓ | ✓ | ✗ | ✗ | — | DT + QA |
| `dt_trust` | ✓ | ✗ | ✓ | ✓ | — | DT + Trust |
| `full`     | ✓ | ✓ | ✓ | ✓ | — | Full (Proposed) |

### 1.2 Baselines referenced in artefacts

| Artefact | Baselines present |
|---|---|
| `results/baseline.json` | all 6 |
| `results/baseline_v2.json` | all 6 |
| `README.md` Table 3 | all 6 |
| `tools/make_figures.py` / `build_figures.py` | all 6 |
| `src/run_baseline.py` `main()` | 5 (drops `dt_trust`) |
| `src/run_all.py` `exp_baseline()` | all 6 |

**Mismatch.** `src/run_baseline.py:main()` only iterates five methods
(`["static", "reactive", "dt_only", "dt_qa", "full"]`) but the JSON it is
supposed to produce contains six. The `format_table()` in the same file also
omits `dt_trust`. `src/run_all.py` does include the sixth method, so the v2
JSON is likely produced by `run_all.py`, not by `run_baseline.py`. The
README claims `run_baseline.py` reproduces Table 3 (which has six rows) —
that is incorrect.

**Remediation.** Add `dt_trust` to `run_baseline.main()` and its table so the
single script that README advertises for Table 3 actually produces the
matching JSON schema.

---

## 2. Trust values — active vs nominal default

### 2.1 What "trust" means in code

`src/trust.py:TrustProcess` maintains a Bayesian-EWMA posterior `T(t) ∈ [0,1]`
that combines twin mismatch `ε_DT`, residual outlier fraction and a soft
anomaly indicator (`src/trust.py:38`). The simulator initialises `T(0)=1.0`
and only updates `T(t)` when `flags.use_security_trust=True`.

When `use_security_trust=False`, `ISACController.trust_proc is None` and the
reported per-slot trust is hardcoded to `1.0` (`src/controller.py:368`). That
value is **not a measurement** — it is a placeholder so downstream code can
keep a scalar trust signal, nothing more.

### 2.2 Committed JSON values (`results/baseline_v2.json`)

| Method    | Reports `use_security_trust` | `trust_mean` in JSON | Semantics |
|---|:-:|---:|---|
| `static`   | ✗ | 1.000 | **nominal default** (no trust engine) |
| `reactive` | ✗ | 1.000 | **nominal default** (no trust engine) |
| `dt_only`  | ✓ | 0.119 | active posterior |
| `dt_qa`    | ✗ | 1.000 | **nominal default** (no trust engine) |
| `full`     | ✓ | 0.443 | active posterior |
| `dt_trust` | ✓ | 0.188 | active posterior |

### 2.3 Paper-facing mismatch

README Table 3 displays the `1.00` values for Static / Reactive / DT+QA in
the *same column* as the `0.44` for Full. A reader has no indication that
the former three are placeholder values while the latter is a measured
posterior. This is the most serious misrepresentation risk in the current
artefacts.

**Remediation.** Extend the per-method JSON schema to include
`trust_semantics ∈ {"active", "nominal_default"}`. Update `run_baseline.py`
/ `run_all.py` to stamp this at write time. In README Table 3, render
nominal-default entries as e.g. "— (n/a)" or "1.00*" with a footnote that
defines the two regimes.

---

## 3. Latency semantics

### 3.1 What `latency_ms` in the JSON actually is

`ISACController.run_slot()` wraps the whole slot compute in
`time.perf_counter()` (`src/controller.py:336, 449`). The number written to
JSON under `latency_ms_mean` is therefore the **simulator wall-clock time of
one control-loop iteration on the machine that ran it**. It is a Python /
NumPy / single-core measurement, not a 5G-RIC native runtime.

### 3.2 Values in `results/baseline_v2.json`

| Method    | `latency_ms_mean` |
|---|---:|
| `static`   | 56.5 |
| `reactive` | 58.0 |
| `dt_only`  | 565.0 |
| `dt_qa`    | 318.2 |
| `full`     | 249.0 |
| `dt_trust` | 451.0 |

These are the values propagated into README Table 3's "Latency (ms)" column.
They are self-consistent with the simulator.

### 3.3 The 31 ms / 1.8 ms numbers

`figures/fig_timing.svg` and `README.md` Highlights both advertise
**"31 ms simulator / 1.8 ms deployed inference"**. These numbers:

- appear **nowhere** in any committed JSON,
- are **not** produced by any runnable script in this repo,
- are labelled on the timing figure as "Runtime budget (measured)".

The 31 ms number is inconsistent with the simulator wall-clock values
above (which are 56–565 ms for the methods that exercise the full pipeline).
The 1.8 ms "deployed" figure is a projection of what a vectorised / native
reimplementation of the per-slot controller might achieve on a near-RT RIC
— i.e. an engineering budget, not a measurement of anything this repo can
execute.

**Remediation.**
1. Rename JSON keys from `latency_ms_*` to
   `simulator_wall_clock_ms_*` (keeping the old keys as aliases for back-
   compat with the existing figure builders) and document in the README
   that this is a Python+NumPy single-core wall-clock.
2. Re-label `fig_timing.svg`'s "Runtime budget (measured)" box as
   "Runtime budget — illustrative projection", and remove the implication
   that 31 ms and 1.8 ms were measured by this simulator.
3. Explain in the README that the 1.8 ms figure is a projected native-
   deployment budget, not a measurement.

---

## 4. Search-cost / shortlist semantics (M, M_s)

### 4.1 Canonical values

- `SimConfig.n_candidates_full = 50` (M)
- `SimConfig.n_shortlist = 12` (M_s)

Both appear in `src/config.py:69,70`, in `fig_timing.svg` ("M=50 → M_s=12"),
and in the README.

### 4.2 Structural reduction

The paper-facing framing is `1 − M_s / M = 76 %` reduction in full-utility
evaluations per slot. This is a *structural* reduction and is independent of
any simulator output; it follows mechanically from `shortlist()` keeping 12
of 50 candidates.

The simulator's wall-clock latency captures additional effects (scoring
cost, training overhead, precoder build inside the shortlist evaluation)
and is therefore not a direct measurement of the 76 % figure.

### 4.3 "Utility saturates by M_s = 12"

Data from `results/shortlist_size.json`:

```
M_s:   1    2    4    6    8   10   12   15   20   30
util:  .233 .231 .221 .241 .239 .261 .260 .244 .281 .203
```

The curve is noisy (2 MC realisations per point), does **not** monotonically
saturate, and the highest point is actually `M_s = 20`. The claim "saturates
by M_s = 12" is at best an approximation and should be downgraded to
"plateaus near M_s = 12 with noise-dominated variation above it".

---

## 5. Anomaly-rate sweep — "peak gap" claim

README currently states:

> "Peak gap between the Full framework and the strongest baseline occurs at
> p = 0.06, where the gap reaches **+0.106 utility points**."

Data from `results/anomaly_sweep_v2.json`:

| p | Static | DT only | DT + QA | Full | Full − best-non-full | Full − Static |
|---:|---:|---:|---:|---:|---:|---:|
| 0.000 | 0.635 | 0.657 | 0.679 | 0.692 | +0.012 | +0.057 |
| 0.005 | 0.621 | 0.641 | 0.673 | 0.686 | +0.012 | +0.065 |
| 0.010 | 0.582 | 0.641 | 0.638 | 0.649 | +0.008 | +0.067 |
| 0.020 | 0.590 | 0.554 | 0.678 | 0.689 | +0.011 | +0.099 |
| 0.060 | 0.492 | 0.480 | 0.587 | 0.597 | **+0.011** | **+0.105** |
| 0.080 | 0.492 | 0.480 | 0.506 | 0.527 | +0.021 | +0.035 |

**Finding.** The +0.106 number is `Full − Static` at `p = 0.06`, **not**
`Full − strongest baseline`. Against the strongest non-full baseline the
peak gap is +0.021 at `p = 0.08`.

**Remediation.** Rewrite the README sentence to say explicitly
"gap vs Static", and quote the smaller gap vs the strongest baseline.

---

## 6. Trust-recovery transient — "down to ≈0.27"

README currently states:

> "drags the Full-framework trust down to ≈0.27, then the 10–90% recovery
> completes in **21 slots**"

Data from `results/trust_transient.json` (attack burst slots 200–300):

- `min(full.trust[200:300]) = 0.061` at slot 275
- 10–90 recovery span = **21 slots** ✓ (using floor `≈0.061` and post-attack
  steady-state `≈0.534`)

**Finding.** The 21-slot recovery span is correct. The "down to ≈0.27"
claim is wrong — the Bayesian-EWMA trust process lets `T(t)` fall well
below the safety floor `T_safe = 0.30` (the floor is a gate threshold, not
a cap on T itself). The true attack-floor minimum is `0.06`.

**Remediation.** Replace "≈0.27" with the actual `≈0.06`. Add a short
sentence clarifying that `T_safe = 0.30` is a gate threshold that triggers
hard fallback to Static, not a floor on the trust process itself.

---

## 7. Headline "+2.3% / +21%" utility claims

From `results/baseline_v2.json`:
- nominal: `Full=0.622`, `DT+QA=0.608` ⇒ `+2.3 %` vs DT+QA. ✓ consistent
  with README.

From `results/anomaly_sweep_v2.json`:
- at `p = 0.06`: `Full=0.597`, `Static=0.492` ⇒ `+21.5 %` vs Static. ✓
  consistent with README.
- vs strongest baseline (`DT+QA = 0.587`) the relative gain is only
  `+1.7 %`.

**Remediation.** The +21 % is well-defined only if the reference is named.
The README should say "+21 % vs Static at p = 0.06", not an unqualified
"+21 % utility under a 6 % anomaly regime", which invites the reader to
assume the reference is the strongest baseline.

---

## 8. Figures — direct vs illustrative

| File | Source | Data-driven? | Notes |
|---|---|---|---|
| `fig_architecture.svg` | hand-authored | illustrative | no data |
| `fig_deployment.svg` | hand-authored | illustrative | no data |
| `fig_timing.svg` | hand-authored | illustrative | **mis-labels 31 ms / 1.8 ms as "measured"** |
| `fig_trust_gate.svg` | hand-authored | illustrative | no data |
| `fig_baseline_bars.svg` | `build_figures.fig_baseline_bars()` | from `baseline_v2.json` | ✓ |
| `fig_baseline_dashboard.svg` | `build_figures.fig_baseline_dashboard()` | from `baseline_v2.json` | ✓ |
| `fig_anomaly_sweep.svg` | `build_figures.fig_anomaly_sweep()` | from `anomaly_sweep_v2.json` | ✓ |
| `fig_twin_delay.svg` | `build_figures.fig_twin_delay()` | from `twin_delay.json` | ✓ |
| `fig_shortlist_size.svg` | `build_figures.fig_shortlist_size()` | from `shortlist_size.json` | ✓ but subtitle claims "saturates near M_s = 20" because it picks the argmax |
| `fig_trust_transient.svg` | `build_figures.fig_trust_transient()` | from `trust_transient.json` | ✓ |
| `fig_pareto.svg` | `build_figures.fig_pareto()` | from `baseline_v2.json` | ✓ |
| `fig_scalability_users.svg` | `build_figures.fig_scalability_users()` | from `scalability_users.json` | ✓ |
| `fig_scalability_targets.svg` | `build_figures.fig_scalability_targets()` | from `scalability_targets.json` | ✓ |

All nine result figures are genuine transformations of the committed JSON.
No synthetic / hand-shaped curves are rendered as simulator output.

**Remediation for `fig_timing.svg`.** Re-label the runtime-budget box as
illustrative/projection and move the 1.8 ms deployed number to a clearly
labelled "projected native" column. See Section 3.3.

---

## 9. "Bit-identical reproducibility" badge

The README carries a green `bit-identical` badge and the text

> "reruns on the same NumPy version produce bit-identical output".

This is true of the **scientific metrics** (utility, rate, Pd, trust,
ε_DT, energy) because every stochastic draw flows through a single seeded
`numpy.random.Generator`. It is **not** true of the `latency_ms_*` fields,
which are `time.perf_counter()` wall-clock measurements and by construction
vary run-to-run and machine-to-machine.

**Remediation.** Add one sentence in the reproducibility doc saying
"bit-identical applies to the seeded numerical metrics; the wall-clock
latency fields vary by machine."

---

## 10. README claim: "reproduces every numerical result"

Given the mismatches catalogued above (peak-gap framing, trust minimum,
shortlist saturation, 31 ms / 1.8 ms, Reactive trust semantics, and the
run_baseline.py/baseline.json schema discrepancy), the README cannot
truthfully claim it reproduces *every* numerical result in the paper.

**Remediation.** Replace "every numerical result" with an enumerated list
of what the simulator produces bit-identically (baseline table, anomaly
sweep curves, twin-delay curves, trust transient, shortlist sweep,
scalability sweeps) and flag the 31 ms / 1.8 ms timing budget and the
architecture / deployment / timing diagrams as illustrative. Add a
"Known alignment status" section that points to this audit.

---

## 11. Required deliverables produced by this audit

- `docs/PAPER_CODE_ALIGNMENT_AUDIT.md` — this file.
- `docs/FIGURE_PROVENANCE.md` — per-figure manifest (see that file).
- `docs/FINAL_ALIGNMENT_STATUS.md` — post-remediation summary.
- Code updates:
  - `src/run_baseline.py` — add `dt_trust`, write `trust_semantics`,
    rename latency keys to `simulator_wall_clock_ms_*` and write them
    alongside the legacy `latency_ms_*` keys.
  - `src/run_all.py` — same schema upgrades.
  - `src/synthesize.py` — read new keys when present, print trust
    semantics column, distinguish wall-clock from projected latency.
  - `tools/build_figures.py` / `tools/make_figures.py` — new "Trust
    semantics" annotation in the baseline dashboard; shortlist subtitle
    updated; use new latency keys.
- Artefact updates:
  - `results/*.json` — add `trust_semantics` and
    `simulator_wall_clock_ms_*` aliases.
  - `figures/fig_timing.svg` — relabel to illustrative projection.
- `README.md` — conservative rewrite; see Section 10.
