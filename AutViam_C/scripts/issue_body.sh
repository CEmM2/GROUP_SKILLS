#!/usr/bin/env bash
# issue_body.sh — thin gh wrapper for the canonical issue-body roundtrip.
#
# Implements the gh halves of references/issue_body_updates.md. The LLM still does the
# Edit/MultiEdit between `fetch` and `push` (Write/Edit run autonomously under accept-edits;
# `sed -i`/`perl -i` do not — never use them). This script owns the two Bash `gh` calls
# plus the label/state flags, so the "exactly 2 gh calls per body update" budget is enforced
# and the close/label-swap can't drift into N calls.
#
# Usage:
#   issue_body.sh fetch <issue>                          # → body to stdout; LLM Writes it to /tmp/issue_<N>_body.md
#   issue_body.sh push  <issue> <body_file> [gh flags…]  # gh issue edit --body-file + extra flags
#   issue_body.sh label <issue> [--add L]… [--remove L]… # label-only edit (no body)
#
# push flag examples (phase close in ONE call):
#   issue_body.sh push 11 /tmp/issue_11_body.md --remove-label in-progress --add-label done --state closed
# label example (gate-cap, scaffold swap):
#   issue_body.sh label 11 --add gate-cap-hit
#   issue_body.sh label 11 --remove not-scaffolded --add scaffolded
set -uo pipefail
log(){ printf '[issue_body] %s\n' "$*" >&2; }

gh auth status >/dev/null 2>&1 || { log "gh not authenticated — skipping (GitHub is a best-effort projection)"; exit 3; }

CMD="${1:?usage: issue_body.sh [fetch|push|label] …}"; shift || true
case "$CMD" in
  fetch)
    ISSUE="${1:?usage: fetch <issue>}"
    gh issue view "$ISSUE" --json body -q .body ;;
  push)
    ISSUE="${1:?usage: push <issue> <body_file> [--add-label L] [--remove-label L] [--state closed|open] [--comment …]}"; BODY="${2:?body_file}"; shift 2
    [ -f "$BODY" ] || { log "body file not found: $BODY"; exit 1; }
    # gh issue edit handles body + labels; --state/--comment are NOT edit flags —
    # route them to gh issue close/reopen/comment so the whole update stays one logical call.
    edit_args=(); state=""; comment=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --state)   state="$2";   shift 2 ;;
        --comment) comment="$2"; shift 2 ;;
        *)         edit_args+=("$1"); shift ;;
      esac
    done
    gh issue edit "$ISSUE" --body-file "$BODY" ${edit_args[@]+"${edit_args[@]}"} || { log "issue edit failed for #$ISSUE"; exit 1; }
    case "$state" in
      closed) gh issue close  "$ISSUE" ${comment:+--comment "$comment"} || { log "issue close failed for #$ISSUE";  exit 1; } ;;
      open)   gh issue reopen "$ISSUE" || { log "issue reopen failed for #$ISSUE"; exit 1; } ;;
      "")     if [ -n "$comment" ]; then gh issue comment "$ISSUE" --body "$comment" || log "comment failed for #$ISSUE"; fi ;;
    esac ;;
  label)
    ISSUE="${1:?usage: label <issue> [--add L]… [--remove L]…}"; shift
    args=()
    while [ $# -gt 0 ]; do
      case "$1" in
        --add)    args+=(--add-label "$2");    shift 2 ;;
        --remove) args+=(--remove-label "$2"); shift 2 ;;
        *)        args+=("$1");                shift ;;
      esac
    done
    [ ${#args[@]} -gt 0 ] || { log "label needs at least one --add/--remove"; exit 2; }
    gh issue edit "$ISSUE" "${args[@]}" || { log "label edit failed for #$ISSUE"; exit 1; } ;;
  close)
    # Close an issue WITHOUT rewriting its body (label swap + close + optional comment, one logical call).
    ISSUE="${1:?usage: close <issue> [--add L] [--remove L] [--comment …]}"; shift
    edit_args=(); comment=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --add)     edit_args+=(--add-label "$2");    shift 2 ;;
        --remove)  edit_args+=(--remove-label "$2"); shift 2 ;;
        --comment) comment="$2";                     shift 2 ;;
        *)         shift ;;
      esac
    done
    if [ ${#edit_args[@]} -gt 0 ]; then
      gh issue edit "$ISSUE" "${edit_args[@]}" || { log "label edit failed for #$ISSUE"; exit 1; }
    fi
    gh issue close "$ISSUE" ${comment:+--comment "$comment"} || { log "close failed for #$ISSUE"; exit 1; } ;;
  *)
    log "usage: issue_body.sh [fetch|push|label] …"; exit 2 ;;
esac
