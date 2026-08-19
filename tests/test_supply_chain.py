from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.1.0-rc.1"
PLUGIN_NAME = "agentic-project-lifecycle"

PINNED_ACTIONS = {
    "actions/checkout": "3d3c42e5aac5ba805825da76410c181273ba90b1",
    "actions/setup-python": "5fda3b95a4ea91299a34e894583c3862153e4b97",
    "actions/upload-artifact": "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
    "github/codeql-action": "5595ccaf912efad79be6eef63a5619ff05969be3",
    "actions/dependency-review-action": "a1d282b36b6f3519aa1f3fc636f609c47dddb294",
    "ossf/scorecard-action": "2d1146689b8cda280b9bc96326124645441f03bc",
    "actions/attest": "1e69f48acb82d1966a394da916b4c1698aa569d6",
}

USES_RE = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)", re.MULTILINE)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_sbom_builder_is_deterministic_spdx_23(tmp_path: Path) -> None:
    outputs = [tmp_path / "first.spdx.json", tmp_path / "second.spdx.json"]
    env = os.environ.copy()
    env["SOURCE_DATE_EPOCH"] = "315532800"
    for output in outputs:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "build_sbom.py"),
                "--version",
                VERSION,
                "--output",
                str(output),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    assert outputs[0].read_bytes() == outputs[1].read_bytes()
    document = json.loads(outputs[0].read_text(encoding="utf-8"))
    assert document["spdxVersion"] == "SPDX-2.3"
    assert document["dataLicense"] == "CC0-1.0"
    assert document["documentNamespace"].startswith(
        "https://github.com/VKK-00/agentic-project-lifecycle/spdx/"
    )
    package = document["packages"][0]
    assert package["name"] == PLUGIN_NAME
    assert package["versionInfo"] == VERSION
    assert package["licenseConcluded"] == "Apache-2.0"
    assert re.fullmatch(r"[0-9a-f]{40}", package["packageVerificationCode"]["packageVerificationCodeValue"])
    assert any(item["fileName"].endswith("SKILL.md") for item in document["files"])
    for item in document["files"]:
        algorithms = {checksum["algorithm"] for checksum in item["checksums"]}
        assert {"SHA1", "SHA256"}.issubset(algorithms)
    relationships = document["relationships"]
    assert any(item["relationshipType"] == "CONTAINS" for item in relationships)
    assert any(item["relationshipType"] == "DEPENDS_ON" for item in relationships)


def test_release_bundle_contains_checksums_for_sbom(tmp_path: Path) -> None:
    output = tmp_path / "dist"
    env = os.environ.copy()
    env["SOURCE_DATE_EPOCH"] = "315532800"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "build_release.py"),
            "--version",
            VERSION,
            "--output",
            str(output),
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    sbom = output / f"{PLUGIN_NAME}-{VERSION}.spdx.json"
    assert sbom.is_file()
    checksums = (output / "SHA256SUMS").read_text(encoding="utf-8")
    assert f"{sha256(sbom)}  {sbom.name}" in checksums


def test_reusable_action_and_repository_governance_files_exist() -> None:
    action = (ROOT / "action.yml").read_text(encoding="utf-8")
    assert "name: Agentic Project Lifecycle" in action
    assert "runs:" in action and "using: composite" in action
    assert "scripts/apl_cli.py" in action
    assert "eval " not in action
    assert "curl " not in action
    assert "git push" not in action

    codeowners = (ROOT / ".github" / "CODEOWNERS").read_text(encoding="utf-8")
    for protected in (
        "/plugins/agentic-project-lifecycle/skills/",
        "/plugins/agentic-project-lifecycle/schemas/",
        "/scripts/",
        "/.github/workflows/",
    ):
        assert protected in codeowners

    template = (ROOT / ".github" / "pull_request_template.md").read_text(
        encoding="utf-8"
    )
    for heading in ("## Change", "## Risk", "## Evidence", "## Rollback"):
        assert heading in template

    governance = (ROOT / "docs" / "REPOSITORY_GOVERNANCE.md").read_text(
        encoding="utf-8"
    )
    for phrase in (
        "required pull request",
        "stale approvals",
        "force pushes",
        "CODEOWNERS",
        "required status checks",
    ):
        assert phrase in governance


def test_security_workflows_are_minimally_privileged_and_pinned() -> None:
    required = {
        "codeql.yml",
        "dependency-review.yml",
        "scorecard.yml",
        "release-attestation.yml",
        "mutation.yml",
    }
    workflows = ROOT / ".github" / "workflows"
    assert required.issubset({path.name for path in workflows.glob("*.yml")})
    assert not (workflows / "export-source-snapshot.yml").exists()

    for path in sorted(workflows.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        for reference in USES_RE.findall(text):
            assert "@" in reference, f"unversioned action in {path}: {reference}"
            action, ref = reference.rsplit("@", 1)
            assert re.fullmatch(r"[0-9a-f]{40}", ref), (
                f"action must be pinned to a full commit SHA in {path}: {reference}"
            )
            expected = next(
                (sha for prefix, sha in PINNED_ACTIONS.items() if action.startswith(prefix)),
                None,
            )
            assert expected is not None, f"unexpected external action in {path}: {action}"
            assert ref == expected, f"unexpected pin for {action}: {ref}"

    codeql = (workflows / "codeql.yml").read_text(encoding="utf-8")
    assert "security-events: write" in codeql
    assert "contents: read" in codeql

    dependency = (workflows / "dependency-review.yml").read_text(encoding="utf-8")
    assert "pull_request:" in dependency
    assert "contents: read" in dependency
    assert "security-events: write" not in dependency

    scorecard = (workflows / "scorecard.yml").read_text(encoding="utf-8")
    assert "security-events: write" in scorecard
    assert "id-token: write" in scorecard

    attestation = (workflows / "release-attestation.yml").read_text(encoding="utf-8")
    assert 'tags: ["v*"]' in attestation
    assert "attestations: write" in attestation
    assert "id-token: write" in attestation
    assert "sbom-path:" in attestation
    assert "subject-checksums:" in attestation

    mutation = (workflows / "mutation.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in mutation
    assert "mutmut run" in mutation
    assert "contents: read" in mutation

    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for runner_test in (
        "tests/runner/test_bounded_runner.py",
        "tests/runner/test_codex_backend.py",
    ):
        assert runner_test in pyproject


def test_ci_runs_one_pinned_dependency_audit_and_drops_checkout_credentials() -> None:
    workflows = ROOT / ".github" / "workflows"
    text = (workflows / "ci.yml").read_text(encoding="utf-8")
    assert text.count("pip-audit==2.10.1") == 1
    assert text.count("python -m pip_audit") == 1

    for path in workflows.glob("*.yml"):
        workflow = path.read_text(encoding="utf-8")
        if "actions/checkout@" in workflow:
            assert "persist-credentials: false" in workflow, path


def test_release_attestation_binds_tag_to_manifest_version() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "release-attestation.yml"
    ).read_text(encoding="utf-8")

    assert "plugin.json" in workflow
    assert "GITHUB_REF_NAME" in workflow
    assert '"v${VERSION}"' in workflow
    assert "steps.version.outputs.version" in workflow
    assert "--version 1.1.0-rc.1" not in workflow
    assert "agentic-project-lifecycle-1.1.0-rc.1.zip" not in workflow
