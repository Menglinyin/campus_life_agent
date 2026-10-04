"""Single-process Locust scenarios against the isolated fixture server."""
from pathlib import Path
import itertools
import json
import os
import random
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from locust import HttpUser, between, events, task
from locust.runners import MasterRunner, WorkerRunner
import yaml
from gevent.event import Event
from evaluation.common import write_report
from evaluation.load.collector import Collector, validate_report

ROOT = Path(__file__).resolve().parent
COLLECTOR = None
SCENARIOS = []
TOKENS = []
COUNTER = itertools.count()
CONFIG = {}


from evaluation.load.scenarios import load_scenarios


@events.init.add_listener
def optional_cpu_monitor(environment, **kwargs):
    # Only for restricted /proc environments, explicitly enabled by the caller.
    # Pinned Locust 2.43.2 exposes its background greenlets on runner.greenlet.
    if os.environ.get("EVAL_LOAD_DISABLE_CPU_MONITOR") != "1":
        return
    if isinstance(environment.runner, (MasterRunner, WorkerRunner)):
        raise ValueError("CPU opt-out is only supported for local Locust")
    for greenlet in list(environment.runner.greenlet):
        if getattr(getattr(greenlet, "_run", None), "__name__", "") == "monitor_cpu_and_memory":
            greenlet.kill(block=False)
    # Locust joins this group; keep it alive until normal runner shutdown.
    environment.runner.greenlet.spawn(Event().wait)
    print("Locust CPU/RAM monitoring explicitly disabled; HTTP checks remain enabled.")


@events.test_start.add_listener
def begin(environment, **kwargs):
    global COLLECTOR, SCENARIOS, TOKENS, CONFIG, COUNTER
    if isinstance(environment.runner, (MasterRunner, WorkerRunner)):
        raise ValueError("This report collector supports single-process Locust only")
    SCENARIOS = load_scenarios(os.environ.get("EVAL_LOAD_SCENARIOS", str(ROOT / "scenarios.yaml")))
    TOKENS = json.loads(os.environ["EVAL_LOAD_TOKENS"]) if os.environ.get("EVAL_LOAD_TOKENS") else [os.environ.get("EVAL_TOKEN_A", "")]
    if not isinstance(TOKENS, list) or not TOKENS or any(not isinstance(x, str) or not x for x in TOKENS):
        raise ValueError("Set valid local load test tokens")
    warmup = float(os.environ.get("EVAL_LOAD_WARMUP", "15"))
    CONFIG = {"declared_scope": os.environ.get("EVAL_LOAD_SCOPE", "unspecified"),
              "warmup_seconds": warmup, "requested_users": environment.parsed_options.num_users,
              "identity_token_count": len(set(TOKENS)), "scenario_ids": [x["id"] for x in SCENARIOS],
              "locust_version": "2.43.2", "redis_session_ttl_context": 259200,
              "cpu_ram_monitor_enabled": os.environ.get("EVAL_LOAD_DISABLE_CPU_MONITOR") != "1",
              "purpose": os.environ.get("EVAL_LOAD_PURPOSE", "load_experiment")}
    COUNTER = itertools.count()
    COLLECTOR = Collector(time.time(), warmup)


@events.request.add_listener
def completed(request_type, name, response_time, response_length, response=None,
              exception=None, start_time=None, context=None, **kwargs):
    if COLLECTOR is None or not name.startswith("chat/"):
        return
    COLLECTOR.record(start_time or time.time(), response_time,
                     getattr(response, "status_code", 0), exception is not None,
                     (context or {}).get("response_mode"))


@events.test_stop.add_listener
def finish(environment, **kwargs):
    if COLLECTOR is None:
        environment.process_exit_code = 2
        return
    report = COLLECTOR.report(time.time(), CONFIG)
    validate_report(report)
    write_report(os.environ.get("EVAL_LOAD_REPORT", str(ROOT.parent / "reports/load.json")), report)
    scope = CONFIG["declared_scope"]
    incompatible = (scope == "demo" and "vllm" in COLLECTOR.modes) or (scope == "model" and "demo" in COLLECTOR.modes)
    if not COLLECTOR.total or COLLECTOR.failed or incompatible:
        environment.process_exit_code = 1


class CampusUser(HttpUser):
    wait_time = between(.5, 1.5)

    def on_start(self):
        self.token = TOKENS[next(COUNTER) % len(TOKENS)]
        self.rng = random.Random(20261004 + next(COUNTER))

    @task
    def chat(self):
        scenario = self.rng.choices(SCENARIOS, weights=[x["weight"] for x in SCENARIOS], k=1)[0]
        with self.client.post("/api/chat", json={"message": scenario["message"]},
                              headers={"Authorization": "Bearer " + self.token},
                              name="chat/" + scenario["id"], timeout=300, catch_response=True,
                              context={}) as response:
            if response.status_code != 200:
                response.failure("unexpected_http_status")
                return
            try:
                body = response.json()
                response.request_meta["context"]["response_mode"] = body.get("mode", "unknown")
                results = body["results"]
                if sorted(x["tool"] for x in results) != sorted(scenario["expected_tools"]):
                    response.failure("tool_set_mismatch")
                    return
                rows = {x["tool"]: x["rows"] for x in results}
                if any(len(rows.get(tool, [])) < count for tool, count in scenario.get("minimum_rows", {}).items()):
                    response.failure("insufficient_business_rows")
                    return
                if not body.get("answer") or not body.get("message_id") or not body.get("session_id"):
                    response.failure("invalid_chat_envelope")
            except (KeyError, ValueError, TypeError):
                response.failure("invalid_chat_json")
