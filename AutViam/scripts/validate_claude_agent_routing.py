#!/usr/bin/env python3
"""Exhaustively validate AutViam Claude routing, profiles, config, and commands."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

from claude_routing_common import RoutingCommonError, load_json, normalize_config
from install_claude_agent_profiles import (
    InstallError,
    PROFILE_SPECS,
    generated_profiles,
    validate_installed,
)
from resolve_claude_agent import (
    ResolveError,
    expected_model_effort,
    load_profiles,
    resolve_agent,
    skill_root,
    validate_policy,
)


class ValidationError(RuntimeError):
    pass


EXPECTED_TIER = {
    (complexity, risk): (
        "opus_xhigh"
        if complexity == 5 or risk == 5 or complexity + risk >= 9
        else "opus_high"
        if complexity >= 4 or risk >= 4 or complexity + risk >= 7
        else "sonnet_high"
        if complexity >= 3 or risk >= 3
        else "sonnet_medium"
    )
    for complexity in range(1, 6)
    for risk in range(1, 6)
}


def validate_schema(policy: Mapping[str, Any], schema: Mapping[str, Any]) -> None:
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        raise ValidationError("routing schema must declare JSON Schema draft 2020-12")
    required = schema.get("required", [])
    missing = sorted(set(required) - policy.keys())
    if missing:
        raise ValidationError(f"routing policy misses schema-required keys: {missing}")
    allowed = set(schema.get("properties", {}))
    unexpected = sorted(set(policy) - allowed)
    if schema.get("additionalProperties") is False and unexpected:
        raise ValidationError(f"routing policy has schema-forbidden keys: {unexpected}")
    for key, property_schema in schema.get("properties", {}).items():
        if key not in policy:
            continue
        value = policy[key]
        if "const" in property_schema and value != property_schema["const"]:
            raise ValidationError(f"routing policy {key} must equal {property_schema['const']!r}")
        expected_type = property_schema.get("type")
        if expected_type == "object" and not isinstance(value, dict):
            raise ValidationError(f"routing policy {key} must be an object")
        if expected_type == "string" and not isinstance(value, str):
            raise ValidationError(f"routing policy {key} must be a string")
        if expected_type == "integer" and (isinstance(value, bool) or not isinstance(value, int)):
            raise ValidationError(f"routing policy {key} must be an integer")


def validate_matrix(policy: Mapping[str, Any]) -> None:
    for pair, expected in EXPECTED_TIER.items():
        actual = policy["base_tier_by_score"][str(pair[0])][str(pair[1])]
        if actual != expected:
            raise ValidationError(f"score matrix mismatch at {pair}: expected {expected}, found {actual}")


def validate_profile_contracts(policy: Mapping[str, Any], agents_dir: Path, generated: Mapping[str, str]) -> None:
    validate_installed(agents_dir, generated)
    by_name = {spec.name: spec for spec in PROFILE_SPECS}
    if len(by_name) != 22:
        raise ValidationError("generated profile specification must contain 22 unique names")
    for spec in PROFILE_SPECS:
        model, effort = expected_model_effort(spec.name)
        if model != spec.model or effort != spec.effort:
            raise ValidationError(f"{spec.name}: model/effort suffix drift")
        supported = policy["models"][spec.model]["supported_efforts"]
        if spec.effort is not None and spec.effort not in supported:
            raise ValidationError(f"{spec.name}: effort {spec.effort} is unsupported by {spec.model}")
        if spec.effort is None and spec.model != "haiku":
            raise ValidationError(f"{spec.name}: non-Haiku profile must pin effort")
        if spec.capability in {"leaf", "flat"} and "Agent(" in spec.tools:
            raise ValidationError(f"{spec.name}: leaf/flat profile exposes Agent")
        if spec.role == "domain_reviewer" and spec.capability == "nested":
            if "Agent(autviam-explorer-" not in spec.tools:
                raise ValidationError(f"{spec.name}: nested Gate B lacks explorer allowlist")
            if "autviam-implementer" in spec.tools:
                raise ValidationError(f"{spec.name}: nested Gate B can spawn implementers")
        if spec.role == "orchestrator" and "Agent(" not in spec.tools:
            raise ValidationError(f"{spec.name}: orchestrator lacks restricted child allowlist")


def validate_routes(policy: Mapping[str, Any], agents_dir: Path) -> int:
    profiles = load_profiles(agents_dir)
    checked = 0
    for complexity in range(1, 6):
        for risk in range(1, 6):
            base = EXPECTED_TIER[(complexity, risk)]
            cases = (
                ("implementer", "leaf"),
                ("orchestrator", "nested"),
                ("spec_reviewer", "leaf"),
                ("domain_reviewer", "flat"),
                ("domain_reviewer", "nested"),
                ("explorer", "leaf"),
                ("mechanical_read_only", "leaf"),
            )
            for role, capability in cases:
                agent, tier, _, metadata = resolve_agent(
                    policy,
                    profiles,
                    complexity=complexity,
                    risk=risk,
                    role=role,
                    capability=capability,
                )
                checked += 1
                if role in {"spec_reviewer", "domain_reviewer"}:
                    expected_agent_tier = (
                        "sonnet-high" if base == "sonnet_medium" else "opus-high" if base in {"sonnet_high", "opus_high"} else "opus-xhigh"
                    )
                    if expected_agent_tier not in agent:
                        raise ValidationError(f"reviewer floor mismatch for {complexity}/{risk}: {agent}")
                if metadata["model"] == "haiku":
                    if role != "mechanical_read_only" or complexity > 2 or risk > 2:
                        raise ValidationError("Haiku escaped the bounded mechanical route")
                if role == "domain_reviewer" and not agent.endswith(f"-{capability}"):
                    raise ValidationError("Gate B capability suffix mismatch")
                if tier != "haiku" and role not in {"spec_reviewer", "domain_reviewer"} and tier != base:
                    raise ValidationError("base routing tier drift")
    return checked


def scan_agent_names(directory: Path) -> dict[str, list[Path]]:
    names: dict[str, list[Path]] = {}
    if not directory.is_dir():
        return names
    for path in directory.rglob("*.md"):
        try:
            from claude_routing_common import parse_frontmatter

            metadata, _ = parse_frontmatter(path)
        except RoutingCommonError:
            continue
        if metadata.get("name"):
            names.setdefault(metadata["name"], []).append(path.resolve())
    return names


def validate_no_duplicate_names(agent_dirs: list[Path]) -> None:
    combined: dict[str, list[Path]] = {}
    for directory in agent_dirs:
        for name, paths in scan_agent_names(directory).items():
            combined.setdefault(name, []).extend(paths)
    duplicates = {name: paths for name, paths in combined.items() if len(set(paths)) > 1}
    if duplicates:
        details = "; ".join(f"{name}: {[str(path) for path in paths]}" for name, paths in duplicates.items())
        raise ValidationError(f"duplicate Claude agent names: {details}")


def validate_no_legacy_profiles(agent_dirs: list[Path]) -> None:
    legacy = {
        "autviam-spec-reviewer",
        "autviam-domain-reviewer",
        "autviam-phase-orchestrator",
    }
    found: list[str] = []
    for directory in agent_dirs:
        for name, paths in scan_agent_names(directory).items():
            if name in legacy:
                found.extend(str(path) for path in paths)
    if found:
        raise ValidationError("active legacy AutViam agent profiles remain: " + ", ".join(sorted(found)))


def validate_commands(root: Path) -> None:
    active = [root / "SKILL.md", *(root / "commands").glob("*.md"), root / "templates" / "task_instructions_template.md"]
    legacy_patterns = (
        r'subagent_type\s*=\s*["\']autviam-spec-reviewer["\']',
        r'subagent_type\s*=\s*["\']autviam-domain-reviewer["\']',
        r'subagent_type\s*=\s*["\']autviam-phase-orchestrator["\']',
    )
    required_commands = ("ScaffoldPhase.md", "ExecPhase.md", "ExecTask.md", "Phase.md", "E2E.md")
    for path in active:
        text = path.read_text(encoding="utf-8")
        for pattern in legacy_patterns:
            if re.search(pattern, text):
                raise ValidationError(f"{path}: active legacy direct agent invocation")
        if re.search(r"Agent\([^)]*\bmodel\s*=", text, re.DOTALL):
            raise ValidationError(f"{path}: per-invocation Agent model override is forbidden")
    for filename in required_commands:
        text = (root / "commands" / filename).read_text(encoding="utf-8")
        if "resolve_claude_agent.py" not in text:
            raise ValidationError(f"{filename}: does not reference the Claude resolver")


def validate_configuration(policy_path: Path, agents_dir: Path, config_path: Path | None, additional_dirs: list[Path]) -> dict[str, Any]:
    policy = load_json(policy_path, "routing policy")
    validate_policy(policy)
    schema = load_json(policy_path.with_name("claude-agent-routing-schema.json"), "routing schema")
    validate_schema(policy, schema)
    config = normalize_config(load_json(config_path, "AutViam config") if config_path and config_path.exists() else {})
    validate_matrix(policy)
    generated = generated_profiles(skill_root())
    validate_profile_contracts(policy, agents_dir, generated)
    validate_no_duplicate_names([agents_dir, *additional_dirs])
    validate_no_legacy_profiles([agents_dir, *additional_dirs])
    routes = validate_routes(policy, agents_dir)
    validate_commands(skill_root())
    return {
        "valid": True,
        "policy_version": policy["policy_version"],
        "profiles_checked": len(PROFILE_SPECS),
        "routes_checked": routes,
        "nested_dispatch": config["nested_dispatch"],
        "runtime_dispatch_verified": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, default=skill_root() / "references" / "claude-agent-routing.json")
    parser.add_argument("--agents-dir", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--additional-agents-dir", type=Path, action="append", default=[])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = validate_configuration(
        args.policy.resolve(),
        args.agents_dir.resolve(),
        args.config.resolve() if args.config else None,
        [path.resolve() for path in args.additional_agents_dir],
    )
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"AutViam Claude routing: VALID ({report['profiles_checked']} profiles, {report['routes_checked']} routes)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (InstallError, ResolveError, RoutingCommonError, ValidationError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
