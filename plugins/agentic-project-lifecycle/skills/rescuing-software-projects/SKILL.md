---
name: rescuing-software-projects
description: Use when a software project is late, repeatedly missing commitments, blocked by failing builds or deployments, carrying uncontrolled scope, lacking clear ownership, or requiring a recovery plan before normal feature work can continue.
license: Apache-2.0
metadata:
  author: VKK-00
  version: 1.1.0-rc.1
  maturity: release-candidate
---
# Rescuing Software Projects

Restore control before optimizing architecture or adding scope. The first outcome is reliable visibility and a small confidence-restoring release.

- **RULE-RESCUE-01:** Freeze new scope temporarily. Establish a reproducible build, test, deployment, and status view; record what is actually working rather than relying on plans or confidence.
- **RULE-RESCUE-02:** Inventory commitments, owners, dependencies, blockers, and the critical path. Mark commitments as keep, renegotiate, defer, or cancel with an accountable decision owner.
- **RULE-RESCUE-03:** Classify blockers as product, technical, dependency, people/ownership, operational, or decision latency. Remove non-critical work and create the smallest release that restores trust or usable value.
- **RULE-RESCUE-04:** Do not start a broad rewrite or platform migration unless it directly removes the current critical-path blocker and has a reversible proof point.
- **RULE-RESCUE-05:** Track daily evidence: passing checks, deployability, blocker age, decision latency, scope change, and remaining risk. Re-baseline roadmap and ownership only after the recovery release is stable.

Read [triage](references/triage.md), [recovery planning](references/recovery-planning.md), and [rebaseline](references/rebaseline.md).
