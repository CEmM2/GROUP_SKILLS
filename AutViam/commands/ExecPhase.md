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

→ run `<skill_root>/scripts/phase_git.sh branch <plan_slug> <phase_id> --from <plan_slug>`. It checks out `<plan_slug>_phase-<phase_id>`, creating it from the **plan branch** `<plan_slug>` when new (so the phase merges cleanly back into it — SKILL.md § Branch & Worktree Model), **refuses on a dirty working tree** (commit/stash first), and prints the branch name. (When Plan-2-Tasks ran without a worktree, `<plan_slug>` may not exist — fall back to `--from <parent_branch>`, else current HEAD.)

Never implement on `main`/`master` without explicit user consent.

## Step 4 — Execution order

1. **Never start a task whose blockers aren't `status="done"` in their JSONs.**
2. **Parallel first pass:** identify tasks where `complexity ≤ 3 AND risk ≤ 3 AND all blockers done`. Dispatch up to 4 concurrent. Before each batch, check that no two tasks in the batch modify the same file (compare `deliverables` and `scope`); if they would, sequence them.
3. **Sequential high-risk:** tasks where complexity OR risk > 3 run one at a time, each in its own commit.
4. After each batch, re-evaluate eligibility.

## Step 5 — Implementer dispatch (per task)

Dispatch via the Task tool using `templates/task_instructions_template.md`. The template tells the implementer to `Read` the task JSON itself — **do not paste JSON content into the prompt**.

**Pre-dispatch skill check (deterministic):**
→ run `<skill_root>/scripts/match_specialists.sh <skill_root>/autviam_config.json implementer.skills <pre-task SHA> <current HEAD>`. It emits a JSON array of the matched `implementer.skills` config entries (each carrying its `skill`/`skill_md`) — entries whose `trigger_patterns` hit at least one file in the diff. Absent config or empty section → `[]`.
Use that array as `implementer_skills`. If it is empty, omit the `## Repo-configured skills` section from the prompt (backward compatible).
`skill_md` path: `<skill_root>/../<skill-dir>/SKILL.md` (resolve relative to the AutViam skill root).

Pass to the implementer:
- `task_json_path: <tasks_folder>/json/<task_id>.json`
- `phase_context_path: <tasks_folder>/Phase_<phase_id>_context_summary.md`
- `handoff_path` (if phase > 1)
- Plan excerpts: only the `plan_lines` ranges from the task's `plan_assets` (or none)
- Any cross-phase failure patterns from Step 1's scan that match this task's risk
- `implementer_skills` (if non-empty): inject as the `## Repo-configured skills` section in the template

If the implementer asks clarifying questions before starting, answer them fully before allowing it to proceed.

**Initialize the gate file and the task entry** (deterministic — `templates/gate_entry.md` is the format):
→ `<skill_root>/scripts/gate_state.py init <tasks_folder>/gates/phase_<phase_id>_gates.md --phase <phase_id> --plan <plan_file> --branch <branch>` (writes the header once; no-op if it already exists).
→ `<skill_root>/scripts/gate_state.py init-task <tasks_folder>/gates/phase_<phase_id>_gates.md <task_id> "<title>"` (adds the per-task section skeleton with the `**Failure counters:**` line; no-op if present).

**No `gh` call here.** Tasks transition to `in-progress` only at phase level — there is no per-task issue to label.

## Step 6 — Review gates (A → B → C, sequential, cap = 3 failures per gate)

After each implementer reports completion, run gates in order. **No `gh` calls during gate loops** — record everything in `gates/phase_<phase_id>_gates.md` (format: `templates/gate_entry.md`).

**Failure-cap rule (non-negotiable):** the failure counts live in the gates file, not memory — after recording each FAIL attempt block, run `<skill_root>/scripts/gate_state.py cap-check <gates_file> <task_id> <gate>`. It prints `OK n` (n fails so far) or `CAP-HIT n` once the 4th failure on the same gate is durable in the file. On `CAP-HIT` → go to Step 7. Also run `<skill_root>/scripts/gate_state.py sync-counters <gates_file> <task_id>` after each recorded attempt to refresh the `**Failure counters:**` line. (`<gates_file>` = `<tasks_folder>/gates/phase_<phase_id>_gates.md`.)

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

Parse the verdict line. On FAIL: **you author** the failure entry in the gates file (1–2 sentences of domain prose + the ```json``` attempt block with `failure_mode`, `what_failed`, `why`). Then run `gate_state.py cap-check <gates_file> <task_id> A` (and `sync-counters`); on `CAP-HIT` go to Step 7, else pass the agent's Issues list to the implementer, ask it to fix, and re-run Gate A.

### Gate B — Domain Quality

Only after Gate A passes.

**Pre-dispatch specialist check (deterministic):**
→ run `<skill_root>/scripts/match_specialists.sh <skill_root>/autviam_config.json domain_reviewer.specialists <base_sha> <head_sha>`. It emits the JSON array of `domain_reviewer.specialists` config entries whose `trigger_patterns` match at least one file in the diff (OR logic). Absent config or empty section → `[]`.
Use that array as `specialist_agents`. If it is empty, omit the `specialist_agents` line from the prompt below (backward compatible — reviewer skips the specialist section entirely).

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

On FAIL: **you author** the prose+JSON attempt block, then run `gate_state.py cap-check <gates_file> <task_id> B` (and `sync-counters`); on `CAP-HIT` go to Step 7, else pass the Issues list to the implementer and re-run **Gate A then Gate B** (Gate A may regress on fixes).

### Gate C — Verification

Run task-relevant tests fresh. Apply the Iron Law:

> Identify the command → run it fresh → read full output → pass = ≥ 95% on task-relevant tests → record exact counts in the gates file. No "should pass" / "probably works" claims.

**In worktree mode:** run the tests against the **main checkout's** environment, importing the **worktree's** source — the worktree's own `uv`/`.venv` is usually missing/broken. E.g. `PYTHONPATH=<worktree> <main_checkout>/.venv/bin/python -m pytest <task tests>` (or `cd <main_checkout> && PYTHONPATH=<worktree> uv run pytest …`). Don't `uv sync` a fresh venv inside the worktree. (SKILL.md § Branch & Worktree Model.)

On FAIL: **you author** the prose+JSON attempt block (with actual test output), then run `gate_state.py cap-check <gates_file> <task_id> C` (and `sync-counters`); on `CAP-HIT` go to Step 7, else return to the implementer with the actual test output.

### Retry compression

On any gate retry, the implementer prompt is just:

```
Fix the issues found by Gate <X>:
<paste agent's Issues list, ~3-10 lines>
Re-read your modifications and the spec. Re-run task tests.
```

Do not re-paste the original task description, diff, or report — the implementer Reads the JSON path it already has.

## Step 7 — Gate cap hit (4th failure on same gate)

When `cap-check` returns `CAP-HIT` (the 4th failure on the same gate is durable in the gates file):

1. **Mark the task in the gates file (you author this):** add a `## STATUS: gate-cap-hit on Gate <X>` block with the four failure entries summarized — prose, not a script.
2. **Update the task JSON:** → run `<skill_root>/scripts/gate_state.py set-status <task_json> gate-cap-hit` (leaves other completion fields untouched).
3. **Update the tracker:** mark this row `gate-cap-hit` with a link to the gates entry.
4. **GitHub:** → run `<skill_root>/scripts/issue_body.sh label <phase_issue> --add gate-cap-hit` (label-only, no body/close). **Project sync (gated):** also → `<skill_root>/scripts/project_sync.sh status <tasks_folder>/github_issue_map.json phase:<phase_id> Blocked` (self-gated, best-effort — no-ops when project disabled; `references/project_sync.md`).
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

Write the ExecPhase-owned completion fields to the task JSON (deterministic — fixed schema):
→ run `<skill_root>/scripts/gate_state.py complete <task_json> --branch <branch> --passed <p> --total <t> --review-score <s> [--minor <m> --medium <m> --high <m> --critical <m> --commands <cmd…> --notes "<notable decisions/deviations>"]`. This sets `status="done"`, `completion_date`, `test_completion` (passed/total/pass_rate/commands from Gate C), `review_score` + `review_breakdown` (from Gate B), `review_status="approved"`, `implementation_branch`, and `completion_notes` in one call.

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

Populate the `Session Reset Packet` table:
→ run `<skill_root>/scripts/gate_state.py reset-packet <tasks_folder>/gates/phase_<phase_id>_gates.md <tasks_folder>/json`. It emits the table rows for every task (including `done`, `skipped`, `gate-cap-hit`) with the deterministic cells already filled — **Status**, **Gate B Score** (from the task JSON `review_score`), and **Gate C** (the test count, or `not-run`). The Gate A score and Decision come back as `?` for you to fill:

- `Gate A Score`: read the gate file's Gate A reviewer verdicts and fill the final score per task (`not-run` if Gate A was never reached).
- `Decision`: a short recommendation for the next session — `accept`, `fix now`, `defer`, or `retry`.

Below the table, add one concise `Gate Findings` bullet per task:

- Gate A sentence: summarize the final actionable finding, or write `clean pass; no actionable findings`.
- Gate B sentence: summarize the final actionable finding, or write `clean pass; no actionable findings`.
- Recommended action sentence: explain the decision in one short sentence.

Keep this section compact. It is a session-reset aid, not a full report; detailed evidence stays in the gates file and task reports.

### 10b. Batched phase-issue update (1 fetch + 1 push, 1 `MultiEdit`)

Per `references/issue_body_updates.md`:

1. `<skill_root>/scripts/issue_body.sh fetch <phase_issue>` → body to stdout.
2. `Write` tool: `<tasks_folder>/scratch/phase_<N>_body.md`.
3. `MultiEdit`: for each task ID in `completed_this_phase`, replace `- [ ] <task_id>` → `- [x] <task_id>` (one MultiEdit call, N edits — never `sed -i`).
4. `<skill_root>/scripts/issue_body.sh push <phase_issue> <tasks_folder>/scratch/phase_<N>_body.md --remove-label in-progress --add-label done --state closed` — body update, label swap, and close in one call.

**Project sync (gated):** `set Status=Done` on the phase item via `project_sync.sh` (self-gated, best-effort — no-ops when project disabled; `references/project_sync.md`):
```bash
<skill_root>/scripts/project_sync.sh status <tasks_folder>/github_issue_map.json phase:<N> Done
```
(The `phase-close.sh` PostToolUse backstop also performs this set when 10b's in-band call is skipped — they're idempotent.)

### 10c. Plan overview checkbox

Per `references/issue_body_updates.md`:

1. `<skill_root>/scripts/issue_body.sh fetch <plan_overview_issue>` → body to stdout.
2. `Write` tool: `<tasks_folder>/scratch/overview_body.md`.
3. `Edit` tool: `- [ ] Phase <N>: <phase_name> (<task_count> tasks) — #<phase_issue>` → `- [x] ...`.
4. `<skill_root>/scripts/issue_body.sh push <plan_overview_issue> <tasks_folder>/scratch/overview_body.md`.

**Project sync (gated, final phase only):** on the last phase, also `set Status=Done` on the overview item → `<skill_root>/scripts/project_sync.sh status <tasks_folder>/github_issue_map.json overview Done` (self-gated, best-effort; `references/project_sync.md`).

### 10d. Draft PR (phase branch → plan branch)

Open the phase's draft PR (idempotent — a handoff *update* rides the existing PR, so re-running does nothing). The `phase-close.sh` backstop fires this too on the handoff write; this in-band call is the primary path:

→ `<skill_root>/scripts/draft_pr.sh phase <tasks_folder>/github_issue_map.json <phase_id> <tasks_folder>/Handoff_Phase_<phase_id+1>.md` — pushes `<plan_slug>_phase-<phase_id>`, opens a draft PR into `<plan_slug>` labelled `merge:commit`, body = this phase's completion-summary section + a repo-relative link to the handoff. gh-gated / best-effort.

**Final phase only:** also open the plan → main draft PR → `<skill_root>/scripts/draft_pr.sh plan <tasks_folder>/github_issue_map.json <tasks_folder>/Handoff_Phase_<phase_id+1>.md` (head `<plan_slug>`, base `main`, label `merge:squash`).

**Total `gh` budget for phase handoff: 4 calls** (1 phase view, 1 combined phase edit+close, 1 overview view, 1 overview edit) + 1 best-effort draft-PR open when a remote is set (+1 more on the final phase for the plan→main PR). Compare to Aut_Faciam's 2 + 2N for per-task flips during the phase.

---

Phase `<phase_id>` is complete. Next: ScaffoldPhase / ExecPhase for the next phase.
