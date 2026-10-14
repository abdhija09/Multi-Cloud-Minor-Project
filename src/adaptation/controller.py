import time
from typing import Callable, Optional

import numpy as np

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
                      AvailabilityTable.
    nominal_failure_probs : np.ndarray
                      Initial per-CSP failure probabilities.
    epsilon         : float – relative-deviation threshold (default 0.10).
    beta            : float – EMA smoothing coefficient (default 0.3).
    seed            : int   – optimiser seed used after a trigger.
    """

    def __init__(
        self,
        optimizer: SearchAlgorithm,
        problem_factory: Callable[[np.ndarray], Problem],
        nominal_failure_probs: np.ndarray,
        epsilon: float = 0.10,
        beta: float = 0.3,
        seed: int = 0,
    ):
        self.optimizer = optimizer
        self.problem_factory = problem_factory
        self.epsilon = epsilon
        self.seed = seed

        self._nominal = np.array(nominal_failure_probs, dtype=float)
        self._estimators = [EMAEstimator(beta=beta) for _ in self._nominal]

        # Track current profile (k, m, chunk_size) for counting changed stripes
        self._current_profile: Optional[tuple[int, int, int]] = None
        self._n_stripes: int = 0

    def set_fleet_state(self, profile: tuple[int, int, int], n_stripes: int) -> None:
        """Record the current fleet assignment so the controller can compute deltas."""
        self._current_profile = profile
        self._n_stripes = n_stripes

    def step(self, observed_failure_rates: np.ndarray) -> Optional[dict]:
        """
        Update EMAs; check deviation; trigger re-optimisation if needed.

        Returns None if no trigger, otherwise a dict with:
            triggered, delta, new_profile (k,m,chunk_size),
            reopt_seconds, changed_stripes, bytes_reencoded.
        """
        # --- Update EMAs ---
        for i, obs in enumerate(observed_failure_rates):
            self._estimators[i].update(float(obs))

        # --- Compute max relative deviation ---
        deviations = np.array([
            est.relative_deviation(nom)
            for est, nom in zip(self._estimators, self._nominal)
        ])
        delta = float(np.max(deviations))

        if delta <= self.epsilon:
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
        chunk_size_new = new_problem.chunk_sizes[c_idx]
        new_profile = (k_new, m_new, chunk_size_new)

        # Changed stripes = all stripes if new profile differs
        changed = self._n_stripes if new_profile != self._current_profile else 0
        bytes_reencoded = (
            changed * (k_new + m_new) * chunk_size_new if changed > 0 else 0
        )

        # Reset nominal to current EMA estimates
        self._nominal = ema_failure_probs.copy()
        self._current_profile = new_profile

        return {
            "triggered": True,
            "delta": delta,
            "new_profile": new_profile,
            "reopt_seconds": reopt_seconds,
            "changed_stripes": changed,
            "bytes_reencoded": bytes_reencoded,
        }
