"""
08_extra_results.py - supplementary results requested at review.

Produces, from the same T0 failure statistics and seeds as the main pipeline:
  R8  (Table 15)  availability-estimator validation: exact vs Monte-Carlo, 95 % CI,
                  plus an importance-sampling estimate for the rare-event cases
  R9  (Table 16)  chunk-size sensitivity: knee (k, m) with chunk size fixed, per regime
  R10 (Table 17)  storage savings at equal availability: fixed RS(4,2) vs adaptive
  R11 (Table 18)  failure-correlation sensitivity (common-cause shock model)
  figures: exact_vs_mc.png, chunk_sensitivity.png, storage_savings.png

Run:  python scripts/08_extra_results.py
"""
import sys, time, json
from pathlib import Path
import numpy as np
import pandas as pd
import yaml
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from oracle.availability import closed_form_availability, monte_carlo_availability
from oracle.memo import AvailabilityTable
from search.base import Problem, knee_point
from search.nsga2 import NSGA2
from baselines.enumerate import exact_pareto
from eval.metrics import nines

TAB = ROOT / "results" / "tables"; FIG = ROOT / "results" / "figures"
TAB.mkdir(parents=True, exist_ok=True); FIG.mkdir(parents=True, exist_ok=True)

cfg = yaml.safe_load(open(ROOT / "config" / "default.yaml"))
regimes_cfg = yaml.safe_load(open(ROOT / "config" / "regimes.yaml"))["regimes"]
CHUNKS_KB = cfg["rs"]["chunk_sizes_kb"]
CHUNKS = [c * 1024 for c in CHUNKS_KB]
MC_RUNS = int(cfg["oracle"]["mc_runs"]); MC_SEED = int(cfg["oracle"]["mc_seed"])
BASE_SEED = int(cfg["stats"]["base_seed"])
REGIMES = ["low", "medium", "high"]
FIXED = (4, 2, 1024 * 1024)

t0 = pd.read_csv(TAB / "T0_fit.csv")
AVAIL = {r: t0[t0.regime == r].sort_values("csp_idx")["availability"].to_numpy() for r in REGIMES}
NCSP = {r: len(AVAIL[r]) for r in REGIMES}


def chunk_avail(regime, k, m):
    a = AVAIL[regime]; return a[np.arange(k + m) % len(a)]


def exact(regime, k, m):
    if k + m > NCSP[regime]: return np.nan
    return closed_form_availability(k, m, chunk_avail(regime, k, m))


def wilson_ci(successes, n, z=1.96):
    if n == 0: return (np.nan, np.nan)
    p = successes / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d; h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def importance_sampling_unavail(regime, k, m, n_runs=200_000, seed=11, boost=20.0):
    """Rare-event estimate of P(fewer than k chunks survive).
    Chunk failure probabilities are tilted upward (q_j = min(0.5, boost*p_j)) and each
    draw is weighted by the likelihood ratio prod_j (p_j/q_j)^x_j ((1-p_j)/(1-q_j))^(1-x_j).
    Returns (estimate, standard error) of the UNAVAILABILITY."""
    p = 1.0 - chunk_avail(regime, k, m); q = np.minimum(0.5, boost * p)
    rng = np.random.default_rng(seed)
    x = rng.random((n_runs, k + m)) < q            # failure indicator under tilted law
    lr = np.prod(np.where(x, p / q, (1 - p) / (1 - q)), axis=1)
    fail = (x.sum(axis=1) > m)                      # stripe lost when > m chunks fail
    w = lr * fail
    return float(w.mean()), float(w.std(ddof=1) / np.sqrt(n_runs))


# -------------------------------------------------------------- R8 / Table 15
def table15():
    rows = []
    knees = {}
    for r in REGIMES:
        r2 = pd.read_csv(TAB / f"R2_{r}.csv").iloc[0]
        knees[r] = (int(r2.k_knee), int(r2.m_knee), int(r2.chunk_kb_knee) * 1024)
    for r in REGIMES:
        for label, (k, m, c) in [("knee (deployed)", knees[r]), ("fixed RS(4,2)", FIXED)]:
            if k + m > NCSP[r]:
                rows.append(dict(regime=r, profile=label, k=k, m=m, exact="infeasible", mc_1e4="", ci95_1e4="", abs_err_1e4="",
                                 mc_1e6="", ci95_1e6="", abs_err_1e6="", is_unavail="", is_se="", is_rel_err=""))
                continue
            ex = exact(r, k, m)
            av = chunk_avail(r, k, m)
            mc4, se4 = monte_carlo_availability(k, m, av, n_runs=MC_RUNS, seed=MC_SEED)
            lo4, hi4 = wilson_ci(round(mc4 * MC_RUNS), MC_RUNS)
            N6 = 1_000_000
            mc6, se6 = monte_carlo_availability(k, m, av, n_runs=N6, seed=MC_SEED + 1)
            lo6, hi6 = wilson_ci(round(mc6 * N6), N6)
            isu, isse = importance_sampling_unavail(r, k, m)
            rows.append(dict(regime=r, profile=label, k=k, m=m, exact=f"{ex:.9f}", exact_unavail=f"{1-ex:.3e}",
                             mc_1e4=f"{mc4:.6f}", ci95_1e4=f"[{lo4:.6f}, {hi4:.6f}]", abs_err_1e4=f"{abs(mc4-ex):.2e}",
                             mc_1e6=f"{mc6:.7f}", ci95_1e6=f"[{lo6:.7f}, {hi6:.7f}]", abs_err_1e6=f"{abs(mc6-ex):.2e}",
                             is_unavail=f"{isu:.3e}", is_se=f"{isse:.1e}", is_rel_err=f"{abs(isu-(1-ex))/(1-ex)*100:.2f}%"))
    df = pd.DataFrame(rows); df.to_csv(TAB / "R8_estimator_validation.csv", index=False)
    # Graph 14
    fig, ax = plt.subplots(figsize=(8, 4.2))
    lab, exv, mcv, err = [], [], [], []
    for _, row in df.iterrows():
        if row.exact == "infeasible": continue
        lab.append(f"{row.regime}\nRS({row.k},{row.m})"); exv.append(float(row.exact))
        mcv.append(float(row.mc_1e6)); lo, hi = [float(x) for x in row.ci95_1e6.strip("[]").split(",")]
        err.append([float(row.mc_1e6) - lo, hi - float(row.mc_1e6)])
    xs = np.arange(len(lab)); err = np.array(err).T
    ax.plot(xs, exv, "s-", color="#0E2A3A", label="Exact (Poisson-binomial)")
    ax.errorbar(xs + 0.08, mcv, yerr=err, fmt="o", color="#B97A12", capsize=4, label="Monte-Carlo, 10^6 draws, 95 % CI")
    ax.set_xticks(xs); ax.set_xticklabels(lab); ax.set_ylabel("Availability"); ax.set_ylim(min(exv) - 0.0008, 1.0002)
    ax.set_title("Exact vs Monte-Carlo availability per deployed configuration"); ax.grid(alpha=.3); ax.legend(loc="lower left")
    fig.tight_layout(); fig.savefig(FIG / "exact_vs_mc.png", dpi=200); plt.close(fig)
    return df


# -------------------------------------------------------------- R9 / Table 16
def table16():
    rows = []
    for r in REGIMES:
        oracle = AvailabilityTable(AVAIL[r], mc_runs=MC_RUNS, seed=MC_SEED); oracle.precompute()
        for ci, c in enumerate(CHUNKS):
            prob = Problem(oracle=oracle, n_csps=NCSP[r], chunk_sizes=[c])
            # exact knee for this chunk size
            front = exact_pareto(prob); ki = knee_point(front); k, m, _ = front.points[ki]
            # NSGA-II runtime with chunk size fixed (3 seeds, mean)
            ts = []
            for rep in range(3):
                t = time.perf_counter(); NSGA2().optimize(prob, seed=BASE_SEED + 100 * ci + rep); ts.append(time.perf_counter() - t)
            ex = exact(r, int(k), int(m))
            rows.append(dict(chunk_kb=CHUNKS_KB[ci], regime=r, k=int(k), m=int(m), availability=f"{ex:.6f}", nines=nines(ex),
                             overhead=f"{m/k:.3f}", repair_mb=f"{k*c/2**20:.2f}", runtime_s=f"{np.mean(ts):.2f}",
                             front_size=len(front.points)))
    df = pd.DataFrame(rows); df.to_csv(TAB / "R9_chunk_sensitivity.csv", index=False)
    # Graph 15
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4))
    for r, col in zip(REGIMES, ["#C24A2B", "#B97A12", "#1E9E6A"]):
        d = df[df.regime == r]
        a1.plot(d.chunk_kb, d.repair_mb.astype(float), "o-", color=col, label=r)
        a2.plot(d.chunk_kb, d.runtime_s.astype(float), "o-", color=col, label=r)
    for a, yl, t in [(a1, "Repair bandwidth of knee profile (MB)", "Repair cost vs chunk size"), (a2, "NSGA-II runtime (s)", "Search runtime vs chunk size")]:
        a.set_xscale("log", base=2); a.set_xticks(CHUNKS_KB); a.set_xticklabels([f"{c} KB" if c < 1024 else f"{c//1024} MB" for c in CHUNKS_KB], rotation=30)
        a.set_ylabel(yl); a.set_title(t); a.grid(alpha=.3); a.legend()
    a1.set_yscale("log", base=2)
    fig.tight_layout(); fig.savefig(FIG / "chunk_sensitivity.png", dpi=200); plt.close(fig)
    return df


# -------------------------------------------------------------- R10 / Table 17
def table17():
    targets = [0.999, 0.9999, 0.99999]
    rows = []
    for r in REGIMES:
        n = NCSP[r]
        # all feasible (k, m) with exact availability
        cand = [(k, m, exact(r, k, m)) for k in range(1, 17) for m in range(0, 9) if k + m <= n]
        fx_k, fx_m, _ = FIXED; fx_feas = fx_k + fx_m <= n; fx_A = exact(r, fx_k, fx_m) if fx_feas else np.nan
        for tgt in targets:
            ok = [(k, m, A) for k, m, A in cand if A >= tgt]
            if not ok:
                rows.append(dict(regime=r, target=f"{tgt*100:g}%", fixed_profile="RS(4,2)", adaptive_profile="infeasible (no (k,m) on %d CSPs reaches target)" % n,
                                 fixed_overhead="", adaptive_overhead="", fixed_storage="", adaptive_storage="", saved_pct="infeasible")); continue
            k, m, A = min(ok, key=lambda t: (t[1] / t[0], t[0] * 1))   # cheapest overhead, then smallest k
            ad_over = m / k; ad_S = 1 + ad_over
            if not fx_feas:
                fixed_desc = "RS(4,2) infeasible (needs 6 CSPs, %d available)" % n; fx_over = ""; fx_S = ""; saved = "n/a (fixed infeasible)"
            elif fx_A < tgt:
                fixed_desc = f"RS(4,2) below target ({nines(fx_A)})"; fx_over = f"{fx_m/fx_k:.3f}"; fx_S = f"{1+fx_m/fx_k:.3f}"; saved = "n/a (fixed misses target)"
            else:
                fixed_desc = "RS(4,2)"; fx_over = f"{fx_m/fx_k:.3f}"; fx_S = f"{1+fx_m/fx_k:.3f}"
                saved = f"{(1+fx_m/fx_k - ad_S)/(1+fx_m/fx_k)*100:.1f}%"
            rows.append(dict(regime=r, target=f"{tgt*100:g}%", fixed_profile=fixed_desc, adaptive_profile=f"RS({k},{m}) [A={A:.6f}, {nines(A)}]",
                             fixed_overhead=fx_over, adaptive_overhead=f"{ad_over:.3f}", fixed_storage=fx_S, adaptive_storage=f"{ad_S:.3f}", saved_pct=saved))
    df = pd.DataFrame(rows); df.to_csv(TAB / "R10_storage_savings.csv", index=False)
    # Graph 16: grouped bars per regime x target (storage ratio S = 1 + m/k); missing bars where infeasible
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.8), sharey=True)
    for ax, r in zip(axes, REGIMES):
        d = df[df.regime == r]; x = np.arange(len(d)); w = 0.36
        fxv = [float(v) if v != "" else np.nan for v in d.fixed_storage]; adv = [float(v) if v != "" else np.nan for v in d.adaptive_storage]
        miss = ["below target" in p for p in d.fixed_profile]
        bars = ax.bar(x - w / 2, fxv, w, color="#9AA9B8", label="Fixed RS(4,2)")
        for b, mflag in zip(bars, miss):
            if mflag: b.set_hatch("///"); b.set_edgecolor("#C24A2B")
        ax.bar(x + w / 2, adv, w, color="#0B7CB8", label="Adaptive (cheapest profile meeting target)")
        for i, (f, a) in enumerate(zip(fxv, adv)):
            if np.isnan(f): ax.text(i - w / 2, 0.05, "n/a", ha="center", fontsize=8, rotation=90, va="bottom", color="#C24A2B")
            if np.isnan(a): ax.text(i + w / 2, 0.05, "n/a", ha="center", fontsize=8, rotation=90, va="bottom", color="#C24A2B")
        ax.set_xticks(x); ax.set_xticklabels(d.target); ax.set_title(f"{r} regime ({NCSP[r]} CSPs)"); ax.grid(axis="y", alpha=.3); ax.set_ylim(0, 3.2)
    axes[0].set_ylabel("Storage ratio  1 + m/k"); axes[0].legend(fontsize=8, loc="upper left")
    axes[2].text(0.5, 2.6, "RS(4,2) needs 6 CSPs;\nnot placeable on 4", ha="center", fontsize=8, color="#C24A2B")
    axes[0].text(1.0, 2.75, "hatched = RS(4,2) placeable\nbut misses the target", ha="center", fontsize=8, color="#C24A2B")
    fig.suptitle("Storage at equal availability target: fixed vs adaptive"); fig.tight_layout(); fig.savefig(FIG / "storage_savings.png", dpi=200); plt.close(fig)
    return df


# -------------------------------------------------------------- R11 / Table 18
def common_cause_availability(regime, k, m, q_shock, shock_size, n_runs=200_000, seed=23):
    """Common-cause model: every epoch, independent chunk failures as before, PLUS with probability
    q_shock a regional shock knocks out `shock_size` randomly chosen CSPs together (all their chunks)."""
    a = AVAIL[regime]; n = len(a); idx = np.arange(k + m) % n
    rng = np.random.default_rng(seed)
    surv = rng.random((n_runs, k + m)) < a[idx]
    shock = rng.random(n_runs) < q_shock
    if shock.any():
        for i in np.flatnonzero(shock):
            dead = rng.choice(n, size=shock_size, replace=False)
            surv[i, np.isin(idx, dead)] = False
    ok = surv.sum(axis=1) >= k
    p = ok.mean(); return float(p), wilson_ci(int(ok.sum()), n_runs)


def table18():
    scen = [("Independent failures", "no shock", 0.0, 0), ("Moderate common-cause", "shock p=1e-3 kills 2 CSPs", 1e-3, 2),
            ("Severe common-cause", "shock p=1e-2 kills half of CSPs", 1e-2, None)]
    rows = []
    for r in REGIMES:
        n = NCSP[r]; r2 = pd.read_csv(TAB / f"R2_{r}.csv").iloc[0]; kk, km, kc = int(r2.k_knee), int(r2.m_knee), int(r2.chunk_kb_knee) * 1024
        for name, model, q, size in scen:
            size_eff = (n // 2) if size is None else size
            fx = common_cause_availability(r, 4, 2, q, size_eff) if 6 <= n else None
            ad = common_cause_availability(r, kk, km, q, size_eff)
            rows.append(dict(regime=r, scenario=name, model=model if size is not None else f"shock p=1e-2 kills {size_eff} of {n} CSPs",
                             fixed_avail=("infeasible" if fx is None else f"{fx[0]:.5f} [{fx[1][0]:.5f}, {fx[1][1]:.5f}]"),
                             adaptive_profile=f"RS({kk},{km})", adaptive_avail=f"{ad[0]:.5f} [{ad[1][0]:.5f}, {ad[1][1]:.5f}]",
                             fixed_overhead="0.500" if fx else "", adaptive_overhead=f"{km/kk:.3f}",
                             fixed_repair_mb="4.00" if fx else "", adaptive_repair_mb=f"{kk*kc/2**20:.2f}"))
    df = pd.DataFrame(rows); df.to_csv(TAB / "R11_correlation_sensitivity.csv", index=False); return df


if __name__ == "__main__":
    t = time.time()
    d15 = table15(); print("R8 / Table 15\n", d15.to_string(), "\n")
    d16 = table16(); print("R9 / Table 16\n", d16.to_string(), "\n")
    d17 = table17(); print("R10 / Table 17\n", d17.to_string(), "\n")
    d18 = table18(); print("R11 / Table 18\n", d18.to_string(), "\n")
    json.dump({"seed_base": BASE_SEED, "mc_seed": MC_SEED, "mc_runs": MC_RUNS, "elapsed_s": round(time.time() - t, 1)}, open(TAB / "R8_R11_meta.json", "w"), indent=1)
    print("done in", round(time.time() - t, 1), "s")
