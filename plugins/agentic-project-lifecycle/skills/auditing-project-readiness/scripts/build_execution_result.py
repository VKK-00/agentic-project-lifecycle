#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from governance.execution_result import build_execution_result


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an execution result from an actual Git diff")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--task", type=Path, required=True)
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    contract = yaml.safe_load(args.task.read_text(encoding="utf-8"))
    result = build_execution_result(root=args.root, contract=contract, head_commit=args.head)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
