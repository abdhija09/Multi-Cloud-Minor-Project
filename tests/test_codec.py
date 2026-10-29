"""Unit tests for Reed-Solomon encoding and decoding."""
import time
import random
import pytest
import numpy as np
from rs.codec import encode, decode, repair
from rs.stripe import Stripe, verify_roundtrip

def test_encode_decode_exhaustive():
    """
    for every k in 1..16, m in 0..8 with k+m <= 24: encode random chunks, 
    decode from 10 random k-subsets, assert exact equality; 
    repair a random lost index and assert equality.
    """
<<<<<<< HEAD
=======
    random.seed(20240601)
    np.random.seed(20240601)
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
    chunk_size = 64
    for k in range(1, 17):
        for m in range(0, 9):
            if k + m > 24:
                continue
                
            chunks = [np.random.randint(0, 256, size=chunk_size, dtype=np.uint8) for _ in range(k)]
            encoded = encode(k, m, chunks)
            
            # Subsets decode
            for _ in range(min(10, 2**(k+m))):
                indices = random.sample(range(k + m), k)
                available = [(idx, encoded[idx]) for idx in indices]
                decoded = decode(k, m, available)
                for i in range(k):
                    assert np.array_equal(chunks[i], decoded[i])
                    
            if m > 0:
                lost_idx = random.randint(0, k + m - 1)
                # Ensure we have k survivors
                survivors = [(i, encoded[i]) for i in range(k + m) if i != lost_idx][:k]
                repaired = repair(k, survivors, lost_idx)
                assert np.array_equal(encoded[lost_idx], repaired)

def test_verify_roundtrip():
<<<<<<< HEAD
=======
    random.seed(7)
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
    stripe = Stripe(stripe_id="s1", k=6, m=3, chunk_size=1024, csp_map=[0]*9, sha256="")
    original = random.randbytes(6 * 1024 - 42) # test padding
    assert verify_roundtrip(stripe, original, n_subsets=5, seed=123)

def test_performance():
    """Performance: encoding 4 chunks of 1 MB must take < 2 s."""
    k = 4
    m = 2
    chunk_size = 1024 * 1024
<<<<<<< HEAD
=======
    np.random.seed(99)
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
    chunks = [np.random.randint(0, 256, size=chunk_size, dtype=np.uint8) for _ in range(k)]
    
    start = time.time()
    _ = encode(k, m, chunks)
    duration = time.time() - start
    
    print(f"Encoding {k} chunks of 1MB with m={m} took {duration:.4f} seconds")
    assert duration < 2.0
<<<<<<< HEAD
=======


def test_decode_rejects_duplicate_indices():
    k, m = 4, 2
    rng = np.random.default_rng(1)
    chunks = [rng.integers(0, 256, size=16, dtype=np.uint8) for _ in range(k)]
    encoded = encode(k, m, chunks)
    available = [(0, encoded[0]), (1, encoded[1]), (1, encoded[1]), (4, encoded[4])]
    with pytest.raises(ValueError, match="duplicate"):
        decode(k, m, available)


def test_repair_rejects_duplicate_indices():
    k, m = 4, 2
    rng = np.random.default_rng(2)
    chunks = [rng.integers(0, 256, size=16, dtype=np.uint8) for _ in range(k)]
    encoded = encode(k, m, chunks)
    survivors = [(0, encoded[0]), (2, encoded[2]), (2, encoded[2]), (5, encoded[5])]
    with pytest.raises(ValueError, match="duplicate"):
        repair(k, survivors, 1)


def test_encode_rejects_too_many_chunks():
    with pytest.raises(AssertionError):
        encode(200, 57, [np.zeros(4, dtype=np.uint8)] * 200)
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
