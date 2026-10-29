from abc import ABC, abstractmethod
from dataclasses import dataclass
import numpy as np

from oracle.memo import AvailabilityTable


@dataclass
class ParetoFront:
    points: np.ndarray  # Shape: (N, 3), dtype int: [k, m, c_idx]
    objective_vectors: np.ndarray  # Shape: (N, 3), dtype float


@dataclass
class Problem:
    oracle: AvailabilityTable
    n_csps: int
    chunk_sizes: list[int]
    max_k: int = 16
    max_m: int = 8

    def feasible(self, k: int, m: int) -> bool:
        """Check if a (k, m) profile is feasible."""
        return 1 <= k <= self.max_k and 0 <= m <= self.max_m and (k + m) <= self.n_csps

    def evaluate(self, k: int, m: int, c_idx: int) -> np.ndarray:
        """Evaluate the objective vector for a profile."""
        if not self.feasible(k, m):
            return np.array([np.inf, np.inf, np.inf])
        chunk_size = self.chunk_sizes[c_idx]
        return self.oracle.objectives(k, m, chunk_size)


class SearchAlgorithm(ABC):
    name: str

    @abstractmethod
    def optimize(self, problem: Problem, seed: int) -> ParetoFront:
        pass


<<<<<<< HEAD
def knee_point(front: ParetoFront) -> int:
    """
    Find the index of the knee point in the Pareto front.
    
    The knee point minimizes the Euclidean distance to the utopia point (0, 0, 0)
    after min-max normalizing each objective column.
=======
def knee_point(front: ParetoFront, avail_floor_eps: float = 1.0 / (2 * 10000)) -> int:
    """
    Find the index of the knee point in the Pareto front.

    The objective vectors are [-A, m/k, k*chunk_size]. Before picking the knee,
    the availability column is rewritten on the "nines" scale,
    nines = -log10(1 - A), and we minimise -nines. Why: the availability
    differences that matter are orders of magnitude (0.99 vs 0.9999), but on
    the raw -A scale they are tiny numbers that the min-max step flattens, so
    the knee would always slide to the cheapest, least redundant profile.

    Monte Carlo can return A == 1.0 exactly (no failures seen), which would
    make nines infinite. So 1 - A is clipped to a floor of avail_floor_eps,
    which defaults to 1/(2 * mc_runs) for the default mc_runs = 10000, i.e.
    half of the smallest non-zero unavailability MC can resolve.

    After that, all three columns are min-max normalised and the knee is the
    point with the smallest Euclidean distance to the utopia point (0, 0, 0).
    The front's objective_vectors are not modified.
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
    If front is empty, returns -1.
    """
    if len(front.points) == 0:
        return -1
<<<<<<< HEAD
    
    obj = front.objective_vectors
    
=======

    obj = np.array(front.objective_vectors, dtype=float, copy=True)

    # Availability column -> -nines (still minimised)
    unavail = np.clip(1.0 + obj[:, 0], avail_floor_eps, 1.0)  # 1 - A, with A = -obj[:, 0]
    obj[:, 0] = np.log10(unavail)  # = -nines

>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
    # Min-max normalization per column
    col_min = np.min(obj, axis=0)
    col_max = np.max(obj, axis=0)
    
    # Handle the case where all points have the same value for an objective
    range_val = col_max - col_min
    range_val[range_val == 0] = 1.0
    
    norm_obj = (obj - col_min) / range_val
    
    # Utopia point is (0, 0, 0) for minimized objectives
    distances = np.linalg.norm(norm_obj, axis=1)
    
    return int(np.argmin(distances))
