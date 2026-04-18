"""
User mobility model: Rayleigh velocities, random headings, per-slot jitter.
"""
import numpy as np
from config import SimConfig


class MobilityModel:
    def __init__(self, cfg: SimConfig, rng: np.random.Generator):
        self.cfg = cfg
        self.rng = rng
        # Initial positions uniform in area
        self.pos = rng.uniform(0, cfg.area_size_m, (cfg.n_users, 2))
        # Rayleigh velocity magnitudes (scale = v_mean / sqrt(pi/2))
        scale = cfg.v_mean_ms / np.sqrt(np.pi / 2)
        speeds = rng.rayleigh(scale, cfg.n_users)
        headings = rng.uniform(0, 2 * np.pi, cfg.n_users)
        self.vel = np.stack([speeds * np.cos(headings), speeds * np.sin(headings)], axis=1)

    def step(self) -> np.ndarray:
        dt = self.cfg.slot_ms / 1000.0
        # Position innovation eta_u drawn per slot (paper's equation 2)
        eta = self.rng.normal(0, self.cfg.v_jitter_std_ms, self.pos.shape)
        # Update position with velocity drift plus innovation
        self.pos = self.pos + self.vel * dt + eta
        # Reflect off boundaries (simple elastic)
        for d in range(2):
            hit_low = self.pos[:, d] < 0
            hit_hi = self.pos[:, d] > self.cfg.area_size_m
            self.pos[hit_low, d] = -self.pos[hit_low, d]
            self.pos[hit_hi, d] = 2 * self.cfg.area_size_m - self.pos[hit_hi, d]
            self.vel[hit_low | hit_hi, d] *= -1
        return self.pos.copy()


if __name__ == "__main__":
    cfg = SimConfig()
    rng = np.random.default_rng(cfg.master_seed)
    m = MobilityModel(cfg, rng)
    pos0 = m.pos.copy()
    for _ in range(100):
        m.step()
    speeds = np.linalg.norm(m.vel, axis=1)
    print(f"After 100 slots (1.0 s):")
    print(f"  Displacement mean: {np.linalg.norm(m.pos - pos0, axis=1).mean():.2f} m")
    print(f"  Speed mean: {speeds.mean():.2f} m/s  (target {cfg.v_mean_ms})")
    print(f"  Position in bounds: {(m.pos >= 0).all() and (m.pos <= cfg.area_size_m).all()}")
