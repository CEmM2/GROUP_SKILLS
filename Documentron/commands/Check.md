# Check

Run a read-only documentation drift check.

## Workflow

1. Resolve the requested Git range or paths with `scripts/documentron.py scope`.
2. Run `prepare --command check` with the same scope.
3. If the packet requires no reviews, use deterministic findings directly.
4. Otherwise run the auditor once with all matched specialist lenses inline. When the packet requires independent review, run the scientific reviewer separately.
5. Do not apply patches. Validate the semantic JSON with `validate-result`.
6. Run `doctor`; add `--run-commands` only when the user requested validation execution.
7. Combine deterministic and semantic JSON, then use `render-report` for `.documentron/reports/check-report.{md,html}`.

Classify missing, stale, contradictory, broken, misplaced, overclaimed, underspecified, deprecated, design-doc, and theory drift. Cite exact evidence and keep unverifiable claims unresolved.
