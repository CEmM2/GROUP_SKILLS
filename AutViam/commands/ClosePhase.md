# ClosePhase

Manually close a phase issue when the phase was finished **outside** ExecPhase Step 10 — e.g. you took over a gate-capped task and completed it by hand, so the in-band close + handoff never ran. The escape hatch for stale-open phase issues.

For the automated paths see ExecPhase Step 10 (in-band) and the `phase-close.sh` PostToolUse backstop (fires on the handoff write). This command is for the case where neither ran.

**Inputs:** `<phase_id>` (required); `<plan_file>` or `<tasks_folder>` to locate `github_issue_map.json` (default `dev/plans/<plan_file_stem>/`).

---

## Step 1 — Resolve

- `gh auth status`. If it fails, stop — there's nothing to close on GitHub (the local tracker is already authoritative).
- Read `<tasks_folder>/github_issue_map.json` → `repo`, `phases.<phase_id>.issue_number`, `plan_overview_issue`, and the `project` block if present.
- Confirm in the tracker / task JSONs that every task in `<phase_id>` is `done` or `skipped`. If any is still `pending`/`in-progress`, warn and ask before closing — you may be closing a phase that isn't actually finished.

## Step 2 — Handoff (if missing)

If `<tasks_folder>/Handoff_Phase_<phase_id+1>.md` is absent, generate it from `templates/Handoff_template.md` (final phase → completion summary). This records the handoff and is the artifact the `phase-close.sh` backstop keys on, so future automation stays consistent.

## Step 3 — Close the phase issue (idempotent)

Skip if already closed. Otherwise swap labels + close + leave the note in one call (no body rewrite needed):

→ `<skill_root>/scripts/issue_body.sh close <phase_issue> --remove in-progress --add done --comment "Phase <N> completed manually — closed via /AutViam close-phase."`

Tick the phase's checkbox in the plan-overview body per `references/issue_body_updates.md`: `<skill_root>/scripts/issue_body.sh fetch <plan_overview_issue>` → Write to `/tmp/overview_body.md` → Edit the checkbox → `<skill_root>/scripts/issue_body.sh push <plan_overview_issue> /tmp/overview_body.md`.

## Step 4 — Project sync (gated)

Set the phase item's Status to Done via `project_sync.sh`; on the final phase, also set the overview item Done (self-gated, idempotent, best-effort — no-ops when project sync is disabled or absent; see `references/project_sync.md`):

```bash
<skill_root>/scripts/project_sync.sh status <tasks_folder>/github_issue_map.json phase:<phase_id> Done
# final phase only:
<skill_root>/scripts/project_sync.sh status <tasks_folder>/github_issue_map.json overview Done
```

## Step 5 — Report

State which issue was closed, what was already closed (if it was a no-op), and whether the board was updated. Point at the next phase if there is one.
