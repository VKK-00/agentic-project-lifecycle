from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_NAME = "agentic-project-lifecycle"
PLUGIN_ROOT = ROOT / "plugins" / PLUGIN_NAME


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_plugin_manifest_and_marketplace_are_consistent() -> None:
    manifest = json.loads(
        (PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    marketplace = json.loads(
        (ROOT / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8")
    )
    entry = marketplace["plugins"][0]

    assert manifest["name"] == PLUGIN_NAME
    assert manifest["version"] == "1.1.0-rc.1"
    assert manifest["skills"] == "./skills/"
    assert manifest["license"] == "Apache-2.0"
    assert entry["name"] == manifest["name"]
    assert entry["source"] == {
        "source": "local",
        "path": "./plugins/agentic-project-lifecycle",
    }


def test_directory_submission_case_counts_are_exact() -> None:
    cases = json.loads((ROOT / "submission" / "test-cases.json").read_text(encoding="utf-8"))
    assert len(cases["positive"]) == 5
    assert len(cases["negative"]) == 3
    ids = [case["id"] for group in cases.values() for case in group]
    assert len(ids) == len(set(ids))


def test_localized_readmes_are_public_and_internal_analysis_is_absent() -> None:
    readmes = [ROOT / "README.md", ROOT / "README.ru.md", ROOT / "README.uk.md"]
    for readme in readmes:
        text = readme.read_text(encoding="utf-8")
        assert "README.ru.md" in text
        assert "README.uk.md" in text
    russian_markdown = sorted(
        path.relative_to(ROOT).as_posix() for path in ROOT.rglob("*.ru.md")
    )
    assert russian_markdown == ["README.ru.md"]


def test_publication_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_publication.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_release_archives_are_reproducible_and_safe(tmp_path: Path) -> None:
    outputs = [tmp_path / "first", tmp_path / "second"]
    env = os.environ.copy()
    env["SOURCE_DATE_EPOCH"] = "315532800"
    for output in outputs:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "build_release.py"),
                "--version",
                "1.1.0-rc.1",
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

    expected = {
        "agentic-project-lifecycle-1.1.0-rc.1.zip",
        "agentic-project-lifecycle-1.1.0-rc.1.tar.gz",
        "agentic-project-lifecycle-1.1.0-rc.1.spdx.json",
        "promotion-gate.json",
        "validation-report.md",
        "SHA256SUMS",
    }
    assert {path.name for path in outputs[0].iterdir()} == expected
    assert {name: file_hash(outputs[0] / name) for name in expected} == {
        name: file_hash(outputs[1] / name) for name in expected
    }

    zip_path = outputs[0] / "agentic-project-lifecycle-1.1.0-rc.1.zip"
    tar_path = outputs[0] / "agentic-project-lifecycle-1.1.0-rc.1.tar.gz"
    with zipfile.ZipFile(zip_path) as archive:
        zip_names = archive.namelist()
    with tarfile.open(tar_path) as archive:
        tar_names = archive.getnames()
    for names in [zip_names, tar_names]:
        assert names
        assert all(name.startswith(f"{PLUGIN_NAME}/") for name in names)
        assert all(".." not in Path(name).parts for name in names)
        assert all("__pycache__" not in name and not name.endswith(".pyc") for name in names)
