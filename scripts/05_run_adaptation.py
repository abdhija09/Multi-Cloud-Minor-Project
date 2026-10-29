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
<<<<<<< HEAD
"""

import os
=======
  experiments/runs/E5/medium_rep<r>_seed<seed>/{meta.json, metrics.csv}

Seeding (deterministic)
  seed (NSGA-II, controller, fleet; epoch e simulates with seed + e)
      = SeedManager(base_seed).seed_for('E5', rep) = base_seed*10**6 + 5*10**3 + rep
  env (nominal CSP failure probs) = 1 - default_rng([base_seed + rep, regime_index])
      .uniform(1 - hi, 1 - lo, n): the same fleet as 04 E4 repeat <rep> for the
      medium regime (repeat 0 == script 03 / E3 / T0).

metrics.csv per run: one row per epoch (epoch, adaptive_A, static_A, triggered,
adaptive_overhead, static_overhead) plus the per-repeat values aggregated into R5,
repeated on every row as rep_* columns.
"""

import os
import sys
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
import yaml
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import scipy.stats as st
from pathlib import Path

<<<<<<< HEAD
=======
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
from oracle.memo import AvailabilityTable
from search.base import Problem, knee_point
from search.nsga2 import NSGA2
from baselines.enumerate import exact_pareto
from simulator.csp import CSP
from simulator.fleet import Fleet
from adaptation.controller import AdaptationController
<<<<<<< HEAD
=======
from eval.reproducibility import SeedManager
from utils.logging import log_run, run_dir_for, clear_runs

EXPERIMENT = "E5"
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794


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
<<<<<<< HEAD
    """Return a factory: avail_array -> Problem."""
=======
    """Return a factory: avail_array -> Problem. chunk_sizes are in BYTES."""
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
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
<<<<<<< HEAD
=======
    regime_index = list(regimes_cfg).index(regime_name)
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
    params = regimes_cfg[regime_name]
    csp_count = params["csp_count"]               # 6
    fail_prob_min, fail_prob_max = float(params["failure_prob_range"][0]), float(params["failure_prob_range"][1])
    n_stripes  = 1000
    n_repeats  = default_cfg["stats"]["repeats"]  # 10
    base_seed  = default_cfg["stats"]["base_seed"]
    n_epochs   = 30
    drift_epoch = 10
    drift_factor = 5.0
<<<<<<< HEAD
    avail_floor = 0.999

    chunk_sizes = default_cfg["rs"]["chunk_sizes_kb"]
=======
    n_post = n_epochs - drift_epoch

    # Units: bytes everywhere a chunk size enters a profile tuple / Problem.
    chunk_sizes = [int(kb) * 1024 for kb in default_cfg["rs"]["chunk_sizes_kb"]]
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
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

<<<<<<< HEAD
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
=======
    def knee_profile(front):
        idx = knee_point(front)
        if idx == -1:
            return None, None
        k, m, c = (int(v) for v in front.points[idx])
        return (k, m, chunk_sizes[c]), float(-front.objective_vectors[idx][0])

    # ── Per-repeat accumulators ──────────────────────────────────────────────
    adap_avail_all   = np.zeros((n_repeats, n_epochs))
    static_avail_all = np.zeros((n_repeats, n_epochs))

    detection_latencies = []   # first trigger at epoch >= drift_epoch, minus drift_epoch
    n_not_detected = 0
    reopt_seconds_list  = []   # summed over ALL triggers in the repeat
    bytes_reencoded_list = []  # summed over ALL triggers in the repeat
    pre_drift_triggers = []    # spurious triggers (epoch < drift_epoch)
    post_drift_triggers = []
    trigger_epochs_all = []
    post_drift_avail_adap, post_drift_avail_static = [], []
    post_drift_overhead_adap, post_drift_overhead_static = [], []
    e5_adap, e5_static = [], []
    e5_not_reached = {"adaptive": 0, "static": 0}
    opt_unavail_list = []

    seed_mgr = SeedManager(base_seed)
    clear_runs(EXPERIMENT, prefix=f"{regime_name}_")

    for rep in range(n_repeats):
        seed = seed_mgr.seed_for(EXPERIMENT, rep)
        env_seed = [base_seed + rep, regime_index]
        rng = np.random.default_rng(env_seed)

        base_avail = rng.uniform(1.0 - fail_prob_max, 1.0 - fail_prob_min, size=csp_count)
        base_fail_probs = 1.0 - base_avail

        # Initial knee (used by Static for all 30 epochs, Adaptive as start)
        init_front = nsga2.optimize(problem_factory(base_avail), seed=seed)
        static_profile, _ = knee_profile(init_front)
        if static_profile is None:
            static_profile = (4, 2, chunk_sizes[0])

        # Oracle optimum under the TRUE drifted probabilities
        drifted_fail_probs = base_fail_probs.copy()
        drifted_fail_probs[:2] = np.minimum(drifted_fail_probs[:2] * drift_factor, 0.9999)
        drift_front = nsga2.optimize(problem_factory(1.0 - drifted_fail_probs), seed=seed)
        drift_opt_profile, opt_avail_post_drift = knee_profile(drift_front)
        opt_unavail_list.append(
            1.0 - opt_avail_post_drift if opt_avail_post_drift is not None else np.nan)

>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
        controller = AdaptationController(
            optimizer=nsga2,
            problem_factory=problem_factory,
            nominal_failure_probs=base_fail_probs,
            epsilon=adap_cfg["epsilon"],
            beta=adap_cfg["beta"],
            seed=seed,
<<<<<<< HEAD
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
=======
            alpha=float(default_cfg["stats"]["alpha"]),
        )
        adap_profile = static_profile
        controller.set_fleet_state(adap_profile, n_stripes)

        rep_trigger_epochs = []
        rep_reopt_seconds = 0.0
        rep_bytes_reencoded = 0
        adap_overheads, static_overheads = [], []
        epoch_log = []

        for epoch in range(n_epochs):
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
            cur_fail_probs = base_fail_probs.copy()
            if epoch >= drift_epoch:
                cur_fail_probs[:2] = np.minimum(
                    cur_fail_probs[:2] * drift_factor, 0.9999)
<<<<<<< HEAD

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
=======
            csps = build_csps(1.0 - cur_fail_probs)

            adap_report = Fleet(
                csps, Fleet.assign_from_profile(*adap_profile, n_stripes), seed
            ).simulate_epoch(seed + epoch)
            static_report = Fleet(
                csps, Fleet.assign_from_profile(*static_profile, n_stripes), seed
            ).simulate_epoch(seed + epoch)

            adap_avail_all[rep, epoch]   = adap_report.availability
            static_avail_all[rep, epoch] = static_report.availability
            if epoch >= drift_epoch:
                adap_overheads.append(adap_report.storage_overhead)
                static_overheads.append(static_report.storage_overhead)

            # Controller sees only what the adaptive fleet observed this epoch:
            # lost / placed chunks per CSP (NaN where nothing was placed).
            observed = adap_report.observed_failure_rates()
            # lost / placed counts switch on the controller's significance gate
            ctrl_result = controller.step(observed,
                                          lost_counts=adap_report.lost_per_csp,
                                          placed_counts=adap_report.placed_per_csp)
            epoch_log.append({
                "epoch": epoch,
                "adaptive_A": float(adap_report.availability),
                "static_A": float(static_report.availability),
                "triggered": int(ctrl_result is not None),
                "adaptive_overhead": float(adap_report.storage_overhead),
                "static_overhead": float(static_report.storage_overhead),
            })
            if ctrl_result is not None:
                # Apply EVERY trigger; new profile takes effect next epoch.
                rep_trigger_epochs.append(epoch)
                rep_reopt_seconds   += ctrl_result["reopt_seconds"]
                rep_bytes_reencoded += ctrl_result["bytes_reencoded"]
                adap_profile = ctrl_result["new_profile"]
                controller.set_fleet_state(adap_profile, n_stripes)

        trigger_epochs_all.append(rep_trigger_epochs)
        pre = [e for e in rep_trigger_epochs if e < drift_epoch]
        post = [e for e in rep_trigger_epochs if e >= drift_epoch]
        pre_drift_triggers.append(len(pre))
        post_drift_triggers.append(len(post))
        if post:
            detection_latencies.append(post[0] - drift_epoch)
        else:
            detection_latencies.append(n_post)   # censored: never detected
            n_not_detected += 1
        reopt_seconds_list.append(rep_reopt_seconds)
        bytes_reencoded_list.append(rep_bytes_reencoded)

        post_adap   = adap_avail_all[rep, drift_epoch:]
        post_static = static_avail_all[rep, drift_epoch:]
        post_drift_avail_adap.append(np.mean(post_adap))
        post_drift_avail_static.append(np.mean(post_static))
        post_drift_overhead_adap.append(np.mean(adap_overheads))
        post_drift_overhead_static.append(np.mean(static_overheads))

        # epochs_to_within_5pct_of_new_optimum, defined on UNAVAILABILITY:
        # first post-drift epoch e (0 = the drift epoch itself) with
        #   (1 - A_epoch) <= 1.05 * (1 - A_opt),
        # where A_opt = oracle (AvailabilityTable, MC) availability of the
        # knee profile of the NSGA-II front built from the TRUE drifted
        # probabilities. (The old 0.95 * A_opt test on availability always
        # passed.) If never reached within the n_post post-drift epochs the
        # repeat is recorded as n_post (censored) and counted as 'not reached'.
        # Caveat: with mc_runs MC trials the oracle cannot resolve
        # unavailability below ~1/mc_runs; if A_opt == 1.0 the target is 0.
        for name, post_arr, store in (("adaptive", post_adap, e5_adap),
                                      ("static", post_static, e5_static)):
            if opt_avail_post_drift is None:
                store.append(float("nan"))
                continue
            target = 1.05 * (1.0 - opt_avail_post_drift)
            hits = np.nonzero((1.0 - post_arr) <= target)[0]
            if len(hits):
                store.append(int(hits[0]))
            else:
                store.append(n_post)
                e5_not_reached[name] += 1

        rep_summary = {
            "rep_detection_latency_epochs": detection_latencies[-1],
            "rep_detected": int(bool(post)),
            "rep_reopt_seconds": rep_reopt_seconds,
            "rep_post_drift_availability_adaptive": float(post_drift_avail_adap[-1]),
            "rep_post_drift_availability_static": float(post_drift_avail_static[-1]),
            "rep_post_drift_overhead_adaptive": float(post_drift_overhead_adap[-1]),
            "rep_post_drift_overhead_static": float(post_drift_overhead_static[-1]),
            "rep_bytes_reencoded": rep_bytes_reencoded,
            "rep_epochs_to_within_5pct_adaptive": e5_adap[-1],
            "rep_epochs_to_within_5pct_static": e5_static[-1],
            "rep_pre_drift_triggers": len(pre),
            "rep_post_drift_triggers": len(post),
            "rep_opt_unavail_post_drift": float(opt_unavail_list[-1]),
        }
        log_run(
            meta={"experiment": EXPERIMENT, "script": "05_run_adaptation.py",
                  "regime": regime_name, "regime_index": regime_index,
                  "repeat": rep, "seed": seed, "base_seed": base_seed,
                  "env_seed": env_seed,
                  "mc_seed": default_cfg["oracle"]["mc_seed"],
                  "mc_runs": default_cfg["oracle"]["mc_runs"],
                  "n_stripes": n_stripes, "n_epochs": n_epochs,
                  "drift_epoch": drift_epoch, "drift_factor": drift_factor,
                  "nominal_failure_probs": [float(x) for x in base_fail_probs],
                  "static_profile": [int(x) for x in static_profile],
                  "drift_opt_profile": [int(x) for x in drift_opt_profile] if drift_opt_profile else None,
                  "final_adaptive_profile": [int(x) for x in adap_profile],
                  "trigger_epochs": [int(e) for e in rep_trigger_epochs],
                  "note": "rep_reopt_seconds is wall-clock and not deterministic"},
            metrics=[{**row, **rep_summary} for row in epoch_log],
            run_dir=run_dir_for(EXPERIMENT, f"{regime_name}_rep{rep}_seed{seed}"),
        )

        print(f"[05] rep {rep}: static={static_profile} drift_opt={drift_opt_profile} "
              f"A_opt={opt_avail_post_drift} final_adaptive={adap_profile} "
              f"triggers={rep_trigger_epochs}")
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794

    # ── R5 Table ─────────────────────────────────────────────────────────────
    def fmt(data):
        m, ci = mean_ci([x for x in data if not (isinstance(x, float) and np.isnan(x))])
        return f"{m:.4f} ± {ci:.4f}"

    r5_rows = [
        {"metric": "detection_latency_epochs",
<<<<<<< HEAD
         "adaptive": fmt(detection_latencies), "static": "N/A"},
=======
         "adaptive": fmt(detection_latencies)
                     + (f" (not detected in {n_not_detected}/{n_repeats}, counted as {n_post})"
                        if n_not_detected else ""),
         "static": "N/A"},
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
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
<<<<<<< HEAD
         "adaptive": fmt(epochs_to_5pct_list), "static": "N/A"},
    ]
    df_r5 = pd.DataFrame(r5_rows)
    df_r5.to_csv(out_tables / "R5.csv", index=False)
    print("R5.csv written.")

    # ── Drift timeline figure ─────────────────────────────────────────────────
=======
         "adaptive": fmt(e5_adap) + (f" (not reached in {e5_not_reached['adaptive']}/{n_repeats}, counted as {n_post})"
                                     if e5_not_reached["adaptive"] else ""),
         "static": fmt(e5_static) + (f" (not reached in {e5_not_reached['static']}/{n_repeats}, counted as {n_post})"
                                     if e5_not_reached["static"] else "")},
        {"metric": "pre_drift_triggers",
         "adaptive": fmt(pre_drift_triggers), "static": "N/A"},
        {"metric": "post_drift_triggers",
         "adaptive": fmt(post_drift_triggers), "static": "N/A"},
    ]
    df_r5 = pd.DataFrame(r5_rows)
    df_r5.to_csv(out_tables / "R5.csv", index=False)
    print(df_r5.to_string(index=False))
    print("R5.csv written.")

    # ── Diagnostics to stdout ────────────────────────────────────────────────
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
    mean_adap   = np.mean(adap_avail_all,   axis=0)
    std_adap    = np.std(adap_avail_all,    axis=0)
    mean_static = np.mean(static_avail_all, axis=0)
    std_static  = np.std(static_avail_all,  axis=0)
<<<<<<< HEAD
    epochs_x    = np.arange(n_epochs)

    # Detect median trigger epoch across repeats
    med_trigger = drift_epoch + np.nanmedian(detection_latencies)
=======
    print("[05] oracle post-drift optimum unavailability per repeat:",
          np.round(opt_unavail_list, 6).tolist())
    print("[05] epoch  adaptive_mean_A  static_mean_A")
    for e in range(n_epochs):
        print(f"[05] {e:5d}  {mean_adap[e]:.4f}  {mean_static[e]:.4f}")

    # ── Drift timeline figure ─────────────────────────────────────────────────
    epochs_x = np.arange(n_epochs)
    med_trigger = drift_epoch + float(np.median(detection_latencies))
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794

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
<<<<<<< HEAD
                label=f"Controller trigger (median ≈ {med_trigger:.0f})")
=======
                label=f"First post-drift trigger (median = {med_trigger:g})")
    # Every trigger (all repeats) as a rug along the bottom of the plot.
    all_trig = [e for reps in trigger_epochs_all for e in reps]
    if all_trig:
        ymin = plt.gca().get_ylim()[0]
        plt.plot(all_trig, [ymin] * len(all_trig), "|", color="purple",
                 markersize=12, alpha=0.4, label="Controller triggers (all repeats)")
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794

    plt.xlabel("Epoch"); plt.ylabel("Fleet Availability")
    plt.title("Drift Timeline – Medium Regime (1 000 stripes)")
    plt.legend(); plt.grid(True, linestyle="--", alpha=0.6)
    plt.tight_layout()
    plt.savefig(out_figures / "drift_timeline.png")
    plt.close()
    print("drift_timeline.png written.")


if __name__ == "__main__":
    main()
