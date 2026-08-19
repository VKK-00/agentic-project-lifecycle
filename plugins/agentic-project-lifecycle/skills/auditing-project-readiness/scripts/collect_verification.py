#!/usr/bin/env python3
"""Run verification commands and atomically publish immutable source-bound evidence."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import platform
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from typing import Any

import yaml

from governance.run_manifest import (
    append_event,
    build_run_manifest,
    file_sha256,
    redact_text,
)
from governance.runner_support import (
    RunnerSupportError,
    network_isolation_command,
    run_supervised_process,
    safe_environment,
    validate_command_argv,
)

SCHEMA_VERSION = "1.0"
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", *args],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
        env=safe_environment({"GIT_CONFIG_GLOBAL": os.devnull}),
    )


def _require_repository_root(root: Path) -> None:
    result = _git(root, "rev-parse", "--show-toplevel")
    if result.returncode != 0 or not result.stdout.strip():
        raise ValueError(result.stderr.strip() or "cannot resolve Git repository top level")
    top_level = Path(result.stdout.strip()).resolve()
    if top_level != root.resolve():
        raise ValueError(
            f"--root must be the Git repository top level: expected {top_level}"
        )


def _repository_identity(root: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for key, args in (
        ("commit", ("rev-parse", "--verify", "HEAD")),
        ("tree", ("rev-parse", "HEAD^{tree}")),
        ("branch", ("symbolic-ref", "--short", "-q", "HEAD")),
    ):
        result = _git(root, *args)
        if key == "branch" and result.returncode == 1:
            values[key] = "DETACHED"
            continue
        value = result.stdout.strip()
        if result.returncode != 0 or not value:
            raise ValueError(result.stderr.strip() or f"cannot resolve repository {key}")
        values[key] = value
    if not re.fullmatch(r"[0-9a-f]{40}", values["commit"]):
        raise ValueError("repository has no valid HEAD commit")
    if not re.fullmatch(r"[0-9a-f]{40}", values["tree"]):
        raise ValueError("repository has no valid HEAD tree")
    return values


def _changed_paths(root: Path) -> set[str]:
    changed: set[str] = set()
    for args in (
        ("diff", "--name-only", "HEAD", "--"),
        ("ls-files", "--others", "--exclude-standard"),
        ("ls-files", "--others", "--ignored", "--exclude-standard"),
    ):
        result = _git(root, *args)
        if result.returncode != 0:
            raise ValueError(result.stderr.strip() or "cannot inspect repository state")
        changed.update(
            line.strip().replace("\\", "/")
            for line in result.stdout.splitlines()
            if line.strip()
        )
    return changed


def _relative_to_root(root: Path, path: Path, label: str) -> Path:
    try:
        return path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"{label} must be inside the repository root") from exc


def _is_under(path: str, prefix: Path) -> bool:
    candidate = Path(path)
    return candidate == prefix or prefix in candidate.parents


def _safe_name(value: str, index: int) -> str:
    normalized = _SAFE_NAME_RE.sub("-", value.strip()).strip("-._").lower()
    return normalized or f"check-{index}"


def _run_id(commit: str) -> str:
    return f"RUN-{_utc_now().strftime('%Y%m%dT%H%M%S%fZ')}-{commit[:12]}-{secrets.token_hex(4)}"


def _evidence_tree_state(
    evidence_root: Path, *, excluded_top_level: set[str]
) -> tuple[tuple[str, str], ...]:
    """Fingerprint prior evidence without following symlinks."""

    if not evidence_root.exists():
        return ()
    records: list[tuple[str, str]] = []

    def visit(directory: Path) -> None:
        with os.scandir(directory) as entries:
            ordered = sorted(entries, key=lambda item: item.name)
        for entry in ordered:
            if directory == evidence_root and entry.name in excluded_top_level:
                continue
            path = Path(entry.path)
            relative = path.relative_to(evidence_root).as_posix()
            metadata = entry.stat(follow_symlinks=False)
            digest = hashlib.sha256()
            digest.update(f"{metadata.st_mode:o}:".encode("ascii"))
            if entry.is_symlink():
                digest.update(os.readlink(path).encode("utf-8", errors="surrogateescape"))
            elif entry.is_dir(follow_symlinks=False):
                digest.update(b"directory")
                records.append((relative, digest.hexdigest()))
                visit(path)
                continue
            elif entry.is_file(follow_symlinks=False):
                with path.open("rb") as handle:
                    for block in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(block)
            else:
                digest.update(f"size={metadata.st_size}".encode("ascii"))
            records.append((relative, digest.hexdigest()))

    visit(evidence_root)
    return tuple(sorted(records))


def _archive_prior_evidence(
    evidence_root: Path, *, excluded_top_level: set[str]
):
    """Create an unlinked disk-backed archive not inherited by child processes."""

    backup = tempfile.TemporaryFile(mode="w+b")
    with tarfile.open(fileobj=backup, mode="w") as archive:
        if evidence_root.exists():
            for entry in sorted(os.scandir(evidence_root), key=lambda item: item.name):
                if entry.name in excluded_top_level:
                    continue
                archive.add(
                    entry.path,
                    arcname=entry.name,
                    recursive=True,
                    filter=lambda info: _normalized_tar_info(info),
                )
    backup.flush()
    backup.seek(0)
    return backup


def _normalized_tar_info(info: tarfile.TarInfo) -> tarfile.TarInfo:
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mtime = 0
    return info


def _remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.exists():
        shutil.rmtree(path)


def _restore_prior_evidence(
    evidence_root: Path,
    backup,
    *,
    excluded_top_level: set[str],
) -> None:
    """Restore the exact pre-verification evidence tree after a tamper attempt."""

    backup.seek(0)
    with tempfile.TemporaryDirectory(prefix="apl-evidence-restore-") as temporary:
        restore_root = Path(temporary)
        with tarfile.open(fileobj=backup, mode="r:") as archive:
            archive.extractall(restore_root, filter="data")
        for entry in list(os.scandir(evidence_root)):
            if entry.name in excluded_top_level:
                continue
            _remove_path(Path(entry.path))
        for entry in sorted(os.scandir(restore_root), key=lambda item: item.name):
            os.replace(entry.path, evidence_root / entry.name)


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
    return value


def _command(item: object, index: int) -> tuple[str, str, list[str], int, int]:
    if not isinstance(item, dict):
        raise ValueError(f"commands[{index}] must be a mapping")
    name = item.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"commands[{index}].name is required")
    claim_id = item.get("claim_id", f"CLAIM-{_safe_name(name, index).upper()}")
    argv = item.get("run")
    if not isinstance(claim_id, str) or not claim_id.strip():
        raise ValueError(f"commands[{index}].claim_id must be a non-empty string")
    if not isinstance(argv, list):
        raise ValueError(f"commands[{index}].run must be a non-empty string list")
    try:
        argv = validate_command_argv(argv)
    except RunnerSupportError as exc:
        raise ValueError(f"commands[{index}].run is unsafe: {exc}") from exc
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
        "tool_versions": {str(key): str(value) for key, value in config.get("tool_versions", {}).items()},
    }


def _unique_names(commands: list[object]) -> list[str]:
    used: set[str] = set()
    result: list[str] = []
    for index, item in enumerate(commands):
        name = item.get("name") if isinstance(item, dict) else ""
        base = _safe_name(str(name), index)
        candidate = base
        suffix = 2
        while candidate in used:
            candidate = f"{base}-{suffix}"
            suffix += 1
        used.add(candidate)
        result.append(candidate)
    return result


def _run_one(
    *,
    root: Path,
    staging: Path,
    artifact_prefix: Path,
    identity: dict[str, str],
    environment: dict[str, Any],
    item: object,
    index: int,
    safe_name: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    name, claim_id, argv, timeout, max_age = _command(item, index)
    collected_at = _utc_now()
    isolated_home = staging / ".verification-home"
    isolated_home.mkdir(mode=0o700, parents=True, exist_ok=True)
    command_env = safe_environment(
        {
            "HOME": str(isolated_home),
            "XDG_CONFIG_HOME": str(isolated_home / ".config"),
            "XDG_CACHE_HOME": str(isolated_home / ".cache"),
            "XDG_DATA_HOME": str(isolated_home / ".local" / "share"),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "PIP_CONFIG_FILE": os.devnull,
            "NPM_CONFIG_USERCONFIG": os.devnull,
        }
    )
    sandbox_argv = network_isolation_command(argv)
    started = time.monotonic()
    completed = run_supervised_process(
        sandbox_argv,
        cwd=root,
        timeout_seconds=timeout,
        env=command_env,
    )
    exit_code = completed.returncode
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    if completed.timed_out:
        stderr += f"\nverification timed out after {timeout} seconds\n"
        result_status = "error"
        summary = f"{name} timed out after {timeout} seconds"
    else:
        result_status = "pass" if exit_code == 0 else "fail"
        summary = (
            f"{name} completed successfully"
            if exit_code == 0
            else f"{name} failed with exit code {exit_code}"
        )
    duration_ms = round((time.monotonic() - started) * 1000)
    stdout = redact_text(stdout)
    stderr = redact_text(stderr)
    combined = stdout + stderr
    files = [
        (f"{safe_name}.log", combined),
        (f"{safe_name}.stdout.log", stdout),
        (f"{safe_name}.stderr.log", stderr),
    ]
    artifacts: list[dict[str, Any]] = []
    for filename, content in files:
        target = staging / filename
        target.write_text(content, encoding="utf-8")
        artifacts.append(
            {
                "path": (artifact_prefix / filename).as_posix(),
                "sha256": file_sha256(target),
                "size_bytes": target.stat().st_size,
            }
        )
    evidence = {
        "schema_version": SCHEMA_VERSION,
        "evidence": {
            "id": f"EVID-{safe_name.upper()}-{identity['commit'][:12]}",
            "claim_id": claim_id,
            "source_commit": identity["commit"],
            "collected_at": _timestamp(collected_at),
            "expires_at": _timestamp(collected_at + timedelta(hours=max_age)),
            "collector": {"type": "tool", "name": "collect_verification.py"},
        },
        "environment": environment,
        "command": {
            "argv": argv,
            "sandbox_argv": sandbox_argv,
            "network_isolation": "os-enforced",
            "exit_code": exit_code,
            "duration_ms": duration_ms,
        },
        "artifacts": artifacts,
        "result": {"status": result_status, "summary": summary},
        "freshness": {"policy": "commit-bound", "max_age_hours": max_age},
    }
    check = {
        "name": name,
        "argv": argv,
        "exit_code": exit_code,
        "duration_ms": duration_ms,
        "log": f"{safe_name}.log",
        "log_sha256": artifacts[0]["sha256"],
        "evidence_id": evidence["evidence"]["id"],
    }
    return check, evidence


def _atomic_write_json(path: Path, value: object) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _publish_latest(final: Path, latest: Path, pointer: Path, pointer_data: dict[str, Any]) -> None:
    candidate = latest.with_name(latest.name + ".new")
    backup = latest.with_name(latest.name + ".old")
    shutil.rmtree(candidate, ignore_errors=True)
    shutil.copytree(final, candidate)
    if backup.exists():
        shutil.rmtree(backup)
    if latest.exists():
        os.replace(latest, backup)
    os.replace(candidate, latest)
    shutil.rmtree(backup, ignore_errors=True)
    _atomic_write_json(pointer, pointer_data)


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect immutable source-bound verification evidence")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    staging: Path | None = None
    lock: Path | None = None
    evidence_backup = None
    protected_evidence_state: tuple[tuple[str, str], ...] = ()
    protected_exclusions: set[str] = set()
    try:
        root = args.root.resolve()
        if not root.is_dir():
            raise ValueError(f"repository root does not exist: {root}")
        _require_repository_root(root)
        output = args.output.resolve()
        output_relative = _relative_to_root(root, output, "output")
        if output_relative == Path("."):
            raise ValueError("output must be a dedicated directory below the repository root")
        evidence_root = output.parent
        evidence_relative = _relative_to_root(root, evidence_root, "evidence root")
        evidence_root.mkdir(parents=True, exist_ok=True)
        runs = evidence_root / "runs"
        runs.mkdir(exist_ok=True)
        lock = evidence_root / ".collect.lock"
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(descriptor)
        except FileExistsError as exc:
            raise ValueError("another verification collection is active") from exc

        protected_exclusions = {lock.name}
        protected_evidence_state = _evidence_tree_state(
            evidence_root, excluded_top_level=protected_exclusions
        )
        evidence_backup = _archive_prior_evidence(
            evidence_root, excluded_top_level=protected_exclusions
        )

        config = _load_config(args.config)
        identity = _repository_identity(root)
        dirty = sorted(path for path in _changed_paths(root) if not _is_under(path, evidence_relative))
        if dirty:
            raise ValueError("repository has non-output changes before verification: " + ", ".join(dirty))

        run_id = _run_id(identity["commit"])
        staging = evidence_root / f".tmp-{run_id}"
        final = runs / run_id
        staging.mkdir()
        protected_exclusions.add(staging.name)
        event_log = staging / "events.jsonl"
        append_event(event_log, run_id=run_id, event_type="run.started", actor={"role": "collector"}, payload={"source": identity})
        environment = _environment(config)
        checks: list[dict[str, Any]] = []
        evidence_records: list[dict[str, Any]] = []
        artifact_prefix = evidence_relative / "runs" / run_id
        names = _unique_names(config["commands"])
        for index, item in enumerate(config["commands"]):
            check, record = _run_one(
                root=root,
                staging=staging,
                artifact_prefix=artifact_prefix,
                identity=identity,
                environment=environment,
                item=item,
                index=index,
                safe_name=names[index],
            )
            checks.append(check)
            evidence_records.append(record)
            current_evidence_state = _evidence_tree_state(
                evidence_root, excluded_top_level=protected_exclusions
            )
            if current_evidence_state != protected_evidence_state:
                assert evidence_backup is not None
                _restore_prior_evidence(
                    evidence_root,
                    evidence_backup,
                    excluded_top_level=protected_exclusions,
                )
                raise ValueError("immutable evidence changed during verification")
            dirty = sorted(path for path in _changed_paths(root) if not _is_under(path, evidence_relative))
            if dirty:
                raise ValueError("verification command changed non-output repository paths: " + ", ".join(dirty))
            if _repository_identity(root) != identity:
                raise ValueError("repository identity changed during verification")
            append_event(event_log, run_id=run_id, event_type="verification.completed", actor={"role": "collector"}, payload=check)

        report = {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "source": {"commit": identity["commit"], "dirty": False},
            "repository_identity": identity,
            "generated_at": _timestamp(_utc_now()),
            "environment": environment,
            "checks": checks,
            "evidence": evidence_records,
            "summary": {
                "passed": sum(item["exit_code"] == 0 for item in checks),
                "failed": sum(item["exit_code"] != 0 for item in checks),
            },
        }
        report_path = staging / "report.json"
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        append_event(event_log, run_id=run_id, event_type="report.completed", actor={"role": "collector"}, payload=report["summary"])
        manifest = build_run_manifest(
            run_id=run_id,
            source_commit=identity["commit"],
            source_tree=identity["tree"],
            branch=identity["branch"],
            event_log=event_log,
            report=report_path,
            metadata={"environment": environment},
        )
        (staging / "run-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(staging, final)
        staging = None
        pointer_data = {
            "schema_version": "1.0",
            "run_id": run_id,
            "run_path": (evidence_relative / "runs" / run_id).as_posix(),
            "source_commit": identity["commit"],
            "report_sha256": file_sha256(final / "report.json"),
        }
        _publish_latest(final, output, evidence_root / "latest.json", pointer_data)
        print(json.dumps(report["summary"]))
        return 0 if report["summary"]["failed"] == 0 else 1
    except (OSError, ValueError, RunnerSupportError, yaml.YAMLError) as exc:
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)
        print(f"VERIFICATION COLLECTION: FAIL\n- {exc}", file=sys.stderr)
        return 1
    finally:
        if evidence_backup is not None:
            evidence_backup.close()
        if lock is not None:
            try:
                lock.unlink(missing_ok=True)
            except OSError:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
