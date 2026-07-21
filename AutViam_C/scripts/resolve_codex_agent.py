#!/usr/bin/env python3
"""Resolve and validate one AutViam_C Path-2 Codex agent route."""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping

try:
    import tomllib
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit("Python 3.11+ is required (tomllib is used).") from exc


BUILT_IN_AGENTS = {"default", "explorer", "worker"}
READ_ONLY_ROLES = {"domain_reviewer", "explorer", "mechanical_read_only", "spec_reviewer"}
WRITABLE_ROLES = {"implementer", "orchestrator"}
REQUIRED_PROFILE_FIELDS = {
    "description",
    "developer_instructions",
    "name",
    "model",
    "model_reasoning_effort",
    "sandbox_mode",
}
EXPECTED_PROFILE_CONFIG = {
    "terra_medium": ("gpt-5.6-terra", "medium"),
    "terra_high": ("gpt-5.6-terra", "high"),
    "sol_high": ("gpt-5.6-sol", "high"),
    "sol_xhigh": ("gpt-5.6-sol", "xhigh"),
    "luna_medium": ("gpt-5.6-luna", "medium"),
}
PURPOSE_ROLES = {
    "explore": {"explorer"},
    "gate-a": {"spec_reviewer"},
    "gate-b": {"domain_reviewer"},
    "implementer": {"implementer"},
    "mechanical-read-only": {"mechanical_read_only"},
    "nesting-probe": {"orchestrator", "spec_reviewer"},
    "phase-orchestrator": {"orchestrator"},
    "scaffold": {"implementer"},
    "specialist": {"explorer"},
}


class RoutingError(RuntimeError):
    """Raised when routing cannot be completed without a silent fallback."""


def skill_root() -> Path:
    return Path(__file__).resolve().parent.parent


def default_policy_path() -> Path:
    return skill_root() / "references" / "codex-agent-routing.json"


def default_agents_dir() -> Path:
    current_skill = skill_root()
    if current_skill.parent.name == "skills" and current_skill.parent.parent.name == ".codex":
        return current_skill.parent.parent / "agents"
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        )
        root = completed.stdout.strip()
        if root:
            return Path(root) / ".codex" / "agents"
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    return Path.cwd() / ".codex" / "agents"


def load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise RoutingError(f"{label} does not exist: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RoutingError(f"could not read {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RoutingError(f"{label} must contain a JSON object: {path}")
    return value


def validate_score(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5:
        raise RoutingError(f"{name} must be an integer from 1 to 5; found {value!r}")
    return value


def validate_policy(policy: Mapping[str, Any]) -> None:
    if policy.get("schema_version") != 1:
        raise RoutingError("routing policy schema_version must be 1")
    if not isinstance(policy.get("policy_version"), str) or not policy["policy_version"].strip():
        raise RoutingError("routing policy policy_version must be a non-empty string")

    score_keys = {str(value) for value in range(1, 6)}
    matrix = policy.get("base_tier_by_score")
    if not isinstance(matrix, dict) or set(matrix) != score_keys:
        raise RoutingError("base_tier_by_score must define exactly complexity scores 1 through 5")
    for complexity, row in matrix.items():
        if not isinstance(row, dict) or set(row) != score_keys:
            raise RoutingError(f"base_tier_by_score[{complexity!r}] must define risks 1 through 5")

    profiles = policy.get("profiles_by_role_and_tier")
    required_roles = {
        "domain_reviewer",
        "explorer",
        "implementer",
        "orchestrator",
        "spec_reviewer",
    }
    if not isinstance(profiles, dict) or set(profiles) != required_roles:
        raise RoutingError(f"profiles_by_role_and_tier must define exactly {sorted(required_roles)}")
    tiers = {value for row in matrix.values() for value in row.values()}
    for role, role_routes in profiles.items():
        if not isinstance(role_routes, dict) or set(role_routes) != tiers:
            raise RoutingError(f"profiles_by_role_and_tier[{role!r}] must define tiers {sorted(tiers)}")
        for agent in role_routes.values():
            if not isinstance(agent, str) or not agent or agent in BUILT_IN_AGENTS:
                raise RoutingError(f"role {role!r} selects forbidden or invalid agent {agent!r}")

    special = policy.get("special_routes", {}).get("mechanical_read_only")
    if not isinstance(special, dict):
        raise RoutingError("special_routes.mechanical_read_only is required")
    validate_score("maximum_complexity", special.get("maximum_complexity"))
    validate_score("maximum_risk", special.get("maximum_risk"))
    if special.get("fallback_role") != "explorer":
        raise RoutingError("mechanical_read_only fallback_role must be 'explorer'")
    if not isinstance(special.get("agent"), str) or special["agent"] in BUILT_IN_AGENTS:
        raise RoutingError("mechanical_read_only agent must name a custom profile")

    failure_policy = policy.get("failure_policy")
    required_failures = {
        "invalid_score",
        "missing_agent_profile",
        "missing_route",
        "unconfigured_model_or_effort",
        "unknown_role",
    }
    if not isinstance(failure_policy, dict) or set(failure_policy) != required_failures:
        raise RoutingError("failure_policy has missing or unexpected entries")
    if set(failure_policy.values()) != {"error"}:
        raise RoutingError("every failure_policy action must be 'error'")


def load_profiles(agents_dir: Path) -> dict[str, tuple[Path, dict[str, Any]]]:
    if not agents_dir.is_dir():
        raise RoutingError(
            f"Codex agents directory does not exist: {agents_dir}; run install_agent_profiles.py first"
        )
    profiles: dict[str, tuple[Path, dict[str, Any]]] = {}
    for path in sorted(agents_dir.glob("*.toml")):
        try:
            with path.open("rb") as handle:
                profile = tomllib.load(handle)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise RoutingError(f"invalid agent TOML {path}: {exc}") from exc
        name = profile.get("name")
        if not isinstance(name, str) or not name:
            continue
        if name in profiles:
            raise RoutingError(f"duplicate Codex agent profile name {name!r}: {profiles[name][0]} and {path}")
        profiles[name] = (path.resolve(), profile)
    return profiles


def validate_selected_profile(
    *,
    agent: str,
    role: str,
    complexity: int,
    risk: int,
    profiles: Mapping[str, tuple[Path, dict[str, Any]]],
) -> tuple[Path, dict[str, Any]]:
    if agent in BUILT_IN_AGENTS:
        raise RoutingError(f"routing selected forbidden built-in agent profile {agent!r}")
    if agent not in profiles:
        raise RoutingError(f"routing selected missing custom agent profile {agent!r}")
    path, profile = profiles[agent]
    missing = sorted(REQUIRED_PROFILE_FIELDS - profile.keys())
    if missing:
        raise RoutingError(f"agent profile {agent!r} omits required fields: {', '.join(missing)}")
    if profile["name"] != agent:
        raise RoutingError(f"agent profile {path} declares name {profile['name']!r}, expected {agent!r}")
    if not isinstance(profile["description"], str) or not profile["description"].strip():
        raise RoutingError(f"agent profile {agent!r} has no description")
    if not isinstance(profile["developer_instructions"], str) or not profile["developer_instructions"].strip():
        raise RoutingError(f"agent profile {agent!r} has no developer_instructions")
    if not isinstance(profile["model"], str) or not profile["model"].strip():
        raise RoutingError(f"agent profile {agent!r} has no explicit model")
    if profile["model_reasoning_effort"] not in {"medium", "high", "xhigh"}:
        raise RoutingError(f"agent profile {agent!r} has unsupported model_reasoning_effort")

    expected_config = next(
        (config for suffix, config in EXPECTED_PROFILE_CONFIG.items() if agent.endswith(suffix)),
        None,
    )
    if expected_config is None:
        raise RoutingError(f"agent profile {agent!r} has no recognized pinned configuration")
    expected_model, expected_effort = expected_config
    if profile["model"] != expected_model or profile["model_reasoning_effort"] != expected_effort:
        raise RoutingError(
            f"agent profile {agent!r} must pin model={expected_model!r} and "
            f"model_reasoning_effort={expected_effort!r}"
        )

    sandbox = profile["sandbox_mode"]
    if role in READ_ONLY_ROLES and sandbox != "read-only":
        raise RoutingError(f"read-only role {role!r} selected writable profile {agent!r}")
    if role in WRITABLE_ROLES and sandbox != "workspace-write":
        raise RoutingError(f"writable role {role!r} selected incompatible profile {agent!r}")

    uses_luna = profile["model"] == "gpt-5.6-luna"
    luna_allowed = role == "mechanical_read_only" and complexity <= 2 and risk <= 2
    if uses_luna != luna_allowed:
        state = "outside" if uses_luna else "inside"
        raise RoutingError(f"agent profile {agent!r} uses Luna {state} the bounded mechanical route")
    return path, profile


def resolve_route(
    policy: Mapping[str, Any],
    profiles: Mapping[str, tuple[Path, dict[str, Any]]],
    *,
    complexity: int,
    risk: int,
    role: str,
    task_id: str | None = None,
) -> dict[str, Any]:
    validate_policy(policy)
    complexity = validate_score("complexity", complexity)
    risk = validate_score("risk", risk)

    regular_roles = policy["profiles_by_role_and_tier"]
    special = policy["special_routes"]["mechanical_read_only"]
    supported_roles = set(regular_roles) | {"mechanical_read_only"}
    if role not in supported_roles:
        raise RoutingError(f"unknown role {role!r}; expected one of {sorted(supported_roles)}")

    tier = policy["base_tier_by_score"][str(complexity)][str(risk)]
    effective_role = role
    if role == "mechanical_read_only" and complexity <= special["maximum_complexity"] and risk <= special["maximum_risk"]:
        agent = special["agent"]
        tier = "luna_medium"
    else:
        if role == "mechanical_read_only":
            effective_role = special["fallback_role"]
        try:
            agent = regular_roles[effective_role][tier]
        except KeyError as exc:
            raise RoutingError(f"no route for role={role!r}, tier={tier!r}") from exc

    profile_path, profile = validate_selected_profile(
        agent=agent,
        role=role,
        complexity=complexity,
        risk=risk,
        profiles=profiles,
    )
    result = {
        "policy_version": policy["policy_version"],
        "complexity": complexity,
        "risk": risk,
        "combined": complexity + risk,
        "role": role,
        "effective_role": effective_role,
        "tier": tier,
        "agent": agent,
        "profile_path": str(profile_path),
        "model": profile["model"],
        "model_reasoning_effort": profile["model_reasoning_effort"],
        "sandbox_mode": profile["sandbox_mode"],
    }
    if task_id is not None:
        result["task_id"] = task_id
    return result


def scores_from_manifest(manifest_path: Path, policy: Mapping[str, Any]) -> tuple[int, int, str | None]:
    manifest = load_json(manifest_path, "task routing manifest")
    if manifest.get("schema_version") != 1:
        raise RoutingError("task routing manifest schema_version must be 1")
    complexity = validate_score("complexity", manifest.get("complexity"))
    risk = validate_score("risk", manifest.get("risk"))
    if manifest.get("combined") != complexity + risk:
        raise RoutingError("task routing manifest combined does not equal complexity + risk")
    if manifest.get("policy_version") != policy["policy_version"]:
        raise RoutingError("task routing manifest policy_version does not match the routing policy")
    task_id = manifest.get("task_id")
    if task_id is not None and (not isinstance(task_id, str) or not task_id.strip()):
        raise RoutingError("task routing manifest task_id must be a non-empty string")
    return complexity, risk, task_id


def scores_from_task_json(task_path: Path) -> tuple[int, int, str]:
    task = load_json(task_path, "task JSON")
    task_id = task.get("task_id")
    if not isinstance(task_id, str) or not task_id.strip():
        raise RoutingError("task JSON task_id must be a non-empty string")
    complexity = validate_score("complexity", task.get("complexity"))
    risk = validate_score("risk", task.get("risk"))
    return complexity, risk, task_id


@contextlib.contextmanager
def evidence_lock(path: Path, timeout_seconds: float = 30.0):
    """Serialize evidence updates with an atomic lock-directory acquisition."""
    lock_path = path.with_name(f".{path.name}.routing-lock")
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            lock_path.mkdir()
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise RoutingError(f"timed out acquiring routing evidence lock: {lock_path}")
            time.sleep(0.02)
    try:
        yield
    finally:
        try:
            lock_path.rmdir()
        except FileNotFoundError:
            pass


def write_routing_evidence(path: Path, purpose: str, result: Mapping[str, Any]) -> None:
    if not purpose.strip():
        raise RoutingError("routing evidence purpose must be non-empty")
    path.parent.mkdir(parents=True, exist_ok=True)
    with evidence_lock(path):
        if path.exists():
            document = load_json(path, "routing evidence target")
        else:
            document = {"schema_version": 1, "routing_evidence": []}

        for score_name in ("complexity", "risk"):
            stored_score = document.get(score_name)
            if stored_score is not None and stored_score != result[score_name]:
                raise RoutingError(
                    f"routing result {score_name}={result[score_name]} does not match "
                    f"evidence target {score_name}={stored_score}; route from the stored task JSON"
                )
        stored_task_id = document.get("task_id")
        result_task_id = result.get("task_id")
        if stored_task_id is not None:
            if result_task_id is None:
                raise RoutingError(
                    "routing evidence target is a task JSON; use --task-json so stored scores "
                    "and task_id cannot be bypassed"
                )
            if stored_task_id != result_task_id:
                raise RoutingError(
                    f"routing result task_id={result_task_id!r} does not match "
                    f"evidence target task_id={stored_task_id!r}"
                )

        evidence = document.setdefault("routing_evidence", [])
        if not isinstance(evidence, list):
            raise RoutingError(f"routing_evidence must be an array in {path}")
        evidence.append(
            {
                "dispatched_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "purpose": purpose,
                "resolver": dict(result),
            }
        )
        fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent), text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(document, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        except Exception:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise


def validate_purpose_role(purpose: str, role: str) -> None:
    allowed_roles = PURPOSE_ROLES.get(purpose)
    if allowed_roles is None:
        raise RoutingError(
            f"unknown routing evidence purpose {purpose!r}; expected one of {sorted(PURPOSE_ROLES)}"
        )
    if role not in allowed_roles:
        raise RoutingError(
            f"routing evidence purpose {purpose!r} requires role in {sorted(allowed_roles)}, "
            f"not {role!r}"
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, default=default_policy_path())
    parser.add_argument("--agents-dir", type=Path, default=default_agents_dir())
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--manifest", type=Path)
    inputs.add_argument("--task-json", type=Path)
    inputs.add_argument("--complexity", type=int)
    parser.add_argument("--risk", type=int)
    parser.add_argument("--role", required=True)
    parser.add_argument("--evidence-file", type=Path)
    parser.add_argument("--purpose")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    policy = load_json(args.policy.resolve(), "routing policy")
    validate_policy(policy)
    if args.manifest:
        if args.risk is not None:
            raise RoutingError("--risk cannot be combined with --manifest")
        complexity, risk, task_id = scores_from_manifest(args.manifest.resolve(), policy)
    elif args.task_json:
        if args.risk is not None:
            raise RoutingError("--risk cannot be combined with --task-json")
        complexity, risk, task_id = scores_from_task_json(args.task_json.resolve())
    else:
        if args.risk is None:
            raise RoutingError("--risk is required with --complexity")
        complexity, risk, task_id = args.complexity, args.risk, None
    profiles = load_profiles(args.agents_dir.resolve())
    result = resolve_route(
        policy,
        profiles,
        complexity=complexity,
        risk=risk,
        role=args.role,
        task_id=task_id,
    )
    if bool(args.evidence_file) != bool(args.purpose):
        raise RoutingError("--evidence-file and --purpose must be supplied together")
    if args.task_json:
        if not args.evidence_file:
            raise RoutingError("--task-json requires --evidence-file and --purpose for auditable dispatch")
        if args.evidence_file.resolve() != args.task_json.resolve():
            raise RoutingError("--task-json and --evidence-file must name the same task JSON")
    if args.evidence_file:
        validate_purpose_role(args.purpose, args.role)
        write_routing_evidence(args.evidence_file.resolve(), args.purpose, result)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RoutingError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
