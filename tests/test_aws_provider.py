"""AWS provider tests against an in-memory fake AWS (moto): no real account needed."""

import time

import boto3
import pytest
from moto import mock_aws

from lazylake.providers.aws import ERROR_LOG_GROUP, AwsGlueProvider


@pytest.fixture
def aws(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")
    with mock_aws():
        yield


def test_lists_jobs_and_runs(aws):
    glue = boto3.client("glue", region_name="eu-west-1")
    for name in ("orders_daily", "customers_scd2"):
        glue.create_job(
            Name=name,
            Role="arn:aws:iam::123456789012:role/glue",
            Command={"Name": "glueetl", "ScriptLocation": "s3://b/s.py"},
            GlueVersion="5.0",
            WorkerType="G.1X",
            NumberOfWorkers=5,
        )
    run_id = glue.start_job_run(JobName="orders_daily")["JobRunId"]

    provider = AwsGlueProvider(region="eu-west-1")
    jobs = provider.list_jobs()

    assert [j.name for j in jobs] == ["customers_scd2", "orders_daily"]
    orders = jobs[1]
    assert orders.last_run is not None and orders.last_run.run_id == run_id
    assert jobs[0].last_run is None
    assert provider.list_runs("orders_daily")[0].run_id == run_id


def test_reads_error_logs(aws):
    logs = boto3.client("logs", region_name="eu-west-1")
    logs.create_log_group(logGroupName=ERROR_LOG_GROUP)
    logs.create_log_stream(logGroupName=ERROR_LOG_GROUP, logStreamName="jr_123")
    logs.put_log_events(
        logGroupName=ERROR_LOG_GROUP,
        logStreamName="jr_123",
        logEvents=[{"timestamp": int(time.time() * 1000), "message": "ValueError: boom"}],
    )

    from lazylake.models import JobRun

    provider = AwsGlueProvider(region="eu-west-1")
    lines = provider.get_logs(JobRun("j", "jr_123", "FAILED"))
    assert lines == ["ValueError: boom"]


def test_missing_logs_are_reported_not_raised(aws):
    from lazylake.models import JobRun

    provider = AwsGlueProvider(region="eu-west-1")
    lines = provider.get_logs(JobRun("j", "jr_nope", "FAILED"))
    assert "No logs" in lines[0]
