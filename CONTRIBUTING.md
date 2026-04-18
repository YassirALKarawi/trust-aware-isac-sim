# Contributing

Thank you for taking an interest in the trust-aware ISAC simulator. This
document explains how the repository is organised and the minimal quality
bar for contributions.

---

## Scope

The repository is primarily a **research reference implementation** for the
IEEE JSAC 2026 submission. Contributions that are welcome:

- Bug fixes in the simulator
- Additional baselines / ablations that plug cleanly into `ControllerFlags`
- New anomaly types that fit the `AnomalyInjector.kinds` interface
- Improved figure generators / publication-ready plots
- Documentation improvements, typo fixes, translations

Out of scope:

- Rewrites of the paper's modelling choices (those are frozen for the submission)
- Anything that breaks bit-identical reproducibility from `master_seed`

---

## Development workflow

```bash
git clone https://github.com/YassirALKarawi/trust-aware-isac-sim.git
cd trust-aware-isac-sim
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Smoke test — should finish in ~30 s
python src/controller.py

# Run targeted experiment
python src/run_baseline.py
```

Before opening a pull request, please confirm:

1. `python src/controller.py` still runs end-to-end.
2. Any new JSON written under `results/` is under 1 MB.
3. `python tools/build_figures.py` still succeeds with only the standard library.
4. `python src/synthesize.py` still prints a coherent summary.

---

## Code style

- Python 3.10+ syntax allowed (`|` union types, `match`, `dataclass` etc.)
- Keep modules single-purpose; the names under `src/` map 1-to-1 to the
  paper's §III / §IV subsections.
- Prefer NumPy vectorisation. No GPU / no quantum-hardware dependency.
- Seed every new random draw through the shared `Generator` in
  `ISACController` — do not call `np.random.*` directly.

---

## Extending the simulator

The main extension surfaces are documented in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md):

| To add… | Edit |
|---|---|
| A new precoder | `controller.ISACController._build_precoder()` |
| A new anomaly type | `anomaly.AnomalyInjector.kinds` + the `step()` branch |
| A new baseline method | `controller.BASELINE_FLAGS` |
| A larger deployment | `SimConfig` in `src/config.py` |

---

## Reporting issues

Please include:

- Python + NumPy version (`python -c "import numpy; print(numpy.__version__)"`)
- The `master_seed` and experiment that was run
- Full traceback or unexpected JSON output

---

## License

By contributing you agree that your contributions will be released under the
MIT License of this repository.
