#!/usr/bin/env python3
from __future__ import annotations

from governance.cli import run_yaml_validator
from governance_contracts import validate_gate_transition


def main() -> int:
    return run_yaml_validator(
        title="GATE TRANSITION",
        namespace="gate",
        description="Validate a lifecycle gate transition",
        validator=validate_gate_transition,
    )


if __name__ == "__main__":
    raise SystemExit(main())
