#!/usr/bin/env python3
"""
Install AutViam_C runtime Codex agent profiles from the bundled Markdown sources.

Expected location:
    <skill_root>/scripts/install_agent_profiles.py

Canonical sources:
    <skill_root>/agents/autviam-implementer.md
    <skill_root>/agents/autviam-phase-orchestrator.md
    <skill_root>/agents/autviam-spec-reviewer.md
    <skill_root>/agents/autviam-domain-reviewer.md
    <skill_root>/agents/autviam-explorer.md
    <skill_root>/agents/autviam-search.md

Generated runtime profiles:
    <repo_root>/.codex/agents/*.toml

Python 3.11+; no third-party dependencies.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

try:
    import tomllib
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit("Python 3.11+ is required (tomllib is used).") from exc

GENERATOR_ID = "AutViam_C/install_agent_profiles.py"
MANAGED_MARKER = f"# AUTVIAM_C_GENERATED_AGENT_PROFILE: {GENERATOR_ID}"
MANIFEST_NAME = "autviam-c-agent-manifest.json"
LEGACY_PROFILE_FILENAMES = (
    "reviewer-terra-high.toml",
    "reviewer-sol-high.toml",
    "reviewer-sol-xhigh.toml",
)

SOURCE_FILES = {
    "implementer": "autviam-implementer.md",
    "orchestrator": "autviam-phase-orchestrator.md",
    "spec_reviewer": "autviam-spec-reviewer.md",
    "domain_reviewer": "autviam-domain-reviewer.md",
    "explorer": "autviam-explorer.md",
    "search": "autviam-search.md",
}


class InstallError(RuntimeError):
    pass


@dataclass(frozen=True)
class MarkdownProfile:
    path: Path
    name: str
    description: str
    body: str
    sha256: str


@dataclass(frozen=True)
class RuntimeProfileSpec:
    filename: str
    name: str
    source: str
    role: str
    model_family: str
    effort: str
    sandbox_mode: str
    description: str


PROFILE_SPECS: tuple[RuntimeProfileSpec, ...] = (
    RuntimeProfileSpec("worker-terra-medium.toml", "worker_terra_medium", "implementer", "implementer", "terra", "medium", "workspace-write", "AutViam_C implementation worker for routine, low-risk tasks."),
    RuntimeProfileSpec("worker-terra-high.toml", "worker_terra_high", "implementer", "implementer", "terra", "high", "workspace-write", "AutViam_C implementation worker for moderate-complexity or moderate-risk tasks."),
    RuntimeProfileSpec("worker-sol-high.toml", "worker_sol_high", "implementer", "implementer", "sol", "high", "workspace-write", "AutViam_C implementation worker for elevated-complexity or elevated-risk tasks."),
    RuntimeProfileSpec("worker-sol-xhigh.toml", "worker_sol_xhigh", "implementer", "implementer", "sol", "xhigh", "workspace-write", "AutViam_C implementation worker for critical or exceptionally difficult tasks."),
    RuntimeProfileSpec("orchestrator-terra-medium.toml", "orchestrator_terra_medium", "orchestrator", "orchestrator", "terra", "medium", "workspace-write", "AutViam_C phase orchestrator for routine, low-risk phases."),
    RuntimeProfileSpec("orchestrator-terra-high.toml", "orchestrator_terra_high", "orchestrator", "orchestrator", "terra", "high", "workspace-write", "AutViam_C phase orchestrator for moderate-complexity or moderate-risk phases."),
    RuntimeProfileSpec("orchestrator-sol-high.toml", "orchestrator_sol_high", "orchestrator", "orchestrator", "sol", "high", "workspace-write", "AutViam_C phase orchestrator for elevated-complexity or elevated-risk phases."),
    RuntimeProfileSpec("orchestrator-sol-xhigh.toml", "orchestrator_sol_xhigh", "orchestrator", "orchestrator", "sol", "xhigh", "workspace-write", "AutViam_C phase orchestrator for critical or exceptionally difficult phases."),
    RuntimeProfileSpec("spec-reviewer-terra-high.toml", "spec_reviewer_terra_high", "spec_reviewer", "spec_reviewer", "terra", "high", "read-only", "AutViam_C read-only Gate A reviewer for routine work."),
    RuntimeProfileSpec("spec-reviewer-sol-high.toml", "spec_reviewer_sol_high", "spec_reviewer", "spec_reviewer", "sol", "high", "read-only", "AutViam_C read-only Gate A reviewer for moderate and elevated work."),
    RuntimeProfileSpec("spec-reviewer-sol-xhigh.toml", "spec_reviewer_sol_xhigh", "spec_reviewer", "spec_reviewer", "sol", "xhigh", "read-only", "AutViam_C read-only Gate A reviewer for critical work."),
    RuntimeProfileSpec("domain-reviewer-terra-high.toml", "domain_reviewer_terra_high", "domain_reviewer", "domain_reviewer", "terra", "high", "read-only", "AutViam_C read-only Gate B reviewer for routine work."),
    RuntimeProfileSpec("domain-reviewer-sol-high.toml", "domain_reviewer_sol_high", "domain_reviewer", "domain_reviewer", "sol", "high", "read-only", "AutViam_C read-only Gate B reviewer for moderate and elevated work."),
    RuntimeProfileSpec("domain-reviewer-sol-xhigh.toml", "domain_reviewer_sol_xhigh", "domain_reviewer", "domain_reviewer", "sol", "xhigh", "read-only", "AutViam_C read-only Gate B reviewer for critical work."),
    RuntimeProfileSpec("explorer-terra-medium.toml", "explorer_terra_medium", "explorer", "explorer", "terra", "medium", "read-only", "Read-only repository explorer for routine evidence gathering."),
    RuntimeProfileSpec("explorer-terra-high.toml", "explorer_terra_high", "explorer", "explorer", "terra", "high", "read-only", "Read-only repository explorer for interpretive or moderate-risk analysis."),
    RuntimeProfileSpec("explorer-sol-high.toml", "explorer_sol_high", "explorer", "explorer", "sol", "high", "read-only", "Read-only specialist for elevated-complexity or elevated-risk analysis."),
    RuntimeProfileSpec("explorer-sol-xhigh.toml", "explorer_sol_xhigh", "explorer", "explorer", "sol", "xhigh", "read-only", "Read-only specialist for critical or exceptionally difficult analysis."),
    RuntimeProfileSpec("search-luna-medium.toml", "search_luna_medium", "search", "search", "luna", "medium", "read-only", "Bounded mechanical read-only search, extraction, indexing, and classification."),
)

PINNED_MODELS = {
    "sol": "gpt-5.6-sol",
    "terra": "gpt-5.6-terra",
    "luna": "gpt-5.6-luna",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install generated AutViam_C Codex runtime agent profiles.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--skill-root", type=Path, help="AutViam_C skill root; defaults to this script's parent.parent.")
    parser.add_argument("--repo-root", type=Path, help="Host repo root; defaults to git root, then cwd.")
    parser.add_argument("--output-dir", type=Path, help="Defaults to <repo-root>/.codex/agents.")
    parser.add_argument("--on-conflict", choices=("fail", "new", "skip"), default="new", help="Handling for an unmanaged target file.")
    parser.add_argument("--force-unmanaged", action="store_true", help="Deliberately overwrite unmanaged target profiles.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--manifest-name", default=MANIFEST_NAME)
    parser.add_argument("--json", action="store_true", help="Print the report as JSON.")
    return parser.parse_args(argv)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_text(path: Path) -> str:
    if not path.is_file():
        raise InstallError(f"Required file not found: {path}")
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise InstallError(f"Could not read {path}: {exc}") from exc


def unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        if value[0] == '"':
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value[1:-1]
        return value[1:-1].replace("''", "'")
    return value


def parse_markdown_profile(path: Path) -> MarkdownProfile:
    text = read_text(path)
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise InstallError(f"{path}: expected YAML frontmatter beginning with '---'.")

    closing = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if closing is None:
        raise InstallError(f"{path}: unterminated YAML frontmatter.")

    metadata: dict[str, str] = {}
    for line_number, line in enumerate(lines[1:closing], start=2):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in line:
            raise InstallError(f"{path}:{line_number}: unsupported frontmatter line {line!r}.")
        key, value = line.split(":", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", key):
            raise InstallError(f"{path}:{line_number}: invalid frontmatter key {key!r}.")
        metadata[key] = unquote(value)

    name = metadata.get("name", "").strip()
    description = metadata.get("description", "").strip()
    body = "\n".join(lines[closing + 1:]).strip() + "\n"

    if not name:
        raise InstallError(f"{path}: frontmatter field 'name' is required.")
    if not description:
        raise InstallError(f"{path}: frontmatter field 'description' is required.")
    if metadata.get("agent_source", "").lower() != "true":
        raise InstallError(f"{path}: canonical source must declare agent_source: true.")
    if not body.strip():
        raise InstallError(f"{path}: profile body is empty.")

    return MarkdownProfile(path.resolve(), name, description, body, sha256_text(text))


def infer_skill_root(argument: Path | None) -> Path:
    return argument.resolve() if argument else Path(__file__).resolve().parent.parent


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


def load_sources(skill_root: Path) -> dict[str, MarkdownProfile]:
    sources = {
        key: parse_markdown_profile(skill_root / "agents" / filename)
        for key, filename in SOURCE_FILES.items()
    }
    expected_names = {key: f"autviam-{key.replace('_', '-')}" for key in SOURCE_FILES}
    expected_names["orchestrator"] = "autviam-phase-orchestrator"
    for key, expected_name in expected_names.items():
        if sources[key].name != expected_name:
            raise InstallError(
                f"{sources[key].path}: expected canonical source name={expected_name!r}, "
                f"found {sources[key].name!r}."
            )
    return sources


def toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def toml_instructions(value: str) -> str:
    normalized = value.rstrip() + "\n"
    triple_single = "'" * 3
    if triple_single not in normalized:
        return triple_single + "\n" + normalized + triple_single
    return toml_string(normalized)


def render_profile(spec: RuntimeProfileSpec, models: Mapping[str, str], sources: Mapping[str, MarkdownProfile], skill_root: Path) -> str:
    try:
        source = sources[spec.source]
    except KeyError as exc:
        raise InstallError(f"Unsupported canonical source: {spec.source}") from exc
    instructions = source.body
    source_path = source.path.relative_to(skill_root).as_posix()
    return "\n".join([
        MANAGED_MARKER,
        f"# canonical_source = {source_path}",
        f"# source_sha256 = {source.sha256}",
        "# Do not hand-edit unless you intentionally take ownership of this file.",
        "",
        f"name = {toml_string(spec.name)}",
        f"description = {toml_string(spec.description)}",
        f"model = {toml_string(models[spec.model_family])}",
        f"model_reasoning_effort = {toml_string(spec.effort)}",
        f"sandbox_mode = {toml_string(spec.sandbox_mode)}",
        "",
        "developer_instructions = " + toml_instructions(instructions),
        "",
    ])


def validate_rendered(spec: RuntimeProfileSpec, text: str, models: Mapping[str, str]) -> None:
    try:
        parsed = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise InstallError(f"{spec.filename}: generated invalid TOML: {exc}") from exc

    expected = {
        "name": spec.name,
        "description": spec.description,
        "model": models[spec.model_family],
        "model_reasoning_effort": spec.effort,
        "sandbox_mode": spec.sandbox_mode,
    }
    for key, expected_value in expected.items():
        if parsed.get(key) != expected_value:
            raise InstallError(f"{spec.filename}: expected {key}={expected_value!r}, found {parsed.get(key)!r}.")

    if not isinstance(parsed.get("developer_instructions"), str) or not parsed["developer_instructions"].strip():
        raise InstallError(f"{spec.filename}: developer_instructions is missing.")
    if spec.role in {"spec_reviewer", "domain_reviewer", "explorer", "search"} and parsed["sandbox_mode"] != "read-only":
        raise InstallError(f"{spec.filename}: read-only role has a writable sandbox.")
    if spec.role == "search":
        if parsed["model"] != models["luna"] or parsed["model_reasoning_effort"] != "medium":
            raise InstallError(f"{spec.filename}: Luna search route is misconfigured.")
    elif parsed["model"] == models["luna"]:
        raise InstallError(f"{spec.filename}: Luna is forbidden outside the search profile.")


def is_managed(path: Path) -> bool:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return MANAGED_MARKER in "".join(handle.readline() for _ in range(4))
    except OSError:
        return False


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def install_profiles(output_dir: Path, generated: Mapping[str, str], args: argparse.Namespace) -> tuple[list[dict[str, str]], bool]:
    actions: list[dict[str, str]] = []
    incomplete = False

    for filename, content in generated.items():
        target = output_dir / filename
        destination = target

        if not target.exists():
            action = "create"
        elif is_managed(target) or args.force_unmanaged:
            if read_text(target) == content:
                actions.append({"file": str(target), "action": "unchanged", "sha256": sha256_text(content)})
                continue
            action = "update"
        else:
            incomplete = True
            if args.on_conflict == "fail":
                raise InstallError(f"Refusing to overwrite unmanaged agent profile: {target}")
            if args.on_conflict == "skip":
                actions.append({"file": str(target), "action": "conflict-skipped", "sha256": sha256_text(content)})
                continue
            destination = target.with_name(target.name + ".new")
            action = "conflict-new"

        if not args.dry_run:
            atomic_write(destination, content)
        actions.append({"file": str(destination), "action": f"would-{action}" if args.dry_run else action, "sha256": sha256_text(content)})

    return actions, incomplete


def retire_legacy_profiles(output_dir: Path, dry_run: bool) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    for filename in LEGACY_PROFILE_FILENAMES:
        path = output_dir / filename
        if not path.exists() or not is_managed(path):
            continue
        digest = sha256_text(read_text(path))
        if not dry_run:
            path.unlink()
        actions.append(
            {
                "file": str(path),
                "action": "would-retire" if dry_run else "retire",
                "sha256": digest,
            }
        )
    return actions


def validate_installed(
    output_dir: Path,
    models: Mapping[str, str],
    generated: Mapping[str, str],
) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    failures: list[str] = []
    for spec in PROFILE_SPECS:
        path = output_dir / spec.filename
        if not path.is_file():
            failures.append(f"missing: {path}")
            continue
        if not is_managed(path):
            failures.append(f"unmanaged: {path}")
            continue
        actual = read_text(path)
        try:
            validate_rendered(spec, actual, models)
        except InstallError as exc:
            failures.append(str(exc))
            continue
        if actual != generated[spec.filename]:
            failures.append(
                f"managed profile content differs from its bundled source rendering: {path}"
            )
            continue
        results.append({"file": str(path), "action": "validated", "sha256": sha256_text(actual)})
    if failures:
        raise InstallError("Installed profile validation failed:\n  " + "\n  ".join(failures))
    return results


def make_report(skill_root: Path, repo_root: Path, output_dir: Path, sources: Mapping[str, MarkdownProfile], models: Mapping[str, str], actions: list[dict[str, str]], incomplete: bool) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "generator": GENERATOR_ID,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "skill_root": str(skill_root),
        "repo_root": str(repo_root),
        "output_dir": str(output_dir),
        "complete": not incomplete,
        "models": dict(models),
        "sources": {
            key: {
                "path": str(profile.path),
                "name": profile.name,
                "description": profile.description,
                "agent_source": True,
                "sha256": profile.sha256,
            }
            for key, profile in sources.items()
        },
        "profiles": [
            {
                "file": spec.filename,
                "name": spec.name,
                "source": spec.source,
                "role": spec.role,
                "model": models[spec.model_family],
                "model_reasoning_effort": spec.effort,
                "sandbox_mode": spec.sandbox_mode,
            }
            for spec in PROFILE_SPECS
        ],
        "actions": actions,
    }


def emit(report: Mapping[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return
    print("AutViam_C runtime agent profiles")
    print(f"  output : {report['output_dir']}")
    print(f"  status : {'complete' if report['complete'] else 'incomplete'}")
    print(f"  count  : {len(report['profiles'])}\n")
    for action in report["actions"]:
        print(f"  {action['action']:<18} {action['file']}")
    if not report["complete"]:
        print("\nUnmanaged conflicts were not overwritten. Review the .new files or rerun with --force-unmanaged.", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    skill_root = infer_skill_root(args.skill_root)
    repo_root = infer_repo_root(args.repo_root)
    output_dir = args.output_dir.resolve() if args.output_dir else repo_root / ".codex" / "agents"
    models = PINNED_MODELS

    sources = load_sources(skill_root)
    generated: dict[str, str] = {}
    for spec in PROFILE_SPECS:
        text = render_profile(spec, models, sources, skill_root)
        validate_rendered(spec, text, models)
        generated[spec.filename] = text

    if args.validate_only:
        actions = validate_installed(output_dir, models, generated)
        report = {
            "schema_version": 1,
            "generator": GENERATOR_ID,
            "output_dir": str(output_dir),
            "complete": True,
            "profiles": [{"file": s.filename, "name": s.name, "source": s.source, "role": s.role, "model": models[s.model_family], "model_reasoning_effort": s.effort, "sandbox_mode": s.sandbox_mode} for s in PROFILE_SPECS],
            "actions": actions,
        }
        emit(report, args.json)
        return 0

    actions, incomplete = install_profiles(output_dir, generated, args)
    if not incomplete:
        if not args.dry_run:
            validate_installed(output_dir, models, generated)
        actions.extend(retire_legacy_profiles(output_dir, args.dry_run))
    report = make_report(skill_root, repo_root, output_dir, sources, models, actions, incomplete)

    if not args.dry_run:
        manifest_path = output_dir / args.manifest_name
        manifest_text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        if manifest_path.exists() and not args.force_unmanaged:
            try:
                existing = json.loads(read_text(manifest_path))
            except (json.JSONDecodeError, InstallError):
                existing = {}
            if existing.get("generator") != GENERATOR_ID:
                conflict = manifest_path.with_name(manifest_path.name + ".new")
                atomic_write(conflict, manifest_text)
                report["complete"] = False
                report["actions"].append({"file": str(conflict), "action": "conflict-new", "sha256": sha256_text(manifest_text)})
            else:
                atomic_write(manifest_path, manifest_text)
        else:
            atomic_write(manifest_path, manifest_text)

    emit(report, args.json)
    return 3 if not report["complete"] else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except InstallError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
