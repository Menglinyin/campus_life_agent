"""Shared metrics, input validation and privacy-conscious report writing."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math
import os
import tempfile

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent


def read_jsonl(path, required=(), limit=1000):
    path = Path(path)
    if path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError("Dataset exceeds 4 MiB")
    rows, ids = [], set()
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict) or any(k not in row for k in ("id", *required)):
            raise ValueError(f"Invalid dataset row {number}")
        if not isinstance(row["id"], str) or not row["id"] or row["id"] in ids:
            raise ValueError(f"Invalid or duplicate id at row {number}")
        ids.add(row["id"])
        rows.append(row)
        if len(rows) > limit:
            raise ValueError("Too many dataset cases")
    if not rows:
        raise ValueError("Empty dataset")
    return rows


def percentile(values, q):
    if not 0 <= q <= 1:
        raise ValueError("Invalid quantile")
    if not values:
        return None
    ordered = sorted(float(x) for x in values)
    if any(not math.isfinite(x) or x < 0 for x in ordered):
        raise ValueError("Invalid latency")
    index = (len(ordered) - 1) * q
    lower, upper = math.floor(index), math.ceil(index)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def ranking_metrics(ranked, relevant, k):
    if k < 1 or len(ranked) != len(set(ranked)):
        raise ValueError("Invalid ranking")
    truth = set(relevant)
    if not truth:
        raise ValueError("No-answer cases have no recall denominator")
    selected = ranked[:k]
    hits = len(set(selected) & truth)
    reciprocal = next((1 / i for i, x in enumerate(selected, 1) if x in truth), 0.0)
    return {"recall_at_k": hits / len(truth), "precision_at_k": hits / k,
            "mrr_at_k": reciprocal, "hit_at_k": int(hits > 0)}


def edit_distance(reference, hypothesis):
    # Two-row Levenshtein; avoids an unbounded full matrix.
    previous = list(range(len(hypothesis) + 1))
    for i, unit in enumerate(reference, 1):
        current = [i]
        for j, candidate in enumerate(hypothesis, 1):
            current.append(min(current[-1] + 1, previous[j] + 1,
                               previous[j - 1] + (unit != candidate)))
        previous = current
    return previous[-1]


def report_base(kind, mode, dataset):
    source = hashlib.sha256()
    for path in sorted([*ROOT.rglob("*.py"), *(PROJECT / "backend/app").rglob("*.py")]):
        source.update(str(path.relative_to(PROJECT)).encode())
        source.update(b"\0")
        source.update(path.read_bytes())
    return {"schema_version": 1, "kind": kind, "mode": mode,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "evaluation_and_backend_code_sha256": source.hexdigest(),
            "dataset_sha256": hashlib.sha256(Path(dataset).read_bytes()).hexdigest()}


def write_report(path, report):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    fd, name = tempfile.mkstemp(prefix=".eval-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(data)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"Report: {path}")


def token_from_env(name):
    value = os.environ.get(name, "")
    if not value:
        raise ValueError(f"Missing token environment variable: {name}")
    return value
