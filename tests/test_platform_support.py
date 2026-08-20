from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import platform_support as support  # noqa: E402


def test_registry_has_exactly_fifteen_unique_platforms() -> None:
    registry = support.load_registry()
    assert len(registry["platforms"]) == 15
    assert {item["id"] for item in registry["platforms"]} == {
        "agent-skills", "codex", "claude-code", "github-copilot", "cursor", "kimi-code",
        "gemini-cli", "opencode", "factory-droid", "amp", "devin", "pi", "hermes",
        "antigravity", "gemini-enterprise",
    }
    aliases = [alias for item in registry["platforms"] for alias in item["aliases"]]
    assert len(aliases) == len(set(aliases))


def test_inventory_is_sorted_regular_and_hashed() -> None:
    inventory = support.canonical_inventory()
    assert inventory == sorted(inventory, key=lambda item: item["path"])
    assert all(item["path"].startswith("skills/") for item in inventory)
    assert all(len(item["sha256"]) == 64 for item in inventory)


def test_rejects_unsafe_target_path() -> None:
    with pytest.raises(support.PlatformError, match="unsafe relative path"):
        support._safe_relative("../outside")


def test_repeated_bundle_builds_are_identical(tmp_path: Path) -> None:
    first = tmp_path / "one.zip"
    second = tmp_path / "two.zip"
    first_manifest = support.build_bundle("codex", first, epoch=1_787_000_000)
    second_manifest = support.build_bundle("codex", second, epoch=1_787_000_000)
    assert first_manifest == second_manifest
    assert first.read_bytes() == second.read_bytes()


def test_install_verify_and_force_rollback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "project"
    target = support.install_platform("codex", scope="project", root=root)
    assert support.verify_installation(target) == []
    original = (target / "APL_PLATFORM_MANIFEST.json").read_bytes()

    def fail_verify(path: Path, *, allow_development_link: bool = False) -> list[str]:
        if path == target:
            return ["injected post-publication failure"]
        return []

    monkeypatch.setattr(support, "verify_installation", fail_verify)
    with pytest.raises(support.PlatformError, match="published verification failed"):
        support.install_platform("codex", scope="project", root=root, force=True)
    assert (target / "APL_PLATFORM_MANIFEST.json").read_bytes() == original


def test_verify_detects_changed_and_extra_file(tmp_path: Path) -> None:
    target = support.install_platform("agent-skills", scope="project", root=tmp_path)
    changed = next(target.glob("skills/*/SKILL.md"))
    changed.write_text("changed\n", encoding="utf-8")
    (target / "extra.txt").write_text("extra\n", encoding="utf-8")
    errors = support.verify_installation(target)
    assert any("changed file" in error for error in errors)
    assert any("unexpected file" in error for error in errors)


def test_activation_contract_rejects_duplicate_and_missing_pressure(tmp_path: Path) -> None:
    digest = hashlib.sha256(b"transcript").hexdigest()
    record = {"schema_version": "1.0", "platform": "codex", "evidence_tier": "smoke-tested", "runs": [
        {"id": "same", "kind": "positive", "transcript": "a.jsonl", "transcript_sha256": digest, "passed": True},
        {"id": "same", "kind": "negative", "transcript": "b.jsonl", "transcript_sha256": digest, "passed": True},
    ]}
    path = tmp_path / "record.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    errors = support.validate_activation_record(path)
    assert any("duplicate run id" in error for error in errors)
    assert any("pressure" in error for error in errors)
