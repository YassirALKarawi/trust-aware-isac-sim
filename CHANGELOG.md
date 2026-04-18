# Changelog

All notable changes to this repository are recorded in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this
project adheres to [Semantic Versioning](https://semver.org/).

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
