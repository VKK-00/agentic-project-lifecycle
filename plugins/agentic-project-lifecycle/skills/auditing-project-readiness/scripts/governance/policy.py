"""Versioned lifecycle policy profiles and transition conformance."""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from governance_contracts import PHASES

ASSURANCE_LEVELS = {"declared": 0, "git-signed": 1, "github-review": 2}


def policy_digest(profile: object) -> str:
    payload = json.dumps(profile, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_policy_profile(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"policy profile root must be a mapping: {path}")
    return value


def _strings(value: object, label: str, errors: list[str]) -> list[str]:
    if not isinstance(value, list):
        errors.append(f"{label} must be a list")
        return []
    result: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{label}[{index}] must be a non-empty string")
        else:
            result.append(item.strip())
    if len(result) != len(set(result)):
        errors.append(f"{label} contains duplicates")
    return result


def validate_policy_profile(data: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, Mapping):
        return ["policy profile root must be a mapping"]
    if data.get("schema_version") != "1.0":
        errors.append("policy profile schema_version must be 1.0")
    policy = data.get("policy")
    if not isinstance(policy, Mapping):
        errors.append("policy must be a mapping")
        policy = {}
    for key in ("id", "version", "name"):
        if not isinstance(policy.get(key), str) or not str(policy.get(key)).strip():
            errors.append(f"policy.{key} is required")
    assurance = policy.get("minimum_approval_assurance")
    if assurance not in ASSURANCE_LEVELS:
        errors.append("policy.minimum_approval_assurance is invalid")
    _strings(policy.get("protected_paths", []), "policy.protected_paths", errors)

    gates = data.get("gates")
    if not isinstance(gates, list) or not gates:
        errors.append("gates must be a non-empty list")
        gates = []
    seen: set[tuple[str, str]] = set()
    for index, raw_gate in enumerate(gates):
        label = f"gates[{index}]"
        if not isinstance(raw_gate, Mapping):
            errors.append(f"{label} must be a mapping")
            continue
        for key in ("id", "from", "to"):
            if not isinstance(raw_gate.get(key), str) or not str(raw_gate.get(key)).strip():
                errors.append(f"{label}.{key} is required")
        phase_from = raw_gate.get("from")
        phase_to = raw_gate.get("to")
        if phase_from not in PHASES:
            errors.append(f"{label}.from is invalid")
        if phase_to not in PHASES:
            errors.append(f"{label}.to is invalid")
        pair = (str(phase_from), str(phase_to))
        if pair in seen:
            errors.append(f"duplicate policy gate: {phase_from}->{phase_to}")
        seen.add(pair)
        _strings(raw_gate.get("required_claims", []), f"{label}.required_claims", errors)
        _strings(raw_gate.get("required_roles", []), f"{label}.required_roles", errors)
        _strings(
            raw_gate.get("non_waivable_blocker_classes", []),
            f"{label}.non_waivable_blocker_classes",
            errors,
        )
        if not isinstance(raw_gate.get("allow_phase_skip"), bool):
            errors.append(f"{label}.allow_phase_skip must be boolean")
    return errors


def _matching_gate(transition: Mapping[str, Any], profile: Mapping[str, Any]) -> Mapping[str, Any] | None:
    move = transition.get("transition")
    if not isinstance(move, Mapping):
        return None
    for gate in profile.get("gates", []):
        if isinstance(gate, Mapping) and gate.get("from") == move.get("from") and gate.get("to") == move.get("to"):
            return gate
    return None


def validate_transition_policy(transition: object, profile: object) -> list[str]:
    errors = validate_policy_profile(profile)
    if not isinstance(transition, Mapping):
        return errors + ["gate transition root must be a mapping"]
    if not isinstance(profile, Mapping):
        return errors
    policy = profile.get("policy") if isinstance(profile.get("policy"), Mapping) else {}
    binding = transition.get("policy") if isinstance(transition.get("policy"), Mapping) else {}
    if binding.get("profile_id") != policy.get("id"):
        errors.append("transition policy profile id does not match trusted profile")
    if binding.get("profile_version") != policy.get("version"):
        errors.append("transition policy profile version does not match trusted profile")
    if binding.get("profile_sha256") != policy_digest(profile):
        errors.append("transition policy profile digest does not match trusted profile")

    gate = _matching_gate(transition, profile)
    if gate is None:
        errors.append("trusted policy does not define the requested gate")
        return errors
    passing_claims = {
        str(item.get("claim_id"))
        for item in transition.get("evidence", [])
        if isinstance(item, Mapping)
        and item.get("status") == "pass"
        and isinstance(item.get("claim_id"), str)
    }
    for claim in gate.get("required_claims", []):
        if claim not in passing_claims:
            errors.append(f"policy requires passing claim: {claim}")

    approved = {
        str(item.get("role")): str(item.get("assurance", "declared"))
        for item in transition.get("approvals", [])
        if isinstance(item, Mapping) and item.get("decision") == "approved"
    }
    minimum = str(policy.get("minimum_approval_assurance", "declared"))
    for role in gate.get("required_roles", []):
        if role not in approved:
            errors.append(f"policy requires approved role: {role}")
        elif ASSURANCE_LEVELS.get(approved[role], -1) < ASSURANCE_LEVELS.get(minimum, 0):
            errors.append(f"policy requires {minimum} assurance for role: {role}")

    forbidden_waivers = set(gate.get("non_waivable_blocker_classes", []))
    for blocker in transition.get("blockers", []):
        if (
            isinstance(blocker, Mapping)
            and blocker.get("status") == "waived"
            and blocker.get("category") in forbidden_waivers
        ):
            errors.append(
                f"policy forbids waiving blocker category: {blocker.get('category')}"
            )

    move = transition.get("transition") if isinstance(transition.get("transition"), Mapping) else {}
    if move.get("type") == "advance" and move.get("from") in PHASES and move.get("to") in PHASES:
        skipped = PHASES.index(str(move["to"])) > PHASES.index(str(move["from"])) + 1
        if skipped and gate.get("allow_phase_skip") is not True:
            errors.append("trusted policy forbids phase skipping")
    return errors
