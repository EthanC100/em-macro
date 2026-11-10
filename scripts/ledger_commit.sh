#!/usr/bin/env bash
# The only way session-written ledger records reach main: Janus's records, post-mortems, event-forecast
# resolutions, investor letters, decisions / forecasts / resolutions logged by the Ledger clerk
# (python -m ledger.clerk log, docs/ledger/clerk.md), and the audit seals that cover them. GitHub Actions uses it too, for Janus's fills
# and for the seals, so every writer of an append-only chain goes through the same path.
#
#   scripts/ledger_commit.sh "<commit message>" -- <command> [args...]
#   e.g. scripts/ledger_commit.sh "Janus quick check: no change" -- \
#          python -m ledger.janus check --positions J001 --result "no change" --model claude-opus-5-5
#   (scripts/janus_commit.sh is the same script under its earlier name.)
#
# Each attempt: fetch origin/main, check it out detached (the working tree must be clean: keep proposal files
# outside the repository, e.g. in /tmp), run `python -m ledger.janus mark` (fills at the next official daily mark,
# stops, horizons; idempotent), run <command>, seal new or resolved decisions and forecasts
# (`python -m ledger.audit seal`), verify both chains, commit the paths in PATHS and push to main. If the push is rejected (someone else pushed), start again from the new main and re-run the
# command there, so two writers never append to the same chain position. A rejected proposal (exit 1) stops at once
# with nothing committed. Exit 3 (config change C06): the Janus CLI rejected a daily review and appended only its
# failed-review record; that record is committed and pushed like any other, then the script exits 3 so the session
# still sees the rejection, fixes the proposal and proposes again.
#
# LEDGER_MSG_FILE: if the command writes a commit message to this file, that message is used (the clerk puts the new
# id in it). LEDGER_BRANCH (testing only, default main): start from and push to that branch instead; Janus's
# `mark` is skipped there, because Janus's chain lives on main and must never fork on a branch.
set -euo pipefail
PATHS=(data/janus data/ledger/postmortems data/ledger/decisions.csv data/ledger/forecasts.csv
       data/ledger/derivatives.csv data/ledger/iv_updates.csv data/ledger/derivative_pnl.csv
       data/ledger/automation_log.csv data/ledger/seals.jsonl data/ledger/reports)
BRANCH="${LEDGER_BRANCH:-main}"
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
  git fetch -q origin "$BRANCH"
  git checkout -q --detach "origin/$BRANCH"
  [ "$BRANCH" = main ] && python -m ledger.janus mark
  [ -n "${LEDGER_MSG_FILE:-}" ] && rm -f "$LEDGER_MSG_FILE"
  set +e
  "$@"
  code=$?
  set -e
  if [ "$code" -ne 0 ] && [ "$code" -ne 3 ]; then
    echo "command failed (exit $code); nothing committed" >&2
    git checkout -q -- "${PATHS[@]}" 2>/dev/null || true
    git clean -qfd -- "${PATHS[@]}" 2>/dev/null || true
    exit "$code"
  fi
  python -m ledger.audit seal >/dev/null
  python -m ledger.janus verify >/dev/null
  python -m ledger.audit verify >/dev/null || { echo "audit chain does not verify; nothing committed" >&2; exit 1; }
  for p in "${PATHS[@]}"; do [ -e "$p" ] && git add -- "$p"; done
  if git diff --cached --quiet; then
    echo "nothing to commit"
    exit "$code"
  fi
  if [ "$code" -eq 3 ]; then
    git commit -q -m "Janus daily review REJECTED: failed-review record (C06); nothing applied"
  elif [ -n "${LEDGER_MSG_FILE:-}" ] && [ -s "$LEDGER_MSG_FILE" ]; then
    git commit -q -F "$LEDGER_MSG_FILE"
  else
    git commit -q -m "$msg"
  fi
  if git push -q origin "HEAD:$BRANCH"; then
    echo "pushed $(git rev-parse --short HEAD) to $BRANCH"
    [ "$code" -eq 3 ] && echo "the proposal was REJECTED (failed-review record committed); fix it and propose again" >&2
    exit "$code"
  fi
  echo "push rejected (attempt $attempt); retrying from the new $BRANCH" >&2
  sleep $((attempt * 4))
done
echo "could not push after 5 attempts" >&2
exit 1
