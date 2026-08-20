# Multi-platform portability implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide secure, deterministic cross-platform packaging and installation for the canonical APL skills.

**Architecture:** The registry is declarative; `platform_support.py` owns validation, inventory, bundles and installs; `apl platform` is only an adapter. Release tooling consumes the same inventory so bundle contents cannot drift.

**Tech Stack:** Python 3.11, PyYAML, jsonschema, pytest, standard-library ZIP/SHA-256/filesystem primitives.

**Spec:** `docs/superpowers/specs/2026-08-20-multiplatform-portability-design.md`

## Global Constraints

- Canonical skills remain under `plugins/agentic-project-lifecycle/skills/`; no platform-specific copies are permitted.
- All generated archives use `SOURCE_DATE_EPOCH`, sorted names and SHA-256 manifests.
- A platform installation may never write outside its explicitly selected root.
- Activation claims start at `not-live-tested` and require separate evidence records.
- Existing PR #3 source is the baseline; temporary export workflows are not part of the increment.

---

### Task 1: Registry and schema

**Files:**
- Create: `platforms/registry.yaml`
- Create: `platforms/platform-registry-v1.schema.json`
- Create: `tests/test_platform_support.py`

- [ ] Add the 15 platform records with unique IDs, aliases, support tiers, native manifests and project/user target templates.
- [ ] Add a strict Draft 2020-12 schema and a failing test for duplicate aliases, traversal and unknown properties.
- [ ] Implement registry loading in the platform module and make the tests pass.
- [ ] Commit: `feat: add validated platform registry`.

### Task 2: Deterministic bundles and manifests

**Files:**
- Create: `scripts/platform_support.py`
- Create: `platforms/platform-bundle-manifest-v1.schema.json`
- Modify: `scripts/build_release.py`
- Modify: `tests/test_platform_support.py`

- [ ] Add failing tests asserting a canonical sorted inventory, symlink rejection and byte-identical repeated platform ZIPs.
- [ ] Implement inventory hashing and a bundle manifest that binds inventory and registry digests.
- [ ] Extend release building to emit all platform ZIPs and include them in `SHA256SUMS`.
- [ ] Run focused tests and commit: `feat: build deterministic platform bundles`.

### Task 3: Transactional installer and CLI

**Files:**
- Modify: `scripts/platform_support.py`
- Modify: `scripts/apl_cli.py`
- Modify: `tests/test_platform_support.py`

- [ ] Add failing tests for dry-run, project/user target selection, altered/missing/extra files and post-publication rollback.
- [ ] Implement staging, pre- and post-publish verification, backup restoration and strict symlink constraints.
- [ ] Add `apl platform list|detect|install|verify|export` with JSON-safe output.
- [ ] Run focused tests and commit: `feat: add transactional platform installer`.

### Task 4: Activation contract and documentation

**Files:**
- Create: `platforms/activation-matrix.yaml`
- Create: `platforms/platform-activation-record-v1.schema.json`
- Modify: `scripts/apl_cli.py`
- Modify: `README.md`
- Modify: `docs/RELEASE_NOTES_v1.1.0-rc.1.md`
- Modify: `tests/test_platform_support.py`

- [ ] Add failing validation cases for absent transcript digests, duplicate run IDs and pressure-policy violations.
- [ ] Implement `apl platform activation validate` and reject unsupported tier promotion.
- [ ] Document installation evidence versus activation evidence versus execution support.
- [ ] Run focused tests and commit: `feat: add platform activation contract`.

### Task 5: Final verification and publication preparation

**Files:**
- Modify: `scripts/validate_publication.py`
- Modify: `VALIDATION.md`
- Test: `tests/test_platform_support.py`

- [ ] Add platform registry, bundle and activation checks to publication validation.
- [ ] Run `python validate.py`, `python -m pytest -q`, `python scripts/validate_publication.py`, `python -m compileall -q plugins scripts tests`, and `git diff --check`.
- [ ] Build two release directories with one fixed `SOURCE_DATE_EPOCH` and compare every artifact SHA-256.
- [ ] Commit the verification integration; push a stacked draft branch only after all checks pass.
