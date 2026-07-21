---
name: auditing-project-readiness
description: Use when checking whether a project, feature, migration, or release is ready to advance; when requirements, tests, evidence, owners, context boundaries, rollout, rollback, or project health may be incomplete or inconsistent.
license: Apache-2.0
metadata:
  author: VKK-00
  version: 1.0.0
  maturity: stable
---
# Auditing Project Readiness

Prefer deterministic checks for mechanically verifiable claims. Use judgment only after schemas, links, commands, and required evidence pass.

- **RULE-AUDIT-01:** Run relevant bundled validators before stating readiness. Report every blocking condition with the artifact, owner, and expected correction.
- **RULE-AUDIT-02:** Require traceability from requirement to implementation feature, verification test, evidence, and release. Do not treat document presence as proof of behavior.
- **RULE-AUDIT-03:** Build a task-specific context packet containing only the goal, approved decisions, relevant contracts, allowed/forbidden paths, and verification commands. Reject path traversal and unrelated repository dumps.
- **RULE-AUDIT-04:** Collect fresh command exit codes, durations, and logs. Never replace observed evidence with an agent's statement that checks passed.
- **RULE-AUDIT-05:** Block release readiness when owner, support, telemetry, rollout, rollback, migration, restore, or critical-risk evidence required by the release stage is missing.
- **RULE-AUDIT-06:** Do not promote a process skill to stable based only on static checks or synthetic fixtures. Require executed baseline-versus-skill behavior evaluation, acceptable held-out false-positive triggering, multiple non-fixture project trials, execution-trace review, leave-one-rule-out ablation, and explicit evaluator limitations.

Use scripts under `scripts/` for state validation, traceability, context packing, verification collection, release readiness, and health reporting. Read [audit contract](references/audit-contract.md) before interpreting a pass.
