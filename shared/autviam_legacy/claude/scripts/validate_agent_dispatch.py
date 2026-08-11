#!/usr/bin/env python3
"""Claude PreToolUse hook enforcing AutViam routing tickets for Agent calls."""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import json
import re
import secrets
import sys
from pathlib import Path
from typing import Any

from claude_routing_common import (
    RoutingCommonError,
    atomic_write_json,
    directory_lock,
    load_json,
    load_ticket_key,
    normalize_config,
    sha256_text,
    ticket_signature,
)
from resolve_claude_agent import (
    ResolveError,
    choose_capability,
    load_profiles,
    phase_scores,
    resolve_agent,
    routing_from_task,
    validate_policy,
)


TICKET_PATTERN = re.compile(r"(?:^|\n)autviam_routing_ticket:\s*([^\s]+)")


class DispatchError(RuntimeError):
    pass


@contextlib.contextmanager
def dispatch_locks(ticket_path: Path, reservation_path: Path):
    with directory_lock(reservation_path):
        with directory_lock(ticket_path):
            yield


def decision(permission: str, reason: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": permission,
            "permissionDecisionReason": reason,
        }
    }


def require_under(path: Path, directory: Path, label: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(directory.resolve())
    except ValueError as exc:
        raise DispatchError(f"{label} is outside the configured ticket directory") from exc
    return resolved


def assert_unique_task_provenance(repo_root: Path, task_path: Path, task: dict[str, Any]) -> None:
    matches: list[Path] = []
    for candidate in repo_root.rglob(task_path.name):
        if candidate.parent.name != "json" or ".claude" in candidate.parts:
            continue
        try:
            value = load_json(candidate, "candidate task JSON")
        except RoutingCommonError:
            continue
        if value.get("task_id") == task.get("task_id") and value.get("plan_file") == task.get("plan_file"):
            matches.append(candidate.resolve())
    if matches != [task_path.resolve()]:
        raise DispatchError("task routing provenance is ambiguous or does not match the canonical plan task")


def record_denial(routing_root: Path, input_value: Any, reason: str) -> None:
    """Append the observed dispatch identity for a denied Agent call."""
    observed = input_value if isinstance(input_value, dict) else {}
    tool_input = observed.get("tool_input")
    tool_input = tool_input if isinstance(tool_input, dict) else {}
    prompt = tool_input.get("prompt")
    match = TICKET_PATTERN.search(prompt) if isinstance(prompt, str) else None
    record = {
        "observed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "reason": reason,
        "session_id": observed.get("session_id"),
        "agent_id": observed.get("agent_id"),
        "agent_type": observed.get("agent_type"),
        "parent_agent_type": observed.get("parent_agent_type"),
        "requested_agent": tool_input.get("subagent_type") or tool_input.get("agent_type"),
        "ticket_path": match.group(1) if match else None,
    }
    denial_path = routing_root / "dispatch-denials.jsonl"
    with directory_lock(denial_path):
        denial_path.parent.mkdir(parents=True, exist_ok=True)
        with denial_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def validate(
    input_value: dict[str, Any],
    *,
    policy_path: Path,
    config_path: Path,
    agents_dir: Path,
    ticket_dir: Path,
    ticket_key_path: Path,
    repo_root: Path,
) -> dict[str, Any] | None:
    if input_value.get("hook_event_name") != "PreToolUse" or input_value.get("tool_name") != "Agent":
        return None
    tool_input = input_value.get("tool_input")
    if not isinstance(tool_input, dict):
        raise DispatchError("Agent hook input has no tool_input object")
    requested_agent = tool_input.get("subagent_type") or tool_input.get("agent_type")
    prompt = tool_input.get("prompt", "")
    if not isinstance(requested_agent, str) or not isinstance(prompt, str):
        raise DispatchError("Agent call must provide subagent_type and prompt")
    match = TICKET_PATTERN.search(prompt)
    if not match:
        if requested_agent.startswith("autviam-"):
            raise DispatchError("AutViam Agent call is missing autviam_routing_ticket")
        return None
    ticket_path = require_under(Path(match.group(1)).expanduser(), ticket_dir, "routing ticket")
    ticket_key = load_ticket_key(ticket_key_path)
    reservation_key = sha256_text(
        json.dumps(
            {
                "session_id": input_value.get("session_id"),
                "dispatching_agent_id": input_value.get("agent_id"),
                "expected_agent": requested_agent,
            },
            sort_keys=True,
        )
    )
    reservation_path = ticket_dir / ".reservations" / reservation_key
    with dispatch_locks(ticket_path, reservation_path):
        ticket = load_json(ticket_path, "routing ticket")
        required = {
            "schema_version", "ticket_id", "parent_role", "child_role", "expected_agent",
            "capability", "depth", "max_depth", "policy_version", "created_at", "expires_at", "consumed",
            "spawn_policy_hash", "signature", "complexity", "risk", "purpose", "evidence_path",
            "parent_ticket_id", "parent_ticket_path", "task_json_path", "expected_model", "expected_effort",
            "phase_id", "phase_task_paths",
        }
        missing = sorted(required - ticket.keys())
        if missing:
            raise DispatchError(f"routing ticket omits fields: {missing}")
        if ticket["schema_version"] != 1:
            raise DispatchError("unsupported routing ticket schema_version")
        signature = ticket.get("signature")
        if not isinstance(signature, str) or not secrets.compare_digest(signature, ticket_signature(ticket, ticket_key)):
            raise DispatchError("routing ticket signature is invalid")
        if ticket["consumed"]:
            raise DispatchError("routing ticket has already been consumed")
        if requested_agent != ticket["expected_agent"]:
            raise DispatchError(
                f"requested agent {requested_agent!r} does not match ticket {ticket['expected_agent']!r}"
            )
        observed_parent = input_value.get("agent_type")
        if ticket.get("parent_agent") is not None and observed_parent != ticket["parent_agent"]:
            raise DispatchError(
                f"observed parent {observed_parent!r} does not match ticket parent {ticket['parent_agent']!r}"
            )
        if ticket.get("parent_agent") is None and observed_parent is not None:
            raise DispatchError("top-level routing ticket cannot be used from a subagent")
        policy = load_json(policy_path, "routing policy")
        validate_policy(policy)
        config = normalize_config(load_json(config_path, "AutViam config") if config_path.exists() else {})
        spawn_state = {"edges": policy["spawn_edges"], "nested_dispatch": config["nested_dispatch"]}
        expected_hash = sha256_text(json.dumps(spawn_state, sort_keys=True))
        if ticket["spawn_policy_hash"] != expected_hash:
            raise DispatchError("routing ticket spawn policy hash does not match current policy/config")
        if ticket["policy_version"] != policy.get("policy_version"):
            raise DispatchError("routing ticket policy version is stale")
        allowed_roles = policy["purpose_roles"].get(ticket["purpose"])
        if not isinstance(allowed_roles, list) or ticket["child_role"] not in allowed_roles:
            raise DispatchError("routing ticket purpose is incompatible with child role")
        allowed = policy["spawn_edges"].get(ticket["parent_role"], [])
        if ticket["child_role"] not in allowed:
            raise DispatchError("routing ticket contains a forbidden parent-child edge")
        if ticket["parent_role"] == "main":
            if ticket["parent_ticket_id"] is not None or ticket["parent_ticket_path"] is not None or ticket["depth"] != 1:
                raise DispatchError("top-level routing ticket has a forged parent/depth chain")
        else:
            if not isinstance(ticket["parent_ticket_path"], str) or not isinstance(ticket["parent_ticket_id"], str):
                raise DispatchError("nested routing ticket omits parent ticket identity")
            parent_path = require_under(Path(ticket["parent_ticket_path"]), ticket_dir, "parent routing ticket")
            parent = load_json(parent_path, "parent routing ticket")
            parent_signature = parent.get("signature")
            if not isinstance(parent_signature, str) or not secrets.compare_digest(
                parent_signature, ticket_signature(parent, ticket_key)
            ):
                raise DispatchError("parent routing ticket signature is invalid")
            if (
                parent.get("ticket_id") != ticket["parent_ticket_id"]
                or parent.get("expected_agent") != ticket.get("parent_agent")
                or parent.get("child_role") != ticket["parent_role"]
                or parent.get("depth", 0) + 1 != ticket["depth"]
            ):
                raise DispatchError("routing ticket parent chain does not match its signed parent")
        if ticket["depth"] > ticket["max_depth"]:
            raise DispatchError("routing ticket exceeds configured max_depth")
        runtime_max = ticket.get("runtime_max_depth")
        if runtime_max is not None and ticket["max_depth"] > runtime_max:
            raise DispatchError("routing ticket max_depth exceeds runtime_max_depth")
        try:
            expires = dt.datetime.fromisoformat(ticket["expires_at"])
        except (TypeError, ValueError) as exc:
            raise DispatchError("routing ticket expires_at is invalid") from exc
        if expires <= dt.datetime.now(dt.timezone.utc):
            raise DispatchError("routing ticket has expired")
        if ticket["task_json_path"] is not None:
            task_path = require_under(Path(ticket["task_json_path"]), repo_root, "task JSON")
            if task_path.parent.name != "json" or task_path.name != f"{ticket.get('task_id')}.json":
                raise DispatchError("routing ticket task path is not the canonical task JSON location")
            if Path(ticket["evidence_path"]).resolve() != task_path:
                raise DispatchError("task routing evidence must be the canonical task JSON")
            task, routing = routing_from_task(task_path, policy)
            assert_unique_task_provenance(repo_root, task_path, task)
            if task.get("task_id") != ticket.get("task_id"):
                raise DispatchError("routing ticket task identity does not match immutable task state")
            if routing["complexity"] != ticket["complexity"] or routing["risk"] != ticket["risk"]:
                raise DispatchError("routing ticket scores do not match immutable task state")
        else:
            if not isinstance(ticket["phase_id"], int):
                raise DispatchError("phase routing ticket omits phase_id")
            evidence_path = require_under(Path(ticket["evidence_path"]), repo_root, "phase evidence")
            complexity, risk, task_paths = phase_scores(evidence_path, ticket["phase_id"], policy)
            for phase_task_path in task_paths:
                phase_task, _ = routing_from_task(Path(phase_task_path), policy)
                assert_unique_task_provenance(repo_root, Path(phase_task_path), phase_task)
            if complexity != ticket["complexity"] or risk != ticket["risk"]:
                raise DispatchError("phase routing ticket scores do not match immutable task aggregates")
            if task_paths != ticket["phase_task_paths"]:
                raise DispatchError("phase routing ticket task set does not match canonical phase tasks")
        capability = choose_capability(ticket["child_role"], "auto", config, ticket["depth"])
        if capability != ticket["capability"]:
            raise DispatchError("routing ticket capability does not match current topology")
        profiles = load_profiles(agents_dir)
        expected_agent, _, _, metadata = resolve_agent(
            policy,
            profiles,
            complexity=ticket["complexity"],
            risk=ticket["risk"],
            role=ticket["child_role"],
            capability=capability,
        )
        if expected_agent != requested_agent:
            raise DispatchError("routing ticket agent does not match the immutable score route")
        if metadata.get("model") != ticket["expected_model"] or metadata.get("effort") != ticket["expected_effort"]:
            raise DispatchError("routing ticket model/effort does not match the generated profile")
        session_id = input_value.get("session_id")
        dispatching_agent_id = input_value.get("agent_id")
        for other_path in ticket_dir.glob("*.json"):
            if other_path.resolve() == ticket_path:
                continue
            try:
                other = load_json(other_path, "routing ticket")
            except RoutingCommonError:
                continue
            if (
                other.get("consumed") is True
                and not other.get("start_audited_at")
                and other.get("expected_agent") == requested_agent
                and other.get("consumed_session_id") == session_id
                and other.get("dispatching_agent_id") == dispatching_agent_id
            ):
                raise DispatchError(
                    "an unaudited dispatch for this session/parent/agent is already pending; serialize identical profiles"
                )
        ticket["consumed"] = True
        ticket["consumed_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        ticket["observed_agent"] = requested_agent
        ticket["consumed_session_id"] = session_id
        ticket["dispatching_agent_id"] = dispatching_agent_id
        ticket["signature"] = ticket_signature(ticket, ticket_key)
        atomic_write_json(ticket_path, ticket)
    return decision("allow", "AutViam routing ticket validated")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--agents-dir", type=Path, required=True)
    parser.add_argument("--ticket-dir", type=Path, required=True)
    parser.add_argument("--ticket-key", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    args = parser.parse_args(argv)
    input_value: Any = None
    try:
        input_value = json.load(sys.stdin)
        if not isinstance(input_value, dict):
            raise DispatchError("hook input must be a JSON object")
        output = validate(
            input_value,
            policy_path=args.policy.resolve(),
            config_path=args.config.resolve(),
            agents_dir=args.agents_dir.resolve(),
            ticket_dir=args.ticket_dir.resolve(),
            ticket_key_path=args.ticket_key.resolve(),
            repo_root=args.repo_root.resolve(),
        )
        if output is not None:
            print(json.dumps(output))
        return 0
    except (DispatchError, ResolveError, RoutingCommonError, json.JSONDecodeError) as exc:
        with contextlib.suppress(Exception):  # Telemetry must never alter the deny decision.
            record_denial(args.ticket_dir.resolve().parent, input_value, str(exc))
        print(json.dumps(decision("deny", str(exc))))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
