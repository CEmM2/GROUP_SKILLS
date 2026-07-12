---
name: Documentron_C
description: Codex-native adapter for deterministic-first Documentron repository documentation governance. Incrementally checks and updates user, developer, architecture, API, and scientific/theory docs; caches content-hashed claims; validates deterministic gates; and routes unresolved equations, numerics, statistics, physics, computational mechanics, and ML semantics through Codex reviewer profiles.
---

# Documentron_C

Use the canonical Documentron core bundled in this skill. All files under `agents/`, `commands/`, `references/`, `scripts/`, and `templates/` are generated from `skills/Documentron`; only this runtime adapter differs.

## Routing

Accept `Documentron_C`, `documentron_c`, or natural-language documentation-governance requests. Route to the command table in the canonical workflow files.

## Codex dispatch adapter

- Use a built-in `explorer` for auditor, architect, theorist, scientific reviewer, and other read-only specialist profiles.
- Use a built-in `worker` only for the writer profile that proposes documentation patches.
- Prepend the selected file from `agents/` to the prompt and pass `packet_path`; never paste the full packet.
- Apply matched specialist profiles inline in the same reviewer context.
- Spawn a separate fresh `explorer` only when `llm_policy.required_reviews` requires independent review.
- If agent dispatch is unavailable, perform the first review inline. Do not claim completion when a required independent review could not run; report it as blocked.

Do not invent custom Codex agent types. Do not use an LLM when the deterministic packet requires zero reviews.

## Canonical workflow

Follow the non-negotiable execution order, scientific-correctness policy, durable-state rules, safety boundaries, and retry policy in the bundled command and reference files. `scripts/documentron.py` remains the sole owner of deterministic state and edits.
