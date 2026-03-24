# TiFEM Development Task Tracker Template

Generated on: YYYY-MM-DD
This tracker records execution status for the plan_name task set.

## plan_name Tracker

Plan source: `dev/plans/planned/plan_name.md`
Task index: `dev/tasks/plan_name/all-tasks.md`

| Task ID | Title | Status | Owner | Blocked by (open) | Blocks | Plan lines | PR/Commit | Verified by | Completed on |
|---|---|---|---|---|---|---|---|---|---|


## Update protocol

1. When a task starts, set `Status` to `in_progress`, assign `Owner`, and keep unresolved blockers in `Blocked by (open)`.
2. When a task is done, set `Status` to `done`, fill `PR/Commit`, `Verified by`, and `Completed on` (YYYY-MM-DD).
3. For each newly completed task, remove its ID from downstream rows in `Blocked by (open)` when applicable.

## Verification status

### Phase <number> aggregate verification:

#### Phase <number> mapping between test and task:

| Task ID | Title | Test file | 
|---|---|---|

#### Verification outcomes:

Assuming the tests folder is `tests/plan_tests`:

    `uv run pytest tests/plan_tests -v` -> pass/total passed (100*pass/total%)

