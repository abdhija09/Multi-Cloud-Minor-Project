"""Memoization cache for expensive objective evaluations."""
from typing import Optional, Union
import numpy as np

from oracle.availability import monte_carlo_availability


class AvailabilityTable:
    """
    Precomputed lookup table and memoization cache for stripe availability.

    Parameters
    ----------
    csp_avail : np.ndarray
        Per-provider availability vector of length n.
    mc_runs : int, optional
        Number of Monte Carlo simulations per cell (default 10000).
    seed : int, optional
        Random seed for simulations (default 7).
    """

    def __init__(self, csp_avail: np.ndarray, mc_runs: int = 10000, seed: int = 7):
        self.csp_avail = np.asarray(csp_avail, dtype=np.float64)
        self.n = len(self.csp_avail)
        self.mc_runs = mc_runs
        self.seed = seed
        self.max_k = 16
        self.max_m = 8
        self._table: Optional[np.ndarray] = None

    def precompute(self, max_k: int = 16, max_m: int = 8) -> None:
        """
        Fills a (max_k + 1, max_m + 1) table once.

        For a stripe of k+m chunks, assign chunks round-robin over the n
        providers: csp_avail[(0..k+m-1) mod n].
        If k+m > n or k <= 0, the profile is infeasible; store NaN.
        """
        self.max_k = max_k
        self.max_m = max_m
        table = np.full((max_k + 1, max_m + 1), np.nan, dtype=np.float64)

        for k in range(1, max_k + 1):
            for m in range(max_m + 1):
                if k + m > self.n:
                    table[k, m] = np.nan
                else:
                    avail_vec = self.csp_avail[np.arange(k + m) % self.n]
                    est, _ = monte_carlo_availability(
                        k, m, avail_vec, n_runs=self.mc_runs, seed=self.seed
                    )
                    table[k, m] = est

        self._table = table

    def invalidate(self, seed: Optional[int] = None) -> None:
        """
        Clears the cached table; next get() recomputes.

        Parameters
        ----------
        seed : int, optional
            Optional new RNG seed for subsequent computations.
        """
        self._table = None
        if seed is not None:
            self.seed = seed

    def get(self, k: int, m: int) -> float:
        """
        Retrieve cached availability for (k, m).

        If k + m > n or k <= 0, returns NaN.
        If table is not yet computed or invalidated, recomputes.
        """
        if k <= 0 or k + m > self.n:
            return float(np.nan)

        if self._table is None:
            self.precompute(self.max_k, self.max_m)

        if k > self.max_k or m > self.max_m:
            self.precompute(max(k, self.max_k), max(m, self.max_m))

        return float(self._table[k, m])

    def objectives(
        self,
        k: int,
        m: int,
        chunk_size: Union[int, float],
    ) -> np.ndarray:
        """
        Evaluate 3-objective vector: [-A, m/k, k*chunk_size].

        If k=0 or profile is infeasible (k+m > n), returns [inf, inf, inf].

        Parameters
        ----------
        k : int
            Number of data chunks.
        m : int
            Number of parity chunks.
        chunk_size : int or float
            Chunk size in bytes or KB.

        Returns
        -------
        np.ndarray
            Array of shape (3,) with [-A, m/k, k*chunk_size] or [inf, inf, inf].
        """
        if k <= 0 or k + m > self.n:
            return np.array([np.inf, np.inf, np.inf], dtype=np.float64)

        A = self.get(k, m)
        if np.isnan(A):
            return np.array([np.inf, np.inf, np.inf], dtype=np.float64)

        return np.array([-A, float(m / k), float(k * chunk_size)], dtype=np.float64)
