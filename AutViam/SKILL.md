---
name: AutViam
description: >
  Token-lean plan-to-execution pipeline. Decomposes plans into phased tasks,
  scaffolds test coverage, executes through quality gates with a hard cap of
  3 failures per gate, and mirrors progress to GitHub at the phase level only.
  Successor to Aut_Faciam — same shape, ~40% lower token cost, agent-based reviewers,
  phase-only GitHub issues. Use when the user invokes /AutViam, or mentions planning,
  scaffolding, or executing phases via Plan-2-Tasks, ScaffoldPhase, ExecPhase, ExecTask.
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

Six helper scripts live at `<skill_root>/scripts/` and own the **deterministic plumbing** the commands used to do by hand (slug/label/path work, gate counting, JSON writeback, git sequences, the `gh` calls). They run without an install step — reference them as `<skill_root>/scripts/<name>`. The LLM keeps Write/Edit for everything reviewable (issue bodies between fetch/push, gate prose+JSON attempt blocks, the Decision narrative).

| Script | Owns |
|---|---|
| `init_plan.sh` | Plan-2-Tasks Step 7 plumbing: `slug`, `dirs` (json/gates/reviews), `labels` (diff-only create), `create-issue` (prints #), `map`, `annotate`. |
| `issue_body.sh` | The canonical issue-body roundtrip `gh` halves: `fetch`, `push` (body + label swap + close/state flags), `label` (label-only). LLM does the Edit/MultiEdit between fetch and push. |
| `gate_state.py` | Gate-file + task-JSON state: `init`/`init-task`, `count`/`cap-check`/`sync-counters` (the 3-failure cap, durable from the file), `complete`/`set-status`/`reset-task`, `last-good-sha`, `reset-packet`. |
| `phase_git.sh` | Deterministic git sequences: `branch` (canonical name + dirty-tree guard), `revert` (reverse-order `git revert`, never `reset --hard`). |
| `match_specialists.sh` | Config-driven specialist/skill matcher: emits the JSON array of `autviam_config.json` entries whose `trigger_patterns` hit the diff. Absent config/section → `[]`. |
| `update_tracker.sh` | GitHub Project (board) sync — `add`/`set` item fields. Gated on `autviam_config.json` → `project` (see `references/project_sync.md`). |

### Folder Conventions
- `<tasks_folder>` defaults to `dev/plans/<plan_file_stem>/` — the per-plan home for all derived artifacts (task JSONs, context summaries, tracker, gates, reviews, issue map, handoffs). The plan markdown itself stays at `dev/plans/<plan_file_stem>.md`, beside this folder.
- `<tracking_file>` defaults to `<tasks_folder>/tasks-tracker.md`
- `<gates_folder>` is always `<tasks_folder>/gates/`
- `<reviews_folder>` is always `<tasks_folder>/reviews/` — rendered review reports (`plan-review`, and `diff-review` when run against a plan) land here instead of the transient `~/.agent/diagrams/`.

### Plan Reading Discipline (token discipline)
- Plan-2-Tasks reads `<plan_file>` in full — once.
- ScaffoldPhase / ExecPhase / ExecTask read `Phase_<N>_context_summary.md` first. Open `<plan_file>` only on the specific `plan_lines` ranges referenced by tasks in scope. Never re-read the plan in full.

### Subagent JSON Passing Discipline
Never paste full task JSON content into a subagent prompt. Always pass the file path and the field list it needs. The subagent runs one Read. This eliminates re-paying multi-KB JSON on every gate retry.

### Model Assignment (single source of truth)
Computed once per task from `complexity + risk` (each 1–5):
- combined > 6 → **Opus** for implementer and reviewer agents
- complexity ≥ 3 OR risk ≥ 3 → **Sonnet or Opus**
- **Haiku** is permitted only for read-only / search subtasks (e.g. test discovery), never for implementer or reviewer roles

Both ExecPhase and ExecTask reference this rule by name; do not re-state it inline.

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

### Subagents
Three named Claude Code subagents are defined in `agents/`:

| Agent | Role | Invoked from |
|---|---|---|
| `autviam-spec-reviewer` | Gate A (spec compliance) | ExecPhase, ExecTask, orchestrator |
| `autviam-domain-reviewer` | Gate B (domain quality) | ExecPhase, ExecTask, orchestrator |
| `autviam-phase-orchestrator` | Runs ScaffoldPhase + ExecPhase for one phase, returns a JSON summary | E2E |

**Install (once per consuming repo):** symlink or copy `agents/*.md` into `.claude/agents/` so Claude Code picks them up. If a reviewer agent is missing, ExecPhase/ExecTask fall back to inlined Task-tool dispatch with the agent's system prompt. The orchestrator has no fallback — if it's missing or nested dispatch is blocked, E2E halts on its pre-flight check (see `commands/E2E.md` § Nested-Dispatch Pre-flight).

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
| Plan-2-Tasks | `task_id`, `title`, `phase`, `objective`, `plan_file`, `plan_lines`, `plan_assets`, `blocked_by`, `blocks`, `scope`, `implementation_steps`, `deliverables`, `acceptance_criteria`, `risks`, `test_plan.*` (initial), `status="pending"` |
| ScaffoldPhase | `test_plan.*` (refined), `test_artifacts`, `verification_commands` |
| ExecPhase / ExecTask | `status`, `completion_date`, `test_completion`, `review_score`, `review_breakdown`, `review_status`, `implementation_branch`, `completion_notes` |

### Valid `asset_type` values for `plan_assets`
`code_snippet`, `equation`, `diagram`, `table`, `constraint`.

---

## Post-Install Configuration (`autviam_config.json`)

Run `/AutViam install` once per repo to wire up repo-specific specialists. The command
scans `.claude/agents/` and `.claude/skills/`, proposes trigger patterns, gets user
approval, and writes `<skill_root>/autviam_config.json`.

**What the config enables:**
- `domain_reviewer.specialists` — agents ExecPhase dispatches during Gate B when the diff
  touches matching files. Each specialist's findings carry the same weight as the domain
  reviewer's own findings.
- `spec_reviewer.specialists` — agents dispatched during Gate A (rare; most repos leave
  this empty).
- `implementer.skills` — skills surfaced to the implementer template (future).

**Runtime mechanics (deterministic — no LLM at trigger time):**

Before dispatching the domain reviewer, ExecPhase/ExecTask runs:
```bash
<skill_root>/scripts/match_specialists.sh <skill_root>/autviam_config.json domain_reviewer.specialists <base_sha> <head_sha>
```
which emits the JSON array of config entries whose `trigger_patterns` match at least one file in
`git diff --name-only <base_sha>..<head_sha>` (OR logic). That array is the `specialist_agents` list
injected into the domain reviewer prompt. An empty array (no config, empty section, or no match) means
standard review — fully backward compatible with repos that have no config. The implementer skill check
and Gate A spec-reviewer specialist check use the same script with the `implementer.skills` /
`spec_reviewer.specialists` section.

**The config is repo-local.** It is never part of the upstream AutViam skill definition.
Template: `templates/autviam_config_template.json`.

---

$@
