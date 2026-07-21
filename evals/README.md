# Evaluation contract

Stable `1.0.0` is gated by executed evidence rather than author confidence.

## Required gates

1. **Pressure-scenario baseline comparison:** `run_instruction_ablation.py` scores the complete loaded specialist skill against the original monolithic skill on 42 rule-owned pressure scenarios.
2. **Leave-one-rule-out value:** every retained normative rule must improve its owned scenario after removal; redundant rules are deleted and recorded.
3. **Held-out routing:** the routing proxy must achieve recall ≥ 0.95, false-positive rate ≤ 0.05, and exact-set accuracy ≥ 0.90 on a frozen English/Russian held-out set.
4. **Executable projects:** four runnable fixture repositories must pass state, traceability, context, verification, release, and health checks.
5. **Non-fixture projects:** at least three pinned public repositories across three modes must complete bounded read-only workflows with facts, assumptions, gates, risks, and next actions.
6. **Trace efficiency:** suite traces must show no systematic unnecessary work and improve over the documented monolithic baseline proxy.

## Scope and limitation

The pressure evaluator is a deterministic instruction-coverage and ablation test. It verifies the artifact the skill controls directly after loading; it does **not** claim isolated live-Codex sampling or universal compliance by every model. The public-repository trials test bounded workflow application, not full production readiness of those repositories.

Run everything with:

```bash
python3 validate.py
```
