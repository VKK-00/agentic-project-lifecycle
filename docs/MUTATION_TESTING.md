# Mutation-testing contract

Mutation testing checks whether the governance tests detect small semantic defects rather than merely execute lines. It is an assurance layer for deterministic validators; it is **not a substitute** for example-based tests, property-based tests, adversarial fixtures, live behavioral evaluation, code review, or threat modeling.

## Scope

`mutmut` is restricted to the governance validator core. Generated files, CLI presentation code, evaluation fixtures, and release scripts are excluded unless a later risk assessment adds them deliberately. The selected pytest files exercise task, gate, evidence, project-state, execution-result, policy, audit, and event-chain invariants.

## Execution

Run from a clean committed worktree on Linux or WSL:

```bash
python -m pip install -e '.[dev]'
rm -rf mutants
mutmut run
mutmut browse
```

A clean full run is required after dependency, schema, policy-profile, or mutmut-configuration changes. Never accept cached results after a material input change without confirming that mutmut invalidated and reran the affected mutants.

## Acceptance rule

The release-candidate target is a mutation score of at least **90%** over decided mutants:

```text
killed / (killed + surviving) >= 0.90
```

Timeout, suspicious, and untested mutants are not counted as killed. Every surviving mutant in an approval, source-binding, path-containment, blocker, evidence-freshness, or actual-diff invariant requires either:

1. a new failing regression test that kills it; or
2. a documented equivalent-mutant decision with the exact mutant, reviewer, rationale, and source commit.

A surviving mutant cannot be dismissed only because the original test suite passes. Mutation output is evidence for a specific source commit, mutmut version, Python version, and test-selection configuration.

## Review record

For a release candidate, retain a summary containing the source commit, tool versions, totals by outcome, calculated score, surviving mutants, equivalent-mutant decisions, command, duration, and evaluator limitations. Do not promote a synthetic or partial run as a completed mutation result.
