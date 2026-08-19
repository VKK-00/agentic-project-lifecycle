#!/usr/bin/env python3
"""Build deterministic plugin archives and release evidence."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from build_sbom import write_sbom

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_NAME = "agentic-project-lifecycle"
PLUGIN_ROOT = ROOT / "plugins" / PLUGIN_NAME
RESULTS = ROOT / "evals" / "results"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_epoch() -> int:
    configured = os.environ.get("SOURCE_DATE_EPOCH")
    if configured:
        return int(configured)
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


def plugin_files() -> list[Path]:
    return sorted(
        path
        for path in PLUGIN_ROOT.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
    )


def archive_name(path: Path) -> str:
    return (Path(PLUGIN_NAME) / path.relative_to(PLUGIN_ROOT)).as_posix()


def build_zip(path: Path, files: list[Path], epoch: int) -> None:
    timestamp = datetime.fromtimestamp(max(epoch, 315532800), tz=timezone.utc)
    date_time = (timestamp.year, timestamp.month, timestamp.day, timestamp.hour, timestamp.minute, timestamp.second)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source in files:
            info = zipfile.ZipInfo(archive_name(source), date_time=date_time)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 if source.suffix == ".py" else 0o644) << 16
            archive.writestr(info, source.read_bytes(), compresslevel=9)


def build_tar(path: Path, files: list[Path], epoch: int) -> None:
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=epoch, compresslevel=9) as zipped:
            with tarfile.open(fileobj=zipped, mode="w") as archive:
                for source in files:
                    data = source.read_bytes()
                    info = tarfile.TarInfo(archive_name(source))
                    info.size = len(data)
                    info.mtime = epoch
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    info.mode = 0o755 if source.suffix == ".py" else 0o644
                    from io import BytesIO

                    archive.addfile(info, BytesIO(data))


def git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "uncommitted-worktree"


def build_validation_report(path: Path, version: str) -> None:
    promotion = json.loads((RESULTS / "promotion-gate.json").read_text(encoding="utf-8"))
    trigger = json.loads((RESULTS / "trigger-report.json").read_text(encoding="utf-8"))["heldout"]
    ablation = json.loads((RESULTS / "instruction-ablation.json").read_text(encoding="utf-8"))
    fixtures = json.loads((RESULTS / "project-trials.json").read_text(encoding="utf-8"))["projects"]
    public_trials = json.loads((RESULTS / "non-fixture-project-trials.json").read_text(encoding="utf-8"))["projects"]
    lines = [
        f"# Validation report: {version}",
        "",
        f"- Commit: `{git_commit()}`",
        f"- Promotion gate: `{'PASS' if promotion.get('promotable') else 'FAIL'}`",
        f"- Held-out exact routing accuracy: `{trigger.get('exact_accuracy')}`",
        f"- Held-out recall: `{trigger.get('recall')}`",
        f"- Held-out false-positive rate: `{trigger.get('false_positive_rate')}`",
        f"- Baseline advantage: `{ablation.get('advantage')}`",
        f"- Retained rules with positive effect: `{ablation.get('case_count') - len(ablation.get('failed_rules', []))}/{ablation.get('case_count')}`",
        f"- Executable fixture projects: `{len(fixtures)}`",
        f"- Pinned public-repository trials: `{len(public_trials)}`",
        "",
        "## Scope and limitations",
        "",
        str(ablation.get("limitations", "No limitations recorded.")),
        "",
        "The public-repository trials use pinned, read-only file evidence. They do not certify those repositories or guarantee model behavior.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Agentic Project Lifecycle release assets")
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    args = parser.parse_args()

    manifest = json.loads((PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    if args.version != manifest.get("version"):
        raise SystemExit(
            f"version mismatch: argument={args.version} manifest={manifest.get('version')}"
        )
    args.output.mkdir(parents=True, exist_ok=True)
    files = plugin_files()
    epoch = source_epoch()
    zip_path = args.output / f"{PLUGIN_NAME}-{args.version}.zip"
    tar_path = args.output / f"{PLUGIN_NAME}-{args.version}.tar.gz"
    for path in [zip_path, tar_path]:
        if path.exists():
            path.unlink()
    build_zip(zip_path, files, epoch)
    build_tar(tar_path, files, epoch)

    sbom_path = args.output / f"{PLUGIN_NAME}-{args.version}.spdx.json"
    write_sbom(sbom_path, args.version, epoch=epoch)

    promotion_path = args.output / "promotion-gate.json"
    shutil.copyfile(RESULTS / "promotion-gate.json", promotion_path)
    validation_path = args.output / "validation-report.md"
    build_validation_report(validation_path, args.version)

    artifacts = [zip_path, tar_path, sbom_path, promotion_path, validation_path]
    checksum_path = args.output / "SHA256SUMS"
    checksum_path.write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in artifacts),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "version": args.version,
                "source_epoch": epoch,
                "plugin_files": len(files),
                "artifacts": [path.name for path in [*artifacts, checksum_path]],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
