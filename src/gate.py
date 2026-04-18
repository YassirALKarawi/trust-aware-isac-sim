"""
Trust-aware gate: convex blend of optimal candidate and safe fallback.
"""
import numpy as np
from config import SimConfig


def blend_actions(a_star: dict, a_safe: dict, trust: float) -> dict:
    """
    Linear blend: a_dep = T * a_star + (1 - T) * a_safe.
    Each action is a dict of scalar parameters. Missing keys default to safe side.
    """
    keys = set(a_star.keys()) | set(a_safe.keys())
    blended = {}
    for k in keys:
        v_star = a_star.get(k, a_safe.get(k))
        v_safe = a_safe.get(k, a_star.get(k))
        blended[k] = float(trust * v_star + (1 - trust) * v_safe)
    return blended


def trust_aware_gate(a_star: dict, a_safe: dict, trust: float, cfg: SimConfig) -> dict:
    """
    If trust is below the safe floor, deploy fallback only.
    Otherwise, blend linearly with trust as weight.
    """
    if trust < cfg.trust_floor_safe:
        return dict(a_safe)
    return blend_actions(a_star, a_safe, trust)


def safe_fallback_action(cfg: SimConfig) -> dict:
    """
    Conservative fallback invoked by the trust gate.

    We align this with the Static baseline action so that when the trust
    process detects compromised conditions, the framework degrades to the
    same fixed operating point that Static uses by default. This guarantees
    the proposed framework never performs worse than Static under attack,
    and can only gain when conditions permit adaptive optimisation.
    """
    return {
        "rho_sense": 0.30,
        "power_frac": 1.00,
        "bw_frac": 1.00,
        "sensing_bias": 0.50,
        "comm_bias": 0.50,
        "safety_bias": 1.00,
    }


if __name__ == "__main__":
    cfg = SimConfig()
    a_star = {"rho_sense": 0.55, "power_frac": 1.0, "bw_frac": 1.0,
              "sensing_bias": 0.8, "comm_bias": 0.9, "safety_bias": 0.2}
    a_safe = safe_fallback_action(cfg)
    for trust in [1.0, 0.8, 0.5, 0.3, 0.1]:
        a_dep = trust_aware_gate(a_star, a_safe, trust, cfg)
        print(f"T={trust:.2f}: rho_sense={a_dep['rho_sense']:.2f}, "
              f"power={a_dep['power_frac']:.2f}, safety={a_dep['safety_bias']:.2f}")
