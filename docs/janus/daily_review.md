# Janus daily review (weekdays, after the US close)

You are running Janus's full daily review, a scheduled session on weekdays at 18:07 New York time (after the US
close, and after the last quick check of the day). Janus is an AI discretionary **paper** book of US$500,000,000,
reported in %. It is an experiment in AI judgement: it never feeds the algorithm, and no edge is claimed. Opening
nothing is a legitimate, often correct, decision.

**Hard rules for this session**
- Never edit, create or delete anything under `data/janus/` or `data/ledger/` yourself. Every change goes through
  `scripts/janus_commit.sh`, which runs the CLI on a fresh `main`, commits and pushes. Keep scratch files in `/tmp`.
- The CLI enforces every rule in code and rejects the **whole** proposal if anything breaks one:
  - at most 2% of the account at risk per position, 10% in total, and 8 open positions;
  - capacity: notional at most 10% of daily volume and below 80% of any exchange position limit. The error states
    the largest size the stop allows;
  - stops can only be tightened;
  - required fields: a 2-3 sentence thesis, what would change its mind, at least one source URL, and The Opposition;
  - a reason for every review; and no-trade reasoning when you open nothing.
- Universe: only the instruments listed in `context`. Conventions:
  - yields: `long` = long the bond;
  - FR-DE: `long` = long OAT / short Bund, which gains when the spread tightens;
  - FX: `long` = long the named currency;
  - futures by contract month (WTI, BRENT, NATGAS, HEATOIL, RBOB, GOLD, SILVER, COPPER, CORN, SOYBEANS, WHEAT):
    `long` = long the contract. `contract` (YYYY-MM) is optional; the default is the front contract by the 35-day
    rule. The stop is a price of that contract. BRENT is held and marked as NYMEX BZ, a flagged proxy for ICE
    Brent. Grains are quoted in US cents per bushel.
  - options, on a futures market only, and only defined risk: add `"option": {"legs": "long 4200 call, short 4600
    call", "expiry": "2027-01-26", "iv_pct": 22, "iv_source": "<source> or estimate"}`. Allowed: a long call or
    put, or a vertical (debit or credit). `risk_pct` is the maximum loss. The stop is a level of the underlying.
    The horizon must be on or before the expiry, and the expiry before the contract's notice date. The value is
    Black-76 at your stated implied volatility (a model estimate). `direction` is derived from the legs.
- **Futures settlements are licensed.** They come from Databento and live only in the private repository
  em-macro-data. A session can propose or tighten futures and options only when it is checked out
  (`EM_MACRO_DATA`, or `../em-macro-data`). Without it the CLI rejects those items; rates and FX work as before.
  `context` shows the settlements for your judgement in this session only. Never copy a settlement, fill price or
  level derived from one into a thesis, review, commit message or any other public text; refer to moves in %.
- Optional, for every new position: `market_probability` (the market's probability that the view is right, 0-100)
  with `market_source`. The fund's Janus allocation rule compares Janus's Brier score with the market's on the
  calls that record it (docs/fund/allocation.md).
- Entries fill at the **next official daily mark** (for futures and options, the first final exchange settlement
  dated on or after today), not at today's price. Positions close automatically at the first mark through the
  stop, on or after the horizon, or at an option's expiry.
- Push to `main` (the script does this). Do not create a branch or a pull request.

## 1. Read the book

```bash
python -m ledger.janus context --fetch > /tmp/janus_context.json
python -m ledger.postmortem due > /tmp/pm_due.json
```

The context lists the rules, every open and pending position (entry, stop, horizon, probability, thesis, change_mind,
latest official mark, P&L, distance to stop), the universe with marks (and 1-week and 1-month levels), and the last
check. Note your own model string (from your system prompt, e.g. `claude-opus-5-5`).

## 2. Review every open position

For each one, research today's news, data and prices with web search: the thesis, every "what would change my
mind" trigger, the distance to the stop and the time to the horizon. Decide **hold**, **close** or
**tighten_stop** (with a new, tighter stop), and give a one-to-three-sentence reason. Every open or pending
position must be reviewed.

## 3. Consider new positions

Scan the universe for a view you can defend with evidence. For each candidate:
- **Size:** the stop is a level in the instrument's own unit, on the losing side of the latest mark. `risk_pct` is
  the % of the account lost if it is hit.
- **Probability:** your honest probability (0-100) that the position closes with a gain before costs. 50 is no
  view; above 70 is rare.
- **Write:** a 2-3 sentence thesis, what would change your mind (concrete, observable triggers), a horizon between
  1 week and 6 months, and the sources you relied on.
- **Pre-check limits:** run `--dry-run` (step 5) to test the size against the limits and capacity before writing
  The Opposition.

## 4. The Opposition, for each new position

Spawn a **separate subagent** (the Agent tool), so the case is argued independently. Give it only the proposed
position: instrument, direction, size, stop, horizon, probability, thesis and change_mind. Instruct it:

> You are The Opposition: an independent reviewer whose only job is to write the strongest honest case AGAINST this
> paper trade. Use web search for evidence. Do not hedge or balance. Return JSON: {"case_against": "4-6 sentences",
> "key_risks": [...], "what_proves_it_wrong": "the observable that would show the trade is wrong",
> "probability_view_wrong": 0-100, "sources": [{"title", "url"}]}.

Put its reply, with its `model`, in the position's `opposition` field. If The Opposition persuades you, drop the
position or change it; never edit its text.

## 5. Write, validate and apply the proposal

`/tmp/janus_review.json`:

```json
{"session": "daily_review", "model": "<your model string>", "session_url": "<this session's URL if known>",
 "market_summary": "2-4 sentences on what matters today",
 "reviews": [{"id": "J001", "action": "hold", "reasoning": "..."}],
 "new_positions": [{"instrument": "US10Y", "direction": "long", "risk_pct": 1.0, "stop": 5.10, "horizon": "2026-12-18",
                    "probability": 58, "thesis": "Two sentences. Or three.", "change_mind": "...",
                    "sources": [{"title": "...", "url": "https://..."}],
                    "opposition": {"case_against": "...", "key_risks": ["..."], "what_proves_it_wrong": "...",
                                   "probability_view_wrong": 50, "sources": [], "model": "<subagent model>"}}],
 "no_trade_reasoning": "required when new_positions is empty",
 "sources_read": [{"title": "...", "url": "https://..."}]}
```

```bash
python -m ledger.janus propose --file /tmp/janus_review.json --dry-run      # fix every error it lists
scripts/janus_commit.sh "Janus daily review $(date -u +%Y-%m-%d): <n> reviews, <n> new" -- \
  python -m ledger.janus propose --file /tmp/janus_review.json
```

## 6. Due post-mortems (every book)

For each `{"book", "id"}` in `/tmp/pm_due.json`, covering my decisions, the algorithm and Janus:
1. Run `python -m ledger.postmortem show <book> <id>` to see the record.
2. Research what actually moved the instrument over the holding period, and judge the decision, not just the
   outcome. For the algorithm, judge the mechanical rule, not a person.
3. Write `/tmp/pm.json`:

```json
{"thesis_right": "yes|no|partly|untested", "skill_or_luck": "skill|luck|mixed|unclear",
 "what_happened": "2-3 sentences", "assessment": "2-4 sentences", "do_differently": "1-3 concrete things",
 "sources": [{"title": "...", "url": "https://..."}]}
```

4. Commit it:

```bash
scripts/janus_commit.sh "Post-mortem <book> <id>" -- \
  python -m ledger.postmortem write <book> <id> --file /tmp/pm.json --model <your model string>
```

## 7. Finish

End with a short summary: positions reviewed and decisions, new positions (with The Opposition's probability that
each is wrong), or the no-trade reasoning, and the post-mortems written. Do nothing else in the repository.
