"""Tamper-evident event logs and source-bound run manifests."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any

_SECRET_KEY_RE = re.compile(r"(?i)(?:password|passwd|secret|token|api[_-]?key|authorization|credential|private[_-]?key)")
_SECRET_VALUE_PATTERNS = (
    re.compile(
        r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----.*?"
        r"-----END (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----",
        re.DOTALL,
    ),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{12,}\b"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}"),
)


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def redact_text(value: str) -> str:
    result = value
    for pattern in _SECRET_VALUE_PATTERNS:
        result = pattern.sub("[REDACTED]", result)
    return result


def redact(value: Any, *, key: str | None = None) -> Any:
    if key is not None and _SECRET_KEY_RE.search(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(item_key): redact(item_value, key=str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def _timestamp(value: datetime | None = None) -> str:
    return (value or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_events(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            parsed = json.loads(line)
            if not isinstance(parsed, dict):
                raise ValueError("event log entries must be objects")
            events.append(parsed)
    return events


def append_event(
    path: Path,
    *,
    run_id: str,
    event_type: str,
    actor: dict[str, Any],
    payload: dict[str, Any],
    timestamp: datetime | None = None,
) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    events = _read_events(path)
    previous_hash = events[-1].get("event_hash") if events else "0" * 64
    event: dict[str, Any] = {
        "event_id": f"EVT-{len(events) + 1:06d}",
        "run_id": run_id,
        "timestamp": _timestamp(timestamp),
        "type": event_type,
        "actor": redact(actor),
        "payload": redact(payload),
        "previous_hash": previous_hash,
    }
    event["event_hash"] = sha256_bytes(_canonical(event))
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return event


def verify_event_log(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        events = _read_events(path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [f"cannot parse event log: {exc}"]
    previous = "0" * 64
    run_id: str | None = None
    for index, event in enumerate(events, start=1):
        if event.get("event_id") != f"EVT-{index:06d}":
            errors.append(f"event sequence mismatch at line {index}")
        if run_id is None:
            run_id = str(event.get("run_id", ""))
        elif event.get("run_id") != run_id:
            errors.append(f"event run id mismatch at line {index}")
        if event.get("previous_hash") != previous:
            errors.append(f"event previous hash mismatch at line {index}")
        supplied = event.get("event_hash")
        unsigned = dict(event)
        unsigned.pop("event_hash", None)
        calculated = sha256_bytes(_canonical(unsigned))
        if supplied != calculated:
            errors.append(f"event hash mismatch at line {index}")
        previous = str(supplied or "")
    return errors


def build_run_manifest(
    *,
    run_id: str,
    source_commit: str,
    source_tree: str,
    branch: str,
    event_log: Path,
    report: Path | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "schema_version": "1.0",
        "run": {
            "id": run_id,
            "source_commit": source_commit,
            "source_tree": source_tree,
            "branch": branch,
        },
        "event_log": {
            "path": event_log.name,
            "sha256": file_sha256(event_log),
            "size_bytes": event_log.stat().st_size,
        },
        "metadata": redact(metadata or {}),
    }
    if report is not None:
        manifest["report"] = {
            "path": report.name,
            "sha256": file_sha256(report),
            "size_bytes": report.stat().st_size,
        }
    return manifest


def validate_run_manifest(manifest: object, *, event_log: Path, report: Path | None = None) -> list[str]:
    errors: list[str] = []
    if not isinstance(manifest, dict):
        return ["run manifest root must be a mapping"]
    if manifest.get("schema_version") != "1.0":
        errors.append("run manifest schema_version must be 1.0")
    run = manifest.get("run")
    if not isinstance(run, dict) or not run.get("id"):
        errors.append("run.id is required")
    event = manifest.get("event_log")
    if not isinstance(event, dict):
        errors.append("event_log must be a mapping")
    else:
        if not event_log.is_file() or event.get("sha256") != file_sha256(event_log):
            errors.append("run manifest event-log digest mismatch")
        elif event.get("size_bytes") != event_log.stat().st_size:
            errors.append("run manifest event-log size mismatch")
    errors.extend(verify_event_log(event_log))
    if report is not None:
        record = manifest.get("report")
        if not isinstance(record, dict):
            errors.append("report must be a mapping")
        elif not report.is_file() or record.get("sha256") != file_sha256(report):
            errors.append("run manifest report digest mismatch")
        elif record.get("size_bytes") != report.stat().st_size:
            errors.append("run manifest report size mismatch")
    return errors
