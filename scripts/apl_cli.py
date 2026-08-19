#!/usr/bin/env python3
"""Unified command-line interface for Agentic Project Lifecycle contracts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "agentic-project-lifecycle"
AUDIT_SCRIPTS = PLUGIN / "skills" / "auditing-project-readiness" / "scripts"
if str(AUDIT_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(AUDIT_SCRIPTS))

from governance.execution_result import build_execution_result, validate_execution_result  # noqa: E402
from governance.issues import explain_code, issues_from_messages, render_issues  # noqa: E402
from governance.policy import validate_policy_profile  # noqa: E402
from governance.project_audit import build_project_audit  # noqa: E402
from governance.run_manifest import verify_event_log  # noqa: E402
from governance.runner import BoundedRunnerError, run_bounded_task  # noqa: E402
from governance.codex_backend import CodexBackend  # noqa: E402
from governance.schema_validation import SCHEMA_FILES, validate_schema_document  # noqa: E402
from governance_contracts import (  # noqa: E402
    validate_evidence_record,
    validate_gate_transition,
    validate_task_contract,
)
from validate_project_state import validate as validate_project_state  # noqa: E402

VERSION = "1.1.0-rc.1"


def _load(path: Path):
    text = path.read_text(encoding="utf-8")
    return json.loads(text) if path.suffix.lower() == ".json" else yaml.safe_load(text)


def _print_validation(kind: str, messages: list[str], output_format: str) -> int:
    issues = issues_from_messages(kind, messages)
    print(render_issues(issues, output_format=output_format, title=f"APL {kind.upper()}"))
    return 1 if issues else 0


def _validate(args: argparse.Namespace) -> int:
    data = _load(args.path)
    structural = validate_schema_document(args.kind, data)
    messages = list(structural)
    if args.kind == "task":
        messages.extend(validate_task_contract(data))
    elif args.kind == "gate":
        messages.extend(validate_gate_transition(data))
    elif args.kind == "evidence":
        messages.extend(validate_evidence_record(data, expected_commit=args.expected_commit))
    elif args.kind == "state":
        messages.extend(validate_project_state(args.path, strict=args.strict, root=args.root))
    elif args.kind == "policy":
        messages.extend(validate_policy_profile(data))
    elif args.kind == "execution":
        if args.task is None:
            messages.append("execution validation requires --task")
        else:
            messages.extend(validate_execution_result(data, contract=_load(args.task), root=args.root))
    return _print_validation(args.kind, messages, args.format)


def _execution(args: argparse.Namespace) -> int:
    result = build_execution_result(root=args.root, contract=_load(args.task), head_commit=args.head)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


def _audit(args: argparse.Namespace) -> int:
    report = build_project_audit(
        project_state=_load(args.state),
        task_contract=_load(args.task),
        gate_transition=_load(args.gate),
        execution_result=_load(args.execution),
        evidence_report=_load(args.evidence),
        policy_profile=_load(args.policy),
        repository_head=args.head,
        root=args.root,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["audit"]["status"] == "pass" else 1


def _doctor(args: argparse.Namespace) -> int:
    git = subprocess.run(["git", "--version"], text=True, capture_output=True, check=False)
    payload = {
        "version": VERSION,
        "python": sys.version.split()[0],
        "git": git.stdout.strip() if git.returncode == 0 else None,
        "schemas": len(list((PLUGIN / "schemas").glob("*.json"))),
        "skills": len(list((PLUGIN / "skills").glob("*/SKILL.md"))),
        "checks": {
            "git": git.returncode == 0,
            "schemas": len(SCHEMA_FILES) == len(list((PLUGIN / "schemas").glob("*.json"))),
            "skills": len(list((PLUGIN / "skills").glob("*/SKILL.md"))) == 7,
        },
    }
    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"APL DOCTOR: {'PASS' if all(payload['checks'].values()) else 'FAIL'}")
        for key, value in payload.items():
            if key != "checks":
                print(f"- {key}: {value}")
    return 0 if all(payload["checks"].values()) else 1


def _explain(args: argparse.Namespace) -> int:
    issue = explain_code(args.code)
    if issue is None:
        print(f"Unknown diagnostic code: {args.code}")
        return 1
    print(f"{issue.code}: {issue.rule}\nPath: {issue.path}\nMessage: {issue.message}\nRemediation: {issue.remediation}")
    return 0


def _events_verify(args: argparse.Namespace) -> int:
    messages = verify_event_log(args.path)
    if args.format == "json":
        print(json.dumps({"pass": not messages, "issues": messages}, indent=2, sort_keys=True))
    else:
        print(f"APL EVENTS: {'PASS' if not messages else 'FAIL'}")
        for message in messages:
            print(f"- {message}")
    return 1 if messages else 0


def _run(args: argparse.Namespace) -> int:
    if not args.experimental:
        print(
            "APL RUN: FAIL\n- --experimental is required for the bounded runner",
            file=sys.stderr,
        )
        return 1
    if args.backend != "codex":
        print(f"APL RUN: FAIL\n- unsupported backend: {args.backend}", file=sys.stderr)
        return 1

    from governance.codex_backend import CodexBackend
    from governance.runner import run_bounded_task

    backend = CodexBackend(
        model=args.model,
        executable=args.codex_executable,
        timeout_seconds=args.timeout_seconds,
    )
    report = run_bounded_task(
        root=args.root,
        task_contract=_load(args.task),
        policy_profile=_load(args.policy),
        backend=backend,
        output_root=args.output,
        confirm_task=args.confirm_task,
        timeout_seconds=args.timeout_seconds,
        run_id=args.run_id,
    )
    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"APL RUN: {report['run']['status'].upper()}")
        print(f"- run_id: {report['run']['id']}")
        print(f"- candidate_commit: {report['run'].get('candidate_commit')}")
        for issue in report.get("issues", []):
            print(f"- issue: {issue}")
    return 0 if report["run"]["status"] == "pass" else 1



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="apl", description="Agentic Project Lifecycle control-plane CLI")
    parser.add_argument("--version", action="version", version=f"apl {VERSION}")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="Validate one governance artifact")
    validate.add_argument("kind", choices=tuple(SCHEMA_FILES))
    validate.add_argument("path", type=Path)
    validate.add_argument("--format", choices=("text", "json", "sarif"), default="text")
    validate.add_argument("--expected-commit")
    validate.add_argument("--task", type=Path)
    validate.add_argument("--root", type=Path)
    validate.add_argument("--strict", action="store_true")
    validate.set_defaults(handler=_validate)

    execution = sub.add_parser("execution", help="Build an ExecutionResult from an observed Git diff")
    execution.add_argument("--root", type=Path, required=True)
    execution.add_argument("--task", type=Path, required=True)
    execution.add_argument("--head", default="HEAD")
    execution.add_argument("--output", type=Path)
    execution.set_defaults(handler=_execution)

    audit = sub.add_parser("audit", help="Run cross-contract project audit")
    for name in ("state", "task", "gate", "execution", "evidence", "policy"):
        audit.add_argument(f"--{name}", type=Path, required=True)
    audit.add_argument("--head", required=True)
    audit.add_argument("--root", type=Path)
    audit.set_defaults(handler=_audit)

    doctor = sub.add_parser("doctor", help="Inspect local APL dependencies and assets")
    doctor.add_argument("--format", choices=("text", "json"), default="text")
    doctor.set_defaults(handler=_doctor)

    explain = sub.add_parser("explain", help="Explain a stable diagnostic code")
    explain.add_argument("code")
    explain.set_defaults(handler=_explain)

    events = sub.add_parser("events", help="Work with tamper-evident event logs")
    events_sub = events.add_subparsers(dest="events_command", required=True)
    verify = events_sub.add_parser("verify", help="Verify a hash-chained JSONL event log")
    verify.add_argument("path", type=Path)
    verify.add_argument("--format", choices=("text", "json"), default="text")
    verify.set_defaults(handler=_events_verify)

    run = sub.add_parser(
        "run", help="Run one approved task through the experimental bounded runner"
    )
    run.add_argument("--experimental", action="store_true")
    run.add_argument("--backend", choices=("codex",), required=True)
    run.add_argument("--root", type=Path, required=True)
    run.add_argument("--task", type=Path, required=True)
    run.add_argument("--policy", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--confirm-task", required=True)
    run.add_argument("--model", required=True)
    run.add_argument("--codex-executable", default="codex")
    run.add_argument("--timeout-seconds", type=int, default=900)
    run.add_argument("--run-id")
    run.add_argument("--format", choices=("text", "json"), default="text")
    run.set_defaults(handler=_run)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.handler(args)
    except (BoundedRunnerError, OSError, RuntimeError, ValueError, yaml.YAMLError, json.JSONDecodeError) as exc:
        print(f"APL: FAIL\n- {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
