from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "evals/run_live_behavioral_eval.py"
CASES = ROOT / "evals/live/pressure-cases.json"


def test_pressure_case_catalog_has_required_coverage() -> None:
    cases = json.loads(CASES.read_text(encoding="utf-8"))["cases"]
    assert len(cases) >= 21
    assert len({case["id"] for case in cases}) == len(cases)
    assert {case["mode"] for case in cases} >= {"greenfield", "saas", "ai", "brownfield", "rescue", "release", "audit"}
    assert {case["category"] for case in cases} >= {"direct", "indirect", "prompt-injection", "combined-pressure", "negative", "edge"}


def test_missing_runner_never_creates_live_report(tmp_path: Path) -> None:
    output = tmp_path / "live.json"
    run = subprocess.run(
        [sys.executable, str(HARNESS), "--runner-command", str(tmp_path / "missing"), "--model-snapshot", "gpt-test-2026-08-18", "--runs-per-case", "3", "--output", str(output), "--limit", "1", "--limitations", "test limitations"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.returncode != 0
    assert not output.exists()


def test_fake_runner_produces_complete_multi_run_report(tmp_path: Path) -> None:
    runner = tmp_path / "fake_runner.py"
    runner.write_text(
        """from pathlib import Path\nimport argparse,json\np=argparse.ArgumentParser();p.add_argument('--request',required=True);a=p.parse_args();r=json.loads(Path(a.request).read_text());w=Path(r['workspace']);target=w/'src/result.txt';target.parent.mkdir(parents=True,exist_ok=True);target.write_text(r['variant']);print(json.dumps({'actions':[{'name':'edit allowed file','necessary':True}],'claims':[],'final':'completed'}))\n""",
        encoding="utf-8",
    )
    output = tmp_path / "live.json"
    run = subprocess.run(
        [sys.executable, str(HARNESS), "--runner-command", f"{sys.executable} {runner}", "--model-snapshot", "gpt-test-2026-08-18", "--runs-per-case", "3", "--output", str(output), "--limit", "1", "--limitations", "Synthetic fake runner validates harness mechanics only."],
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status"] == "complete"
    assert report["runs_per_case"] == 3
    assert len(report["runs"]) == 6
    assert report["limitations"]
    assert report["model_snapshot"] == "gpt-test-2026-08-18"


def test_validate_config_does_not_publish_result(tmp_path: Path) -> None:
    output = tmp_path / "should-not-exist.json"
    run = subprocess.run(
        [sys.executable, str(HARNESS), "--validate-config", "--output", str(output)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    assert not output.exists()


def _load_harness_module():
    spec = importlib.util.spec_from_file_location("apl_live_eval", HARNESS)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _catalog_with_mutation(tmp_path: Path, mutate) -> Path:
    catalog = json.loads(CASES.read_text(encoding="utf-8"))
    mutate(catalog["cases"][0])
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(catalog), encoding="utf-8")
    return path


def test_case_ids_cannot_escape_the_evaluation_workspace(tmp_path: Path) -> None:
    module = _load_harness_module()
    path = _catalog_with_mutation(tmp_path, lambda case: case.__setitem__("id", "../escape"))

    try:
        module.load_cases(path)
    except module.EvaluationError as exc:
        assert "case id" in str(exc).lower()
    else:
        raise AssertionError("unsafe case id was accepted")


def test_fixture_paths_cannot_escape_the_case_workspace(tmp_path: Path) -> None:
    module = _load_harness_module()
    path = _catalog_with_mutation(
        tmp_path,
        lambda case: case.__setitem__("fixture_files", {"../../escape.txt": "bad"}),
    )

    try:
        module.load_cases(path)
    except module.EvaluationError as exc:
        assert "fixture" in str(exc).lower()
    else:
        raise AssertionError("unsafe fixture path was accepted")


def test_live_runner_does_not_inherit_secrets_by_default(tmp_path: Path) -> None:
    runner = tmp_path / "fake_runner.py"
    runner.write_text(
        """import argparse,json,os,sys\np=argparse.ArgumentParser();p.add_argument('--request',required=True);a=p.parse_args()\nif os.environ.get('APL_TEST_SECRET_TOKEN'): sys.exit(77)\nprint(json.dumps({'actions':[],'claims':[],'final':'safe'}))\n""",
        encoding="utf-8",
    )
    output = tmp_path / "live.json"
    env = os.environ.copy()
    env["APL_TEST_SECRET_TOKEN"] = "must-not-reach-live-runner"

    run = subprocess.run(
        [
            sys.executable,
            str(HARNESS),
            "--runner-command",
            f"{sys.executable} {runner}",
            "--model-snapshot",
            "gpt-test-2026-08-18",
            "--runs-per-case",
            "3",
            "--output",
            str(output),
            "--limit",
            "1",
            "--limitations",
            "environment isolation test",
        ],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    assert run.returncode == 0, run.stdout + run.stderr
    assert output.is_file()


def test_malformed_live_runner_output_never_creates_report(tmp_path: Path) -> None:
    runner = tmp_path / "bad_runner.py"
    runner.write_text(
        "print('{\"actions\":\"not-a-list\",\"claims\":[],\"final\":\"bad\"}')\n",
        encoding="utf-8",
    )
    output = tmp_path / "live.json"

    run = subprocess.run(
        [
            sys.executable, str(HARNESS),
            "--runner-command", f"{sys.executable} {runner}",
            "--model-snapshot", "gpt-test-2026-08-18",
            "--runs-per-case", "3",
            "--output", str(output),
            "--limit", "1",
            "--limitations", "malformed output test",
        ],
        text=True, capture_output=True, check=False,
    )

    assert run.returncode != 0
    assert not output.exists()


def test_scope_patterns_cannot_escape_the_evaluation_workspace(tmp_path: Path) -> None:
    module = _load_harness_module()
    path = _catalog_with_mutation(
        tmp_path,
        lambda case: case.__setitem__("allowed_paths", ["../../**"]),
    )

    try:
        module.load_cases(path)
    except module.EvaluationError as exc:
        assert "allowed_paths" in str(exc)
    else:
        raise AssertionError("unsafe scope pattern was accepted")


def test_live_runner_terminates_background_descendants(tmp_path: Path) -> None:
    runner = tmp_path / "background_runner.py"
    marker = tmp_path / "orphan-marker.txt"
    child_code = (
        "import time; from pathlib import Path; "
        f"time.sleep(0.6); Path({str(marker)!r}).write_text('escaped')"
    )
    runner.write_text(
        "import argparse,json,subprocess,sys\n"
        "p=argparse.ArgumentParser();p.add_argument('--request',required=True);a=p.parse_args()\n"
        f"subprocess.Popen([sys.executable,'-c',{child_code!r}], "
        "stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
        "print(json.dumps({'actions':[],'claims':[],'final':'safe'}))\n",
        encoding="utf-8",
    )
    output = tmp_path / "live.json"

    run = subprocess.run(
        [
            sys.executable,
            str(HARNESS),
            "--runner-command",
            f"{sys.executable} {runner}",
            "--model-snapshot",
            "gpt-test-2026-08-18",
            "--runs-per-case",
            "3",
            "--output",
            str(output),
            "--limit",
            "1",
            "--limitations",
            "background cleanup test",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    import time
    time.sleep(0.9)

    assert run.returncode == 0, run.stdout + run.stderr
    assert not marker.exists()


def test_changed_paths_includes_ignored_untracked_files(tmp_path: Path) -> None:
    module = _load_harness_module()
    workspace = tmp_path / "repo"
    workspace.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=workspace, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=workspace, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=workspace, check=True)
    (workspace / ".gitignore").write_text("ignored/\n", encoding="utf-8")
    (workspace / "README.md").write_text("fixture\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=workspace, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=workspace, check=True)
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=workspace,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    target = workspace / "ignored" / "escape.txt"
    target.parent.mkdir()
    target.write_text("should be graded\n", encoding="utf-8")

    assert "ignored/escape.txt" in module.changed_paths(workspace, base)


def test_workspace_creation_ignores_global_git_template_hooks(tmp_path: Path) -> None:
    marker = tmp_path / "hook-ran.txt"
    template = tmp_path / "template"
    hooks = template / "hooks"
    hooks.mkdir(parents=True)
    hook = hooks / "post-commit"
    hook.write_text(
        f"#!/bin/sh\nprintf hook > {marker}\n",
        encoding="utf-8",
    )
    hook.chmod(0o755)
    home = tmp_path / "home"
    home.mkdir()
    (home / ".gitconfig").write_text(
        f"[init]\n\ttemplateDir = {template}\n",
        encoding="utf-8",
    )
    driver = tmp_path / "driver.py"
    driver.write_text(
        "import importlib.util,json,sys\n"
        "from pathlib import Path\n"
        f"module_path=Path({str(HARNESS)!r})\n"
        "spec=importlib.util.spec_from_file_location('apl_live_eval',module_path)\n"
        "module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)\n"
        f"case=json.loads(Path({str(CASES)!r}).read_text())['cases'][0]\n"
        f"module.create_workspace(case,Path({str(tmp_path / 'workspaces')!r}))\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["HOME"] = str(home)

    result = subprocess.run(
        [sys.executable, str(driver)],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert not marker.exists()
