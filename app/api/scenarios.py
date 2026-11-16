"""Failure scenarios: how each fault is injected, which control must catch it, how it is fixed.

Plan-time scenarios only change input variables (scenarios/<id>/broken.tfvars) and are stopped
by a gate before anything is applied. Runtime scenarios change the emulator behind Terraform's
back, the way a person with console access would.
"""
import datetime
import json
import os
import pathlib
import random
import string
import uuid

import boto3

ROOT = pathlib.Path(__file__).resolve().parents[2]
WORK = pathlib.Path(os.environ.get("LAB_WORK", "/tmp/lab"))
LEAK_DIR = WORK / "leak"
STATE_BUCKET = os.environ.get("STATE_BUCKET", "iac-lab-tfstate")
LOCK_TABLE = os.environ.get("LOCK_TABLE", "iac-lab-tflock")
STATE_KEY = "envs/local/terraform.tfstate"
MAKE = ["make", "--no-print-directory"]


def _lab_vpc(ec2):
    vpcs = ec2.describe_vpcs(Filters=[{"Name": "tag:Project", "Values": ["iac-lab"]}])["Vpcs"]
    if not vpcs:
        raise RuntimeError("baseline is not applied: run the pipeline first")
    return vpcs[0]["VpcId"]


# --- state lock -------------------------------------------------------------------------------
def inject_lock(log):
    lock_id = str(uuid.uuid4())
    info = {
        "ID": lock_id,
        "Operation": "OperationTypeApply",
        "Who": "ci-runner@cancelled-job",
        "Created": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "Path": f"{STATE_BUCKET}/{STATE_KEY}",
    }
    boto3.client("dynamodb").put_item(
        TableName=LOCK_TABLE,
        Item={"LockID": {"S": f"{STATE_BUCKET}/{STATE_KEY}"}, "Info": {"S": json.dumps(info)}},
    )
    log(f"Simulated a pipeline job killed mid-apply: its lock {lock_id} was never released.")


def fix_lock_cmd():
    item = boto3.client("dynamodb").get_item(
        TableName=LOCK_TABLE, Key={"LockID": {"S": f"{STATE_BUCKET}/{STATE_KEY}"}}
    ).get("Item")
    lock_id = json.loads(item["Info"]["S"])["ID"] if item else "none"
    return MAKE + ["unlock", f"ID={lock_id}"]


# --- drift ------------------------------------------------------------------------------------
def inject_drift(log):
    ec2 = boto3.client("ec2")
    groups = ec2.describe_security_groups(
        Filters=[{"Name": "vpc-id", "Values": [_lab_vpc(ec2)]}, {"Name": "group-name", "Values": ["*-db"]}]
    )["SecurityGroups"]
    ec2.authorize_security_group_ingress(
        GroupId=groups[0]["GroupId"],
        IpPermissions=[{
            "IpProtocol": "tcp", "FromPort": 5432, "ToPort": 5432,
            "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "temp debug access"}],
        }],
    )
    log(f"Added an ingress rule 0.0.0.0/0:5432 to {groups[0]['GroupId']} directly through the API (not in code).")


# --- dirty destroy ----------------------------------------------------------------------------
def inject_orphans(log):
    ec2 = boto3.client("ec2")
    vpc_id = _lab_vpc(ec2)
    subnet = ec2.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])["Subnets"][0]
    sg = ec2.create_security_group(GroupName="manual-debug", Description="created by hand", VpcId=vpc_id)
    eni = ec2.create_network_interface(SubnetId=subnet["SubnetId"], Groups=[sg["GroupId"]])
    log(f"Created by hand, outside Terraform: {sg['GroupId']} and {eni['NetworkInterface']['NetworkInterfaceId']}.")
    log("On AWS these block `terraform destroy` with DependencyViolation when the VPC is deleted.")


def fix_orphans(log):
    ec2 = boto3.client("ec2")
    groups = ec2.describe_security_groups(Filters=[{"Name": "group-name", "Values": ["manual-debug"]}])
    for group in groups["SecurityGroups"]:
        enis = ec2.describe_network_interfaces(Filters=[{"Name": "group-id", "Values": [group["GroupId"]]}])
        for eni in enis["NetworkInterfaces"]:
            ec2.delete_network_interface(NetworkInterfaceId=eni["NetworkInterfaceId"])
            log(f"Deleted {eni['NetworkInterfaceId']}")
        ec2.delete_security_group(GroupId=group["GroupId"])
        log(f"Deleted {group['GroupId']}")


# --- secret leak ------------------------------------------------------------------------------
def inject_leak(log):
    # The fake key is generated at runtime so the repository itself never contains one.
    key = "AKIA" + "".join(random.choices(string.ascii_uppercase + "234567", k=16))
    secret = "".join(random.choices(string.ascii_letters + string.digits, k=40))
    LEAK_DIR.mkdir(parents=True, exist_ok=True)
    (LEAK_DIR / "deploy.env").write_text(f"AWS_ACCESS_KEY_ID={key}\nAWS_SECRET_ACCESS_KEY={secret}\n")
    log("Wrote deploy.env with a (fake, random) AWS access key, as if someone were about to commit it.")


def fix_leak(log):
    (LEAK_DIR / "deploy.env").write_text("# Credentials come from the CI OIDC role, never from a file.\n")
    log("Removed the key from deploy.env. In real life: also revoke the key, it must be considered exposed.")


GITLEAKS = ["gitleaks", "dir", str(LEAK_DIR), "--no-banner", "--redact"]


def _plan(scenario_id):
    return MAKE + ["plan", f"VARS=scenarios/{scenario_id}/broken.tfvars"]


# control: pipeline stage that must stop the fault. expect: text proving it was that control.
# highlight: node of the network map that the UI marks while the fault is active.
SCENARIOS = {
    "missing-route": {
        "kind": "plan", "control": "policy", "highlight": "rt-app",
        "expect": r"no default route",
        "detect": [("plan", _plan("missing-route")), ("policy", MAKE + ["policy"])],
        "verify": [("plan", MAKE + ["plan"]), ("policy", MAKE + ["policy"])],
    },
    "open-security-group": {
        "kind": "plan", "control": "scan", "highlight": "sg-db",
        "expect": r"CKV2_LAB_1",
        "detect": [("plan", _plan("open-security-group")), ("scan", MAKE + ["scan"])],
        "verify": [("plan", MAKE + ["plan"]), ("scan", MAKE + ["scan"])],
    },
    "costly-resource": {
        "kind": "plan", "control": "cost", "highlight": "rds",
        "expect": r"over budget",
        "detect": [("plan", _plan("costly-resource")), ("cost", MAKE + ["cost"])],
        "verify": [("plan", MAKE + ["plan"]), ("cost", MAKE + ["cost"])],
    },
    "state-lock": {
        "kind": "runtime", "control": "plan", "highlight": "state",
        "expect": r"Error acquiring the state lock",
        "inject": inject_lock,
        "detect": [("plan", MAKE + ["plan"])],
        "fix": [("unlock", fix_lock_cmd)],
        "verify": [("plan", MAKE + ["plan"])],
    },
    "drift": {
        "kind": "runtime", "control": "drift", "highlight": "sg-db",
        "expect": r"DRIFT DETECTED",
        "inject": inject_drift,
        "detect": [("drift", MAKE + ["drift"])],
        "fix": [("plan", MAKE + ["plan"]), ("apply", MAKE + ["apply"])],
        "verify": [("drift", MAKE + ["drift"])],
    },
    "dirty-destroy": {
        "kind": "runtime", "control": "orphan-check", "highlight": "orphan",
        "expect": r"ORPHAN",
        "inject": inject_orphans,
        "detect": [("orphan-check", MAKE + ["orphan-check"])],
        "fix": [("cleanup", fix_orphans)],
        "verify": [("orphan-check", MAKE + ["orphan-check"])],
    },
    "secret-leak": {
        "kind": "repo", "control": "secrets", "highlight": "repo",
        "expect": r"leaks found",
        "inject": inject_leak,
        "detect": [("secrets", GITLEAKS)],
        "fix": [("cleanup", fix_leak)],
        "verify": [("secrets", GITLEAKS)],
    },
}
