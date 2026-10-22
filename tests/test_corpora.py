"""Tests for corpus loading and chunking utilities."""
import zipfile

import numpy as np
import pytest

from utils.corpora import (find_silesia, load_silesia, make_chunks,
                           synthetic_files)


@pytest.mark.parametrize("n_bytes", [0, 1, 255, 256, 257, 1000])
def test_make_chunks_pads_and_unpacks(n_bytes):
    data = bytes(np.random.default_rng(n_bytes).integers(0, 256, n_bytes, dtype=np.uint8))
    chunks, original_len = make_chunks(data, 256)
    assert original_len == n_bytes
    assert len(chunks) == -(-n_bytes // 256)
    assert all(c.dtype == np.uint8 and c.size == 256 for c in chunks)
    joined = b"".join(c.tobytes() for c in chunks)
    assert joined[:original_len] == data
    assert set(joined[original_len:]) <= {0}


def test_make_chunks_rejects_bad_size():
    with pytest.raises(ValueError):
        make_chunks(b"abc", 0)


def test_synthetic_files_sizes():
    files = synthetic_files(sizes_mb=(1, 2))
    assert [len(d) for _, d in files] == [1024 * 1024, 2 * 1024 * 1024]
    assert synthetic_files(sizes_mb=(1,))[0][1] == files[0][1]  # deterministic


def test_load_silesia_dir_and_zip(tmp_path):
    d = tmp_path / "silesia"
    d.mkdir()
    (d / "dickens").write_bytes(b"hello")
    (d / "xml").write_bytes(b"<a/>")
    (d / ".DS_Store").write_bytes(b"junk")
    assert find_silesia(tmp_path) == d
    assert load_silesia(d) == [("dickens", b"hello"), ("xml", b"<a/>")]

    z = tmp_path / "other" / "silesia.zip"
    z.parent.mkdir()
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("silesia/xml", b"<a/>")
        zf.writestr("dickens", b"hello")
    assert find_silesia(z.parent) == z
    assert load_silesia(z) == [("dickens", b"hello"), ("xml", b"<a/>")]


def test_load_silesia_missing(tmp_path):
    assert find_silesia(tmp_path) is None
    with pytest.raises(FileNotFoundError):
        load_silesia(tmp_path / "nope")
