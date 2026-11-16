"""Lab API. Runs the same `make` targets as CI, records every stage and serves the web UI."""
import os
import pathlib
import re
import subprocess
import sys
import threading
import time
import uuid

import boto3
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import cost_estimate  # noqa: E402
import orphan_check  # noqa: E402
import plan_policy  # noqa: E402
import tfjson  # noqa: E402
from scenarios import MAKE, SCENARIOS, WORK  # noqa: E402

GATES = ["fmt", "validate", "lint", "secrets", "plan", "scan", "policy", "cost"]
BUDGET = float(os.environ.get("BUDGET", "100"))

app = FastAPI(title="multicloud-iac-lab")
jobs: dict[str, dict] = {}
approvals: dict[str, dict] = {}
injected: set[str] = set()
runner = threading.Lock()  # one job at a time: they all share one Terraform state
state_cache: dict = {}


class PipelineRequest(BaseModel):
    apply: bool = True


class Approval(BaseModel):
    approve: bool


def run_step(stage, action):
    """Run a command (list), a callable returning a command, or a python function(log)."""
    lines = []

    def log(text):
        lines.append(text)
        stage["log"] = "\n".join(lines)[-60000:]

    started = time.monotonic()
    stage["status"] = "running"
    try:
        if callable(action) and action.__name__.endswith("_cmd"):
            action = action()
        if callable(action):
            action(log)
            code = 0
        else:
            log("$ " + " ".join(action))
            proc = subprocess.Popen(action, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            for line in proc.stdout:
                log(line.rstrip())
            code = proc.wait()
    except Exception as exc:  # shown in the UI instead of killing the worker thread
        log(f"ERROR: {exc}")
        code = 1
    stage["seconds"] = round(time.monotonic() - started, 1)
    stage["status"] = "passed" if code == 0 else "failed"
    return code == 0


def start_job(kind, steps, scenario=None, expect_failure=None):
    """steps: list of (name, action). Returns the public job record; work happens in a thread."""
    if not runner.acquire(blocking=False):
        raise HTTPException(409, "another job is running")
    job = {
        "id": uuid.uuid4().hex[:8], "kind": kind, "scenario": scenario, "status": "running",
        "started": time.time(), "seconds": None,
        "stages": [{"name": name, "status": "pending", "seconds": None, "log": ""} for name, _ in steps],
    }
    jobs[job["id"]] = job

    def work():
        started = time.monotonic()
        try:
            for stage, (_, action) in zip(job["stages"], steps):
                if action == "approval":
                    gate = approvals[job["id"]] = {"event": threading.Event(), "approve": False}
                    stage["status"] = job["status"] = "waiting"
                    gate["event"].wait()
                    stage["status"] = "passed" if gate["approve"] else "failed"
                    stage["log"] = "approved" if gate["approve"] else "rejected: nothing was applied"
                    job["status"] = "running"
                    if not gate["approve"]:
                        job["status"] = "rejected"
                        break
                elif not run_step(stage, action):
                    job["status"] = "failed"
                    break
            if job["status"] == "running":
                job["status"] = "passed"
            if expect_failure:
                # An injected fault is "detected" only when the expected control stopped it.
                last = next((s for s in reversed(job["stages"]) if s["status"] != "pending"), None)
                caught = job["status"] == "failed" and re.search(expect_failure, last["log"])
                job["status"] = "detected" if caught else "missed"
                job["control"] = last["name"]
        finally:
            for stage in job["stages"]:
                if stage["status"] == "pending":
                    stage["status"] = "skipped"
            job["seconds"] = round(time.monotonic() - started, 1)
            state_cache.clear()
            runner.release()

    threading.Thread(target=work, daemon=True).start()
    return job


def make(target):
    return (target, MAKE + [target])


def state():
    """Current Terraform state as JSON (cached until the next job finishes)."""
    if "doc" not in state_cache:
        out = subprocess.run(
            ["terraform", f"-chdir={ROOT / 'envs/local'}", "show", "-json"], capture_output=True, text=True
        )
        state_cache["doc"] = tfjson.json.loads(out.stdout) if out.returncode == 0 and out.stdout.strip() else {}
    return state_cache["doc"]


@app.on_event("startup")
def setup():
    start_job("setup", [make("init")])


@app.get("/api/status")
def status():
    setup_job = next((j for j in jobs.values() if j["kind"] == "setup"), None)
    return {
        "ready": bool(setup_job and setup_job["status"] == "passed"),
        "setup": setup_job,
        "busy": runner.locked(),
        "applied": sum(1 for _ in tfjson.resources(state())) if not runner.locked() else None,
        "emulator": os.environ.get("AWS_ENDPOINT_URL", ""),
        "budget": BUDGET,
    }


@app.post("/api/pipeline")
def pipeline(req: PipelineRequest | None = None):
    steps = [make(t) for t in GATES]
    if req is None or req.apply:
        steps += [("approval", "approval"), make("apply")]
    return start_job("pipeline", steps)


@app.post("/api/destroy")
def destroy():
    return start_job("destroy", [make("destroy"), make("orphan-check")])


@app.get("/api/jobs")
def list_jobs():
    return [{k: v for k, v in j.items() if k != "stages"} | {
        "stages": [{k: v for k, v in s.items() if k != "log"} for s in j["stages"]]
    } for j in jobs.values()]


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "unknown job")
    return jobs[job_id]


@app.post("/api/jobs/{job_id}/approval")
def approve(job_id: str, body: Approval):
    gate = approvals.get(job_id)
    if not gate or gate["event"].is_set():
        raise HTTPException(409, "job is not waiting for approval")
    gate["approve"] = body.approve
    gate["event"].set()
    return {"ok": True}


@app.get("/api/scenarios")
def list_scenarios():
    return [
        {"id": sid, "kind": s["kind"], "control": s["control"], "highlight": s["highlight"], "injected": sid in injected}
        for sid, s in SCENARIOS.items()
    ]


def scenario_or_404(sid):
    if sid not in SCENARIOS:
        raise HTTPException(404, "unknown scenario")
    return SCENARIOS[sid]


@app.post("/api/scenarios/{sid}/inject")
def inject(sid: str):
    scenario = scenario_or_404(sid)
    steps = ([("inject", scenario["inject"])] if "inject" in scenario else []) + scenario["detect"]
    job = start_job("inject", steps, scenario=sid, expect_failure=scenario["expect"])
    injected.add(sid)
    return job


@app.post("/api/scenarios/{sid}/fix")
def fix(sid: str):
    scenario = scenario_or_404(sid)
    job = start_job("fix", scenario.get("fix", []) + scenario["verify"], scenario=sid)
    injected.discard(sid)
    return job


@app.get("/api/network")
def network():
    """Topology read from the Terraform state, plus the live security group rules."""
    res = list(tfjson.resources(state()))
    if not res:
        return {"applied": False, "highlights": [SCENARIOS[s]["highlight"] for s in injected]}

    def of(kind):
        return [r["values"] for r in res if r["type"] == kind]

    default_target = {}
    for route in of("aws_route"):
        if route.get("destination_cidr_block") == "0.0.0.0/0":
            default_target[route["route_table_id"]] = "nat" if route.get("nat_gateway_id") else "igw"

    sg = next((g for g in of("aws_security_group")), None)
    live_rules = []
    if sg:
        try:
            groups = boto3.client("ec2").describe_security_groups(GroupIds=[sg["id"]])["SecurityGroups"]
            live_rules = [
                {"cidr": r["CidrIp"], "port": p.get("FromPort")}
                for p in groups[0]["IpPermissions"] for r in p.get("IpRanges", [])
            ]
        except Exception:
            live_rules = []
    db = next(iter(of("aws_db_instance")), None)
    return {
        "applied": True,
        "vpc": {"cidr": of("aws_vpc")[0]["cidr_block"], "name": of("aws_vpc")[0]["tags"]["Name"]},
        "subnets": sorted(
            ({"name": s["tags"]["Name"], "tier": s["tags"]["Tier"], "az": s["availability_zone"], "cidr": s["cidr_block"]}
             for s in of("aws_subnet")), key=lambda s: (s["az"], s["tier"])),
        "route_tables": [
            {"name": t["tags"]["Name"], "tier": t["tags"]["Tier"], "default_route": default_target.get(t["id"])}
            for t in of("aws_route_table")
        ],
        "nat_gateways": len(of("aws_nat_gateway")),
        "db": db and {
            "id": db["identifier"], "class": db["instance_class"], "multi_az": db["multi_az"],
            "public": db["publicly_accessible"], "encrypted": db["storage_encrypted"],
        },
        "db_rules": {
            "code": [{"cidr": c, "port": i["from_port"]} for i in (sg or {}).get("ingress", []) for c in i["cidr_blocks"]],
            "live": live_rules,
        },
        "alarms": [a["alarm_name"] for a in of("aws_cloudwatch_metric_alarm")],
        "highlights": [SCENARIOS[s]["highlight"] for s in injected],
    }


@app.get("/api/finops")
def finops():
    doc = state()
    try:
        orphans = orphan_check.find_orphans(doc)
    except Exception:
        orphans = []
    return {
        "budget": BUDGET,
        "cost": cost_estimate.estimate(doc),
        "untagged": [{"address": a, "message": m} for a, m in plan_policy.check_tags(doc)],
        "required_tags": plan_policy.REQUIRED_TAGS,
        "orphans": orphans,
    }


app.mount("/", StaticFiles(directory=ROOT / "app/web", html=True), name="web")
