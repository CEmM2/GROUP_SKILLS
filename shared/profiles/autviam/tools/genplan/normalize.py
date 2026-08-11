"""Normalize semantic plans to a stable hashable form (RFC 8785-style ordering)."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

DECIMAL_RE = re.compile(r"^[+-]?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?$")


def _canonical_decimal(value: str) -> str:
    if not DECIMAL_RE.fullmatch(value):
        raise ValueError(f"invalid exact decimal string: {value!r}")
    dec = Decimal(value)
    if not dec.is_finite():
        raise ValueError("NaN/infinity forbidden")
    if dec.is_zero():
        return "0"
    rendered = format(dec, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered


def _normalize_value(value: Any) -> Any:
    if isinstance(value, dict):
        # Quantity object
        if set(value.keys()) <= {"value", "unit", "uncertainty"} and "value" in value and "unit" in value:
            out = {
                "value": (
                    _canonical_decimal(value["value"])
                    if isinstance(value["value"], str)
                    else value["value"]
                ),
                "unit": value["unit"],
                "uncertainty": (
                    None
                    if value.get("uncertainty") is None
                    else (
                        _canonical_decimal(value["uncertainty"])
                        if isinstance(value["uncertainty"], str)
                        else value["uncertainty"]
                    )
                ),
            }
            return out
        return {k: _normalize_value(value[k]) for k in sorted(value.keys())}
    if isinstance(value, list):
        return [_normalize_value(v) for v in value]
    if isinstance(value, str):
        # NFC would go here; keep as-is for source fidelity in statements.
        return value
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        # Normative quantities must not be bare floats; leave as error marker via string
        raise ValueError(f"bare float not allowed in normative data: {value!r}")
    return value


def _sort_object_lists(plan: dict[str, Any]) -> dict[str, Any]:
    """Sort known object arrays by id for stable hashing."""

    out = deepcopy(plan)
    for key in (
        "milestones",
        "work_packages",
        "semantic_checkpoints",
        "evidence_intents",
        "requirements",
        "decisions",
        "assets",
        "context_requirements",
        "open_decisions",
        "preconditions",
        "failure_modes",
    ):
        if isinstance(out.get(key), list):
            out[key] = sorted(
                out[key],
                key=lambda item: (
                    item.get("id", "") if isinstance(item, dict) else str(item)
                ),
            )
    return out


def dumps_canonical(obj: Any) -> str:
    """Stable JSON: sorted keys, no insignificant whitespace variance, trailing newline."""

    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def content_hash(obj: Any) -> str:
    raw = dumps_canonical(obj).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class NormalizedPlan:
    plan: dict[str, Any]
    normalized_json: str
    normalized_hash: str
    source_manifest_hash: str


def normalize_semantic_plan(plan: dict[str, Any]) -> NormalizedPlan:
    """Return normalized plan + hashes. Approval must not be inside the plan."""

    if "approval" in plan:
        raise ValueError("approval must not be embedded in the semantic plan document")
    cleaned = {k: v for k, v in plan.items() if k != "approval"}
    ordered = _sort_object_lists(cleaned)
    normalized = _normalize_value(ordered)
    if not isinstance(normalized, dict):
        raise ValueError("normalized plan must be a mapping")
    # Source manifest hash from sources.manifest if present
    manifest = []
    sources = normalized.get("sources")
    if isinstance(sources, dict) and isinstance(sources.get("manifest"), list):
        manifest = sources["manifest"]
    manifest_hash = content_hash(manifest)
    body = dumps_canonical(normalized)
    return NormalizedPlan(
        plan=normalized,
        normalized_json=body,
        normalized_hash=content_hash(normalized),
        source_manifest_hash=manifest_hash,
    )
