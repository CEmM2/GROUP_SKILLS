---
name: AutViam_C
description: >
  Codex-native phased plan execution with test scaffolding, quality gates,
  capability-aware model and prompt routing, a hard failure cap, and phase-level
  GitHub tracking. Use for AutViam_C or its phase commands.
---

# AutViam_C — Codex Plan → Scaffold → Execute

Self-contained pipeline turning a markdown plan into tracked, executed, verified work. This is the Codex-native fork of AutViam: it preserves the phase-only GitHub issue model and gate discipline while routing every subagent through a capability-aware execution specification. Bundled Markdown files are canonical role prompts. Generated TOMLs are external-launch profiles and audit projections; their names are native subagent types only when the active dispatcher probe explicitly says so.

## Routing

Parse the first token after the user's `AutViam_C` or `$AutViam_C` invocation and read the matching command file from `commands/`. If no match, list the commands and ask the user.

| Input pattern | Command file |
|---|---|
| `tasks <plan_file> [tasks_folder] [tracking_file]` | `commands/Plan-2-Tasks.md` |
| `scaffold <phase_id> <plan_file> [tasks_folder] [tracking_file]` | `commands/ScaffoldPhase.md` |
| `exec <phase_id> <plan_file> [tasks_folder] [tracking_file]` | `commands/ExecPhase.md` |
| `phase <phase_id> <plan_file> [tasks_folder] [tracking_file]` | `commands/Phase.md` |
| `close-phase <phase_id> [plan_file] [tasks_folder]` | `commands/ClosePhase.md` |
| `close-plan <plan_file> [tasks_folder]` | `commands/ClosePlan.md` |
| `task <task_id> <plan_file> [tasks_folder] [tracking_file]` | `commands/ExecTask.md` |
| `e2e <plan_file> [tasks_folder] [tracking_file] [--stop-after <target>] [--skip-plan-2-tasks] [--arch]` | `commands/E2E.md` |
| `gen-plan <feature request>` | `commands/GenPlan.md` |
| `fact-check [target]` | `commands/FactCheck.md` |
| `plan-review <plan_file> [codebase]` | `commands/PlanReview.md` |
| `diff-review [scope]` | `commands/DiffReview.md` |
| `arch <path...>` / `arch --feature <plan_file>` (alias `architecture`) | `commands/Architecture.md` |
| `explain <symbol\|file\|flow\|concept>` | `commands/Explain.md` |
| `install [--dry-run]` | `commands/Install.md` |

Templates live in `templates/`. Codex agent prompt profiles live in `agents/` (see § Codex Agent Profiles). On-demand references live in `references/`.

---

## Shared Architecture

### Folder Conventions
- `<tasks_folder>` defaults to `dev/plans/<plan_file_stem>/` — the per-plan home for all derived artifacts (task JSONs, context summaries, tracker, gates, reviews, issue map, handoffs). The plan markdown itself stays at `dev/plans/<plan_file_stem>.md`, beside this folder.
- `<tracking_file>` defaults to `<tasks_folder>/tasks-tracker.md`
- `<gates_folder>` is always `<tasks_folder>/gates/`
- `<reviews_folder>` is always `<tasks_folder>/reviews/` — rendered review reports (`plan-review`, and `diff-review` when run against a plan) land here instead of the transient `dev/diagrams/`.

### Branch & Worktree Model
The pipeline isolates each plan on its own branch + git worktree so phases merge cleanly and `main` history stays squash-clean:

- **Plan branch `<plan_slug>`** — created at plan approval (`gen-plan` Step 6) from `main`, or from the current branch when `branch=this` is passed to `gen-plan`. Created **without checkout** (`phase_git.sh plan-branch`) so the worktree can claim it.
- **Plan worktree** — `Plan-2-Tasks` adds a worktree at `<repo-parent>/WorkTrees/<repo>-<plan_slug>` on `<plan_slug>` (`phase_git.sh worktree`). **All derived artifacts and all phase work happen inside this worktree** (it owns `dev/plans/<stem>/`); the main checkout stays on whatever branch it was.
- **Phase branches `<plan_slug>_phase-<N>`** — `ScaffoldPhase`/`ExecPhase` fork each phase from the plan branch (`phase_git.sh branch <slug> <N> --from <slug>`); the phase merges back into `<plan_slug>`.
- **Merge flow:** `<plan_slug>_phase-<N>` → `<plan_slug>` (merge commit) → `main` (squash). The squash keeps `main` to one commit per plan.
- **Draft PRs** (`draft_pr.sh` — best-effort, idempotent, opened in-band at ExecPhase Step 10 and by the `phase-close.sh` backstop): each phase handoff opens `<slug>_phase-<N>` → `<slug>` (label `merge:commit`); plan close opens `<slug>` → `main` (label `merge:squash`). GitHub can't pin a per-PR merge method, so the **label** records intent and the eventual `gh pr merge --merge`/`--squash` applies it. A handoff *update* rides the existing PR — no new PR.

**Worktree discipline (every step, once a plan worktree exists):**
- **Target the worktree explicitly for all git + file ops** — your shell's cwd can silently revert to the main checkout between tool calls, so never trust it. Use `git -C <worktree> …` for any ad-hoc git, and write to absolute paths under `<worktree>/`. The bundled scripts already enforce this: `phase_git.sh branch`, `draft_pr.sh`, and `phase-close.sh` resolve the plan worktree from the slug/map and run `git -C <worktree>` themselves, so a phase branch can't be created in the main checkout by accident.
- **Tests run against main's env, the worktree's source** — a fresh worktree usually has no working `uv`/`.venv`. For Gate C, use the **main checkout's** environment and shadow in the worktree's code: `PYTHONPATH=<worktree> <main_checkout>/.venv/bin/python -m pytest <task tests>` (or `cd <main_checkout> && PYTHONPATH=<worktree> uv run pytest …`). Don't `uv sync`/recreate a venv inside the worktree just to test.

### Plan Reading Discipline (token discipline)
- Plan-2-Tasks reads `<plan_file>` in full — once.
- ScaffoldPhase / ExecPhase / ExecTask read `Phase_<N>_context_summary.md` first. Open `<plan_file>` only on the specific `plan_lines` ranges referenced by tasks in scope. Never re-read the plan in full.

### Codex Agent JSON Passing Discipline
Never paste full task JSON content into a Codex agent prompt. Always pass the file path and the field list it needs. The receiving agent reads the file itself. This eliminates re-paying multi-KB JSON on every gate retry.

### Codex Agent Assignment (single source of truth)

Use `references/codex-agent-routing.json` as the canonical routing policy. Compute `complexity` and `risk` once per task during Plan-2-Tasks, store both values in the task JSON, and never recompute them in a phase or subagent. Score with `references/codex-routing-scoring.md`.

Before every Codex subagent dispatch:

1. For a task dispatch, identify its task JSON path; the resolver must read `task_id`, `complexity`, and `risk` directly from that file. For a phase orchestrator, use the maximum stored complexity and maximum stored risk across that phase's tasks.
2. Select one role: `implementer`, `orchestrator`, `spec_reviewer`, `domain_reviewer`, `explorer`, or `mechanical_read_only`.
3. For every task dispatch, invoke `<skill_root>/scripts/resolve_codex_agent.py --dispatcher-capabilities <skill_root>/runtime/subagent-dispatch-capabilities.json --task-json <task-json> --role <role> --evidence-file <same-task-json> --purpose <purpose>`. Raw `--complexity/--risk` inputs are reserved for phase aggregation and diagnostics; they cannot write evidence into a task JSON.
4. Parse the JSON output and dispatch using `recommended_mode` and `dispatch`:
   - `native_exact`: call the native dispatcher with `dispatch.model`, `dispatch.reasoning_effort`, and, only when its schema supports it, `dispatch.sandbox_mode`; load `dispatch.prompt_file` as the exact role contract and append task-specific inputs.
   - `native_model_prompt`: call the native dispatcher with `dispatch.model` and the exact role prompt. Pass effort or sandbox only when those keys are present. Preserve the returned degradation fields in evidence.
   - `external_exact`: invoke `dispatch.launcher` with the returned model, reasoning effort, sandbox, exact prompt file, and task inputs.
   - `unavailable`: block before implementation or a gate; do not fabricate a result.
5. Confirm the resolver atomically appended its complete output, dispatch purpose, and timestamp to the task JSON or phase routing-evidence file.
6. Never pass `profile_projection.name` as `agent_type` unless the capability record explicitly confirms custom-profile support. The normal native contract is supported base model + exact canonical role prompt + task inputs.
7. Do not substitute another model, effort, prompt, or execution mode. Treat resolver, validation, launcher, and dispatch-availability failures as fatal. Never fall back silently.

The routing JSON selects execution requirements plus an audit profile projection. Canonical Markdown in `agents/` is the sole source of truth for durable role behavior. The installer serializes that behavior into `.codex/agents/*.toml` for external launch, audit, and consistency validation. The bounded `mechanical_read_only` route uses Luna only for `complexity <= 2` and `risk <= 2`; larger mechanical read-only tasks route through the normal explorer tier. Reviewers never use Luna and apply the reviewer floor defined by the policy.

A review dispatch is valid only when it uses the resolver-selected base model, every supported required control, the exact canonical role prompt, and all task inputs. Validity never depends on a native dispatcher accepting a generated TOML filename.

**Sandbox containment is never degradable for a read-only role.** `dispatch_policy` states per role which controls may go uncontrolled when the dispatcher cannot enforce them: `allow_uncontrolled_effort` trades reasoning quality, `allow_uncontrolled_sandbox` trades containment. The four read-only roles (`spec_reviewer`, `domain_reviewer`, `explorer`, `mechanical_read_only`) set the latter to `false` and the resolver rejects any policy that says otherwise — an uncontrolled sandbox would let them inherit the caller's `workspace-write` access, silently turning a read-only reviewer into a writer. On a dispatcher without sandbox override they route to the exact external launcher, or block as `unavailable`; they never dispatch natively. `implementer` and `orchestrator` already pin `workspace-write`, so inheriting the caller's sandbox is not an escalation and they stay dispatchable.

**External launcher availability is measured, never advertised.** `external_dispatch.available` says only that a launcher is configured and that its interface exposes the required controls. Whether this environment permits the launch is a separate fact, measured by `scripts/probe_codex_dispatch.py` and stored as `runtime_executable`; an unprobed record counts as not executable, and `_external_exact_supported` requires the measured value. This matters because a dispatcher exposing neither per-child reasoning effort nor a sandbox override routes *every* role externally — so a launcher trusted on the strength of its `--help` output blocks the whole pipeline at the first gate rather than at install. The capability record is session-bound via `environment_fingerprint`: run `probe_codex_dispatch.py --check` before a run that did not just install, and re-probe when it fails. See `references/recovery.md` § Routing blocked as `unavailable`.

For retries and repeated gates, invoke the resolver again from the same stored scores and record a new evidence entry. Both ExecPhase and ExecTask reference this rule by name; do not duplicate or alter the policy inline.

For workflows that need a standalone immutable routing record, copy `templates/task-routing-manifest.json`, fill it from the stored task scores and active policy version, then invoke the resolver with `--manifest <path>`. The resolver rejects combined-score or policy-version drift.

### GitHub Issue Map
Single bridge file at `<tasks_folder>/github_issue_map.json`:

```json
{
  "plan_file": "dev/plans/my_plan.md",
  "plan_slug": "my-plan",
  "plan_overview_issue": 10,
  "phases": { "1": { "issue_number": 11 }, "2": { "issue_number": 12 } },
  "repo": "owner/repo-name"
}
```

Plan-2-Tasks creates this. Subsequent commands read it. **There is no per-task issue layer** — tasks are tracked as checkboxes inside the phase issue body. This is the single largest cost reduction vs Aut_Faciam.

**Project sync (gated):** when `autviam_c_config.json` → `project` names a board (not `"disable"`), Plan-2-Tasks § 7g appends a `project` block (`owner`, `number`, `overview_item`, `phase_items`) to this file, and Scaffold/ExecPhase keep each item's **Status** in step with the issue lifecycle (Todo → Done, or Blocked on gate-cap-hit). See `references/project_sync.md`. Absent or `"disable"` → no Project calls at all.

### Label Taxonomy (names only — colors and creation live in Plan-2-Tasks § 7a)
`plan:<slug>`, `plan-issue`, `phase-issue`, `not-scaffolded`, `scaffolded`, `phase-N`, `in-progress`, `done`, `gate-cap-hit`.

Per-task gate-pass labels are gone (that data lives in task JSON + gate file).

### Gate Failure Cap (new — non-negotiable)
Per task, per gate: **maximum 3 failed attempts**. On the 4th failed attempt for the same gate the task is marked `gate-cap-hit` and execution halts. See ExecPhase Step 7 and ExecTask Step 5 for the stop behavior — including the rule that in-flight parallel tasks must be allowed to finish before the user is prompted.

### Idempotency
First step for any command with GitHub steps: `gh auth status`. If it fails, skip all GitHub steps and produce local artifacts only — the local pipeline is the source of truth.

Before creating any issue, check `github_issue_map.json` and skip if already present. Save the map after each successful creation.

### Tracker Remains Authoritative
The markdown tracker is the source of truth. GitHub issues are a projection.

### On-Demand References
- `references/codex-agent-routing.json` — canonical Path-2 score/role-to-profile policy. Read only when inspecting or changing routing; normal dispatches call the resolver.
- `references/codex-agent-routing.schema.json` — machine-readable routing-policy shape. Read when changing or diagnosing policy configuration.
- `references/codex-routing-scoring.md` — complexity/risk rubric plus routing-evidence format. Read during Plan-2-Tasks scoring or a legacy score backfill.
- `references/recovery.md` — rollback procedure for unrecoverable tasks/branches. Read only on repeated Gate C failure or gate cap.
- `references/issue_body_updates.md` — canonical fetch→Write→Edit→push pattern for GitHub issue body mutations. Read when first touching an issue body in a session.
- `references/failure_modes.md` — failure-mode taxonomy for gate entries. Read when first writing a gate failure entry.
- `references/report_shell.md` — the one frozen HTML shell every report (`gen-plan` companion, `plan-review`, `diff-review`, `fact-check`, `arch`, `explain`) renders into. Read once per session, the first time you build a report.
- `references/mermaid_module.md` — opt-in zoom/pan Mermaid topology block, theme-wired to the frozen shell. Read when a report (`arch`, `explain`, or a flow in `plan-review`/`diff-review`) needs a diagram with real edges.
- `references/project_sync.md` — gated GitHub Project board sync mechanics (active only when `autviam_c_config.json` → `project` names a board). Read when wiring or refreshing Project item status.

### Codex Agent Profiles
Six canonical Markdown prompt sources provide the durable role bodies used by the runtime profile installer:

| Prompt profile | Runtime role | Role | Invoked from |
|---|---|---|---|
| `autviam-implementer` | `implementer` | Implementation behavior | ScaffoldPhase, ExecPhase, ExecTask, orchestrator |
| `autviam-spec-reviewer` | `spec_reviewer` | Gate A (spec compliance) | ExecPhase, ExecTask, orchestrator |
| `autviam-domain-reviewer` | `domain_reviewer` | Gate B (domain quality) | ExecPhase, ExecTask, orchestrator |
| `autviam-explorer` | `explorer` | Read-only specialist work | specialist dispatch |
| `autviam-search` | `mechanical_read_only` | Bounded mechanical search | search dispatch |
| `autviam-phase-orchestrator` | `orchestrator` | Runs ScaffoldPhase + ExecPhase for one phase, returns a JSON summary | E2E |

Run `AutViam_C install` once in each consumer repository to generate the nineteen TOML projections under `.codex/agents/`: four implementers, four orchestrators, three Gate A reviewers, three Gate B reviewers, four explorers, and one mechanical-search profile. The installer pins model, effort, and sandbox for external launch and audit consistency. Installation also writes `<skill_root>/runtime/subagent-dispatch-capabilities.json` from the active dispatcher schema and validates every route against it.

At dispatch time, follow the resolver-selected mode. Native dispatch loads the returned canonical Markdown prompt and adds task-specific data. External dispatch uses the exact launcher settings and may consume the TOML projection. Inline reviewer fallback is prohibited because it bypasses routing evidence and independent review. A TOML profile is never presumed to be a native nested-agent identity.

The implementer's durable behavior comes from `agents/autviam-implementer.md`; `templates/task_instructions_template.md` carries only per-dispatch task and phase data.

### Bundled scripts

Fourteen helper scripts live at `<skill_root>/scripts/` (reference them as `<skill_root>/scripts/<name>`). The LLM keeps the judgment work (objectives, scoring, gate verdicts, prose attempt blocks, Decision narrative) around deterministic plumbing.

| Script | Owns |
|---|---|
| `routing_core.py` | **Generated — canonical source is `skills/shared/scripts/routing_core.py`, shared with AutViam.** Atomic JSON/text writes, the stale-breaking directory lock (`evidence_lock` wraps it), score validation, and hashing. Never hand-edit the per-skill copy. |
| `expand_codex_agents.py` | Deprecated compatibility entry point; always exits nonzero and directs callers to canonical `install_agent_profiles.py`, because template-derived profiles cannot pass exact managed-source validation. Scheduled for removal after 2026-10-01. |
| `install_agent_profiles.py` | Idempotently generates nineteen external-launch/audit TOML projections from six canonical role sources in the consumer repo's `.codex/agents/`, preserving unmanaged collisions and pinning model, effort, sandbox, and Codex serialization. |
| `resolve_codex_agent.py` | Fail-closed resolver: validates stored scores, capability probe, policy, role, prompt, profile projection, reviewer floor, and Luna boundary; emits an executable native/external dispatch specification and evidence. |
| `validate_codex_agent_routing.py` | Exhaustively validates all 150 score-role combinations, policy and capability shape, exact canonical-source rendering, executable dispatch availability, controlled-vs-uncontrolled fields, reviewer floor, and Luna boundary. |
| `init_plan.sh` | Per-plan plumbing for Plan-2-Tasks Step 7: slug derivation, folder scaffolding, label diff/create, `gh issue create` (prints the number), issue-map write, task-JSON `github_issue` annotation. |
| `issue_body.sh` | The two `gh` halves of the canonical issue-body roundtrip (`fetch` → LLM edits → `push`) plus label-only / state / close flags. The LLM still does the Edit between fetch and push — never `sed -i`. |
| `gate_state.py` | Gate-file + task-JSON machine state: failure counting and the 3-failure cap (`cap-check`), counters-line sync, completion writeback, status set, rollback reset, last-good Gate C SHA, Session Reset Packet rows. |
| `phase_git.sh` | Phase branch create/checkout with a dirty-tree guard; `plan-branch` (create the plan branch `<slug>`, no checkout); `worktree` (add the plan worktree at `<repo-parent>/WorkTrees/<repo>-<slug>`); reverse-order `git revert` rollback (never `reset --hard` on a shared branch). |
| `match_specialists.sh` | Config-driven specialist/skill matcher — emits the matched `autviam_c_config.json` entries whose `trigger_patterns` hit the diff (deterministic, no LLM at trigger time). |
| `project_sync.sh` | The gated GitHub Project wrapper (`resolve`/`add`/`status`): board resolution from `autviam_c_config.json` → `project` (4 forms + name→number), idempotency, and the `project`-block bookkeeping in `github_issue_map.json`. Self-gates to a no-op when project sync is off; wraps `update_tracker.sh`. See `references/project_sync.md`. |
| `update_tracker.sh` | Low-level GitHub Project primitive (one `gh project item-edit` per call, IDs cached) wrapped by `project_sync.sh`. Not called directly by the commands. |
| `phase-close.sh` | **PostToolUse hook backstop** (not command-invoked): on a `Handoff_Phase_<N>.md` write, idempotently closes the completed phase's issue, sets its Project item to Done, and opens the phase draft PR (via `draft_pr.sh`). Wire it per Install § Step 7. No-op for non-handoff writes; idempotent with ExecPhase Step 10b. |
| `draft_pr.sh` | Opens the idempotent draft PR on handoff: `phase` (`<slug>_phase-<N>`→`<slug>`, label `merge:commit`) and `plan` (`<slug>`→`main`, label `merge:squash`). Body = the handoff's Phase-N completion-summary section + a repo-relative link to the handoff. gh-gated, best-effort. |

---

## Task JSON Schema

Each task is a JSON file in `<tasks_folder>/json/`. Template: `templates/template.json`.

When GitHub integration is active each task's JSON has:

```json
"github_issue": { "phase_issue": 11, "repo": "owner/repo-name" }
```

No `task_issue` field — phase-issues-only.

### Field ownership

| Command | Owns these fields |
|---|---|
| Plan-2-Tasks | `task_id`, `title`, `phase`, `objective`, `plan_file`, `plan_lines`, `plan_assets`, `blocked_by`, `blocks`, `scope`, `implementation_steps`, `deliverables`, `acceptance_criteria`, `risks`, `complexity`, `risk`, `routing_evidence=[]`, `test_plan.*` (initial), `status="pending"` |
| ScaffoldPhase | `routing_evidence` (append), `test_plan.*` (refined), `test_artifacts`, `verification_commands` |
| ExecPhase / ExecTask | `routing_evidence` (append), `status`, `completion_date`, `test_completion`, `review_score`, `review_breakdown`, `review_status`, `implementation_branch`, `completion_notes` |

### Valid `asset_type` values for `plan_assets`
`code_snippet`, `equation`, `diagram`, `table`, `constraint`.

---

## Post-Install Configuration (`autviam_c_config.json`)

Run `AutViam_C install` once per repo to generate and validate the external-launch/audit profiles and active dispatcher capability record, then wire up optional repo-specific Codex prompt profiles and skills. The command scans optional repo-local profile and skill folders, proposes trigger patterns, gets user approval, and writes `<skill_root>/autviam_c_config.json`.

**What the config enables:**
- `domain_reviewer.specialists` — read-only prompt lenses used during Gate B when the diff touches matching files. Each specialist's findings carry the same weight as the domain reviewer's own findings. **By default the routed domain reviewer applies each lens inline** (reading its `prompt_file`) rather than adding a nested dispatch. See `agents/autviam-domain-reviewer.md`.
- `spec_reviewer.specialists` — read-only prompt lenses used during Gate A (rare; most repos leave this empty). Any separate specialist dispatch must itself resolve role `explorer` from the task's stored scores.
- `implementer.skills` — skills surfaced to the implementer template when matching files changed.

**Runtime mechanics (deterministic — no LLM at trigger time):**

Before dispatching the domain reviewer, ExecPhase/ExecTask runs:
```bash
<skill_root>/scripts/match_specialists.sh <skill_root>/autviam_c_config.json domain_reviewer.specialists <base_sha> <head_sha>
```
which emits the JSON array of config entries whose `trigger_patterns` match at least one file in
`git diff --name-only <base_sha>..<head_sha>` (OR logic). That array is the `specialist_agents` list
injected into the domain reviewer prompt. An empty array (no config, empty section, or no match) means
standard review — fully backward compatible with repos that have no config. The implementer skill check
and Gate A spec-reviewer specialist check use the same script with the `implementer.skills` /
`spec_reviewer.specialists` section.

**The config is repo-local.** It is never part of the upstream AutViam_C skill definition.
Template: `templates/autviam_c_config_template.json`.
