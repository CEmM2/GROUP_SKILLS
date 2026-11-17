# Repairs after the split

What breaks when the private repository stops holding the public tree, and how
each was fixed. Ordered by how often it came up across three repositories.

## 1. "The repository root" in private tests

Most common by far: 74 of 152 moved test files in one repository.

Tests find the root by walking up to a folder that holds both `pyproject.toml`
and `dev/` (or `packages/`, or `.github/workflows`), or by counting
`Path(__file__).resolve().parents[N]` from their old place. That folder no
longer exists: `pyproject.toml` is under `public/`, `dev/` is at the workspace
root. Symptoms: `RuntimeError: could not locate repo root` at collection, or a
path under the wrong root.

Fix:

1. Copy `templates/layout.py` to `private_tests/_layout.py` and fill in `MOVED`
   from the move table. `repo_path("packages/x/tests/y.py")` then returns the
   present home of any path of the old single checkout.
2. Run `scripts/rewrite_root_lookups.py private_tests --old-home GROUP=OLD_DIR ...`.
   It makes each root helper return the workspace root and sends every path
   built on it, or on `parents[N]`, through `repo_path`.
3. Check every file parses, read the diff, run the tests.

Files that still need a hand edit:

- a test that asserts its own location (`relative_to(parents[5]) == "packages/..."`);
- a test that lists sibling test files through a variable such as
  `_TESTS_ROOT = Path(__file__).parent.parent.parent` and joins names onto it;
- a test that runs `pytest` in a subprocess with `-c pyproject.toml`: point it
  at the root `pytest.ini` and pass both `private_tests` and the public test
  folder; normalise collected node IDs back to the old paths before comparing.

## 2. Imports of the public test package

Private tests import shared helpers as `tests.<module>`, from the public test
package (`tests.ref`, `tests._e2e_helpers`) and from private folders that used
to sit inside it (`tests.spike`, `tests.plan_tests...`). After the move, half
of those live elsewhere.

Fix: in `private_tests/conftest.py`, put the folder that holds the public
`tests` package on `sys.path`, import it, and append the private folder to
`tests.__path__` (part 2 of `templates/conftest.py`). No import changes.

## 3. Fixtures from a public conftest.py

Tests that used fixtures from the public `conftest.py` lose them, because
pytest only applies a conftest to files below it.

Fix: `private_tests/<group>/conftest.py` loads the public file and copies its
names into its own namespace (part 3 of `templates/conftest.py`).

## 4. pytest settings

The root has no `pyproject.toml`, so the public `[tool.pytest.ini_options]`
does not apply to the private tests.

Fix: a root `pytest.ini` with `testpaths = private_tests`,
`--import-mode=importlib`, and the public marker list repeated (otherwise
`--strict-markers` fails). Run with `uv run --project public pytest`: one
environment, the public one. Drop `cache_dir`; `pytest.ini` warns on it.

Empty `__init__.py` files in moved test folders can make two test files with
the same name collide, so one of them never runs. Remove them unless a test
imports its folder as a package.

## 5. Tests that asserted on code the public side has changed

After the move the private tests run against the current public code instead
of the stale private copy. Tests asserting wording that a later public commit
removed (internal plan references in messages and docstrings, for example)
fail. That is a finding, not a defect of the move.

Fix: list the node IDs in `private_tests/stale_against_public.txt`; part 4 of
`templates/conftest.py` marks them as strict expected failures. The owner
decides whether to update or delete each one.

## 6. Agent hooks that run tools at the root

A format-on-edit or type-check hook that calls `uv run ruff` or `uv run mypy`
at the root fails silently: the root is no longer a project.

Fix: `uv run --directory "$PUBLIC" ...` with `PUBLIC` computed from the
hook's own location, or `uv run --project "$CLAUDE_PROJECT_DIR/public" ...`.
Hooks that take file paths as arguments must make relative paths absolute
first, because `--directory` changes the working directory. Search
`.claude/settings.json`, `.claude/hooks/`, `.codex/`, `.agents/hooks/` and any
`codex-setup.sh` for `uv run` and `uv sync`.

## 7. Path-scoped agent rules

Rules files with `paths:` frontmatter (`packages/core/src/**`) stop matching
when the code moves under `public/`. Prefix them, and add `private_tests/**`
to the tests rule.

## 8. Agent instruction files

`CLAUDE.md` and `AGENTS.md` describe the old single tree. Add the workspace
section (`templates/workspace-section.md`): what lives where, where commands
run, how a change touching both repositories is committed. Agents and skills
that name `packages/...` can stay as they are if the instructions say those
paths are relative to `public/`.

## 9. The repository's own governance tests

The record of the move is a new file, and repositories with rules about their
own documents test it like any other. One rejected a new file under
`dev/plans` without a "superseded" banner. Put the record where such rules do
not apply (`dev/reports/` there) or follow them.

## 10. Setup steps the old checkout had already done

A fresh clone exposed twelve failing tests that needed `npm ci` in a plugin
folder: the old checkout had the modules, so nothing documented the step.
Always verify from a fresh `git clone --recurse-submodules`, set up the way CI
does it, and add any missing step to the workspace README.

## 11. Things outside the tests

- personal configuration files at the root stay private; say in the
  instructions how the tool finds them from inside `public/`
  (`--config ../file.yaml`);
- private scripts that grep or walk `packages/` need the `public/` prefix;
- release or helper scripts elsewhere that default to a separate public clone
  should point at `public/` instead; a submodule's `.git` is a file, so test
  with `git rev-parse --git-dir`, not `[ -d .git ]`;
- a documentation site built from the private repository stops updating once
  the docs are public-only.
