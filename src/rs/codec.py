"""Reed-Solomon erasure coding encoder and decoder implementation."""
from functools import lru_cache

import numpy as np
from rs.galois import gf_mul_vec, gf_inverse, gf_matmul, vandermonde

MAX_CHUNKS = 256  # GF(2^8) has 256 elements, so at most 256 distinct generator rows.


@lru_cache(maxsize=128)
def _cached_vandermonde(rows: int, cols: int) -> np.ndarray:
    G = vandermonde(rows, cols)
    G.setflags(write=False)
    return G


def _generator(rows: int, cols: int) -> np.ndarray:
    """vandermonde(rows, cols), cached per shape; returns a fresh writable copy."""
    return _cached_vandermonde(rows, cols).copy()


def _check_indices(indices: list[int], what: str) -> None:
    if len(set(indices)) != len(indices):
        dups = sorted({i for i in indices if indices.count(i) > 1})
        raise ValueError(f"{what}: duplicate chunk indices {dups}; need k distinct chunks")
    bad = [i for i in indices if not 0 <= i < MAX_CHUNKS]
    if bad:
        raise ValueError(f"{what}: chunk indices out of range [0, {MAX_CHUNKS}): {bad}")


def encode(k: int, m: int, chunks: list[np.ndarray]) -> list[np.ndarray]:
    """
    Encode k data chunks into k+m chunks (systematic encoding).
    """
    assert k + m <= MAX_CHUNKS, f"k + m must be <= {MAX_CHUNKS} over GF(2^8), got k={k}, m={m}"
    if m == 0:
        return list(chunks)

    G = _generator(k + m, k)
    out = list(chunks)
    
    for i in range(k, k + m):
        parity = np.zeros_like(chunks[0])
        for j in range(k):
            if G[i, j] != 0:
                parity ^= gf_mul_vec(chunks[j], G[i, j])
        out.append(parity)
        
    return out

def decode(k: int, m: int, available: list[tuple[int, np.ndarray]]) -> list[np.ndarray]:
    """
    Decode any k chunks from a set of available chunks back into the k original data chunks.
    """
    assert k + m <= MAX_CHUNKS, f"k + m must be <= {MAX_CHUNKS} over GF(2^8), got k={k}, m={m}"
    if len(available) < k:
        raise ValueError("Not enough chunks to decode")
    _check_indices([idx for idx, _ in available], "decode")

    indices = [idx for idx, _ in available[:k]]
    survivors = [chunk for _, chunk in available[:k]]
    
    rows = max(indices) + 1
    G = _generator(max(rows, k + m), k)
    
    G_sub = np.zeros((k, k), dtype=np.uint8)
    for i, idx in enumerate(indices):
        G_sub[i, :] = G[idx, :]
        
    G_inv = gf_inverse(G_sub)
    
    recovered = []
    for i in range(k):
        rec_chunk = np.zeros_like(survivors[0])
        for j in range(k):
            if G_inv[i, j] != 0:
                rec_chunk ^= gf_mul_vec(survivors[j], G_inv[i, j])
        recovered.append(rec_chunk)
        
    return recovered

def repair(k: int, chunks: list[tuple[int, np.ndarray]], lost_idx: int) -> np.ndarray:
    """
    Rebuild one lost chunk from k survivor chunks.
    """
    if len(chunks) < k:
        raise ValueError("Not enough chunks for repair")
    _check_indices([idx for idx, _ in chunks], "repair")
    if not 0 <= lost_idx < MAX_CHUNKS:
        raise ValueError(f"repair: lost_idx {lost_idx} out of range [0, {MAX_CHUNKS})")

    indices = [idx for idx, _ in chunks[:k]]
    survivors = [chunk for _, chunk in chunks[:k]]
    
    rows = max(max(indices), lost_idx) + 1
    G = _generator(max(rows, k), k)
    
    G_sub = np.zeros((k, k), dtype=np.uint8)
    for i, idx in enumerate(indices):
        G_sub[i, :] = G[idx, :]
        
    G_inv = gf_inverse(G_sub)
    lost_row = G[lost_idx:lost_idx+1, :]
    
    repair_row = gf_matmul(lost_row, G_inv)[0]
    
    rec_chunk = np.zeros_like(survivors[0])
    for j in range(k):
        if repair_row[j] != 0:
            rec_chunk ^= gf_mul_vec(survivors[j], repair_row[j])
            
    return rec_chunk

def repair_bandwidth(k: int, chunk_size: int) -> int:
    """Return the amount of network bandwidth required to repair one chunk."""
    return k * chunk_size
