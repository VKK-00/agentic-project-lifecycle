from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import given, settings, strategies as st

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "plugins" / "agentic-project-lifecycle" / "skills" / "auditing-project-readiness" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from governance_contracts import (  # noqa: E402
    PHASES,
    validate_evidence_record,
    validate_gate_transition,
    validate_task_contract,
)

COMMIT = "a" * 40


def task_contract(path: str) -> dict:
    return {
        "schema_version": "1.0",
        "task": {
            "id": "TASK-PROP",
            "objective": "Exercise path invariants",
            "kind": "audit",
            "source_commit": COMMIT,
            "risk_level": "low",
            "current_gate": "planning",
        },
        "scope": {
            "allowed_paths": [path],
            "forbidden_paths": ["secrets/**"],
            "max_changed_files": 1,
            "max_diff_lines": 1,
            "max_new_dependencies": 0,
        },
        "permissions": {
            "filesystem": "read-only",
            "network": "disabled",
            "allowed_commands": [],
            "forbidden_command_patterns": [],
            "dependency_changes": "forbidden",
            "destructive_actions": "forbidden",
            "production_actions": "forbidden",
        },
        "plan": {"id": "PLAN-PROP", "status": "draft", "steps": []},
        "approval": {"required": False, "status": "not-required"},
        "rollback": {},
        "completion": {"required_evidence": ["contract_validation"]},
    }


@given(st.lists(st.sampled_from(["..", "src", "nested", "file.py"]), min_size=2, max_size=8))
@settings(max_examples=80, deadline=None)
def test_any_parent_segment_is_rejected(parts: list[str]) -> None:
    hypothesis.assume(".." in parts)
    candidate = "/".join(parts)
    errors = validate_task_contract(task_contract(candidate))
    assert any("repository-relative without traversal" in item for item in errors)


@given(
    phase_from=st.sampled_from(PHASES),
    phase_to=st.sampled_from(PHASES),
)
@settings(max_examples=100, deadline=None)
def test_advance_never_moves_same_or_backward(phase_from: str, phase_to: str) -> None:
    transition = {
        "schema_version": "1.0",
        "transition": {
            "id": "GATE-PROP",
            "project_id": "PROJECT-PROP",
            "type": "advance",
            "from": phase_from,
            "to": phase_to,
            "requested_at": "2026-08-18T00:00:00Z",
            "source_commit": COMMIT,
        },
        "outcome": {"id": "OUTCOME-PROP", "statement": "Property check", "owner": "owner"},
        "conditions": [],
        "evidence": [],
        "approvals": [],
        "blockers": [],
        "residual_risks": [],
        "policy": {"hard_blocker_behavior": "stop-dependent-work", "allow_phase_skip": True},
        "decision": {"status": "pending"},
    }
    errors = validate_gate_transition(transition)
    if PHASES.index(phase_to) <= PHASES.index(phase_from):
        assert "advance transition must move to a later phase" in errors


@given(hours=st.integers(min_value=1, max_value=720), elapsed=st.integers(min_value=0, max_value=800))
@settings(max_examples=100, deadline=None)
def test_evidence_freshness_is_monotonic(hours: int, elapsed: int) -> None:
    collected = datetime(2026, 8, 18, tzinfo=timezone.utc)
    evidence = {
        "schema_version": "1.0",
        "evidence": {
            "id": "EVID-PROP",
            "claim_id": "CLAIM-PROP",
            "source_commit": COMMIT,
            "collected_at": collected.isoformat(),
            "expires_at": (collected + timedelta(hours=hours)).isoformat(),
            "collector": {"type": "tool", "name": "property-test"},
        },
        "environment": {
            "working_directory": ".",
            "platform": "test",
            "python_version": "3.11",
            "tool_versions": {"hypothesis": "test"},
        },
        "command": {"argv": ["true"], "exit_code": 0, "duration_ms": 0},
        "artifacts": [{"path": "evidence/log", "sha256": "0" * 64, "size_bytes": 0}],
        "result": {"status": "pass", "summary": "observed"},
        "freshness": {"policy": "time-bound", "max_age_hours": hours},
    }
    errors = validate_evidence_record(evidence, now=collected + timedelta(hours=elapsed))
    if elapsed >= hours:
        assert any(item in errors for item in ("evidence is expired", "evidence exceeds freshness max_age_hours"))
    else:
        assert "evidence is expired" not in errors


@given(st.recursive(st.none() | st.booleans() | st.integers() | st.text(max_size=12), lambda children: st.lists(children, max_size=4) | st.dictionaries(st.text(max_size=8), children, max_size=4), max_leaves=20))
@settings(max_examples=100, deadline=None)
def test_validators_never_raise_on_arbitrary_yaml_values(value: object) -> None:
    for validator in (validate_task_contract, validate_gate_transition, validate_evidence_record):
        original = deepcopy(value)
        result = validator(value)
        assert isinstance(result, list)
        assert value == original
