# ScaffoldPhase

Pre-execution scaffolding — generates test stubs, populates test fields in task JSONs, pre-fills the tracker, and populates the phase issue body.

**Inputs:** `<phase_id>` (int, required); `<plan_file>` (required); `<tasks_folder>`, `<tracking_file>` (default per SKILL.md).

---

## Step 0 — Re-scaffold check

If `Phase_<phase_id>_Scaffold_Validation.md` exists in `<tasks_folder>`, warn the user (test stubs may be overwritten, JSONs re-updated). Proceed only on explicit confirmation. On confirm, rename the existing file to `Phase_<phase_id>_Scaffold_Validation_prev.md` first.

Also check the phase's label in `github_issue_map.json`: if `scaffolded` is already present, note this in the warning.

## Step 1 — Load context (no full plan re-read)

Read:
- `<tasks_folder>/Phase_<phase_id>_context_summary.md` — your primary reference
- `<tasks_folder>/all-tasks.md` — to identify tasks in this phase
- Each task JSON's `plan_lines` field, then read only those line ranges from `<plan_file>`. Never read the plan in full.

## Step 1b — Switch to the phase branch

Always scaffold phase `<phase_id>` on its own branch, forked from the plan branch (SKILL.md § Branch & Worktree Model). Inside the plan worktree (checked out on `<plan_slug>`):

→ `<skill_root>/scripts/phase_git.sh branch <plan_slug> <phase_id> --from <plan_slug>` — checks out `<plan_slug>_phase-<phase_id>` (creating it from the plan branch when new; refuses on a dirty tree — commit/stash first). `<plan_slug>` is in `github_issue_map.json`; if no map exists, derive it with `<skill_root>/scripts/init_plan.sh slug <plan_file>`.

(Skip when Plan-2-Tasks ran without a worktree/plan branch — scaffold on the current branch.)

## Step 2 — Discover existing tests **once**

Run a single file search for `tests/**/*.py` and take the first 60 results. Group by top-level subdirectory (e.g. `tests/unit/`, `tests/integration/`). Build a one-paragraph "test layout summary" string:

```
tests/ layout — unit (38 files under tests/unit/), integration (12 under tests/integration/),
plan_tests (4 under tests/plan_tests/). Naming pattern: test_<feature>.py with TestX classes.
```

This single string is reused for every routed scaffold agent in Step 4. Do **not** re-run the test discovery per task.

## Step 3 — Validate task JSONs

For each task in `<phase_id>`, read its JSON. Flag any of:

| Field | Flag if |
|---|---|
| `objective` | blank |
| `acceptance_criteria` | empty / placeholder |
| `implementation_steps` | < 2 real entries |
| `deliverables` | empty / placeholder |
| `risks` | empty / placeholder |
| `test_plan.tier` | blank |
| `test_plan.cases` | empty / placeholder |

Auto-fill rules (only these — not `objective`/`acceptance_criteria`/`implementation_steps`/`deliverables`, which need human intent):
- `test_plan.tier`: kernel/function → `unit`; cross-file linking → `integration`; behavioral regression → `regression`
- `test_plan.cases`: derive one per `acceptance_criteria` entry
- `risks`: infer from `implementation_steps` (new kernels, numerical integration, constitutive updates)

Create or update `<tasks_folder>/Phase_<phase_id>_Scaffold_Validation.md`:

```markdown
# Phase <phase_id> Scaffold Validation

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---|---|---|---|
```

`Scaffold Action` is `auto-filled` or `needs-human-review`. Don't block the phase on `needs-human-review` — continue scaffolding and surface the gap in the summary.

## Step 4 — Generate test stubs (parallel routed agents)

For each task in `<phase_id>`, apply SKILL.md § Codex Agent Assignment with `--dispatcher-capabilities <skill_root>/runtime/subagent-dispatch-capabilities.json --task-json <task-json> --role implementer --evidence-file <same-task-json> --purpose scaffold`, then execute the resolver-selected mode with the exact returned implementer prompt and task inputs. If a legacy task lacks either score, assign both once with `references/codex-routing-scoring.md`, write them to its JSON, and mark `legacy_score_backfill: true` before invoking the resolver. Never pass copied task scores with raw `--complexity/--risk`, and never treat `profile_projection.name` as a native type without an explicit capability. Spawn all eligible agents in parallel, one per task, up to 4 concurrent. A routing failure or `unavailable` mode is fatal.

**Pass to each routed agent (do NOT paste the JSON):**

```
task_json_path: <tasks_folder>/json/<task_id>.json
phase_context_path: <tasks_folder>/Phase_<phase_id>_context_summary.md
test_layout_summary: <the single string from Step 2>
qmd_search_terms: <2-3 representative terms from objective>
```

**Worker instructions:**

1. Read the task JSON. Use `objective`, `acceptance_criteria`, `test_plan`, `deliverables`.
2. Search the project's test collection via `/qmd-search` with `type:'lex'` and `type:'vec'` queries on the search terms. Find tests whose names, docstrings, or tested symbols overlap with `objective`/`acceptance_criteria`/`deliverables`.
3. Classify each `test_plan.cases` entry as `covered`, `partial`, or `missing`. Skip stub creation entirely if all are `covered`.
4. Determine the test file path: follow the layout in `test_layout_summary`. Stub filename is always `test_<task_id>.py`. Place it at `tests/plan_tests/test_<task_id>.py` whether or not `tests/plan_tests/` already exists — create the directory if missing.
5. Generate one stub per `partial`/`missing` case:

   ```text
   import pytest

   class TestTask<TaskId>:
       """Tests for Task <task_id>: <title>. AC covered: <indices>."""

       @pytest.mark.<tier>
       def test_<case_description>(self):
           """Verifies: <what>. AC: <criterion>. Passes when: <expected>."""
           pytest.skip("stub — implement after Task <task_id>")
   ```

6. Report back (concise):
   - Stub path written (or "all cases covered, no stub")
   - For each case: classification + (existing test path or new stub function name)

Wait for all routed agents.

## Step 5 — Update task JSONs

For each task, touch **only** these fields:

```json
"test_plan": { "tier": "...", "cases": [...] },
"test_artifacts": ["<existing test files>", "<new stub file>"],
"verification_commands": [
  "uv run pytest <existing>::TestX::test_y -v",
  "uv run pytest tests/plan_tests/test_<task_id>.py -v"
]
```

Rules:
- Use `::Class::method` scoping in `verification_commands` where possible.
- If `test_plan.cases` was already non-placeholder, append rather than overwrite.
- Don't touch any other field.

## Step 6 — Pre-fill tracker

Open `<tracking_file>`, find the Phase `<phase_id>` section, fill the mapping table and verification outcomes block from Step 4 reports.

## Step 7 — Scaffold summary

Append to `Phase_<phase_id>_Scaffold_Validation.md`:

```markdown
## Scaffold Summary

| Metric | Value |
|---|---|
| Tasks scaffolded | N |
| Cases covered | N |
| Cases stubbed | N |
| Tasks needing review | N |
| Files created | N |

## Existing Test Coverage Found
| Task ID | Test case | Test file | Function | Coverage |
|---|---|---|---|---|

## Tasks Needing Human Review Before Execute
| Task ID | Title | Field | Issue |
|---|---|---|---|

## Ready for Execute
- Task X: <title>
- ...
```

Print this summary to the console.

## Step 8 — Populate phase issue (1 `gh` call, no per-task issues)

**Pre-check:** `gh auth status`. If unavailable, skip Step 8 — all local artifacts are already complete.

Render the populated body from `templates/phase_populated_issue.md` to `<tasks_folder>/scratch/phase_<N>_body.md`. The body's `### Tasks` section lists every task as a checkbox referencing the task ID and title:

```
- [ ] P<N>-1 — <task_title>
- [ ] P<N>-2 — <task_title>
```

There are no task issue numbers — the checkbox text is the only identifier. ExecPhase/ExecTask flip these to `- [x]` on completion.

Push the body and swap labels in a single call:

→ `<skill_root>/scripts/issue_body.sh push <phase_issue> <tasks_folder>/scratch/phase_<N>_body.md --remove-label not-scaffolded --add-label scaffolded`

(One `gh` call: body update + label swap together. The script skips and exits 3 if `gh` is unauthenticated.)

**Project sync (gated):** also set the phase item's Status to `Todo` — self-gated/best-effort, no-ops if project is disabled (see `references/project_sync.md`):

```bash
<skill_root>/scripts/project_sync.sh status <tasks_folder>/github_issue_map.json phase:<N> Todo
```

**Total `gh` budget for Step 8: 1 call** (+1 best-effort project call when armed; vs N+2 in Aut_Faciam).

---

Phase `<phase_id>` is scaffolded and ready for ExecPhase.
