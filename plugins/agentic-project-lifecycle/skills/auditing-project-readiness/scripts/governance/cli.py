"""Shared CLI adapter for legacy semantic validators."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable

import yaml

from .issues import issues_from_messages, render_issues

Validator = Callable[[object], list[str]]


def run_yaml_validator(
    *,
    title: str,
    namespace: str,
    description: str,
    validator: Validator,
    extra_arguments: Callable[[argparse.ArgumentParser], None] | None = None,
    invoke: Callable[[Validator, object, argparse.Namespace], list[str]] | None = None,
) -> int:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("path", type=Path)
    parser.add_argument("--format", choices=("text", "json", "sarif"), default="text")
    if extra_arguments is not None:
        extra_arguments(parser)
    args = parser.parse_args()
    try:
        data = yaml.safe_load(args.path.read_text(encoding="utf-8"))
        messages = invoke(validator, data, args) if invoke else validator(data)
    except Exception as exc:  # CLI boundary must fail closed.
        messages = [f"cannot parse YAML: {exc}"]
    issues = issues_from_messages(namespace, messages)
    print(render_issues(issues, output_format=args.format, title=title))
    return 1 if issues else 0
