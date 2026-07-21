#!/usr/bin/env python3
"""Exhaustively validate the AutViam_C Path-2 routing policy and profiles."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

from resolve_codex_agent import (
    BUILT_IN_AGENTS,
    EXPECTED_PROFILE_CONFIG,
    RoutingError,
    default_agents_dir,
    default_policy_path,
    load_json,
    load_profiles,
    resolve_route,
    skill_root,
    validate_policy,
)
from install_agent_profiles import (
    InstallError,
    PINNED_MODELS,
    PROFILE_SPECS,
    load_sources,
    render_profile,
    validate_rendered,
)


EXPECTED_TIER_BY_SCORE = {
    (complexity, risk): (
        "sol_xhigh"
        if complexity == 5 or risk == 5 or complexity + risk >= 9
        else "sol_high"
        if complexity >= 4 or risk >= 4 or complexity + risk >= 7
        else "terra_high"
        if complexity >= 3 or risk >= 3
        else "terra_medium"
    )
    for complexity in range(1, 6)
    for risk in range(1, 6)
}
ROLES = ("implementer", "orchestrator", "reviewer", "explorer", "mechanical_read_only")


class ValidationError(RuntimeError):
    """Raised when the routing configuration is inconsistent or incomplete."""


def _schema_type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    raise ValidationError(f"unsupported JSON Schema type {expected!r}")


def validate_against_schema(
    value: Any,
    schema: Mapping[str, Any],
    root_schema: Mapping[str, Any],
    location: str = "$",
) -> None:
    """Validate the JSON Schema subset used by the bundled routing policy."""
    if "$ref" in schema:
        reference = schema["$ref"]
        if not isinstance(reference, str) or not reference.startswith("#/"):
            raise ValidationError(f"{location}: unsupported schema reference {reference!r}")
        target: Any = root_schema
        for component in reference[2:].split("/"):
            try:
                target = target[component.replace("~1", "/").replace("~0", "~")]
            except (KeyError, TypeError) as exc:
                raise ValidationError(f"{location}: unresolved schema reference {reference!r}") from exc
        validate_against_schema(value, target, root_schema, location)
        return

    expected_type = schema.get("type")
    if expected_type is not None and not _schema_type_matches(value, expected_type):
        raise ValidationError(f"{location}: expected JSON type {expected_type}, found {type(value).__name__}")
    if "const" in schema and value != schema["const"]:
        raise ValidationError(f"{location}: expected constant {schema['const']!r}, found {value!r}")
    if "enum" in schema and value not in schema["enum"]:
        raise ValidationError(f"{location}: value {value!r} is not in {schema['enum']!r}")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            raise ValidationError(f"{location}: string is shorter than minLength")
        pattern = schema.get("pattern")
        if pattern is not None and re.search(pattern, value) is None:
            raise ValidationError(f"{location}: string does not match pattern {pattern!r}")
    if isinstance(value, int) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            raise ValidationError(f"{location}: value is below minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            raise ValidationError(f"{location}: value is above maximum {schema['maximum']}")
    if isinstance(value, dict):
        required = schema.get("required", [])
        missing = sorted(set(required) - value.keys())
        if missing:
            raise ValidationError(f"{location}: missing required properties {missing}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            unexpected = sorted(set(value) - properties.keys())
            if unexpected:
                raise ValidationError(f"{location}: unexpected properties {unexpected}")
        for key, child in value.items():
            if key in properties:
                validate_against_schema(child, properties[key], root_schema, f"{location}.{key}")


def referenced_agents(policy: Mapping[str, Any]) -> set[str]:
    agents = {
        agent
        for role_routes in policy["profiles_by_role_and_tier"].values()
        for agent in role_routes.values()
    }
    agents.add(policy["special_routes"]["mechanical_read_only"]["agent"])
    return agents


def expected_config_for_agent(agent: str) -> tuple[str, str]:
    for tier in ("terra_medium", "terra_high", "sol_high", "sol_xhigh", "luna_medium"):
        if agent.endswith(tier):
            return EXPECTED_PROFILE_CONFIG[tier]
    raise ValidationError(f"cannot infer the configured tier from agent profile name {agent!r}")


def validate_profiles(policy: Mapping[str, Any], profiles: Mapping[str, tuple[Path, dict[str, Any]]]) -> int:
    agents = referenced_agents(policy)
    if agents & BUILT_IN_AGENTS:
        raise ValidationError(f"policy selects built-in profiles: {sorted(agents & BUILT_IN_AGENTS)}")
    missing = sorted(agents - profiles.keys())
    if missing:
        raise ValidationError(f"policy-selected agent profiles are missing: {missing}")

    source_root = skill_root()
    sources = load_sources(source_root)
    specs_by_name = {spec.name: spec for spec in PROFILE_SPECS}
    expected_profiles = {
        spec.name: render_profile(spec, PINNED_MODELS, sources, source_root)
        for spec in PROFILE_SPECS
    }

    for agent in sorted(agents):
        path, profile = profiles[agent]
        spec = specs_by_name.get(agent)
        if spec is None:
            raise ValidationError(f"policy selected profile with no bundled managed specification: {agent!r}")
        actual_text = path.read_text(encoding="utf-8")
        validate_rendered(spec, actual_text, PINNED_MODELS)
        if actual_text != expected_profiles[agent]:
            raise ValidationError(
                f"{path}: managed profile content differs from its bundled source rendering"
            )
        expected_model, expected_effort = expected_config_for_agent(agent)
        if profile.get("name") != agent:
            raise ValidationError(f"{path}: profile name does not match route {agent!r}")
        if profile.get("model") != expected_model:
            raise ValidationError(f"{path}: expected model {expected_model!r}, found {profile.get('model')!r}")
        if profile.get("model_reasoning_effort") != expected_effort:
            raise ValidationError(
                f"{path}: expected model_reasoning_effort {expected_effort!r}, "
                f"found {profile.get('model_reasoning_effort')!r}"
            )
        writable = agent.startswith("worker_") or agent.startswith("orchestrator_")
        expected_sandbox = "workspace-write" if writable else "read-only"
        if profile.get("sandbox_mode") != expected_sandbox:
            raise ValidationError(
                f"{path}: expected sandbox_mode {expected_sandbox!r}, found {profile.get('sandbox_mode')!r}"
            )
    return len(agents)


def validate_matrix(policy: Mapping[str, Any]) -> None:
    matrix = policy["base_tier_by_score"]
    for (complexity, risk), expected in EXPECTED_TIER_BY_SCORE.items():
        actual = matrix[str(complexity)][str(risk)]
        if actual != expected:
            raise ValidationError(
                f"score matrix mismatch for complexity={complexity}, risk={risk}: "
                f"expected {expected!r}, found {actual!r}"
            )


def validate_routes(policy: Mapping[str, Any], profiles: Mapping[str, tuple[Path, dict[str, Any]]]) -> int:
    routes_checked = 0
    for complexity in range(1, 6):
        for risk in range(1, 6):
            for role in ROLES:
                result = resolve_route(
                    policy,
                    profiles,
                    complexity=complexity,
                    risk=risk,
                    role=role,
                )
                routes_checked += 1
                if role == "mechanical_read_only":
                    should_use_luna = complexity <= 2 and risk <= 2
                    uses_luna = result["model"] == "gpt-5.6-luna"
                    if uses_luna != should_use_luna:
                        raise ValidationError("mechanical_read_only Luna boundary is not enforced")
                if role == "reviewer":
                    tier = EXPECTED_TIER_BY_SCORE[(complexity, risk)]
                    if tier == "terra_medium" and result["agent"] != "reviewer_terra_high":
                        raise ValidationError("reviewer floor is missing for a routine task")
                    if tier in {"terra_high", "sol_high"} and result["agent"] != "reviewer_sol_high":
                        raise ValidationError("reviewer floor is missing for a moderate or elevated task")
                    if result["model"] == "gpt-5.6-luna":
                        raise ValidationError("reviewer route selected Luna")
    return routes_checked


def validate_configuration(policy_path: Path, agents_dir: Path) -> dict[str, Any]:
    policy = load_json(policy_path, "routing policy")
    validate_policy(policy)
    schema_path = policy_path.parent / "codex-agent-routing.schema.json"
    schema = load_json(schema_path, "routing policy schema")
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        raise ValidationError("routing schema must declare JSON Schema draft 2020-12")
    validate_against_schema(policy, schema, schema)
    profiles = load_profiles(agents_dir)
    validate_matrix(policy)
    profiles_checked = validate_profiles(policy, profiles)
    routes_checked = validate_routes(policy, profiles)
    return {
        "valid": True,
        "policy_version": policy["policy_version"],
        "policy": str(policy_path),
        "agents_dir": str(agents_dir),
        "routes_checked": routes_checked,
        "profiles_checked": profiles_checked,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, default=default_policy_path())
    parser.add_argument("--agents-dir", type=Path, default=default_agents_dir())
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = validate_configuration(args.policy.resolve(), args.agents_dir.resolve())
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(
            "AutViam_C Codex agent routing: VALID\n"
            f"  policy version  : {report['policy_version']}\n"
            f"  routes checked  : {report['routes_checked']}\n"
            f"  profiles checked: {report['profiles_checked']}"
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (InstallError, RoutingError, ValidationError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
