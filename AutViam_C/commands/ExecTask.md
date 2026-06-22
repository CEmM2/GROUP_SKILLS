# ExecTask

Execute a single task through gates A → B → C, enforce the 3-failure cap, then present a full report. Use when you want to work through one task at a time with visibility before moving on.

**Inputs:** `<task_id>` (e.g. `P2-3`, required); `<plan_file>` (required); `<tasks_folder>`, `<tracking_file>` (defaults per SKILL.md).

---

## Step 1 — Load and validate

Read `<tasks_folder>/json/<task_id>.json`. Extract `phase` from `task.phase`.

Then read:
- `<tasks_folder>/Phase_<phase>_context_summary.md`
- `<tasks_folder>/all-tasks.md`
- `<tasks_folder>/Handoff_Phase_<phase>.md` (if phase > 1)
- `<tasks_folder>/github_issue_map.json`
- `<tasks_folder>/gates/phase_<phase>_gates.md` — scan for past failure patterns relevant to this task

Open `<plan_file>` only at the task's `plan_lines` range — never in full.

**Preconditions:**
- All `task.blocked_by` entries must have `status="done"` in their JSONs. If any blocker is pending, report and stop.
- Task `status` must not already be `"done"`. If it is, ask for confirmation before re-executing.
- Task `status` must not be `"gate-cap-hit"` from a prior run unless the user is explicitly retrying with new instructions (in which case reset failure counters to 0).

Compute complexity and risk (1–5 each). Apply SKILL.md § Codex Agent Assignment.

## Step 2 — Branch setup

If not already on `<plan_slug>_phase-<phase>`:

→ `<skill_root>/scripts/phase_git.sh branch <plan_slug> <phase> [--from <parent_branch>]`

It checks out (or creates) `<plan_slug>_phase-<phase>`, **refuses on a dirty working tree** (commit/stash first, or `--force`), and prints the branch name. `plan_slug` lives in `github_issue_map.json`. If no map exists (Plan-2-Tasks was run without GitHub), derive it with `<skill_root>/scripts/init_plan.sh slug <plan_file>`.

## Step 3 — Implementer dispatch

Dispatch a Codex `worker` using `templates/task_instructions_template.md`. Pass paths and excerpts only — do not paste JSON content. The calling agent owns integration, gate execution, and final commits after the worker returns.

**Pre-dispatch skill check (deterministic):** same as ExecPhase Step 5 —
→ `<skill_root>/scripts/match_specialists.sh <skill_root>/autviam_c_config.json implementer.skills <base_sha> <head_sha>`
prints the JSON array of matched `implementer.skills` entries (or `[]`). Use it as `implementer_skills`; omit the `## Repo-configured skills` section from the prompt when empty.

Initialize the gate file and task entry in `gates/phase_<phase>_gates.md`:
→ `<skill_root>/scripts/gate_state.py init <tasks_folder>/gates/phase_<phase>_gates.md --phase <phase> --plan <plan_file> --branch <branch>`
→ `<skill_root>/scripts/gate_state.py init-task <tasks_folder>/gates/phase_<phase>_gates.md <task_id> "<title>"`

**No `gh` call here** — there is no per-task issue under AutViam_C.

## Step 4 — Gates (cap = 3 failures per gate)

Run A → B → C in sequence. The gates file is the source of truth for the per-gate failure count — after recording each FAIL block, run `gate_state.py cap-check <tasks_folder>/gates/phase_<phase>_gates.md <task_id> <gate>` (→ cap step on `CAP-HIT`) and `gate_state.py sync-counters <tasks_folder>/gates/phase_<phase>_gates.md <task_id>`. Never track failure counts in memory.

### Gate A — Spec Compliance
Dispatch `autviam-spec-reviewer` as a Codex `explorer` prompt profile (see ExecPhase Step 6 for the prompt template). Parse verdict. If Codex agent dispatch is unavailable, run the profile inline and record `review_mode="inline"`. On FAIL: record the JSON block (`gate:"A"`, `result:"fail"`), run `cap-check … A` + `sync-counters`, then loop.

### Gate B — Domain Quality
Only after Gate A passes.

**Pre-dispatch specialist check (deterministic):** same as ExecPhase Gate B —
→ `<skill_root>/scripts/match_specialists.sh <skill_root>/autviam_c_config.json domain_reviewer.specialists <base_sha> <head_sha>`
prints the JSON array of matched specialists (or `[]`). Use it as `specialist_agents`; omit from the domain reviewer prompt when empty.

Dispatch `autviam-domain-reviewer` as a Codex `explorer` prompt profile. On FAIL: record the JSON block (`gate:"B"`, `result:"fail"`), run `cap-check … B` + `sync-counters`, re-run **Gate A then Gate B**.

### Gate C — Verification
Run task tests fresh. Apply the Iron Law: identify → run → read → require ≥ 95% on task-relevant tests → record exact counts. No "should pass" claims. On FAIL: record the JSON block (`gate:"C"`, `result:"fail"`), run `cap-check … C` + `sync-counters`. On PASS, the Gate C JSON block records `result:"pass"` + the `commit` SHA (read later by `last-good-sha` for rollback).

### Retry compression
On any retry, pass the implementer just the reviewer's Issues list (~3–10 lines) + "Re-read your modifications and the spec. Re-run task tests." Do not re-paste the original task description or diff.

### Gate cap hit (`cap-check` reports `CAP-HIT` — 4th failure on same gate)
1. Update task JSON: → `<skill_root>/scripts/gate_state.py set-status <tasks_folder>/json/<task_id>.json gate-cap-hit`.
2. Record a `## STATUS: gate-cap-hit on Gate <X>` block in the gates file with all three failures summarized.
3. Update the tracker.
4. → `<skill_root>/scripts/issue_body.sh label <phase_issue> --add gate-cap-hit` (1 `gh` call).
5. Surface the stop report and ask the user:

```markdown
## ExecTask halted — gate failure cap reached

**Task:** <task_id> — <title>
**Gate that capped:** <X>
**Failure modes seen:** <list>

### Failure history
- Attempt 1: <one-line summary>
- Attempt 2: <one-line summary>
- Attempt 3: <one-line summary>
- Attempt 4 (final): <one-line summary>

### Last reviewer Issues
<paste the agent's Issues block from the 4th attempt>

### Options
1. Take over (you implement; mark task `done` in tracker when finished)
2. Provide instructions and retry (resets failure counters)
3. Skip task (cascade-skip dependents)
4. Rollback this task (see `references/recovery.md`)
5. Stop and inspect manually

What would you like to do?
```

Read `references/recovery.md` only if option 4 or 5 is picked. Do not auto-resume.

## Step 5 — Completion (all three gates pass)

### Local
Write the completion fields in one deterministic call:
→ `<skill_root>/scripts/gate_state.py complete <tasks_folder>/json/<task_id>.json --branch <branch> --passed <p> --total <t> --review-score <s> [--minor m --medium m --high m --critical m] [--commands "cmd1" …] [--notes "note1" …] [--date <today>]`

It sets `status="done"`, `completion_date`, `test_completion`, `review_score` + `review_breakdown`, `review_status="approved"`, and `implementation_branch`. You supply `--notes` (LLM judgment).

Update `<tracking_file>` (mark done, fill verification cells).

Record completion in the gates file.

### GitHub (1 `gh` call, batched-style for the single task)
Per `references/issue_body_updates.md`:

1. → `<skill_root>/scripts/issue_body.sh fetch <phase_issue>` (prints the body).
2. Materialise the captured body to `/tmp/phase_<N>_body.md` with a Codex file-editing tool.
3. Edit the temp file: `- [ ] <task_id>` → `- [x] <task_id>` (exact-string)
4. → `<skill_root>/scripts/issue_body.sh push <phase_issue> /tmp/phase_<N>_body.md`

**Budget:** 2 `gh` calls for the body roundtrip. No labels, no per-task issue. If this is the last task remaining in the phase, also do the phase handoff sequence from ExecPhase Step 10.

## Step 6 — Present report

Show the user:

```markdown
## Task <task_id>: <title> — Complete

### Implementation Summary
<what was built, files changed>

### Gate History
**Gate A:** <N> attempts → Pass
**Gate B:** <N> attempts → Pass
**Gate C:** <pass>/<total> (<percentage>%)

### Failure Patterns (if any)
<failure modes encountered and resolutions; flag matches with prior phases>

### Files Changed
<list>

### Test Evidence
<exact counts from Gate C>

### Open Questions
<anything flagged by implementer or reviewers>
```

Save this report to `<tasks_folder>/reports/<task_id>_report.md` (create `reports/` if absent).

**Ask:** "Ready to proceed to the next task, or want to discuss anything about this one?"
