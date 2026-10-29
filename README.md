<<<<<<< HEAD
# rs-adaptive: Self-Adaptive Reed–Solomon (k, m) Parameter Selection for Multi-Cloud Encrypted Storage using NSGA-II

rs-adaptive is a research framework for dynamic multi-objective optimization of Reed–Solomon erasure coding parameters (k, m) across heterogeneous multi-cloud storage providers. By formulating parameter selection as a multi-objective optimization problem spanning availability, repair overhead, storage cost, and latency, the system leverages NSGA-II to discover Pareto-optimal configurations and employs an online adaptive controller to dynamically adjust striping regimes under shifting cloud provider failure rates and network conditions.

## Execution Order

The research pipeline scripts should be executed in the following sequential order:

1. `scripts/01_download_datasets.sh` - Download empirical cloud availability and failure traces.
2. `scripts/02_fit_failure_stats.py` - Fit statistical failure distributions and regime parameters from traces.
3. `scripts/03_run_exact_front.py` - Compute ground-truth Pareto fronts using exhaustive search across regimes.
4. `scripts/04_run_search.py` - Execute NSGA-II and metaheuristic baseline comparisons across experimental regimes.
5. `scripts/05_run_adaptation.py` - Run dynamic fleet adaptation simulations under non-stationary regime shifts.
6. `scripts/06_verify_roundtrip.py` - Validate end-to-end data integrity with encode, failure-simulate, and decode roundtrips.
7. `scripts/07_summarize.py` - Aggregate experimental runs, compute statistical metrics, and generate tables/figures.
=======
# RS-adaptive: Self-Adaptive Reed–Solomon (k, m) Selection for Multi-Cloud Storage using NSGA-II

This project stores a file across several cloud providers using Reed–Solomon (RS) erasure coding.
It picks how many data pieces (k) and spare pieces (m) to use, by searching for the best trade-off with NSGA-II.
When a provider becomes less reliable, it notices the change and picks new values on its own.


## The problem

A CSP (Cloud Service Provider) can be down at any moment.
RS(k, m) cuts a file into k pieces and adds m spare pieces; any k pieces rebuild the file.
More spares means safer data but more storage and more repair traffic.
The best (k, m) depends on how reliable the CSPs are, and that changes over time.

We balance three goals:

1. **Availability** — the chance the file can be rebuilt (higher is better).
2. **Storage overhead** — m / k, the extra storage paid for spares (lower is better).
3. **Repair bandwidth** — k × chunk size, bytes downloaded to rebuild one lost piece (lower is better).

## Setup (once)

Needs Python 3.11.

```bash
python3.11 -m venv .venv
source .venv/bin/activate          # Windows (Git Bash): source .venv/Scripts/activate
pip install -r requirements.txt
python -m pytest -q                # expect: 45 passed
```

## Run everything (about 10 minutes on a laptop)

```bash
bash scripts/01_download_datasets.sh                                # Silesia test files (~65 MB)
python scripts/02_fit_failure_stats.py                              # per-CSP failure rates  -> T0
python scripts/03_run_exact_front.py                                # exact Pareto front     -> R2
python scripts/04_run_search.py --experiment E3-all --repeats 10    # NSGA-II vs exact       -> R3
python scripts/04_run_search.py --experiment E4-all --repeats 10    # fleet vs fixed RS(4,2) -> R4
python scripts/05_run_adaptation.py                                 # drift adaptation       -> R5
python scripts/06_verify_roundtrip.py                               # encode/decode real files -> R7
python scripts/07_summarize.py                                      # R1, R6, all figures, ALL_TABLES.md
```

Script 07 stops with an error if R7 shows even one hash mismatch.

Live demo of one file (not part of the pipeline):

```bash
python scripts/demo_roundtrip.py --file data/silesia/dickens --k 6 --m 3 --delete 3   # rebuilt OK
python scripts/demo_roundtrip.py --file data/silesia/dickens --k 6 --m 3 --delete 4   # fails: too few pieces
```

## Where the results are

- `results/tables/ALL_TABLES.md` — every table (T0, R1–R7) with a plain-English caption.
- `results/tables/*.csv` — the same tables as CSV.
- `results/figures/*.png` — Pareto fronts, NSGA-II convergence, drift timeline, overhead vs fixed.
- `experiments/runs/<experiment>/<run>/` — one folder per run with `meta.json` (seed, config hash, git commit) and `metrics.csv`.

`data/` and `experiments/runs/` are not in git. Run the pipeline to recreate them.

## Key results (from `ALL_TABLES.md`)

| | low reliability (8 CSPs) | medium (6 CSPs) | high (4 CSPs) |
|---|---|---|---|
| Knee (k, m, chunk) | RS(2,2), 256 KB | RS(2,1), 256 KB | RS(2,1), 256 KB |
| NSGA-II vs exact front | HV 1.000, IGD 0 | HV 1.000, IGD 0 | HV 1.000, IGD 0 |
| Fixed RS(4,2) availability (exact) | 2.6 nines | 5.7 nines | infeasible (needs 6 CSPs) |
| Our knee availability (exact) | 3.7 nines | 4.2 nines | 6.1 nines |

- Drift test (medium): detected after 1.3 epochs, 0 false alarms before drift, availability 0.9998 vs 0.9996 without adaptation.
- Round-trip: 5,091 stripe checks on the full Silesia corpus, 0 mismatches.

## Folder map

```
config/            default.yaml (all parameters), regimes.yaml, experiments.yaml
src/rs/            Reed–Solomon over GF(2^8): galois.py, codec.py, stripe.py
src/oracle/        availability (Monte-Carlo + exact), memo table, repair cost
src/search/        NSGA-II, knee point; moead/bpso/mspga are stubs for future work
src/baselines/     exact enumeration, fixed RS(4,2), greedy
src/simulator/     CSPs and the 1,000-stripe fleet
src/adaptation/    EMA monitor and the re-optimisation controller
src/eval/          HV, IGD, spacing, nines; seeds and repeat runs
src/utils/         failure traces, Silesia corpus, run logging
scripts/           01–07 pipeline + demo_roundtrip.py
tests/             pytest suite
results/           tables and figures
```

## Notes

- **No cloud account needed.** Failure rates are synthetic, drawn with a fixed seed inside each regime's range.
  `bash scripts/01_download_datasets.sh --with-azure` also fetches the Azure trace, but it is optional.
- **R1 Monte-Carlo check.** With the deployed 10,000 runs, the worst cell is off by 0.0077 (3.9 standard errors).
  The 0.005 error limit is therefore checked at 160,000 runs, where the worst error is 0.0026.
- Every run is seeded, so the same commands give the same numbers.

## Docs

- [AUDIT_REPORT.md](AUDIT_REPORT.md) — what was checked and fixed
>>>>>>> 0808679dfd75aa9d19055fdcb55817ed73b00794
