# Agentic Project Lifecycle

[![CI](https://github.com/VKK-00/agentic-project-lifecycle/actions/workflows/ci.yml/badge.svg)](https://github.com/VKK-00/agentic-project-lifecycle/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/VKK-00/agentic-project-lifecycle?include_prereleases)](https://github.com/VKK-00/agentic-project-lifecycle/releases)

Agentic Project Lifecycle is a Codex skills-only plugin for governing large software projects from discovery through production operations. It combines one lifecycle orchestrator with six focused specialist skills, executable project fixtures, held-out routing tests, and a measurable release-readiness gate.

> Release status: `main` contains the verified `1.1.0-rc.1` implementation. A Git tag and release assets have not yet been published; use `--ref main` until that release is cut. Stable `1.1.0` remains blocked on authenticated repeated live-agent evaluation.

[English](README.md) | [Русский](README.ru.md) | [Українська](README.uk.md)

## What it helps with

- Turn a product idea into a governed delivery plan with explicit artifacts and decision gates.
- Build SaaS and AI products with domain-specific product, architecture, evaluation, and operational controls.
- Modernize brownfield systems while preserving compatibility and planning safe cutovers.
- Rescue delayed or unstable projects using evidence-first triage and rebaselining.
- Prepare releases, rollback plans, observability, and incident-learning loops.
- Audit traceability, verification evidence, and release readiness without inventing missing proof.

## Included skills

| Skill | Purpose |
| --- | --- |
| `orchestrating-large-projects` | Routes work across the lifecycle and keeps project artifacts coherent. |
| `building-saas-products` | Covers SaaS discovery, tenancy, entitlements, billing, activation, and operations. |
| `building-ai-products` | Defines AI product boundaries, evaluations, safety controls, and operations. |
| `modernizing-existing-projects` | Handles brownfield discovery, migration patterns, cutover, and decommissioning. |
| `rescuing-software-projects` | Triages distressed projects and creates evidence-based recovery plans. |
| `releasing-and-operating-products` | Governs staged releases, reliability, rollback, incidents, and learning. |
| `auditing-project-readiness` | Validates project state, traceability, evidence, and release readiness. |

## Install in Codex

Add this repository as a plugin marketplace, then install the plugin:

```text
codex plugin marketplace add VKK-00/agentic-project-lifecycle --ref main
codex plugin add agentic-project-lifecycle@vkk-00-agent-plugins
```

In the Codex desktop app, the same marketplace can be added from **Plugins > Marketplaces**, after which **Agentic Project Lifecycle** appears in the plugin list.

## Multi-platform distribution

APL has one canonical seven-skill inventory and produces deterministic bundles for Agent Skills, Codex, Claude Code, GitHub Copilot, Cursor, Kimi Code, Gemini CLI, OpenCode, Factory Droid, Amp, Devin, Pi, Hermes, Antigravity, and Gemini Enterprise.

To inspect supported targets and install into an explicit project or user root:

```bash
python apl platform list
python apl platform install codex --scope project --root /path/to/project
python apl platform verify /path/to/project/.codex/skills/agentic-project-lifecycle
```

The installer stages and verifies a full copy before atomically publishing it; `--force` restores the previous installation if post-publication verification fails. `--scope user` always requires an explicit `--root`; it never writes to a guessed home directory.

## Start using it

Ask Codex something concrete, for example:

```text
Turn this product idea into a governed project from discovery through release.
```

```text
Audit this project's readiness for beta or general availability.
```

```text
Create a recovery plan for this delayed software project.
```

The orchestrator selects the relevant specialist skills. You can also invoke a skill explicitly, for example `$auditing-project-readiness`.

## Validate from source

Requirements: Python 3.11 or newer.

```bash
python -m pip install -e ".[dev]"
python validate.py
python -m pytest -q
python scripts/validate_publication.py
```

Build deterministic release archives:

```bash
python scripts/build_release.py --version 1.1.0-rc.1 --output dist
```

The build creates ZIP and `tar.gz` plugin archives, 15 platform bundles, validation evidence, the promotion-gate result, and SHA-256 checksums.

## Evidence and limitations

Distribution support does not prove that a platform activated the skills or that a model followed them. Activation evidence and bounded execution are separate claims; the committed activation matrix intentionally records every platform as `not-live-tested`.

The repository includes held-out routing cases, executable fixture projects, pinned read-only public-repository trials, execution-trace analysis, and leave-one-rule-out instruction ablation. See [Validation](VALIDATION.md), [Stability report](STABILITY_REPORT.md), and [evaluation documentation](evals/README.md).

These evaluations test the suite's routing and artifact rules; they do not prove that every model run or project outcome will be correct. The public-repository trials do not certify the sampled projects. Users remain responsible for reviewing changes and approving consequential actions.

## Project documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Release process](docs/RELEASE_PROCESS.md)
- [Support](docs/SUPPORT.md)
- [Security policy](SECURITY.md)
- [Contributing](CONTRIBUTING.md)
- [Privacy](docs/PRIVACY.md)
- [Terms](docs/TERMS.md)

## License and attribution

Licensed under Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

This is an independent community project maintained by VKK-00. It is not an official OpenAI product. The project was developed with assistance from OpenAI Codex; responsibility for the published content remains with the maintainer.
