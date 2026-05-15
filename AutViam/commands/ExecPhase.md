# ExecPhase

Execute all tasks in a phase through gates A → B → C, enforce the 3-failure-per-gate cap, and update the phase issue at meaningful boundaries only.

**Inputs:** `<phase_id>` (int, required); `<plan_file>` (required); `<tasks_folder>`, `<tracking_file>` (defaults per SKILL.md).

---

## Step 1 — Load context (no full plan re-read)

Read in this order:
- `<tasks_folder>/Phase_<phase_id>_context_summary.md` — primary context
- `<tasks_folder>/all-tasks.md` — to identify tasks in this phase and their cross-phase blockers
- `<tasks_folder>/github_issue_map.json` — for the phase issue number and repo
- `<tasks_folder>/gates/phase_<phase_id>_gates.md` — initialize if absent

For `<phase_id>` > 1: read `<tasks_folder>/Handoff_Phase_<phase_id>.md` in full.

**Open `<plan_file>` only on the `plan_lines` ranges of tasks in this phase.** Never read the plan in full.

**Cross-phase pattern scan:** quickly grep all `gates/phase_*_gates.md` files for the failure modes most relevant to this phase's risk profile (see `references/failure_modes.md`). Note recurring patterns so the implementer can be warned upfront.

## Step 2 — Task analysis

For each task in `<phase_id>`, write to `<tasks_folder>/Phase_<phase_id>_Tasks_analysis.md`:

```
| Task ID | Title | Complexity (1-5) | Risk (1-5) | Combined | Blocked By | Blocks |
|---|---|---|---|---|---|---|
```

Apply the model assignment rule from SKILL.md § Model Assignment — do not restate it here.

## Step 3 — Branch setup

```bash
git checkout -b <plan_slug>_phase-<phase_id>
```

Never implement on `main`/`master` without explicit user consent.

## Step 4 — Execution order

1. **Never start a task whose blockers aren't `status="done"` in their JSONs.**
2. **Parallel first pass:** identify tasks where `complexity ≤ 3 AND risk ≤ 3 AND all blockers done`. Dispatch up to 4 concurrent. Before each batch, check that no two tasks in the batch modify the same file (compare `deliverables` and `scope`); if they would, sequence them.
3. **Sequential high-risk:** tasks where complexity OR risk > 3 run one at a time, each in its own commit.
4. After each batch, re-evaluate eligibility.

## Step 5 — Implementer dispatch (per task)

Dispatch via the Task tool using `templates/task_instructions_template.md`. The template tells the implementer to `Read` the task JSON itself — **do not paste JSON content into the prompt**.

Pass to the implementer:
- `task_json_path: <tasks_folder>/json/<task_id>.json`
- `phase_context_path: <tasks_folder>/Phase_<phase_id>_context_summary.md`
- `handoff_path` (if phase > 1)
- Plan excerpts: only the `plan_lines` ranges from the task's `plan_assets` (or none)
- Any cross-phase failure patterns from Step 1's scan that match this task's risk

If the implementer asks clarifying questions before starting, answer them fully before allowing it to proceed.

**Initialize the task entry** in `gates/phase_<phase_id>_gates.md` (see `templates/gate_entry.md`).

**No `gh` call here.** Tasks transition to `in-progress` only at phase level — there is no per-task issue to label.

## Step 6 — Review gates (A → B → C, sequential, cap = 3 failures per gate)

After each implementer reports completion, run gates in order. **No `gh` calls during gate loops** — record everything in `gates/phase_<phase_id>_gates.md` (format: `templates/gate_entry.md`).

**Failure-cap rule (non-negotiable):** track `gate_a_failures` and `gate_b_failures` and `gate_c_failures` per task. On the **3rd** failure of any one gate, the next attempt is the last. If that 4th attempt also fails on the same gate → **gate cap hit** → go to Step 7.

### Gate A — Spec Compliance

Dispatch the `autviam-spec-reviewer` agent:

```
Agent(subagent_type="autviam-spec-reviewer", prompt="""
task_json_path: <tasks_folder>/json/<task_id>.json
base_sha: <pre-task SHA>
head_sha: <current HEAD>
implementer_report: <one-line summary>
prior_failure_summary: <only if retry — copy the Issues list from the prior gate entry>
""")
```

If the agent is not installed, fall back to dispatching the Task tool with the agent's system prompt inlined (see `agents/autviam-spec-reviewer.md`).

Parse the verdict line. On FAIL: record the failure entry in the gates file (1–2 sentences + JSON block with `failure_mode`, `what_failed`, `why`). Pass the agent's Issues list to the implementer, ask it to fix, re-run Gate A. Increment `gate_a_failures`.

### Gate B — Domain Quality

Only after Gate A passes.

**Pre-dispatch specialist check (deterministic bash):**
```bash
# Check if repo-local specialist config exists
test -f <skill_root>/autviam_config.json && cat <skill_root>/autviam_config.json
```
If the config exists, read `domain_reviewer.specialists`. For each specialist run:
```bash
git diff --name-only <base_sha>..<head_sha> | grep -E 'pattern1|pattern2|...'
# (OR logic — any match qualifies)
```
Build `specialist_agents`: include only specialists where at least one diff file matched.
If the config is absent or `specialist_agents` is empty, omit the field from the prompt
(backward compatible — reviewer skips the specialist section entirely).

Dispatch `autviam-domain-reviewer`:

```
Agent(subagent_type="autviam-domain-reviewer", prompt="""
task_json_path: <tasks_folder>/json/<task_id>.json
base_sha: <pre-task SHA>
head_sha: <current HEAD>
implementer_report: <one-line summary>
phase_context_path: <tasks_folder>/Phase_<phase_id>_context_summary.md
design_docs_dir: dev/design_docs/   # if exists
prior_failure_summary: <only if retry>
specialist_agents: <JSON list — omit line if empty>
""")
```

On FAIL: record, pass Issues list to implementer, re-run **Gate A then Gate B** (Gate A may regress on fixes). Increment `gate_b_failures`.

### Gate C — Verification

Run task-relevant tests fresh. Apply the Iron Law:

> Identify the command → run it fresh → read full output → pass = ≥ 95% on task-relevant tests → record exact counts in the gates file. No "should pass" / "probably works" claims.

On FAIL: record, return to implementer with actual test output. Increment `gate_c_failures`.

### Retry compression

On any gate retry, the implementer prompt is just:

```
Fix the issues found by Gate <X>:
<paste agent's Issues list, ~3-10 lines>
Re-read your modifications and the spec. Re-run task tests.
```

Do not re-paste the original task description, diff, or report — the implementer Reads the JSON path it already has.

## Step 7 — Gate cap hit (4th failure on same gate)

When `gate_<x>_failures == 4` for a task:

1. **Mark the task in the gates file:** add a `## STATUS: gate-cap-hit on Gate <X>` block with the three failure entries summarized.
2. **Update the task JSON:** `"status": "gate-cap-hit"`, leave other completion fields untouched.
3. **Update the tracker:** mark this row `gate-cap-hit` with a link to the gates entry.
4. **GitHub:** add `gate-cap-hit` label to the **phase issue** (1 `gh` call). Do not edit the body or close anything yet.
5. **Stop dispatching new tasks.** Set an internal `stop_new_dispatches` flag.
6. **Wait for all in-flight parallel tasks to finish their current gate sequence.** They may themselves hit the cap — log each one the same way. Do not cancel them; let them complete (pass or cap).
7. **Once all parallel tasks have settled, surface the stop report and ask the user:**

   ```markdown
   ## ExecPhase halted — gate failure cap reached

   **Phase:** <phase_id> — `<phase_name>`
   **Branch:** `<plan_slug>_phase-<phase_id>`

   ### Tasks at cap
   - **<task_id>** — Gate <X> · 4 failures · failure modes seen: <list>
     Last issues: <paste the last agent Issues block>
   - <repeat per capped task>

   ### Tasks still pending
   <task IDs that hadn't started yet>

   ### Tasks completed this run
   <task IDs that passed all 3 gates>

   ### Options
   1. **Take over** — you implement the capped task(s) manually; pipeline resumes when you mark them `done` in the tracker.
   2. **Provide instructions** — give me extra context / a different approach; I retry the capped task(s) with failure counters reset to 0.
   3. **Skip task(s)** — I mark the capped task(s) `skipped`, cascade-skip dependents, and continue with the remaining independent tasks.
   4. **Rollback** — I revert the capped task(s)' commits (see `references/recovery.md`) and continue with remaining independent tasks.
   5. **Stop phase entirely** — I leave everything in place for manual inspection.

   What would you like to do?
   ```

   Read `references/recovery.md` only if the user picks option 4 or 5.

8. **Resume per user's choice.** Do not auto-resume.

## Step 8 — Task completion (all three gates pass)

### Local

Update the task JSON:
- `"status": "done"`, `"completion_date": "<today>"`
- `test_completion` (passed/total/pass_rate/commands from Gate C)
- `review_score`, `review_breakdown` (from Gate B)
- `"review_status": "approved"`
- `"implementation_branch": "<branch>"`
- `completion_notes` (notable decisions/deviations)

Update `<tracking_file>`: mark task done, fill `Verified by` / `PR/Commit` / `Completed on`.

Record completion timestamp in the gates file.

**Append the task ID to an in-memory `completed_this_phase` list.** No GitHub call here — checkbox flips are batched to Step 10.

## Step 9 — Repeat for all phase tasks

Return to Step 4 and process the next eligible batch. Continue until either:
- all tasks in `<phase_id>` are done, or
- gate cap hit (Step 7).

## Step 10 — Phase handoff and batched GitHub update

When all tasks in `<phase_id>` are done (or the user has chosen to continue past skipped/capped tasks):

### 10a. Handoff file

Generate `<tasks_folder>/Handoff_Phase_<phase_id+1>.md` from `templates/Handoff_template.md`. On the final phase, generate it as a project completion summary; skip the "edit next phase issue" implication.

### 10b. Batched phase-issue update (1 fetch + 1 push, 1 `MultiEdit`)

Per `references/issue_body_updates.md`:

1. `Bash`: `gh issue view <phase_issue> --json body -q .body`
2. `Write` tool: `/tmp/phase_<N>_body.md`
3. `MultiEdit`: for each task ID in `completed_this_phase`, replace `- [ ] <task_id>` → `- [x] <task_id>` (one MultiEdit call, N edits)
4. `Bash`: `gh issue edit <phase_issue> --body-file /tmp/phase_<N>_body.md --remove-label "in-progress" --add-label "done" --state closed` — body update, label swap, and close in one call.

### 10c. Plan overview checkbox

Per `references/issue_body_updates.md`:

1. `Bash`: `gh issue view <plan_overview_issue> --json body -q .body`
2. `Write` tool: `/tmp/overview_body.md`
3. `Edit` tool: `- [ ] Phase <N>: <phase_name> (<task_count> tasks) — #<phase_issue>` → `- [x] ...`
4. `Bash`: `gh issue edit <plan_overview_issue> --body-file /tmp/overview_body.md`

**Total `gh` budget for phase handoff: 4 calls** (1 phase view, 1 combined phase edit+close, 1 overview view, 1 overview edit). Compare to Aut_Faciam's 2 + 2N for per-task flips during the phase.

---

Phase `<phase_id>` is complete. Next: ScaffoldPhase / ExecPhase for the next phase.
