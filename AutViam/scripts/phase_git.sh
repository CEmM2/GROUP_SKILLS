#!/usr/bin/env bash
# phase_git.sh — deterministic git sequences for AutViam phases.
#
#   branch : create/checkout the phase branch with the canonical name + a dirty-tree guard
#            (E2E Human-Intervention trigger 6 — never silently lose uncommitted work).
#   revert : roll back commits with `git revert` in reverse order — NEVER `reset --hard`
#            on a shared branch (references/recovery.md § Single-task rollback).
#
# Usage:
#   phase_git.sh branch <plan_slug> <phase_id> [--from <parent_branch>] [--force]
#       → checks out `<plan_slug>_phase-<phase_id>` (from <parent_branch>, else current HEAD);
#         refuses on a dirty working tree unless --force; prints the branch name.
#   phase_git.sh revert <sha> [<sha>…]
#       → `git revert --no-edit` each SHA in REVERSE order (find the last-good SHA via
#         `gate_state.py last-good-sha`).
set -uo pipefail
log(){ printf '[phase_git] %s\n' "$*" >&2; }

CMD="${1:?usage: phase_git.sh [branch|revert] …}"; shift || true
case "$CMD" in
  branch)
    SLUG="${1:?usage: branch <plan_slug> <phase_id> [--from <parent>] [--force]}"; PHASE="${2:?phase_id}"; shift 2
    FROM=""; FORCE=0
    while [ $# -gt 0 ]; do
      case "$1" in
        --from)  FROM="$2"; shift 2 ;;
        --force) FORCE=1;   shift ;;
        *)       shift ;;
      esac
    done
    BRANCH="${SLUG}_phase-${PHASE}"
    if [ "$FORCE" -ne 1 ] && [ -n "$(git status --porcelain 2>/dev/null)" ]; then
      log "working tree is dirty — commit or stash first, or pass --force. Refusing to risk uncommitted work."
      exit 4
    fi
    if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
      git checkout "$BRANCH" >/dev/null 2>&1 || { log "checkout $BRANCH failed"; exit 1; }
      log "checked out existing $BRANCH"
    else
      if [ -n "$FROM" ]; then
        git checkout -b "$BRANCH" "$FROM" >/dev/null 2>&1 || { log "create $BRANCH from $FROM failed"; exit 1; }
        log "created $BRANCH from $FROM"
      else
        git checkout -b "$BRANCH" >/dev/null 2>&1 || { log "create $BRANCH failed"; exit 1; }
        log "created $BRANCH from current HEAD"
      fi
    fi
    echo "$BRANCH" ;;
  revert)
    [ $# -ge 1 ] || { log "usage: revert <sha> [<sha>…]"; exit 2; }
    shas=("$@")
    for (( i=${#shas[@]}-1; i>=0; i-- )); do
      git revert --no-edit "${shas[$i]}" >/dev/null 2>&1 || {
        log "revert failed at ${shas[$i]} — resolve the conflict by hand. Never 'reset --hard' a shared branch."
        exit 1
      }
    done
    log "reverted ${#shas[@]} commit(s) in reverse order" ;;
  *)
    log "usage: phase_git.sh [branch|revert] …"; exit 2 ;;
esac
