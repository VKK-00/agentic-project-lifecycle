## Change

Describe the bounded behavior or documentation change and the source requirement it addresses.

## Risk

State the risk level, protected surfaces touched, permission changes, and residual risks. Write `None` only after review.

## Evidence

List the exact commands, exit codes, source commit, artifacts, and relevant governance contracts. Do not substitute an agent statement for observed evidence.

## Rollback

Name the checkpoint or revert procedure, abort triggers, and the owner responsible for recovery.

## Checklist

- [ ] The change is within the approved scope and diff budget.
- [ ] Tests were observed failing before the behavior change and passing afterward where TDD applies.
- [ ] Required approvals and evidence are source-bound.
- [ ] No secrets, machine-local paths, or temporary export workflows are included.
