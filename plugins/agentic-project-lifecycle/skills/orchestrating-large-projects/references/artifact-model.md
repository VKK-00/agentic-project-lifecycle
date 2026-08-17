# Artifact model

Keep one canonical source for each fact, requirement, decision, risk, plan, evidence record, and release decision. Use stable IDs and repository-relative paths. Store durable context in the repository rather than only in chat.

Long-horizon artifacts describe outcomes and constraints. Near-term artifacts name exact interfaces, allowed and forbidden paths, commands, expected results, owners, approvals, bounded permissions, and rollback. Consequential executable work uses a task contract; lifecycle advancement uses a gate-transition contract; readiness claims cite evidence records.

Every approval and evidence record is bound to the source commit it evaluated. A later code, dependency, configuration, test, or contract change invalidates evidence whose claim depends on that state. Keep observed logs and artifact digests with the evidence; never replace them with an agent statement.

`docs/project-state.yaml` is the materialized current view, not an event history. New projects use schema version `2.0`, structured artifact records, classified blockers, residual risks, and links to active contracts. The underlying decisions and evidence remain independently reviewable artifacts.
