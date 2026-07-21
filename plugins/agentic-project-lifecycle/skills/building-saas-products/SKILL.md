---
name: building-saas-products
description: Use when a hosted subscription product involves tenants or workspaces, pricing plans, entitlements, billing, activation, retention, churn, customer support, account lifecycle, or SaaS unit economics.
license: Apache-2.0
metadata:
  author: VKK-00
  version: 1.0.0
  maturity: stable
---
# Building SaaS Products

Treat SaaS as product, business model, tenancy system, billing state machine, and continuously operated service—not merely hosted software.

## Validate the business boundary

- **RULE-SAAS-01:** Distinguish primary user, buyer, administrator, approver, and ideal customer segment. Define the painful workflow, willingness-to-pay assumption, acquisition motion, and first value event before expanding scope.
- **RULE-SAAS-02:** Specify tenant ownership, membership, invitations, role-based authorization, plan entitlements, data isolation, export, retention, deletion, and ownership transfer. Keep identity, authorization, and entitlements separate.

## Make money and access deterministic

- **RULE-SAAS-03:** Model the complete subscription lifecycle: trial, checkout, activation, upgrade, downgrade, proration, failed payment, retries, grace period, suspension, cancellation, refund, reconciliation, and webhook idempotency. Assign a source of truth for subscription state.
- **RULE-SAAS-04:** Define metric contracts for activation, time-to-value, retention, churn, expansion, revenue, support load, and quality guardrails. Each metric needs a formula, population, window, source, owner, baseline, and target.
- **RULE-SAAS-05:** Track unit economics and cost-to-serve by tenant or core workflow. Set review thresholds for infrastructure, vendor, support, and AI costs before committing pricing.
- **RULE-SAAS-06:** Do not open beta or GA without tested account deletion/export, support ownership, privacy handling, billing recovery paths, observability, and rollback.

Read [discovery and economics](references/discovery-and-economics.md), [tenancy and billing](references/tenancy-billing-entitlements.md), and [activation and operations](references/activation-metrics-operations.md) when those decisions are active.
