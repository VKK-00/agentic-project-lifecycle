# Release process

The suite version and plugin package version are intentionally separate:

- `suite.yaml` and individual skill metadata describe the release-candidate behavioral suite (`1.1.0-rc.1`).
- `.codex-plugin/plugin.json` describes the distributable plugin package (`1.1.0-rc.1` during public installation validation).

## Release gate

1. Review the worktree and confirm no unrelated changes or secrets are present.
2. Run `python validate.py` to regenerate and check evaluation evidence.
3. Run `python -m pytest -q` and `python scripts/validate_publication.py`.
4. Validate the plugin manifest with the official plugin validator and every `SKILL.md` with the official skill validator.
5. Build the release bundle twice with the same `SOURCE_DATE_EPOCH`; the ZIP, `tar.gz`, SPDX 2.3 SBOM, validation report, promotion record, and `SHA256SUMS` must be byte-for-byte reproducible.
6. Commit and push the verified source. CI, CodeQL, dependency review where applicable, and the repository's required status checks must pass on the release commit.
7. Tag the verified commit. The trusted tag workflow must create build-provenance and SBOM attestations for the checksummed subjects using short-lived OIDC identity.
8. Create a GitHub prerelease with the deterministic bundle, `SHA256SUMS`, SBOM, validation evidence, and verification instructions. Do not replace assets under an existing version.
9. Verify checksums and attestations from a clean environment, then install from the tagged GitHub marketplace and verify plugin discovery before promotion to GA.

## Versioning

Use semantic versioning for the plugin. A breaking behavior or manifest contract change increments the major version. Backward-compatible functionality increments the minor version. Fixes and documentation corrections increment the patch version. Prerelease identifiers are used while a distribution path is still being validated.

## Rollback

Git tags and release assets are immutable evidence. If a release is defective, mark it clearly in GitHub, publish a corrected version, and recommend pinning the previous known-good tag. Do not replace existing release archives under the same version.

## Consumer verification

Verify release files before installation:

```bash
sha256sum --check SHA256SUMS
gh attestation verify agentic-project-lifecycle-<version>.zip --repo VKK-00/agentic-project-lifecycle
```

A valid attestation proves provenance and subject integrity for the recorded build; it does not replace behavioral, security, or compatibility review.
