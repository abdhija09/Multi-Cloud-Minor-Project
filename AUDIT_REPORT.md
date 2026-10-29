# Audit Report — Phases 1 to 5

This report checks the code against the project specification.
Each row says what was expected, what was found, and the final status.

- **PASS** = matches the spec (rows marked "fixed" were wrong at first and have been corrected).
- **NOTE** = a deliberate decision, explained in the row.

Environment: Python 3.11.17 in `.venv`; all packages from `requirements.txt`.
Test suite: green after every fix (see the final section).

## Phase 1 — Layout and configuration

| item | expected | found | status |
|---|---|---|---|
| Folder layout | config/, src/{rs,oracle,search,baselines,adaptation,simulator,eval,utils}, scripts 01–07, tests ×4 | all files present with the exact names | PASS |
| results/tables, results/figures | present | present | PASS |
| data/, experiments/runs/ | present, git-ignored | were never created; script 01 now creates them | PASS (fixed) |
| rs.max_k / max_m | 16 / 8 | 16 / 8 | PASS |
| rs.chunk_sizes_kb | [256 … 8192] | as specified | PASS |
| rs.field_poly | 0x11D | 0x11D (loads as int 285) | PASS |
| oracle.mc_runs / mc_seed | 10000 / 7 | 10000 / 7 | PASS |
| search params | 50 / 40 / 0.05 / 0.9 | as specified | PASS |
| adaptation params | β 0.3 / ε 0.10 / 3600 s | as specified | PASS |
| stats params | 10 / 42 / 0.05 | as specified | PASS |
| regimes | low 8 [1e-2,1e-1], medium 6 [1e-3,1e-2], high 4 [1e-4,1e-3] | values right, but `1e-2` loaded as a **string** in PyYAML | PASS (fixed: written as `1.0e-2` etc.) |
| experiments.yaml | E1–E6 with stripes and repeats | present | PASS |
| requirements.txt | 9 packages | all 9 | PASS |
| pytest.ini | pythonpath = src | present | PASS |
| .gitignore | data/, experiments/runs/ | present | PASS |
| Stubs | moead, bpso, mspga raise NotImplementedError("extension") | present | PASS |
| Per-phase git commits | one commit per phase | one commit for phases 1–5 | NOTE (owner decision: history kept as is; one commit for the remaining work) |

## Phase 2 — Reed–Solomon codec (src/rs)

| item | expected | found | status |
|---|---|---|---|
| build_tables | returns (exp[512], log[256]) for 0x11D | built tables but returned nothing | PASS (fixed) |
| gf_mul | exp/log tables; equals naive multiply on all 65,536 pairs | correct; tested exhaustively | PASS |
| gf_div | correct division | **wrong** when log a < log b (uint16 wrap): gf_div(1,2) gave 1, not 142 | PASS (fixed + exhaustive test) |
| gf_pow | correct powers | overflow for large exponents; gf_pow(0,0) gave 0 | PASS (fixed + tests for e = 0…300 and negative e) |
| gf_inv | a·inv(a) = 1 | correct | PASS |
| Generator matrix | systematic G = [I_k \| P], any k rows invertible | correct (Vandermonde, distinct points) | PASS; test now also covers (16,8) |
| encode / decode / repair | k+m chunks, first k unchanged, decode from any k, repair any lost chunk | correct; pure numpy | PASS; clear errors added for duplicate indices and k+m > 256 |
| verify_roundtrip | SHA-256 over 10 random k-subsets | correct | PASS |
| No RS library | pure numpy | pure numpy | PASS |
| Speed | 4 × 1 MB encode < 2 s | ≈ 0.01 s | PASS |
| Codec tests | k 1–16, m 0–8, 10 subsets, repair | present, but unseeded | PASS (fixed: fixed seeds) |

## Phase 3 — Fitness oracle (src/oracle)

| item | expected | found | status |
|---|---|---|---|
| closed_form_availability | exact subset sum | correct | PASS |
| monte_carlo_availability | (estimate, SE), SE = √(p(1−p)/n) | correct | PASS |
| fit_availability | thin wrapper around fit_failure_rates | crashed (n_csps not passed) | PASS (fixed) |
| AvailabilityTable | precompute / get / invalidate / objectives = [−A, m/k, k·c]; infeasible → inf | correct | PASS |
| Oracle test | \|MC − exact\| ≤ 2·SE | used a looser 2.5·SE with a floor | PASS (fixed — see note below) |

Note on the 2·SE test: a 2·SE band is a 95 % interval, so about 5 % of cells miss it by pure chance.
With fixed seeds, 5 of 130 cells miss (3.8 %).
The test keeps the strict 2·SE check per cell and allows at most the binomial 99th-percentile number of misses (≈ 12).
A biased estimator would blow far past that. Cells where MC gives exactly 0 or 1 must match within 1/n_runs.

## Phase 4 — Search, baselines, metrics

| item | expected | found | status |
|---|---|---|---|
| Problem / ParetoFront / SearchAlgorithm | as spec | correct | PASS |
| exact_pareto | all 864 profiles, non-dominated set | correct | PASS |
| NSGA2 operators | pymoo, integer vars, SBX 0.9, PM 0.05, RoundingRepair, pop 50, gen 40 | correct | PASS |
| Feasibility repair m ← n − k | applied to the population | was applied to a copy inside `_evaluate`, so results could keep infeasible points | PASS (fixed: proper pymoo `Repair` class) |
| optimize_with_history | per-generation fronts | correct | PASS |
| knee_point | min normalised distance to utopia | normalised availability linearly, so the knee ignored reliability (same knee (2,1) in every regime) | PASS (fixed: availability normalised in "nines", −log10(1−A); objectives unchanged) |
| greedy_profile / fixed_profile | as spec | correct | PASS |
| hypervolume / igd | pymoo HV / IGD | correct | PASS |
| spacing | Schott, by hand | computed on raw units (KB column dominated) | PASS (fixed: normalised by the exact front's bounds) |
| nines | −log10(1−p) | printed "inf nines" when MC saturates | PASS (fixed: "≥4.0 nines (MC limit)") |
| script 03 → R2 + pareto figures | per regime | correct | PASS |
| script 04 E3 → R3 + convergence figures | one regime per `--experiment E3-<regime>` | ignored the regime suffix and ran all regimes | PASS (fixed; per-regime seeds so 03 and 04 see the same providers) |
| Scripts runnable without PYTHONPATH | yes | 03/04/05 needed PYTHONPATH | PASS (fixed) |

## Phase 5 — Fleet simulation and drift adaptation

| item | expected | found | status |
|---|---|---|---|
| CSP dataclass, FleetReport | as spec | correct | PASS |
| Fleet.simulate_epoch | Bernoulli per chunk, overhead, bytes repaired, latency | latency counted "no repairs" as 0 ms; dead stripes counted as repaired | PASS (fixed: NaN when no repairs; lost data counted separately) |
| EMAEstimator(β = 0.3) | update / relative_deviation | started from the first noisy observation | PASS (fixed: starts from the nominal rate) |
| AdaptationController.step | trigger when max relative deviation > 0.10, re-run NSGA-II, return dict | chunk size mixed KB and bytes; was fed the *true* probabilities instead of observed ones | PASS (fixed: bytes everywhere; fed observed lost/placed counts) |
| Trigger noise | — | with real observed counts (~2.5 lost chunks per provider per epoch) the controller fired every epoch, even before drift | PASS (fixed: significance gate — trigger only if deviation > ε **and** a binomial test rejects the nominal rate at α = 0.05 / n_csps; ε and β unchanged) |
| script 04 E4 → R4 | Fixed vs Greedy vs knee, 1,000 stripes, 10 repeats | correct columns | PASS; added the exact oracle availability and the profile used, because 1,000 stripes × 1 epoch cannot resolve above ~3 nines |
| script 05 → R5 + drift_timeline | drift ×5 on CSPs 0–1 at epoch 10, 30 epochs | only the first trigger was applied; the recovery metric could never fail | PASS (fixed: every trigger applied; recovery measured on unavailability) |
| Run folders | every table number backed by experiments/runs/…/meta.json with seed | no script wrote run folders | PASS (fixed in Phase 6 work) |

## Phase 6 — Traces, corpora, logging, reproducibility

| item | expected | found | status |
|---|---|---|---|
| Failure traces | Azure trace fit, synthetic fallback | Azure not used (owner decision: offline project); seeded synthetic rates inside each regime's range; `--with-azure` still available | NOTE |
| Corpora | Silesia loader + chunking | `load_silesia` (folder or zip), `make_chunks` returns chunks + original length | PASS |
| Run logging | meta.json (seed, config hash, git commit) + metrics.csv per run | `log_run` / `load_runs`; 85 run folders across E0, E1, E3–E6, R1, R6 | PASS |
| Reproducibility | SeedManager, repeat_run, significance test | present, tested in `tests/test_logging_repro.py` | PASS |
| Scripts 01, 02, 06, 07 | as spec | written; 07 refuses to run if R7 has any mismatch | PASS |
| Demo helper | — | `scripts/demo_roundtrip.py` added for the viva demo only | NOTE |

## Sanity checks on results

Full pipeline 01 → 07 run on 2026-10-14. Every step exited 0. `pytest -q`: 45 passed.
`results/tables/ALL_TABLES.md` contains no `[TBD]`.

| check | result | status |
|---|---|---|
| Less reliable CSPs need more spares (R2) | knee m = 2 in low, m = 1 in high | PASS |
| NSGA-II finds the exact front (R3) | normalised HV 1.000, IGD 0, knee match 100 % in all 3 regimes | PASS |
| Knee beats fixed RS(4,2) where CSPs are weak (R4 low) | 3.7 nines vs 2.6 nines (exact), at overhead 2.00 vs 1.50 | PASS |
| Medium regime trade-off (R4 medium) | fixed RS(4,2) has more nines (5.7 vs 4.2) at the same overhead; the knee repairs 16× fewer bytes | NOTE — the knee is a balance point, not the most available point |
| High regime (R4 high) | RS(4,2) needs 6 CSPs, only 4 exist → infeasible; knee RS(2,1) gives 6.1 nines | PASS |
| No false alarms before drift (R5) | 0.0 pre-drift triggers (was 10/10 before the significance gate) | PASS |
| Drift is caught and helps (R5) | detected after 1.3 ± 0.35 epochs; availability 0.9998 vs 0.9996 static; overhead 1.73 vs 1.50 | PASS |
| MC oracle error (R1) | at 10,000 runs max \|MC − exact\| = 0.0077 (3.9 SE, one low-regime cell); at 160,000 runs 0.0026 | NOTE — the 0.005 bound is asserted at 160,000 runs |
| Round-trip (R7) | 5,091 stripe checks, 8 profiles, full Silesia corpus, 0 hash mismatches | PASS |
| Resources (R6) | NSGA-II 2.5 s mean, 5.1 s max; peak memory 283 MiB; CPU only | PASS |
