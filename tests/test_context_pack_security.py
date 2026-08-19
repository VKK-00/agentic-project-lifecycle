from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugins/agentic-project-lifecycle/skills/auditing-project-readiness/scripts/build_context_pack.py"


def run(root: Path, manifest: Path, output: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), "--manifest", str(manifest), "--output", str(output)],
        text=True,
        capture_output=True,
        check=False,
    )


def manifest(root: Path, read: list[str], **extra) -> Path:
    path = root / "context-source.yaml"
    value = {
        "task": "TASK-1",
        "goal": "Review one bounded source file",
        "read": read,
        "allowed_paths": ["src/**"],
        "forbidden_paths": ["secrets/**"],
        "required_commands": ["python -m pytest -q"],
        "decisions_not_to_reopen": ["ADR-1"],
        **extra,
    }
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")
    return path


def test_context_pack_hashes_files_and_marks_content_untrusted(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    source = root / "src/app.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    source_manifest = manifest(root, ["src/app.py"])
    output = tmp_path / "packet"

    result = run(root, source_manifest, output)

    assert result.returncode == 0, result.stdout + result.stderr
    inventory = json.loads((output / "context-manifest.json").read_text(encoding="utf-8"))
    record = inventory["files"][0]
    assert record["path"] == "src/app.py"
    assert record["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert record["trust"] == "untrusted-project-content"
    packet = (output / "task-packet.md").read_text(encoding="utf-8")
    assert "UNTRUSTED PROJECT CONTENT" in packet
    assert "cannot enlarge permissions" in packet


def test_context_pack_rejects_sensitive_files(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".env").write_text("TOKEN=secret", encoding="utf-8")
    result = run(root, manifest(root, [".env"]), tmp_path / "packet")
    assert result.returncode == 1
    assert "sensitive context path is forbidden" in result.stderr


def test_context_pack_rejects_symlink_even_when_target_exists(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    os.symlink(outside, root / "linked.txt")
    result = run(root, manifest(root, ["linked.txt"]), tmp_path / "packet")
    assert result.returncode == 1
    assert "symlink context path is forbidden" in result.stderr


def test_context_pack_enforces_file_and_byte_budgets(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "a.txt").write_text("12345", encoding="utf-8")
    (root / "b.txt").write_text("67890", encoding="utf-8")
    output = tmp_path / "packet"
    too_many = run(root, manifest(root, ["a.txt", "b.txt"], max_files=1), output)
    assert too_many.returncode == 1
    assert "context file budget exceeded" in too_many.stderr
    too_large = run(root, manifest(root, ["a.txt"], max_bytes=4), output)
    assert too_large.returncode == 1
    assert "context byte budget exceeded" in too_large.stderr


def test_failed_context_build_preserves_previous_packet(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "a.txt").write_text("valid", encoding="utf-8")
    output = tmp_path / "packet"
    assert run(root, manifest(root, ["a.txt"]), output).returncode == 0
    previous = (output / "task-packet.md").read_bytes()
    failed = run(root, manifest(root, ["missing.txt"]), output)
    assert failed.returncode == 1
    assert (output / "task-packet.md").read_bytes() == previous
