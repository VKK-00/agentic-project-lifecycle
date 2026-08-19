#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import yaml

from governance.execution_result import validate_execution_result
from governance.issues import issues_from_messages, render_issues


def _load(path: Path):
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    return yaml.safe_load(text)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an actual execution result")
    parser.add_argument("path", type=Path)
    parser.add_argument("--task", type=Path, required=True)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--format", choices=("text", "json", "sarif"), default="text")
    args = parser.parse_args()
    try:
        data = _load(args.path)
        contract = _load(args.task)
        messages = validate_execution_result(data, contract=contract, root=args.root)
    except Exception as exc:
        messages = [f"cannot validate execution result: {exc}"]
    issues = issues_from_messages("execution", messages)
    print(render_issues(issues, output_format=args.format, title="EXECUTION RESULT"))
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
