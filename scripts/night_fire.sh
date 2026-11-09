#!/usr/bin/env bash
# Fire the next night-shift routine through its API trigger. The URL and token come from environment variables of
# the cloud environment (names in config/night.yaml "triggers"); they are never in the repository, never printed.
#   scripts/night_fire.sh night-worker "chained from night-explorer run 4"
# Exit 0: fired (HTTP 200). Exit 6: no URL/token in this environment (the hourly schedule is the fallback).
set -euo pipefail
routine="${1:?routine}"; text="${2:-chained}"
case "$routine" in
  night-worker)   u=NIGHT_WORKER_FIRE_URL;   t=NIGHT_WORKER_FIRE_TOKEN ;;
  night-explorer) u=NIGHT_EXPLORER_FIRE_URL; t=NIGHT_EXPLORER_FIRE_TOKEN ;;
  promote)        u=NIGHT_PROMOTE_FIRE_URL;  t=NIGHT_PROMOTE_FIRE_TOKEN ;;
  morning-report) u=NIGHT_MORNING_FIRE_URL;  t=NIGHT_MORNING_FIRE_TOKEN ;;
  *) echo "unknown routine $routine" >&2; exit 2 ;;
esac
if [ -z "${!u:-}" ] || [ -z "${!t:-}" ]; then
  echo "no API trigger for $routine in this environment ($u/$t unset): the hourly schedule will pick it up" >&2
  exit 6
fi
body=$(python3 -c 'import json,sys; print(json.dumps({"text": sys.argv[1][:500]}))' "$text")
code=$(curl -sS -o /dev/null -w "%{http_code}" -X POST "${!u}" \
  -H "Authorization: Bearer ${!t}" -H "anthropic-beta: experimental-cc-routine-2026-04-01" \
  -H "anthropic-version: 2023-06-01" -H "Content-Type: application/json" -d "$body" || echo 000)
echo "fired $routine: HTTP $code"
[ "$code" = 200 ]
