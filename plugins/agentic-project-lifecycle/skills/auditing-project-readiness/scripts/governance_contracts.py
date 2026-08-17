#!/usr/bin/env python3
"""Pure validators for Agentic Project Lifecycle governance contracts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
import re
from typing import Any

import yaml

SCHEMA_VERSION = "1.0"
PROJECT_STATE_SCHEMA_VERSION = "2.0"
COMMIT_RE = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[\\/]")
PHASES = (
    "orientation",
    "discovery",
    "specification",
    "solution-design",
    "planning",
    "implementation",
    "release",
    "operations",
)


def _mapping(value: object, label: str, errors: list[str]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        errors.append(f"{label} must be a mapping")
        return {}
    return value


def _items(value: object, label: str, errors: list[str]) -> list[Any]:
    if not isinstance(value, list):
        errors.append(f"{label} must be a list")
        return []
    return value


def _text(
    mapping: Mapping[str, Any], key: str, label: str, errors: list[str]
) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label}.{key} is required")
        return ""
    return value.strip()


def _enum(
    mapping: Mapping[str, Any],
    key: str,
    allowed: set[str],
    label: str,
    errors: list[str],
) -> str:
    value = mapping.get(key)
    if value not in allowed:
        errors.append(f"{label}.{key} must be one of {sorted(allowed)}")
        return ""
    return str(value)


def _integer(
    mapping: Mapping[str, Any],
    key: str,
    label: str,
    errors: list[str],
    *,
    minimum: int,
) -> int | None:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        errors.append(f"{label}.{key} must be an integer >= {minimum}")
        return None
    return value


def _commit(value: object, label: str, errors: list[str]) -> str:
    if not isinstance(value, str) or not COMMIT_RE.fullmatch(value):
        errors.append(f"{label} must be a full lowercase Git commit SHA")
        return ""
    return value


def _timestamp(value: object, label: str, errors: list[str]) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label} is required")
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        errors.append(f"{label} must be an ISO-8601 timestamp")
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        errors.append(f"{label} must include a timezone")
        return None
    return parsed.astimezone(timezone.utc)


def _relative_path(
    value: object, label: str, errors: list[str], *, allow_root: bool = False
) -> str:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label} must be repository-relative and non-empty")
        return ""
    raw = value.strip()
    normalized = raw.replace("\\", "/")
    path = PurePosixPath(normalized)
    if (
        normalized.startswith("/")
        or normalized.startswith("~")
        or WINDOWS_ABSOLUTE_RE.match(raw)
        or ".." in path.parts
        or ("." == normalized and not allow_root)
    ):
        errors.append(f"{label} must be repository-relative without traversal")
        return ""
    return normalized


def _string_list(value: object, label: str, errors: list[str]) -> list[str]:
    items = _items(value, label, errors)
    result: list[str] = []
    for index, item in enumerate(items):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{label}[{index}] must be a non-empty string")
        else:
            result.append(item.strip())
    if len(result) != len(set(result)):
        errors.append(f"{label} contains duplicates")
    return result


def _schema(data: Mapping[str, Any], errors: list[str]) -> None:
    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")


def validate_task_contract(data: object) -> list[str]:
    """Validate a bounded execution task contract without mutating it."""

    errors: list[str] = []
    root = _mapping(data, "root", errors)
    if not root:
        return errors
    _schema(root, errors)

    task = _mapping(root.get("task"), "task", errors)
    _text(task, "id", "task", errors)
    _text(task, "objective", "task", errors)
    _enum(
        task,
        "kind",
        {"feature", "bugfix", "remediation", "migration", "release", "audit"},
        "task",
        errors,
    )
    task_commit = _commit(task.get("source_commit"), "task.source_commit", errors)
    risk_level = _enum(
        task,
        "risk_level",
        {"low", "medium", "high", "critical"},
        "task",
        errors,
    )
    _enum(task, "current_gate", set(PHASES), "task", errors)

    scope = _mapping(root.get("scope"), "scope", errors)
    allowed_paths = _string_list(scope.get("allowed_paths"), "scope.allowed_paths", errors)
    forbidden_paths = _string_list(
        scope.get("forbidden_paths"), "scope.forbidden_paths", errors
    )
    if not allowed_paths:
        errors.append("scope.allowed_paths must contain at least one path")
    for index, value in enumerate(allowed_paths):
        _relative_path(value, f"scope.allowed_paths[{index}]", errors)
    for index, value in enumerate(forbidden_paths):
        _relative_path(value, f"scope.forbidden_paths[{index}]", errors)
    exact_overlap = sorted(set(allowed_paths).intersection(forbidden_paths))
    if exact_overlap:
        errors.append(
            "scope path cannot be both allowed and forbidden: "
            + ", ".join(exact_overlap)
        )
    _integer(scope, "max_changed_files", "scope", errors, minimum=1)
    _integer(scope, "max_diff_lines", "scope", errors, minimum=1)
    _integer(scope, "max_new_dependencies", "scope", errors, minimum=0)

    permissions = _mapping(root.get("permissions"), "permissions", errors)
    filesystem = _enum(
        permissions,
        "filesystem",
        {"read-only", "workspace-write-scoped"},
        "permissions",
        errors,
    )
    network = _enum(
        permissions,
        "network",
        {"disabled", "allowlist"},
        "permissions",
        errors,
    )
    allowed_commands = _string_list(
        permissions.get("allowed_commands"), "permissions.allowed_commands", errors
    )
    _string_list(
        permissions.get("forbidden_command_patterns"),
        "permissions.forbidden_command_patterns",
        errors,
    )
    dependency_changes = _enum(
        permissions,
        "dependency_changes",
        {"forbidden", "approval-required", "allowed"},
        "permissions",
        errors,
    )
    destructive_actions = _enum(
        permissions,
        "destructive_actions",
        {"forbidden", "approval-required"},
        "permissions",
        errors,
    )
    production_actions = permissions.get("production_actions")
    if production_actions != "forbidden":
        errors.append("production actions must remain forbidden")
    if network == "allowlist":
        domains = _string_list(
            permissions.get("allowed_domains"), "permissions.allowed_domains", errors
        )
        if not domains:
            errors.append("network allowlist requires permissions.allowed_domains")

    plan = _mapping(root.get("plan"), "plan", errors)
    _text(plan, "id", "plan", errors)
    plan_status = _enum(
        plan,
        "status",
        {"draft", "approved", "rejected", "superseded"},
        "plan",
        errors,
    )
    steps = _items(plan.get("steps"), "plan.steps", errors)
    if filesystem == "workspace-write-scoped" and plan_status != "approved":
        errors.append("writable task requires an approved plan")
    if filesystem == "workspace-write-scoped" and not steps:
        errors.append("writable task requires at least one plan step")
    seen_steps: set[str] = set()
    for index, raw_step in enumerate(steps):
        label = f"plan.steps[{index}]"
        step = _mapping(raw_step, label, errors)
        step_id = _text(step, "id", label, errors)
        if step_id:
            if step_id in seen_steps:
                errors.append(f"duplicate plan step id {step_id}")
            seen_steps.add(step_id)
        addresses = _string_list(step.get("addresses"), f"{label}.addresses", errors)
        if not addresses:
            errors.append(f"{label}.addresses must not be empty")
        _text(step, "action", label, errors)
        _text(step, "expected_changes", label, errors)
        commands = _string_list(
            step.get("verification_commands"),
            f"{label}.verification_commands",
            errors,
        )
        if not commands:
            errors.append(f"{label}.verification_commands must not be empty")
        for command in commands:
            if command not in allowed_commands:
                errors.append(
                    f"{label} verification command is not allowed: {command}"
                )

    approval = _mapping(root.get("approval"), "approval", errors)
    approval_required = approval.get("required")
    if not isinstance(approval_required, bool):
        errors.append("approval.required must be boolean")
        approval_required = False
    approval_status = _enum(
        approval,
        "status",
        {"not-required", "pending", "approved", "rejected", "expired"},
        "approval",
        errors,
    )
    consequential = risk_level in {"high", "critical"}
    elevated_permissions = (
        network == "allowlist"
        or dependency_changes in {"approval-required", "allowed"}
        or destructive_actions == "approval-required"
    )
    requires_approval = bool(
        approval_required or consequential or elevated_permissions
    )
    if consequential and approval_required is not True:
        errors.append("high-risk task requires approval.required true")
    if elevated_permissions and approval_required is not True:
        errors.append("elevated permissions require approval.required true")
    if consequential and approval_status != "approved":
        errors.append("high-risk task requires approved human authorization")
    if elevated_permissions and approval_status != "approved":
        errors.append("elevated permissions require approved authorization")
    if approval_status == "approved":
        _text(approval, "approved_by", "approval", errors)
        _timestamp(approval.get("approved_at"), "approval.approved_at", errors)
        approval_commit = _commit(
            approval.get("source_commit"), "approval.source_commit", errors
        )
        if task_commit and approval_commit and task_commit != approval_commit:
            errors.append("approval is not bound to the task source commit")
    elif requires_approval:
        errors.append("required approval is not approved")

    rollback = _mapping(root.get("rollback"), "rollback", errors)
    if filesystem == "workspace-write-scoped":
        checkpoint_commit = _commit(
            rollback.get("checkpoint_commit"),
            "rollback.checkpoint_commit",
            errors,
        )
        if (
            task_commit
            and checkpoint_commit
            and task_commit != checkpoint_commit
        ):
            errors.append(
                "rollback checkpoint is not bound to the task source commit"
            )
        _enum(
            rollback,
            "strategy",
            {"reset-to-checkpoint", "revert-commit", "restore-from-patch"},
            "rollback",
            errors,
        )
        if not isinstance(rollback.get("preserve_failed_diff"), bool):
            errors.append("rollback.preserve_failed_diff must be boolean")

    completion = _mapping(root.get("completion"), "completion", errors)
    required_evidence = _string_list(
        completion.get("required_evidence"),
        "completion.required_evidence",
        errors,
    )
    if not required_evidence:
        errors.append("completion.required_evidence must not be empty")

    return errors


def validate_gate_transition(data: object) -> list[str]:
    """Validate a lifecycle gate decision without mutating it."""

    errors: list[str] = []
    root = _mapping(data, "root", errors)
    if not root:
        return errors
    _schema(root, errors)

    transition = _mapping(root.get("transition"), "transition", errors)
    _text(transition, "id", "transition", errors)
    _text(transition, "project_id", "transition", errors)
    transition_type = _enum(
        transition,
        "type",
        {"advance", "reopen", "hold", "waive"},
        "transition",
        errors,
    )
    phase_from = _enum(transition, "from", set(PHASES), "transition", errors)
    phase_to = _enum(transition, "to", set(PHASES), "transition", errors)
    _timestamp(transition.get("requested_at"), "transition.requested_at", errors)
    transition_commit = _commit(
        transition.get("source_commit"), "transition.source_commit", errors
    )

    outcome = _mapping(root.get("outcome"), "outcome", errors)
    _text(outcome, "id", "outcome", errors)
    _text(outcome, "statement", "outcome", errors)
    _text(outcome, "owner", "outcome", errors)

    policy = _mapping(root.get("policy"), "policy", errors)
    _enum(
        policy,
        "hard_blocker_behavior",
        {"stop-dependent-work", "continue-independent-only"},
        "policy",
        errors,
    )
    allow_phase_skip = policy.get("allow_phase_skip")
    if not isinstance(allow_phase_skip, bool):
        errors.append("policy.allow_phase_skip must be boolean")
        allow_phase_skip = False

    approvals = _items(root.get("approvals"), "approvals", errors)
    approved_roles: set[str] = set()
    for index, raw_approval in enumerate(approvals):
        label = f"approvals[{index}]"
        approval = _mapping(raw_approval, label, errors)
        role = _text(approval, "role", label, errors)
        required = approval.get("required")
        if not isinstance(required, bool):
            errors.append(f"{label}.required must be boolean")
            required = False
        decision = _enum(
            approval,
            "decision",
            {"pending", "approved", "rejected", "expired"},
            label,
            errors,
        )
        if decision == "approved":
            approved_roles.add(role)
            _text(approval, "actor", label, errors)
            _timestamp(approval.get("decided_at"), f"{label}.decided_at", errors)
            approval_commit = _commit(
                approval.get("source_commit"), f"{label}.source_commit", errors
            )
            if (
                transition_commit
                and approval_commit
                and transition_commit != approval_commit
            ):
                errors.append(f"{label} is not bound to the transition commit")
        elif required:
            errors.append(f"required approval {role or index} is not approved")

    if transition_type == "advance" and phase_from and phase_to:
        from_index = PHASES.index(phase_from)
        to_index = PHASES.index(phase_to)
        if to_index != from_index + 1:
            if not allow_phase_skip:
                errors.append("phase skip is not permitted by policy")
            elif "lifecycle-owner" not in approved_roles:
                errors.append("phase skip requires lifecycle-owner approval")
    elif transition_type == "reopen" and phase_from and phase_to:
        if PHASES.index(phase_to) >= PHASES.index(phase_from):
            errors.append("reopen transition must move to an earlier phase")

    evidence_items = _items(root.get("evidence"), "evidence", errors)
    evidence_by_id: dict[str, Mapping[str, Any]] = {}
    for index, raw_evidence in enumerate(evidence_items):
        label = f"evidence[{index}]"
        evidence = _mapping(raw_evidence, label, errors)
        evidence_id = _text(evidence, "id", label, errors)
        if evidence_id in evidence_by_id:
            errors.append(f"duplicate gate evidence id {evidence_id}")
        elif evidence_id:
            evidence_by_id[evidence_id] = evidence
        _relative_path(evidence.get("path"), f"{label}.path", errors)
        _enum(evidence, "status", {"pass", "fail", "stale"}, label, errors)
        evidence_commit = _commit(
            evidence.get("source_commit"), f"{label}.source_commit", errors
        )
        if (
            transition_commit
            and evidence_commit
            and transition_commit != evidence_commit
        ):
            errors.append(
                f"evidence {evidence_id or index} is not bound to the transition commit"
            )

    conditions = _items(root.get("conditions"), "conditions", errors)
    for index, raw_condition in enumerate(conditions):
        label = f"conditions[{index}]"
        condition = _mapping(raw_condition, label, errors)
        condition_id = _text(condition, "id", label, errors)
        status = _enum(
            condition,
            "status",
            {"pending", "satisfied", "unsatisfied", "waived"},
            label,
            errors,
        )
        refs = _string_list(condition.get("evidence"), f"{label}.evidence", errors)
        if status == "satisfied" and not refs:
            errors.append(f"satisfied condition {condition_id or index} needs evidence")
        for evidence_id in refs:
            if evidence_id not in evidence_by_id:
                errors.append(
                    f"condition {condition_id or index} references missing evidence {evidence_id}"
                )

    blockers = _items(root.get("blockers"), "blockers", errors)
    residual_risks = _items(root.get("residual_risks"), "residual_risks", errors)
    risk_blockers: set[str] = set()
    for index, raw_risk in enumerate(residual_risks):
        label = f"residual_risks[{index}]"
        risk = _mapping(raw_risk, label, errors)
        blocker_id = _text(risk, "blocker_id", label, errors)
        if blocker_id:
            risk_blockers.add(blocker_id)
        _text(risk, "owner", label, errors)
        _text(risk, "statement", label, errors)
        _text(risk, "review_by", label, errors)

    open_hard: list[str] = []
    open_soft: list[str] = []
    for index, raw_blocker in enumerate(blockers):
        label = f"blockers[{index}]"
        blocker = _mapping(raw_blocker, label, errors)
        blocker_id = _text(blocker, "id", label, errors)
        blocker_class = _enum(
            blocker,
            "class",
            {"hard", "soft", "informational"},
            label,
            errors,
        )
        blocker_status = _enum(
            blocker,
            "status",
            {"open", "resolved", "waived"},
            label,
            errors,
        )
        _text(blocker, "owner", label, errors)
        _text(blocker, "reason", label, errors)
        if blocker_status == "open" and blocker_class == "hard":
            open_hard.append(blocker_id)
        if blocker_status == "open" and blocker_class == "soft":
            open_soft.append(blocker_id)
        if blocker_status == "waived":
            waiver = _mapping(blocker.get("waiver"), f"{label}.waiver", errors)
            _text(waiver, "approved_by", f"{label}.waiver", errors)
            _text(waiver, "rationale", f"{label}.waiver", errors)
            _timestamp(
                waiver.get("expires_at"), f"{label}.waiver.expires_at", errors
            )
            waiver_commit = _commit(
                waiver.get("source_commit"),
                f"{label}.waiver.source_commit",
                errors,
            )
            if (
                transition_commit
                and waiver_commit
                and transition_commit != waiver_commit
            ):
                errors.append(f"waiver for {blocker_id or index} is not commit-bound")

    decision = _mapping(root.get("decision"), "decision", errors)
    decision_status = _enum(
        decision,
        "status",
        {"pending", "approved", "rejected"},
        "decision",
        errors,
    )
    if decision_status in {"approved", "rejected"}:
        _text(decision, "decided_by", "decision", errors)
        _timestamp(decision.get("decided_at"), "decision.decided_at", errors)
        _text(decision, "rationale", "decision", errors)

    if decision_status == "approved":
        for blocker_id in open_hard:
            errors.append(f"approved transition has an open hard blocker {blocker_id}")
        for blocker_id in open_soft:
            if blocker_id not in risk_blockers:
                errors.append(
                    f"open soft blocker {blocker_id} requires a residual-risk record"
                )
        for index, raw_condition in enumerate(conditions):
            condition = raw_condition if isinstance(raw_condition, Mapping) else {}
            if condition.get("status") not in {"satisfied", "waived"}:
                errors.append(
                    "approved transition has unsatisfied condition "
                    + str(condition.get("id", index))
                )
        for evidence_id, evidence in evidence_by_id.items():
            if evidence.get("status") != "pass":
                errors.append(
                    f"approved transition has non-passing evidence {evidence_id}"
                )

    return errors


def validate_evidence_record(
    data: object,
    *,
    expected_commit: str | None = None,
    now: datetime | None = None,
) -> list[str]:
    """Validate one observed verification evidence record."""

    errors: list[str] = []
    root = _mapping(data, "root", errors)
    if not root:
        return errors
    _schema(root, errors)

    evidence = _mapping(root.get("evidence"), "evidence", errors)
    _text(evidence, "id", "evidence", errors)
    _text(evidence, "claim_id", "evidence", errors)
    source_commit = _commit(
        evidence.get("source_commit"), "evidence.source_commit", errors
    )
    if expected_commit is not None:
        if not COMMIT_RE.fullmatch(expected_commit):
            errors.append("expected commit must be a full lowercase Git commit SHA")
        elif source_commit and source_commit != expected_commit:
            errors.append("evidence source commit does not match expected commit")
    collected_at = _timestamp(
        evidence.get("collected_at"), "evidence.collected_at", errors
    )
    expires_at = _timestamp(
        evidence.get("expires_at"), "evidence.expires_at", errors
    )
    collector = _mapping(evidence.get("collector"), "evidence.collector", errors)
    _enum(
        collector,
        "type",
        {"tool", "human", "agent-with-tool"},
        "evidence.collector",
        errors,
    )
    _text(collector, "name", "evidence.collector", errors)

    environment = _mapping(root.get("environment"), "environment", errors)
    _relative_path(
        environment.get("working_directory"),
        "environment.working_directory",
        errors,
        allow_root=True,
    )
    _text(environment, "platform", "environment", errors)
    _text(environment, "python_version", "environment", errors)
    tool_versions = _mapping(
        environment.get("tool_versions"), "environment.tool_versions", errors
    )
    for name, version in tool_versions.items():
        if not isinstance(name, str) or not name.strip():
            errors.append("environment.tool_versions keys must be non-empty strings")
        if not isinstance(version, str) or not version.strip():
            errors.append(
                f"environment.tool_versions.{name} must be a non-empty string"
            )

    command = _mapping(root.get("command"), "command", errors)
    argv = _string_list(command.get("argv"), "command.argv", errors)
    if not argv:
        errors.append("command.argv must not be empty")
    exit_code = command.get("exit_code")
    if isinstance(exit_code, bool) or not isinstance(exit_code, int):
        errors.append("command.exit_code must be an integer")
        exit_code = None
    _integer(command, "duration_ms", "command", errors, minimum=0)

    artifacts = _items(root.get("artifacts"), "artifacts", errors)
    if not artifacts:
        errors.append("artifacts must contain at least one observed output")
    for index, raw_artifact in enumerate(artifacts):
        label = f"artifacts[{index}]"
        artifact = _mapping(raw_artifact, label, errors)
        _relative_path(artifact.get("path"), f"{label}.path", errors)
        digest = artifact.get("sha256")
        if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            errors.append(f"{label}.sha256 must be a lowercase SHA-256 digest")
        _integer(artifact, "size_bytes", label, errors, minimum=0)

    result = _mapping(root.get("result"), "result", errors)
    result_status = _enum(
        result,
        "status",
        {"pass", "fail", "error"},
        "result",
        errors,
    )
    _text(result, "summary", "result", errors)
    if result_status == "pass" and exit_code is not None and exit_code != 0:
        errors.append("pass result requires exit_code 0")
    if result_status == "fail" and exit_code == 0:
        errors.append("fail result requires a non-zero exit_code")

    freshness = _mapping(root.get("freshness"), "freshness", errors)
    _enum(
        freshness,
        "policy",
        {"commit-bound", "time-bound", "manual-review"},
        "freshness",
        errors,
    )
    max_age = _integer(
        freshness, "max_age_hours", "freshness", errors, minimum=1
    )

    reference_now = now or datetime.now(timezone.utc)
    if reference_now.tzinfo is None or reference_now.utcoffset() is None:
        errors.append("reference time must include a timezone")
    else:
        reference_now = reference_now.astimezone(timezone.utc)
        if (
            collected_at is not None
            and collected_at > reference_now + timedelta(minutes=5)
        ):
            errors.append("evidence.collected_at is in the future")
        if expires_at is not None and reference_now >= expires_at:
            errors.append("evidence is expired")
        if collected_at is not None and max_age is not None:
            if reference_now > collected_at + timedelta(hours=max_age):
                errors.append("evidence exceeds freshness max_age_hours")
    if collected_at is not None and expires_at is not None and expires_at <= collected_at:
        errors.append("evidence.expires_at must be after collected_at")

    return errors


PROJECT_STATE_STATUSES = {"blocked", "in-progress", "review", "ready", "complete"}
ARTIFACT_STATUSES = {"draft", "review", "approved", "verified", "complete"}
REQUIRED_ARTIFACTS_BY_PHASE = {
    "specification": ("charter", "prd"),
    "solution-design": ("charter", "prd", "design"),
    "planning": ("charter", "prd", "design", "plan"),
    "implementation": ("charter", "prd", "design", "plan"),
    "release": (
        "charter",
        "prd",
        "design",
        "plan",
        "evidence",
        "release_plan",
        "runbook",
    ),
    "operations": (
        "charter",
        "prd",
        "design",
        "plan",
        "evidence",
        "release_plan",
        "runbook",
    ),
}


def _state_commit(value: object, label: str, errors: list[str]) -> str:
    if value == "uncommitted":
        return "uncommitted"
    return _commit(value, label, errors)


def _load_linked_yaml(
    root: Path, relative: str, label: str, errors: list[str]
) -> object | None:
    candidate = (root / relative).resolve()
    resolved_root = root.resolve()
    if candidate != resolved_root and resolved_root not in candidate.parents:
        errors.append(f"{label} escapes the project root")
        return None
    if not candidate.is_file():
        errors.append(f"{label} does not exist: {relative}")
        return None
    try:
        return yaml.safe_load(candidate.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        errors.append(f"{label} cannot be parsed: {exc}")
        return None


def validate_project_state_v2(
    data: object, *, root: Path | None = None
) -> list[str]:
    """Validate the strict project-state v2 contract."""

    errors: list[str] = []
    state = _mapping(data, "root", errors)
    if not state:
        return errors
    if state.get("schema_version") != PROJECT_STATE_SCHEMA_VERSION:
        errors.append(
            f"project-state schema_version must be {PROJECT_STATE_SCHEMA_VERSION}"
        )

    project = _mapping(state.get("project"), "project", errors)
    for key in ("id", "name", "type", "mode", "owner"):
        _text(project, key, "project", errors)

    lifecycle = _mapping(state.get("lifecycle"), "lifecycle", errors)
    phase = _enum(
        lifecycle, "current_phase", set(PHASES), "lifecycle", errors
    )
    lifecycle_status = _enum(
        lifecycle, "status", PROJECT_STATE_STATUSES, "lifecycle", errors
    )
    _text(lifecycle, "gate_id", "lifecycle", errors)
    lifecycle_commit = _state_commit(
        lifecycle.get("source_commit"), "lifecycle.source_commit", errors
    )
    if lifecycle_commit == "uncommitted" and lifecycle_status in {"ready", "complete"}:
        errors.append("ready or complete state must be bound to a Git commit")

    outcome = _mapping(state.get("current_outcome"), "current_outcome", errors)
    for key in ("id", "statement", "metric", "target", "owner"):
        _text(outcome, key, "current_outcome", errors)

    blockers = _items(state.get("blockers"), "blockers", errors)
    residual_risks = _items(
        state.get("residual_risks"), "residual_risks", errors
    )
    risks_by_blocker: set[str] = set()
    for index, raw_risk in enumerate(residual_risks):
        label = f"residual_risks[{index}]"
        risk = _mapping(raw_risk, label, errors)
        blocker_id = _text(risk, "blocker_id", label, errors)
        if blocker_id:
            risks_by_blocker.add(blocker_id)
        _text(risk, "statement", label, errors)
        _text(risk, "owner", label, errors)
        _text(risk, "review_by", label, errors)

    open_hard: list[str] = []
    open_soft: list[str] = []
    for index, raw_blocker in enumerate(blockers):
        label = f"blockers[{index}]"
        blocker = _mapping(raw_blocker, label, errors)
        blocker_id = _text(blocker, "id", label, errors)
        blocker_class = _enum(
            blocker,
            "class",
            {"hard", "soft", "informational"},
            label,
            errors,
        )
        blocker_status = _enum(
            blocker,
            "status",
            {"open", "resolved", "waived"},
            label,
            errors,
        )
        _text(blocker, "owner", label, errors)
        _text(blocker, "reason", label, errors)
        if blocker_status == "open" and blocker_class == "hard":
            open_hard.append(blocker_id)
        if blocker_status == "open" and blocker_class == "soft":
            open_soft.append(blocker_id)
        if blocker_status == "waived":
            waiver = _mapping(blocker.get("waiver"), f"{label}.waiver", errors)
            _text(waiver, "approved_by", f"{label}.waiver", errors)
            _text(waiver, "rationale", f"{label}.waiver", errors)
            _timestamp(
                waiver.get("expires_at"), f"{label}.waiver.expires_at", errors
            )
            waiver_commit = _state_commit(
                waiver.get("source_commit"),
                f"{label}.waiver.source_commit",
                errors,
            )
            if (
                lifecycle_commit
                and waiver_commit
                and lifecycle_commit != waiver_commit
            ):
                errors.append(f"waiver for {blocker_id or index} is not commit-bound")

    if lifecycle_status in {"ready", "complete"}:
        for blocker_id in open_hard:
            errors.append(
                f"{lifecycle_status} state cannot contain open hard blocker {blocker_id}"
            )
    for blocker_id in open_soft:
        if blocker_id not in risks_by_blocker:
            errors.append(
                f"open soft blocker {blocker_id} requires a residual-risk record"
            )

    artifacts = _mapping(state.get("artifacts"), "artifacts", errors)
    required = REQUIRED_ARTIFACTS_BY_PHASE.get(phase, ())
    for name in required:
        raw_record = artifacts.get(name)
        if not isinstance(raw_record, Mapping):
            errors.append(f"required artifact {name} is missing")
            continue
        if raw_record.get("status") not in {"approved", "verified", "complete"}:
            errors.append(f"required artifact {name} is not approved or verified")

    for name, raw_record in artifacts.items():
        label = f"artifacts.{name}"
        record = _mapping(raw_record, label, errors)
        artifact_status = _enum(
            record, "status", ARTIFACT_STATUSES, label, errors
        )
        relative = _relative_path(record.get("path"), f"{label}.path", errors)
        _text(record, "owner", label, errors)
        artifact_commit = _state_commit(
            record.get("source_commit"), f"{label}.source_commit", errors
        )
        if (
            lifecycle_commit
            and artifact_commit
            and lifecycle_commit != artifact_commit
        ):
            errors.append(f"{label} is not bound to lifecycle.source_commit")
        approval = _mapping(record.get("approval"), f"{label}.approval", errors)
        approval_status = _enum(
            approval,
            "status",
            {"pending", "approved", "rejected", "not-required"},
            f"{label}.approval",
            errors,
        )
        if artifact_status in {"approved", "complete"} and approval_status != "approved":
            errors.append(f"{label} requires approved artifact authorization")
        if artifact_status == "verified" and approval_status not in {
            "approved",
            "not-required",
        }:
            errors.append(f"{label} verification approval is incomplete")
        if approval_status == "approved":
            _text(approval, "approved_by", f"{label}.approval", errors)
            _timestamp(
                approval.get("approved_at"),
                f"{label}.approval.approved_at",
                errors,
            )
            approval_commit = _state_commit(
                approval.get("source_commit"),
                f"{label}.approval.source_commit",
                errors,
            )
            if (
                lifecycle_commit
                and approval_commit
                and lifecycle_commit != approval_commit
            ):
                errors.append(f"{label}.approval is not commit-bound")
        if root is not None and relative:
            candidate = (root / relative).resolve()
            resolved_root = root.resolve()
            if candidate != resolved_root and resolved_root not in candidate.parents:
                errors.append(f"{label}.path escapes the project root")
            elif not candidate.is_file():
                errors.append(f"{label}.path does not exist: {relative}")

    contracts = _mapping(state.get("contracts"), "contracts", errors)
    for key, validator, display in (
        ("active_task", validate_task_contract, "active task contract"),
        ("active_transition", validate_gate_transition, "active gate transition"),
    ):
        value = contracts.get(key)
        if value is None:
            continue
        relative = _relative_path(value, f"contracts.{key}", errors)
        if root is None or not relative:
            continue
        linked = _load_linked_yaml(root, relative, display, errors)
        if linked is None:
            continue
        for issue in validator(linked):
            errors.append(f"{display}: {issue}")
        if isinstance(linked, Mapping):
            linked_commit = None
            if key == "active_task":
                linked_commit = (
                    linked.get("task", {}).get("source_commit")
                    if isinstance(linked.get("task"), Mapping)
                    else None
                )
            else:
                linked_commit = (
                    linked.get("transition", {}).get("source_commit")
                    if isinstance(linked.get("transition"), Mapping)
                    else None
                )
            if lifecycle_commit and linked_commit and linked_commit != lifecycle_commit:
                errors.append(f"{display} is not bound to lifecycle.source_commit")

    return errors
