"""
02_fit_failure_stats.py

<<<<<<< HEAD
Fit per-regime failure rates from the Azure VM trace (if present) or
from synthetic data.  Writes results/tables/T0_fit.csv.
=======
Per-regime, per-CSP failure probabilities -> results/tables/T0_fit.csv
(columns: regime, csp_idx, failure_prob, availability, source, range min/max).

Source
------
- 'azure'     : data/vmtable.csv.gz was loaded (only downloaded with
                `bash scripts/01_download_datasets.sh --with-azure`); values are
                fitted from the trace by utils.traces.fit_failure_rates.
                NOTE: scripts 03-05 do NOT consume these values; they always
                use the synthetic draw below, so with source='azure' T0 is a
                plausibility reference only.
- 'synthetic' : no trace. fit_failure_rates(None, n, failure_prob_range,
                seed=[base_seed, regime_index]) returns
                    1 - default_rng([base_seed, regime_index]).uniform(1-hi, 1-lo, n)
                which is EXACTLY 1 - (the CSP availabilities used by script 03,
                04 E3, and 04 E4 repeat 0) for that regime (asserted below).
                So T0 documents the actual experiment inputs.

Also logs one run folder per regime: experiments/runs/E0/<regime>_rep0_seed<seed>/.
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
"""

import os
import sys
import yaml
import numpy as np
import pandas as pd
from pathlib import Path

<<<<<<< HEAD
# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from utils.traces import load_azure_vm_traces, fit_failure_rates
=======
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from utils.traces import load_azure_vm_traces, fit_failure_rates
from utils.logging import log_run, run_dir_for, clear_runs

EXPERIMENT = "E0"
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794


def main():
    project_root = Path(__file__).resolve().parent.parent
<<<<<<< HEAD
    data_dir = project_root / "data"
    azure_path = data_dir / "vmtable.csv.gz"

    with open(project_root / "config" / "regimes.yaml") as f:
        regimes_cfg = yaml.safe_load(f)["regimes"]
=======
    azure_path = project_root / "data" / "vmtable.csv.gz"

    with open(project_root / "config" / "regimes.yaml") as f:
        regimes_cfg = yaml.safe_load(f)["regimes"]
    with open(project_root / "config" / "default.yaml") as f:
        default_cfg = yaml.safe_load(f)
    base_seed = int(default_cfg["stats"]["base_seed"])
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794

    out_dir = project_root / "results" / "tables"
    os.makedirs(out_dir, exist_ok=True)

<<<<<<< HEAD
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
=======
    df = load_azure_vm_traces(azure_path)          # None if absent
    source = "azure" if df is not None else "synthetic"

    rows = []
    for regime_index, (regime_name, params) in enumerate(regimes_cfg.items()):
        n_csps = params["csp_count"]
        lo, hi = (float(x) for x in params["failure_prob_range"])
        env_seed = [base_seed, regime_index]

        fitted = fit_failure_rates(df, n_csps, failure_prob_range=(lo, hi),
                                   seed=env_seed)

        if df is None:
            # Must equal the availabilities scripts 03/04 draw for this regime.
            avail_used = np.random.default_rng(env_seed).uniform(1.0 - hi, 1.0 - lo,
                                                                  size=n_csps)
            assert np.allclose(fitted, 1.0 - avail_used, rtol=0, atol=1e-15), \
                f"T0 synthetic draw diverged from experiment inputs ({regime_name})"

        regime_rows = []
        for csp_idx in range(n_csps):
            regime_rows.append({
                "regime": regime_name,
                "csp_idx": csp_idx,
                "failure_prob": float(fitted[csp_idx]),
                "availability": 1.0 - float(fitted[csp_idx]),
                "source": source,
                "failure_prob_range_min": lo,
                "failure_prob_range_max": hi,
            })
        rows.extend(regime_rows)

        clear_runs(EXPERIMENT, prefix=f"{regime_name}_")
        log_run(
            meta={"experiment": EXPERIMENT, "script": "02_fit_failure_stats.py",
                  "regime": regime_name, "regime_index": regime_index,
                  "repeat": 0, "seed": base_seed, "env_seed": env_seed,
                  "mc_seed": default_cfg["oracle"]["mc_seed"], "source": source},
            metrics=regime_rows,
            run_dir=run_dir_for(EXPERIMENT, f"{regime_name}_rep0_seed{base_seed}"),
        )
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794

    df_out = pd.DataFrame(rows)
    out_path = out_dir / "T0_fit.csv"
    df_out.to_csv(out_path, index=False)
<<<<<<< HEAD
=======
    print(df_out.to_string(index=False))
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
    print(f"[02] T0_fit.csv written -> {out_path}  ({len(df_out)} rows, source={source})")


if __name__ == "__main__":
    main()
