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

## The executable: `project_sync.sh`

Every project touch goes through one bundled wrapper, `<skill_root>/scripts/project_sync.sh`. It owns the deterministic plumbing that used to be LLM prose: **board resolution** (the 4 config forms below + name → number via `gh project list`), **idempotency**, and the **`project`-block bookkeeping** in `github_issue_map.json`. It wraps the low-level `update_tracker.sh` primitive (one `gh project item-edit` per call, project/field/option IDs cached) — the commands never call `update_tracker.sh` directly.

`project_sync.sh` self-gates: when the config's `project` is `"disable"` or absent it prints `OFF` / no-ops. It is idempotent (a second `add` of the same item is skipped), best-effort, and never blocks — every failure logs to stderr and exits non-zero without throwing, so callers ignore the exit code.

Three subcommands:

```bash
# resolve the board (OFF when disabled/absent, else "<owner> <number>"; name → number)
project_sync.sh resolve <config> [repo_owner]

# add an item, set Plan/Phase, cache the item id in the map's `project` block (idempotent)
#   which = overview | phase:<N>
project_sync.sh add <map> <config> <which> <issue_url> [--slug S] [--phase N]

# set Status on a cached item (issue URL derived from the map)
#   which = overview | phase:<N>
project_sync.sh status <map> <which> <status>
```

Board resolution reads `<skill_root>/autviam_c_config.json` → `project` (the same 4 forms as the Gate above): absent/`"disable"` → `OFF`; `"Some Name"` → owner defaults to the repo owner, name → number; `{ "owner", "name" }` → name → number; `{ "owner", "number": N }` → used directly. Two boards sharing a title can't be resolved from a name alone — `project_sync.sh` warns and skips (it does not guess). `update_tracker.sh` caches the field/option IDs itself in a temp file, so they need not live in the map.

## `project` block (cached in `github_issue_map.json`)

`project_sync.sh add` maintains a `project` block alongside the issue map so later phases skip re-resolution — this bookkeeping is now **automatic** (no manual JSON editing):

```json
"project": {
  "owner": "SOSOVSKI", "number": 4,
  "overview_item": "PVTI_...",
  "phase_items": { "1": "PVTI_...", "2": "PVTI_..." }
}
```

`add` reads this block first for idempotency (an already-cached `overview`/`phase:<N>` is skipped) and writes the new item id back into it. `status` reads `owner`/`number` plus the issue numbers from the map to derive the item and its issue URL — so callers pass only `which`, never raw item or project ids.

## Lifecycle touchpoints (all gated, all best-effort)

The `project`-block bookkeeping and the Gate/board-resolution above are now automatic inside `project_sync.sh` — each touchpoint is a single wrapper call:

| AutViam_C step | `project_sync.sh` call |
|---|---|
| Plan-2-Tasks, after creating issues (§ 7h) | `project_sync.sh add <map> <config> overview <overview_issue_url> --slug <slug>`; per phase `project_sync.sh add <map> <config> phase:<N> <phase_issue_url> --slug <slug> --phase <N>` (Repo auto-populates from the built-in **Repository** field; item ids cached automatically) |
| ScaffoldPhase Step 8 (scaffolded) | `project_sync.sh status <map> phase:<N> Todo` |
| ExecPhase Step 10b (phase done + close) | `project_sync.sh status <map> phase:<N> Done` |
| ExecPhase Step 7 (gate-cap-hit) | `project_sync.sh status <map> phase:<N> Blocked` |
| ExecPhase final phase | `project_sync.sh status <map> overview Done` |

## Invariants

- **Gated** — only runs when `project` resolves to a real board.
- **Degrade-gracefully** — gh-auth failure, unresolvable project, missing field/option, or permission denial → log + skip. Issues + the markdown tracker stay authoritative; a project failure **never** blocks the pipeline. (`project_sync.sh` logs to stderr and exits non-zero without throwing; ignore its exit code.)
- **Idempotent** — `project_sync.sh add` checks the cached `project.overview_item` / `project.phase_items[N]` before adding; field-sets are idempotent. Safe to re-run.
- **Projection-of-a-projection** — Project ← issues ← markdown tracker. Nothing upstream depends on the board.

## Expected field schema on the board

`Status` (single-select including `Todo, In Progress, Blocked, Done`), `Plan` (text), `Phase` (number). The built-in `Repository` field auto-populates. If a field or option is missing, `project_sync.sh` (via `update_tracker.sh`) skips that set rather than erroring — so a board missing `Blocked` just won't show capped phases as blocked; everything else still works.
