"""
05_run_adaptation.py

Medium regime, 6 CSPs, 1,000 stripes, 10 repeats.
30 epochs; at epoch 10 multiply failure probability of CSPs 0 and 1 by 5.

Strategies:
  adaptive : NSGA-II + AdaptationController
  static   : fixed knee profile from epoch 0

Outputs:
  results/tables/R5.csv
  results/figures/drift_timeline.png
"""

import os
import yaml
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import scipy.stats as st
from pathlib import Path

from oracle.memo import AvailabilityTable
from search.base import Problem, knee_point
from search.nsga2 import NSGA2
from baselines.enumerate import exact_pareto
from simulator.csp import CSP
from simulator.fleet import Fleet
from adaptation.controller import AdaptationController


def ensure_dir(p):
    os.makedirs(p, exist_ok=True)


def mean_ci(data, confidence=0.95):
    a = np.asarray(data, dtype=float)
    n = len(a)
    if n < 2:
        return float(np.mean(a)), 0.0
    m, se = np.mean(a), st.sem(a)
    h = se * st.t.ppf((1 + confidence) / 2.0, n - 1)
    return float(m), float(h)


def build_csps(availabilities: np.ndarray) -> list[CSP]:
    return [
        CSP(csp_id=i, availability=float(a),
            capacity_bytes=10 * 1024**3,
            unit_storage_cost=0.02, unit_egress_cost=0.09,
            latency_ms=20.0 + i * 5.0)
        for i, a in enumerate(availabilities)
    ]


def make_problem_factory(default_cfg, chunk_sizes, max_k, max_m):
    """Return a factory: avail_array -> Problem."""
    def factory(avail: np.ndarray) -> Problem:
        oracle = AvailabilityTable(
            csp_avail=avail,
            mc_runs=default_cfg["oracle"]["mc_runs"],
            seed=default_cfg["oracle"]["mc_seed"],
        )
        return Problem(oracle=oracle, n_csps=len(avail),
                       chunk_sizes=chunk_sizes, max_k=max_k, max_m=max_m)
    return factory


def main():
    project_root = Path(__file__).resolve().parent.parent
    with open(project_root / "config" / "regimes.yaml") as f:
        regimes_cfg = yaml.safe_load(f)["regimes"]
    with open(project_root / "config" / "default.yaml") as f:
        default_cfg = yaml.safe_load(f)

    out_tables  = project_root / "results" / "tables"
    out_figures = project_root / "results" / "figures"
    ensure_dir(out_tables)
    ensure_dir(out_figures)

    # ── Configuration ────────────────────────────────────────────────────────
    regime_name = "medium"
    params = regimes_cfg[regime_name]
    csp_count = params["csp_count"]               # 6
    fail_prob_min, fail_prob_max = float(params["failure_prob_range"][0]), float(params["failure_prob_range"][1])
    n_stripes  = 1000
    n_repeats  = default_cfg["stats"]["repeats"]  # 10
    base_seed  = default_cfg["stats"]["base_seed"]
    n_epochs   = 30
    drift_epoch = 10
    drift_factor = 5.0
    avail_floor = 0.999

    chunk_sizes = default_cfg["rs"]["chunk_sizes_kb"]
    max_k = default_cfg["rs"]["max_k"]
    max_m = default_cfg["rs"]["max_m"]
    algo_cfg  = default_cfg["search"]
    adap_cfg  = default_cfg["adaptation"]

    problem_factory = make_problem_factory(default_cfg, chunk_sizes, max_k, max_m)

    nsga2 = NSGA2(
        pop_size=algo_cfg["pop_size"],
        generations=algo_cfg["generations"],
        mutation_rate=algo_cfg["mutation_rate"],
        crossover_rate=algo_cfg["crossover_rate"],
    )

    # ── Per-repeat accumulators ──────────────────────────────────────────────
    # Shape (n_repeats, n_epochs) for availability timeline
    adap_avail_all  = np.zeros((n_repeats, n_epochs))
    static_avail_all = np.zeros((n_repeats, n_epochs))

    detection_latencies = []   # epochs from drift_epoch until controller first triggers
    reopt_seconds_list  = []
    post_drift_avail_adap   = []
    post_drift_avail_static = []
    post_drift_overhead_adap   = []
    post_drift_overhead_static = []
    bytes_reencoded_list = []
    epochs_to_5pct_list  = []

    for rep in range(n_repeats):
        seed = base_seed + rep
        rng = np.random.default_rng(seed)

        # Baseline failure probs (pre-drift)
        base_fail_probs = rng.uniform(fail_prob_min, fail_prob_max, size=csp_count)
        base_avail = 1.0 - base_fail_probs

        # Initial problem & optimal knee
        init_problem = problem_factory(base_avail)
        init_front   = nsga2.optimize(init_problem, seed=seed)
        k_idx0 = knee_point(init_front)
        if k_idx0 == -1:
            k0, m0, c_idx0 = 4, 2, 0
        else:
            k0 = int(init_front.points[k_idx0, 0])
            m0 = int(init_front.points[k_idx0, 1])
            c_idx0 = int(init_front.points[k_idx0, 2])
        static_chunk_bytes = chunk_sizes[c_idx0] * 1024

        # Post-drift optimal (for "within 5% of new optimum" metric)
        drifted_fail_probs = base_fail_probs.copy()
        drifted_fail_probs[:2] = np.minimum(drifted_fail_probs[:2] * drift_factor, 0.9999)
        drifted_avail = 1.0 - drifted_fail_probs
        drift_problem  = problem_factory(drifted_avail)
        drift_front    = nsga2.optimize(drift_problem, seed=seed)
        k_idx_d = knee_point(drift_front)
        if k_idx_d != -1:
            obj_d = drift_front.objective_vectors[k_idx_d]
            opt_avail_post_drift = -obj_d[0]
        else:
            opt_avail_post_drift = None

        # Adaptive controller
        controller = AdaptationController(
            optimizer=nsga2,
            problem_factory=problem_factory,
            nominal_failure_probs=base_fail_probs,
            epsilon=adap_cfg["epsilon"],
            beta=adap_cfg["beta"],
            seed=seed,
        )
        # Start with initial knee profile
        adap_k, adap_m = k0, m0
        adap_chunk_bytes = static_chunk_bytes
        controller.set_fleet_state((adap_k, adap_m, adap_chunk_bytes), n_stripes)

        rep_detection_latency = None
        rep_reopt_seconds     = 0.0
        rep_bytes_reencoded   = 0
        rep_triggered         = False

        for epoch in range(n_epochs):
            # Current failure probs (drift applied after epoch >= drift_epoch)
            cur_fail_probs = base_fail_probs.copy()
            if epoch >= drift_epoch:
                cur_fail_probs[:2] = np.minimum(
                    cur_fail_probs[:2] * drift_factor, 0.9999)

            cur_avail = 1.0 - cur_fail_probs
            csps = build_csps(cur_avail)

            # Adaptive fleet
            adap_assignment = Fleet.assign_from_profile(
                adap_k, adap_m, adap_chunk_bytes, n_stripes)
            adap_fleet   = Fleet(csps, adap_assignment, seed)
            adap_report  = adap_fleet.simulate_epoch(seed + epoch)

            # Static fleet
            static_assignment = Fleet.assign_from_profile(
                k0, m0, static_chunk_bytes, n_stripes)
            static_fleet  = Fleet(csps, static_assignment, seed)
            static_report = static_fleet.simulate_epoch(seed + epoch)

            adap_avail_all[rep, epoch]   = adap_report.availability
            static_avail_all[rep, epoch] = static_report.availability

            # Controller step: observe failure rates from CSP survival
            ctrl_result = controller.step(cur_fail_probs)
            if ctrl_result is not None and not rep_triggered:
                rep_triggered = True
                rep_detection_latency = epoch - drift_epoch
                rep_reopt_seconds     = ctrl_result["reopt_seconds"]
                rep_bytes_reencoded   = ctrl_result["bytes_reencoded"]
                # Update adaptive profile
                adap_k, adap_m, adap_chunk_bytes = ctrl_result["new_profile"]
                controller.set_fleet_state(
                    (adap_k, adap_m, adap_chunk_bytes), n_stripes)

        # Post-drift window: epochs 10..29
        post_adap   = adap_avail_all[rep, drift_epoch:]
        post_static = static_avail_all[rep, drift_epoch:]

        post_drift_avail_adap.append(np.mean(post_adap))
        post_drift_avail_static.append(np.mean(post_static))

        # Storage overhead for adaptive post-drift
        post_drift_overhead_adap.append(
            (adap_k + adap_m) / adap_k if adap_k > 0 else 0)
        post_drift_overhead_static.append(
            (k0 + m0) / k0 if k0 > 0 else 0)

        detection_latencies.append(
            rep_detection_latency if rep_detection_latency is not None
            else n_epochs - drift_epoch)
        reopt_seconds_list.append(rep_reopt_seconds)
        bytes_reencoded_list.append(rep_bytes_reencoded)

        # Epochs to within 5% of new optimum (adaptive)
        if opt_avail_post_drift is not None:
            threshold = 0.95 * opt_avail_post_drift
            e_5pct = n_epochs - drift_epoch   # default: never
            for e_rel, a in enumerate(post_adap):
                if a >= threshold:
                    e_5pct = e_rel
                    break
            epochs_to_5pct_list.append(e_5pct)
        else:
            epochs_to_5pct_list.append(float("nan"))

    # ── R5 Table ─────────────────────────────────────────────────────────────
    def fmt(data):
        m, ci = mean_ci([x for x in data if not (isinstance(x, float) and np.isnan(x))])
        return f"{m:.4f} ± {ci:.4f}"

    r5_rows = [
        {"metric": "detection_latency_epochs",
         "adaptive": fmt(detection_latencies), "static": "N/A"},
        {"metric": "reopt_seconds",
         "adaptive": fmt(reopt_seconds_list), "static": "N/A"},
        {"metric": "post_drift_availability",
         "adaptive": fmt(post_drift_avail_adap),
         "static":   fmt(post_drift_avail_static)},
        {"metric": "post_drift_overhead",
         "adaptive": fmt(post_drift_overhead_adap),
         "static":   fmt(post_drift_overhead_static)},
        {"metric": "bytes_reencoded",
         "adaptive": fmt(bytes_reencoded_list), "static": "0"},
        {"metric": "epochs_to_within_5pct_of_new_optimum",
         "adaptive": fmt(epochs_to_5pct_list), "static": "N/A"},
    ]
    df_r5 = pd.DataFrame(r5_rows)
    df_r5.to_csv(out_tables / "R5.csv", index=False)
    print("R5.csv written.")

    # ── Drift timeline figure ─────────────────────────────────────────────────
    mean_adap   = np.mean(adap_avail_all,   axis=0)
    std_adap    = np.std(adap_avail_all,    axis=0)
    mean_static = np.mean(static_avail_all, axis=0)
    std_static  = np.std(static_avail_all,  axis=0)
    epochs_x    = np.arange(n_epochs)

    # Detect median trigger epoch across repeats
    med_trigger = drift_epoch + np.nanmedian(detection_latencies)

    plt.figure(figsize=(10, 6))
    plt.plot(epochs_x, mean_adap,   label="Adaptive (NSGA-II)",  color="steelblue")
    plt.fill_between(epochs_x,
                     mean_adap - std_adap,
                     mean_adap + std_adap, alpha=0.25, color="steelblue")
    plt.plot(epochs_x, mean_static, label="Static (epoch-0 knee)", color="tomato",
             linestyle="--")
    plt.fill_between(epochs_x,
                     mean_static - std_static,
                     mean_static + std_static, alpha=0.20, color="tomato")

    plt.axvline(drift_epoch,  color="orange",  linestyle=":",
                label=f"Drift epoch ({drift_epoch})")
    plt.axvline(med_trigger,  color="purple",  linestyle="-.",
                label=f"Controller trigger (median ≈ {med_trigger:.0f})")

    plt.xlabel("Epoch"); plt.ylabel("Fleet Availability")
    plt.title("Drift Timeline – Medium Regime (1 000 stripes)")
    plt.legend(); plt.grid(True, linestyle="--", alpha=0.6)
    plt.tight_layout()
    plt.savefig(out_figures / "drift_timeline.png")
    plt.close()
    print("drift_timeline.png written.")


if __name__ == "__main__":
    main()
