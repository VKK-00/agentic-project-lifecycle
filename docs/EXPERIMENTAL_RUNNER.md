# Experimental bounded runner

The bounded runner is **experimental**. It is an optional execution adapter for an already approved Agentic Project Lifecycle task; it is not part of the stable skills-only behavioral contract.

## Security boundary

Every run requires **explicit task confirmation** equal to `task.id`. The source repository must be clean and the output directory must be outside it. The runner creates disposable detached Git worktrees, uses a **read-only planner**, permits scoped writes only during execution, and uses an **independent verifier** in a separate read-only candidate worktree.

For the Codex backend, network access is disabled, web search is disabled, approval escalation is set to `never`, user configuration and repository rules are ignored, and production actions remain forbidden by the task contract. The backend requires an explicit pinned model and an executable selected by the operator.

Deterministic verification commands run with **operating-system network isolation**: a Linux network namespace combined with a disposable PID namespace, or a macOS Seatbelt network profile. Linux uses `unshare --net --pid --fork --kill-child` so background descendants are terminated with the verification namespace. The runner fails closed when the host cannot provide a supported network isolator rather than silently violating `permissions.network: disabled`.

The Codex child process receives a sanitized environment. Unrelated **secret environment variables** are removed, Git prompts and hooks are disabled, and only explicitly supplied non-secret adapter variables are added. Codex authentication should use its normal `CODEX_HOME` credential store; this adapter does not forward API keys from the parent environment.

The runner **never applies the candidate patch automatically**. A successful run exports `candidate.patch`; a failed or cancelled run preserves `failed.patch` when a candidate exists. Applying either patch remains a separate human-controlled action.

## Compatibility status

The provider-neutral runner is covered by deterministic fake-backend tests. The Codex CLI adapter must remain behind `--experimental` until an **authenticated smoke test** has been completed against a pinned CLI and model version in the target environment. CLI compatibility is an observed property, not inferred from documentation.

## Invocation

```bash
python scripts/apl_cli.py run \
  --experimental \
  --backend codex \
  --root /path/to/repository \
  --task /path/to/task-contract.yaml \
  --policy /path/to/policy-profile.yaml \
  --output /separate/path/apl-runs \
  --confirm-task TASK-001 \
  --model <pinned-model-id>
```
