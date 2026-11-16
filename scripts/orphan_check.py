"""List resources that exist in the account but are not in the Terraform state.

Usage: orphan_check.py state.json   (exit 1 when orphans are found)
After a clean destroy the state is empty, so anything listed here was left behind.
"""
import os
import sys

import boto3

from tfjson import load, resources

BACKEND = {os.environ.get("STATE_BUCKET", "iac-lab-tfstate"), os.environ.get("LOCK_TABLE", "iac-lab-tflock")}


def state_ids(doc):
    ids = set()
    for res in resources(doc):
        for key in ("id", "arn", "name", "identifier", "allocation_id", "dashboard_name", "alarm_name"):
            value = res["values"].get(key)
            if isinstance(value, str):
                ids.add(value)
    return ids


def live_resources():
    """Yield (type, id, tags) for everything the lab could have created."""
    ec2 = boto3.client("ec2")
    default_vpcs = {v["VpcId"] for v in ec2.describe_vpcs()["Vpcs"] if v.get("IsDefault")}

    def in_lab(item):
        return item.get("VpcId") not in default_vpcs

    def tags(item):
        return {t["Key"]: t["Value"] for t in item.get("Tags", [])}

    for v in filter(in_lab, ec2.describe_vpcs()["Vpcs"]):
        yield "vpc", v["VpcId"], tags(v)
    for s in filter(in_lab, ec2.describe_subnets()["Subnets"]):
        yield "subnet", s["SubnetId"], tags(s)
    for g in filter(in_lab, ec2.describe_security_groups()["SecurityGroups"]):
        yield "security-group", g["GroupId"], tags(g)
    for r in filter(in_lab, ec2.describe_route_tables()["RouteTables"]):
        if not any(a.get("Main") for a in r.get("Associations", [])):  # main table is created by AWS
            yield "route-table", r["RouteTableId"], tags(r)
    nat_enis = set()  # interfaces that belong to a NAT gateway are not orphans
    for n in ec2.describe_nat_gateways()["NatGateways"]:
        if n["State"] not in ("deleted", "deleting") and in_lab(n):
            nat_enis.update(a.get("NetworkInterfaceId") for a in n.get("NatGatewayAddresses", []))
            yield "nat-gateway", n["NatGatewayId"], tags(n)
    for a in ec2.describe_addresses()["Addresses"]:
        yield "elastic-ip", a["AllocationId"], tags(a)
    for i in filter(in_lab, ec2.describe_network_interfaces()["NetworkInterfaces"]):
        if not i.get("RequesterManaged") and i["NetworkInterfaceId"] not in nat_enis:
            yield "network-interface", i["NetworkInterfaceId"], {t["Key"]: t["Value"] for t in i.get("TagSet", [])}
    for d in boto3.client("rds").describe_db_instances()["DBInstances"]:
        yield "db-instance", d["DBInstanceIdentifier"], {t["Key"]: t["Value"] for t in d.get("TagList", [])}
    for g in boto3.client("logs").describe_log_groups()["logGroups"]:
        yield "log-group", g["logGroupName"], None
    for a in boto3.client("cloudwatch").describe_alarms()["MetricAlarms"]:
        yield "alarm", a["AlarmName"], None
    for b in boto3.client("s3").list_buckets()["Buckets"]:
        if b["Name"] not in BACKEND:
            yield "s3-bucket", b["Name"], None
    for t in boto3.client("dynamodb").list_tables()["TableNames"]:
        if t not in BACKEND:
            yield "dynamodb-table", t, None


def find_orphans(doc):
    known = state_ids(doc)
    return [
        {"type": kind, "id": rid, "tagged": bool(tags and tags.get("ManagedBy"))}
        for kind, rid, tags in live_resources()
        if rid not in known
    ]


def main(path):
    orphans = find_orphans(load(path))
    for o in orphans:
        hint = "" if o["tagged"] else " (no ManagedBy tag: created outside Terraform)"
        print(f"ORPHAN {o['type']}: {o['id']}{hint}")
    print(f"[{'FAIL' if orphans else 'PASS'}] orphan-check: {len(orphans)} resource(s) outside the Terraform state")
    return 1 if orphans else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
