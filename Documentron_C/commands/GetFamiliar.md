# GetFamiliar

Build durable repository-documentation configuration with minimal semantic work.

## Workflow

1. Run `init`, `inventory`, and `discover-specialists` without `--write`.
2. Detect tracked docs, manifests, entrypoints, design-doc roots, and validation tools from inventory. Do not execute repository code.
3. Generate `.documentron/doc-map.yml`, `theory-map.yml`, `repo-rules.yml`, and `repo-docs-guide.md` from deterministic inventories and templates.
4. Use the architect/auditor only for ambiguous responsibility, audience, terminology, or design-status classification. Pass file paths and unresolved fields only.
5. Present discovered specialist manifests and configuration changes for approval; compile them with `discover-specialists --write` only after approval.
6. Run `doctor` and render the report.

Do not use an LLM to enumerate files, infer regex triggers, check links, or render reports.
