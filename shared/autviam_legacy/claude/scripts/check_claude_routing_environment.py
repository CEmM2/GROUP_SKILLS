#!/usr/bin/env python3
"""Fail closed on Claude environment overrides that outrank agent frontmatter."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from claude_routing_common import RoutingCommonError, load_json, normalize_config


OVERRIDES = ("CLAUDE_CODE_SUBAGENT_MODEL", "CLAUDE_CODE_EFFORT_LEVEL")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    config = normalize_config(load_json(args.config.resolve(), "AutViam config") if args.config and args.config.exists() else {})
    active = {name: os.environ[name] for name in OVERRIDES if os.environ.get(name)}
    permitted = config["allow_environment_overrides"]
    report = {
        "valid": not active or permitted,
        "active_overrides": active,
        "enforcement": "externally-overridden" if active and permitted else config["routing_enforcement"],
    }
    if args.json:
        print(json.dumps(report, indent=2))
    elif active:
        print("Claude routing environment overrides: " + ", ".join(sorted(active)))
    else:
        print("Claude routing environment: deterministic")
    if active and not permitted:
        print(
            "error: deterministic AutViam routing is blocked by " + ", ".join(sorted(active)),
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RoutingCommonError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
