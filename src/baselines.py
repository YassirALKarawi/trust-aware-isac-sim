"""
Canonical baseline metadata — single source of truth.

Every other module (`run_baseline.py`, `run_all.py`, `synthesize.py`,
`tools/make_figures.py`, `tools/build_figures.py`) and every paper-facing
artefact should consume the definitions in this file rather than duplicating
them. See `docs/PAPER_CODE_ALIGNMENT_AUDIT.md` §1–§2.

`trust_semantics` is either:

    "active"           — the method runs the Bayesian-EWMA TrustProcess and
                         the trust value in the JSON is a genuine posterior;

    "nominal_default"  — the method does not run any trust engine. The
                         trust value in the JSON is a placeholder 1.0
                         emitted by the controller so downstream code can
                         assume a scalar signal exists. It MUST NOT be
                         compared numerically against an active posterior.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class BaselineSpec:
    key: str
    display: str
    trust_semantics: str  # "active" | "nominal_default"
    description: str


# Ordered canonical list — matches Table 3 of the paper.
BASELINE_SPECS = [
    BaselineSpec(
        key="static",
        display="Static ISAC",
        trust_semantics="nominal_default",
        description="Fixed balanced action every slot; no twin, no trust, no screener.",
    ),
    BaselineSpec(
        key="reactive",
        display="Reactive",
        trust_semantics="nominal_default",
        description="Three-preset selector driven by a crude load signal; no trust engine.",
    ),
    BaselineSpec(
        key="dt_only",
        display="DT only",
        trust_semantics="active",
        description="Digital twin + active trust process; no quantum-assisted screening, no gate.",
    ),
    BaselineSpec(
        key="dt_qa",
        display="DT + QA",
        trust_semantics="nominal_default",
        description="Digital twin + QA screener; no trust engine, no gate.",
    ),
    BaselineSpec(
        key="dt_trust",
        display="DT + Trust",
        trust_semantics="active",
        description="Digital twin + active trust process + trust-aware gate; no QA screener.",
    ),
    BaselineSpec(
        key="full",
        display="Full (Proposed)",
        trust_semantics="active",
        description="Full framework: twin + active trust + QA screener + trust-aware gate.",
    ),
]


BASELINE_ORDER = [s.key for s in BASELINE_SPECS]
BASELINE_DISPLAY = {s.key: s.display for s in BASELINE_SPECS}
BASELINE_TRUST_SEMANTICS = {s.key: s.trust_semantics for s in BASELINE_SPECS}


def is_active_trust(method_key: str) -> bool:
    """True iff the method's trust_mean in the JSON is a measured posterior."""
    return BASELINE_TRUST_SEMANTICS.get(method_key) == "active"
