# Three runs (2026-11)

What the survey showed and what the move needed, per repository. Use it to
judge how big a new run will be.

| | AKMS | zotero-summarizer | MechDSL |
|---|---|---|---|
| Tracked in private before | 3,792 | 1,033 | 1,943 |
| Copies of public files removed | 676 | 174 | 388 |
| Private files moved out of public folders | 1,044 | 1 | 152 |
| Which side was ahead | public (private stale in 141, missing 321) | equal but one file | public (101 files) |
| Differing files and outcome | 23, all discarded | 1 (`pyproject.toml` version), public kept | 105 (13 owner-name rewrites, 92 newer on public), public kept |
| Private test files edited | 25 | 1 | 74 by script + 3 by hand |
| Private tests before → after | 485 passed (20 duplicates) → 492 passed | 640 → 635 public + 5 private | 769 passed, 1 failed → 753 passed, 15 expected failures |
| Unexpected findings | two empty `__init__.py` files hid 27 tests | `npm ci` missing from setup | 15 tests asserted wording the public side had removed; a governance test rejected the record |

## AKMS

Public side was already where work happened (pull requests into `dev`). The
private copy had drifted: stale in 141 files, missing 321. Most of the move was
the node vault and generator data inside `packages/`. Five `.github` copies
carried a "public repository only" guard; with no private workflows the guard
had nothing to do. The export ledger and sync script were retired.

## zotero-summarizer

The last release commit had been made on the public repository, so the private
`pyproject.toml` was one version behind. Otherwise identical. The public side
had no `dev` branch, no protection and no hardening; all were added before the
split, and a CI trigger change for `dev` went up as a pull request.

## MechDSL

The survey's closest-public-commit check showed private `main` equal to the
publication of 2026-09-01 apart from 13 owner-name rewrites: nothing newer on
the private side. Later work had been made on a branch cut from the public
history. The 152 private test files used the public test package as `tests`,
its fixtures, and repository-root lookups. Branch-rule changes on the public
side were left to the owner because they lowered a review requirement.

## Not ready: when the private side is the source

A fourth repository was surveyed and not moved: its other side was three
months behind and the private repository was the only place where work
happened, with vendored subtrees being removed. Moving it would have meant
classifying thousands of files about to be deleted. The layout needs the other
side to be where code changes are made first.
