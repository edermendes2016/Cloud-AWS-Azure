"""Offline monthly cost estimate from `terraform show -json` output (plan or state).

Usage: cost_estimate.py plan.json [--budget USD]   (exit 1 when the total is over budget)
Prices come from finops/prices.json: a labelled reference snapshot, not a quote.
"""
import argparse
import json
import pathlib
import sys

from tfjson import load, resources

PRICES = json.loads((pathlib.Path(__file__).parent.parent / "finops" / "prices.json").read_text())
HOURS = PRICES["hours_per_month"]


def price(res):
    """Return (monthly USD or None when unknown, detail) for one resource; None when it is free."""
    kind, v = res["type"], res["values"]
    if kind == "aws_nat_gateway":
        return PRICES["nat_gateway_hour"] * HOURS, "NAT gateway, per hour (data processing not included)"
    if kind == "aws_eip":
        return PRICES["public_ipv4_hour"] * HOURS, "public IPv4 address"
    if kind == "aws_db_instance":
        hourly = PRICES["rds_postgres_hour"].get(v.get("instance_class"))
        factor = 2 if v.get("multi_az") else 1
        storage = (v.get("allocated_storage") or 0) * PRICES["rds_gp3_gb_month"] * factor
        detail = f"{v.get('instance_class')}, {'Multi-AZ' if factor == 2 else 'Single-AZ'}, {v.get('allocated_storage')} GB gp3"
        if hourly is None:
            return None, detail + " (class not in the price table)"
        return hourly * HOURS * factor + storage, detail
    if kind == "aws_cloudwatch_metric_alarm":
        return PRICES["cloudwatch_alarm_month"], "standard alarm"
    if kind == "aws_cloudwatch_dashboard":
        return PRICES["cloudwatch_dashboard_month"], "custom dashboard"
    return None


def estimate(doc):
    items = []
    for res in resources(doc):
        priced = price(res)
        if priced:
            items.append({"address": res["address"], "type": res["type"], "monthly": priced[0], "detail": priced[1]})
    items.sort(key=lambda i: -(i["monthly"] or 0))
    return {"items": items, "total": round(sum(i["monthly"] or 0 for i in items), 2), "note": PRICES["_note"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--budget", type=float)
    args = parser.parse_args()

    result = estimate(load(args.path))
    for item in result["items"]:
        amount = "   unknown" if item["monthly"] is None else f"{item['monthly']:10.2f}"
        print(f"{amount}  {item['address']}  ({item['detail']})")
    print(f"{result['total']:10.2f}  TOTAL USD/month (reference list prices, see finops/prices.json)")
    if args.budget is not None:
        over = result["total"] > args.budget
        print(f"[{'FAIL' if over else 'PASS'}] budget {args.budget:.2f} USD/month" + (": estimate is over budget" if over else ""))
        return 1 if over else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
