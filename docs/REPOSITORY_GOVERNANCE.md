# Repository governance

The repository should enforce its governance model through GitHub rulesets rather than relying on contributor convention alone.

## Required branch controls

The default branch requires a **required pull request** before merge, at least one independent approval, resolution of review conversations, and all configured **required status checks**. New commits dismiss **stale approvals**. Direct pushes, branch deletion, and **force pushes** are disabled. Administrators should use the same controls except for documented emergency recovery.

## Ownership

`CODEOWNERS` assigns explicit review ownership to lifecycle skills, formal schemas, validation and release scripts, GitHub workflows, the reusable Action, and security policy. High-risk changes should be reviewed by someone other than the author or executing agent.

## Required checks

At minimum, protect the branch with:

- CI on Python 3.11 and 3.12;
- publication and deterministic release validation;
- CodeQL;
- dependency review;
- secret scanning and push protection where the hosting plan supports them;
- conversation resolution and CODEOWNERS review.

Scheduled OpenSSF Scorecard and mutation testing provide assurance signals but need not block every pull request.

## Release controls

Release tags are created only from a commit that passed the required checks. The tag workflow builds deterministic archives, an SPDX SBOM, checksums, build provenance, and an SBOM attestation. Release evidence is immutable; a defective release receives a new version rather than replacement assets under the same tag.

## Emergency changes

An emergency exception must identify the incident, approver, scope, expiry, compensating controls, rollback, and follow-up review. It does not authorize bypassing secret handling, production safety, or evidence integrity requirements.
