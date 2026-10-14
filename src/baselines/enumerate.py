import numpy as np
from search.base import ParetoFront, Problem

def exact_pareto(problem: Problem) -> ParetoFront:
    """
    Compute the exact Pareto front by exhaustive enumeration.
    
    Loops over all k, m, c_idx. Skips infeasible configurations.
    Returns the non-dominated set (minimisation on all three columns).
    """
    points = []
    objectives = []
    
    for k in range(1, problem.max_k + 1):
        for m in range(0, problem.max_m + 1):
            if not problem.feasible(k, m):
                continue
            for c_idx in range(len(problem.chunk_sizes)):
                obj = problem.evaluate(k, m, c_idx)
                if not np.any(np.isinf(obj)):
                    points.append([k, m, c_idx])
                    objectives.append(obj)
                    
    if not points:
        return ParetoFront(
            points=np.empty((0, 3), dtype=int),
            objective_vectors=np.empty((0, 3), dtype=float)
        )
        
    points = np.array(points, dtype=int)
    objectives = np.array(objectives, dtype=float)
    
    # Identify non-dominated points (minimisation)
    # A point is dominated if another point is <= in all objectives and < in at least one.
    n_points = len(points)
    is_dominated = np.zeros(n_points, dtype=bool)
    
    for i in range(n_points):
        if is_dominated[i]:
            continue
        # Compare point i with all other points j
        # objectives[j] <= objectives[i] and objectives[j] < objectives[i] in at least one
        # If any j dominates i, i is dominated.
        diff = objectives - objectives[i]
        # (diff <= 0).all(axis=1) means j is <= i in all objectives
        # (diff < 0).any(axis=1) means j is < i in at least one objective
        dominates_i = (diff <= 0).all(axis=1) & (diff < 0).any(axis=1)
        if dominates_i.any():
            is_dominated[i] = True
            
    non_dominated_indices = ~is_dominated
    
    return ParetoFront(
        points=points[non_dominated_indices],
        objective_vectors=objectives[non_dominated_indices]
    )
