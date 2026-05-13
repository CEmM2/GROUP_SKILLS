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
| `task <task_id> <plan_file> [tasks_folder] [tracking_file]` | `commands/ExecTask.md` |

Templates live in `templates/`. Review agents live in `agents/` (see § Reviewer Agents). On-demand references live in `references/`.

---

## Shared Architecture

### Folder Conventions
- `<tasks_folder>` defaults to `dev/tasks/<plan_file_stem>/`
- `<tracking_file>` defaults to `dev/tracking/tasks-tracker_<plan_file_stem>.md`
- `<gates_folder>` is always `<tasks_folder>/gates/`

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

### Reviewer Agents
Gate A (spec compliance) and Gate B (domain quality) are run as named Claude Code subagents — `autviam-spec-reviewer` and `autviam-domain-reviewer` — defined in `agents/`. Invoke via the Agent tool with `subagent_type` set to the agent name.

**Install (once per consuming repo):** symlink or copy the two `agents/*.md` files into `.claude/agents/` so Claude Code picks them up. If the agents are not installed, ExecPhase/ExecTask falls back to dispatching the Task tool with the agent's system prompt inlined — same behavior, slightly more tokens.

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

$@
