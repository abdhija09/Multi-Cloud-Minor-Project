import json

import numpy as np
import pandas as pd
import pytest

from utils.logging import log_run, load_runs, run_dir_for, clear_runs, config_hash
from eval.reproducibility import SeedManager, experiment_id, repeat_run, significance_test


def test_log_run_load_runs_round_trip(tmp_path):
    for rep in range(3):
        seed = 1000 + rep
        log_run({"experiment": "EX", "regime": "low", "repeat": rep, "seed": seed},
                {"hv": 0.5 + rep, "igd": 0.0},
                run_dir_for("EX", f"low_rep{rep}_seed{seed}", runs_root=tmp_path))

    meta = json.loads((tmp_path / "EX" / "low_rep1_seed1001" / "meta.json").read_text())
    for key in ("seed", "config_hash", "git_commit", "git_dirty", "timestamp_utc"):
        assert key in meta
    assert meta["config_hash"] == config_hash() and len(meta["config_hash"]) == 64

    df = load_runs("EX", runs_root=tmp_path)
    assert len(df) == 3
    assert sorted(df["seed"]) == [1000, 1001, 1002]
    assert sorted(df["hv"]) == [0.5, 1.5, 2.5]
    assert set(df["run_name"]) == {f"low_rep{r}_seed{1000 + r}" for r in range(3)}


def test_log_run_multi_row_metrics_and_overwrite(tmp_path):
    d = run_dir_for("EX", "r0", runs_root=tmp_path)
    log_run({"seed": 1}, [{"epoch": e, "A": 1.0} for e in range(5)], d)
    log_run({"seed": 1}, pd.DataFrame({"epoch": [0, 1], "A": [0.9, 0.8]}), d)
    df = load_runs("EX", runs_root=tmp_path)
    assert list(df["epoch"]) == [0, 1]           # overwritten, not appended


def test_log_run_requires_seed(tmp_path):
    with pytest.raises(ValueError):
        log_run({"experiment": "EX"}, {"x": 1}, tmp_path / "r")


def test_meta_metric_name_collision_is_prefixed(tmp_path):
    log_run({"seed": 3, "x": "meta"}, {"x": 1.0}, run_dir_for("EX", "r", runs_root=tmp_path))
    df = load_runs("EX", runs_root=tmp_path)
    assert df.loc[0, "x"] == 1.0 and df.loc[0, "meta_x"] == "meta"


def test_load_runs_missing_and_clear(tmp_path):
    assert load_runs("NOPE", runs_root=tmp_path).empty
    log_run({"seed": 1}, {"x": 1}, run_dir_for("EX", "low_rep0", runs_root=tmp_path))
    log_run({"seed": 1}, {"x": 1}, run_dir_for("EX", "high_rep0", runs_root=tmp_path))
    assert clear_runs("EX", prefix="low_", runs_root=tmp_path) == 1
    assert list(load_runs("EX", runs_root=tmp_path)["run_name"]) == ["high_rep0"]


def test_seed_manager_formula_and_stable_ids():
    sm = SeedManager(base_seed=42)
    assert sm.seed_for("E3", 0) == 42 * 10**6 + 3 * 10**3 + 0
    assert sm.seed_for("E3-low", 7) == 42_003_007
    assert sm.seed_for(4, 2) == 42_004_002
    assert sm.seed_for("E0", 0) == 42_000_000
    # order-independent: calling other experiments first changes nothing
    sm.seed_for("E5", 0)
    assert sm.seed_for("E3", 0) == 42_003_000
    assert SeedManager(1).seed_for("E2", 5) == 1_002_005
    assert experiment_id("sensitivity_analysis") == 3      # name from experiments.yaml
    with pytest.raises(ValueError):
        experiment_id("not-an-experiment")


def test_repeat_run_stats_and_n1():
    df = repeat_run(lambda s: {"v": float(s % 1000)}, "E1", repeats=4)
    row = df.set_index("metric").loc["v"]
    assert row["mean"] == pytest.approx(1.5)
    assert row["std"] == pytest.approx(np.std([0, 1, 2, 3], ddof=1))
    assert row["ci_upper"] > row["mean"] > row["ci_lower"]
    one = repeat_run(lambda s: {"v": 2.0}, "E1", repeats=1).iloc[0]
    assert one["std"] == 0.0 and one["ci_95"] == 0.0


def test_significance_test():
    assert significance_test([1, 2, 3, 4, 5], [10, 11, 12, 13, 14]) < 0.05
    assert significance_test([1, 2, 3], [1, 2, 3]) > 0.5
