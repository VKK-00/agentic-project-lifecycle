#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from governance_contracts import validate_gate_transition


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a lifecycle gate transition")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    try:
        data = yaml.safe_load(args.path.read_text(encoding="utf-8"))
        errors = validate_gate_transition(data)
    except Exception as exc:
        errors = [f"cannot parse YAML: {exc}"]
    if errors:
        print("GATE TRANSITION: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("GATE TRANSITION: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
