"""Plan gate: route and tag rules evaluated on `terraform show -json` output.

Usage: plan_policy.py plan.json   (exit 1 when any rule fails)
"""
import sys

from tfjson import load, resources, route_table_refs

REQUIRED_TAGS = ["Project", "Env", "Owner", "CostCenter", "ManagedBy"]
# Tier tag of a route table -> must it have a default route (0.0.0.0/0)?
DEFAULT_ROUTE_BY_TIER = {"public": True, "app": True, "data": False}


def check_routes(doc):
    refs = route_table_refs(doc)
    with_default = set()  # route table addresses that get a 0.0.0.0/0 route
    for res in resources(doc):
        if res["type"] == "aws_route" and res["values"].get("destination_cidr_block") == "0.0.0.0/0":
            base = res["address"].split("[")[0]
            if base in refs:
                with_default.add(res["address"].replace(base, refs[base], 1))

    failures = []
    for res in resources(doc):
        if res["type"] != "aws_route_table":
            continue
        tier = (res["values"].get("tags") or {}).get("Tier")
        if tier not in DEFAULT_ROUTE_BY_TIER:
            failures.append((res["address"], "route table has no valid Tier tag (public, app or data)"))
            continue
        has_default = res["address"] in with_default
        if DEFAULT_ROUTE_BY_TIER[tier] and not has_default:
            failures.append((res["address"], f"{tier} tier has no default route (0.0.0.0/0): no outbound traffic"))
        if not DEFAULT_ROUTE_BY_TIER[tier] and has_default:
            failures.append((res["address"], f"{tier} tier must stay isolated but has a default route"))
    return failures


def check_tags(doc):
    failures = []
    for res in resources(doc):
        values = res["values"]
        if "tags_all" not in values:
            continue  # resource type does not support tags
        missing = [t for t in REQUIRED_TAGS if not (values.get("tags_all") or {}).get(t)]
        if missing:
            failures.append((res["address"], "missing tags: " + ", ".join(missing)))
    return failures


def main(path):
    doc = load(path)
    failed = False
    for rule, check in (("routes", check_routes), ("tags", check_tags)):
        failures = check(doc)
        failed = failed or bool(failures)
        print(f"[{'FAIL' if failures else 'PASS'}] {rule}")
        for address, message in failures:
            print(f"  - {address}: {message}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
