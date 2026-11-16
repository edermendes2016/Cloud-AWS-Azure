"""Unit tests for the plan gates. They run on hand-written plan documents: no emulator needed."""
import cost_estimate
import plan_policy

TAGS = {"Project": "p", "Env": "e", "Owner": "o", "CostCenter": "c", "ManagedBy": "terraform"}


def plan(resources, route_refs=None):
    config = [
        {"address": route, "type": "aws_route", "expressions": {"route_table_id": {"references": [table + ".id", table]}}}
        for route, table in (route_refs or {}).items()
    ]
    return {
        "planned_values": {"root_module": {"resources": [dict(mode="managed", **r) for r in resources]}},
        "configuration": {"root_module": {"resources": config}},
    }


def table(name, tier):
    return {"address": f"aws_route_table.{name}", "type": "aws_route_table", "values": {"tags": {"Tier": tier}, "tags_all": TAGS}}


def default_route(name):
    return {"address": f"aws_route.{name}", "type": "aws_route", "values": {"destination_cidr_block": "0.0.0.0/0"}}


def test_app_tier_without_default_route_fails():
    failures = plan_policy.check_routes(plan([table("app", "app")]))
    assert failures and "no default route" in failures[0][1]


def test_app_tier_with_default_route_passes():
    doc = plan([table("app", "app"), default_route("app_default")], {"aws_route.app_default": "aws_route_table.app"})
    assert plan_policy.check_routes(doc) == []


def test_data_tier_must_stay_isolated():
    doc = plan([table("data", "data"), default_route("leak")], {"aws_route.leak": "aws_route_table.data"})
    assert "isolated" in plan_policy.check_routes(doc)[0][1]


def test_missing_tags_are_reported():
    res = {"address": "aws_vpc.x", "type": "aws_vpc", "values": {"tags_all": {"Project": "p"}}}
    assert "CostCenter" in plan_policy.check_tags(plan([res]))[0][1]


def test_multi_az_doubles_the_database_price():
    def db(multi_az):
        values = {"instance_class": "db.t3.micro", "multi_az": multi_az, "allocated_storage": 20}
        return plan([{"address": "aws_db_instance.x", "type": "aws_db_instance", "values": values}])

    single = cost_estimate.estimate(db(False))["total"]
    assert cost_estimate.estimate(db(True))["total"] == round(single * 2, 2)


def test_unknown_instance_class_is_flagged_not_priced_as_zero():
    values = {"instance_class": "db.unknown", "multi_az": False, "allocated_storage": 20}
    doc = plan([{"address": "aws_db_instance.x", "type": "aws_db_instance", "values": values}])
    assert cost_estimate.estimate(doc)["items"][0]["monthly"] is None
