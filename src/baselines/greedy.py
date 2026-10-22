import numpy as np
from search.base import Problem

def greedy_profile(problem: Problem, avail_floor: float) -> tuple[int, int, int]:
    """
    Find the profile with minimum m/k among feasible profiles 
    with availability >= avail_floor.
    Ties broken by smaller k * chunk_size.
    Returns (k, m, c_idx).
    """
    best_profile = None
    best_m_k = np.inf
    best_repair = np.inf
    
    for k in range(1, problem.max_k + 1):
        for m in range(0, problem.max_m + 1):
            if not problem.feasible(k, m):
                continue
                
            for c_idx in range(len(problem.chunk_sizes)):
                obj = problem.evaluate(k, m, c_idx)
                if np.any(np.isinf(obj)):
                    continue
                    
                neg_A = obj[0]
                A = -neg_A
                
                if A >= avail_floor:
                    m_k = obj[1]
                    repair = obj[2]
                    
                    if m_k < best_m_k:
                        best_m_k = m_k
                        best_repair = repair
                        best_profile = (k, m, c_idx)
                    elif m_k == best_m_k and repair < best_repair:
                        best_repair = repair
                        best_profile = (k, m, c_idx)
                        
    if best_profile is None:
        raise ValueError(f"No feasible profile found with availability >= {avail_floor}")
        
    return best_profile
