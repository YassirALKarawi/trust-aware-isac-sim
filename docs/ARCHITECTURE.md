# Architecture

This document describes the module graph, key design decisions, and the
canonical extension points of the simulator. It complements the top-level
[README](../README.md) and the paper's §III–§IV.

---

## Visual overview

<p align="center">
  <img src="../figures/fig_architecture.svg" alt="Architecture" width="100%"/>
</p>

<p align="center">
  <img src="../figures/fig_timing.svg" alt="Per-slot timing" width="100%"/>
</p>

<p align="center">
  <img src="../figures/fig_trust_gate.svg" alt="Trust gate" width="100%"/>
</p>

<p align="center">
  <img src="../figures/fig_deployment.svg" alt="Deployment geometry" width="92%"/>
</p>

---

## Module dependency graph

```
                  ┌─────────────┐
                  │  config.py  │  ← parameters (SimConfig)
                  └──────┬──────┘
                         │
     ┌───────────────────┼───────────────────┐
     │                   │                   │
 ┌───▼───┐    ┌─────────▼───┐    ┌──────────▼─────────┐
 │channel│    │  mobility   │    │     anomaly        │
 └───┬───┘    └─────┬───────┘    └──────────┬─────────┘
     │              │                       │
     └──────┬───────┴───────────────────────┘
            │
     ┌──────▼────────────┐
     │   digital_twin    │──────┐
     └──────┬────────────┘      │
            │                    │
     ┌──────▼────────┐    ┌─────▼──────┐    ┌──────────┐
     │    trust      │    │ screening  │    │  gate    │
     └──────┬────────┘    └─────┬──────┘    └─────┬────┘
            │                    │                │
            └────────────────────┼────────────────┘
                                 │
                        ┌────────▼──────────┐
                        │    controller     │
                        │  (ties together)  │
                        └────────┬──────────┘
                                 │
                        ┌────────▼──────────┐
                        │     sensing       │  ← Swerling-I + CPI
                        └───────────────────┘
```

---

## Per-module responsibilities

| Module | Responsibility | Key entry point |
|---|---|---|
| `config.py` | Every system parameter lives in one `SimConfig` dataclass. | `SimConfig()` |
| `channel.py` | Rician AR(1) channel bank across 4 BSs + UPA steering vectors. | `ChannelBank.step()` |
| `mobility.py` | Rayleigh-distributed pedestrian speeds with per-slot heading innovation. | `Mobility.step()` |
| `sensing.py` | Swerling-I detection, coherent pulse integration (512 chirps), CRLB accuracy. | `Sensor.detect()` |
| `digital_twin.py` | Delayed telemetry queue, Kalman-like filter, fidelity metric. | `DigitalTwin.update()` |
| `trust.py` | Bayesian-EWMA trust process with bounded evidence. | `TrustProcess.update()` |
| `screening.py` | Classical deterministic surrogate of VQC scoring; shortlisting. | `QAScreener.shortlist()` |
| `gate.py` | Convex blend `T·a_opt + (1-T)·a_safe`; hard fallback below floor. | `TrustGate.apply()` |
| `anomaly.py` | Poisson-onset / geometric-duration jamming / spoofing / mixed injection. | `AnomalyInjector.step()` |
| `controller.py` | Master controller wiring all modules and the slot loop. | `ISACController.run()` |
| `run_baseline.py` | Baseline comparison experiment (Table 3, 4). | `main()` |
| `run_all.py` | Full experiment suite. | `main()` |
| `synthesize.py` | JSON → human-readable summary. | `main()` |

---

## Key design decisions

### Separation of `H_true` and `H_method`

Every method with a digital twin evaluates candidate actions on a twin-derived
channel tensor (`H_method`), but actions deploy against the true physical
channel (`H_true`). This is the mechanism that exposes the cost of trusting
a corrupted twin: under spoofing, `H_method` points the precoder at the
wrong place while `H_true` determines what users actually receive.

### Safe fallback alignment with Static ISAC

The safe fallback action invoked by the trust gate is the same allocation
used by Static ISAC (`rho_sense = 0.30`, `power_frac = 1.00`, `bw_frac = 1.00`).
This guarantees that the full framework can never perform worse than Static
under trust collapse — it either matches Static or adapts beyond it.

### Ground-truth trust in utility

The trust term in the utility function uses a ground-truth value (1.0 in
nominal slots, 0.3 in anomaly slots) shared across all methods, rather than
each method's internal trust estimate. This prevents penalising trust-aware
methods for honestly reporting low confidence; methods differ in how they
perceive and respond to the true state, not in how they report it.

### Coordinated JT-RZF precoding

All four BSs share a joint 256-antenna precoder constructed from the
aggregated channel, with MMSE-scaled regularisation `reg = K·σ²/P`. This
matches the cell-free massive MIMO architecture described in the paper.

### Coherent pulse integration

The SCNR at the matched-filter output includes an integration gain of
`n_pulses_cpi = 512`, reflecting a standard FMCW coherent processing
interval. This boost — roughly 27 dB — is what brings Swerling-I detection
probability into the operationally interesting regime at 200–400 m sensing
ranges.

### Hotspot deployment

Users and targets are drawn uniformly within a 450 m radius around the area
centre (`hotspot_radius_m = 450`). This matches the use case in the paper —
coordinated service of a bounded region — and restores enough angular
diversity in the aggregated channel for the coordinated precoder to exploit.

---

## Extending the simulator

### New precoder scheme

Add a case in `controller.ISACController._build_precoder()` keyed on
`cfg.precoder`. The function receives the channel tensor `H` and the action
dictionary, and must return a precoder tensor of the same shape as `H` with
power-allocated weights.

### New anomaly type

Add the kind name in `anomaly.AnomalyInjector.kinds` and a corresponding
branch in `step()`. Populate the `eff` dictionary with the appropriate
`jam_db_rise`, `spoof_fraction`, and any new fields that the controller's
sensing or twin modules should react to.

### New baseline method

Add an entry to `controller.BASELINE_FLAGS` with the appropriate
`ControllerFlags` configuration. If the method's behaviour differs from the
standard pipeline, extend `ControllerFlags` with a new boolean flag and wire
it into `run_slot()`.

### Larger scale

Increase `n_slots`, `n_mc_runs`, `n_users`, and `n_targets` in `SimConfig`.
The coordinated JT-RZF precoder scales as `O(n_users³)` per candidate
evaluation; beyond `n_users = 100` it becomes the dominant cost and should
be replaced with a per-subgroup approximation for tractable runtime.
