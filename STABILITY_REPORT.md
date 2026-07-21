# Large Project Skills Suite — Stability Report

**Version:** `1.0.0`<br>
**Status:** Stable against the declared evaluation contract<br>
**Date:** 2026-07-21<br>
**Architecture:** Orchestrator plus focused specialist skills

## Package composition

- `orchestrating-large-projects`
- `building-saas-products`
- `building-ai-products`
- `modernizing-existing-projects`
- `rescuing-software-projects`
- `releasing-and-operating-products`
- `auditing-project-readiness`

## 1.0 promotion gates

| Gate | Result | Evidence |
|---|---:|---|
| Executed baseline comparison | PASS | 0.2279 → 0.8931; advantage **+0.6652** across 42 pressure scenarios |
| False-positive triggering | PASS | FPR **0.0000**, precision 1.0000, recall 0.9574, exact-set accuracy 0.9600 on 50 held-out prompts |
| Executable project modes | PASS | 4 fixture repositories: ai, brownfield, rescue, saas |
| Non-fixture project modes | PASS | 3 pinned public repositories: ai, brownfield, saas |
| Execution-trace efficiency | PASS | median unnecessary actions: suite **0.0**, monolithic baseline proxy **2.5** |
| Rule ablation | PASS | all 42 retained rules had positive leave-one-rule-out contribution |
| Rule removal | PASS | removed `RULE-ORCH-07` because it added no independent measurable value |
| Static/package validation | PASS | `python3 validate.py` completed without blockers |
| Test suite | PASS | `pytest -q`: 7 passed |

## Non-fixture project trials

### `documenso/documenso`

- Mode: `saas`
- Commit: `cc5ef3df160f6f6da4550e7255f11127cc91cbba`
- Workflow status: `pass`
- Bounded gate: `GATE-SAAS-BILLING-RECOVERY-EVIDENCE` → `conditional`
- Sources inspected: 3
- Trace actions: 7

### `open-webui/open-webui`

- Mode: `ai`
- Commit: `ecd48e2f718220a6400ecf49eafd4867a38feb10`
- Workflow status: `pass`
- Bounded gate: `GATE-AI-MODEL-CHANGE-EVIDENCE` → `blocked`
- Sources inspected: 2
- Trace actions: 7

### `pallets/flask`

- Mode: `brownfield`
- Commit: `36e4a824f340fdee7ed50937ba8e7f6bc7d17f81`
- Workflow status: `pass`
- Bounded gate: `GATE-BROWNFIELD-COMPATIBILITY-SLICE` → `conditional`
- Sources inspected: 2
- Trace actions: 7

## Removed rule

`RULE-ORCH-07` was removed. Leave-one-rule-out evaluation showed zero independent contribution; the same minimum-specialist-set constraint is already present in the orchestrator overview.
The behavior remains enforced by: SKILL.md overview: activate only the smallest specialist set that matches the work.

## Evaluation scope and limitation

Measures pressure-scenario rubric coverage in the complete loaded skill versus the original monolithic baseline and versus removal of each retained normative rule.

**Limitation:** Deterministic skill-instruction coverage eval; it does not claim isolated live-Codex sampling or universal model compliance.

The non-fixture trials are bounded, read-only workflows. Their PASS status means the suite produced an evidence-backed gate decision without scope inflation; it does not declare those repositories production-ready.

## Reproduce

```bash
python3 validate.py
pytest -q
```
