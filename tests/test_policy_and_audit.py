from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "plugins/agentic-project-lifecycle/skills/auditing-project-readiness/scripts"
POLICIES = ROOT / "plugins/agentic-project-lifecycle/skills/orchestrating-large-projects/references/policies"
sys.path.insert(0, str(SCRIPTS))

from governance.policy import (  # noqa: E402
    load_policy_profile,
    policy_digest,
    validate_policy_profile,
    validate_transition_policy,
)
from governance.project_audit import build_project_audit  # noqa: E402

BASE = "a" * 40
HEAD = "b" * 40


def profile() -> dict:
    return {
        "schema_version": "1.0",
        "policy": {
            "id": "default-software",
            "version": "1.0",
            "name": "Default software lifecycle",
            "minimum_approval_assurance": "declared",
            "protected_paths": [".github/**", "migrations/**"],
        },
        "gates": [
            {
                "id": "implementation-to-release",
                "from": "implementation",
                "to": "release",
                "required_claims": ["unit_tests", "integration_tests", "diff_conformance"],
                "required_roles": ["engineering-owner"],
                "non_waivable_blocker_classes": ["security-critical", "data-integrity"],
                "allow_phase_skip": False,
            }
        ],
    }


def transition(policy: dict | None = None) -> dict:
    policy = policy or profile()
    return {
        "schema_version": "1.0",
        "transition": {
            "id": "GATE-RELEASE",
            "project_id": "PROJECT-1",
            "type": "advance",
            "from": "implementation",
            "to": "release",
            "requested_at": "2026-08-18T00:00:00Z",
            "source_commit": HEAD,
        },
        "outcome": {"id": "OUT-1", "statement": "Candidate is ready for staged release", "owner": "alice"},
        "conditions": [
            {"id": "COND-1", "status": "satisfied", "evidence": ["E1", "E2", "E3"]}
        ],
        "evidence": [
            {"id": "E1", "claim_id": "unit_tests", "path": "evidence/unit.json", "status": "pass", "source_commit": HEAD},
            {"id": "E2", "claim_id": "integration_tests", "path": "evidence/integration.json", "status": "pass", "source_commit": HEAD},
            {"id": "E3", "claim_id": "diff_conformance", "path": "evidence/diff.json", "status": "pass", "source_commit": HEAD},
        ],
        "approvals": [
            {
                "role": "engineering-owner",
                "required": True,
                "decision": "approved",
                "actor": "alice",
                "assurance": "declared",
                "decided_at": "2026-08-18T00:01:00Z",
                "source_commit": HEAD,
            }
        ],
        "blockers": [],
        "residual_risks": [],
        "policy": {
            "hard_blocker_behavior": "stop-dependent-work",
            "allow_phase_skip": False,
            "profile_id": policy["policy"]["id"],
            "profile_version": policy["policy"]["version"],
            "profile_sha256": policy_digest(policy),
        },
        "decision": {"status": "approved", "decided_by": "alice", "decided_at": "2026-08-18T00:02:00Z", "rationale": "All policy requirements pass"},
    }


def task(policy: dict | None = None) -> dict:
    policy = policy or profile()
    command = "python -m pytest -q"
    return {
        "schema_version": "1.0",
        "task": {"id": "TASK-1", "objective": "Prepare release candidate", "kind": "feature", "source_commit": BASE, "risk_level": "high", "current_gate": "implementation"},
        "scope": {"allowed_paths": ["src/**", "tests/**"], "forbidden_paths": [".github/**"], "max_changed_files": 5, "max_diff_lines": 500, "max_new_dependencies": 0},
        "permissions": {"filesystem": "workspace-write-scoped", "network": "disabled", "allowed_commands": [command], "forbidden_command_patterns": ["git push"], "dependency_changes": "forbidden", "destructive_actions": "forbidden", "production_actions": "forbidden"},
        "plan": {"id": "PLAN-1", "status": "approved", "steps": [{"id": "STEP-1", "addresses": ["REQ-1"], "action": "Implement", "expected_changes": "Code and tests", "verification_commands": [command]}]},
        "approval": {"required": True, "status": "approved", "approved_by": "alice", "approved_at": "2026-08-18T00:00:00Z", "source_commit": BASE},
        "rollback": {"checkpoint_commit": BASE, "strategy": "reset-to-checkpoint", "preserve_failed_diff": True},
        "completion": {"required_evidence": ["unit_tests", "integration_tests", "diff_conformance"]},
        "policy": {"profile_id": policy["policy"]["id"], "profile_version": policy["policy"]["version"], "profile_sha256": policy_digest(policy)},
    }


def execution(policy: dict | None = None) -> dict:
    policy = policy or profile()
    contract = task(policy)
    from governance.execution_result import contract_digest
    return {
        "schema_version": "1.0",
        "execution": {"id": "EXEC-1", "task_id": "TASK-1", "base_commit": BASE, "head_commit": HEAD, "task_contract_sha256": contract_digest(contract), "policy_profile_sha256": policy_digest(policy), "status": "candidate"},
        "change_set": {"changed_files": [], "total_changed_files": 0, "total_diff_lines": 0, "new_dependencies": []},
        "result": {"status": "pass", "violations": []},
    }


def evidence_report() -> dict:
    records = []
    for index, claim in enumerate(("unit_tests", "integration_tests", "diff_conformance"), start=1):
        records.append(
            {
                "schema_version": "1.0",
                "evidence": {"id": f"E{index}", "claim_id": claim, "source_commit": HEAD, "collected_at": "2026-08-18T00:00:00Z", "expires_at": "2099-08-19T00:00:00Z", "collector": {"type": "tool", "name": "fixture"}},
                "environment": {"working_directory": ".", "platform": "linux", "python_version": "3.12", "tool_versions": {"fixture": "1"}},
                "command": {"argv": ["fixture", claim], "exit_code": 0, "duration_ms": 1},
                "artifacts": [{"path": f"evidence/{claim}.log", "sha256": "0" * 64, "size_bytes": 0}],
                "result": {"status": "pass", "summary": "passed"},
                "freshness": {"policy": "commit-bound", "max_age_hours": 1000000},
            }
        )
    return {"schema_version": "1.0", "source": {"commit": HEAD, "dirty": False}, "evidence": records, "summary": {"passed": 3, "failed": 0}}


def state(policy: dict | None = None) -> dict:
    policy = policy or profile()
    return {
        "schema_version": "2.0",
        "project": {"id": "PROJECT-1", "name": "Project", "type": "software", "mode": "brownfield", "owner": "alice"},
        "lifecycle": {"current_phase": "implementation", "status": "review", "gate_id": "GATE-RELEASE", "source_commit": HEAD},
        "current_outcome": {"id": "OUT-1", "statement": "Release candidate", "metric": "policy claims", "target": "all pass", "owner": "alice"},
        "blockers": [],
        "residual_risks": [],
        "artifacts": {},
        "contracts": {"active_task": None, "active_transition": None},
        "policy": {"profile_id": policy["policy"]["id"], "profile_version": policy["policy"]["version"], "profile_sha256": policy_digest(policy)},
    }


def test_policy_profile_passes_and_has_stable_digest() -> None:
    value = profile()
    assert validate_policy_profile(value) == []
    assert policy_digest(value) == policy_digest(profile())


def test_transition_policy_requires_all_claims_and_roles() -> None:
    value = transition()
    value["evidence"] = value["evidence"][:1]
    value["approvals"] = []
    errors = validate_transition_policy(value, profile())
    assert "policy requires passing claim: integration_tests" in errors
    assert "policy requires passing claim: diff_conformance" in errors
    assert "policy requires approved role: engineering-owner" in errors


def test_policy_rejects_waiver_of_nonwaivable_blocker() -> None:
    value = transition()
    value["blockers"] = [
        {"id": "BLK-1", "class": "hard", "category": "security-critical", "status": "waived", "owner": "alice", "reason": "security gap", "waiver": {"approved_by": "alice", "rationale": "accept", "expires_at": "2099-01-01T00:00:00Z", "source_commit": HEAD}}
    ]
    assert "policy forbids waiving blocker category: security-critical" in validate_transition_policy(value, profile())


def test_policy_files_cover_all_supported_modes() -> None:
    expected = {"default-software", "saas-product", "ai-product", "modernization", "project-rescue", "release-readiness", "readiness-audit"}
    loaded = {load_policy_profile(path)["policy"]["id"] for path in POLICIES.glob("*.yaml")}
    assert loaded == expected
    assert all(validate_policy_profile(load_policy_profile(path)) == [] for path in POLICIES.glob("*.yaml"))


def test_cross_contract_audit_passes_consistent_bundle() -> None:
    value = build_project_audit(
        project_state=state(),
        task_contract=task(),
        gate_transition=transition(),
        execution_result=execution(),
        evidence_report=evidence_report(),
        policy_profile=profile(),
        repository_head=HEAD,
    )
    assert value["audit"]["status"] == "pass"
    assert value["issues"] == []


def test_cross_contract_audit_detects_commit_and_identity_mismatches() -> None:
    bad_state = state()
    bad_state["project"]["id"] = "OTHER-PROJECT"
    bad_evidence = evidence_report()
    bad_evidence["source"]["commit"] = BASE
    value = build_project_audit(
        project_state=bad_state,
        task_contract=task(),
        gate_transition=transition(),
        execution_result=execution(),
        evidence_report=bad_evidence,
        policy_profile=profile(),
        repository_head=HEAD,
    )
    messages = [issue["message"] for issue in value["issues"]]
    assert "gate transition project id does not match project state" in messages
    assert "evidence report source commit does not match execution head" in messages


def test_cross_contract_audit_detects_missing_completion_claim() -> None:
    report = evidence_report()
    report["evidence"] = report["evidence"][:2]
    value = build_project_audit(
        project_state=state(),
        task_contract=task(),
        gate_transition=transition(),
        execution_result=execution(),
        evidence_report=report,
        policy_profile=profile(),
        repository_head=HEAD,
    )
    messages = [issue["message"] for issue in value["issues"]]
    assert "task completion requires passing claim: diff_conformance" in messages


def test_policy_and_audit_clis_emit_json(tmp_path: Path) -> None:
    import json
    import subprocess
    import sys
    import yaml

    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(yaml.safe_dump(profile(), sort_keys=False), encoding="utf-8")
    policy_cli = SCRIPTS / "validate_policy_profile.py"
    policy_run = subprocess.run(
        [sys.executable, str(policy_cli), str(policy_path), "--format", "json"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert policy_run.returncode == 0, policy_run.stdout + policy_run.stderr
    assert json.loads(policy_run.stdout)["pass"] is True

    files = {
        "state.yaml": state(),
        "task.yaml": task(),
        "gate.yaml": transition(),
        "execution.json": execution(),
        "evidence.json": evidence_report(),
    }
    for name, value in files.items():
        path = tmp_path / name
        if name.endswith(".json"):
            path.write_text(json.dumps(value), encoding="utf-8")
        else:
            path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")
    audit_cli = SCRIPTS / "audit_project.py"
    audit_run = subprocess.run(
        [
            sys.executable,
            str(audit_cli),
            "--state", str(tmp_path / "state.yaml"),
            "--task", str(tmp_path / "task.yaml"),
            "--gate", str(tmp_path / "gate.yaml"),
            "--execution", str(tmp_path / "execution.json"),
            "--evidence", str(tmp_path / "evidence.json"),
            "--policy", str(policy_path),
            "--head", HEAD,
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert audit_run.returncode == 0, audit_run.stdout + audit_run.stderr
    assert json.loads(audit_run.stdout)["audit"]["status"] == "pass"
