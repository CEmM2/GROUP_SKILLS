#!/usr/bin/env python3
"""Claude-specific routing helpers for AutViam, plus the shared-core re-exports.

The generic primitives (JSON load, atomic write, locking, score validation, hashing)
live in `routing_core.py`, which is single-sourced from `skills/shared/scripts/` and
shared with AutViam_C. They are re-exported here so every existing
`from claude_routing_common import ...` keeps working unchanged.

`RoutingCommonError` is an *alias* for `RoutingCoreError`, not a subclass — the two names
bind the same class, so core-raised errors still match every `except RoutingCommonError`
site in this skill.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import Any, Mapping

from routing_core import (
    LOCK_STALE_AFTER_SECONDS,
    RoutingCoreError as RoutingCommonError,
    atomic_write_json,
    atomic_write_text,
    directory_lock as _core_directory_lock,
    load_json,
    sha256_text,
    validate_score,
)

__all__ = [
    # Re-exported from routing_core (canonical: skills/shared/scripts/routing_core.py).
    "LOCK_STALE_AFTER_SECONDS",
    "RoutingCommonError",
    "atomic_write_json",
    "atomic_write_text",
    "directory_lock",
    "load_json",
    "sha256_text",
    "validate_score",
    # Claude-specific.
    "default_nested_dispatch",
    "load_ticket_key",
    "normalize_config",
    "parse_frontmatter",
    "parse_frontmatter_text",
    "ticket_signature",
]


def directory_lock(path: Path, timeout_seconds: float = 30.0, stale_after_seconds: float = LOCK_STALE_AFTER_SECONDS):
    """AutViam's lock — pins the `.autviam-lock` suffix quoted by references/recovery.md."""
    return _core_directory_lock(
        path,
        timeout_seconds=timeout_seconds,
        stale_after_seconds=stale_after_seconds,
        suffix="autviam-lock",
        label="lock",
    )


def ticket_signature(ticket: Mapping[str, Any], key: bytes) -> str:
    payload = {name: value for name, value in ticket.items() if name != "signature"}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hmac.new(key, canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def load_ticket_key(path: Path) -> bytes:
    if not path.is_file():
        raise RoutingCommonError(f"routing ticket key does not exist: {path}")
    key = path.read_text(encoding="utf-8").strip().encode("ascii", errors="strict")
    if len(key) < 32:
        raise RoutingCommonError(f"routing ticket key is too short: {path}")
    return key


def parse_frontmatter_text(text: str, label: str) -> tuple[dict[str, str], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise RoutingCommonError(f"{label}: expected YAML frontmatter")
    try:
        closing = next(index for index in range(1, len(lines)) if lines[index].strip() == "---")
    except StopIteration as exc:
        raise RoutingCommonError(f"{label}: unterminated YAML frontmatter") from exc
    metadata: dict[str, str] = {}
    for line_number, line in enumerate(lines[1:closing], start=2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            raise RoutingCommonError(f"{label}:{line_number}: unsupported frontmatter line")
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"').strip("'")
    body = "\n".join(lines[closing + 1 :]).strip() + "\n"
    return metadata, body


def parse_frontmatter(path: Path) -> tuple[dict[str, str], str]:
    if not path.is_file():
        raise RoutingCommonError(f"agent file does not exist: {path}")
    return parse_frontmatter_text(path.read_text(encoding="utf-8"), str(path))


def default_nested_dispatch() -> dict[str, Any]:
    return {
        "mode": "off",
        "max_depth": 4,
        "runtime_max_depth": None,
        "phase_orchestrator": {"spawn_implementers": True, "spawn_reviewers": True},
        "domain_reviewer": {"specialists": "nested"},
        "on_depth_exhausted": "caller",
    }


def normalize_config(config: Mapping[str, Any] | None) -> dict[str, Any]:
    source = dict(config or {})
    nested = source.get("nested_dispatch", "off")
    if isinstance(nested, str):
        normalized_nested = default_nested_dispatch()
        normalized_nested["mode"] = nested
    elif isinstance(nested, dict):
        normalized_nested = default_nested_dispatch()
        normalized_nested.update(nested)
        for section in ("phase_orchestrator", "domain_reviewer"):
            merged = dict(default_nested_dispatch()[section])
            value = nested.get(section, {})
            if isinstance(value, dict):
                merged.update(value)
            normalized_nested[section] = merged
    else:
        raise RoutingCommonError("nested_dispatch must be a string or object")

    if normalized_nested["mode"] not in {"off", "on", "auto"}:
        raise RoutingCommonError("nested_dispatch.mode must be off, on, or auto")
    max_depth = normalized_nested.get("max_depth")
    runtime_max = normalized_nested.get("runtime_max_depth")
    if isinstance(max_depth, bool) or not isinstance(max_depth, int) or max_depth < 1:
        raise RoutingCommonError("nested_dispatch.max_depth must be a positive integer")
    if runtime_max is not None and (
        isinstance(runtime_max, bool) or not isinstance(runtime_max, int) or runtime_max < 1
    ):
        raise RoutingCommonError("nested_dispatch.runtime_max_depth must be null or a positive integer")
    if runtime_max is not None and max_depth > runtime_max:
        raise RoutingCommonError("nested_dispatch.max_depth exceeds runtime_max_depth")
    if normalized_nested["domain_reviewer"].get("specialists") not in {"nested", "caller", "off"}:
        raise RoutingCommonError("domain_reviewer.specialists must be nested, caller, or off")
    phase_permissions = normalized_nested["phase_orchestrator"]
    if not all(isinstance(phase_permissions.get(key), bool) for key in ("spawn_implementers", "spawn_reviewers")):
        raise RoutingCommonError("phase_orchestrator spawn flags must be booleans")
    if normalized_nested.get("on_depth_exhausted") not in {"caller", "block"}:
        raise RoutingCommonError("on_depth_exhausted must be caller or block")
    if normalized_nested["mode"] == "on" and runtime_max is None:
        raise RoutingCommonError("nested mode on requires a declared or detected runtime_max_depth")

    enforcement = source.get("routing_enforcement", "hook")
    if enforcement not in {"hook", "procedural"}:
        raise RoutingCommonError("routing_enforcement must be hook or procedural")
    allow_overrides = source.get("allow_environment_overrides", False)
    if not isinstance(allow_overrides, bool):
        raise RoutingCommonError("allow_environment_overrides must be boolean")
    source["schema_version"] = "2-claude-routing"
    source["routing_enforcement"] = enforcement
    source["allow_environment_overrides"] = allow_overrides
    source["nested_dispatch"] = normalized_nested
    return source
