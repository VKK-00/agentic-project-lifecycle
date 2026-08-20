# Multi-platform portability design

## Goal

Distribute one canonical Agentic Project Lifecycle skill inventory to supported agent platforms without claiming that installation proves model activation or bounded execution.

## Architecture

`platforms/registry.yaml` is the single source of platform metadata: identifiers, aliases, native manifest locations, installation targets and evidence tier. A small `platform_support` module loads and validates that registry, derives a canonical file inventory, creates deterministic bundles and performs transactional installation/verification. The existing `apl` command exposes these operations as a separate `platform` namespace.

Every platform bundle includes the canonical skills once, a generated manifest with SHA-256 inventory and registry digest, plus an optional native manifest. The installer stages a complete target, verifies it, atomically replaces an existing target, verifies the published copy, and restores the previous target if any post-publication check fails. Development symlinks are opt-in and may not escape the canonical skill root.

## Platform claims

Distribution support, activation evidence and execution support are deliberately independent. All records begin as `not-live-tested`; only records that pass the activation contract may be promoted. Codex remains the sole experimental bounded-execution adapter unless separately proven.

## Error handling and security

Registry parsing rejects unknown keys, duplicate IDs/aliases, traversal paths and targets outside the selected project/user root. File collection rejects symlinks and non-regular files. Verification detects missing, altered and extra files. Install failures leave the prior target unchanged or restore it before returning an error.

## Verification

Focused tests cover registry/schema invariants, bundle determinism, supported CLI flows, installer rollback, path and symlink attacks, activation-record validation and release inventory. The final gate runs the full pytest suite, validation/publication scripts, compileall, diff check, and two release builds whose artifact digests must match.
