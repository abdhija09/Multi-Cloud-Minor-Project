"""
Trace parsers and loaders for cloud storage availability and failure datasets.

Supports the Azure Public Dataset 2019 VM table (vmtable.csv.gz) and
falls back to synthetic data when the file is absent.
"""

import zlib
from pathlib import Path
from typing import Optional, Sequence, Union

import numpy as np
import pandas as pd

AZURE_VM_COLUMNS = [
    "vmid", "subscriptionid", "deploymentid", "vmcreated", "vmdeleted",
    "maxcpu", "avgcpu", "p95maxcpu", "vmcategory", "vmcorecountbucket",
    "vmmemorybucket",
]


def load_azure_vm_traces(path) -> Optional[pd.DataFrame]:
    """
    Load the Azure Public Dataset 2019 VM table (vmtable.csv.gz).

    The published file has NO header row; columns are assigned from
    AZURE_VM_COLUMNS. If a header row is present anyway it is dropped.

    Returns None (after printing a clear message) if the file is absent;
    callers then use the synthetic fallback in fit_failure_rates(None, ...).
    """
    path = Path(path)
    if not path.exists():
        print(
            f"[traces] Azure VM trace file not found: {path}\n"
            "  Returning None; fit_failure_rates() will use the synthetic\n"
            "  fallback (uniform in the regime range, fixed seed).\n"
            "  To use real traces, run: bash scripts/01_download_datasets.sh"
        )
        return None

    print(f"[traces] Loading Azure VM traces from {path} ...")
    df = pd.read_csv(path, compression="infer", header=None,
                     names=AZURE_VM_COLUMNS, low_memory=False)
    if len(df) and str(df.iloc[0]["vmid"]).strip().lower() == "vmid":
        df = df.iloc[1:].reset_index(drop=True)
    print(f"[traces] Loaded {len(df):,} VM records.")
    return df


def _csp_index(x, n_csps: int) -> int:
    """Stable (process-independent) bucket: crc32(str(x)) mod n_csps."""
    return zlib.crc32(str(x).encode()) % n_csps


def fit_failure_rates(
    df: Optional[pd.DataFrame],
    n_csps: int,
    failure_prob_range: Sequence[float] = (1e-3, 1e-2),
    seed: Union[int, Sequence[int]] = 42,
) -> np.ndarray:
    """
    Estimate per-pseudo-provider failure probabilities from a VM trace DataFrame.

    Heuristic
    ---------
    1. Compute each VM's lifetime = vmdeleted - vmcreated.
    2. Compute the 5th percentile of all lifetimes as a "premature termination"
       threshold.  VMs whose lifetime falls below this threshold are considered
       to represent a node failure event.
    3. Bucket each VM's deploymentid into a pseudo-CSP with
       zlib.crc32(str(deploymentid)) % n_csps (stable across processes,
       unlike the salted built-in hash()).
    4. For each pseudo-CSP, compute the fraction of its VMs that terminated
       prematurely.  This fraction is treated as the CSP's failure probability.
    5. Clip to [1e-4, 1e-1] to keep values physically plausible.

    The heuristic is intentionally coarse: real failure rates depend on many
    factors (hardware class, geographic region, workload), but this gives a
    reproducible, data-driven prior that can be refined with richer traces.

    Synthetic fallback: if df is None (trace absent), returns
        1 - default_rng(seed).uniform(1 - hi, 1 - lo, n_csps)
    (clipped as above), i.e. exactly the failure probabilities implied by the
    availability draw the experiment scripts make. With
    seed=[base_seed, regime_index] this equals 1 - (CSP availabilities of
    scripts 03 / 04-E3 / 04-E4 repeat 0) for that regime.

    Parameters
    ----------
    df : pd.DataFrame or None
        VM trace table as returned by load_azure_vm_traces().
    n_csps : int
        Number of pseudo-CSPs (providers) to produce.
    failure_prob_range : (lo, hi)
        Regime range used only by the synthetic fallback.
    seed : int or sequence of int
        numpy SeedSequence entropy, used only by the synthetic fallback.

    Returns
    -------
    np.ndarray of shape (n_csps,)
        Per-CSP failure probability, clipped to [1e-4, 1e-1].
    """
    if df is None:
        lo, hi = float(failure_prob_range[0]), float(failure_prob_range[1])
        avail = np.random.default_rng(seed).uniform(1.0 - hi, 1.0 - lo, size=n_csps)
        return np.clip(1.0 - avail, 1e-4, 1e-1)

    df = df.copy()
    df["lifetime"] = pd.to_numeric(df["vmdeleted"], errors="coerce") - \
                     pd.to_numeric(df["vmcreated"], errors="coerce")
    df = df.dropna(subset=["lifetime"])
    df["lifetime"] = df["lifetime"].clip(lower=0)

    p5_lifetime = float(df["lifetime"].quantile(0.05))

    df["premature"] = df["lifetime"] < p5_lifetime

    df["csp_idx"] = df["deploymentid"].apply(lambda d: _csp_index(d, n_csps))

    failure_probs = np.full(n_csps, 1e-4)
    grouped = df.groupby("csp_idx")["premature"]
    for idx, group in grouped:
        failure_probs[int(idx)] = float(group.mean())

    return np.clip(failure_probs, 1e-4, 1e-1)
