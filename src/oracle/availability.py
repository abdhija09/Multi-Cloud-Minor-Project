"""Monte Carlo and analytical multi-cloud data availability evaluation."""
import itertools
from typing import Tuple
import numpy as np


def closed_form_availability(k: int, m: int, avail: np.ndarray) -> float:
    """
    Exact analytical availability for an (k, m) erasure coding stripe.

    Exact: sum over all subsets S of {0..k+m-1} with |S| >= k of:
        prod_{j in S} a_j * prod_{j not in S} (1 - a_j)

    avail has length k+m (per-chunk host availability).
    Only used for validation on small k+m.

    Parameters
    ----------
    k : int
        Number of data chunks needed to reconstruct the stripe.
    m : int
        Number of parity chunks.
    avail : np.ndarray
        Per-chunk host availability probabilities of length k + m.

    Returns
    -------
    float
        Exact analytical availability probability.
    """
    n = k + m
    avail = np.asarray(avail, dtype=np.float64)
    if len(avail) != n:
        raise ValueError(f"avail length ({len(avail)}) must match k + m ({n})")
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0

    unavail = 1.0 - avail
    all_indices = set(range(n))
    total_avail = 0.0

    for r in range(k, n + 1):
        for subset in itertools.combinations(range(n), r):
            s_set = set(subset)
            p_surv = float(np.prod(avail[list(subset)])) if subset else 1.0
            not_s = list(all_indices - s_set)
            p_fail = float(np.prod(unavail[not_s])) if not_s else 1.0
            total_avail += p_surv * p_fail

    return float(total_avail)


def monte_carlo_availability(
    k: int,
    m: int,
    avail: np.ndarray,
    n_runs: int = 10000,
    seed: int = 7,
) -> Tuple[float, float]:
    """
    Estimate availability via Monte Carlo simulation.

    Draw n_runs Bernoulli survival vectors with numpy:
        rng.random((n_runs, k+m)) < avail
    Count rows with >= k survivors, return (estimate, standard_error)
    where SE = sqrt(p * (1 - p) / n_runs).

    Parameters
    ----------
    k : int
        Number of data chunks required for reconstruction.
    m : int
        Number of parity chunks.
    avail : np.ndarray
        Per-chunk host availability probabilities of length k + m.
    n_runs : int, optional
        Number of Monte Carlo trials (default 10000).
    seed : int, optional
        Random seed for simulation (default 7).

    Returns
    -------
    tuple[float, float]
        (estimate, standard_error) where SE = sqrt(p * (1 - p) / n_runs).
    """
    n = k + m
    avail = np.asarray(avail, dtype=np.float64)
    if len(avail) != n:
        raise ValueError(f"avail length ({len(avail)}) must match k + m ({n})")
    if n_runs <= 0:
        raise ValueError(f"n_runs must be positive, got {n_runs}")
    if k <= 0:
        return 1.0, 0.0
    if k > n:
        return 0.0, 0.0

    rng = np.random.default_rng(seed)
    # Shape: (n_runs, n). Boolean mask of survivors per chunk
    surv_matrix = rng.random((n_runs, n)) < avail
    surviving_counts = np.sum(surv_matrix, axis=1)
    successes = np.sum(surviving_counts >= k)

    estimate = float(successes / n_runs)
    se = float(np.sqrt(estimate * (1.0 - estimate) / n_runs))
    return estimate, se


def fit_availability(failure_trace_df) -> np.ndarray:
    """
    Fit availability / failure rates from failure trace DataFrame.

    Thin wrapper calling utils.traces.fit_failure_rates (implemented in phase 6).
    """
    from utils.traces import fit_failure_rates
    return fit_failure_rates(failure_trace_df)
