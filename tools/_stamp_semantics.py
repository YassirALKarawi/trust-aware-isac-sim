"""
One-shot migration script: stamp `trust_semantics` and
`simulator_wall_clock_ms_*` aliases onto the committed JSON artefacts so
they match the schema emitted by the current `run_baseline.py` /
`run_all.py`. See docs/PAPER_CODE_ALIGNMENT_AUDIT.md §2–§3.

This script is idempotent and uses stdlib only (no numpy), so it can run in
any environment that has Python. It rewrites the files in place.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"

# Canonical trust-semantics map — must stay in sync with src/baselines.py.
TRUST_SEMANTICS = {
    "static":   "nominal_default",
    "reactive": "nominal_default",
    "dt_only":  "active",
    "dt_qa":    "nominal_default",
    "dt_trust": "active",
    "full":     "active",
}


def _is_method_leaf(d: dict) -> bool:
    """A leaf dict is one that contains the aggregate keys."""
    return isinstance(d, dict) and "utility_mean" in d and "latency_ms_mean" in d


def _stamp_leaf(leaf: dict, method_key: str | None) -> None:
    """Add `simulator_wall_clock_ms_*` aliases and `trust_semantics`."""
    if "latency_ms_mean" in leaf and "simulator_wall_clock_ms_mean" not in leaf:
        leaf["simulator_wall_clock_ms_mean"] = leaf["latency_ms_mean"]
        leaf["simulator_wall_clock_ms_std"]  = leaf["latency_ms_std"]
    if method_key in TRUST_SEMANTICS:
        leaf["trust_semantics"] = TRUST_SEMANTICS[method_key]


def stamp_method_keyed(d: dict) -> None:
    """
    {method: {...}} or {method: {param: {...}}}.
    The top-level key is the method; leaves are aggregate dicts.
    """
    for method, inner in d.items():
        if _is_method_leaf(inner):
            _stamp_leaf(inner, method)
        elif isinstance(inner, dict):
            for _, leaf in inner.items():
                if _is_method_leaf(leaf):
                    _stamp_leaf(leaf, method)


def stamp_shortlist(d: dict) -> None:
    """Shortlist sweep: top-level key is M_s. The underlying method is `full`."""
    for _, leaf in d.items():
        if _is_method_leaf(leaf):
            _stamp_leaf(leaf, "full")


def process(path: Path) -> bool:
    data = json.loads(path.read_text())
    name = path.stem
    if name == "shortlist_size":
        stamp_shortlist(data)
    elif name == "trust_transient":
        # This file stores raw time series, not aggregate leaves. No stamp.
        return False
    elif name == "master_summary":
        # Aggregated mixed-schema document; skip to avoid accidental drift.
        return False
    else:
        stamp_method_keyed(data)
    path.write_text(json.dumps(data, indent=2))
    return True


def main() -> None:
    for p in sorted(RESULTS.glob("*.json")):
        if process(p):
            print(f"stamped: {p.relative_to(ROOT)}")
        else:
            print(f"skipped: {p.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
