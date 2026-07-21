#!/usr/bin/env python3
"""Create just-in-time project artifacts from this skill's templates.

The script never overwrites existing files unless --force is supplied. It
preflights the complete write set before touching the target repository.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Mapping, Sequence

SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_ROOT = SKILL_ROOT / "assets" / "templates"
PLACEHOLDER_RE = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class ScaffoldError(RuntimeError):
    """Raised for a user-correctable scaffolding problem."""


@dataclass(frozen=True)
class PlannedWrite:
    template: str
    destination: Path
    values: Mapping[str, str]


def slugify(value: str) -> str:
    """Return a stable lowercase filesystem slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    if not slug:
        raise ScaffoldError(f"Cannot create a slug from {value!r}")
    return slug


def validate_identifier(value: str, label: str) -> str:
    value = value.strip()
    if not ID_RE.fullmatch(value):
        raise ScaffoldError(
            f"{label} must start with a letter or digit and contain only "
            "letters, digits, dots, underscores, and hyphens"
        )
    return value


def render_template(template_name: str, values: Mapping[str, str]) -> str:
    template_path = TEMPLATE_ROOT / template_name
    if not template_path.is_file():
        raise ScaffoldError(f"Template not found: {template_path}")

    text = template_path.read_text(encoding="utf-8")
    required = set(PLACEHOLDER_RE.findall(text))
    missing = sorted(required.difference(values))
    if missing:
        raise ScaffoldError(
            f"Missing values for {template_name}: {', '.join(missing)}"
        )

    for key in required:
        text = text.replace("{{" + key + "}}", values[key])

    unresolved = sorted(set(PLACEHOLDER_RE.findall(text)))
    if unresolved:
        raise ScaffoldError(
            f"Unresolved placeholders in {template_name}: {', '.join(unresolved)}"
        )
    return text.rstrip() + "\n"


def execute_writes(
    writes: Sequence[PlannedWrite], *, force: bool, dry_run: bool
) -> list[Path]:
    destinations = [item.destination for item in writes]
    duplicates = sorted(
        {str(path) for path in destinations if destinations.count(path) > 1}
    )
    if duplicates:
        raise ScaffoldError(f"Duplicate destinations: {', '.join(duplicates)}")

    existing = [path for path in destinations if path.exists()]
    if existing and not force:
        formatted = "\n".join(f"  - {path}" for path in existing)
        raise ScaffoldError(
            "Refusing to overwrite existing files. Use --force only after review:\n"
            + formatted
        )

    rendered = [
        (item.destination, render_template(item.template, item.values))
        for item in writes
    ]

    if dry_run:
        for destination, _ in rendered:
            print(f"WOULD CREATE {destination}")
        return destinations

    for destination, content in rendered:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
        print(f"CREATED {destination}")
    return destinations


def common_values(owner: str) -> dict[str, str]:
    return {"OWNER": owner.strip() or "unassigned", "DATE": date.today().isoformat()}


def build_init(args: argparse.Namespace) -> list[PlannedWrite]:
    root = args.root.resolve()
    values = {
        **common_values(args.owner),
        "PROJECT_NAME": args.project_name.strip(),
    }
    if not values["PROJECT_NAME"]:
        raise ScaffoldError("--project-name cannot be empty")
    return [
        PlannedWrite("project-state.yaml", root / "docs/project-state.yaml", values),
        PlannedWrite(
            "project-charter.md",
            root / "docs/00-governance/PROJECT_CHARTER.md",
            values,
        ),
        PlannedWrite("prd.md", root / "docs/02-product/PRD.md", values),
        PlannedWrite("roadmap.md", root / "docs/05-planning/ROADMAP.md", values),
    ]


def build_feature(args: argparse.Namespace) -> list[PlannedWrite]:
    root = args.root.resolve()
    feature_id = validate_identifier(args.id.upper(), "Feature ID")
    feature_name = args.name.strip()
    if not feature_name:
        raise ScaffoldError("--name cannot be empty")
    feature_slug = slugify(feature_name)
    values = {
        **common_values(args.owner),
        "FEATURE_ID": feature_id,
        "FEATURE_NAME": feature_name,
        "FEATURE_SLUG": feature_slug,
    }
    folder = root / "specs" / f"{feature_id}-{feature_slug}"
    return [
        PlannedWrite("feature-spec.md", folder / "spec.md", values),
        PlannedWrite("design-spec.md", folder / "design.md", values),
        PlannedWrite("implementation-plan.md", folder / "plan.md", values),
        PlannedWrite("tasks.md", folder / "tasks.md", values),
        PlannedWrite("test-plan.md", folder / "test-plan.md", values),
        PlannedWrite("verification-evidence.md", folder / "evidence.md", values),
    ]


def build_release(args: argparse.Namespace) -> list[PlannedWrite]:
    root = args.root.resolve()
    version = validate_identifier(args.version, "Release version")
    release_name = args.name.strip()
    if not release_name:
        raise ScaffoldError("--name cannot be empty")
    values = {
        **common_values(args.owner),
        "RELEASE_VERSION": version,
        "RELEASE_NAME": release_name,
    }
    destination = root / "docs/05-planning/releases" / f"{version}.md"
    return [PlannedWrite("release-plan.md", destination, values)]


def build_adr(args: argparse.Namespace) -> list[PlannedWrite]:
    root = args.root.resolve()
    adr_id = validate_identifier(args.id.upper(), "ADR ID")
    title = args.title.strip()
    if not title:
        raise ScaffoldError("--title cannot be empty")
    adr_slug = slugify(title)
    values = {
        **common_values(args.owner),
        "ADR_ID": adr_id,
        "ADR_TITLE": title,
        "ADR_SLUG": adr_slug,
    }
    destination = root / "docs/04-architecture/adr" / f"{adr_id}-{adr_slug}.md"
    return [PlannedWrite("adr.md", destination, values)]


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--root", type=Path, default=Path.cwd(), help="Target project root"
    )
    parser.add_argument(
        "--owner", default="unassigned", help="Initial document owner"
    )
    parser.add_argument(
        "--force", action="store_true", help="Overwrite existing destination files"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print destinations without writing"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scaffold project artifacts without creating empty bureaucracy.",
        epilog=(
            "Examples:\n"
            "  scaffold_project.py init --project-name 'Acme Portal' --owner alice\n"
            "  scaffold_project.py feature --id FEAT-001 --name 'CSV preview'\n"
            "  scaffold_project.py release --version v0.1-alpha --name 'Internal alpha'\n"
            "  scaffold_project.py adr --id ADR-0001 --title 'Use PostgreSQL'"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser(
        "init", help="Create the minimal project state, charter, PRD, and roadmap"
    )
    add_common_arguments(init_parser)
    init_parser.add_argument("--project-name", required=True)
    init_parser.set_defaults(builder=build_init)

    feature_parser = subparsers.add_parser(
        "feature", help="Create spec, design, plan, and evidence for one feature"
    )
    add_common_arguments(feature_parser)
    feature_parser.add_argument("--id", required=True, help="For example FEAT-001")
    feature_parser.add_argument("--name", required=True)
    feature_parser.set_defaults(builder=build_feature)

    release_parser = subparsers.add_parser(
        "release", help="Create a staged release plan"
    )
    add_common_arguments(release_parser)
    release_parser.add_argument(
        "--version", required=True, help="For example v0.1-alpha"
    )
    release_parser.add_argument("--name", required=True)
    release_parser.set_defaults(builder=build_release)

    adr_parser = subparsers.add_parser("adr", help="Create an architecture decision record")
    add_common_arguments(adr_parser)
    adr_parser.add_argument("--id", required=True, help="For example ADR-0001")
    adr_parser.add_argument("--title", required=True)
    adr_parser.set_defaults(builder=build_adr)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        writes = args.builder(args)
        execute_writes(writes, force=args.force, dry_run=args.dry_run)
    except ScaffoldError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
