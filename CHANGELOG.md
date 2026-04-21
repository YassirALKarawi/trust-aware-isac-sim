# Changelog

All notable changes to this repository are recorded in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this
project adheres to [Semantic Versioning](https://semver.org/).

## [1.1.0] — 2026-04-21

Paper ↔ code consistency pass. The repository now enforces a single source
of truth across `src/`, `results/`, `figures/`, and the paper-facing docs.
See `docs/PAPER_CODE_ALIGNMENT_AUDIT.md` for the input audit and
`docs/FINAL_ALIGNMENT_STATUS.md` for the resulting canonical snapshot.

### Added
- `src/baselines.py` — canonical baseline list with `trust_semantics`.
- `docs/PAPER_CODE_ALIGNMENT_AUDIT.md`, `docs/FIGURE_PROVENANCE.md`,
  `docs/FINAL_ALIGNMENT_STATUS.md`.
- `tools/_stamp_semantics.py` — stdlib-only JSON schema migration helper.
- `simulator_wall_clock_ms_mean` / `simulator_wall_clock_ms_std` fields
  and `trust_semantics` field in every result JSON leaf.
- Six-method baseline table in `run_baseline.py` (previously five).

### Changed
- `figures/fig_timing.svg` runtime-budget bar relabelled from
  "Runtime budget (measured)" to "illustrative projection — not measured
  by this simulator". The 31 ms / 1.8 ms values are now presented as
  engineering projections, not profiler outputs.
- README baseline table marks nominal-default trust entries so they
  cannot be confused with active Bayesian-EWMA posteriors.
- README anomaly-sweep section reports both "gap vs Static" and "gap vs
  strongest baseline" explicitly.
- README shortlist section reports plateau (not saturation) and the
  structural 76 % reduction at `M = 50, M_s = 12` explicitly.
- README trust-transient section reports the actual floor `T ≈ 0.06`.
- README removes the "every numerical result" claim and adds a
  "Known alignment status" pointer.
- `docs/REPRODUCIBILITY.md` distinguishes seeded bit-identical metrics
  from machine-dependent wall-clock fields.

### Fixed
- `run_all.py` now writes to the in-repo `results/` directory and emits
  both the monolithic `all_results.json` and the per-experiment files
  consumed by the figure builders.
- `run_baseline.py` now runs all six canonical methods including
  `dt_trust` (was missing from the previous 5-method table).

## [1.0.0] — 2026-04-18

First public release accompanying the IEEE JSAC 2026 submission.

### Added
- Full discrete-time simulator under `src/` implementing every module
  described in §III–§IV of the paper.
- Deterministic experiment runners `run_baseline.py` and `run_all.py`.
- Pre-computed JSON experiment outputs under `results/` covering baseline,
  anomaly-rate sweep, twin-delay sweep, shortlist-size sensitivity, trust
  transient, and scalability experiments.
- Aggregated summary generator `src/synthesize.py`.
- Publication-grade figure generator `tools/make_figures.py` (matplotlib).
- Zero-dependency SVG figure generator `tools/build_figures.py` and its
  helper module `tools/svg_plot.py`.
- Hand-crafted architecture diagrams in `figures/`:
  `fig_architecture.svg`, `fig_trust_gate.svg`, `fig_timing.svg`,
  `fig_deployment.svg`.
- Result figures in `figures/`: `fig_baseline_bars.svg`,
  `fig_anomaly_sweep.svg`, `fig_twin_delay.svg`, `fig_shortlist_size.svg`,
  `fig_trust_transient.svg`, `fig_pareto.svg`,
  `fig_scalability_users.svg`, `fig_scalability_targets.svg`.
- `CITATION.cff` for machine-readable citation.
- `CONTRIBUTING.md` with the development workflow.
- Reworked `README.md` with badges, architecture diagrams, results gallery,
  and a result-to-paper mapping table.
- Expanded `docs/ARCHITECTURE.md` and `docs/REPRODUCIBILITY.md`.

### Fixed
- `src/synthesize.py` no longer hard-codes the absolute results path; it
  resolves the `results/` directory relative to the repository root.
