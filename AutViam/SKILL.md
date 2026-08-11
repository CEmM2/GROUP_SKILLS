---
name: AutViam
description: Claude conversational façade for the shared AutViam Whatter profile.
---

# AutViam

AutViam is a thin Claude-facing façade over the independently versioned shared profile published at `<skills-root>/shared/profiles/autviam`. It contains no scheduler, gate, prompt, or mutable task-state implementation.

Before interpreting a command, resolve the shared bootstrap:

```bash
python <skills-root>/shared/scripts/autviam_facade.py \
  --facade claude --skill-root <skills-root>/AutViam --command <command> [arguments]
```

It blocks clearly when Whatter or the profile is missing and only emits a `whatter_invocation`; it never executes one or selects a fallback. Execute the returned `argv` with the returned `env` merged into the process environment. The `WHATTER_AUTVIAM_PROFILE` binding is mandatory: do not reconstruct or execute a bare Whatter command from the table below.

| Command | Whatter CLI |
|---|---|
| `gen-plan` | `whatter profile genplan` |
| `plan-compile` | `whatter plan compile` |
| `status` | `whatter runtime status` |
| `run`, `review`, `close`, `delivery` | Block with migration guidance until Whatter exposes those production CLI surfaces. |

Old `tasks`, `scaffold`, `exec`, `phase`, fixed-gate, and tracker semantics are obsolete. During the compatibility window ending 2026-10-01, use `legacy <old-command>` explicitly; the façade never routes an old command to legacy automatically.
