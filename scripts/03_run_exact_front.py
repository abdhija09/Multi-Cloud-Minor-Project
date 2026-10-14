import os
import yaml
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

from oracle.memo import AvailabilityTable
from search.base import Problem, knee_point
from baselines.enumerate import exact_pareto
from eval.metrics import nines

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
    
    out_tables = project_root / "results" / "tables"
    out_figures = project_root / "results" / "figures"
    ensure_dir(out_tables)
    ensure_dir(out_figures)
    
    rng = np.random.default_rng(42)
    
    for regime_name, params in regimes_cfg.items():
        print(f"Processing regime: {regime_name}")
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
            k_idx = knee_point(front)
            knee_p = front.points[k_idx]
            knee_obj = front.objective_vectors[k_idx]
            
            k_knee, m_knee, c_idx = knee_p
            chunk_kb_knee = chunk_sizes[c_idx]
            
            A_knee = -knee_obj[0]
            overhead = knee_obj[1]
            repair_bw = knee_obj[2]
            
            nines_str = nines(A_knee)
        else:
            k_knee, m_knee, chunk_kb_knee = -1, -1, -1
            A_knee, overhead, repair_bw = 0.0, 0.0, 0.0
            nines_str = "0 nines"
            
        # Write R2
        df = pd.DataFrame([{
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
        }])
        df.to_csv(out_tables / f"R2_{regime_name}.csv", index=False)
        
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
