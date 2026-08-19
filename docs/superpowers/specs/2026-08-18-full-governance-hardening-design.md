# Full Governance Hardening Design

## Objective

Complete the Agentic Project Lifecycle control plane without turning the skills-only plugin into a privileged coding agent. The system must bind approved intent to actual repository changes, observable verification, lifecycle policy, and reproducible release evidence.

## Architecture

The existing seven skills remain the behavioral surface. Normative detail stays in concise references; mechanical claims move into versioned contracts, JSON Schemas, deterministic Python validators, a provider-neutral CLI, and optional isolated execution adapters. Compatibility wrappers preserve existing script paths and legacy project-state validation.

The control loop is:

```text
TaskContract + PolicyProfile
→ isolated execution
→ ExecutionResult from actual Git diff
→ EvidenceRecord and RunManifest
→ cross-contract ProjectAudit
→ GateTransition
→ release readiness and provenance
```

## Components

1. **Contract core** — task, transition, evidence, project state, execution result, policy, audit, and run-manifest validation with stable diagnostic codes.
2. **Git conformance** — source/head lineage, path allow/deny rules, diff budgets, dependency and protected-surface detection, and rollback binding.
3. **Evidence system** — immutable run directories, source identity invariance, artifact digests, freshness, redaction, atomic publication, and hash-chained events.
4. **Policy profiles** — versioned minimum claims, roles, assurance levels, phase-skip rules, and non-waivable blockers.
5. **Cross-contract audit** — reconcile IDs, phases, commits, digests, evidence claims, execution lineage, and repository HEAD.
6. **Interfaces** — backwards-compatible scripts, unified `apl` CLI, SARIF/JSON/text output, reusable GitHub Action, and optional provider-neutral runner.
7. **Assurance** — example tests, property/state-machine tests, hostile fixtures, mutation contract, live behavioral evaluation harness, threat model, SBOM, and provenance.

## Safety boundaries

- Production actions remain forbidden in the plugin and reference runner.
- Repository prose, issues, comments, fetched content, local hooks, and model output are untrusted.
- Planning is read-only; execution is scoped; verification must not mutate source state.
- A hard blocker stops dependent work. A waiver is explicit, source-bound, expiring, and cannot convert failing evidence into passing evidence.
- High-risk and elevated-permission approvals require verifiable assurance or an explicit recorded limitation.
- No readiness statement is universal: every result is scoped to stage, environment, commit, policy, and evidence cutoff.

## Compatibility and versioning

This is a backward-compatible behavioral expansion of suite `1.0.0`, released as `1.1.0-rc.1`. Legacy state validation remains available without strict mode. Stable promotion is blocked until live multi-run behavioral evidence exists and the explicit promotion gate passes.

## Verification strategy

Every implementation increment follows RED–GREEN–REFACTOR. The final gate includes the full pytest suite, `validate.py`, publication validation, compileall, deterministic double build, JSON Schema examples, security diff review, and GitHub Actions on the published branch.
