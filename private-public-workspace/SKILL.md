---
name: private-public-workspace
description: Turn a private repository that keeps a stripped or synced copy of a public repository into a workspace where the public repository is a git submodule at public/ and each file has one home. Use when the user wants to stop syncing, exporting or stripping a private mirror, asks to "move <repo> to the workspace layout", or wants to survey a private/public repository pair first.
---

# Private/public repository as one workspace

A private repository that carries a copy of its public counterpart has to be
compared, stripped and synced forever, and the copy goes stale. This skill
replaces that with one layout:

- public files live only in the public repository, which the private
  repository includes as a git submodule at `public/` tracking `dev`;
- private files live only in the private repository, at its root;
- nothing is copied, exported or stripped any more.

It works one repository at a time, and stops for the owner at the points
marked **Stop**.

## Inputs

- the private repository (local checkout path and source branch);
- the public repository (`OWNER/NAME`) and its default branch;
- the publishing-kit `repos.toml` and the repository's entry name, if the pair
  was published with one (it says which private files are private by rule);
- the private test command used today, for the baseline.

## Rules that apply throughout

- Never push to the public default branch, never open a pull request and never
  write PR text into the public repository yourself. Push a branch and hand the
  owner the compare link (`compare/dev...<branch>?expand=1`), title and body.
- No `Co-authored-by` or other trailers in public commits; private commits
  follow the private repository's own attribution rule.
- Never run `git config` in a temporary worktree; pass identities with `git -c`.
- Do not lower protections (required reviews, branch rules) without the
  owner's explicit word for that repository.
- Do the move in a worktree on a branch. Touch the owner's main checkout only
  at the end, and only after checking no other session is working in it.
- Deleting leftovers in the owner's checkout (caches, old `.venv`, generated
  files) is the owner's call; list them instead.

## Steps

### 1. Survey (read-only)

Clone the public repository without file contents, then run the survey:

```bash
git clone --bare --filter=blob:none https://github.com/OWNER/NAME.git pub.git
scripts/survey.py --private PATH --private-ref origin/BRANCH \
  --public pub.git --public-ref BRANCH [--kit repos.toml --name ENTRY]
```

`git fetch` the private checkout first: the other computer may have pushed.

Read the report:

- **`closest_public_commit`** with score 0 means the private branch is exactly
  an earlier publication: nothing on the private side is newer, and every
  differing file can take the public version.
- **`private_ahead`**, **`diverged`**, or a public side that has not changed in
  months while the private side has: **Stop.** The public side is not where
  work happens. Publish first, or leave this repository for later.
- **`rewritten_on_publish`**: files the kit edits on the way out; the public
  version wins.
- **`private_files_under_public_top_level_names`**: these must move. Draft the
  move table from it (keep their grouping, e.g. `private_tests/<package>/`).
- Files in both repositories that each repository needs its own copy of
  (`.gitignore`, `.gitattributes`): keep them.

Also list work that exists only on this computer: branches without an upstream
(`git branch -vv`), uncommitted changes, stashes, worktrees, spare public
clones. **Stop** and ask the owner whether to push, commit or drop each.

Write the survey up for the owner, with the proposed move table. **Stop** for
approval of the move table and any file that differs in a way the rules above
do not settle.

### 2. Prepare the public side

To work through pull requests into `dev`, the public repository needs:

- a `dev` branch created from the default branch;
- branch protection on both (pull request required, linear history,
  conversations resolved, no deletion; the default branch also requires the
  CI checks and refuses force pushes; `dev` accepts force pushes so it can be
  reset after a release). Zero required reviews is the single-maintainer
  setting, because nobody can approve their own pull request; if the
  repository requires more today, **Stop** and ask;
- the publishing kit's `scripts/harden_repo.sh OWNER/NAME [--env ...]` if the
  owner uses it (tag rules, immutable releases, read-only workflow tokens,
  gated PyPI environments). It turns on "delete branch on merge", so `dev`
  must be protected at least against deletion: otherwise merging `dev` into
  the default branch deletes it, and the submodule tracks `dev`;
- CI that runs for `dev`. If the workflows name only the default branch, push
  a branch adding `dev` to the triggers and hand the owner the pull request.
  Require the checks on `dev` only after that is merged.

Only require checks that run on every pull request; a path-filtered workflow's
check never reports on some pull requests and blocks them.

### 3. Baseline

Run the private tests and the public suite in the old layout and keep the
totals and the skip list. Every later difference has to be explained against
these numbers.

### 4. Move

```bash
git tag pre-workspace-layout-YYYY-MM origin/BRANCH && git push origin pre-workspace-layout-YYYY-MM
git worktree add -b workspace-layout ../NAME_workspace origin/BRANCH
```

In the worktree, one commit each:

1. `git mv` the private files out of the public top-level names, per the move
   table.
2. `git rm` every file that also exists on the public side, except the
   per-repository ones.
3. `git submodule add -b dev https://github.com/OWNER/NAME.git public`, then
   `git -C public switch dev`.

### 5. Repair

Set up the one environment inside `public/` (its own `uv sync` or install
command, plus any other step CI runs, such as `npm ci`). Then fix what the
move broke; `references/repairs.md` has each case with its fix:

- the private tests: `templates/conftest.py`, `templates/layout.py`,
  `scripts/rewrite_root_lookups.py`, a root `pytest.ini`;
- hooks, path-scoped rules, Codex setup scripts and private scripts that
  assume the code is at the root;
- `CLAUDE.md` and `AGENTS.md`: add `templates/workspace-section.md`;
- `scripts/workspace.sh` into `dev/tools/`, and a short root `README.md` with
  the clone and setup commands.

### 6. Verify

- Private tests with `uv run --project public pytest` at the root, public
  tests inside `public/`. Compare with the baseline and explain every change in
  the counts, including skips.
- Tests that now fail because they assert on code the public side changed are
  findings: list them in `private_tests/stale_against_public.txt` and report
  them. **Stop** if any other test fails.
- Clone the branch fresh with `--recurse-submodules`, set it up the way CI
  does, and run the private tests again.

### 7. Land

- Write the record from `templates/record.md` where the repository's own
  document rules allow it, and commit.
- Push the branch to the private default branch (it is a fast-forward). If the
  private repository only accepts pull requests there, open one and
  rebase-merge it, so the commits stay as they are. Then move the owner's
  checkout onto it: `git switch BRANCH`, `git merge --ff-only`,
  `git submodule update --init`, `git -C public switch dev`. Remove the worktree.
- Make sure the publishing kit's entry for this repository is disabled: a
  publication from the new layout would push an almost empty tree.

### 8. Afterwards (with the owner)

- The owner checks a fresh recursive clone on the second computer.
- Then retire what the old layout needed: spare public clones, the extra
  remote pointing at the public repository, worktrees on public branches, sync
  or export scripts. Check each holds nothing unpushed first.
- Unmerged private branches that edit files the move rewrote need a rebase.

## Report

Tell the owner: the private commit and the recorded public commit; the counts
before and after with every difference explained; the stale tests; what was
not done on the public side and why; the pull requests waiting for them with
link, title and body; the second-computer command; and the leftovers they may
delete.

## Files

- `scripts/survey.py`: the comparison (step 1).
- `scripts/rewrite_root_lookups.py`: root-lookup rewrite for moved tests (step 5).
- `scripts/workspace.sh`: `status` and `pull` for both repositories.
- `templates/conftest.py`, `templates/layout.py`: private-test wiring.
- `templates/workspace-section.md`: the section for `CLAUDE.md` and `AGENTS.md`.
- `templates/record.md`: the record of the move.
- `references/repairs.md`: what breaks and how to fix it.
- `references/runs.md`: numbers and findings from the first three runs.
