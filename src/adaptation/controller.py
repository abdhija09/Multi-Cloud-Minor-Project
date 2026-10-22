import time
from typing import Callable, Optional

import numpy as np
from scipy.stats import binomtest

from adaptation.monitor import EMAEstimator
from oracle.memo import AvailabilityTable
from search.base import Problem, knee_point, ParetoFront
from search.base import SearchAlgorithm


class AdaptationController:
    """
    Monitors per-CSP failure rates via EMA and triggers re-optimisation
    when the maximum relative deviation exceeds epsilon.

    Parameters
    ----------
    optimizer       : SearchAlgorithm – used to re-run after a trigger.
    problem_factory : Callable[[np.ndarray], Problem]
                      Given a 1-D array of *availability* values (one per CSP),
                      returns a fully constructed Problem with a fresh
                      AvailabilityTable. Problem.chunk_sizes MUST be in
                      bytes: new_profile = (k, m, chunk_size_bytes) is
                      applied to the fleet as-is.
    nominal_failure_probs : np.ndarray
                      Initial per-CSP failure probabilities.
    epsilon         : float – relative-deviation threshold (default 0.10).
    beta            : float – EMA smoothing coefficient (default 0.3).
    seed            : int   – optimiser seed used after a trigger.
    alpha           : float – significance level of the drift test (default 0.05).

    Significance gate: a CSP only counts as drifted when its EMA deviates by
    more than epsilon AND a two-sided binomial test on the chunks it lost /
    held since the last reset rejects its nominal rate at alpha / n_csps
    (Bonferroni over CSPs). With ~2-3 losses per CSP per epoch a single epoch
    is mostly noise; the test waits until the counts are strong enough.
    The gate is used only when step() receives lost/placed counts.
    """

    def __init__(
        self,
        optimizer: SearchAlgorithm,
        problem_factory: Callable[[np.ndarray], Problem],
        nominal_failure_probs: np.ndarray,
        epsilon: float = 0.10,
        beta: float = 0.3,
        seed: int = 0,
        alpha: float = 0.05,
    ):
        self.optimizer = optimizer
        self.problem_factory = problem_factory
        self.epsilon = epsilon
        self.seed = seed
        self.alpha = alpha
        self.beta = beta

        self._nominal = np.array(nominal_failure_probs, dtype=float)
        # EMA starts at the nominal rate (the prior), not at the first observation
        self._estimators = [EMAEstimator(beta=beta, initial=float(p)) for p in self._nominal]
        # Lost / placed chunk counts per CSP since the last reset (significance gate)
        self._lost = np.zeros(len(self._nominal))
        self._placed = np.zeros(len(self._nominal))

        # Track current profile (k, m, chunk_size) for counting changed stripes
        self._current_profile: Optional[tuple[int, int, int]] = None
        self._n_stripes: int = 0

    def set_fleet_state(self, profile: tuple[int, int, int], n_stripes: int) -> None:
        """Record the current fleet assignment so the controller can compute deltas."""
        self._current_profile = profile
        self._n_stripes = n_stripes

    def _significant(self) -> np.ndarray:
        """Per-CSP flag: binomial test on counts since last reset rejects nominal."""
        level = self.alpha / len(self._nominal)
        flags = np.zeros(len(self._nominal), dtype=bool)
        for j, (lost, placed, nom) in enumerate(zip(self._lost, self._placed, self._nominal)):
            if placed <= 0 or not (0.0 < nom < 1.0):
                continue
            p_value = binomtest(int(lost), int(placed), float(nom)).pvalue
            flags[j] = p_value < level
        return flags

    def step(
        self,
        observed_failure_rates: np.ndarray,
        lost_counts: Optional[np.ndarray] = None,
        placed_counts: Optional[np.ndarray] = None,
    ) -> Optional[dict]:
        """
        Update EMAs; check deviation; trigger re-optimisation if needed.

        lost_counts / placed_counts (optional, per CSP, this epoch) switch on
        the significance gate described in the class docstring.

        Returns None if no trigger, otherwise a dict with:
            triggered, delta, new_profile (k,m,chunk_size),
            reopt_seconds, changed_stripes, bytes_reencoded.
        """
        use_gate = lost_counts is not None and placed_counts is not None
        if use_gate:
            self._lost += np.nan_to_num(np.asarray(lost_counts, dtype=float))
            self._placed += np.nan_to_num(np.asarray(placed_counts, dtype=float))

        # --- Update EMAs ---
        # NaN = no observation this epoch (e.g. the CSP held no chunks):
        # leave that CSP's EMA untouched.
        for i, obs in enumerate(observed_failure_rates):
            obs = float(obs)
            if np.isfinite(obs):
                self._estimators[i].update(obs)

        # --- Compute max relative deviation ---
        deviations = np.array([
            est.relative_deviation(nom)
            for est, nom in zip(self._estimators, self._nominal)
        ])
        delta = float(np.max(deviations))

        if use_gate:
            drifted = (deviations > self.epsilon) & self._significant()
            if not drifted.any():
                return None
        elif delta <= self.epsilon:
            return None

        # --- Trigger: rebuild problem with EMA-derived availabilities ---
        ema_failure_probs = np.array([
            est.value if est.value is not None else nom
            for est, nom in zip(self._estimators, self._nominal)
        ])
        ema_availabilities = 1.0 - ema_failure_probs

        t0 = time.perf_counter()
        new_problem = self.problem_factory(ema_availabilities)
        front: ParetoFront = self.optimizer.optimize(new_problem, seed=self.seed)
        reopt_seconds = time.perf_counter() - t0

        if len(front.points) == 0:
            return None

        k_idx = knee_point(front)
        knee = front.points[k_idx]
        k_new, m_new, c_idx = int(knee[0]), int(knee[1]), int(knee[2])
        chunk_size_new = int(new_problem.chunk_sizes[c_idx])  # bytes
        new_profile = (k_new, m_new, chunk_size_new)

        # All stripes share one profile, so either every stripe is re-encoded
        # or none is (only when (k, m, c) actually changed).
        changed = self._n_stripes if new_profile != self._current_profile else 0
        bytes_reencoded = changed * (k_new + m_new) * chunk_size_new

        # Reset nominal to current EMA estimates and start counting afresh
        self._nominal = ema_failure_probs.copy()
        self._lost[:] = 0
        self._placed[:] = 0
        self._current_profile = new_profile

        return {
            "triggered": True,
            "delta": delta,
            "new_profile": new_profile,
            "reopt_seconds": reopt_seconds,
            "changed_stripes": changed,
            "bytes_reencoded": bytes_reencoded,
        }
