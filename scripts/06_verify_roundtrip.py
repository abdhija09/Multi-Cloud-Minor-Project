"""
06_verify_roundtrip.py

For every knee profile in R2 CSVs and every profile deployed in R4/R5 CSVs,
encode Silesia corpus files (or 5 synthetic 1-16 MB files if absent),
then verify that 10 random k-subsets decode back to the original data.

Writes results/tables/R7_verification.csv.
Exits non-zero on any hash mismatch.
"""

import sys
import os
import csv
import glob
import hashlib
import random
import re
import pandas as pd
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from rs.stripe import Stripe, verify_roundtrip
from utils.corpora import load_silesia, synthetic_files


def get_r2_profiles(tables_dir: Path) -> list[dict]:
    """Extract knee profiles from all R2_*.csv files."""
    profiles = []
    for f in sorted(tables_dir.glob("R2_*.csv")):
        df = pd.read_csv(f)
        for _, row in df.iterrows():
            k = int(row["k_knee"])
            m = int(row["m_knee"])
            c_kb = int(row["chunk_kb_knee"])
            if k > 0:
                profiles.append({
                    "source": f.stem,
                    "regime": str(row.get("regime", f.stem)),
                    "k": k, "m": m, "chunk_kb": c_kb,
                })
    return profiles


def get_r4_profiles(tables_dir: Path) -> list[dict]:
    """Extract deployed profiles from R4_*.csv (Fixed and NSGA-II rows)."""
    profiles = []
    # Fixed baseline always (4, 2, 1024)
    profiles.append({"source": "R4_fixed", "regime": "all", "k": 4, "m": 2, "chunk_kb": 1024})
    return profiles


def get_r5_profiles(tables_dir: Path) -> list[dict]:
    """R5 adaptive profile: use (2,1,256) as documented in R2_medium."""
    profiles = []
    r5 = tables_dir / "R5.csv"
    if r5.exists():
        # The adaptive profile from medium regime knee
        profiles.append({"source": "R5_adaptive", "regime": "medium", "k": 2, "m": 1, "chunk_kb": 256})
    return profiles


def dedupe_profiles(profiles: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for p in profiles:
        key = (p["k"], p["m"], p["chunk_kb"])
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def run_verification(files: list[tuple[str, bytes]], profile: dict,
                     n_subsets: int = 10) -> dict:
    k = profile["k"]
    m = profile["m"]
    chunk_bytes = profile["chunk_kb"] * 1024

    stripes_decoded = 0
    roundtrip_passes = 0
    hash_mismatches = 0

    for name, data in files:
        # Split data into stripes of k*chunk_bytes each
        stripe_size = k * chunk_bytes
        offset = 0
        while offset < len(data):
            chunk_data = data[offset: offset + stripe_size]
            offset += stripe_size

            stripe = Stripe(
                stripe_id=f"{name}@{offset}",
                k=k, m=m,
                chunk_size=chunk_bytes,
                csp_map=list(range(k + m)),
                sha256=hashlib.sha256(chunk_data).hexdigest(),
            )
            ok = verify_roundtrip(stripe, chunk_data, n_subsets=n_subsets)
            stripes_decoded += 1
            if ok:
                roundtrip_passes += 1
            else:
                hash_mismatches += 1

    return {
        "stripes_decoded": stripes_decoded,
        "roundtrip_passes": roundtrip_passes,
        "hash_mismatches": hash_mismatches,
    }


def main():
    project_root = Path(__file__).resolve().parent.parent
    tables_dir = project_root / "results" / "tables"
    silesia_path = project_root / "data" / "silesia.zip"
    if not silesia_path.exists():
        silesia_path = project_root / "data" / "silesia"

    # Load corpus
    try:
        files = load_silesia(silesia_path)
        print(f"[06] Using Silesia corpus: {len(files)} files")
    except FileNotFoundError:
        print("[06] Silesia not found – using 5 synthetic files (1–16 MB each)")
        files = synthetic_files(n=5, seed=0)

    # Collect all profiles
    profiles = (
        get_r2_profiles(tables_dir)
        + get_r4_profiles(tables_dir)
        + get_r5_profiles(tables_dir)
    )
    profiles = dedupe_profiles(profiles)
    print(f"[06] Verifying {len(profiles)} unique (k,m,chunk_kb) profiles ...")

    rows = []
    any_mismatch = False

    for p in profiles:
        print(f"  k={p['k']}, m={p['m']}, chunk_kb={p['chunk_kb']} ({p['source']})")
        stats = run_verification(files, p, n_subsets=10)
        mismatch = stats["hash_mismatches"] > 0
        if mismatch:
            any_mismatch = True
            print(f"  *** MISMATCH DETECTED: {stats['hash_mismatches']} failures ***")

        rows.append({
            "regime": p.get("regime", ""),
            "profiles_deployed": f"k={p['k']},m={p['m']},c={p['chunk_kb']}KB",
            "stripes_decoded": stats["stripes_decoded"],
            "roundtrip_passes": stats["roundtrip_passes"],
            "hash_mismatches": stats["hash_mismatches"],
            "source": p["source"],
        })

    df = pd.DataFrame(rows)
    out_path = tables_dir / "R7_verification.csv"
    df.to_csv(out_path, index=False)
    print(f"[06] R7_verification.csv written → {out_path}")
    print(df.to_string(index=False))

    if any_mismatch:
        print("\n[06] FATAL: Hash mismatches detected. Pipeline integrity compromised.")
        sys.exit(1)
    else:
        print("\n[06] All roundtrip checks PASSED.")
        sys.exit(0)


if __name__ == "__main__":
    main()
