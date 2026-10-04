"""Scenario evaluation through actual FastAPI endpoints, not answer string mocks."""
import argparse
from contextlib import contextmanager
from time import perf_counter
from uuid import UUID
import httpx
from evaluation.common import ROOT, read_jsonl, report_base, write_report, token_from_env, percentile
from evaluation.fixtures import demo_client


def compare_subset(actual, expected):
    return isinstance(actual, dict) and all(actual.get(k) == v for k, v in expected.items())


def assertions(response, expected):
    checks = {"http_status": response.status_code == expected.get("status", 200)}
    if response.status_code != 200:
        return checks
    try:
        body = response.json()
    except ValueError:
        return {**checks, "json": False}
    for key, value in expected.items():
        if key == "tools":
            results = body.get("results", [])
            names = [x.get("tool") for x in results]
            checks["tools"] = sorted(names) == sorted(value)
        elif key == "answer_contains":
            checks[key] = all(text in body.get("answer", "") for text in value)
        elif key == "preferences":
            checks[key] = compare_subset(body, value)
        elif key == "version":
            checks[key] = body.get(key) == value
        elif key == "message_count":
            checks[key] = len(body.get("messages", [])) == value
        elif key == "chart_prices":
            try:
                checks[key] = body["options"]["series"][0]["data"] == value
            except (KeyError, IndexError, TypeError):
                checks[key] = False
        elif key == "rows":
            by_tool = {x.get("tool"): x.get("rows", []) for x in body.get("results", [])}
            for tool, rule in value.items():
                rows = by_tool.get(tool, [])
                prefix = "rows:" + tool
                checks[prefix + ":count"] = len(rows) == rule["count"]
                checks[prefix + ":required"] = set(rule.get("required_ids", [])) <= {x.get("id") for x in rows}
                checks[prefix + ":excluded"] = not (set(rule.get("excluded_ids", [])) & {x.get("id") for x in rows})
                checks[prefix + ":fields"] = all(compare_subset(x, rule.get("all", {})) for x in rows)
                if "max_price" in rule:
                    checks[prefix + ":budget"] = all(isinstance(x.get("price"), (float, int)) and x["price"] <= rule["max_price"] for x in rows)
    if "results" in body:
        for key in ("session_id", "message_id"):
            try:
                UUID(body[key]); checks[key] = True
            except (KeyError, ValueError, TypeError):
                checks[key] = False
    return checks


def request_step(client, tokens, step, context):
    identity = step.get("user", "a")
    headers = {} if identity == "anonymous" else {"Authorization": "Bearer " + tokens[identity]}
    operation = step.get("operation", "chat")
    if operation == "chat":
        payload = {"message": step["message"]}
        if step.get("reuse_session"):
            payload["session_id"] = context["session_id"]
        if step.get("date"):
            payload["date"] = step["date"]
        response = client.post("/api/chat", json=payload, headers=headers)
        if response.status_code == 200:
            context.update({k: response.json()[k] for k in ("session_id", "message_id")})
        return response
    if operation == "history":
        return client.get("/api/sessions/" + context["session_id"] + "/messages", headers=headers)
    if operation == "preferences":
        return client.get("/api/preferences", headers=headers)
    if operation == "chart":
        return client.post("/api/charts", json={"message_id": context["message_id"]}, headers=headers)
    if operation == "tts":
        return client.post("/api/voice/synthesize", json={"message_id": context["message_id"]}, headers=headers)
    raise ValueError("Unknown scenario operation")


@contextmanager
def case_client(mode, base_url, timeout):
    if mode == "demo":
        with demo_client() as (client, settings):
            by_user = {user: token for token, user in settings.user_tokens.items()}
            yield client, {"a": by_user["eval-a"], "b": by_user["eval-b"]}
    else:
        tokens = {"a": token_from_env("EVAL_TOKEN_A"), "b": token_from_env("EVAL_TOKEN_B")}
        if tokens["a"] == tokens["b"]:
            raise ValueError("Two different identities required")
        with httpx.Client(base_url=base_url, timeout=timeout, trust_env=False) as client:
            # Remote fixture is shared: normalize A's prefs before each independent case.
            reset = client.post("/api/chat", json={"message": "我能吃辣，不再吃素，预算100元"},
                                headers={"Authorization": "Bearer " + tokens["a"]})
            if reset.status_code != 200:
                raise ValueError("Remote fixture preference reset failed")
            yield client, tokens


def run(dataset, mode="demo", base_url="http://127.0.0.1:8010", timeout=300):
    scenarios = read_jsonl(dataset, ("steps",))
    valid_checks = {"status", "tools", "answer_contains", "preferences", "version", "message_count", "chart_prices", "rows"}
    for scenario in scenarios:
        if not isinstance(scenario["steps"], list) or not scenario["steps"]:
            raise ValueError("Scenario has no steps")
        for step in scenario["steps"]:
            if not isinstance(step.get("expect"), dict) or not step["expect"] or set(step["expect"]) - valid_checks:
                raise ValueError("Missing or unknown expectation")
            if step.get("user", "a") not in ("a", "b", "anonymous"):
                raise ValueError("Unknown identity")
    results, latencies, observed_modes = [], [], set()
    for scenario in scenarios:
        context, steps = {}, []
        try:
            with case_client(mode, base_url, timeout) as (client, tokens):
                for index, step in enumerate(scenario["steps"], 1):
                    start = perf_counter()
                    try:
                        response = request_step(client, tokens, step, context)
                        elapsed = (perf_counter() - start) * 1000
                        latencies.append(elapsed)
                        checks = assertions(response, step["expect"])
                        if response.status_code == 200 and step.get("operation", "chat") == "chat":
                            observed_modes.add(response.json().get("mode", "unknown"))
                        steps.append({"step": index, "status_code": response.status_code,
                                      "passed": all(checks.values()), "checks": checks, "latency_ms": elapsed})
                    except Exception as exc:
                        steps.append({"step": index, "passed": False, "error_type": type(exc).__name__})
        except Exception as exc:
            steps.append({"step": 0, "passed": False, "error_type": type(exc).__name__})
        results.append({"id": scenario["id"], "passed": all(x["passed"] for x in steps), "steps": steps})
    passed = sum(x["passed"] for x in results)
    all_steps = [x for case in results for x in case["steps"]]
    report = report_base("agent", mode, dataset)
    report.update(status="passed" if passed == len(results) else "failed", cases=results,
                  observed_response_modes=sorted(observed_modes),
                  metrics={"scenarios_total": len(results), "scenarios_passed": passed,
                           "scenario_pass_rate": passed / len(results), "steps_total": len(all_steps),
                           "steps_passed": sum(x["passed"] for x in all_steps),
                           "latency_p50_ms": percentile(latencies, .5), "latency_p95_ms": percentile(latencies, .95)},
                  limitations=["Synthetic fixed-date fixture contract only; not real campus coverage.",
                               "Every scenario gets a fresh demo DB; HTTP mode resets A preferences before each case.",
                               "Rules/row correctness, not a model reasoning accuracy benchmark.",
                               "Backend fallback tool routing and deterministic business formatting remain enabled.",
                               "Latency includes endpoint/client overhead; not GPU load capacity.",
                               "Remote reset requests are excluded from step metrics; do not run on personal/production data."])
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset", default=ROOT / "agent/dataset.jsonl")
    p.add_argument("--mode", choices=["demo", "http"], default="demo")
    p.add_argument("--base-url", default="http://127.0.0.1:8010")
    p.add_argument("--timeout", type=float, default=300)
    p.add_argument("--output", default=ROOT / "reports/agent.json")
    a = p.parse_args()
    if a.timeout <= 0:
        p.error("timeout must be positive")
    try:
        report = run(a.dataset, a.mode, a.base_url, a.timeout)
        write_report(a.output, report)
    except (ValueError, OSError) as exc:
        p.exit(2, f"Evaluation could not start: {type(exc).__name__}\n")
    print(f"Agent: {report['status']}; {report['metrics']['scenarios_passed']}/{report['metrics']['scenarios_total']} scenarios")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
