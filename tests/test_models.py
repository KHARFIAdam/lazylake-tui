from lazylake.models import JobRun


def test_cost_from_workers(monkeypatch):
    monkeypatch.setenv("LAZYLAKE_GLUE_DPU_HOUR_PRICE", "0.44")
    run = JobRun("j", "r", "SUCCEEDED", execution_time_s=3600, worker_type="G.2X", number_of_workers=5)
    assert run.dpu_hours == 10  # 5 workers × 2 DPU × 1 h
    assert run.estimated_cost_usd == 4.4


def test_cost_prefers_dpu_seconds():
    run = JobRun(
        "j",
        "r",
        "SUCCEEDED",
        execution_time_s=3600,
        worker_type="G.2X",
        number_of_workers=5,
        dpu_seconds=1800,
    )
    assert run.dpu_hours == 0.5


def test_no_cost_when_unknown():
    assert JobRun("j", "r", "RUNNING").estimated_cost_usd is None
