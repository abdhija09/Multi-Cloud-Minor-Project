"""
Run logging utilities: one folder per run with ``meta.json`` + ``metrics.csv``,
and a loader that gathers every run of an experiment into one DataFrame.

Layout (paths resolve from the repo root, independent of the cwd)::

    <repo>/experiments/runs/<experiment>/<run_name>/meta.json
    <repo>/experiments/runs/<experiment>/<run_name>/metrics.csv

``log_run`` stamps every meta.json with provenance it computes itself:

- ``config_hash``     sha256 of config/default.yaml + regimes.yaml + experiments.yaml
                      (file contents concatenated in that order)
- ``git_commit``      ``git rev-parse HEAD`` ('unknown' if git is unavailable)
- ``git_dirty``       True if the worktree has uncommitted changes (None if unknown)
- ``timestamp_utc``   ISO-8601 UTC time of the write

``seed`` is mandatory in ``meta`` (ValueError otherwise).
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Optional, Union

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNS_ROOT = REPO_ROOT / "experiments" / "runs"
CONFIG_FILES = ("default.yaml", "regimes.yaml", "experiments.yaml")

MetricsLike = Union[Mapping, Iterable[Mapping], pd.DataFrame]


def config_hash(config_dir: Optional[Path] = None) -> str:
    """sha256 hex digest of the concatenated config file contents."""
    config_dir = Path(config_dir) if config_dir else REPO_ROOT / "config"
    h = hashlib.sha256()
    for name in CONFIG_FILES:
        h.update((config_dir / name).read_bytes())
    return h.hexdigest()


def git_info(repo_root: Optional[Path] = None) -> dict:
    """{'git_commit': sha or 'unknown', 'git_dirty': bool or None}."""
    cwd = str(repo_root or REPO_ROOT)
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cwd,
                                capture_output=True, text=True, timeout=10,
                                check=True).stdout.strip() or "unknown"
    except Exception:
        return {"git_commit": "unknown", "git_dirty": None}
    try:
        status = subprocess.run(["git", "status", "--porcelain"], cwd=cwd,
                                capture_output=True, text=True, timeout=10,
                                check=True).stdout
        dirty = bool(status.strip())
    except Exception:
        dirty = None
    return {"git_commit": commit, "git_dirty": dirty}


def runs_dir(experiment: str, runs_root: Optional[Union[str, Path]] = None) -> Path:
    """<runs_root>/<experiment> (runs_root defaults to <repo>/experiments/runs)."""
    root = Path(runs_root) if runs_root is not None else DEFAULT_RUNS_ROOT
    return root / experiment


def run_dir_for(experiment: str, run_name: str,
                runs_root: Optional[Union[str, Path]] = None) -> Path:
    return runs_dir(experiment, runs_root) / run_name


def clear_runs(experiment: str, prefix: str = "",
               runs_root: Optional[Union[str, Path]] = None) -> int:
    """
    Delete run folders of *experiment* whose name starts with *prefix*.
    Scripts call this before re-logging a regime so stale runs (e.g. from a
    run with more repeats or a different seed formula) never mix into
    load_runs(). Returns the number of folders removed.
    """
    d = runs_dir(experiment, runs_root)
    if not d.exists():
        return 0
    n = 0
    for p in d.iterdir():
        if p.is_dir() and p.name.startswith(prefix):
            shutil.rmtree(p)
            n += 1
    return n


def _metrics_frame(metrics: MetricsLike) -> pd.DataFrame:
    if isinstance(metrics, pd.DataFrame):
        return metrics.reset_index(drop=True)
    if isinstance(metrics, Mapping):
        return pd.DataFrame([dict(metrics)])
    return pd.DataFrame([dict(m) for m in metrics])


def log_run(meta: dict, metrics: MetricsLike, run_dir) -> Path:
    """
    Write ``meta.json`` and ``metrics.csv`` into *run_dir* (created if needed;
    a relative path is taken relative to the repo root). Both files are
    overwritten, so re-running a script replaces its runs.

    meta    : must contain 'seed'; config_hash, git_commit, git_dirty and
              timestamp_utc are added here (they override caller values).
    metrics : dict (one row), list of dicts, or DataFrame (one row per entry,
              e.g. a per-epoch log).

    Returns the run directory path.
    """
    if "seed" not in meta:
        raise ValueError("log_run: meta must include 'seed'")

    run_dir = Path(run_dir)
    if not run_dir.is_absolute():
        run_dir = REPO_ROOT / run_dir
    run_dir.mkdir(parents=True, exist_ok=True)

    full_meta = dict(meta)
    full_meta["config_hash"] = config_hash()
    full_meta.update(git_info())
    full_meta["timestamp_utc"] = datetime.now(timezone.utc).isoformat()

    with open(run_dir / "meta.json", "w") as f:
        json.dump(full_meta, f, indent=2, default=str)

    _metrics_frame(metrics).to_csv(run_dir / "metrics.csv", index=False)
    return run_dir


def load_runs(experiment: str,
              runs_root: Optional[Union[str, Path]] = None) -> pd.DataFrame:
    """
    Load every run folder under <runs_root>/<experiment>/ into one DataFrame.

    Each metrics.csv row becomes a row; scalar meta fields are added as
    columns (named ``meta_<key>`` when the key collides with a metric
    column; non-scalar values are stored as JSON strings), plus ``run_name``.
    Returns an empty DataFrame if there are no runs.
    """
    d = runs_dir(experiment, runs_root)
    if not d.exists():
        return pd.DataFrame()

    frames = []
    for run_dir in sorted(p for p in d.iterdir() if p.is_dir()):
        metrics_path = run_dir / "metrics.csv"
        if not metrics_path.exists():
            continue
        df = pd.read_csv(metrics_path)
        meta_path = run_dir / "meta.json"
        if meta_path.exists():
            with open(meta_path) as f:
                meta = json.load(f)
            for k, v in meta.items():
                col = f"meta_{k}" if k in df.columns else k
                if isinstance(v, (dict, list)):
                    v = json.dumps(v)
                df[col] = v
        df["run_name"] = run_dir.name
        frames.append(df)

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
