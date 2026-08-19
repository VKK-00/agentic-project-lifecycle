from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_ci_audits_a_pinned_external_dependency_snapshot() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    assert "pip freeze --exclude-editable" in workflow
    assert 'audit-requirements.txt' in workflow
    assert "python -m pip_audit --strict --no-deps --requirement" in workflow
    assert "--skip-editable" not in workflow
