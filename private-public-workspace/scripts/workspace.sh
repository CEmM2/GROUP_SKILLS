#!/bin/bash
# Show or refresh the two repositories in this checkout.
#
#   workspace.sh status   state of the private repository and of public/
#   workspace.sh pull     fast-forward both; leaves the recorded public commit alone
#
# The private repository records one commit of public/. `pull` moves the
# public checkout to the tip of its branch without committing that move, so
# the record changes only when someone runs `git add public` on purpose.
# Works on macOS /bin/bash 3.2.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PUBLIC="$ROOT/public"

if ! git -C "$PUBLIC" rev-parse --git-dir >/dev/null 2>&1; then
  echo "public/ is not checked out. Run: git -C \"$ROOT\" submodule update --init" >&2
  exit 1
fi

describe() {
  local dir="$1" branch upstream counts dirty
  branch="$(git -C "$dir" symbolic-ref --quiet --short HEAD || echo "detached")"
  echo "  branch:  $branch  ($(git -C "$dir" rev-parse --short HEAD))"
  if upstream="$(git -C "$dir" rev-parse --abbrev-ref '@{upstream}' 2>/dev/null)"; then
    counts="$(git -C "$dir" rev-list --left-right --count "HEAD...$upstream")"
    echo "  vs $upstream:  ahead ${counts%%[[:space:]]*}, behind ${counts##*[[:space:]]}"
  else
    echo "  no upstream branch"
  fi
  dirty="$(git -C "$dir" status --porcelain --ignore-submodules=all | wc -l | tr -d ' ')"
  echo "  uncommitted files:  $dirty"
}

status() {
  local recorded current
  echo "private  ($ROOT)"
  describe "$ROOT"
  echo "public   ($PUBLIC)"
  describe "$PUBLIC"
  recorded="$(git -C "$ROOT" rev-parse HEAD:public)"
  current="$(git -C "$PUBLIC" rev-parse HEAD)"
  if [ "$recorded" = "$current" ]; then
    echo "  recorded commit:  same as the checkout"
  else
    echo "  recorded commit:  $(git -C "$PUBLIC" rev-parse --short "$recorded" 2>/dev/null || echo "${recorded:0:7}")  (the checkout differs)"
  fi
}

pull() {
  git -C "$ROOT" pull --ff-only --no-recurse-submodules
  if git -C "$PUBLIC" symbolic-ref --quiet HEAD >/dev/null; then
    git -C "$PUBLIC" pull --ff-only
  else
    echo "public/ is on a detached commit; run: git -C public switch dev" >&2
    exit 1
  fi
}

case "${1:-status}" in
  status) status ;;
  pull) pull ;;
  *) sed -n '2,5p' "$0" >&2; exit 2 ;;
esac
