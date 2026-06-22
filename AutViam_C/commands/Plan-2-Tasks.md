# Plan-2-Tasks

Convert a plan into granular tasks, set up tracking, and create the GitHub plan + phase issues.

**Inputs:** `<plan_file>` (required); `<tasks_folder>` (default `dev/plans/<plan_file_stem>/`); `<tracking_file>` (default `<tasks_folder>/tasks-tracker.md`).

---

## Step 1 — Read the plan once

This is the **only** command in the pipeline that reads `<plan_file>` in full. Extract:
- Problem statement and motivation
- Each proposed change (files to modify, new files, deletions)
- Rejected alternatives and their reasoning
- Explicit scope boundaries / non-goals
- "Risk Assessment" section, if present

## Step 2 — Decompose into phased tasks

If the plan is already phased, assess whether each phase can be decomposed further into self-contained tasks.

**Phase numbering (non-negotiable):** integers 1, 2, 3, … N, in execution order. Drives branch names (`<plan>_phase-2`), gate files, context summaries, `phase-N` labels, and CLI routing (`AutViam_C scaffold 2`). Non-numeric plan phase names ("Foundation", "Alpha") get mapped to integers; record the original name in the phase's context summary.

**Task ID format:** `P<phase>-<seq>` (e.g. `P1-1`, `P2-4`). Makes phase membership visible everywhere.

## Step 3 — `all-tasks.md` and dependency verification

Create `<tasks_folder>/all-tasks.md`:

```
| Task ID | Phase | Title | Blocked by (immediate) | Blocks (immediate) | Derived from plan lines |
|---|---|---|---|---|---|
```

Verify:
- **No circular dependencies** — A blocks B and B blocks A (directly or transitively) means decompose further.
- **Call-graph consistency** — if function A calls function B per the plan, B's task must appear in A's `blocked_by`. This is the most common bug.
- **Cross-phase blockers are explicit** — Phase 2 tasks blocked by Phase 1 tasks must list those blockers, even though phases run sequentially.

## Step 4 — Create task JSONs

For each task, create `<tasks_folder>/json/<task_id>.json` from `templates/template.json`.

Field ownership: see SKILL.md § Task JSON Schema. Populate only the fields Plan-2-Tasks owns; leave the rest at template defaults.

For `plan_assets`: where the plan includes code, equations, diagrams, tables, or explicit constraints, record `{asset_type, plan_file, plan_lines, description}` entries. Downstream commands use `plan_lines` to read only the relevant slice of the plan instead of the whole file.

## Step 5 — Tracking file

Create `<tracking_file>` from `templates/tasks-tracker_template.md`.

## Step 6 — Phase context summaries

For each phase, create `<tasks_folder>/Phase_<N>_context_summary.md` from `templates/phase_context_summary.md`. Distill **must know** and **should know** knowledge for that phase only. This file is what ScaffoldPhase / ExecPhase / ExecTask read instead of the full plan.

## Step 7 — GitHub: plan overview + phase issues

**Pre-check:** `gh auth status`. If it fails, skip Step 7 entirely. Local artifacts (all-tasks.md, JSONs, tracker, context summaries) are already complete — GitHub integration can be added later by re-running Plan-2-Tasks.

**Derive `plan_slug`:** lowercase the plan filename, replace `_` and spaces with `-`, drop the extension. Store in `github_issue_map.json` as `plan_slug`.

### 7a. Ensure labels exist (diff, don't blast)

```bash
gh label list --json name -q '.[].name' > /tmp/existing_labels.txt
```

Required labels (created only if missing):

| Name | Color | Description |
|---|---|---|
| `plan:<slug>` | `1d76db` | Plan: <plan_name> |
| `plan-issue` | `0075ca` | Plan overview issue |
| `phase-issue` | `7057ff` | Phase parent issue |
| `not-scaffolded` | `e4e669` | Phase not yet scaffolded |
| `scaffolded` | `0e8a16` | Phase scaffolded |
| `in-progress` | `fbca04` | Phase actively executing |
| `done` | `0e8a16` | Phase complete |
| `gate-cap-hit` | `b60205` | Task hit 4th gate failure — manual intervention required |
| `tier:unit` | `f9d0c4` | Unit test tier |
| `tier:integration` | `f9d0c4` | Integration test tier |
| `tier:regression` | `f9d0c4` | Regression test tier |
| `phase-<N>` (per phase) | `d4c5f9` | Phase <N> |

For each name not in `/tmp/existing_labels.txt`, run `gh label create <name> --color <hex> --description "<desc>"`. Skip the rest. Typical second-plan-in-the-same-repo run = 1–2 label creates instead of 14+.

### 7b. Plan overview issue

Render `templates/plan_overview_issue.md` to `/tmp/plan_overview_body.md`, then:

```bash
gh issue create --title "📋 [<slug>] Plan: <plan_name>" --label "plan-issue,plan:<slug>" --body-file /tmp/plan_overview_body.md
```

Capture the issue number.

### 7c. Phase issues (one per phase, in order)

Render `templates/phase_skeleton_issue.md` per phase, then:

```bash
gh issue create --title "[<slug>] Phase <N>: <phase_name>" --label "phase-issue,phase-<N>,not-scaffolded,plan:<slug>" --body-file /tmp/phase_<N>_body.md
```

Capture each issue number.

### 7d. Backfill phase numbers into plan overview

The plan overview was created with `#<phase_issue_number>` placeholders. Replace them with real numbers using the canonical pattern in `references/issue_body_updates.md` — fetch once, edit all placeholders in one pass, push once.

### 7e. Save the issue map

Write `<tasks_folder>/github_issue_map.json`:

```json
{
  "plan_file": "<plan_file>",
  "plan_slug": "<slug>",
  "plan_overview_issue": <N>,
  "phases": { "1": { "issue_number": <N1> }, "2": { "issue_number": <N2> } },
  "repo": "<owner/repo>"
}
```

### 7f. Add `github_issue` to each task JSON

```json
"github_issue": { "phase_issue": <phase_issue_number>, "repo": "<owner/repo>" }
```

No `task_issue` field — phase-issues-only.

### 7g. Create gates folder

```bash
mkdir -p <tasks_folder>/gates
```

### 7h. Project sync (gated — only if `autviam_c_config.json` → `project` is set)

If project sync is armed, read `references/project_sync.md`, then add the overview issue and each phase issue to the board and set their fields:

```bash
.codex/scripts/update_tracker.sh add <issue-url>            # → item id
.codex/scripts/update_tracker.sh set <issue-url> Plan  <slug>
.codex/scripts/update_tracker.sh set <issue-url> Phase <N>   # phase issues only
```

The built-in **Repository** field auto-populates — no Repo set needed. Append a `project` block (`owner`, `number`, `overview_item`, `phase_items`) to `github_issue_map.json` so Scaffold/ExecPhase reuse the item ids. If `project` is `"disable"`/absent, skip this step entirely — same degrade-gracefully rule as 7a's `gh auth` pre-check.

---

Done. The plan is decomposed, tracked, and visible on GitHub at the phase level. ScaffoldPhase is the next step for any phase you want to execute.
