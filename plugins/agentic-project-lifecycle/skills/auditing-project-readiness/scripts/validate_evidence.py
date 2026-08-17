#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from governance_contracts import validate_evidence_record


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate source-bound evidence")
    parser.add_argument("path", type=Path)
    parser.add_argument("--expected-commit")
    args = parser.parse_args()
    try:
        data = yaml.safe_load(args.path.read_text(encoding="utf-8"))
        errors = validate_evidence_record(
            data, expected_commit=args.expected_commit
        )
    except Exception as exc:
        errors = [f"cannot parse YAML: {exc}"]
    if errors:
        print("EVIDENCE: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("EVIDENCE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
