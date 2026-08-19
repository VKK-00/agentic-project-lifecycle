#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from governance.project_audit import build_project_audit


def _load(path: Path):
    text = path.read_text(encoding="utf-8")
    return json.loads(text) if path.suffix.lower() == ".json" else yaml.safe_load(text)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit cross-contract project consistency")
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--task", type=Path, required=True)
    parser.add_argument("--gate", type=Path, required=True)
    parser.add_argument("--execution", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = build_project_audit(
        project_state=_load(args.state),
        task_contract=_load(args.task),
        gate_transition=_load(args.gate),
        execution_result=_load(args.execution),
        evidence_report=_load(args.evidence),
        policy_profile=_load(args.policy),
        repository_head=args.head,
        root=args.root,
    )
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0 if report["audit"]["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
