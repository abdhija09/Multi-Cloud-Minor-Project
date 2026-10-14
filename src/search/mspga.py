from search.base import SearchAlgorithm

class MSPGA(SearchAlgorithm):
    name = "MSPGA"
    
    def optimize(self, problem, seed):
        raise NotImplementedError("extension")
