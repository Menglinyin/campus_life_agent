"""Regenerate references from backend declarations; no startup or DB connection.

Run from the project root: python docs/generate_reference.py
Requires backend/requirements.txt installed in the active environment.
"""
from pathlib import Path
import json
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "backend"))

from app.main import create_app
from app.settings import Settings
from app.storage.mysql import Base
from app.storage import models  # Register all mapped tables.
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateIndex, CreateTable


def main():
    output = PROJECT / "docs" / "generated"
    output.mkdir(parents=True, exist_ok=True)
    spec = create_app().openapi()  # No lifespan: no Services, DB, models or seeds.
    (output / "openapi.json").write_text(
        json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    schema = Settings.model_json_schema()  # No Settings() or environment reads.
    for name in ("user_tokens", "llm_api_key", "mcp_token"):
        schema["properties"][name].pop("default", None)
        schema["properties"][name]["description"] = "Credentials: configure locally."
    # Machine-specific default path must not be baked into the deliverable.
    schema["properties"]["skill_root"]["default"] = "backend/skill_packages"
    (output / "settings_schema.json").write_text(
        json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    dialect = mysql.dialect()
    statements = [
        "-- GENERATED FROM SQLALCHEMY ORM. Reference only; not a migration.",
        "-- Python defaults are not SERVER DEFAULT clauses.",
        "-- No database was connected to generate this file.",
    ]
    for table in Base.metadata.sorted_tables:
        statements.append(str(CreateTable(table).compile(dialect=dialect)).strip() + ";")
        for index in sorted(table.indexes, key=lambda x: x.name):
            statements.append(str(CreateIndex(index).compile(dialect=dialect)) + ";")
    (output / "mysql_schema.sql").write_text("\n\n".join(statements) + "\n", encoding="utf-8")
    print(f"Generated OpenAPI ({len(spec['paths'])} paths), settings schema and {len(Base.metadata.tables)} SQL tables.")


if __name__ == "__main__":
    main()
