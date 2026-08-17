# Governance Contract Enforcement Design

## Objective

Strengthen Agentic Project Lifecycle without turning it into a coding-agent runtime. The plugin will make its existing governance rules mechanically enforceable through versioned YAML contracts, deterministic Python validators, source-bound evidence, and scaffolded artifacts that are internally consistent with the validators.

## Scope

This increment implements four contracts:

1. **Task contract** — objective, bounded paths and diff budgets, permissions, approved plan, verification commands, approval, rollback, and required evidence.
2. **Gate transition** — lifecycle transition, conditions, blockers, approvals, waivers, residual risks, and final decision.
3. **Evidence record** — claim, source commit, command result, timestamps, environment, artifact digests, and freshness policy.
4. **Project state v2** — current lifecycle state, classified blockers, source-bound artifacts, and links to active contracts.

It also aligns the scaffolded `project-state.yaml` and release artifacts with the validators. It does not execute plans, create branches, call models, deploy, or modify production systems.

## Architecture

A dependency-free module, `governance_contracts.py`, owns parsing helpers and pure validation functions. Thin CLI scripts load YAML, call one validator, print stable `PASS`/`FAIL` output, and return conventional exit codes. `validate_project_state.py` keeps compatibility with legacy project-state files by default but offers strict v2 enforcement; newly scaffolded projects use v2.

The contract files are documented in `governance-contracts.md` and mirrored by parseable YAML schema descriptors under `references/schemas/`. The descriptors are normative field catalogs rather than a dependency on an external JSON Schema runtime. Python remains the enforcement source of truth.

## Validation rules

### Task contract

A writable task requires an approved plan. Consequential risk requires explicit approval. Paths must be repository-relative and traversal-free. Verification commands must be allowed by the permission envelope. Production actions remain forbidden. Rollback must identify a checkpoint and strategy.

### Gate transition

An approved advance cannot contain open hard blockers, unsatisfied conditions, stale evidence, missing required approvals, or unexplained phase skips. Open soft blockers require an owned residual-risk record. Waivers require an approver, rationale, expiry, and source-commit binding.

### Evidence record

Passing evidence must represent an observed successful command, not an agent assertion. Commit IDs, timestamps, result/exit-code consistency, artifact SHA-256 values, and freshness are validated. A caller may provide an expected commit and reference time.

### Project state v2

Required artifacts become structured objects with path, status, owner, source commit, and approval. Ready/complete states cannot contain open hard blockers. Open soft blockers require residual-risk ownership. Referenced contract files must exist and pass their validators when a repository root is supplied.

## Compatibility

Existing implicit-v1 project-state files retain current validation behavior unless `strict=True` or `--strict` is used. The CLI prints a compatibility warning for legacy state. New scaffold output uses `schema_version: "2.0"`, so new projects receive enforcement by default.

## Scaffolding

`scaffold_project.py init` creates a valid v2 project state. `feature` adds a machine-readable `task-contract.yaml`. `release` creates a canonical YAML release plan for readiness checks and retains a Markdown operator-facing plan. Existing files are never overwritten without `--force`.

## Testing

Tests import validators directly and exercise both valid and invalid contracts. They verify traversal rejection, approval and permission coupling, hard-blocker gate behavior, evidence freshness and commit binding, strict/legacy project-state behavior, scaffold-validator consistency, and release YAML/Markdown creation. Every implementation unit follows test-first red/green cycles.

## Failure behavior

Validators collect all detectable errors and never mutate the target project. YAML parse failures, invalid roots, missing linked files, and inconsistent states return exit code 1 with stable diagnostics. Scaffolding keeps its existing preflight-before-write and no-overwrite guarantees.
