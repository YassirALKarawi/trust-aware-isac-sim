"""
Aggregate all experiment results into a compact summary for paper rewriting.
Reads every JSON in results/ and prints a structured report.
"""
import json
from pathlib import Path
import numpy as np

R = Path("/home/claude/sim/results")


def load(name):
    p = R / f"{name}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text())


def fmt_row(label, vals, width=10):
    row = f"{label:<22s}"
    for v in vals:
        if isinstance(v, str):
            row += f" {v:>{width}s}"
        else:
            row += f" {v:>{width}.3f}"
    return row


print("=" * 78)
print("  SIMULATION SYNTHESIS — all experiments")
print("=" * 78)

# ---------- Baseline ----------
b = load("baseline")
if b:
    print("\n[1] Baseline comparison (p_anom = 0.04, 200 slots, 3 MC)")
    print("-" * 78)
    header = ["Method", "Utility", "±std", "Rate(Mbps)", "Pd", "Energy", "Lat(ms)"]
    print(f"{header[0]:<22s} {header[1]:>8s} {header[2]:>6s} {header[3]:>11s} "
          f"{header[4]:>6s} {header[5]:>7s} {header[6]:>8s}")
    order = ["static", "reactive", "dt_only", "dt_qa", "full", "dt_trust"]
    display = {
        "static": "Static ISAC",
        "reactive": "Reactive",
        "dt_only": "DT only (+Sec)",
        "dt_qa": "DT + QA",
        "full": "Full Proposed",
        "dt_trust": "DT + Trust",
    }
    for m in order:
        if m not in b:
            continue
        s = b[m]
        print(f"{display[m]:<22s} {s['utility_mean']:>8.3f} "
              f"{s['utility_std']:>6.3f} "
              f"{s['rate_bps_total_mean']/1e6:>11.1f} "
              f"{s['p_d_mean_mean']:>6.3f} "
              f"{s['energy_norm_mean']:>7.3f} "
              f"{s['latency_ms_mean']:>8.2f}")
    best = max(b.items(), key=lambda kv: kv[1]['utility_mean'])
    print(f"\n  Winner: {display[best[0]]}  utility = {best[1]['utility_mean']:.3f}")

# ---------- Anomaly sweep ----------
a = load("anomaly_sweep")
if a:
    print("\n[2] Anomaly-rate sweep (utility vs p_anom)")
    print("-" * 78)
    rates = sorted(set(float(k) for m in a.values() for k in m.keys()))
    cols = ["static", "dt_only", "dt_qa", "full"]
    print(f"{'p_anom':<22s}", " ".join(f"{c:>10s}" for c in cols))
    for p in rates:
        vals = [a[m][str(p)]['utility_mean'] for m in cols]
        print(fmt_row(f"{p:.3f}", vals))
    # find crossover
    print("\n  Winner by regime:")
    for p in rates:
        vals = {m: a[m][str(p)]['utility_mean'] for m in cols}
        win = max(vals, key=vals.get)
        print(f"    p={p:.3f}  → {win} ({vals[win]:.3f})")

# ---------- Twin delay ----------
td = load("twin_delay")
if td:
    print("\n[3] Twin synchronisation delay sweep (utility vs tau)")
    print("-" * 78)
    taus = sorted(set(int(k) for m in td.values() for k in m.keys()))
    cols = ["dt_only", "dt_qa", "full"]
    print(f"{'tau (slots)':<22s}", " ".join(f"{c:>10s}" for c in cols))
    for t in taus:
        vals = [td[m][str(t)]['utility_mean'] for m in cols]
        print(fmt_row(f"{t}", vals))
    # robustness
    full_range = [td["full"][str(t)]['utility_mean'] for t in taus]
    span = max(full_range) - min(full_range)
    print(f"\n  Full-framework utility span over tau = [{min(full_range):.3f}, {max(full_range):.3f}]")
    print(f"  Swing: {span:.3f} ({100*span/np.mean(full_range):.1f}%)")

# ---------- Shortlist size ----------
ss = load("shortlist_size")
if ss:
    print("\n[4] Shortlist-size sensitivity")
    print("-" * 78)
    sizes = sorted(int(k) for k in ss.keys())
    print(f"{'M_s':>5s} {'utility':>10s} {'latency(ms)':>14s} {'rate(Mbps)':>12s}")
    for s in sizes:
        v = ss[str(s)]
        print(f"{s:>5d} {v['utility_mean']:>10.3f} {v['latency_ms_mean']:>14.2f} "
              f"{v['rate_bps_total_mean']/1e6:>12.1f}")
    best_s = max(sizes, key=lambda x: ss[str(x)]['utility_mean'])
    print(f"\n  Peak at M_s = {best_s}, utility = {ss[str(best_s)]['utility_mean']:.3f}")

# ---------- Trust transient ----------
tt = load("trust_transient")
if tt:
    print("\n[5] Trust-recovery transient (500 slots, burst 200-300)")
    print("-" * 78)
    for m in ["full", "dt_only"]:
        trust = tt[m]['trust']
        pre = np.mean(trust[150:200])
        floor = min(trust[200:300])
        post = np.mean(trust[400:500])
        # 10-90 recovery
        post_arr = trust[300:]
        rise = pre - floor
        t10 = next((i for i, v in enumerate(post_arr) if v > floor + 0.1 * rise), len(post_arr))
        t90 = next((i for i, v in enumerate(post_arr) if v > floor + 0.9 * rise), len(post_arr))
        print(f"  {m}:")
        print(f"    pre-attack trust   : {pre:.3f}")
        print(f"    attack floor       : {floor:.3f}")
        print(f"    10-90 recovery span: {t90-t10} slots")
        print(f"    post-recovery trust: {post:.3f}")

# ---------- Scalability ----------
su = load("scalability_users")
if su:
    print("\n[6] User-count scalability")
    print("-" * 78)
    # intersection of keys across methods so partial saves don't crash the output
    common_U = sorted(
        set.intersection(*[set(int(k) for k in su[m].keys()) for m in ["static", "dt_only", "full"]])
    )
    cols = ["static", "dt_only", "full"]
    print(f"{'U':>5s}", " ".join(f"{c:>10s}" for c in cols))
    for U in common_U:
        vals = [su[m][str(U)]['utility_mean'] for m in cols]
        print(fmt_row(f"{U}", vals))

st = load("scalability_targets")
if st:
    print("\n[7] Target-count scalability")
    print("-" * 78)
    Ks = sorted(int(k) for k in st['static'].keys())
    cols = ["static", "dt_only", "full"]
    print(f"{'K':>5s}", " ".join(f"{c:>10s}" for c in cols))
    for K in Ks:
        vals = [st[m][str(K)]['utility_mean'] for m in cols]
        print(fmt_row(f"{K}", vals))

print("\n" + "=" * 78)
print("  END OF SYNTHESIS")
print("=" * 78)
