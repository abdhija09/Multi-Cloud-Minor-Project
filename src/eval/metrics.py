import numpy as np
from pymoo.indicators.hv import HV
from pymoo.indicators.igd import IGD
from search.base import ParetoFront

def hypervolume(front: ParetoFront, reference_point: np.ndarray) -> float:
    """
    Compute Hypervolume (HV) using pymoo.
    reference_point should be worst possible objective values for minimisation.
    """
    if len(front.objective_vectors) == 0:
        return 0.0
    ind = HV(ref_point=np.array(reference_point))
    return ind(front.objective_vectors)

def igd(front: ParetoFront, true_front: ParetoFront) -> float:
    """
    Compute Inverted Generational Distance (IGD) vs the true Pareto front.
    """
    if len(front.objective_vectors) == 0 or len(true_front.objective_vectors) == 0:
        return np.inf
    ind = IGD(true_front.objective_vectors)
    return ind(front.objective_vectors)

<<<<<<< HEAD
def spacing(front: ParetoFront) -> float:
    """
    Schott's spacing metric.
    Measures the standard deviation of distances to nearest neighbors in objective space.
    """
    obj = front.objective_vectors
    if len(obj) < 2:
        return 0.0
        
=======
def spacing(front: ParetoFront, bounds=None) -> float:
    """
    Schott's spacing metric.
    Measures the standard deviation of distances to nearest neighbors in objective space.

    bounds : optional (ideal, nadir) pair of arrays. When given, each objective
    is min-max normalised with them first, so a column with large units
    (k*chunk_size in KB) does not swamp the others. Columns where
    nadir == ideal are left un-scaled (divided by 1).
    """
    obj = np.asarray(front.objective_vectors, dtype=float)
    if len(obj) < 2:
        return 0.0

    if bounds is not None:
        ideal = np.asarray(bounds[0], dtype=float)
        nadir = np.asarray(bounds[1], dtype=float)
        span = nadir - ideal
        span[span == 0] = 1.0
        obj = (obj - ideal) / span

>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
    # Compute L1 distance between all pairs
    # shape: (N, N)
    diff = obj[:, np.newaxis, :] - obj[np.newaxis, :, :]
    dist = np.sum(np.abs(diff), axis=2).astype(float)
    
    # Fill diagonal with infinity to not pick distance to self
    np.fill_diagonal(dist, np.inf)
    
    # Nearest neighbor distances
    d_i = np.min(dist, axis=1)
    
    d_mean = np.mean(d_i)
    
    # Variance sum
    sum_diff = np.sum((d_i - d_mean) ** 2)
    
    # Spacing
    S = np.sqrt(sum_diff / (len(obj) - 1))
    return float(S)

<<<<<<< HEAD
def nines(p: float) -> str:
    """
    Convert availability probability to 'nines' string.
    E.g., 0.99999 -> "5 nines"
    """
    if p >= 1.0:
        return "inf nines"
=======
def nines(p: float, mc_runs: int = 10000) -> str:
    """
    Convert availability probability to 'nines' string.
    E.g., 0.99999 -> "5 nines"

    p == 1.0 comes from a Monte Carlo estimate with zero observed failures, so
    the true value is only known to be beyond the MC resolution of 1/mc_runs.
    That case reports the bound, e.g. ">=4.0 nines (MC limit)" for 10000 runs.
    """
    if p >= 1.0:
        return f">={np.log10(mc_runs):.1f} nines (MC limit)"
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
    if p <= 0.0:
        return "0 nines"
        
    n = -np.log10(1 - p)
    # Round to closest int if very near
    n_round = round(n)
    if abs(n - n_round) < 1e-4:
        return f"{n_round} nines"
    
    return f"{n:.1f} nines"
