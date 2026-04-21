# Final Alignment Status

Canonical post-remediation summary. Read this together with
[`PAPER_CODE_ALIGNMENT_AUDIT.md`](PAPER_CODE_ALIGNMENT_AUDIT.md) (the input
audit) and [`FIGURE_PROVENANCE.md`](FIGURE_PROVENANCE.md) (the figure
manifest).

---

## 1. Paper snapshot the repository now matches

The repo is internally consistent with the following snapshot, driven end-
to-end by the committed JSON artefacts in [`../results/`](../results):

| Quantity | Value | Source |
|---|---|---|
| Full utility (nominal) | **0.622** | `baseline_v2.json` |
| DT + QA utility (nominal) | **0.608** | `baseline_v2.json` |
| Full utility @ p = 0.06 | **0.597** | `anomaly_sweep_v2.json` |
| Static utility @ p = 0.06 | **0.492** | `anomaly_sweep_v2.json` |
| DT + QA utility @ p = 0.06 | **0.587** | `anomaly_sweep_v2.json` |
| Peak gap vs Static @ p = 0.06 | **+0.105** | derived |
| Peak gap vs strongest baseline (@ p = 0.08) | **+0.021** | derived |
| Full-framework trust floor under 100-slot attack | **T ≈ 0.06** | `trust_transient.json` |
| 10–90 % recovery | **21 slots** | `trust_transient.json` |
| Full-framework utility swing over τ ∈ [1,10] | **≈ 1 %** | `twin_delay.json` |
| Structural screener reduction at M = 50, M_s = 12 | **76 %** | `1 − M_s/M` |

All other figures and tables in `README.md` are derived from the same seven
JSON files.

---

## 2. Exact baseline set (single source of truth)

Defined in [`../src/baselines.py`](../src/baselines.py). Six methods, in
Table-3 order:

| Key | Display | Uses twin | Uses QA screener | Uses trust gate | Active trust engine |
|---|---|:-:|:-:|:-:|:-:|
| `static`   | Static ISAC      | ✗ | ✗ | ✗ | ✗ |
| `reactive` | Reactive         | ✗ | ✗ | ✗ | ✗ |
| `dt_only`  | DT only          | ✓ | ✗ | ✗ | ✓ |
| `dt_qa`    | DT + QA          | ✓ | ✓ | ✗ | ✗ |
| `dt_trust` | DT + Trust       | ✓ | ✗ | ✓ | ✓ |
| `full`     | Full (Proposed)  | ✓ | ✓ | ✓ | ✓ |

All runner scripts (`run_baseline.py`, `run_all.py`), figure builders
(`build_figures.py`, `make_figures.py`), and the synthesis script
(`synthesize.py`) consume this list directly; no other module duplicates
the baseline definitions.

---

## 3. Trust semantics (exact)

Every per-method entry in the JSON carries an explicit `trust_semantics`
field:

- `"active"` — method runs `src/trust.py::TrustProcess`. The `trust_mean`
  in the JSON is a Bayesian-EWMA posterior. Methods: `dt_only`, `dt_trust`,
  `full`.
- `"nominal_default"` — method does not run any trust engine. The
  `trust_mean = 1.0` is a placeholder and MUST NOT be compared numerically
  with an active posterior. Methods: `static`, `reactive`, `dt_qa`.

Paper-facing rendering:

- README Table 3 marks nominal-default trust entries with `*` and provides
  the legend.
- `fig_baseline_bars.svg` subtitle explicitly names the three methods with
  active trust.
- `make_figures.fig_baseline` plants an asterisk glyph at the base of each
  bar whose trust is a nominal default.

`T_safe = 0.30` is a **gate threshold** that triggers hard fallback to
Static; it is not a floor on `T(t)`. The trust process can and does fall
below it during a sustained attack — the committed JSON shows a minimum
`T ≈ 0.06`.

---

## 4. Latency semantics (exact)

Three distinct concepts, each with its own name:

1. **Simulator wall-clock** — `simulator_wall_clock_ms_mean` in every JSON
   leaf. Produced by `time.perf_counter()` wrapping
   `ISACController.run_slot()`. CPython + NumPy, single core, measured on
   whatever machine produced the JSON. The legacy `latency_ms_*` keys are
   kept as aliases for back-compat with the figure builders.
2. **Stage budget** — the per-stage layout of the 10 ms slot drawn in
   `figures/fig_timing.svg`. Illustrative, no numerical data.
3. **Projected native deployed** — the "≈ 31 ms projected simulator" and
   "≈ 1.8 ms projected native deployed" annotations on `fig_timing.svg`.
   Engineering projections of what a vectorised / native reimplementation
   could achieve; **not** simulator output. The figure is labelled
   "illustrative projection — not measured by this simulator".

`fig_timing.svg` directs readers to the JSON for the actual measured
wall-clock.

---

## 5. Claims downgraded from earlier drafts

| Earlier claim | New claim | Reason |
|---|---|---|
| "reproduces every numerical result" | "produces the committed JSON artefacts and the data-driven figures" | several paper-facing numbers (31 ms, 1.8 ms, timing budget) are projections, not simulator outputs |
| "peak gap vs strongest baseline +0.106 at p = 0.06" | "peak gap vs Static +0.105 at p = 0.06; vs strongest baseline +0.021 at p = 0.08" | arithmetic mis-attribution (see audit §5) |
| "Full-framework trust dragged down to ≈ 0.27" | "floor T ≈ 0.06 under sustained attack" | actual JSON minimum (see audit §6) |
| "Utility saturates by M_s = 12" | "utility plateaus near M_s ≈ 10–20; argmax on the 2-MC sweep is at M_s = 20" | curve is noise-dominated above M_s ≈ 10 (see audit §4.3) |
| Timing-figure "Runtime budget (measured)" with 31 ms / 1.8 ms | "Runtime budget — illustrative projection, not measured" | budgets, not profiler outputs |
| Reactive / Static / DT + QA trust = 1.00 shown next to active posteriors | Same values shown with `nominal_default` marker | prevents misinterpretation (see audit §2) |
| `run_baseline.py` claims to reproduce Table 3 but only ran 5 methods | `run_baseline.py` now runs all 6 methods including `dt_trust` | schema mismatch (see audit §1.2) |

---

## 6. Claims fully reproducible as-is

From the committed JSON without any code modification:

- Full vs. DT + QA utility gain in nominal conditions: **+2.3 %**.
- Full vs. Static utility gain at p = 0.06: **+21.5 %**.
- Trust 10–90 % recovery after a 100-slot burst: **21 slots**.
- Full utility swing across τ ∈ [1, 10]: **≈ 1 %**.
- Baseline Table 3 values (utility, rate, P_d, energy) for all six methods.
- Per-method simulator wall-clock values (on the machine that produced the
  committed JSON).

All nine "measured" or "derived" entries in
[`FIGURE_PROVENANCE.md`](FIGURE_PROVENANCE.md) rebuild verbatim via
`tools/build_figures.py` and `tools/make_figures.py`.

---

## 7. Remaining limitations

- The shortlist sweep has only 2 Monte-Carlo realisations per `M_s`, which
  leaves the utility curve noise-dominated above `M_s ≈ 10`. The paper-
  facing "plateaus near M_s ≈ 10–20" claim is qualitative for that reason.
  Tightening this requires `n_mc ≥ 10` at each point (see
  [REPRODUCIBILITY.md §"Extending the experiment scale"](REPRODUCIBILITY.md)).
- `results/anomaly_sweep_v2.json` misses `p = 0.04` (the nominal base rate)
  because the sweep stops at 0.02 and resumes at 0.06. This gap is visible
  in the anomaly-sweep plot.
- `simulator_wall_clock_ms_*` fields are machine-dependent and therefore
  not bit-identical. Only the seeded scientific metrics are.
- `figures/fig_timing.svg`'s 31 ms and 1.8 ms numbers remain projections;
  turning them into simulator measurements would require a vectorised
  reimplementation of the per-slot controller — outside the scope of this
  repository.
- The simulator is classical end-to-end. No quantum hardware is invoked,
  simulated, or required. The screener is a classical deterministic
  surrogate of variational quantum-style scoring.

---

## 8. How this was verified

- Every JSON under `results/` was inspected and stamped with
  `trust_semantics` and `simulator_wall_clock_ms_*` via
  [`../tools/_stamp_semantics.py`](../tools/_stamp_semantics.py). The
  script is idempotent.
- The stdlib-only figure rebuild succeeded with the new schema:
  ```
  python tools/build_figures.py  →  wrote 13 SVG figures
  ```
- All edited Python modules parse cleanly (syntax-checked with `ast.parse`).
- No paper-facing number in the current README is inconsistent with its
  cited JSON source at three-decimal precision.

---

## 9. Commits on this alignment branch

Branch: `feature/align-paper-consistency`. See the Git log for the
exact history; the single commit attached to this file documents the
complete Phase 1–10 remediation.
