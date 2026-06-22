---
name: AutViam_C
description: >
  Codex-native token-lean plan-to-execution pipeline. Decomposes plans into
  phased tasks, scaffolds tests, executes through quality gates with a hard
  3-failure cap, uses Codex worker/explorer agents via bundled prompt profiles,
  and mirrors progress to GitHub at the phase level only. Use when the user
  invokes AutViam_C or asks for Plan-2-Tasks, ScaffoldPhase, ExecPhase, ExecTask,
  or E2E plan execution in Codex.
---

# AutViam_C — Codex Plan → Scaffold → Execute

Self-contained pipeline turning a markdown plan into tracked, executed, verified work. This is the Codex-native fork of AutViam: it preserves the phase-only GitHub issue model and gate discipline, but replaces Claude Code installed agents with bundled Codex prompt profiles dispatched through Codex `worker` and `explorer` agents.

## Routing

Parse the first token after the user's `AutViam_C` or `$AutViam_C` invocation and read the matching command file from `commands/`. If no match, list the commands and ask the user.

| Input pattern | Command file |
|---|---|
| `tasks <plan_file> [tasks_folder] [tracking_file]` | `commands/Plan-2-Tasks.md` |
| `scaffold <phase_id> <plan_file> [tasks_folder] [tracking_file]` | `commands/ScaffoldPhase.md` |
| `exec <phase_id> <plan_file> [tasks_folder] [tracking_file]` | `commands/ExecPhase.md` |
| `phase <phase_id> <plan_file> [tasks_folder] [tracking_file]` | `commands/Phase.md` |
| `close-phase <phase_id> [plan_file] [tasks_folder]` | `commands/ClosePhase.md` |
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
- `<reviews_folder>` is always `<tasks_folder>/reviews/` — rendered review reports (`plan-review`, and `diff-review` when run against a plan) land here instead of the transient `~/.agent/diagrams/`.

### Plan Reading Discipline (token discipline)
- Plan-2-Tasks reads `<plan_file>` in full — once.
- ScaffoldPhase / ExecPhase / ExecTask read `Phase_<N>_context_summary.md` first. Open `<plan_file>` only on the specific `plan_lines` ranges referenced by tasks in scope. Never re-read the plan in full.

### Codex Agent JSON Passing Discipline
Never paste full task JSON content into a Codex agent prompt. Always pass the file path and the field list it needs. The receiving agent reads the file itself. This eliminates re-paying multi-KB JSON on every gate retry.

### Codex Agent Assignment (single source of truth)
Computed once per task from `complexity + risk` (each 1–5):
- Implementers and phase orchestrators use Codex `worker` agents.
- Gate reviewers and read-only specialists use Codex `explorer` agents.
- `combined > 6` → `reasoning_effort="xhigh"` for implementer and reviewer dispatches.
- `complexity >= 3 OR risk >= 3` → `reasoning_effort="high"`.
- Low-risk read-only/search subtasks may use `reasoning_effort="low"` or `"medium"`.

Do not invent custom Codex `agent_type` names. The bundled files under `agents/` are prompt profiles loaded into the prompt for built-in Codex agent types. Omit model overrides unless the user explicitly asks for a particular model or a task clearly requires one.

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

**Project sync (gated):** when `autviam_c_config.json` → `project` names a board (not `"disable"`), Plan-2-Tasks § 7h appends a `project` block (`owner`, `number`, `overview_item`, `phase_items`) to this file, and Scaffold/ExecPhase keep each item's **Status** in step with the issue lifecycle (Todo → Done, or Blocked on gate-cap-hit). See `references/project_sync.md`. Absent or `"disable"` → no Project calls at all.

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
- `references/project_sync.md` — gated GitHub Project board sync mechanics (active only when `autviam_c_config.json` → `project` names a board). Read when wiring or refreshing Project item status.

### Codex Agent Profiles
Three bundled Codex prompt profiles are defined in `agents/`:

| Prompt profile | Codex agent type | Role | Invoked from |
|---|---|---|
| `autviam-spec-reviewer` | `explorer` | Gate A (spec compliance) | ExecPhase, ExecTask, orchestrator |
| `autviam-domain-reviewer` | `explorer` | Gate B (domain quality) | ExecPhase, ExecTask, orchestrator |
| `autviam-phase-orchestrator` | `worker` | Runs ScaffoldPhase + ExecPhase for one phase, returns a JSON summary | E2E |

**Codex mechanism:** there is no custom named-agent install step. Keep these files inside the skill and, when dispatching, prepend the relevant profile content to a `spawn_agent` prompt using the built-in `agent_type` listed above. If `spawn_agent` is unavailable, ExecPhase/ExecTask may run the reviewer profile inline and record that inline mode was used. E2E depends on Codex worker dispatch; if dispatch is unavailable, halt on the pre-flight check instead of silently degrading.

The implementer remains template-based (`templates/task_instructions_template.md`) because per-phase context is injected per dispatch.

### Bundled scripts

Seven helper scripts live at `<skill_root>/scripts/` and run without an install step (reference them as `<skill_root>/scripts/<name>`). The commands call these for the deterministic, error-prone plumbing; the LLM keeps the judgment work (objectives, gate verdicts, prose attempt blocks, Decision narrative) around them.

| Script | Owns |
|---|---|
| `init_plan.sh` | Per-plan plumbing for Plan-2-Tasks Step 7: slug derivation, folder scaffolding, label diff/create, `gh issue create` (prints the number), issue-map write, task-JSON `github_issue` annotation. |
| `issue_body.sh` | The two `gh` halves of the canonical issue-body roundtrip (`fetch` → LLM edits → `push`) plus label-only / state / close flags. The LLM still does the Edit between fetch and push — never `sed -i`. |
| `gate_state.py` | Gate-file + task-JSON machine state: failure counting and the 3-failure cap (`cap-check`), counters-line sync, completion writeback, status set, rollback reset, last-good Gate C SHA, Session Reset Packet rows. |
| `phase_git.sh` | Phase branch create/checkout with a dirty-tree guard, and reverse-order `git revert` rollback (never `reset --hard` on a shared branch). |
| `match_specialists.sh` | Config-driven specialist/skill matcher — emits the matched `autviam_c_config.json` entries whose `trigger_patterns` hit the diff (deterministic, no LLM at trigger time). |
| `project_sync.sh` | The gated GitHub Project wrapper (`resolve`/`add`/`status`): board resolution from `autviam_c_config.json` → `project` (4 forms + name→number), idempotency, and the `project`-block bookkeeping in `github_issue_map.json`. Self-gates to a no-op when project sync is off; wraps `update_tracker.sh`. See `references/project_sync.md`. |
| `update_tracker.sh` | Low-level GitHub Project primitive (one `gh project item-edit` per call, IDs cached) wrapped by `project_sync.sh`. Not called directly by the commands. |

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

## Post-Install Configuration (`autviam_c_config.json`)

Run `AutViam_C install` once per repo to wire up repo-specific Codex prompt profiles and skills. The command scans optional repo-local Codex agent/profile folders and skill folders, proposes trigger patterns, gets user approval, and writes `<skill_root>/autviam_c_config.json`.

**What the config enables:**
- `domain_reviewer.specialists` — Codex `explorer` prompt profiles ExecPhase dispatches during Gate B when the diff touches matching files. Each specialist's findings carry the same weight as the domain reviewer's own findings.
- `spec_reviewer.specialists` — Codex `explorer` prompt profiles dispatched during Gate A (rare; most repos leave this empty).
- `implementer.skills` — skills surfaced to the implementer template when matching files changed.

**Runtime mechanics (deterministic — no LLM at trigger time):**

Before dispatching the domain reviewer, ExecPhase runs:
```bash
git diff --name-only <base_sha>..<head_sha> \
  | grep -E '<trigger_pattern>'
```
for each configured specialist. Only specialists with at least one matching file are included
in the `specialist_agents` list injected into the domain reviewer prompt. An empty list means
standard review — fully backward compatible with repos that have no config.

**The config is repo-local.** It is never part of the upstream AutViam_C skill definition.
Template: `templates/autviam_c_config_template.json`.
