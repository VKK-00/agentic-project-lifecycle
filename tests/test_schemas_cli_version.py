from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/agentic-project-lifecycle"
SCHEMAS = PLUGIN / "schemas"

EXPECTED_SCHEMAS = {
    "task-contract-v1.schema.json",
    "gate-transition-v1.schema.json",
    "evidence-record-v1.schema.json",
    "execution-result-v1.schema.json",
    "project-state-v2.schema.json",
    "policy-profile-v1.schema.json",
    "project-audit-v1.schema.json",
    "run-manifest-v1.schema.json",
}


def test_release_candidate_versions_are_consistent() -> None:
    suite = yaml.safe_load((ROOT / "suite.yaml").read_text(encoding="utf-8"))
    plugin = json.loads((PLUGIN / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert suite["version"] == "1.1.0-rc.1"
    assert suite["target_stable_version"] == "1.1.0"
    assert suite["status"] == "release-candidate"
    assert plugin["version"] == "1.1.0-rc.1"
    assert 'version = "1.1.0rc1"' in pyproject
    for path in (PLUGIN / "skills").glob("*/SKILL.md"):
        text = path.read_text(encoding="utf-8")
        assert "version: 1.1.0-rc.1" in text
        assert "maturity: release-candidate" in text


def test_formal_json_schemas_are_draft_2020_12_and_closed() -> None:
    assert {path.name for path in SCHEMAS.glob("*.json")} == EXPECTED_SCHEMAS
    for path in SCHEMAS.glob("*.json"):
        schema = json.loads(path.read_text(encoding="utf-8"))
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["type"] == "object"
        assert schema.get("unevaluatedProperties") is False
        jsonschema.Draft202012Validator.check_schema(schema)


def test_schema_examples_validate() -> None:
    examples = ROOT / "tests/schema_examples"
    for document in examples.glob("*.yaml"):
        data = yaml.safe_load(document.read_text(encoding="utf-8"))
        schema_name = data.pop("_schema")
        schema = json.loads((SCHEMAS / schema_name).read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(data)


def test_apl_cli_exposes_version_doctor_validate_and_explain(tmp_path: Path) -> None:
    cli = ROOT / "apl"
    version = subprocess.run([sys.executable, str(cli), "--version"], text=True, capture_output=True, check=False)
    assert version.returncode == 0
    assert version.stdout.strip() == "apl 1.1.0-rc.1"

    doctor = subprocess.run([sys.executable, str(cli), "doctor", "--format", "json"], text=True, capture_output=True, check=False)
    assert doctor.returncode == 0, doctor.stdout + doctor.stderr
    doctor_payload = json.loads(doctor.stdout)
    assert doctor_payload["schemas"] == 8
    assert doctor_payload["skills"] == 7

    policy = tmp_path / "policy.yaml"
    policy.write_text(
        (PLUGIN / "skills/orchestrating-large-projects/references/policies/default-software.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    validation = subprocess.run(
        [sys.executable, str(cli), "validate", "policy", str(policy), "--format", "json"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert validation.returncode == 0, validation.stdout + validation.stderr
    assert json.loads(validation.stdout)["pass"] is True

    explain = subprocess.run([sys.executable, str(cli), "explain", "APL-TASK-021"], text=True, capture_output=True, check=False)
    assert explain.returncode == 0
    assert "source-bound-approval" in explain.stdout


def test_promotion_gate_is_honest_about_missing_live_behavioral_evidence() -> None:
    run = subprocess.run(
        [sys.executable, str(ROOT / "evals/check_promotion_gate.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    report = json.loads(run.stdout)
    assert report["target"] == "1.1.0"
    assert report["promotable"] is False
    assert "live multi-run behavioral evaluation is missing" in report["blocking_conditions"]

    strict = subprocess.run(
        [sys.executable, str(ROOT / "evals/check_promotion_gate.py"), "--require-promotable"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert strict.returncode == 1


def test_apl_events_verify_hash_chain(tmp_path: Path) -> None:
    sys.path.insert(0, str(PLUGIN / "skills/auditing-project-readiness/scripts"))
    from governance.run_manifest import append_event
    log = tmp_path / "events.jsonl"
    append_event(log, run_id="RUN-CLI", event_type="run.started", actor={"role": "test"}, payload={})
    run = subprocess.run([sys.executable, str(ROOT / "apl"), "events", "verify", str(log), "--format", "json"], text=True, capture_output=True, check=False)
    assert run.returncode == 0, run.stdout + run.stderr
    assert json.loads(run.stdout)["pass"] is True
