# Refresh

Repair broader documentation drift using the same incremental engine as `update`.

## Workflow

1. Resolve the requested date, tag, or full scope deterministically.
2. Run `prepare --command refresh`.
3. Partition work into deterministic defects and invalidated semantic claims.
4. Apply deterministic repairs first. Use one bounded semantic pass per evidence packet, with matched lenses inline.
5. Require independent review for packet-designated scientific, security, or safety claims.
6. Validate and dry-run structured patches before applying them.
7. Re-index, validate, and render the report.

For `--full`, batch packets by documentation surface and enforce `llm_policy.packet_max_bytes`; never send the entire repository in one prompt.
