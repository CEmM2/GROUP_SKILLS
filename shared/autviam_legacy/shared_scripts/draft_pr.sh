#!/usr/bin/env bash
# draft_pr.sh — open (idempotently) the draft PR for a completed phase or a completed plan.
#
# Branch model (SKILL.md § Branch & Worktree Model): phase work happens on `<plan_slug>_phase-<N>`,
# which merges into the plan branch `<plan_slug>`, which finally squash-merges into `main`. This
# script opens the matching draft PR when a handoff is written and labels it with the INTENDED merge
# method — GitHub can't pin a per-PR method at creation, so the label drives the eventual
# `gh pr merge --squash|--merge`:
#
#   draft_pr.sh phase <map_file> <N> <handoff_path>   # <plan_slug>_phase-<N> → <plan_slug>  · merge:commit
#   draft_pr.sh plan  <map_file> <handoff_path>        # <plan_slug> → <base (default main)>  · merge:squash
#
# Idempotent: if a PR already exists for the head branch, it is left alone (new commits ride it, so a
# handoff *update* needs no new PR). Best-effort & gated: no-op (exit 0/3) when gh is unauthenticated,
# the map is missing, or the head branch can't be pushed. Always safe to call from a hook.
#
# Reads plan_slug from <map_file>. Plan base branch override: $AUTVIAM_PLAN_BASE (default "main").
set -uo pipefail
log(){ printf '[draft_pr] %s\n' "$*" >&2; }

CMD="${1:?usage: draft_pr.sh [phase|plan] …}"; shift || true
PLAN_BASE="${AUTVIAM_PLAN_BASE:-main}"

gh auth status >/dev/null 2>&1 || { log "gh not authenticated — skipping draft PR (best-effort)"; exit 3; }

map_get(){ MAP="$1" KEY="$2" python3 - <<'PY' 2>/dev/null || true
import json, os, sys
try: m = json.load(open(os.environ["MAP"]))
except Exception: sys.exit(0)
v = m.get(os.environ["KEY"], "")
print(v if isinstance(v, (str, int)) else "")
PY
}

# Extract the "## Phase <N> Completion Summary" block (up to the next '---' or '## ') from a handoff.
summary_section(){ HF="$1" N="$2" python3 - <<'PY' 2>/dev/null || true
import os, re
try: t = open(os.environ["HF"], encoding="utf-8").read()
except Exception: t = ""
head = re.compile(r'^##\s+Phase\s+%s\s+Completion Summary' % re.escape(os.environ["N"]))
out, grab = [], False
for ln in t.splitlines():
    if grab:
        if ln.strip() == "---" or ln.startswith("## "): break
        out.append(ln)
    elif head.match(ln):
        grab = True; out.append(ln)
print("\n".join(out).strip())
PY
}

# Path of $1 relative to its worktree root (falls back to the input if it's outside a repo).
# Anchors git on the file's own dir, not cwd — cwd may have reverted to the main checkout.
reltoroot(){
  local r p; r="$(git -C "$(dirname "$1")" rev-parse --show-toplevel 2>/dev/null)"
  p="$(cd "$(dirname "$1")" 2>/dev/null && pwd)/$(basename "$1")"
  case "$p" in "$r"/*) printf '%s' "${p#"$r"/}" ;; *) printf '%s' "$1" ;; esac
}

# open_pr <head> <base> <label> <title> <handoff_path> <N-or-empty>
open_pr(){
  local head="$1" base="$2" label="$3" title="$4" hf="$5" n="$6"
  if gh pr view "$head" --json number >/dev/null 2>&1; then
    log "PR for $head already open — new commits ride it (no new PR on handoff update)"; return 0
  fi
  # Push from the plan worktree (refs are shared, but anchor git in a real checkout — the
  # caller's cwd may have reverted to the main checkout or elsewhere).
  local wt; wt="$(git -C "$(dirname "$MAP")" rev-parse --show-toplevel 2>/dev/null)"
  G=(git); [ -n "$wt" ] && G=(git -C "$wt")
  "${G[@]}" push -u origin "$base" >/dev/null 2>&1 || true       # base must exist on the remote
  "${G[@]}" push -u origin "$head" >/dev/null 2>&1 || { log "cannot push $head — skipping PR"; return 0; }
  gh label create "$label" --color "1d76db" --description "AutViam intended merge method" --force >/dev/null 2>&1 || true
  local rel sum scratch bf body
  rel="$(reltoroot "$hf")"
  sum=""; [ -n "$n" ] && sum="$(summary_section "$hf" "$n")"
  body="$(printf '%s\n\n---\n\nHandoff: [`%s`](%s)\n' "${sum:-_Completion summary pending — see handoff._}" "$rel" "$rel")"
  scratch="$(dirname "$MAP")/scratch"; mkdir -p "$scratch" 2>/dev/null || true
  bf="$scratch/pr_${head//\//_}_body.md"
  if printf '%s' "$body" > "$bf" 2>/dev/null; then
    gh pr create --draft --title "$title" --body-file "$bf" --head "$head" --base "$base" --label "$label" >/dev/null 2>&1 \
      && log "opened draft PR: $head → $base ($label)" \
      || log "gh pr create failed: $head → $base (base missing on remote, or PR exists)"
  else
    gh pr create --draft --title "$title" --body "$body" --head "$head" --base "$base" --label "$label" >/dev/null 2>&1 \
      && log "opened draft PR: $head → $base ($label)" \
      || log "gh pr create failed: $head → $base"
  fi
}

case "$CMD" in
  phase)
    MAP="${1:?usage: phase <map_file> <N> <handoff_path>}"; N="${2:?N}"; HF="${3:?handoff_path}"
    [ -f "$MAP" ] || { log "no issue map ($MAP) — skipping"; exit 0; }
    SLUG="$(map_get "$MAP" plan_slug)"; [ -n "$SLUG" ] || { log "no plan_slug in map — skipping"; exit 0; }
    open_pr "${SLUG}_phase-${N}" "$SLUG" "merge:commit" "${SLUG} phase ${N} handoff" "$HF" "$N" ;;
  plan)
    MAP="${1:?usage: plan <map_file> <handoff_path>}"; HF="${2:?handoff_path}"
    [ -f "$MAP" ] || { log "no issue map ($MAP) — skipping"; exit 0; }
    SLUG="$(map_get "$MAP" plan_slug)"; [ -n "$SLUG" ] || { log "no plan_slug in map — skipping"; exit 0; }
    open_pr "$SLUG" "$PLAN_BASE" "merge:squash" "${SLUG} plan complete — squash to ${PLAN_BASE}" "$HF" "" ;;
  *)
    log "usage: draft_pr.sh [phase|plan] …"; exit 2 ;;
esac
