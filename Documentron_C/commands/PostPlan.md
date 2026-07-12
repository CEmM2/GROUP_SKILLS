# PostPlan

Prepare and execute documentation closeout for an implemented plan.

## Workflow

1. Run `prepare --command post-plan --plan <plan_file>` to resolve scope, affected docs, invalidated claims, specialists, and review requirements.
2. Run the `update` workflow for the packet scope.
3. Unless disabled, run `architecture` for the same scope.
4. Unless disabled, run `theory check`; never run theory refresh automatically.
5. Aggregate structured statuses and render `.documentron/reports/post-plan-<slug>.{md,html}`.

The orchestrator itself uses no LLM. Semantic calls occur only inside selected subworkflows. Re-running at the same content hashes must reuse ledger verdicts and produce identical reports.

The outcomes are `clean`, `docs-updated`, `docs-drift-found`, `scientific-review-needed`, or `blocked`.
