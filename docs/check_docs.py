"""Check local Markdown links, JSON syntax and required documentation files.

This is documentation verification, not a runtime or load test.
Run from any directory: python /path/to/project/docs/check_docs.py
"""
from pathlib import Path
import json
import re
import sys
from urllib.parse import unquote

DOCS = Path(__file__).resolve().parent
REQUIRED = (
    "README.md", "architecture.md", "reproduction.md", "database_schema.md",
    "rag_pipeline.md", "mcp_and_skills.md", "multimodal.md", "model_deployment.md",
    "parameters.md", "capacity_planning.md", "load_test_plan.md", "data_collection.md",
    "dependency_versions.md", "upstream_components.md", "implementation_status.md",
    "api_reference.md", "troubleshooting.md", "verification.md",
)


def main():
    errors = []
    for name in REQUIRED:
        path = DOCS / name
        if not path.is_file() or not path.read_text(encoding="utf-8").strip():
            errors.append(f"Missing or empty: {name}")
    links = 0
    for path in sorted(DOCS.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        if text.count("```") % 2:
            errors.append(f"Unclosed code fence: {path.name}")
        for match in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", text):
            target = match.group(1)
            if target.startswith(("http:", "https:", "mailto:", "sandbox:", "#")):
                continue
            target = unquote(target.split("#", 1)[0])
            links += 1
            if not (path.parent / target).exists():
                errors.append(f"Broken link: {path.relative_to(DOCS)} -> {target}")
    json_files = list(DOCS.rglob("*.json"))
    for path in json_files:
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            errors.append(f"Invalid JSON: {path.name}: {type(exc).__name__}")
    report = json.loads((DOCS / "examples" / "load_test_report.json").read_text(encoding="utf-8"))
    if report["status"] == "not_run" and any(v is not None for v in report["metrics"].values()):
        errors.append("Unrun load report contains measured metrics")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"Documentation checks passed: {len(REQUIRED)} required pages, {links} local links, {len(json_files)} JSON files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
