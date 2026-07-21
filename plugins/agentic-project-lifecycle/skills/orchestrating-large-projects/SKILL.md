---
name: orchestrating-large-projects
description: Use when Codex must start, decompose, plan, recover, or govern a multi-week product or software initiative with multiple subsystems, stakeholders, agents, or release stages. Do not use for an isolated bugfix, small refactor, or one already-approved bounded feature.
license: Apache-2.0
metadata:
  author: VKK-00
  version: 1.0.0
  maturity: stable
---
# Orchestrating Large Projects

Treat repository artifacts, code, tests, and observed evidence as project memory. Use this skill as a router and activate only the smallest specialist set that matches the work.

## Orient and decompose

- **RULE-ORCH-01:** Inspect applicable `AGENTS.md`, project docs, code structure, tests, CI, deployment path, `git status`, and recent history before proposing edits. State the current mode, outcome, nearest gate, and highest-risk unknown.
- **RULE-ORCH-02:** Split independent outcomes, release cadences, ownership boundaries, or data/security boundaries into separate subprojects. Give each subproject its own `spec → plan → implementation → verification` cycle.
- **RULE-ORCH-03:** During discovery, ask one highest-value unanswered question per message. Do not repeat facts already supplied or discoverable in the repository.

## Make decisions inspectable

- **RULE-ORCH-04:** Maintain a concise ledger of facts, assumptions, decisions, open questions, risks, and evidence. Never silently promote an assumption into a requirement.
- **RULE-ORCH-05:** Before a consequential product, UX, architecture, data, security, or delivery decision, present two or three materially different approaches with trade-offs and a recommendation.
- **RULE-ORCH-06:** Do not write production-bound code until the current slice has testable acceptance criteria and an approved design. A disposable spike is allowed only with a hypothesis, timebox, non-production boundary, and exit criterion.

## Route and finish

Activate specialists only when their triggers apply: `building-saas-products`, `building-ai-products`, `modernizing-existing-projects`, `rescuing-software-projects`, `releasing-and-operating-products`, and `auditing-project-readiness`.

- **RULE-ORCH-08:** End each substantial turn with the current phase and decision, files read or changed, observed verification results, unresolved assumptions and risks, and the next bounded gate or executable task.

Read [routing and gates](references/routing-and-gates.md) for phase selection and [artifact model](references/artifact-model.md) when establishing sources of truth.
