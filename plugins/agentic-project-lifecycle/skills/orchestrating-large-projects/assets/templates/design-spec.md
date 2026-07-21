---
id: "DESIGN-{{FEATURE_ID}}"
status: draft
owner: "{{OWNER}}"
last_reviewed: "{{DATE}}"
source_of_truth: true
related:
  - "{{FEATURE_ID}}"
---

# {{FEATURE_ID}} — {{FEATURE_NAME}} Design

## Design goals and non-goals

### Goals

- <!-- add item -->

### Non-goals

- <!-- add item -->

## Alternatives

| Option | Benefits | Costs/risks | Reversibility |
|---|---|---|---|
| Recommended | | | |
| Alternative | | | |

## Product and UX design

### Information architecture

[Navigation, hierarchy, and entry/exit points.]

### Primary flow

```text
[User flow or diagram]
```

### UI states

| Surface | Default | Empty | Loading | Error | Denied | Recovery |
|---|---|---|---|---|---|---|
| | | | | | | |

### Content and accessibility

- Terminology and copy rules:
- Keyboard/focus behavior:
- Screen-reader semantics:
- Responsive/localization constraints:

## Technical design

### Components and boundaries

| Component | Responsibility | Public interface | Dependencies |
|---|---|---|---|
| | | | |

### Data flow

```text
[Client → API → domain → storage/integration → telemetry]
```

### Data model and migrations

- Entities/fields:
- Invariants:
- Migration strategy:
- Rollback/restore strategy:

### API and event contracts

[Exact endpoints/messages, schemas, errors, idempotency and compatibility rules.]

### Failure modes

| Failure | Detection | User behavior | System recovery | Alert |
|---|---|---|---|---|
| | | | | |

### Security and privacy

- Trust boundaries:
- Authorization:
- Input validation:
- Secret/PII handling:
- Auditability:

### Observability and capacity

- Logs:
- Metrics:
- Traces:
- SLO/budgets:
- Capacity assumptions:

## Test design

| Requirement/risk | Test level | Scenario | Evidence |
|---|---|---|---|
| | | | |

## Rollout

- Feature flag/cohorts:
- Compatibility/migration order:
- Health signals:
- Abort and rollback trigger:

## Decision records

[List ADRs created or updated by this design.]

## Approval

| Role | Name | Decision | Date |
|---|---|---|---|
| Product/design | | pending | |
| Engineering | | pending | |
| Security, if required | | pending | |
