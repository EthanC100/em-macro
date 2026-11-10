# Janus quick check (every 30 minutes)

You are running Janus's quick check, a short session run every 30 minutes by two hourly Claude Code scheduled tasks
(at :15 and :45 past the hour). Janus is an AI discretionary **paper** book: an experiment in AI judgement.
It never feeds the algorithm, and no edge is claimed. Keep the check short (aim for under 10 minutes).

**Hard rules for this session**
- Never edit, create or delete anything under `data/janus/` or `data/ledger/` yourself. Every change goes through
  `scripts/janus_commit.sh`, which runs the CLI on a fresh `main`, commits and pushes. Keep your scratch files in
  `/tmp`, never in the repository.
- A quick check never opens a position. It may close one, or tighten a stop. It never widens a stop: the CLI
  rejects that.
- Push to `main` (the script does this). Do not create a branch or a pull request.
- Trades fill at the **next official daily mark**, not at the price you see now. The price now is for judgement
  only.
- **Futures settlements** (private, licensed) are read through a **read-only** clone of em-macro-data. The CLI
  (`context`, `propose`, `mark`) makes or refreshes it itself, through the environment's own GitHub access, and
  prints one `settlements: ...` line on stderr. If that line says it could not clone, attach the repository with
  `add_repo` (owner `EthanC100`, repo `em-macro-data`, access `read`) and run `context` again. If that is refused
  too, carry on without futures settlements.
  - Never print, echo or log the token: no `env`, `printenv` or `echo`, and never put it in a URL or a git
    command.
  - Never write to em-macro-data: no commit, push, `ledger.derivs settle` or `ledger.settlements fetch`.
  - Never copy a settlement or a price derived from one into a check result, review, commit message or any public
    text; describe moves in %.
  - If the clone fails, you cannot tighten a futures or options stop this session. A close is still possible; it
    fills at the next settlement in ledger-daily. Note it in the result.

## 1. Read the book

```bash
python -m ledger.janus context --fetch > /tmp/janus_context.json   # read-only; fresh official marks, and the private
                                                                   # settlements via the read-only clone; writes nothing
```

From it, note the following. If a module is missing, run `pip install -q -r requirements.txt` first.
- **For each open or pending position:** `entry`, `stop`, `horizon`, `thesis`, `change_mind` (the triggers that
  would change Janus's mind), `mark` and `mark_date` (the latest official daily mark), `net_pnl_pct` and
  `distance_to_stop_pct_account`.
- **`last_check`**, and your own model string (from your system prompt, e.g. `claude-opus-5-5`).
- **`flags`**: the mandate's flags, computed by the CLI. Flags are raised for:
  - a failed daily review: rejected by the CLI (a failed-review record, config change C06; this includes a review
    that breaks a C07 rule: a 50% call, too few candidates when the minimum binds, a missing or wrong time anchor,
    or a deferred idea not opened at the next session), or empty `sources_read`;
  - no daily review since yesterday;
  - the account below 3% at risk without a current specific reason (an event-based reason expires at the end of
    the next trading day after the event, C06).

  The CLI attaches them to your check record by itself. Also start your `--result` line with `FLAG:` and the flag,
  for example `FLAG: daily review 2026-11-08 failed (empty sources_read); no change`. A quick check never opens a
  position to fix a risk-budget flag: only the daily review opens positions.

If there are **no open positions**, skip to step 4 and record `--positions none --result "no open positions; no change"`.

## 2. Current prices and news, position by position

For each open position, use web search for:
- **The current market price** of the instrument from free public sources (a quote page, a central-bank or exchange
  release). Is it near the stop, or past the horizon?
- **News since the last check** that bears on the **thesis**, and on each **"what would change my mind"** trigger:
  data releases, central-bank statements, political events, supply news for energy.

Something has **changed** only if one of these holds:
- a "change my mind" trigger has fired;
- the thesis is contradicted by new facts;
- the price is close enough to the stop that tightening (to lock in a gain) or closing (cutting a broken trade)
  is warranted.

Ordinary noise is not a change.

## 3. If something changed: act through the CLI

Write `/tmp/janus_quick.json` with **only the positions you act on**:

```json
{"session": "quick_check", "model": "<your model string>", "session_url": "<this session's URL if known>",
 "market_summary": "one or two sentences on what changed",
 "reviews": [{"id": "J001", "action": "close", "reasoning": "The 'payrolls above 250k' trigger fired: 312k at 13:30 UTC."},
             {"id": "J002", "action": "tighten_stop", "new_stop": 1.0950, "reasoning": "Lock in the move after the ECB minutes."}],
 "sources_read": [{"title": "...", "url": "https://..."}]}
```

Validate it, then apply it:

```bash
python -m ledger.janus propose --file /tmp/janus_quick.json --dry-run
scripts/janus_commit.sh "Janus quick check $(date -u +%H:%M) UTC: <what changed>" -- \
  python -m ledger.janus propose --file /tmp/janus_quick.json
```

If the CLI rejects the proposal (exit 1, it lists every error), fix it and try again, at most twice. If it is still
rejected, record a check whose result says what you tried and why it was rejected (step 4).

## 4. If nothing changed: one check record

```bash
scripts/janus_commit.sh "Janus quick check $(date -u +%H:%M) UTC: no change" -- \
  python -m ledger.janus check --positions J001,J002 --result "no change" --model <your model string>
```

- `--positions` must list **every** open or pending position (or `none`).
- `--result` is one line of at most 240 characters: "no change", or a short note such as "no change; WTI 1.2% from
  J003's stop, watching OPEC".

## 5. Finish

The push to `main` rebuilds the Ledger, whose Janus page shows "last checked". End with one line: the time, the
positions checked, and "no change" or what changed. Do nothing else in the repository.
