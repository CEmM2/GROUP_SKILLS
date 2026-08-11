---
name: AutViam_C
description: Codex conversational façade for the shared AutViam Whatter profile.
---

# AutViam_C

AutViam_C is a thin Codex-facing façade over the same independently versioned AutViam profile used by `AutViam`. It contains no scheduler, gate, prompt, routing, or mutable task-state implementation.

Before interpreting a command, resolve the shared bootstrap:

```bash
python <skills-root>/shared/scripts/autviam_facade.py \
  --facade codex --skill-root <skills-root>/AutViam_C --command <command> [arguments]
```

The resolver validates the profile dependency and Whatter executable, emits a `whatter_invocation`, and blocks rather than falling back. It does not invoke Whatter itself. Execute the returned `argv` with the returned `env` merged into the process environment. The `WHATTER_AUTVIAM_PROFILE` binding is mandatory: do not reconstruct or execute a bare Whatter command from the table below.

| Command | Whatter CLI |
|---|---|
| `gen-plan` | `whatter profile genplan` |
| `plan-compile` | `whatter plan compile` |
| `status` | `whatter runtime status` |
| `run`, `review`, `close`, `delivery` | Block with migration guidance until Whatter exposes those production CLI surfaces. |

The old `tasks`, `scaffold`, `exec`, `phase`, fixed-gate, and tracker commands have obsolete semantics. During the compatibility window ending 2026-10-01, invoke `legacy <old-command>` explicitly; no legacy fallback is automatic or silent.
