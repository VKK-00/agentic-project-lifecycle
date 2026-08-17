from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
AUDIT_SCRIPTS = (
    REPO_ROOT
    / "plugins"
    / "agentic-project-lifecycle"
    / "skills"
    / "auditing-project-readiness"
    / "scripts"
)
sys.path.insert(0, str(AUDIT_SCRIPTS))

from governance_contracts import (  # noqa: E402
    validate_evidence_record,
    validate_task_contract,
)

COLLECTOR = AUDIT_SCRIPTS / "collect_verification.py"
COMMIT = "a" * 40
OTHER_COMMIT = "b" * 40


def valid_task_contract() -> dict:
    command = "python -m pytest tests/test_widget.py -q"
    return {
        "schema_version": "1.0",
        "task": {
            "id": "TASK-001",
            "objective": "Implement one bounded widget behavior",
            "kind": "feature",
            "source_commit": COMMIT,
            "risk_level": "high",
            "current_gate": "implementation",
        },
        "scope": {
            "allowed_paths": ["src/widget/**", "tests/widget/**"],
            "forbidden_paths": [".github/**", "migrations/**"],
            "max_changed_files": 8,
            "max_diff_lines": 500,
            "max_new_dependencies": 0,
        },
        "permissions": {
            "filesystem": "workspace-write-scoped",
            "network": "disabled",
            "allowed_commands": [command],
            "forbidden_command_patterns": ["rm -rf", "git push"],
            "dependency_changes": "forbidden",
            "destructive_actions": "forbidden",
            "production_actions": "forbidden",
        },
        "plan": {
            "id": "PLAN-001",
            "status": "approved",
            "steps": [
                {
                    "id": "STEP-001",
                    "addresses": ["REQ-001"],
                    "action": "Add the validated widget behavior",
                    "expected_changes": "Widget implementation and focused tests",
                    "verification_commands": [command],
                }
            ],
        },
        "approval": {
            "required": True,
            "status": "approved",
            "approved_by": "alice",
            "approved_at": "2026-08-17T18:00:00Z",
            "source_commit": COMMIT,
        },
        "rollback": {
            "checkpoint_commit": COMMIT,
            "strategy": "reset-to-checkpoint",
            "preserve_failed_diff": True,
        },
        "completion": {"required_evidence": ["observed_verification"]},
    }


def valid_evidence_record() -> dict:
    return {
        "schema_version": "1.0",
        "evidence": {
            "id": "EVID-001",
            "claim_id": "CLAIM-001",
            "source_commit": COMMIT,
            "collected_at": "2026-08-17T18:00:00Z",
            "expires_at": "2026-08-18T18:00:00Z",
            "collector": {"type": "tool", "name": "pytest"},
        },
        "environment": {
            "working_directory": ".",
            "platform": "linux",
            "python_version": "3.12.1",
            "tool_versions": {"pytest": "9.0.2"},
        },
        "command": {
            "argv": ["python", "-m", "pytest", "-q"],
            "exit_code": 0,
            "duration_ms": 123,
        },
        "artifacts": [
            {
                "path": "logs/pytest.log",
                "sha256": "0" * 64,
                "size_bytes": 42,
            }
        ],
        "result": {"status": "pass", "summary": "All selected tests passed"},
        "freshness": {"policy": "commit-bound", "max_age_hours": 24},
    }


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )


def init_git_repository(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    assert git(root, "init", "-q").returncode == 0
    assert git(root, "config", "user.name", "Test User").returncode == 0
    assert git(root, "config", "user.email", "test@example.com").returncode == 0
    (root / "README.md").write_text("fixture\n", encoding="utf-8")
    assert git(root, "add", ".").returncode == 0
    assert git(root, "commit", "-qm", "initial fixture").returncode == 0


def write_verification_config(root: Path, argv: list[str]) -> Path:
    path = root / "verification.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "commands": [
                    {
                        "name": "check",
                        "claim_id": "CLAIM-CHECK",
                        "run": argv,
                        "timeout_seconds": 10,
                        "max_age_hours": 24,
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    assert git(root, "add", "verification.yaml").returncode == 0
    assert git(root, "commit", "-qm", "add verification config").returncode == 0
    return path


def run_collector(
    root: Path, config: Path, output: Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(COLLECTOR),
            "--root",
            str(root),
            "--config",
            str(config),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )


def test_elevated_permissions_require_explicit_source_bound_approval() -> None:
    contract = valid_task_contract()
    contract["task"]["risk_level"] = "low"
    contract["permissions"]["network"] = "allowlist"
    contract["permissions"]["allowed_domains"] = ["pypi.org"]
    contract["approval"] = {"required": False, "status": "approved"}

    errors = validate_task_contract(contract)

    assert "elevated permissions require approval.required true" in errors
    assert "approval.approved_by is required" in errors
    assert "approval.approved_at is required" in errors
    assert "approval.source_commit must be a full lowercase Git commit SHA" in errors


def test_write_rollback_checkpoint_must_match_task_source_commit() -> None:
    contract = valid_task_contract()
    contract["rollback"]["checkpoint_commit"] = OTHER_COMMIT

    assert (
        "rollback checkpoint is not bound to the task source commit"
        in validate_task_contract(contract)
    )


def test_evidence_rejects_collection_time_materially_in_the_future() -> None:
    evidence = valid_evidence_record()
    evidence["evidence"]["collected_at"] = "2026-08-17T20:00:01Z"
    evidence["evidence"]["expires_at"] = "2026-08-18T20:00:01Z"
    now = datetime(2026, 8, 17, 19, 55, tzinfo=timezone.utc)

    assert "evidence.collected_at is in the future" in validate_evidence_record(
        evidence, now=now
    )


def test_collect_verification_rejects_repository_root_as_output(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    init_git_repository(root)
    config = write_verification_config(root, [sys.executable, "-c", "print('ok')"])

    result = run_collector(root, config, root)

    assert result.returncode == 1
    assert "output must be a dedicated directory below the repository root" in (
        result.stdout + result.stderr
    )


def test_collect_verification_rejects_source_changes_made_by_command(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    init_git_repository(root)
    config = write_verification_config(
        root,
        [
            sys.executable,
            "-c",
            "from pathlib import Path; Path('README.md').write_text('mutated\\n')",
        ],
    )

    result = run_collector(root, config, root / "evidence" / "latest")

    assert result.returncode == 1
    assert "verification command changed non-output repository paths" in (
        result.stdout + result.stderr
    )
    assert not (root / "evidence/latest/report.json").exists()
