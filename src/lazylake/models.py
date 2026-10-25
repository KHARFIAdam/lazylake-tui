"""Data models shared by every provider (real AWS, demo, tests).

The interface (the TUI) only knows these classes: it does not know whether the data
comes from AWS or from a fake dataset. That is what makes the project testable.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime

# Indicative price of a Glue DPU-hour (us-east-1 / eu-west-1). It varies by region:
# override it with the LAZYLAKE_GLUE_DPU_HOUR_PRICE environment variable.
DEFAULT_DPU_HOUR_PRICE = 0.44

# Number of DPUs per worker, by Glue worker type.
WORKER_DPU = {
    "G.025X": 0.25,
    "G.1X": 1,
    "G.2X": 2,
    "G.4X": 4,
    "G.8X": 8,
    "Standard": 1,
    "Z.2X": 2,
}


def dpu_hour_price() -> float:
    try:
        return float(os.environ.get("LAZYLAKE_GLUE_DPU_HOUR_PRICE", DEFAULT_DPU_HOUR_PRICE))
    except ValueError:
        return DEFAULT_DPU_HOUR_PRICE


@dataclass
class JobRun:
    job_name: str
    run_id: str
    state: str  # SUCCEEDED, FAILED, RUNNING, TIMEOUT, STOPPED...
    started_on: datetime | None = None
    execution_time_s: int = 0
    error_message: str | None = None
    worker_type: str | None = None
    number_of_workers: int | None = None
    max_capacity: float | None = None
    dpu_seconds: float | None = None

    @property
    def dpu_hours(self) -> float | None:
        """DPU-hours consumed (estimated when AWS does not provide DPUSeconds)."""
        if self.dpu_seconds is not None:
            return self.dpu_seconds / 3600
        if not self.execution_time_s:
            return None
        if self.worker_type and self.number_of_workers:
            dpu = WORKER_DPU.get(self.worker_type, 1) * self.number_of_workers
        elif self.max_capacity:
            dpu = self.max_capacity
        else:
            return None
        return dpu * self.execution_time_s / 3600

    @property
    def estimated_cost_usd(self) -> float | None:
        hours = self.dpu_hours
        return None if hours is None else round(hours * dpu_hour_price(), 4)


@dataclass
class GlueJob:
    name: str
    glue_version: str | None = None
    worker_type: str | None = None
    number_of_workers: int | None = None
    last_run: JobRun | None = None
    runs: list[JobRun] = field(default_factory=list)

    @property
    def last_state(self) -> str:
        return self.last_run.state if self.last_run else "NEVER_RUN"
