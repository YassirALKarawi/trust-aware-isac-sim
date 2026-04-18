"""
Quantum-inspired candidate screening.

Classical simulation of the variational-quantum scoring described in the paper:
  - Each candidate action a_i is encoded into a feature vector.
  - A trained scoring map produces a score that ranks candidates.
  - Top-M_s candidates form the shortlist for full utility evaluation.

We keep this classically simulable (as the paper states) since our ansatz is
short-depth and the feature map is data-aligned. The scoring function below
is a deterministic approximation of <phi(a)| U^dagger H U |phi(a)> trained
offline against logged utilities.
"""
import numpy as np
from config import SimConfig


class QuantumScreener:
    """Ranks candidate actions by a trained surrogate score aligned to utility."""

    def __init__(self, cfg: SimConfig, rng: np.random.Generator):
        self.cfg = cfg
        self.rng = rng
        # Learned weights mapping (candidate features, twin-state features, trust) -> score
        # Dim: (n_features, 1). Initialised randomly and refined via the
        # outer-loop training in the main simulator.
        self.n_candidate_features = 8
        self.n_state_features = 6
        self.theta = rng.normal(0, 0.2, self.n_candidate_features + self.n_state_features + 1)
        self.trained = False

    def _feat_candidate(self, candidate: dict) -> np.ndarray:
        """Extract features from a candidate action."""
        return np.array([
            candidate.get("rho_sense", 0.5),
            candidate.get("power_frac", 1.0),
            candidate.get("bw_frac", 1.0),
            candidate.get("n_active_bs", self.cfg.n_bs) / self.cfg.n_bs,
            candidate.get("sensing_bias", 0.5),
            candidate.get("comm_bias", 0.5),
            candidate.get("safety_bias", 0.5),
            1.0,  # bias feature
        ])

    def _feat_state(self, twin_summary: dict, trust: float) -> np.ndarray:
        """Compress twin state + trust into a feature vector."""
        return np.array([
            twin_summary.get("eps_dt", 0.0),
            twin_summary.get("fidelity", 1.0),
            twin_summary.get("avg_channel_gain_db", -100) / 100,
            twin_summary.get("avg_clutter_ratio", 1.0),
            twin_summary.get("user_density", 0.5),
            trust,
        ])

    def score(self, candidate: dict, twin_summary: dict, trust: float) -> float:
        """Deterministic score; higher = better."""
        fc = self._feat_candidate(candidate)
        fs = self._feat_state(twin_summary, trust)
        # Bilinear mix with nonlinearity, emulating expectation-value behaviour
        feat = np.concatenate([fc, fs, [1.0]])
        raw = float(feat @ self.theta)
        return np.tanh(raw) + 0.5 * np.sin(raw * 0.7)

    def shortlist(self, candidates: list, twin_summary: dict, trust: float,
                  n_keep: int = None) -> list:
        """Return top-n_keep candidates ranked by score."""
        if n_keep is None:
            n_keep = self.cfg.n_shortlist
        scored = [(i, self.score(c, twin_summary, trust)) for i, c in enumerate(candidates)]
        scored.sort(key=lambda x: -x[1])
        return [candidates[i] for i, _ in scored[:n_keep]]

    def train_online(self, candidates: list, utilities: list,
                     twin_summary: dict, trust: float, lr: float = 0.02) -> None:
        """
        One online gradient step against (score - utility)^2 loss.
        Matches the outer-loop training in the paper.
        """
        for c, u in zip(candidates, utilities):
            fc = self._feat_candidate(c)
            fs = self._feat_state(twin_summary, trust)
            feat = np.concatenate([fc, fs, [1.0]])
            raw = float(feat @ self.theta)
            pred = np.tanh(raw) + 0.5 * np.sin(raw * 0.7)
            d_pred_d_raw = 1 - np.tanh(raw) ** 2 + 0.35 * np.cos(raw * 0.7)
            grad = 2 * (pred - u) * d_pred_d_raw * feat
            self.theta -= lr * grad
        self.trained = True


if __name__ == "__main__":
    cfg = SimConfig()
    rng = np.random.default_rng(cfg.master_seed)
    qs = QuantumScreener(cfg, rng)

    # Create a set of candidates with varying quality
    candidates = []
    true_util = []
    for i in range(cfg.n_candidates_full):
        c = {
            "rho_sense": rng.uniform(0.2, 0.6),
            "power_frac": rng.uniform(0.5, 1.0),
            "bw_frac": rng.uniform(0.5, 1.0),
            "sensing_bias": rng.uniform(0.0, 1.0),
            "comm_bias": rng.uniform(0.0, 1.0),
            "safety_bias": rng.uniform(0.0, 1.0),
        }
        candidates.append(c)
        # True utility: favours balanced power, reasonable sensing allocation
        u = 0.6 * c["power_frac"] + 0.3 * (1 - abs(c["rho_sense"] - 0.4)) - 0.1 * abs(c["sensing_bias"] - 0.5)
        true_util.append(u + rng.normal(0, 0.02))

    twin_summary = {"eps_dt": 0.05, "fidelity": 0.95}

    # Train screener
    for epoch in range(50):
        qs.train_online(candidates, true_util, twin_summary, trust=1.0)

    # Assess ranking quality
    shortlist = qs.shortlist(candidates, twin_summary, trust=1.0, n_keep=12)
    shortlist_idx = [candidates.index(c) for c in shortlist]
    shortlist_util = [true_util[i] for i in shortlist_idx]
    top12_full = sorted(enumerate(true_util), key=lambda x: -x[1])[:12]
    overlap = len(set(shortlist_idx) & set(i for i, _ in top12_full))
    print(f"Top-12 overlap with ground truth top-12: {overlap}/12")
    print(f"Screener mean utility: {np.mean(shortlist_util):.3f}")
    print(f"Ground-truth top-12 mean utility: {np.mean([u for _, u in top12_full]):.3f}")
