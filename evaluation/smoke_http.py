"""Start a temporary HTTP fixture and verify HTTP/optional short Locust wiring.

This is a demo connectivity check, not a capacity benchmark.
"""
import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import time

import httpx
from evaluation.common import ROOT, PROJECT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--load-python", type=Path, help="Python executable in a separate Locust venv")
    parser.add_argument("--disable-cpu-monitor", action="store_true", help="Propagate explicit restricted-environment opt-out")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports")
    args = parser.parse_args()
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    env = {**os.environ, "EVAL_TOKEN_A": "eval-a-token", "EVAL_TOKEN_B": "eval-b-token"}
    env.pop("EVAL_LOAD_TOKENS", None)
    env["EVAL_LOAD_PURPOSE"] = "demo_connectivity_smoke"
    base = f"http://127.0.0.1:{port}"
    with TemporaryDirectory(prefix="campus-http-smoke-") as directory:
        with (Path(directory) / "fixture.log").open("w") as log:
            server = subprocess.Popen([sys.executable, "-m", "evaluation.serve_fixture", "--port", str(port)],
                                      cwd=PROJECT, env=env, stdout=log, stderr=log)
            try:
                ready = False
                with httpx.Client(timeout=1, trust_env=False) as client:
                    for _ in range(200):
                        if server.poll() is not None:
                            break
                        try:
                            ready = client.get(base + "/api/health").status_code == 200
                        except httpx.HTTPError:
                            pass
                        if ready:
                            break
                        time.sleep(.1)
                if not ready:
                    print("Temporary fixture server could not start.", file=sys.stderr)
                    return 2
                result = subprocess.run([sys.executable, "-m", "evaluation.agent.evaluate", "--mode", "http",
                                         "--base-url", base, "--output", str(args.output_dir / "http_demo_agent.json")],
                                        cwd=PROJECT, env=env)
                if result.returncode:
                    return result.returncode
                if args.load_python:
                    command = [str(args.load_python.absolute()), "-m", "evaluation.load.run_load",
                                             "--host", base, "--users", "2", "--spawn-rate", "2",
                                             "--runtime-seconds", "8", "--warmup-seconds", "1",
                                             "--output", str(args.output_dir / "demo_load_smoke.json")]
                    if args.disable_cpu_monitor:
                        command.append("--disable-cpu-monitor")
                    result = subprocess.run(command, cwd=PROJECT, env=env)
                    return result.returncode
                return 0
            finally:
                server.terminate()
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()


if __name__ == "__main__":
    raise SystemExit(main())
