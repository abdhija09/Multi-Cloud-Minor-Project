"""
Run logging utilities: write meta.json + metrics.csv per run,
and load all runs for a given experiment.
"""

import json
import csv
import os
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd


def log_run(meta: dict, metrics: dict, run_dir) -> None:
    """
    Persist run metadata and metrics to *run_dir*.

    Creates:
    - ``meta.json``    – experiment metadata (config, timestamps, etc.)
    - ``metrics.csv``  – single-row CSV with all numeric metrics.

    Parameters
    ----------
    meta : dict
        Arbitrary key/value metadata (experiment name, seed, config, …).
    metrics : dict
        Numeric metric name → value.
    run_dir : str or Path
        Directory to write into; created if it does not exist.
    """
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    meta = dict(meta)
    meta.setdefault("timestamp_utc", datetime.now(timezone.utc).isoformat())

    meta_path = run_dir / "meta.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2, default=str)

    metrics_path = run_dir / "metrics.csv"
    write_header = not metrics_path.exists()
    with open(metrics_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(metrics.keys()))
        if write_header:
            writer.writeheader()
        writer.writerow(metrics)


def load_runs(experiment: str, results_root="results") -> pd.DataFrame:
    """
    Load all run directories for a given *experiment* name.

    Scans ``results_root/<experiment>/run_*/metrics.csv`` (and meta.json)
    and returns a combined DataFrame, one row per run.

    Parameters
    ----------
    experiment : str
        Experiment identifier (e.g. "E3-medium").
    results_root : str or Path
        Root of the results directory tree.

    Returns
    -------
    pd.DataFrame  (empty if no runs found)
    """
    results_root = Path(results_root)
    exp_dir = results_root / experiment

    if not exp_dir.exists():
        return pd.DataFrame()

    frames = []
    for run_dir in sorted(exp_dir.glob("run_*")):
        metrics_path = run_dir / "metrics.csv"
        meta_path    = run_dir / "meta.json"

        if not metrics_path.exists():
            continue

        df = pd.read_csv(metrics_path)
        if meta_path.exists():
            with open(meta_path) as f:
                meta = json.load(f)
            for k, v in meta.items():
                df[f"meta_{k}"] = v
        df["run_dir"] = str(run_dir)
        frames.append(df)

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
