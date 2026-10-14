"""
Corpus utilities for loading real and synthetic data for roundtrip tests.
"""

import os
import zipfile
from pathlib import Path
from typing import NamedTuple

import numpy as np


def load_silesia(path) -> list[tuple[str, bytes]]:
    """
    Load files from the Silesia corpus.

    Accepts either:
    - A directory containing the raw Silesia files.
    - A zip archive (silesia.zip) produced by the official download.

    Returns a list of (name, data_bytes) tuples, one per corpus file.
    If the path does not exist, raises FileNotFoundError.
    """
    path = Path(path)
    results: list[tuple[str, bytes]] = []

    if not path.exists():
        raise FileNotFoundError(
            f"Silesia corpus not found at {path}. "
            "Run bash scripts/01_download_datasets.sh to download it."
        )

    if path.is_dir():
        for p in sorted(path.iterdir()):
            if p.is_file():
                results.append((p.name, p.read_bytes()))
    elif path.suffix == ".zip" or str(path).endswith(".zip"):
        with zipfile.ZipFile(path, "r") as zf:
            for name in sorted(zf.namelist()):
                info = zf.getinfo(name)
                if not info.is_dir():
                    results.append((os.path.basename(name), zf.read(name)))
    else:
        # Treat as a single file
        results.append((path.name, path.read_bytes()))

    return results


class ChunkSet(NamedTuple):
    """Result of make_chunks – carries the padded chunks and original length."""
    chunks: list[np.ndarray]      # list of fixed-size uint8 arrays
    original_length: int           # byte-length before padding


def make_chunks(data: bytes, size: int) -> ChunkSet:
    """
    Split *data* into fixed-size uint8 numpy arrays of length *size*.

    The last chunk is zero-padded to exactly *size* bytes.
    The original length is stored in the returned ChunkSet so callers can
    unpad after decode.

    Parameters
    ----------
    data : bytes
        Raw input data.
    size : int
        Target chunk size in bytes.

    Returns
    -------
    ChunkSet(chunks, original_length)
    """
    original_length = len(data)
    # Pad data so it is an exact multiple of size
    remainder = len(data) % size
    if remainder != 0:
        data = data + b"\x00" * (size - remainder)

    chunks = []
    for offset in range(0, len(data), size):
        arr = np.frombuffer(data[offset: offset + size], dtype=np.uint8).copy()
        chunks.append(arr)

    return ChunkSet(chunks=chunks, original_length=original_length)


def synthetic_files(
    n: int = 5,
    min_bytes: int = 1 * 1024 * 1024,
    max_bytes: int = 16 * 1024 * 1024,
    seed: int = 0,
) -> list[tuple[str, bytes]]:
    """
    Generate *n* synthetic binary files with sizes between min_bytes and max_bytes.

    Used as a fallback when the Silesia corpus is not available.
    """
    rng = np.random.default_rng(seed)
    files = []
    for i in range(n):
        size = int(rng.integers(min_bytes, max_bytes + 1))
        data = bytes(rng.integers(0, 256, size=size, dtype=np.uint8))
        files.append((f"synthetic_{i:02d}.bin", data))
    return files
