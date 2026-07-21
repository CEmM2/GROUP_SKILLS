# Phase

Scaffold then execute one phase, **inline in the main thread** — AutViam's non-nested execution path.

ScaffoldPhase and ExecPhase resolve every generated agent and depth-aware ticket one level down from the main session. A nested Gate B may resolve explorer specialists at depth 2; caller mode keeps Gate B flat and has the main caller dispatch routed explorers.

Use `phase` for "do this one phase now." For a lean full run when nested dispatch is available, use `e2e`; when it isn't, `e2e` degrades to a loop over this command (see `E2E.md` § Step 0 — Capability gate).

**Inputs:** `<phase_id>` (int, required); `<plan_file>` (required); `<tasks_folder>`, `<tracking_file>` (default per SKILL.md).

---

## Step 0 — Pre-flight

- `gh auth status` (per SKILL.md § Idempotency — all GitHub steps skip cleanly if it fails; the local pipeline stays the source of truth).
- Confirm `<tasks_folder>/all-tasks.md` exists. If not, run `commands/Plan-2-Tasks.md` first (or tell the user to run `tasks`).
- Confirm `<phase_id>` is a real phase in `all-tasks.md` and that its cross-phase blockers (tasks in earlier phases) are `status="done"`.
- Run `check_claude_routing_environment.py` and `validate_claude_agent_routing.py`; validate topology at parent depth 0 before ScaffoldPhase. ScaffoldPhase/ExecPhase must use `resolve_claude_agent.py` for every child dispatch.

## Step 1 — Scaffold

If `<tasks_folder>/Phase_<phase_id>_Scaffold_Validation.md` is **absent**, run `commands/ScaffoldPhase.md` for `<phase_id>` now. If present, reuse it — honor ScaffoldPhase Step 0's re-scaffold guard (re-scaffold only on explicit user confirmation).

## Step 2 — Execute

Run `commands/ExecPhase.md` for `<phase_id>` in the **same main thread**. Everything ExecPhase defines holds unchanged: immutable routing, resolver/ticket enforcement, the 3-failure cap, Gate C, and Step 10 handoff/GitHub updates.

## Step 3 — Report

Surface ExecPhase's phase summary (tasks done / capped / skipped) and the resume hint for the next phase. On `gate-cap-hit`, ExecPhase's own Step 7 human-intervention prompt applies **directly** — you are in the main thread, so there is no orchestrator round-trip to translate the user's choice into a `resume_mode`.

---

**Context note.** The inline path spends main-thread context (~30–60k tokens/phase) — the cost the E2E orchestrator avoids by absorbing per-task noise inside a subagent. That trade is deliberate: correctness over leanness when nesting isn't available. If you're running many phases and nesting *is* available, prefer `e2e`.
