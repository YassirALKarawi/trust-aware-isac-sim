"""
Sensing model.
Implements:
  - Neyman-Pearson detection under Swerling-I target model
  - Closed-form P_d(gamma, P_fa) from Swerling 1960
  - CRLB on target-delay estimation (Kay 1993)
  - Correlated clutter process with exponential autocorrelation
"""
import numpy as np
from config import SimConfig


def swerling1_pd(gamma_scnr_lin: float, p_fa: float) -> float:
    """
    Swerling-I detection probability:
        P_d = P_fa ^ (1 / (1 + gamma))
    """
    gamma_scnr_lin = max(gamma_scnr_lin, 1e-6)
    return p_fa ** (1.0 / (1.0 + gamma_scnr_lin))


def crlb_delay(gamma_scnr_lin: float, beta_hz: float) -> float:
    """Cramer-Rao lower bound on target-delay estimation."""
    gamma_scnr_lin = max(gamma_scnr_lin, 1e-6)
    return 1.0 / (8 * np.pi ** 2 * beta_hz ** 2 * gamma_scnr_lin)


def accuracy_proxy(gamma_scnr_lin: float, cfg: SimConfig) -> float:
    """
    Normalised accuracy in [0,1], monotone in SCNR.
    Uses CRLB at SCNR = 0.1 as the floor reference (worst usable case).
    """
    crlb = crlb_delay(gamma_scnr_lin, cfg.beta_eff_hz)
    crlb_ref = crlb_delay(0.1, cfg.beta_eff_hz)  # worst case reference
    return float(np.clip(1.0 - crlb / crlb_ref, 0.0, 1.0))


class ClutterProcess:
    """Correlated Rayleigh-amplitude clutter, per target, per BS."""

    def __init__(self, cfg: SimConfig, rng: np.random.Generator):
        self.cfg = cfg
        self.rng = rng
        # AR(1) clutter with decay constant tau_c
        self.rho_c = np.exp(-1.0 / cfg.clutter_corr_slots)
        # Clutter mean power = thermal_noise * 10^(excess/10)
        n0_w_hz = 10 ** ((cfg.n0_dbm_hz - 30) / 10)
        thermal = n0_w_hz * cfg.bw_hz
        self.clutter_mean = thermal * 10 ** (cfg.clutter_mean_excess_db / 10)
        # State: (n_bs, n_targets) Rayleigh amplitude
        shape = (cfg.n_bs, cfg.n_targets)
        # Start from stationary distribution
        self._amp2 = self.rng.exponential(self.clutter_mean, shape)

    def step(self) -> np.ndarray:
        """Return current clutter power per (BS, target)."""
        innovation = self.rng.exponential(self.clutter_mean, self._amp2.shape)
        self._amp2 = self.rho_c * self._amp2 + (1 - self.rho_c) * innovation
        return self._amp2.copy()


def sensing_power_budget(p_bs_w: float, rho_sense: float) -> float:
    """Fraction of BS power allocated to sensing waveform."""
    return p_bs_w * rho_sense


def scnr_for_target(p_sense_w: float, array_gain: float, rcs_m2: float,
                    distance_m: float, clutter_power_w: float,
                    noise_power_w: float, cfg: SimConfig) -> float:
    """
    SCNR at the matched filter output for a mono-static radar:
      gamma = (P_tx * G_tx * G_rx * lambda^2 * sigma) / ((4pi)^3 * R^4 * (N + C))
    Simplified form using effective array gain.
    """
    lam = cfg.lambda_c()
    num = p_sense_w * array_gain * rcs_m2 * lam ** 2
    den = (4 * np.pi) ** 3 * (distance_m ** 4) * (noise_power_w + clutter_power_w)
    return num / (den + 1e-30)


if __name__ == "__main__":
    cfg = SimConfig()
    rng = np.random.default_rng(cfg.master_seed)

    # Sanity check: Swerling-I
    for g in [0.1, 1.0, 10.0, 100.0]:
        pd = swerling1_pd(g, 1e-3)
        print(f"SCNR={g:>6.1f}: P_d = {pd:.4f}")

    # Single-target SCNR check
    p_tx = cfg.p_bs_max_w() * 0.5  # half power to sensing
    G_array = cfg.n_ant_per_bs * cfg.n_ant_per_bs  # Tx*Rx gain (~4096)
    n0 = 10 ** ((cfg.n0_dbm_hz - 30) / 10) * cfg.bw_hz
    clutter = 10 * n0  # 10 dB above noise

    # Close target at 100 m, far at 500 m
    for d in [50, 100, 300, 600]:
        g = scnr_for_target(p_tx, G_array, 1.0, d, clutter, n0, cfg)
        pd = swerling1_pd(g, 1e-3)
        acc = accuracy_proxy(g, cfg)
        print(f"range={d:>4d} m: SCNR={10*np.log10(g):>5.1f} dB, P_d={pd:.3f}, acc={acc:.3f}")

    # Clutter process
    clutter_proc = ClutterProcess(cfg, rng)
    c0 = clutter_proc.step()
    c1 = clutter_proc.step()
    print(f"\nClutter shape: {c0.shape}, mean: {c0.mean():.2e}, temporal ratio: {np.corrcoef(c0.ravel(), c1.ravel())[0,1]:.3f}")
