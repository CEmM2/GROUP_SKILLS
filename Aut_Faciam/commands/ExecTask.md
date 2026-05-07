# ExecTask

Execute a single task through all quality gates, then present a full report for review.

This command is for when you want to work through one task at a time — see the full implementation, gate results, and failure history before moving on. It runs the implementer and all three gates autonomously, then gives you the complete picture.

**Inputs:**
- `<task_id>`: the specific task to execute (e.g., `P2-3`)
- `<plan_file>`: path to the markdown plan, spec, or RFC document
- `<tasks_folder>`: if provided, otherwise defaults to `dev/tasks/<plan file name>/`
- `<tracking_file>`: if provided, otherwise defaults to `dev/tracking/tasks-tracker_<plan file name>.md`

---

## Step 1 — Load and Validate

Read the task JSON from `<tasks_folder>/json/<task_id>.json`. Extract the phase from `task.phase`.

Read:
- `<plan_file>` in full
- `all-tasks.md` in `<tasks_folder>` — to understand where this task sits in the phase and what depends on it
- `Phase_<phase>_context_summary.md` from `<tasks_folder>`
- Handoff file if phase > 1 (`Handoff_Phase_<phase>.md`)
- `<tasks_folder>/github_issue_map.json` for issue numbers
- Existing `<tasks_folder>/gates/phase_<phase>_gates.md` — scan for past failure patterns relevant to this task

**Validate preconditions:**
- All tasks in `task.blocked_by` must have `status: "done"` in their JSON files. If any blocker is incomplete, report which blockers are pending and stop. Do not proceed with a blocked task.
- The task's `status` should not already be `"done"`. If it is, warn the user and ask for confirmation before re-executing.

**Assess complexity and risk** (1–5 scale each). Apply model assignment rules:
- Combined > 6 → Opus 4.6 for implementer and reviewers
- Either ≥ 3 → Sonnet 4.6 or Opus 4.6
- Haiku only for read-only subtasks

---

## Step 2 — Branch Setup

If not already on a phase branch:

```bash
git checkout -b <plan_slug>_phase-<phase>
```

Or verify you're on the correct branch. The `plan_slug` is found in `github_issue_map.json`. If the map doesn't exist yet (Plan-2-Tasks was run without GitHub), derive it the same way: lowercase the plan filename, replace underscores/spaces with hyphens, drop the extension.

---

## Step 3 — Implementation Dispatch

Dispatch an implementer subagent using the template at `templates/task_instructions_template.md`. **Provide the full task text inline.**

**GitHub update (1 `gh` call):**

```bash
gh issue edit <task_issue> --remove-label "blocked" --add-label "in-progress"
```

Initialize the task entry in `gates/phase_<phase>_gates.md`.

---

## Step 4 — Gate Sequence (autonomous)

Run all three gates in sequence. No `gh` calls during this phase — all results go to the gates file.

Gates A&B pass rule: start from 10; deduct 1 point per minor issue and 2 points per medium issue. Pass only if the score is ≥ 8 and there are no high or critical issues.

### Gate A — Spec Compliance

Use the `templates/spec_compliance_template.md` subagent template. If it fails, record the failure in the gates file, have the implementer fix, and re-run. Loop until pass.

### Gate B — Domain Quality

Only after Gate A passes. Review against design docs and plan. If it fails, record, fix, re-run Gate A, then Gate B. Loop until pass.

### Gate C — Verification

Run the full test command fresh. Apply the Iron Law (see ExecPhase Step 6 for details). Record test results in the gates file.

---

## Step 5 — Completion

### Local updates:

Update `<tracking_file>` with completion data.

Update the task JSON with:
- `"status": "done"`
- `"completion_date": "<today>"`
- `test_completion` with actual pass/fail counts
- `review_score` and `review_breakdown`
- `review_status`
- `implementation_branch`
- `completion_notes`

Record completion in `gates/phase_<phase>_gates.md`.

### GitHub updates (3-4 `gh` calls):

```bash
gh issue edit <task_issue> --remove-label "in-progress" --add-label "done,gate-a-pass,gate-b-pass"
gh issue close <task_issue>
```

Update phase issue tasklist using the canonical 4-step pattern from SKILL.md § Updating Issue Body Checklists (fetch via `gh issue view`, materialise with `Write` tool, mutate with `Edit` tool, push back via `gh issue edit --body-file`).

Unblock downstream tasks if applicable.

---

## Step 6 — Present Report

After everything completes, present a summary to the user. This is the key difference from ExecPhase — instead of immediately moving to the next task, pause and show the full picture:

```markdown
## Task <task_id>: <title> — Complete

### Implementation Summary
<what was built, which files changed>

### Gate History
<for each gate attempt, summarize: pass/fail, and for failures what went wrong and how it was fixed>

**Gate A:** <N> attempts → Pass
**Gate B:** <N> attempts → Pass
**Gate C:** Tests <pass>/<total> (<percentage>%)

### Failure Patterns (if any)
<If any gate failed, summarize the failure modes and resolutions.
 Flag if this matches patterns from previous phases.>

### Files Changed
<list of files with brief descriptions>

### Test Evidence
<exact test output counts from Gate C>

### Open Questions
<anything the implementer or reviewers flagged as uncertain>
```

If there were gate failures, highlight whether the failure modes match patterns from previous phases — this is useful signal for upcoming tasks.

Save this report to `<tasks_folder>/reports/<task_id>_report.md` (create the `reports/` directory if it doesn't exist). This builds an archival record across the plan that can be reviewed later.

**Ask the user:** "Ready to proceed to the next task, or do you want to discuss anything about this one?"
