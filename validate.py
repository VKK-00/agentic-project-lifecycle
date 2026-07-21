#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
PLUGIN_ROOT = ROOT / "plugins" / "agentic-project-lifecycle"
SKILLS_ROOT = PLUGIN_ROOT / "skills"


def static_checks() -> list[str]:
    errors: list[str] = []
    names: set[str] = set()
    suite = yaml.safe_load((ROOT / "suite.yaml").read_text(encoding="utf-8"))
    expected_names = set(suite.get("skills", []))
    expected_version = str(suite.get("version", ""))
    link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    manifest = yaml.safe_load((ROOT / "suite.yaml").read_text(encoding="utf-8"))
    if manifest.get("version") != "1.0.0" or manifest.get("status") != "stable":
        errors.append("suite.yaml must declare version 1.0.0 and status stable")
    expected = set(manifest.get("skills", []))
    actual = {path.name for path in SKILLS_ROOT.iterdir() if path.is_dir()}
    if expected != actual:
        errors.append(f"manifest skill set differs from filesystem: expected={sorted(expected)} actual={sorted(actual)}")
    declared_rules: set[str] = set()
    for directory in sorted(SKILLS_ROOT.iterdir()):
        if not directory.is_dir():
            continue
        path = directory / "SKILL.md"
        if not path.is_file():
            errors.append(f"missing {path}")
            continue
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---\n"):
            errors.append(f"{path}: missing YAML frontmatter")
            continue
        _, raw, body = text.split("---", 2)
        metadata = yaml.safe_load(raw)
        name = metadata.get("name")
        if name != directory.name:
            errors.append(f"{path}: name does not match directory")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", str(name)):
            errors.append(f"{path}: invalid skill name")
        if name in names:
            errors.append(f"duplicate skill name: {name}")
        names.add(name)
        skill_version = str(metadata.get("metadata", {}).get("version", ""))
        if skill_version != expected_version:
            errors.append(f"{path}: version {skill_version} does not match suite {expected_version}")
        if expected_version == "1.0.0" and metadata.get("metadata", {}).get("maturity") != "stable":
            errors.append(f"{path}: stable suite requires maturity: stable")
        description = str(metadata.get("description", ""))
        if not description.startswith("Use when "):
            errors.append(f"{path}: description must start with 'Use when '")
        if len(description) > 1024:
            errors.append(f"{path}: description exceeds 1024 characters")
        if len(body.split()) >= 500:
            errors.append(f"{path}: body exceeds 500 words")
        if metadata.get("metadata", {}).get("version") != "1.0.0" or metadata.get("metadata", {}).get("maturity") != "stable":
            errors.append(f"{path}: metadata must be 1.0.0 stable")
        for rule_id in re.findall(r"RULE-[A-Z]+-\d{2}", body):
            if rule_id in declared_rules:
                errors.append(f"duplicate normative rule id: {rule_id}")
            declared_rules.add(rule_id)
        if not (directory / "evals/evals.json").is_file():
            errors.append(f"missing {directory / 'evals/evals.json'}")
        agent_path = directory / "agents/openai.yaml"
        if not agent_path.is_file():
            errors.append(f"missing {agent_path}")
        else:
            agent = yaml.safe_load(agent_path.read_text(encoding="utf-8"))
            prompt = agent.get("interface", {}).get("default_prompt", "")
            if f"${name}" not in prompt:
                errors.append(f"{agent_path}: default_prompt does not invoke ${name}")
        for target in link_pattern.findall(body):
            if "://" in target or target.startswith("#"):
                continue
            clean = target.split("#", 1)[0]
            if clean and not (path.parent / clean).resolve().exists():
                errors.append(f"{path}: broken link {target}")
    if names != expected_names:
        errors.append(f"installed skill set differs from suite.yaml: {sorted(names ^ expected_names)}")
    for script in ROOT.rglob("*.py"):
        try:
            ast.parse(script.read_text(encoding="utf-8"), filename=str(script))
        except (OSError, SyntaxError, UnicodeDecodeError) as exc:
            errors.append(f"{script}: {exc}")
    return errors


def run(relative: str, timeout: int = 180) -> dict:
    result = subprocess.run(
        [sys.executable, str(ROOT / relative)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    return {
        "check": relative,
        "exit_code": result.returncode,
        "stdout": result.stdout[-5000:],
        "stderr": result.stderr[-5000:],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Agentic Project Lifecycle")
    parser.parse_args()
    errors = static_checks()
    checks = []
    for relative in [
        "evals/run_trigger_eval.py",
        "evals/run_project_trials.py",
        "evals/analyze_execution_traces.py",
        "evals/run_non_fixture_trials.py",
        "evals/run_static_ablation.py",
        "evals/analyze_rule_redundancy.py",
        "evals/run_instruction_ablation.py",
        "evals/check_promotion_gate.py",
        "scripts/validate_publication.py",
    ]:
        item = run(relative)
        checks.append(item)
        if item["exit_code"] != 0:
            errors.append(f"{relative} exited {item['exit_code']}")
        print(item["stdout"].strip())
        if item["stderr"].strip():
            print(item["stderr"].strip(), file=sys.stderr)
    report = {"pass": not errors, "static_errors": errors, "checks": checks}
    output = ROOT / "evals/results/validation-summary.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if errors:
        print("VALIDATION: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("VALIDATION: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
