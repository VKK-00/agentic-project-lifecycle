# Governance Contract Enforcement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make lifecycle gates, bounded execution plans, evidence freshness, and project state mechanically enforceable inside the existing skills-only plugin.

**Architecture:** Add a pure Python validation module shared by thin CLI wrappers, preserve legacy state compatibility while scaffolding strict v2 state, and keep all enforcement local and deterministic. Machine-readable YAML descriptors document the contracts; no runtime or new dependency is introduced.

**Tech Stack:** Python 3.11+, PyYAML 6.x, pytest 8/9, Markdown and YAML plugin assets.

## Global Constraints

- Do not add a model runtime, deployment integration, network call, or hosted component.
- Do not add a production dependency beyond existing `PyYAML>=6.0,<7`.
- Preserve legacy project-state validation unless strict mode is requested.
- Reject absolute paths, traversal, and repository-escaping linked artifacts.
- Never accept an agent statement as verification evidence without observed command fields.
- Keep scaffold writes preflighted and non-overwriting by default.

---

### Task 1: Core task, gate, and evidence validators

**Files:**
- Create: `tests/test_governance_contracts.py`
- Create: `plugins/agentic-project-lifecycle/skills/auditing-project-readiness/scripts/governance_contracts.py`

**Interfaces:**
- Produces: `validate_task_contract(data: object) -> list[str]`
- Produces: `validate_gate_transition(data: object) -> list[str]`
- Produces: `validate_evidence_record(data: object, *, expected_commit: str | None = None, now: datetime | None = None) -> list[str]`

- [ ] **Step 1: Write failing tests for valid and invalid task contracts**

```python
def test_task_contract_requires_approved_plan_for_write():
    contract = valid_task_contract()
    contract["plan"]["status"] = "draft"
    assert "writable task requires an approved plan" in validate_task_contract(contract)


def test_task_contract_rejects_path_traversal():
    contract = valid_task_contract()
    contract["scope"]["allowed_paths"] = ["../outside/**"]
    assert any("repository-relative" in item for item in validate_task_contract(contract))
```

- [ ] **Step 2: Write failing tests for hard blockers and gate skips**

```python
def test_approved_gate_cannot_have_open_hard_blocker():
    transition = valid_gate_transition()
    transition["blockers"] = [{"id": "BLK-1", "class": "hard", "status": "open", "owner": "alice", "reason": "unsafe"}]
    assert "approved transition has an open hard blocker BLK-1" in validate_gate_transition(transition)
```

- [ ] **Step 3: Write failing tests for evidence commit binding and freshness**

```python
def test_evidence_must_match_expected_commit():
    evidence = valid_evidence_record()
    assert "evidence source commit does not match expected commit" in validate_evidence_record(
        evidence, expected_commit="b" * 40
    )
```

- [ ] **Step 4: Run targeted tests and verify RED**

Run: `python -m pytest tests/test_governance_contracts.py -q`

Expected: collection failure because `governance_contracts.py` does not exist.

- [ ] **Step 5: Implement minimal pure validation helpers**

```python
def validate_task_contract(data: object) -> list[str]: ...
def validate_gate_transition(data: object) -> list[str]: ...
def validate_evidence_record(data: object, *, expected_commit: str | None = None, now: datetime | None = None) -> list[str]: ...
```

Implementation must validate schema versions, enums, repository-relative paths, approvals, plan/permission coupling, blockers, waivers, condition status, commit IDs, timestamps, exit-code/result consistency, artifact digests, and expiration.

- [ ] **Step 6: Run targeted tests and verify GREEN**

Run: `python -m pytest tests/test_governance_contracts.py -q`

Expected: all Task 1 tests pass.

- [ ] **Step 7: Commit**

```bash
git add tests/test_governance_contracts.py plugins/agentic-project-lifecycle/skills/auditing-project-readiness/scripts/governance_contracts.py
git commit -m "feat: add governance contract validators"
```

### Task 2: CLI wrappers and strict project-state v2

**Files:**
- Create: `plugins/agentic-project-lifecycle/skills/auditing-project-readiness/scripts/validate_task_contract.py`
- Create: `plugins/agentic-project-lifecycle/skills/auditing-project-readiness/scripts/validate_gate_transition.py`
- Create: `plugins/agentic-project-lifecycle/skills/auditing-project-readiness/scripts/validate_evidence.py`
- Modify: `plugins/agentic-project-lifecycle/skills/auditing-project-readiness/scripts/validate_project_state.py`
- Modify: `tests/test_governance_contracts.py`

**Interfaces:**
- Produces: each CLI accepts a YAML path and returns 0 for pass, 1 for validation failure.
- Produces: `validate(path: Path, *, strict: bool = False, root: Path | None = None) -> list[str]` in `validate_project_state.py`.

- [ ] **Step 1: Add failing project-state tests**

```python
def test_strict_project_state_rejects_legacy_state(tmp_path): ...
def test_v2_project_state_rejects_ready_with_hard_blocker(tmp_path): ...
def test_v2_project_state_validates_linked_task_contract(tmp_path): ...
```

- [ ] **Step 2: Add failing CLI exit-code tests**

Use `subprocess.run` against each wrapper and assert stable `TASK CONTRACT: PASS`, `GATE TRANSITION: FAIL`, and `EVIDENCE: PASS` prefixes.

- [ ] **Step 3: Run tests and verify RED**

Run: `python -m pytest tests/test_governance_contracts.py -q`

Expected: failures for missing wrappers and strict state behavior.

- [ ] **Step 4: Implement thin wrappers and v2 validation**

The project-state validator must retain the legacy checks when strict mode is false, reject legacy state in strict mode, and validate structured artifact records and linked contracts for v2.

- [ ] **Step 5: Run tests and verify GREEN**

Run: `python -m pytest tests/test_governance_contracts.py -q`

Expected: all Task 1-2 tests pass.

- [ ] **Step 6: Commit**

```bash
git add tests/test_governance_contracts.py plugins/agentic-project-lifecycle/skills/auditing-project-readiness/scripts
git commit -m "feat: enforce strict project state and contract CLIs"
```

### Task 3: Source-bound verification evidence and release readiness

**Files:**
- Modify: `plugins/agentic-project-lifecycle/skills/auditing-project-readiness/scripts/collect_verification.py`
- Modify: `plugins/agentic-project-lifecycle/skills/auditing-project-readiness/scripts/check_release_readiness.py`
- Modify: `tests/test_governance_contracts.py`

**Interfaces:**
- `collect_verification.py` keeps `checks` and `summary`, and adds `schema_version`, `evidence`, `environment`, and artifact digests.
- `check_release_readiness.py` accepts the enriched report and rejects failed, stale, malformed, or commit-mismatched evidence.

- [ ] **Step 1: Write failing collector tests**

Assert that a successful command produces a 40-character source commit in a Git repository, timezone-aware timestamps, SHA-256 log artifacts, and consistent pass status.

- [ ] **Step 2: Write failing readiness tests**

Assert readiness fails when evidence is expired or bound to another commit and passes for fresh matching evidence.

- [ ] **Step 3: Run tests and verify RED**

Run: `python -m pytest tests/test_governance_contracts.py -q`

- [ ] **Step 4: Implement enrichment and readiness validation**

Use only the standard library plus PyYAML. Preserve old report keys for compatibility.

- [ ] **Step 5: Run tests and verify GREEN**

Run: `python -m pytest tests/test_governance_contracts.py -q`

- [ ] **Step 6: Commit**

```bash
git add tests/test_governance_contracts.py plugins/agentic-project-lifecycle/skills/auditing-project-readiness/scripts/collect_verification.py plugins/agentic-project-lifecycle/skills/auditing-project-readiness/scripts/check_release_readiness.py
git commit -m "feat: bind verification evidence to source state"
```

### Task 4: Scaffold internally valid governance artifacts

**Files:**
- Modify: `plugins/agentic-project-lifecycle/skills/orchestrating-large-projects/scripts/scaffold_project.py`
- Modify: `plugins/agentic-project-lifecycle/skills/orchestrating-large-projects/assets/templates/project-state.yaml`
- Create: `plugins/agentic-project-lifecycle/skills/orchestrating-large-projects/assets/templates/task-contract.yaml`
- Create: `plugins/agentic-project-lifecycle/skills/orchestrating-large-projects/assets/templates/release-plan.yaml`
- Modify: `tests/test_governance_contracts.py`

**Interfaces:**
- `init` creates project-state v2 that passes strict validation.
- `feature` additionally creates `task-contract.yaml`.
- `release` creates both canonical `<version>.yaml` and operator-facing `<version>.md`.

- [ ] **Step 1: Write failing scaffold consistency tests**

Run `scaffold_project.py init`, `feature`, and `release` in a temporary Git repository and validate the generated YAML with the new validators.

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_governance_contracts.py -q`

Expected: current project-state shape fails strict validation and release YAML is absent.

- [ ] **Step 3: Implement templates and scaffold write sets**

Add any required template values (`PROJECT_ID`, `SOURCE_COMMIT`, `FEATURE_ID`) deterministically; use `uncommitted` only for initial scaffold state and document that release readiness requires replacement by a commit SHA.

- [ ] **Step 4: Run tests and verify GREEN**

Run: `python -m pytest tests/test_governance_contracts.py -q`

- [ ] **Step 5: Commit**

```bash
git add tests/test_governance_contracts.py plugins/agentic-project-lifecycle/skills/orchestrating-large-projects
git commit -m "feat: scaffold enforceable governance contracts"
```

### Task 5: Normative documentation and skill routing

**Files:**
- Create: `plugins/agentic-project-lifecycle/skills/orchestrating-large-projects/references/governance-contracts.md`
- Create: `plugins/agentic-project-lifecycle/skills/orchestrating-large-projects/references/schemas/task-contract.schema.yaml`
- Create: `plugins/agentic-project-lifecycle/skills/orchestrating-large-projects/references/schemas/gate-transition.schema.yaml`
- Create: `plugins/agentic-project-lifecycle/skills/auditing-project-readiness/references/schemas/evidence-record.schema.yaml`
- Modify: `plugins/agentic-project-lifecycle/skills/orchestrating-large-projects/references/routing-and-gates.md`
- Modify: `plugins/agentic-project-lifecycle/skills/orchestrating-large-projects/references/artifact-model.md`
- Modify: `plugins/agentic-project-lifecycle/skills/auditing-project-readiness/references/audit-contract.md`
- Modify: `plugins/agentic-project-lifecycle/skills/orchestrating-large-projects/SKILL.md`
- Modify: `plugins/agentic-project-lifecycle/skills/auditing-project-readiness/SKILL.md`
- Modify: `tests/test_governance_contracts.py`

**Interfaces:**
- Schema descriptors parse as YAML and identify required fields and validator commands.
- Skills direct consequential work through contracts without adding new broad triggers.

- [ ] **Step 1: Add failing documentation-contract tests**

Assert all schema descriptors parse, reference the correct validator, and the two skills mention hard blockers, bounded permissions, source-bound evidence, and rollback.

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_governance_contracts.py -q`

- [ ] **Step 3: Write concise normative references and rules**

Keep normative details in references and only routing/enforcement imperatives in `SKILL.md` to avoid inflating trigger behavior.

- [ ] **Step 4: Run tests and verify GREEN**

Run: `python -m pytest tests/test_governance_contracts.py -q`

- [ ] **Step 5: Commit**

```bash
git add tests/test_governance_contracts.py plugins/agentic-project-lifecycle/skills
git commit -m "docs: define enforceable lifecycle contracts"
```

### Task 6: Full verification and packaging review

**Files:**
- Modify only files required by observed failures.

- [ ] **Step 1: Run targeted contract tests**

Run: `python -m pytest tests/test_governance_contracts.py -q`

Expected: PASS.

- [ ] **Step 2: Compile all plugin Python scripts**

Run: `python -m compileall -q plugins/agentic-project-lifecycle/skills`

Expected: exit code 0 and no output.

- [ ] **Step 3: Run all available repository checks**

Run in the complete GitHub repository/CI: `python validate.py`, `python -m pytest -q`, and `python scripts/validate_publication.py`.

Expected: all exit code 0. Any generated evaluation result changes must be inspected and committed only when caused by the retained rule text.

- [ ] **Step 4: Build deterministic archives twice**

Run `SOURCE_DATE_EPOCH=315532800 python scripts/build_release.py --version 1.0.0-rc.1 --output <dir>` twice and compare SHA-256 values.

Expected: identical archives and evidence files.

- [ ] **Step 5: Review diff and commit fixes**

```bash
git diff --check
git status --short
git commit -am "test: verify governance contract enforcement"
```

Create the final commit only if verification required tracked corrections.
