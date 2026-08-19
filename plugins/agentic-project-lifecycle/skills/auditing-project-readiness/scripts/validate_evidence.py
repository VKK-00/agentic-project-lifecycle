#!/usr/bin/env python3
from __future__ import annotations

import argparse

from governance.cli import run_yaml_validator
from governance_contracts import validate_evidence_record


def _extra(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--expected-commit")


def _invoke(validator, data, args: argparse.Namespace) -> list[str]:
    return validator(data, expected_commit=args.expected_commit)


def main() -> int:
    return run_yaml_validator(
        title="EVIDENCE",
        namespace="evidence",
        description="Validate source-bound evidence",
        validator=validate_evidence_record,
        extra_arguments=_extra,
        invoke=_invoke,
    )


if __name__ == "__main__":
    raise SystemExit(main())
