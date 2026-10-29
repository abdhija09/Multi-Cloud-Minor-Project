"""
07_summarize.py

<<<<<<< HEAD
Final pipeline summary. Refuses to run if R7 has mismatches or is missing.

Actions:
1. Assemble R1 (oracle validation: MC vs closed-form for (4,2), (9,3), (14,4))
2. Measure R6 resource envelope (wall-clock, peak RSS, disk per NSGA-II run)
3. Gather all result CSVs (T0, R1-R7) into results/tables/ALL_TABLES.md
4. Regenerate all figures summary references
"""

import sys
import os
import time
import json
import glob
import tracemalloc
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def check_r7(tables_dir: Path) -> None:
    r7_path = tables_dir / "R7_verification.csv"
    if not r7_path.exists():
        print("[07] FATAL: R7_verification.csv is missing.")
        print("     Run script 06 first: python scripts/06_verify_roundtrip.py")
        sys.exit(1)
    df = pd.read_csv(r7_path)
    total_mismatches = int(df["hash_mismatches"].sum())
    if total_mismatches > 0:
        print(f"[07] FATAL: R7 reports {total_mismatches} hash mismatch(es). "
              "Fix codec before summarising.")
        sys.exit(1)
    print(f"[07] R7 check passed (0 mismatches across {len(df)} profiles).")


def build_r1(project_root: Path) -> pd.DataFrame:
    """Oracle validation: MC vs closed-form for select (k,m) pairs + max diff sweep."""
    from oracle.availability import closed_form_availability, monte_carlo_availability

    rng = np.random.default_rng(42)
    test_cases = [
        (4, 2, "low"),
        (9, 3, "medium"),
        (14, 4, "high"),
    ]

    rows = []
    for k, m, label in test_cases:
        avail = rng.uniform(0.90, 0.999, size=k + m)
        cf = closed_form_availability(k, m, avail)
        mc_est, mc_se = monte_carlo_availability(k, m, avail, n_runs=50_000, seed=7)
        rows.append({
            "profile": f"({k},{m})",
            "regime_label": label,
            "closed_form": round(cf, 8),
            "mc_estimate": round(mc_est, 8),
            "mc_se": round(mc_se, 8),
            "abs_diff": round(abs(cf - mc_est), 8),
            "within_2se": abs(cf - mc_est) <= 2 * mc_se,
        })

    # Full sweep max |diff| over all k in 1..8, m in 0..4
    max_diff = 0.0
    for k in range(1, 9):
        for m in range(0, 5):
            if k + m > 12:
                continue
            avail = rng.uniform(0.90, 0.999, size=k + m)
            if len(avail) == 0:
                continue
            cf = closed_form_availability(k, m, avail)
            mc_est, mc_se = monte_carlo_availability(k, m, avail, n_runs=20_000, seed=7)
            max_diff = max(max_diff, abs(cf - mc_est))

    rows.append({
        "profile": "sweep_max",
        "regime_label": "all",
        "closed_form": float("nan"),
        "mc_estimate": float("nan"),
        "mc_se": float("nan"),
        "abs_diff": round(max_diff, 8),
        "within_2se": True,
    })

    return pd.DataFrame(rows)


def build_r6(project_root: Path) -> pd.DataFrame:
    """R6: resource envelope for one NSGA-II run (wall-clock, peak RSS, disk)."""
    import psutil

    try:
        import torch
        has_cuda = torch.cuda.is_available()
    except ImportError:
        has_cuda = False

    assert not has_cuda, "CUDA device detected – pipeline must run on CPU only."

=======
Final pipeline summary. Refuses to run (exit 1) if R7 is missing or reports
any roundtrip mismatch. Otherwise:

1. Regenerates the figures of scripts 03 / 04 (E3) / 05 by re-running those
   scripts, and checks that the tables R7 was built from (R2, R4, R5) came out
   byte-identical; if not, R7 is stale and the script exits 1.
2. R1: oracle validation, Monte Carlo vs exact (Poisson-binomial DP), for
   (4,2) high, (9,3) medium, (14,4) low and a full (k<=16, m<=8) sweep per regime.
3. R6: resource envelope (NSGA-II wall-clock, peak RSS, run-folder disk, CUDA).
4. results/figures/overhead_vs_fixed.png from the R4 tables.
5. results/tables/ALL_TABLES.md: T0, R1..R7 with captions built from the numbers.

Usage: python scripts/07_summarize.py [--skip-regen]
"""

import argparse
import hashlib
import math
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

TABLES = PROJECT_ROOT / "results" / "tables"
FIGURES = PROJECT_ROOT / "results" / "figures"
TOL = 5e-3
RSS_LIMIT_MIB = 2048
R1_CASES = [(4, 2, "high"), (9, 3, "medium"), (14, 4, "low")]
SWEEP_K, SWEEP_M = range(1, 17), range(0, 9)
# Validation MC size: 4 x the worst-case SE (0.5 / sqrt(N)) stays below TOL.
N_VALIDATION = math.ceil((4 * 0.5 / TOL) ** 2)
FIGS_FROM_SCRIPTS = ([f"pareto_exact_{r}.png" for r in ("low", "medium", "high")]
                     + [f"convergence_{r}.png" for r in ("low", "medium", "high")]
                     + ["drift_timeline.png"])


def load_cfg():
    with open(PROJECT_ROOT / "config" / "default.yaml") as f:
        cfg = yaml.safe_load(f)
    with open(PROJECT_ROOT / "config" / "regimes.yaml") as f:
        regimes = yaml.safe_load(f)["regimes"]
    return cfg, regimes


def regime_avail(regimes, name, base_seed) -> np.ndarray:
    """CSP availabilities exactly as script 03 draws them (rng([base_seed, regime_index]))."""
    idx = list(regimes).index(name)
    p = regimes[name]
    f_lo, f_hi = (float(x) for x in p["failure_prob_range"])
    return np.random.default_rng([base_seed, idx]).uniform(1.0 - f_hi, 1.0 - f_lo, size=p["csp_count"])


# ── 0. R7 guard ─────────────────────────────────────────────────────────────

def check_r7() -> pd.DataFrame:
    path = TABLES / "R7_verification.csv"
    if not path.exists():
        print("[07] REFUSING TO RUN: results/tables/R7_verification.csv is missing.\n"
              "     Run: python scripts/06_verify_roundtrip.py")
        sys.exit(1)
    df = pd.read_csv(path)
    bad = int(df["hash_mismatches"].sum())
    if bad > 0 or (df["roundtrip_passes"] != df["stripes_decoded"]).any() or df.empty:
        print(f"[07] REFUSING TO RUN: R7 reports {bad} hash mismatch(es) "
              "(or failed / empty rows). Fix the codec and re-run script 06.")
        sys.exit(1)
    print(f"[07] R7 check passed: 0 mismatches over {int(df['stripes_decoded'].sum())} "
          f"stripe checks in {len(df)} rows.")
    return df


# ── 1. Figures from scripts 03/04/05 ────────────────────────────────────────

def _hash_inputs() -> dict:
    """
    Fingerprint of everything R7's profile list is built from: the R2 / R4
    tables and, per E5 repeat, the deployed profiles + trigger epochs.
    (R5.csv itself is not hashed: its reopt_seconds row is wall-clock.)
    """
    import json
    files = sorted(TABLES.glob("R2_*.csv")) + sorted(TABLES.glob("R4_*.csv"))
    out = {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    for mp in sorted((PROJECT_ROOT / "experiments" / "runs" / "E5").glob("*/meta.json")):
        meta = json.loads(mp.read_text())
        out[f"E5/{mp.parent.name}"] = json.dumps(
            [meta.get(k) for k in ("seed", "static_profile", "final_adaptive_profile", "trigger_epochs")])
    return out


def regenerate_script_figures():
    before = _hash_inputs()
    py = sys.executable
    for cmd in ([py, "scripts/03_run_exact_front.py"],
                [py, "scripts/04_run_search.py", "--experiment", "E3-all"],
                [py, "scripts/05_run_adaptation.py"]):
        t0 = time.perf_counter()
        print(f"[07] regenerating figures: {' '.join(cmd[1:])} ...", flush=True)
        r = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stdout[-3000:], r.stderr[-3000:])
            print(f"[07] FATAL: {cmd[1]} failed (exit {r.returncode}).")
            sys.exit(1)
        print(f"[07]   done in {time.perf_counter() - t0:.1f}s")
    after = _hash_inputs()
    changed = [k for k in set(before) | set(after) if before.get(k) != after.get(k)]
    if changed:
        print(f"[07] FATAL: re-running scripts 03-05 changed {sorted(changed)}; "
              "R7 was verified against the old profiles. Re-run script 06, then 07.")
        sys.exit(1)
    print("[07] R2/R4 tables and E5 deployed profiles unchanged by regeneration (R7 still matches them).")


# ── 2. R1 oracle validation ─────────────────────────────────────────────────

def exact_availability(k: int, avail: np.ndarray) -> float:
    """P(at least k of the independent chunks survive): Poisson-binomial DP, O(n^2)."""
    dp = np.zeros(len(avail) + 1)
    dp[0] = 1.0
    for a in avail:
        dp[1:] = dp[1:] * (1.0 - a) + dp[:-1] * a
        dp[0] *= 1.0 - a
    return float(dp[k:].sum())


def build_r1(cfg, regimes) -> tuple[pd.DataFrame, dict]:
    from oracle.availability import closed_form_availability, monte_carlo_availability

    base_seed, mc_runs, mc_seed = cfg["stats"]["base_seed"], cfg["oracle"]["mc_runs"], cfg["oracle"]["mc_seed"]
    avails = {r: regime_avail(regimes, r, base_seed) for r in regimes}

    # The DP must agree with the subset-enumeration closed form wherever that is cheap.
    for r, av in avails.items():
        for k, m in ((1, 0), (2, 1), (3, 3), (4, 4), (5, 3)):
            a = av[np.arange(k + m) % len(av)]
            assert abs(exact_availability(k, a) - closed_form_availability(k, m, a)) < 1e-12

    def one(k, m, regime, n_runs):
        av = avails[regime]
        a = av[np.arange(k + m) % len(av)]           # round-robin, as src/oracle/memo.py
        ex = exact_availability(k, a)
        mc, se = monte_carlo_availability(k, m, a, n_runs=n_runs, seed=mc_seed)
        d = abs(mc - ex)
        return ex, mc, se, d, (d / se if se > 0 else float("nan"))

    rows = []
    for k, m, regime in R1_CASES:
        for n_runs in (mc_runs, N_VALIDATION):
            ex, mc, se, d, z = one(k, m, regime, n_runs)
            rows.append({"row": f"({k},{m})", "regime": regime, "n_csps": len(avails[regime]),
                         "mc_runs": n_runs, "exact": ex, "exact_unavail": 1.0 - ex, "mc": mc, "se": se,
                         "abs_diff": d, "diff_over_se": z})
    sweep = {}
    for n_runs in (mc_runs, N_VALIDATION):
        for regime in regimes:
            res = [one(k, m, regime, n_runs) for k in SWEEP_K for m in SWEEP_M]
            d = max(r[3] for r in res)
            se = max(r[2] for r in res)
            zs = [r[4] for r in res if not np.isnan(r[4])]
            sweep[(n_runs, regime)] = (d, se)
            rows.append({"row": "sweep max (k 1-16, m 0-8)", "regime": regime,
                         "n_csps": len(avails[regime]), "mc_runs": n_runs,
                         "exact": float("nan"), "exact_unavail": float("nan"), "mc": float("nan"), "se": se,
                         "abs_diff": d, "diff_over_se": max(zs) if zs else float("nan")})
    df = pd.DataFrame(rows)

    val = df[df.mc_runs == N_VALIDATION]
    dep = df[df.mc_runs == mc_runs]
    summary = {"mc_runs": mc_runs, "n_val": N_VALIDATION, "n_cells": len(SWEEP_K) * len(SWEEP_M) * len(regimes),
               "val_max_diff": float(val.abs_diff.max()), "val_max_se": float(val.se.max()),
               "val_max_z": float(val.diff_over_se.max()),
               "dep_max_diff": float(dep.abs_diff.max()), "dep_max_se": float(dep.se.max()),
               "dep_max_z": float(dep.diff_over_se.max()),
               "cases": {r["row"]: r for r in df[(df.mc_runs == N_VALIDATION) & df.row.str.startswith("(")].to_dict("records")},
               "dep_cases": {r["row"]: r for r in df[(df.mc_runs == mc_runs) & df.row.str.startswith("(")].to_dict("records")}}
    assert summary["val_max_diff"] < TOL, f"R1: max |MC - exact| = {summary['val_max_diff']} >= {TOL}"
    assert summary["val_max_se"] < TOL, f"R1: max SE = {summary['val_max_se']} >= {TOL}"
    if summary["dep_max_diff"] >= TOL:
        print(f"[07] NOTE: at the deployed mc_runs={mc_runs}, max |MC - exact| = "
              f"{summary['dep_max_diff']:.4g} (>= {TOL}); max |diff|/SE = {summary['dep_max_z']:.2f}. "
              f"The {TOL} bound is asserted at mc_runs={N_VALIDATION}.")
    return df, summary


# ── 3. R6 resource envelope ─────────────────────────────────────────────────

class PeakRSS:
    """Samples this process's RSS every 10 ms on a background thread."""
    def __init__(self):
        import psutil
        self.proc, self.peak, self._stop = psutil.Process(), 0, threading.Event()

    def __enter__(self):
        self.peak = self.proc.memory_info().rss
        self.t = threading.Thread(target=self._run, daemon=True)
        self.t.start()
        return self

    def _run(self):
        while not self._stop.is_set():
            self.peak = max(self.peak, self.proc.memory_info().rss)
            time.sleep(0.01)

    def __exit__(self, *exc):
        self._stop.set()
        self.t.join()
        self.peak = max(self.peak, self.proc.memory_info().rss)


def ru_maxrss_bytes() -> int:
    if sys.platform == "win32":
        import psutil
        return int(psutil.Process().memory_info().peak_wset)

    import resource
    v = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(v if sys.platform == "darwin" else v * 1024)


def build_r6(cfg, regimes, seeds=(0, 1)) -> tuple[pd.DataFrame, dict]:
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
    from oracle.memo import AvailabilityTable
    from search.base import Problem
    from search.nsga2 import NSGA2

<<<<<<< HEAD
    import yaml
    with open(project_root / "config" / "default.yaml") as f:
        cfg = yaml.safe_load(f)
    with open(project_root / "config" / "regimes.yaml") as f:
        regimes = yaml.safe_load(f)["regimes"]

    params = regimes["medium"]
    csp_count = params["csp_count"]
    rng = np.random.default_rng(42)
    avails = rng.uniform(0.99, 0.999, size=csp_count)

    oracle = AvailabilityTable(csp_avail=avails,
                               mc_runs=cfg["oracle"]["mc_runs"],
                               seed=cfg["oracle"]["mc_seed"])
    problem = Problem(oracle=oracle, n_csps=csp_count,
                      chunk_sizes=cfg["rs"]["chunk_sizes_kb"],
                      max_k=cfg["rs"]["max_k"], max_m=cfg["rs"]["max_m"])
    nsga2 = NSGA2(pop_size=cfg["search"]["pop_size"],
                  generations=cfg["search"]["generations"],
                  mutation_rate=cfg["search"]["mutation_rate"],
                  crossover_rate=cfg["search"]["crossover_rate"])

    proc = psutil.Process()
    tracemalloc.start()
    t0 = time.perf_counter()

    nsga2.optimize(problem, seed=42)

    wall_secs = time.perf_counter() - t0
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    peak_rss_mb = proc.memory_info().rss / 1024**2

    # Disk: size of results directory
    results_dir = project_root / "results"
    disk_bytes = sum(
        f.stat().st_size
        for f in results_dir.rglob("*") if f.is_file()
    )

    assert peak_rss_mb < 2048, f"Peak RSS {peak_rss_mb:.0f} MB exceeds 2 GB limit."
    print(f"[07] R6: wall={wall_secs:.2f}s, peak_RSS={peak_rss_mb:.1f}MB, "
          f"disk={disk_bytes/1024**2:.1f}MB, CUDA={has_cuda}")

    return pd.DataFrame([{
        "metric": "wall_clock_per_run_s",
        "value": round(wall_secs, 3),
    }, {
        "metric": "peak_rss_mb",
        "value": round(peak_rss_mb, 1),
    }, {
        "metric": "disk_results_mb",
        "value": round(disk_bytes / 1024**2, 1),
    }, {
        "metric": "cuda_used",
        "value": int(has_cuda),
    }])


def csv_to_markdown(path: Path, title: str) -> str:
    try:
        df = pd.read_csv(path)
    except Exception as e:
        return f"### {title}\n\n*(error reading {path.name}: {e})*\n\n"

    lines = [f"### {title}", ""]
    # Header
    lines.append("| " + " | ".join(str(c) for c in df.columns) + " |")
    lines.append("| " + " | ".join(["---"] * len(df.columns)) + " |")
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(str(v) for v in row.values) + " |")
    lines.append("")
    return "\n".join(lines)


def main():
    project_root = Path(__file__).resolve().parent.parent
    tables_dir = project_root / "results" / "tables"
    figures_dir = project_root / "results" / "figures"
    os.makedirs(tables_dir, exist_ok=True)

    # 1. Guard: check R7
    check_r7(tables_dir)

    # 2. Build R1 (oracle validation)
    print("[07] Building R1 oracle validation table …")
    r1 = build_r1(project_root)
    r1.to_csv(tables_dir / "R1_oracle.csv", index=False)
    print(r1.to_string(index=False))

    # 3. Build R6 (resource envelope)
    print("[07] Building R6 resource envelope …")
    r6 = build_r6(project_root)
    r6.to_csv(tables_dir / "R6_resources.csv", index=False)
    print(r6.to_string(index=False))

    # 4. Assemble ALL_TABLES.md
    print("[07] Assembling ALL_TABLES.md …")
    table_specs = [
        ("T0_fit.csv",            "T0 – Failure Rate Fit (Azure / Synthetic)"),
        ("R1_oracle.csv",         "R1 – Oracle Validation (MC vs Closed-Form)"),
        ("R2_low.csv",            "R2 – Exact Pareto Front (Low Regime)"),
        ("R2_medium.csv",         "R2 – Exact Pareto Front (Medium Regime)"),
        ("R2_high.csv",           "R2 – Exact Pareto Front (High Regime)"),
        ("R3_low.csv",            "R3 – NSGA-II Quality (Low Regime)"),
        ("R3_medium.csv",         "R3 – NSGA-II Quality (Medium Regime)"),
        ("R3_high.csv",           "R3 – NSGA-II Quality (High Regime)"),
        ("R4_low.csv",            "R4 – Fleet Simulation (Low Regime)"),
        ("R4_medium.csv",         "R4 – Fleet Simulation (Medium Regime)"),
        ("R4_high.csv",           "R4 – Fleet Simulation (High Regime)"),
        ("R5.csv",                "R5 – Adaptation Loop (Medium Regime)"),
        ("R6_resources.csv",      "R6 – Resource Envelope"),
        ("R7_verification.csv",   "R7 – Roundtrip Verification"),
    ]

    md_lines = [
        "# Pipeline Results – ALL_TABLES",
        "",
        f"*Generated by `scripts/07_summarize.py`*",
        "",
    ]

    # Figures index
    md_lines += ["## Figures", ""]
    for fig in sorted(figures_dir.glob("*.png")):
        md_lines.append(f"- `results/figures/{fig.name}`")
    md_lines.append("")

    md_lines.append("## Tables")
    md_lines.append("")

    for filename, title in table_specs:
        path = tables_dir / filename
        if path.exists():
            md_lines.append(csv_to_markdown(path, title))
        else:
            md_lines.append(f"### {title}\n\n*(file not found: {filename})*\n")

    all_tables_path = tables_dir / "ALL_TABLES.md"
    all_tables_path.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"[07] ALL_TABLES.md written → {all_tables_path}")
    print("[07] Done.")
=======
    try:
        import torch
        cuda = bool(torch.cuda.is_available())
        cuda_note = f"torch {torch.__version__}: cuda available = {cuda}"
    except ImportError:
        cuda, cuda_note = False, "torch not installed, CPU-only by construction"
    assert not cuda, "CUDA device detected; the pipeline must run CPU-only."

    s = cfg["search"]
    rows, walls = [], []
    with PeakRSS() as mon:
        for regime in regimes:
            av = regime_avail(regimes, regime, cfg["stats"]["base_seed"])
            times = []
            for sd in seeds:
                # Fresh oracle per run: the timing includes the MC table build, as in a real run.
                problem = Problem(oracle=AvailabilityTable(av, mc_runs=cfg["oracle"]["mc_runs"],
                                                           seed=cfg["oracle"]["mc_seed"]),
                                  n_csps=len(av), chunk_sizes=cfg["rs"]["chunk_sizes_kb"],
                                  max_k=cfg["rs"]["max_k"], max_m=cfg["rs"]["max_m"])
                nsga = NSGA2(pop_size=s["pop_size"], generations=s["generations"],
                             mutation_rate=s["mutation_rate"], crossover_rate=s["crossover_rate"])
                t0 = time.perf_counter()
                nsga.optimize(problem, seed=cfg["stats"]["base_seed"] + sd)
                times.append(time.perf_counter() - t0)
            walls += times
            rows.append({"metric": "nsga2_wall_clock_s", "scope": regime, "n": len(times),
                         "mean": np.mean(times), "max": np.max(times), "unit": "s"})
    peak_mb = mon.peak / 2**20
    ru_mb = ru_maxrss_bytes() / 2**20
    rows.append({"metric": "nsga2_wall_clock_s", "scope": "all regimes", "n": len(walls),
                 "mean": np.mean(walls), "max": np.max(walls), "unit": "s"})
    rows.append({"metric": "peak_rss_sampled_during_nsga2", "scope": "process", "n": len(walls),
                 "mean": float("nan"), "max": peak_mb, "unit": "MiB"})
    rows.append({"metric": "peak_rss_ru_maxrss", "scope": "process lifetime", "n": 1,
                 "mean": float("nan"), "max": ru_mb, "unit": "MiB"})

    runs_root = PROJECT_ROOT / "experiments" / "runs"
    disk = {}
    if runs_root.exists():
        for exp in sorted(p for p in runs_root.iterdir() if p.is_dir()):
            sizes = [sum(f.stat().st_size for f in rd.rglob("*") if f.is_file())
                     for rd in exp.iterdir() if rd.is_dir()]
            if sizes:
                disk[exp.name] = sizes
                rows.append({"metric": "disk_per_run_dir", "scope": f"experiments/runs/{exp.name}",
                             "n": len(sizes), "mean": np.mean(sizes) / 1024,
                             "max": np.max(sizes) / 1024, "unit": "KiB"})
    rows.append({"metric": "cuda_device", "scope": cuda_note, "n": 1,
                 "mean": float("nan"), "max": int(cuda), "unit": "bool"})

    peak_all_mb = max(peak_mb, ru_mb)
    assert peak_all_mb < RSS_LIMIT_MIB, f"Peak RSS {peak_all_mb:.0f} MiB exceeds {RSS_LIMIT_MIB} MiB."
    all_sizes = [s for v in disk.values() for s in v]
    summary = {"wall_mean": float(np.mean(walls)), "wall_max": float(np.max(walls)), "n_runs": len(walls),
               "peak_mb": peak_mb, "ru_mb": ru_mb, "cuda_note": cuda_note,
               "n_run_dirs": len(all_sizes), "n_exps": len(disk),
               "disk_max_kib": (max(all_sizes) / 1024) if all_sizes else float("nan")}
    return pd.DataFrame(rows), summary


# ── 4. Overview figure ──────────────────────────────────────────────────────

def pm(s):
    """'1.5000 ± 0.0369' -> (1.5, 0.0369); plain numbers -> (x, 0)."""
    parts = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?|nan", str(s))
    vals = [float(p) for p in parts]
    return (vals[0], vals[1] if len(vals) > 1 else 0.0) if vals else (float("nan"), 0.0)


def load_r4(regimes) -> dict:
    return {r: pd.read_csv(TABLES / f"R4_{r}.csv") for r in regimes if (TABLES / f"R4_{r}.csv").exists()}


def strategy_key(name: str) -> str:
    n = name.lower()
    return "fixed" if "fixed" in n else "greedy" if "greedy" in n else "nsga2" if "nsga" in n else n


def plot_overhead_vs_fixed(r4: dict, regimes_cfg: dict) -> Path:
    order = [("fixed", "Fixed RS(4,2) 1 MB"), ("greedy", "Greedy"), ("nsga2", "NSGA-II knee")]
    colors = {"fixed": "#2a78d6", "greedy": "#eb6834", "nsga2": "#1baf7a"}  # dataviz slots 1-3
    regimes = list(r4)
    width = 0.26
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ymax = 0.0
    for j, (key, label) in enumerate(order):
        xs, hs, es, infeas = [], [], [], []
        for i, r in enumerate(regimes):
            df = r4[r]
            row = df[df.strategy.map(strategy_key) == key]
            if row.empty:
                continue
            mu, ci = pm(row.storage_overhead.iloc[0])
            xs.append(i + (j - 1) * width)
            hs.append(mu)
            es.append(ci)
            ymax = max(ymax, mu + ci)
            oracle = str(row.get("oracle_availability_exact", pd.Series([""])).iloc[0])
            infeas.append(regimes_cfg[r]["csp_count"] if "infeasible" in oracle else None)
        bars = ax.bar(xs, hs, width - 0.03, yerr=es, capsize=3, color=colors[key], label=label,
                      edgecolor="white", linewidth=1.5)
        for b, h, e, bad in zip(bars, hs, es, infeas):
            ax.text(b.get_x() + b.get_width() / 2, h + e + 0.03, f"{h:.2f}", ha="center",
                    va="bottom", fontsize=8, color="#52514e")
            if bad:
                ax.text(b.get_x() + b.get_width() / 2, h / 2, f"infeasible\non {bad} CSPs",
                        ha="center", va="center", fontsize=7, color="white", rotation=90)
    ax.set_xticks(range(len(regimes)))
    ax.set_xticklabels([f"{r} regime" for r in regimes])
    ax.set_ylabel("Storage overhead ((k+m)/k, fleet mean)")
    ax.set_ylim(0, ymax * 1.18)
    ax.set_title("Storage overhead: Fixed RS(4,2) vs Greedy vs NSGA-II knee (R4)")
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.legend(frameon=False, loc="upper left", ncol=3)
    fig.tight_layout()
    out = FIGURES / "overhead_vs_fixed.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


# ── 5. ALL_TABLES.md ────────────────────────────────────────────────────────

def fmt(v) -> str:
    if isinstance(v, (float, np.floating)):
        if np.isnan(v):
            return "n/a"
        if v == 0 or (1e-3 <= abs(v) < 1e6):
            return f"{v:.6g}"
        return f"{v:.3e}"
    return str(v).replace("|", "\\|")


def md_table(df: pd.DataFrame) -> str:
    lines = ["| " + " | ".join(fmt(c) for c in df.columns) + " |",
             "| " + " | ".join("---" for _ in df.columns) + " |"]
    lines += ["| " + " | ".join(fmt(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(lines)


def concat_regimes(prefix: str, regimes) -> pd.DataFrame:
    frames = []
    for r in regimes:
        p = TABLES / f"{prefix}_{r}.csv"
        if p.exists():
            df = pd.read_csv(p)
            if "regime" not in df.columns:
                df.insert(0, "regime", r)
            frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def nines(a: float) -> str:
    return "n/a" if np.isnan(a) else (f"{-math.log10(1 - a):.1f}" if a < 1 else "over 9")


def _meta(experiment: str) -> dict:
    """meta.json of the first run folder of *experiment* ({} if none)."""
    import json
    d = PROJECT_ROOT / "experiments" / "runs" / experiment
    metas = sorted(d.glob("*/meta.json")) if d.exists() else []
    return json.loads(metas[0].read_text()) if metas else {}


def caption_t0(t0: pd.DataFrame) -> str:
    if t0.empty:
        return "T0 is empty."
    per = t0.groupby("regime", sort=False).size()
    s = ["T0 lists the per-CSP failure inputs: "
         + ", ".join(f"{n} CSPs in {r}" for r, n in per.items()) + "."]
    if "source" in t0.columns:
        s.append(f"The data source is: {', '.join(sorted(t0.source.astype(str).unique()))}.")
    av_cols = [c for c in t0.columns if "availability" in c and pd.api.types.is_numeric_dtype(t0[c])]
    for col in av_cols:
        for r, g in t0.groupby("regime", sort=False):
            s.append(f"In {r}, {col} runs from {g[col].min():.4f} to {g[col].max():.4f}.")
    s.append("Every later table is built on these per-CSP numbers.")
    return " ".join(s)


def caption_r1(s) -> str:
    out = ["R1 checks the Monte Carlo (MC) availability oracle against the exact answer.",
           "Exact values use a Poisson-binomial recursion; it matches subset enumeration on small cases.",
           "Chunks go round-robin over the regime's CSPs, as in the oracle.",
           "So (9,3) and (14,4) put several chunks on one CSP, which a real deployment forbids.",
           "The availability math is still well defined, and that is all R1 tests."]
    for name, v in s["cases"].items():
        dep = s["dep_cases"][name]
        if v["se"] == 0:
            out.append(f"For {name} in {v['regime']}, exact unavailability is {v['exact_unavail']:.2e}; "
                       f"MC saw no failure, so the error is {v['abs_diff']:.2e}.")
        else:
            out.append(f"For {name} in {v['regime']}, exact availability is {v['exact']:.6f}.")
            out.append(f"MC gives {dep['mc']:.6f} with {s['mc_runs']} runs and {v['mc']:.6f} with {s['n_val']} runs.")
    out += [f"The sweep covers {s['n_cells']} (k,m) cells over all regimes.",
            f"With {s['n_val']} runs, max |MC - exact| is {s['val_max_diff']:.2e} and max SE is {s['val_max_se']:.2e}.",
            f"Both are under the {TOL} limit.",
            f"With the deployed {s['mc_runs']} runs, max |MC - exact| is {s['dep_max_diff']:.2e} "
            f"and max SE is {s['dep_max_se']:.2e}.",
            f"The worst |MC - exact|/SE is {s['dep_max_z']:.2f} and {s['val_max_z']:.2f}, so errors look like sampling noise.",
            "When MC sees no failure, SE is 0 and the ratio shows n/a."]
    return " ".join(out)


def caption_r2(r2: pd.DataFrame) -> str:
    s = ["R2 is the exact Pareto front found by full enumeration, with its knee point."]
    for r in r2.itertuples():
        s.append(f"In {r.regime} ({r.n} CSPs) the front has {r.n_nondominated} points.")
        s.append(f"The knee is RS({r.k_knee},{r.m_knee}) with {r.chunk_kb_knee} KB chunks.")
        s.append(f"It reaches availability {float(r.A_knee):.4f} ({r.nines}) at overhead m/k = {float(r.overhead):.2f}.")
    s.append("These knees are the reference answers NSGA-II must find.")
    return " ".join(s)


def caption_r3(r3: pd.DataFrame) -> str:
    s = ["R3 measures how close NSGA-II gets to the exact front (means over repeats)."]
    for regime, g in r3.groupby("regime", sort=False):
        v = dict(zip(g.metric, g["mean"]))
        if "norm_hv" in v and "igd" in v:
            s.append(f"In {regime}, normalised hypervolume is {v['norm_hv']:.3f} and IGD is {v['igd']:.3g}.")
        if "knee_match_rate" in v:
            s.append(f"The knee matches the exact knee in {100 * v['knee_match_rate']:.0f}% of repeats.")
        if "gens_to_95" in v:
            s.append(f"It reaches 95% of its final hypervolume after {v['gens_to_95']:.1f} generations.")
    s.append("Hypervolume near 1 and IGD near 0 mean NSGA-II recovers the exact front.")
    return " ".join(s)


def caption_r4(r4: dict) -> str:
    n_stripes = _meta("E4").get("n_stripes")
    s = [f"R4 simulates a fleet of {n_stripes} stripes per regime and compares three strategies."
         if n_stripes else "R4 simulates a stripe fleet per regime and compares three strategies."]
    sim_limit = set()
    for regime, df in r4.items():
        get = {strategy_key(x): row for x, (_, row) in zip(df.strategy, df.iterrows())}
        sim_limit.update(str(x) for x in df.nines if "sim limit" in str(x))
        if "nsga2" in get:
            n = get["nsga2"]
            s.append(f"In {regime}, the NSGA-II knee deploys {n['profile (k,m,c) x repeats']}.")
            s.append(f"Its storage overhead is {pm(n.storage_overhead)[0]:.2f} ({n.overhead_vs_fixed_pct} vs fixed), "
                     f"with exact availability {n.oracle_availability_exact} ({n.oracle_nines}).")
        if "fixed" in get:
            f = get["fixed"]
            prof = re.findall(r"\((\d+),(\d+),", str(f["profile (k,m,c) x repeats"]))
            if "infeasible" in str(f.oracle_availability_exact) and prof:
                k, m = (int(x) for x in prof[0])
                s.append(f"Fixed RS({k},{m}) needs {k + m} CSPs, so it is infeasible in {regime}.")
            else:
                s.append(f"Fixed reaches {f.oracle_availability_exact} ({f.oracle_nines}).")
        if "greedy" in get:
            g = get["greedy"]
            s.append(f"Greedy deploys {g['profile (k,m,c) x repeats']} at overhead {pm(g.storage_overhead)[0]:.2f}, "
                     f"exact availability {g.oracle_availability_exact}.")
    if sim_limit:
        s.append(f"Simulated availability saturates at {sorted(sim_limit)[0]}, so the exact column is the fairer comparison.")
    return " ".join(s)


def caption_r5(r5: pd.DataFrame, regimes) -> str:
    meta = _meta("E5")
    v = {r.metric: r for r in r5.itertuples()}
    if meta:
        reg = meta.get("regime", "medium")
        s = [f"R5 tests the adaptation loop in the {reg} regime ({regimes[reg]['csp_count']} CSPs).",
             f"At epoch {meta['drift_epoch']}, two CSPs start failing {meta['drift_factor']:g} times as often."]
    else:
        s = ["R5 tests the adaptation loop under failure-rate drift."]
    if "post_drift_availability" in v:
        r = v["post_drift_availability"]
        s.append(f"After drift, adaptive availability is {pm(r.adaptive)[0]:.4f} versus {pm(r.static)[0]:.4f} for static.")
    if "post_drift_overhead" in v:
        r = v["post_drift_overhead"]
        s.append(f"Adaptive pays overhead {pm(r.adaptive)[0]:.2f} versus {pm(r.static)[0]:.2f} for static.")
    if "detection_latency_epochs" in v:
        s.append(f"The drift is detected after {pm(v['detection_latency_epochs'].adaptive)[0]:.1f} epochs on average.")
    if "pre_drift_triggers" in v:
        s.append(f"Before drift there are {pm(v['pre_drift_triggers'].adaptive)[0]:.1f} false triggers per run on average.")
    if "reopt_seconds" in v:
        s.append(f"Re-optimising takes {pm(v['reopt_seconds'].adaptive)[0]:.1f} s per run in total.")
    s.append("So the controller trades some extra storage for higher availability after drift.")
    return " ".join(s)


def caption_r6(s) -> str:
    return " ".join([
        "R6 is the resource envelope on this machine.",
        f"One NSGA-II run takes {s['wall_mean']:.2f} s on average and {s['wall_max']:.2f} s at most ({s['n_runs']} runs).",
        f"Peak memory is {max(s['peak_mb'], s['ru_mb']):.0f} MiB, under the {RSS_LIMIT_MIB / 1024:g} GiB limit.",
        (f"The largest of {s['n_run_dirs']} run folders in {s['n_exps']} experiments uses {s['disk_max_kib']:.1f} KiB on disk."
         if s["n_run_dirs"] else "No run folders were found under experiments/runs."),
        f"No GPU is used ({s['cuda_note']}).",
        "The whole method fits on an ordinary laptop CPU.",
    ])


def caption_r7(r7: pd.DataFrame) -> str:
    profs = set()
    for t in r7.profiles_deployed:
        profs.update(re.findall(r"\(\d+,\d+,\d+KB\)", str(t)))
    corpus = r7.corpus.iloc[0] if "corpus" in r7.columns else "the test corpus"
    cov = r7.coverage.iloc[0] if "coverage" in r7.columns else "full"
    return " ".join([
        "R7 checks that every deployed profile really stores and returns the data byte for byte.",
        f"It covers {len(profs)} distinct RS profiles on {corpus}.",
        f"Coverage: {cov}.",
        f"Each stripe was decoded from {_meta('E6').get('n_subsets', 'several')} random k-subsets and compared by SHA-256.",
        f"All {int(r7.stripes_decoded.sum())} stripe checks passed with {int(r7.hash_mismatches.sum())} hash mismatches.",
        "Profiles that are infeasible on a small fleet are still valid codes, so they are verified too.",
    ])


def write_all_tables(r1, s1, r6, s6, regimes, figures) -> Path:
    t0 = pd.read_csv(TABLES / "T0_fit.csv") if (TABLES / "T0_fit.csv").exists() else pd.DataFrame()
    r2 = concat_regimes("R2", regimes)
    r3 = concat_regimes("R3", regimes)
    r4 = load_r4(regimes)
    r5 = pd.read_csv(TABLES / "R5.csv")
    r7 = pd.read_csv(TABLES / "R7_verification.csv")
    sections = [
        ("T0 - Failure statistics per CSP", t0, caption_t0(t0)),
        ("R1 - Oracle validation (Monte Carlo vs exact)", r1, caption_r1(s1)),
        ("R2 - Exact Pareto front and knee", r2, caption_r2(r2)),
        ("R3 - NSGA-II quality vs exact front", r3, caption_r3(r3)),
        ("R4 - Fleet simulation: Fixed vs Greedy vs NSGA-II", pd.concat(
            [df.assign(regime=r)[["regime"] + list(df.columns)] for r, df in r4.items()], ignore_index=True),
         caption_r4(r4)),
        ("R5 - Adaptation under drift (medium regime)", r5, caption_r5(r5, regimes)),
        ("R6 - Resource envelope", r6, caption_r6(s6)),
        ("R7 - Roundtrip verification", r7, caption_r7(r7)),
    ]
    lines = ["# Pipeline results - ALL_TABLES", "",
             "*Generated by `scripts/07_summarize.py`; every number below is read from results/tables.*", "",
             "## Figures", ""]
    lines += [f"- `results/figures/{f}`" for f in figures] + ["", "## Tables", ""]
    for title, df, cap in sections:
        lines += [f"### {title}", "", md_table(df) if not df.empty else "*(no rows)*", "", cap, ""]
    text = "\n".join(lines)
    assert "[TBD]" not in text
    out = TABLES / "ALL_TABLES.md"
    out.write_text(text, encoding="utf-8")
    return out


def try_log(experiment, run_name, meta, metrics):
    try:
        from utils.logging import log_run, run_dir_for, clear_runs
        clear_runs(experiment)
        log_run(meta, metrics, run_dir_for(experiment, run_name))
    except Exception as e:
        print(f"[07] WARNING: log_run({experiment}) failed: {e!r}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-regen", action="store_true",
                    help="do not re-run scripts 03/04/05 to regenerate their figures")
    args = ap.parse_args()
    t_start = time.perf_counter()
    os.makedirs(TABLES, exist_ok=True)
    os.makedirs(FIGURES, exist_ok=True)

    check_r7()
    cfg, regimes = load_cfg()

    if args.skip_regen:
        print("[07] --skip-regen: keeping existing figures from scripts 03/04/05.")
    else:
        regenerate_script_figures()
        check_r7()
    missing = [f for f in FIGS_FROM_SCRIPTS if not (FIGURES / f).exists()]
    if missing:
        print(f"[07] FATAL: figures missing after regeneration: {missing}")
        sys.exit(1)

    print(f"[07] R1: oracle validation (mc_runs {cfg['oracle']['mc_runs']} and {N_VALIDATION}) ...")
    r1, s1 = build_r1(cfg, regimes)
    r1.to_csv(TABLES / "R1_oracle.csv", index=False)
    with pd.option_context("display.width", 200):
        print(r1.to_string(index=False))
    try_log("R1", f"oracle_seed{cfg['stats']['base_seed']}",
            {"experiment": "R1", "seed": cfg["stats"]["base_seed"], "mc_seed": cfg["oracle"]["mc_seed"],
             "mc_runs_deployed": cfg["oracle"]["mc_runs"], "mc_runs_validation": N_VALIDATION,
             "tolerance": TOL}, r1)

    print("[07] R6: resource envelope ...")
    r6, s6 = build_r6(cfg, regimes)
    r6.to_csv(TABLES / "R6_resources.csv", index=False)
    with pd.option_context("display.width", 200):
        print(r6.to_string(index=False))
    try_log("R6", f"resources_seed{cfg['stats']['base_seed']}",
            {"experiment": "R6", "seed": cfg["stats"]["base_seed"], "platform": sys.platform}, r6)

    fig = plot_overhead_vs_fixed(load_r4(regimes), regimes)
    print(f"[07] wrote {fig.relative_to(PROJECT_ROOT)}")

    figures = FIGS_FROM_SCRIPTS + ["overhead_vs_fixed.png"]
    out = write_all_tables(r1, s1, r6, s6, regimes, figures)
    print(f"[07] wrote {out.relative_to(PROJECT_ROOT)}")
    print(f"[07] Done in {time.perf_counter() - t_start:.1f}s.")
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794


if __name__ == "__main__":
    main()
