#!/usr/bin/env python3
"""Fail-closed compatibility shim for the retired template-expansion workflow."""

from __future__ import annotations

import sys


MESSAGE = (
    "expand_codex_agents.py is deprecated for Path 2 because template-derived profiles "
    "cannot satisfy exact managed-source validation. Use install_agent_profiles.py to "
    "generate the canonical managed profiles. This shim is scheduled for removal after "
    "2026-10-01."
)


def main() -> int:
    print(f"error: {MESSAGE}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
