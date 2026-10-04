"""Bounded raw latency collection, standalone from Locust for deterministic tests."""
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from evaluation.common import percentile


class Collector:
    def __init__(self, start, warmup, max_samples=100000):
        if warmup < 0 or max_samples < 1:
            raise ValueError("Invalid collection limits")
        self.start = start
        self.warmup = warmup
        self.max_samples = max_samples
        self.values = []
        self.status_codes = Counter()
        self.modes = Counter()
        self.total = self.failed = self.dropped = 0

    def record(self, started_at, duration_ms, status_code, failed, response_mode=None):
        if started_at < self.start + self.warmup:
            return
        if not math.isfinite(duration_ms) or duration_ms < 0:
            raise ValueError("Invalid duration")
        self.total += 1
        self.failed += bool(failed)
        self.status_codes[str(status_code)] += 1
        if response_mode:
            self.modes[response_mode] += 1
        if len(self.values) < self.max_samples:
            self.values.append(duration_ms)
        else:
            self.dropped += 1

    def report(self, ended_at, metadata):
        duration = max(0, ended_at - self.start - self.warmup)
        # If capped, withhold percentiles rather than call the first N a full sample.
        latencies = [] if self.dropped else self.values
        metrics = {"requests_total": self.total if self.total else None,
                   "requests_successful": self.total - self.failed if self.total else None,
                   "requests_failed": self.failed if self.total else None,
                   "success_rate": (self.total - self.failed) / self.total if self.total else None,
                   "completed_chat_rps": (self.total - self.failed) / duration if duration and self.total else None,
                   "e2e_p50_ms": percentile(latencies, .5), "e2e_p95_ms": percentile(latencies, .95),
                   "e2e_p99_ms": percentile(latencies, .99), "gpu_0_peak_gib": None, "gpu_1_peak_gib": None,
                   "ttft_p95_ms": None, "model_queue_peak": None}
        return {"schema_version": 1, "kind": "load", "status": "completed" if self.total else "no_samples",
                "created_at": datetime.now(timezone.utc).isoformat(), "metadata": metadata,
                "measurement_seconds": duration, "metrics": metrics,
                "http_status_counts": dict(self.status_codes), "observed_response_modes": dict(self.modes),
                "latency_samples_retained": len(self.values), "latency_samples_dropped": self.dropped,
                "limitations": ["Counts all measured chat completions; semantic failure counts as failure even with HTTP 200.",
                                "Warmup excluded by request start timestamp; measurement includes any shutdown drain.",
                                "Closed-loop concurrent clients, not a controlled open arrival rate.",
                                "GPU/queue/TTFT are not collected by this script and remain null.",
                                "If latency cap is exceeded, percentiles are withheld.",
                                "Declared demo/model scope is a label; observed modes do not prove specific hardware."]}


def validate_report(report):
    from jsonschema import validate
    schema = json.loads((Path(__file__).parent / "report_schema.json").read_text(encoding="utf-8"))
    validate(report, schema)
