from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_threat_model_covers_agentic_trust_boundaries() -> None:
    text = (ROOT / "docs/THREAT_MODEL.md").read_text(encoding="utf-8")
    for phrase in (
        "Goal hijacking",
        "Tool misuse",
        "Identity and privilege abuse",
        "Agentic supply chain",
        "Unexpected code execution",
        "Evidence fabrication",
        "Approval bypass",
        "Memory poisoning",
    ):
        assert phrase in text
    assert "asset" in text.lower()
    assert "residual risk" in text.lower()


def test_hostile_fixture_catalog_has_expected_attack_surfaces() -> None:
    catalog = json.loads((ROOT / "tests/hostile_fixtures/catalog.json").read_text(encoding="utf-8"))
    ids = {item["id"] for item in catalog["fixtures"]}
    assert ids >= {
        "readme-goal-hijack",
        "agents-permission-broadening",
        "symlink-escape",
        "fake-evidence",
        "source-mutating-verifier",
        "malicious-package-hook",
        "mcp-indirect-injection",
    }
    assert all(item["expected_control"] for item in catalog["fixtures"])
