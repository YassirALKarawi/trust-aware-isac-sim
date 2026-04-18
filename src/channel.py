"""
Physical channel model.
Implements:
  - correlated Rician fading with AR(1) temporal evolution (Clarke 1968 / Jakes)
  - 8x8 UPA steering vector
  - log-normal shadowing
  - path loss (simplified close-in model)
"""
import numpy as np
from config import SimConfig


def steering_vector(theta: float, phi: float, cfg: SimConfig) -> np.ndarray:
    """Steering vector for an 8x8 UPA with half-wavelength spacing."""
    dx = dy = cfg.lambda_c() / 2.0
    n_rows, n_cols = cfg.ant_rows, cfg.ant_cols
    # x-direction phase gradient (azimuth component)
    m = np.arange(n_cols)
    a_x = np.exp(1j * 2 * np.pi * m * dx * np.sin(theta) * np.cos(phi) / cfg.lambda_c())
    # y-direction phase gradient (elevation component)
    k = np.arange(n_rows)
    a_y = np.exp(1j * 2 * np.pi * k * dy * np.sin(theta) * np.sin(phi) / cfg.lambda_c())
    # kron returns length n_rows*n_cols = 64
    return np.kron(a_x, a_y) / np.sqrt(n_rows * n_cols)


def path_loss_db(distance_m: float, cfg: SimConfig, shadow_db: float = 0.0) -> float:
    """Close-in reference-distance path loss, dB."""
    d0 = 1.0  # 1 m reference
    fspl_d0 = 20 * np.log10(4 * np.pi * d0 / cfg.lambda_c())
    return fspl_d0 + 10 * cfg.pl_exponent * np.log10(distance_m / d0) + shadow_db


def path_loss_linear(distance_m: float, cfg: SimConfig, shadow_db: float = 0.0) -> float:
    pl_db = path_loss_db(distance_m, cfg, shadow_db)
    return 10 ** (-pl_db / 10)


class RicianAR1ChannelBank:
    """
    Maintains an (n_bs x n_users) tensor of Rician channel vectors over time.
    Each channel is a sum of a deterministic LoS steering component and an
    NLoS scattered component that evolves via an AR(1) recursion.
    """

    def __init__(self, cfg: SimConfig, rng: np.random.Generator):
        self.cfg = cfg
        self.rng = rng
        self.N_t = cfg.n_ant_per_bs
        self.n_bs = cfg.n_bs
        self.n_users = cfg.n_users
        # Rician K factor linear
        self.K_R = 10 ** (cfg.k_rice_db / 10)
        # Scattered component (NLoS) state — complex Gaussian, shape (n_bs, n_users, N_t)
        self._h_nlos = (
            self.rng.standard_normal((self.n_bs, self.n_users, self.N_t))
            + 1j * self.rng.standard_normal((self.n_bs, self.n_users, self.N_t))
        ) / np.sqrt(2)
        self.rho = cfg.rho_ar1

    def evolve(self) -> None:
        """One-step AR(1) update of the scattered component."""
        innovation = (
            self.rng.standard_normal(self._h_nlos.shape)
            + 1j * self.rng.standard_normal(self._h_nlos.shape)
        ) / np.sqrt(2)
        self._h_nlos = self.rho * self._h_nlos + np.sqrt(1 - self.rho ** 2) * innovation

    def channel(self, bs_pos, user_pos, shadow_db) -> np.ndarray:
        """
        Return full Rician channel tensor (n_bs, n_users, N_t) for given geometry.
        bs_pos: (n_bs, 2), user_pos: (n_users, 2), shadow_db: (n_bs, n_users)
        """
        K = self.K_R
        H = np.zeros((self.n_bs, self.n_users, self.N_t), dtype=complex)
        for b in range(self.n_bs):
            for u in range(self.n_users):
                dx = user_pos[u, 0] - bs_pos[b, 0]
                dy = user_pos[u, 1] - bs_pos[b, 1]
                dist = np.sqrt(dx * dx + dy * dy) + 1.0  # avoid zero
                theta = np.arctan2(dy, dx)  # azimuth
                phi = 0.0                    # elevation (users at ground level)
                a_los = steering_vector(theta, phi, self.cfg) * np.sqrt(self.N_t)
                pl = np.sqrt(path_loss_linear(dist, self.cfg, shadow_db[b, u]))
                h_det = np.sqrt(K / (K + 1)) * a_los
                h_sca = np.sqrt(1 / (K + 1)) * self._h_nlos[b, u]
                H[b, u] = pl * (h_det + h_sca)
        return H


def compute_sinr(H: np.ndarray, W: np.ndarray, noise_power: float, assoc: np.ndarray) -> np.ndarray:
    """
    SINR for each user under MRT precoding.
    H: (n_bs, n_users, N_t) channel tensor
    W: (n_bs, n_users, N_t) precoder tensor (non-zero only for associated users)
    assoc: (n_users,) mapping user -> serving BS
    noise_power: scalar thermal noise power
    returns: (n_users,) SINR linear
    """
    n_bs, n_users, N_t = H.shape
    sinr = np.zeros(n_users)
    for u in range(n_users):
        b_serve = assoc[u]
        # Useful signal power
        useful = np.abs(np.vdot(H[b_serve, u], W[b_serve, u])) ** 2
        # Interference: all other (user,BS) precoders seen through u's channel
        interf = 0.0
        for b in range(n_bs):
            for j in range(n_users):
                if (j == u) and (b == b_serve):
                    continue
                interf += np.abs(np.vdot(H[b, u], W[b, j])) ** 2
        sinr[u] = useful / (interf + noise_power + 1e-20)
    return sinr


if __name__ == "__main__":
    # Smoke test
    cfg = SimConfig()
    rng = np.random.default_rng(cfg.master_seed)
    bank = RicianAR1ChannelBank(cfg, rng)
    bs_pos = rng.uniform(0, cfg.area_size_m, (cfg.n_bs, 2))
    user_pos = rng.uniform(0, cfg.area_size_m, (cfg.n_users, 2))
    shadow_db = rng.normal(0, cfg.shadow_std_db, (cfg.n_bs, cfg.n_users))
    H = bank.channel(bs_pos, user_pos, shadow_db)
    print(f"Channel tensor shape: {H.shape}")
    print(f"Channel gain range (dB): {10*np.log10(np.mean(np.abs(H)**2, axis=-1).ravel()).min():.1f} to {10*np.log10(np.mean(np.abs(H)**2, axis=-1).ravel()).max():.1f}")
    # Evolve one step
    bank.evolve()
    H2 = bank.channel(bs_pos, user_pos, shadow_db)
    # Correlation check
    corr = np.abs(np.vdot(H[0,0], H2[0,0])) / (np.linalg.norm(H[0,0]) * np.linalg.norm(H2[0,0]))
    print(f"Temporal correlation (should be close to rho={cfg.rho_ar1}): {corr:.3f}")
