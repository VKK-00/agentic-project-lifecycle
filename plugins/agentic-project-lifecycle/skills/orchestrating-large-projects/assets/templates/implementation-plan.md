# {{FEATURE_ID}} — {{FEATURE_NAME}} Implementation Plan

**Goal:** [One independently verifiable feature outcome.]

**Architecture:** [Two or three sentences describing the approved approach and boundaries.]

**Source specs:** `spec.md`, `design.md`, relevant ADRs and contracts.

## Global constraints

- Do not expand approved scope.
- Preserve public compatibility unless the design explicitly approves a break.
- Use test-first for production behavior.
- Update docs, telemetry and migrations in the same change that requires them.
- Never claim completion without command results and evidence.

## File map

| Action | Path | Responsibility |
|---|---|---|
| Create/modify | `exact/path` | |

## Dependency order

```text
[Task dependency graph]
```

## Task 1 — [independently reviewable deliverable]

**Files**

- Create: `exact/path`
- Modify: `exact/path:line-range`
- Test: `exact/test/path`

**Interfaces**

- Consumes: `[exact signature/schema]`
- Produces: `[exact signature/schema]`

- [ ] Write a failing test or pre-change proof for one behavior.
- [ ] Run `[exact command]`; expected result: `[specific failure]`.
- [ ] Implement the minimum change that satisfies the behavior.
- [ ] Run `[exact command]`; expected result: PASS with `[details]`.
- [ ] Run relevant lint/typecheck/integration checks.
- [ ] Review `git diff` for scope, security, generated files and docs impact.
- [ ] Commit with `[exact intended commit message]`.

## Task 2 — [next independently reviewable deliverable]

[Repeat the complete structure; do not write “same as Task 1”.]

## Final verification

| Command/scenario | Expected result | Evidence location |
|---|---|---|
| | | |

## Review gates

1. Spec compliance review.
2. Code quality/security/operability review.
3. Release readiness review when user-facing or operational risk changes.
