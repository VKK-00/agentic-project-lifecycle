#!/usr/bin/env python3
"""Run configured verification commands and emit source-bound evidence."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import platform
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any

import yaml

SCHEMA_VERSION = "1.0"
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )


def _head_commit(root: Path) -> str:
    result = _git(root, "rev-parse", "--verify", "HEAD")
    commit = result.stdout.strip()
    if result.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}", commit):
        detail = result.stderr.strip() or "repository has no valid HEAD commit"
        raise ValueError(f"cannot bind evidence to Git HEAD: {detail}")
    return commit


def _changed_paths(root: Path) -> set[str]:
    changed: set[str] = set()
    for args in (
        ("diff", "--name-only", "HEAD", "--"),
        ("ls-files", "--others", "--exclude-standard"),
    ):
        result = _git(root, *args)
        if result.returncode != 0:
            detail = result.stderr.strip() or "unknown Git error"
            raise ValueError(f"cannot inspect repository state: {detail}")
        changed.update(line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip())
    return changed


def _relative_to_root(root: Path, path: Path, label: str) -> Path:
    resolved_root = root.resolve()
    resolved = path.resolve()
    try:
        return resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"{label} must be inside the repository root") from exc


def _is_under(path: str, prefix: Path) -> bool:
    candidate = Path(path)
    return candidate == prefix or prefix in candidate.parents


def _safe_name(value: str, index: int) -> str:
    normalized = _SAFE_NAME_RE.sub("-", value.strip()).strip("-._").lower()
    return normalized or f"check-{index}"


def _load_config(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"cannot read verification config: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("verification config root must be a mapping")
    commands = value.get("commands")
    if not isinstance(commands, list) or not commands:
        raise ValueError("verification config commands must be a non-empty list")
    tool_versions = value.get("tool_versions", {})
    if not isinstance(tool_versions, dict):
        raise ValueError("verification config tool_versions must be a mapping")
    for key, version in tool_versions.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError("tool_versions keys must be non-empty strings")
        if not isinstance(version, (str, int, float)) or not str(version).strip():
            raise ValueError(f"tool_versions.{key} must be non-empty")
    return value


def _command(item: object, index: int) -> tuple[str, str, list[str], int, int]:
    if not isinstance(item, dict):
        raise ValueError(f"commands[{index}] must be a mapping")
    name = item.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"commands[{index}].name is required")
    claim_id = item.get("claim_id", f"CLAIM-{_safe_name(name, index).upper()}")
    if not isinstance(claim_id, str) or not claim_id.strip():
        raise ValueError(f"commands[{index}].claim_id must be a non-empty string")
    argv = item.get("run")
    if (
        not isinstance(argv, list)
        or not argv
        or any(not isinstance(value, str) or not value for value in argv)
    ):
        raise ValueError(f"commands[{index}].run must be a non-empty string list")
    timeout = item.get("timeout_seconds", 90)
    max_age = item.get("max_age_hours", 24)
    if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout < 1:
        raise ValueError(f"commands[{index}].timeout_seconds must be an integer >= 1")
    if isinstance(max_age, bool) or not isinstance(max_age, int) or max_age < 1:
        raise ValueError(f"commands[{index}].max_age_hours must be an integer >= 1")
    return name.strip(), claim_id.strip(), argv, timeout, max_age


def _environment(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "working_directory": ".",
        "platform": platform.system().lower() or sys.platform,
        "python_version": platform.python_version(),
        "tool_versions": {
            str(key): str(value) for key, value in config.get("tool_versions", {}).items()
        },
    }


def _run_one(
    *,
    root: Path,
    output: Path,
    output_relative: Path,
    commit: str,
    environment: dict[str, Any],
    item: object,
    index: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    name, claim_id, argv, timeout, max_age = _command(item, index)
    safe_name = _safe_name(name, index)
    collected_at = _utc_now()
    started = time.monotonic()
    try:
        completed = subprocess.run(
            argv,
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
        exit_code = completed.returncode
        log = (completed.stdout or "") + (completed.stderr or "")
        result_status = "pass" if exit_code == 0 else "fail"
        summary = (
            f"{name} completed successfully"
            if exit_code == 0
            else f"{name} failed with exit code {exit_code}"
        )
    except subprocess.TimeoutExpired as exc:
        exit_code = 124
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        log = stdout + stderr + f"\nverification timed out after {timeout} seconds\n"
        result_status = "error"
        summary = f"{name} timed out after {timeout} seconds"
    duration_ms = round((time.monotonic() - started) * 1000)

    log_path = output / f"{safe_name}.log"
    log_path.write_text(log, encoding="utf-8")
    log_bytes = log_path.read_bytes()
    digest = hashlib.sha256(log_bytes).hexdigest()
    artifact_path = (output_relative / log_path.name).as_posix()

    evidence = {
        "schema_version": SCHEMA_VERSION,
        "evidence": {
            "id": f"EVID-{safe_name.upper()}-{commit[:12]}",
            "claim_id": claim_id,
            "source_commit": commit,
            "collected_at": _timestamp(collected_at),
            "expires_at": _timestamp(collected_at + timedelta(hours=max_age)),
            "collector": {
                "type": "tool",
                "name": "collect_verification.py",
            },
        },
        "environment": environment,
        "command": {
            "argv": argv,
            "exit_code": exit_code,
            "duration_ms": duration_ms,
        },
        "artifacts": [
            {
                "path": artifact_path,
                "sha256": digest,
                "size_bytes": len(log_bytes),
            }
        ],
        "result": {"status": result_status, "summary": summary},
        "freshness": {"policy": "commit-bound", "max_age_hours": max_age},
    }
    check = {
        "name": name,
        "argv": argv,
        "exit_code": exit_code,
        "duration_ms": duration_ms,
        "log": log_path.name,
        "log_sha256": digest,
        "evidence_id": evidence["evidence"]["id"],
    }
    return check, evidence


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect source-bound verification evidence"
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        root = args.root.resolve()
        if not root.is_dir():
            raise ValueError(f"repository root does not exist: {root}")
        output_relative = _relative_to_root(root, args.output, "output")
        if output_relative == Path("."):
            raise ValueError(
                "output must be a dedicated directory below the repository root"
            )
        config = _load_config(args.config)
        commit = _head_commit(root)
        dirty = sorted(
            path
            for path in _changed_paths(root)
            if not _is_under(path, output_relative)
        )
        if dirty:
            raise ValueError(
                "repository has non-output changes before verification: "
                + ", ".join(dirty)
            )

        args.output.mkdir(parents=True, exist_ok=True)
        environment = _environment(config)
        checks: list[dict[str, Any]] = []
        evidence_records: list[dict[str, Any]] = []
        for index, item in enumerate(config["commands"]):
            check, record = _run_one(
                root=root,
                output=args.output,
                output_relative=output_relative,
                commit=commit,
                environment=environment,
                item=item,
                index=index,
            )
            checks.append(check)
            evidence_records.append(record)
            post_command_dirty = sorted(
                path
                for path in _changed_paths(root)
                if not _is_under(path, output_relative)
            )
            if post_command_dirty:
                raise ValueError(
                    "verification command changed non-output repository paths: "
                    + ", ".join(post_command_dirty)
                )

        report = {
            "schema_version": SCHEMA_VERSION,
            "source": {"commit": commit, "dirty": False},
            "generated_at": _timestamp(_utc_now()),
            "environment": environment,
            "checks": checks,
            "evidence": evidence_records,
            "summary": {
                "passed": sum(item["exit_code"] == 0 for item in checks),
                "failed": sum(item["exit_code"] != 0 for item in checks),
            },
        }
        (args.output / "report.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(report["summary"]))
        return 0 if report["summary"]["failed"] == 0 else 1
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"VERIFICATION COLLECTION: FAIL\n- {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
