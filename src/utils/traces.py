"""
Trace parsers and loaders for cloud storage availability and failure datasets.

Supports the Azure Public Dataset 2019 VM table (vmtable.csv.gz) and
falls back to synthetic data when the file is absent.
"""

import numpy as np
import pandas as pd
from pathlib import Path


def load_azure_vm_traces(path) -> pd.DataFrame:
    """
    Load the Azure Public Dataset 2019 VM table.

    Expected columns: vmid, subscriptionid, deploymentid, vmcreated, vmdeleted,
    maxcpu, avgcpu, p95maxcpu, vmcategory, vmcorecountbucket, vmmemorybucket.

    If the file is absent, prints a clear message and returns a synthetic
    DataFrame that mimics the schema.

    Parameters
    ----------
    path : str or Path
        Path to vmtable.csv.gz.

    Returns
    -------
    pd.DataFrame
    """
    path = Path(path)
    if not path.exists():
        print(
            f"[traces] Azure VM trace file not found: {path}\n"
            "  Falling back to synthetic data.\n"
            "  To use real traces, run: bash scripts/01_download_datasets.sh"
        )
        return _synthetic_vm_table(n=10_000, seed=42)

    print(f"[traces] Loading Azure VM traces from {path} ...")
    df = pd.read_csv(path, compression="gzip", low_memory=False)
    print(f"[traces] Loaded {len(df):,} VM records.")
    return df


def _synthetic_vm_table(n: int = 10_000, seed: int = 42) -> pd.DataFrame:
    """Generate a synthetic VM table that mimics the Azure 2019 schema."""
    rng = np.random.default_rng(seed)
    vm_ids = [f"vm_{i:06d}" for i in range(n)]
    sub_ids = [f"sub_{rng.integers(0, 100):03d}" for _ in range(n)]
    dep_ids = [f"dep_{rng.integers(0, 500):04d}" for _ in range(n)]

    # Lifetimes in seconds; most VMs live a few hours to a few days
    created = rng.integers(0, 86400 * 30, size=n)
    lifetime = rng.exponential(scale=86400 * 5, size=n).astype(int)
    deleted = created + np.maximum(lifetime, 60)  # at least 60 s

    return pd.DataFrame({
        "vmid": vm_ids,
        "subscriptionid": sub_ids,
        "deploymentid": dep_ids,
        "vmcreated": created,
        "vmdeleted": deleted,
        "maxcpu": rng.uniform(0, 100, n),
        "avgcpu": rng.uniform(0, 60, n),
        "p95maxcpu": rng.uniform(0, 90, n),
        "vmcategory": rng.choice(["Delay-insensitive", "Interactive", "Unknown"], n),
        "vmcorecountbucket": rng.choice(["1", "2", "4", "8"], n),
        "vmmemorybucket": rng.choice(["2", "4", "8", "16"], n),
    })


def fit_failure_rates(df: pd.DataFrame, n_csps: int) -> np.ndarray:
    """
    Estimate per-pseudo-provider failure probabilities from a VM trace DataFrame.

    Heuristic
    ---------
    1. Compute each VM's lifetime = vmdeleted - vmcreated.
    2. Compute the 5th percentile of all lifetimes as a "premature termination"
       threshold.  VMs whose lifetime falls below this threshold are considered
       to represent a node failure event.
    3. Hash each VM's deploymentid (modulo n_csps) to assign it to a pseudo-CSP.
    4. For each pseudo-CSP, compute the fraction of its VMs that terminated
       prematurely.  This fraction is treated as the CSP's failure probability.
    5. Clip to [1e-4, 1e-1] to keep values physically plausible.

    The heuristic is intentionally coarse: real failure rates depend on many
    factors (hardware class, geographic region, workload), but this gives a
    reproducible, data-driven prior that can be refined with richer traces.

    Parameters
    ----------
    df : pd.DataFrame
        VM trace table as returned by load_azure_vm_traces().
    n_csps : int
        Number of pseudo-CSPs (providers) to produce.

    Returns
    -------
    np.ndarray of shape (n_csps,)
        Per-CSP failure probability, clipped to [1e-4, 1e-1].
    """
    df = df.copy()
    df["lifetime"] = pd.to_numeric(df["vmdeleted"], errors="coerce") - \
                     pd.to_numeric(df["vmcreated"], errors="coerce")
    df = df.dropna(subset=["lifetime"])
    df["lifetime"] = df["lifetime"].clip(lower=0)

    p5_lifetime = float(df["lifetime"].quantile(0.05))

    df["premature"] = df["lifetime"] < p5_lifetime

    # Hash deploymentid → pseudo-CSP index
    df["csp_idx"] = df["deploymentid"].apply(
        lambda d: hash(str(d)) % n_csps
    )

    failure_probs = np.full(n_csps, 1e-4)
    grouped = df.groupby("csp_idx")["premature"]
    for idx, group in grouped:
        failure_probs[int(idx)] = float(group.mean())

    return np.clip(failure_probs, 1e-4, 1e-1)
