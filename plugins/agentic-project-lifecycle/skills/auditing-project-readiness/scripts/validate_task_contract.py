#!/usr/bin/env python3
from __future__ import annotations

from governance.cli import run_yaml_validator
from governance_contracts import validate_task_contract


def main() -> int:
    return run_yaml_validator(
        title="TASK CONTRACT",
        namespace="task",
        description="Validate a bounded task contract",
        validator=validate_task_contract,
    )


if __name__ == "__main__":
    raise SystemExit(main())
