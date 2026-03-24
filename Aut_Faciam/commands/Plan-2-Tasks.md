# Plan-2-Tasks

Convert a plan into granular tasks, set up tracking, and create GitHub issue skeletons.

**Inputs:**
- `<plan_file>`: path to a markdown plan, spec, or RFC document
- `<tasks_folder>`: if provided, otherwise use `dev/tasks/<plan file name>/`
- `<tracking_file>`: if provided, otherwise use `dev/tracking/tasks-tracker_<plan file name>.md`

---

## Step 1 — Read and Analyze the Plan

Read the plan file in full. Extract:
- The problem statement and motivation
- Each proposed change (files to modify, new files, deletions)
- Rejected alternatives and their reasoning
- Any explicit scope boundaries or non-goals

## Step 2 — Break Down into Granular Tasks

Break down the plan into granular tasks. If the plan is already divided into tasks, assess whether they can be further decomposed into smaller self-contained tasks.

**Phase numbering (non-negotiable):** Phases must be assigned sequential integers starting from 1, in execution order: 1, 2, 3, … N. This numbering drives all downstream references — branch names (`<plan>_phase-2`), gate files (`phase_2_gates.md`), context summaries (`Phase_2_context_summary.md`), GitHub labels (`phase-2`), and CLI routing (`Aut_Faciam scaffold 2`). If the plan uses non-numeric or non-sequential phase names (e.g., "Foundation", "Alpha", "Polish"), map them to sequential integers and record the original name in the phase's context summary and `all-tasks.md` title column.

**Task ID format:** `P<phase>-<seq>` where `<phase>` is the phase integer and `<seq>` is a sequential number within the phase, starting from 1. Examples: `P1-1`, `P1-2`, `P2-1`, `P3-4`. This format makes phase membership immediately visible in any context (tracker, issue titles, gate files, JSON filenames).

## Step 3 — List All Tasks and Verify Dependencies

Create `all-tasks.md` in `<tasks_folder>` using this table format:

```
| Task ID | Phase | Title | Blocked by (immediate) | Blocks (immediate) | Derived from plan lines |
|---|---|---|---|---|---|
```

After creating the table, verify the dependency graph:
- **No circular dependencies.** If A blocks B and B blocks A (directly or transitively), something is wrong — decompose further or restructure.
- **Call graph consistency.** If function A calls function B according to the plan, then B's task must appear in A's `blocked_by`. Walk through the plan's code specs and function signatures to verify this. This is the most common source of incorrect dependencies.
- **Cross-phase dependencies are explicit.** If a task in Phase 2 depends on a Phase 1 task, that must be in `blocked_by` even though phases are sequential — the dependency tracker needs it for unblocking logic.

## Step 4 — Create Task JSONs

For each task, create a JSON file in `<tasks_folder>/json/` using the template at `templates/template.json`.

**Populate these fields** (Plan-2-Tasks owns them):
- `task_id`, `title`, `phase`, `objective`, `plan_file`, `plan_lines`
- `plan_assets` — if the plan includes code snippets, flow charts, or pre-defined constants, reference them with a short description, the plan file path, and start/end line numbers
- `blocked_by`, `blocks` — verify that the call graph and data flow in the plan match the dependency edges you declare. If function A calls function B, then B's task must be listed as a blocker for A's task
- `scope`, `implementation_steps`, `deliverables`
- `acceptance_criteria` — derived from the plan's requirements for this task
- `risks` — look for a "Risk Assessment" section in the plan; identify which task each risk affects and append the plan's mitigation. If no mitigation exists, inform the user
- `test_plan.tier` and `test_plan.cases` — initial estimates (ScaffoldPhase may refine them)
- `status`: set to `"pending"`

**Leave these at template defaults** (other commands own them):
- `test_artifacts`: leave as `[""]` — ScaffoldPhase populates with actual test file paths
- `verification_commands`: leave as `[""]` — ScaffoldPhase populates with targeted pytest commands
- `test_completion`: leave zeroed — ExecPhase/ExecTask fills after Gate C
- `review_score`, `review_breakdown`, `review_status`: leave zeroed/empty — ExecPhase/ExecTask fills after Gate B
- `implementation_branch`: leave as `""` — ExecPhase/ExecTask sets when creating the branch
- `completion_date`: leave as `""` — ExecPhase/ExecTask sets on completion
- `completion_notes`: leave as `[""]` — ExecPhase/ExecTask fills

## Step 5 — Create the Tracking File

Create `<tracking_file>` following the template at `templates/tasks-tracker_template.md`.

## Step 6 — Generate Context Files

For each implementation phase, distill a **must know** and **should know** knowledge set and place it in `<tasks_folder>`, naming it `Phase_<phase_id>_context_summary.md`, including:
- Conventions
- Key principles
- Allowed deviation from specs — **only if explicitly written in the plan**
- Phase-relevant pre-resolved design decisions
- Downstream impact of the phase

## Step 7 — Create GitHub Issues (Plan Overview + Phase Skeletons)

This step creates the GitHub issue structure. All issues start as skeletons — phase issues get populated when ScaffoldPhase runs, task issues don't exist yet.

**Pre-check:** Run `gh auth status`. If `gh` is not available or not authenticated, skip this entire step, warn the user, and still produce all local artifacts (all-tasks.md, task JSONs, tracker, context files). The GitHub integration can be retroactively added by re-running Plan-2-Tasks later.

**Derive the plan slug:** Take the plan filename (without extension), lowercase it, replace underscores and spaces with hyphens. Examples: `adding_projects_feature.md` → `adding-projects-feature`, `Email Refactor.md` → `email-refactor`. This slug namespaces all GitHub issues for this plan, preventing collisions when multiple plans have open issues in the same repo. Store it in `github_issue_map.json` as `plan_slug`.

### 7a. Ensure labels exist

Run all label creation commands. These are idempotent (`--force` flag). The `plan:<slug>` label is unique to this plan:

```bash
gh label create "plan:<slug>" --color "1d76db" --description "Plan: <plan_name>" --force
gh label create "plan-issue" --color "0075ca" --description "Plan overview issue" --force
gh label create "phase-issue" --color "7057ff" --description "Phase parent issue" --force
gh label create "task-issue" --color "008672" --description "Individual task issue" --force
gh label create "not-scaffolded" --color "e4e669" --description "Phase not yet scaffolded" --force
gh label create "scaffolded" --color "0e8a16" --description "Phase scaffolded and ready" --force
gh label create "blocked" --color "d93f0b" --description "Blocked by dependency" --force
gh label create "in-progress" --color "fbca04" --description "Actively being worked on" --force
gh label create "gate-a-pass" --color "c5def5" --description "Spec compliance passed" --force
gh label create "gate-b-pass" --color "bfdadc" --description "Domain quality passed" --force
gh label create "done" --color "0e8a16" --description "All gates passed" --force
gh label create "tier:unit" --color "f9d0c4" --description "Unit test tier" --force
gh label create "tier:integration" --color "f9d0c4" --description "Integration test tier" --force
gh label create "tier:regression" --color "f9d0c4" --description "Regression test tier" --force
```

Also create a `phase-N` label for each phase discovered in the plan:

```bash
gh label create "phase-<N>" --color "d4c5f9" --description "Phase <N>" --force
```

### 7b. Create the plan overview issue

Use the template at `templates/plan_overview_issue.md`. Fill it with data from the plan analysis. Create with:

```bash
gh issue create --title "📋 [<slug>] Plan: <plan_name>" --label "plan-issue,plan:<slug>" --body-file <tempfile>
```

Capture the returned issue number.

### 7c. Create skeleton phase issues (in order)

For each phase, use the template at `templates/phase_skeleton_issue.md`. Create in order so each can reference the previous:

```bash
gh issue create --title "[<slug>] Phase <N>: <phase_name>" --label "phase-issue,phase-<N>,not-scaffolded,plan:<slug>" --body-file <tempfile>
```

Capture each issue number.

### 7d. Update plan overview with real issue numbers

After all phase issues exist, edit the plan overview issue body to replace placeholder `#<phase_issue_number>` references with actual numbers.

### 7e. Create the issue mapping file

Save `<tasks_folder>/github_issue_map.json` (see SKILL.md for schema). Record the plan slug, plan overview issue number, each phase's issue number, and the repo name.

### 7f. Add `github_issue` field to task JSONs

For each task JSON, add:

```json
"github_issue": {
  "phase_issue": <phase_issue_number>,
  "task_issue": null,
  "repo": "<owner/repo-name>"
}
```

### 7g. Create the gates folder

```bash
mkdir -p <tasks_folder>/gates
```

---

ultrathink
