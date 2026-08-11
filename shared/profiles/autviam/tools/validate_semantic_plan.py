#!/usr/bin/env python3
"""Validate AutViam semantic-plan fixtures (A2-3).

Standalone of the Whatter kernel compile path. Enforces A-002 hierarchy
(no semantic Phase), A-003 scp IDs, explicit authority, and A-005 quantities.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("PyYAML required: pip install pyyaml") from exc

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = PACKAGE_ROOT / "schemas" / "semantic-plan" / "semantic-plan.schema.yaml"

ID_PATTERNS = {
    "plan": re.compile(r"^plan-[a-z][a-z0-9]*(?:-[a-z0-9]+)*$"),
    "program": re.compile(r"^prog-[a-z][a-z0-9]*(?:-[a-z0-9]+)*$"),
    "milestone": re.compile(r"^ms-[a-z][a-z0-9]*(?:-[a-z0-9]+)*$"),
    "work_package": re.compile(r"^wp-[a-z][a-z0-9]*(?:-[a-z0-9]+)*$"),
    "semantic_checkpoint": re.compile(r"^scp-[a-z][a-z0-9]*(?:-[a-z0-9]+)*$"),
    "evidence_intent": re.compile(r"^ei-[a-z][a-z0-9]*(?:-[a-z0-9]+)*$"),
    "requirement": re.compile(r"^req-[a-z][a-z0-9]*(?:-[a-z0-9]+)*$"),
    "decision": re.compile(r"^dec-[a-z][a-z0-9]*(?:-[a-z0-9]+)*$"),
    "asset": re.compile(r"^asset-[a-z][a-z0-9]*(?:-[a-z0-9]+)*$"),
    "context_requirement": re.compile(r"^ctx-[a-z][a-z0-9]*(?:-[a-z0-9]+)*$"),
}

FORBIDDEN_TOP = {
    "phases",
    "phase",
    "execution_phases",
    "execution_plan",
    "retry_budget",
    "routing",
    "gate_policy",
    "max_task_attempts",
    "scheduler",
    "recovery_profile",
}
FORBIDDEN_NESTED = {
    "retry_budget",
    "max_attempts",
    "routing_scores",
    "gate_a",
    "gate_b",
    "gate_c",
    "execution_phase_id",
    "phase_id",
    "branch_strategy",
    "worktree_policy",
    "model_tier",
    "session_affinity",
}
AUTHORITY_CLASSES = {
    "verified",
    "repository-supported",
    "user-asserted",
    "inferred",
    "uncertain",
    "contradicted",
    "profile-policy",
    "human-approved",
}
DECIMAL_RE = re.compile(r"^[+-]?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?$")


class SemanticValidationError(ValueError):
    """Semantic plan failed A2-3 rules."""


def load_yaml(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise SemanticValidationError(f"{path}: document must be a mapping")
    return data


def _walk_forbidden(obj: Any, path: str, errors: list[str]) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            here = f"{path}.{key}" if path else key
            if key in FORBIDDEN_NESTED or key in FORBIDDEN_TOP:
                errors.append(f"{here}: forbidden semantic/execution field {key!r}")
            if key in {"phase", "phases"} or (
                isinstance(key, str) and key.endswith("_phase") and key != "trace_phase"
            ):
                # catch semantic phase objects
                if key in {"phase", "phases", "execution_phase_id", "phase_id"}:
                    errors.append(f"{here}: semantic Phase object/field is forbidden (A-002)")
            _walk_forbidden(value, here, errors)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _walk_forbidden(item, f"{path}[{i}]", errors)


def _is_quantity_object(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and "value" in value
        and "unit" in value
        and "uncertainty" in value
        and set(value.keys()) <= {"value", "unit", "uncertainty"}
    )


def _validate_quantity(value: Any, path: str, errors: list[str]) -> str | None:
    """Return canonical decimal string if valid quantity, else None and append errors."""

    if not _is_quantity_object(value):
        return None
    raw = value.get("value")
    unit = value.get("unit")
    unc = value.get("uncertainty")
    if not isinstance(raw, str):
        errors.append(
            f"{path}.value: normative quantity value must be an exact decimal string "
            f"(got {type(raw).__name__})"
        )
        return None
    if not DECIMAL_RE.fullmatch(raw):
        errors.append(f"{path}.value: invalid exact decimal string {raw!r}")
        return None
    try:
        dec = Decimal(raw)
    except InvalidOperation:
        errors.append(f"{path}.value: not a finite decimal {raw!r}")
        return None
    if not dec.is_finite():
        errors.append(f"{path}.value: NaN/infinity forbidden")
        return None
    if not isinstance(unit, str) or not unit.strip():
        errors.append(f"{path}.unit: mandatory non-blank unit string")
        return None
    if unc is not None:
        if not isinstance(unc, str) or not DECIMAL_RE.fullmatch(unc):
            errors.append(f"{path}.uncertainty: must be null or exact decimal string")
            return None
    # Canonical plain decimal
    if dec.is_zero():
        return "0"
    rendered = format(dec, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered


def _scan_quantities(obj: Any, path: str, errors: list[str], canons: list[tuple[str, str]]) -> None:
    if _is_quantity_object(obj):
        canon = _validate_quantity(obj, path, errors)
        if canon is not None:
            canons.append((path, canon))
        return
    if isinstance(obj, dict):
        # Reject half-quantity shapes that look intentional
        if "value" in obj and "unit" in obj and not _is_quantity_object(obj):
            errors.append(f"{path}: quantity-like object must have keys value/unit/uncertainty only")
        for key, value in obj.items():
            _scan_quantities(value, f"{path}.{key}" if path else key, errors, canons)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _scan_quantities(item, f"{path}[{i}]", errors, canons)


def _check_id(kind: str, obj_id: str, path: str, errors: list[str]) -> None:
    pat = ID_PATTERNS.get(kind)
    if pat is None:
        return
    if not isinstance(obj_id, str) or not pat.fullmatch(obj_id):
        errors.append(f"{path}.id: expected {kind} id matching {pat.pattern}, got {obj_id!r}")


def _require_authority(obj: dict[str, Any], path: str, errors: list[str]) -> None:
    auth = obj.get("authority")
    if auth is None:
        errors.append(f"{path}: missing required field 'authority'")
    elif auth not in AUTHORITY_CLASSES:
        errors.append(f"{path}.authority: unknown class {auth!r}")


def validate_semantic_plan(data: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if data.get("schema_version") != "autviam.semantic-plan/v1":
        errors.append(
            f"schema_version must be 'autviam.semantic-plan/v1', got {data.get('schema_version')!r}"
        )

    for key in FORBIDDEN_TOP:
        if key in data:
            errors.append(f"top-level forbidden field {key!r} (A-002 / no execution policy as fact)")

    _walk_forbidden(data, "", errors)

    plan = data.get("plan")
    if not isinstance(plan, dict):
        errors.append("plan: required mapping")
        plan = {}
    else:
        for field in ("id", "title", "program_id"):
            if field not in plan:
                errors.append(f"plan.{field}: required")
        if "id" in plan:
            _check_id("plan", plan["id"], "plan", errors)
        if "program_id" in plan:
            _check_id("program", plan["program_id"], "plan.program_id", errors)
        _require_authority(plan, "plan", errors)

    milestone_ids: set[str] = set()
    for i, ms in enumerate(data.get("milestones") or []):
        path = f"milestones[{i}]"
        if not isinstance(ms, dict):
            errors.append(f"{path}: must be mapping")
            continue
        _check_id("milestone", ms.get("id", ""), path, errors)
        _require_authority(ms, path, errors)
        if "title" not in ms:
            errors.append(f"{path}.title: required")
        if ms.get("id"):
            milestone_ids.add(ms["id"])
        if ms.get("program_id"):
            _check_id("program", ms["program_id"], f"{path}.program_id", errors)

    wp_ids: set[str] = set()
    for i, wp in enumerate(data.get("work_packages") or []):
        path = f"work_packages[{i}]"
        if not isinstance(wp, dict):
            errors.append(f"{path}: must be mapping")
            continue
        _check_id("work_package", wp.get("id", ""), path, errors)
        _require_authority(wp, path, errors)
        if "title" not in wp:
            errors.append(f"{path}.title: required")
        mid = wp.get("milestone_id")
        if not mid:
            errors.append(f"{path}.milestone_id: required")
        elif mid not in milestone_ids and data.get("milestones") is not None:
            errors.append(f"{path}.milestone_id: unknown reference {mid!r}")
        if wp.get("id"):
            wp_ids.add(wp["id"])

    scp_ids: set[str] = set()
    for i, scp in enumerate(data.get("semantic_checkpoints") or []):
        path = f"semantic_checkpoints[{i}]"
        if not isinstance(scp, dict):
            errors.append(f"{path}: must be mapping")
            continue
        _check_id("semantic_checkpoint", scp.get("id", ""), path, errors)
        _require_authority(scp, path, errors)
        wpid = scp.get("work_package_id")
        if not wpid:
            errors.append(f"{path}.work_package_id: required")
        elif wpid not in wp_ids and data.get("work_packages") is not None:
            errors.append(f"{path}.work_package_id: unknown reference {wpid!r}")
        if scp.get("id"):
            scp_ids.add(scp["id"])

    for i, ei in enumerate(data.get("evidence_intents") or []):
        path = f"evidence_intents[{i}]"
        if not isinstance(ei, dict):
            errors.append(f"{path}: must be mapping")
            continue
        _check_id("evidence_intent", ei.get("id", ""), path, errors)
        _require_authority(ei, path, errors)
        scpid = ei.get("semantic_checkpoint_id")
        if not scpid:
            errors.append(f"{path}.semantic_checkpoint_id: required")
        elif scpid not in scp_ids and data.get("semantic_checkpoints") is not None:
            errors.append(f"{path}.semantic_checkpoint_id: unknown reference {scpid!r}")

    for i, req in enumerate(data.get("requirements") or []):
        path = f"requirements[{i}]"
        if not isinstance(req, dict):
            continue
        _check_id("requirement", req.get("id", ""), path, errors)
        _require_authority(req, path, errors)

    for i, dec in enumerate(data.get("decisions") or []):
        path = f"decisions[{i}]"
        if not isinstance(dec, dict):
            continue
        _check_id("decision", dec.get("id", ""), path, errors)
        _require_authority(dec, path, errors)

    for i, asset in enumerate(data.get("assets") or []):
        path = f"assets[{i}]"
        if not isinstance(asset, dict):
            continue
        _check_id("asset", asset.get("id", ""), path, errors)
        _require_authority(asset, path, errors)

    for i, ctx in enumerate(data.get("context_requirements") or []):
        path = f"context_requirements[{i}]"
        if not isinstance(ctx, dict):
            continue
        _check_id("context_requirement", ctx.get("id", ""), path, errors)
        _require_authority(ctx, path, errors)

    canons: list[tuple[str, str]] = []
    _scan_quantities(data, "", errors, canons)

    # Reject ecp-* as semantic checkpoint ids
    for i, scp in enumerate(data.get("semantic_checkpoints") or []):
        if isinstance(scp, dict) and isinstance(scp.get("id"), str) and scp["id"].startswith("ecp-"):
            errors.append(
                f"semantic_checkpoints[{i}].id: ecp-* is execution-only (A-003)"
            )

    return {
        "valid": not errors,
        "errors": errors,
        "quantity_canonicals": canons,
        "object_counts": {
            "milestones": len(data.get("milestones") or []),
            "work_packages": len(data.get("work_packages") or []),
            "semantic_checkpoints": len(data.get("semantic_checkpoints") or []),
            "evidence_intents": len(data.get("evidence_intents") or []),
        },
    }


def validate_path(path: Path) -> dict[str, Any]:
    data = load_yaml(path)
    result = validate_semantic_plan(data)
    result["path"] = str(path)
    return result


def run_fixture_suite(fixtures_root: Path | None = None) -> dict[str, Any]:
    root = fixtures_root or (PACKAGE_ROOT / "fixtures")
    report: dict[str, Any] = {
        "schema_version": "autviam.a2-3.fixture-report/v1",
        "valid": [],
        "invalid": [],
        "all_passed": True,
    }
    for path in sorted((root / "valid").glob("*.yaml")):
        result = validate_path(path)
        entry = {
            "path": path.name,
            "expected": "valid",
            "valid": result["valid"],
            "errors": result["errors"],
            "quantity_canonicals": result["quantity_canonicals"],
        }
        if not result["valid"]:
            report["all_passed"] = False
        report["valid"].append(entry)
    for path in sorted((root / "invalid").glob("*.yaml")):
        result = validate_path(path)
        entry = {
            "path": path.name,
            "expected": "invalid",
            "valid": result["valid"],
            "rejected_as_expected": not result["valid"],
            "errors": result["errors"],
        }
        if result["valid"]:
            report["all_passed"] = False
        report["invalid"].append(entry)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path, help="Semantic plan YAML files")
    parser.add_argument(
        "--suite",
        action="store_true",
        help="Run package fixtures/valid and fixtures/invalid suite",
    )
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args(argv)

    if args.suite or not args.paths:
        report = run_fixture_suite()
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print(
                f"fixture suite all_passed={report['all_passed']} "
                f"valid={len(report['valid'])} invalid={len(report['invalid'])}"
            )
            for entry in report["valid"] + report["invalid"]:
                status = "OK" if (
                    (entry["expected"] == "valid" and entry["valid"])
                    or (entry["expected"] == "invalid" and not entry["valid"])
                ) else "FAIL"
                print(f"  [{status}] {entry['path']} expected={entry['expected']} valid={entry['valid']}")
                if status == "FAIL":
                    for err in entry.get("errors") or []:
                        print(f"    - {err}")
        return 0 if report["all_passed"] else 1

    all_ok = True
    results = []
    for path in args.paths:
        result = validate_path(path)
        results.append(result)
        if not result["valid"]:
            all_ok = False
    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        for result in results:
            print(f"{result['path']}: valid={result['valid']}")
            for err in result["errors"]:
                print(f"  - {err}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
