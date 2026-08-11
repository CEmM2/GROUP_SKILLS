"""Semantic approval binding — external to the plan document (does not self-hash)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .normalize import NormalizedPlan, content_hash, dumps_canonical, normalize_semantic_plan


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def approve_plan(
    normalized: NormalizedPlan,
    *,
    approver_id: str,
    authority: str = "human-approved",
    conditions: list[str] | None = None,
    exclusions: list[str] | None = None,
) -> dict[str, Any]:
    """Bind approval to exact normalized + source-manifest hashes.

    The approval object deliberately omits a self-hash of the full approval
    envelope; verifiers recompute binding from the listed digests.
    """

    receipt = {
        "schema_version": "autviam.semantic-approval/v1",
        "approved": True,
        "normalized_hash": normalized.normalized_hash,
        "source_manifest_hash": normalized.source_manifest_hash,
        "approver_id": approver_id,
        "authority": authority,
        "conditions": list(conditions or []),
        "exclusions": list(exclusions or []),
        "approved_at": utc_now(),
        "plan_id": (normalized.plan.get("plan") or {}).get("id"),
    }
    # Binding digest over the hash pair + approver (not the timestamp) for
    # machine checks that ignore wall clock.
    binding_payload = {
        "normalized_hash": receipt["normalized_hash"],
        "source_manifest_hash": receipt["source_manifest_hash"],
        "approver_id": approver_id,
        "authority": authority,
        "conditions": receipt["conditions"],
        "exclusions": receipt["exclusions"],
    }
    receipt["binding_hash"] = content_hash(binding_payload)
    return receipt


def verify_approval(
    plan: dict[str, Any],
    approval: dict[str, Any],
    *,
    require_approved: bool = True,
) -> dict[str, Any]:
    """Recompute normalization and check approval binding.

    Returns a structured result; does not raise on mismatch (callers decide).
    """

    issues: list[str] = []
    if require_approved and not approval.get("approved"):
        issues.append("approval.approved is not true")

    try:
        normalized = normalize_semantic_plan(plan)
    except Exception as exc:  # noqa: BLE001
        return {
            "valid": False,
            "issues": [f"normalize failed: {exc}"],
            "normalized_hash": None,
        }

    if approval.get("normalized_hash") != normalized.normalized_hash:
        issues.append(
            "normalized_hash mismatch: "
            f"approval={approval.get('normalized_hash')} "
            f"recomputed={normalized.normalized_hash}"
        )
    if approval.get("source_manifest_hash") != normalized.source_manifest_hash:
        issues.append(
            "source_manifest_hash mismatch: "
            f"approval={approval.get('source_manifest_hash')} "
            f"recomputed={normalized.source_manifest_hash}"
        )

    # Recompute binding hash ignoring timestamp
    binding_payload = {
        "normalized_hash": approval.get("normalized_hash"),
        "source_manifest_hash": approval.get("source_manifest_hash"),
        "approver_id": approval.get("approver_id"),
        "authority": approval.get("authority"),
        "conditions": approval.get("conditions") or [],
        "exclusions": approval.get("exclusions") or [],
    }
    expected_binding = content_hash(binding_payload)
    if approval.get("binding_hash") != expected_binding:
        # If hashes already mismatched, binding will too; still report.
        if approval.get("normalized_hash") == normalized.normalized_hash:
            issues.append("binding_hash mismatch")

    return {
        "valid": not issues,
        "issues": issues,
        "normalized_hash": normalized.normalized_hash,
        "source_manifest_hash": normalized.source_manifest_hash,
        "approval_normalized_hash": approval.get("normalized_hash"),
    }


def source_change_invalidates(
    original_plan: dict[str, Any],
    modified_source_text: str,
    approval: dict[str, Any],
    *,
    reclassify,
) -> dict[str, Any]:
    """Helper for tests: after source text changes, approval must fail."""

    new_plan = reclassify(modified_source_text)
    return verify_approval(new_plan, approval)
