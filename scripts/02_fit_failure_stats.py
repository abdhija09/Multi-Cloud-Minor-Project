"""
02_fit_failure_stats.py

Fit per-regime failure rates from the Azure VM trace (if present) or
from synthetic data.  Writes results/tables/T0_fit.csv.
"""

import os
import sys
import yaml
import numpy as np
import pandas as pd
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from utils.traces import load_azure_vm_traces, fit_failure_rates


def main():
    project_root = Path(__file__).resolve().parent.parent
    data_dir = project_root / "data"
    azure_path = data_dir / "vmtable.csv.gz"

    with open(project_root / "config" / "regimes.yaml") as f:
        regimes_cfg = yaml.safe_load(f)["regimes"]

    out_dir = project_root / "results" / "tables"
    os.makedirs(out_dir, exist_ok=True)

    # Load traces (falls back to synthetic if file absent)
    df = load_azure_vm_traces(azure_path)
    source = "azure" if azure_path.exists() else "synthetic"

    rows = []
    rng = np.random.default_rng(42)

    for regime_name, params in regimes_cfg.items():
        n_csps = params["csp_count"]
        fail_prob_min = float(params["failure_prob_range"][0])
        fail_prob_max = float(params["failure_prob_range"][1])

        # Fit from trace
        fitted = fit_failure_rates(df, n_csps)

        # Also compute synthetic (uniform draw) for comparison
        synth = rng.uniform(fail_prob_min, fail_prob_max, size=n_csps)

        for csp_idx in range(n_csps):
            rows.append({
                "regime": regime_name,
                "csp_idx": csp_idx,
                "source": source,
                "failure_prob_fitted": round(float(fitted[csp_idx]), 6),
                "failure_prob_range_min": fail_prob_min,
                "failure_prob_range_max": fail_prob_max,
                "failure_prob_synthetic": round(float(synth[csp_idx]), 6),
                "availability_fitted": round(1.0 - float(fitted[csp_idx]), 6),
                "availability_synthetic": round(1.0 - float(synth[csp_idx]), 6),
            })

    df_out = pd.DataFrame(rows)
    out_path = out_dir / "T0_fit.csv"
    df_out.to_csv(out_path, index=False)
    print(f"[02] T0_fit.csv written -> {out_path}  ({len(df_out)} rows, source={source})")


if __name__ == "__main__":
    main()
