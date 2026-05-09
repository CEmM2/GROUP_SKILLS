---
name: Aut_Faciam
description: >
  Plan-to-execution pipeline with GitHub Issues integration. Decomposes plans into
  phased tasks, scaffolds test coverage, executes with quality gates, and mirrors
  everything to GitHub for kanban tracking and agent dispatch. Use this skill whenever
  the user invokes /Aut_Faciam, or mentions planning tasks, scaffolding phases,
  executing phases or tasks, GitHub issue tracking for development plans, kanban
  boards for task management, or agent dispatch via GitHub issues. If the user
  references Plan-2-Tasks, ScaffoldPhase, ExecPhase, or ExecTask, this skill applies.
---

# Aut_Faciam — Plan → Scaffold → Execute with GitHub Issues

This skill is a self-contained pipeline for turning a markdown plan into tracked, executed, verified work. It manages four stages: decomposing a plan into phased tasks, scaffolding test coverage before execution, executing tasks through quality gates, and mirroring everything to GitHub issues for visibility and agent dispatch.

The name means "I shall do it" — which is what happens when you point this at a plan.

## Routing

This skill accepts subcommands via `$@`. Parse the first token to determine which command to run, then read the corresponding file from the `commands/` folder:

| Input pattern | Command file | What it does |
|---------------|-------------|--------------|
| `tasks <plan_file> [tasks_folder] [tracking_file]` | `commands/Plan-2-Tasks.md` | Decomposes plan → task JSONs, tracker, context files, GitHub issues |
| `scaffold <phase_id> <plan_file> [tasks_folder] [tracking_file]` | `commands/ScaffoldPhase.md` | Generates test stubs, validates task JSONs, populates GitHub issues |
| `exec <phase_id> <plan_file> [tasks_folder] [tracking_file]` | `commands/ExecPhase.md` | Executes all tasks in a phase through quality gates |
| `task <task_id> <plan_file> [tasks_folder] [tracking_file]` | `commands/ExecTask.md` | Executes a single task through all gates, presents full report |

After identifying the subcommand, read the corresponding command file from this skill's `commands/` directory and follow its instructions. Templates referenced by the commands live in this skill's `templates/` directory.

**Important:** If the first token doesn't match any of the above, show the user the available subcommands and ask them to clarify.

---

## Shared Architecture

The sections below define concepts shared across all four commands. Each command file references these by name rather than redefining them.

### Folder Conventions

All commands share the same defaulting logic for paths:

- `<tasks_folder>`: defaults to `dev/tasks/<plan_file_name>/` (the plan filename without extension)
- `<tracking_file>`: defaults to `dev/tracking/tasks-tracker_<plan_file_name>.md`
- `<gates_folder>`: always `<tasks_folder>/gates/` — contains per-phase gate history files

### GitHub Issue Map

The bridge between local task data and GitHub issues. Lives at `<tasks_folder>/github_issue_map.json`:

```json
{
  "plan_file": "dev/plans/my_plan.md",
  "plan_slug": "my-plan",
  "plan_overview_issue": 10,
  "phases": {
    "1": { "issue_number": 11, "task_issues": {} },
    "2": { "issue_number": 12, "task_issues": {} }
  },
  "repo": "owner/repo-name"
}
```

Plan-2-Tasks creates this file. ScaffoldPhase and ExecPhase read and update it. The `task_issues` map gets populated when ScaffoldPhase creates individual task issues. The `plan_slug` is derived from the plan filename (lowercase, hyphens, no extension) and used as a namespace prefix on all GitHub issue titles and as a `plan:<slug>` label.

### Label Taxonomy

All labels are created idempotently via `gh label create --force`. Plan-2-Tasks creates them all upfront; subsequent commands assume they exist.

| Label | Color | Meaning |
|-------|-------|---------|
| `plan:<slug>` | `#1d76db` | Plan namespace — on every issue belonging to this plan |
| `plan-issue` | `#0075ca` | Plan overview issue |
| `phase-issue` | `#7057ff` | Phase-level parent issue |
| `task-issue` | `#008672` | Individual task issue |
| `not-scaffolded` | `#e4e669` | Phase hasn't been scaffolded yet |
| `scaffolded` | `#0e8a16` | Phase scaffolded, tasks populated |
| `blocked` | `#d93f0b` | Task waiting on a blocker |
| `in-progress` | `#fbca04` | Task actively being worked on |
| `gate-a-pass` | `#c5def5` | Spec compliance passed |
| `gate-b-pass` | `#bfdadc` | Domain quality passed |
| `done` | `#0e8a16` | All gates passed |
| `phase-N` | `#d4c5f9` | Phase number (one per phase) |
| `tier:unit` | `#f9d0c4` | Unit test tier |
| `tier:integration` | `#f9d0c4` | Integration test tier |
| `tier:regression` | `#f9d0c4` | Regression test tier |

### Recovery and Rollback

If a task fails Gate C repeatedly or a high-risk task destabilizes the branch:

1. **Identify the last good commit:** Check `gates/phase_<N>_gates.md` for the last passing Gate C entry — it records the commit SHA.
2. **Revert the broken task:** `git revert <bad_commit_sha>` — this preserves history. **NEVER** use `git reset --hard`.
3. **Update the task JSON:** Set `status` back to `"pending"`, clear `completion_date` and `test_completion`.
4. **Update the tracker:** Mark the task as `reverted` with a note pointing to the gate history entry.
5. **Re-attempt or escalate:** Re-dispatch the task with the failure context from the gates file, or flag it to the user for manual intervention.

If the entire phase branch is unrecoverable, create a new branch from the parent branch and re-execute only the incomplete tasks (the gate history and task JSONs track which tasks completed successfully).

### Idempotency and Error Handling

**First step for any command with GitHub steps:** Run `gh auth status` to verify `gh` is available and authenticated. If it fails, skip all GitHub steps for this command run and warn the user. The local pipeline (task JSONs, tracker, scaffold reports, gate history) must work independently — issues are a convenience layer, not a dependency.

Every GitHub operation must be safe to re-run:

- Before creating any issue, check `github_issue_map.json` — if the issue number already exists for that entity, skip creation and use the existing number.
- If a `gh issue create` fails mid-batch, save progress to `github_issue_map.json` after each successful creation so you can resume on retry.

### Minimizing `gh` Calls

GitHub API calls are network roundtrips that slow execution and can hit rate limits (5000/hour authenticated). The guiding principle: **GitHub gets updated at meaningful state transitions only** — task start, task completion, phase completion. Intermediate work (gate review loops, fix-review cycles) stays local in the gates files.

Concrete budget per lifecycle event:
- Plan-2-Tasks: ~(14 + 2×N_phases + 2) calls — 14 base labels (including plan:<slug>) + N phase labels + 1 overview + N phase skeletons + 1 overview update
- ScaffoldPhase: ~(N_tasks + 2) calls — N task issues + 1 phase body update + 1 label swap
- ExecTask: 3-4 calls — 1 label in-progress, 1 label done + 1 close, 1 phase body update, +1 per unblocked downstream task
- ExecPhase: same as ExecTask × N_tasks + 2 for phase handoff (close current + check off in overview)

### Gate History Files (Hybrid Markdown + JSON)

Gate history is tracked in `<tasks_folder>/gates/phase_<N>_gates.md`. This hybrid format serves two purposes: the prose sections are searchable by BM25 full-text search or vector semantic search (to find similar past failures and their resolutions), while the embedded JSON blocks are parseable programmatically for metrics and analysis.

Before each gate attempt, search existing gate files for similar failure patterns. If a previous task hit the same kind of issue, the resolution is right there — use it to inform the current attempt.

See `templates/gate_entry.md` for the format.

**Failure mode categories** (use consistently across all gate entries so they're queryable):

| Category | Meaning |
|----------|---------|
| `missing_impl` | Required feature not implemented |
| `extra_work` | Unrequested features added |
| `misunderstanding` | Requirement interpreted incorrectly |
| `physics_error` | Constitutive/numerical correctness issue |
| `test_gap` | Insufficient test coverage |
| `style_violation` | Code quality or convention issue |
| `integration_break` | Broke something outside the task's scope |

### Updating Issue Body Checklists

Several commands need to check off items in issue bodies (task checkoffs in phase issues, phase checkoffs in plan overview). Use the **tool-based** workflow below — it is the canonical pattern for every body mutation this skill performs. Do **not** use `sed`, `awk -i inplace`, `perl -i`, or `python -c` to rewrite the file: those are shell mutations that require per-invocation approval under Claude Code's `accept-edits` mode, which breaks the autonomy of this pipeline. The `Write` and `Edit` tools, by contrast, run autonomously under `accept-edits`.

**Canonical 4-step pattern** (applies to every fetch-modify-update of an issue body):

1. **Fetch (1 Bash call, no shell redirect).** Run `gh issue view <issue_number> --json body -q .body` and let stdout return through the tool result. Do **not** redirect with `> /tmp/issue_body.md` — the redirect is an extra shell feature that adds nothing over capturing stdout directly.
2. **Materialise (Write tool).** Use the `Write` tool to save the captured body to a temp file, e.g. `/tmp/issue_body.md`. This is auto-approved under `accept-edits`.
3. **Mutate (Edit tool, exact-string).** Use the `Edit` tool to perform the exact-string replacement — e.g. `old_string: "- [ ] #<N>"`, `new_string: "- [x] #<N>"`. The `#<N>` disambiguates the match so no `replace_all` is needed. For larger structural replacements (e.g. swapping a `Pending` placeholder for a multi-line `<details>` block), use one Edit call with a sufficiently long `old_string` to make the match unique. Edit runs autonomously under `accept-edits`.
4. **Push back (1 Bash call).** Run `gh issue edit <issue_number> --body-file /tmp/issue_body.md`.

**Bash-call budget:** exactly 2 per body update (one `gh issue view` read, one `gh issue edit` write). Everything in between is tool-driven and autonomous.

Use `MultiEdit` for several known-string swaps in one pass; use `Write` (full template render) when the rewrite is structural enough that no exact-string match exists. Prefer `Edit`/`MultiEdit` over `Write` when feasible — the surgical diff is easier to audit. Never pass multi-line markdown as inline `--body` arguments — always go through the tempfile.

### Tracker Remains Authoritative

The markdown tracker is the source of truth. GitHub issues are a projection — useful for visibility and agent dispatch, but the tracker is what gets updated first. If they diverge (someone manually closes an issue, a task is re-opened), the tracker wins.

---

## Task JSON Schema

Each task is a JSON file in `<tasks_folder>/json/`. The template is at `templates/template.json`. When the GitHub integration is active, each task JSON includes a `github_issue` field:

```json
"github_issue": {
  "phase_issue": 11,
  "task_issue": 42,
  "repo": "owner/repo-name"
}
```

`task_issue` is `null` until ScaffoldPhase creates the task-level issue.

### Valid `asset_type` values for `plan_assets`

| Value | Meaning |
|-------|---------|
| `code_snippet` | Inline code from the plan (pseudocode, signatures, examples) |
| `equation` | Mathematical formula or derivation |
| `diagram` | Flow chart, architecture diagram, or schematic |
| `table` | Data table, constant definitions, or parameter sets |
| `constraint` | Explicit requirement or invariant stated in the plan |

---

$@
