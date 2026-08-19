from __future__ import annotations

from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def test_mutation_testing_is_scoped_to_contract_core() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    mutmut = config["tool"]["mutmut"]
    assert mutmut["source_paths"]
    assert any("governance" in item for item in mutmut["source_paths"])
    assert mutmut["pytest_add_cli_args_test_selection"]
    assert any("test_governance" in item for item in mutmut["pytest_add_cli_args_test_selection"])
    assert mutmut["mutate_only_covered_lines"] is True


def test_mutation_contract_documents_required_threshold_and_command() -> None:
    text = (ROOT / "docs/MUTATION_TESTING.md").read_text(encoding="utf-8")
    assert "mutmut run" in text
    assert "90%" in text
    assert "surviving mutant" in text.lower()
    assert "not a substitute" in text.lower()
