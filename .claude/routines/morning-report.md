# Routine: morning-report

Routine model: Sonnet 5.5 (`claude-sonnet-5-5`) · Effort: medium
Triggers: API trigger fired by promote, and schedule 06:50 Asia/Singapore (cron `CRON_TZ=Asia/Singapore 50 6 * * *`)
as the fallback; if today's report already exists on dev, the second run ends at once. Push notification on.
Subagent: reporter (Sonnet 5.5, medium).

You start with no memory. Everything you need is in the repository.

## 0. Read first
1. `CLAUDE.md` ("Night shift: hard rules").
2. `docs/agent-state.json` and `docs/queue.md`.
3. `results/night/promote/<today>.json` (may be missing: then "promote did not run").

## 1. Janus (read only, no new schedule)
Janus has its own scheduled tasks; this report only reads their results from `data/janus/records.jsonl` on
`origin/main` (`git fetch -q origin main && git checkout -q origin/main -- data/janus` in a scratch worktree, or
read it on dev after night-start's merge): the latest daily review (C05: `sources_read`, positions, % at risk,
`below_budget`) and the latest quick check with its flags. `nightshift.morning` does this through
`ledger.janus.review_status` / `budget_status`.

## 2. Write it
Agent tool, `subagent_type: reporter`: "Write this morning's report." It runs
`python -m nightshift.morning --needs "<issue> => <recommendation>"` (at most 3) and keeps it to one phone screen.
Commit: `scripts/night_commit.sh "Morning report <date>" -- python -m nightshift.morning --needs ...`.

## 3. Deliver
End your session with the report's text as your final message (the push notification shows it). Do nothing else.
Never paste a licensed price, a salt or a secret.
