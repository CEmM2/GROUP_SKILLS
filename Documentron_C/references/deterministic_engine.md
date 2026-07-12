# Deterministic engine

`scripts/documentron.py` owns every reproducible operation. Run it from the repository root with `--repo .`.

## Commands

| Command | Purpose | LLM use |
|---|---|---|
| `init` | Create `.documentron/config.json` and state directories without overwriting config. | None |
| `inventory` | Enumerate tracked files, documentation, design docs, and manifests. | None |
| `scope` | Resolve paths from a Git range, plan, path list, or paths file. | None |
| `prepare` | Build a bounded, content-hashed semantic-review packet and route specialists. | None |
| `match-specialists` | Explain declarative specialist matches. | None |
| `validate-result` | Validate semantic-review counts, verdicts, evidence lists, and patches. | None |
| `apply-result` | Apply preimage-hashed documentation patches and update the claim ledger. | None |
| `doctor` | Validate config, specialists, links, and allowlisted commands. | None |
| `render-report` | Render deterministic Markdown and offline HTML from JSON. | None |
| `discover-specialists` | Find `documentron-specialist.json` manifests; optionally compile them into config. | None |

## Semantic boundary

Run `prepare` before reading broad repository context. The packet contains:

- resolved scope and content hash;
- affected documentation;
- invalidated claims only;
- matched specialists and match reasons;
- minimum semantic-review count;
- bounded evidence excerpts.

If `llm_policy.required_reviews` is zero, do not invoke an LLM. If it is nonzero, pass the packet path rather than copying its full JSON into a prompt. Apply every matched specialist as an inline lens unless independent review is required.

The LLM returns JSON conforming to `templates/semantic-result.schema.json`. Validate it before any edit. `apply-result` accepts documentation patches only and requires an exact SHA-256 preimage plus a unique text match.

## Claim ledger

`.documentron/claims.jsonl` caches verified claims. A claim is reused only while its paragraph hash and complete scope/evidence hash remain unchanged. Source, equation, test, configuration, units, frame, tolerance, or citation changes therefore invalidate the verdict.

Do not update the ledger by hand. `apply-result` records validated results.

## Retry policy

- Malformed semantic JSON: one schema-repair attempt.
- Deterministic failure: no LLM retry; fix the input or script defect.
- Semantic correction failing validation: one targeted repair.
- Same semantic failure twice: stop as blocked.

## Safety

Only commands listed in `.documentron/config.json` under `validation.allowlisted_commands` may be executed, and only when `doctor --run-commands` is explicitly requested. Discovery and preparation never execute repository code.
