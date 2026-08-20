"""Fail-closed distribution support for canonical APL skills."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
from typing import Any, Mapping
import zipfile

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "agentic-project-lifecycle"
SKILLS = PLUGIN / "skills"
PLATFORMS = ROOT / "platforms"
REGISTRY_PATH = PLATFORMS / "registry.yaml"


class PlatformError(RuntimeError):
    """Input or filesystem condition that must prevent platform publication."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _read_schema(name: str) -> Mapping[str, Any]:
    return json.loads((PLATFORMS / name).read_text(encoding="utf-8"))


def registry_digest() -> str:
    return _sha256(REGISTRY_PATH.read_bytes())


def _safe_relative(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise PlatformError(f"unsafe relative path: {value!r}")
    return path


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise PlatformError(f"cannot load platform registry: {exc}") from exc
    errors = sorted(Draft202012Validator(_read_schema("platform-registry-v1.schema.json")).iter_errors(document), key=str)
    if errors:
        raise PlatformError("invalid platform registry: " + "; ".join(error.message for error in errors))
    ids: set[str] = set()
    aliases: set[str] = set()
    for record in document["platforms"]:
        identifier = record["id"]
        if identifier in ids:
            raise PlatformError(f"duplicate platform id: {identifier}")
        ids.add(identifier)
        for alias in record["aliases"]:
            if alias in aliases:
                raise PlatformError(f"duplicate platform alias: {alias}")
            aliases.add(alias)
        _safe_relative(record["project_path"])
        _safe_relative(record["user_path"])
        if "native_manifest" in record:
            _safe_relative(record["native_manifest"])
    return document


def resolve_platform(identifier: str) -> dict[str, Any]:
    for platform in load_registry()["platforms"]:
        if identifier == platform["id"] or identifier in platform["aliases"]:
            return platform
    raise PlatformError(f"unknown platform: {identifier}")


def canonical_inventory() -> list[dict[str, str]]:
    if SKILLS.is_symlink() or not SKILLS.is_dir():
        raise PlatformError("canonical skills root must be a real directory")
    inventory: list[dict[str, str]] = []
    for source in sorted(SKILLS.rglob("*")):
        relative = source.relative_to(SKILLS)
        if any(part == "__pycache__" for part in relative.parts):
            continue
        metadata = source.lstat()
        if stat.S_ISLNK(metadata.st_mode):
            raise PlatformError(f"canonical skills contain a symlink: {relative.as_posix()}")
        if source.is_dir():
            continue
        if not stat.S_ISREG(metadata.st_mode):
            raise PlatformError(f"canonical skills contain a non-regular file: {relative.as_posix()}")
        inventory.append({"path": (PurePosixPath("skills") / relative.as_posix()).as_posix(), "sha256": _sha256(source.read_bytes())})
    if not inventory:
        raise PlatformError("canonical skill inventory is empty")
    return sorted(inventory, key=lambda record: record["path"])


def inventory_digest(inventory: list[dict[str, str]] | None = None) -> str:
    return _sha256(_canonical_json(inventory if inventory is not None else canonical_inventory()))


def bundle_manifest(identifier: str) -> dict[str, Any]:
    platform = resolve_platform(identifier)
    inventory = canonical_inventory()
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "platform": platform["id"],
        "registry_sha256": registry_digest(),
        "inventory_sha256": inventory_digest(inventory),
        "files": inventory,
    }
    if platform.get("native_manifest"):
        native = ROOT / platform["native_manifest"]
        if not native.is_file() or native.is_symlink():
            raise PlatformError(f"missing or unsafe native manifest: {platform['native_manifest']}")
        payload["native_manifest"] = {"path": platform["native_manifest"], "sha256": _sha256(native.read_bytes())}
    return payload


def _zip_info(name: str, epoch: int) -> zipfile.ZipInfo:
    timestamp = __import__("datetime").datetime.fromtimestamp(max(epoch, 315532800), tz=__import__("datetime").timezone.utc)
    info = zipfile.ZipInfo(name, date_time=(timestamp.year, timestamp.month, timestamp.day, timestamp.hour, timestamp.minute, timestamp.second))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    return info


def build_bundle(identifier: str, output: Path, *, epoch: int) -> dict[str, Any]:
    manifest = bundle_manifest(identifier)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr(_zip_info("APL_PLATFORM_MANIFEST.json", epoch), json.dumps(manifest, indent=2, sort_keys=True) + "\n", compresslevel=9)
        for record in manifest["files"]:
            source = SKILLS / PurePosixPath(record["path"]).relative_to("skills")
            archive.writestr(_zip_info(record["path"], epoch), source.read_bytes(), compresslevel=9)
        native = manifest.get("native_manifest")
        if native:
            archive.writestr(_zip_info(native["path"], epoch), (ROOT / native["path"]).read_bytes(), compresslevel=9)
    return manifest


def _target(root: Path, relative: str) -> Path:
    base = root.resolve()
    target = (base / Path(*_safe_relative(relative).parts)).resolve(strict=False)
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise PlatformError("installation target escapes selected root") from exc
    return target


def installation_target(identifier: str, *, scope: str, root: Path) -> Path:
    platform = resolve_platform(identifier)
    if scope not in {"project", "user"}:
        raise PlatformError("scope must be project or user")
    return _target(root, platform[f"{scope}_path"])


def _write_tree(destination: Path, manifest: Mapping[str, Any], *, link: bool) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    if link:
        if os.name == "nt":
            raise PlatformError("development symlink mode is not supported on Windows")
        os.symlink(SKILLS.resolve(), destination / "skills", target_is_directory=True)
    else:
        for record in manifest["files"]:
            relative = PurePosixPath(record["path"])
            target = destination.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(SKILLS / relative.relative_to("skills"), target)
    (destination / "APL_PLATFORM_MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verify_installation(target: Path, *, allow_development_link: bool = False) -> list[str]:
    if target.is_symlink() or not target.is_dir():
        return ["installation target is missing or not a real directory"]
    manifest_path = target / "APL_PLATFORM_MANIFEST.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        errors = [error.message for error in Draft202012Validator(_read_schema("platform-bundle-manifest-v1.schema.json")).iter_errors(manifest)]
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read platform manifest: {exc}"]
    expected = {"APL_PLATFORM_MANIFEST.json"}
    skills_link = target / "skills"
    if skills_link.is_symlink():
        if not allow_development_link:
            errors.append("symlink not allowed: skills")
        elif skills_link.resolve() != SKILLS.resolve():
            errors.append("development skills symlink does not resolve to canonical skills")
        else:
            return sorted(errors)
    for record in manifest.get("files", []):
        relative = PurePosixPath(record["path"])
        expected.add(relative.as_posix())
        path = target.joinpath(*relative.parts)
        if path.is_symlink():
            if allow_development_link and relative.parts == ("skills",):
                continue
            errors.append(f"symlink not allowed: {relative}")
        elif not path.is_file():
            errors.append(f"missing file: {relative}")
        elif _sha256(path.read_bytes()) != record["sha256"]:
            errors.append(f"changed file: {relative}")
    actual = {path.relative_to(target).as_posix() for path in target.rglob("*") if path.is_file() and not path.is_symlink()}
    extras = sorted(actual - expected)
    errors.extend(f"unexpected file: {name}" for name in extras)
    return sorted(errors)


def install_platform(identifier: str, *, scope: str, root: Path, force: bool = False, dry_run: bool = False, link: bool = False) -> Path:
    target = installation_target(identifier, scope=scope, root=root)
    if target.exists() and not force:
        raise PlatformError(f"installation already exists: {target}; use --force to replace it")
    if dry_run:
        return target
    manifest = bundle_manifest(identifier)
    parent = target.parent
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{target.name}.stage-", dir=parent) as temporary:
        stage = Path(temporary) / target.name
        _write_tree(stage, manifest, link=link)
        errors = verify_installation(stage, allow_development_link=link)
        if errors:
            raise PlatformError("staging verification failed: " + "; ".join(errors))
        backup = parent / f".{target.name}.backup-{next(tempfile._get_candidate_names())}"
        moved_old = False
        try:
            if target.exists():
                os.replace(target, backup)
                moved_old = True
            os.replace(stage, target)
            errors = verify_installation(target, allow_development_link=link)
            if errors:
                raise PlatformError("published verification failed: " + "; ".join(errors))
            if moved_old:
                shutil.rmtree(backup)
        except Exception:
            if target.exists():
                shutil.rmtree(target)
            if moved_old and backup.exists():
                os.replace(backup, target)
            raise
    return target


def validate_activation_record(path: Path) -> list[str]:
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read activation record: {exc}"]
    errors = [error.message for error in Draft202012Validator(_read_schema("platform-activation-record-v1.schema.json")).iter_errors(record)]
    if errors:
        return sorted(errors)
    try:
        resolve_platform(record["platform"])
    except PlatformError as exc:
        errors.append(str(exc))
    tiers = {"not-live-tested": 0, "smoke-tested": 1, "repeated-behavior-tested": 3}
    minimum = tiers[record["evidence_tier"]]
    seen_ids: set[str] = set()
    counts = {kind: 0 for kind in ("positive", "negative", "pressure")}
    for run in record["runs"]:
        if run["id"] in seen_ids:
            errors.append(f"duplicate run id: {run['id']}")
        seen_ids.add(run["id"])
        if run["passed"]:
            counts[run["kind"]] += 1
    for kind, count in counts.items():
        if count < minimum:
            errors.append(f"{record['evidence_tier']} requires {minimum} passing {kind} runs")
    return sorted(errors)
