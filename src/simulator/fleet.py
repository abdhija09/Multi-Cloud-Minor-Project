from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

from simulator.csp import CSP


@dataclass
class ProfileAssignment:
    """One (k, m, chunk_size) tuple per stripe."""
    profiles: List[Tuple[int, int, int]]  # [(k, m, chunk_size_bytes), ...]


@dataclass
class FleetReport:
    availability: float
    storage_overhead: float
    bytes_repaired: int
    mean_repair_latency_ms: float


class Fleet:
    def __init__(self, csps: List[CSP], assignment: ProfileAssignment, seed: int = 0):
        self.csps = csps
        self.assignment = assignment
        self.seed = seed
        self._n_csps = len(csps)

    def simulate_epoch(self, seed: int) -> FleetReport:
        """
        Simulate one epoch:
        - Chunks placed round-robin on CSPs.
        - Bernoulli survival drawn per chunk from its CSP's availability.
        - Stripe is alive if survivors >= k.
        - Count lost chunks × k × c as bytes_repaired.
        - storage_overhead = sum((k+m)*c) / sum(k*c).
        - latency = mean over repair events of k × mean_csp_latency.
        """
        rng = np.random.default_rng(seed)

        stripes = self.assignment.profiles  # list of (k, m, chunk_size_bytes)
        n_stripes = len(stripes)

        alive_stripes = 0
        total_bytes_repaired = 0
        repair_latencies = []

        total_encoded_bytes = 0  # sum((k+m)*c)
        total_data_bytes = 0     # sum(k*c)

        # Build a flat list of (csp_idx, avail) assignments round-robin
        # We assign chunks csp_slot = chunk_global_index % n_csps
        csp_availabilities = np.array([c.availability for c in self.csps])
        csp_latencies = np.array([c.latency_ms for c in self.csps])

        chunk_offset = 0
        for (k, m, chunk_size) in stripes:
            n_chunks = k + m
            total_encoded_bytes += n_chunks * chunk_size
            total_data_bytes += k * chunk_size

            # Round-robin CSP assignment for this stripe's chunks
            csp_indices = [(chunk_offset + i) % self._n_csps for i in range(n_chunks)]
            avails = csp_availabilities[csp_indices]

            # Draw Bernoulli survival for each chunk
            survived = rng.random(n_chunks) < avails  # True if chunk survived

            n_survived = int(survived.sum())
            n_lost = n_chunks - n_survived
            stripe_alive = n_survived >= k

            if stripe_alive:
                alive_stripes += 1

            # Bytes repaired = lost chunks × k × chunk_size
            # (we need k reads to reconstruct each lost chunk)
            bytes_repaired_stripe = n_lost * k * chunk_size
            total_bytes_repaired += bytes_repaired_stripe

            # If repair is needed (any lost chunk), record latency
            if n_lost > 0:
                # Latency = k × mean latency of surviving CSPs used for repair
                surviving_csp_latencies = csp_latencies[csp_indices][survived]
                if len(surviving_csp_latencies) > 0:
                    mean_read_latency = np.mean(surviving_csp_latencies)
                else:
                    mean_read_latency = np.mean(csp_latencies)
                repair_latencies.append(k * mean_read_latency)

            chunk_offset += n_chunks

        fleet_availability = alive_stripes / n_stripes if n_stripes > 0 else 0.0
        storage_overhead = (total_encoded_bytes / total_data_bytes
                            if total_data_bytes > 0 else 0.0)
        mean_repair_latency = (float(np.mean(repair_latencies))
                               if repair_latencies else 0.0)

        return FleetReport(
            availability=fleet_availability,
            storage_overhead=storage_overhead,
            bytes_repaired=total_bytes_repaired,
            mean_repair_latency_ms=mean_repair_latency,
        )

    @staticmethod
    def assign_from_profile(
        k: int,
        m: int,
        chunk_size: int,
        n_stripes: int,
    ) -> ProfileAssignment:
        """Apply the same (k, m, chunk_size) profile to all stripes."""
        return ProfileAssignment(profiles=[(k, m, chunk_size)] * n_stripes)
