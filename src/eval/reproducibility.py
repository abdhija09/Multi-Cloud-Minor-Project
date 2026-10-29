"""
Reproducibility utilities: deterministic seed management, repeated-run
statistics, and significance testing.
"""

from __future__ import annotations

<<<<<<< HEAD
import inspect
from typing import Callable, Any
=======
import re
from pathlib import Path
from typing import Callable
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794

import numpy as np
import pandas as pd
import scipy.stats as stats
<<<<<<< HEAD


# Experiment name → stable integer ID (extended as needed)
_EXPERIMENT_IDS: dict[str, int] = {}
_next_id = 0


def _experiment_id(name: str) -> int:
    global _next_id
    if name not in _EXPERIMENT_IDS:
        _EXPERIMENT_IDS[name] = _next_id
        _next_id += 1
    return _EXPERIMENT_IDS[name]
=======
import yaml


_EXPERIMENTS_YAML = Path(__file__).resolve().parents[2] / "config" / "experiments.yaml"


def experiment_id(experiment: str | int) -> int:
    """
    Stable integer id of an experiment, independent of call order.

    - int                    -> itself
    - 'E<n>' / 'E<n>-<suffix>' (e.g. 'E3', 'E3-low', 'e4_all') -> n
    - otherwise: the 1-based position of the name in config/experiments.yaml,
      matched against the 'E<n>' key or the experiment's 'name' field.
    Raises ValueError if the experiment cannot be resolved.
    """
    if isinstance(experiment, (int, np.integer)) and not isinstance(experiment, bool):
        return int(experiment)
    name = str(experiment).strip()
    m = re.match(r"^[Ee](\d+)(?:$|[-_ ])", name)
    if m:
        return int(m.group(1))
    try:
        with open(_EXPERIMENTS_YAML) as f:
            exps = yaml.safe_load(f)["experiments"]
    except (OSError, KeyError, TypeError):
        exps = {}
    for pos, (key, cfg) in enumerate(exps.items(), start=1):
        if name == key or (isinstance(cfg, dict) and name == cfg.get("name")):
            km = re.match(r"^[Ee](\d+)$", key)
            return int(km.group(1)) if km else pos
    raise ValueError(f"Unknown experiment {experiment!r}: use an int, 'E<n>[-suffix]', "
                     "or a key/name from config/experiments.yaml")
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794


class SeedManager:
    """
    Deterministic seed factory.

    seed_for(experiment, repeat) = base_seed * 10**6 + experiment_id * 10**3 + repeat

<<<<<<< HEAD
=======
    experiment_id comes from experiment_id() (stable: 'E3-low' -> 3), so the
    same (experiment, repeat) always gets the same seed in any process.
    Seeds are unique as long as experiment_id < 1000 and repeat < 1000.

>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
    Parameters
    ----------
    base_seed : int
        Global base seed (default 42).
    """

    def __init__(self, base_seed: int = 42):
<<<<<<< HEAD
        self.base_seed = base_seed

    def seed_for(self, experiment: str, repeat: int) -> int:
        eid = _experiment_id(experiment)
        return self.base_seed * 10**6 + eid * 10**3 + repeat
=======
        self.base_seed = int(base_seed)

    def seed_for(self, experiment: str | int, repeat: int) -> int:
        if not 0 <= int(repeat) < 1000:
            raise ValueError(f"repeat must be in [0, 1000), got {repeat}")
        eid = experiment_id(experiment)
        return self.base_seed * 10**6 + eid * 10**3 + int(repeat)
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794


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
<<<<<<< HEAD
    pd.DataFrame with columns [metric, mean, std, ci_lower, ci_upper, ci_95]
=======
    pd.DataFrame with columns [metric, n, mean, std, ci_lower, ci_upper, ci_95]
        std is the sample std (ddof=1); ci_95 is the half-width of the 95%
        t-interval (t_{0.975, n-1} * std / sqrt(n)). With n == 1 the spread is
        undefined: std and ci_95 are reported as 0.0 (not NaN) so the CI
        collapses to the single observation.
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
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
<<<<<<< HEAD
        std  = float(np.std(a, ddof=1))
        se   = std / np.sqrt(n)
        t_crit = float(stats.t.ppf(0.975, df=n - 1)) if n > 1 else 0.0
        half_ci = t_crit * se
        rows.append({
            "metric":   metric,
=======
        if n > 1:
            std = float(np.std(a, ddof=1))
            half_ci = float(stats.t.ppf(0.975, df=n - 1)) * std / np.sqrt(n)
        else:
            std, half_ci = 0.0, 0.0
        rows.append({
            "metric":   metric,
            "n":        n,
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
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
