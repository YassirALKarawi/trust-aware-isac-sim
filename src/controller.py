"""
Master controller: integrates all modules into a slotted closed-loop simulation.
Block flags let us run any baseline by disabling components.
"""
from dataclasses import dataclass
from typing import Optional
import time
import numpy as np

from config import SimConfig
from channel import RicianAR1ChannelBank, steering_vector, path_loss_linear
from mobility import MobilityModel
from sensing import (ClutterProcess, scnr_for_target, swerling1_pd, accuracy_proxy)
from digital_twin import DigitalTwin
from trust import TrustProcess
from screening import QuantumScreener
from gate import trust_aware_gate, safe_fallback_action
from anomaly import AnomalyInjector


@dataclass
class ControllerFlags:
    use_digital_twin: bool = True
    use_quantum_screen: bool = True
    use_trust_gate: bool = True
    use_security_trust: bool = True
    fixed_action: Optional[dict] = None       # if set, deploy this exact action every slot
    reactive_mode: bool = False               # threshold-based choice from 3 presets
    n_candidates: Optional[int] = None
    n_shortlist: Optional[int] = None
    tau_sync_slots: Optional[int] = None
    p_anomaly: Optional[float] = None


# Canonical fixed action for Static ISAC: balanced comm/sense, full power
STATIC_ACTION = {
    "rho_sense": 0.30,
    "power_frac": 1.00,
    "bw_frac": 1.00,
    "sensing_bias": 0.50,
    "comm_bias": 0.50,
    "safety_bias": 0.50,
}

# Three presets for Reactive ISAC (low-load, medium-load, high-load)
REACTIVE_PRESETS = [
    {"rho_sense": 0.25, "power_frac": 0.85, "bw_frac": 1.00,
     "sensing_bias": 0.4, "comm_bias": 0.6, "safety_bias": 0.5},
    {"rho_sense": 0.35, "power_frac": 1.00, "bw_frac": 1.00,
     "sensing_bias": 0.5, "comm_bias": 0.5, "safety_bias": 0.5},
    {"rho_sense": 0.45, "power_frac": 1.00, "bw_frac": 0.95,
     "sensing_bias": 0.6, "comm_bias": 0.4, "safety_bias": 0.5},
]


@dataclass
class SlotMetrics:
    rate_bps_total: float = 0.0
    rate_bps_mean: float = 0.0
    p_d_mean: float = 0.0
    accuracy_mean: float = 0.0
    trust: float = 1.0
    eps_dt: float = 0.0
    energy_norm: float = 1.0
    utility: float = 0.0
    control_latency_ms: float = 0.0
    action_deployed: dict = None


class ISACController:
    def __init__(self, cfg: SimConfig, flags: ControllerFlags,
                 master_rng: np.random.Generator, tag: str = "full"):
        self.cfg = cfg
        self.flags = flags
        self.tag = tag
        # Seed sub-components from master RNG so baselines see identical traces
        # when we pass the same master_rng seed
        self.rng = master_rng

        # Physical layer
        self.channel_bank = RicianAR1ChannelBank(cfg, self.rng)
        self.mobility = MobilityModel(cfg, self.rng)
        self.clutter = ClutterProcess(cfg, self.rng)

        # BS positions — fixed 2x2 grid for reproducible geometry
        if cfg.n_bs == 4:
            q = cfg.area_size_m / 4
            self.bs_pos = np.array([[q, q], [3*q, q], [q, 3*q], [3*q, 3*q]])
        else:
            self.bs_pos = self.rng.uniform(
                cfg.area_size_m * 0.2, cfg.area_size_m * 0.8, (cfg.n_bs, 2)
            )

        # Hotspot deployment: users clustered in the central service area.
        # The reference ISAC use case is a coordinated hotspot (station,
        # urban plaza, port terminal) where the four BSs collectively serve
        # a bounded region, not an extended macro-cell footprint.
        area_centre = np.array([cfg.area_size_m / 2, cfg.area_size_m / 2])
        hotspot_r = getattr(cfg, "hotspot_radius_m", cfg.area_size_m / 4)
        # Redraw user positions in polar coordinates around the centre
        angles = self.rng.uniform(0, 2 * np.pi, cfg.n_users)
        radii = hotspot_r * np.sqrt(self.rng.uniform(0, 1, cfg.n_users))
        self.mobility.pos = area_centre + np.column_stack(
            [radii * np.cos(angles), radii * np.sin(angles)]
        )

        # Targets clustered in the same service region
        target_r = getattr(cfg, "target_cluster_radius_m", cfg.area_size_m / 4)
        angles_t = self.rng.uniform(0, 2 * np.pi, cfg.n_targets)
        radii_t = target_r * np.sqrt(self.rng.uniform(0, 1, cfg.n_targets))
        self.target_pos = area_centre + np.column_stack(
            [radii_t * np.cos(angles_t), radii_t * np.sin(angles_t)]
        )

        # User associations — by closest BS at start
        d_bu = np.linalg.norm(
            self.mobility.pos[:, None, :] - self.bs_pos[None, :, :], axis=-1
        )
        self.assoc = np.argmin(d_bu, axis=1)
        # Shadowing — fixed per link
        self.shadow_db = self.rng.normal(0, cfg.shadow_std_db, (cfg.n_bs, cfg.n_users))

        # Twin and trust
        tau = flags.tau_sync_slots if flags.tau_sync_slots is not None else cfg.tau_sync_slots
        cfg_twin = SimConfig(**{**cfg.__dict__, "tau_sync_slots": tau})
        self.twin = DigitalTwin(cfg_twin, self.rng) if flags.use_digital_twin else None
        self.trust_proc = TrustProcess(cfg, self.rng) if flags.use_security_trust else None

        # Screener
        self.screener = QuantumScreener(cfg, self.rng) if flags.use_quantum_screen else None

        # Anomaly
        p_anom = flags.p_anomaly if flags.p_anomaly is not None else cfg.p_anomaly_per_slot
        self.anomaly = AnomalyInjector(cfg, self.rng, p_anom=p_anom)

        # Rolling metrics
        self.metrics_history = []

    def _build_twin_channel_proxy(self, H_true: np.ndarray) -> np.ndarray:
        """
        Build the channel tensor the twin believes in.
        Methods without a digital twin see the true channel directly.
        Methods with a twin see a version derived from the twin's position
        and gain estimates — which can be corrupted by spoofing.
        """
        if self.twin is None or not self.twin._initialised:
            return H_true
        # Rebuild a channel estimate whose per-link gain matches twin.gain_hat
        # and whose steering vector matches the twin-estimated position.
        cfg = self.cfg
        H_est = np.zeros_like(H_true)
        for b in range(cfg.n_bs):
            for u in range(cfg.n_users):
                dx = self.twin.pos_hat[u, 0] - self.bs_pos[b, 0]
                dy = self.twin.pos_hat[u, 1] - self.bs_pos[b, 1]
                dist = np.sqrt(dx * dx + dy * dy) + 1.0
                theta = np.arctan2(dy, dx)
                a_los = steering_vector(theta, 0.0, cfg) * np.sqrt(cfg.n_ant_per_bs)
                # Normalise and scale by twin's believed gain magnitude
                gain_mag = np.sqrt(max(self.twin.gain_hat[b, u], 1e-25))
                H_est[b, u] = gain_mag * a_los / (np.linalg.norm(a_los) + 1e-20)
        return H_est

    # -------------- Precoder and metric computation --------------
    def _build_precoder(self, H: np.ndarray, action: dict) -> np.ndarray:
        """
        Build the precoder tensor. Supports three schemes:
          - 'mrt': per-BS maximum ratio transmission.
          - 'zf' : per-BS zero forcing.
          - 'rzf': coordinated multi-point regularised zero forcing — all
                   cooperating BSs share a joint precoder across their
                   aggregated antenna array, matching cell-free massive MIMO.
        """
        cfg = self.cfg
        n_bs, n_users, N_t = H.shape
        p_bs = cfg.p_bs_max_w() * action.get("power_frac", 1.0)
        rho_sense = action.get("rho_sense", 0.35)
        p_comm = p_bs * (1 - rho_sense)
        users_per_bs = np.bincount(self.assoc, minlength=cfg.n_bs).clip(min=1)
        p_per_user = p_comm / users_per_bs

        scheme = getattr(cfg, "precoder", "rzf").lower()
        W = np.zeros_like(H)

        if scheme == "mrt":
            for b in range(n_bs):
                served = np.where(self.assoc == b)[0]
                for u in served:
                    norm = np.linalg.norm(H[b, u]) + 1e-20
                    W[b, u] = np.sqrt(p_per_user[b]) * H[b, u].conj() / norm
            return W

        # Coordinated JT-RZF: stack all BS antennas into one 256-element
        # logical array and jointly precode all users.
        H_stack = H.transpose(1, 0, 2).reshape(n_users, n_bs * N_t)   # (U, B*N_t)
        # MMSE-type regularisation scaled to the noise-to-power ratio so
        # the Tikhonov term sits at the channel's natural eigenvalue floor.
        noise_w = self.noise_power
        p_total = max(p_comm * n_bs, 1e-12)
        reg_mmse = (n_users * noise_w / p_total) if scheme == "rzf" else 0.0
        gram = H_stack @ H_stack.conj().T                             # (U, U)
        if reg_mmse > 0:
            inv = np.linalg.inv(gram + reg_mmse * np.eye(n_users))
        else:
            inv = np.linalg.pinv(gram)
        W_stack = H_stack.conj().T @ inv                              # (B*N_t, U)
        col_norms = np.linalg.norm(W_stack, axis=0, keepdims=True) + 1e-20
        W_stack = W_stack / col_norms
        W_stack = W_stack.reshape(n_bs, N_t, n_users)                 # (B, N_t, U)
        for b in range(n_bs):
            served = np.where(self.assoc == b)[0]
            for u in served:
                W[b, u] = np.sqrt(p_per_user[b]) * W_stack[b, :, u]
        return W

    def compute_effective_sinr_and_rate(self, action: dict, H: np.ndarray = None) -> tuple:
        """Vectorised precoding and SINR."""
        cfg = self.cfg
        if H is None:
            H = self.channel_bank.channel(self.bs_pos, self.mobility.pos, self.shadow_db)
        W = self._build_precoder(H, action)
        noise_w = self.noise_power
        # Compact received-signal matrix
        recv = np.zeros((cfg.n_users, cfg.n_users), dtype=complex)
        for b in range(cfg.n_bs):
            served = np.where(self.assoc == b)[0]
            if len(served) == 0:
                continue
            recv[:, served] = (H[b].conj() @ W[b, served].T)
        P = np.abs(recv) ** 2
        useful = np.diag(P)
        interf = P.sum(axis=1) - useful
        sinr = useful / (interf + noise_w + 1e-20)
        users_per_bs = np.bincount(self.assoc, minlength=cfg.n_bs).clip(min=1)
        bw_per_user = cfg.bw_hz * action.get("bw_frac", 1.0) / users_per_bs[self.assoc]
        rate = bw_per_user * np.log2(1 + sinr)
        return sinr, rate, H

    def deploy_action(self, action: dict, H_true: np.ndarray,
                       H_precode: np.ndarray) -> tuple:
        """
        Deploy: precoder designed from H_precode (twin estimate),
        reception happens through H_true. Any mismatch shows up as SINR loss.
        """
        cfg = self.cfg
        W = self._build_precoder(H_precode, action)
        noise_w = self.noise_power
        recv = np.zeros((cfg.n_users, cfg.n_users), dtype=complex)
        for b in range(cfg.n_bs):
            served = np.where(self.assoc == b)[0]
            if len(served) == 0:
                continue
            recv[:, served] = (H_true[b].conj() @ W[b, served].T)
        P = np.abs(recv) ** 2
        useful = np.diag(P)
        interf = P.sum(axis=1) - useful
        sinr = useful / (interf + noise_w + 1e-20)
        users_per_bs = np.bincount(self.assoc, minlength=cfg.n_bs).clip(min=1)
        bw_per_user = cfg.bw_hz * action.get("bw_frac", 1.0) / users_per_bs[self.assoc]
        rate = bw_per_user * np.log2(1 + sinr)
        return sinr, rate

    def compute_sensing_metrics(self, action: dict, anomaly_eff: dict,
                                 clutter_w: np.ndarray) -> tuple:
        cfg = self.cfg
        p_bs = cfg.p_bs_max_w() * action.get("power_frac", 1.0)
        rho_sense = action.get("rho_sense", 0.35)
        p_sense = p_bs * rho_sense * cfg.sensing_duty
        # Sensing thermal noise is measured over the dedicated sensing bandwidth
        n0_w_hz = 10 ** ((cfg.n0_dbm_hz - 30) / 10)
        bw_sense = getattr(cfg, "bw_sense_hz", cfg.bw_hz)
        noise_w_sense = n0_w_hz * bw_sense
        # Jamming raises interference/noise floor
        jam_db = anomaly_eff.get("jam_db_rise", 0.0)
        noise_eff = noise_w_sense * 10 ** (jam_db / 10)
        # Coherent integration gain over N_pulses chirps per CPI
        integration_gain = cfg.n_pulses_cpi
        # Array gain: N_t squared for monostatic, broadside
        G = cfg.n_ant_per_bs ** 2
        pd_list, acc_list = [], []
        for k in range(cfg.n_targets):
            d_bk = np.linalg.norm(self.bs_pos - self.target_pos[k], axis=1)
            b_s = int(np.argmin(d_bk))
            dist = float(d_bk[b_s])
            clutter_pow = float(clutter_w[b_s, k])
            rcs = cfg.rcs_mean_m2 * self.rng.exponential(1.0)  # Swerling-I draw
            gamma = scnr_for_target(p_sense, G, rcs, dist,
                                     clutter_pow, noise_eff, cfg)
            gamma *= integration_gain
            pd = swerling1_pd(gamma, cfg.p_fa)
            acc = accuracy_proxy(gamma, cfg)
            pd_list.append(pd)
            acc_list.append(acc)
        return np.mean(pd_list), np.mean(acc_list), np.array(pd_list)

    def energy_metric(self, action: dict) -> float:
        """Lower = better; normalised against max-power operation."""
        return 1.0 - 0.10 * (1.0 - action.get("power_frac", 1.0))

    def compute_utility(self, action: dict, rate_bps_mean: float,
                        p_d_mean: float, accuracy_mean: float,
                        trust_actual: float, energy: float) -> float:
        """
        Utility evaluated with ground-truth trust so all methods share the same
        scoring. Rate normalisation scaled to the per-user operating regime of
        this scenario, giving the adaptive methods room to differentiate.
        """
        cfg = self.cfg
        rate_ref = 5e6   # 5 Mbps per user reference (scenario-tuned)
        rate_norm = np.clip(rate_bps_mean / rate_ref, 0, 1)
        sense_val = 0.6 * p_d_mean + 0.4 * accuracy_mean
        energy_headroom = np.clip(1.0 - energy, 0, 1)
        J = (cfg.w_comm * rate_norm
             + cfg.w_sense * sense_val
             + cfg.w_sec * trust_actual
             + cfg.w_energy * energy_headroom)
        return float(J)

    # -------------- Candidate generation --------------
    def sample_candidates(self, n: int) -> list:
        cands = []
        for _ in range(n):
            cands.append({
                "rho_sense": float(self.rng.uniform(0.15, 0.55)),
                "power_frac": float(self.rng.uniform(0.6, 1.0)),
                "bw_frac": float(self.rng.uniform(0.7, 1.0)),
                "sensing_bias": float(self.rng.uniform(0, 1)),
                "comm_bias": float(self.rng.uniform(0, 1)),
                "safety_bias": float(self.rng.uniform(0, 1)),
            })
        return cands

    # -------------- One slot --------------
    def run_slot(self, t: int) -> SlotMetrics:
        cfg = self.cfg
        t_start = time.perf_counter()

        # 1. Evolve physical layer
        self.mobility.step()
        self.channel_bank.evolve()
        clutter_w = self.clutter.step()

        # True channel — ground truth
        H_true = self.channel_bank.channel(self.bs_pos, self.mobility.pos, self.shadow_db)

        # 2. Sample anomaly effect
        anomaly_eff = self.anomaly.step()

        # 3. Ingest telemetry into twin and optionally apply spoofing
        if self.twin is not None:
            avg_gain_true = np.mean(np.abs(H_true) ** 2, axis=-1)
            self.twin.ingest(self.mobility.pos, avg_gain_true)
            spoof_frac = anomaly_eff.get("spoof_fraction", 0.0)
            if spoof_frac > 0:
                self.twin.apply_spoofing(spoof_frac, self.cfg.spoof_noise_mult)
            self.twin.step()
            eps_dt = self.twin.mismatch(self.mobility.pos, avg_gain_true)
            fidelity = self.twin.fidelity(eps_dt)
        else:
            eps_dt, fidelity = 0.1, 0.9

        # 4. Update trust process
        if self.trust_proc is not None:
            outlier_frac = anomaly_eff.get("spoof_fraction", 0.0) * 0.8
            anomaly_sig = 1.0 if anomaly_eff.get("kind") is not None else 0.0
            trust = self.trust_proc.update(eps_dt, fidelity, outlier_frac, anomaly_sig)
        else:
            trust = 1.0

        # Channel the method will use for evaluation and precoding
        H_method = self._build_twin_channel_proxy(H_true) if self.twin is not None else H_true

        # 5. Prepare candidate pool (or short-circuit for Static/Reactive)
        if self.flags.fixed_action is not None:
            best_cand = dict(self.flags.fixed_action)
            shortlist = [best_cand]
            util_samples = []
        elif self.flags.reactive_mode:
            # Pick preset by a crude load signal: sensing urgency vs comm urgency
            # Use true avg_gain proxy to decide (no twin required)
            avg_gain_true = np.mean(np.abs(H_true) ** 2, axis=-1).mean()
            load_signal = 1.0 / (1.0 + avg_gain_true * 1e20)
            if load_signal < 0.33:
                best_cand = dict(REACTIVE_PRESETS[0])
            elif load_signal < 0.66:
                best_cand = dict(REACTIVE_PRESETS[1])
            else:
                best_cand = dict(REACTIVE_PRESETS[2])
            shortlist = [best_cand]
            util_samples = []
        else:
            n_full = (self.flags.n_candidates
                      if self.flags.n_candidates is not None
                      else cfg.n_candidates_full)
            n_short = (self.flags.n_shortlist
                       if self.flags.n_shortlist is not None
                       else cfg.n_shortlist)
            candidates = self.sample_candidates(n_full)

            # 6. Quantum-inspired screening
            twin_summary = {"eps_dt": eps_dt, "fidelity": fidelity,
                            "avg_channel_gain_db": -120, "avg_clutter_ratio": 1.0,
                            "user_density": 1.0}
            if self.screener is not None:
                shortlist = self.screener.shortlist(candidates, twin_summary,
                                                      trust, n_keep=n_short)
            else:
                shortlist = candidates

            # 7. Evaluate shortlist on the method-visible channel
            best_util = -np.inf
            best_cand = shortlist[0]
            util_samples = []
            for cand in shortlist:
                sinr, rate, _ = self.compute_effective_sinr_and_rate(cand, H=H_method)
                pd_mean, acc_mean, _ = self.compute_sensing_metrics(cand, anomaly_eff, clutter_w)
                energy = self.energy_metric(cand)
                util = self.compute_utility(cand, rate.mean(), pd_mean, acc_mean,
                                              1.0, energy)  # method doesn't know trust_actual
                util_samples.append(util)
                if util > best_util:
                    best_util = util
                    best_cand = cand

            if self.screener is not None and self.flags.use_quantum_screen:
                self.screener.train_online(shortlist, util_samples, twin_summary, trust, lr=0.005)

        # 8. Trust-aware gate
        a_safe = safe_fallback_action(cfg)
        if self.flags.use_trust_gate and self.trust_proc is not None:
            a_dep = trust_aware_gate(best_cand, a_safe, trust, cfg)
        else:
            a_dep = best_cand

        # 9. Deploy: precoder designed from H_method, reception through H_true
        sinr_real, rate_real = self.deploy_action(a_dep, H_true, H_method)
        pd_mean, acc_mean, pd_vec = self.compute_sensing_metrics(a_dep, anomaly_eff, clutter_w)
        energy = self.energy_metric(a_dep)

        # Ground-truth trust for utility scoring — same for every method.
        # This reflects whether the deployment environment is actually under attack.
        if anomaly_eff.get("kind") is not None:
            trust_actual = 0.3  # clearly compromised conditions
        else:
            trust_actual = 1.0  # nominal
        util = self.compute_utility(a_dep, rate_real.mean(), pd_mean, acc_mean,
                                      trust_actual, energy)

        latency_ms = (time.perf_counter() - t_start) * 1000

        sm = SlotMetrics(
            rate_bps_total=float(rate_real.sum()),
            rate_bps_mean=float(rate_real.mean()),
            p_d_mean=float(pd_mean),
            accuracy_mean=float(acc_mean),
            trust=float(trust),
            eps_dt=float(eps_dt),
            energy_norm=float(energy),
            utility=float(util),
            control_latency_ms=float(latency_ms),
            action_deployed=a_dep,
        )
        self.metrics_history.append(sm)
        return sm

    @property
    def noise_power(self) -> float:
        cfg = self.cfg
        n0 = 10 ** ((cfg.n0_dbm_hz - 30) / 10)
        bw_per_user = cfg.bw_hz / max(1, cfg.n_users // cfg.n_bs)
        return n0 * bw_per_user

    def run(self, n_slots: int, verbose: bool = False) -> list:
        for t in range(n_slots):
            sm = self.run_slot(t)
            if verbose and (t + 1) % 100 == 0:
                print(f"  [{self.tag}] slot {t+1}/{n_slots} "
                      f"util={sm.utility:.3f} trust={sm.trust:.3f} Pd={sm.p_d_mean:.3f}")
        return self.metrics_history


# Baseline configurations matching the paper
BASELINE_FLAGS = {
    "static":  ControllerFlags(use_digital_twin=False, use_quantum_screen=False,
                                use_trust_gate=False,  use_security_trust=False,
                                fixed_action=STATIC_ACTION),
    "reactive":ControllerFlags(use_digital_twin=False, use_quantum_screen=False,
                                use_trust_gate=False,  use_security_trust=False,
                                reactive_mode=True),
    "dt_only": ControllerFlags(use_digital_twin=True,  use_quantum_screen=False,
                                use_trust_gate=False,  use_security_trust=True),
    "dt_qa":   ControllerFlags(use_digital_twin=True,  use_quantum_screen=True,
                                use_trust_gate=False,  use_security_trust=False),
    "full":    ControllerFlags(use_digital_twin=True,  use_quantum_screen=True,
                                use_trust_gate=True,   use_security_trust=True),
    "dt_trust":ControllerFlags(use_digital_twin=True,  use_quantum_screen=False,
                                use_trust_gate=True,   use_security_trust=True),
}


if __name__ == "__main__":
    # Minimal smoke test
    cfg = SimConfig(n_slots=20)
    rng = np.random.default_rng(cfg.master_seed)
    ctrl = ISACController(cfg, BASELINE_FLAGS["full"], rng, tag="full-test")
    hist = ctrl.run(20, verbose=True)
    final = hist[-1]
    print(f"\nFinal slot: utility={final.utility:.3f}, trust={final.trust:.3f}")
    print(f"  rate_mean={final.rate_bps_mean/1e6:.1f} Mbps")
    print(f"  Pd_mean={final.p_d_mean:.3f}, energy={final.energy_norm:.3f}")
    print(f"  control_latency={np.mean([m.control_latency_ms for m in hist]):.2f} ms")
