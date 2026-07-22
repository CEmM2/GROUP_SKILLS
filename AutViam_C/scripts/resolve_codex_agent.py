#!/usr/bin/env python3
"""Resolve and validate one AutViam_C Path-2 Codex agent route."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

# `RoutingError` is an *alias* for `RoutingCoreError`, not a subclass: the two names bind
# the same class, so errors raised inside routing_core still match the `except
# RoutingError` sites here and in validate_codex_agent_routing.py. Subclassing would let
# core errors escape those handlers and turn clean `exit 2` failures into tracebacks.
from routing_core import (
    LOCK_STALE_AFTER_SECONDS,
    RoutingCoreError as RoutingError,
    atomic_write_json,
    directory_lock,
    load_json,
    validate_score,
)

try:
    import tomllib
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit("Python 3.11+ is required (tomllib is used).") from exc


BUILT_IN_AGENTS = {"default", "explorer", "worker"}
READ_ONLY_ROLES = {
    "domain_reviewer",
    "explorer",
    "mechanical_read_only",
    "spec_reviewer",
}
WRITABLE_ROLES = {"implementer", "orchestrator"}
REQUIRED_PROFILE_FIELDS = {
    "description",
    "developer_instructions",
    "name",
    "model",
    "model_reasoning_effort",
    "sandbox_mode",
}
EXPECTED_PROFILE_CONFIG = {
    "terra_medium": ("gpt-5.6-terra", "medium"),
    "terra_high": ("gpt-5.6-terra", "high"),
    "sol_high": ("gpt-5.6-sol", "high"),
    "sol_xhigh": ("gpt-5.6-sol", "xhigh"),
    "luna_medium": ("gpt-5.6-luna", "medium"),
}
PURPOSE_ROLES = {
    "explore": {"explorer"},
    "gate-a": {"spec_reviewer"},
    "gate-b": {"domain_reviewer"},
    "implementer": {"implementer"},
    "mechanical-read-only": {"mechanical_read_only"},
    "nesting-probe": {"orchestrator", "spec_reviewer"},
    "phase-orchestrator": {"orchestrator"},
    "scaffold": {"implementer"},
    "specialist": {"explorer"},
}
ROLE_PROMPT_FILES = {
    "implementer": "autviam-implementer.md",
    "orchestrator": "autviam-phase-orchestrator.md",
    "spec_reviewer": "autviam-spec-reviewer.md",
    "domain_reviewer": "autviam-domain-reviewer.md",
    "explorer": "autviam-explorer.md",
    "mechanical_read_only": "autviam-search.md",
}


def skill_root() -> Path:
    return Path(__file__).resolve().parent.parent


def default_policy_path() -> Path:
    return skill_root() / "references" / "codex-agent-routing.json"


def default_capabilities_path() -> Path:
    return skill_root() / "runtime" / "subagent-dispatch-capabilities.json"


def default_agents_dir() -> Path:
    current_skill = skill_root()
    if (
        current_skill.parent.name == "skills"
        and current_skill.parent.parent.name == ".codex"
    ):
        return current_skill.parent.parent / "agents"
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        )
        root = completed.stdout.strip()
        if root:
            return Path(root) / ".codex" / "agents"
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    return Path.cwd() / ".codex" / "agents"


def validate_policy(policy: Mapping[str, Any]) -> None:
    if policy.get("schema_version") != 1:
        raise RoutingError("routing policy schema_version must be 1")
    if (
        not isinstance(policy.get("policy_version"), str)
        or not policy["policy_version"].strip()
    ):
        raise RoutingError("routing policy policy_version must be a non-empty string")

    score_keys = {str(value) for value in range(1, 6)}
    matrix = policy.get("base_tier_by_score")
    if not isinstance(matrix, dict) or set(matrix) != score_keys:
        raise RoutingError(
            "base_tier_by_score must define exactly complexity scores 1 through 5"
        )
    for complexity, row in matrix.items():
        if not isinstance(row, dict) or set(row) != score_keys:
            raise RoutingError(
                f"base_tier_by_score[{complexity!r}] must define risks 1 through 5"
            )

    profiles = policy.get("profiles_by_role_and_tier")
    required_roles = {
        "domain_reviewer",
        "explorer",
        "implementer",
        "orchestrator",
        "spec_reviewer",
    }
    if not isinstance(profiles, dict) or set(profiles) != required_roles:
        raise RoutingError(
            f"profiles_by_role_and_tier must define exactly {sorted(required_roles)}"
        )
    tiers = {value for row in matrix.values() for value in row.values()}
    for role, role_routes in profiles.items():
        if not isinstance(role_routes, dict) or set(role_routes) != tiers:
            raise RoutingError(
                f"profiles_by_role_and_tier[{role!r}] must define tiers {sorted(tiers)}"
            )
        for agent in role_routes.values():
            if not isinstance(agent, str) or not agent or agent in BUILT_IN_AGENTS:
                raise RoutingError(
                    f"role {role!r} selects forbidden or invalid agent {agent!r}"
                )

    dispatch_policy = policy.get("dispatch_policy")
    dispatch_roles = required_roles | {"mechanical_read_only"}
    if not isinstance(dispatch_policy, dict) or set(dispatch_policy) != dispatch_roles:
        raise RoutingError(
            f"dispatch_policy must define exactly {sorted(dispatch_roles)}"
        )
    for role, requirement in dispatch_policy.items():
        if not isinstance(requirement, dict) or set(requirement) != {
            "allow_uncontrolled_effort",
            "allow_uncontrolled_sandbox",
            "minimum_enforcement",
        }:
            raise RoutingError(
                f"dispatch_policy[{role!r}] has missing or unexpected fields"
            )
        if requirement["minimum_enforcement"] not in {"exact", "model_and_prompt"}:
            raise RoutingError(
                f"dispatch_policy[{role!r}] has invalid minimum_enforcement"
            )
        for flag in ("allow_uncontrolled_effort", "allow_uncontrolled_sandbox"):
            if not isinstance(requirement[flag], bool):
                raise RoutingError(f"dispatch_policy[{role!r}] {flag} must be boolean")
        if role in READ_ONLY_ROLES and requirement["allow_uncontrolled_sandbox"]:
            raise RoutingError(
                f"read-only role {role!r} must not set allow_uncontrolled_sandbox; an "
                "uncontrolled sandbox lets it inherit the caller's write access"
            )

    special = policy.get("special_routes", {}).get("mechanical_read_only")
    if not isinstance(special, dict):
        raise RoutingError("special_routes.mechanical_read_only is required")
    validate_score("maximum_complexity", special.get("maximum_complexity"))
    validate_score("maximum_risk", special.get("maximum_risk"))
    if special.get("fallback_role") != "explorer":
        raise RoutingError("mechanical_read_only fallback_role must be 'explorer'")
    if not isinstance(special.get("agent"), str) or special["agent"] in BUILT_IN_AGENTS:
        raise RoutingError(
            "mechanical_read_only agent must name an external/audit profile projection"
        )

    failure_policy = policy.get("failure_policy")
    required_failures = {
        "invalid_score",
        "missing_agent_profile",
        "missing_route",
        "unconfigured_model_or_effort",
        "unknown_role",
        "invalid_dispatcher_capabilities",
        "missing_prompt_file",
    }
    if not isinstance(failure_policy, dict) or set(failure_policy) != required_failures:
        raise RoutingError("failure_policy has missing or unexpected entries")
    if set(failure_policy.values()) != {"error"}:
        raise RoutingError("every failure_policy action must be 'error'")


def _require_boolean(document: Mapping[str, Any], key: str, label: str) -> bool:
    value = document.get(key)
    if not isinstance(value, bool):
        raise RoutingError(f"{label}.{key} must be boolean")
    return value


def _supported_models(document: Mapping[str, Any], label: str) -> list[str]:
    value = document.get("supported_models")
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise RoutingError(
            f"{label}.supported_models must be an array of non-empty strings"
        )
    if len(value) != len(set(value)):
        raise RoutingError(f"{label}.supported_models must not contain duplicates")
    return list(value)


def validate_dispatcher_capabilities(capabilities: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize the runtime-derived dispatcher capability record."""
    if capabilities.get("schema_version") != 1:
        raise RoutingError("dispatcher capabilities schema_version must be 1")
    if (
        not isinstance(capabilities.get("probed_at"), str)
        or not capabilities["probed_at"].strip()
    ):
        raise RoutingError(
            "dispatcher capabilities probed_at must be a non-empty string"
        )

    normalized: dict[str, Any] = {
        "schema_version": 1,
        "probed_at": capabilities["probed_at"],
        "supports_custom_agent_type": _require_boolean(
            capabilities, "supports_custom_agent_type", "dispatcher capabilities"
        ),
        "supports_model_selection": _require_boolean(
            capabilities, "supports_model_selection", "dispatcher capabilities"
        ),
        "supports_reasoning_effort": _require_boolean(
            capabilities, "supports_reasoning_effort", "dispatcher capabilities"
        ),
        "supports_sandbox_override": _require_boolean(
            capabilities, "supports_sandbox_override", "dispatcher capabilities"
        ),
        "supported_models": _supported_models(capabilities, "dispatcher capabilities"),
    }

    external = capabilities.get("external_dispatch")
    if external is None:
        normalized["external_dispatch"] = {"available": False}
        return normalized
    if not isinstance(external, dict):
        raise RoutingError(
            "dispatcher capabilities.external_dispatch must be an object"
        )
    available = _require_boolean(
        external, "available", "dispatcher capabilities.external_dispatch"
    )
    normalized_external: dict[str, Any] = {"available": available}
    if available:
        mode = external.get("mode")
        if mode not in {"codex_cli", "mcp"}:
            raise RoutingError(
                "dispatcher capabilities.external_dispatch.mode must be 'codex_cli' or 'mcp'"
            )
        command = external.get("command")
        if (
            not isinstance(command, list)
            or not command
            or any(not isinstance(part, str) or not part for part in command)
        ):
            raise RoutingError(
                "dispatcher capabilities.external_dispatch.command must be a non-empty string array"
            )
        normalized_external.update(
            {
                "mode": mode,
                "command": list(command),
                "supports_model_selection": _require_boolean(
                    external,
                    "supports_model_selection",
                    "dispatcher capabilities.external_dispatch",
                ),
                "supports_reasoning_effort": _require_boolean(
                    external,
                    "supports_reasoning_effort",
                    "dispatcher capabilities.external_dispatch",
                ),
                "supports_sandbox_override": _require_boolean(
                    external,
                    "supports_sandbox_override",
                    "dispatcher capabilities.external_dispatch",
                ),
                "supported_models": _supported_models(
                    external, "dispatcher capabilities.external_dispatch"
                ),
            }
        )
    normalized["external_dispatch"] = normalized_external
    return normalized


def load_profiles(agents_dir: Path) -> dict[str, tuple[Path, dict[str, Any]]]:
    if not agents_dir.is_dir():
        raise RoutingError(
            f"Codex agents directory does not exist: {agents_dir}; run install_agent_profiles.py first"
        )
    profiles: dict[str, tuple[Path, dict[str, Any]]] = {}
    for path in sorted(agents_dir.glob("*.toml")):
        try:
            with path.open("rb") as handle:
                profile = tomllib.load(handle)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise RoutingError(f"invalid agent TOML {path}: {exc}") from exc
        name = profile.get("name")
        if not isinstance(name, str) or not name:
            continue
        if name in profiles:
            raise RoutingError(
                f"duplicate Codex agent profile name {name!r}: {profiles[name][0]} and {path}"
            )
        profiles[name] = (path.resolve(), profile)
    return profiles


def validate_selected_profile(
    *,
    agent: str,
    role: str,
    complexity: int,
    risk: int,
    profiles: Mapping[str, tuple[Path, dict[str, Any]]],
) -> tuple[Path, dict[str, Any]]:
    if agent in BUILT_IN_AGENTS:
        raise RoutingError(
            f"routing selected forbidden built-in agent profile {agent!r}"
        )
    if agent not in profiles:
        raise RoutingError(f"routing selected missing custom agent profile {agent!r}")
    path, profile = profiles[agent]
    missing = sorted(REQUIRED_PROFILE_FIELDS - profile.keys())
    if missing:
        raise RoutingError(
            f"agent profile {agent!r} omits required fields: {', '.join(missing)}"
        )
    if profile["name"] != agent:
        raise RoutingError(
            f"agent profile {path} declares name {profile['name']!r}, expected {agent!r}"
        )
    if (
        not isinstance(profile["description"], str)
        or not profile["description"].strip()
    ):
        raise RoutingError(f"agent profile {agent!r} has no description")
    if (
        not isinstance(profile["developer_instructions"], str)
        or not profile["developer_instructions"].strip()
    ):
        raise RoutingError(f"agent profile {agent!r} has no developer_instructions")
    if not isinstance(profile["model"], str) or not profile["model"].strip():
        raise RoutingError(f"agent profile {agent!r} has no explicit model")
    if profile["model_reasoning_effort"] not in {"medium", "high", "xhigh"}:
        raise RoutingError(
            f"agent profile {agent!r} has unsupported model_reasoning_effort"
        )

    expected_config = next(
        (
            config
            for suffix, config in EXPECTED_PROFILE_CONFIG.items()
            if agent.endswith(suffix)
        ),
        None,
    )
    if expected_config is None:
        raise RoutingError(
            f"agent profile {agent!r} has no recognized pinned configuration"
        )
    expected_model, expected_effort = expected_config
    if (
        profile["model"] != expected_model
        or profile["model_reasoning_effort"] != expected_effort
    ):
        raise RoutingError(
            f"agent profile {agent!r} must pin model={expected_model!r} and "
            f"model_reasoning_effort={expected_effort!r}"
        )

    sandbox = profile["sandbox_mode"]
    if role in READ_ONLY_ROLES and sandbox != "read-only":
        raise RoutingError(
            f"read-only role {role!r} selected writable profile {agent!r}"
        )
    if role in WRITABLE_ROLES and sandbox != "workspace-write":
        raise RoutingError(
            f"writable role {role!r} selected incompatible profile {agent!r}"
        )

    uses_luna = profile["model"] == "gpt-5.6-luna"
    luna_allowed = role == "mechanical_read_only" and complexity <= 2 and risk <= 2
    if uses_luna != luna_allowed:
        state = "outside" if uses_luna else "inside"
        raise RoutingError(
            f"agent profile {agent!r} uses Luna {state} the bounded mechanical route"
        )
    return path, profile


def validate_prompt_projection(prompt_path: Path, profile: Mapping[str, Any]) -> Path:
    if not prompt_path.is_file():
        raise RoutingError(f"canonical role prompt does not exist: {prompt_path}")
    try:
        text = prompt_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RoutingError(
            f"could not read canonical role prompt {prompt_path}: {exc}"
        ) from exc
    parts = text.split("---", 2)
    if len(parts) != 3 or parts[0].strip():
        raise RoutingError(
            f"canonical role prompt has invalid frontmatter: {prompt_path}"
        )
    body = parts[2].strip()
    if not body:
        raise RoutingError(f"canonical role prompt body is empty: {prompt_path}")
    if profile.get("developer_instructions", "").strip() != body:
        raise RoutingError(
            f"external profile projection does not match canonical role prompt: {prompt_path}"
        )
    return prompt_path.resolve()


def _external_exact_supported(external: Mapping[str, Any], model: str) -> bool:
    return bool(
        external.get("available")
        and external.get("supports_model_selection")
        and external.get("supports_reasoning_effort")
        and external.get("supports_sandbox_override")
        and model in external.get("supported_models", [])
    )


def build_dispatch_specification(
    *,
    requirement: Mapping[str, Any],
    capabilities: Mapping[str, Any],
    model: str,
    reasoning_effort: str,
    sandbox_mode: str,
    prompt_file: Path,
    profile_name: str,
    profile_file: Path,
) -> dict[str, Any]:
    native_model_supported = bool(
        capabilities["supports_model_selection"]
        and model in capabilities["supported_models"]
    )
    native_effort_supported = bool(capabilities["supports_reasoning_effort"])
    native_sandbox_supported = bool(capabilities["supports_sandbox_override"])
    native_exact_supported = bool(
        native_model_supported and native_effort_supported and native_sandbox_supported
    )
    external = capabilities["external_dispatch"]
    external_exact_supported = _external_exact_supported(external, model)

    minimum = requirement["minimum_enforcement"]
    allow_uncontrolled_effort = requirement["allow_uncontrolled_effort"]
    allow_uncontrolled_sandbox = requirement["allow_uncontrolled_sandbox"]
    if minimum == "exact":
        if native_exact_supported:
            mode = "native_exact"
        elif external_exact_supported:
            mode = "external_exact"
        else:
            mode = "unavailable"
    elif (
        native_model_supported
        and (native_effort_supported or allow_uncontrolled_effort)
        and (native_sandbox_supported or allow_uncontrolled_sandbox)
    ):
        mode = "native_exact" if native_exact_supported else "native_model_prompt"
    elif external_exact_supported:
        mode = "external_exact"
    else:
        mode = "unavailable"

    required = {
        "model": model,
        "reasoning_effort": reasoning_effort,
        "sandbox_mode": sandbox_mode,
        "prompt_file": str(prompt_file),
    }
    native_dispatch = {
        "supported": native_model_supported,
        "model": model,
        "reasoning_effort_supported": native_effort_supported,
        "sandbox_override_supported": native_sandbox_supported,
        "custom_profile_supported": capabilities["supports_custom_agent_type"],
    }
    external_dispatch: dict[str, Any] = {
        "supported": external_exact_supported,
        "profile": profile_name,
        "profile_file": str(profile_file),
    }
    if external.get("available"):
        external_dispatch.update(
            {
                "mode": external["mode"],
                "command": external["command"],
            }
        )

    uncontrolled_fields: list[str] = []
    if not native_model_supported:
        uncontrolled_fields.append("model")
    if not native_effort_supported:
        uncontrolled_fields.append("reasoning_effort")
    if not native_sandbox_supported:
        uncontrolled_fields.append("sandbox_mode")

    if mode == "native_exact":
        dispatch: dict[str, Any] = {
            "mode": mode,
            "routing_enforcement": "exact",
            **required,
            "controlled_fields": [
                "model",
                "reasoning_effort",
                "sandbox_mode",
                "prompt_file",
            ],
            "uncontrolled_fields": [],
        }
    elif mode == "native_model_prompt":
        controlled_fields = ["model", "prompt_file"]
        dispatch = {
            "mode": mode,
            "routing_enforcement": "model-and-prompt",
            "model": model,
            "prompt_file": str(prompt_file),
            "requested_effort": reasoning_effort,
            "effective_effort": reasoning_effort
            if native_effort_supported
            else "uncontrolled",
            "requested_sandbox": sandbox_mode,
            "effective_sandbox": sandbox_mode
            if native_sandbox_supported
            else "uncontrolled",
            "controlled_fields": controlled_fields,
            "uncontrolled_fields": [
                field
                for field in ("reasoning_effort", "sandbox_mode")
                if field in uncontrolled_fields
            ],
        }
        degradation: list[str] = []
        if native_effort_supported:
            dispatch["reasoning_effort"] = reasoning_effort
            controlled_fields.append("reasoning_effort")
        else:
            degradation.append("dispatcher does not expose per-subagent effort")
        if native_sandbox_supported:
            dispatch["sandbox_mode"] = sandbox_mode
            controlled_fields.append("sandbox_mode")
        else:
            degradation.append(
                "dispatcher does not expose per-subagent sandbox override"
            )
        dispatch["degradation"] = "; ".join(degradation)
    elif mode == "external_exact":
        dispatch = {
            "mode": mode,
            "routing_enforcement": "exact",
            **required,
            "launcher": {
                "mode": external["mode"],
                "command": external["command"],
            },
            "controlled_fields": [
                "model",
                "reasoning_effort",
                "sandbox_mode",
                "prompt_file",
            ],
            "uncontrolled_fields": [],
        }
    else:
        dispatch = {
            "mode": "unavailable",
            "routing_enforcement": "none",
            "required": required,
            "controlled_fields": [],
            "uncontrolled_fields": uncontrolled_fields,
            "reason": "neither the native dispatcher nor the configured external launcher satisfies the role policy",
        }

    return {
        "required": required,
        "native_dispatch": native_dispatch,
        "external_dispatch": external_dispatch,
        "recommended_mode": mode,
        "dispatch": dispatch,
        "profile_projection": {
            "name": profile_name,
            "file": str(profile_file),
        },
    }


def resolve_route(
    policy: Mapping[str, Any],
    profiles: Mapping[str, tuple[Path, dict[str, Any]]],
    capabilities: Mapping[str, Any],
    *,
    complexity: int,
    risk: int,
    role: str,
    task_id: str | None = None,
) -> dict[str, Any]:
    validate_policy(policy)
    complexity = validate_score("complexity", complexity)
    risk = validate_score("risk", risk)

    regular_roles = policy["profiles_by_role_and_tier"]
    special = policy["special_routes"]["mechanical_read_only"]
    supported_roles = set(regular_roles) | {"mechanical_read_only"}
    if role not in supported_roles:
        raise RoutingError(
            f"unknown role {role!r}; expected one of {sorted(supported_roles)}"
        )

    tier = policy["base_tier_by_score"][str(complexity)][str(risk)]
    effective_role = role
    if (
        role == "mechanical_read_only"
        and complexity <= special["maximum_complexity"]
        and risk <= special["maximum_risk"]
    ):
        agent = special["agent"]
        tier = "luna_medium"
    else:
        if role == "mechanical_read_only":
            effective_role = special["fallback_role"]
        try:
            agent = regular_roles[effective_role][tier]
        except KeyError as exc:
            raise RoutingError(f"no route for role={role!r}, tier={tier!r}") from exc

    profile_path, profile = validate_selected_profile(
        agent=agent,
        role=role,
        complexity=complexity,
        risk=risk,
        profiles=profiles,
    )
    prompt_role = (
        "mechanical_read_only" if agent == special["agent"] else effective_role
    )
    prompt_path = validate_prompt_projection(
        skill_root() / "agents" / ROLE_PROMPT_FILES[prompt_role],
        profile,
    )
    execution = build_dispatch_specification(
        # Keyed on effective_role: a mechanical_read_only task above the Luna bound
        # runs on the explorer profile and must obey the explorer's dispatch policy.
        requirement=policy["dispatch_policy"][effective_role],
        capabilities=capabilities,
        model=profile["model"],
        reasoning_effort=profile["model_reasoning_effort"],
        sandbox_mode=profile["sandbox_mode"],
        prompt_file=prompt_path,
        profile_name=agent,
        profile_file=profile_path,
    )
    result = {
        "policy_version": policy["policy_version"],
        "complexity": complexity,
        "risk": risk,
        "combined": complexity + risk,
        "role": role,
        "effective_role": effective_role,
        "tier": tier,
        **execution,
    }
    if task_id is not None:
        result["task_id"] = task_id
    return result


def scores_from_manifest(
    manifest_path: Path, policy: Mapping[str, Any]
) -> tuple[int, int, str | None]:
    manifest = load_json(manifest_path, "task routing manifest")
    if manifest.get("schema_version") != 1:
        raise RoutingError("task routing manifest schema_version must be 1")
    complexity = validate_score("complexity", manifest.get("complexity"))
    risk = validate_score("risk", manifest.get("risk"))
    if manifest.get("combined") != complexity + risk:
        raise RoutingError(
            "task routing manifest combined does not equal complexity + risk"
        )
    if manifest.get("policy_version") != policy["policy_version"]:
        raise RoutingError(
            "task routing manifest policy_version does not match the routing policy"
        )
    task_id = manifest.get("task_id")
    if task_id is not None and (not isinstance(task_id, str) or not task_id.strip()):
        raise RoutingError("task routing manifest task_id must be a non-empty string")
    return complexity, risk, task_id


def scores_from_task_json(task_path: Path) -> tuple[int, int, str]:
    task = load_json(task_path, "task JSON")
    task_id = task.get("task_id")
    if not isinstance(task_id, str) or not task_id.strip():
        raise RoutingError("task JSON task_id must be a non-empty string")
    complexity = validate_score("complexity", task.get("complexity"))
    risk = validate_score("risk", task.get("risk"))
    return complexity, risk, task_id


def evidence_lock(
    path: Path,
    timeout_seconds: float = 30.0,
    stale_after_seconds: float = LOCK_STALE_AFTER_SECONDS,
):
    """AutViam_C's lock — pins the `.routing-lock` suffix and message text that
    references/recovery.md quotes."""
    return directory_lock(
        path,
        timeout_seconds=timeout_seconds,
        stale_after_seconds=stale_after_seconds,
        suffix="routing-lock",
        label="routing evidence lock",
    )


def write_routing_evidence(path: Path, purpose: str, result: Mapping[str, Any]) -> None:
    if not purpose.strip():
        raise RoutingError("routing evidence purpose must be non-empty")
    path.parent.mkdir(parents=True, exist_ok=True)
    with evidence_lock(path):
        if path.exists():
            document = load_json(path, "routing evidence target")
        else:
            document = {"schema_version": 1, "routing_evidence": []}

        for score_name in ("complexity", "risk"):
            stored_score = document.get(score_name)
            if stored_score is not None and stored_score != result[score_name]:
                raise RoutingError(
                    f"routing result {score_name}={result[score_name]} does not match "
                    f"evidence target {score_name}={stored_score}; route from the stored task JSON"
                )
        stored_task_id = document.get("task_id")
        result_task_id = result.get("task_id")
        if stored_task_id is not None:
            if result_task_id is None:
                raise RoutingError(
                    "routing evidence target is a task JSON; use --task-json so stored scores "
                    "and task_id cannot be bypassed"
                )
            if stored_task_id != result_task_id:
                raise RoutingError(
                    f"routing result task_id={result_task_id!r} does not match "
                    f"evidence target task_id={stored_task_id!r}"
                )

        evidence = document.setdefault("routing_evidence", [])
        if not isinstance(evidence, list):
            raise RoutingError(f"routing_evidence must be an array in {path}")
        evidence.append(
            {
                "dispatched_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "purpose": purpose,
                "resolver": dict(result),
            }
        )
        atomic_write_json(path, document)


def validate_purpose_role(purpose: str, role: str) -> None:
    allowed_roles = PURPOSE_ROLES.get(purpose)
    if allowed_roles is None:
        raise RoutingError(
            f"unknown routing evidence purpose {purpose!r}; expected one of {sorted(PURPOSE_ROLES)}"
        )
    if role not in allowed_roles:
        raise RoutingError(
            f"routing evidence purpose {purpose!r} requires role in {sorted(allowed_roles)}, "
            f"not {role!r}"
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, default=default_policy_path())
    parser.add_argument("--agents-dir", type=Path, default=default_agents_dir())
    parser.add_argument(
        "--dispatcher-capabilities",
        type=Path,
        default=default_capabilities_path(),
        help="Runtime-derived subagent dispatcher capability record.",
    )
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--manifest", type=Path)
    inputs.add_argument("--task-json", type=Path)
    inputs.add_argument("--complexity", type=int)
    parser.add_argument("--risk", type=int)
    parser.add_argument("--role", required=True)
    parser.add_argument("--evidence-file", type=Path)
    parser.add_argument("--purpose")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    policy = load_json(args.policy.resolve(), "routing policy")
    validate_policy(policy)
    capabilities = validate_dispatcher_capabilities(
        load_json(args.dispatcher_capabilities.resolve(), "dispatcher capabilities")
    )
    if args.manifest:
        if args.risk is not None:
            raise RoutingError("--risk cannot be combined with --manifest")
        complexity, risk, task_id = scores_from_manifest(
            args.manifest.resolve(), policy
        )
    elif args.task_json:
        if args.risk is not None:
            raise RoutingError("--risk cannot be combined with --task-json")
        complexity, risk, task_id = scores_from_task_json(args.task_json.resolve())
    else:
        if args.risk is None:
            raise RoutingError("--risk is required with --complexity")
        complexity, risk, task_id = args.complexity, args.risk, None
    profiles = load_profiles(args.agents_dir.resolve())
    result = resolve_route(
        policy,
        profiles,
        capabilities,
        complexity=complexity,
        risk=risk,
        role=args.role,
        task_id=task_id,
    )
    if bool(args.evidence_file) != bool(args.purpose):
        raise RoutingError("--evidence-file and --purpose must be supplied together")
    if args.task_json:
        if not args.evidence_file:
            raise RoutingError(
                "--task-json requires --evidence-file and --purpose for auditable dispatch"
            )
        if args.evidence_file.resolve() != args.task_json.resolve():
            raise RoutingError(
                "--task-json and --evidence-file must name the same task JSON"
            )
    if args.evidence_file:
        validate_purpose_role(args.purpose, args.role)
        write_routing_evidence(args.evidence_file.resolve(), args.purpose, result)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RoutingError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
