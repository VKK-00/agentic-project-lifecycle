#!/usr/bin/env python3
"""Build a deterministic SPDX 2.3 SBOM for the distributable plugin."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_NAME = "agentic-project-lifecycle"
PLUGIN_ROOT = ROOT / "plugins" / PLUGIN_NAME
PYPROJECT = ROOT / "pyproject.toml"
NAMESPACE_ROOT = "https://github.com/VKK-00/agentic-project-lifecycle/spdx"


def source_epoch() -> int:
    configured = os.environ.get("SOURCE_DATE_EPOCH")
    if configured is not None:
        try:
            value = int(configured)
        except ValueError as exc:
            raise ValueError("SOURCE_DATE_EPOCH must be an integer") from exc
        if value < 0:
            raise ValueError("SOURCE_DATE_EPOCH must not be negative")
        return value

    result = subprocess.run(
        ["git", "log", "-1", "--format=%ct"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip().isdigit():
        return int(result.stdout.strip())
    return 315532800


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha1_bytes(payload: bytes) -> str:
    return hashlib.sha1(payload, usedforsecurity=False).hexdigest()


def plugin_files() -> list[Path]:
    return sorted(
        (
            path
            for path in PLUGIN_ROOT.rglob("*")
            if path.is_file()
            and "__pycache__" not in path.parts
            and path.suffix != ".pyc"
        ),
        key=lambda path: path.relative_to(PLUGIN_ROOT).as_posix(),
    )


def spdx_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]
    normalized = re.sub(r"[^A-Za-z0-9.-]+", "-", value).strip("-.")[:40]
    label = normalized or "item"
    return f"SPDXRef-{prefix}-{label}-{digest}"


def package_verification_code(file_sha1s: list[str]) -> str:
    joined = "".join(sorted(file_sha1s)).encode("ascii")
    return hashlib.sha1(joined, usedforsecurity=False).hexdigest()


def dependency_entries() -> list[dict[str, str]]:
    project = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]
    raw_dependencies = project.get("dependencies", [])
    dependencies: list[dict[str, str]] = []
    for raw in raw_dependencies:
        if not isinstance(raw, str):
            raise ValueError("project dependencies must be strings")
        match = re.fullmatch(r"\s*([A-Za-z0-9_.-]+)\s*(.*)\s*", raw)
        if match is None:
            raise ValueError(f"cannot parse dependency requirement: {raw}")
        name = match.group(1)
        requirement = match.group(2).strip() or "NOASSERTION"
        dependencies.append({"name": name, "requirement": requirement})
    return sorted(dependencies, key=lambda item: item["name"].lower())


def build_document(version: str, *, epoch: int | None = None) -> dict[str, Any]:
    if not version or any(character.isspace() for character in version):
        raise ValueError("version must be a non-empty token")

    effective_epoch = source_epoch() if epoch is None else epoch
    if effective_epoch < 0:
        raise ValueError("epoch must not be negative")
    created = datetime.fromtimestamp(effective_epoch, tz=timezone.utc).replace(
        microsecond=0
    )

    main_package_id = "SPDXRef-Package-agentic-project-lifecycle"
    files: list[dict[str, Any]] = []
    relationships: list[dict[str, str]] = [
        {
            "spdxElementId": "SPDXRef-DOCUMENT",
            "relationshipType": "DESCRIBES",
            "relatedSpdxElement": main_package_id,
        }
    ]
    inventory_material: list[str] = []
    file_sha1s: list[str] = []

    for path in plugin_files():
        relative = path.relative_to(PLUGIN_ROOT).as_posix()
        payload = path.read_bytes()
        sha256 = sha256_bytes(payload)
        sha1 = sha1_bytes(payload)
        file_sha1s.append(sha1)
        inventory_material.append(f"{relative}\0{sha256}\n")
        file_id = spdx_id("File", relative)
        files.append(
            {
                "fileName": f"./{relative}",
                "SPDXID": file_id,
                "checksums": [
                    {"algorithm": "SHA256", "checksumValue": sha256},
                    {"algorithm": "SHA1", "checksumValue": sha1},
                ],
                "licenseConcluded": "NOASSERTION",
                "licenseInfoInFiles": ["NOASSERTION"],
                "copyrightText": "NOASSERTION",
                "fileTypes": ["SOURCE"],
            }
        )
        relationships.append(
            {
                "spdxElementId": main_package_id,
                "relationshipType": "CONTAINS",
                "relatedSpdxElement": file_id,
            }
        )

    dependencies = dependency_entries()
    packages: list[dict[str, Any]] = [
        {
            "name": PLUGIN_NAME,
            "SPDXID": main_package_id,
            "versionInfo": version,
            "downloadLocation": (
                "https://github.com/VKK-00/agentic-project-lifecycle"
            ),
            "filesAnalyzed": True,
            "packageVerificationCode": {
                "packageVerificationCodeValue": package_verification_code(file_sha1s)
            },
            "licenseConcluded": "Apache-2.0",
            "licenseDeclared": "Apache-2.0",
            "copyrightText": "Copyright VKK-00",
            "homepage": "https://github.com/VKK-00/agentic-project-lifecycle",
            "supplier": "Person: VKK-00",
            "primaryPackagePurpose": "APPLICATION",
        }
    ]

    for dependency in dependencies:
        dependency_id = spdx_id("Package", dependency["name"])
        packages.append(
            {
                "name": dependency["name"],
                "SPDXID": dependency_id,
                "versionInfo": dependency["requirement"],
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "licenseConcluded": "NOASSERTION",
                "licenseDeclared": "NOASSERTION",
                "copyrightText": "NOASSERTION",
                "supplier": "NOASSERTION",
                "primaryPackagePurpose": "LIBRARY",
                "comment": (
                    "Declared Python runtime requirement from pyproject.toml; "
                    "the exact resolved version is environment-specific."
                ),
            }
        )
        relationships.append(
            {
                "spdxElementId": main_package_id,
                "relationshipType": "DEPENDS_ON",
                "relatedSpdxElement": dependency_id,
            }
        )
        inventory_material.append(
            f"dependency\0{dependency['name']}\0{dependency['requirement']}\n"
        )

    inventory_digest = hashlib.sha256(
        "".join(inventory_material).encode("utf-8")
    ).hexdigest()
    namespace = f"{NAMESPACE_ROOT}/{version}/{inventory_digest}"

    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"{PLUGIN_NAME}-{version}",
        "documentNamespace": namespace,
        "creationInfo": {
            "created": created.isoformat().replace("+00:00", "Z"),
            "creators": ["Tool: agentic-project-lifecycle-build-sbom/1.1"],
            "licenseListVersion": "3.27",
        },
        "documentDescribes": [main_package_id],
        "packages": packages,
        "files": files,
        "relationships": relationships,
    }


def write_sbom(path: Path, version: str, *, epoch: int | None = None) -> None:
    document = build_document(version, epoch=epoch)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a deterministic SPDX 2.3 SBOM"
    )
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        write_sbom(args.output, args.version)
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        raise SystemExit(f"SBOM BUILD: FAIL\n- {exc}") from exc
    print(
        json.dumps(
            {
                "version": args.version,
                "output": str(args.output),
                "sha256": sha256_bytes(args.output.read_bytes()),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
