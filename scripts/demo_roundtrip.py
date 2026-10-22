"""Live demo: split one file with RS(k, m), delete some pieces, rebuild, compare SHA-256.

Usage:
    python scripts/demo_roundtrip.py --file data/silesia/dickens --k 6 --m 3 --delete 3
    python scripts/demo_roundtrip.py --file data/silesia/dickens --k 6 --m 3 --delete 4

Not part of the 01-07 pipeline; only for the viva demo.
"""
import argparse
import hashlib
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from rs.codec import encode, decode  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", required=True)
    ap.add_argument("--k", type=int, default=6)
    ap.add_argument("--m", type=int, default=3)
    ap.add_argument("--delete", type=int, default=3, help="how many of the k+m pieces to lose")
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    k, m = args.k, args.m

    data = Path(args.file).read_bytes()
    original_hash = hashlib.sha256(data).hexdigest()
    print(f"file      : {args.file} ({len(data):,} bytes)")
    print(f"SHA-256   : {original_hash[:16]}...")

    # One stripe: k equal data pieces (last one zero-padded)
    piece = -(-len(data) // k)
    padded = data + b"\x00" * (piece * k - len(data))
    chunks = [np.frombuffer(padded[i * piece:(i + 1) * piece], dtype=np.uint8).copy() for i in range(k)]

    t0 = time.perf_counter()
    pieces = encode(k, m, chunks)
    print(f"encode    : RS({k},{m}) -> {k + m} pieces of {piece:,} bytes ({time.perf_counter() - t0:.2f}s)")

    rng = np.random.default_rng(args.seed)
    lost = sorted(rng.choice(k + m, size=min(args.delete, k + m), replace=False).tolist())
    survivors = [(i, pieces[i]) for i in range(k + m) if i not in lost]
    print(f"deleted   : pieces {lost} -> {len(survivors)} left (need {k})")

    if len(survivors) < k:
        print(f"RESULT    : FAILED - only {len(survivors)} pieces left, RS({k},{m}) needs any {k}.")
        return 1

    t0 = time.perf_counter()
    rebuilt = decode(k, m, survivors)
    restored = b"".join(c.tobytes() for c in rebuilt)[:len(data)]
    restored_hash = hashlib.sha256(restored).hexdigest()
    print(f"decode    : done ({time.perf_counter() - t0:.2f}s)")
    print(f"SHA-256   : {restored_hash[:16]}...")
    ok = restored_hash == original_hash
    print(f"RESULT    : {'OK - file rebuilt byte for byte' if ok else 'MISMATCH'}")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
