#!/usr/bin/env bash
# phase_git.sh — deterministic git sequences for AutViam phases.
#
#   branch      : create/checkout the phase branch `<slug>_phase-<N>` IN THE PLAN WORKTREE
#                 (resolved from the slug, so it's correct even when the caller's cwd has
#                 reverted to the main checkout) + a dirty-tree guard (never lose work).
#   plan-branch : create the plan branch `<slug>` from a base (default main) WITHOUT checkout,
#                 so a worktree can claim it. Idempotent.
#   worktree    : add a worktree for the plan branch at <repo-parent>/WorkTrees/<repo>-<slug>.
#   revert      : roll back commits with `git revert` in reverse order — NEVER `reset --hard`
#                 on a shared branch (references/recovery.md § Single-task rollback).
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

# Resolve the plan worktree for a slug from `git worktree list` (convention:
# <repo-parent>/WorkTrees/<repo>-<slug>). Echoes the path, or empty if none. Lets git ops
# target the worktree even when the caller's cwd has reverted to the main checkout.
wt_for_slug(){
  git worktree list --porcelain 2>/dev/null \
    | sed -n 's/^worktree //p' \
    | grep -E "/WorkTrees/[^/]*-$1\$" | head -1
}

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
    # Target the plan worktree when one exists for this slug — the caller's cwd may have
    # reverted to the main checkout, and `checkout -b` there would move main's HEAD.
    WT="$(wt_for_slug "$SLUG")"; G=(git); [ -n "$WT" ] && G=(git -C "$WT")
    if [ "$FORCE" -ne 1 ] && [ -n "$("${G[@]}" status --porcelain 2>/dev/null)" ]; then
      log "working tree is dirty${WT:+ ($WT)} — commit or stash first, or pass --force. Refusing to risk uncommitted work."
      exit 4
    fi
    if "${G[@]}" show-ref --verify --quiet "refs/heads/$BRANCH"; then
      "${G[@]}" checkout "$BRANCH" >/dev/null 2>&1 || { log "checkout $BRANCH failed"; exit 1; }
      log "checked out existing $BRANCH${WT:+ in $WT}"
    else
      if [ -n "$FROM" ]; then
        "${G[@]}" checkout -b "$BRANCH" "$FROM" >/dev/null 2>&1 || { log "create $BRANCH from $FROM failed"; exit 1; }
        log "created $BRANCH from $FROM${WT:+ in $WT}"
      else
        "${G[@]}" checkout -b "$BRANCH" >/dev/null 2>&1 || { log "create $BRANCH failed"; exit 1; }
        log "created $BRANCH from current HEAD${WT:+ in $WT}"
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
  plan-branch)
    SLUG="${1:?usage: plan-branch <plan_slug> [--from <base>]}"; shift
    FROM="main"
    while [ $# -gt 0 ]; do case "$1" in --from) FROM="${2:?}"; shift 2 ;; *) shift ;; esac; done
    if git show-ref --verify --quiet "refs/heads/$SLUG"; then
      log "plan branch $SLUG already exists"; echo "$SLUG"; exit 0
    fi
    git rev-parse --verify --quiet "${FROM}^{commit}" >/dev/null 2>&1 || { log "base '$FROM' not found"; exit 1; }
    # Create WITHOUT checkout — the current worktree stays put, so the plan worktree can claim $SLUG.
    git branch "$SLUG" "$FROM" >/dev/null 2>&1 || { log "create plan branch $SLUG from $FROM failed"; exit 1; }
    log "created plan branch $SLUG from $FROM (not checked out)"; echo "$SLUG" ;;
  worktree)
    SLUG="${1:?usage: worktree <plan_slug>}"; shift
    # Anchor on the MAIN worktree (first entry of `git worktree list`), not cwd's toplevel,
    # so the path is correct even when called from inside another worktree.
    ROOT="$(git worktree list --porcelain 2>/dev/null | sed -n 's/^worktree //p' | head -1)"
    [ -n "$ROOT" ] || ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || { log "not inside a git repo"; exit 1; }
    WT="$(dirname "$ROOT")/WorkTrees/$(basename "$ROOT")-${SLUG}"
    if git worktree list --porcelain 2>/dev/null | grep -qxF "worktree $WT"; then
      log "worktree already present: $WT"; echo "$WT"; exit 0
    fi
    git show-ref --verify --quiet "refs/heads/$SLUG" || { log "plan branch $SLUG missing — run 'plan-branch $SLUG' first"; exit 1; }
    mkdir -p "$(dirname "$WT")"
    git worktree add "$WT" "$SLUG" >/dev/null 2>&1 || { log "worktree add failed ($WT on $SLUG — branch checked out elsewhere?)"; exit 1; }
    log "added worktree $WT on $SLUG"; echo "$WT" ;;
  *)
    log "usage: phase_git.sh [branch|plan-branch|worktree|revert] …"; exit 2 ;;
esac
