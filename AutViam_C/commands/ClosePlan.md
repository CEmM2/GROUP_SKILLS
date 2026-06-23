# ClosePlan

Finalize a completed plan: close the plan-overview issue, set the Project overview item to Done, and open the plan → main draft PR (squash). The plan-level equivalent of `close-phase` — run it once every phase is done. The automated phase-level equivalents live in ExecPhase Step 10 (in-band) and the `phase-close.sh` backstop; this is the deliberate, plan-level close.

**Inputs:** `<plan_file>` (required); `<tasks_folder>` to locate `github_issue_map.json` (default `dev/plans/<plan_file_stem>/`).

---

## Step 1 — Resolve

- `gh auth status`. If it fails, stop — there's nothing to close on GitHub (the local tracker stays authoritative).
- Read `<tasks_folder>/github_issue_map.json` → `plan_slug`, `repo`, `plan_overview_issue`, the `phases` map, and the `project` block if present.
- Confirm the plan is actually done: every `phases.<N>` issue should be closed and each phase's tasks `done`/`skipped` in the tracker / task JSONs. If any phase is still open or has `pending`/`in-progress` tasks, warn and ask before closing.

## Step 2 — Final handoff (if missing)

If the final `<tasks_folder>/Handoff_Phase_<last+1>.md` is absent, generate it from `templates/Handoff_template.md` as a project completion summary. This is the artifact `draft_pr.sh plan` links to.

## Step 3 — Close the overview issue (idempotent)

Skip if already closed. Otherwise close it with a note (no body rewrite needed):

→ `<skill_root>/scripts/issue_body.sh close <plan_overview_issue> --add done --comment "Plan <plan_slug> completed — closed via AutViam_C close-plan."`

## Step 4 — Project sync (gated)

Set the overview item's Status to Done (self-gated, best-effort — no-ops when project sync is off; `references/project_sync.md`):

```bash
<skill_root>/scripts/project_sync.sh status <tasks_folder>/github_issue_map.json overview Done
```

## Step 5 — Plan → main draft PR

Open (idempotently) the plan's draft PR to `main`, labelled `merge:squash` (SKILL.md § Branch & Worktree Model):

→ `<skill_root>/scripts/draft_pr.sh plan <tasks_folder>/github_issue_map.json <tasks_folder>/Handoff_Phase_<last+1>.md`

It pushes `<plan_slug>`, opens a draft PR `<plan_slug>` → `main` (body = the final completion summary + a repo-relative link to the handoff). The `merge:squash` label records the intended method; merge it with `gh pr merge <plan_slug> --squash` when ready, so `main` gets one squashed commit for the whole plan.

## Step 6 — Report

State what was closed (overview issue), whether the board was updated, and the draft PR URL (or that it already existed). Remind the user the plan branch squash-merges into `main`.
