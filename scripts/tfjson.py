"""Helpers to read `terraform show -json` output (plan or state)."""
import json


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def resources(doc):
    """Yield every managed resource of a plan (planned_values) or state (values) document."""
    root = (doc.get("planned_values") or doc.get("values") or {}).get("root_module", {})
    stack = [root]
    while stack:
        module = stack.pop()
        stack.extend(module.get("child_modules", []))
        for res in module.get("resources", []):
            if res.get("mode") == "managed":
                yield res


def route_table_refs(doc):
    """Map each aws_route in the plan configuration to the route table it points at.

    Returns {"<module path>aws_route.<name>": "<module path>aws_route_table.<name>"}. Needed
    because on a first plan the route_table_id value is still unknown, only the reference exists.
    """
    refs = {}
    stack = [("", doc.get("configuration", {}).get("root_module", {}))]
    while stack:
        prefix, module = stack.pop()
        for name, call in module.get("module_calls", {}).items():
            stack.append((f"{prefix}module.{name}.", call.get("module", {})))
        for res in module.get("resources", []):
            if res["type"] != "aws_route":
                continue
            for ref in res.get("expressions", {}).get("route_table_id", {}).get("references", []):
                if ref.count(".") == 1 and ref.startswith("aws_route_table."):
                    refs[prefix + res["address"]] = prefix + ref
    return refs
