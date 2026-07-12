# Update

Incrementally update documentation for a plan, PR, commit range, or explicit paths.

## Workflow

1. Resolve scope deterministically from the supplied source. Prefer an explicit Git base/head over prose metadata.
2. Run `prepare --command update` with that scope.
3. If `required_reviews=0`, make only deterministic map/generated-interface changes.
4. Otherwise run one auditor/writer semantic pass with all matched lenses inline. Run a fresh independent scientific reviewer when required.
5. Validate result JSON, dry-run the patches, then apply them.
6. Re-run preparation. Unchanged claims must be reused; remaining invalidated claims must be explained.
7. Run allowlisted validation when authorized and render the update report from JSON.

Update user, developer, theory, README, maps, and rules only when the scope-to-document mapping selects them. Do not scan or rewrite unrelated documentation.
