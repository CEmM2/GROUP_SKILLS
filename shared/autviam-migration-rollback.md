# AutViam v1 cutover, migration, and rollback

The release state in `autviam-cutover-release.json` makes the shared Whatter profile the default
for new work. Both façades report that state with every profile-backed invocation. They never
silently fall back when Whatter or the profile is missing.

## Start new work

Use `gen-plan`, `plan-compile`, or `status` normally. The façade validates the published profile,
binds its exact tree hash and path through `WHATTER_AUTVIAM_PROFILE`, and emits a Whatter invocation.
The host must execute the emitted `argv` with the emitted `env`; it must not reconstruct a bare
command.

## Inspect or operate legacy work

Lifecycle v1/v2 readers, plans, trackers, and stored runs remain unchanged and readable. Before the
compatibility window ends on 2026-10-01, invoke an old workflow only as
`legacy <old-command>`. Legacy code is frozen to compatibility and security fixes. A missing new
profile or Whatter executable is not permission to select legacy.

## Governed rollback

Rollback changes only the release pointer; it never rewrites Git or run history.

1. Preserve the failed release, its exact commit, and its evidence.
2. In a new commit, change only
   `selection.default_for_new_projects` in `autviam-cutover-release.json` from `profile-backed` to
   `legacy`.
3. Deploy the shared payload through `tools/deploy_documentron_autviam.sh`.
4. Run the focused façade and deployment tests. A normal command must report
   `mode: rollback-legacy-default`; this visible mode is the operator-selected rollback, not a
   fallback.
5. Re-run the bootstrap artifact-reference audit. Do not remove profile packages, legacy readers,
   plans, runs, or evidence.

To restore the cutover, make another forward commit changing the pointer to `profile-backed`, deploy,
and repeat full deterministic verification. Merge remains a separate governed action after the
default `delivery.ready` terminal state.

`cleanup-candidates.json` is an inventory only. It authorizes no deletion. Any later cleanup needs a
new approval after the compatibility window and a fresh retained-artifact reference audit.
