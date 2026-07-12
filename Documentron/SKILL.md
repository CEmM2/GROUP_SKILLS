---
name: Documentron
description: Deterministic-first documentation governance for repositories. Incrementally checks and updates user, developer, architecture, API, and scientific/theory documentation; caches content-hashed claims; validates links and configured builds; and routes only unresolved semantics through matched specialist reviewers. Use for repository documentation initialization, drift checks, fact-checking, post-plan updates, architecture maps, or equation/numerical/statistical/ML documentation review.
---

# Documentron

Keep repository documentation correct while minimizing semantic-model work. Run deterministic discovery, matching, validation, patching, state updates, and report rendering through `scripts/documentron.py`. Use an LLM only when its generated packet requires semantic review.

## Routing

Read only the selected command file.

| Input | Command |
|---|---|
| `init [--strict]` | `commands/Init.md` |
| `get-familiar` / `familiarize` | `commands/GetFamiliar.md` |
| `check [scope]` | `commands/Check.md` |
| `update (--pr N | --plan FILE | --commits LIST | --since DATE)` | `commands/Update.md` |
| `refresh (--since DATE | --from-tag TAG | --full)` | `commands/Refresh.md` |
| `post-plan PLAN [flags]` | `commands/PostPlan.md` |
| `doctor [--strict]` | `commands/Doctor.md` |
| `architecture SCOPE` / `arch SCOPE` | `commands/Architecture.md` |
| `factcheck TARGET` / `fact-check TARGET` | `commands/FactCheck.md` |
| `theory build/check/refresh/map ...` | `commands/Theory.md` |
| `install [--dry-run]` | `commands/Install.md` |

## Non-negotiable execution order

1. Run `scripts/documentron.py prepare --command <command> <scope arguments>` before broad reading.
2. Read the emitted packet by path. Do not paste it into another agent prompt.
3. If `llm_policy.required_reviews` is zero, complete through scripts only.
4. Otherwise apply every matched specialist inline. Use a fresh independent reviewer only when the packet requires a second review.
5. Return JSON shaped by `templates/semantic-result.schema.json`.
6. Run `validate-result`, then `apply-result`; never edit workflow state or the claim ledger manually.
7. Run deterministic validation and render reports from JSON.

Read `references/deterministic_engine.md` when operating the engine. Read `references/scientific_review.md` whenever scientific review is required.
Read `references/design_docs.md` when design documents enter the resolved scope.

## Scientific correctness

Equations, physical assumptions, numerics, algorithms, statistics, and ML semantics always remain eligible for—normally require—domain-specialist LLM review. Deterministic checks prepare evidence and validate executable properties; they do not waive semantic review. New or changed equations, physical assumptions, security, and safety claims require an independent second review by default.

## Source status

Classify evidence by claim type rather than using one global precedence list:

- current behavior: executable tests/examples, generated interfaces, implementation;
- public contract: schemas, public interfaces, contract tests;
- identifiers/signatures: AST or generated interfaces;
- intent: active design docs;
- temporal claims: Git history;
- implemented theory: code, tests, derivation mapping;
- literature: cited primary sources;
- performance: reproducible benchmark artifacts.

Git history does not prove current behavior. Design docs do not prove implementation. Existing docs are never self-validating.

## Core profiles and specialists

The profiles in `agents/` define stable roles: auditor, writer, architect, theorist, and scientific reviewer. Repo-specific specialists declare triggers in `documentron-specialist.json`; `discover-specialists` compiles them without LLM inference. Specialist matching is deterministic and reports its reasons.

Apply specialist profiles as inline lenses to avoid duplicate repository reads. Dispatch separately only for a required independent review or an explicit isolation rule.

## Durable state

Commit configuration and maps under `.documentron/`; treat generated runs and reports according to the consuming repository's policy. The authoritative state is:

- `.documentron/config.json`
- `.documentron/claims.jsonl`
- `.documentron/doc-map.yml`
- `.documentron/theory-map.yml`
- `.documentron/repo-rules.yml`
- `.documentron/architecture/`

GitHub issues and PR summaries are projections.

## Safety and retries

- Execute only allowlisted validation commands and only when explicitly requested.
- Permit one malformed-JSON repair and one targeted semantic correction.
- Never retry deterministic failures through an LLM.
- Stop when the same semantic failure recurs.
- Require preimage-hashed, uniquely matching patches.

For AutViam integration, read `references/autviam_post_plan_hook.md`. The hook prepares a deterministic post-plan packet; the host runtime performs any required semantic review.
