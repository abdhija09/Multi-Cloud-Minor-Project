"""Galois field arithmetic operations (GF(2^8)) for Reed-Solomon coding."""
import numpy as np

EXP_TABLE = np.zeros(512, dtype=np.uint16)
LOG_TABLE = np.zeros(256, dtype=np.uint16)

def build_tables(prim=0x11D):
    """Build the exponential and logarithm tables for GF(2^8)."""
    global EXP_TABLE, LOG_TABLE
    EXP_TABLE = np.zeros(512, dtype=np.uint16)
    LOG_TABLE = np.zeros(256, dtype=np.uint16)
    
    val = 1
    for i in range(255):
        EXP_TABLE[i] = val
        LOG_TABLE[val] = i
        val <<= 1
        if val & 0x100:
            val ^= prim
            
    for i in range(255, 512):
        EXP_TABLE[i] = EXP_TABLE[i - 255]

build_tables(0x11D)

def gf_mul(a: int, b: int) -> int:
    """Multiply two field elements."""
    if a == 0 or b == 0:
        return 0
    return int(EXP_TABLE[LOG_TABLE[a] + LOG_TABLE[b]])

def gf_div(a: int, b: int) -> int:
    """Divide two field elements."""
    if a == 0:
        return 0
    if b == 0:
        raise ZeroDivisionError("GF(2^8) division by zero")
    return int(EXP_TABLE[(LOG_TABLE[a] - LOG_TABLE[b]) % 255])

def gf_pow(a: int, e: int) -> int:
    """Exponentiate a field element."""
    if a == 0:
        return 0
    return int(EXP_TABLE[(LOG_TABLE[a] * e) % 255])

def gf_inv(a: int) -> int:
    """Compute the multiplicative inverse of a field element."""
    if a == 0:
        raise ZeroDivisionError("GF(2^8) inversion of zero")
    return int(EXP_TABLE[255 - LOG_TABLE[a]])

def gf_mul_vec(a: np.ndarray, b: int) -> np.ndarray:
    """Multiply a vector of field elements by a scalar element."""
    if b == 0:
        return np.zeros_like(a)
    if b == 1:
        return a.copy()
    
    lut = np.zeros(256, dtype=np.uint8)
    for i in range(256):
        lut[i] = gf_mul(i, b)
    return lut[a]

def gf_matmul(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    """Multiply two matrices over GF(2^8)."""
    res = np.zeros((A.shape[0], B.shape[1]), dtype=np.uint8)
    for i in range(A.shape[0]):
        for j in range(B.shape[1]):
            dot = 0
            for k in range(A.shape[1]):
                dot ^= gf_mul(A[i, k], B[k, j])
            res[i, j] = dot
    return res

def gf_inverse(M: np.ndarray) -> np.ndarray:
    """Compute the inverse of a square matrix over GF(2^8) via Gaussian elimination."""
    n = M.shape[0]
    A = np.hstack((M, np.eye(n, dtype=np.uint8)))
    for i in range(n):
        if A[i, i] == 0:
            for j in range(i + 1, n):
                if A[j, i] != 0:
                    A[[i, j]] = A[[j, i]]
                    break
            else:
                raise ValueError("Matrix is singular")
        
        inv_pivot = gf_inv(A[i, i])
        if inv_pivot != 1:
            for k in range(i, 2*n):
                A[i, k] = gf_mul(A[i, k], inv_pivot)
                
        for j in range(n):
            if i != j and A[j, i] != 0:
                factor = A[j, i]
                for k in range(i, 2*n):
                    A[j, k] ^= gf_mul(A[i, k], factor)
                    
    return A[:, n:]

def vandermonde(rows: int, cols: int) -> np.ndarray:
    """
    Generate a systematic generator matrix G = [I_k | P]^T of shape (rows, cols)
    using a Vandermonde matrix.
    """
    V = np.zeros((rows, cols), dtype=np.uint8)
    for i in range(rows):
        for j in range(cols):
            if i == 0 and j == 0:
                V[i, j] = 1
            elif i == 0:
                V[i, j] = 0
            else:
                V[i, j] = gf_pow(i, j)
                
    top = V[:cols, :cols]
    inv_top = gf_inverse(top)
    return gf_matmul(V, inv_top)
