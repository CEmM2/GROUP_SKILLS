#!/usr/bin/env python3
"""Record the result of a bounded live Claude recursive-dispatch probe."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import secrets
import sys
from pathlib import Path

from claude_routing_common import RoutingCommonError, atomic_write_json, load_json, normalize_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--observed-depth", type=int)
    parser.add_argument("--safe-limit", type=int, default=4)
    parser.add_argument("--evidence-file", type=Path)
    parser.add_argument("--audit-log", type=Path)
    parser.add_argument("--session-id")
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--record", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.safe_limit < 1:
        raise RoutingCommonError("safe limit must be positive")
    config_path = args.config.resolve()
    config = normalize_config(load_json(config_path, "AutViam config") if config_path.exists() else {})
    if args.prepare:
        if not args.evidence_file:
            raise RoutingCommonError("--prepare requires --evidence-file")
        if not args.session_id:
            raise RoutingCommonError("--prepare requires --session-id from the live Claude session")
        evidence = {
            "schema_version": 1,
            "probe_id": secrets.token_hex(16),
            "session_id": args.session_id,
            "safe_limit": args.safe_limit,
            "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "method": "live-no-write-recursive-agent-chain",
            "workspace_writes": False,
            "attempts": [],
        }
        atomic_write_json(args.evidence_file.resolve(), evidence)
        report = {
            "probe_required": True,
            "evidence_file": str(args.evidence_file.resolve()),
            "probe_id": evidence["probe_id"],
            "safe_limit": args.safe_limit,
            "instructions": (
                "Run the temporary PASS-only recursive Agent chain. Append one attempt per depth "
                "with status pass|failed and the returned agent_id; set workspace_writes=false."
            ),
        }
    elif args.observed_depth is None:
        report = {
            "probe_required": True,
            "safe_limit": args.safe_limit,
            "instructions": (
                "Rerun with --evidence-file <path> --prepare, execute the no-write recursive Agent "
                "chain, then finalize with --observed-depth N --evidence-file <path> --record."
            ),
        }
    else:
        if not args.evidence_file or not args.audit_log:
            raise RoutingCommonError("recording an observed depth requires --evidence-file and --audit-log")
        evidence = load_json(args.evidence_file.resolve(), "nested-dispatch probe evidence")
        if evidence.get("schema_version") != 1 or evidence.get("method") != "live-no-write-recursive-agent-chain":
            raise RoutingCommonError("probe evidence schema or method is invalid")
        if evidence.get("safe_limit") != args.safe_limit or evidence.get("workspace_writes") is not False:
            raise RoutingCommonError("probe evidence limit/write contract is invalid")
        attempts = evidence.get("attempts")
        if not isinstance(attempts, list) or not attempts:
            raise RoutingCommonError("probe evidence must contain live dispatch attempts")
        if len(attempts) > args.safe_limit:
            raise RoutingCommonError("probe evidence exceeds safe-limit")
        pass_depths: list[int] = []
        passing_attempts: list[dict[str, object]] = []
        for expected_depth, attempt in enumerate(attempts, start=1):
            if not isinstance(attempt, dict) or attempt.get("depth") != expected_depth:
                raise RoutingCommonError("probe attempt depths must be contiguous from 1")
            if attempt.get("status") not in {"pass", "failed"}:
                raise RoutingCommonError("probe attempt status must be pass or failed")
            if attempt["status"] == "pass":
                if not isinstance(attempt.get("agent_id"), str) or not attempt["agent_id"].strip():
                    raise RoutingCommonError("passing probe attempts require a runtime agent_id")
                pass_depths.append(expected_depth)
                passing_attempts.append(attempt)
            elif expected_depth != len(attempts):
                raise RoutingCommonError("a failed probe attempt must be final")
        verified_depth = max(pass_depths, default=0)
        if verified_depth != args.observed_depth:
            raise RoutingCommonError("observed depth does not match probe evidence")
        if verified_depth < args.safe_limit and attempts[-1].get("status") != "failed":
            raise RoutingCommonError("probe stopped below safe-limit without a failed child spawn")
        audit_records: list[dict[str, object]] = []
        try:
            for line in args.audit_log.read_text(encoding="utf-8").splitlines():
                value = json.loads(line)
                if isinstance(value, dict):
                    audit_records.append(value)
        except (OSError, json.JSONDecodeError) as exc:
            raise RoutingCommonError(f"could not read probe audit log: {exc}") from exc
        previous_agent_id: object = None
        for attempt in passing_attempts:
            agent_id = attempt.get("agent_id")
            agent_type = attempt.get("agent_type")
            if not isinstance(agent_type, str) or not agent_type.startswith("routing-probe-"):
                raise RoutingCommonError("passing probe attempts require routing-probe agent_type")
            if attempt.get("parent_agent_id") != previous_agent_id:
                raise RoutingCommonError("probe evidence parent-agent chain is invalid")
            matches = [
                record
                for record in audit_records
                if record.get("session_id") == evidence.get("session_id")
                and record.get("agent_id") == agent_id
                and record.get("agent_type") == agent_type
            ]
            if len(matches) != 1:
                raise RoutingCommonError("probe attempt does not match exactly one SubagentStart audit record")
            audited_depth = matches[0].get("observed_depth")
            if audited_depth is not None and audited_depth != attempt["depth"]:
                raise RoutingCommonError("probe attempt depth disagrees with runtime audit")
            audited_parent = matches[0].get("parent_agent_id")
            if audited_parent is not None and audited_parent != previous_agent_id:
                raise RoutingCommonError("probe parent chain disagrees with runtime audit")
            previous_agent_id = agent_id
        if args.observed_depth < 1 or args.observed_depth > args.safe_limit:
            raise RoutingCommonError("observed depth must be between 1 and safe-limit")
        nested = config["nested_dispatch"]
        nested["runtime_max_depth"] = args.observed_depth
        if nested["max_depth"] > args.observed_depth:
            nested["max_depth"] = args.observed_depth
        if nested["mode"] == "auto":
            nested["mode"] = "on" if args.observed_depth >= 2 else "off"
        config["runtime_probe"] = {
            "observed_depth": args.observed_depth,
            "safe_limit": args.safe_limit,
            "recorded_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "method": "live-no-write-recursive-agent-chain",
            "probe_id": evidence.get("probe_id"),
            "evidence_file": str(args.evidence_file.resolve()),
        }
        if args.record:
            atomic_write_json(config_path, config)
        report = {"probe_required": False, "recorded": args.record, "config": config}
    print(json.dumps(report, indent=2) if args.json else report)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RoutingCommonError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
