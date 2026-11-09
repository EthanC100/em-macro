# Routine: weekly-brief

Routine model: Sonnet 5.5 (`claude-sonnet-5-5`) · Effort: medium
Trigger: schedule Saturdays 08:00 Asia/Singapore (cron `CRON_TZ=Asia/Singapore 0 8 * * 6`). Connector: Gmail
(draft only). Not part of the night chain and not counted in its cap.
Subagent: reporter (Sonnet 5.5, medium).

You start with no memory. Everything you need is in the repository.

## 0. Read first
1. `CLAUDE.md` ("Night shift: hard rules": no licensed data in public outputs).
2. `docs/agent-state.json` and `docs/queue.md` (only to know what the night shift did this week).
3. `config/brief.yaml`.

## 1. The week's weekly review
The brief is built on the week's weekly review: the latest "Horizon Weekly Brief" scheduled-task document
(Claude Docs) if this routine has that connector, otherwise the week's ledger files on main (decisions, marks,
Janus records, the algorithm's estimate) and `docs/todo.md`. Note which one you used in `weekly_review`.
(That task currently runs Saturdays 18:00 Singapore, after this one: see docs/agent-system.md, Needs Ethan.)

## 2. Draft, check, render
Agent tool, `subagent_type: reporter`: "Write this week's brief." It writes `/tmp/brief.json` (format in
`nightshift/brief.py`): beginner-readable, byline "Ethan Cukierman, Horizons" in plain text, every market level
with two public sources from different sites, written into the text only as `{id}`, no licensed settlement prices.
```bash
python -m nightshift.brief check --file /tmp/brief.json
scripts/night_commit.sh "Weekly brief <date>" -- python -m nightshift.brief render --file /tmp/brief.json
```
Unconfirmed levels are flagged "(unverified)" (or dropped, per config). The PDF is `briefs/<date>.pdf` on dev.

## 3. Deliver
- `auto_send: false` (default): create a **Gmail draft** to `delivery.mailing_list` (or to Ethan only if it is
  empty) with `briefs/<date>.txt` as the body and the PDF attached if the connector allows, else a link to the PDF
  on GitHub. Do not send it.
- `auto_send: true`: send through the mailing service in `delivery.service` with the key from the environment
  variable it names (never printed). If the key is missing, fall back to the draft and say so.
End with one line: the PDF path, levels verified/flagged, draft or sent.
