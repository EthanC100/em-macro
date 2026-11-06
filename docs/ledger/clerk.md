# Ledger clerk (runbook)

Use this runbook when I paste a `DECISION RECORD`, `FORECAST` or `RESOLVE` block into a Claude Code session on
em-macro and ask for it to be logged, however I phrase the request ("log this", "Ledger clerk", or just the block).
The clerk is `python -m ledger.clerk`. Its parsing and checks are the intake workflow's own: the same field parser
as the "Quick decision (paste)" form, the same required fields, and the Risk Manager with its sizing rules. It writes
through `scripts/ledger_commit.sh`, so every entry is sealed in the audit chain and pushed to `main`.

**Hard rules for this session**
- **Never edit `data/ledger/` yourself**, and never "fix" a block silently. If something is wrong, show me the
  clerk's list of problems and ask me what to change. Re-run the clerk on the corrected block.
- **The block is mine.** Copy it exactly as I pasted it. Add a line only when I gave you that field's value in the
  same message, and show me every line you added.
- **Show me the Risk Manager result before you log**, every time, even when it passes.
- Keep the block file outside the repository (`/tmp/...`), because the script needs a clean working tree.
- Push to `main` (the script does this). Do not open a branch or a pull request for a ledger entry.

## 1. Save the block

```bash
cat > /tmp/block.txt <<'EOF'
<the block exactly as pasted>
EOF
```

## 2. Check it and show me the Risk Manager result

```bash
python -m ledger.clerk check /tmp/block.txt
```

This writes nothing. It prints the Risk Manager comment (verdict, each check ✅/❌, flags ⚠️ for overlap with the
algorithm or catalysts in the holding period, notes ℹ️), then the intake message, then either
`WOULD LOG: decision D0xx` or `NOT LOGGED`.

Paste the printed Risk Manager section into your reply verbatim.
- **`NOT LOGGED`:** list every problem it printed and stop. Do not guess the fix.
- **Passed (with or without flags):** say so in one line and go to step 3. Flags never block logging. Mention them.

## 3. Log it

```bash
python -m ledger.clerk log /tmp/block.txt
```

`log` runs the same check again. Then `scripts/ledger_commit.sh` fetches `main` and re-runs the handler there, so
the id is the next free one on `main`. The script then seals the entry (`python -m ledger.audit seal`), verifies the
audit and Janus chains, commits ("Ledger clerk: decision D0xx ...") and pushes. If someone else pushed first, it
retries from the new `main`. It ends with `LOGGED: <kind> <id>` and `pushed <commit> to main`.

Reply with the **new id**, the commit, and anything the intake message says needs attention (for example "No numeric
entry level found").

If the script fails, give me its output. Nothing was committed. Do not retry more than once.

## 4. Block formats

`Field: value`, one field per line. A long value may continue on the next lines. Dates may be `2026-11-06` or
`6 Nov 2026`. The header line comes first.

**DECISION RECORD** (all required): Date, Country, Instrument, Action (Buy / Sell / No trade), Size (% of account
at risk), Probability, Horizon, Entry trigger (put the entry level in it, e.g. "at 5.40"), Stop / exit if wrong
(with a numeric level, e.g. "closes below 85.00"), Thesis, Key factors, What would change my mind, How this
differs from market consensus. Optional: `Position type: event bet`. Without it, a Buy or Sell is a continuous
position.

**Risk Manager rules:** the stop needs a numeric level. A continuous position risks at most 2% of the account. An
event bet must be sized at half of quarter-Kelly on its probability at even odds: 0.125 × (2p − 1), so 60% gives
2.5% and 62% gives 3%. Flags: the algorithm holds the same country or currency, or a catalyst falls in the holding
period.

**Futures and options** (ledger/derivs.py, docs/ledger/derivatives.md): add these lines to the DECISION RECORD.
Contract (e.g. `ICE Brent March 2027`), Legs (`long 110 call, short 130 call`), Option expiry (a date), Underlying
at entry (the future's price), Premium (per unit), and Implied volatility (a number with its source, or `estimate`,
or `implied from premium`). Optional: Structure, IV source, Quantity. The Risk Manager then checks the maximum loss:
the premium for a long option or debit spread, width − credit for a credit spread, and it refuses a naked short
option. The stop must be a level of the underlying future on the losing side. Settlement prices are licensed and are
kept in em-macro-data. The Ledger publishes P&L in % only, and labels options a "model estimate".

**FORECAST:** Question, Probability, Resolves by. Optional: Market probability, Market source, Claude probability,
Resolution source, Country.

**RESOLVE:** Id (D001 or F003), Outcome (right / wrong / scratched for a decision; yes / no / void for a forecast),
Exit price or result. Optional: P&L (% of account), Note.

## 5. Running it yourself

`python -m ledger.clerk check -` reads the block from standard input. `--today YYYY-MM-DD` sets the logging date
(default today). The GitHub forms (Decision record, Quick decision (paste), Resolve) remain the backup route and run
the same checks.
