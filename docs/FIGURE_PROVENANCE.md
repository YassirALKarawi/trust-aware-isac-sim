# Figure Provenance

One entry per committed figure under `figures/`, documenting how each file is
produced and what kind of content it carries. This is the manifest required
by `docs/PAPER_CODE_ALIGNMENT_AUDIT.md` Phase 6.

Classification key:

- **measured** — every plotted value is a simulator output read from a JSON
  in `results/`. No hand-shaping, smoothing, or hardcoded values.
- **derived** — plotted values are deterministic arithmetic transforms of
  simulator outputs (e.g. percentage-reduction bars, normalised ratios).
- **projected** — values are engineering budgets / extrapolations that the
  simulator does not and cannot produce in this repository. Must be labelled
  as such in the figure itself.
- **illustrative** — hand-authored architecture, deployment, or mechanism
  diagrams with no numerical data. No data source.

| # | File | Content class | Source script | Input JSON | Notes |
|---:|---|---|---|---|---|
| 1 | `fig_architecture.svg` | illustrative | hand-authored SVG | — | Module-dependency diagram. No data. |
| 2 | `fig_deployment.svg` | illustrative | hand-authored SVG | — | 4-BS / 40-user / 10-target cell-free geometry. No data. |
| 3 | `fig_timing.svg` | illustrative + projected | hand-authored SVG | — | Per-slot timing ruler. The "31 ms projected simulator" and "≈1.8 ms projected native deployed" numbers are engineering budgets, now labelled as **illustrative projection — not measured by this simulator**. Readers comparing to the JSON should use `simulator_wall_clock_ms_mean` in `results/baseline.json`. |
| 4 | `fig_trust_gate.svg` | illustrative | hand-authored SVG | — | Gate-mechanism diagram. No data. |
| 5 | `fig_baseline_bars.svg` | measured | `tools/build_figures.py:fig_baseline_bars` | `results/baseline_v2.json` | Utility with ±std error bars. Subtitle names the three methods with active Bayesian-EWMA trust. |
| 6 | `fig_baseline_dashboard.svg` | measured + derived | `tools/build_figures.py:fig_baseline_dashboard` | `results/baseline_v2.json` | Utility / Rate / P_d / Energy⁻¹ normalised to per-metric max. Energy⁻¹ bar is `1 − E + 0.2`, a visual rescaling (derived). |
| 7 | `fig_anomaly_sweep.svg` | measured | `tools/build_figures.py:fig_anomaly_sweep` | `results/anomaly_sweep_v2.json` | Subtitle quotes BOTH the peak gap vs Static and the peak gap vs the strongest baseline, so readers cannot conflate them (see audit §5). |
| 8 | `fig_twin_delay.svg` | measured | `tools/build_figures.py:fig_twin_delay` | `results/twin_delay.json` | Utility swing ≈1 % across τ ∈ [1, 10]. |
| 9 | `fig_shortlist_size.svg` | measured | `tools/build_figures.py:fig_shortlist_size` | `results/shortlist_size.json` | Subtitle reports the structural reduction `1 − M_s/M = 76 %` at the canonical `M=50, M_s=12` and says "plateaus near M_s ≈ 10–20" (noise-dominated). The curve's argmax is reported honestly. Second trace is simulator wall-clock (rescaled). |
| 10 | `fig_trust_transient.svg` | measured | `tools/build_figures.py:fig_trust_transient` | `results/trust_transient.json` | Attack burst slots 200–300. Subtitle reports the actual floor `min T(t) ≈ 0.06` and the 10–90 recovery span (21 slots on the committed JSON). Horizontal line at `T_safe = 0.30` now labelled as gate threshold, not a cap on `T(t)`. |
| 11 | `fig_pareto.svg` | measured | `tools/build_figures.py:fig_pareto` | `results/baseline_v2.json` | Energy–utility scatter with non-dominated frontier. |
| 12 | `fig_scalability_users.svg` | measured | `tools/build_figures.py:fig_scalability_users` | `results/scalability_users.json` | Utility vs U ∈ {10, 20, 40, 60, 80}. |
| 13 | `fig_scalability_targets.svg` | measured | `tools/build_figures.py:fig_scalability_targets` | `results/scalability_targets.json` | Utility vs K ∈ {2, 5, 10, 15, 20}. |

## Regeneration

Every "measured" and "derived" figure rebuilds directly from the files under
`results/`. No figure in this manifest is synthetic or smoothed.

```bash
# Stdlib-only SVG rebuild (what the repo ships)
python tools/build_figures.py

# Matplotlib PNG + PDF equivalents
python tools/make_figures.py
```

The illustrative / projected SVGs (`fig_architecture`, `fig_deployment`,
`fig_timing`, `fig_trust_gate`) are checked in as-is and are not regenerated
by the tool scripts.

## Audit hook

If a new figure is added, it must also be added to this file with its
content class and source. A figure that plots numbers the simulator does
not emit MUST be labelled `projected` or `illustrative`, never `measured`.
