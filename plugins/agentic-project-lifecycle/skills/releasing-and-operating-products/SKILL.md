---
name: releasing-and-operating-products
description: Use when preparing alpha, beta, release candidate, general availability, production rollout, feature flags, migrations, rollback, SLOs, alerts, runbooks, customer support, incident response, or post-release learning.
license: Apache-2.0
metadata:
  author: VKK-00
  version: 1.1.0-rc.1
  maturity: release-candidate
---
# Releasing and Operating Products

A release is a controlled exposure with a product hypothesis, operational ownership, and a reversible path—not merely a deployment.

## Define and expose safely

- **RULE-OPS-01:** Specify audience, hypothesis, included and excluded scope, entry criteria, exit criteria, metrics, known limitations, owner, and support channel for every staged release.
- **RULE-OPS-02:** Define SLOs or explicit reliability targets, telemetry, dashboards, actionable alerts, runbooks, escalation, and support ownership before exposing users.
- **RULE-OPS-03:** Use the smallest safe exposure mechanism—internal cohort, allowlist, feature flag, canary, or percentage rollout—with explicit pause and rollback thresholds.
- **RULE-OPS-04:** Rehearse migrations, backup restore, rollback, and operator recovery on production-shaped conditions. A backup without a successful restore test is not recovery evidence.

## Operate and learn

- **RULE-OPS-05:** Record incident impact, timeline, detection, causes, contributing factors, corrective actions, owners, and deadlines without blame. Feed evidence back into specifications and roadmap.
- **RULE-OPS-06:** Do not declare a release complete without fresh command results, manual critical-path checks, known limitations, approval status, and observed post-release metrics.

Read [release stages](references/release-stages.md), [reliability and recovery](references/reliability-and-recovery.md), and [incidents and learning](references/incidents-and-learning.md).
