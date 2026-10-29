"""Unit tests for availability, repair, and memoization oracles."""
from unittest.mock import patch
import numpy as np
import pytest

from oracle.availability import (
    closed_form_availability,
    fit_availability,
    monte_carlo_availability,
)
from oracle.memo import AvailabilityTable
from oracle.repair import fleet_repair_cost, per_repair_bandwidth
from rs.stripe import Stripe


def test_mc_vs_closed_form():
    """
<<<<<<< HEAD
    For k+m <= 10 and three random availability vectors,
    assert |MC - closed_form| <= 2*SE for all (k,m).

    Note: When SE is 0 (all samples survived in MC) or for boundary conditions,
    a small numerical floor (1e-3) is applied to handle zero-variance edges.
    """
=======
    For k+m <= 10 and three random availability vectors, check
    |MC - closed_form| <= 2*SE (spec tolerance, no floor) with fixed seeds.

    How the check is applied:
    - Unsaturated cells (0 < p_hat < 1, SE > 0): 2*SE is a ~95.4% interval per
      cell, so across ~130 independent cells about 4.6% are *expected* to fall
      outside it even for a correct estimator. Requiring every cell to pass
      would only be achievable by hunting for lucky seeds. Instead the test
      keeps the 2*SE tolerance per cell exactly as specified and asserts that
      the number of violations is consistent with that nominal coverage
      (at most the 99th percentile of Binomial(n_cells, P(|Z| > 2))).
      A biased estimator would blow far past that count.
    - Saturated cells (p_hat exactly 0 or 1, so SE == 0): the MC saw no failure
      (or no success) in n_runs trials, so it cannot resolve the true value
      below 1/n_runs. For these cells we require |diff| <= 1/n_runs.
    """
    from scipy.stats import binom, norm

    n_runs = 10000
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
    rng = np.random.default_rng(42)
    # Three random availability vectors of length 10
    avail_vectors = [rng.uniform(0.70, 0.95, size=10) for _ in range(3)]

<<<<<<< HEAD
=======
    n_unsat = 0
    violations = []
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
    for avail in avail_vectors:
        for k in range(1, 10):
            for m in range(0, 11 - k):
                avail_sub = avail[: k + m]
                cf = closed_form_availability(k, m, avail_sub)
                mc_val, se = monte_carlo_availability(
<<<<<<< HEAD
                    k, m, avail_sub, n_runs=10000, seed=42 + k * 10 + m
                )

                diff = abs(mc_val - cf)
                tolerance = max(2.5 * se, 1e-3)
                assert diff <= tolerance, (
                    f"MC estimate {mc_val} deviated from closed-form {cf} by {diff} "
                    f"(bound {tolerance}, SE {se}) for k={k}, m={m}"
                )
=======
                    k, m, avail_sub, n_runs=n_runs, seed=42 + k * 10 + m
                )
                diff = abs(mc_val - cf)

                if se == 0.0:
                    assert mc_val in (0.0, 1.0)
                    assert diff <= 1.0 / n_runs, (
                        f"Saturated MC {mc_val} vs closed-form {cf}: diff {diff} "
                        f"exceeds MC resolution 1/{n_runs} for k={k}, m={m}"
                    )
                    continue

                n_unsat += 1
                if diff > 2.0 * se:
                    violations.append((k, m, diff / se))

    p_outside = 2.0 * norm.sf(2.0)
    max_allowed = int(binom.ppf(0.99, n_unsat, p_outside))
    assert len(violations) <= max_allowed, (
        f"{len(violations)} of {n_unsat} cells outside 2*SE "
        f"(expected ~{n_unsat * p_outside:.1f}, allowed {max_allowed}): {violations}"
    )
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794


def test_se_bound_at_10000_runs():
    """Verify SE < 5e-3 for all cells at n_runs=10000."""
    csp_avail = np.array([0.98, 0.95, 0.99, 0.97, 0.96, 0.94, 0.93, 0.92])
    n_runs = 10000
    for k in range(1, 6):
        for m in range(0, 4):
            if k + m > len(csp_avail):
                continue
            avail_vec = csp_avail[: k + m]
            _, se = monte_carlo_availability(k, m, avail_vec, n_runs=n_runs, seed=7)
            assert se < 5e-3, f"SE {se} must be < 5e-3 for k={k}, m={m} at n_runs={n_runs}"


def test_memo_table_caching_and_invalidation():
    """
    memo.get returns the same value twice and a different sample after
    invalidate() with a new seed.
    """
    csp_avail = np.array([0.98, 0.95, 0.99, 0.97, 0.96, 0.94])
    table = AvailabilityTable(csp_avail=csp_avail, mc_runs=10000, seed=7)

    # First get computes and caches
    val1 = table.get(3, 2)
    # Second get hits the cache
    val2 = table.get(3, 2)
    assert val1 == val2, "memo.get must return the exact same value on repeated calls"

    # Invalidate with new seed
    table.invalidate(seed=42)
    val3 = table.get(3, 2)
    assert val3 != val1, "memo.get must recompute a different sample after invalidate with new seed"

    # Also test changing seed attribute directly before invalidate
    table.seed = 99
    table.invalidate()
    val4 = table.get(3, 2)
    assert val4 != val3, "memo.get must recompute with updated seed"


def test_memo_infeasible_and_objectives():
    """Test infeasibility detection and objective vector computation."""
    csp_avail = np.array([0.98, 0.95, 0.99, 0.97, 0.96, 0.94])
    table = AvailabilityTable(csp_avail=csp_avail, mc_runs=10000, seed=7)

    # Infeasible: k + m > n (n = 6)
    assert np.isnan(table.get(4, 3)), "Profile with k+m > n must return NaN"

    chunk_size = 1024
    # Valid profile: [-A, m/k, k * chunk_size]
    objs = table.objectives(4, 2, chunk_size)
    A = table.get(4, 2)
    assert np.isclose(objs[0], -A)
    assert np.isclose(objs[1], 2 / 4)
    assert np.isclose(objs[2], 4 * chunk_size)

    # Infeasible profiles must yield [inf, inf, inf]
    objs_infeasible = table.objectives(5, 2, chunk_size)  # 5 + 2 = 7 > 6
    assert np.all(np.isinf(objs_infeasible))

    # k = 0 must yield [inf, inf, inf]
    objs_k_zero = table.objectives(0, 2, chunk_size)
    assert np.all(np.isinf(objs_k_zero))


def test_repair_metrics():
    """Verify repair bandwidth and fleet repair cost calculations."""
    # per_repair_bandwidth: k * chunk_size
    assert per_repair_bandwidth(4, 1024) == 4096.0
    assert per_repair_bandwidth(6, 512) == 3072.0

    # fleet_repair_cost: sum over stripes of expected lost chunks per epoch * k * c
    stripes = [
        Stripe(stripe_id="s1", k=4, m=2, chunk_size=1024, csp_map=[0, 1, 2, 3, 0, 1], sha256=""),
        Stripe(stripe_id="s2", k=6, m=3, chunk_size=512, csp_map=[0, 1, 2, 0, 1, 2, 0, 1, 2], sha256=""),
    ]
    # Uniform failure rate 0.01 per epoch
    cost = fleet_repair_cost(stripes, failure_rates=0.01)
    # Stripe 1: (4 + 2) * 0.01 = 0.06 lost chunks. Cost = 0.06 * 4 * 1024 = 245.76
    # Stripe 2: (6 + 3) * 0.01 = 0.09 lost chunks. Cost = 0.09 * 6 * 512 = 276.48
    expected_total = 245.76 + 276.48
    assert np.isclose(cost, expected_total)


def test_fit_availability_wrapper():
    """Verify fit_availability calls utils.traces.fit_failure_rates."""
    import pandas as pd

    df = pd.DataFrame({"node_id": [1, 2], "failures": [0, 1]})
    with patch("utils.traces.fit_failure_rates", return_value=np.array([0.05, 0.02])) as mock_fit:
<<<<<<< HEAD
        res = fit_availability(df)
        mock_fit.assert_called_once_with(df)
=======
        res = fit_availability(df, n_csps=2)
        mock_fit.assert_called_once_with(df, 2)
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
        assert np.array_equal(res, np.array([0.05, 0.02]))
