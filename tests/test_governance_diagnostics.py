from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "plugins/agentic-project-lifecycle/skills/auditing-project-readiness/scripts"
sys.path.insert(0, str(SCRIPTS))

from governance.issues import Issue, issues_from_messages, render_issues  # noqa: E402


def test_known_message_gets_stable_code_and_path() -> None:
    issues = issues_from_messages(
        "task",
        ["approval is not bound to the task source commit"],
    )
    assert issues == [
        Issue(
            code="APL-TASK-021",
            severity="error",
            path="approval.source_commit",
            rule="source-bound-approval",
            message="approval is not bound to the task source commit",
            remediation="Approve the current task contract against its source commit.",
        )
    ]


def test_unknown_message_gets_deterministic_fallback_code() -> None:
    first = issues_from_messages("task", ["novel invariant failed"])[0]
    second = issues_from_messages("task", ["novel invariant failed"])[0]
    assert first.code == second.code
    assert first.code.startswith("APL-TASK-X")


def test_json_and_sarif_rendering_are_machine_readable() -> None:
    issue = Issue("APL-TASK-001", "error", "task.id", "required", "task.id is required", "Set task.id.")
    json_payload = json.loads(render_issues([issue], output_format="json", title="TASK CONTRACT"))
    assert json_payload["pass"] is False
    assert json_payload["issues"][0]["code"] == "APL-TASK-001"

    sarif = json.loads(render_issues([issue], output_format="sarif", title="TASK CONTRACT"))
    assert sarif["version"] == "2.1.0"
    result = sarif["runs"][0]["results"][0]
    assert result["ruleId"] == "APL-TASK-001"
    assert result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] == "task.id"


def test_legacy_text_preserves_human_message() -> None:
    issue = Issue("APL-TASK-001", "error", "task.id", "required", "task.id is required", "Set task.id.")
    rendered = render_issues([issue], output_format="text", title="TASK CONTRACT")
    assert rendered == "TASK CONTRACT: FAIL\n- [APL-TASK-001] task.id is required"


def test_task_cli_supports_json_without_breaking_legacy_text(tmp_path: Path) -> None:
    invalid = tmp_path / "task.yaml"
    invalid.write_text(yaml.safe_dump({"schema_version": "1.0"}), encoding="utf-8")
    script = SCRIPTS / "validate_task_contract.py"
    json_run = subprocess.run(
        [sys.executable, str(script), str(invalid), "--format", "json"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert json_run.returncode == 1
    payload = json.loads(json_run.stdout)
    assert payload["pass"] is False
    assert all(item["code"].startswith("APL-TASK-") for item in payload["issues"])

    text_run = subprocess.run(
        [sys.executable, str(script), str(invalid)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert text_run.returncode == 1
    assert text_run.stdout.startswith("TASK CONTRACT: FAIL")
