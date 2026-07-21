#!/usr/bin/env python3
"""Executed pressure-scenario instruction-coverage and per-rule ablation eval.

This evaluator measures the artifact that a Codex skill controls directly: the
instructions available after a skill is loaded. It is deterministic and
reproducible; it is not presented as an isolated live-model sampling run.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVALS = ROOT / "evals"
RESULTS = EVALS / "results"
SKILLS_ROOT = ROOT / "plugins" / "agentic-project-lifecycle" / "skills"


def normalize(text: str) -> str:
    return " ".join(text.lower().split())


def has_any(text: str, group: list[str]) -> bool:
    value = normalize(text)
    return any(normalize(term) in value for term in group)


def score(text: str, case: dict) -> float:
    required = case.get("required_groups", [])
    forbidden = case.get("forbidden_groups", [])
    positive = sum(has_any(text, group) for group in required) / max(1, len(required))
    penalty = (
        sum(has_any(text, group) for group in forbidden) / len(forbidden)
        if forbidden
        else 0.0
    )
    return max(0.0, min(1.0, positive - 0.4 * penalty))


def remove_rule(text: str, rule_id: str) -> str:
    return "\n".join(line for line in text.splitlines() if rule_id not in line)


def main() -> int:
    cases = json.loads((EVALS / "behavior-cases.json").read_text(encoding="utf-8"))["cases"]
    baseline = (EVALS / "baseline/building-large-software-projects-SKILL.md").read_text(encoding="utf-8")
    skills = {
        path.parent.name: path.read_text(encoding="utf-8")
        for path in SKILLS_ROOT.glob("*/SKILL.md")
    }
    rows = []
    for case in cases:
        rule_id = case["id"]
        full_text = skills[case["skill"]]
        ablated_text = remove_rule(full_text, rule_id)
        baseline_score = score(baseline, case)
        full_score = score(full_text, case)
        ablated_score = score(ablated_text, case)
        rows.append(
            {
                "rule_id": rule_id,
                "skill": case["skill"],
                "baseline": round(baseline_score, 4),
                "full": round(full_score, 4),
                "ablated": round(ablated_score, 4),
                "baseline_delta": round(full_score - baseline_score, 4),
                "ablation_delta": round(full_score - ablated_score, 4),
                "positive_effect": full_score > ablated_score and full_score >= baseline_score,
            }
        )
    count = len(rows)
    baseline_average = sum(row["baseline"] for row in rows) / count
    skill_average = sum(row["full"] for row in rows) / count
    ablated_average = sum(row["ablated"] for row in rows) / count
    failed = [row["rule_id"] for row in rows if not row["positive_effect"]]
    report = {
        "kind": "executed-pressure-scenario-instruction-ablation",
        "scope": "Measures pressure-scenario rubric coverage in the complete loaded skill versus the original monolithic baseline and versus removal of each retained normative rule.",
        "limitations": "Deterministic skill-instruction coverage eval; it does not claim isolated live-Codex sampling or universal model compliance.",
        "case_count": count,
        "baseline_score": round(baseline_average, 4),
        "skill_score": round(skill_average, 4),
        "ablated_score": round(ablated_average, 4),
        "advantage": round(skill_average - baseline_average, 4),
        "all_retained_rules_positive_effect": not failed,
        "failed_rules": failed,
        "rules": rows,
    }
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "instruction-ablation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in report.items() if k != "rules"}, indent=2))
    return 0 if report["advantage"] > 0 and not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
