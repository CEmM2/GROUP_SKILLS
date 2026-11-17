## Workspace Layout

This checkout holds two repositories:

- **`public/`** is the public repository (`<PUBLIC_OWNER>/<REPO>`) as a git
  submodule on its `dev` branch. All code, public tests, docs and CI live
  there and nowhere else.
- **Everything else** is the private repository (`<PRIVATE_OWNER>/<REPO>`):
  plans, reviews, design docs, private tests and agent configuration.

A file has one home. Nothing is copied between the two repositories and nothing
is exported from the private one.

```
.
├── public/                # submodule → <PUBLIC_OWNER>/<REPO> (branch dev)
├── dev/                   # plans, reviews, records
│   └── tools/workspace.sh # state of both repositories
├── private_tests/         # tests that read private files; run against public/
└── .claude/, .codex/, .agents/
```

Paths in older plans, reviews and agent files that start with `<PUBLIC_TOP_NAMES>`
are relative to `public/`.

## Working In Two Repositories

- **Code, public tests, docs:** work inside `public/`. It is an ordinary clone
  of the public repository: branch from `dev`, commit, push, pull request into
  `dev`. `dev` → `<DEFAULT_BRANCH>` is rebase-merged; releases are tagged on
  `<DEFAULT_BRANCH>`. The public-repository rules (pull requests, PR text,
  commit trailers, private names) apply to everything under `public/`.
- **Plans, reviews, private tests, agent files:** commit at the workspace root.
- **A change that touches both** is two commits, one in each repository.
- `git status` at the root shows `public` as modified when its checkout is not
  at the recorded commit. That is normal while working. Record a new commit
  (`git add public`) only when a private commit depends on it.
- `dev/tools/workspace.sh status` prints the state of both repositories.
- A fresh clone needs `git clone --recurse-submodules`, then
  `git -C public switch dev` (a submodule starts on a detached commit).

## Commands

```bash
cd public && <SETUP_COMMAND>                 # the one environment
cd public && <PUBLIC_TEST_COMMAND>           # public tests
uv run --project public pytest               # private tests, at the workspace root
```
