from search.base import SearchAlgorithm

class BPSO(SearchAlgorithm):
    name = "BPSO"
    
    def optimize(self, problem, seed):
        raise NotImplementedError("extension")
