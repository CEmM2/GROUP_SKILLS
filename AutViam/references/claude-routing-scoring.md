# Claude routing scoring

Use this reference only during Plan-2-Tasks or an explicit legacy initialization. Never rescore a routed task during scaffolding, execution, review, retry, completion, or reset.

## Scores

Assign both `complexity` and `risk` as integers from 1 through 5 while the full plan context is available. Record a short task-specific rationale.

- Complexity 1–2: localized, established pattern, small verification surface.
- Complexity 3: cross-file reasoning or moderate integration work.
- Complexity 4: architectural, algorithmic, or broad contract work.
- Complexity 5: exceptional ambiguity, difficult algorithms, or system-wide coupling.
- Risk 1–2: reversible and low-impact failure modes.
- Risk 3: meaningful compatibility, data, or correctness consequences.
- Risk 4: security, numerical, migration, or broad API risk.
- Risk 5: safety-critical, irreversible, or exceptionally consequential work.

## Tier matrix

Apply in order:

1. Either score is 5, or combined is at least 9 → `opus_xhigh`.
2. Either score is at least 4, or combined is at least 7 → `opus_high`.
3. Either score is at least 3 → `sonnet_high`.
4. Otherwise → `sonnet_medium`.

Gate reviewers use the policy's reviewer floor. Haiku is limited to mechanical, objectively checkable, read-only work with both scores at most 2. File-writing, review, architecture, debugging, security, equations, and numerical judgment never use Haiku.

## Persistent state

Store scores under `task.routing` with `combined`, the active `policy_version`, an ISO-8601 `scored_at`, `scored_by`, and `rationale`. Missing or partially populated routing is invalid. A legacy initializer may populate an absent or entirely-null routing object once and must refuse overwrite.

Every dispatch records the resolver output, purpose, parent role and agent, child role and agent, capability, depth, maximum depth, enforcement mode, ticket path, and UTC timestamp. Task evidence stays in the task JSON; phase-orchestrator evidence stays in `Phase_<N>_routing_evidence.json`.
