# Changelog

## 1.1.0-rc.1 - 2026-08-18

- Added stable diagnostics with JSON and SARIF output.
- Added actual Git-diff enforcement through ExecutionResult.
- Added versioned policy profiles and cross-contract project audits.
- Added Draft 2020-12 schemas, the unified `apl` CLI, and a reusable GitHub Action.
- Added immutable evidence runs, tamper-evident manifests, hostile fixtures, and a repeated live behavioral evaluation harness.
- Added deterministic SPDX 2.3 SBOM generation, pinned security workflows, dependency auditing, mutation testing, and release attestations.
- Kept stable promotion blocked pending real multi-run behavioral evaluation.

## Unreleased

- Added Ukrainian installation and usage documentation alongside the English and Russian versions.
- Removed the internal Russian project-analysis document from the public repository.

## 1.0.0-rc.1 - 2026-07-21

- Packaged the stable `1.0.0` skill suite as the `agentic-project-lifecycle` Codex plugin.
- Added repository marketplace metadata, visual assets, public installation documentation, privacy and support policies, and directory-review test cases.
- Moved the canonical skill source under the plugin while keeping evaluation and release tooling outside the distribution.
- Added publication validation, deterministic release archives, checksums, and GitHub Actions CI.
- Pinned CI actions to immutable release commits and enabled weekly dependency update checks.

## 1.0.0

- Replaced one monolithic workflow with an orchestrator plus six specialist skills.
- Added deterministic project-state, traceability, context-pack, verification, release-readiness, and health checks.
- Added held-out trigger evaluation, executable fixtures, pinned public-repository trials, trace analysis, and leave-one-rule-out ablation.
- Removed `RULE-ORCH-07` after ablation showed no independent measurable contribution.
- Promoted to stable only after the documented acceptance gate passed.
