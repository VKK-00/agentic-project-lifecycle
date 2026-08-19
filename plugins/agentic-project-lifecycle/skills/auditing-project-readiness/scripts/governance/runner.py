"""Provider-neutral bounded execution in disposable Git worktrees."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
from typing import Any, Protocol
from uuid import uuid4

from governance_contracts import validate_task_contract

from .execution_result import (
    build_execution_result,
    contract_digest,
    validate_execution_result,
)
from .policy import policy_digest, validate_policy_profile
from .run_manifest import append_event, build_run_manifest
from .runner_support import (
    GitSnapshot,
    RunnerSupportError,
    add_worktree,
    atomic_json,
    candidate_commit as create_candidate_commit,
    commit_patch,
    output_outside_source,
    prune_worktrees,
    remove_worktree,
    repository_root,
    run_verification_commands,
    snapshot,
    temporary_worktree_root,
    worktree_patch,
    write_json,
)
from .schema_validation import validate_schema_document

_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$")


class BoundedRunnerError(ValueError):
    """Raised when a bounded run cannot safely start."""


class _RunnerStageError(RuntimeError):
    """Internal stage failure that becomes a fail-closed report."""


class _RunnerCancelled(RuntimeError):
    """Internal cancellation signal."""


class ExecutionBackend(Protocol):
    """Provider-neutral planner, executor, and verifier interface."""

    name: str

    def plan(
        self,
        *,
        worktree: Path,
        task_contract: dict[str, Any],
        policy_profile: dict[str, Any],
        timeout_seconds: int,
        cancellation: "CancellationToken",
    ) -> Mapping[str, Any]: ...

    def execute(
        self,
        *,
        worktree: Path,
        task_contract: dict[str, Any],
        policy_profile: dict[str, Any],
        plan_result: dict[str, Any],
        timeout_seconds: int,
        cancellation: "CancellationToken",
    ) -> Mapping[str, Any]: ...

    def verify(
        self,
        *,
        worktree: Path,
        task_contract: dict[str, Any],
        policy_profile: dict[str, Any],
        candidate_commit: str,
        execution_result: dict[str, Any],
        command_records: list[dict[str, Any]],
        timeout_seconds: int,
        cancellation: "CancellationToken",
    ) -> Mapping[str, Any]: ...


@dataclass
class CancellationToken:
    """Thread-safe cooperative cancellation token."""

    _event: threading.Event = field(default_factory=threading.Event)

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self, stage: str) -> None:
        if self.cancelled:
            raise _RunnerCancelled(f"bounded run cancelled during {stage}")


@dataclass(frozen=True)
class PlanningRequest:
    worktree: Path
    task_contract: Mapping[str, Any]
    policy_profile: Mapping[str, Any]


@dataclass(frozen=True)
class BackendPlan:
    plan_id: str
    step_ids: tuple[str, ...]
    summary: str
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionRequest:
    worktree: Path
    task_contract: Mapping[str, Any]
    policy_profile: Mapping[str, Any]
    plan: BackendPlan


@dataclass(frozen=True)
class BackendExecution:
    summary: str
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VerificationRequest:
    worktree: Path
    task_contract: Mapping[str, Any]
    policy_profile: Mapping[str, Any]
    plan: BackendPlan
    execution_result: Mapping[str, Any]
    verification_commands: tuple[Mapping[str, Any], ...] = ()
    candidate_commit: str | None = None


@dataclass(frozen=True)
class BackendVerification:
    status: str
    summary: str
    findings: tuple[str, ...] = ()
    raw: Mapping[str, Any] = field(default_factory=dict)


def _run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"RUN-{stamp}-{uuid4().hex[:10]}"


def _safe_backend_name(backend: ExecutionBackend) -> str:
    value = getattr(backend, "name", "")
    if not isinstance(value, str) or not value.strip():
        raise BoundedRunnerError("execution backend must expose a non-empty name")
    return value.strip()


def _validate_start(
    *,
    root: Path,
    task_contract: Mapping[str, Any],
    policy_profile: Mapping[str, Any],
    confirm_task: str,
    output_root: Path,
    timeout_seconds: int,
    verification_timeout_seconds: int,
    run_id: str,
) -> tuple[GitSnapshot, Path]:
    errors: list[str] = []
    errors.extend(validate_schema_document("task", task_contract))
    errors.extend(validate_task_contract(task_contract))
    errors.extend(validate_schema_document("policy", policy_profile))
    errors.extend(validate_policy_profile(policy_profile))

    task = task_contract.get("task") if isinstance(task_contract.get("task"), Mapping) else {}
    task_id = str(task.get("id", ""))
    if confirm_task != task_id:
        errors.append(f"exact task confirmation is required: {task_id}")
    for label, value in (
        ("timeout_seconds", timeout_seconds),
        ("verification_timeout_seconds", verification_timeout_seconds),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            errors.append(f"{label} must be an integer >= 1")
    if not _RUN_ID_RE.fullmatch(run_id):
        errors.append(
            "run_id must contain only letters, numbers, dots, underscores, or hyphens"
        )

    trusted = policy_profile.get("policy") if isinstance(policy_profile.get("policy"), Mapping) else {}
    binding = task_contract.get("policy") if isinstance(task_contract.get("policy"), Mapping) else {}
    if binding.get("profile_id") != trusted.get("id"):
        errors.append("task policy profile id does not match trusted profile")
    if binding.get("profile_version") != trusted.get("version"):
        errors.append("task policy profile version does not match trusted profile")
    if binding.get("profile_sha256") != policy_digest(policy_profile):
        errors.append("task policy profile digest does not match trusted profile")

    permissions = task_contract.get("permissions") if isinstance(task_contract.get("permissions"), Mapping) else {}
    if permissions.get("filesystem") != "workspace-write-scoped":
        errors.append("bounded runner requires workspace-write-scoped filesystem permission")
    if permissions.get("network") != "disabled":
        errors.append("bounded runner requires network disabled")
    if permissions.get("production_actions") != "forbidden":
        errors.append("production actions remain forbidden")

    source = snapshot(root)
    if source.status:
        errors.append("source repository must be clean before bounded execution")
    if task.get("source_commit") != source.head:
        errors.append("task source commit does not match source repository HEAD")

    try:
        output = output_outside_source(root, output_root)
    except RunnerSupportError as exc:
        raise BoundedRunnerError(str(exc)) from exc
    final = output / "runs" / run_id
    if final.exists():
        errors.append(f"run output already exists: {final}")
    if errors:
        raise BoundedRunnerError("; ".join(errors))
    return source, output


def _mapping_result(value: object, stage: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise _RunnerStageError(f"{stage} backend result must be a mapping")
    return {str(key): item for key, item in value.items()}


def _expected_step_ids(contract: Mapping[str, Any]) -> list[str]:
    plan = contract.get("plan") if isinstance(contract.get("plan"), Mapping) else {}
    steps = plan.get("steps") if isinstance(plan.get("steps"), list) else []
    return [
        str(step.get("id"))
        for step in steps
        if isinstance(step, Mapping) and step.get("id")
    ]


def _validate_plan_result(result: Mapping[str, Any], contract: Mapping[str, Any]) -> None:
    task = contract["task"]
    plan = contract["plan"]
    if result.get("status") != "ready":
        raise _RunnerStageError("planner did not return status=ready")
    if result.get("task_id") != task["id"]:
        raise _RunnerStageError("planner task id does not match the approved task")
    if result.get("plan_id") != plan["id"]:
        raise _RunnerStageError("planner plan id does not match the approved plan")
    if result.get("step_ids") != _expected_step_ids(contract):
        raise _RunnerStageError("planner step ids do not match the approved plan")


def _validate_execute_result(result: Mapping[str, Any], contract: Mapping[str, Any]) -> None:
    task = contract["task"]
    plan = contract["plan"]
    if result.get("status") != "completed":
        raise _RunnerStageError("executor did not return status=completed")
    if result.get("task_id") != task["id"]:
        raise _RunnerStageError("executor task id does not match the approved task")
    if result.get("plan_id") != plan["id"]:
        raise _RunnerStageError("executor plan id does not match the approved plan")
    if result.get("executed_step_ids") != _expected_step_ids(contract):
        raise _RunnerStageError("executor step ids do not match the approved plan")


def _validate_verify_result(
    result: Mapping[str, Any],
    contract: Mapping[str, Any],
    candidate_commit: str,
) -> None:
    task = contract["task"]
    if result.get("task_id") != task["id"]:
        raise _RunnerStageError("verifier task id does not match the approved task")
    if result.get("candidate_commit") != candidate_commit:
        raise _RunnerStageError(
            "verifier candidate commit does not match the observed candidate"
        )
    findings = result.get("findings")
    if not isinstance(findings, list) or any(
        not isinstance(item, str) for item in findings
    ):
        raise _RunnerStageError("verifier findings must be a string list")
    if result.get("status") != "pass" or findings:
        raise _RunnerStageError("independent verifier rejected the candidate")


def _read_only_unchanged(before: GitSnapshot, after: GitSnapshot) -> bool:
    return before == after


def _write_identity_unchanged(before: GitSnapshot, after: GitSnapshot) -> bool:
    return (
        before.head == after.head
        and before.tree == after.tree
        and before.branch == after.branch
    )


def run_bounded_task(
    *,
    root: Path,
    task_contract: Mapping[str, Any],
    policy_profile: Mapping[str, Any],
    backend: ExecutionBackend,
    output_root: Path,
    confirm_task: str,
    timeout_seconds: int = 300,
    verification_timeout_seconds: int = 120,
    cancellation: CancellationToken | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Execute an approved task in disposable worktrees without applying it."""

    source = repository_root(root)
    identifier = run_id or _run_id()
    backend_name = _safe_backend_name(backend)
    source_snapshot, output = _validate_start(
        root=source,
        task_contract=task_contract,
        policy_profile=policy_profile,
        confirm_task=confirm_task,
        output_root=output_root,
        timeout_seconds=timeout_seconds,
        verification_timeout_seconds=verification_timeout_seconds,
        run_id=identifier,
    )
    token = cancellation or CancellationToken()
    task = dict(task_contract["task"])
    preserve_failed = bool(
        isinstance(task_contract.get("rollback"), Mapping)
        and task_contract["rollback"].get("preserve_failed_diff") is True
    )

    runs_root = output / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    temporary_run = runs_root / f".{identifier}.{uuid4().hex}.tmp"
    final_run = runs_root / identifier
    temporary_run.mkdir(parents=True)
    event_log = temporary_run / "events.jsonl"

    worktree_parent = temporary_worktree_root(identifier)
    execution_worktree: Path | None = None
    command_worktree: Path | None = None
    verifier_worktree: Path | None = None
    execution_started = False
    candidate_commit: str | None = None
    candidate_patch: bytes | None = None
    plan_result: dict[str, Any] | None = None
    execute_result: dict[str, Any] | None = None
    verify_result: dict[str, Any] | None = None
    command_records: list[dict[str, Any]] = []
    execution_result: dict[str, Any] | None = None
    issues: list[str] = []
    status = "fail"
    source_preserved = True
    patch_name: str | None = None

    def event(event_type: str, role: str, payload: dict[str, Any]) -> None:
        append_event(
            event_log,
            run_id=identifier,
            event_type=event_type,
            actor={"backend": backend_name, "role": role},
            payload=payload,
        )

    event(
        "run.started",
        "orchestrator",
        {
            "task_id": task["id"],
            "source_commit": source_snapshot.head,
            "task_contract_sha256": contract_digest(task_contract),
            "policy_profile_sha256": policy_digest(policy_profile),
        },
    )

    try:
        token.raise_if_cancelled("startup")
        execution_worktree = worktree_parent / "execution"
        add_worktree(source, execution_worktree, source_snapshot.head)
        event("worktree.created", "orchestrator", {"purpose": "execution"})

        event("planning.started", "planner", {})
        planning_before = snapshot(execution_worktree)
        token.raise_if_cancelled("planning")
        plan_result = _mapping_result(
            backend.plan(
                worktree=execution_worktree,
                task_contract=dict(task_contract),
                policy_profile=dict(policy_profile),
                timeout_seconds=timeout_seconds,
                cancellation=token,
            ),
            "planner",
        )
        write_json(temporary_run / "plan-result.json", plan_result)
        token.raise_if_cancelled("planning")
        if not _read_only_unchanged(planning_before, snapshot(execution_worktree)):
            raise _RunnerStageError("planner changed the read-only worktree")
        _validate_plan_result(plan_result, task_contract)
        event("planning.completed", "planner", {"result": plan_result})

        if snapshot(source) != source_snapshot:
            source_preserved = False
            raise _RunnerStageError(
                "source repository changed during bounded execution"
            )

        event("execution.started", "executor", {})
        execution_started = True
        execution_before = snapshot(execution_worktree)
        token.raise_if_cancelled("execution")
        execute_result = _mapping_result(
            backend.execute(
                worktree=execution_worktree,
                task_contract=dict(task_contract),
                policy_profile=dict(policy_profile),
                plan_result=plan_result,
                timeout_seconds=timeout_seconds,
                cancellation=token,
            ),
            "executor",
        )
        write_json(temporary_run / "execute-result.json", execute_result)
        token.raise_if_cancelled("execution")
        if not _write_identity_unchanged(
            execution_before, snapshot(execution_worktree)
        ):
            raise _RunnerStageError("executor changed worktree HEAD, tree, or branch")
        _validate_execute_result(execute_result, task_contract)
        event("execution.completed", "executor", {"result": execute_result})

        if snapshot(source) != source_snapshot:
            source_preserved = False
            raise _RunnerStageError(
                "source repository changed during bounded execution"
            )

        candidate_commit = create_candidate_commit(
            execution_worktree,
            source_commit=source_snapshot.head,
            task_id=str(task["id"]),
        )
        candidate_patch = commit_patch(
            source, source_snapshot.head, candidate_commit
        )
        execution_result = build_execution_result(
            root=source,
            contract=task_contract,
            head_commit=candidate_commit,
        )
        violations = validate_execution_result(
            execution_result,
            contract=task_contract,
            root=source,
        )
        execution_result["execution"]["status"] = (
            "pass" if not violations else "fail"
        )
        execution_result["result"] = {
            "status": "pass" if not violations else "fail",
            "violations": violations,
        }
        write_json(temporary_run / "execution-result.json", execution_result)
        event(
            "diff.validated",
            "orchestrator",
            {
                "candidate_commit": candidate_commit,
                "violations": violations,
            },
        )
        if violations:
            raise _RunnerStageError("; ".join(violations))

        command_worktree = worktree_parent / "command-verification"
        add_worktree(source, command_worktree, candidate_commit)
        event(
            "verification.commands.started",
            "deterministic-verifier",
            {"candidate_commit": candidate_commit},
        )
        command_records = run_verification_commands(
            workspace=command_worktree,
            task_contract=task_contract,
            run_dir=temporary_run,
            timeout_seconds=verification_timeout_seconds,
        )
        event(
            "verification.commands.completed",
            "deterministic-verifier",
            {"commands": command_records},
        )
        token.raise_if_cancelled("deterministic verification")

        verifier_worktree = worktree_parent / "semantic-verification"
        add_worktree(source, verifier_worktree, candidate_commit)
        event(
            "verification.semantic.started",
            "verifier",
            {"candidate_commit": candidate_commit},
        )
        verification_before = snapshot(verifier_worktree)
        token.raise_if_cancelled("semantic verification")
        verify_result = _mapping_result(
            backend.verify(
                worktree=verifier_worktree,
                task_contract=dict(task_contract),
                policy_profile=dict(policy_profile),
                candidate_commit=candidate_commit,
                execution_result=execution_result,
                command_records=command_records,
                timeout_seconds=timeout_seconds,
                cancellation=token,
            ),
            "verifier",
        )
        write_json(temporary_run / "verify-result.json", verify_result)
        token.raise_if_cancelled("semantic verification")
        if not _read_only_unchanged(
            verification_before, snapshot(verifier_worktree)
        ):
            raise _RunnerStageError(
                "verifier changed the read-only candidate worktree"
            )
        _validate_verify_result(verify_result, task_contract, candidate_commit)
        event(
            "verification.semantic.completed",
            "verifier",
            {"result": verify_result},
        )

        if snapshot(source) != source_snapshot:
            source_preserved = False
            raise _RunnerStageError(
                "source repository changed during bounded execution"
            )

        (temporary_run / "candidate.patch").write_bytes(candidate_patch)
        patch_name = "candidate.patch"
        status = "pass"
    except _RunnerCancelled as exc:
        status = "cancelled"
        issues.append(str(exc))
        event("run.cancelled", "orchestrator", {"reason": str(exc)})
    except (TimeoutError, subprocess.TimeoutExpired) as exc:
        status = "fail"
        issues.append(str(exc))
        event(
            "run.failed",
            "orchestrator",
            {"reason": str(exc), "kind": "timeout"},
        )
    except (BoundedRunnerError, _RunnerStageError, RunnerSupportError, ValueError) as exc:
        status = "fail"
        issues.append(str(exc))
        event("run.failed", "orchestrator", {"reason": str(exc)})
    except Exception as exc:  # Backend boundary must fail closed.
        status = "fail"
        message = f"{type(exc).__name__}: {exc}"
        issues.append(message)
        event("run.failed", "orchestrator", {"reason": message})
    finally:
        if status != "pass" and execution_started and preserve_failed:
            patch = candidate_patch
            if (
                patch is None
                and execution_worktree is not None
                and execution_worktree.exists()
            ):
                try:
                    patch = worktree_patch(execution_worktree)
                except Exception as exc:  # Preserve the primary failure.
                    issues.append(f"failed patch export failed: {exc}")
            if patch:
                (temporary_run / "failed.patch").write_bytes(patch)
                patch_name = "failed.patch"

        remove_worktree(source, verifier_worktree)
        remove_worktree(source, command_worktree)
        remove_worktree(source, execution_worktree)
        prune_worktrees(source)
        shutil.rmtree(worktree_parent, ignore_errors=True)

        if snapshot(source) != source_snapshot:
            source_preserved = False
            message = "source repository changed during bounded execution"
            if message not in issues:
                issues.append(message)
            status = "fail"

        event(
            "run.completed",
            "orchestrator",
            {
                "status": status,
                "source_preserved": source_preserved,
                "candidate_commit": candidate_commit,
                "patch": patch_name,
            },
        )

        report: dict[str, Any] = {
            "schema_version": "1.0",
            "run": {
                "id": identifier,
                "status": status,
                "task_id": task["id"],
                "backend": backend_name,
                "source_commit": source_snapshot.head,
                "candidate_commit": candidate_commit,
            },
            "stages": {
                "plan": plan_result,
                "execute": execute_result,
                "deterministic_verification": command_records,
                "verify": verify_result,
            },
            "execution_result": execution_result,
            "transaction": {
                "source_preserved": source_preserved,
                "rollback_status": (
                    "source-unchanged"
                    if source_preserved
                    else "external-source-mutation-detected"
                ),
                "patch": patch_name,
            },
            "issues": issues,
        }
        report_path = temporary_run / "report.json"
        write_json(report_path, report)
        manifest = build_run_manifest(
            run_id=identifier,
            source_commit=source_snapshot.head,
            source_tree=source_snapshot.tree,
            branch=source_snapshot.branch,
            event_log=event_log,
            report=report_path,
            metadata={
                "backend": backend_name,
                "task_id": task["id"],
                "status": status,
                "candidate_commit": candidate_commit,
                "task_contract_sha256": contract_digest(task_contract),
                "policy_profile_sha256": policy_digest(policy_profile),
                "patch": patch_name,
            },
        )
        write_json(temporary_run / "run-manifest.json", manifest)
        os.replace(temporary_run, final_run)
        atomic_json(
            output / "latest.json",
            {
                "run_id": identifier,
                "status": status,
                "path": f"runs/{identifier}",
            },
        )

    return report
