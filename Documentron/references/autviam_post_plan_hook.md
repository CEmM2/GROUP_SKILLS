# AutViam post-plan hook

Wire `scripts/documentron-post-plan-hook.sh <plan_file> [repo_root]` after a successful AutViam or AutViam_C plan closure.

The hook does not invoke an assistant. It deterministically:

1. resolves the exact plan path and referenced scope;
2. prepares a content-hashed `post-plan` packet;
3. stores the packet summary at `.documentron/hooks/pending-post-plan.json`;
4. prints the packet path for the host runtime.

The host reads that packet and runs only the semantic reviews required by `llm_policy.required_reviews`. Theory refresh is never automatic.

The hook is idempotent: unchanged plan/evidence hashes produce the same run identifier and packet path. A Documentron failure must not reopen or mutate already-closed AutViam work; report it as documentation debt.
