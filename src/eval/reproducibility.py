"""
Reproducibility utilities: deterministic seed management, repeated-run
statistics, and significance testing.
"""

from __future__ import annotations

import inspect
from typing import Callable, Any

import numpy as np
import pandas as pd
import scipy.stats as stats


# Experiment name → stable integer ID (extended as needed)
_EXPERIMENT_IDS: dict[str, int] = {}
_next_id = 0


def _experiment_id(name: str) -> int:
    global _next_id
    if name not in _EXPERIMENT_IDS:
        _EXPERIMENT_IDS[name] = _next_id
        _next_id += 1
    return _EXPERIMENT_IDS[name]


class SeedManager:
    """
    Deterministic seed factory.

    seed_for(experiment, repeat) = base_seed * 10**6 + experiment_id * 10**3 + repeat

    Parameters
    ----------
    base_seed : int
        Global base seed (default 42).
    """

    def __init__(self, base_seed: int = 42):
        self.base_seed = base_seed

    def seed_for(self, experiment: str, repeat: int) -> int:
        eid = _experiment_id(experiment)
        return self.base_seed * 10**6 + eid * 10**3 + repeat


def repeat_run(
    run_fn: Callable[[int], dict[str, float]],
    experiment: str,
    repeats: int = 10,
    seed_manager: SeedManager | None = None,
) -> pd.DataFrame:
    """
    Run *run_fn* independently *repeats* times with reproducible seeds and
    aggregate the results.

    Parameters
    ----------
    run_fn : Callable[[int], dict[str, float]]
        Function that accepts a seed integer and returns a dict of metric
        name → float value.
    experiment : str
        Experiment identifier used for seeding.
    repeats : int
        Number of independent repetitions.
    seed_manager : SeedManager or None
        Custom seed manager; defaults to SeedManager(base_seed=42).

    Returns
    -------
    pd.DataFrame with columns [metric, mean, std, ci_lower, ci_upper, ci_95]
    """
    if seed_manager is None:
        seed_manager = SeedManager()

    raw: dict[str, list[float]] = {}
    for rep in range(repeats):
        seed = seed_manager.seed_for(experiment, rep)
        result = run_fn(seed)
        for k, v in result.items():
            raw.setdefault(k, []).append(float(v))

    rows = []
    for metric, values in raw.items():
        a = np.array(values)
        n = len(a)
        mean = float(np.mean(a))
        std  = float(np.std(a, ddof=1))
        se   = std / np.sqrt(n)
        t_crit = float(stats.t.ppf(0.975, df=n - 1)) if n > 1 else 0.0
        half_ci = t_crit * se
        rows.append({
            "metric":   metric,
            "mean":     mean,
            "std":      std,
            "ci_lower": mean - half_ci,
            "ci_upper": mean + half_ci,
            "ci_95":    half_ci,
        })

    return pd.DataFrame(rows)


def significance_test(a: list[float] | np.ndarray,
                       b: list[float] | np.ndarray) -> float:
    """
    Mann–Whitney U test (two-sided) comparing samples *a* and *b*.

    Returns the p-value.  A small p-value (e.g. < 0.05) indicates that the
    two samples are drawn from different distributions.

    Parameters
    ----------
    a, b : array-like
        Two independent samples.

    Returns
    -------
    float  – two-sided p-value.
    """
    _, p = stats.mannwhitneyu(a, b, alternative="two-sided")
    return float(p)
