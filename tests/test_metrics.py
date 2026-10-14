import numpy as np
from search.base import ParetoFront
from eval.metrics import hypervolume, igd, spacing, nines

def test_hypervolume():
    # Hand-made 2-point 2-objective front
    # Let's say points are (1, 4) and (4, 1) and reference point is (5, 5)
    # Area = (5-1)*(5-4) + (5-4)*(5-1) - overlap = 4*1 + 1*4 - ? 
    # Wait, area dominated by (1,4) is (5-1)*(5-4) = 4*1 = 4.
    # Area dominated by (4,1) is (5-4)*(5-1) = 1*4 = 4.
    # Intersection is (5-4)*(5-4) = 1*1 = 1.
    # Total area = 4 + 4 - 1 = 7.
    
    obj = np.array([
        [1, 4],
        [4, 1]
    ])
    front = ParetoFront(points=np.empty((2,3)), objective_vectors=obj)
    ref = np.array([5, 5])
    hv = hypervolume(front, ref)
    assert np.isclose(hv, 7.0)
    
def test_igd():
    # IGD of a front against itself is 0
    obj = np.array([
        [1, 4, 1],
        [4, 1, 1],
        [2, 2, 2]
    ])
    front = ParetoFront(points=np.empty((3,3)), objective_vectors=obj)
    val = igd(front, front)
    assert np.isclose(val, 0.0)
    
def test_spacing():
    # Spacing of evenly spaced points is ~0
    # Let's create points spaced equally in L1
    obj = np.array([
        [1, 9],
        [2, 8],
        [3, 7],
        [4, 6]
    ])
    front = ParetoFront(points=np.empty((4,3)), objective_vectors=obj)
    val = spacing(front)
    assert np.isclose(val, 0.0)
    
def test_nines():
    assert nines(0.99999) == "5 nines"
    assert nines(0.99) == "2 nines"
    assert nines(1.0) == "inf nines"
    assert nines(0.0) == "0 nines"
