"""Git, process, and artifact helpers for the bounded runner."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import signal
import stat
import shlex
import shutil
import subprocess
import tempfile
import time
from typing import Any
from uuid import uuid4

_SENSITIVE_ENV_RE = re.compile(
    r"(?i)(?:password|passwd|secret|token|api[_-]?key|authorization|credential|private[_-]?key)"
)
_SHELL_CONTROL_RE = re.compile(r"(?:&&|\|\||[|;<>`]|\$\(|\r|\n)")
_AUTH_CONTEXT_ENV_KEYS = {
    "AWS_CONFIG_FILE",
    "AWS_DEFAULT_PROFILE",
    "AWS_PROFILE",
    "AWS_SHARED_CREDENTIALS_FILE",
    "AZURE_CONFIG_DIR",
    "CODEX_HOME",
    "DOCKER_CONFIG",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "KUBECONFIG",
    "NETRC",
    "NPM_CONFIG_USERCONFIG",
    "PIP_CONFIG_FILE",
}

_SHELL_INTERPRETERS = {
    "bash",
    "sh",
    "zsh",
    "fish",
    "cmd",
    "cmd.exe",
    "powershell",
    "powershell.exe",
    "pwsh",
}


class RunnerSupportError(RuntimeError):
    """Fail-closed helper failure."""


@dataclass(frozen=True)
class SupervisedProcessResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool


def terminate_process_group(process: subprocess.Popen[str]) -> None:
    """Terminate an active supervised process group without PID-reuse races."""

    if process.poll() is not None:
        return
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=0.2)
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=0.2)
        except subprocess.TimeoutExpired:
            pass
        return

    taskkill = shutil.which("taskkill")
    if taskkill:
        subprocess.run(
            [taskkill, "/PID", str(process.pid), "/T", "/F"],
            text=True,
            capture_output=True,
            check=False,
        )
    elif process.poll() is None:  # pragma: no cover - Windows fallback
        process.kill()
        process.wait(timeout=1)


def run_supervised_process(
    argv: list[str],
    *,
    cwd: Path,
    timeout_seconds: int,
    env: Mapping[str, str],
    input_text: str | None = None,
) -> SupervisedProcessResult:
    """Run one argv command with timeout and descendant cleanup."""

    creationflags = (
        getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        if os.name == "nt"
        else 0
    )
    process = subprocess.Popen(
        argv,
        cwd=cwd,
        text=True,
        stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=dict(env),
        start_new_session=(os.name == "posix"),
        creationflags=creationflags,
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(
            input=input_text, timeout=timeout_seconds
        )
        returncode = int(process.returncode or 0)
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = (
            exc.stdout.decode("utf-8", errors="replace")
            if isinstance(exc.stdout, bytes)
            else (exc.stdout or "")
        )
        stderr = (
            exc.stderr.decode("utf-8", errors="replace")
            if isinstance(exc.stderr, bytes)
            else (exc.stderr or "")
        )
        terminate_process_group(process)
        returncode = 124
    return SupervisedProcessResult(
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
        timed_out=timed_out,
    )


@dataclass(frozen=True)
class GitSnapshot:
    head: str
    tree: str
    branch: str
    status: str
    ignored_state: tuple[tuple[str, str], ...]


def git(
    root: Path,
    *args: str,
    check: bool = True,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", *args],
        cwd=root,
        text=True,
        input=input_text,
        capture_output=True,
        check=False,
        env=safe_environment(),
    )
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RunnerSupportError(detail or f"git {' '.join(args)} failed")
    return result


def git_bytes(root: Path, *args: str) -> bytes:
    env = safe_environment()
    result = subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", *args],
        cwd=root,
        capture_output=True,
        check=False,
        env=env,
    )
    if result.returncode != 0:
        raise RunnerSupportError(
            result.stderr.decode(errors="replace").strip()
            or f"git {' '.join(args)} failed"
        )
    return result.stdout


def repository_root(root: Path) -> Path:
    resolved = root.resolve()
    if not resolved.is_dir():
        raise RunnerSupportError(f"repository root does not exist: {resolved}")
    top = Path(git(resolved, "rev-parse", "--show-toplevel").stdout.strip()).resolve()
    if top != resolved:
        raise RunnerSupportError(
            f"--root must be the Git repository top level: expected {top}"
        )
    return resolved


def ignored_worktree_state(root: Path) -> tuple[tuple[str, str], ...]:
    """Return a deterministic fingerprint of ignored, untracked worktree files."""

    payload = git_bytes(
        root,
        "ls-files",
        "--others",
        "--ignored",
        "--exclude-standard",
        "-z",
    )
    records: list[tuple[str, str]] = []
    for raw in payload.split(b"\0"):
        if not raw:
            continue
        relative = raw.decode("utf-8", errors="surrogateescape").replace("\\", "/")
        candidate = root / relative
        try:
            metadata = candidate.lstat()
        except FileNotFoundError:
            # A concurrent deletion is still represented deterministically.
            records.append((relative, "missing"))
            continue
        digest = hashlib.sha256()
        digest.update(f"{metadata.st_mode:o}:".encode("ascii"))
        if stat.S_ISLNK(metadata.st_mode):
            digest.update(os.readlink(candidate).encode("utf-8", errors="surrogateescape"))
        elif stat.S_ISREG(metadata.st_mode):
            with candidate.open("rb") as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(block)
        else:
            digest.update(f"size={metadata.st_size}".encode("ascii"))
        records.append((relative, digest.hexdigest()))
    return tuple(sorted(records))


def snapshot(root: Path) -> GitSnapshot:
    branch_result = git(root, "symbolic-ref", "--short", "-q", "HEAD", check=False)
    branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "DETACHED"
    return GitSnapshot(
        head=git(root, "rev-parse", "--verify", "HEAD").stdout.strip(),
        tree=git(root, "rev-parse", "--verify", "HEAD^{tree}").stdout.strip(),
        branch=branch,
        status=git(
            root,
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ).stdout,
        ignored_state=ignored_worktree_state(root),
    )


def output_outside_source(root: Path, output_root: Path) -> Path:
    output = output_root.resolve()
    try:
        output.relative_to(root)
    except ValueError:
        return output
    raise RunnerSupportError("runner output must be outside the source repository")


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    write_json(temporary, value)
    os.replace(temporary, path)


def add_worktree(root: Path, path: Path, commit: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    git(root, "worktree", "add", "--detach", str(path), commit)


def remove_worktree(root: Path, path: Path | None) -> None:
    if path is None:
        return
    git(root, "worktree", "remove", "--force", str(path), check=False)
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)


def prune_worktrees(root: Path) -> None:
    git(root, "worktree", "prune", check=False)


def temporary_worktree_root(run_id: str) -> Path:
    return Path(tempfile.mkdtemp(prefix=f"apl-runner-{run_id}-"))


def candidate_commit(
    worktree: Path,
    *,
    source_commit: str,
    task_id: str,
) -> str:
    ignored = ignored_worktree_state(worktree)
    if ignored:
        raise RunnerSupportError(
            "executor created ignored candidate files: "
            + ", ".join(path for path, _digest in ignored)
        )
    git(worktree, "add", "-A")
    unchanged = git(
        worktree,
        "diff",
        "--cached",
        "--quiet",
        "HEAD",
        "--",
        check=False,
    )
    if unchanged.returncode == 0:
        raise RunnerSupportError("executor produced no repository changes")
    if unchanged.returncode != 1:
        raise RunnerSupportError(
            unchanged.stderr.strip() or "cannot inspect staged candidate"
        )
    tree = git(worktree, "write-tree").stdout.strip()
    epoch = git(worktree, "show", "-s", "--format=%ct", source_commit).stdout.strip()
    env = safe_environment()
    env.update(
        {
            "GIT_AUTHOR_NAME": "Agentic Project Lifecycle",
            "GIT_AUTHOR_EMAIL": "apl-runner@invalid.local",
            "GIT_COMMITTER_NAME": "Agentic Project Lifecycle",
            "GIT_COMMITTER_EMAIL": "apl-runner@invalid.local",
            "GIT_AUTHOR_DATE": f"@{epoch} +0000",
            "GIT_COMMITTER_DATE": f"@{epoch} +0000",
        }
    )
    result = subprocess.run(
        [
            "git",
            "-c",
            "core.hooksPath=/dev/null",
            "commit-tree",
            tree,
            "-p",
            source_commit,
            "-m",
            f"APL candidate for {task_id}",
        ],
        cwd=worktree,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    commit = result.stdout.strip()
    if result.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise RunnerSupportError(
            result.stderr.strip() or "cannot create candidate commit"
        )
    return commit


def commit_patch(root: Path, base: str, head: str) -> bytes:
    return git_bytes(root, "diff", "--binary", "--full-index", base, head, "--")


def worktree_patch(worktree: Path) -> bytes:
    git(worktree, "add", "-A", check=False)
    return git_bytes(worktree, "diff", "--cached", "--binary", "--full-index", "HEAD", "--")


def safe_environment(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in os.environ.items():
        if _SENSITIVE_ENV_RE.search(key):
            continue
        result[key] = value
    result.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "core.hooksPath",
            "GIT_CONFIG_VALUE_0": "/dev/null",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        }
    )
    for key in (
        "SSH_AUTH_SOCK",
        "GIT_ASKPASS",
        "SSH_ASKPASS",
        *_AUTH_CONTEXT_ENV_KEYS,
    ):
        result.pop(key, None)
    if extra:
        for key, value in extra.items():
            normalized = str(key)
            if _SENSITIVE_ENV_RE.search(normalized):
                raise RunnerSupportError(
                    f"sensitive environment override is not permitted: {normalized}"
                )
            result[normalized] = str(value)
    return result



def pid_isolation_command(argv: list[str]) -> list[str]:
    """Keep Linux descendants inside a disposable PID namespace."""

    if platform.system() != "Linux":
        return list(argv)
    executable = shutil.which("unshare")
    if not executable:
        raise RunnerSupportError(
            "PID-isolated process execution is unavailable on this Linux host"
        )
    return [
        executable,
        "--pid",
        "--fork",
        "--kill-child=SIGKILL",
        "--map-root-user",
        "--",
        *argv,
    ]


def network_isolation_command(argv: list[str]) -> list[str]:
    """Wrap a verification command in a fail-closed OS network sandbox."""

    system = platform.system()
    if system == "Linux":
        executable = shutil.which("unshare")
        if executable:
            return [
                executable,
                "--net",
                "--pid",
                "--fork",
                "--kill-child=SIGKILL",
                "--map-root-user",
                "--",
                *argv,
            ]
    elif system == "Darwin":
        executable = shutil.which("sandbox-exec")
        if executable:
            profile = "(version 1)(allow default)(deny network*)"
            return [executable, "-p", profile, *argv]
    raise RunnerSupportError(
        "network-isolated verification is unavailable on this platform"
    )


def validate_command_argv(argv: list[str]) -> list[str]:
    if not argv or any(not isinstance(item, str) or not item for item in argv):
        raise RunnerSupportError("verification argv must be a non-empty string list")
    if Path(argv[0]).name.casefold() in _SHELL_INTERPRETERS:
        raise RunnerSupportError(
            f"shell interpreter is not permitted for verification: {argv[0]}"
        )
    return list(argv)


def parse_command(command: str) -> list[str]:
    if _SHELL_CONTROL_RE.search(command):
        raise RunnerSupportError(
            f"verification command contains shell control syntax: {command}"
        )
    try:
        argv = shlex.split(command, posix=True)
    except ValueError as exc:
        raise RunnerSupportError(f"cannot parse verification command: {exc}") from exc
    if not argv:
        raise RunnerSupportError("verification command is empty")
    return validate_command_argv(argv)


def verification_commands(task_contract: Mapping[str, Any]) -> list[str]:
    commands: list[str] = []
    plan = task_contract.get("plan")
    if not isinstance(plan, Mapping):
        return commands
    for step in plan.get("steps", []):
        if not isinstance(step, Mapping):
            continue
        for command in step.get("verification_commands", []):
            if isinstance(command, str) and command not in commands:
                commands.append(command)
    return commands


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_verification_commands(
    *,
    workspace: Path,
    task_contract: Mapping[str, Any],
    run_dir: Path,
    timeout_seconds: int,
) -> list[dict[str, Any]]:
    identity = snapshot(workspace)
    initial_ignored = dict(identity.ignored_state)
    records: list[dict[str, Any]] = []
    commands = verification_commands(task_contract)
    if not commands:
        raise RunnerSupportError(
            "approved plan contains no deterministic verification commands"
        )
    for index, command in enumerate(commands, start=1):
        requested_argv = parse_command(command)
        sandbox_argv = network_isolation_command(requested_argv)
        isolated_home = run_dir / ".verification-home"
        isolated_home.mkdir(mode=0o700, parents=True, exist_ok=True)
        command_env = safe_environment(
            {
                "HOME": str(isolated_home),
                "XDG_CONFIG_HOME": str(isolated_home / ".config"),
                "XDG_CACHE_HOME": str(isolated_home / ".cache"),
                "XDG_DATA_HOME": str(isolated_home / ".local" / "share"),
                "GIT_CONFIG_GLOBAL": os.devnull,
                "PIP_CONFIG_FILE": os.devnull,
                "NPM_CONFIG_USERCONFIG": os.devnull,
                "PYTEST_ADDOPTS": "-p no:cacheprovider",
                "COVERAGE_FILE": str(run_dir / ".coverage"),
                "MYPY_CACHE_DIR": str(run_dir / ".mypy_cache"),
                "RUFF_CACHE_DIR": str(run_dir / ".ruff_cache"),
            }
        )
        started = time.monotonic()
        completed = run_supervised_process(
            sandbox_argv,
            cwd=workspace,
            timeout_seconds=timeout_seconds,
            env=command_env,
        )
        exit_code = completed.returncode
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        timed_out = completed.timed_out
        if timed_out:
            stderr += f"\nverification timed out after {timeout_seconds} seconds\n"
        duration_ms = round((time.monotonic() - started) * 1000)
        from .run_manifest import redact_text
        stdout = redact_text(stdout)
        stderr = redact_text(stderr)
        stdout_path = run_dir / f"verification-{index:03d}.stdout.log"
        stderr_path = run_dir / f"verification-{index:03d}.stderr.log"
        stdout_path.write_text(stdout, encoding="utf-8")
        stderr_path.write_text(stderr, encoding="utf-8")
        records.append(
            {
                "command": command,
                "requested_argv": requested_argv,
                "argv": requested_argv,
                "sandbox_argv": sandbox_argv,
                "network_isolation": "os-enforced",
                "exit_code": exit_code,
                "duration_ms": duration_ms,
                "timed_out": timed_out,
                "stdout": {
                    "path": stdout_path.name,
                    "sha256": sha256_file(stdout_path),
                    "size_bytes": stdout_path.stat().st_size,
                },
                "stderr": {
                    "path": stderr_path.name,
                    "sha256": sha256_file(stderr_path),
                    "size_bytes": stderr_path.stat().st_size,
                },
            }
        )
        current = snapshot(workspace)
        current_ignored = dict(current.ignored_state)
        created_ignored = sorted(set(current_ignored) - set(initial_ignored))
        changed_ignored = sorted(
            path
            for path in set(current_ignored).intersection(initial_ignored)
            if current_ignored[path] != initial_ignored[path]
        )
        removed_ignored = sorted(set(initial_ignored) - set(current_ignored))
        if created_ignored:
            raise RunnerSupportError(
                "verification command created ignored candidate files: "
                + ", ".join(created_ignored)
            )
        if changed_ignored or removed_ignored:
            raise RunnerSupportError(
                "verification command changed ignored candidate files: "
                + ", ".join(changed_ignored + removed_ignored)
            )
        if (
            current.head != identity.head
            or current.tree != identity.tree
            or current.branch != identity.branch
        ):
            raise RunnerSupportError(
                "verification command changed candidate HEAD, tree, or branch"
            )
        tracked = git(workspace, "diff", "--quiet", "HEAD", "--", check=False)
        staged = git(workspace, "diff", "--cached", "--quiet", "HEAD", "--", check=False)
        if tracked.returncode != 0 or staged.returncode != 0:
            raise RunnerSupportError(
                "verification command changed tracked candidate files"
            )
        if exit_code != 0:
            raise RunnerSupportError(
                f"verification command failed with exit code {exit_code}: {command}"
            )
    return records
