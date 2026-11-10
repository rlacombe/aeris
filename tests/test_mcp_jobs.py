from concurrent.futures import Future

from aeris.mcp.server import _ExposureJob, _ExposureJobs


def test_exposure_job_reports_running_completed_and_unknown():
    jobs = _ExposureJobs()
    future = Future()
    jobs._jobs["job"] = _ExposureJob(future=future)

    assert jobs.status("job") == {"status": "running", "job_id": "job"}
    future.set_result({"status": "completed", "n_completed": 3})
    assert jobs.status("job") == {
        "status": "completed",
        "job_id": "job",
        "result": {"status": "completed", "n_completed": 3},
    }
    assert jobs.status("missing")["status"] == "error"


def test_exposure_job_reports_worker_failure():
    jobs = _ExposureJobs()
    future = Future()
    jobs._jobs["job"] = _ExposureJob(future=future)
    future.set_exception(RuntimeError("upstream failed"))

    result = jobs.status("job")

    assert result["status"] == "failed"
    assert result["error"] == "upstream failed"
