from pathlib import Path
import yaml


def load_scenarios(path):
    spec = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(spec, dict) or spec.get("schema_version") != 1:
        raise ValueError("Invalid scenario schema")
    scenarios = spec.get("scenarios", [])
    if not scenarios or len({x["id"] for x in scenarios}) != len(scenarios):
        raise ValueError("Empty or duplicate scenarios")
    known = {"query_classrooms", "query_courses", "recommend_dishes", "query_secondhand", "search_knowledge"}
    for x in scenarios:
        if type(x.get("weight")) is not int or x["weight"] < 1:
            raise ValueError("Invalid scenario weight")
        if not isinstance(x.get("message"), str) or not 1 <= len(x["message"]) <= 2000:
            raise ValueError("Invalid scenario message")
        if not x.get("expected_tools") or set(x["expected_tools"]) - known:
            raise ValueError("Invalid expected tools")
        if any(type(n) is not int or n < 0 for n in x.get("minimum_rows", {}).values()):
            raise ValueError("Invalid minimum row count")
        if set(x.get("minimum_rows", {})) - set(x["expected_tools"]):
            raise ValueError("Invalid row expectations")
    return scenarios


