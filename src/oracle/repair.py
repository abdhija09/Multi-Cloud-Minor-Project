"""Repair network bandwidth and cross-cloud reconstruction cost estimation."""
from typing import Any, Sequence, Union
import numpy as np


def per_repair_bandwidth(k: int, chunk_size: Union[int, float]) -> float:
    """
    Compute network bandwidth required to repair a single lost chunk.

    Repairing an erasure-coded chunk requires downloading k surviving chunks
    of size chunk_size.

    Parameters
    ----------
    k : int
        Number of chunks required for reconstruction.
    chunk_size : int or float
        Size of each chunk in bytes or KB.

    Returns
    -------
    float
        Total network bandwidth consumed (k * chunk_size).
    """
    return float(k * chunk_size)


def fleet_repair_cost(
    stripes: Sequence[Any],
    failure_rates: Union[float, int, np.ndarray, Sequence[float], dict],
) -> float:
    """
    Compute fleet repair cost per epoch.

    Sum over stripes of: expected lost chunks per epoch * k * chunk_size.

    Parameters
    ----------
    stripes : sequence
        Iterable of stripes (e.g. Stripe dataclass or dicts) with k, chunk_size,
        and optionally m, csp_map.
    failure_rates : float, array-like, or dict
        Failure probability or rate per chunk per epoch. If scalar, applied
        uniformly to all chunks. If dict or array, mapped to chunks via csp_map
        or chunk index.

    Returns
    -------
    float
        Fleet-wide expected repair cost / bandwidth.
    """
    total_cost = 0.0

    for stripe in stripes:
        k = stripe.k if hasattr(stripe, "k") else stripe["k"]
        chunk_size = stripe.chunk_size if hasattr(stripe, "chunk_size") else stripe["chunk_size"]
        m = stripe.m if hasattr(stripe, "m") else stripe.get("m", 0)
        csp_map = getattr(stripe, "csp_map", None)
        if csp_map is None and isinstance(stripe, dict):
            csp_map = stripe.get("csp_map", None)

        n_chunks = k + m

        # Compute expected number of lost chunks in this stripe during the epoch
        if isinstance(failure_rates, (int, float)):
            expected_lost = n_chunks * float(failure_rates)
        elif isinstance(failure_rates, dict):
            if csp_map is not None:
                expected_lost = sum(float(failure_rates.get(p, 0.0)) for p in csp_map[:n_chunks])
            else:
                expected_lost = sum(float(failure_rates.get(i, 0.0)) for i in range(n_chunks))
        elif isinstance(failure_rates, (list, tuple, np.ndarray)):
            fr_arr = np.asarray(failure_rates, dtype=np.float64)
            if csp_map is not None:
                expected_lost = sum(float(fr_arr[p]) for p in csp_map[:n_chunks])
            elif len(fr_arr) == n_chunks:
                expected_lost = float(np.sum(fr_arr))
            else:
                expected_lost = sum(float(fr_arr[i % len(fr_arr)]) for i in range(n_chunks))
        else:
            expected_lost = 0.0

        stripe_cost = expected_lost * k * chunk_size
        total_cost += stripe_cost

    return float(total_cost)
