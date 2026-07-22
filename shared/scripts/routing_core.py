#!/usr/bin/env python3
"""Primitives shared by the AutViam (Claude) and AutViam_C (Codex) routing stacks.

This module holds only what is *provably identical* across both stacks: JSON loading,
atomic writes, the lock family, score validation, and hashing. Routing policy, tier
selection, evidence shape, tickets, and dispatcher capabilities stay per-skill — the two
stacks enforce deliberately different contracts (AutViam is fail-closed via dispatch
hooks; AutViam_C degrades against a capability probe) and must not be merged here.

Each skill aliases `RoutingCoreError` to its own public error name so existing `except`
sites keep working unchanged.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Iterator, Mapping

__all__ = [
    "LOCK_STALE_AFTER_SECONDS",
    "RoutingCoreError",
    "atomic_write_json",
    "atomic_write_text",
    "directory_lock",
    "load_json",
    "sha256_text",
    "validate_score",
]

LOCK_STALE_AFTER_SECONDS = 300.0


class RoutingCoreError(RuntimeError):
    """Base error for every shared routing primitive."""


def load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise RoutingCoreError(f"{label} does not exist: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RoutingCoreError(f"could not read {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RoutingCoreError(f"{label} must contain a JSON object: {path}")
    return value


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent), text=True)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
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


def atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    atomic_write_text(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def validate_score(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5:
        raise RoutingCoreError(f"{name} must be an integer from 1 through 5; found {value!r}")
    return value


def _write_lock_owner(lock_path: Path) -> None:
    """Stamp the holder into the lock so a stale one is diagnosable and breakable."""
    owner = {"pid": os.getpid(), "acquired_at": time.time()}
    try:
        (lock_path / "owner.json").write_text(json.dumps(owner), encoding="utf-8")
    except OSError:
        pass


def _break_stale_lock(lock_path: Path, stale_after_seconds: float) -> None:
    """Reclaim a lock abandoned by a killed holder.

    Routing failures are fatal by design, so a leftover lock would otherwise wedge every
    later dispatch for that file permanently. Only the process that wins the atomic
    rename removes it, so concurrent breakers cannot delete a fresh lock.
    """
    try:
        age = time.time() - lock_path.stat().st_mtime
    except FileNotFoundError:
        return
    if age < stale_after_seconds:
        return
    condemned = lock_path.with_name(f"{lock_path.name}.stale.{os.getpid()}")
    try:
        os.rename(lock_path, condemned)
    except OSError:
        return
    shutil.rmtree(condemned, ignore_errors=True)


def _release_lock(lock_path: Path) -> None:
    """Release only if we still hold it — a broken-and-reacquired lock is not ours."""
    try:
        owner = json.loads((lock_path / "owner.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        owner = None
    if owner is not None and owner.get("pid") != os.getpid():
        return
    shutil.rmtree(lock_path, ignore_errors=True)


@contextlib.contextmanager
def directory_lock(
    path: Path,
    timeout_seconds: float = 30.0,
    stale_after_seconds: float = LOCK_STALE_AFTER_SECONDS,
    suffix: str = "autviam-lock",
    label: str = "lock",
) -> Iterator[None]:
    """Serialize writes to `path` with an atomic lock-directory acquisition.

    `suffix` names the lock directory and `label` names it in the timeout message, so
    each stack keeps its established on-disk name and error text (`.<file>.autviam-lock`
    for AutViam, `.<file>.routing-lock` / "routing evidence lock" for AutViam_C). Both
    are quoted verbatim by each skill's references/recovery.md.
    """
    lock_path = path.with_name(f".{path.name}.{suffix}")
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            lock_path.mkdir()
            break
        except FileExistsError:
            _break_stale_lock(lock_path, stale_after_seconds)
            if time.monotonic() >= deadline:
                raise RoutingCoreError(
                    f"timed out acquiring {label}: {lock_path}. A live holder is still "
                    f"writing, or a lock newer than {stale_after_seconds:.0f}s was "
                    f"abandoned; remove the directory to recover."
                )
            time.sleep(0.02)
    _write_lock_owner(lock_path)
    try:
        yield
    finally:
        _release_lock(lock_path)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
