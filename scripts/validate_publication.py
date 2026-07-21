#!/usr/bin/env python3
"""Validate the public repository, marketplace, and plugin release contract."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_NAME = "agentic-project-lifecycle"
PLUGIN_ROOT = ROOT / "plugins" / PLUGIN_NAME
SKILLS_ROOT = PLUGIN_ROOT / "skills"
MANIFEST_PATH = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"
MARKETPLACE_PATH = ROOT / ".agents" / "plugins" / "marketplace.json"
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
SECRET_PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    "OpenAI-style token": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "Slack token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
}
MACHINE_PATH_PATTERN = re.compile(
    r"(?i)"
    + r"C:"
    + r"\\Users\\"
    + r"[^\\\s]+"
    + r"|/"
    + r"Users/"
    + r"[^/\s]+"
)
TEXT_EXTENSIONS = {
    "",
    ".json",
    ".md",
    ".py",
    ".svg",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}


def load_json(path: Path, errors: list[str]) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"cannot parse JSON {path.relative_to(ROOT)}: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"JSON root must be an object: {path.relative_to(ROOT)}")
        return {}
    return value


def resolve_inside(base: Path, value: str, label: str, errors: list[str]) -> Path | None:
    if not value.startswith("./"):
        errors.append(f"{label} must start with './': {value}")
        return None
    resolved = (base / value[2:]).resolve()
    base_resolved = base.resolve()
    if resolved != base_resolved and base_resolved not in resolved.parents:
        errors.append(f"{label} escapes its root: {value}")
        return None
    return resolved


def check_manifest(errors: list[str]) -> dict:
    manifest = load_json(MANIFEST_PATH, errors)
    required = ["name", "version", "description", "author", "skills", "interface"]
    for key in required:
        if not manifest.get(key):
            errors.append(f"plugin manifest field is missing: {key}")
    if manifest.get("name") != PLUGIN_NAME:
        errors.append("plugin name must match the plugin directory")
    if not SEMVER_RE.fullmatch(str(manifest.get("version", ""))):
        errors.append("plugin version must be strict semver")
    author = manifest.get("author", {})
    if not isinstance(author, dict) or author.get("name") != "VKK-00":
        errors.append("plugin author.name must identify VKK-00")
    if manifest.get("license") != "Apache-2.0":
        errors.append("plugin license must be Apache-2.0")
    skills_path = resolve_inside(PLUGIN_ROOT, str(manifest.get("skills", "")), "skills", errors)
    if skills_path != SKILLS_ROOT.resolve():
        errors.append("plugin skills path must resolve to ./skills/")

    interface = manifest.get("interface", {})
    if not isinstance(interface, dict):
        errors.append("plugin interface must be an object")
        return manifest
    for key in [
        "displayName",
        "shortDescription",
        "longDescription",
        "developerName",
        "category",
        "capabilities",
        "defaultPrompt",
    ]:
        if not interface.get(key):
            errors.append(f"plugin interface field is missing: {key}")
    prompts = interface.get("defaultPrompt", [])
    if not isinstance(prompts, list) or not 1 <= len(prompts) <= 3:
        errors.append("defaultPrompt must contain one to three prompts")
    else:
        for index, prompt in enumerate(prompts, start=1):
            if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 128:
                errors.append(f"defaultPrompt[{index}] must be a non-empty string <= 128 chars")
    for key in ["websiteURL", "privacyPolicyURL", "termsOfServiceURL"]:
        value = interface.get(key)
        if not isinstance(value, str) or not value.startswith("https://"):
            errors.append(f"interface.{key} must be an absolute HTTPS URL")
    for key in ["composerIcon", "logo"]:
        value = interface.get(key)
        if not isinstance(value, str):
            errors.append(f"interface.{key} must be a relative asset path")
            continue
        asset = resolve_inside(PLUGIN_ROOT, value, f"interface.{key}", errors)
        if asset is not None and not asset.is_file():
            errors.append(f"interface.{key} does not exist: {value}")
    return manifest


def check_marketplace(errors: list[str]) -> dict:
    marketplace = load_json(MARKETPLACE_PATH, errors)
    if marketplace.get("name") != "vkk-00-agent-plugins":
        errors.append("marketplace name must be vkk-00-agent-plugins")
    plugins = marketplace.get("plugins", [])
    if not isinstance(plugins, list) or len(plugins) != 1:
        errors.append("marketplace must contain exactly one plugin entry")
        return marketplace
    entry = plugins[0]
    if entry.get("name") != PLUGIN_NAME:
        errors.append("marketplace plugin name does not match the manifest")
    source = entry.get("source", {})
    if source.get("source") != "local":
        errors.append("repo marketplace source must be local")
    source_path = resolve_inside(ROOT, str(source.get("path", "")), "marketplace source.path", errors)
    if source_path != PLUGIN_ROOT.resolve():
        errors.append("marketplace source.path must resolve to the plugin root")
    policy = entry.get("policy", {})
    if policy.get("installation") not in {"AVAILABLE", "INSTALLED_BY_DEFAULT", "NOT_AVAILABLE"}:
        errors.append("marketplace policy.installation is invalid")
    if policy.get("authentication") not in {"ON_INSTALL", "ON_USE"}:
        errors.append("marketplace policy.authentication is invalid")
    if not entry.get("category"):
        errors.append("marketplace category is required")
    return marketplace


def check_skills(errors: list[str]) -> None:
    suite = yaml.safe_load((ROOT / "suite.yaml").read_text(encoding="utf-8"))
    expected = set(suite.get("skills", []))
    actual = {path.name for path in SKILLS_ROOT.iterdir() if path.is_dir()}
    if actual != expected:
        errors.append(f"skill set mismatch: expected={sorted(expected)} actual={sorted(actual)}")
    for name in sorted(actual):
        path = SKILLS_ROOT / name / "SKILL.md"
        if not path.is_file():
            errors.append(f"missing skill file: {path.relative_to(ROOT)}")
            continue
        text = path.read_text(encoding="utf-8")
        try:
            _, raw, _ = text.split("---", 2)
            metadata = yaml.safe_load(raw)
        except (ValueError, yaml.YAMLError) as exc:
            errors.append(f"invalid skill frontmatter {path.relative_to(ROOT)}: {exc}")
            continue
        if metadata.get("name") != name:
            errors.append(f"skill name mismatch: {path.relative_to(ROOT)}")
        if not str(metadata.get("description", "")).startswith("Use when "):
            errors.append(f"skill description must start with 'Use when ': {name}")
        if "compatibility" in metadata:
            errors.append(f"unsupported compatibility frontmatter remains: {name}")
        if metadata.get("metadata", {}).get("author") != "VKK-00":
            errors.append(f"skill author must be VKK-00: {name}")


def check_submission_materials(errors: list[str]) -> None:
    path = ROOT / "submission" / "test-cases.json"
    data = load_json(path, errors)
    positive = data.get("positive", [])
    negative = data.get("negative", [])
    if not isinstance(positive, list) or len(positive) != 5:
        errors.append("submission must contain exactly five positive test cases")
    if not isinstance(negative, list) or len(negative) != 3:
        errors.append("submission must contain exactly three negative test cases")
    for group_name, cases in [("positive", positive), ("negative", negative)]:
        if not isinstance(cases, list):
            continue
        for index, case in enumerate(cases, start=1):
            if not isinstance(case, dict):
                errors.append(f"{group_name} test case {index} must be an object")
                continue
            for key in ["id", "prompt", "expected_behavior", "expected_result"]:
                if not case.get(key):
                    errors.append(f"{group_name} test case {index} is missing {key}")


def check_public_files(errors: list[str]) -> None:
    required = [
        "README.md",
        "README.ru.md",
        "README.uk.md",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "LICENSE",
        "NOTICE",
        "docs/PRIVACY.md",
        "docs/TERMS.md",
        "docs/SUPPORT.md",
    ]
    for relative in required:
        path = ROOT / relative
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"required public file is missing or empty: {relative}")
    russian_markdown = sorted(
        path.relative_to(ROOT).as_posix() for path in ROOT.rglob("*.ru.md") if path.is_file()
    )
    if russian_markdown != ["README.ru.md"]:
        errors.append(
            "README.ru.md must be the only Russian-localized Markdown file: "
            f"found={russian_markdown}"
        )
    for relative in ["LICENSE", "plugins/agentic-project-lifecycle/LICENSE"]:
        path = ROOT / relative
        if path.is_file() and path.stat().st_size < 10_000:
            errors.append(f"Apache-2.0 license text is incomplete: {relative}")


def check_repository_hygiene(errors: list[str]) -> None:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        errors.append("cannot enumerate publishable files with git ls-files")
        return
    for raw_relative in result.stdout.split(b"\0"):
        if not raw_relative:
            continue
        relative = raw_relative.decode("utf-8", errors="surrogateescape")
        path = ROOT / relative
        if not path.is_file():
            continue
        if path.suffix == ".pyc" or "__pycache__" in path.parts:
            errors.append(f"generated Python file must not be published: {relative}")
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS and path.name not in {"LICENSE", "NOTICE"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if MACHINE_PATH_PATTERN.search(text):
            errors.append(f"machine-local user path found: {relative}")
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                errors.append(f"possible {label} found: {relative}")


def main() -> int:
    errors: list[str] = []
    manifest = check_manifest(errors)
    check_marketplace(errors)
    check_skills(errors)
    check_submission_materials(errors)
    check_public_files(errors)
    check_repository_hygiene(errors)
    report = {
        "pass": not errors,
        "plugin": manifest.get("name"),
        "version": manifest.get("version"),
        "errors": errors,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
