# Architecture

Agentic Project Lifecycle uses an **orchestrator plus specialists** architecture. The orchestrator owns lifecycle routing and cross-artifact consistency; six specialist skills own domain-specific decisions.

## Repository layout

```text
.agents/plugins/marketplace.json              Repository marketplace
plugins/agentic-project-lifecycle/             Distributable plugin
  .codex-plugin/plugin.json                    Plugin manifest
  assets/                                      Plugin visual assets
  skills/                                      Canonical skill source
evals/                                         Routing, project, trace, and ablation evaluations
tests/                                         Regression and packaging tests
scripts/                                       Installation, validation, and release tooling
submission/                                    Directory-review test cases
suite.yaml                                     Behavioral suite contract
validate.py                                    Aggregate evaluation entry point
```

The plugin's `skills/` directory is the only canonical copy of the seven skills. Evaluation fixtures and repository tooling remain outside the plugin so installed users receive the runtime instructions and helpers without development-only evidence.

## Routing model

1. `orchestrating-large-projects` identifies the lifecycle phase, project mode, evidence available, and decisions at risk.
2. It selects the smallest relevant specialist set.
3. Specialists update or validate their owned artifacts.
4. Cross-cutting gates connect scope, architecture, implementation, verification, release, and operations.
5. `auditing-project-readiness` evaluates the evidence without silently filling gaps.

The mode specialists are SaaS delivery, AI products, brownfield modernization, and project rescue. Release and readiness specialists are cross-cutting.

## Artifact model

The suite favors durable repository artifacts over chat-only decisions: project charter, PRD, architecture description, feature specifications, implementation plans, release plans, verification evidence, rollback procedures, runbooks, and project state. Templates live under the orchestrator skill.

Traceability is directional: goals and requirements lead to design and implementation; implementation leads to verification evidence; release decisions cite that evidence. Missing links remain visible as gaps.

## Validation architecture

- Trigger evaluation measures routing accuracy, recall, and false-positive behavior on development and held-out cases.
- Executable fixtures cover greenfield SaaS, AI, brownfield, and rescue modes.
- Pinned public-repository trials provide read-only non-fixture evidence.
- Trace analysis measures unnecessary actions and workflow completion.
- Instruction ablation removes one retained rule at a time to measure independent contribution.
- The promotion gate consolidates the thresholds into a single release decision.
- Publication validation separately checks the plugin manifest, marketplace, public documents, submission cases, repository hygiene, and obvious secret patterns.

See `PROJECT_ANALYSIS.ru.md` for the complete implementation analysis and maintenance notes.
