# Codex Routing Scoring and Evidence

Use this reference only when Plan-2-Tasks assigns immutable routing scores or when a legacy task has no stored scores. Do not rescore a task during scaffolding, execution, review, or retry.

## Complexity (1–5)

Score the inherent reasoning and implementation difficulty:

- `1` — mechanical, localized edit with an obvious pattern and one validation path.
- `2` — bounded change across a few nearby files with familiar behavior.
- `3` — multi-file behavior, non-trivial state or API interaction, or several edge cases.
- `4` — architectural coupling, concurrency, migrations, advanced algorithms, or difficult integration.
- `5` — novel or exceptionally difficult architecture, algorithms, numerics, or cross-system behavior.

Use the highest applicable description. File count alone does not lower a conceptually difficult task.

## Risk (1–5)

Score the consequence and likelihood of a wrong result:

- `1` — easy to detect and reverse; no user data, security, compatibility, or scientific impact.
- `2` — limited regression surface with strong local tests and straightforward rollback.
- `3` — public behavior, persistent state, cross-module compatibility, or incomplete observability.
- `4` — security, data integrity, deployment, concurrency, broad compatibility, or material scientific impact.
- `5` — safety-critical behavior, irreversible data loss, authentication boundaries, or correctness-critical equations/numerics with weak independent verification.

Use the highest applicable consequence even when the code change is small.

## Assignment Rules

1. Plan-2-Tasks assigns both scores once and writes them to `complexity` and `risk` in the task JSON.
2. Include a one-sentence rationale for each score in the phase context summary or task analysis.
3. Never average or reduce scores because a capable agent is available.
4. Never let a subagent recompute the scores.
5. For a phase orchestrator, route with the maximum stored complexity and maximum stored risk across tasks in that phase. This is aggregation, not rescoring.
6. For a legacy task missing either field, the first command that needs dispatch assigns both values once, writes them to the task JSON, records `legacy_score_backfill: true`, and then treats them as immutable.

## Mechanical Read-Only Eligibility

Use role `mechanical_read_only` only when the requested output is objectively checkable and non-interpretive: exact search, file inventory, extraction, indexing, classification, or structured summarization. Both stored scores must be at most `2` for the Luna route.

Do not use the mechanical role for debugging, causal analysis, architecture, security, gate review, correctness, scientific interpretation, or numerical validation. If the work is read-only but interpretive, use `explorer`.

## Routing Evidence

Append one evidence object for every dispatch attempt by passing `--evidence-file` and `--purpose` to `resolve_codex_agent.py`. For a task, also pass `--task-json <same-task-json>`; raw score arguments cannot target a task evidence file. The resolver serializes concurrent writers and replaces the JSON atomically. Store task-level evidence in the task JSON `routing_evidence` array. Store phase-orchestrator evidence in `<tasks_folder>/Phase_<N>_routing_evidence.json`.

```json
{
  "dispatched_at": "<ISO-8601 UTC timestamp>",
  "purpose": "implementer | gate-a | gate-b | specialist | scaffold | phase-orchestrator | nesting-probe",
  "resolver": {
    "policy_version": "2026-07-21",
    "complexity": 4,
    "risk": 3,
    "combined": 7,
    "role": "domain_reviewer",
    "effective_role": "domain_reviewer",
    "tier": "sol_high",
    "required": {
      "model": "gpt-5.6-sol",
      "reasoning_effort": "high",
      "sandbox_mode": "read-only",
      "prompt_file": "<skill_root>/agents/autviam-domain-reviewer.md"
    },
    "native_dispatch": {
      "supported": true,
      "model": "gpt-5.6-sol",
      "reasoning_effort_supported": false,
      "sandbox_override_supported": false,
      "custom_profile_supported": false
    },
    "external_dispatch": {
      "supported": true,
      "profile": "domain_reviewer_sol_high",
      "profile_file": "<repo>/.codex/agents/domain-reviewer-sol-high.toml",
      "mode": "codex_cli",
      "command": ["codex", "exec"]
    },
    "recommended_mode": "external_exact",
    "dispatch": {
      "mode": "external_exact",
      "routing_enforcement": "exact",
      "model": "gpt-5.6-sol",
      "reasoning_effort": "high",
      "sandbox_mode": "read-only",
      "prompt_file": "<skill_root>/agents/autviam-domain-reviewer.md",
      "launcher": {"mode": "codex_cli", "command": ["codex", "exec"]},
      "controlled_fields": ["model", "reasoning_effort", "sandbox_mode", "prompt_file"],
      "uncontrolled_fields": []
    },
    "profile_projection": {
      "name": "domain_reviewer_sol_high",
      "file": "<repo>/.codex/agents/domain-reviewer-sol-high.toml"
    }
  }
}
```

Preserve failed resolver or dispatch attempts in the gate/phase record with the command, nonzero status, and error text. Do not fabricate a successful evidence object when routing failed.
