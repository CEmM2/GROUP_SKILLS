# Recovery and Rollback

Load this file only when (a) a task hits the gate failure cap (4th failure on the same gate), (b) Gate C fails repeatedly across reruns, or (c) the user chooses "rollback" at a gate-cap stop.

## Single-task rollback

1. **Find the last good commit.** Open `gates/phase_<N>_gates.md`, locate the most recent passing Gate C entry for any task on the current branch — its JSON block carries the commit SHA.
2. **Revert the broken commit(s).** `git revert <bad_sha>` for each commit introduced by the failing task, in reverse order. Preserves history. **Never** use `git reset --hard` on a shared branch.
3. **Reset the task JSON.** Set `status="pending"`, clear `completion_date`, `test_completion`, `review_score`, `review_breakdown`, `review_status`, `implementation_branch`, `completion_notes`.
4. **Mark the tracker.** Add a `reverted` note in the tracker row pointing to the gate history entry that captured the failure pattern.
5. **Re-attempt or escalate.** Either re-dispatch with the failure context as additional guidance, or surface it for human intervention.

## Whole-phase rollback

If the phase branch is unrecoverable:

1. Create a fresh branch from the parent branch (`<plan_slug>_phase-<N>` from the previous phase's tip, or `main` for Phase 1).
2. Identify completed tasks (`status="done"` in their JSONs) and incomplete tasks (anything else).
3. Re-execute only the incomplete tasks on the fresh branch — the gate history and JSONs tell you which to re-run.
4. Keep the old branch around until the new one passes Gate C across the phase; then delete the old branch.

## Gate-cap stop options the user may pick

When ExecPhase/ExecTask halts on a 4th-failure-on-same-gate, present these options:

- **Take over** — user implements the task by hand. Pipeline resumes once user marks the task `done` in the tracker.
- **Provide instructions** — user supplies extra context/clarification; pipeline retries the gate with `<failure_count>` reset to 0 and the new context appended to the implementer prompt.
- **Skip task** — task is marked `status="skipped"` in JSON and tracker; downstream tasks that depended on it are also marked `skipped` (cascade). Phase continues with remaining independent tasks.
- **Rollback this task** — apply single-task rollback above; phase continues with remaining tasks.
- **Stop phase entirely** — leave all in-flight artifacts in place; user inspects manually.
