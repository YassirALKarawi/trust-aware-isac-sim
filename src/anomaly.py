"""
Anomaly injection: jamming, spoofing, and mixed scenarios.
Poisson-distributed onset, geometrically-distributed duration.
"""
import numpy as np
from config import SimConfig


class AnomalyInjector:
    def __init__(self, cfg: SimConfig, rng: np.random.Generator, p_anom: float = None):
        self.cfg = cfg
        self.rng = rng
        self.p_anom = cfg.p_anomaly_per_slot if p_anom is None else p_anom
        self.active = None          # current anomaly type or None
        self.remaining = 0          # slots left in current episode
        self.kinds = ["jamming", "spoofing", "mixed"]

    def step(self) -> dict:
        """
        Returns a dict describing the anomaly state for this slot:
          {kind, jam_db_rise, spoof_fraction, signal_strength in [0,1]}
        """
        if self.remaining == 0:
            # No active anomaly; maybe trigger a new one
            if self.rng.random() < self.p_anom:
                self.active = self.rng.choice(self.kinds)
                mean_dur = self.cfg.anomaly_mean_duration_slots
                self.remaining = max(1, int(self.rng.geometric(1.0 / mean_dur)))
            else:
                self.active = None
        # Build effect dict
        if self.active is None:
            return {"kind": None, "jam_db_rise": 0.0,
                    "spoof_fraction": 0.0, "signal_strength": 0.0}
        self.remaining -= 1
        # Intensity envelope: ramp up then decay
        inten = 1.0
        eff = {"kind": self.active, "jam_db_rise": 0.0,
               "spoof_fraction": 0.0, "signal_strength": inten}
        if self.active == "jamming":
            eff["jam_db_rise"] = self.cfg.jam_db_rise
        elif self.active == "spoofing":
            eff["spoof_fraction"] = 0.25
        elif self.active == "mixed":
            eff["jam_db_rise"] = 0.5 * self.cfg.jam_db_rise
            eff["spoof_fraction"] = 0.15
        return eff


if __name__ == "__main__":
    cfg = SimConfig()
    rng = np.random.default_rng(cfg.master_seed)
    ai = AnomalyInjector(cfg, rng, p_anom=0.05)
    hits = {"jamming": 0, "spoofing": 0, "mixed": 0, None: 0}
    total_active = 0
    for t in range(500):
        eff = ai.step()
        hits[eff["kind"]] = hits.get(eff["kind"], 0) + 1
        if eff["kind"] is not None:
            total_active += 1
    print(f"Active slots: {total_active}/500 ({100*total_active/500:.1f}%)")
    print(f"Kind distribution: {hits}")
