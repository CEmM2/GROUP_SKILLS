# Project sync — native GitHub Project tracking (gated, optional)

When `autviam_config.json` → `project` names a board, AutViam adds its plan/phase issues to that GitHub Project and keeps each item's **Status** in step with the issue lifecycle. When `project` is `"disable"` or absent, AutViam makes **zero** Project calls — this whole reference is a no-op. Read it on the first project touch in a session.

It rides the GitHub touchpoints AutViam already has (Plan-2-Tasks creates issues; Scaffold/ExecPhase swap labels). No new pipeline steps; ~1 extra `gh` call per touchpoint, only when armed.

## The executable: `project_sync.sh`

Every Project touch goes through one script — `<skill_root>/scripts/project_sync.sh`. It is the high-level entry point that **owns the deterministic plumbing the LLM used to do by hand**: board resolution (the 4 config forms + name→number), the idempotency check, and the `project`-block bookkeeping in `github_issue_map.json`. It wraps the low-level `update_tracker.sh` primitive (one `gh project item-edit` per call, field/option IDs cached) and bridges the board config to it via `TRACKER_OWNER`/`TRACKER_NUMBER`.

It **self-gates**: when `project` is `"disable"` or absent it returns `OFF` and no-ops. It is idempotent and best-effort — every failure logs to stderr and exits non-zero **without blocking**; callers ignore the exit code.

Three subcommands:

```bash
# Resolve the board — "OFF" when disabled/absent, else "<owner> <number>".
project_sync.sh resolve <config_path> [repo_owner]

# Add an item to the board, set Plan (+ Phase for phases), cache the item id in the map.
# which = overview | phase:<N>. Idempotent — skips if already cached in the project block.
project_sync.sh add <map_file> <config_path> <which> <issue_url> [--slug S] [--phase N]

# Set Status on the cached item (issue URL derived from the map).
# which = overview | phase:<N>.
project_sync.sh status <map_file> <which> <status>
```

`add` and `resolve` perform the board resolution and the `project`-block writeback automatically — the LLM no longer resolves boards or hand-writes the project block. If the underlying `update_tracker.sh` is absent or a field/option is missing, the wrapped call skips that set rather than erroring (degrade-gracefully).

## Gate (resolve first) — background

`project_sync.sh` does this for you (`resolve`, and the gate inside `add`/`status`); this is the config vocabulary it reads from `<skill_root>/autviam_config.json` → `project`:

- absent or `"disable"` → **OFF**. No Project calls.
- `"Some Name"` → owner defaults to the repo owner (`gh repo view --json owner -q .owner.login`); name → number.
- `{ "owner": "...", "name": "..." }` → name → number.
- `{ "owner": "...", "number": N }` → used directly.

Name → number resolution is `gh project list --owner <owner> --format json` → match `title`; two boards sharing a title can't be resolved from a name alone, so the script warns and skips (never guesses). The LLM does **not** run any of these `gh` calls itself anymore.

## Bridge block (cached in `github_issue_map.json`) — background

`project_sync.sh add` writes and maintains this `project` block so later phases skip re-resolution — the LLM no longer hand-writes it:

```json
"project": {
  "owner": "REPO_OWNER", "number": "Project_N",
  "overview_item": "PVTI_...",
  "phase_items": { "1": "PVTI_...", "2": "PVTI_..." }
}
```

(`update_tracker.sh` caches the field/option IDs itself in a temp file, so they need not live in the map.) The idempotency check reads this block: `add overview` skips when `overview_item` is set, `add phase:<N>` skips when `phase_items[N]` is set.

## Lifecycle touchpoints (all gated, all best-effort)

| AutViam step | `project_sync.sh` call |
|---|---|
| Plan-2-Tasks, after creating issues (§ 7g) | overview: `project_sync.sh add <map> <config> overview <overview_issue_url> --slug <slug>` · per phase: `project_sync.sh add <map> <config> phase:<N> <phase_issue_url> --slug <slug> --phase <N>` (Repo auto-populates from the built-in **Repository** field; item ids cached into the `project` block) |
| ScaffoldPhase Step 8 (scaffolded) | `project_sync.sh status <map> phase:<N> Todo` |
| ExecPhase Step 10b (phase done + close) | `project_sync.sh status <map> phase:<N> Done` |
| ExecPhase Step 7 (gate-cap-hit) | `project_sync.sh status <map> phase:<N> Blocked` |
| ExecPhase final phase | `project_sync.sh status <map> overview Done` |

## Invariants

- **Gated** — only runs when `project` resolves to a real board.
- **Degrade-gracefully** — gh-auth failure, unresolvable project, missing field/option, or permission denial → log + skip. Issues + the markdown tracker stay authoritative; a project failure **never** blocks the pipeline. (`project_sync.sh` logs and exits non-zero without throwing; callers ignore its exit code.)
- **Idempotent** — `project_sync.sh add` checks `project.{overview_item,phase_items[N]}` before adding; field-sets are idempotent. Safe to re-run.
- **Projection-of-a-projection** — Project ← issues ← markdown tracker. Nothing upstream depends on the board.

## Expected field schema on the board

`Status` (single-select including `Todo, In Progress, Blocked, Done`), `Plan` (text), `Phase` (number). The built-in `Repository` field auto-populates. If a field or option is missing, `update_tracker.sh` skips that set rather than erroring — so a board missing `Blocked` just won't show capped phases as blocked; everything else still works.
