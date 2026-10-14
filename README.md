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
