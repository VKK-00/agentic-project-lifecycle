# Version 1.1.0-rc.1 Validation

Platform portability is gated by `tests/test_platform_support.py`. It verifies registry uniqueness, canonical inventory hashing, deterministic bundles, transactional rollback, tamper detection and activation-evidence minimums. A release build emits one platform bundle for each registry record; all assets are in `SHA256SUMS`.

## Decision

**RELEASE CANDIDATE — NOT YET PROMOTED TO STABLE 1.1.0.**

The existing routing, fixture, non-fixture, trace, and instruction-ablation evidence remains useful, but it does not establish real model compliance. Stable promotion additionally requires a completed multi-run live behavioral evaluation on held-out pressure cases.

## Evidence already retained

- Held-out deterministic routing evaluation.
- Executable fixture projects across four modes.
- Pinned read-only public-repository trials.
- Trace-efficiency analysis.
- Leave-one-rule-out instruction ablation.
- Contract, actual-diff, policy, audit, schema, and publication regression tests.

## Explicit limitation

Current deterministic evaluations measure the rule and artifact system, not universal or isolated live-agent behavior. A passing project audit is scoped to the supplied repository state, policy profile, commit, environment, and evidence cutoff.
