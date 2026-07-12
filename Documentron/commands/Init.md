# Init

Initialize deterministic state, then scaffold documentation only from verified repository surfaces.

## Workflow

1. Run `scripts/documentron.py --repo . init` and `inventory`.
2. Preserve an existing documentation engine. Create MkDocs configuration only when none exists and the user selected MkDocs.
3. Copy/adapt templates for `.documentron/` maps and create missing documentation roots.
4. Use deterministic inventory for filenames, entrypoints, public symbols, tests, and commands.
5. Use the writer only for semantic introductions that cannot be generated from structured facts. Scientific content follows `references/scientific_review.md`.
6. Run `doctor --run-commands` only when configured validation is explicitly authorized.
7. Render `.documentron/reports/init-report.{md,html}` from JSON.

Never invent APIs, units, frames, behavior, or validation results.
