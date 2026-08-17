# Routing and gates

The lifecycle phases are `orientation → discovery → specification → solution-design → planning → implementation → release → operations`. Route directly to the matching specialist after orientation for brownfield modernization, rescue, release, or audit work, but do not bypass the entry conditions of the destination phase.

## Transition rule

Advance only through a validated gate transition whose outcome, owner, conditions, approvals, evidence, blockers, residual risks, decision, and source commit are explicit. The default transition is to the next phase. Skipping a phase requires policy permission and lifecycle-owner approval. Reopening moves to an earlier phase when new evidence invalidates an accepted assumption, design, plan, or readiness claim.

A transition may be `approved`, `rejected`, `held`, or `waived`. Approval is not inferred from work having started. A rejected or held transition leaves project state at the current phase. A waiver records the precise condition being accepted, the decision owner, rationale, residual risk, review or expiry date, and source commit.

## Blocker policy

Classify findings as `hard`, `soft`, or `informational`. An open hard blocker stops dependent work. An open soft blocker requires an owned residual-risk record and may proceed only under the transition policy. Informational findings do not alter the gate. After a retry limit is reached, preserve the blocker and stop or continue only independent work; never silently treat exhaustion as resolution.

## Phase evidence

Orientation establishes mode, outcome, owner, repository state, and highest-risk unknown. Discovery establishes validated problem and constraints. Specification establishes observable requirements and acceptance criteria. Solution design establishes approved interfaces, data and security boundaries, and alternatives considered. Planning establishes a source-bound task contract with bounded permissions and rollback. Implementation produces a bounded diff and observed verification. Release requires fresh source-bound evidence, rollout, support, telemetry, migration or restore evidence when applicable, and rollback. Operations requires ownership, service signals, incident handling, and learning loops.

Use [governance contracts](governance-contracts.md) for the machine-readable task and transition boundaries.
