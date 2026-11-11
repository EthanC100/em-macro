#!/usr/bin/env bash
# Open, update or close "[ALERT] Ledger marks stale" (or, with --late-runs, "[ALERT] ledger-daily late", Q018)
# from the JSON written by `python -m ledger.watchdog`.
# Usage: marks_alert.sh <watchdog.json>     (needs GH_TOKEN and GITHUB_REPOSITORY)
set -euo pipefail
f="$1"
stale=$(python -c "import json;print(str(json.load(open('$f'))['stale']).lower())")
title=$(python -c "import json;print(json.load(open('$f'))['title'])")
python -c "import json;print(json.load(open('$f'))['body'])" > "$f.body.md"
gh label create alert --repo "$GITHUB_REPOSITORY" --color d73a4a \
  --description "Automated failure alert from a workflow" --force >/dev/null 2>&1 || true
existing=$(gh issue list --repo "$GITHUB_REPOSITORY" --state open --label alert --limit 100 \
             --json number,title --jq ".[] | select(.title == \"$title\") | .number" | head -n 1)
if [ "$stale" = "true" ]; then
  if [ -n "$existing" ]; then
    gh issue comment "$existing" --repo "$GITHUB_REPOSITORY" --body-file "$f.body.md"
    echo "commented on #$existing"
  else
    gh issue create --repo "$GITHUB_REPOSITORY" --title "$title" --label alert --body-file "$f.body.md"
  fi
elif [ -n "$existing" ]; then
  # close_comment: from the ledger-daily lateness check (Q018); the marks check keeps its own wording
  gh issue close "$existing" --repo "$GITHUB_REPOSITORY" --reason completed \
    --comment "$(python -c "import json;d=json.load(open('$f'));print(d.get('close_comment') or 'Marks are fresh again (%s).' % d.get('last_fetch'))")"
  echo "closed #$existing"
fi
