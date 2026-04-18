"""
Trust process: Bayesian log-likelihood accumulation with EWMA smoothing.
The trust score T(t) in [0,1] is the posterior belief that the deployment
chain operates under nominal conditions.
"""
import numpy as np
from config import SimConfig


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30, 30)))


class TrustProcess:
    def __init__(self, cfg: SimConfig, rng: np.random.Generator):
        self.cfg = cfg
        self.rng = rng
        self.T = 1.0                # start fully trusted
        self.lambda_cum = 0.0       # cumulative log-likelihood for bookkeeping
        self.alpha = cfg.alpha_ewma
        self.lambda_clip = cfg.lambda_clip

    def log_likelihood(self, eps_dt: float, residual_outlier_fraction: float,
                       anomaly_signal: float) -> float:
        """
        Build a bounded log-likelihood ratio for anomaly vs nominal hypothesis.
        Sources:
          - twin mismatch eps_dt (higher -> more evidence for anomaly)
          - fraction of telemetry outliers (higher -> more evidence)
          - injected anomaly_signal in [0,1] (soft indicator)
        """
        l_eps = 3.0 * np.clip(eps_dt - 0.05, -0.5, 0.5)
        l_out = 4.0 * np.clip(residual_outlier_fraction, 0, 1)
        l_anom = 2.0 * np.clip(anomaly_signal, 0, 1)
        lam = l_eps + l_out + l_anom
        return float(np.clip(lam, -self.lambda_clip, self.lambda_clip))

    def update(self, eps_dt: float, fidelity: float,
               outlier_frac: float, anomaly_signal: float) -> float:
        """
        One-slot EWMA update approximating the full Bayesian recursion.
        T(t+1) = alpha T(t) + (1-alpha) [1 - sigma(Lambda - Lambda_0)] * F_DT(t)
        """
        lam = self.log_likelihood(eps_dt, outlier_frac, anomaly_signal)
        self.lambda_cum += lam
        posterior_nominal = 1.0 - sigmoid(lam - self.cfg.lambda0)
        target = posterior_nominal * fidelity
        self.T = self.alpha * self.T + (1 - self.alpha) * target
        self.T = float(np.clip(self.T, 0.0, 1.0))
        return self.T


if __name__ == "__main__":
    cfg = SimConfig()
    rng = np.random.default_rng(cfg.master_seed)
    tp = TrustProcess(cfg, rng)

    # Nominal conditions for 50 slots then anomaly for 100 slots, then recovery
    trace = []
    for t in range(50):
        tp.update(eps_dt=0.02, fidelity=0.98, outlier_frac=0.0, anomaly_signal=0.0)
        trace.append(tp.T)
    for t in range(100):
        tp.update(eps_dt=0.15, fidelity=0.7, outlier_frac=0.3, anomaly_signal=0.8)
        trace.append(tp.T)
    for t in range(150):
        tp.update(eps_dt=0.02, fidelity=0.98, outlier_frac=0.0, anomaly_signal=0.0)
        trace.append(tp.T)

    trace = np.array(trace)
    print(f"Trust trace: nominal steady = {trace[:50].mean():.3f}")
    print(f"             attack floor = {trace[50:150].min():.3f}")
    print(f"             recovery at t=250 = {trace[200]:.3f}")
    print(f"             recovery at t=280 = {trace[230]:.3f}")
    # 10-90 recovery time estimate
    post_attack = trace[150:]
    t10 = np.argmax(post_attack > 0.1 * (post_attack[-1] - post_attack[0]) + post_attack[0])
    t90 = np.argmax(post_attack > 0.9 * (post_attack[-1] - post_attack[0]) + post_attack[0])
    print(f"  10-90 recovery span: {t90 - t10} slots")
