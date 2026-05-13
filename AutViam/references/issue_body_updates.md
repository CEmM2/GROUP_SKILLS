# GitHub Issue Body Mutations — Canonical Pattern

Use this exact 4-step pattern for every fetch-modify-update of an issue body. Never use `sed`, `awk -i inplace`, `perl -i`, or `python -c` for these mutations — those are shell mutations that require per-invocation approval under Claude Code's `accept-edits` mode and break pipeline autonomy. `Write` and `Edit` run autonomously under `accept-edits`.

## The 4 steps

1. **Fetch** (1 Bash call): `gh issue view <issue_number> --json body -q .body` — capture stdout directly. Do **not** redirect to a file in the shell; capture from the tool result.
2. **Materialise** (Write tool): save the captured body to `/tmp/issue_<N>_body.md`.
3. **Mutate** (Edit / MultiEdit tool): apply exact-string replacements. Disambiguate matches with surrounding context (e.g. include `#<N>` in `old_string` for checkbox flips). For structural rewrites with no stable anchor, render the new body with `Write` instead.
4. **Push back** (1 Bash call): `gh issue edit <issue_number> --body-file /tmp/issue_<N>_body.md`.

**Budget:** exactly 2 Bash calls per body update (one read, one write). Everything else is tool-driven and autonomous.

## Batching checkbox flips (phase-issue task list)

AutViam batches task-completion checkbox flips to the phase boundary. During a phase, keep a list of completed task IDs in memory. At phase close, run the 4 steps once for the phase issue body, using `MultiEdit` in step 3 to flip all `- [ ] <task_id>` → `- [x] <task_id>` lines in a single pass.

## Never

- Pass multi-line markdown as inline `--body "..."` — always go through the tempfile.
- Re-fetch the body mid-batch — fetch once at start of each mutation cycle, mutate, push once.
