#!/usr/bin/env python3
from __future__ import annotations

from governance.cli import run_yaml_validator
from governance.policy import validate_policy_profile


def main() -> int:
    return run_yaml_validator(
        title="POLICY PROFILE",
        namespace="policy",
        description="Validate a trusted lifecycle policy profile",
        validator=validate_policy_profile,
    )


if __name__ == "__main__":
    raise SystemExit(main())
