from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

from simulator.csp import CSP


@dataclass
class ProfileAssignment:
    """One (k, m, chunk_size) tuple per stripe. chunk_size is in BYTES."""
    profiles: List[Tuple[int, int, int]]  # [(k, m, chunk_size_bytes), ...]


@dataclass
class FleetReport:
    # --- spec fields ---
    availability: float
    storage_overhead: float
    bytes_repaired: int
    mean_repair_latency_ms: float
    # --- optional observability fields (extensions) ---
    # Per-CSP chunk counts for this epoch, so a monitor can compute OBSERVED
    # failure rates (lost / placed) instead of reading the true probabilities.
    lost_per_csp: Optional[np.ndarray] = None
    placed_per_csp: Optional[np.ndarray] = None
    # Stripes with fewer than k survivors cannot be repaired; their data is lost.
    dead_stripes: int = 0
    bytes_lost: int = 0  # k * c per dead stripe (user data that is unrecoverable)

    def observed_failure_rates(self) -> np.ndarray:
        """lost / placed per CSP; NaN for CSPs that held no chunks this epoch."""
        if self.lost_per_csp is None or self.placed_per_csp is None:
            raise ValueError("FleetReport has no per-CSP counts")
        placed = np.asarray(self.placed_per_csp, dtype=float)
        lost = np.asarray(self.lost_per_csp, dtype=float)
        out = np.full(placed.shape, np.nan)
        np.divide(lost, placed, out=out, where=placed > 0)
        return out


class Fleet:
    def __init__(self, csps: List[CSP], assignment: ProfileAssignment, seed: int = 0):
        self.csps = csps
        self.assignment = assignment
        self.seed = seed
        self._n_csps = len(csps)

    def simulate_epoch(self, seed: int) -> FleetReport:
        """
        Simulate one epoch:
        - Chunks placed round-robin on CSPs with a GLOBAL offset that carries
          over between stripes (stripe i starts where stripe i-1 ended).
          Note: the oracle (AvailabilityTable) always places a stripe on CSPs
          0..k+m-1 mod n; the two agree only when (k+m) is a multiple of n.
        - Bernoulli survival drawn per chunk from its CSP's availability.
        - Stripe is alive if survivors >= k.
        - bytes_repaired = sum over ALIVE stripes of lost chunks × k × c
          (each lost chunk needs k reads). Dead stripes cannot be repaired;
          their user data (k × c) is reported in bytes_lost instead.
        - storage_overhead = sum((k+m)*c) / sum(k*c).
        - latency per repair = k × mean latency of ALL CSPs the stripe is
          placed on (survivors and failed alike); mean_repair_latency_ms is
          the mean over repairs, NaN if there were no repairs.
        """
        rng = np.random.default_rng(seed)

        stripes = self.assignment.profiles  # list of (k, m, chunk_size_bytes)
        n_stripes = len(stripes)

        alive_stripes = 0
        dead_stripes = 0
        total_bytes_repaired = 0
        total_bytes_lost = 0
        repair_latencies = []

        total_encoded_bytes = 0  # sum((k+m)*c)
        total_data_bytes = 0     # sum(k*c)

        lost_per_csp = np.zeros(self._n_csps, dtype=np.int64)
        placed_per_csp = np.zeros(self._n_csps, dtype=np.int64)

        csp_availabilities = np.array([c.availability for c in self.csps])
        csp_latencies = np.array([c.latency_ms for c in self.csps])

        chunk_offset = 0
        for (k, m, chunk_size) in stripes:
            n_chunks = k + m
            total_encoded_bytes += n_chunks * chunk_size
            total_data_bytes += k * chunk_size

            csp_indices = (chunk_offset + np.arange(n_chunks)) % self._n_csps
            avails = csp_availabilities[csp_indices]

            survived = rng.random(n_chunks) < avails

            np.add.at(placed_per_csp, csp_indices, 1)
            np.add.at(lost_per_csp, csp_indices[~survived], 1)

            n_survived = int(survived.sum())
            n_lost = n_chunks - n_survived

            if n_survived >= k:
                alive_stripes += 1
                if n_lost > 0:
                    total_bytes_repaired += n_lost * k * chunk_size
                    repair_latencies.append(
                        k * float(np.mean(csp_latencies[csp_indices])))
            else:
                dead_stripes += 1
                total_bytes_lost += k * chunk_size

            chunk_offset += n_chunks

        fleet_availability = alive_stripes / n_stripes if n_stripes > 0 else 0.0
        storage_overhead = (total_encoded_bytes / total_data_bytes
                            if total_data_bytes > 0 else 0.0)
        mean_repair_latency = (float(np.mean(repair_latencies))
                               if repair_latencies else float("nan"))

        return FleetReport(
            availability=fleet_availability,
            storage_overhead=storage_overhead,
            bytes_repaired=int(total_bytes_repaired),
            mean_repair_latency_ms=mean_repair_latency,
            lost_per_csp=lost_per_csp,
            placed_per_csp=placed_per_csp,
            dead_stripes=dead_stripes,
            bytes_lost=int(total_bytes_lost),
        )

    @staticmethod
    def assign_from_profile(
        k: int,
        m: int,
        chunk_size: int,
        n_stripes: int,
    ) -> ProfileAssignment:
        """Apply the same (k, m, chunk_size_bytes) profile to all stripes."""
        return ProfileAssignment(profiles=[(k, m, chunk_size)] * n_stripes)
