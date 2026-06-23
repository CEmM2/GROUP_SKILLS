# Issue Body Updates

Use this exact 4-step pattern for every fetch-modify-update of a GitHub issue body. Avoid ad hoc shell text mutation (`sed -i`, `awk -i`, `perl -i`, `python -c`) for these changes; it is harder to review and more brittle than materialising the body and editing it with Codex file-editing tools.

## Pattern

1. **Fetch** (1 shell call): `gh issue view <issue_number> --json body -q .body` — capture stdout directly. Do **not** redirect to a file in the shell; capture from the tool result.
2. **Materialise**: save the captured body to `<tasks_folder>/scratch/issue_<N>_body.md` with a Codex file-editing tool.
3. **Mutate**: apply exact-string replacements in that temp file. Disambiguate matches with surrounding context (e.g. include `#<N>` in the old string for checkbox flips). For structural rewrites with no stable anchor, render the new body into the temp file.
4. **Push back** (1 shell call): `gh issue edit <issue_number> --body-file <tasks_folder>/scratch/issue_<N>_body.md`.

**Budget:** exactly 2 shell calls per body update (one read, one write). Everything else is file-edit driven.

## Phase Checkbox Batch

AutViam_C batches task-completion checkbox flips to the phase boundary. During a phase, keep a list of completed task IDs in memory. At phase close, run the 4 steps once for the phase issue body, flipping all `- [ ] <task_id>` lines to `- [x] <task_id>` in one file edit.

## Avoid

- Editing issue bodies directly with fragile shell one-liners.
- Re-fetching between every checkbox flip.
- Passing multi-line markdown as inline `--body "..."`; always go through the tempfile.
