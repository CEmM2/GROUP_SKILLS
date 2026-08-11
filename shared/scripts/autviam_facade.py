#!/usr/bin/env python3
"""Validate the shared AutViam profile dependency and map a façade command.

This module intentionally does not execute Whatter or contain scheduler, gate, prompt,
or mutable task-state behavior. The host conversation executes the emitted command only
after the user has supplied the normal Whatter inputs and authorization.
"""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any


SCRIPT_ROOT = Path(__file__).resolve().parent
SHARED_ROOT = SCRIPT_ROOT.parent
METADATA_PATH = SHARED_ROOT / "autviam-profile-dependency.json"
CUTOVER_PATH = SHARED_ROOT / "autviam-cutover-release.json"
PROFILE_ENV_VAR = "WHATTER_AUTVIAM_PROFILE"


class BootstrapError(ValueError):
    """A dependency or command condition that must block the façade."""


def load_metadata() -> dict[str, Any]:
    try:
        document = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BootstrapError(
            f"AutViam profile dependency metadata is unavailable: {METADATA_PATH}"
        ) from exc
    if document.get("schema_version") != "autviam.profile-dependency/v1":
        raise BootstrapError(
            "AutViam profile dependency metadata has an unsupported schema version."
        )
    return document


def load_cutover(metadata: dict[str, Any]) -> dict[str, Any]:
    try:
        document = json.loads(CUTOVER_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BootstrapError(
            f"AutViam cutover release metadata is unavailable: {CUTOVER_PATH}"
        ) from exc
    if document.get("schema_version") != "autviam.cutover-release/v1":
        raise BootstrapError(
            "AutViam cutover metadata has an unsupported schema version."
        )
    selected = document.get("selection", {}).get("default_for_new_projects")
    if selected not in {"profile-backed", "legacy"}:
        raise BootstrapError(
            "AutViam cutover metadata has an invalid default selection."
        )
    if document.get("selection", {}).get("automatic_fallback") is not False:
        raise BootstrapError(
            "AutViam cutover metadata must disable automatic fallback."
        )
    if (
        document.get("legacy", {}).get("available_until")
        != metadata["compatibility"]["legacy_available_until"]
    ):
        raise BootstrapError("AutViam cutover and compatibility windows disagree.")
    if (
        document.get("legacy", {}).get("freeze_policy")
        != "compatibility-and-security-fixes-only"
    ):
        raise BootstrapError("AutViam legacy freeze policy is invalid.")
    if document.get("delivery") != {
        "default_terminal": "delivery.ready",
        "merge_behavior": "separate-governed-action",
    }:
        raise BootstrapError("AutViam cutover delivery policy is invalid.")
    return document


def cutover_summary(cutover: dict[str, Any]) -> dict[str, Any]:
    return {
        "release_id": cutover["release_id"],
        "default_for_new_projects": cutover["selection"]["default_for_new_projects"],
        "automatic_fallback": cutover["selection"]["automatic_fallback"],
        "default_terminal": cutover["delivery"]["default_terminal"],
        "merge_behavior": cutover["delivery"]["merge_behavior"],
    }


def tree_hash(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(path.rglob("*")):
        if (
            not item.is_file()
            or "__pycache__" in item.parts
            or item.name == ".DS_Store"
        ):
            continue
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(item.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def resolve_profile(metadata: dict[str, Any], override: str | None) -> dict[str, str]:
    profile = (
        Path(override).resolve()
        if override
        else SHARED_ROOT / metadata["profile"]["source_path"]
    )
    if not profile.is_dir():
        raise BootstrapError(f"AutViam profile dependency is missing: {profile}")
    for required in metadata["profile"]["required_files"]:
        if not (profile / required).is_file():
            raise BootstrapError(
                f"AutViam profile dependency is incomplete: {profile / required}"
            )
    return {
        "id": metadata["profile"]["id"],
        "path": str(profile),
        "sha256": tree_hash(profile),
    }


def require_whatter(command: str) -> str:
    candidate = Path(command)
    if candidate.is_absolute() or "/" in command:
        available = candidate.is_file() and candidate.stat().st_mode & 0o111
    else:
        available = shutil.which(command) is not None
    if not available:
        raise BootstrapError(
            f"Whatter dependency is unavailable: {command}. Install/configure Whatter; no fallback is selected."
        )
    return command


def explicit_legacy(
    metadata: dict[str, Any],
    facade: str,
    arguments: list[str],
    *,
    today: date | None = None,
    cutover: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cutover = cutover or load_cutover(metadata)
    if not arguments:
        raise BootstrapError("`legacy` requires the old command to invoke explicitly.")
    available_until = metadata["compatibility"]["legacy_available_until"]
    try:
        expires_on = date.fromisoformat(available_until)
    except (TypeError, ValueError) as exc:
        raise BootstrapError(
            "AutViam legacy compatibility metadata has an invalid end date."
        ) from exc
    if (today or date.today()) > expires_on:
        raise BootstrapError(
            f"AutViam legacy compatibility window ended on {available_until}; migrate to the profile-backed workflow."
        )
    legacy = SHARED_ROOT / metadata["compatibility"]["legacy_skills"][facade]
    if not legacy.is_file():
        raise BootstrapError(f"Explicit legacy invocation is unavailable: {legacy}")
    return {
        "mode": "explicit-legacy",
        "facade": facade,
        "legacy_command": arguments[0],
        "legacy_skill": str(legacy),
        "available_until": available_until,
        "legacy_freeze": cutover["legacy"]["freeze_policy"],
        "cutover": cutover_summary(cutover),
    }


def bootstrap(
    *,
    facade: str,
    skill_root: str,
    command: str,
    arguments: list[str],
    whatter: str | None,
    profile_dir: str | None,
) -> dict[str, Any]:
    metadata = load_metadata()
    cutover = load_cutover(metadata)
    expected_skill = "AutViam" if facade == "claude" else "AutViam_C"
    if Path(skill_root).name != expected_skill:
        raise BootstrapError(
            f"{facade} façade must use the {expected_skill} skill root."
        )
    if command == "legacy":
        return explicit_legacy(metadata, facade, arguments, cutover=cutover)
    if cutover["selection"]["default_for_new_projects"] == "legacy":
        legacy = explicit_legacy(
            metadata, facade, [command, *arguments], cutover=cutover
        )
        legacy["mode"] = "rollback-legacy-default"
        return legacy
    if command in metadata["obsolete_commands"]:
        raise BootstrapError(
            f"`{command}` has obsolete scheduler/gate semantics. Explicitly invoke `legacy {command}` through the compatibility window, or migrate to `run`, `review`, `close`, and `delivery`."
        )
    if command in metadata["unavailable_commands"]:
        raise BootstrapError(
            f"`{command}` is not mapped because {metadata['unavailable_commands'][command]} "
            "Use the profile-backed workflow once that Whatter CLI surface is available; no substitute is selected."
        )
    if command not in metadata["commands"]:
        supported = ", ".join(metadata["commands"])
        raise BootstrapError(
            f"Unsupported AutViam façade command `{command}`. Supported commands: {supported}."
        )
    profile = resolve_profile(metadata, profile_dir)
    executable = require_whatter(whatter or metadata["whatter"]["executable"])
    return {
        "mode": "whatter-command",
        "facade": facade,
        "cutover": cutover_summary(cutover),
        "profile": profile,
        "whatter_invocation": {
            "argv": [executable, *metadata["commands"][command], *arguments],
            "env": {PROFILE_ENV_VAR: profile["path"]},
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--facade", choices=("claude", "codex"), required=True)
    parser.add_argument("--skill-root", required=True)
    parser.add_argument("--command", required=True)
    parser.add_argument("--whatter")
    parser.add_argument("--profile-dir")
    parser.add_argument("arguments", nargs="*")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = bootstrap(
            facade=args.facade,
            skill_root=args.skill_root,
            command=args.command,
            arguments=args.arguments,
            whatter=args.whatter,
            profile_dir=args.profile_dir,
        )
    except BootstrapError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
