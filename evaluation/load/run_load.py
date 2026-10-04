"""Invoke pinned Locust; tokens stay in environment, never command arguments."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit
import json
from evaluation.load.scenarios import load_scenarios


def main():
    root = Path(__file__).resolve().parent
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", default="http://127.0.0.1:8010")
    p.add_argument("--users", type=int, default=4)
    p.add_argument("--spawn-rate", type=float, default=1)
    p.add_argument("--runtime-seconds", type=int, default=300)
    p.add_argument("--warmup-seconds", type=int, default=15)
    p.add_argument("--scope", choices=["demo", "model"], default="demo")
    p.add_argument("--disable-cpu-monitor", action="store_true", help="Explicit opt-out for restricted /proc; recorded in report")
    p.add_argument("--output", type=Path, default=root.parent / "reports/load.json")
    a = p.parse_args()
    if a.users < 1 or a.spawn_rate <= 0 or a.warmup_seconds < 0 or a.runtime_seconds <= a.warmup_seconds:
        p.error("Invalid users/rate/runtime/warmup")
    if not os.environ.get("EVAL_TOKEN_A") and not os.environ.get("EVAL_LOAD_TOKENS"):
        p.error("Set EVAL_TOKEN_A or EVAL_LOAD_TOKENS locally")
    try:
        tokens = json.loads(os.environ["EVAL_LOAD_TOKENS"]) if os.environ.get("EVAL_LOAD_TOKENS") else [os.environ.get("EVAL_TOKEN_A")]
        if not isinstance(tokens, list) or not tokens or any(not isinstance(x, str) or not x for x in tokens):
            raise ValueError("invalid tokens")
        load_scenarios(os.environ.get("EVAL_LOAD_SCENARIOS", str(root / "scenarios.yaml")))
    except (ValueError, KeyError, TypeError, OSError):
        p.error("Invalid token list or scenario file")
    parsed = urlsplit(a.host)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.path not in ("", "/") or parsed.username or parsed.password or parsed.query or parsed.fragment:
        p.error("host must be an HTTP(S) origin without credentials or query")
    env = {**os.environ, "EVAL_LOAD_WARMUP": str(a.warmup_seconds), "EVAL_LOAD_SCOPE": a.scope,
           "EVAL_LOAD_REPORT": str(a.output.resolve())}
    if a.disable_cpu_monitor:
        env["EVAL_LOAD_DISABLE_CPU_MONITOR"] = "1"
    command = [sys.executable, "-m", "locust", "-f", str(root / "locustfile.py"), "--headless",
               "--host", a.host, "-u", str(a.users), "-r", str(a.spawn_rate),
               "--run-time", f"{a.runtime_seconds}s", "--stop-timeout", "310", "--only-summary"]
    output = a.output.resolve()
    previous = output.stat().st_mtime_ns if output.exists() else None
    code = subprocess.call(command, env=env)
    if not output.exists() or output.stat().st_mtime_ns == previous:
        print("No fresh load report was produced.", file=sys.stderr)
        return code or 2
    report = json.loads(output.read_text(encoding="utf-8"))
    if report["status"] != "completed" or not report["metrics"]["requests_total"]:
        return code or 1
    return code


if __name__ == "__main__":
    raise SystemExit(main())
