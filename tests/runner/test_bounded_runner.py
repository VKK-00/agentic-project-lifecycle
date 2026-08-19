from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "plugins/agentic-project-lifecycle/skills/auditing-project-readiness/scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from governance.policy import policy_digest  # noqa: E402
from governance.run_manifest import validate_run_manifest, verify_event_log  # noqa: E402
from governance.runner import (  # noqa: E402
    BoundedRunnerError,
    CancellationToken,
    run_bounded_task,
)
from governance.runner_support import (  # noqa: E402
    IsolationCapability,
    RunnerSupportError,
    network_isolation_command,
    probe_network_isolation,
    run_verification_commands,
)


def git(root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, text=True, capture_output=True, check=False
    )
    if check:
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


def task_contract(base: str, *, allowed_paths: list[str] | None = None) -> dict:
    profile = policy_profile()
    command = "python -m pytest -q"
    return {
        "schema_version": "1.0",
        "task": {
            "id": "TASK-RUN-001",
            "objective": "Apply one bounded application change",
            "kind": "feature",
            "source_commit": base,
            "risk_level": "high",
            "current_gate": "implementation",
        },
        "scope": {
            "allowed_paths": allowed_paths or ["src/**", "tests/**"],
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
            "id": "PLAN-RUN-001",
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


class FakeBackend:
    name = "fake"

    def __init__(
        self,
        *,
        planner_mutates: bool = False,
        execute_path: str = "src/app.py",
        verifier_mutates: bool = False,
        cancel_after_execute: bool = False,
        timeout_stage: str | None = None,
        mutate_source: Path | None = None,
    ) -> None:
        self.planner_mutates = planner_mutates
        self.execute_path = execute_path
        self.verifier_mutates = verifier_mutates
        self.cancel_after_execute = cancel_after_execute
        self.timeout_stage = timeout_stage
        self.mutate_source = mutate_source
        self.verify_calls = 0

    def plan(self, *, worktree: Path, task_contract: dict, policy_profile: dict, timeout_seconds: int, cancellation: CancellationToken) -> dict:
        if self.timeout_stage == "plan":
            raise TimeoutError("planner timeout")
        if self.planner_mutates:
            (worktree / "src/app.py").write_text("PLANNER = 1\n", encoding="utf-8")
        return {
            "status": "ready",
            "task_id": task_contract["task"]["id"],
            "plan_id": task_contract["plan"]["id"],
            "step_ids": [step["id"] for step in task_contract["plan"]["steps"]],
            "summary": "Approved plan understood",
        }

    def execute(self, *, worktree: Path, task_contract: dict, policy_profile: dict, plan_result: dict, timeout_seconds: int, cancellation: CancellationToken) -> dict:
        if self.timeout_stage == "execute":
            raise TimeoutError("executor timeout")
        target = worktree / self.execute_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("VALUE = 2\n", encoding="utf-8")
        if self.mutate_source is not None:
            (self.mutate_source / "README.md").write_text("concurrent mutation\n", encoding="utf-8")
        if self.cancel_after_execute:
            cancellation.cancel()
        return {
            "status": "completed",
            "task_id": task_contract["task"]["id"],
            "plan_id": task_contract["plan"]["id"],
            "executed_step_ids": [step["id"] for step in task_contract["plan"]["steps"]],
            "summary": "Change applied in isolated worktree",
        }

    def verify(self, *, worktree: Path, task_contract: dict, policy_profile: dict, candidate_commit: str, execution_result: dict, command_records: list[dict], timeout_seconds: int, cancellation: CancellationToken) -> dict:
        self.verify_calls += 1
        if self.timeout_stage == "verify":
            raise TimeoutError("verifier timeout")
        if self.verifier_mutates:
            (worktree / "src/app.py").write_text("VERIFIER = 1\n", encoding="utf-8")
        return {
            "status": "pass",
            "task_id": task_contract["task"]["id"],
            "candidate_commit": candidate_commit,
            "findings": [],
            "summary": "Candidate independently verified",
        }


def run_dir(output: Path, report: dict) -> Path:
    return output / "runs" / report["run"]["id"]


def assert_source_unchanged(root: Path, base: str) -> None:
    assert git(root, "rev-parse", "HEAD") == base
    assert git(root, "status", "--porcelain=v1", "--untracked-files=all") == ""
    assert (root / "src/app.py").read_text(encoding="utf-8") == "VALUE = 1\n"


def test_bounded_runner_exports_valid_candidate_without_touching_source(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    base = init_repo(root)
    output = tmp_path / "runner-output"
    contract = task_contract(base)
    backend = FakeBackend()

    report = run_bounded_task(
        root=root,
        task_contract=contract,
        policy_profile=policy_profile(),
        backend=backend,
        output_root=output,
        confirm_task="TASK-RUN-001",
        timeout_seconds=20,
        run_id="RUN-TEST-SUCCESS",
    )

    assert report["run"]["status"] == "pass"
    assert report["run"]["candidate_commit"] != base
    assert report["execution_result"]["result"] == {"status": "pass", "violations": []}
    assert backend.verify_calls == 1
    assert_source_unchanged(root, base)

    folder = run_dir(output, report)
    patch = folder / "candidate.patch"
    assert patch.is_file()
    assert "VALUE = 2" in patch.read_text(encoding="utf-8")
    assert verify_event_log(folder / "events.jsonl") == []
    manifest = json.loads((folder / "run-manifest.json").read_text(encoding="utf-8"))
    assert validate_run_manifest(
        manifest,
        event_log=folder / "events.jsonl",
        report=folder / "report.json",
    ) == []
    latest = json.loads((output / "latest.json").read_text(encoding="utf-8"))
    assert latest["run_id"] == "RUN-TEST-SUCCESS"
    assert latest["status"] == "pass"
    assert "apl-runner-" not in git(root, "worktree", "list", "--porcelain")


def test_bounded_runner_rejects_planner_writes_and_cleans_worktree(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    base = init_repo(root)
    output = tmp_path / "runner-output"

    report = run_bounded_task(
        root=root,
        task_contract=task_contract(base),
        policy_profile=policy_profile(),
        backend=FakeBackend(planner_mutates=True),
        output_root=output,
        confirm_task="TASK-RUN-001",
        run_id="RUN-TEST-PLANNER",
    )

    assert report["run"]["status"] == "fail"
    assert any("planner changed the read-only worktree" in issue for issue in report["issues"])
    assert_source_unchanged(root, base)
    assert not (run_dir(output, report) / "candidate.patch").exists()
    assert "apl-runner-" not in git(root, "worktree", "list", "--porcelain")


def test_bounded_runner_preserves_failed_out_of_scope_patch_and_skips_verifier(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    base = init_repo(root)
    output = tmp_path / "runner-output"
    backend = FakeBackend(execute_path="docs/escape.md")

    report = run_bounded_task(
        root=root,
        task_contract=task_contract(base),
        policy_profile=policy_profile(),
        backend=backend,
        output_root=output,
        confirm_task="TASK-RUN-001",
        run_id="RUN-TEST-SCOPE",
    )

    assert report["run"]["status"] == "fail"
    assert any("changed path is outside allowed scope: docs/escape.md" in issue for issue in report["issues"])
    assert backend.verify_calls == 0
    patch = run_dir(output, report) / "failed.patch"
    assert patch.is_file()
    assert "docs/escape.md" in patch.read_text(encoding="utf-8")
    assert_source_unchanged(root, base)


def test_bounded_runner_rejects_verifier_writes(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    base = init_repo(root)
    output = tmp_path / "runner-output"

    report = run_bounded_task(
        root=root,
        task_contract=task_contract(base),
        policy_profile=policy_profile(),
        backend=FakeBackend(verifier_mutates=True),
        output_root=output,
        confirm_task="TASK-RUN-001",
        run_id="RUN-TEST-VERIFIER",
    )

    assert report["run"]["status"] == "fail"
    assert any("verifier changed the read-only candidate worktree" in issue for issue in report["issues"])
    assert (run_dir(output, report) / "failed.patch").is_file()
    assert_source_unchanged(root, base)


def test_bounded_runner_honors_cancellation_after_execution(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    base = init_repo(root)
    output = tmp_path / "runner-output"

    report = run_bounded_task(
        root=root,
        task_contract=task_contract(base),
        policy_profile=policy_profile(),
        backend=FakeBackend(cancel_after_execute=True),
        output_root=output,
        confirm_task="TASK-RUN-001",
        cancellation=CancellationToken(),
        run_id="RUN-TEST-CANCEL",
    )

    assert report["run"]["status"] == "cancelled"
    assert any("cancelled" in issue for issue in report["issues"])
    assert (run_dir(output, report) / "failed.patch").is_file()
    assert_source_unchanged(root, base)


def test_bounded_runner_records_backend_timeout(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    base = init_repo(root)
    output = tmp_path / "runner-output"

    report = run_bounded_task(
        root=root,
        task_contract=task_contract(base),
        policy_profile=policy_profile(),
        backend=FakeBackend(timeout_stage="execute"),
        output_root=output,
        confirm_task="TASK-RUN-001",
        timeout_seconds=1,
        run_id="RUN-TEST-TIMEOUT",
    )

    assert report["run"]["status"] == "fail"
    assert any("executor timeout" in issue for issue in report["issues"])
    assert_source_unchanged(root, base)


def test_bounded_runner_detects_concurrent_source_mutation(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    base = init_repo(root)
    output = tmp_path / "runner-output"

    report = run_bounded_task(
        root=root,
        task_contract=task_contract(base),
        policy_profile=policy_profile(),
        backend=FakeBackend(mutate_source=root),
        output_root=output,
        confirm_task="TASK-RUN-001",
        run_id="RUN-TEST-SOURCE-MUTATION",
    )

    assert report["run"]["status"] == "fail"
    assert report["transaction"]["source_preserved"] is False
    assert any("source repository changed during bounded execution" in issue for issue in report["issues"])


def test_bounded_runner_requires_exact_task_confirmation_and_external_output(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    base = init_repo(root)
    contract = task_contract(base)

    with pytest.raises(BoundedRunnerError, match="exact task confirmation"):
        run_bounded_task(
            root=root,
            task_contract=contract,
            policy_profile=policy_profile(),
            backend=FakeBackend(),
            output_root=tmp_path / "output",
            confirm_task="WRONG",
        )

    with pytest.raises(BoundedRunnerError, match="outside the source repository"):
        run_bounded_task(
            root=root,
            task_contract=contract,
            policy_profile=policy_profile(),
            backend=FakeBackend(),
            output_root=root / "runner-output",
            confirm_task="TASK-RUN-001",
        )


def test_network_isolation_command_fails_closed_when_platform_has_no_supported_isolator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("governance.runner_support.platform.system", lambda: "Windows")
    with pytest.raises(RunnerSupportError, match="network-isolated verification"):
        network_isolation_command(["python", "-m", "pytest", "-q"])


def test_network_isolation_probe_reports_permission_denied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("governance.runner_support.platform.system", lambda: "Linux")
    monkeypatch.setattr(
        "governance.runner_support.shutil.which",
        lambda name: "/usr/bin/unshare" if name == "unshare" else None,
    )
    monkeypatch.setattr(
        "governance.runner_support.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0], returncode=1, stdout="", stderr="unshare: Operation not permitted"
        ),
    )

    capability = probe_network_isolation()

    assert capability.available is False
    assert capability.mechanism == "linux-unshare"
    assert "Operation not permitted" in capability.reason


def test_network_isolation_command_fails_closed_when_probe_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "governance.runner_support.probe_network_isolation",
        lambda: IsolationCapability(
            available=False,
            platform="Linux",
            mechanism="linux-unshare",
            executable="/usr/bin/unshare",
            reason="unshare: Operation not permitted",
        ),
    )

    with pytest.raises(RunnerSupportError, match="Operation not permitted"):
        network_isolation_command(["python", "-m", "pytest", "-q"])


def test_network_isolation_command_uses_probed_linux_network_namespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "governance.runner_support.probe_network_isolation",
        lambda: IsolationCapability(
            available=True,
            platform="Linux",
            mechanism="linux-unshare",
            executable="/usr/bin/unshare",
            reason="network namespace changed",
        ),
    )
    assert network_isolation_command(["python", "-m", "pytest", "-q"]) == [
        "/usr/bin/unshare",
        "--net",
        "--pid",
        "--fork",
        "--kill-child=SIGKILL",
        "--map-root-user",
        "--",
        "python",
        "-m",
        "pytest",
        "-q",
    ]


def test_verification_rejects_ignored_candidate_side_effects(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    init_repo(root)
    (root / ".gitignore").write_text("ignored/\n", encoding="utf-8")
    git(root, "add", ".gitignore")
    git(root, "commit", "-qm", "ignore scratch directory")
    script = root / "write_ignored.py"
    script.write_text(
        "from pathlib import Path\n"
        "path = Path('ignored/escape.txt')\n"
        "path.parent.mkdir()\n"
        "path.write_text('escaped')\n",
        encoding="utf-8",
    )
    git(root, "add", "write_ignored.py")
    git(root, "commit", "-qm", "add verification fixture")
    base = git(root, "rev-parse", "HEAD")
    contract = task_contract(base)
    command = f"{sys.executable} write_ignored.py"
    contract["permissions"]["allowed_commands"] = [command]
    contract["plan"]["steps"][0]["verification_commands"] = [command]

    with pytest.raises(
        RunnerSupportError, match="verification command created ignored candidate files"
    ):
        run_verification_commands(
            workspace=root,
            task_contract=contract,
            run_dir=tmp_path / "run",
            timeout_seconds=10,
        )


def test_bounded_runner_rejects_executor_ignored_files(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    init_repo(root)
    (root / ".gitignore").write_text("ignored/\n", encoding="utf-8")
    git(root, "add", ".gitignore")
    git(root, "commit", "-qm", "ignore scratch directory")
    base = git(root, "rev-parse", "HEAD")

    report = run_bounded_task(
        root=root,
        task_contract=task_contract(base),
        policy_profile=policy_profile(),
        backend=FakeBackend(execute_path="ignored/escape.py"),
        output_root=tmp_path / "runner-output",
        confirm_task="TASK-RUN-001",
        run_id="RUN-TEST-IGNORED-EXECUTOR",
    )

    assert report["run"]["status"] == "fail"
    assert any(
        "executor created ignored candidate files" in issue
        for issue in report["issues"]
    )
    assert_source_unchanged(root, base)
