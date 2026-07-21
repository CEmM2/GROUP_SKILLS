# E2E

Run a plan end-to-end with the main agent staying out of per-task detail. Plan-2-Tasks runs in the main thread once, then each phase either runs **inline** (the `phase` path, in main) or is delegated to the custom orchestrator profile returned by the Path-2 resolver and loaded with the `autviam-phase-orchestrator` prompt body, depending on the resolved nested-dispatch mode. In orchestrator mode the agent returns only a phase summary, so main-agent context grows by ~1–2k tokens per phase instead of ~30–60k.

**Inputs:**
- `<plan_file>` — required
- `<tasks_folder>`, `<tracking_file>` — default per SKILL.md
- `--stop-after <target>` — controls where the run stops. `<target>` forms:
  - `pN` (e.g. `p3`) — stop after phase N completes. Phases > N are not started in this run.
  - `N`  (e.g. `2`)  — stop after N phases have run in this invocation, regardless of phase number.
  - *(omitted)* — run end-to-end. The loop only stops when a human-intervention trigger fires.
- `--skip-plan-2-tasks` — assume Plan-2-Tasks already ran. Detected automatically by presence of `<tasks_folder>/all-tasks.md`; this flag forces the skip even if detection is ambiguous.
- `--arch` — when the run finishes the whole plan (stop reason `all-phases-done`), auto-run `commands/Architecture.md` in `--feature` mode against `<plan_file>` to snapshot the implemented feature's architecture. Omitted → the final report only *offers* the command (one line), so E2E stays token-lean by default.

---

## Dispatch Contract (read before writing any orchestrator dispatch prompt)

The routed orchestrator loads its job description from `agents/autviam-phase-orchestrator.md` and reads the ScaffoldPhase/ExecPhase command files itself. **The dispatch prompt is data, not instructions.** Its only job is to hand the orchestrator the per-phase pointers it cannot derive on its own. (This section applies only in orchestrator mode — see § Nested-Dispatch capability.)

### What the dispatch prompt MUST contain (and nothing else)

Use this template verbatim. Fill the angle-bracketed placeholders; do not add other sections, do not paraphrase the boilerplate.

```text
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
- "No spawn_agent" / "no delegated agents" — environment constraints on custom-profile dispatch must be resolved before E2E runs (Step 0), not papered over in the dispatch prompt. See § Nested-Dispatch capability.
- Re-stating any of the orchestrator's internal rules (gate cap = 3, plan-reading discipline, JSON-by-path, halt triggers). The orchestrator already knows these. Re-stating risks drift if the rules change and is pure cost.
- Restating ScaffoldPhase or ExecPhase steps. The orchestrator reads them itself.
- Critical-risk notes that are already in `Phase_<N>_context_summary.md` or task JSONs. The orchestrator reads those.

### Nested-Dispatch capability (resolved after decomposition)

The orchestrator pattern requires **two** levels of dispatch: the main agent spawns the routed orchestrator profile (level 1), which spawns routed implementers + reviewers (level 2). Some environments forbid level 2. Whether a given Codex runtime allows nesting is environment-dependent, so E2E reads the configured `nested_dispatch` mode in Step 0, resolves `auto` after decomposition, and **branches**, rather than assuming nesting works:

Codex defaults `agents.max_depth` to 1, so orchestrator mode normally requires `[agents] max_depth = 2` in the active `config.toml`. The probe remains authoritative because managed policy or the active client may still constrain nesting.

- **`off`** (default) — skip the orchestrator entirely; run each phase inline via the `phase` path (Step 3a, inline branch). Same end-to-end result, more main-thread context per phase. Always works, because it never nests.
- **`on`** — use the routed custom orchestrator per phase (Step 3a, orchestrator branch). Choose this only when you know the Codex runtime lets it spawn nested routed agents.
- **`auto`** — after decomposition, run one minimal nesting probe against the first runnable phase. Resolve that phase's maximum stored scores with role `orchestrator`, dispatch that custom profile, and have it resolve role `spec_reviewer` from the same scores before spawning the generated Gate A profile on an "echo PASS" request. Record both resolver results in the phase evidence file with purpose `nesting-probe`. Success → `on`; failure → fall back to `off`. Do not use built-in profiles for the probe.

Set the mode in `autviam_c_config.json` → `nested_dispatch` (default `"off"` if absent). **There is no "halt and fix" path** — a missing nesting capability is a platform limit, not a config bug, so E2E degrades to the inline path instead of dead-ending.

---

## Step 0 — Capability gate

Read `<skill_root>/autviam_c_config.json` → `nested_dispatch` (default `"off"` if the key or file is absent). Resolve the run mode:

- `"off"` → **inline mode**. No orchestrator, no probe.
- `"on"` → **orchestrator mode**.
- `"auto"` → set mode to **probe pending**. Do not probe yet: task scores do not exist until Plan-2-Tasks and the runnable phase list is known.

Record the configured mode or pending state. Step 2b resolves the pending probe before Step 3 branches.

## Step 1 — Plan-2-Tasks (once, in main)

If `<tasks_folder>/all-tasks.md` does not exist and `--skip-plan-2-tasks` is not set, run `commands/Plan-2-Tasks.md` in the main thread. This is the only command in the pipeline that benefits from reading the plan in full, so it stays in main — its output (JSONs, tracker, context summaries, issue map) is what every subsequent phase depends on.

If `all-tasks.md` exists or the flag is set, skip Step 1.

## Step 2 — Determine phase list

Read `<tasks_folder>/all-tasks.md`. Identify distinct phase IDs in execution order. Skip any phase whose tasks are all `status="done"` — that's the resume case.

If `--stop-after pN`:
- If phase `N` isn't in the run list (above the highest phase, or already fully done): warn the user and clarify intent before proceeding. Don't silently run more than they expected.
- Otherwise truncate the run list at phase `N` (inclusive).

If `--stop-after <N>` (count): keep the full run list — the count is applied dynamically in Step 3.

## Step 2b — Resolve pending auto mode

Only when Step 0 recorded **probe pending**:

- If the run list is empty, skip the probe and use inline mode; there is no phase work to delegate.
- Otherwise, read the first runnable phase's task JSONs and calculate the maximum stored `complexity` and maximum stored `risk` without changing either score.
- Invoke the resolver with those aggregate scores and role `orchestrator`, using `<tasks_folder>/Phase_<N>_routing_evidence.json` and purpose `nesting-probe`.
- Dispatch exactly the returned orchestrator profile. It must resolve role `spec_reviewer` from the same aggregate scores, append that result to the same phase evidence file with purpose `nesting-probe`, and spawn the generated Gate A profile on the bounded "echo PASS" request.
- If both custom-profile dispatches succeed, resolve mode to orchestrator. Otherwise resolve mode to inline and record the failure; never substitute a built-in profile.

## Step 3 — Phase loop

For each phase in the run list:

### 3a. Run the phase (branch on the resolved mode)

**Inline mode (`off`, default):** run the phase in the main thread exactly as `commands/Phase.md` does — ScaffoldPhase (if not already scaffolded) then ExecPhase for phase `<N>`. The implementer and Gate A/B reviewer profiles dispatch as single-level `spawn_agent` calls. There is no dispatch prompt and no orchestrator; gate-cap and precondition handling come straight from ExecPhase (see § 3c).

**Orchestrator mode (`on`):** take the maximum stored `complexity` and maximum stored `risk` across the phase's tasks, invoke the resolver with role `orchestrator`, and write the complete result to `<tasks_folder>/Phase_<N>_routing_evidence.json` with purpose `phase-orchestrator` and a UTC timestamp. Then dispatch the phase through exactly the returned custom profile:

```text
spawn_agent(
  agent_type="<resolver.agent>",
  message="""
<the dispatch-prompt template from § Dispatch Contract, fully filled>
"""
)
```

The installed orchestrator TOML already embeds the canonical `autviam-phase-orchestrator.md` behavior. The dispatch prompt contains phase data only.

### 3b. Read the phase result

**Orchestrator mode:** the orchestrator's last fenced JSON block is the structured result. Extract `status`, `tasks_done`, `capped_tasks`, `handoff_path`, `summary_line`. Show the user the `summary_line` and the 3–5 prose lines preceding the JSON — that's all the per-phase detail the main context absorbs.

**Inline mode:** ExecPhase ran in the main thread, so its status (`completed` / `gate-cap-hit` / `blocked-by-precondition` / `failed`), the tasks done/capped, and the handoff path are already available directly — no JSON parsing. Summarize them for the user the same way.

### 3c. Branch on status

| Status | Action |
|---|---|
| `completed` | Increment `phases_run_this_invocation`. If `--stop-after <count>` and `phases_run_this_invocation == count`: stop loop, go to Step 4. If this phase was the truncation target from `--stop-after pN`: stop loop, go to Step 4. If this is the last phase in the run list: stop loop, go to Step 4. Otherwise: continue to the next phase. |
| `gate-cap-hit` | Surface the cap report (§ Gate-Cap Bounce-Back). Await user choice. Resume on the same phase with the chosen `resume_mode` and re-loop. The retry **does not** count toward `--stop-after <N>` — only fully-completed phases count. |
| `blocked-by-precondition` | Stop. Surface to user — quote any `offending_instruction` if present. The precondition must be fixed before re-trying. |
| `failed` | Stop. Surface the `error` field. |

**Inline-mode note:** there is no orchestrator to re-dispatch. On `gate-cap-hit`, ExecPhase's own Step 7 surfaces the options and resumes in place per the user's choice; the loop continues with the same `completed` / cap-stop outcomes. The `resume_mode` round-trip in § Gate-Cap Bounce-Back applies to **orchestrator mode only**.

## Step 4 — Final report

Present to the user:

- Phases completed in this invocation: list with `summary_line` each
- Phases capped, skipped, or rolled back: list with last-known state
- Stop reason: one of `all-phases-done`, `stop-after-target-reached`, `gate-cap-stop`, `precondition-blocked`, `failure`, `permission-denied`, `dirty-working-tree`, `scaffold-flag`, `nested-dispatch-unavailable`
- Plan overview issue URL (visibility)
- Resume command: `AutViam_C e2e <plan_file>` if there's more to do, or "plan complete"

### Architecture snapshot (only when stop reason is `all-phases-done`)

The plan is fully implemented, so its feature architecture is now worth capturing as a planning asset:

- If `--arch` was passed: run `commands/Architecture.md` in `--feature` mode against `<plan_file>` (writes `dev/architecture/<plan_slug>.html` + `.md` digest). Report the two paths.
- Otherwise: print the offer verbatim, and stop there — don't render it inline (keeps the main thread lean):

  ```
  Snapshot the implemented architecture (durable + planning digest):  AutViam_C arch --feature <plan_file>
  ```

Skip this section entirely for any other stop reason — a partial run isn't a feature to snapshot yet.

---

## Human-Intervention Triggers

When `--stop-after` is omitted, the run continues automatically across phases. The loop pauses for the user *only* when one of these occurs:

1. **Gate cap hit** — phase returns `status="gate-cap-hit"`. Handled by § Gate-Cap Bounce-Back.
2. **Precondition violation** — phase returns `status="blocked-by-precondition"`. Surface and stop.
3. **Unexpected failure** — phase returns `status="failed"`. Surface and stop.
4. **Plan-2-Tasks ambiguity (Step 1 only)** — if decomposition surfaces a question that can't be resolved from the plan alone, the question is asked in the main thread before Step 2 starts.
5. **Permission denial** — if any `gh` / `git` / MCP write command is denied, surface the denied command and stop. Do not retry.
6. **Dirty working tree at branch checkout** — if `git checkout -b <phase_branch>` would lose uncommitted work, stop and ask.
7. **Scaffold flag** — if ScaffoldPhase marks a task `needs-human-review` on a critical field (`objective`, `acceptance_criteria`, `implementation_steps`, `deliverables`), stop and ask. Non-critical flags do not pause.
8. **Nested dispatch unavailable (auto mode only)** — the Step 0 probe failed. E2E falls back to inline mode automatically and continues; it does **not** stop. (In `off` mode there is no probe; in `on` mode a live orchestrator-dispatch failure surfaces as `failed` per trigger 3.)

For triggers 2–7 the loop halts at the current phase boundary and surfaces the relevant context to the user. Resume is via re-invoking `AutViam_C e2e <plan_file>` after the user resolves the issue.

---

## Gate-Cap Bounce-Back

When a phase returns `status="gate-cap-hit"` (orchestrator mode), surface this to the user:

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

In **inline mode** there is no orchestrator to re-dispatch; ExecPhase's Step 7 handles the same five options in place.

---

## Budget notes

- **Main agent context per phase:** ~1–2k tokens in orchestrator mode (orchestrator prose summary + JSON return + occasional gate-cap bounce-back); more in inline mode, where ExecPhase runs in main.
- **Routed orchestrator context per phase:** bounded by phase size; thrown away when the orchestrator returns (orchestrator mode only).
- **`gh` calls per phase:** same as ExecPhase Step 10 (~4 calls). E2E adds no GitHub overhead of its own.
