# ExecPhase

Execute all tasks in a phase through quality gates, tracking gate history locally and updating GitHub issues at meaningful state transitions.

**Inputs:**
- `<phase_id>`: the current phase to execute (integer)
- `<plan_file>`: path to a markdown plan, spec, or RFC document
- `<tasks_folder>`: if provided, otherwise defaults to `dev/tasks/<plan file name>/`
- `<tracking_file>`: if provided, otherwise defaults to `dev/tracking/tasks-tracker_<plan file name>.md`

---

## Step 1 — Load Context

Read the `<plan_file>` in full. Extract:
- The purpose and goals of the current phase and how it feeds into subsequent phases
- Any explicit scope boundaries, non-goals, or architectural constraints
- Cross-phase dependencies that may affect implementation decisions in this phase

Find the context summary file (`Phase_<phase_id>_context_summary.md`) in `<tasks_folder>`.

If `<phase_id>` is greater than 1, search for a handoff file (`Handoff_Phase_<phase_id>.md`) in `<tasks_folder>` and read it in full.

Load `<tasks_folder>/github_issue_map.json` to have issue numbers available throughout execution.

Initialize (or load existing) `<tasks_folder>/gates/phase_<phase_id>_gates.md` for gate history tracking.

**Search existing gate files for patterns:** Before starting execution, scan all existing `gates/phase_*_gates.md` files for failure patterns. If previous phases encountered recurring issues (e.g., a common `physics_error` pattern), note these so implementers can be warned upfront.

---

## Step 2 — Task Analysis

Read `all-tasks.md` inside `<tasks_folder>`. For each task belonging to the current phase:
- Map blocking and blocked-by relationships
- Assess complexity (1–5 scale: 1 = trivial, 5 = highly complex)
- Assess risk (1–5 scale: 1 = low risk, 5 = high risk)

Create `Phase_<phase_id>_Tasks_analysis.md` inside `<tasks_folder>`:

```
| Task ID | Title | Complexity (1-5) | Risk (1-5) | Combined Score | Blocked By | Blocks |
|---------|-------|-----------------|------------|----------------|------------|--------|
```

**Model assignment rules (non-negotiable):**
- Combined score (complexity + risk) > 6 → **Opus 4.6 only** for implementation and review subagents
- Complexity OR risk ≥ 3 → **Sonnet 4.6 or Opus 4.6** for implementation and review subagents
- Haiku subagents are permitted **only** for search, fetch, and read-only tasks regardless of score

---

## Step 3 — Branch Setup

```bash
git checkout -b <plan_slug>_phase-<phase_id>
```

Never implement on `main` or `master` without explicit user consent.

---

## Step 4 — Execution Order

1. **Never execute a task whose blocker has not been marked complete and verified** (evidence of passing tests required — not the subagent's claim alone).
2. **Parallel first pass:** Identify all tasks where both complexity ≤ 3 AND risk ≤ 3 AND all blockers are satisfied. Dispatch these in parallel — one subagent per task, up to 4 concurrent. If more than 4 tasks qualify, process them in batches of 4. Before dispatching a parallel batch, verify that no two tasks in the batch modify the same file (check `deliverables` and `scope` in their JSONs). If file scopes overlap, run those tasks sequentially instead. Each task's `gh issue edit` (label flip to in-progress) can run concurrently — these are independent calls.
3. **Sequential high-risk tasks:** Tasks where complexity OR risk > 3 are executed one at a time, each in its own commit.
4. Process remaining tasks in dependency order after the parallel batch completes and is verified.

---

## Step 5 — Implementation Dispatch

For each task, dispatch an implementer subagent using the template at `templates/task_instructions_template.md`. **Provide the full task text inline — do not make the subagent read files itself.**

**If the implementer subagent asks questions before starting:** Answer them fully and completely before allowing it to proceed.

**GitHub update (1 `gh` call):**

```bash
gh issue edit <task_issue> --remove-label "blocked" --add-label "in-progress"
```

**Gate history:** Initialize the task's entry in `gates/phase_<phase_id>_gates.md` with the start timestamp and branch name (see `templates/gate_entry.md` for format).

---

## Step 6 — Review Gates (mandatory, in this order)

After each implementer subagent reports completion, run gates A → B → C in sequence. **Do not skip or reorder them.**

GateS A&B pass rule: start from 10; deduct 1 point per minor issue and 2 points per medium issue. Pass only if the score is ≥ 8 and there are no high or critical issues.

**During all gate review loops: no `gh` calls.** All gate attempts are recorded in `gates/phase_<phase_id>_gates.md` only. Use the format from `templates/gate_entry.md`.

### Gate A — Spec Compliance Review

Dispatch a spec compliance reviewer subagent using the template at `templates/spec_compliance_template.md`. **Provide the FULL TASK JSON CONTENT inline.**

**If spec review finds issues:** Record the failure in the gates file (failure mode, what failed, why). The implementer fixes them, then spec review runs again. Record the resolution on the passing attempt. Repeat until pass. Do not proceed to Gate B until Gate A passes.

### Gate B — Domain Quality Review

Only dispatch after Gate A passes.

Dispatch a domain quality reviewer subagent using the template at `templates/domain_quality_template.md`. **Provide the FULL TASK JSON CONTENT inline.** Also provide:
- The implementer's report
- The BASE_SHA (commit before the task) and HEAD_SHA (current commit)

**If the reviewer raises issues:** Record in gates file, mark task as WIP in tracker, fix, re-run Gate A, then re-run Gate B. Repeat until approved.

### Gate C — Verification Before Completion

Before updating any tracking file or marking any task complete, run the full test command fresh and read the actual output. Apply the Iron Law:

```
1. IDENTIFY: What command proves this task passes?
2. RUN: Execute the FULL command (fresh, not cached)
3. READ: Full output — check exit code, count pass/fail
4. VERIFY: Does output confirm ≥ 95% pass on all task-relevant tests?
   - If NO: Record in gates file, return to implementation
   - If YES: Record exact evidence (e.g., "47/49 tests passed")
5. ONLY THEN: Update tracking file
```

**Do not use:** "should pass", "probably works", "looks correct", or any claim without fresh run evidence. No exceptions.

---

## Step 7 — Task Completion (after all three gates pass)

### Local updates:

Update `<tracking_file>`:
- Mark task as complete
- Fill ALL previously empty cells for the completed task
- In "Verified by": list every test file written or modified, including any from dry-run failure-route analysis
- Record exact test pass evidence from Gate C

Update the task's JSON file with:
- `"status": "done"`
- `"completion_date": "<today>"`
- `test_completion` with actual pass/fail counts from Gate C
- `review_score` and `review_breakdown` from Gate B (minor/medium/high/critical issue counts)
- `"review_status": "approved"`
- `"implementation_branch": "<current branch name>"`
- `completion_notes` with any notable implementation decisions or deviations

Record completion timestamp in `gates/phase_<phase_id>_gates.md`.

### GitHub updates (3-4 `gh` calls):

```bash
# 1. Labels + close (2 gh calls)
gh issue edit <task_issue> --remove-label "in-progress" --add-label "done,gate-a-pass,gate-b-pass"
gh issue close <task_issue>
```

**2. Check off in phase issue (2 gh calls — follow the canonical 4-step pattern from SKILL.md § Updating Issue Body Checklists):**

1. `Bash`: `gh issue view <phase_issue> --json body -q .body` — capture stdout.
2. `Write` tool: save captured body to `/tmp/phase_body.md`.
3. `Edit` tool: `old_string: "- [ ] #<task_issue>"`, `new_string: "- [x] #<task_issue>"`.
4. `Bash`: `gh issue edit <phase_issue> --body-file /tmp/phase_body.md`.

```bash
# 3. Unblock downstream (1 gh call per newly-unblocked task)
gh issue edit <downstream_task_issue> --remove-label "blocked"
```

---

## Step 8 — Repeat for All Phase Tasks

Return to Step 4 and process the next eligible task (respecting dependencies). Continue until all tasks in `<phase_id>` are complete with all three gates passing.

---

## Step 9 — Phase Handoff

When all tasks in the current phase are complete and verified, generate a handoff file in `<tasks_folder>` following the template at `templates/Handoff_template.md`. Name it `Handoff_Phase_<next_phase_id>.md`.

**If this is the final phase** (no next phase exists), still generate the handoff as a project completion summary, but skip the "edit next phase issue" step. Close the current phase issue and check it off in the plan overview. The plan overview issue itself stays open as a record — the user can close it manually when they consider the plan fully delivered.

The handoff lives in `<tasks_folder>/Handoff_Phase_<next_phase_id>.md`; the next
phase issue's `**Handoff in:**` line points at this file in the repo, so no GitHub
body edit is needed for handoff propagation.

### GitHub updates (2 `gh` calls):

1. **Close the current phase issue:**

```bash
gh issue close <current_phase_issue>
```

2. **Check off the phase in the plan overview issue** (canonical 4-step pattern from SKILL.md § Updating Issue Body Checklists):
   1. `Bash`: `gh issue view <plan_overview_issue> --json body -q .body` — capture stdout.
   2. `Write` tool: save to `/tmp/overview_body.md`.
   3. `Edit` tool: `old_string: "- [ ] Phase <N>: <phase_name> (<task_count> tasks) — #<current_phase_issue>"`, `new_string: "- [x] Phase <N>: <phase_name> (<task_count> tasks) — #<current_phase_issue>"`.
   4. `Bash`: `gh issue edit <plan_overview_issue> --body-file /tmp/overview_body.md`.
