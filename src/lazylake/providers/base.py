"""Contract shared by every data source.

Adding a service (Athena, Step Functions, SageMaker…) = writing a class
that fulfils this contract. It is the ideal entry point for contributors.
"""

from __future__ import annotations

from typing import Protocol

from lazylake.models import GlueJob, JobRun


class GlueProvider(Protocol):
    label: str  # shown in the header, e.g. "aws:prod / eu-west-1"

    def list_jobs(self) -> list[GlueJob]:
        """All jobs, with their last run filled in."""
        ...

    def list_runs(self, job_name: str, limit: int = 20) -> list[JobRun]:
        """Run history of a job, most recent first."""
        ...

    def get_logs(self, run: JobRun, errors_only: bool = True) -> list[str]:
        """Raw log lines of a run (the error log by default)."""
        ...
