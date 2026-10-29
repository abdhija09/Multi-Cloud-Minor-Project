"""
06_verify_roundtrip.py

<<<<<<< HEAD
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
=======
For every knee profile in R2_*.csv and every profile deployed in R4 / R5:
encode every Silesia file (or 5 synthetic random files of 1, 2, 4, 8, 16 MB
if Silesia is absent) and verify the roundtrip with 10 random k-subsets.

Each file is cut into stripes of k chunks of c bytes (the last stripe is
zero-padded). Every stripe is encoded to k+m chunks and decoded from 10
random k-subsets; the sha256 of every decode is compared with the stripe's
original bytes (rs.stripe.verify_roundtrip).

Profile sources (nothing hardcoded):
  R2  : results/tables/R2_<regime>.csv  -> (k_knee, m_knee, chunk_kb_knee)
  R4  : results/tables/R4_<regime>.csv  -> column 'profile (k,m,c) x repeats'
  R5  : run folders experiments/runs/E5/*/meta.json (static + final
        profiles); intermediate adaptive profiles are replayed from the logged
        seeds and must reproduce the logged triggers / final / overheads.

Writes results/tables/R7_verification.csv
  [regime, profiles_deployed, stripes_decoded, roundtrip_passes,
   hash_mismatches, source, corpus, bytes_verified, coverage]
and one run folder per row under experiments/runs/E6/.
Exit code 1 on any mismatch.

Usage: python scripts/06_verify_roundtrip.py [--max-mb-per-file N]
"""

import argparse
import importlib.util
import re
import sys
import time
import zipfile
import zlib
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rs.stripe import Stripe, verify_roundtrip  # noqa: E402
from utils.corpora import find_silesia, load_silesia, synthetic_files, SYNTHETIC_SIZES_MB  # noqa: E402

N_SUBSETS = 10
R4_PROFILE_COL = "profile (k,m,c) x repeats"
# "(3,3,256KB)" or "(3, 3, 262144)"; group 4 = optional "KB" suffix.
PROFILE_RE = re.compile(r"\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(KB)?\s*\)")


def fmt_profile(p) -> str:
    k, m, c_kb = p
    return f"({k},{m},{c_kb}KB)"


def parse_profiles(text: str) -> list[tuple[int, int, int]]:
    """All (k, m, c_kb) tuples in *text*. A bare c >= 64 KiB is read as bytes."""
    out = []
    for k, m, c, kb in PROFILE_RE.findall(str(text)):
        c = int(c)
        if not kb and c >= 64 * 1024:
            c //= 1024
        out.append((int(k), int(m), c))
    return out


# ── Profile sources ─────────────────────────────────────────────────────────

def r2_groups(tables_dir: Path) -> list[dict]:
    groups = []
    for f in sorted(tables_dir.glob("R2_*.csv")):
        df = pd.read_csv(f)
        regime = f.stem.split("_", 1)[1]
        profs = [(int(r.k_knee), int(r.m_knee), int(r.chunk_kb_knee))
                 for r in df.itertuples() if int(r.k_knee) > 0]
        groups.append({"regime": regime, "source": "R2 knee", "profiles": profs})
    return groups


def r4_groups(tables_dir: Path) -> list[dict]:
    groups = []
    for f in sorted(tables_dir.glob("R4_*.csv")):
        df = pd.read_csv(f)
        if R4_PROFILE_COL not in df.columns:
            raise SystemExit(f"[06] {f.name} has no '{R4_PROFILE_COL}' column; re-run script 04.")
        regime = f.stem.split("_", 1)[1]
        profs = []
        for text in df[R4_PROFILE_COL]:
            profs += parse_profiles(text)
        groups.append({"regime": regime, "source": "R4 strategies",
                       "profiles": sorted(set(profs))})
    return groups


def _as_profile(v):
    """[k, m, c_bytes] / (k, m, c_bytes) -> (k, m, c_kb)."""
    k, m, c = (int(x) for x in v)
    return (k, m, c // 1024 if c >= 64 * 1024 else c)


def r5_profiles_from_runs() -> tuple[list[tuple[int, int, int]], str, str]:
    """
    Every profile deployed in E5, read from experiments/runs/E5/*/meta.json.

    meta.json logs static_profile, final_adaptive_profile and trigger_epochs
    per repeat, but not the intermediate adaptive profiles. Those are
    recovered by replaying the repeat's controller loop from the logged seed
    and nominal_failure_probs (same code path as script 05), and the replay is
    only trusted if it reproduces the logged trigger epochs, the logged final
    profile and the per-epoch adaptive_overhead in metrics.csv.
    Raises SystemExit if a replay disagrees with the log.
    """
    import json
    from utils.logging import runs_dir
    d = runs_dir("E5")
    metas = sorted(d.glob("*/meta.json")) if d.exists() else []
    if not metas:
        return [], "", ""

    spec = importlib.util.spec_from_file_location(
        "run_adaptation_05", PROJECT_ROOT / "scripts" / "05_run_adaptation.py")
    s05 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(s05)
    from search.nsga2 import NSGA2
    from simulator.fleet import Fleet
    from adaptation.controller import AdaptationController
    with open(PROJECT_ROOT / "config" / "default.yaml") as f:
        cfg = yaml.safe_load(f)
    chunk_sizes = [int(kb) * 1024 for kb in cfg["rs"]["chunk_sizes_kb"]]
    factory = s05.make_problem_factory(cfg, chunk_sizes, cfg["rs"]["max_k"], cfg["rs"]["max_m"])
    a = cfg["search"]
    nsga2 = NSGA2(pop_size=a["pop_size"], generations=a["generations"],
                  mutation_rate=a["mutation_rate"], crossover_rate=a["crossover_rate"])

    if len(metas) != int(cfg["stats"]["repeats"]):
        raise SystemExit(f"[06] FATAL: experiments/runs/E5 has {len(metas)} repeats, config expects "
                         f"{cfg['stats']['repeats']} (script 05 still running or interrupted?). Re-run 05.")
    deployed, regimes_seen = set(), set()
    for mp in metas:
        meta = json.loads(mp.read_text())
        regimes_seen.add(meta.get("regime", "medium"))
        metrics = pd.read_csv(mp.parent / "metrics.csv")
        seed, n_stripes = int(meta["seed"]), int(meta["n_stripes"])
        base_fail = np.asarray(meta["nominal_failure_probs"], dtype=float)
        static = tuple(int(x) for x in meta["static_profile"])
        deployed.add(_as_profile(static))
        deployed.add(_as_profile(meta["final_adaptive_profile"]))
        if any(meta.get(k) != v for k, v in (("drift_epoch", 10), ("drift_factor", 5.0))):
            print(f"[06]   note: {mp.parent.name} uses drift settings "
                  f"{meta.get('drift_epoch')}/{meta.get('drift_factor')}")

        ctrl = AdaptationController(
            optimizer=nsga2, problem_factory=factory, nominal_failure_probs=base_fail,
            epsilon=cfg["adaptation"]["epsilon"], beta=cfg["adaptation"]["beta"],
            seed=seed, alpha=float(cfg["stats"]["alpha"]))
        prof, triggers, overheads = static, [], []
        ctrl.set_fleet_state(prof, n_stripes)
        for epoch in range(int(meta["n_epochs"])):
            fail = base_fail.copy()
            if epoch >= int(meta["drift_epoch"]):
                fail[:2] = np.minimum(fail[:2] * float(meta["drift_factor"]), 0.9999)
            rep = Fleet(s05.build_csps(1.0 - fail),
                        Fleet.assign_from_profile(*prof, n_stripes), seed).simulate_epoch(seed + epoch)
            overheads.append(rep.storage_overhead)
            res = ctrl.step(rep.observed_failure_rates(),
                            lost_counts=rep.lost_per_csp, placed_counts=rep.placed_per_csp)
            if res is not None:
                triggers.append(epoch)
                prof = tuple(int(x) for x in res["new_profile"])
                deployed.add(_as_profile(prof))
                ctrl.set_fleet_state(prof, n_stripes)
        ok = (triggers == list(meta["trigger_epochs"])
              and list(prof) == list(meta["final_adaptive_profile"])
              and ("adaptive_overhead" not in metrics
                   or np.allclose(overheads, metrics["adaptive_overhead"].to_numpy())))
        print(f"[06]   E5 {mp.parent.name}: static={_as_profile(static)} triggers={triggers} "
              f"final={_as_profile(prof)} replay_matches_log={ok}")
        if not ok:
            raise SystemExit(f"[06] FATAL: replay of {mp.parent} does not match its log "
                             f"(logged triggers {meta['trigger_epochs']}, final "
                             f"{meta['final_adaptive_profile']}). Re-run script 05.")
    return sorted(deployed), ",".join(sorted(regimes_seen)), (f"experiments/runs/E5 ({len(metas)} repeats; intermediate "
                              "profiles replayed from logged seeds and checked against the log)")


def r5_groups(tables_dir: Path) -> list[dict]:
    if not (tables_dir / "R5.csv").exists():
        print("[06] R5.csv absent; no R5 profiles to verify.")
        return []
    profs, regime, origin = r5_profiles_from_runs()
    if not profs:
        raise SystemExit("[06] FATAL: R5.csv exists but experiments/runs/E5 has no run folders; "
                         "re-run scripts/05_run_adaptation.py.")
    print(f"[06] R5 profiles ({origin}): {[fmt_profile(p) for p in profs]}")
    return [{"regime": regime, "source": "R5 static+adaptive", "profiles": profs}]


# ── Verification ────────────────────────────────────────────────────────────

def verify_profile(files, profile, max_bytes_per_file=None) -> dict:
    """Encode every byte of every file (or the first max_bytes) as stripes and check each."""
    k, m, c_kb = profile
    chunk = c_kb * 1024
    stripe_bytes = k * chunk
    n = passes = mism = nbytes = 0
    for name, data in files:
        if max_bytes_per_file is not None:
            data = data[:max_bytes_per_file]
        nbytes += len(data)
        for i, off in enumerate(range(0, len(data), stripe_bytes)):
            piece = data[off: off + stripe_bytes]
            stripe = Stripe(stripe_id=f"{name}#{i}", k=k, m=m, chunk_size=chunk,
                            csp_map=list(range(k + m)), sha256="")
            # Distinct, reproducible subsets per (profile, file, stripe).
            seed = zlib.crc32(f"{k},{m},{c_kb}|{name}|{i}".encode())
            ok = verify_roundtrip(stripe, piece, n_subsets=N_SUBSETS, seed=seed)
            n += 1
            passes += ok
            mism += (not ok)
    return {"stripes_decoded": n, "roundtrip_passes": passes,
            "hash_mismatches": mism, "bytes": nbytes}


def load_corpus():
    src = find_silesia(PROJECT_ROOT / "data")
    if src is not None:
        try:
            files = load_silesia(src)
            return files, f"Silesia ({src.relative_to(PROJECT_ROOT)})"
        except (zipfile.BadZipFile, OSError) as e:
            print(f"[06] WARNING: Silesia at {src} unreadable ({e!r}); "
                  "maybe still downloading. Falling back to synthetic files.")
    else:
        print("[06] Silesia not found in data/silesia or data/silesia.zip.")
    sizes = "/".join(str(s) for s in SYNTHETIC_SIZES_MB)
    return synthetic_files(seed=0), f"synthetic random {sizes} MB (Silesia absent)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-mb-per-file", type=float, default=None,
                    help="verify only the first N MB of each file (default: every byte)")
    args = ap.parse_args()
    max_bytes = int(args.max_mb_per_file * 1024 * 1024) if args.max_mb_per_file else None

    t_start = time.perf_counter()
    tables_dir = PROJECT_ROOT / "results" / "tables"
    with open(PROJECT_ROOT / "config" / "default.yaml") as f:
        base_seed = yaml.safe_load(f)["stats"]["base_seed"]

    files, corpus = load_corpus()
    total = sum(len(d) for _, d in files)
    print(f"[06] Corpus: {corpus}: {len(files)} files, {total} bytes")
    coverage = ("full (every byte of every file)" if max_bytes is None
                else f"first {args.max_mb_per_file:g} MB of each file")
    print(f"[06] Coverage: {coverage}")

    groups = r2_groups(tables_dir) + r4_groups(tables_dir) + r5_groups(tables_dir)

    # The codec check for a profile does not depend on regime: verify each
    # distinct profile once and attribute its counts to every group using it.
    cache: dict[tuple, dict] = {}
    for g in groups:
        for p in g["profiles"]:
            if p not in cache:
                t0 = time.perf_counter()
                cache[p] = verify_profile(files, p, max_bytes)
                st = cache[p]
                print(f"[06]   {fmt_profile(p)}: {st['stripes_decoded']} stripes, "
                      f"{st['hash_mismatches']} mismatches ({time.perf_counter() - t0:.1f}s)")

    rows = []
    for g in groups:
        sts = [cache[p] for p in g["profiles"]]
        rows.append({
            "regime": g["regime"],
            "profiles_deployed": ", ".join(fmt_profile(p) for p in g["profiles"]),
            "stripes_decoded": sum(s["stripes_decoded"] for s in sts),
            "roundtrip_passes": sum(s["roundtrip_passes"] for s in sts),
            "hash_mismatches": sum(s["hash_mismatches"] for s in sts),
            "source": g["source"],
            "corpus": corpus,
            "bytes_verified": sum(s["bytes"] for s in sts),
            "coverage": coverage,
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
        })

    df = pd.DataFrame(rows)
    out_path = tables_dir / "R7_verification.csv"
    df.to_csv(out_path, index=False)
<<<<<<< HEAD
    print(f"[06] R7_verification.csv written → {out_path}")
    print(df.to_string(index=False))

    if any_mismatch:
        print("\n[06] FATAL: Hash mismatches detected. Pipeline integrity compromised.")
        sys.exit(1)
    else:
        print("\n[06] All roundtrip checks PASSED.")
        sys.exit(0)
=======
    elapsed = time.perf_counter() - t_start
    with pd.option_context("display.width", 250, "display.max_colwidth", 60):
        print(df.to_string(index=False))
    print(f"[06] {len(cache)} distinct profiles, {N_SUBSETS} random k-subsets per stripe; "
          f"wrote {out_path} in {elapsed:.1f}s")

    try:
        from utils.logging import log_run, run_dir_for, clear_runs
        clear_runs("E6")
        for i, r in enumerate(rows):
            log_run({"experiment": "E6", "seed": base_seed, "subset_seed": "crc32(k,m,c|file|stripe)",
                     "n_subsets": N_SUBSETS, "regime": r["regime"], "source": r["source"],
                     "corpus": corpus, "coverage": coverage},
                    r, run_dir_for("E6", f"{i:02d}_{r['regime']}_{r['source'].split()[0]}"))
        print("[06] run folders written to experiments/runs/E6/")
    except Exception as e:
        print(f"[06] WARNING: log_run failed ({e!r}); R7 CSV is still written.")

    if df["hash_mismatches"].sum() > 0 or (df["roundtrip_passes"] != df["stripes_decoded"]).any():
        print("\n[06] FATAL: hash mismatches detected. Codec integrity compromised.")
        sys.exit(1)
    print("\n[06] All roundtrip checks PASSED.")
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794


if __name__ == "__main__":
    main()
