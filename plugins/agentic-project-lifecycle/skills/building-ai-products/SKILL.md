---
name: building-ai-products
description: Use when product behavior depends on LLMs or other models, prompts, retrieval, tool calling, AI evaluation, model routing, grounding, safety, latency, token cost, provider fallback, or model rollback.
license: Apache-2.0
metadata:
  author: VKK-00
  version: 1.1.0-rc.1
  maturity: release-candidate
---
# Building AI Products

Treat model behavior as a versioned, measured, failure-prone product dependency. Keep product policy outside opaque prompt text.

## Bound model authority

- **RULE-AI-01:** State why AI is needed, which decisions remain deterministic, what the model may do autonomously, when human confirmation is required, and the fallback when the model is unavailable or uncertain.
- **RULE-AI-02:** Version a model/prompt contract with purpose, input schema, output schema, grounding sources, prohibited behavior, retry policy, fallback, and ownership.

## Evaluate and operate

- **RULE-AI-03:** Create a representative held-out golden dataset and compare the candidate against a baseline using task-specific thresholds and guardrails. Record failures by category, not only one aggregate score.
- **RULE-AI-04:** Set latency, cost, context, routing, caching, and provider-failure budgets. Test fallback behavior and model deprecation before launch.
- **RULE-AI-05:** Threat-model prompt injection, data leakage, tool misuse, unsafe automation, unsupported claims, and sensitive-data handling. Require grounding or explicit uncertainty where correctness matters.
- **RULE-AI-06:** Do not widen exposure without versioned prompts/models, production sampling, regression evals, observability, a kill switch, and rollback to a known baseline.

Read [product boundary](references/product-boundary.md), [evaluation system](references/evaluation-system.md), and [operations and safety](references/operations-and-safety.md).
