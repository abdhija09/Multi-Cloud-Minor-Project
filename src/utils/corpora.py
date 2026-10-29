"""
Corpus utilities for loading real and synthetic data for roundtrip tests.
"""

import os
import zipfile
from pathlib import Path
<<<<<<< HEAD
from typing import NamedTuple

import numpy as np

=======
from typing import NamedTuple, Optional

import numpy as np

MB = 1024 * 1024

# Fallback corpus when Silesia is absent: one random file of each size.
SYNTHETIC_SIZES_MB = (1, 2, 4, 8, 16)

>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794

def load_silesia(path) -> list[tuple[str, bytes]]:
    """
    Load files from the Silesia corpus.

    Accepts either:
<<<<<<< HEAD
    - A directory containing the raw Silesia files.
    - A zip archive (silesia.zip) produced by the official download.

    Returns a list of (name, data_bytes) tuples, one per corpus file.
    If the path does not exist, raises FileNotFoundError.
=======
    - A directory containing the unzipped Silesia files (hidden files skipped).
    - A zip archive (silesia.zip) produced by the official download.

    Returns a list of (name, data_bytes) tuples sorted by name.
    Raises FileNotFoundError if the path does not exist or holds no files,
    and zipfile.BadZipFile if the archive is corrupt / partially downloaded.
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
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
<<<<<<< HEAD
            if p.is_file():
                results.append((p.name, p.read_bytes()))
    elif path.suffix == ".zip" or str(path).endswith(".zip"):
        with zipfile.ZipFile(path, "r") as zf:
            for name in sorted(zf.namelist()):
                info = zf.getinfo(name)
                if not info.is_dir():
                    results.append((os.path.basename(name), zf.read(name)))
=======
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
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
    else:
        # Treat as a single file
        results.append((path.name, path.read_bytes()))

<<<<<<< HEAD
    return results


class ChunkSet(NamedTuple):
    """Result of make_chunks – carries the padded chunks and original length."""
    chunks: list[np.ndarray]      # list of fixed-size uint8 arrays
    original_length: int           # byte-length before padding
=======
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
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794


def make_chunks(data: bytes, size: int) -> ChunkSet:
    """
    Split *data* into fixed-size uint8 numpy arrays of length *size*.

<<<<<<< HEAD
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
=======
    The last chunk is zero-padded to exactly *size* bytes. Empty data gives
    no chunks. The original length is returned so callers can unpad after
    decode: ``b"".join(c.tobytes() for c in chunks)[:original_len] == data``.
    """
    if size <= 0:
        raise ValueError(f"chunk size must be positive, got {size}")
    original_length = len(data)
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
    remainder = len(data) % size
    if remainder != 0:
        data = data + b"\x00" * (size - remainder)

<<<<<<< HEAD
    chunks = []
    for offset in range(0, len(data), size):
        arr = np.frombuffer(data[offset: offset + size], dtype=np.uint8).copy()
        chunks.append(arr)

=======
    chunks = [
        np.frombuffer(data[offset: offset + size], dtype=np.uint8).copy()
        for offset in range(0, len(data), size)
    ]
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
    return ChunkSet(chunks=chunks, original_length=original_length)


def synthetic_files(
<<<<<<< HEAD
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
=======
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
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
