"""
Configuration for the ISAC simulation.
All parameters match the values reported in the paper's System Model.
"""
import numpy as np
from dataclasses import dataclass, field


@dataclass
class SimConfig:
    # Scenario
    area_size_m: float = 1000.0            # 1000 x 1000 m^2
    n_bs: int = 4                          # B
    n_users: int = 40                      # U
    n_targets: int = 10                    # K
    n_ant_per_bs: int = 64                 # 8x8 UPA
    ant_rows: int = 8
    ant_cols: int = 8

    # Radio
    fc_hz: float = 28e9                    # carrier (mmWave)
    bw_hz: float = 100e6                   # bandwidth per BS (comm)
    bw_sense_hz: float = 400e6             # dedicated sensing waveform bandwidth
    c_light: float = 3e8
    p_bs_max_dbm: float = 40.0             # per-BS transmit power
    n0_dbm_hz: float = -174.0              # thermal noise spectral density
    pl_exponent: float = 3.5               # path loss exponent
    shadow_std_db: float = 8.0             # log-normal shadowing std dev
    k_rice_db: float = 6.0                 # Rician K factor
    rho_ar1: float = 0.99                  # temporal correlation coefficient

    # Precoder
    precoder: str = "rzf"                  # "mrt" | "zf" | "rzf"
    rzf_regularisation: float = 1e-3       # Tikhonov factor

    # Hotspot deployment geometry (None = legacy uniform deployment)
    hotspot_radius_m: float = 450.0        # users within this radius of area centre
    target_cluster_radius_m: float = 450.0 # targets within this radius of area centre

    # Slot timing
    slot_ms: float = 10.0                  # near-RT slot
    n_slots: int = 500                     # per simulation run
    n_mc_runs: int = 5                     # Monte Carlo realisations

    # Mobility (pedestrian)
    v_mean_ms: float = 1.2                 # Rayleigh mean
    v_jitter_std_ms: float = 0.15          # per-slot heading innovation

    # Sensing
    p_fa: float = 1e-3                     # false alarm probability
    rcs_mean_m2: float = 1.0               # target radar cross section mean
    clutter_mean_excess_db: float = 10.0   # clutter above thermal noise
    clutter_corr_slots: int = 5            # clutter temporal correlation
    beta_eff_hz: float = 200e6             # effective waveform bandwidth for CRLB
                                           # (tied to dedicated sensing channel)
    n_pulses_cpi: int = 512                # coherent chirps per processing interval
    sensing_duty: float = 0.8              # fraction of slot used for sensing

    # Digital twin
    tau_sync_slots: int = 2                # default synchronisation delay
    obs_noise_std: float = 0.05            # measurement-noise relative std

    # Trust (Bayesian-EWMA)
    alpha_ewma: float = 0.90               # EWMA coefficient
    lambda0: float = 0.0                   # decision tipping threshold
    lambda_clip: float = 3.0               # outlier clip on log-likelihood

    # Quantum-assisted screening
    n_candidates_full: int = 50            # M
    n_shortlist: int = 12                  # M_s

    # Utility weights (rate, sensing, security, energy)
    w_comm: float = 0.40
    w_sense: float = 0.30
    w_sec: float = 0.20
    w_energy: float = 0.10

    # Anomaly injection
    p_anomaly_per_slot: float = 0.04       # base Poisson rate
    anomaly_mean_duration_slots: int = 40  # geometric mean duration
    spoof_noise_mult: float = 10.0         # spoofing variance inflation
    jam_db_rise: float = 15.0              # jamming interference floor rise

    # Trust gate
    trust_floor_safe: float = 0.30         # below this → fallback action only

    # Random seed master
    master_seed: int = 20260417

    def noise_power_per_user_w(self) -> float:
        """Thermal noise power over the user-assigned bandwidth."""
        n0_w_hz = 10 ** ((self.n0_dbm_hz - 30) / 10)
        bw_per_user = self.bw_hz / max(1, self.n_users // self.n_bs)
        return n0_w_hz * bw_per_user

    def p_bs_max_w(self) -> float:
        return 10 ** ((self.p_bs_max_dbm - 30) / 10)

    def lambda_c(self) -> float:
        return self.c_light / self.fc_hz


DEFAULT_CFG = SimConfig()
