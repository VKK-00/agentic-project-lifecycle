# Audit contract

A validator pass proves only the assertions that validator checked against the supplied inputs. Report the audit scope, source commit, artifact versions, commands, exit codes, durations, environment, limitations, blockers, owners, and required corrections. Never infer production readiness from document presence, an agent statement, or stale evidence.

Run the applicable contract validators before interpreting project state or readiness:

```text
python scripts/validate_task_contract.py <task-contract.yaml>
python scripts/validate_gate_transition.py <gate-transition.yaml>
python scripts/validate_evidence.py <evidence.yaml> --expected-commit <full-sha>
python scripts/validate_project_state.py <project-state.yaml> --strict --root <repository>
```

Observed evidence must include the full source commit, timezone-aware collection and expiry timestamps, command arguments, integer exit code, duration, environment, result, artifact path, artifact digest, and freshness policy. The release checker additionally verifies that referenced artifacts still exist with the recorded digest and size and that no non-evidence source changes occurred after collection.

A readiness result is always scoped to a target stage, repository state, environment, and evidence cutoff. Missing proof remains a visible gap. Open hard blockers stop dependent work; open soft blockers require an owned residual-risk record and explicit policy treatment.
