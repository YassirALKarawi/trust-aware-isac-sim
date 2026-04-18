"""
Digital twin with synchronisation delay and observation noise.
Maintains a filtered estimate of user positions and per-link channel gains.
Mismatch tracks the difference between physical and estimated state.
"""
import numpy as np
from collections import deque
from config import SimConfig


class DigitalTwin:
    def __init__(self, cfg: SimConfig, rng: np.random.Generator):
        self.cfg = cfg
        self.rng = rng
        self.tau = cfg.tau_sync_slots
        # Delayed telemetry buffer — stores (positions, channel_gains) snapshots
        self._telemetry_buffer: deque = deque(maxlen=max(1, self.tau + 2))
        # Twin state
        self.pos_hat = None  # estimated user positions
        self.gain_hat = None  # estimated channel gain magnitude per (bs, user)
        # Predicted one-step
        self.pos_pred = None
        self.vel_est = None  # velocity estimate for prediction step
        self._initialised = False

    def ingest(self, true_pos: np.ndarray, true_gain: np.ndarray) -> None:
        """
        Accept current-slot ground truth. Digital twin will use this with tau_sync delay.
        true_pos: (n_users, 2)
        true_gain: (n_bs, n_users) — |h|^2 mean across antennas
        """
        # Add Gaussian observation noise
        pos_obs = true_pos + self.rng.normal(
            0, self.cfg.obs_noise_std * self.cfg.area_size_m / 100, true_pos.shape
        )
        gain_obs = true_gain * np.exp(
            self.rng.normal(0, self.cfg.obs_noise_std, true_gain.shape)
        )
        self._telemetry_buffer.append((pos_obs.copy(), gain_obs.copy()))

    def apply_spoofing(self, fraction: float, multiplier: float) -> None:
        """Corrupt the most recent telemetry as a spoofing attack."""
        if len(self._telemetry_buffer) == 0:
            return
        pos_obs, gain_obs = self._telemetry_buffer[-1]
        n_users = pos_obs.shape[0]
        n_corrupt = int(n_users * fraction)
        if n_corrupt == 0:
            return
        idx = self.rng.choice(n_users, n_corrupt, replace=False)
        # Corrupt position by a substantial fraction of the deployment area
        # so that the affected users' steering vectors are materially wrong.
        # Displacement std = fraction_area * area_size, e.g. 0.05 * 1000 = 50 m.
        pos_std = 0.05 * multiplier * self.cfg.area_size_m / 10
        pos_obs[idx] += self.rng.normal(0, pos_std, (n_corrupt, 2))
        # Corrupt gain
        if gain_obs.ndim == 2:
            noise = self.rng.normal(
                0, 0.5 * multiplier * self.cfg.obs_noise_std,
                (gain_obs.shape[0], n_corrupt)
            )
            gain_obs[:, idx] *= np.exp(noise)
        else:
            noise = self.rng.normal(0, 0.5 * multiplier * self.cfg.obs_noise_std, n_corrupt)
            gain_obs[idx] *= np.exp(noise)
        self._telemetry_buffer[-1] = (pos_obs, gain_obs)

    def step(self) -> None:
        """
        Advance twin by one slot. Uses telemetry from tau slots ago, predicts forward
        to current slot with linear motion model.
        """
        if len(self._telemetry_buffer) == 0:
            return
        # Pull delayed telemetry if available
        if len(self._telemetry_buffer) > self.tau:
            pos_delayed, gain_delayed = self._telemetry_buffer[-self.tau - 1]
        else:
            pos_delayed, gain_delayed = self._telemetry_buffer[0]
        # Kalman-like update: blend prediction with delayed measurement
        # (simple alpha-blend since we're not maintaining full covariance for speed)
        alpha_k = 0.7  # fixed gain for filtering; higher = more weight to measurement
        if not self._initialised:
            self.pos_hat = pos_delayed.copy()
            self.gain_hat = gain_delayed.copy()
            self.vel_est = np.zeros_like(pos_delayed)
            self._initialised = True
        else:
            # Velocity estimate from successive delayed snapshots
            if len(self._telemetry_buffer) > self.tau + 1:
                pos_prev, _ = self._telemetry_buffer[-self.tau - 2]
                self.vel_est = (pos_delayed - pos_prev) / (self.cfg.slot_ms / 1000.0)
            # Propagate to current slot with motion model
            propagated = pos_delayed + self.vel_est * (self.tau * self.cfg.slot_ms / 1000.0)
            self.pos_hat = (1 - alpha_k) * self.pos_hat + alpha_k * propagated
            self.gain_hat = (1 - alpha_k) * self.gain_hat + alpha_k * gain_delayed

    def mismatch(self, true_pos: np.ndarray, true_gain: np.ndarray) -> float:
        """Normalised twin mismatch epsilon_DT(t)."""
        if not self._initialised:
            return 1.0
        num = np.linalg.norm(true_pos - self.pos_hat) + np.linalg.norm(
            np.log(true_gain + 1e-30) - np.log(np.abs(self.gain_hat) + 1e-30)
        )
        den = np.linalg.norm(true_pos) + np.linalg.norm(np.log(true_gain + 1e-30)) + 1.0
        return float(num / den)

    def fidelity(self, eps_dt: float, kappa: float = 2.0) -> float:
        """F_DT(t) = exp(-kappa * eps_DT)."""
        return float(np.exp(-kappa * eps_dt))


if __name__ == "__main__":
    cfg = SimConfig()
    rng = np.random.default_rng(cfg.master_seed)
    dt = DigitalTwin(cfg, rng)
    # Fake ground truth trajectory
    pos = np.random.uniform(0, cfg.area_size_m, (cfg.n_users, 2))
    gain = np.random.exponential(1e-9, (cfg.n_bs, cfg.n_users))
    eps_trace = []
    for t in range(20):
        dt.ingest(pos, gain)
        dt.step()
        eps = dt.mismatch(pos, gain)
        eps_trace.append(eps)
        # Move a little
        pos += rng.normal(0, 0.1, pos.shape)
    print(f"Mismatch trace over 20 slots: first={eps_trace[0]:.3f}, last={eps_trace[-1]:.3f}")
    print(f"Fidelity (last): F_DT = {dt.fidelity(eps_trace[-1]):.3f}")
