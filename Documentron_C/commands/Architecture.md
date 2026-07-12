# Architecture

Generate architecture artifacts from deterministic topology plus bounded semantic labels.

## Workflow

1. Resolve tracked scope and run `inventory`.
2. Generate module/import/interface edges with static tooling available in the repository. Record dynamic or unresolved edges separately.
3. Run `prepare --command architecture` for the scoped paths.
4. Use the architect only to label responsibilities, contracts, runtime flows, extension points, and risks that static analysis cannot establish. Apply specialists inline.
5. Use the auditor to verify semantic labels when the packet requires independent review.
6. Render `.documentron/architecture/<slug>.{md,html}` from structured graph/result data.

Every node and edge must map to a real path or symbol. Mark inferred responsibilities and uncertain dynamic edges. Mermaid is optional and must be generated from the verified edge list, not freehand prose.
