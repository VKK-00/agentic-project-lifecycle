"""Draft 2020-12 structural validation for governance artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

PLUGIN_ROOT = Path(__file__).resolve().parents[4]
SCHEMA_ROOT = PLUGIN_ROOT / "schemas"

SCHEMA_FILES = {
    "task": "task-contract-v1.schema.json",
    "gate": "gate-transition-v1.schema.json",
    "evidence": "evidence-record-v1.schema.json",
    "execution": "execution-result-v1.schema.json",
    "state": "project-state-v2.schema.json",
    "policy": "policy-profile-v1.schema.json",
    "audit": "project-audit-v1.schema.json",
    "run": "run-manifest-v1.schema.json",
}


def load_schema(kind: str) -> dict[str, Any]:
    filename = SCHEMA_FILES.get(kind)
    if filename is None:
        raise ValueError(f"unknown schema kind: {kind}")
    return json.loads((SCHEMA_ROOT / filename).read_text(encoding="utf-8"))


def validate_schema_document(kind: str, data: object) -> list[str]:
    validator = Draft202012Validator(load_schema(kind))
    errors = sorted(validator.iter_errors(data), key=lambda item: list(item.absolute_path))
    result: list[str] = []
    for error in errors:
        path = ".".join(str(part) for part in error.absolute_path) or "."
        result.append(f"schema {path}: {error.message}")
    return result
