# Janus daily review (after the US close)

You are running Janus's full daily review, a scheduled session at 18:07 New York time (after the US close, and after
the last quick check of the day). Janus is an AI discretionary **paper** book of US$500,000,000, reported in %. It is
an experiment in AI judgement: it never feeds the algorithm, and no edge is claimed.

## Mandate (from 9 November 2026; config change C05)

Set by the owner before Janus had opened any position, so set without seeing any result.

**1. Research is required.**
- Every daily review does web research on the main drivers across its universe before deciding:
  - **central banks:** decisions, minutes, speeches, market pricing of the next meetings;
  - **data:** releases since the last review and the calendar ahead;
  - **geopolitics:** wars, sanctions, shipping, elections, trade;
  - **positioning:** CFTC Commitments of Traders, fund flows, surveys, crowded trades.
- Record everything you read in `sources_read`, each with its URL, and tag each source with its `driver`.
- The CLI rejects a daily review whose `sources_read` is empty. Such a review counts as **failed**, and every quick
  check flags it until a researched review is recorded.

**2. Risk budget.**
- Janus normally holds **2-6 positions** using **3-10% of the account at risk**.
- Choose your best ideas even at modest conviction, for example a probability of 55%. "Nothing clears a high bar" is
  not the standard: the standard is your best ideas, sized honestly.
- **Size scales with conviction and with your edge over the market probability** (`probability` −
  `market_probability`):

  | edge over the market probability | typical `risk_pct` |
  |---|---|
  | small (about 3-7 points, e.g. 55% against a 50% market) | **0.25-0.5%** |
  | moderate (about 8-15 points) | 0.5-1.25% |
  | large (above 15 points, rare) | 1.25-2% (the 2% limit) |

- **Below 3% at risk** is allowed only with a specific written reason tied to an identifiable event or condition,
  in `below_budget`. A general "no edge" or "uncertainty" is not a reason. Give:
  - `condition`: the event or condition, for example "US CPI on 12 Nov decides the December Fed call";
  - `until`: the date (at most 30 days ahead) when it resolves or you reassess;
  - `reasoning`: why it justifies holding less.

  The CLI rejects a review that leaves the account below 3% without it. It also rejects a generic condition and a
  missing or distant date.
- **Weekend and market-holiday reviews** may defer new entries to the next trading day, but must still research and
  name the ideas, in `deferred_ideas`. Each idea gives `instrument`, `direction`, `risk_pct`, `probability`,
  `market_probability` and `thesis`.
  - On a market holiday that falls on a weekday, also set `market_holiday` to its name.
  - If the deferred ideas plus open risk come to less than 3%, `below_budget` is still required.
  - The next trading-day review opens them (with The Opposition), or says why not.

**All existing limits stay**: 2% at risk per position, 10% in total, 8 open positions, capacity, costs, The
Opposition and `market_probability` on every new position.

**Hard rules for this session**
- Never edit, create or delete anything under `data/janus/` or `data/ledger/` yourself. Every change goes through
  `scripts/janus_commit.sh`, which runs the CLI on a fresh `main`, commits and pushes. Keep scratch files in `/tmp`.
- The CLI enforces every rule in code and rejects the **whole** proposal if anything breaks one:
  - at most 2% of the account at risk per position, 10% in total, and 8 open positions;
  - capacity: notional at most 10% of daily volume and below 80% of any exchange position limit. The error states
    the largest size the stop allows;
  - stops can only be tightened;
  - required fields: a 2-3 sentence thesis, what would change its mind, at least one source URL, the market's
    probability with its source and basis, and The Opposition;
  - a reason for every review; and no-trade reasoning when you open nothing;
  - the mandate: a non-empty `sources_read`, and `below_budget` (or `deferred_ideas` on a weekend or holiday) when
    the account would be below 3% at risk.
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
  em-macro-data. The CLI (`context`, `propose`, `mark`) makes or refreshes a **read-only** clone of it (sparse,
  `ledger/` only), next to this repository, and prints one `settlements: ...` status line on stderr.
  - The clone uses the environment's own GitHub access through the Claude Code git proxy, which works only when
    em-macro-data is one of this session's repositories. `DATA_REPO_READ_TOKEN` is a fallback for environments
    without that proxy: the proxy replaces any header a client sends, so the token cannot help here.
  - If the status line says it could not clone, attach the repository yourself with the `add_repo` tool
    (owner `EthanC100`, repo `em-macro-data`, access `read`), then run `context` again. If `add_repo` refuses, carry
    on without futures settlements, as below.
  - **Never print, echo or log the token.** Do not run `env`, `printenv` or `echo $DATA_REPO_READ_TOKEN`, and do not
    put it in a URL or a git command yourself. Let the CLI use it.
  - **Never write to em-macro-data** from this session: no commit, push, `ledger.derivs settle` or
    `ledger.settlements fetch`. The clone's push URL is disabled and the code refuses writes to it. Only
    ledger-daily fetches settlements.
  - If the status says the clone failed, futures and options proposals and tightenings are rejected for this
    session. Rates and FX work as before. Say so in the market summary.
  - `context` shows the settlements for your judgement in this session only. Never copy a settlement, fill price
    or level derived from one into a thesis, review, commit message or any other public text; refer to moves in %.
- **Required on every new position:** `market_probability`, the market's probability (%, 0-100, like
  `probability`) that the view is right, with `market_source` and `market_basis`. Use the best market-implied
  figure available:
  - `"options"`: the risk-neutral probability from option prices (for an options position, the probability the
    structure finishes in profit; for a futures view, the option-implied probability of reaching the target);
  - `"prediction market"`: e.g. Kalshi or Polymarket on the event the thesis turns on;
  - `"futures"`: e.g. fed funds or SOFR futures for a rate move;
  - `"other market"`: another market-implied measure, named in the source.

  Where none exists, use `"market_probability": 50` with `"market_basis": "none"` and a source saying so ("no
  market-implied probability: coin flip, 0.50"). The fund's Janus rule compares Brier scores with this figure
  (docs/fund/allocation.md). Do not invent a market number: 50 with basis none is the honest answer when there is
  no market price.
- Entries fill at the **next official daily mark** (for futures and options, the first final exchange settlement
  dated on or after today), not at today's price. Positions close automatically at the first mark through the
  stop, on or after the horizon, or at an option's expiry.
- Push to `main` (the script does this). Do not create a branch or a pull request.

## 1. Read the book

```bash
python -m ledger.janus context --fetch > /tmp/janus_context.json
python -m ledger.postmortem due > /tmp/pm_due.json
```

The context lists the rules and the mandate, every open and pending position (entry, stop, horizon, probability,
thesis, change_mind, latest official mark, P&L, distance to stop), the universe with marks (and 1-week and 1-month
levels), the last check, `daily_review_status`, `risk_budget_status` and any `flags`. Note your own model string
(from your system prompt, e.g. `claude-opus-5-5`).

## 1b. Research the drivers (required)

Before deciding anything, research the main drivers across the universe with web search, and keep every source you
read for `sources_read`:
- **Central banks:** Fed, ECB, BoE, BoJ, SNB, BoC and RBA. Cover the latest decisions, minutes and speeches, and
  what futures price for the next meetings.
- **Data:** the releases since the last review (inflation, labour, activity, inventories for energy) and the
  calendar for the coming week.
- **Geopolitics:** conflicts and shipping (Hormuz, the Red Sea), sanctions, OPEC+, elections and trade measures.
- **Positioning:** the latest CFTC Commitments of Traders, flows, surveys, and anything crowded.

Write down, for yourself, the two or three things that matter most today. They feed the market summary and your
ideas. On a weekend or holiday, do the same research: the ideas you name are entered on the next trading day.

## 2. Review every open position

For each one, research today's news, data and prices with web search: the thesis, every "what would change my
mind" trigger, the distance to the stop and the time to the horizon. Decide **hold**, **close** or
**tighten_stop** (with a new, tighter stop), and give a one-to-three-sentence reason. Every open or pending
position must be reviewed.

## 3. Choose new positions (the risk budget)

Rank the views your research supports and take your best ones, even at modest conviction (for example 55%), until
the account is normally at 3-10% at risk in 2-6 positions. For each candidate:
- **Probability:** your honest probability (0-100) that the position closes with a gain before costs. 50 is no
  view; above 70 is rare. Compare it with `market_probability`: the difference is your edge.
- **Size:** the stop is a level in the instrument's own unit, on the losing side of the latest mark. `risk_pct` is
  the % of the account lost if it is hit. Scale it with conviction and edge, as in the mandate's table: a small
  edge gets 0.25-0.5%.
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
                    "probability": 58, "market_probability": 50, "market_basis": "none",
                    "market_source": "no market-implied probability for this level: coin flip (0.50)",
                    "thesis": "Two sentences. Or three.", "change_mind": "...",
                    "sources": [{"title": "...", "url": "https://..."}],
                    "opposition": {"case_against": "...", "key_risks": ["..."], "what_proves_it_wrong": "...",
                                   "probability_view_wrong": 50, "sources": [], "model": "<subagent model>"}}],
 "no_trade_reasoning": "required when new_positions is empty",
 "sources_read": [{"title": "...", "url": "https://...", "driver": "central banks|data|geopolitics|positioning"}],
 "below_budget": {"condition": "US CPI on 12 Nov decides the December Fed call", "until": "2026-11-13",
                  "reasoning": "required only if the account would be below 3% at risk"},
 "deferred_ideas": [{"instrument": "US10Y", "direction": "long", "risk_pct": 0.5, "probability": 56,
                     "market_probability": 50, "thesis": "weekend or market-holiday reviews only"}],
 "market_holiday": "only on a weekday market holiday: its name"}
```

Leave out `below_budget`, `deferred_ideas` and `market_holiday` when they do not apply. Never leave out
`sources_read`.

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

End with a short summary: the drivers you researched, positions reviewed and decisions, new positions (with their
edge over the market probability, size, and The Opposition's probability that each is wrong), the account's risk
against the 3-10% budget (and the `below_budget` reason or the deferred ideas, if any), and the post-mortems
written. Do nothing else in the repository.
