#!/usr/bin/env python3
"""Probe whether the configured external launcher can actually be executed here.

`install_agent_profiles.py` and the Install command establish that a launcher is
*configured* and that its interface advertises the controls AutViam_C needs. Neither
establishes that this environment will let the launcher run: a nested `codex exec` is
routinely refused by sandbox policy, by `[agents] max_depth`, or by an approval layer
above the session. Until #55 that gap was invisible, because read-only roles silently
degraded to a native model-and-prompt dispatch. They no longer do — they route to
`external_exact` or block — so an untested launcher now wedges Gate A, Gate B, explore,
and the mechanical read-only route at the moment they are needed.

This script closes the gap by *running* the launcher once, bounded and read-only, and
recording three states the capability record previously collapsed into one boolean:

  configured           the record names a launcher                (static)
  interface_validated  its advertised controls satisfy the policy (static)
  runtime_executable   a real bounded launch succeeded here       (measured)

It also stamps `environment_fingerprint`, so a record probed in one session is not
trusted by a later session with different permissions.

Only `mode: "codex_cli"` can be probed automatically; an `mcp` launcher is reached
through the host's tool layer rather than a subprocess, so it must be recorded with
`--record-manual` after the operator verifies it.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

from resolve_codex_agent import (
    RoutingError,
    default_capabilities_path,
    evidence_lock,
    validate_dispatcher_capabilities,
)
from routing_core import atomic_write_json, load_json, sha256_text

# Bounded, read-only, and self-contained: the probe must prove the launcher runs, not
# exercise the model's judgement, so it asks for one token and inspects nothing.
PROBE_TOKEN = "AUTVIAM-C-PROBE-OK"
PROBE_PROMPT = (
    "This is a bounded AutViam_C launcher probe. Do not read, list, or modify any "
    f"repository file. Reply with exactly this token and nothing else: {PROBE_TOKEN}"
)
PROBE_RESULTS = {
    "ok",
    "launcher-missing",
    "no-output",
    "not-configured",
    "permission-denied",
    "recorded-manually",
    "timeout",
    "unprobed",
}
# Substrings that identify a refusal by the environment rather than a launcher error.
# Matched case-insensitively against stderr; deliberately broad, because a false
# "permission-denied" and a false "launcher error" both land on runtime_executable=False.
DENIAL_MARKERS = (
    "approval",
    "denied",
    "forbidden",
    "max_depth",
    "not permitted",
    "operation not permitted",
    "permission",
    "read-only file system",
    "refused",
    "sandbox",
)


def _launcher_version(binary: str) -> str:
    """Best-effort launcher version for the fingerprint; never fatal."""
    try:
        completed = subprocess.run(
            [binary, "--version"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return (completed.stdout or completed.stderr).strip() or "unknown"


def environment_fingerprint(command: list[str]) -> str:
    """Hash the launch-relevant environment.

    Values are hashed, never stored, so a `CODEX_*` variable carrying a token cannot
    leak into a file that lives in the repository. The fingerprint deliberately covers
    the launcher identity and every `CODEX_*` variable: those are what decide whether a
    nested launch is permitted, so a change in any of them must invalidate the probe.
    """
    binary = shutil.which(command[0]) or command[0]
    codex_env = sorted(
        f"{name}={value}" for name, value in os.environ.items() if name.startswith("CODEX_")
    )
    material = "\n".join(
        [
            "autviam-c-dispatch-probe/1",
            platform.platform(),
            " ".join(command),
            binary,
            _launcher_version(binary) if Path(binary).exists() else "missing",
            *codex_env,
        ]
    )
    return sha256_text(material)


def build_probe_command(
    external: Mapping[str, Any],
    *,
    model: str,
    reasoning_effort: str,
    cwd: Path,
    extra_args: list[str],
) -> list[str]:
    """Build the launch AutViam_C would really make, minus the task payload.

    The probe must exercise the *same* flags a live dispatch would, or it proves
    nothing: an environment can permit bare `codex exec` and still refuse it with a
    sandbox override. Flags are added only where the record advertises support, so a
    launcher is never failed for lacking a control the policy did not ask of it.
    """
    command = [*external["command"]]
    if external.get("supports_model_selection"):
        command += ["-m", model]
    if external.get("supports_reasoning_effort"):
        command += ["-c", f'model_reasoning_effort="{reasoning_effort}"']
    if external.get("supports_sandbox_override"):
        command += ["-s", "read-only"]
    command += ["-C", str(cwd)]
    command += extra_args
    command.append("-")
    return command


def classify(completed: subprocess.CompletedProcess[str]) -> tuple[str, str]:
    """Map a finished launch onto (result, detail).

    `no-output` is kept distinct from `permission-denied` on purpose. A launcher that
    exits 0 having printed nothing is the failure mode that is easiest to misread as
    success, and the one an operator must debug differently.
    """
    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()
    if completed.returncode != 0:
        lowered = stderr.lower()
        if any(marker in lowered for marker in DENIAL_MARKERS):
            return "permission-denied", stderr[:500] or "launcher refused by the environment"
        return "launcher-missing" if completed.returncode == 127 else "permission-denied", (
            stderr[:500] or f"launcher exited with status {completed.returncode}"
        )
    if not stdout:
        return "no-output", "launcher exited 0 but produced no output"
    return "ok", ""


def run_probe(
    external: Mapping[str, Any],
    *,
    model: str,
    reasoning_effort: str,
    cwd: Path,
    timeout_seconds: float,
    extra_args: list[str],
) -> dict[str, Any]:
    command = build_probe_command(
        external,
        model=model,
        reasoning_effort=reasoning_effort,
        cwd=cwd,
        extra_args=extra_args,
    )
    record: dict[str, Any] = {"command": command}
    try:
        completed = subprocess.run(
            command,
            input=PROBE_PROMPT,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError:
        record.update(result="launcher-missing", detail=f"launcher not found on PATH: {command[0]}")
        return record
    except subprocess.TimeoutExpired:
        record.update(result="timeout", detail=f"launcher did not finish within {timeout_seconds:.0f}s")
        return record
    except OSError as exc:
        record.update(result="permission-denied", detail=f"launcher could not be started: {exc}")
        return record
    result, detail = classify(completed)
    record.update(result=result, detail=detail)
    # Token compliance is reported but never gates the verdict: the question is whether
    # the environment permits the launch, not whether the model followed instructions.
    record["token_echoed"] = PROBE_TOKEN in (completed.stdout or "")
    return record


def launcher_command(external: Mapping[str, Any]) -> list[str]:
    """The launcher identity to fingerprint — never the full probe argv.

    `check()` and `apply_probe()` must derive the fingerprint from the same input or a
    freshly probed record fails its own freshness test. Deriving both from the record's
    `command` makes that agreement structural rather than a convention.
    """
    command = external.get("command")
    if isinstance(command, list) and command and all(isinstance(part, str) for part in command):
        return list(command)
    return ["codex"]


def apply_probe(capabilities: dict[str, Any], probe: Mapping[str, Any]) -> dict[str, Any]:
    """Fold a probe outcome into the capability record."""
    if probe["result"] not in PROBE_RESULTS:
        # recovery.md documents each value and its remedy; an unlisted one would reach
        # an operator with no documented fix.
        raise RoutingError(f"unknown probe result {probe['result']!r}")
    external = dict(capabilities.get("external_dispatch") or {})
    external["runtime_executable"] = probe["result"] in {"ok", "recorded-manually"}
    external["last_probe_result"] = probe["result"]
    external["last_probe_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    external["environment_fingerprint"] = environment_fingerprint(launcher_command(external))
    detail = probe.get("detail") or ""
    if detail:
        external["failure_detail"] = detail
    else:
        external.pop("failure_detail", None)
    updated = dict(capabilities)
    updated["external_dispatch"] = external
    return updated


def check(capabilities: Mapping[str, Any]) -> tuple[bool, str]:
    """Return (usable, message) for the recorded external launcher in this environment."""
    external = capabilities.get("external_dispatch") or {}
    if not external.get("available"):
        return False, "capability record declares no external launcher (external_dispatch.available is false)"
    result = external.get("last_probe_result", "unprobed")
    if not external.get("runtime_executable"):
        detail = external.get("failure_detail")
        suffix = f": {detail}" if detail else ""
        return False, f"external launcher is not runtime-executable here (last probe: {result}){suffix}"
    recorded = external.get("environment_fingerprint")
    current = environment_fingerprint(launcher_command(external))
    if recorded != current:
        return False, (
            "external launcher was probed in a different environment; the launcher "
            "identity or a CODEX_* variable changed since the probe, so the record no "
            "longer describes this session"
        )
    return True, f"external launcher is executable here (probed {external.get('last_probe_at')})"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dispatcher-capabilities",
        type=Path,
        default=default_capabilities_path(),
        help="Capability record to probe and update in place.",
    )
    parser.add_argument("--cwd", type=Path, default=Path.cwd(), help="Working directory for the probe launch.")
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument(
        "--launcher-arg",
        action="append",
        default=[],
        dest="launcher_args",
        help="Extra launcher argument (repeatable), e.g. --launcher-arg --ephemeral.",
    )
    parser.add_argument(
        "--record-manual",
        choices=["executable", "launcher-missing", "no-output", "permission-denied", "timeout"],
        help="Record an operator-verified outcome without launching (required for mode 'mcp').",
    )
    parser.add_argument("--check", action="store_true", help="Report whether the recorded probe is usable here; write nothing.")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.timeout_seconds <= 0:
        raise RoutingError("--timeout-seconds must be positive")
    path = args.dispatcher_capabilities.resolve()
    raw = load_json(path, "dispatcher capabilities")
    # Validate before touching it: the probe must never be the reason a record starts
    # failing the resolver's own contract.
    capabilities = validate_dispatcher_capabilities(raw)
    external = capabilities["external_dispatch"]

    if args.check:
        usable, message = check(raw)
        report = {"usable": usable, "message": message, "capabilities": str(path)}
        print(json.dumps(report, indent=2) if args.json else message)
        return 0 if usable else 1

    if not external.get("available"):
        probe = {"result": "not-configured", "detail": "external_dispatch.available is false", "command": ["codex"]}
    elif args.record_manual:
        result = "recorded-manually" if args.record_manual == "executable" else args.record_manual
        probe = {
            "result": result,
            "detail": "recorded by operator without an automated launch",
            "command": list(external["command"]),
        }
    elif external["mode"] != "codex_cli":
        raise RoutingError(
            f"external launcher mode {external['mode']!r} cannot be probed automatically; verify it by "
            "hand and rerun with --record-manual executable (or --record-manual permission-denied)"
        )
    else:
        supported = external["supported_models"]
        if not supported:
            raise RoutingError("external launcher advertises no supported models; nothing to probe")
        probe = run_probe(
            external,
            model=supported[0],
            reasoning_effort="medium",
            cwd=args.cwd.resolve(),
            timeout_seconds=args.timeout_seconds,
            extra_args=list(args.launcher_args),
        )

    with evidence_lock(path):
        current = load_json(path, "dispatcher capabilities")
        updated = apply_probe(current, probe)
        # Re-validate the exact document about to be written, so a probe can never
        # leave behind a record the resolver would reject at dispatch time.
        validate_dispatcher_capabilities(updated)
        atomic_write_json(path, updated)

    report = {
        "result": probe["result"],
        "runtime_executable": updated["external_dispatch"]["runtime_executable"],
        "detail": probe.get("detail", ""),
        "command": probe["command"],
        "capabilities": str(path),
    }
    print(json.dumps(report, indent=2) if args.json else report)
    return 0 if report["runtime_executable"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RoutingError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
