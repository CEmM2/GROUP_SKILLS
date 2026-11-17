# Workspace layout: public repo as a submodule (record)

Done on <DATE>. Public files live only in `<PUBLIC_OWNER>/<REPO>`, included here
as a git submodule at `public/` tracking `dev` (recorded at <SHA>). Private
files live only here. The old layout is at the tag `pre-workspace-layout-<YYYY-MM>`.

| Step | Commit | Result |
|---|---|---|
| Freeze | tag at <SHA> | pushed |
| Move | <SHA> | <N> private files → <WHERE> |
| Remove copies | <SHA> | <N> files removed |
| Submodule | <SHA> | `public/` → <PUBLIC_OWNER>/<REPO>, branch `dev` |
| Paths, tests, agent files | <SHA> | see below |

## Survey before the change

<Tracked files; private by rule; identical copies; each kind of difference and
which side won; the closest public commit; files that exist in both repos.>

## Where things went

| Was | Is | Files |
|---|---|---|

## What had to be repaired

<One bullet per kind of repair: imports, fixtures, root lookups, hand-edited
tests, pytest settings, hooks, path-scoped rules, agent files, scripts.>

## Tests

| | Old layout | New layout |
|---|---|---|
| passed | | |
| expected failures | | |
| failed | | |
| skipped | | |

<Explain every difference in the counts.>

## On the public side

<dev branch, branch rules, hardening, CI trigger change and its PR.>

## Left open

<Second-computer check, spare clones, extra remotes and worktrees to retire,
unmerged private branches that need a rebase, stale tests, publishing-kit
entry that must stay disabled.>
