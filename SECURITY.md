# Security policy

## Supported versions

Security fixes are provided for the newest published release. During the release-candidate phase, use the newest prerelease tag.

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability. Use GitHub's private vulnerability reporting for this repository:

<https://github.com/VKK-00/agentic-project-lifecycle/security/advisories/new>

Include the affected version, reproduction steps, impact, and any suggested mitigation. The maintainer will acknowledge a complete report within seven calendar days and will coordinate disclosure after a fix or documented mitigation is available.

## Security boundary

This plugin contains instructions, templates, and local Python validation utilities. It does not operate a hosted backend, request credentials, or intentionally transmit project content. Codex and any tools enabled in a user's environment remain separate systems with their own permissions and policies.

Treat generated plans and code as untrusted until reviewed. Keep secrets out of prompts, repositories, logs, and evaluation fixtures. Review proposed shell commands and external writes before approving consequential actions.
