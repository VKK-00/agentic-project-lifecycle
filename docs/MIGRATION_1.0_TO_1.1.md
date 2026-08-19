# Migration from 1.0 to 1.1

Version `1.1.0-rc.1` preserves the seven existing skills and legacy validator entry points while adding enforceable governance contracts.

## Compatible behavior

- Existing skill names and `RULE-*` identifiers remain unchanged.
- Legacy project-state documents still validate when `--strict` is not used.
- Existing `validate_task_contract.py`, `validate_gate_transition.py`, `validate_evidence.py`, and `validate_project_state.py` paths remain available.

## New behavior

- Consequential work can bind to a versioned policy profile.
- `ExecutionResult` validates the actual Git diff against the approved TaskContract.
- Validators support stable diagnostic codes, JSON, and SARIF.
- The unified `apl` CLI is the recommended interface.
- Strict state validation resolves and verifies the Git repository root.
- Stable `1.1.0` promotion requires completed live multi-run behavioral evaluation; static and fixture evidence alone is insufficient.

## Recommended migration

1. Keep existing state documents in compatible mode while adopting the v2 scaffold.
2. Select a policy profile and record its ID, version, and SHA-256 digest.
3. Generate an ExecutionResult for every write-capable task.
4. Run `apl audit` before approving a lifecycle transition.
5. Update CI to build `1.1.0-rc.1` artifacts and treat the promotion report as evidence, not an automatic stable declaration.
