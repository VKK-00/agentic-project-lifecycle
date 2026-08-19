#!/usr/bin/env python3
"""Check release readiness against plans, fresh evidence, and repository state."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys
from typing import Any

import yaml

try:
    from governance.runner_support import safe_environment
    from governance_contracts import validate_evidence_record
except ModuleNotFoundError:  # pragma: no cover - import path for module loaders
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from governance.runner_support import safe_environment
    from governance_contracts import validate_evidence_record

REQUIRED_RELEASE_FIELDS = (
    "version",
    "stage",
    "owner",
    "support_owner",
    "audience",
    "hypothesis",
    "included",
    "excluded",
    "entry_criteria",
    "exit_criteria",
    "metrics",
    "known_limitations",
    "rollout",
    "rollback",
)
REQUIRED_FILES = (
    "docs/07-release/ROLLBACK.md",
    "docs/08-operations/OBSERVABILITY.md",
    "docs/08-operations/RUNBOOK.md",
)


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", *args],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
        env=safe_environment(),
    )


def _head_commit(root: Path, errors: list[str]) -> str:
    result = _git(root, "rev-parse", "--verify", "HEAD")
    commit = result.stdout.strip()
    if result.returncode != 0 or len(commit) != 40:
        errors.append("cannot resolve repository HEAD commit")
        return ""
    return commit


def _changed_paths(root: Path, errors: list[str]) -> list[str]:
    changed: set[str] = set()
    for args in (
        ("diff", "--name-only", "HEAD", "--"),
        ("ls-files", "--others", "--exclude-standard"),
        ("ls-files", "--others", "--ignored", "--exclude-standard"),
    ):
        result = _git(root, *args)
        if result.returncode != 0:
            errors.append("cannot inspect repository changes")
            return []
        changed.update(line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip())
    return sorted(path for path in changed if path != "evidence" and not path.startswith("evidence/"))


def _read_yaml(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        errors.append(f"cannot parse {label}: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{label} root must be a mapping")
        return {}
    return value


def _read_json(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"cannot parse {label}: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{label} root must be an object")
        return {}
    return value


def _validate_artifacts(
    root: Path, record: dict[str, Any], index: int, errors: list[str]
) -> None:
    artifacts = record.get("artifacts")
    if not isinstance(artifacts, list):
        return
    for artifact_index, raw in enumerate(artifacts):
        if not isinstance(raw, dict):
            continue
        relative = raw.get("path")
        expected_digest = raw.get("sha256")
        expected_size = raw.get("size_bytes")
        if not isinstance(relative, str) or not relative:
            continue
        candidate = (root / relative).resolve()
        resolved_root = root.resolve()
        if candidate != resolved_root and resolved_root not in candidate.parents:
            errors.append(
                f"evidence[{index}]: artifact[{artifact_index}] escapes repository root"
            )
            continue
        if not candidate.is_file():
            errors.append(
                f"evidence[{index}]: artifact is missing: {relative}"
            )
            continue
        payload = candidate.read_bytes()
        if hashlib.sha256(payload).hexdigest() != expected_digest:
            errors.append(
                f"evidence[{index}]: artifact digest mismatch: {relative}"
            )
        if len(payload) != expected_size:
            errors.append(
                f"evidence[{index}]: artifact size mismatch: {relative}"
            )


def _validate_latest_mirror(
    root: Path, record: dict[str, Any], index: int, errors: list[str]
) -> None:
    artifacts = record.get("artifacts")
    if not isinstance(artifacts, list):
        return
    for artifact_index, raw in enumerate(artifacts):
        if not isinstance(raw, dict):
            continue
        relative = raw.get("path")
        if not isinstance(relative, str) or not relative:
            continue
        filename = Path(relative).name
        mirror = root / "evidence" / "latest" / filename
        if not mirror.is_file():
            errors.append(f"evidence[{index}]: latest artifact mirror is missing: {filename}")
            continue
        payload = mirror.read_bytes()
        if hashlib.sha256(payload).hexdigest() != raw.get("sha256"):
            errors.append(f"evidence[{index}]: artifact digest mismatch: evidence/latest/{filename}")
        if len(payload) != raw.get("size_bytes"):
            errors.append(f"evidence[{index}]: artifact size mismatch: evidence/latest/{filename}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check release readiness")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--release", required=True)
    args = parser.parse_args()

    root = args.root.resolve()
    errors: list[str] = []
    head = _head_commit(root, errors)

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", args.release):
        errors.append("release identifier is invalid")
        release_data: dict[str, Any] = {}
        release_path = root / "docs/05-planning/releases/invalid.yaml"
    else:
        release_path = root / f"docs/05-planning/releases/{args.release}.yaml"
    if not release_path.is_file():
        if "release identifier is invalid" not in errors:
            errors.append(f"missing release plan: {release_path.relative_to(root)}")
        release_data = {}
    else:
        release_data = _read_yaml(release_path, "release plan", errors)
    for field in REQUIRED_RELEASE_FIELDS:
        if not release_data.get(field):
            errors.append(f"release field missing: {field}")

    for relative in REQUIRED_FILES:
        if not (root / relative).is_file():
            errors.append(f"missing {relative}")

    evidence_path = root / "evidence/latest/report.json"
    report: dict[str, Any] = {}
    if not evidence_path.is_file():
        errors.append("missing evidence/latest/report.json")
    else:
        report = _read_json(evidence_path, "verification evidence", errors)

    if report:
        if report.get("schema_version") != "1.0":
            errors.append("verification evidence schema_version must be 1.0")
        source = report.get("source")
        if not isinstance(source, dict):
            errors.append("verification evidence source must be an object")
        else:
            if head and source.get("commit") != head:
                errors.append(
                    "verification evidence source commit does not match repository HEAD"
                )
            if source.get("dirty") is not False:
                errors.append("verification evidence must come from a clean source state")

        summary = report.get("summary")
        if not isinstance(summary, dict) or summary.get("failed", 1) != 0:
            errors.append("verification evidence contains failures")

        evidence_records = report.get("evidence")
        if not isinstance(evidence_records, list) or not evidence_records:
            errors.append("verification evidence must contain at least one record")
        else:
            for index, record in enumerate(evidence_records):
                for error in validate_evidence_record(record, expected_commit=head or None):
                    errors.append(f"evidence[{index}]: {error}")
                if isinstance(record, dict):
                    _validate_artifacts(root, record, index, errors)
                    _validate_latest_mirror(root, record, index, errors)

    dirty = _changed_paths(root, errors)
    if dirty:
        errors.append(
            "repository has non-evidence changes after verification: "
            + ", ".join(dirty)
        )

    if errors:
        print("RELEASE READINESS: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("RELEASE READINESS: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
