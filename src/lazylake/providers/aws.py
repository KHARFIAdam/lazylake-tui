"""Real AWS provider, based on boto3 (the official AWS SDK for Python).

Credentials are resolved by the standard AWS credential chain: the AWS_PROFILE
variable, ~/.aws/config (including SSO after `aws sso login`), an IAM role…
lazylake never stores any secret.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import boto3
from botocore.exceptions import ClientError

from lazylake.models import GlueJob, JobRun

ERROR_LOG_GROUP = "/aws-glue/jobs/error"
OUTPUT_LOG_GROUP = "/aws-glue/jobs/output"


def _to_run(raw: dict) -> JobRun:
    return JobRun(
        job_name=raw["JobName"],
        run_id=raw["Id"],
        state=raw.get("JobRunState", "UNKNOWN"),
        started_on=raw.get("StartedOn"),
        execution_time_s=raw.get("ExecutionTime", 0) or 0,
        error_message=raw.get("ErrorMessage"),
        worker_type=raw.get("WorkerType"),
        number_of_workers=raw.get("NumberOfWorkers"),
        max_capacity=raw.get("MaxCapacity"),
        dpu_seconds=raw.get("DPUSeconds"),
    )


class AwsGlueProvider:
    def __init__(self, profile: str | None = None, region: str | None = None):
        self.session = boto3.Session(profile_name=profile, region_name=region)
        self.glue = self.session.client("glue")
        self.logs = self.session.client("logs")
        self.label = f"aws:{profile or 'default'} / {self.session.region_name}"

    def list_jobs(self) -> list[GlueJob]:
        jobs: list[GlueJob] = []
        for page in self.glue.get_paginator("get_jobs").paginate():
            for raw in page["Jobs"]:
                jobs.append(
                    GlueJob(
                        name=raw["Name"],
                        glue_version=raw.get("GlueVersion"),
                        worker_type=raw.get("WorkerType"),
                        number_of_workers=raw.get("NumberOfWorkers"),
                    )
                )

        # One get_job_runs call per job: run them in parallel to stay fast
        # even with hundreds of jobs.
        def fill_last_run(job: GlueJob) -> None:
            runs = self.list_runs(job.name, limit=1)
            job.last_run = runs[0] if runs else None

        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(fill_last_run, jobs))
        return sorted(jobs, key=lambda j: j.name.lower())

    def list_runs(self, job_name: str, limit: int = 20) -> list[JobRun]:
        resp = self.glue.get_job_runs(JobName=job_name, MaxResults=limit)
        return [_to_run(r) for r in resp.get("JobRuns", [])]

    def get_logs(self, run: JobRun, errors_only: bool = True) -> list[str]:
        group = ERROR_LOG_GROUP if errors_only else OUTPUT_LOG_GROUP
        lines: list[str] = []
        kwargs = {"logGroupName": group, "logStreamName": run.run_id, "startFromHead": True}
        try:
            while True:
                resp = self.logs.get_log_events(**kwargs)
                lines.extend(e["message"] for e in resp["events"])
                token = resp.get("nextForwardToken")
                if not resp["events"] or token == kwargs.get("nextToken") or len(lines) > 20_000:
                    break
                kwargs["nextToken"] = token
        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            if code == "ResourceNotFoundException":
                return [f"No logs found in {group} for run {run.run_id}."]
            raise
        return lines
