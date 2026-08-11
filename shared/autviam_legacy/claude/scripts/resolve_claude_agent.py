#!/usr/bin/env python3
"""Resolve one AutViam Claude agent and issue a depth-aware dispatch ticket."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

from claude_routing_common import (
    RoutingCommonError,
    atomic_write_json,
    directory_lock,
    load_json,
    load_ticket_key,
    normalize_config,
    parse_frontmatter,
    sha256_text,
    ticket_signature,
)


class ResolveError(RuntimeError):
    pass


def skill_root() -> Path:
    return Path(__file__).resolve().parent.parent


def default_policy() -> Path:
    return skill_root() / "references" / "claude-agent-routing.json"


def infer_repo_root() -> Path:
    try:
        result = subprocess.run(["git", "rev-parse", "--show-toplevel"], check=True, capture_output=True, text=True)
        if result.stdout.strip():
            return Path(result.stdout.strip()).resolve()
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    return Path.cwd().resolve()


def validate_score(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5:
        raise ResolveError(f"{name} must be an integer from 1 through 5; found {value!r}")
    return value


def validate_policy(policy: Mapping[str, Any]) -> None:
    if policy.get("schema_version") != 1 or not str(policy.get("policy_version", "")).strip():
        raise ResolveError("routing policy schema_version/policy_version is invalid")
    keys = {str(value) for value in range(1, 6)}
    matrix = policy.get("base_tier_by_score")
    if not isinstance(matrix, dict) or set(matrix) != keys:
        raise ResolveError("routing policy must define all five complexity rows")
    for row in matrix.values():
        if not isinstance(row, dict) or set(row) != keys:
            raise ResolveError("every routing matrix row must define risks 1 through 5")
    required_roles = {"implementer", "orchestrator", "spec_reviewer", "domain_reviewer", "explorer"}
    routes = policy.get("profiles_by_role_and_tier")
    if not isinstance(routes, dict) or set(routes) != required_roles:
        raise ResolveError(f"routing policy must define exactly roles {sorted(required_roles)}")
    models = policy.get("models")
    if not isinstance(models, dict) or set(models) != {"opus", "sonnet", "haiku"}:
        raise ResolveError("routing policy model catalog is incomplete")
    if not isinstance(policy.get("spawn_edges"), dict) or not isinstance(policy.get("purpose_roles"), dict):
        raise ResolveError("routing policy spawn_edges and purpose_roles are required")


def routing_from_task(task_path: Path, policy: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    task = load_json(task_path, "task JSON")
    task_id = task.get("task_id")
    if not isinstance(task_id, str) or not task_id.strip():
        raise ResolveError("task JSON task_id must be non-empty")
    routing = task.get("routing")
    if not isinstance(routing, dict):
        raise ResolveError("task routing is missing; initialize it explicitly")
    required = {"complexity", "risk", "combined", "policy_version", "scored_at", "scored_by", "rationale"}
    if set(routing) != required or any(routing.get(key) in {None, ""} for key in required):
        raise ResolveError("task routing must be completely populated before dispatch")
    complexity = validate_score("routing.complexity", routing["complexity"])
    risk = validate_score("routing.risk", routing["risk"])
    if routing["combined"] != complexity + risk:
        raise ResolveError("task routing combined does not equal complexity + risk")
    if routing["policy_version"] != policy["policy_version"]:
        raise ResolveError("task routing policy_version mismatch requires explicit migration")
    return task, routing


def phase_scores(evidence_path: Path, phase_id: int, policy: Mapping[str, Any]) -> tuple[int, int, list[str]]:
    if phase_id < 1:
        raise ResolveError("phase_id must be positive")
    task_dir = evidence_path.parent / "json"
    task_paths = sorted(task_dir.glob(f"P{phase_id}-*.json"))
    if not task_paths:
        raise ResolveError(f"phase routing found no P{phase_id}-*.json tasks under {task_dir}")
    scores: list[tuple[int, int]] = []
    for task_path in task_paths:
        task, routing = routing_from_task(task_path, policy)
        if not str(task["task_id"]).startswith(f"P{phase_id}-"):
            raise ResolveError(f"phase task identity does not match phase {phase_id}: {task_path}")
        scores.append((routing["complexity"], routing["risk"]))
    return max(value[0] for value in scores), max(value[1] for value in scores), [str(path.resolve()) for path in task_paths]


def initialize_task(task_path: Path, policy: Mapping[str, Any], complexity: int, risk: int, rationale: str, scored_by: str) -> dict[str, Any]:
    complexity = validate_score("complexity", complexity)
    risk = validate_score("risk", risk)
    if not rationale.strip():
        raise ResolveError("--rationale is required for routing initialization")
    with directory_lock(task_path):
        task = load_json(task_path, "task JSON")
        existing = task.get("routing")
        if existing is not None:
            if not isinstance(existing, dict) or any(value not in {None, ""} for value in existing.values()):
                raise ResolveError("refusing to overwrite existing task routing")
        task["routing"] = {
            "complexity": complexity,
            "risk": risk,
            "combined": complexity + risk,
            "policy_version": policy["policy_version"],
            "scored_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "scored_by": scored_by,
            "rationale": rationale.strip(),
        }
        task.setdefault("routing_evidence", [])
        atomic_write_json(task_path, task)
    return task["routing"]


def load_profiles(agents_dir: Path) -> dict[str, tuple[Path, dict[str, str]]]:
    if not agents_dir.is_dir():
        raise ResolveError(f"Claude agents directory does not exist: {agents_dir}")
    profiles: dict[str, tuple[Path, dict[str, str]]] = {}
    for path in sorted(agents_dir.rglob("*.md")):
        metadata, _ = parse_frontmatter(path)
        name = metadata.get("name")
        if not name:
            continue
        if name in profiles:
            raise ResolveError(f"duplicate Claude agent name {name!r}: {profiles[name][0]} and {path}")
        profiles[name] = (path.resolve(), metadata)
    return profiles


def expected_model_effort(agent: str) -> tuple[str, str | None]:
    if agent.endswith("-haiku"):
        return "haiku", None
    if "-sonnet-medium" in agent:
        return "sonnet", "medium"
    if "-sonnet-high" in agent:
        return "sonnet", "high"
    if "-opus-high" in agent:
        return "opus", "high"
    if "-opus-xhigh" in agent:
        return "opus", "xhigh"
    raise ResolveError(f"agent name has no recognized model/effort suffix: {agent}")


def choose_capability(role: str, requested: str, config: Mapping[str, Any], depth: int) -> str:
    if role != "domain_reviewer":
        if requested not in {"auto", "leaf"}:
            raise ResolveError(f"role {role} supports only leaf capability")
        return "leaf" if role != "orchestrator" else "nested"
    nested = config["nested_dispatch"]
    specialist_mode = nested["domain_reviewer"]["specialists"]
    runtime_max = nested.get("runtime_max_depth")
    next_depth_fits = depth + 1 <= nested["max_depth"] and (
        runtime_max is None or depth + 1 <= runtime_max
    )
    nested_allowed = specialist_mode == "nested" and next_depth_fits
    if requested == "nested" and not nested_allowed:
        raise ResolveError("nested Gate B requested when topology or depth does not permit it")
    if requested == "flat":
        return "flat"
    if nested_allowed:
        return "nested"
    if specialist_mode == "nested" and nested["on_depth_exhausted"] == "block" and not next_depth_fits:
        raise ResolveError("specialist depth budget exhausted and config requires block")
    return "flat"


def resolve_agent(policy: Mapping[str, Any], profiles: Mapping[str, tuple[Path, dict[str, str]]], *, complexity: int, risk: int, role: str, capability: str) -> tuple[str, str, Path, dict[str, str]]:
    complexity = validate_score("complexity", complexity)
    risk = validate_score("risk", risk)
    special = policy["special_routes"]["mechanical_read_only"]
    tier = policy["base_tier_by_score"][str(complexity)][str(risk)]
    effective_role = role
    if role == "mechanical_read_only" and complexity <= special["maximum_complexity"] and risk <= special["maximum_risk"]:
        agent = special["agent"]
        tier = "haiku"
    else:
        if role == "mechanical_read_only":
            effective_role = special["fallback_role"]
        routes = policy["profiles_by_role_and_tier"]
        if effective_role not in routes:
            raise ResolveError(f"unknown routing role {role!r}")
        agent = routes[effective_role][tier]
        if effective_role == "domain_reviewer":
            agent = f"{agent}-{capability}"
    if agent not in profiles:
        raise ResolveError(f"resolved generated Claude agent is missing: {agent}")
    path, metadata = profiles[agent]
    expected_model, expected_effort = expected_model_effort(agent)
    if metadata.get("model") != expected_model or metadata.get("effort") != expected_effort:
        raise ResolveError(f"{path}: model/effort does not match resolved agent name")
    if role == "mechanical_read_only" and agent == special["agent"] and metadata.get("effort") is not None:
        raise ResolveError("Haiku mechanical-search profile must omit effort")
    return agent, tier, path, metadata


def require_under(path: Path, directory: Path, label: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(directory.resolve())
    except ValueError as exc:
        raise ResolveError(f"{label} must be under {directory.resolve()}: {resolved}") from exc
    return resolved


def parent_context(
    parent_ticket: Path | None,
    requested_depth: int | None,
    ticket_dir: Path,
    ticket_key: bytes,
) -> tuple[str, str | None, int, dict[str, Any] | None, Path | None]:
    if parent_ticket is None:
        depth = 1 if requested_depth is None else requested_depth
        if depth != 1:
            raise ResolveError("top-level dispatch depth must be 1")
        return "main", None, depth, None, None
    parent_ticket = require_under(parent_ticket, ticket_dir, "parent routing ticket")
    ticket = load_json(parent_ticket, "parent routing ticket")
    signature = ticket.get("signature")
    if not isinstance(signature, str) or not secrets.compare_digest(signature, ticket_signature(ticket, ticket_key)):
        raise ResolveError("parent routing ticket signature is invalid")
    parent_role = ticket.get("child_role")
    parent_agent = ticket.get("expected_agent")
    parent_depth = ticket.get("depth")
    if not isinstance(parent_role, str) or not isinstance(parent_agent, str) or not isinstance(parent_depth, int):
        raise ResolveError("parent routing ticket is malformed")
    depth = parent_depth + 1 if requested_depth is None else requested_depth
    if depth != parent_depth + 1:
        raise ResolveError("child depth must equal parent ticket depth + 1")
    return parent_role, parent_agent, depth, ticket, parent_ticket


def validate_edge(policy: Mapping[str, Any], parent_role: str, child_role: str) -> None:
    allowed = policy["spawn_edges"].get(parent_role, [])
    if child_role not in allowed:
        raise ResolveError(f"spawn edge {parent_role!r} -> {child_role!r} is forbidden")


def append_evidence(path: Path, purpose: str, result: Mapping[str, Any]) -> None:
    with directory_lock(path):
        document = load_json(path, "routing evidence target") if path.exists() else {"routing_evidence": []}
        if "routing" in document:
            routing = document["routing"]
            if routing.get("complexity") != result["complexity"] or routing.get("risk") != result["risk"]:
                raise ResolveError("resolver scores do not match evidence target routing")
            if document.get("task_id") != result.get("task_id"):
                raise ResolveError("resolver task_id does not match evidence target")
        evidence = document.setdefault("routing_evidence", [])
        if not isinstance(evidence, list):
            raise ResolveError("routing_evidence must be an array")
        evidence.append({"dispatched_at": dt.datetime.now(dt.timezone.utc).isoformat(), "purpose": purpose, "resolver": dict(result)})
        atomic_write_json(path, document)


def issue_ticket(
    ticket_dir: Path,
    ticket_key: bytes,
    result: Mapping[str, Any],
    policy: Mapping[str, Any],
    config: Mapping[str, Any],
) -> Path:
    now = dt.datetime.now(dt.timezone.utc)
    expires = now + dt.timedelta(seconds=policy["ticket_ttl_seconds"])
    spawn_state = {"edges": policy["spawn_edges"], "nested_dispatch": config["nested_dispatch"]}
    ticket = {
        "schema_version": 1,
        "ticket_id": secrets.token_hex(16),
        "task_id": result.get("task_id"),
        "task_json_path": result.get("task_json_path"),
        "phase_id": result.get("phase_id"),
        "phase_task_paths": result.get("phase_task_paths"),
        "evidence_path": result["evidence_path"],
        "complexity": result["complexity"],
        "risk": result["risk"],
        "purpose": result["purpose"],
        "parent_agent": result.get("parent_agent"),
        "parent_role": result["parent_role"],
        "parent_ticket_id": result.get("parent_ticket_id"),
        "parent_ticket_path": result.get("parent_ticket_path"),
        "child_role": result["role"],
        "expected_agent": result["agent"],
        "expected_model": result["model"],
        "expected_effort": result["effort"],
        "capability": result["capability"],
        "depth": result["depth"],
        "max_depth": result["max_depth"],
        "runtime_max_depth": result["runtime_max_depth"],
        "spawn_policy_hash": sha256_text(json.dumps(spawn_state, sort_keys=True)),
        "policy_version": result["policy_version"],
        "created_at": now.isoformat(),
        "expires_at": expires.isoformat(),
        "consumed": False,
    }
    ticket["signature"] = ticket_signature(ticket, ticket_key)
    path = ticket_dir / f"{ticket['ticket_id']}.json"
    atomic_write_json(path, ticket)
    return path.resolve()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, default=default_policy())
    parser.add_argument("--config", type=Path)
    parser.add_argument("--agents-dir", type=Path)
    parser.add_argument("--ticket-dir", type=Path)
    parser.add_argument("--ticket-key", type=Path)
    parser.add_argument("--task-json", type=Path)
    parser.add_argument("--complexity", type=int)
    parser.add_argument("--risk", type=int)
    parser.add_argument("--phase-id", type=int)
    parser.add_argument("--initialize", action="store_true")
    parser.add_argument("--rationale", default="")
    parser.add_argument("--scored-by", default="legacy-execution-backfill")
    parser.add_argument("--role", required=True)
    parser.add_argument("--capability", choices=("auto", "leaf", "flat", "nested"), default="auto")
    parser.add_argument("--depth", type=int)
    parser.add_argument("--parent-ticket", type=Path)
    parser.add_argument("--purpose", required=True)
    parser.add_argument("--evidence-file", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    policy = load_json(args.policy.resolve(), "routing policy")
    validate_policy(policy)
    repo_root = infer_repo_root()
    config_path = (args.config or skill_root() / "autviam_config.json").resolve()
    config = normalize_config(load_json(config_path, "AutViam config") if config_path.exists() else {})
    active_overrides = [
        name
        for name in ("CLAUDE_CODE_SUBAGENT_MODEL", "CLAUDE_CODE_EFFORT_LEVEL")
        if os.environ.get(name)
    ]
    if active_overrides and not config["allow_environment_overrides"]:
        raise ResolveError(
            "deterministic routing is blocked by environment override(s): " + ", ".join(active_overrides)
        )
    agents_dir = (args.agents_dir or repo_root / ".claude" / "agents").resolve()
    profiles = load_profiles(agents_dir)

    if args.initialize:
        if not args.task_json or args.complexity is None or args.risk is None:
            raise ResolveError("--initialize requires --task-json, --complexity, and --risk")
        initialize_task(args.task_json.resolve(), policy, args.complexity, args.risk, args.rationale, args.scored_by)
    if args.task_json:
        task_path = args.task_json.resolve()
        task, routing = routing_from_task(task_path, policy)
        complexity, risk, task_id = routing["complexity"], routing["risk"], task["task_id"]
        if args.evidence_file and args.evidence_file.resolve() != task_path:
            raise ResolveError("task evidence must be written to the same task JSON")
        evidence_path = task_path
    else:
        if not args.evidence_file:
            raise ResolveError("phase routing requires --evidence-file")
        evidence_path = args.evidence_file.resolve()
        if args.role != "orchestrator" or args.phase_id is None:
            raise ResolveError("taskless routing is reserved for orchestrators and requires --phase-id")
        complexity, risk, phase_task_paths = phase_scores(evidence_path, args.phase_id, policy)
        if args.complexity is not None and args.complexity != complexity:
            raise ResolveError("provided phase complexity does not match immutable task aggregate")
        if args.risk is not None and args.risk != risk:
            raise ResolveError("provided phase risk does not match immutable task aggregate")
        task_id = None

    allowed_roles = policy["purpose_roles"].get(args.purpose)
    if not isinstance(allowed_roles, list) or args.role not in allowed_roles:
        raise ResolveError(f"purpose {args.purpose!r} is incompatible with role {args.role!r}")
    ticket_dir = (args.ticket_dir or repo_root / ".claude" / "autviam-routing" / "tickets").resolve()
    ticket_key_path = (args.ticket_key or repo_root / ".claude" / "autviam-routing" / "ticket.key").resolve()
    ticket_key = load_ticket_key(ticket_key_path)
    parent_role, parent_agent, depth, parent_ticket, parent_ticket_path = parent_context(
        args.parent_ticket.resolve() if args.parent_ticket else None,
        args.depth,
        ticket_dir,
        ticket_key,
    )
    validate_edge(policy, parent_role, args.role)
    nested = config["nested_dispatch"]
    if parent_role == "orchestrator":
        permissions = nested["phase_orchestrator"]
        if args.role == "implementer" and not permissions["spawn_implementers"]:
            raise ResolveError("phase orchestrator implementer spawning is disabled by config")
        if args.role in {"spec_reviewer", "domain_reviewer"} and not permissions["spawn_reviewers"]:
            raise ResolveError("phase orchestrator reviewer spawning is disabled by config")
    if args.role == "orchestrator" and nested["mode"] != "on":
        raise ResolveError("phase orchestrator dispatch requires nested_dispatch.mode=on after any auto probe")
    if depth > nested["max_depth"]:
        raise ResolveError("dispatch depth exceeds configured max_depth")
    runtime_max = nested.get("runtime_max_depth")
    if runtime_max is not None and depth > runtime_max:
        raise ResolveError("dispatch depth exceeds runtime_max_depth")
    capability = choose_capability(args.role, args.capability, config, depth)
    agent, tier, profile_path, metadata = resolve_agent(policy, profiles, complexity=complexity, risk=risk, role=args.role, capability=capability)
    model = metadata["model"]
    effort = metadata.get("effort")
    supported = policy["models"][model]["supported_efforts"]
    if effort is not None and effort not in supported:
        raise ResolveError(f"model {model} does not support effort {effort}")
    enforcement = config["routing_enforcement"]
    if config["allow_environment_overrides"] and (os.environ.get("CLAUDE_CODE_SUBAGENT_MODEL") or os.environ.get("CLAUDE_CODE_EFFORT_LEVEL")):
        enforcement = "externally-overridden"
    result: dict[str, Any] = {
        "policy_version": policy["policy_version"],
        "task_id": task_id,
        "complexity": complexity,
        "risk": risk,
        "combined": complexity + risk,
        "role": args.role,
        "purpose": args.purpose,
        "tier": tier,
        "capability": capability,
        "agent": agent,
        "profile_path": str(profile_path),
        "model": model,
        "effort": effort,
        "parent_role": parent_role,
        "parent_agent": parent_agent,
        "parent_ticket_id": parent_ticket.get("ticket_id") if parent_ticket else None,
        "parent_ticket_path": str(parent_ticket_path) if parent_ticket_path else None,
        "depth": depth,
        "max_depth": nested["max_depth"],
        "runtime_max_depth": runtime_max,
        "enforcement": enforcement,
        "policy_path": str(args.policy.resolve()),
        "config_path": str(config_path),
        "task_json_path": str(task_path) if args.task_json else None,
        "evidence_path": str(evidence_path),
        "phase_id": args.phase_id,
        "phase_task_paths": phase_task_paths if not args.task_json else None,
    }
    ticket_path = issue_ticket(ticket_dir, ticket_key, result, policy, config)
    result["ticket_path"] = str(ticket_path)
    append_evidence(evidence_path, args.purpose, result)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ResolveError, RoutingCommonError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
