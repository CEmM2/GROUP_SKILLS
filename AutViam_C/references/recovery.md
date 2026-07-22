# Recovery and Rollback

Load this file only when (a) a task hits the gate failure cap (4th failure on the same gate), (b) Gate C fails repeatedly across reruns, or (c) the user chooses "rollback" at a gate-cap stop.

## Single-task rollback

1. **Find the last good commit.** → `<skill_root>/scripts/gate_state.py last-good-sha <tasks_folder>/gates/phase_<N>_gates.md` prints the most recent passing Gate C commit SHA (the `commit` field of the last `gate:"C", result:"pass"` JSON block). Exits non-zero if none is recorded.
2. **Revert the broken commit(s).** → `<skill_root>/scripts/phase_git.sh revert <bad_sha> [<bad_sha>…]` runs `git revert --no-edit` on each SHA **in reverse order**, preserving history. It **never** uses `git reset --hard` on a shared branch; on a conflict it stops and asks you to resolve by hand.
3. **Reset the task JSON.** → `<skill_root>/scripts/gate_state.py reset-task <tasks_folder>/json/<task_id>.json` sets `status="pending"` and clears `completion_date`, `test_completion`, `review_score`, `review_breakdown`, `review_status`, `implementation_branch`, `completion_notes`.
4. **Mark the tracker.** Add a `reverted` note in the tracker row pointing to the gate history entry that captured the failure pattern.
5. **Re-attempt or escalate.** Either re-dispatch with the failure context as additional guidance, or surface it for human intervention.

## Whole-phase rollback

If the phase branch is unrecoverable:

1. Create a fresh branch from the parent branch: → `<skill_root>/scripts/phase_git.sh branch <plan_slug> <N> --from <parent_branch>` (parent = the previous phase's tip, or `main` for Phase 1).
2. Identify completed tasks (`status="done"` in their JSONs) and incomplete tasks (anything else).
3. Re-execute only the incomplete tasks on the fresh branch — the gate history and JSONs tell you which to re-run.
4. Keep the old branch around until the new one passes Gate C across the phase; then delete the old branch.

## Stuck routing lock

`resolve_codex_agent.py` serializes routing-evidence writes with a lock directory
(`.<file>.routing-lock`) beside the target file. A resolver killed mid-write leaves it
behind, and because routing failures are fatal by design that would otherwise block every
later dispatch for the task.

Locks older than 300s are broken automatically on the next acquisition, so this normally
self-heals. If a dispatch still fails with `timed out acquiring routing evidence lock`,
either a live resolver is genuinely writing (wait), or the lock was abandoned less than
300s ago — inspect `owner.json` inside the lock directory for the holding PID, confirm
that process is gone, then remove the directory:

```bash
cat <path>/.<file>.routing-lock/owner.json   # {"pid": …, "acquired_at": …}
rm -rf <path>/.<file>.routing-lock
```

Removing the lock never discards evidence — evidence writes are atomic, so the task JSON
is either the pre-write or the post-write version, never a partial one.

## Gate-cap stop options the user may pick

When ExecPhase/ExecTask halts on a 4th-failure-on-same-gate, present these options:

- **Take over** — user implements the task by hand. Pipeline resumes once user marks the task `done` in the tracker.
- **Provide instructions** — user supplies extra context/clarification; pipeline retries the gate with `<failure_count>` reset to 0 and the new context appended to the implementer prompt.
- **Skip task** — task is marked `status="skipped"` in JSON and tracker; downstream tasks that depended on it are also marked `skipped` (cascade). Phase continues with remaining independent tasks.
- **Rollback this task** — apply single-task rollback above; phase continues with remaining tasks.
- **Stop phase entirely** — leave all in-flight artifacts in place; user inspects manually.
