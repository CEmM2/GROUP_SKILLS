#!/usr/bin/env python3
"""Generate and safely install the 22 managed AutViam Claude agent profiles."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import secrets
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from claude_routing_common import (
    RoutingCommonError,
    atomic_write_json,
    atomic_write_text,
    load_json,
    normalize_config,
    parse_frontmatter,
    parse_frontmatter_text,
    sha256_text,
)


GENERATOR = "AutViam/install_claude_agent_profiles.py"
MANAGED_MARKER = f"<!-- AUTVIAM_GENERATED_AGENT_PROFILE: {GENERATOR} -->"
MANIFEST_NAME = "autviam-claude-agent-manifest.json"
LEGACY_NAMES = (
    "autviam-spec-reviewer.md",
    "autviam-domain-reviewer.md",
    "autviam-phase-orchestrator.md",
)


@dataclass(frozen=True)
class ProfileSpec:
    name: str
    source: str
    role: str
    model: str
    effort: str | None
    capability: str
    tools: str
    description: str


READ_TOOLS = "Read, Grep, Glob, Bash"
WRITE_TOOLS = "Read, Grep, Glob, Bash, Edit, Write"
EXPLORER_NAMES = [
    "autviam-explorer-sonnet-medium",
    "autviam-explorer-sonnet-high",
    "autviam-explorer-opus-high",
    "autviam-explorer-opus-xhigh",
]
IMPLEMENTER_NAMES = [
    "autviam-implementer-sonnet-medium",
    "autviam-implementer-sonnet-high",
    "autviam-implementer-opus-high",
    "autviam-implementer-opus-xhigh",
]
SPEC_NAMES = [
    "autviam-spec-reviewer-sonnet-high",
    "autviam-spec-reviewer-opus-high",
    "autviam-spec-reviewer-opus-xhigh",
]
DOMAIN_NAMES = [
    f"autviam-domain-reviewer-{tier}-{capability}"
    for tier in ("sonnet-high", "opus-high", "opus-xhigh")
    for capability in ("flat", "nested")
]


def agent_tool(names: list[str]) -> str:
    return f"Agent({', '.join(names)})"


def profile_specs() -> tuple[ProfileSpec, ...]:
    tiers = (
        ("sonnet-medium", "sonnet", "medium"),
        ("sonnet-high", "sonnet", "high"),
        ("opus-high", "opus", "high"),
        ("opus-xhigh", "opus", "xhigh"),
    )
    specs: list[ProfileSpec] = []
    for suffix, model, effort in tiers:
        specs.append(ProfileSpec(f"autviam-implementer-{suffix}", "implementer", "implementer", model, effort, "leaf", WRITE_TOOLS, f"AutViam implementation worker ({model}, {effort})."))
        specs.append(ProfileSpec(f"autviam-phase-orchestrator-{suffix}", "phase_orchestrator", "orchestrator", model, effort, "nested", f"{WRITE_TOOLS}, {agent_tool(IMPLEMENTER_NAMES + SPEC_NAMES + DOMAIN_NAMES)}", f"AutViam phase orchestrator ({model}, {effort})."))
        specs.append(ProfileSpec(f"autviam-explorer-{suffix}", "explorer", "explorer", model, effort, "leaf", READ_TOOLS, f"AutViam read-only specialist ({model}, {effort})."))
    for suffix, model, effort in tiers[1:]:
        specs.append(ProfileSpec(f"autviam-spec-reviewer-{suffix}", "spec_reviewer", "spec_reviewer", model, effort, "leaf", READ_TOOLS, f"AutViam Gate A reviewer ({model}, {effort})."))
        for capability in ("flat", "nested"):
            tools = READ_TOOLS if capability == "flat" else f"{READ_TOOLS}, {agent_tool(EXPLORER_NAMES)}"
            specs.append(ProfileSpec(f"autviam-domain-reviewer-{suffix}-{capability}", "domain_reviewer", "domain_reviewer", model, effort, capability, tools, f"AutViam Gate B {capability} reviewer ({model}, {effort})."))
    specs.append(ProfileSpec("autviam-search-haiku", "search", "mechanical_read_only", "haiku", None, "leaf", READ_TOOLS, "AutViam bounded mechanical read-only search agent."))
    return tuple(specs)


PROFILE_SPECS = profile_specs()
SOURCE_FILES = {
    "implementer": "autviam-implementer.md",
    "phase_orchestrator": "autviam-phase-orchestrator.md",
    "spec_reviewer": "autviam-spec-reviewer.md",
    "domain_reviewer": "autviam-domain-reviewer.md",
    "explorer": "autviam-explorer.md",
    "search": "autviam-search.md",
}


class InstallError(RuntimeError):
    pass


def infer_repo_root(argument: Path | None) -> Path:
    if argument:
        return argument.resolve()
    try:
        result = subprocess.run(["git", "rev-parse", "--show-toplevel"], check=True, capture_output=True, text=True)
        if result.stdout.strip():
            return Path(result.stdout.strip()).resolve()
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    return Path.cwd().resolve()


def load_sources(skill_root: Path) -> dict[str, tuple[str, str]]:
    sources: dict[str, tuple[str, str]] = {}
    for key, filename in SOURCE_FILES.items():
        path = skill_root / "agents" / filename
        metadata, body = parse_frontmatter(path)
        if metadata.get("agent_source") != "true":
            raise InstallError(f"{path}: canonical source must declare agent_source: true")
        sources[key] = (path.read_text(encoding="utf-8"), body)
    return sources


def capability_prelude(spec: ProfileSpec) -> str:
    if spec.role == "domain_reviewer":
        if spec.capability == "flat":
            return "Generated capability: flat. Never call Agent; consume caller specialist reports or apply prompt lenses inline."
        return "Generated capability: nested. Resolve explorer children with tickets and use only the frontmatter Agent allowlist when verified runtime depth remains."
    if spec.role == "orchestrator":
        return "Generated capability: orchestrator. Resolve every child and include its routing ticket; never use an unlisted child agent."
    return "Generated capability: leaf. Do not call Agent or create subagents."


def render_profile(spec: ProfileSpec, sources: Mapping[str, tuple[str, str]]) -> str:
    source_text, body = sources[spec.source]
    frontmatter = [
        "---",
        f"name: {spec.name}",
        f"description: {spec.description}",
        f"model: {spec.model}",
    ]
    if spec.effort is not None:
        frontmatter.append(f"effort: {spec.effort}")
    frontmatter.extend([f"tools: {spec.tools}", "---", MANAGED_MARKER])
    source_hash = sha256_text(source_text)
    return "\n".join(frontmatter) + f"\n<!-- source_sha256: {source_hash} -->\n\n{capability_prelude(spec)}\n\n{body}"


def validate_profile(spec: ProfileSpec, text: str) -> None:
    metadata, body = parse_frontmatter_text(text, spec.name)
    expected = {
        "name": spec.name,
        "description": spec.description,
        "model": spec.model,
        "tools": spec.tools,
    }
    if spec.effort is not None:
        expected["effort"] = spec.effort
    for key, value in expected.items():
        if metadata.get(key) != value:
            raise InstallError(f"{spec.name}: expected {key}={value!r}, found {metadata.get(key)!r}")
    if spec.effort is None and "effort" in metadata:
        raise InstallError(f"{spec.name}: Haiku profile must omit effort")
    if not body.strip() or MANAGED_MARKER not in body:
        raise InstallError(f"{spec.name}: missing managed body")
    has_agent = "Agent(" in spec.tools or spec.tools.split(", ").count("Agent") > 0
    if spec.capability in {"leaf", "flat"} and has_agent:
        raise InstallError(f"{spec.name}: leaf/flat profile exposes Agent")
    if spec.capability == "nested" and "Agent(" not in spec.tools:
        raise InstallError(f"{spec.name}: nested profile lacks a restricted Agent allowlist")


def generated_profiles(skill_root: Path) -> dict[str, str]:
    sources = load_sources(skill_root)
    generated: dict[str, str] = {}
    for spec in PROFILE_SPECS:
        text = render_profile(spec, sources)
        validate_profile(spec, text)
        generated[f"{spec.name}.md"] = text
    return generated


def validate_policy_compatibility(policy: Mapping[str, Any]) -> None:
    models = policy.get("models")
    if not isinstance(models, dict):
        raise InstallError("Claude routing policy has no model catalog")
    if len(PROFILE_SPECS) != 22:
        raise InstallError("installer must define exactly 22 generated profiles")
    for spec in PROFILE_SPECS:
        model = models.get(spec.model)
        if not isinstance(model, dict) or model.get("value") != spec.model:
            raise InstallError(f"{spec.name}: model {spec.model!r} is absent from the routing policy")
        supported = model.get("supported_efforts")
        if not isinstance(supported, list):
            raise InstallError(f"{spec.name}: policy effort catalog is invalid")
        if spec.effort is not None and spec.effort not in supported:
            raise InstallError(f"{spec.name}: effort {spec.effort!r} is unsupported by {spec.model}")
        if spec.effort is None and spec.model != "haiku":
            raise InstallError(f"{spec.name}: only Haiku may omit effort")


def is_managed(path: Path) -> bool:
    try:
        return MANAGED_MARKER in path.read_text(encoding="utf-8")
    except OSError:
        return False


def install(output_dir: Path, generated: Mapping[str, str], dry_run: bool, force_unmanaged: bool) -> tuple[list[dict[str, str]], bool]:
    actions: list[dict[str, str]] = []
    incomplete = False
    for filename, text in generated.items():
        target = output_dir / filename
        destination = target
        if target.exists() and not is_managed(target) and not force_unmanaged:
            destination = target.with_name(target.name + ".new")
            action = "conflict-new"
            incomplete = True
        elif target.exists() and target.read_text(encoding="utf-8") == text:
            actions.append({"file": str(target), "action": "unchanged"})
            continue
        else:
            action = "update" if target.exists() else "create"
        if not dry_run:
            atomic_write_text(destination, text)
        actions.append({"file": str(destination), "action": f"would-{action}" if dry_run else action})
    return actions, incomplete


def validate_installed(output_dir: Path, generated: Mapping[str, str]) -> list[dict[str, str]]:
    failures: list[str] = []
    results: list[dict[str, str]] = []
    for spec in PROFILE_SPECS:
        path = output_dir / f"{spec.name}.md"
        if not path.is_file():
            failures.append(f"missing: {path}")
            continue
        actual = path.read_text(encoding="utf-8")
        try:
            validate_profile(spec, actual)
        except (InstallError, RoutingCommonError) as exc:
            failures.append(str(exc))
            continue
        if actual != generated[path.name]:
            failures.append(f"managed profile differs from canonical source rendering: {path}")
            continue
        results.append({"file": str(path), "action": "validated"})
    if failures:
        raise InstallError("installed profile validation failed:\n  " + "\n  ".join(failures))
    return results


def migrate_config(path: Path, dry_run: bool) -> dict[str, Any]:
    original = load_json(path, "AutViam config") if path.exists() else {}
    normalized = normalize_config(original)
    if not dry_run:
        atomic_write_json(path, normalized)
    return normalized


def ensure_ticket_key(repo_root: Path, dry_run: bool) -> Path:
    key_path = repo_root / ".claude" / "autviam-routing" / "ticket.key"
    ignore_path = key_path.parent / ".gitignore"
    ignore_entries = ("ticket.key", "tickets/", "subagent-start.jsonl", "probe-*.json")
    if not dry_run:
        existing = ignore_path.read_text(encoding="utf-8").splitlines() if ignore_path.exists() else []
        updated = [*existing, *(entry for entry in ignore_entries if entry not in existing)]
        atomic_write_text(ignore_path, "\n".join(updated) + "\n")
    if key_path.exists():
        if not key_path.is_file():
            raise InstallError(f"routing ticket key path is not a file: {key_path}")
        if not dry_run:
            os.chmod(key_path, 0o600)
        return key_path
    if not dry_run:
        atomic_write_text(key_path, secrets.token_hex(32) + "\n")
        os.chmod(key_path, 0o600)
    return key_path


def install_hook(
    repo_root: Path,
    skill_root: Path,
    output_dir: Path,
    config_path: Path,
    ticket_key: Path,
    dry_run: bool,
) -> None:
    settings_path = repo_root / ".claude" / "settings.json"
    settings = load_json(settings_path, "Claude settings") if settings_path.exists() else {}
    hooks = settings.setdefault("hooks", {})
    pre = hooks.setdefault("PreToolUse", [])
    ticket_dir = repo_root / ".claude" / "autviam-routing" / "tickets"
    command = (
        f'python3 "{skill_root / "scripts" / "validate_agent_dispatch.py"}" '
        f'--policy "{skill_root / "references" / "claude-agent-routing.json"}" '
        f'--config "{config_path}" --agents-dir "{output_dir}" '
        f'--ticket-dir "{ticket_dir}" --ticket-key "{ticket_key}" --repo-root "{repo_root}"'
    )
    entry = {"matcher": "Agent", "hooks": [{"type": "command", "command": command, "timeout": 30}]}
    if entry not in pre:
        pre.append(entry)
    starts = hooks.setdefault("SubagentStart", [])
    audit_command = f'python3 "{skill_root / "scripts" / "audit_subagent_start.py"}"'
    audit_entry = {"matcher": "autviam-.*|routing-probe-.*", "hooks": [{"type": "command", "command": audit_command, "timeout": 30}]}
    if audit_entry not in starts:
        starts.append(audit_entry)
    if not dry_run:
        atomic_write_json(settings_path, settings)


def retire_legacy(output_dir: Path, dry_run: bool) -> list[str]:
    present = [output_dir / name for name in LEGACY_NAMES if (output_dir / name).exists()]
    if not present:
        return []
    backup = output_dir.parent / "autviam-routing" / "legacy-agent-backups" / dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    if not dry_run:
        backup.mkdir(parents=True, exist_ok=False)
        for path in present:
            shutil.move(str(path), backup / path.name)
    return [str(path) for path in present]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-root", type=Path)
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force-unmanaged", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--install-hook", action="store_true")
    parser.add_argument("--retire-legacy", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    skill_root = (args.skill_root or Path(__file__).resolve().parent.parent).resolve()
    repo_root = infer_repo_root(args.repo_root)
    output_dir = (args.output_dir or repo_root / ".claude" / "agents").resolve()
    policy_path = skill_root / "references" / "claude-agent-routing.json"
    policy = load_json(policy_path, "Claude routing policy")
    validate_policy_compatibility(policy)
    generated = generated_profiles(skill_root)
    if args.validate_only:
        actions = validate_installed(output_dir, generated)
        report = {"complete": True, "profiles": len(PROFILE_SPECS), "actions": actions}
    else:
        actions, incomplete = install(output_dir, generated, args.dry_run, args.force_unmanaged)
        config_path = (args.config or skill_root / "autviam_config.json").resolve()
        config = migrate_config(config_path, args.dry_run)
        ticket_key = ensure_ticket_key(repo_root, args.dry_run)
        spawn_state = {
            "edges": policy.get("spawn_edges"),
            "nested_dispatch": config["nested_dispatch"],
        }
        if args.install_hook:
            install_hook(repo_root, skill_root, output_dir, config_path, ticket_key, args.dry_run)
        retired = retire_legacy(output_dir, args.dry_run) if args.retire_legacy and not incomplete else []
        report = {
            "schema_version": 1,
            "generator": GENERATOR,
            "complete": not incomplete,
            "profiles": len(PROFILE_SPECS),
            "output_dir": str(output_dir),
            "ticket_key": str(ticket_key),
            "routing_policy": {
                "path": str(policy_path.resolve()),
                "version": policy.get("policy_version"),
                "spawn_edges": policy.get("spawn_edges"),
                "spawn_policy_hash": sha256_text(json.dumps(spawn_state, sort_keys=True)),
            },
            "config": config,
            "actions": actions,
            "retired_legacy": retired,
            "restart_required": not args.dry_run,
        }
        if not args.dry_run:
            atomic_write_json(output_dir / MANIFEST_NAME, report)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"AutViam Claude profiles: {report['profiles']} ({'complete' if report['complete'] else 'incomplete'})")
        print("Restart or explicitly reload Claude Code after generation.")
    return 0 if report["complete"] else 3


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (InstallError, RoutingCommonError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
