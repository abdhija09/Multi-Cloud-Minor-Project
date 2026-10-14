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


def knee_point(front: ParetoFront) -> int:
    """
    Find the index of the knee point in the Pareto front.
    
    The knee point minimizes the Euclidean distance to the utopia point (0, 0, 0)
    after min-max normalizing each objective column.
    If front is empty, returns -1.
    """
    if len(front.points) == 0:
        return -1
    
    obj = front.objective_vectors
    
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
