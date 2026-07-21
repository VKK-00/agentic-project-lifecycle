# Version 1.0.0 Validation

## Decision

**PROMOTED TO STABLE 1.0.0** under the acceptance contract in `evals/check_promotion_gate.py`.

## Evidence

| Gate | Result |
|---|---:|
| Baseline score | 0.2279 |
| Specialist-suite score | 0.8931 |
| Advantage | +0.6652 |
| Retained rules with positive contribution | 42/42 |
| Held-out prompts | 50 |
| Trigger precision | 1.0000 |
| Trigger recall | 0.9574 |
| False-positive rate | 0.0000 |
| Exact routing accuracy | 0.9600 |
| Executable fixture projects | 4 |
| Public non-fixture trials | 3 |
| Suite median unnecessary actions | 0.0 |
| Baseline-proxy median unnecessary actions | 2.5 |

## Rule removal

`RULE-ORCH-07` was removed after leave-one-rule-out evaluation showed no independent contribution. Its intended behavior remains in the orchestrator overview.

## Non-fixture modes

- `documenso/documenso` at `cc5ef3df160f6f6da4550e7255f11127cc91cbba` — saas workflow: pass
- `open-webui/open-webui` at `ecd48e2f718220a6400ecf49eafd4867a38feb10` — ai workflow: pass
- `pallets/flask` at `36e4a824f340fdee7ed50937ba8e7f6bc7d17f81` — brownfield workflow: pass

## Limitations

Deterministic skill-instruction coverage eval; it does not claim isolated live-Codex sampling or universal model compliance.

A passing read-only trial does not state that the referenced repository is globally ready for release; it states that the bounded skill workflow completed against pinned evidence without inventing missing facts.
