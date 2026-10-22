"""
Corpus utilities for loading real and synthetic data for roundtrip tests.
"""

import os
import zipfile
from pathlib import Path
from typing import NamedTuple, Optional

import numpy as np

MB = 1024 * 1024

# Fallback corpus when Silesia is absent: one random file of each size.
SYNTHETIC_SIZES_MB = (1, 2, 4, 8, 16)


def load_silesia(path) -> list[tuple[str, bytes]]:
    """
    Load files from the Silesia corpus.

    Accepts either:
    - A directory containing the unzipped Silesia files (hidden files skipped).
    - A zip archive (silesia.zip) produced by the official download.

    Returns a list of (name, data_bytes) tuples sorted by name.
    Raises FileNotFoundError if the path does not exist or holds no files,
    and zipfile.BadZipFile if the archive is corrupt / partially downloaded.
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
            if p.is_file() and not p.name.startswith("."):
                results.append((p.name, p.read_bytes()))
    elif zipfile.is_zipfile(path) or path.suffix == ".zip":
        with zipfile.ZipFile(path, "r") as zf:
            for name in sorted(zf.namelist()):
                base = os.path.basename(name)
                if zf.getinfo(name).is_dir() or not base or base.startswith(".") \
                        or name.startswith("__MACOSX/"):
                    continue
                results.append((base, zf.read(name)))
    else:
        # Treat as a single file
        results.append((path.name, path.read_bytes()))

    if not results:
        raise FileNotFoundError(f"No files found in Silesia location {path}.")
    return results


def find_silesia(data_dir) -> Optional[Path]:
    """
    Locate the Silesia corpus under *data_dir*.

    Prefers the unzipped directory ``data_dir/silesia`` (if it holds at least
    one non-hidden file), else ``data_dir/silesia.zip``. Returns None if neither
    is present.
    """
    data_dir = Path(data_dir)
    d = data_dir / "silesia"
    if d.is_dir() and any(p.is_file() and not p.name.startswith(".") for p in d.iterdir()):
        return d
    z = data_dir / "silesia.zip"
    if z.is_file():
        return z
    return None


class ChunkSet(NamedTuple):
    """Result of make_chunks. Unpacks as ``chunks, original_len = make_chunks(...)``."""
    chunks: list[np.ndarray]      # list of fixed-size uint8 arrays
    original_length: int          # byte-length before padding


def make_chunks(data: bytes, size: int) -> ChunkSet:
    """
    Split *data* into fixed-size uint8 numpy arrays of length *size*.

    The last chunk is zero-padded to exactly *size* bytes. Empty data gives
    no chunks. The original length is returned so callers can unpad after
    decode: ``b"".join(c.tobytes() for c in chunks)[:original_len] == data``.
    """
    if size <= 0:
        raise ValueError(f"chunk size must be positive, got {size}")
    original_length = len(data)
    remainder = len(data) % size
    if remainder != 0:
        data = data + b"\x00" * (size - remainder)

    chunks = [
        np.frombuffer(data[offset: offset + size], dtype=np.uint8).copy()
        for offset in range(0, len(data), size)
    ]
    return ChunkSet(chunks=chunks, original_length=original_length)


def synthetic_files(
    sizes_mb=SYNTHETIC_SIZES_MB,
    seed: int = 0,
) -> list[tuple[str, bytes]]:
    """
    Generate one uniformly random binary file per size in *sizes_mb*
    (default 1, 2, 4, 8, 16 MB). Fallback corpus when Silesia is absent.
    """
    rng = np.random.default_rng(seed)
    return [
        (f"synthetic_{s}MB.bin", rng.integers(0, 256, size=int(s * MB), dtype=np.uint8).tobytes())
        for s in sizes_mb
    ]
