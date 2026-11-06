# Ledger monthly investor letters (the 3rd, retried to the 6th)

You are writing the monthly investor letters, one per book: **Me** (my decisions), the **Algorithm** (v1.0 and
v1.1, frozen mechanical rules, not AI) and **Janus** (an AI paper book, an experiment with no claimed edge). The
session is scheduled on the 3rd to the 6th of each month, after the 3rd-of-month `systematic-monthly` run books the
month that just ended. The later days are there in case that run is late, as on 4 November 2026.

**Hard rules for this session**
- **The figures come from the data and code inserts them verbatim.** You write only the narrative. Every
  percentage you quote must be a figure in the data; the CLI rejects any that is not ("never invent a number").
- **Never edit `data/ledger/` yourself.** Every change goes through `scripts/ledger_commit.sh`, which pushes to
  `main`. Keep scratch files in `/tmp`.
- **Each letter is written once.** The CLI refuses a second letter for the same book and month, and refuses any
  letter before the month is booked.
- **Plain, direct English, no hype.** Describe the algorithm as rules that did something; do not second-guess
  them. Describe Janus as an AI experiment. Forecasts are scored by Brier only and are in no book's P&L.
- **Push to `main`** (the script does this). Do not create a branch or a pull request.

## 1. Is there anything to write?

```bash
python -m ledger.letters figures > /tmp/figures.json     # the month that just ended
```

- If `booked` is false, the month's official figures are not in yet. Stop with "Not booked yet; will retry
  tomorrow" and write nothing.
- If `written` already lists all three books, stop with "Letters already written". Otherwise write only the
  missing ones.

## 2. Write each missing letter

For each missing book, read its block in `figures` and write `/tmp/letter_<book>.json`:

```json
{"summary": "2-3 sentences",
 "what_worked": "2-4 sentences",
 "what_did_not": "2-4 sentences",
 "risk": "2-3 sentences on the current positions and risk"}
```

Use only the figures given. Round percentages as they appear: 0.31% for -0.306 is fine, an unlisted 4% is not. If
a section has nothing to report (for example, no position closed), say so plainly.

```bash
scripts/ledger_commit.sh "Investor letter <book> <YYYY-MM>" -- \
  python -m ledger.letters write --month <YYYY-MM> --book <book> --file /tmp/letter_<book>.json --model <your model string>
```

If it is rejected (exit 1), read the reason, fix the narrative and run it again.

## 3. Finish

End with one line per book: written, already written, or not booked. The letters appear under Reports in the
Ledger.
