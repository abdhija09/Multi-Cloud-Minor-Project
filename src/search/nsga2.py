import numpy as np
from pymoo.core.problem import ElementwiseProblem
from pymoo.algorithms.moo.nsga2 import NSGA2 as PymooNSGA2
from pymoo.operators.sampling.rnd import IntegerRandomSampling
from pymoo.operators.crossover.sbx import SBX
from pymoo.operators.mutation.pm import PM
from pymoo.operators.repair.rounding import RoundingRepair
from pymoo.optimize import minimize

from search.base import ParetoFront, Problem, SearchAlgorithm


class _PymooProblemWrapper(ElementwiseProblem):
    def __init__(self, problem: Problem):
        self._problem = problem
        
        # Variables: k, m, c_idx
        xl = np.array([1, 0, 0])
        xu = np.array([problem.max_k, problem.max_m, len(problem.chunk_sizes) - 1])
        
        super().__init__(
            n_var=3,
            n_obj=3,
            xl=xl,
            xu=xu,
            vtype=int
        )
        
    def _evaluate(self, x, out, *args, **kwargs):
        k, m, c_idx = int(x[0]), int(x[1]), int(x[2])
        
        # Repair infeasible configurations
        if k + m > self._problem.n_csps:
            m = max(0, self._problem.n_csps - k)
            # Update x so that returned solutions are consistent
            x[1] = m
            
        obj = self._problem.evaluate(k, m, c_idx)
        out["F"] = obj


class NSGA2(SearchAlgorithm):
    name = "NSGA-II"
    
    def __init__(self, pop_size=50, generations=40, mutation_rate=0.05, crossover_rate=0.9):
        self.pop_size = pop_size
        self.generations = generations
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate

    def _create_algorithm(self):
        return PymooNSGA2(
            pop_size=self.pop_size,
            sampling=IntegerRandomSampling(),
            crossover=SBX(prob=self.crossover_rate, eta=15, vtype=float, repair=RoundingRepair()),
            mutation=PM(prob=self.mutation_rate, eta=20, vtype=float, repair=RoundingRepair()),
            eliminate_duplicates=True
        )

    def optimize(self, problem: Problem, seed: int) -> ParetoFront:
        pymoo_problem = _PymooProblemWrapper(problem)
        algorithm = self._create_algorithm()
        
        res = minimize(
            pymoo_problem,
            algorithm,
            ('n_gen', self.generations),
            seed=seed,
            save_history=False,
            verbose=False
        )
        
        if res.F is None:
            return ParetoFront(
                points=np.empty((0, 3), dtype=int),
                objective_vectors=np.empty((0, 3), dtype=float)
            )
            
        # res.X and res.F might be 1D if only one solution is found
        X = np.atleast_2d(res.X).astype(int)
        F = np.atleast_2d(res.F).astype(float)
        
        return ParetoFront(points=X, objective_vectors=F)

    def optimize_with_history(self, problem: Problem, seed: int):
        """
        Returns (final_front, list_of_fronts_per_generation).
        """
        pymoo_problem = _PymooProblemWrapper(problem)
        algorithm = self._create_algorithm()
        
        res = minimize(
            pymoo_problem,
            algorithm,
            ('n_gen', self.generations),
            seed=seed,
            save_history=True,
            verbose=False
        )
        
        if res.F is None:
            empty_front = ParetoFront(
                points=np.empty((0, 3), dtype=int),
                objective_vectors=np.empty((0, 3), dtype=float)
            )
            return empty_front, []
            
        final_X = np.atleast_2d(res.X).astype(int)
        final_F = np.atleast_2d(res.F).astype(float)
        final_front = ParetoFront(points=final_X, objective_vectors=final_F)
        
        history_fronts = []
        for algo in res.history:
            opt = algo.opt
            if opt is None or len(opt) == 0:
                history_fronts.append(ParetoFront(
                    points=np.empty((0, 3), dtype=int),
                    objective_vectors=np.empty((0, 3), dtype=float)
                ))
            else:
                hist_X = np.atleast_2d(opt.get("X")).astype(int)
                hist_F = np.atleast_2d(opt.get("F")).astype(float)
                history_fronts.append(ParetoFront(points=hist_X, objective_vectors=hist_F))
                
        return final_front, history_fronts
