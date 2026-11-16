"""End-to-end tests against the running lab API (skipped when the lab is not up).

Order matters: apply the baseline, break it in seven ways, then prove the destroy is clean.
"""
import os
import time

import httpx
import pytest

API = httpx.Client(base_url=os.environ.get("LAB_URL", "http://localhost:8080"), timeout=30)

try:
    API.get("/api/status")
except httpx.HTTPError:
    pytestmark = pytest.mark.skip(reason="lab API is not running (make up)")


def run(path, approve=True, **body):
    """Start a job and wait for it; answers the approval gate on the way."""
    job = API.post(path, json=body or None).raise_for_status().json()
    deadline = time.time() + 900
    while time.time() < deadline:
        job = API.get(f"/api/jobs/{job['id']}").json()
        if job["status"] == "waiting":
            API.post(f"/api/jobs/{job['id']}/approval", json={"approve": approve})
        elif job["status"] != "running":
            return job
        time.sleep(1)
    raise TimeoutError(path)


def log_of(job):
    return "\n".join(f"--- {s['name']}: {s['status']}\n{s['log'][-3000:]}" for s in job["stages"])


def test_setup_finished():
    deadline = time.time() + 180
    while not API.get("/api/status").json()["ready"]:
        assert time.time() < deadline, "setup did not finish"
        time.sleep(2)


def test_rejected_approval_applies_nothing():
    job = run("/api/pipeline", approve=False)
    assert job["status"] == "rejected", log_of(job)
    assert job["stages"][-1]["status"] == "skipped"


def test_pipeline_applies_baseline():
    job = run("/api/pipeline")
    assert job["status"] == "passed", log_of(job)
    network = API.get("/api/network").json()
    assert network["applied"] and len(network["subnets"]) == 6
    assert network["db"]["public"] is False and network["db"]["encrypted"] is True


def test_baseline_is_tagged_and_within_budget():
    finops = API.get("/api/finops").json()
    assert finops["untagged"] == [] and finops["orphans"] == []
    assert 0 < finops["cost"]["total"] <= finops["budget"]


SCENARIOS = [s["id"] for s in API.get("/api/scenarios").json()] if "pytestmark" not in globals() else []


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_scenario_is_detected_then_fixed(scenario):
    expected_control = next(s["control"] for s in API.get("/api/scenarios").json() if s["id"] == scenario)
    job = run(f"/api/scenarios/{scenario}/inject")
    assert job["status"] == "detected", log_of(job)
    assert job["control"] == expected_control
    job = run(f"/api/scenarios/{scenario}/fix")
    assert job["status"] == "passed", log_of(job)


def test_destroy_leaves_nothing_behind():
    job = run("/api/destroy")
    assert job["status"] == "passed", log_of(job)
    assert API.get("/api/network").json()["applied"] is False
