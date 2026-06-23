# Plan-2-Tasks

Convert a plan into granular tasks, set up tracking, and create the GitHub plan + phase issues.

**Inputs:** `<plan_file>` (required); `<tasks_folder>` (default `dev/plans/<plan_file_stem>/`); `<tracking_file>` (default `<tasks_folder>/tasks-tracker.md`).

---

## Step 0 — Plan worktree (branch + worktree + plan copy)

Before writing any artifact, set up the plan's isolated worktree so every derived file lands on the plan branch (SKILL.md § Branch & Worktree Model). Pre-check with `git rev-parse --show-toplevel` — if this isn't a git repo, **skip Step 0** and operate in place under `dev/plans/<stem>/` on the current branch (note the skip in the final summary).

1. **Slug:** → `<skill_root>/scripts/init_plan.sh slug <plan_file>` (prints `<plan_slug>`; reuse it in Step 7 — no need to re-derive).
2. **Ensure the plan branch** (idempotent — `gen-plan` usually created it; this covers hand-written plans that skipped `gen-plan`): → `<skill_root>/scripts/phase_git.sh plan-branch <plan_slug>`.
3. **Worktree:** → `<skill_root>/scripts/phase_git.sh worktree <plan_slug>` (prints `<worktree>` = `<repo-parent>/WorkTrees/<repo>-<plan_slug>`, checked out on `<plan_slug>`).
4. **Copy the plan in** (a copy — the original is left untouched, intentionally): copy `<plan_file>` to `<worktree>/dev/plans/<stem>.md` (canonical, beside the folder) **and** into `<worktree>/dev/plans/<stem>/`; copy its `-plan.html` companion too if it exists.
5. **Operate inside the worktree from here on.** Every path below — `<tasks_folder>` = `<worktree>/dev/plans/<stem>/`, the issue map, tracker, gates, summaries, scratch — resolves under `<worktree>`. The main checkout stays put.
6. **Keep transients out of git:** write `<tasks_folder>/.gitignore` containing `scratch/` and `diagrams/`.

## Step 1 — Read the plan once

This is the **only** command in the pipeline that reads `<plan_file>` in full. Extract:
- Problem statement and motivation
- Each proposed change (files to modify, new files, deletions)
- Rejected alternatives and their reasoning
- Explicit scope boundaries / non-goals
- "Risk Assessment" section, if present

## Step 2 — Decompose into phased tasks

If the plan is already phased, assess whether each phase can be decomposed further into self-contained tasks.

**Phase numbering (non-negotiable):** integers 1, 2, 3, … N, in execution order. Drives branch names (`<plan>_phase-2`), gate files, context summaries, `phase-N` labels, and CLI routing (`AutViam scaffold 2`). Non-numeric plan phase names ("Foundation", "Alpha") get mapped to integers; record the original name in the phase's context summary.

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

First scaffold the per-plan folders: → run `<skill_root>/scripts/init_plan.sh dirs <tasks_folder>` (makes `<tasks_folder>/{json,gates,reviews,scratch}` — this covers Step 4's `json/`, ExecPhase's `gates/`, the `reviews/` folder, and the gitignored `scratch/` for transient issue-body files, in one call).

For each task, create `<tasks_folder>/json/<task_id>.json` from `templates/template.json`.

Field ownership: see SKILL.md § Task JSON Schema. Populate only the fields Plan-2-Tasks owns; leave the rest at template defaults.

For `plan_assets`: where the plan includes code, equations, diagrams, tables, or explicit constraints, record `{asset_type, plan_file, plan_lines, description}` entries. Downstream commands use `plan_lines` to read only the relevant slice of the plan instead of the whole file.

## Step 5 — Tracking file

Create `<tracking_file>` from `templates/tasks-tracker_template.md`.

## Step 6 — Phase context summaries

For each phase, create `<tasks_folder>/Phase_<N>_context_summary.md` from `templates/phase_context_summary.md`. Distill **must know** and **should know** knowledge for that phase only. This file is what ScaffoldPhase / ExecPhase / ExecTask read instead of the full plan.

## Step 7 — GitHub: plan overview + phase issues

**Pre-check:** `gh auth status`. If it fails, skip Step 7 entirely. Local artifacts (all-tasks.md, JSONs, tracker, context summaries) are already complete — GitHub integration can be added later by re-running Plan-2-Tasks.

**Derive `plan_slug`:** lowercase the plan filename, replace `_` and spaces with `-`, drop the extension.
→ run `<skill_root>/scripts/init_plan.sh slug <plan_file>` (prints the slug). Store it in `github_issue_map.json` as `plan_slug` and reuse it for the issue titles/labels below.

### 7a. Ensure labels exist (diff, don't blast)

→ run `<skill_root>/scripts/init_plan.sh labels <slug> "<plan_name>" <phase_count>`. It diffs against `gh label list` and creates only the MISSING labels (incl. `phase-1`..`phase-<phase_count>`), so a typical second-plan-in-the-same-repo run is 1–2 creates instead of 14+. If `gh` is unauthenticated it skips and exits 3.

The label taxonomy it ensures (reference — colors/descriptions live in the script):

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

### 7b. Plan overview issue

Render `templates/plan_overview_issue.md` to `<tasks_folder>/scratch/plan_overview_body.md` (the body stays LLM-authored), then:

→ `num=$(<skill_root>/scripts/init_plan.sh create-issue --title "📋 [<slug>] Plan: <plan_name>" --labels "plan-issue,plan:<slug>" --body-file <tasks_folder>/scratch/plan_overview_body.md)`

`create-issue` prints the new issue NUMBER on stdout — capture it as the overview issue number.

### 7c. Phase issues (one per phase, in order)

Render `templates/phase_skeleton_issue.md` per phase to `<tasks_folder>/scratch/phase_<N>_body.md` (LLM-authored body), then per phase:

→ `<skill_root>/scripts/init_plan.sh create-issue --title "[<slug>] Phase <N>: <phase_name>" --labels "phase-issue,phase-<N>,not-scaffolded,plan:<slug>" --body-file <tasks_folder>/scratch/phase_<N>_body.md`

Capture each printed issue number (keyed by phase `<N>`) for §7d/§7e.

### 7d. Backfill phase numbers into plan overview

The plan overview was created with `#<phase_issue_number>` placeholders. Replace them with real numbers using the canonical roundtrip in `references/issue_body_updates.md` — fetch once, MultiEdit all placeholders in one pass, push once:

1. `<skill_root>/scripts/issue_body.sh fetch <overview_issue>` → body to stdout.
2. `Write` the body to `<tasks_folder>/scratch/issue_<overview_issue>_body.md`.
3. `MultiEdit` that file: replace every `#<phase_issue_number>` placeholder with the real number from §7c (one MultiEdit, N edits — never `sed -i`).
4. `<skill_root>/scripts/issue_body.sh push <overview_issue> <tasks_folder>/scratch/issue_<overview_issue>_body.md`.

### 7e. Save the issue map

→ run `<skill_root>/scripts/init_plan.sh map <tasks_folder> <plan_file> <slug> <overview_issue> <repo> 1:<i1> 2:<i2> …` (one `N:issue` token per phase, using the numbers captured in §7c). It writes `<tasks_folder>/github_issue_map.json`:

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

→ run `<skill_root>/scripts/init_plan.sh annotate <tasks_folder>/json <tasks_folder>/github_issue_map.json`. It adds, keyed by each task's `phase`:

```json
"github_issue": { "phase_issue": <phase_issue_number>, "repo": "<owner/repo>" }
```

No `task_issue` field — phase-issues-only.

### 7g. Project sync (gated)

Add the overview issue and each phase issue to the GitHub Project board via `project_sync.sh` — one `add` for the overview, one per phase. The issue URL is `https://github.com/<repo>/issues/<number>`, built from `<repo>` and the issue numbers captured at creation (§7b/§7c):

```bash
<skill_root>/scripts/project_sync.sh add <tasks_folder>/github_issue_map.json <skill_root>/autviam_config.json overview https://github.com/<repo>/issues/<overview_issue> --slug <slug>
# per phase <N>:
<skill_root>/scripts/project_sync.sh add <tasks_folder>/github_issue_map.json <skill_root>/autviam_config.json phase:<N> https://github.com/<repo>/issues/<phase_issue> --slug <slug> --phase <N>
```

`project_sync.sh` self-gates on `autviam_config.json` → `project` (returns OFF and no-ops when `"disable"`/absent), is idempotent (skips an item already cached in the map's `project` block), and is best-effort (logs + skips on any failure, never blocks). It resolves the board, sets Plan/Phase (the built-in **Repository** field auto-populates), and writes the `project` block (`owner`, `number`, `overview_item`, `phase_items`) into `github_issue_map.json` itself, so Scaffold/ExecPhase reuse the item ids — no manual board resolution or project-block authoring. Background: `references/project_sync.md`.

## Step 8 — Commit the plan artifacts on the plan branch

Inside the worktree, commit the derived artifacts so the plan branch has a **clean tree** — `ScaffoldPhase` forks phase branches from `<plan_slug>` and `phase_git.sh branch` refuses a dirty tree:

→ `git -C <worktree> add dev/plans/<stem> dev/plans/<stem>.md`
→ `git -C <worktree> commit -m "AutViam: decompose plan <plan_slug> (tasks, tracker, context, issue map)"`

Best-effort: if there is nothing to commit, skip. `scratch/` and `diagrams/` are gitignored (Step 0.6), so they stay out of the commit. (Skipped entirely when Step 0 was skipped — no worktree, no plan branch.)

---

Done. The plan is decomposed, tracked, and visible on GitHub at the phase level. ScaffoldPhase is the next step for any phase you want to execute.
