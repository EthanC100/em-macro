#!/usr/bin/env bash
# The only way Janus's records (and session-written post-mortems) reach main.
#
#   scripts/janus_commit.sh "<commit message>" -- <command> [args...]
#   e.g. scripts/janus_commit.sh "Janus quick check: no change" -- \
#          python -m ledger.janus check --positions J001 --result "no change" --model claude-opus-5-5
#
# Each attempt: fetch origin/main, check it out detached (the working tree must be clean: keep proposal files
# outside the repository, e.g. in /tmp), run `python -m ledger.janus mark` (fills at the next official daily mark,
# stops, horizons; idempotent), run <command>, verify the hash chain, commit data/janus and data/ledger/postmortems,
# and push to main. If the push is rejected (someone else pushed), start again from the new main and re-run the
# command there, so two writers never append to the same chain position. A rejected proposal (exit 1) stops at once
# with nothing committed.
set -euo pipefail
msg="${1:?commit message}"; shift
[ "${1:-}" = "--" ] && shift
[ "$#" -gt 0 ] || { echo "usage: $0 \"message\" -- command..." >&2; exit 2; }
cd "$(git rev-parse --show-toplevel)"
if [ -n "$(git status --porcelain)" ]; then
  echo "working tree is not clean; keep proposal files outside the repository:" >&2
  git status --short >&2
  exit 2
fi
for attempt in 1 2 3 4 5; do
  git fetch -q origin main
  git checkout -q --detach origin/main
  python -m ledger.janus mark
  set +e
  "$@"
  code=$?
  set -e
  if [ "$code" -ne 0 ]; then
    echo "command failed (exit $code); nothing committed" >&2
    git checkout -q -- data/janus data/ledger/postmortems 2>/dev/null || true
    git clean -qfd -- data/janus data/ledger/postmortems 2>/dev/null || true
    exit "$code"
  fi
  python -m ledger.janus verify >/dev/null
  for p in data/janus data/ledger/postmortems; do [ -e "$p" ] && git add -- "$p"; done
  if git diff --cached --quiet; then
    echo "nothing to commit"
    exit 0
  fi
  git commit -q -m "$msg"
  if git push -q origin HEAD:main; then
    echo "pushed $(git rev-parse --short HEAD) to main"
    exit 0
  fi
  echo "push rejected (attempt $attempt); retrying from the new main" >&2
  sleep $((attempt * 4))
done
echo "could not push after 5 attempts" >&2
exit 1
