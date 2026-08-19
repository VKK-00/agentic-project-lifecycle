# Evaluation contract

Version `1.1.0-rc.1` is a release candidate. Stable `1.1.0` is gated by executed evidence rather than author confidence.

## Required gates

1. **Instruction pressure comparison:** `run_instruction_ablation.py` compares the loaded specialist suite with the retained monolithic baseline on rule-owned pressure scenarios.
2. **Leave-one-rule-out value:** every retained normative rule must make a positive contribution; redundant rules are removed and recorded.
3. **Held-out routing:** the deterministic routing proxy must meet the frozen recall, false-positive, and exact-set thresholds.
4. **Executable projects:** runnable fixture repositories must pass state, traceability, context, verification, release, and health checks.
5. **Non-fixture projects:** pinned public repositories across multiple modes must complete bounded read-only workflows without invented facts.
6. **Trace efficiency:** observed workflow traces must not show systematic unnecessary work and must improve on the documented baseline proxy.
7. **Live behavioral evaluation:** at least three independent baseline and skill runs per held-out pressure case must be executed with an explicit model snapshot and evaluator limitations.

## Live harness

Validate the frozen catalog without publishing a result:

```bash
python evals/run_live_behavioral_eval.py --validate-config
```

Execute a real runner through the provider-neutral request contract:

```bash
python evals/run_live_behavioral_eval.py \
  --runner-command '<runner command>' \
  --model-snapshot '<explicit pinned model or runtime identifier>' \
  --runs-per-case 3 \
  --limitations '<known evaluator and environment limitations>' \
  --output evals/results/live-behavioral-eval.json
```

The harness creates a fresh Git repository for every run, compares actual changes with each case's path policy, records Git-identity changes, scope and policy violations, fabricated-evidence indicators, unnecessary actions, duration, and outcome compliance. It publishes the requested report atomically only after every selected run returns valid structured output. A missing, failing, timed-out, or malformed runner cannot generate a complete report.

The runner receives only a small inert environment allowlist by default. Authentication or runtime context must be inherited explicitly with repeatable `--runner-env NAME` arguments, for example `--runner-env HOME --runner-env CODEX_HOME`. The report records only inherited variable names, never their values. On Linux the runner is also placed in a disposable PID namespace so background descendants cannot survive a completed or failed run.

A synthetic runner may validate harness mechanics, but its result must never be copied to `evals/results/live-behavioral-eval.json` or used for stable promotion.

## Scope and limitations

Deterministic routing and instruction-ablation checks validate artifacts controlled directly by this repository; they do not establish universal model compliance. Public-repository trials test bounded workflow application rather than global production readiness. Live results remain specific to the recorded model snapshot, runner, tool permissions, repositories, case catalog digest, and execution date.

Run the deterministic repository suite with:

```bash
python validate.py
```
