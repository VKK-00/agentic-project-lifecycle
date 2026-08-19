from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "plugins/agentic-project-lifecycle/skills/auditing-project-readiness/scripts"
sys.path.insert(0, str(SCRIPTS))

from governance.runner_support import probe_network_isolation  # noqa: E402

from governance.run_manifest import (  # noqa: E402
    append_event,
    build_run_manifest,
    redact,
    validate_run_manifest,
    verify_event_log,
)

COLLECTOR = SCRIPTS / "collect_verification.py"


def git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def init_repo(root: Path) -> tuple[str, Path]:
    root.mkdir(parents=True)
    git(root, "init", "-q")
    git(root, "config", "user.name", "Test User")
    git(root, "config", "user.email", "test@example.com")
    (root / "README.md").write_text("fixture\n", encoding="utf-8")
    config = root / "verification.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "commands": [
                    {
                        "name": "unit",
                        "claim_id": "unit_tests",
                        "run": [sys.executable, "-c", "print('token=' + 'sk-' + 'supersecretvalue123456789')"],
                        "max_age_hours": 24,
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    git(root, "add", ".")
    git(root, "commit", "-qm", "fixture")
    return git(root, "rev-parse", "HEAD"), config


def run_collector(
    root: Path, config: Path, *, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(COLLECTOR), "--root", str(root), "--config", str(config), "--output", str(root / "evidence/latest")],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def test_hash_chained_event_log_detects_tampering(tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    append_event(log, run_id="RUN-1", event_type="task.loaded", actor={"role": "orchestrator"}, payload={"task": "T1"})
    append_event(log, run_id="RUN-1", event_type="verification.completed", actor={"role": "verifier"}, payload={"exit_code": 0})
    assert verify_event_log(log) == []

    lines = log.read_text(encoding="utf-8").splitlines()
    event = json.loads(lines[0])
    event["payload"]["task"] = "TAMPERED"
    lines[0] = json.dumps(event, sort_keys=True)
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert "event hash mismatch at line 1" in verify_event_log(log)


def test_redaction_removes_secret_keys_and_token_patterns() -> None:
    value = redact(
        {
            "password": "hunter2",
            "nested": {
                "authorization": "Bearer abcdefghijklmnop",
                "text": "use " + "sk-" + "secretsecretsecretsecret",
                "aws": "AK" + "IA" + "ABCDEFGHIJKLMNOP",
                "private": (
                    "-----BEGIN " + "PRIVATE" + " KEY-----\nsecret\n-----END "
                    + "PRIVATE" + " KEY-----"
                ),
            },
        }
    )
    assert value["password"] == "[REDACTED]"
    assert value["nested"]["authorization"] == "[REDACTED]"
    assert "sk-secret" not in value["nested"]["text"]
    assert ("AK" + "IA") not in value["nested"]["aws"]
    assert ("PRIVATE" + " KEY") not in value["nested"]["private"]


def test_run_manifest_is_bound_to_event_log_digest(tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    append_event(log, run_id="RUN-1", event_type="run.started", actor={"role": "orchestrator"}, payload={})
    manifest = build_run_manifest(run_id="RUN-1", source_commit="a" * 40, source_tree="b" * 40, branch="main", event_log=log)
    assert validate_run_manifest(manifest, event_log=log) == []
    log.write_text(log.read_text() + "{}\n", encoding="utf-8")
    assert "run manifest event-log digest mismatch" in validate_run_manifest(manifest, event_log=log)


def test_collector_publishes_immutable_runs_and_latest_pointer(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    commit, config = init_repo(root)
    first = run_collector(root, config)
    assert first.returncode == 0, first.stdout + first.stderr
    first_pointer = json.loads((root / "evidence/latest.json").read_text(encoding="utf-8"))
    first_dir = root / first_pointer["run_path"]
    first_report_digest = first_pointer["report_sha256"]
    assert first_dir.is_dir()
    assert first_pointer["source_commit"] == commit
    assert (first_dir / "run-manifest.json").is_file()
    assert verify_event_log(first_dir / "events.jsonl") == []
    assert "sk-supersecret" not in (first_dir / "unit.log").read_text(encoding="utf-8")

    second = run_collector(root, config)
    assert second.returncode == 0, second.stdout + second.stderr
    second_pointer = json.loads((root / "evidence/latest.json").read_text(encoding="utf-8"))
    assert second_pointer["run_id"] != first_pointer["run_id"]
    assert first_dir.is_dir()
    assert first_pointer["report_sha256"] == first_report_digest
    assert len(list((root / "evidence/runs").iterdir())) == 2
    assert (root / "evidence/latest/report.json").is_file()


def test_failed_collection_preserves_previous_latest_pointer(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _, config = init_repo(root)
    assert run_collector(root, config).returncode == 0
    before = (root / "evidence/latest.json").read_bytes()

    config.write_text(
        yaml.safe_dump({"commands": [{"name": "mutate", "run": [sys.executable, "-c", "from pathlib import Path; Path('README.md').write_text('changed')"]}]}),
        encoding="utf-8",
    )
    git(root, "add", "verification.yaml")
    git(root, "commit", "-qm", "mutating config")
    result = run_collector(root, config)
    assert result.returncode == 1
    assert (root / "evidence/latest.json").read_bytes() == before


def _replace_verification_command(root: Path, config: Path, argv: list[str]) -> None:
    config.write_text(
        yaml.safe_dump(
            {
                "commands": [
                    {
                        "name": "security-check",
                        "claim_id": "security_check",
                        "run": argv,
                        "timeout_seconds": 5,
                        "max_age_hours": 24,
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    git(root, "add", "verification.yaml")
    git(root, "commit", "-qm", "replace verification command")


def test_collector_does_not_inherit_secret_environment_variables(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _, config = init_repo(root)
    _replace_verification_command(
        root,
        config,
        [
            sys.executable,
            "-c",
            "import os,sys; sys.exit(41 if os.environ.get('APL_TEST_SECRET_TOKEN') else 0)",
        ],
    )
    env = os.environ.copy()
    env["APL_TEST_SECRET_TOKEN"] = "must-not-reach-verification"

    result = run_collector(root, config, env=env)

    assert result.returncode == 0, result.stdout + result.stderr


def test_collector_uses_a_distinct_linux_network_namespace(tmp_path: Path) -> None:
    capability = probe_network_isolation()
    if not capability.available or os.environ.get("APL_TEST_FAKE_UNSHARE") == "1":
        import pytest
        pytest.skip(f"real Linux network namespace unavailable: {capability.reason}")
    root = tmp_path / "repo"
    _, config = init_repo(root)
    parent_namespace = os.readlink("/proc/self/ns/net")
    _replace_verification_command(
        root,
        config,
        [
            sys.executable,
            "-c",
            (
                "import os,sys; "
                "sys.exit(0 if os.readlink('/proc/self/ns/net') != "
                "os.environ['APL_PARENT_NET_NS'] else 42)"
            ),
        ],
    )
    env = os.environ.copy()
    env["APL_PARENT_NET_NS"] = parent_namespace

    result = run_collector(root, config, env=env)

    assert result.returncode == 0, result.stdout + result.stderr


def test_collector_terminates_background_descendants(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _, config = init_repo(root)
    child_code = (
        "import time; from pathlib import Path; "
        "time.sleep(0.6); Path('orphan-marker.txt').write_text('escaped')"
    )
    parent_code = (
        "import subprocess,sys; "
        "subprocess.Popen([sys.executable,'-c'," + repr(child_code) + "], "
        "stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, "
        "stderr=subprocess.DEVNULL)"
    )
    _replace_verification_command(
        root, config, [sys.executable, "-c", parent_code]
    )

    result = run_collector(root, config)
    time.sleep(0.9)

    assert result.returncode == 0, result.stdout + result.stderr
    assert not (root / "orphan-marker.txt").exists()


def test_collector_rejects_ignored_source_changes_made_by_command(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _, config = init_repo(root)
    (root / ".gitignore").write_text("ignored/\n", encoding="utf-8")
    git(root, "add", ".gitignore")
    git(root, "commit", "-qm", "ignore scratch directory")
    _replace_verification_command(
        root,
        config,
        [
            sys.executable,
            "-c",
            (
                "from pathlib import Path; "
                "p=Path('ignored/escape.txt'); p.parent.mkdir(); "
                "p.write_text('escaped')"
            ),
        ],
    )

    result = run_collector(root, config)

    assert result.returncode == 1
    assert "verification command changed non-output repository paths" in (
        result.stdout + result.stderr
    )


def test_collector_requires_repository_top_level_root(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _, config = init_repo(root)
    nested = root / "nested"
    nested.mkdir()

    result = subprocess.run(
        [
            sys.executable,
            str(COLLECTOR),
            "--root",
            str(nested),
            "--config",
            str(config),
            "--output",
            str(nested / "evidence/latest"),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "Git repository top level" in (result.stdout + result.stderr)


def test_collector_rejects_tampering_with_previous_immutable_run(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    _, config = init_repo(root)
    first = run_collector(root, config)
    assert first.returncode == 0, first.stdout + first.stderr
    pointer = json.loads((root / "evidence/latest.json").read_text(encoding="utf-8"))
    previous_report = root / pointer["run_path"] / "report.json"
    original = previous_report.read_bytes()

    _replace_verification_command(
        root,
        config,
        [
            sys.executable,
            "-c",
            (
                "from pathlib import Path; "
                f"Path({str(previous_report)!r}).write_text('tampered\\n')"
            ),
        ],
    )

    result = run_collector(root, config)

    assert result.returncode == 1
    assert "immutable evidence changed during verification" in (
        result.stdout + result.stderr
    )
    assert previous_report.read_bytes() == original
