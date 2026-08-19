"""Stable diagnostics and machine-readable rendering for governance validators."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re
from typing import Iterable


@dataclass(frozen=True, slots=True)
class Issue:
    code: str
    severity: str
    path: str
    rule: str
    message: str
    remediation: str


_KNOWN: dict[str, tuple[str, str, str, str]] = {
    "approval is not bound to the task source commit": (
        "APL-TASK-021",
        "approval.source_commit",
        "source-bound-approval",
        "Approve the current task contract against its source commit.",
    ),
    "writable task requires an approved plan": (
        "APL-TASK-012",
        "plan.status",
        "approved-plan-before-write",
        "Approve the plan before granting write access.",
    ),
    "advance transition must move to a later phase": (
        "APL-GATE-011",
        "transition.to",
        "forward-advance",
        "Use reopen or hold for non-forward transitions.",
    ),
    "evidence source commit does not match expected commit": (
        "APL-EVID-009",
        "evidence.source_commit",
        "source-binding",
        "Collect fresh evidence against the expected commit.",
    ),
}

_PREFIXES = {
    "task": "TASK",
    "gate": "GATE",
    "evidence": "EVID",
    "state": "STATE",
    "execution": "EXEC",
    "policy": "POLICY",
    "audit": "AUDIT",
    "run": "RUN",
}

_PATH_RE = re.compile(r"\b(?:task|scope|permissions|plan|approval|rollback|completion|transition|policy|evidence|environment|command|result|freshness|lifecycle|artifacts|contracts)(?:\.[A-Za-z0-9_\-]+|\[[0-9]+\])+")


def _fallback(namespace: str, message: str) -> Issue:
    prefix = _PREFIXES.get(namespace, namespace.upper()[:8] or "GEN")
    digest = hashlib.sha256(message.encode("utf-8")).hexdigest()[:6].upper()
    match = _PATH_RE.search(message)
    path = match.group(0) if match else "."
    return Issue(
        code=f"APL-{prefix}-X{digest}",
        severity="error",
        path=path,
        rule="semantic-validation",
        message=message,
        remediation="Correct the supplied contract and run the validator again.",
    )


def issues_from_messages(namespace: str, messages: Iterable[str]) -> list[Issue]:
    issues: list[Issue] = []
    for message in messages:
        known = _KNOWN.get(message)
        if known is None:
            issues.append(_fallback(namespace, message))
            continue
        code, path, rule, remediation = known
        issues.append(Issue(code, "error", path, rule, message, remediation))
    return issues


def _json_payload(issues: list[Issue], title: str) -> dict[str, object]:
    return {
        "validator": title,
        "pass": not issues,
        "issues": [asdict(issue) for issue in issues],
    }


def _sarif_payload(issues: list[Issue], title: str) -> dict[str, object]:
    rules: dict[str, dict[str, object]] = {}
    results: list[dict[str, object]] = []
    for issue in issues:
        rules.setdefault(
            issue.code,
            {
                "id": issue.code,
                "name": issue.rule,
                "shortDescription": {"text": issue.message},
                "help": {"text": issue.remediation},
            },
        )
        results.append(
            {
                "ruleId": issue.code,
                "level": "error" if issue.severity == "error" else "warning",
                "message": {"text": issue.message},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": issue.path or "."}
                        }
                    }
                ],
            }
        )
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "Agentic Project Lifecycle",
                        "informationUri": "https://github.com/VKK-00/agentic-project-lifecycle",
                        "rules": list(rules.values()),
                    }
                },
                "results": results,
                "automationDetails": {"description": {"text": title}},
            }
        ],
    }


def render_issues(
    issues: Iterable[Issue], *, output_format: str, title: str
) -> str:
    materialized = list(issues)
    if output_format == "json":
        return json.dumps(_json_payload(materialized, title), indent=2, sort_keys=True)
    if output_format == "sarif":
        return json.dumps(_sarif_payload(materialized, title), indent=2, sort_keys=True)
    if output_format != "text":
        raise ValueError(f"unsupported output format: {output_format}")
    lines = [f"{title}: {'PASS' if not materialized else 'FAIL'}"]
    lines.extend(f"- [{issue.code}] {issue.message}" for issue in materialized)
    return "\n".join(lines)


def explain_code(code: str) -> Issue | None:
    for message, (known_code, path, rule, remediation) in _KNOWN.items():
        if known_code == code:
            return Issue(known_code, "error", path, rule, message, remediation)
    return None
