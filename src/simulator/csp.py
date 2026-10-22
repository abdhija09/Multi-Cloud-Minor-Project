from dataclasses import dataclass


@dataclass
class CSP:
    csp_id: int
    availability: float        # probability a chunk survives one epoch
    capacity_bytes: int
    unit_storage_cost: float   # cost per byte per epoch
    unit_egress_cost: float    # cost per byte transferred out
    latency_ms: float          # mean repair-read latency in milliseconds
