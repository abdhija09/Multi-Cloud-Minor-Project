from search.base import SearchAlgorithm

class MOEAD(SearchAlgorithm):
    name = "MOEA/D"
    
    def optimize(self, problem, seed):
        raise NotImplementedError("extension")
