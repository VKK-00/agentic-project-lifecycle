from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import sys

SCRIPTS = (
    Path(__file__).resolve().parents[1]
    / "plugins"
    / "agentic-project-lifecycle"
    / "skills"
    / "auditing-project-readiness"
    / "scripts"
)
sys.path.insert(0, str(SCRIPTS))

from governance_contracts import (  # noqa: E402
    validate_evidence_record,
    validate_gate_transition,
    validate_task_contract,
)

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
        "completion": {
            "required_evidence": [
                "test_result",
                "diff_review",
                "verifier_decision",
            ]
        },
    }


def valid_gate_transition() -> dict:
    return {
        "schema_version": "1.0",
        "transition": {
            "id": "GATE-001",
            "project_id": "PROJECT-001",
            "type": "advance",
            "from": "planning",
            "to": "implementation",
            "requested_at": "2026-08-17T18:00:00Z",
            "source_commit": COMMIT,
        },
        "outcome": {
            "id": "OUTCOME-001",
            "statement": "The bounded implementation slice is ready to start",
            "owner": "alice",
        },
        "conditions": [
            {
                "id": "COND-001",
                "status": "satisfied",
                "evidence": ["EVID-001"],
            }
        ],
        "evidence": [
            {
                "id": "EVID-001",
                "path": "evidence/EVID-001.yaml",
                "status": "pass",
                "source_commit": COMMIT,
            }
        ],
        "approvals": [
            {
                "role": "engineering",
                "required": True,
                "decision": "approved",
                "actor": "alice",
                "decided_at": "2026-08-17T18:05:00Z",
                "source_commit": COMMIT,
            }
        ],
        "blockers": [],
        "residual_risks": [],
        "policy": {
            "hard_blocker_behavior": "stop-dependent-work",
            "allow_phase_skip": False,
        },
        "decision": {
            "status": "approved",
            "decided_by": "alice",
            "decided_at": "2026-08-17T18:10:00Z",
            "rationale": "All entry conditions and approvals are present",
        },
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


def test_valid_task_contract_passes() -> None:
    assert validate_task_contract(valid_task_contract()) == []


def test_task_contract_requires_approved_plan_for_write() -> None:
    contract = valid_task_contract()
    contract["plan"]["status"] = "draft"
    assert "writable task requires an approved plan" in validate_task_contract(contract)


def test_task_contract_rejects_path_traversal() -> None:
    contract = valid_task_contract()
    contract["scope"]["allowed_paths"] = ["../outside/**"]
    assert any(
        "scope.allowed_paths[0] must be repository-relative" in item
        for item in validate_task_contract(contract)
    )


def test_task_contract_requires_verification_command_permission() -> None:
    contract = valid_task_contract()
    contract["permissions"]["allowed_commands"] = []
    assert any(
        "verification command is not allowed" in item
        for item in validate_task_contract(contract)
    )


def test_high_risk_task_requires_source_bound_approval() -> None:
    contract = valid_task_contract()
    contract["approval"]["status"] = "pending"
    contract["approval"].pop("approved_by")
    assert "high-risk task requires approved human authorization" in validate_task_contract(
        contract
    )


def test_production_actions_cannot_be_enabled() -> None:
    contract = valid_task_contract()
    contract["permissions"]["production_actions"] = "allowed"
    assert "production actions must remain forbidden" in validate_task_contract(contract)


def test_valid_gate_transition_passes() -> None:
    assert validate_gate_transition(valid_gate_transition()) == []


def test_approved_gate_cannot_have_open_hard_blocker() -> None:
    transition = valid_gate_transition()
    transition["blockers"] = [
        {
            "id": "BLK-001",
            "class": "hard",
            "status": "open",
            "owner": "alice",
            "reason": "Unsafe migration",
        }
    ]
    assert (
        "approved transition has an open hard blocker BLK-001"
        in validate_gate_transition(transition)
    )


def test_soft_blocker_requires_owned_residual_risk() -> None:
    transition = valid_gate_transition()
    transition["blockers"] = [
        {
            "id": "BLK-002",
            "class": "soft",
            "status": "open",
            "owner": "alice",
            "reason": "Minor observability gap",
        }
    ]
    assert (
        "open soft blocker BLK-002 requires a residual-risk record"
        in validate_gate_transition(transition)
    )


def test_phase_skip_requires_explicit_policy_and_approval() -> None:
    transition = valid_gate_transition()
    transition["transition"]["from"] = "discovery"
    transition["transition"]["to"] = "planning"
    assert "phase skip is not permitted by policy" in validate_gate_transition(transition)


def test_approved_gate_requires_satisfied_conditions() -> None:
    transition = valid_gate_transition()
    transition["conditions"][0]["status"] = "pending"
    assert (
        "approved transition has unsatisfied condition COND-001"
        in validate_gate_transition(transition)
    )


def test_gate_evidence_must_match_transition_commit() -> None:
    transition = valid_gate_transition()
    transition["evidence"][0]["source_commit"] = OTHER_COMMIT
    assert (
        "evidence EVID-001 is not bound to the transition commit"
        in validate_gate_transition(transition)
    )


def test_valid_evidence_record_passes() -> None:
    now = datetime(2026, 8, 17, 19, 0, tzinfo=timezone.utc)
    assert validate_evidence_record(valid_evidence_record(), now=now) == []


def test_evidence_must_match_expected_commit() -> None:
    evidence = valid_evidence_record()
    now = datetime(2026, 8, 17, 19, 0, tzinfo=timezone.utc)
    assert (
        "evidence source commit does not match expected commit"
        in validate_evidence_record(evidence, expected_commit=OTHER_COMMIT, now=now)
    )


def test_evidence_result_must_match_exit_code() -> None:
    evidence = valid_evidence_record()
    evidence["command"]["exit_code"] = 2
    now = datetime(2026, 8, 17, 19, 0, tzinfo=timezone.utc)
    assert "pass result requires exit_code 0" in validate_evidence_record(
        evidence, now=now
    )


def test_evidence_rejects_expired_record() -> None:
    evidence = valid_evidence_record()
    now = datetime(2026, 8, 19, 19, 0, tzinfo=timezone.utc)
    assert "evidence is expired" in validate_evidence_record(evidence, now=now)


def test_evidence_rejects_invalid_artifact_digest() -> None:
    evidence = valid_evidence_record()
    evidence["artifacts"][0]["sha256"] = "not-a-digest"
    now = datetime(2026, 8, 17, 19, 0, tzinfo=timezone.utc)
    assert any(
        "artifacts[0].sha256 must be a lowercase SHA-256 digest" in item
        for item in validate_evidence_record(evidence, now=now)
    )


def test_validators_do_not_mutate_input() -> None:
    task = valid_task_contract()
    gate = valid_gate_transition()
    evidence = valid_evidence_record()
    originals = deepcopy((task, gate, evidence))
    validate_task_contract(task)
    validate_gate_transition(gate)
    validate_evidence_record(
        evidence, now=datetime(2026, 8, 17, 19, 0, tzinfo=timezone.utc)
    )
    assert (task, gate, evidence) == originals

import importlib.util
import subprocess
import yaml


def load_project_state_validator():
    path = SCRIPTS / "validate_project_state.py"
    spec = importlib.util.spec_from_file_location("project_state_validator", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.validate


def legacy_project_state() -> dict:
    return {
        "project": {
            "id": "PROJECT-001",
            "name": "Legacy",
            "type": "software",
            "mode": "brownfield",
        },
        "lifecycle": {"current_phase": "orientation", "status": "in-progress"},
        "current_outcome": {
            "id": "OUTCOME-001",
            "statement": "Orient the project",
            "metric": "Known scope",
            "target": "Documented",
        },
        "blockers": [],
        "artifacts": {},
    }


def artifact_record(path: str, *, status: str = "approved") -> dict:
    return {
        "status": status,
        "path": path,
        "owner": "alice",
        "source_commit": COMMIT,
        "approval": {
            "status": "approved",
            "approved_by": "alice",
            "approved_at": "2026-08-17T18:00:00Z",
            "source_commit": COMMIT,
        },
    }


def valid_project_state_v2(*, phase: str = "orientation", status: str = "in-progress") -> dict:
    artifacts = {}
    if phase in {"specification", "solution-design", "planning", "implementation", "release", "operations"}:
        artifacts.update(
            {
                "charter": artifact_record("docs/00-governance/PROJECT_CHARTER.md"),
                "prd": artifact_record("docs/02-product/PRD.md"),
            }
        )
    if phase in {"solution-design", "planning", "implementation", "release", "operations"}:
        artifacts["design"] = artifact_record("docs/04-architecture/DESIGN.md")
    if phase in {"planning", "implementation", "release", "operations"}:
        artifacts["plan"] = artifact_record("docs/05-planning/PLAN.md")
    if phase in {"release", "operations"}:
        artifacts.update(
            {
                "evidence": artifact_record(
                    "evidence/latest/report.yaml", status="verified"
                ),
                "release_plan": artifact_record(
                    "docs/05-planning/releases/v1.yaml"
                ),
                "runbook": artifact_record("docs/08-operations/RUNBOOK.md"),
            }
        )
    return {
        "schema_version": "2.0",
        "project": {
            "id": "PROJECT-001",
            "name": "Governed project",
            "type": "software",
            "mode": "brownfield",
            "owner": "alice",
        },
        "lifecycle": {
            "current_phase": phase,
            "status": status,
            "gate_id": "GATE-001",
            "source_commit": COMMIT,
        },
        "current_outcome": {
            "id": "OUTCOME-001",
            "statement": "Advance one bounded outcome",
            "metric": "Acceptance checks",
            "target": "All pass",
            "owner": "alice",
        },
        "blockers": [],
        "residual_risks": [],
        "artifacts": artifacts,
        "contracts": {"active_task": None, "active_transition": None},
    }


def materialize_project_state_files(root: Path, state: dict) -> None:
    for record in state.get("artifacts", {}).values():
        path = root / record["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("evidence\n", encoding="utf-8")


def test_strict_project_state_rejects_legacy_state(tmp_path: Path) -> None:
    path = tmp_path / "project-state.yaml"
    path.write_text(yaml.safe_dump(legacy_project_state()), encoding="utf-8")
    validate = load_project_state_validator()
    assert "strict mode requires project-state schema_version 2.0" in validate(
        path, strict=True, root=tmp_path
    )


def test_legacy_project_state_still_passes_without_strict_mode(tmp_path: Path) -> None:
    path = tmp_path / "project-state.yaml"
    path.write_text(yaml.safe_dump(legacy_project_state()), encoding="utf-8")
    validate = load_project_state_validator()
    assert validate(path, root=tmp_path) == []


def test_valid_project_state_v2_passes_strict_validation(tmp_path: Path) -> None:
    state = valid_project_state_v2(phase="implementation")
    materialize_project_state_files(tmp_path, state)
    path = tmp_path / "project-state.yaml"
    path.write_text(yaml.safe_dump(state, sort_keys=False), encoding="utf-8")
    validate = load_project_state_validator()
    assert validate(path, strict=True, root=tmp_path) == []


def test_v2_project_state_rejects_ready_with_hard_blocker(tmp_path: Path) -> None:
    state = valid_project_state_v2(status="ready")
    state["blockers"] = [
        {
            "id": "BLK-STATE-001",
            "class": "hard",
            "status": "open",
            "owner": "alice",
            "reason": "Critical acceptance check failed",
        }
    ]
    path = tmp_path / "project-state.yaml"
    path.write_text(yaml.safe_dump(state, sort_keys=False), encoding="utf-8")
    validate = load_project_state_validator()
    assert (
        "ready state cannot contain open hard blocker BLK-STATE-001"
        in validate(path, strict=True, root=tmp_path)
    )


def test_v2_project_state_validates_linked_task_contract(tmp_path: Path) -> None:
    state = valid_project_state_v2(phase="implementation")
    materialize_project_state_files(tmp_path, state)
    contract_path = tmp_path / "docs" / "contracts" / "task.yaml"
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    invalid_contract = valid_task_contract()
    invalid_contract["plan"]["status"] = "draft"
    contract_path.write_text(
        yaml.safe_dump(invalid_contract, sort_keys=False), encoding="utf-8"
    )
    state["contracts"]["active_task"] = "docs/contracts/task.yaml"
    state_path = tmp_path / "project-state.yaml"
    state_path.write_text(yaml.safe_dump(state, sort_keys=False), encoding="utf-8")
    validate = load_project_state_validator()
    assert any(
        error.startswith("active task contract: writable task requires an approved plan")
        for error in validate(state_path, strict=True, root=tmp_path)
    )


def run_validator_cli(script: str, path: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), str(path), *extra],
        text=True,
        capture_output=True,
        check=False,
    )


def test_task_contract_cli_reports_pass(tmp_path: Path) -> None:
    path = tmp_path / "task.yaml"
    path.write_text(yaml.safe_dump(valid_task_contract(), sort_keys=False), encoding="utf-8")
    result = run_validator_cli("validate_task_contract.py", path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.startswith("TASK CONTRACT: PASS")


def test_gate_transition_cli_reports_fail(tmp_path: Path) -> None:
    transition = valid_gate_transition()
    transition["conditions"][0]["status"] = "pending"
    path = tmp_path / "gate.yaml"
    path.write_text(yaml.safe_dump(transition, sort_keys=False), encoding="utf-8")
    result = run_validator_cli("validate_gate_transition.py", path)
    assert result.returncode == 1
    assert result.stdout.startswith("GATE TRANSITION: FAIL")
    assert "unsatisfied condition COND-001" in result.stdout


def test_evidence_cli_reports_pass_with_expected_commit(tmp_path: Path) -> None:
    path = tmp_path / "evidence.yaml"
    evidence = valid_evidence_record()
    evidence["evidence"]["expires_at"] = "2099-08-18T18:00:00Z"
    evidence["freshness"]["max_age_hours"] = 1_000_000
    path.write_text(yaml.safe_dump(evidence, sort_keys=False), encoding="utf-8")
    result = run_validator_cli("validate_evidence.py", path, "--expected-commit", COMMIT)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.startswith("EVIDENCE: PASS")

import hashlib
import json
import os

COLLECTOR = SCRIPTS / "collect_verification.py"
RELEASE_CHECKER = SCRIPTS / "check_release_readiness.py"


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )


def init_git_repository(root: Path) -> str:
    root.mkdir(parents=True, exist_ok=True)
    assert git(root, "init", "-q").returncode == 0
    assert git(root, "config", "user.name", "Test User").returncode == 0
    assert git(root, "config", "user.email", "test@example.com").returncode == 0
    marker = root / "README.md"
    marker.write_text("fixture\n", encoding="utf-8")
    assert git(root, "add", ".").returncode == 0
    assert git(root, "commit", "-qm", "initial fixture").returncode == 0
    result = git(root, "rev-parse", "HEAD")
    assert result.returncode == 0
    return result.stdout.strip()


def write_verification_config(root: Path) -> Path:
    path = root / "verification.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "tool_versions": {"python": sys.version.split()[0]},
                "commands": [
                    {
                        "name": "unit",
                        "claim_id": "CLAIM-UNIT",
                        "run": [
                            sys.executable,
                            "-c",
                            "print('verified')",
                        ],
                        "timeout_seconds": 10,
                        "max_age_hours": 24,
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    assert git(root, "add", "verification.yaml").returncode == 0
    assert git(root, "commit", "-qm", "add verification config").returncode == 0
    return path


def run_collector(root: Path, config: Path, output: Path) -> subprocess.CompletedProcess[str]:
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


def test_collect_verification_emits_source_bound_evidence(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    init_git_repository(root)
    config = write_verification_config(root)
    expected_commit = git(root, "rev-parse", "HEAD").stdout.strip()
    output = root / "evidence" / "latest"

    result = run_collector(root, config, output)

    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert report["schema_version"] == "1.0"
    assert report["source"] == {"commit": expected_commit, "dirty": False}
    assert report["summary"] == {"passed": 1, "failed": 0}
    assert len(report["evidence"]) == 1
    record = report["evidence"][0]
    assert record["evidence"]["source_commit"] == expected_commit
    assert record["evidence"]["claim_id"] == "CLAIM-UNIT"
    assert record["command"]["exit_code"] == 0
    assert record["result"]["status"] == "pass"
    assert record["freshness"] == {"policy": "commit-bound", "max_age_hours": 24}
    log_path = output / "unit.log"
    assert record["artifacts"][0]["sha256"] == hashlib.sha256(
        log_path.read_bytes()
    ).hexdigest()
    assert validate_evidence_record(record, expected_commit=expected_commit) == []


def create_release_fixture(root: Path) -> tuple[str, Path]:
    root.mkdir(parents=True, exist_ok=True)
    required = [
        root / "docs/07-release/ROLLBACK.md",
        root / "docs/08-operations/OBSERVABILITY.md",
        root / "docs/08-operations/RUNBOOK.md",
    ]
    for path in required:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {path.stem}\n", encoding="utf-8")
    release = root / "docs/05-planning/releases/v1.yaml"
    release.parent.mkdir(parents=True, exist_ok=True)
    release.write_text(
        yaml.safe_dump(
            {
                "version": "v1",
                "stage": "internal-alpha",
                "owner": "alice",
                "support_owner": "bob",
                "audience": ["internal-testers"],
                "hypothesis": "The bounded change is usable",
                "included": ["widget"],
                "excluded": ["production rollout"],
                "entry_criteria": ["verification passes"],
                "exit_criteria": ["no critical regression"],
                "metrics": ["critical journey success"],
                "known_limitations": ["internal only"],
                "rollout": ["local smoke"],
                "rollback": ["revert release commit"],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    init_git_repository(root)
    # init_git_repository adds README after files exist, then commits every file.
    config = write_verification_config(root)
    commit = git(root, "rev-parse", "HEAD").stdout.strip()
    output = root / "evidence" / "latest"
    result = run_collector(root, config, output)
    assert result.returncode == 0, result.stdout + result.stderr
    return commit, output


def run_release_checker(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(RELEASE_CHECKER),
            "--root",
            str(root),
            "--release",
            "v1",
        ],
        text=True,
        capture_output=True,
        check=False,
    )


def test_release_readiness_accepts_fresh_matching_evidence(tmp_path: Path) -> None:
    root = tmp_path / "release"
    create_release_fixture(root)
    result = run_release_checker(root)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.startswith("RELEASE READINESS: PASS")


def test_release_readiness_rejects_commit_mismatch(tmp_path: Path) -> None:
    root = tmp_path / "release"
    _, output = create_release_fixture(root)
    report_path = output / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["source"]["commit"] = OTHER_COMMIT
    report["evidence"][0]["evidence"]["source_commit"] = OTHER_COMMIT
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    result = run_release_checker(root)

    assert result.returncode == 1
    assert "verification evidence source commit does not match repository HEAD" in result.stdout


def test_release_readiness_rejects_expired_evidence(tmp_path: Path) -> None:
    root = tmp_path / "release"
    _, output = create_release_fixture(root)
    report_path = output / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["evidence"][0]["evidence"]["expires_at"] = "2000-01-01T00:00:00Z"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    result = run_release_checker(root)

    assert result.returncode == 1
    assert "evidence[0]: evidence is expired" in result.stdout


def test_release_readiness_rejects_dirty_source_changes(tmp_path: Path) -> None:
    root = tmp_path / "release"
    create_release_fixture(root)
    (root / "README.md").write_text("changed after verification\n", encoding="utf-8")

    result = run_release_checker(root)

    assert result.returncode == 1
    assert "repository has non-evidence changes after verification" in result.stdout


def test_collect_verification_rejects_dirty_source(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    init_git_repository(root)
    config = write_verification_config(root)
    (root / "README.md").write_text("dirty before verification\n", encoding="utf-8")

    result = run_collector(root, config, root / "evidence" / "latest")

    assert result.returncode == 1
    assert "repository has non-output changes before verification" in (
        result.stdout + result.stderr
    )


def test_release_readiness_rejects_artifact_digest_mismatch(tmp_path: Path) -> None:
    root = tmp_path / "release"
    _, output = create_release_fixture(root)
    (output / "unit.log").write_text("tampered\n", encoding="utf-8")

    result = run_release_checker(root)

    assert result.returncode == 1
    assert "evidence[0]: artifact digest mismatch" in result.stdout

SCAFFOLD = (
    Path(__file__).resolve().parents[1]
    / "plugins"
    / "agentic-project-lifecycle"
    / "skills"
    / "orchestrating-large-projects"
    / "scripts"
    / "scaffold_project.py"
)


def run_scaffold(root: Path, command: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCAFFOLD),
            command,
            "--root",
            str(root),
            *args,
        ],
        text=True,
        capture_output=True,
        check=False,
    )


def test_init_scaffold_creates_strict_project_state_v2(tmp_path: Path) -> None:
    root = tmp_path / "project"
    init_git_repository(root)

    result = run_scaffold(
        root,
        "init",
        "--project-name",
        "Governed Portal",
        "--owner",
        "alice",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    state_path = root / "docs/project-state.yaml"
    state = yaml.safe_load(state_path.read_text(encoding="utf-8"))
    assert state["schema_version"] == "2.0"
    validate = load_project_state_validator()
    assert validate(state_path, strict=True, root=root) == []


def test_feature_scaffold_creates_valid_source_bound_task_contract(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    expected_commit = init_git_repository(root)

    result = run_scaffold(
        root,
        "feature",
        "--id",
        "FEAT-001",
        "--name",
        "CSV Preview",
        "--owner",
        "alice",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    contract_path = root / "specs/FEAT-001-csv-preview/task-contract.yaml"
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    assert contract["task"]["source_commit"] == expected_commit
    assert validate_task_contract(contract) == []


def test_release_scaffold_creates_canonical_yaml_and_operator_markdown(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    init_git_repository(root)

    result = run_scaffold(
        root,
        "release",
        "--version",
        "v0.1-alpha",
        "--name",
        "Internal Alpha",
        "--owner",
        "alice",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    folder = root / "docs/05-planning/releases"
    yaml_path = folder / "v0.1-alpha.yaml"
    markdown_path = folder / "v0.1-alpha.md"
    assert yaml_path.is_file()
    assert markdown_path.is_file()
    release = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    for field in (
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
    ):
        assert release[field]

ORCHESTRATOR_ROOT = (
    Path(__file__).resolve().parents[1]
    / "plugins"
    / "agentic-project-lifecycle"
    / "skills"
    / "orchestrating-large-projects"
)
AUDITOR_ROOT = (
    Path(__file__).resolve().parents[1]
    / "plugins"
    / "agentic-project-lifecycle"
    / "skills"
    / "auditing-project-readiness"
)


def test_schema_descriptors_name_their_enforcing_validators() -> None:
    cases = [
        (
            ORCHESTRATOR_ROOT / "references/schemas/task-contract.schema.yaml",
            "task-contract",
            "validate_task_contract.py",
            {"task", "scope", "permissions", "plan", "approval", "rollback", "completion"},
        ),
        (
            ORCHESTRATOR_ROOT / "references/schemas/gate-transition.schema.yaml",
            "gate-transition",
            "validate_gate_transition.py",
            {"transition", "outcome", "conditions", "evidence", "approvals", "blockers", "residual_risks", "policy", "decision"},
        ),
        (
            AUDITOR_ROOT / "references/schemas/evidence-record.schema.yaml",
            "evidence-record",
            "validate_evidence.py",
            {"evidence", "environment", "command", "artifacts", "result", "freshness"},
        ),
    ]
    for path, kind, validator, required in cases:
        descriptor = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert descriptor["kind"] == kind
        assert descriptor["version"] == "1.0"
        assert descriptor["validator"].endswith(validator)
        assert set(descriptor["required_sections"]) == required


def test_orchestrator_routes_executable_work_through_bounded_contracts() -> None:
    skill = (ORCHESTRATOR_ROOT / "SKILL.md").read_text(encoding="utf-8").lower()
    reference = (ORCHESTRATOR_ROOT / "references/governance-contracts.md").read_text(
        encoding="utf-8"
    ).lower()
    combined = skill + "\n" + reference
    for phrase in (
        "bounded permissions",
        "hard blocker",
        "source-bound evidence",
        "rollback",
        "stop dependent work",
    ):
        assert phrase in combined


def test_auditor_requires_contract_validation_and_observed_evidence() -> None:
    skill = (AUDITOR_ROOT / "SKILL.md").read_text(encoding="utf-8").lower()
    contract = (AUDITOR_ROOT / "references/audit-contract.md").read_text(
        encoding="utf-8"
    ).lower()
    combined = skill + "\n" + contract
    for phrase in (
        "validate_task_contract.py",
        "validate_gate_transition.py",
        "validate_evidence.py",
        "source commit",
        "artifact digest",
        "agent statement",
    ):
        assert phrase in combined
