---
name: AutViam
description: >
  Claude-native phased plan execution with immutable score routing, recursive
  subagents, depth-aware tickets, test scaffolding, quality gates, and
  phase-level GitHub tracking. Use for /AutViam.
---

# AutViam — Plan → Scaffold → Execute

Self-contained pipeline turning a markdown plan into tracked, executed, verified work. Successor to Aut_Faciam tuned for token efficiency and Claude Code review agents.

## Routing

Parse the first token of `$@` and read the matching command file from `commands/`. If no match, list the four commands and ask the user.

| Input pattern | Command file |
|---|---|
| `tasks <plan_file> [tasks_folder] [tracking_file]` | `commands/Plan-2-Tasks.md` |
| `scaffold <phase_id> <plan_file> [tasks_folder] [tracking_file]` | `commands/ScaffoldPhase.md` |
| `exec <phase_id> <plan_file> [tasks_folder] [tracking_file]` | `commands/ExecPhase.md` |
| `phase <phase_id> <plan_file> [tasks_folder] [tracking_file]` | `commands/Phase.md` |
| `close-phase <phase_id> [plan_file] [tasks_folder]` | `commands/ClosePhase.md` |
| `close-plan <plan_file> [tasks_folder]` | `commands/ClosePlan.md` |
| `task <task_id> <plan_file> [tasks_folder] [tracking_file]` | `commands/ExecTask.md` |
| `e2e <plan_file> [tasks_folder] [tracking_file] [--stop-after <target>] [--skip-plan-2-tasks]` | `commands/E2E.md` |
| `gen-plan <feature request>` | `commands/GenPlan.md` |
| `fact-check [target]` | `commands/FactCheck.md` |
| `plan-review <plan_file> [codebase]` | `commands/PlanReview.md` |
| `diff-review [scope]` | `commands/DiffReview.md` |
| `arch <path...>` / `arch --feature <plan_file>` (alias `architecture`) | `commands/Architecture.md` |
| `explain <symbol\|file\|flow\|concept>` | `commands/Explain.md` |
| `install [--dry-run]` | `commands/Install.md` |

Templates live in `templates/`. Review agents live in `agents/` (see § Reviewer Agents). On-demand references live in `references/`.

---

## Shared Architecture

### Bundled scripts

Eighteen helper scripts live at `<skill_root>/scripts/`. Existing plan/GitHub scripts retain their responsibilities; the routing scripts deterministically generate Claude agents, resolve immutable task routing, issue and validate depth-aware tickets, audit subagent starts, check environment overrides, and record live depth probes.

| Script | Owns |
|---|---|
| `install_claude_agent_profiles.py` | Generates and exact-validates 22 model/effort/capability-specific `.claude/agents/*.md` profiles from six canonical prompt sources; safely merges hooks/config and reports restart requirements. |
| `resolve_claude_agent.py` | Reads persistent task routing, validates role/purpose/topology/depth, selects one generated agent, issues a single-use ticket, and appends serialized evidence. |
| `validate_claude_agent_routing.py` | Exhaustively checks 175 score-role-capability routes, exact generated content, reviewer floor, Haiku boundary, tools, duplicate names, and active command usage. |
| `validate_agent_dispatch.py` | Blocking `PreToolUse` hook for AutViam Agent calls; validates and consumes tickets and rejects wrong agents, reuse, expiry, and depth overruns. |
| `check_claude_routing_environment.py` | Blocks `CLAUDE_CODE_SUBAGENT_MODEL` / `CLAUDE_CODE_EFFORT_LEVEL` in strict mode or labels evidence externally overridden in permissive mode. |
| `probe_nested_dispatch.py` | Prepares and validates evidence from a bounded no-write recursive Agent probe, then records the verified maximum depth and resolves auto mode. |
| `audit_subagent_start.py` | Audit-only `SubagentStart` logger for generated AutViam agent identity and runtime-reported depth. |
| `routing_core.py` | **Generated — canonical source is `skills/shared/scripts/routing_core.py`, shared with AutViam_C.** Atomic JSON/text writes, the stale-breaking directory lock, score validation, and hashing. Never hand-edit the per-skill copy. |
| `claude_routing_common.py` | Claude-specific helpers — ticket signing, frontmatter parsing, legacy-config normalization — plus re-exports of `routing_core` so existing imports are unchanged. |
| `init_plan.sh` | Plan-2-Tasks Step 7 plumbing: `slug`, `dirs` (json/gates/reviews), `labels` (diff-only create), `create-issue` (prints #), `map`, `annotate`. |
| `issue_body.sh` | The canonical issue-body roundtrip `gh` halves: `fetch`, `push` (body + label swap + close/state flags), `label` (label-only). LLM does the Edit/MultiEdit between fetch and push. |
| `gate_state.py` | Gate-file + task-JSON state: `init`/`init-task`, `count`/`cap-check`/`sync-counters` (the 3-failure cap, durable from the file), `complete`/`set-status`/`reset-task`, `last-good-sha`, `reset-packet`. |
| `phase_git.sh` | Deterministic git sequences: `branch` (phase branch + dirty-tree guard), `plan-branch` (create the plan branch `<slug>`, no checkout), `worktree` (add the plan worktree at `<repo-parent>/WorkTrees/<repo>-<slug>`), `revert` (reverse-order `git revert`, never `reset --hard`). |
| `match_specialists.sh` | Config-driven specialist/skill matcher: emits the JSON array of `autviam_config.json` entries whose `trigger_patterns` hit the diff. Absent config/section → `[]`. |
| `project_sync.sh` | The gated GitHub-Project writer (the high-level entry point): `resolve` (board OFF/owner+number), `add` (board item + Plan/Phase + `project`-block cache, idempotent), `status` (Status from the map). Self-gates on `autviam_config.json` → `project`; wraps `update_tracker.sh`. See `references/project_sync.md`. |
| `update_tracker.sh` | Low-level Project primitive `project_sync.sh` calls — one `gh project item-edit` per `add`/`set`, IDs cached. Callers use `project_sync.sh`; this is the wrapped primitive. |
| `phase-close.sh` | **PostToolUse hook backstop** (not command-invoked): on a `Handoff_Phase_<N>.md` write, idempotently closes the completed phase's issue (label swap in-progress→done), sets its Project item to Done, and opens the phase draft PR (via `draft_pr.sh`). Wire it per Install § Step 7. No-op for non-handoff writes; idempotent with ExecPhase Step 10b. |
| `draft_pr.sh` | Opens the idempotent draft PR on handoff: `phase` (`<slug>_phase-<N>`→`<slug>`, label `merge:commit`) and `plan` (`<slug>`→`main`, label `merge:squash`). Body = the handoff's Phase-N completion-summary section + a repo-relative link to the handoff. gh-gated, best-effort. |

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

### Subagent JSON Passing Discipline
Never paste full task JSON content into a subagent prompt. Always pass the file path and the field list it needs. The subagent runs one Read. This eliminates re-paying multi-KB JSON on every gate retry.

### Claude Agent Assignment (single source of truth)

Use `references/claude-agent-routing.json` as the routing policy and `references/claude-routing-scoring.md` only when Plan-2-Tasks scores a task or an explicit legacy initializer fills an absent routing object. Never rescore during execution.

Before every Agent dispatch:

1. Run `check_claude_routing_environment.py`; strict-mode overrides are fatal.
2. Invoke `resolve_claude_agent.py` with the task JSON, role, purpose, current/next depth, optional parent ticket, and task evidence path. For a phase orchestrator, pass `--phase-id` and the phase evidence file; the resolver derives maximum scores from the canonical phase task JSONs.
3. Parse its JSON and dispatch exactly `agent`; include `autviam_routing_ticket: <ticket_path>` in the prompt. Never pass an Agent `model` argument.
4. Treat missing routing, policy mismatch, invalid purpose/edge/capability, exhausted blocking depth, missing profile, hook rejection, or dispatch failure as fatal. Do not use a legacy base agent or generic fallback.

The policy selects Sonnet medium/high or Opus high/xhigh from immutable 1–5 scores. Gate reviewers apply a floor: routine work uses Sonnet high; moderate/elevated work uses Opus high. Haiku is reachable only through `mechanical_read_only` with both scores at most 2 and never writes or reviews.

`autviam_config.json` owns topology, not models: `nested_dispatch.mode`, `max_depth`, detected/declared `runtime_max_depth`, phase-orchestrator child permissions, specialist mode (`nested|caller|off`), and depth exhaustion (`caller|block`). The resolver requires each child edge to be allowed and each depth to fit both ceilings.

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

**Project sync (gated):** when `autviam_config.json` → `project` names a board (not `"disable"`), Plan-2-Tasks § 7g appends a `project` block (`owner`, `number`, `overview_item`, `phase_items`) to this file, and Scaffold/ExecPhase keep each item's **Status** in step with the issue lifecycle (Todo → Done, or Blocked on gate-cap-hit). See `references/project_sync.md`. Absent or `"disable"` → no Project calls at all.

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
- `references/recovery.md` — rollback procedure for unrecoverable tasks/branches. Read only on repeated Gate C failure or gate cap.
- `references/issue_body_updates.md` — canonical fetch→Write→Edit→push pattern for GitHub issue body mutations. Read when first touching an issue body in a session.
- `references/failure_modes.md` — failure-mode taxonomy for gate entries. Read when first writing a gate failure entry.
- `references/report_shell.md` — the one frozen HTML shell every report (`gen-plan` companion, `plan-review`, `diff-review`, `fact-check`, `arch`, `explain`) renders into. Read once per session, the first time you build a report.
- `references/mermaid_module.md` — opt-in zoom/pan Mermaid topology block, theme-wired to the frozen shell. Read when a report (`arch`, `explain`, or a flow in `plan-review`/`diff-review`) needs a diagram with real edges.
- `references/project_sync.md` — gated GitHub Project board sync mechanics (active only when `autviam_config.json` → `project` names a board). Read when wiring or refreshing Project item status.

### Subagents
Six canonical Claude prompt sources are defined in `agents/`:

| Agent | Role | Invoked from |
|---|---|---|
| `autviam-implementer` | Implementation rules | generated implementer profiles |
| `autviam-spec-reviewer` | Gate A | generated leaf Gate A profiles |
| `autviam-domain-reviewer` | Gate B | generated flat/nested Gate B profiles |
| `autviam-explorer` | Read-only specialist work | generated explorer profiles |
| `autviam-search` | Mechanical read-only work | generated Haiku profile |
| `autviam-phase-orchestrator` | One routed phase | generated orchestrator profiles |

**Install once per consuming repo:** run `scripts/install_claude_agent_profiles.py`. It generates 22 explicit profiles in `.claude/agents/`; canonical source files are prompt inputs and must not be invoked directly. Restart or reload Claude Code after generation. Missing generated profiles have no fallback.

The implementer remains template-based (`templates/task_instructions_template.md`) because per-phase context is injected per dispatch.

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
| Plan-2-Tasks | `task_id`, task/spec fields, `routing.*`, `routing_evidence=[]`, `test_plan.*` (initial), `status="pending"` |
| ScaffoldPhase | `routing_evidence` (append), `test_plan.*` (refined), `test_artifacts`, `verification_commands` |
| ExecPhase / ExecTask | `routing_evidence` (append), completion, tests, review, branch, and notes fields; never `routing.*` |

### Valid `asset_type` values for `plan_assets`
`code_snippet`, `equation`, `diagram`, `table`, `constraint`.

---

## Post-Install Configuration (`autviam_config.json`)

Run `/AutViam install` once per repo to generate/validate runtime profiles and hooks, migrate legacy config, and wire repo-specific specialists.

**What the config enables:**
- `nested_dispatch.domain_reviewer.specialists` selects `nested`, `caller`, or `off` behavior for matched Gate B lenses. Nested dispatch uses routed explorer children; caller mode passes routed explorer reports into flat Gate B; off runs standard review only.
- `spec_reviewer.specialists` — agents dispatched during Gate A (rare; most repos leave
  this empty).
- `implementer.skills` — skills surfaced to the implementer template (future).

**Runtime mechanics (deterministic — no LLM at trigger time):**

For `nested` and `caller`, ExecPhase/ExecTask runs:
```bash
<skill_root>/scripts/match_specialists.sh <skill_root>/autviam_config.json domain_reviewer.specialists <base_sha> <head_sha>
```
which emits the JSON array of config entries whose `trigger_patterns` match at least one file in
`git diff --name-only <base_sha>..<head_sha>` (OR logic). Nested mode injects that array as
`specialist_agents`; caller mode dispatches routed explorers and injects only their `specialist_reports`;
off mode skips matching and injects neither. An empty array means standard review. The implementer skill check
and Gate A spec-reviewer specialist check use the same script with the `implementer.skills` /
`spec_reviewer.specialists` section.

**The config is repo-local.** It is never part of the upstream AutViam skill definition.
Template: `templates/autviam_config_template.json`.

---

$@
