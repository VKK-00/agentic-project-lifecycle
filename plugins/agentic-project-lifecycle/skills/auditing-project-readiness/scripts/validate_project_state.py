#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import subprocess

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from governance_contracts import (  # noqa: E402
    PROJECT_STATE_SCHEMA_VERSION,
    validate_project_state_v2,
)

PHASES = {
    "orientation",
    "discovery",
    "specification",
    "solution-design",
    "planning",
    "implementation",
    "release",
    "operations",
}
STATUSES = {"blocked", "in-progress", "review", "ready", "complete"}


def _validate_legacy(data: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["root must be a mapping"]
    project = data.get("project", {})
    life = data.get("lifecycle", {})
    outcome = data.get("current_outcome", {})
    for key in ("id", "name", "type", "mode"):
        if not project.get(key):
            errors.append(f"project.{key} is required")
    if life.get("current_phase") not in PHASES:
        errors.append("lifecycle.current_phase is invalid")
    if life.get("status") not in STATUSES:
        errors.append("lifecycle.status is invalid")
    for key in ("id", "statement", "metric", "target"):
        if outcome.get(key) in (None, ""):
            errors.append(f"current_outcome.{key} is required")
    blockers = data.get("blockers", []) or []
    for blocker in blockers:
        if not blocker.get("id") or not blocker.get("reason"):
            errors.append("every blocker needs id and reason")
        if not blocker.get("owner"):
            errors.append(f"unowned blocker: {blocker.get('id', 'unknown')}")
    if life.get("status") == "ready" and blockers:
        errors.append("ready state cannot contain blockers")
    artifacts = data.get("artifacts", {})
    phase = life.get("current_phase")
    required = {
        "specification": ["charter", "prd"],
        "solution-design": ["charter", "prd", "design"],
        "planning": ["charter", "prd", "design", "plan"],
        "implementation": ["charter", "prd", "design", "plan"],
        "release": [
            "charter",
            "prd",
            "design",
            "plan",
            "evidence",
            "release_plan",
            "runbook",
        ],
        "operations": [
            "charter",
            "prd",
            "design",
            "plan",
            "evidence",
            "release_plan",
            "runbook",
        ],
    }.get(phase, [])
    for name in required:
        if artifacts.get(name) not in {"approved", "verified", "complete"}:
            errors.append(f"artifact {name} is not approved/verified")
    return errors


def validate(
    path: Path, *, strict: bool = False, root: Path | None = None
) -> list[str]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"cannot parse YAML: {exc}"]
    is_v2 = isinstance(data, dict) and data.get("schema_version") == PROJECT_STATE_SCHEMA_VERSION
    if strict and not is_v2:
        return [
            f"strict mode requires project-state schema_version {PROJECT_STATE_SCHEMA_VERSION}"
        ]
    if is_v2:
        return validate_project_state_v2(data, root=root)
    return _validate_legacy(data)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--root", type=Path)
    args = parser.parse_args()
    root = args.root
    if args.strict and root is None:
        result = subprocess.run(
            ["git", "-C", str(args.path.resolve().parent), "rev-parse", "--show-toplevel"],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            print("PROJECT STATE: FAIL")
            print("- strict mode requires a resolvable Git repository root")
            return 1
        root = Path(result.stdout.strip()).resolve()
    errors = validate(args.path, strict=args.strict, root=root)
    if errors:
        print("PROJECT STATE: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    suffix = "" if args.strict else " (strict or compatible legacy)"
    print(f"PROJECT STATE: PASS{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
