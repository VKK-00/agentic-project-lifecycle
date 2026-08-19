---
name: modernizing-existing-projects
description: Use when changing a legacy or brownfield system with unclear behavior, weak tests, old dependencies, compatibility constraints, risky data migrations, public contracts, staged replacement, or decommissioning work.
license: Apache-2.0
metadata:
  author: VKK-00
  version: 1.1.0-rc.1
  maturity: release-candidate
---
# Modernizing Existing Projects

Modernize from executable truth toward a safer target in reversible slices. Do not begin with a clean-room rewrite proposal.

## Establish current truth

- **RULE-MOD-01:** Inventory runtime entry points, critical workflows, external contracts, data ownership, deployments, telemetry, incidents, and actual consumers before selecting a target architecture.
- **RULE-MOD-02:** Add characterization tests or production-derived contract checks around behavior that must survive. Distinguish intended behavior from accidental behavior explicitly.

## Migrate reversibly

- **RULE-MOD-03:** Prefer strangler slices, adapters, and stable seams over a big-bang rewrite unless an explicit constraint makes incremental migration impossible.
- **RULE-MOD-04:** Use expand-and-contract changes for schemas and public interfaces. Define compatibility windows, dual-read/write rules where needed, cutover criteria, and rollback for every slice.
- **RULE-MOD-05:** Rehearse data migration and reconciliation on production-shaped data. Measure loss, duplication, ordering, latency, and recovery rather than trusting a successful command exit.
- **RULE-MOD-06:** Decommission only after traffic, data, consumers, alerts, support procedures, and rollback windows prove the old path is no longer required.

Read [brownfield discovery](references/brownfield-discovery.md), [migration patterns](references/migration-patterns.md), and [cutover and decommission](references/cutover-and-decommission.md).
