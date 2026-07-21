# E2E

Run a plan end-to-end with config-governed inline or recursively delegated phases. Every orchestrator, implementer, reviewer, and specialist is selected by persistent routing and a depth-aware ticket.

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

The generated orchestrator profile embeds the canonical source from `agents/autviam-phase-orchestrator.md`. **The dispatch prompt is data, not instructions.**

### What the dispatch prompt MUST contain (and nothing else)

Use this template verbatim. Fill the angle-bracketed placeholders; do not add other sections, do not paraphrase the boilerplate.

```
skill_root: <absolute path to skills/AutViam/, e.g. /home/user/repo/.claude/skills/AutViam/>
autviam_routing_ticket: <absolute resolver ticket path>
current_depth: 1
maximum_depth: <configured max_depth>
specialist_topology: nested | caller | off
phase_id: <integer>
plan_file: <path to plan markdown>
tasks_folder: <path, or "default">
tracking_file: <path, or "default">
plan_slug: <slug from github_issue_map.json, or derived per SKILL.md>
working_directory: <repo root>
parent_branch: <branch name the new phase branch should fork from>
resume_mode: fresh | take_over | retry_with_instructions | skip_capped | rollback | caller_specialist_reports
resume_payload: <only if resume_mode != fresh — see orchestrator spec for shape>

## Phase-specific context not derivable from the skill or task JSONs

<— Put HERE, and ONLY HERE, anything project-specific the orchestrator can't infer:
   - testing pattern conventions from CLAUDE.md
   - environment-specific tooling substitutions (e.g. MCP github_issue_write
     replacing gh CLI, vitest-only Gate C policy)
   - known pre-existing test failures to ignore
   - links to handoff notes / context summaries the orchestrator should weight
   Keep it factual and short. Treat the orchestrator as already knowing
   AutViam's rules. —>
```

### Anti-patterns — never include these in the dispatch prompt

The following instructions defeat the orchestrator pattern. The orchestrator will halt with `status: "blocked-by-precondition"` if it sees them:

- "Do all implementation inline yourself" / "do not dispatch implementers" / "do gate reviews yourself"
- "No Agent tool" / "no subagents" / "no Task tool" — environment constraints on nesting must be resolved before E2E runs, not papered over in the dispatch prompt. See § Nested-Dispatch Pre-flight.
- Re-stating any of the orchestrator's internal rules (gate cap = 3, plan-reading discipline, JSON-by-path, halt triggers). The orchestrator already knows these. Re-stating risks drift if the rules change and is pure cost.
- Restating ScaffoldPhase or ExecPhase steps. The orchestrator reads them itself.
- Critical-risk notes that are already in `Phase_<N>_context_summary.md` or task JSONs. The orchestrator reads those.

### Nested-Dispatch capability (resolved in Step 0)

The orchestrator pattern uses depth 1 for the phase orchestrator, depth 2 for implementers/reviewers, and optionally depth 3 for Gate B specialists. `autviam_config.json` sets the AutViam ceiling and the live probe records the runtime ceiling:

- **`off`** — skip the orchestrator entirely; run each phase inline via the `phase` path (Step 3a, inline branch). Same end-to-end result, more main-thread context per phase.
- **`on`** — require declared/detected `runtime_max_depth`, validate `max_depth <= runtime_max_depth`, and use the resolved generated orchestrator.
- **`auto`** — run a bounded, no-write recursive Agent probe up to the safe limit, record the maximum observed depth with `probe_nested_dispatch.py`, then select on when the required topology fits or off otherwise.

At every edge, `resolve_claude_agent.py` checks configured/runtime ceilings and the spawn graph. `on_depth_exhausted=caller` flattens specialist work to the nearest permitted caller and selects flat Gate B; `block` stops with `blocked-by-precondition`.

---

## Step 0 — Capability gate

Run the environment and exhaustive routing validators, then normalize legacy `nested_dispatch: "off"|"on"|"auto"` to the structured object. Resolve `nested_dispatch.mode`:

- `"off"` → **inline mode**. No orchestrator, no probe.
- `"on"` → **orchestrator mode**.
- `"auto"` → first run `probe_nested_dispatch.py --config <config> --safe-limit <N> --evidence-file <operational-path> --session-id <live-session-id> --prepare`. Use temporary `routing-probe-depth-N` PASS-only profiles (never implementation or production reviewer prompts) whose only allowed child is the next probe depth. Append each actual Agent result (`agent_id`, `agent_type`, `parent_agent_id`, depth, status) to the evidence file, stop on the first failed child spawn or safe limit, then finalize with `--observed-depth <N> --evidence-file <operational-path> --audit-log <project>/.claude/autviam-routing/subagent-start.jsonl --record`. Remove the temporary probe profiles. The script requires an exact same-session SubagentStart audit match and parent chain for every passing depth and rejects missing, non-contiguous, write-producing, or mismatched evidence. Select orchestrator only if the required phase topology fits.

Record the resolved mode — Step 3 branches on it. This runs **before** Plan-2-Tasks so no decomposition work is wasted discovering that nesting is unavailable.

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

### 3a. Run the phase (branch on the Step 0 mode)

**Inline mode (`off`):** run the phase in the main thread exactly as `commands/Phase.md` does — ScaffoldPhase (if not already scaffolded) then ExecPhase for phase `<N>`. The implementer and Gate A/B reviewers dispatch as single-level subagents. There is no dispatch prompt and no orchestrator; gate-cap and precondition handling come straight from ExecPhase (see § 3c).

**Orchestrator mode (`on`):** invoke `resolve_claude_agent.py` with `--phase-id <N>`, role/purpose `orchestrator`/`phase-orchestrator`, depth 1, and `<tasks_folder>/Phase_<N>_routing_evidence.json`. The resolver and hook independently scan `<tasks_folder>/json/P<N>-*.json` and compute the maximum immutable complexity/risk aggregates; do not pass caller-authored phase scores. Dispatch exactly the returned generated profile and ticket:

```
Agent(
  subagent_type="<resolver.agent>",
  description="AutViam phase <N> orchestrator",
  prompt="autviam_routing_ticket: <resolver.ticket_path>\n<the dispatch template, fully filled>"
)
```

Never pass `model` in the Agent call. Missing profile, hook rejection, or dispatch failure is fatal; there is no legacy or inline fallback while resolved mode is `on`.

### 3b. Read the phase result

**Orchestrator mode:** the orchestrator's last fenced JSON block is the structured result. Extract `status`, `tasks_done`, `capped_tasks`, `handoff_path`, `summary_line`, and `caller_specialist_request`. Show the user the `summary_line` and the 3–5 prose lines preceding the JSON — that's all the per-phase detail the main context absorbs.

**Inline mode:** ExecPhase ran in the main thread, so its status (`completed` / `gate-cap-hit` / `blocked-by-precondition` / `failed`), the tasks done/capped, and the handoff path are already available directly — no JSON parsing. Summarize them for the user the same way.

### 3c. Branch on status

| Status | Action |
|---|---|
| `completed` | Increment `phases_run_this_invocation`. If `--stop-after <count>` and `phases_run_this_invocation == count`: stop loop, go to Step 4. If this phase was the truncation target from `--stop-after pN`: stop loop, go to Step 4. If this is the last phase in the run list: stop loop, go to Step 4. Otherwise: continue to the next phase. |
| `caller-specialists-required` | In the main session, resolve each requested lens as role `explorer`, purpose `specialist`, at top-level depth 1 from the named task's immutable routing. Dispatch with tickets and write the reports atomically under `<tasks_folder>/reviews/`. Preserve the request's complete `resume_packet`. Resolve a **fresh** phase-orchestrator ticket from `--phase-id <N>` and the canonical phase task JSONs, then redispatch with `resume_mode="caller_specialist_reports"` and `resume_payload={"task_id":"...","reports_path":"...","resume_packet":<unchanged request.resume_packet>}`. A failed resolver/dispatch is fatal; never substitute inline review. Re-loop on the same phase without incrementing the completed count. |
| `gate-cap-hit` | Surface the cap report (§ Gate-Cap Bounce-Back). Await user choice. Re-dispatch the orchestrator with the chosen `resume_mode` and re-loop on the same phase. The retry **does not** count toward `--stop-after <N>` — only fully-completed phases count. |
| `blocked-by-precondition` | Stop. Surface to user — quote any `offending_instruction` if present. The precondition must be fixed before re-trying. |
| `failed` | Stop. Surface the `error` field. |

**Inline-mode note:** there is no orchestrator to re-dispatch. On `gate-cap-hit`, ExecPhase's own Step 7 surfaces the options and resumes in place per the user's choice; the loop continues with the same `completed` / cap-stop outcomes. The `resume_mode` round-trip in § Gate-Cap Bounce-Back applies to **orchestrator mode only**.

## Step 4 — Final report

Present to the user:

- Phases completed in this invocation: list with `summary_line` each
- Phases capped, skipped, or rolled back: list with last-known state
- Stop reason: one of `all-phases-done`, `stop-after-target-reached`, `gate-cap-stop`, `precondition-blocked`, `failure`, `permission-denied`, `dirty-working-tree`, `scaffold-flag`, `nested-dispatch-unavailable`
- Plan overview issue URL (visibility)
- Resume command: `/AutViam e2e <plan_file>` if there's more to do, or "plan complete"

### Architecture snapshot (only when stop reason is `all-phases-done`)

The plan is fully implemented, so its feature architecture is now worth capturing as a planning asset:

- If `--arch` was passed: run `commands/Architecture.md` in `--feature` mode against `<plan_file>` (writes `dev/architecture/<plan_slug>.html` + `.md` digest). Report the two paths.
- Otherwise: print the offer verbatim, and stop there — don't render it inline (keeps the main thread lean):

  ```
  Snapshot the implemented architecture (durable + planning digest):  /AutViam arch --feature <plan_file>
  ```

Skip this section entirely for any other stop reason — a partial run isn't a feature to snapshot yet.

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
8. **Nested dispatch unavailable (auto mode only)** — the Step 0 probe failed. E2E falls back to inline mode automatically and continues; it does **not** stop. (In `off` mode there is no probe; in `on` mode a live orchestrator-dispatch failure surfaces as `failed` per trigger 3.)

For triggers 2–8 the loop halts at the current phase boundary and surfaces the relevant context to the user. Resume is via re-invoking `/AutViam e2e <plan_file>` after the user resolves the issue.

---

## Gate-Cap Bounce-Back

When an orchestrator returns `status="gate-cap-hit"`, surface this to the user:

```markdown
## AutViam E2E paused — Phase <N> hit gate cap

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
- **Orchestrator context per phase:** bounded by phase size; thrown away when the subagent returns.
- **`gh` calls per phase:** same as ExecPhase Step 10 (~4 calls). E2E adds no GitHub overhead of its own.
