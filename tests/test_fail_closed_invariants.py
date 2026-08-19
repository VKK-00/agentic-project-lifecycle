from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "plugins/agentic-project-lifecycle/skills/auditing-project-readiness/scripts"
sys.path.insert(0, str(SCRIPTS))

from governance_contracts import validate_gate_transition  # noqa: E402

COMMIT = "a" * 40
COLLECTOR = SCRIPTS / "collect_verification.py"
RELEASE_CHECKER = SCRIPTS / "check_release_readiness.py"
STATE_VALIDATOR = SCRIPTS / "validate_project_state.py"


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=False)


def init_repo(root: Path) -> str:
    root.mkdir(parents=True)
    assert git(root, "init", "-q").returncode == 0
    git(root, "config", "user.name", "Test User")
    git(root, "config", "user.email", "test@example.com")
    (root / "README.md").write_text("fixture\n", encoding="utf-8")
    git(root, "add", ".")
    assert git(root, "commit", "-qm", "initial").returncode == 0
    return git(root, "rev-parse", "HEAD").stdout.strip()


def transition(kind: str, phase_from: str, phase_to: str, *, allow_skip: bool = True) -> dict:
    return {
        "schema_version": "1.0",
        "transition": {
            "id": "GATE-1",
            "project_id": "PROJECT-1",
            "type": kind,
            "from": phase_from,
            "to": phase_to,
            "requested_at": "2026-08-18T00:00:00Z",
            "source_commit": COMMIT,
        },
        "outcome": {"id": "OUT-1", "statement": "Bounded outcome", "owner": "alice"},
        "conditions": [],
        "evidence": [],
        "approvals": [
            {
                "role": "lifecycle-owner",
                "required": True,
                "decision": "approved",
                "actor": "alice",
                "decided_at": "2026-08-18T00:01:00Z",
                "source_commit": COMMIT,
            }
        ],
        "blockers": [],
        "residual_risks": [],
        "policy": {"hard_blocker_behavior": "stop-dependent-work", "allow_phase_skip": allow_skip},
        "decision": {
            "status": "approved",
            "decided_by": "alice",
            "decided_at": "2026-08-18T00:02:00Z",
            "rationale": "Reviewed",
        },
    }


def test_advance_cannot_move_backwards_even_with_skip_approval() -> None:
    errors = validate_gate_transition(transition("advance", "implementation", "planning"))
    assert "advance transition must move to a later phase" in errors


def test_advance_cannot_hold_same_phase() -> None:
    errors = validate_gate_transition(transition("advance", "planning", "planning"))
    assert "advance transition must move to a later phase" in errors


def test_hold_must_keep_same_phase() -> None:
    errors = validate_gate_transition(transition("hold", "planning", "implementation"))
    assert "hold transition must remain in the current phase" in errors


def test_waive_must_keep_same_phase() -> None:
    errors = validate_gate_transition(transition("waive", "planning", "implementation"))
    assert "waive transition must remain in the current phase" in errors


def strict_state(commit: str) -> dict:
    return {
        "schema_version": "2.0",
        "project": {"id": "P1", "name": "P", "type": "software", "mode": "brownfield", "owner": "alice"},
        "lifecycle": {"current_phase": "implementation", "status": "in-progress", "gate_id": "G1", "source_commit": commit},
        "current_outcome": {"id": "O1", "statement": "Ship", "metric": "checks", "target": "pass", "owner": "alice"},
        "blockers": [],
        "residual_risks": [],
        "artifacts": {
            name: {
                "status": "approved",
                "path": path,
                "owner": "alice",
                "source_commit": commit,
                "approval": {"status": "approved", "approved_by": "alice", "approved_at": "2026-08-18T00:00:00Z", "source_commit": commit},
            }
            for name, path in {
                "charter": "docs/charter.md",
                "prd": "docs/prd.md",
                "design": "docs/design.md",
                "plan": "docs/missing-plan.md",
            }.items()
        },
        "contracts": {"active_task": None, "active_transition": None},
    }


def test_strict_cli_resolves_git_root_and_checks_linked_paths(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    commit = init_repo(root)
    docs = root / "docs"
    docs.mkdir()
    for name in ("charter.md", "prd.md", "design.md"):
        (docs / name).write_text(name, encoding="utf-8")
    state = docs / "project-state.yaml"
    state.write_text(yaml.safe_dump(strict_state(commit), sort_keys=False), encoding="utf-8")
    result = subprocess.run([sys.executable, str(STATE_VALIDATOR), str(state), "--strict"], cwd=root, text=True, capture_output=True, check=False)
    assert result.returncode == 1
    assert "artifacts.plan.path does not exist" in result.stdout


def write_config(root: Path, commands: list[dict]) -> Path:
    path = root / "verification.yaml"
    path.write_text(yaml.safe_dump({"commands": commands}, sort_keys=False), encoding="utf-8")
    git(root, "add", "verification.yaml")
    assert git(root, "commit", "-qm", "verification config").returncode == 0
    return path


def run_collector(root: Path, config: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(COLLECTOR), "--root", str(root), "--config", str(config), "--output", str(root / "evidence/latest")],
        text=True,
        capture_output=True,
        check=False,
    )


def test_collector_rejects_clean_head_change(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    init_repo(root)
    script = "from pathlib import Path; import subprocess; Path('generated.txt').write_text('x'); subprocess.run(['git','add','.']); subprocess.run(['git','commit','-qm','generated'])"
    config = write_config(root, [{"name": "mutating", "run": [sys.executable, "-c", script]}])
    result = run_collector(root, config)
    assert result.returncode == 1
    assert "repository identity changed during verification" in result.stderr


def test_collector_rejects_branch_change(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    init_repo(root)
    config = write_config(root, [{"name": "branch", "run": ["git", "checkout", "-b", "verification-mutated"]}])
    result = run_collector(root, config)
    assert result.returncode == 1
    assert "repository identity changed during verification" in result.stderr


def test_colliding_command_names_get_unique_artifacts(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    init_repo(root)
    config = write_config(
        root,
        [
            {"name": "Unit Tests", "run": [sys.executable, "-c", "print('one')"]},
            {"name": "unit-tests", "run": [sys.executable, "-c", "print('two')"]},
        ],
    )
    result = run_collector(root, config)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads((root / "evidence/latest/report.json").read_text(encoding="utf-8"))
    logs = [record["artifacts"][0]["path"] for record in report["evidence"]]
    assert len(logs) == len(set(logs)) == 2


def test_release_checker_rejects_unsafe_release_identifier(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    init_repo(root)
    result = subprocess.run(
        [sys.executable, str(RELEASE_CHECKER), "--root", str(root), "--release", "../../escape"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1
    assert "release identifier is invalid" in result.stdout
