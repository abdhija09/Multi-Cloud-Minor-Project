"""Unit tests for Galois field arithmetic operations."""
import itertools
import random
import pytest
import numpy as np
from rs.galois import gf_mul, gf_inv, gf_div, gf_pow, build_tables, vandermonde, gf_inverse, gf_matmul

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

def test_vandermonde_largest_case_sampled():
    """k=16, m=8: 200 random k-row subsets (fixed seed) are all invertible."""
    k, m = 16, 8
    G = vandermonde(k + m, k)
    assert np.array_equal(G[:k, :k], np.eye(k, dtype=np.uint8))
    rng = random.Random(1234)
    for _ in range(200):
        rows = sorted(rng.sample(range(k + m), k))
        inv = gf_inverse(G[rows, :])
        assert np.array_equal(gf_matmul(G[rows, :], inv), np.eye(k, dtype=np.uint8))


def test_gf_div_exhaustive():
    """gf_mul(gf_div(a, b), b) == a for all a in 0..255, b in 1..255."""
    for a in range(256):
        for b in range(1, 256):
            assert gf_mul(gf_div(a, b), b) == a
    assert gf_div(1, 2) == 142


def test_gf_div_by_zero():
    with pytest.raises(ZeroDivisionError):
        gf_div(5, 0)


def test_build_tables_returns_tables():
    exp, log = build_tables(0x11D)
    assert exp.shape == (512,)
    assert log.shape == (256,)
    for a in range(1, 256):
        assert exp[log[a]] == a


def test_gf_pow_matches_repeated_mul():
    """gf_pow(a, e) equals repeated gf_mul for all a and e in 0..300."""
    for a in range(256):
        acc = 1
        for e in range(301):
            assert gf_pow(a, e) == acc, (a, e)
            acc = gf_mul(acc, a)


def test_gf_pow_zero_cases():
    for a in range(256):
        assert gf_pow(a, 0) == 1
    for e in range(1, 300):
        assert gf_pow(0, e) == 0


def test_gf_pow_negative_exponent():
    for a in range(1, 256):
        inv = gf_inv(a)
        assert gf_pow(a, -1) == inv
        for e in range(1, 20):
            assert gf_pow(a, -e) == gf_pow(inv, e)
            assert gf_mul(gf_pow(a, -e), gf_pow(a, e)) == 1
