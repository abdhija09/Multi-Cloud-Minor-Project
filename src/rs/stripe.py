"""Data striping, chunk management, and layout structures for erasure-coded storage."""
import hashlib
import random
from dataclasses import dataclass
import numpy as np
from rs.codec import encode, decode

@dataclass
class Stripe:
    stripe_id: str
    k: int
    m: int
    chunk_size: int
    csp_map: list[int]
    sha256: str

def verify_roundtrip(stripe: Stripe, original: bytes, n_subsets: int = 10, seed: int = 0) -> bool:
    """
    Pad original data, encode it, then verify that random k-subsets can correctly
    reconstruct the original data.
    """
    rnd = random.Random(seed)
    target_size = stripe.k * stripe.chunk_size
    
    pad_len = target_size - len(original)
    if pad_len < 0:
        raise ValueError("Original data is larger than stripe capacity")
        
    padded = original + b'\x00' * pad_len
    
    chunks = []
    for i in range(stripe.k):
        chunk_bytes = padded[i * stripe.chunk_size : (i + 1) * stripe.chunk_size]
        chunks.append(np.frombuffer(chunk_bytes, dtype=np.uint8))
        
    encoded_chunks = encode(stripe.k, stripe.m, chunks)
    original_hash = hashlib.sha256(original).hexdigest()
    
    for _ in range(n_subsets):
        indices = rnd.sample(range(stripe.k + stripe.m), stripe.k)
        available = [(idx, encoded_chunks[idx]) for idx in indices]
        
        decoded_chunks = decode(stripe.k, stripe.m, available)
        
        decoded_bytes = b"".join(c.tobytes() for c in decoded_chunks)
        unpadded = decoded_bytes[:len(original)]
        
        if hashlib.sha256(unpadded).hexdigest() != original_hash:
            return False
            
    return True
