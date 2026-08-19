"""Cross-contract audit for a coherent project governance state."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict
from typing import Any

from governance.execution_result import contract_digest, validate_execution_result
from governance.issues import issues_from_messages
from governance.policy import policy_digest, validate_policy_profile, validate_transition_policy
from governance_contracts import validate_evidence_record, validate_gate_transition, validate_task_contract


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _passing_claims(report: Mapping[str, Any], head: str, errors: list[str]) -> set[str]:
    source = _mapping(report.get("source"))
    if source.get("commit") != head:
        errors.append("evidence report source commit does not match execution head")
    records = report.get("evidence")
    if not isinstance(records, list):
        errors.append("evidence report must contain evidence records")
        return set()
    claims: set[str] = set()
    for index, raw in enumerate(records):
        for error in validate_evidence_record(raw, expected_commit=head):
            errors.append(f"evidence[{index}]: {error}")
        record = _mapping(raw)
        evidence = _mapping(record.get("evidence"))
        result = _mapping(record.get("result"))
        if result.get("status") == "pass" and isinstance(evidence.get("claim_id"), str):
            claims.add(str(evidence["claim_id"]))
    return claims


def build_project_audit(
    *,
    project_state: object,
    task_contract: object,
    gate_transition: object,
    execution_result: object,
    evidence_report: object,
    policy_profile: object,
    repository_head: str,
    root=None,
) -> dict[str, Any]:
    errors: list[str] = []
    state = _mapping(project_state)
    task = _mapping(task_contract)
    transition = _mapping(gate_transition)
    execution = _mapping(execution_result)
    report = _mapping(evidence_report)
    profile = _mapping(policy_profile)

    errors.extend(f"task contract: {item}" for item in validate_task_contract(task))
    errors.extend(f"gate transition: {item}" for item in validate_gate_transition(transition))
    errors.extend(f"policy profile: {item}" for item in validate_policy_profile(profile))
    errors.extend(f"transition policy: {item}" for item in validate_transition_policy(transition, profile))
    errors.extend(f"execution result: {item}" for item in validate_execution_result(execution, contract=task, root=root))

    state_project = _mapping(state.get("project"))
    state_lifecycle = _mapping(state.get("lifecycle"))
    task_data = _mapping(task.get("task"))
    task_policy = _mapping(task.get("policy"))
    transition_data = _mapping(transition.get("transition"))
    transition_policy = _mapping(transition.get("policy"))
    execution_data = _mapping(execution.get("execution"))
    state_policy = _mapping(state.get("policy"))
    trusted_policy = _mapping(profile.get("policy"))
    digest = policy_digest(profile)

    if transition_data.get("project_id") != state_project.get("id"):
        errors.append("gate transition project id does not match project state")
    if transition_data.get("from") != state_lifecycle.get("current_phase"):
        errors.append("gate transition source phase does not match project state")
    if task_data.get("current_gate") != transition_data.get("from"):
        errors.append("task current gate does not match gate transition source phase")
    if state_lifecycle.get("gate_id") != transition_data.get("id"):
        errors.append("project-state gate id does not match active transition")
    if execution_data.get("task_id") != task_data.get("id"):
        errors.append("execution task id does not match task contract")
    if execution_data.get("base_commit") != task_data.get("source_commit"):
        errors.append("execution base commit does not match task source commit")
    head = str(execution_data.get("head_commit", ""))
    for label, value in (
        ("repository HEAD", repository_head),
        ("project state", state_lifecycle.get("source_commit")),
        ("gate transition", transition_data.get("source_commit")),
    ):
        if value != head:
            errors.append(f"{label} commit does not match execution head")
    if execution_data.get("task_contract_sha256") != contract_digest(task):
        errors.append("execution task contract digest does not match supplied task contract")

    for label, binding in (
        ("task", task_policy),
        ("transition", transition_policy),
        ("project state", state_policy),
    ):
        if binding.get("profile_id") != trusted_policy.get("id"):
            errors.append(f"{label} policy id does not match trusted profile")
        if binding.get("profile_version") != trusted_policy.get("version"):
            errors.append(f"{label} policy version does not match trusted profile")
        if binding.get("profile_sha256") != digest:
            errors.append(f"{label} policy digest does not match trusted profile")
    if execution_data.get("policy_profile_sha256") != digest:
        errors.append("execution policy digest does not match trusted profile")

    claims = _passing_claims(report, head, errors)
    completion = _mapping(task.get("completion"))
    for claim in completion.get("required_evidence", []):
        if claim not in claims:
            errors.append(f"task completion requires passing claim: {claim}")

    issues = issues_from_messages("audit", errors)
    return {
        "schema_version": "1.0",
        "audit": {
            "status": "pass" if not issues else "fail",
            "project_id": state_project.get("id"),
            "repository_head": repository_head,
            "policy_profile_sha256": digest,
        },
        "issues": [asdict(issue) for issue in issues],
    }
