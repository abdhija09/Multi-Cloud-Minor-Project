"""
04_run_search.py
  --experiment E3-  : NSGA-II vs exact Pareto (hypervolume, IGD, spacing, convergence)
  --experiment E4-  : Fleet simulation comparing Fixed / Greedy / NSGA-II knee
  --repeats N       : number of independent repeats (default 10)
"""

import os
import argparse
import yaml
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import scipy.stats as st

from oracle.memo import AvailabilityTable
from search.base import Problem, knee_point
from baselines.enumerate import exact_pareto
from baselines.greedy import greedy_profile
from search.nsga2 import NSGA2
from eval.metrics import hypervolume, igd, spacing
from simulator.csp import CSP
from simulator.fleet import Fleet, FleetReport


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def mean_ci(data, confidence=0.95):
    a = np.asarray(data, dtype=float)
    n = len(a)
    if n < 2:
        return float(np.mean(a)), 0.0
    m, se = np.mean(a), st.sem(a)
    h = se * st.t.ppf((1 + confidence) / 2.0, n - 1)
    return float(m), float(h)


# ---------------------------------------------------------------------------
# E3 – convergence / quality vs exact Pareto
# ---------------------------------------------------------------------------

def run_e3(regime_name, params, default_cfg, out_tables, out_figures, n_repeats, rng_env):
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

    exact_front = exact_pareto(problem)
    exact_knee_idx = knee_point(exact_front)
    if exact_knee_idx == -1:
        print(f"  No exact front for {regime_name}. Skipping.")
        return
    exact_knee_point = list(exact_front.points[exact_knee_idx])

    worst = np.max(exact_front.objective_vectors, axis=0)
    ref_point = np.where(worst < 0, worst * 0.9, worst * 1.1)
    ref_point[ref_point == 0] = 0.1
    exact_hv = hypervolume(exact_front, ref_point) or 1e-9

    algo_cfg = default_cfg["search"]
    base_seed = default_cfg["stats"]["base_seed"]
    nsga2 = NSGA2(pop_size=algo_cfg["pop_size"], generations=algo_cfg["generations"],
                  mutation_rate=algo_cfg["mutation_rate"],
                  crossover_rate=algo_cfg["crossover_rate"])

    results = {k: [] for k in ["norm_hv", "igd", "spacing", "gens_to_95", "knee_match"]}
    hv_traces = []

    for rep in range(n_repeats):
        seed = base_seed + rep
        final_front, history_fronts = nsga2.optimize_with_history(problem, seed)

        rep_hv = hypervolume(final_front, ref_point)
        results["norm_hv"].append(rep_hv / exact_hv)
        results["igd"].append(igd(final_front, exact_front))
        results["spacing"].append(spacing(final_front))

        algo_knee_idx = knee_point(final_front)
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


def run_e4(regime_name, params, default_cfg, out_tables, out_figures, n_repeats, rng_env):
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

    for rep in range(n_repeats):
        seed = base_seed + rep
        rng_rep = np.random.default_rng(seed)

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

        # ── NSGA-II knee ───────────────────────────────────────────────────
        nsga2 = NSGA2(pop_size=algo_cfg["pop_size"],
                      generations=algo_cfg["generations"],
                      mutation_rate=algo_cfg["mutation_rate"],
                      crossover_rate=algo_cfg["crossover_rate"])
        front = nsga2.optimize(problem, seed=seed)
        k_idx = knee_point(front)
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
        latency_vals = [r.mean_repair_latency_ms for r in reports]

        avail_m, avail_ci = mean_ci(avail_vals)
        overhead_m, overhead_ci = mean_ci(overhead_vals)
        repaired_m, repaired_ci = mean_ci(repaired_vals)
        latency_m, latency_ci = mean_ci(latency_vals)

        overhead_vs_fixed = (overhead_m - ref_overhead_mean) / ref_overhead_mean * 100
        avail_vs_fixed = (avail_m - ref_avail_mean) / ref_avail_mean * 100 if ref_avail_mean else 0

        import math
        nines_str = (
            f"{-math.log10(max(1 - avail_m, 1e-15)):.1f} nines"
            if avail_m < 1.0 else "inf nines"
        )

        rows.append({
            "strategy": labels[strategy],
            "fleet_availability": f"{avail_m:.6f} ± {avail_ci:.6f}",
            "nines": nines_str,
            "storage_overhead": f"{overhead_m:.4f} ± {overhead_ci:.4f}",
            "bytes_repaired": f"{repaired_m:.0f} ± {repaired_ci:.0f}",
            "mean_repair_latency_ms": f"{latency_m:.2f} ± {latency_ci:.2f}",
            "overhead_vs_fixed_pct": f"{overhead_vs_fixed:+.1f}%",
            "availability_vs_fixed_pct": f"{avail_vs_fixed:+.1f}%",
        })

    df = pd.DataFrame(rows)
    df.to_csv(out_tables / f"R4_{regime_name}.csv", index=False)
    print(f"  R4_{regime_name}.csv written")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment", type=str, default="E3-",
                        help="E3- for convergence study, E4- for fleet simulation")
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


if __name__ == "__main__":
    main()
