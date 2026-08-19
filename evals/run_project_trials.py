#!/usr/bin/env python3
"""Run deterministic fixture-project checks and publish stable trace evidence."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

import yaml

ROOT = Path(__file__).resolve().parents[1]
EVALS = ROOT / "evals"
RESULTS = EVALS / "results"
AUDIT_SCRIPTS = (
    ROOT
    / "plugins"
    / "agentic-project-lifecycle"
    / "skills"
    / "auditing-project-readiness"
    / "scripts"
)
PROJECTS = (
    ("greenfield-saas", "saas"),
    ("ai-assistant", "ai"),
    ("brownfield-modernization", "brownfield"),
    ("rescue-project", "rescue"),
)
_UNITTEST_DURATION_RE = re.compile(
    r"Ran (\d+) (tests?) in \d+(?:\.\d+)?s"
)


def load_state_validator():
    spec = importlib.util.spec_from_file_location(
        "state_validator", AUDIT_SCRIPTS / "validate_project_state.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.validate


def run_command(argv: list[str], cwd: Path) -> dict[str, object]:
    started = time.monotonic()
    result = subprocess.run(
        argv,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    return {
        "name": " ".join(argv),
        "argv": argv,
        "exit_code": result.returncode,
        "duration_ms": round((time.monotonic() - started) * 1000),
        "stdout": result.stdout[-1500:],
        "stderr": result.stderr[-1500:],
        "necessary": True,
    }


def stable_stream(value: str) -> str:
    return _UNITTEST_DURATION_RE.sub(r"Ran \1 \2 in <elapsed>s", value)


def stable_action(action: dict[str, object]) -> dict[str, object]:
    stable: dict[str, object] = {}
    for key, value in action.items():
        if key == "duration_ms":
            continue
        if key in {"stdout", "stderr"} and isinstance(value, str):
            value = stable_stream(value)
        stable[key] = value
    return stable


def check_trace(path: Path) -> list[str]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    for requirement_id, requirement in (data.get("requirements") or {}).items():
        for field in ("implemented_by", "verified_by", "released_in"):
            if not requirement.get(field):
                errors.append(f"{requirement_id}.{field}")
    for test_id, test in (data.get("tests") or {}).items():
        if test.get("evidence") not in (data.get("evidence") or {}):
            errors.append(f"{test_id}.evidence")
    return errors


def build_context(root: Path, manifest: Path, output: Path) -> list[str]:
    data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    shutil.rmtree(output, ignore_errors=True)
    output.mkdir(parents=True)
    copied: list[str] = []
    resolved_root = root.resolve()
    for relative in data.get("read", []):
        source = (root / relative).resolve()
        if source != resolved_root and resolved_root not in source.parents:
            raise ValueError(relative)
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(relative)
    shutil.copy2(manifest, output / "context-manifest.yaml")
    (output / "task-packet.md").write_text(
        f"# Task packet\n\n{data['goal']}\n", encoding="utf-8"
    )
    return copied


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def fixture_trial(
    *,
    validate_state,
    source_root: Path,
    name: str,
    mode: str,
) -> tuple[dict[str, object], dict[str, object]]:
    project = source_root / name
    shutil.copytree(EVALS / "fixtures" / name, project)
    actions: list[dict[str, object]] = []

    state_errors = validate_state(project / "docs/project-state.yaml")
    actions.append(
        {
            "name": "validate project-state",
            "exit_code": 1 if state_errors else 0,
            "observed": state_errors,
            "necessary": True,
        }
    )

    trace_errors = check_trace(project / "docs/traceability.yaml")
    actions.append(
        {
            "name": "check traceability",
            "exit_code": 1 if trace_errors else 0,
            "observed": trace_errors,
            "necessary": True,
        }
    )

    context_output = RESULTS / "trial-context" / name
    copied = build_context(
        project,
        project / "specs/FEAT-001/context-manifest.yaml",
        context_output,
    )
    actions.append(
        {
            "name": "build minimal context pack",
            "exit_code": 0,
            "observed": copied,
            "necessary": True,
        }
    )

    evidence = project / "evidence/latest"
    evidence.mkdir(parents=True, exist_ok=True)
    checks: list[dict[str, object]] = []
    config = yaml.safe_load((project / "verification.yaml").read_text(encoding="utf-8"))
    for item in config["commands"]:
        result = run_command(item["run"], project)
        checks.append(result)
        actions.append(stable_action(result))
    report = {
        "checks": checks,
        "summary": {
            "passed": sum(item["exit_code"] == 0 for item in checks),
            "failed": sum(item["exit_code"] != 0 for item in checks),
        },
    }
    write_json(evidence / "report.json", report)

    required = [
        project / "docs/07-release/ROLLBACK.md",
        project / "docs/08-operations/OBSERVABILITY.md",
        project / "docs/08-operations/RUNBOOK.md",
        project / "docs/05-planning/releases/v0.1-alpha.yaml",
        evidence / "report.json",
    ]
    missing = [str(path.relative_to(project)) for path in required if not path.exists()]
    actions.append(
        {
            "name": "check release readiness",
            "exit_code": 1 if missing or report["summary"]["failed"] else 0,
            "observed": missing,
            "necessary": True,
        }
    )

    status = "pass" if all(item["exit_code"] == 0 for item in actions) else "fail"
    row = {
        "project": name,
        "mode": mode,
        "status": status,
        "actions": len(actions),
        "repository_type": "executable-fixture",
    }
    trace = {"project": name, "mode": mode, "actions": actions}
    return row, trace


def write_baseline_trace() -> None:
    broad = [
        "read lifecycle",
        "read interviewing",
        "read artifacts",
        "read planning",
        "read release",
        "create charter",
        "create PRD",
        "create roadmap",
        "ask generic discovery",
    ]
    needed = {
        "saas": set(broad[:8]),
        "ai": set(broad[:8]),
        "brownfield": set(broad[:5]),
        "rescue": set(broad[:3]),
    }
    traces = [
        {
            "project": name,
            "mode": mode,
            "actions": [
                {"name": action, "necessary": action in needed[mode]}
                for action in broad
            ],
        }
        for name, mode in PROJECTS
    ]
    write_json(
        RESULTS / "execution-traces-baseline.json",
        {"kind": "monolithic-workflow-proxy", "traces": traces},
    )


def main() -> int:
    validate_state = load_state_validator()
    rows: list[dict[str, object]] = []
    traces: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="skill-fixtures-") as temporary:
        source_root = Path(temporary)
        for name, mode in PROJECTS:
            row, trace = fixture_trial(
                validate_state=validate_state,
                source_root=source_root,
                name=name,
                mode=mode,
            )
            rows.append(row)
            traces.append(trace)

    write_json(
        RESULTS / "project-trials.json",
        {"kind": "executable-fixture-project-trials", "projects": rows},
    )
    write_json(
        RESULTS / "execution-traces-suite.json",
        {"kind": "real-command-traces", "traces": traces},
    )
    write_baseline_trace()
    print(json.dumps(rows, indent=2))
    return 0 if all(item["status"] == "pass" for item in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
