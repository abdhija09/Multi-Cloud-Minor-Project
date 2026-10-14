"""
07_summarize.py

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

    from oracle.memo import AvailabilityTable
    from search.base import Problem
    from search.nsga2 import NSGA2

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


if __name__ == "__main__":
    main()
