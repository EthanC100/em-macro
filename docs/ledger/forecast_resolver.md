# Ledger forecast resolver (daily)

You are running the Ledger's forecast resolver, a short scheduled Claude Code session every day (weekends
included), after the morning `ledger-daily` run. Its only job is to settle **event** forecasts, the ones that no
official data series can settle, such as election results and race calls. Mechanical questions (central-bank
decisions, price or spread levels) are settled by `ledger-daily` from official data. Do not touch them.

**Hard rules for this session**
- **You work blind.** The CLI gives you each question, its resolution source and dates, never my, the market's or
  Claude's probability. Do not look them up in the repository: judge only what happened.
- **Never edit `data/ledger/` yourself.** Every change goes through `scripts/ledger_commit.sh`, which applies the
  CLI on a fresh `main`, seals the resolution in the audit chain and pushes. Keep scratch files in `/tmp`.
- **A forecast is settled only as its stated resolution source would settle it.** For example, "AP race call"
  means the Associated Press has called the race, and a data release means the official publisher's figure.
  Projections, polls, prediction markets and opinion pieces are not results.
- **A yes or no needs at least two independent sources** that state the outcome directly: different organisations,
  with different domains and different names. Two pages of one outlet, or a syndicated copy of the same wire story,
  count once. The CLI enforces this and rejects the whole file otherwise.
- **Push to `main`** (the script does this). Do not create a branch or a pull request.

## 1. What is due

```bash
python -m ledger.resolve events > /tmp/events.json      # open event forecasts past their resolution date (blind)
```

If the list is empty, stop here and end with "No event forecasts due." Commit nothing.

## 2. Research each one

For each item, search the web for what happened, as of today, judged as its `resolution_source` would judge it.
Record the exact URL, organisation, date and a short quote for every page you rely on. If the source has not
settled it yet (for example, AP has not called the race), the outcome is `unresolved`. Say why in one sentence.
`ledger-daily` opens a `[RESOLVE?]` issue with that note if it stays unsettled for 2 days after the resolution
date.

## 3. Write, apply, push

`/tmp/settle.json`:

```json
{"model": "<your model string, e.g. claude-opus-5-5>",
 "results": [
  {"id": "F001", "outcome": "yes", "summary": "AP called the Senate for the Republicans on 5 Nov 2026.",
   "sources": [{"organisation": "Associated Press", "url": "https://apnews.com/...", "date": "2026-11-05", "quote": "..."},
               {"organisation": "Reuters", "url": "https://www.reuters.com/...", "date": "2026-11-05", "quote": "..."}]},
  {"id": "F002", "outcome": "unresolved", "summary": "AP has not called Michigan; 97% of the vote counted."}]}
```

```bash
scripts/ledger_commit.sh "Forecast resolver $(date -u +%Y-%m-%d): <ids settled>" -- \
  python -m ledger.resolve settle-events --file /tmp/settle.json
```

If it is rejected (exit 1, every error is listed), fix the file and run it again. Usually the fix is another
independent source, or `unresolved`. Nothing is written by a rejected file.

## 4. Finish

End with one line per forecast: the id, the outcome, and the two organisations relied on (or why it is still
unresolved). The push to `main` rebuilds the Ledger, which shows the Brier scores.
