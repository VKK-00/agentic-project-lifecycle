# Agentic Project Lifecycle v1.1.0-rc.1

This release candidate adds deterministic enforcement to the existing seven-skill lifecycle suite.

## Included

- Stable diagnostic codes with text, JSON, and SARIF output.
- Actual Git-diff validation through `ExecutionResult`.
- Versioned policy profiles and cross-contract project audit.
- Draft 2020-12 JSON Schemas.
- Unified `apl` CLI and reusable composite GitHub Action.
- Immutable evidence runs, tamper-evident event logs, hostile fixtures, and repeated live-evaluation harness.
- Deterministic SPDX 2.3 SBOM, pinned security workflows, CodeQL, dependency review, Scorecard, dependency audit, mutation testing, and tag-only provenance/SBOM attestations.
- Fail-closed transition, strict-root, source-identity, collision, and release-path handling.
- Network-isolated verification probes the actual operating-system capability before use; an installed `unshare` or `sandbox-exec` executable is not treated as proof that isolation is available.

## Promotion status

The release candidate is not promoted to stable merely because static, fixture, and publication checks pass. Stable `1.1.0` additionally requires a completed live multi-run behavioral evaluation on held-out pressure cases with explicit limitations.
