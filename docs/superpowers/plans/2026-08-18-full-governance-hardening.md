# Full Governance Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development. Every behavior change follows test-first RED–GREEN–REFACTOR.

**Goal:** Close the remaining gap between approved lifecycle contracts and actual agent-assisted repository execution.

**Architecture:** Extend the existing skills-only governance plane with modular deterministic contracts, actual-diff validation, trusted policy profiles, immutable evidence, cross-contract audits, provider-neutral interfaces, and optional isolated execution. Preserve existing skills and compatibility entry points.

**Tech Stack:** Python 3.11+, PyYAML, jsonschema, pytest, optional Hypothesis and mutmut, Git/GitHub Actions.

## Global constraints

- Keep exactly seven public lifecycle skills.
- Keep `SKILL.md` concise and route heavy detail to references/scripts.
- Do not add hosted services, credentials, production deployment, or mandatory model/provider dependencies.
- Keep old CLI script paths operational.
- Fail closed for malformed, stale, unverifiable, or source-mismatched claims.
- Commit and verify each independently reviewable increment.

### Task 1: Close known fail-open transition, root, evidence, and release-path cases

Write regression tests for transition direction, strict-root resolution, repository identity mutation during verification, log-name collisions, and unsafe release identifiers. Implement the minimum fixes and commit.

### Task 2: Add modular diagnostics

Add stable issue codes, JSON/SARIF/text rendering, and compatibility conversion to legacy strings. Cover with focused tests and commit.

### Task 3: Enforce actual Git diff

Add ExecutionResult, build/validate commands, path and budget checks, dependency/protected-surface detection, contract/policy digests, and lineage checks. Test against real temporary Git repositories and commit.

### Task 4: Add versioned policy profiles and cross-contract audit

Add policy profiles for general software, SaaS, AI, modernization, rescue, release, and readiness audit. Reconcile project state, task, transition, execution, evidence, policy, and HEAD. Test missing claims, roles, mismatches, and blockers; commit.

### Task 5: Publish formal schemas, version 1.1 RC, and unified CLI

Add Draft 2020-12 schemas with closed objects, examples, schema validation, `apl` CLI, migration notes, honest promotion state, and compatibility tests. Commit.

### Task 6: Make evidence immutable and auditable

Add immutable run directories, atomic latest pointer, HEAD/tree/branch invariance, redaction, hash-chained JSONL events, RunManifest, secure context packs, hostile fixtures, property tests, mutation configuration, and real-run behavioral eval harness. Commit in reviewable slices.

### Task 7: Harden GitHub and release supply chain

Add reusable Action, CODEOWNERS, PR template, CodeQL, dependency review, pip audit, Scorecard, SPDX SBOM, deterministic release inclusion, attestations, threat model, and repository-governance documentation. Commit.

### Task 8: Add optional bounded runner

Add a provider-neutral isolated worktree runner and an experimental Codex adapter behind an explicit flag. Prove planner/executor/verifier boundaries, rollback, patch export, timeout, cancellation, and source preservation. Commit.

### Task 9: Final verification and publication

Run all local gates, security review, build reproducibility, publish a remote branch and draft PR, verify GitHub Actions, update PR evidence, and leave stable promotion blocked until real live eval evidence is present.
