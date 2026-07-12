# FactCheck

Verify a target document incrementally and correct it only when evidence determines the replacement.

## Workflow

1. Run `prepare --command factcheck --paths <target> [evidence paths...]`.
2. Reuse ledger verdicts; review only `invalidated_claims`.
3. Resolve naming, path, link, quantitative, signature, and generated-interface facts deterministically where possible.
4. For remaining semantics, run the auditor with matched lenses inline. Follow `references/scientific_review.md` for scientific claims and run the independent reviewer when required.
5. Have the writer emit schema-conforming, preimage-hashed patches only for confirmed corrections. The auditor and writer may be one call for ordinary claims; high-risk scientific authoring and independent verification remain separate.
6. Run `validate-result`, then `apply-result --dry-run`. Apply for real only after the dry run succeeds.
7. Re-run `prepare` and deterministic validation. Recurring semantic failure stops the workflow.
8. Render the structured result; do not append free-form summaries directly.

Git history verifies temporal claims only. Design docs verify intent only.
