from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "plugins" / "agentic-project-lifecycle"
SKILLS_ROOT = PLUGIN_ROOT / "skills"


def test_stable_version_is_consistent() -> None:
    suite = yaml.safe_load((ROOT / "suite.yaml").read_text(encoding="utf-8"))
    assert suite["version"] == "1.0.0"
    assert suite["status"] == "stable"
    assert len(suite["skills"]) == 7
    for name in suite["skills"]:
        text = (SKILLS_ROOT / name / "SKILL.md").read_text(encoding="utf-8")
        _, raw, _ = text.split("---", 2)
        metadata = yaml.safe_load(raw)
        assert metadata["metadata"]["version"] == "1.0.0"
        assert metadata["metadata"]["maturity"] == "stable"


def test_all_retained_rules_have_positive_effect() -> None:
    report = json.loads((ROOT / "evals/results/instruction-ablation.json").read_text(encoding="utf-8"))
    assert report["advantage"] > 0.10
    assert report["all_retained_rules_positive_effect"] is True
    assert report["failed_rules"] == []
    assert report["case_count"] == 42


def test_trigger_false_positive_rate_and_recall() -> None:
    heldout = json.loads((ROOT / "evals/results/trigger-report.json").read_text(encoding="utf-8"))["heldout"]
    assert heldout["false_positive_rate"] <= 0.05
    assert heldout["recall"] >= 0.95
    assert heldout["exact_accuracy"] >= 0.90


def test_project_modes_and_trace_efficiency() -> None:
    fixture = json.loads((ROOT / "evals/results/project-trials.json").read_text(encoding="utf-8"))["projects"]
    real = json.loads((ROOT / "evals/results/non-fixture-project-trials.json").read_text(encoding="utf-8"))["projects"]
    traces = json.loads((ROOT / "evals/results/trace-analysis.json").read_text(encoding="utf-8"))
    assert len(fixture) == 4 and all(p["status"] == "pass" for p in fixture)
    assert {p["mode"] for p in fixture} == {"saas", "ai", "brownfield", "rescue"}
    assert len(real) == 3 and all(p["status"] == "pass" for p in real)
    assert len({p["mode"] for p in real}) == 3
    assert traces["systematic_overwork"] is False
    assert traces["suite"]["median_unnecessary_actions"] < traces["baseline"]["median_unnecessary_actions"]


def test_redundant_rule_was_removed() -> None:
    removed = json.loads((ROOT / "evals/results/rules-removed.json").read_text(encoding="utf-8"))["removed_rules"]
    assert [item["id"] for item in removed] == ["RULE-ORCH-07"]
    assert "RULE-ORCH-07" not in (
        SKILLS_ROOT / "orchestrating-large-projects" / "SKILL.md"
    ).read_text(encoding="utf-8")


def test_promotion_gate_passes() -> None:
    report = json.loads((ROOT / "evals/results/promotion-gate.json").read_text(encoding="utf-8"))
    assert report["promotable"] is True
    assert report["recommended_version"] == "1.0.0"
    assert report["blocking_conditions"] == []


def test_installer_smoke(tmp_path: Path) -> None:
    target = tmp_path / ".agents" / "skills"
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/install_skills.py"), "--target", str(target)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    installed = {p.name for p in target.iterdir() if p.is_dir()}
    suite = yaml.safe_load((ROOT / "suite.yaml").read_text(encoding="utf-8"))
    assert installed == set(suite["skills"])
    second = subprocess.run(
        [sys.executable, str(ROOT / "scripts/install_skills.py"), "--target", str(target)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert second.returncode != 0
    assert "refusing to overwrite" in second.stderr + second.stdout
