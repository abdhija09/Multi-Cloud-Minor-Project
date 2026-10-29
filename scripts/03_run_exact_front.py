import os
<<<<<<< HEAD
=======
import sys
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
import yaml
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

<<<<<<< HEAD
=======
# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
from oracle.memo import AvailabilityTable
from search.base import Problem, knee_point
from baselines.enumerate import exact_pareto
from eval.metrics import nines
<<<<<<< HEAD
=======
from utils.logging import log_run, run_dir_for, clear_runs

# Run folders: experiments/runs/E2/<regime>_rep0_seed<base_seed>/ (metrics = the R2 row).
EXPERIMENT = "E1"
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def main():
    project_root = Path(__file__).resolve().parent.parent
    regimes_path = project_root / "config" / "regimes.yaml"
    default_path = project_root / "config" / "default.yaml"
    
    with open(regimes_path, "r") as f:
        regimes_cfg = yaml.safe_load(f)["regimes"]
        
    with open(default_path, "r") as f:
        default_cfg = yaml.safe_load(f)
        
    chunk_sizes = default_cfg["rs"]["chunk_sizes_kb"]
    max_k = default_cfg["rs"]["max_k"]
    max_m = default_cfg["rs"]["max_m"]
<<<<<<< HEAD
=======
    base_seed = int(default_cfg["stats"]["base_seed"])
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
    
    out_tables = project_root / "results" / "tables"
    out_figures = project_root / "results" / "figures"
    ensure_dir(out_tables)
    ensure_dir(out_figures)
    
<<<<<<< HEAD
    rng = np.random.default_rng(42)
    
    for regime_name, params in regimes_cfg.items():
        print(f"Processing regime: {regime_name}")
=======
    for regime_index, (regime_name, params) in enumerate(regimes_cfg.items()):
        print(f"Processing regime: {regime_name}")
        # Environment (CSP availability) stream: default_rng([base_seed, regime_index]).
        # Identical in scripts/04 (E3, and E4 repeat 0) and in T0 (script 02),
        # so R2/R3/R4/T0 describe the same fleet; independent of which regimes run.
        env_seed = [base_seed, regime_index]
        rng = np.random.default_rng(env_seed)
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
        csp_count = params["csp_count"]
        fail_prob_min, fail_prob_max = params["failure_prob_range"]
        
        # availabilities in 1 - failure_prob_range
        # failure_prob_range is [min_f, max_f]
        avail_min = 1.0 - float(fail_prob_max)
        avail_max = 1.0 - float(fail_prob_min)
        
        availabilities = rng.uniform(avail_min, avail_max, size=csp_count)
        
        oracle = AvailabilityTable(
            csp_avail=availabilities, 
            mc_runs=default_cfg["oracle"]["mc_runs"], 
            seed=default_cfg["oracle"]["mc_seed"]
        )
        
        problem = Problem(
            oracle=oracle,
            n_csps=csp_count,
            chunk_sizes=chunk_sizes,
            max_k=max_k,
            max_m=max_m
        )
        
        front = exact_pareto(problem)
        n_nondom = len(front.points)
        print(f"  Found {n_nondom} non-dominated points.")
        
        if n_nondom > 0:
<<<<<<< HEAD
            k_idx = knee_point(front)
=======
            k_idx = knee_point(front, avail_floor_eps=1.0 / (2 * default_cfg["oracle"]["mc_runs"]))
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
            knee_p = front.points[k_idx]
            knee_obj = front.objective_vectors[k_idx]
            
            k_knee, m_knee, c_idx = knee_p
            chunk_kb_knee = chunk_sizes[c_idx]
            
            A_knee = -knee_obj[0]
            overhead = knee_obj[1]
            repair_bw = knee_obj[2]
            
<<<<<<< HEAD
            nines_str = nines(A_knee)
=======
            nines_str = nines(A_knee, mc_runs=default_cfg["oracle"]["mc_runs"])
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
        else:
            k_knee, m_knee, chunk_kb_knee = -1, -1, -1
            A_knee, overhead, repair_bw = 0.0, 0.0, 0.0
            nines_str = "0 nines"
            
        # Write R2
<<<<<<< HEAD
        df = pd.DataFrame([{
=======
        r2_row = {
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
            "regime": regime_name,
            "n": csp_count,
            "n_nondominated": n_nondom,
            "k_knee": k_knee,
            "m_knee": m_knee,
            "chunk_kb_knee": chunk_kb_knee,
            "A_knee": A_knee,
            "nines": nines_str,
            "overhead": overhead,
            "repair_bw_bytes": repair_bw * 1024  # Assuming repair_bw objective was in KB if chunk size was in KB
<<<<<<< HEAD
        }])
        df.to_csv(out_tables / f"R2_{regime_name}.csv", index=False)
=======
        }
        df = pd.DataFrame([r2_row])
        df.to_csv(out_tables / f"R2_{regime_name}.csv", index=False)

        clear_runs(EXPERIMENT, prefix=f"{regime_name}_")
        log_run(
            meta={"experiment": EXPERIMENT, "script": "03_run_exact_front.py",
                  "regime": regime_name, "regime_index": regime_index, "repeat": 0,
                  "seed": base_seed, "env_seed": env_seed,
                  "mc_seed": default_cfg["oracle"]["mc_seed"],
                  "mc_runs": default_cfg["oracle"]["mc_runs"],
                  "csp_availabilities": [float(a) for a in availabilities]},
            metrics=r2_row,
            run_dir=run_dir_for(EXPERIMENT, f"{regime_name}_rep0_seed{base_seed}"),
        )
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
        
        # Plot
        if n_nondom > 0:
            plt.figure(figsize=(8, 6))
            A_vals = -front.objective_vectors[:, 0]
            mk_vals = front.objective_vectors[:, 1]
            
            plt.scatter(mk_vals, A_vals, c='blue', alpha=0.5, label='Pareto Front')
            plt.scatter([overhead], [A_knee], c='red', s=100, marker='*', label='Knee Point')
            
            plt.xlabel('Storage Overhead (m/k)')
            plt.ylabel('Availability (A)')
            plt.title(f'Exact Pareto Front - {regime_name.capitalize()} Regime')
            plt.legend()
            plt.grid(True, linestyle='--', alpha=0.7)
            plt.tight_layout()
            
            plt.savefig(out_figures / f"pareto_exact_{regime_name}.png")
            plt.close()

if __name__ == "__main__":
    main()
