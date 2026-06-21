# Project sync — native GitHub Project tracking (gated, optional)

When `autviam_c_config.json` → `project` names a board, AutViam_C adds its plan/phase issues to that GitHub Project and keeps each item's **Status** in step with the issue lifecycle. When `project` is `"disable"` or absent, AutViam_C makes **zero** Project calls — this whole reference is a no-op. Read it on the first project touch in a session.

It rides the GitHub touchpoints AutViam_C already has (Plan-2-Tasks creates issues; Scaffold/ExecPhase swap labels). No new pipeline steps; ~1 extra `gh` call per touchpoint, only when armed.

## Gate (resolve first)

Read `<skill_root>/autviam_c_config.json` → `project`:

- absent or `"disable"` → **OFF**. Skip everything below.
- `"Some Name"` → owner defaults to the repo owner (`gh repo view --json owner -q .owner.login`); resolve name → number.
- `{ "owner": "...", "name": "..." }` → resolve name → number.
- `{ "owner": "...", "number": N }` → use directly.

Resolve a name to a number once: `gh project list --owner <owner> --format json` → match `title`. Two boards sharing a title can't be resolved from a name alone — warn and skip (don't guess).

## The executable: `update_tracker.sh`

All adds/sets go through the repo helper `.claude/scripts/update_tracker.sh`, which resolves and caches the project/field/option IDs so each call is one `gh project item-edit`:

```bash
.claude/scripts/update_tracker.sh add <issue-or-pr-url>            # prints the new item id
.claude/scripts/update_tracker.sh set <issue-or-pr-url> Plan   <slug>
.claude/scripts/update_tracker.sh set <issue-or-pr-url> Phase  <N>
.claude/scripts/update_tracker.sh set <issue-or-pr-url> Status Done
```

If the helper is absent in the host repo, fall back to raw `gh project item-add` / `gh project item-edit --id <itemId> --project-id <pid> --field-id <fid> ...` with IDs resolved per the gate above.

## Bridge block (cache in `github_issue_map.json`)

Plan-2-Tasks writes a `project` block alongside the issue map so later phases skip re-resolution:

```json
"project": {
  "owner": "SOSOVSKI", "number": 4,
  "overview_item": "PVTI_...",
  "phase_items": { "1": "PVTI_...", "2": "PVTI_..." }
}
```

(`update_tracker.sh` caches the field/option IDs itself in a temp file, so they need not live in the map.)

## Lifecycle touchpoints (all gated, all best-effort)

| AutViam_C step | Project action |
|---|---|
| Plan-2-Tasks, after creating each issue (§ 7h) | `add` item; `set Plan=<slug>`, `set Phase=<N>` (Repo auto-populates from the built-in **Repository** field); cache item ids |
| ScaffoldPhase Step 8 (scaffolded) | `set Status=Todo` on the phase item |
| ExecPhase Step 10b (phase done + close) | `set Status=Done` on the phase item |
| ExecPhase Step 7 (gate-cap-hit) | `set Status=Blocked` on the phase item |
| ExecPhase final phase | `set Status=Done` on the overview item |

## Invariants

- **Gated** — only runs when `project` resolves to a real board.
- **Degrade-gracefully** — gh-auth failure, unresolvable project, missing field/option, or permission denial → log + skip. Issues + the markdown tracker stay authoritative; a project failure **never** blocks the pipeline. (`update_tracker.sh` exits non-zero without throwing; ignore its exit code.)
- **Idempotent** — check `project.phase_items[N]` before adding; field-sets are idempotent. Safe to re-run.
- **Projection-of-a-projection** — Project ← issues ← markdown tracker. Nothing upstream depends on the board.

## Expected field schema on the board

`Status` (single-select including `Todo, In Progress, Blocked, Done`), `Plan` (text), `Phase` (number). The built-in `Repository` field auto-populates. If a field or option is missing, `update_tracker.sh` skips that set rather than erroring — so a board missing `Blocked` just won't show capped phases as blocked; everything else still works.
