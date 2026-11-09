#!/usr/bin/env bash
# The night shift's bookkeeping writes to dev (never main): state, queue, logs, morning reports, Lab sleeves,
# pre-registration drafts and briefs. Code changes go through a PR into dev instead (the implementer).
#
#   scripts/night_commit.sh "<commit message>" -- <command> [args...]
#   e.g. scripts/night_commit.sh "night: worker run 3 released" -- python -m nightshift.state release night-worker --outcome empty
#
# Each attempt: fetch origin/dev, check it out detached (the working tree must be clean), run <command>, refuse if
# anything outside PATHS changed, commit PATHS, push HEAD:dev. A rejected push starts again from the new dev and
# re-runs the command, so two runs never overwrite each other's state. NIGHT_BRANCH (testing only, default dev).
set -euo pipefail
PATHS=(docs/agent-state.json docs/queue.md docs/prereg_drafts results/exploration results/opposition results/night
       lab/sleeves lab/registry.csv briefs)
BRANCH="${NIGHT_BRANCH:-dev}"
case "$BRANCH" in main|master) echo "night_commit.sh never writes to $BRANCH" >&2; exit 2;; esac
msg="${1:?commit message}"; shift
[ "${1:-}" = "--" ] && shift
[ "$#" -gt 0 ] || { echo "usage: $0 \"message\" -- command..." >&2; exit 2; }
cd "$(git rev-parse --show-toplevel)"
if [ -n "$(git status --porcelain)" ]; then
  echo "working tree is not clean; keep scratch files outside the repository:" >&2
  git status --short >&2
  exit 2
fi
for attempt in 1 2 3 4 5; do
  git fetch -q origin "$BRANCH"
  git checkout -q --detach "origin/$BRANCH"
  set +e
  "$@"
  code=$?
  set -e
  if [ "$code" -ne 0 ]; then
    echo "command failed (exit $code); nothing committed" >&2
    git checkout -q -- . 2>/dev/null || true
    git clean -qfd -- "${PATHS[@]}" 2>/dev/null || true
    exit "$code"
  fi
  outside=$(git status --porcelain --untracked-files=all | awk '{print $2}' | while read -r f; do
    ok=no; for p in "${PATHS[@]}"; do case "$f" in "$p"|"$p"/*) ok=yes;; esac; done
    [ "$ok" = no ] && echo "$f"; done || true)
  if [ -n "$outside" ]; then
    echo "refused: the command changed files outside the night shift's paths:" >&2; echo "$outside" >&2
    git checkout -q -- . ; git clean -qfd
    exit 1
  fi
  for p in "${PATHS[@]}"; do [ -e "$p" ] && git add -- "$p"; done
  if git diff --cached --quiet; then echo "nothing to commit"; exit 0; fi
  git commit -q -m "$msg"
  if git push -q origin "HEAD:$BRANCH"; then
    echo "pushed $(git rev-parse --short HEAD) to $BRANCH"
    exit 0
  fi
  echo "push rejected (attempt $attempt); retrying from the new $BRANCH" >&2
  sleep $((attempt * 4))
done
echo "could not push after 5 attempts" >&2
exit 1
