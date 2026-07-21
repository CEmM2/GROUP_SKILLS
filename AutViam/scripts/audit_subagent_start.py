#!/usr/bin/env python3
"""Audit-only Claude SubagentStart hook for AutViam generated agents."""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path

from claude_routing_common import (
    RoutingCommonError,
    atomic_write_json,
    directory_lock,
    load_json,
    load_ticket_key,
    ticket_signature,
)


def consume_start_context(
    project_dir: Path,
    agent_type: str,
    session_id: object,
    parent_agent_id: object,
) -> dict[str, object]:
    routing_root = project_dir / ".claude" / "autviam-routing"
    ticket_dir = routing_root / "tickets"
    key_path = routing_root / "ticket.key"
    if not ticket_dir.is_dir() or not key_path.is_file():
        return {}
    key = load_ticket_key(key_path)
    candidates: list[tuple[str, Path, dict[str, object]]] = []
    for path in ticket_dir.glob("*.json"):
        try:
            ticket = load_json(path, "routing ticket")
        except RoutingCommonError:
            continue
        if (
            ticket.get("consumed") is True
            and ticket.get("observed_agent") == agent_type
            and ticket.get("consumed_session_id") == session_id
            and ticket.get("dispatching_agent_id") == parent_agent_id
            and not ticket.get("start_audited_at")
            and ticket.get("signature") == ticket_signature(ticket, key)
        ):
            candidates.append((str(ticket.get("consumed_at", "")), path, ticket))
    if len(candidates) != 1:
        return {}
    _, path, ticket = candidates[0]
    with directory_lock(path):
        current = load_json(path, "routing ticket")
        if current.get("start_audited_at"):
            return {}
        current["start_audited_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        current["signature"] = ticket_signature(current, key)
        atomic_write_json(path, current)
    return {
        "ticket_id": ticket.get("ticket_id"),
        "ticket_path": str(path.resolve()),
        "parent_agent": ticket.get("parent_agent"),
        "parent_role": ticket.get("parent_role"),
        "observed_depth": ticket.get("depth"),
        "capability": ticket.get("capability"),
    }


def main() -> int:
    value = json.load(sys.stdin)
    if not isinstance(value, dict) or value.get("hook_event_name") != "SubagentStart":
        return 0
    agent_type = value.get("agent_type")
    is_production = isinstance(agent_type, str) and agent_type.startswith("autviam-")
    is_probe = isinstance(agent_type, str) and agent_type.startswith("routing-probe-")
    if not is_production and not is_probe:
        return 0
    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", value.get("cwd", "."))).resolve()
    audit_path = project_dir / ".claude" / "autviam-routing" / "subagent-start.jsonl"
    parent_agent_id = value.get("parent_agent_id")
    ticket_context = (
        consume_start_context(project_dir, agent_type, value.get("session_id"), parent_agent_id)
        if is_production
        else {}
    )
    record = {
        "observed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "session_id": value.get("session_id"),
        "agent_id": value.get("agent_id"),
        "agent_type": agent_type,
        "observed_depth": value.get(
            "agent_depth", value.get("depth", ticket_context.get("observed_depth"))
        ),
        "parent_agent": value.get("parent_agent_type", ticket_context.get("parent_agent")),
        "parent_agent_id": parent_agent_id,
        "parent_role": ticket_context.get("parent_role"),
        "capability": ticket_context.get("capability"),
        "ticket_id": ticket_context.get("ticket_id"),
        "ticket_path": ticket_context.get("ticket_path"),
    }
    with directory_lock(audit_path):
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        with audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # Audit telemetry must never block a valid subagent start.
        print(f"AutViam SubagentStart audit error: {exc}", file=sys.stderr)
        raise SystemExit(0)
