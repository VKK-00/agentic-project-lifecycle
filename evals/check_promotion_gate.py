#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "evals/results"
SKILLS_ROOT = ROOT / "plugins" / "agentic-project-lifecycle" / "skills"


def load(name: str) -> dict:
    path = RESULTS / name
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    blockers: list[str] = []

    trigger = load("trigger-report.json").get("heldout", {})
    if trigger.get("recall", 0) < 0.95:
        blockers.append("held-out trigger recall is below 0.95")
    if trigger.get("false_positive_rate", 1) > 0.05:
        blockers.append("held-out false-positive rate exceeds 0.05")
    if trigger.get("exact_accuracy", 0) < 0.90:
        blockers.append("held-out exact routing accuracy is below 0.90")

    fixture = load("project-trials.json").get("projects", [])
    if len(fixture) < 4 or any(item.get("status") != "pass" for item in fixture):
        blockers.append("four executable fixture modes have not all passed")
    if len({item.get("mode") for item in fixture}) < 4:
        blockers.append("fixture trials do not cover four distinct modes")

    real = load("non-fixture-project-trials.json")
    real_projects = real.get("projects", [])
    if len(real_projects) < 3 or any(item.get("status") != "pass" for item in real_projects):
        blockers.append("at least three non-fixture project workflows must pass")
    if len({item.get("mode") for item in real_projects}) < 3:
        blockers.append("non-fixture workflows must span at least three modes")

    traces = load("trace-analysis.json")
    if traces.get("systematic_overwork", True):
        blockers.append("execution traces show systematic unnecessary work")
    if traces.get("suite", {}).get("median_unnecessary_actions", 999) >= traces.get("baseline", {}).get("median_unnecessary_actions", 0):
        blockers.append("suite trace efficiency does not improve on the baseline proxy")
    if real.get("trace_summary", {}).get("systematic_overwork", True):
        blockers.append("non-fixture traces show systematic unnecessary work")

    ablation = load("instruction-ablation.json")
    if ablation.get("advantage", 0) <= 0.10:
        blockers.append("executed baseline advantage is not greater than 0.10")
    if not ablation.get("all_retained_rules_positive_effect", False):
        blockers.append("one or more retained rules lack positive ablation effect")
    if not ablation.get("limitations"):
        blockers.append("evaluator limitations are not explicit")

    static = load("static-ablation-report.json")
    if not static.get("pass", False):
        blockers.append("declared rules and assertion ownership are inconsistent")
    redundancy = load("rule-redundancy.json")
    if not redundancy.get("pass", False):
        blockers.append("high-overlap rule pairs remain")

    removed = load("rules-removed.json").get("removed_rules", [])
    if not removed:
        blockers.append("no rule-removal decision is recorded")

    import yaml
    manifest = yaml.safe_load((ROOT / "suite.yaml").read_text(encoding="utf-8"))
    if manifest.get("version") != "1.0.0" or manifest.get("status") != "stable":
        blockers.append("suite manifest is not 1.0.0 stable")
    for path in sorted(SKILLS_ROOT.glob("*/SKILL.md")):
        text = path.read_text(encoding="utf-8")
        if "version: 1.0.0\n" not in text or "maturity: stable\n" not in text:
            blockers.append(f"{path.parent.name} is not marked 1.0.0 stable")

    report = {
        "target": "1.0.0",
        "promotable": not blockers,
        "recommended_version": "1.0.0" if not blockers else "1.0.0-rc1",
        "blocking_conditions": blockers,
        "evidence": {
            "pressure_eval": {
                "baseline_score": ablation.get("baseline_score"),
                "skill_score": ablation.get("skill_score"),
                "advantage": ablation.get("advantage"),
                "retained_rules": ablation.get("case_count"),
                "all_retained_rules_positive_effect": ablation.get("all_retained_rules_positive_effect"),
            },
            "triggering": {
                "heldout_cases": len(trigger.get("cases", [])),
                "precision": trigger.get("precision"),
                "recall": trigger.get("recall"),
                "false_positive_rate": trigger.get("false_positive_rate"),
                "exact_accuracy": trigger.get("exact_accuracy"),
            },
            "projects": {
                "executable_fixture_projects": len(fixture),
                "fixture_modes": sorted({item.get("mode") for item in fixture}),
                "non_fixture_projects": len(real_projects),
                "non_fixture_modes": sorted({item.get("mode") for item in real_projects}),
            },
            "traces": {
                "suite_median_unnecessary_actions": traces.get("suite", {}).get("median_unnecessary_actions"),
                "baseline_proxy_median_unnecessary_actions": traces.get("baseline", {}).get("median_unnecessary_actions"),
                "real_project_systematic_overwork": real.get("trace_summary", {}).get("systematic_overwork"),
            },
            "removed_rules": removed,
        },
        "evaluation_scope": ablation.get("scope"),
        "evaluation_limitations": ablation.get("limitations"),
    }
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "promotion-gate.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["promotable"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
