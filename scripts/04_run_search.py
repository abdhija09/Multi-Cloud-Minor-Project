"""
04_run_search.py
<<<<<<< HEAD
  --experiment E3-  : NSGA-II vs exact Pareto (hypervolume, IGD, spacing, convergence)
  --experiment E4-  : Fleet simulation comparing Fixed / Greedy / NSGA-II knee
  --repeats N       : number of independent repeats (default 10)
"""

import os
=======
  --experiment E3-<regime> : NSGA-II vs exact Pareto (hypervolume, IGD, spacing, convergence)
  --experiment E4-<regime> : Fleet simulation comparing Fixed / Greedy / NSGA-II knee
                             <regime> is a name from config/regimes.yaml or 'all'
                             (a bare 'E3-' / 'E4-' also means all)
  --repeats N              : number of independent repeats (default 10)

Seeding (deterministic; see src/eval/reproducibility.py)
  seed (algorithm / simulation) = SeedManager(base_seed).seed_for('E3'|'E4', rep)
                                = base_seed*10**6 + {3|4}*10**3 + rep
  env  (CSP availability draw):
    E3 : default_rng([base_seed, regime_index])        – one fleet for all repeats,
                                                        identical to script 03 (R2)
    E4 : default_rng([base_seed + rep, regime_index])  – fresh fleet per repeat;
                                                        repeat 0 == script 03 / E3
Run folders: experiments/runs/<E3|E4>/<regime>_rep<r>_seed<seed>/
  (meta.json + metrics.csv with the per-repeat numbers aggregated into R3/R4).
"""

import os
import sys
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
import argparse
import yaml
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import scipy.stats as st

<<<<<<< HEAD
from oracle.memo import AvailabilityTable
=======
# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from oracle.memo import AvailabilityTable
from oracle.availability import closed_form_availability
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
from search.base import Problem, knee_point
from baselines.enumerate import exact_pareto
from baselines.greedy import greedy_profile
from search.nsga2 import NSGA2
from eval.metrics import hypervolume, igd, spacing
from simulator.csp import CSP
from simulator.fleet import Fleet, FleetReport
<<<<<<< HEAD
=======
from eval.reproducibility import SeedManager
from utils.logging import log_run, run_dir_for, clear_runs
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def mean_ci(data, confidence=0.95):
<<<<<<< HEAD
    a = np.asarray(data, dtype=float)
    n = len(a)
=======
    """Mean and CI half-width over the non-NaN entries (NaN = not observed)."""
    a = np.asarray(data, dtype=float)
    a = a[~np.isnan(a)]
    n = len(a)
    if n == 0:
        return float("nan"), float("nan")
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
    if n < 2:
        return float(np.mean(a)), 0.0
    m, se = np.mean(a), st.sem(a)
    h = se * st.t.ppf((1 + confidence) / 2.0, n - 1)
    return float(m), float(h)


# ---------------------------------------------------------------------------
# E3 – convergence / quality vs exact Pareto
# ---------------------------------------------------------------------------

<<<<<<< HEAD
def run_e3(regime_name, params, default_cfg, out_tables, out_figures, n_repeats, rng_env):
=======
def run_e3(regime_name, regime_index, params, default_cfg, out_tables, out_figures, n_repeats,
           rng_env, env_seed, seed_mgr):
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
    csp_count = params["csp_count"]
    fail_prob_min, fail_prob_max = params["failure_prob_range"]
    avail_min = 1.0 - float(fail_prob_max)
    avail_max = 1.0 - float(fail_prob_min)
    availabilities = rng_env.uniform(avail_min, avail_max, size=csp_count)

    chunk_sizes = default_cfg["rs"]["chunk_sizes_kb"]
    max_k = default_cfg["rs"]["max_k"]
    max_m = default_cfg["rs"]["max_m"]

    oracle = AvailabilityTable(
        csp_avail=availabilities,
        mc_runs=default_cfg["oracle"]["mc_runs"],
        seed=default_cfg["oracle"]["mc_seed"],
    )
    problem = Problem(oracle=oracle, n_csps=csp_count, chunk_sizes=chunk_sizes,
                      max_k=max_k, max_m=max_m)

<<<<<<< HEAD
    exact_front = exact_pareto(problem)
    exact_knee_idx = knee_point(exact_front)
=======
    knee_eps = 1.0 / (2 * default_cfg["oracle"]["mc_runs"])
    exact_front = exact_pareto(problem)
    exact_knee_idx = knee_point(exact_front, avail_floor_eps=knee_eps)
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
    if exact_knee_idx == -1:
        print(f"  No exact front for {regime_name}. Skipping.")
        return
    exact_knee_point = list(exact_front.points[exact_knee_idx])

    worst = np.max(exact_front.objective_vectors, axis=0)
    ref_point = np.where(worst < 0, worst * 0.9, worst * 1.1)
    ref_point[ref_point == 0] = 0.1
    exact_hv = hypervolume(exact_front, ref_point) or 1e-9
<<<<<<< HEAD
=======
    # (ideal, nadir) of the exact front, used to normalise spacing
    spacing_bounds = (np.min(exact_front.objective_vectors, axis=0),
                      np.max(exact_front.objective_vectors, axis=0))
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794

    algo_cfg = default_cfg["search"]
    base_seed = default_cfg["stats"]["base_seed"]
    nsga2 = NSGA2(pop_size=algo_cfg["pop_size"], generations=algo_cfg["generations"],
                  mutation_rate=algo_cfg["mutation_rate"],
                  crossover_rate=algo_cfg["crossover_rate"])

    results = {k: [] for k in ["norm_hv", "igd", "spacing", "gens_to_95", "knee_match"]}
    hv_traces = []
<<<<<<< HEAD

    for rep in range(n_repeats):
        seed = base_seed + rep
=======
    clear_runs("E3", prefix=f"{regime_name}_")

    for rep in range(n_repeats):
        seed = seed_mgr.seed_for("E3", rep)
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
        final_front, history_fronts = nsga2.optimize_with_history(problem, seed)

        rep_hv = hypervolume(final_front, ref_point)
        results["norm_hv"].append(rep_hv / exact_hv)
        results["igd"].append(igd(final_front, exact_front))
<<<<<<< HEAD
        results["spacing"].append(spacing(final_front))

        algo_knee_idx = knee_point(final_front)
=======
        results["spacing"].append(spacing(final_front, bounds=spacing_bounds))

        algo_knee_idx = knee_point(final_front, avail_floor_eps=knee_eps)
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
        match = (algo_knee_idx != -1 and
                 list(final_front.points[algo_knee_idx]) == exact_knee_point)
        results["knee_match"].append(1.0 if match else 0.0)

        trace = [hypervolume(h, ref_point) for h in history_fronts]
        hv_traces.append(trace)
        final_gen_hv = trace[-1] if trace else 0.0
        target = 0.95 * final_gen_hv
        gen95 = algo_cfg["generations"]
        for g, val in enumerate(trace):
            if val >= target:
                gen95 = g
                break
        results["gens_to_95"].append(gen95)

<<<<<<< HEAD
=======
        log_run(
            meta={"experiment": "E3", "script": "04_run_search.py",
                  "regime": regime_name, "regime_index": regime_index,
                  "repeat": rep, "seed": seed, "base_seed": base_seed,
                  "env_seed": env_seed,
                  "mc_seed": default_cfg["oracle"]["mc_seed"],
                  "mc_runs": default_cfg["oracle"]["mc_runs"],
                  "csp_availabilities": [float(a) for a in availabilities],
                  "exact_hv": float(exact_hv)},
            metrics={k: float(results[k][-1]) for k in results},
            run_dir=run_dir_for("E3", f"{regime_name}_rep{rep}_seed{seed}"),
        )

>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
    df = pd.DataFrame({
        "metric": ["norm_hv", "igd", "spacing", "gens_to_95", "knee_match_rate"],
        "mean": [mean_ci(results[k])[0] for k in
                 ["norm_hv", "igd", "spacing", "gens_to_95", "knee_match"]],
        "95_CI": [mean_ci(results[k])[1] for k in
                  ["norm_hv", "igd", "spacing", "gens_to_95", "knee_match"]],
    })
    df.to_csv(out_tables / f"R3_{regime_name}.csv", index=False)

    # Convergence figure
    trace_arr = np.array(hv_traces)
    if trace_arr.size > 0:
        mean_trace = np.mean(trace_arr, axis=0)
        std_trace = np.std(trace_arr, axis=0)
        gens = np.arange(len(mean_trace))
        plt.figure(figsize=(8, 6))
        plt.plot(gens, mean_trace, label="NSGA-II Mean HV")
        plt.fill_between(gens, mean_trace - std_trace, mean_trace + std_trace, alpha=0.3)
        plt.axhline(exact_hv, color="red", linestyle="--", label="Exact HV")
        plt.xlabel("Generations"); plt.ylabel("Hypervolume")
        plt.title(f"Convergence – {regime_name.capitalize()} Regime")
        plt.legend(); plt.grid(True, linestyle="--", alpha=0.7); plt.tight_layout()
        plt.savefig(out_figures / f"convergence_{regime_name}.png"); plt.close()


# ---------------------------------------------------------------------------
# E4 – fleet simulation: Fixed vs Greedy vs NSGA-II knee
# ---------------------------------------------------------------------------

def build_csps(availabilities: np.ndarray, regime_params: dict) -> list[CSP]:
    """Create CSP objects from availability array."""
    csps = []
    for i, avail in enumerate(availabilities):
        csps.append(CSP(
            csp_id=i,
            availability=float(avail),
            capacity_bytes=10 * 1024**3,   # 10 GiB each
            unit_storage_cost=0.02,
            unit_egress_cost=0.09,
            latency_ms=20.0 + i * 5.0,     # mild per-CSP variation
        ))
    return csps


<<<<<<< HEAD
def run_e4(regime_name, params, default_cfg, out_tables, out_figures, n_repeats, rng_env):
=======
def run_e4(regime_name, regime_index, params, default_cfg, out_tables, out_figures, n_repeats,
           rng_env, env_seed, seed_mgr):
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
    n_stripes = 1000
    csp_count = params["csp_count"]
    fail_prob_min, fail_prob_max = params["failure_prob_range"]
    avail_min = 1.0 - float(fail_prob_max)
    avail_max = 1.0 - float(fail_prob_min)

    chunk_sizes = default_cfg["rs"]["chunk_sizes_kb"]   # list[int], in KB
    max_k = default_cfg["rs"]["max_k"]
    max_m = default_cfg["rs"]["max_m"]
    base_seed = default_cfg["stats"]["base_seed"]
    algo_cfg = default_cfg["search"]

    # Fixed baseline profile
    FIXED_K, FIXED_M, FIXED_C_KB = 4, 2, 1024

    # Rows: one dict per (strategy, repeat)
    strategy_results: dict[str, list[FleetReport]] = {
        "fixed": [], "greedy": [], "nsga2_knee": []
    }
<<<<<<< HEAD

    for rep in range(n_repeats):
        seed = base_seed + rep
        rng_rep = np.random.default_rng(seed)
=======
    # Exact (closed-form) availability of each strategy's profile per repeat.
    # The fleet simulation (1 epoch x n_stripes) cannot resolve availabilities
    # above ~log10(n_stripes) nines, so R4 also reports the oracle value.
    # NaN = profile infeasible on this fleet (k+m > n CSPs).
    oracle_avail: dict[str, list[float]] = {"fixed": [], "greedy": [], "nsga2_knee": []}
    profiles_used: dict[str, list[str]] = {"fixed": [], "greedy": [], "nsga2_knee": []}

    def exact_avail(k, m, avail):
        if k + m > len(avail):
            return float("nan")
        return closed_form_availability(k, m, avail[np.arange(k + m) % len(avail)])

    clear_runs("E4", prefix=f"{regime_name}_")
    for rep in range(n_repeats):
        seed = seed_mgr.seed_for("E4", rep)        # NSGA-II + fleet simulation
        # Environment stream (kept from the base_seed + rep scheme so the
        # fleets are unchanged): [base_seed + rep, regime_index].
        # Repeat 0 reproduces the availabilities used by script 03 / E3.
        rep_env_seed = [base_seed + rep, regime_index]
        rng_rep = np.random.default_rng(rep_env_seed)
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794

        # Fresh availability draw per repeat
        availabilities = rng_rep.uniform(avail_min, avail_max, size=csp_count)
        csps = build_csps(availabilities, params)

        oracle = AvailabilityTable(
            csp_avail=availabilities,
            mc_runs=default_cfg["oracle"]["mc_runs"],
            seed=default_cfg["oracle"]["mc_seed"],
        )
        problem = Problem(oracle=oracle, n_csps=csp_count, chunk_sizes=chunk_sizes,
                          max_k=max_k, max_m=max_m)

        # ── Fixed ──────────────────────────────────────────────────────────
        fixed_chunk_bytes = FIXED_C_KB * 1024
        # Find the c_idx closest to 1024 KB; might not be exact
        c_idx_fixed = min(range(len(chunk_sizes)),
                          key=lambda i: abs(chunk_sizes[i] - FIXED_C_KB))
        assignment_fixed = Fleet.assign_from_profile(
            FIXED_K, FIXED_M, fixed_chunk_bytes, n_stripes)
        fleet_fixed = Fleet(csps, assignment_fixed, seed)
        report_fixed = fleet_fixed.simulate_epoch(seed)
        strategy_results["fixed"].append(report_fixed)
<<<<<<< HEAD
=======
        oracle_avail["fixed"].append(exact_avail(FIXED_K, FIXED_M, availabilities))
        profiles_used["fixed"].append(f"({FIXED_K},{FIXED_M},{FIXED_C_KB}KB)")
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794

        # ── Greedy ─────────────────────────────────────────────────────────
        avail_floor = 0.999
        try:
            g_k, g_m, g_c_idx = greedy_profile(problem, avail_floor)
        except ValueError:
            # If no feasible profile meets the floor, fall back to fixed
            g_k, g_m, g_c_idx = FIXED_K, FIXED_M, c_idx_fixed

        g_chunk_bytes = chunk_sizes[g_c_idx] * 1024
        assignment_greedy = Fleet.assign_from_profile(g_k, g_m, g_chunk_bytes, n_stripes)
        fleet_greedy = Fleet(csps, assignment_greedy, seed)
        report_greedy = fleet_greedy.simulate_epoch(seed)
        strategy_results["greedy"].append(report_greedy)
<<<<<<< HEAD
=======
        oracle_avail["greedy"].append(exact_avail(g_k, g_m, availabilities))
        profiles_used["greedy"].append(f"({g_k},{g_m},{chunk_sizes[g_c_idx]}KB)")
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794

        # ── NSGA-II knee ───────────────────────────────────────────────────
        nsga2 = NSGA2(pop_size=algo_cfg["pop_size"],
                      generations=algo_cfg["generations"],
                      mutation_rate=algo_cfg["mutation_rate"],
                      crossover_rate=algo_cfg["crossover_rate"])
        front = nsga2.optimize(problem, seed=seed)
<<<<<<< HEAD
        k_idx = knee_point(front)
=======
        k_idx = knee_point(front, avail_floor_eps=1.0 / (2 * default_cfg["oracle"]["mc_runs"]))
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
        if k_idx == -1:
            # Fall back to fixed
            n_k, n_m, n_c_idx = FIXED_K, FIXED_M, c_idx_fixed
        else:
            n_k, n_m, n_c_idx = (int(front.points[k_idx, 0]),
                                  int(front.points[k_idx, 1]),
                                  int(front.points[k_idx, 2]))
        n_chunk_bytes = chunk_sizes[n_c_idx] * 1024
        assignment_nsga2 = Fleet.assign_from_profile(n_k, n_m, n_chunk_bytes, n_stripes)
        fleet_nsga2 = Fleet(csps, assignment_nsga2, seed)
        report_nsga2 = fleet_nsga2.simulate_epoch(seed)
        strategy_results["nsga2_knee"].append(report_nsga2)
<<<<<<< HEAD
=======
        oracle_avail["nsga2_knee"].append(exact_avail(n_k, n_m, availabilities))
        profiles_used["nsga2_knee"].append(f"({n_k},{n_m},{chunk_sizes[n_c_idx]}KB)")

        log_run(
            meta={"experiment": "E4", "script": "04_run_search.py",
                  "regime": regime_name, "regime_index": regime_index,
                  "repeat": rep, "seed": seed, "base_seed": base_seed,
                  "env_seed": rep_env_seed,
                  "mc_seed": default_cfg["oracle"]["mc_seed"],
                  "mc_runs": default_cfg["oracle"]["mc_runs"],
                  "n_stripes": n_stripes,
                  "csp_availabilities": [float(a) for a in availabilities]},
            metrics=[{
                "strategy": strat,
                "profile": profiles_used[strat][-1],
                "fleet_availability": float(strategy_results[strat][-1].availability),
                "storage_overhead": float(strategy_results[strat][-1].storage_overhead),
                "bytes_repaired": float(strategy_results[strat][-1].bytes_repaired),
                "mean_repair_latency_ms": float(strategy_results[strat][-1].mean_repair_latency_ms),
                "oracle_availability_exact": float(oracle_avail[strat][-1]),
            } for strat in ("fixed", "greedy", "nsga2_knee")],
            run_dir=run_dir_for("E4", f"{regime_name}_rep{rep}_seed{seed}"),
        )
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794

    # Aggregate and build R4
    ref_reports = strategy_results["fixed"]
    ref_avail_mean = np.mean([r.availability for r in ref_reports])
    ref_overhead_mean = np.mean([r.storage_overhead for r in ref_reports])

    rows = []
    labels = {"fixed": "Fixed RS(4,2) 1MB",
              "greedy": "Greedy (avail_floor=0.999)",
              "nsga2_knee": "NSGA-II knee"}

    for strategy, reports in strategy_results.items():
        avail_vals = [r.availability for r in reports]
        overhead_vals = [r.storage_overhead for r in reports]
        repaired_vals = [r.bytes_repaired for r in reports]
<<<<<<< HEAD
=======
        # NaN latency = epoch with no repairs; mean_ci ignores those (nanmean)
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
        latency_vals = [r.mean_repair_latency_ms for r in reports]

        avail_m, avail_ci = mean_ci(avail_vals)
        overhead_m, overhead_ci = mean_ci(overhead_vals)
        repaired_m, repaired_ci = mean_ci(repaired_vals)
        latency_m, latency_ci = mean_ci(latency_vals)

        overhead_vs_fixed = (overhead_m - ref_overhead_mean) / ref_overhead_mean * 100
        avail_vs_fixed = (avail_m - ref_avail_mean) / ref_avail_mean * 100 if ref_avail_mean else 0

        import math
<<<<<<< HEAD
        nines_str = (
            f"{-math.log10(max(1 - avail_m, 1e-15)):.1f} nines"
            if avail_m < 1.0 else "inf nines"
        )

        rows.append({
            "strategy": labels[strategy],
=======
        # 0 dead stripes out of n_stripes only shows availability >= 1 - 1/n_stripes
        nines_str = (
            f"{-math.log10(max(1 - avail_m, 1e-15)):.1f} nines"
            if avail_m < 1.0 else f">={math.log10(n_stripes):.1f} nines (sim limit)"
        )
        o_vals = np.array(oracle_avail[strategy], dtype=float)
        if np.all(np.isnan(o_vals)):
            oracle_str, oracle_nines = "infeasible (k+m > n CSPs)", "n/a"
        else:
            o_m = float(np.nanmean(o_vals))
            oracle_str = f"{o_m:.7f}"
            oracle_nines = f"{-math.log10(max(1 - o_m, 1e-15)):.1f} nines"
        prof_counts = pd.Series(profiles_used[strategy]).value_counts()
        profile_str = ", ".join(f"{p} x{c}" for p, c in prof_counts.items())

        rows.append({
            "strategy": labels[strategy],
            "profile (k,m,c) x repeats": profile_str,
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
            "fleet_availability": f"{avail_m:.6f} ± {avail_ci:.6f}",
            "nines": nines_str,
            "storage_overhead": f"{overhead_m:.4f} ± {overhead_ci:.4f}",
            "bytes_repaired": f"{repaired_m:.0f} ± {repaired_ci:.0f}",
            "mean_repair_latency_ms": f"{latency_m:.2f} ± {latency_ci:.2f}",
            "overhead_vs_fixed_pct": f"{overhead_vs_fixed:+.1f}%",
            "availability_vs_fixed_pct": f"{avail_vs_fixed:+.1f}%",
<<<<<<< HEAD
=======
            "oracle_availability_exact": oracle_str,
            "oracle_nines": oracle_nines,
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
        })

    df = pd.DataFrame(rows)
    df.to_csv(out_tables / f"R4_{regime_name}.csv", index=False)
    print(f"  R4_{regime_name}.csv written")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
<<<<<<< HEAD
    parser.add_argument("--experiment", type=str, default="E3-",
                        help="E3- for convergence study, E4- for fleet simulation")
=======
    parser.add_argument("--experiment", type=str, default="E3-all",
                        help="E3-<regime|all> for convergence study, "
                             "E4-<regime|all> for fleet simulation")
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
    parser.add_argument("--repeats", type=int, default=10)
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    regimes_path = project_root / "config" / "regimes.yaml"
    default_path = project_root / "config" / "default.yaml"

    with open(regimes_path) as f:
        regimes_cfg = yaml.safe_load(f)["regimes"]
    with open(default_path) as f:
        default_cfg = yaml.safe_load(f)

    out_tables = project_root / "results" / "tables"
    out_figures = project_root / "results" / "figures"
    ensure_dir(out_tables)
    ensure_dir(out_figures)

<<<<<<< HEAD
    # Shared environment RNG (reproduces same availability draw as 03 script)
    rng_env = np.random.default_rng(42)

    for regime_name, params in regimes_cfg.items():
        print(f"Running {args.experiment} on regime: {regime_name}")

        if args.experiment.startswith("E3"):
            run_e3(regime_name, params, default_cfg, out_tables, out_figures,
                   args.repeats, rng_env)
        elif args.experiment.startswith("E4"):
            run_e4(regime_name, params, default_cfg, out_tables, out_figures,
                   args.repeats, rng_env)
        else:
            print(f"Unknown experiment {args.experiment}. Use E3- or E4-.")
=======
    exp_kind, _, regime_sel = args.experiment.partition("-")
    regime_sel = regime_sel or "all"
    if exp_kind not in ("E3", "E4"):
        parser.error(f"Unknown experiment {args.experiment}. Use E3-<regime|all> or E4-<regime|all>.")
    if regime_sel != "all" and regime_sel not in regimes_cfg:
        parser.error(f"Unknown regime '{regime_sel}'. Choose from "
                     f"{list(regimes_cfg)} or 'all'.")

    base_seed = int(default_cfg["stats"]["base_seed"])
    seed_mgr = SeedManager(base_seed)

    # regime_index is the position in regimes.yaml, so seeding is identical to
    # script 03 regardless of which regimes are selected here.
    for regime_index, (regime_name, params) in enumerate(regimes_cfg.items()):
        if regime_sel != "all" and regime_name != regime_sel:
            continue
        print(f"Running {exp_kind} on regime: {regime_name}")
        # Same per-regime environment RNG as script 03
        env_seed = [base_seed, regime_index]
        rng_env = np.random.default_rng(env_seed)

        if exp_kind == "E3":
            run_e3(regime_name, regime_index, params, default_cfg, out_tables,
                   out_figures, args.repeats, rng_env, env_seed, seed_mgr)
        else:
            run_e4(regime_name, regime_index, params, default_cfg, out_tables,
                   out_figures, args.repeats, rng_env, env_seed, seed_mgr)
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794


if __name__ == "__main__":
    main()
