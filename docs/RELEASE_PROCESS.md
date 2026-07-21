# Release process

The suite version and plugin package version are intentionally separate:

- `suite.yaml` and individual skill metadata describe the stable behavioral suite (`1.0.0`).
- `.codex-plugin/plugin.json` describes the distributable plugin package (`1.0.0-rc.1` during public installation validation).

## Release gate

1. Review the worktree and confirm no unrelated changes or secrets are present.
2. Run `python validate.py` to regenerate and check evaluation evidence.
3. Run `python -m pytest -q` and `python scripts/validate_publication.py`.
4. Validate the plugin manifest with the official plugin validator and every `SKILL.md` with the official skill validator.
5. Build archives twice with the same `SOURCE_DATE_EPOCH`; all hashes must match.
6. Commit and push the verified source. CI on the release commit must pass.
7. Tag the verified commit and create a GitHub prerelease with the deterministic archives, evidence files, and `SHA256SUMS`.
8. Install from the tagged GitHub marketplace and verify plugin discovery before promotion to GA.

## Versioning

Use semantic versioning for the plugin. A breaking behavior or manifest contract change increments the major version. Backward-compatible functionality increments the minor version. Fixes and documentation corrections increment the patch version. Prerelease identifiers are used while a distribution path is still being validated.

## Rollback

Git tags and release assets are immutable evidence. If a release is defective, mark it clearly in GitHub, publish a corrected version, and recommend pinning the previous known-good tag. Do not replace existing release archives under the same version.
