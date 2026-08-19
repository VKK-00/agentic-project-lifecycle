from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "plugins/agentic-project-lifecycle/skills/auditing-project-readiness/scripts"
sys.path.insert(0, str(SCRIPTS))

from governance.execution_result import (  # noqa: E402
    build_execution_result,
    contract_digest,
    validate_execution_result,
)


def git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def init_repo(root: Path) -> str:
    root.mkdir(parents=True)
    git(root, "init", "-q")
    git(root, "config", "user.name", "Test User")
    git(root, "config", "user.email", "test@example.com")
    (root / "src").mkdir()
    (root / "tests").mkdir()
    (root / "src/app.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "tests/test_app.py").write_text("def test_value():\n    assert True\n", encoding="utf-8")
    (root / "pyproject.toml").write_text('[project]\nname="fixture"\ndependencies=[]\n', encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-qm", "base")
    return git(root, "rev-parse", "HEAD")


def task_contract(base: str, *, max_files: int = 4, max_lines: int = 100, max_deps: int = 0) -> dict:
    command = "python -m pytest -q"
    return {
        "schema_version": "1.0",
        "task": {
            "id": "TASK-EXEC-001",
            "objective": "Change the application within approved scope",
            "kind": "feature",
            "source_commit": base,
            "risk_level": "high",
            "current_gate": "implementation",
        },
        "scope": {
            "allowed_paths": ["src/**", "tests/**", "pyproject.toml"],
            "forbidden_paths": [".github/**", "migrations/**"],
            "max_changed_files": max_files,
            "max_diff_lines": max_lines,
            "max_new_dependencies": max_deps,
        },
        "permissions": {
            "filesystem": "workspace-write-scoped",
            "network": "disabled",
            "allowed_commands": [command],
            "forbidden_command_patterns": ["git push"],
            "dependency_changes": "forbidden" if max_deps == 0 else "approval-required",
            "destructive_actions": "forbidden",
            "production_actions": "forbidden",
        },
        "plan": {
            "id": "PLAN-EXEC-001",
            "status": "approved",
            "steps": [
                {
                    "id": "STEP-001",
                    "addresses": ["REQ-001"],
                    "action": "Change src/app.py",
                    "expected_changes": "Application and tests",
                    "verification_commands": [command],
                }
            ],
        },
        "approval": {
            "required": True,
            "status": "approved",
            "approved_by": "alice",
            "approved_at": "2026-08-18T00:00:00Z",
            "source_commit": base,
        },
        "rollback": {
            "checkpoint_commit": base,
            "strategy": "reset-to-checkpoint",
            "preserve_failed_diff": True,
        },
        "completion": {"required_evidence": ["unit_tests", "diff_review"]},
    }


def commit_change(root: Path, path: str, content: str, message: str = "change") -> str:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", message)
    return git(root, "rev-parse", "HEAD")


def test_build_and_validate_allowed_actual_diff(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    base = init_repo(root)
    head = commit_change(root, "src/app.py", "VALUE = 2\n")
    contract = task_contract(base)

    result = build_execution_result(root=root, contract=contract, head_commit=head)

    assert result["execution"]["base_commit"] == base
    assert result["execution"]["head_commit"] == head
    assert result["execution"]["task_contract_sha256"] == contract_digest(contract)
    assert result["change_set"]["total_changed_files"] == 1
    assert result["change_set"]["changed_files"][0]["path"] == "src/app.py"
    assert validate_execution_result(result, contract=contract, root=root) == []


def test_execution_rejects_path_outside_allowlist(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    base = init_repo(root)
    head = commit_change(root, "docs/escape.md", "not allowed\n")
    contract = task_contract(base)
    result = build_execution_result(root=root, contract=contract, head_commit=head)

    errors = validate_execution_result(result, contract=contract, root=root)

    assert "changed path is outside allowed scope: docs/escape.md" in errors


def test_execution_enforces_changed_file_and_diff_budgets(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    base = init_repo(root)
    (root / "src/app.py").write_text("VALUE = 2\nEXTRA = 3\n", encoding="utf-8")
    (root / "tests/test_app.py").write_text("def test_value():\n    assert True\n    assert 1\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "large")
    contract = task_contract(base, max_files=1, max_lines=1)
    result = build_execution_result(root=root, contract=contract, head_commit="HEAD")

    errors = validate_execution_result(result, contract=contract, root=root)

    assert "changed file budget exceeded: 2 > 1" in errors
    assert any(error.startswith("diff line budget exceeded:") for error in errors)


def test_execution_rejects_deletion_without_explicit_scope_permission(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    base = init_repo(root)
    (root / "tests/test_app.py").unlink()
    git(root, "add", "-A")
    git(root, "commit", "-qm", "delete test")
    contract = task_contract(base)
    result = build_execution_result(root=root, contract=contract, head_commit="HEAD")

    errors = validate_execution_result(result, contract=contract, root=root)

    assert "file deletion is not permitted: tests/test_app.py" in errors


def test_execution_counts_new_python_dependencies(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    base = init_repo(root)
    head = commit_change(
        root,
        "pyproject.toml",
        '[project]\nname="fixture"\ndependencies=["requests>=2", "rich>=13"]\n',
        "dependencies",
    )
    contract = task_contract(base, max_deps=1)
    result = build_execution_result(root=root, contract=contract, head_commit=head)

    assert result["change_set"]["new_dependencies"] == ["requests", "rich"]
    assert "new dependency budget exceeded: 2 > 1" in validate_execution_result(
        result, contract=contract, root=root
    )


def test_execution_rejects_contract_digest_tampering(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    base = init_repo(root)
    commit_change(root, "src/app.py", "VALUE = 2\n")
    contract = task_contract(base)
    result = build_execution_result(root=root, contract=contract, head_commit="HEAD")
    result["execution"]["task_contract_sha256"] = "0" * 64

    assert "execution task contract digest does not match approved contract" in validate_execution_result(
        result, contract=contract, root=root
    )


def test_execution_requires_head_descendant_of_source_commit(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    base = init_repo(root)
    git(root, "checkout", "--orphan", "unrelated")
    git(root, "rm", "-rf", ".")
    (root / "src").mkdir(exist_ok=True)
    (root / "src/app.py").write_text("VALUE = 9\n", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-qm", "unrelated")
    contract = task_contract(base)

    try:
        build_execution_result(root=root, contract=contract, head_commit="HEAD")
    except ValueError as exc:
        assert "head commit is not a descendant of task source commit" in str(exc)
    else:
        raise AssertionError("unrelated execution lineage was accepted")


def test_execution_cli_emits_json(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    base = init_repo(root)
    commit_change(root, "src/app.py", "VALUE = 2\n")
    contract = task_contract(base)
    task_path = root / "task.yaml"
    task_path.write_text(yaml.safe_dump(contract, sort_keys=False), encoding="utf-8")
    result = build_execution_result(root=root, contract=contract, head_commit="HEAD")
    result_path = root / "execution.json"
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    script = SCRIPTS / "validate_execution_result.py"

    completed = subprocess.run(
        [sys.executable, str(script), str(result_path), "--task", str(task_path), "--root", str(root), "--format", "json"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert json.loads(completed.stdout)["pass"] is True
