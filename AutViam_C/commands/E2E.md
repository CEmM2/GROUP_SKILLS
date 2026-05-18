# E2E

Run a plan end-to-end with the main agent staying out of per-task detail. Plan-2-Tasks runs in the main thread once, then each phase is delegated to a Codex `worker` loaded with the `autviam-phase-orchestrator` prompt profile. The worker returns only a phase summary, so main-agent context grows by ~1–2k tokens per phase instead of ~30–60k.

**Inputs:**
- `<plan_file>` — required
- `<tasks_folder>`, `<tracking_file>` — default per SKILL.md
- `--stop-after <target>` — controls where the run stops. `<target>` forms:
  - `pN` (e.g. `p3`) — stop after phase N completes. Phases > N are not started in this run.
  - `N`  (e.g. `2`)  — stop after N phases have run in this invocation, regardless of phase number.
  - *(omitted)* — run end-to-end. The loop only stops when a human-intervention trigger fires.
- `--skip-plan-2-tasks` — assume Plan-2-Tasks already ran. Detected automatically by presence of `<tasks_folder>/all-tasks.md`; this flag forces the skip even if detection is ambiguous.

---

## Dispatch Contract (read before writing any orchestrator dispatch prompt)

The orchestrator worker loads its job description from `agents/autviam-phase-orchestrator.md` and reads the ScaffoldPhase/ExecPhase command files itself. **The dispatch prompt is data, not instructions.** Its only job is to hand the orchestrator the per-phase pointers it cannot derive on its own.

### What the dispatch prompt MUST contain (and nothing else)

Use this template verbatim. Fill the angle-bracketed placeholders; do not add other sections, do not paraphrase the boilerplate.

```
skill_root: <absolute path to skills/AutViam_C/, e.g. /home/user/repo/.codex/skills/AutViam_C/>
phase_id: <integer>
plan_file: <path to plan markdown>
tasks_folder: <path, or "default">
tracking_file: <path, or "default">
plan_slug: <slug from github_issue_map.json, or derived per SKILL.md>
working_directory: <repo root>
parent_branch: <branch name the new phase branch should fork from>
resume_mode: fresh | take_over | retry_with_instructions | skip_capped | rollback
resume_payload: <only if resume_mode != fresh — see orchestrator spec for shape>

## Phase-specific context not derivable from the skill or task JSONs

<— Put HERE, and ONLY HERE, anything project-specific the orchestrator can't infer:
   - testing pattern conventions from CLAUDE.md
   - environment-specific tooling substitutions (e.g. MCP github_issue_write
     replacing gh CLI, vitest-only Gate C policy)
   - known pre-existing test failures to ignore
   - links to handoff notes / context summaries the orchestrator should weight
   Keep it factual and short. Treat the orchestrator as already knowing
   AutViam_C's rules. —>
```

### Anti-patterns — never include these in the dispatch prompt

The following instructions defeat the orchestrator pattern. The orchestrator will halt with `status: "blocked-by-precondition"` if it sees them:

- "Do all implementation inline yourself" / "do not dispatch implementers" / "do gate reviews yourself"
- "No spawn_agent" / "no delegated agents" — environment constraints on Codex worker/explorer dispatch must be resolved before E2E runs, not papered over in the dispatch prompt. See § Codex Dispatch Pre-flight.
- Re-stating any of the orchestrator's internal rules (gate cap = 3, plan-reading discipline, JSON-by-path, halt triggers). The orchestrator already knows these. Re-stating risks drift if the rules change and is pure cost.
- Restating ScaffoldPhase or ExecPhase steps. The orchestrator reads them itself.
- Critical-risk notes that are already in `Phase_<N>_context_summary.md` or task JSONs. The orchestrator reads those.

### Codex Dispatch Pre-flight

Before the first phase dispatch in any E2E run, verify that Codex agent dispatch is available by starting a minimal `explorer` with the `autviam-spec-reviewer` profile and a harmless synthetic prompt. If it returns cleanly, Codex dispatch works in this environment — proceed. If it fails, halt E2E with a clear report and ask the user to run a non-E2E command or fix the runtime limitation before retrying. **Do not paper over a dispatch failure with inline instructions to the orchestrator** — that silently degrades the architecture without telling you why.

---

## Step 1 — Plan-2-Tasks (once, in main)

If `<tasks_folder>/all-tasks.md` does not exist and `--skip-plan-2-tasks` is not set, run `commands/Plan-2-Tasks.md` in the main thread. This is the only command in the pipeline that benefits from reading the plan in full, so it stays in main — its output (JSONs, tracker, context summaries, issue map) is what every subsequent phase orchestrator depends on.

If `all-tasks.md` exists or the flag is set, skip Step 1.

## Step 2 — Determine phase list

Read `<tasks_folder>/all-tasks.md`. Identify distinct phase IDs in execution order. Skip any phase whose tasks are all `status="done"` — that's the resume case.

If `--stop-after pN`:
- If phase `N` isn't in the run list (above the highest phase, or already fully done): warn the user and clarify intent before proceeding. Don't silently run more than they expected.
- Otherwise truncate the run list at phase `N` (inclusive).

If `--stop-after <N>` (count): keep the full run list — the count is applied dynamically in Step 3.

## Step 3 — Phase loop

For each phase in the run list:

### 3a. Dispatch the orchestrator

```
spawn_agent(
  agent_type="worker",
  message="""
Use `<skill_root>/agents/autviam-phase-orchestrator.md` as your prompt profile.

<the dispatch-prompt template from § Dispatch Contract, fully filled>
"""
)
```

There is no custom named-agent install fallback in Codex. If `spawn_agent` is unavailable, halt E2E and offer `AutViam_C exec <phase_id> <plan_file>` as the inline alternative.

### 3b. Parse the return

The orchestrator's last fenced JSON block is the structured result. Extract `status`, `tasks_done`, `capped_tasks`, `handoff_path`, `summary_line`. Show the user the `summary_line` and the prose preceding the JSON (3–5 lines). That's all the per-phase detail the main context absorbs.

### 3c. Branch on status

| Status | Action |
|---|---|
| `completed` | Increment `phases_run_this_invocation`. If `--stop-after <count>` and `phases_run_this_invocation == count`: stop loop, go to Step 4. If this phase was the truncation target from `--stop-after pN`: stop loop, go to Step 4. If this is the last phase in the run list: stop loop, go to Step 4. Otherwise: continue to the next phase. |
| `gate-cap-hit` | Surface the cap report (§ Gate-Cap Bounce-Back). Await user choice. Re-dispatch the orchestrator with the chosen `resume_mode` and re-loop on the same phase. The retry **does not** count toward `--stop-after <N>` — only fully-completed phases count. |
| `blocked-by-precondition` | Stop. Surface to user — quote any `offending_instruction` if present. The precondition must be fixed before re-trying. |
| `failed` | Stop. Surface the `error` field. |

## Step 4 — Final report

Present to the user:

- Phases completed in this invocation: list with `summary_line` each
- Phases capped, skipped, or rolled back: list with last-known state
- Stop reason: one of `all-phases-done`, `stop-after-target-reached`, `gate-cap-stop`, `precondition-blocked`, `failure`, `permission-denied`, `dirty-working-tree`, `scaffold-flag`, `codex-dispatch-unavailable`
- Plan overview issue URL (visibility)
- Resume command: `AutViam_C e2e <plan_file>` if there's more to do, or "plan complete"

---

## Human-Intervention Triggers

When `--stop-after` is omitted, the run continues automatically across phases. The loop pauses for the user *only* when one of these occurs:

1. **Gate cap hit** — orchestrator returns `status="gate-cap-hit"`. Handled by § Gate-Cap Bounce-Back.
2. **Precondition violation** — orchestrator returns `status="blocked-by-precondition"`. Surface and stop.
3. **Unexpected failure** — orchestrator returns `status="failed"`. Surface and stop.
4. **Plan-2-Tasks ambiguity (Step 1 only)** — if decomposition surfaces a question the orchestrator can't resolve from the plan alone, the question is asked in the main thread before Step 2 starts.
5. **Permission denial** — if any `gh` / `git` / MCP write command is denied, surface the denied command and stop. Do not retry.
6. **Dirty working tree at branch checkout** — if `git checkout -b <phase_branch>` would lose uncommitted work, stop and ask.
7. **Scaffold flag** — if ScaffoldPhase marks a task `needs-human-review` on a critical field (`objective`, `acceptance_criteria`, `implementation_steps`, `deliverables`), stop and ask. Non-critical flags do not pause.
8. **Codex dispatch unavailable** — pre-flight or live failure of worker/explorer dispatch. Stop and ask.

For triggers 2–8 the loop halts at the current phase boundary and surfaces the relevant context to the user. Resume is via re-invoking `AutViam_C e2e <plan_file>` after the user resolves the issue.

---

## Gate-Cap Bounce-Back

When an orchestrator returns `status="gate-cap-hit"`, surface this to the user:

```markdown
## AutViam_C E2E paused — Phase <N> hit gate cap

**Capped tasks in this run:**
- **<task_id>** — Gate <X> · failure modes: <list>
  Last reviewer Issues:
  <paste last_issues>

**Tasks completed this phase before the cap:** <tasks_done>

### Options
1. **Take over** — you implement the capped task(s); reply with the task IDs you've finished
2. **Retry with instructions** — give me extra context and I'll dispatch the orchestrator again with counters reset
3. **Skip capped task(s)** — cascade-skip dependents and finish the rest of the phase
4. **Rollback** — revert the capped task(s)' commits and resume
5. **Stop the E2E run** — leave everything in place for manual inspection

Which option, and for which task IDs?
```

Re-dispatch the orchestrator with the user's choice mapped to `resume_mode`:

| User choice | `resume_mode` | `resume_payload` |
|---|---|---|
| Take over | `take_over` | list of task IDs the user implemented |
| Retry with instructions | `retry_with_instructions` | `{"task_ids": [...], "guidance": "<user's text>"}` |
| Skip | `skip_capped` | list of task IDs to skip |
| Rollback | `rollback` | list of task IDs to rollback |
| Stop | (don't re-dispatch — go to Step 4 with stop reason `gate-cap-stop`) | — |

---

## Budget notes

- **Main agent context per phase:** ~1–2k tokens (orchestrator prose summary + JSON return + occasional gate-cap bounce-back).
- **Orchestrator worker context per phase:** bounded by phase size; thrown away when the worker returns.
- **`gh` calls per phase:** same as ExecPhase Step 10 (~4 calls). E2E adds no GitHub overhead of its own.
