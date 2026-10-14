"""Unit tests for Galois field arithmetic operations."""
import itertools
import numpy as np
from rs.galois import gf_mul, gf_inv, vandermonde, gf_inverse

def naive_mul(a: int, b: int) -> int:
    """Carry-less polynomial multiplication mod 0x11D."""
    p = 0
    for _ in range(8):
        if (b & 1) != 0:
            p ^= a
        hi = (a & 0x80) != 0
        a <<= 1
        if hi:
            a ^= 0x11D
        b >>= 1
    return p

def test_gf_mul_exhaustive():
    """gf_mul equals naive carry-less polynomial multiply mod 0x11D for ALL 65,536 pairs."""
    for a in range(256):
        for b in range(256):
            assert gf_mul(a, b) == naive_mul(a, b)

def test_gf_inv():
    """gf_inv(a)*a == 1 for a in 1..255."""
    for a in range(1, 256):
        assert gf_mul(gf_inv(a), a) == 1

def test_vandermonde():
    """every kxk submatrix of vandermonde(k+m,k) is invertible for a few (k,m) samples."""
    for k, m in [(4, 2), (6, 3), (10, 4)]:
        G = vandermonde(k + m, k)
        assert np.array_equal(G[:k, :k], np.eye(k, dtype=np.uint8))
        
        # Test every kxk submatrix by picking k rows from k+m
        for cols in itertools.combinations(range(k + m), k):
            sub = G[list(cols), :]
            # If sub is not invertible, gf_inverse will raise ValueError
            inv = gf_inverse(sub)
            assert inv is not None
