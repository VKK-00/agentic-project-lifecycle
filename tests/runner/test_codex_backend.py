from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import threading
import time

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "plugins/agentic-project-lifecycle/skills/auditing-project-readiness/scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from governance.codex_backend import CodexBackend  # noqa: E402
from governance.policy import policy_digest  # noqa: E402
from governance.runner import CancellationToken  # noqa: E402


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, text=True, capture_output=True, check=False
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def init_repo(root: Path) -> str:
    root.mkdir(parents=True)
    git(root, "init", "-q")
    git(root, "config", "user.name", "Test User")
    git(root, "config", "user.email", "test@example.com")
    (root / "src").mkdir()
    (root / "tests").mkdir()
    (root / "src/app.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "tests/test_app.py").write_text(
        "def test_value():\n    assert True\n", encoding="utf-8"
    )
    git(root, "add", ".")
    git(root, "commit", "-qm", "base")
    return git(root, "rev-parse", "HEAD")


def policy_profile() -> dict:
    return {
        "schema_version": "1.0",
        "policy": {
            "id": "default-software",
            "version": "1.0",
            "name": "Default software lifecycle",
            "minimum_approval_assurance": "declared",
            "protected_paths": [".github/**", "migrations/**"],
        },
        "gates": [
            {
                "id": "implementation-to-release",
                "from": "implementation",
                "to": "release",
                "required_claims": [
                    "unit_tests",
                    "integration_tests",
                    "diff_conformance",
                ],
                "required_roles": ["engineering-owner"],
                "non_waivable_blocker_classes": [
                    "security-critical",
                    "data-integrity",
                ],
                "allow_phase_skip": False,
            }
        ],
    }


def task_contract(base: str) -> dict:
    profile = policy_profile()
    command = "python -m pytest -q"
    return {
        "schema_version": "1.0",
        "task": {
            "id": "TASK-CODEX-001",
            "objective": "Apply one bounded application change",
            "kind": "feature",
            "source_commit": base,
            "risk_level": "high",
            "current_gate": "implementation",
        },
        "scope": {
            "allowed_paths": ["src/**", "tests/**"],
            "forbidden_paths": [".github/**", "migrations/**"],
            "max_changed_files": 4,
            "max_diff_lines": 100,
            "max_new_dependencies": 0,
        },
        "permissions": {
            "filesystem": "workspace-write-scoped",
            "network": "disabled",
            "allowed_commands": [command],
            "forbidden_command_patterns": ["git push", "rm -rf"],
            "dependency_changes": "forbidden",
            "destructive_actions": "forbidden",
            "production_actions": "forbidden",
        },
        "plan": {
            "id": "PLAN-CODEX-001",
            "status": "approved",
            "steps": [
                {
                    "id": "STEP-001",
                    "addresses": ["REQ-001"],
                    "action": "Update the application value",
                    "expected_changes": "Application source and focused tests",
                    "verification_commands": [command],
                }
            ],
        },
        "approval": {
            "required": True,
            "status": "approved",
            "approved_by": "alice",
            "approved_at": "2026-08-18T00:00:00Z",
            "source_commit": base,
        },
        "rollback": {
            "checkpoint_commit": base,
            "strategy": "reset-to-checkpoint",
            "preserve_failed_diff": True,
        },
        "completion": {
            "required_evidence": [
                "unit_tests",
                "integration_tests",
                "diff_conformance",
            ]
        },
        "policy": {
            "profile_id": profile["policy"]["id"],
            "profile_version": profile["policy"]["version"],
            "profile_sha256": policy_digest(profile),
        },
    }


def write_fake_codex(path: Path) -> None:
    path.write_text(
        """#!/usr/bin/env python3
import json
import os
from pathlib import Path
import re
import sys

args = sys.argv[1:]
prompt = sys.stdin.read()
entry = {
    "argv": args,
    "stdin": prompt,
    "cwd": str(Path.cwd()),
    "inherited_test_secret": os.environ.get("APL_TEST_SECRET_TOKEN"),
}
log = Path(os.environ["FAKE_CODEX_LOG"])
with log.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(entry) + "\\n")

def value(flag):
    return args[args.index(flag) + 1]

if "[APL_STAGE=plan]" in prompt:
    payload = {
        "status": "ready",
        "task_id": "TASK-CODEX-001",
        "plan_id": "PLAN-CODEX-001",
        "step_ids": ["STEP-001"],
        "summary": "approved plan understood",
    }
elif "[APL_STAGE=execute]" in prompt:
    (Path.cwd() / "src/app.py").write_text("VALUE = 2\\n", encoding="utf-8")
    payload = {
        "status": "completed",
        "task_id": "TASK-CODEX-001",
        "plan_id": "PLAN-CODEX-001",
        "executed_step_ids": ["STEP-001"],
        "summary": "bounded change completed",
    }
else:
    match = re.search(r'"candidate_commit"\\s*:\\s*"([0-9a-f]{40})"', prompt)
    payload = {
        "status": "pass",
        "task_id": "TASK-CODEX-001",
        "candidate_commit": match.group(1) if match else "0" * 40,
        "findings": [],
        "summary": "candidate verified",
    }
if os.environ.get("FAKE_CODEX_INVALID_SCHEMA"):
    payload["summary"] = 123
Path(value("--output-last-message")).write_text(json.dumps(payload), encoding="utf-8")
print(json.dumps({"type": "fake.completed"}))
""",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def test_codex_backend_uses_locked_down_exec_flags_and_structured_outputs(
    tmp_path: Path,
) -> None:
    fake = tmp_path / "codex"
    log = tmp_path / "codex-calls.jsonl"
    write_fake_codex(fake)
    worktree = tmp_path / "workspace"
    (worktree / "src").mkdir(parents=True)
    (worktree / "src/app.py").write_text("VALUE = 1\n", encoding="utf-8")
    contract = task_contract("a" * 40)
    profile = policy_profile()
    backend = CodexBackend(
        model="gpt-5.3-codex",
        executable=str(fake),
        environment={"FAKE_CODEX_LOG": str(log)},
    )
    token = CancellationToken()

    plan = backend.plan(
        worktree=worktree,
        task_contract=contract,
        policy_profile=profile,
        timeout_seconds=20,
        cancellation=token,
    )
    execute = backend.execute(
        worktree=worktree,
        task_contract=contract,
        policy_profile=profile,
        plan_result=plan,
        timeout_seconds=20,
        cancellation=token,
    )
    verify = backend.verify(
        worktree=worktree,
        task_contract=contract,
        policy_profile=profile,
        candidate_commit="b" * 40,
        execution_result={"result": {"status": "pass", "violations": []}},
        timeout_seconds=20,
        cancellation=token,
    )

    assert plan["status"] == "ready"
    assert execute["status"] == "completed"
    assert verify["status"] == "pass"
    calls = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert len(calls) == 3
    forbidden = {
        "--dangerously-bypass-approvals-and-sandbox",
        "--full-auto",
        "--yolo",
        "danger-full-access",
    }
    for index, call in enumerate(calls):
        argv = call["argv"]
        assert argv[0] == "exec"
        assert argv[-1] == "-"
        assert "--ask-for-approval" in argv
        assert argv[argv.index("--ask-for-approval") + 1] == "never"
        for flag in (
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--json",
            "--output-schema",
            "--output-last-message",
            "--cd",
            "--model",
        ):
            assert flag in argv
        assert argv[argv.index("--model") + 1] == "gpt-5.3-codex"
        assert "sandbox_workspace_write.network_access=false" in argv
        assert not forbidden.intersection(argv)
        expected_sandbox = "workspace-write" if index == 1 else "read-only"
        assert argv[argv.index("--sandbox") + 1] == expected_sandbox
    assert "[APL_STAGE=plan]" in calls[0]["stdin"]
    assert "[APL_STAGE=execute]" in calls[1]["stdin"]
    assert "[APL_STAGE=verify]" in calls[2]["stdin"]
    assert '"candidate_commit": "' + "b" * 40 + '"' in calls[2]["stdin"]


def test_codex_backend_requires_explicit_model_and_existing_executable(
    tmp_path: Path,
) -> None:
    fake = tmp_path / "codex"
    write_fake_codex(fake)
    for model in ("latest", "auto", "default"):
        with pytest.raises(ValueError, match="explicit pinned model"):
            CodexBackend(model=model, executable=str(fake))
    with pytest.raises(ValueError, match="cannot find Codex executable"):
        CodexBackend(model="gpt-5.3-codex", executable=str(tmp_path / "missing"))


def test_codex_backend_does_not_inherit_unrelated_secret_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = tmp_path / "codex"
    log = tmp_path / "codex-calls.jsonl"
    write_fake_codex(fake)
    worktree = tmp_path / "workspace"
    worktree.mkdir()
    monkeypatch.setenv("APL_TEST_SECRET_TOKEN", "must-not-reach-codex")
    backend = CodexBackend(
        model="gpt-5.3-codex",
        executable=str(fake),
        environment={"FAKE_CODEX_LOG": str(log)},
    )

    backend.plan(
        worktree=worktree,
        task_contract=task_contract("a" * 40),
        policy_profile=policy_profile(),
        timeout_seconds=20,
        cancellation=CancellationToken(),
    )

    call = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
    assert call["inherited_test_secret"] is None


def test_codex_backend_terminates_in_flight_process_when_cancelled(
    tmp_path: Path,
) -> None:
    fake = tmp_path / "codex"
    fake.write_text(
        "#!/usr/bin/env python3\nimport time\ntime.sleep(10)\n",
        encoding="utf-8",
    )
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    worktree = tmp_path / "workspace"
    worktree.mkdir()
    token = CancellationToken()
    timer = threading.Timer(0.15, token.cancel)
    timer.start()
    backend = CodexBackend(model="gpt-5.3-codex", executable=str(fake))
    started = time.monotonic()
    try:
        with pytest.raises(Exception, match="cancelled"):
            backend.plan(
                worktree=worktree,
                task_contract=task_contract("a" * 40),
                policy_profile=policy_profile(),
                timeout_seconds=20,
                cancellation=token,
            )
    finally:
        timer.cancel()
    assert time.monotonic() - started < 2.0


def test_apl_run_requires_experimental_flag(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    base = init_repo(root)
    task_path = tmp_path / "task.yaml"
    policy_path = tmp_path / "policy.yaml"
    task_path.write_text(yaml.safe_dump(task_contract(base), sort_keys=False), encoding="utf-8")
    policy_path.write_text(yaml.safe_dump(policy_profile(), sort_keys=False), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/apl_cli.py"),
            "run",
            "--backend",
            "codex",
            "--root",
            str(root),
            "--task",
            str(task_path),
            "--policy",
            str(policy_path),
            "--output",
            str(tmp_path / "output"),
            "--confirm-task",
            "TASK-CODEX-001",
            "--model",
            "gpt-5.3-codex",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "--experimental" in result.stderr


def test_apl_run_executes_fake_codex_backend_end_to_end(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    base = init_repo(root)
    task_path = tmp_path / "task.yaml"
    policy_path = tmp_path / "policy.yaml"
    output = tmp_path / "output"
    fake = tmp_path / "codex"
    log = tmp_path / "calls.jsonl"
    write_fake_codex(fake)
    task_path.write_text(yaml.safe_dump(task_contract(base), sort_keys=False), encoding="utf-8")
    policy_path.write_text(yaml.safe_dump(policy_profile(), sort_keys=False), encoding="utf-8")
    env = os.environ.copy()
    env["FAKE_CODEX_LOG"] = str(log)

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/apl_cli.py"),
            "run",
            "--experimental",
            "--backend",
            "codex",
            "--root",
            str(root),
            "--task",
            str(task_path),
            "--policy",
            str(policy_path),
            "--output",
            str(output),
            "--confirm-task",
            "TASK-CODEX-001",
            "--model",
            "gpt-5.3-codex",
            "--codex-executable",
            str(fake),
            "--timeout-seconds",
            "20",
            "--format",
            "json",
        ],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["run"]["status"] == "pass"
    assert (output / "runs" / report["run"]["id"] / "candidate.patch").is_file()
    assert git(root, "rev-parse", "HEAD") == base
    assert (root / "src/app.py").read_text(encoding="utf-8") == "VALUE = 1\n"


def test_experimental_runner_documentation_states_security_boundary() -> None:
    text = (ROOT / "docs/EXPERIMENTAL_RUNNER.md").read_text(encoding="utf-8").lower()
    for phrase in (
        "experimental",
        "explicit task confirmation",
        "read-only planner",
        "independent verifier",
        "network access is disabled",
        "operating-system network isolation",
        "secret environment variables",
        "never applies the candidate patch automatically",
        "authenticated smoke test",
    ):
        assert phrase in text


def test_codex_backend_revalidates_structured_output_locally(
    tmp_path: Path,
) -> None:
    fake = tmp_path / "codex"
    log = tmp_path / "codex-calls.jsonl"
    write_fake_codex(fake)
    worktree = tmp_path / "workspace"
    worktree.mkdir()
    backend = CodexBackend(
        model="gpt-5.3-codex",
        executable=str(fake),
        environment={
            "FAKE_CODEX_LOG": str(log),
            "FAKE_CODEX_INVALID_SCHEMA": "1",
        },
    )

    with pytest.raises(ValueError, match="structured output violates schema"):
        backend.plan(
            worktree=worktree,
            task_contract=task_contract("a" * 40),
            policy_profile=policy_profile(),
            timeout_seconds=20,
            cancellation=CancellationToken(),
        )


def test_codex_backend_terminates_background_descendants_after_success(
    tmp_path: Path,
) -> None:
    fake = tmp_path / "codex"
    marker = tmp_path / "orphan-marker.txt"
    child_code = (
        "import time; from pathlib import Path; "
        f"time.sleep(0.6); Path({str(marker)!r}).write_text('escaped')"
    )
    script = f"""#!/usr/bin/env python3
import json,subprocess,sys
from pathlib import Path
args=sys.argv[1:]
def value(flag): return args[args.index(flag)+1]
subprocess.Popen([sys.executable,'-c',{child_code!r}], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
payload={{'status':'ready','task_id':'TASK-CODEX-001','plan_id':'PLAN-CODEX-001','step_ids':['STEP-001'],'summary':'ready'}}
Path(value('--output-last-message')).write_text(json.dumps(payload), encoding='utf-8')
print(json.dumps({{'type':'done'}}))
"""
    fake.write_text(script, encoding="utf-8")
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    worktree = tmp_path / "workspace"
    worktree.mkdir()
    backend = CodexBackend(model="gpt-5.3-codex", executable=str(fake))

    result = backend.plan(
        worktree=worktree,
        task_contract=task_contract("a" * 40),
        policy_profile=policy_profile(),
        timeout_seconds=20,
        cancellation=CancellationToken(),
    )
    time.sleep(0.9)

    assert result["status"] == "ready"
    assert not marker.exists()
