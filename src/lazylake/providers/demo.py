"""Demo provider: fake data, zero AWS calls.

Useful to try the tool without an AWS account, take screenshots
for the README / LinkedIn, and develop the interface offline.
"""

from __future__ import annotations

import zlib
from datetime import datetime, timedelta, timezone

from lazylake.models import GlueJob, JobRun

NOW = datetime.now(timezone.utc)

FAKE_SPARK_LOG = """\
26/10/17 08:41:02 INFO GlueContext: GlueContext initialized
26/10/17 08:41:05 INFO SparkContext: Running Spark version 3.5.4-amzn-0
26/10/17 08:41:20 WARN NativeCodeLoader: Unable to load native-hadoop library
26/10/17 08:42:11 INFO DAGScheduler: Job 0 finished
26/10/17 08:43:57 ERROR ProcessLauncher: Error from Python:Traceback (most recent call last):
  File "/tmp/orders_daily.py", line 42, in <module>
    df = spark.read.parquet("s3://acme-lake/raw/orders/dt=2026-10-16/")
  File "/opt/amazon/spark/python/lib/pyspark.zip/pyspark/sql/readwriter.py", line 544, in parquet
pyspark.errors.exceptions.captured.AnalysisException: [PATH_NOT_FOUND] Path does not exist: s3://acme-lake/raw/orders/dt=2026-10-16.
	at org.apache.spark.sql.errors.QueryCompilationErrors$.dataPathNotExistError(QueryCompilationErrors.scala:1500)
	at org.apache.spark.sql.execution.datasources.DataSource$.checkAndGlobPathIfNecessary(DataSource.scala:757)
	at scala.collection.immutable.List.foreach(List.scala:431)
26/10/17 08:43:58 INFO SparkContext: Successfully stopped SparkContext
"""


def _run(
    job: str, n: int, state: str, hours_ago: float, exec_s: int, workers: int = 5, error: str | None = None
) -> JobRun:
    return JobRun(
        job_name=job,
        run_id=f"jr_{zlib.crc32(f'{job}-{n}'.encode()):010d}{n:02d}",
        state=state,
        started_on=NOW - timedelta(hours=hours_ago),
        execution_time_s=exec_s,
        error_message=error,
        worker_type="G.1X",
        number_of_workers=workers,
    )


class DemoGlueProvider:
    label = "demo (no AWS calls)"

    def __init__(self) -> None:
        err = "AnalysisException: [PATH_NOT_FOUND] Path does not exist: s3://acme-lake/raw/orders/dt=2026-10-16."
        self._runs = {
            "orders_daily": [
                _run("orders_daily", 3, "FAILED", 0.3, 176, error=err),
                _run("orders_daily", 2, "SUCCEEDED", 24.3, 512),
                _run("orders_daily", 1, "SUCCEEDED", 48.3, 498),
            ],
            "customers_scd2": [
                _run("customers_scd2", 2, "SUCCEEDED", 2, 1320, workers=10),
                _run("customers_scd2", 1, "SUCCEEDED", 26, 1290, workers=10),
            ],
            "clickstream_compaction": [
                _run("clickstream_compaction", 2, "RUNNING", 0.1, 340, workers=20),
                _run(
                    "clickstream_compaction",
                    1,
                    "TIMEOUT",
                    6,
                    2880,
                    workers=20,
                    error="Job run timed out after 48 minutes.",
                ),
            ],
            "features_churn_model": [
                _run("features_churn_model", 1, "SUCCEEDED", 5, 760, workers=4),
            ],
            "legacy_export_csv": [],
        }

    def list_jobs(self) -> list[GlueJob]:
        jobs = []
        for name, runs in self._runs.items():
            jobs.append(
                GlueJob(
                    name=name,
                    glue_version="5.0",
                    worker_type="G.1X",
                    number_of_workers=5,
                    last_run=runs[0] if runs else None,
                )
            )
        return sorted(jobs, key=lambda j: j.name)

    def list_runs(self, job_name: str, limit: int = 20) -> list[JobRun]:
        return self._runs.get(job_name, [])[:limit]

    def get_logs(self, run: JobRun, errors_only: bool = True) -> list[str]:
        if run.state in ("FAILED", "TIMEOUT"):
            return FAKE_SPARK_LOG.splitlines()
        return [
            "26/10/17 08:41:02 INFO GlueContext: GlueContext initialized",
            "26/10/17 08:49:44 INFO SparkContext: Successfully stopped SparkContext",
        ]
