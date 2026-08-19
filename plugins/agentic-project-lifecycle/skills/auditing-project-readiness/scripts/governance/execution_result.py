"""Build and validate execution results from an observed Git diff."""

from __future__ import annotations

from collections.abc import Mapping
import fnmatch
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tomllib
from typing import Any

from governance_contracts import validate_task_contract

COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
DEPENDENCY_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+")
PROTECTED_PATTERNS = (
    ".github/**",
    "migrations/**",
    "auth/**",
    "secrets/**",
    "infra/**",
)


def contract_digest(contract: object) -> str:
    payload = json.dumps(contract, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise ValueError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result


def _resolve_commit(root: Path, value: str) -> str:
    result = _git(root, "rev-parse", "--verify", f"{value}^{{commit}}")
    commit = result.stdout.strip()
    if not COMMIT_RE.fullmatch(commit):
        raise ValueError(f"cannot resolve full Git commit: {value}")
    return commit


def _is_ancestor(root: Path, base: str, head: str) -> bool:
    result = _git(root, "merge-base", "--is-ancestor", base, head, check=False)
    if result.returncode not in {0, 1}:
        raise ValueError(result.stderr.strip() or "cannot validate execution lineage")
    return result.returncode == 0


def _matches(path: str, pattern: str) -> bool:
    normalized = pattern.replace("\\", "/").lstrip("./")
    candidate = path.replace("\\", "/").lstrip("./")
    if normalized.endswith("/**"):
        prefix = normalized[:-3].rstrip("/")
        return candidate == prefix or candidate.startswith(prefix + "/")
    return fnmatch.fnmatchcase(candidate, normalized) or PurePosixPath(candidate).match(normalized)


def _name_status(root: Path, base: str, head: str) -> list[dict[str, Any]]:
    raw = subprocess.run(
        ["git", "diff", "--name-status", "-z", base, head, "--"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if raw.returncode != 0:
        raise ValueError(raw.stderr.decode(errors="replace").strip() or "cannot inspect Git diff")
    tokens = raw.stdout.decode("utf-8", errors="surrogateescape").split("\0")
    if tokens and tokens[-1] == "":
        tokens.pop()
    records: list[dict[str, Any]] = []
    index = 0
    while index < len(tokens):
        status_token = tokens[index]
        index += 1
        status = status_token[:1]
        if status in {"R", "C"}:
            if index + 1 >= len(tokens):
                raise ValueError("malformed rename/copy record in Git diff")
            previous = tokens[index]
            path = tokens[index + 1]
            index += 2
        else:
            if index >= len(tokens):
                raise ValueError("malformed path record in Git diff")
            previous = None
            path = tokens[index]
            index += 1
        records.append(
            {
                "path": path.replace("\\", "/"),
                "status": {
                    "A": "added",
                    "D": "deleted",
                    "M": "modified",
                    "R": "renamed",
                    "C": "copied",
                    "T": "type-changed",
                    "U": "unmerged",
                }.get(status, "unknown"),
                **({"previous_path": previous.replace("\\", "/")} if previous else {}),
            }
        )
    return records


def _numstat(root: Path, base: str, head: str, path: str) -> tuple[int, int]:
    result = _git(root, "diff", "--numstat", base, head, "--", path)
    additions = deletions = 0
    for line in result.stdout.splitlines():
        fields = line.split("\t", 2)
        if len(fields) < 2:
            continue
        additions += int(fields[0]) if fields[0].isdigit() else 0
        deletions += int(fields[1]) if fields[1].isdigit() else 0
    return additions, deletions


def _mode(root: Path, commit: str, path: str) -> str | None:
    result = _git(root, "ls-tree", commit, "--", path)
    if not result.stdout.strip():
        return None
    return result.stdout.split(maxsplit=1)[0]


def _show(root: Path, commit: str, path: str) -> str | None:
    result = _git(root, "show", f"{commit}:{path}", check=False)
    return result.stdout if result.returncode == 0 else None


def _dependency_name(value: str) -> str | None:
    match = DEPENDENCY_NAME_RE.match(value.strip())
    return match.group(0).lower().replace("_", "-") if match else None


def _dependencies_from_content(path: str, content: str | None) -> set[str]:
    if content is None:
        return set()
    name = Path(path).name
    if name == "pyproject.toml":
        try:
            data = tomllib.loads(content)
        except tomllib.TOMLDecodeError:
            return set()
        project = data.get("project", {}) if isinstance(data, dict) else {}
        values: list[str] = []
        if isinstance(project, dict):
            values.extend(value for value in project.get("dependencies", []) if isinstance(value, str))
            optional = project.get("optional-dependencies", {})
            if isinstance(optional, dict):
                for group in optional.values():
                    if isinstance(group, list):
                        values.extend(value for value in group if isinstance(value, str))
        return {dep for value in values if (dep := _dependency_name(value))}
    if name == "package.json":
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return set()
        values: set[str] = set()
        if isinstance(data, dict):
            for section in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
                mapping = data.get(section, {})
                if isinstance(mapping, dict):
                    values.update(str(key).lower() for key in mapping)
        return values
    if name.startswith("requirements") and name.endswith(".txt"):
        values: set[str] = set()
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", "-")):
                continue
            if dep := _dependency_name(stripped):
                values.add(dep)
        return values
    return set()


def _new_dependencies(root: Path, base: str, head: str, paths: list[str]) -> list[str]:
    manifests = {
        path
        for path in paths
        if Path(path).name in {"pyproject.toml", "package.json"}
        or (Path(path).name.startswith("requirements") and path.endswith(".txt"))
    }
    before: set[str] = set()
    after: set[str] = set()
    for path in manifests:
        before.update(_dependencies_from_content(path, _show(root, base, path)))
        after.update(_dependencies_from_content(path, _show(root, head, path)))
    return sorted(after - before)


def build_execution_result(
    *, root: Path, contract: Mapping[str, Any], head_commit: str = "HEAD"
) -> dict[str, Any]:
    root = root.resolve()
    contract_errors = validate_task_contract(contract)
    if contract_errors:
        raise ValueError("invalid task contract: " + "; ".join(contract_errors))
    task = contract["task"]
    base = _resolve_commit(root, str(task["source_commit"]))
    head = _resolve_commit(root, head_commit)
    if not _is_ancestor(root, base, head):
        raise ValueError("head commit is not a descendant of task source commit")

    records = _name_status(root, base, head)
    step_ids = [str(step.get("id")) for step in contract.get("plan", {}).get("steps", []) if step.get("id")]
    for record in records:
        additions, deletions = _numstat(root, base, head, record["path"])
        old_mode = _mode(root, base, record.get("previous_path", record["path"]))
        new_mode = _mode(root, head, record["path"])
        record.update(
            {
                "additions": additions,
                "deletions": deletions,
                "old_mode": old_mode,
                "new_mode": new_mode,
                "plan_steps": step_ids,
            }
        )
    paths = [record["path"] for record in records]
    return {
        "schema_version": "1.0",
        "execution": {
            "id": f"EXEC-{str(task['id'])}-{head[:12]}",
            "task_id": task["id"],
            "base_commit": base,
            "head_commit": head,
            "task_contract_sha256": contract_digest(contract),
            **(
                {"policy_profile_sha256": contract["policy"]["profile_sha256"]}
                if isinstance(contract.get("policy"), Mapping)
                and isinstance(contract["policy"].get("profile_sha256"), str)
                else {}
            ),
            "status": "candidate",
        },
        "change_set": {
            "changed_files": records,
            "total_changed_files": len(records),
            "total_diff_lines": sum(record["additions"] + record["deletions"] for record in records),
            "new_dependencies": _new_dependencies(root, base, head, paths),
        },
        "result": {"status": "pending", "violations": []},
    }


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def validate_execution_result(
    data: object,
    *,
    contract: Mapping[str, Any],
    root: Path | None = None,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, Mapping):
        return ["execution result root must be a mapping"]
    contract_errors = validate_task_contract(contract)
    errors.extend(f"task contract: {error}" for error in contract_errors)
    execution = _mapping(data.get("execution"))
    change_set = _mapping(data.get("change_set"))
    task = _mapping(contract.get("task"))
    scope = _mapping(contract.get("scope"))
    permissions = _mapping(contract.get("permissions"))

    if data.get("schema_version") != "1.0":
        errors.append("execution result schema_version must be 1.0")
    if execution.get("task_id") != task.get("id"):
        errors.append("execution task id does not match approved contract")
    if execution.get("base_commit") != task.get("source_commit"):
        errors.append("execution base commit does not match task source commit")
    if execution.get("task_contract_sha256") != contract_digest(contract):
        errors.append("execution task contract digest does not match approved contract")

    changed = change_set.get("changed_files")
    if not isinstance(changed, list):
        errors.append("change_set.changed_files must be a list")
        changed = []
    allowed = [str(value) for value in scope.get("allowed_paths", []) if isinstance(value, str)]
    forbidden = [str(value) for value in scope.get("forbidden_paths", []) if isinstance(value, str)]
    allow_deletions = scope.get("allow_deletions") is True
    allow_mode_changes = scope.get("allow_mode_changes") is True
    observed_paths: list[str] = []
    for index, raw_record in enumerate(changed):
        if not isinstance(raw_record, Mapping):
            errors.append(f"change_set.changed_files[{index}] must be a mapping")
            continue
        path = raw_record.get("path")
        if not isinstance(path, str) or not path:
            errors.append(f"change_set.changed_files[{index}].path is required")
            continue
        observed_paths.append(path)
        if not any(_matches(path, pattern) for pattern in allowed):
            errors.append(f"changed path is outside allowed scope: {path}")
        if any(_matches(path, pattern) for pattern in forbidden):
            errors.append(f"changed path is forbidden by task contract: {path}")
        if raw_record.get("status") == "deleted" and not allow_deletions:
            errors.append(f"file deletion is not permitted: {path}")
        old_mode = raw_record.get("old_mode")
        new_mode = raw_record.get("new_mode")
        if old_mode and new_mode and old_mode != new_mode and not allow_mode_changes:
            errors.append(f"file mode change is not permitted: {path}")
        if new_mode == "160000" or old_mode == "160000":
            errors.append(f"gitlink or submodule change is not permitted: {path}")
        if any(_matches(path, pattern) for pattern in PROTECTED_PATTERNS):
            approval = _mapping(contract.get("approval"))
            if task.get("risk_level") not in {"high", "critical"} or approval.get("status") != "approved":
                errors.append(f"protected surface change lacks high-assurance approval: {path}")

    total_files = change_set.get("total_changed_files")
    if total_files != len(changed):
        errors.append("recorded changed-file total does not match changed_files")
    max_files = scope.get("max_changed_files")
    if isinstance(max_files, int) and not isinstance(max_files, bool) and len(changed) > max_files:
        errors.append(f"changed file budget exceeded: {len(changed)} > {max_files}")
    calculated_lines = sum(
        int(record.get("additions", 0)) + int(record.get("deletions", 0))
        for record in changed
        if isinstance(record, Mapping)
        and isinstance(record.get("additions", 0), int)
        and isinstance(record.get("deletions", 0), int)
    )
    if change_set.get("total_diff_lines") != calculated_lines:
        errors.append("recorded diff-line total does not match changed_files")
    max_lines = scope.get("max_diff_lines")
    if isinstance(max_lines, int) and not isinstance(max_lines, bool) and calculated_lines > max_lines:
        errors.append(f"diff line budget exceeded: {calculated_lines} > {max_lines}")

    new_dependencies = change_set.get("new_dependencies")
    if not isinstance(new_dependencies, list) or any(not isinstance(item, str) for item in new_dependencies):
        errors.append("change_set.new_dependencies must be a string list")
        new_dependencies = []
    max_dependencies = scope.get("max_new_dependencies")
    if isinstance(max_dependencies, int) and not isinstance(max_dependencies, bool) and len(new_dependencies) > max_dependencies:
        errors.append(f"new dependency budget exceeded: {len(new_dependencies)} > {max_dependencies}")
    if new_dependencies and permissions.get("dependency_changes") == "forbidden":
        errors.append("task contract forbids dependency changes")

    if root is not None and COMMIT_RE.fullmatch(str(execution.get("head_commit", ""))):
        try:
            observed = build_execution_result(
                root=root,
                contract=contract,
                head_commit=str(execution["head_commit"]),
            )
        except ValueError as exc:
            errors.append(str(exc))
        else:
            if observed["change_set"] != dict(change_set):
                errors.append("execution result does not match the observed Git diff")
    return errors
