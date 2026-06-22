# Recovery and Rollback

Load this file only when (a) a task hits the gate failure cap (4th failure on the same gate), (b) Gate C fails repeatedly across reruns, or (c) the user chooses "rollback" at a gate-cap stop.

## Single-task rollback

1. **Find the last good commit.** → run `<skill_root>/scripts/gate_state.py last-good-sha <gates_file>` (`<gates_file>` = `gates/phase_<N>_gates.md`). It scans the gate file and prints the most recent passing Gate C commit SHA (exits non-zero if none found).
2. **Revert the broken commit(s).** → run `<skill_root>/scripts/phase_git.sh revert <bad_sha> [<bad_sha>…]`. It `git revert --no-edit`s each SHA in **reverse order** (preserves history; **never** `git reset --hard` on a shared branch). On a revert conflict it stops and tells you to resolve by hand.
3. **Reset the task JSON.** → run `<skill_root>/scripts/gate_state.py reset-task <task_json>`. It sets `status="pending"` and clears `completion_date`, `test_completion`, `review_score`, `review_breakdown`, `review_status`, `implementation_branch`, `completion_notes` to template defaults.
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
