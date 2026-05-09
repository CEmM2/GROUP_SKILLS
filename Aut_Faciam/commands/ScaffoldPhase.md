# ScaffoldPhase

Pre-execution scaffolding pass — generates test stubs, populates test fields in task JSONs, pre-fills the tracker's test-task mapping table, and publishes task issues to GitHub.

**Inputs:**
- `<phase_id>`: the phase to scaffold (integer)
- `<plan_file>`: path to the markdown plan, spec, or RFC document
- `<tasks_folder>`: if provided, otherwise defaults to `dev/tasks/<plan file name>/`
- `<tracking_file>`: if provided, otherwise defaults to `dev/tracking/tasks-tracker_<plan file name>.md`

---

## Step 0 — Re-scaffold Check

If `Phase_<phase_id>_Scaffold_Validation.md` already exists in `<tasks_folder>`, this phase was previously scaffolded. Warn the user and list what will be affected (test stubs may be overwritten, task JSONs will be re-updated). Proceed only with explicit confirmation. If the user confirms, rename the existing validation file to `Phase_<phase_id>_Scaffold_Validation_prev.md` before continuing.

Also check the phase issue labels in `github_issue_map.json` — if the phase was already scaffolded (label `scaffolded` present), note this in the warning.

---

## Step 1 — Load Context

Read the `<plan_file>` in full to understand:
- The purpose and goals of `<phase_id>`
- The domain and physics context (e.g. constitutive model being implemented, numerical method, solver type)
- Any explicit testing requirements or constraints called out in the plan

Find the context summary file (`Phase_<phase_id>_context_summary.md`) in `<tasks_folder>`. This is your reference context — use it to fill in any missing context in the task JSONs.

Read `all-tasks.md` inside `<tasks_folder>` to identify all tasks belonging to `<phase_id>`.

---

## Step 2 — Read and Validate All Task JSONs for the Phase

For each task in `<phase_id>`, read its JSON file from `<tasks_folder>/json/`.

Check the following fields and flag any that are empty, missing, or contain only placeholder strings:

| Field | Flag if |
|-------|---------|
| `objective` | blank or `""` |
| `acceptance_criteria` | empty array or `[""]` |
| `implementation_steps` | fewer than 2 real entries |
| `deliverables` | empty array or `[""]` |
| `risks` | empty array or `[""]` |
| `test_plan.tier` | blank |
| `test_plan.cases` | empty array or `[""]` |

Produce `Phase_<phase_id>_Scaffold_Validation.md` in `<tasks_folder>`:

```markdown
# Phase <phase_id> Scaffold Validation

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---------|-------|-----------------------------|-----------------|
```

Set `Scaffold Action` per flagged field to one of:
- `auto-filled` — can be inferred from objective / acceptance criteria / plan context
- `needs-human-review` — too ambiguous to fill without human implementation intent

**Auto-fill rules:**
- `test_plan.tier`: infer from task type — kernel/function → `unit`; linking several files → `integration`; regression against prior behavior → `regression`
- `test_plan.cases`: derive from `acceptance_criteria` — each criterion maps to at least one test case description
- `risks`: if empty, infer from `implementation_steps` — flag any step involving new Taichi kernels, numerical integration, or constitutive updates as risk-bearing

Do not auto-fill `objective`, `acceptance_criteria`, `implementation_steps`, or `deliverables` — these require human intent. Mark them `needs-human-review` and continue scaffolding anyway; do not block the phase.

---

## Step 3 — Generate Test Stubs

For each task in `<phase_id>`, spawn a subagent (Haiku is sufficient — this is a read-and-template task) to generate test stubs.

Provide each subagent with:
- The full task JSON content
- The plan context for this phase
- The existing test folder structure: use Glob to search `tests/**/*.py` and include the first 40 results so the subagent can match naming conventions

The subagent must:

1. **Search for existing tests** that already cover this task before generating anything:
   - Use `/qmd-search` to search the project's test collection for test functions or classes whose names, docstrings, or tested symbols overlap with the task's `objective`, `acceptance_criteria`, or `deliverables`
   - Use both lexical (`type:'lex'`) and semantic (`type:'vec'`) queries with 2-3 representative terms from the task objective
   - For each existing test found, assess whether it fully covers a `test_plan.cases` entry, partially covers it, or is unrelated
   - Classify each `test_plan.cases` entry as: `covered`, `partial`, or `missing`
   - Only generate stubs for `partial` and `missing` cases
   - If all cases are `covered`, skip stub file creation entirely and report findings

2. Determine the correct test file path by following the existing naming convention in `tests/`. If a plan-specific subfolder exists (e.g. `tests/plan_tests/`), place stubs there. If no convention is clear, use `tests/plan_tests/test_<task_id>.py`.

3. Generate a stub file with:
   - One test function per entry in `test_plan.cases`
   - Function names derived from the case description (snake_case, descriptive)
   - A docstring per function stating: what it verifies, which `acceptance_criteria` entry it covers, and what a passing result looks like
   - `pytest.mark` decorators based on `test_plan.tier`
   - `pytest.skip("stub — implement after Task <task_id> is complete")` as the body

   ```python
   import pytest
   # TODO: replace with actual imports after Task <task_id> implementation
   # from <package>.<module> import <symbol>

   class TestTask<TaskId>:
       """
       Tests for Task <task_id>: <title>
       Acceptance criteria covered: <list criteria indices>
       """

       @pytest.mark.<tier>
       def test_<case_description>(self):
           """
           Verifies: <what this test checks>
           Acceptance criterion: <criterion text>
           Passes when: <expected outcome>
           """
           pytest.skip("stub — implement after Task <task_id> is complete")
   ```

4. Write the stub file to disk.

5. Report back:
   - Existing tests found and their coverage classification per case
   - Stub file path written (or "no stub needed — all cases covered")
   - Number of new stubs generated
   - One line per stub: function name + which criterion it covers
   - One line per covered case: existing test path + function name

Spawn all subagents in parallel — one per task. Wait for all to report before proceeding.

---

## Step 4 — Update Task JSONs

After all subagents report, update each task's JSON file. Only touch the following fields — leave all others unchanged:

```json
"test_plan": {
    "tier": "<inferred or existing tier>",
    "cases": ["<case 1 (covered)>", "<case 2 (partial)>", "<case 3 (missing)>"]
},
"test_artifacts": [
    "tests/existing/test_existing_coverage.py",
    "tests/plan_tests/test_<task_id>.py"
],
"verification_commands": [
    "uv run pytest tests/existing/test_existing_coverage.py::TestClass::test_relevant -v",
    "uv run pytest tests/plan_tests/test_<task_id>.py -v"
]
```

Rules:
- `test_artifacts`: include both existing test files that cover this task AND the new stub file (if one was created)
- `verification_commands`: include targeted pytest commands for both existing relevant tests and new stubs. Use `::Class::method` scoping where possible
- If `test_plan.cases` was already populated with non-placeholder content, do not overwrite — append only
- Do not touch `status`, `completion_date`, `test_completion`, `review_score`, `review_breakdown`, `review_status`, or `implementation_branch`

---

## Step 5 — Pre-fill Tracker Test-Task Mapping

Open `<tracking_file>` and locate the section for Phase `<phase_id>`. Pre-fill the mapping table and verification outcomes block.

---

## Step 6 — Scaffold Summary Report

Append to `Phase_<phase_id>_Scaffold_Validation.md`:

```markdown
## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | N |
| Cases covered | N |
| Cases stubbed | N |
| Tasks needing review | N |
| Files created | N |
| Auto-filled fields | <list> |

## Existing Test Coverage Found

| Task ID | Test case | Existing test file | Function | Coverage |
|---------|-----------|-------------------|----------|----------|

## Tasks Needing Human Review Before Execute

| Task ID | Title | Field | Issue |
|---------|-------|-------|-------|

## Ready for Execute

Fully scaffolded:
- Task X: <title>
- ...

Needs human review before execution:
- Task Z: <title> — missing: <field names>
```

Print this summary to the console so it is visible without opening the file.

---

## Step 7 — Populate Phase Issue and Create Task Issues

**Pre-check:** Run `gh auth status`. If `gh` is unavailable, skip this step entirely — all local scaffold artifacts (validation, stubs, updated JSONs, tracker) are already complete. Warn the user.

### 7a. Read the issue map

Load `<tasks_folder>/github_issue_map.json` to get the plan slug, phase issue number, and repo info. The `plan_slug` field is used to prefix all issue titles and apply the `plan:<slug>` label.

### 7b. Create task-level issues (in dependency order)

Process tasks in dependency order (blockers first) so that `Blocked by #N` references resolve to real issue numbers.

For each task, create a task issue using the template at `templates/task_issue.md`. Populate it from the task JSON + scaffold findings (existing test coverage, stubs, acceptance criteria).

```bash
gh issue create --title "[<slug>] <task_id>: <task_title>" \
  --label "task-issue,phase-<N>,tier:<tier>,plan:<slug>" \
  --body-file <tempfile>
```

Add the `blocked` label if the task has ANY entries in `blocked_by` whose corresponding task JSONs do not have `"status": "done"`. At scaffold time this typically means most cross-phase dependencies and all within-phase dependencies are unresolved. That's expected — ExecPhase will remove the `blocked` label as blockers complete. Only tasks with zero blockers (or all blockers already done from previous phases) should start without the label.

Capture the returned issue number. Save to `github_issue_map.json` immediately after each successful creation (for crash resilience).

### 7c. Update the phase issue

Replace the skeleton phase issue body with the populated version using the template at `templates/phase_populated_issue.md`. Include:
- Scaffold summary metrics (collapsed: tasks scaffolded / cases covered / cases stubbed / tasks needing review / files created)
- Task checklist with real issue numbers (`- [ ] #<task_issue> — <title>`)
- A `**Context:**` link to `Phase_<N>_context_summary.md` (relative path; do not embed)
- A `**Handoff in:**` link to `Handoff_Phase_<N>.md` if it exists (relative path; do not embed)

Because this is a full body replacement (not a surgical edit), use the `Write` tool to build the new body from the template, then push it:

1. `Write` tool: render the populated template into `/tmp/phase_body.md`.
2. `Bash`: `gh issue edit <phase_issue> --remove-label "not-scaffolded" --add-label "scaffolded" --body-file /tmp/phase_body.md`.

### 7d. Update issue map and task JSONs

Update `github_issue_map.json` with the task issue numbers under `phases.<N>.task_issues`.

Update each task JSON's `github_issue.task_issue` field with its issue number.

---

ultrathink
