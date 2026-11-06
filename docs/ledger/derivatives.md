# Futures and options in the Me book

Code: `ledger/derivs.py`. Tests: `tests/test_derivs.py`. Decisions are logged through the clerk
(`docs/ledger/clerk.md`) with the extra lines below.

## Marks: exchange final settlements by contract month (Databento)

Code: `ledger/settlements.py`, which reuses `em_macro/commod_databento.py`. Each mark is the exchange's **final** daily
settlement of the position's own contract month, from Databento GLBX.MDP3 (CME Globex MDP 3.0), schema
`statistics`: stat_type 3 with the final bit of stat_flags set. The preliminary settlement CME sends first is
ignored.

| product | contract | Globex root | proxy |
|---|---|---|---|
| BRENT | ICE Brent crude, by contract month | NYMEX Brent Last Day Financial, BZ, same month | **yes**: BZ settles to the ICE Brent futures settlement on ICE's last trading day; flagged as proxy |
| WTI, NATGAS, HEATOIL, RBOB | NYMEX CL, NG, HO, RB | CL, NG, HO, RB | no |
| GOLD, SILVER, COPPER | COMEX GC, SI, HG | GC, SI, HG | no |
| CORN, SOYBEANS, WHEAT | CBOT ZC, ZS, ZW (prices in US cents per bushel) | ZC, ZS, ZW | no |

Spot prices (EIA via FRED) are never used for a contract month. On 3 Nov 2026 spot Brent was 107.03 while March
2027 traded near 94, so in this backwardated market a spot mark would misprice every option.

**Daily run.** `ledger-daily` runs `python -m ledger.settlements fetch`. It fetches every contract month the books
need: my open futures and options decisions from their entry date, Janus's positions, and the front and next
contract of each Janus market. It sends one request, starting the day after the last stored settlement.
`ledger.derivs mark --no-fetch` and `ledger.janus mark` then mark from the store. Databento's historical data runs
a few hours behind. A day's final settlement (sent by CME after about 00:30 UTC) is usually available by about
09:00 UTC, so the 09:22 UTC backup run picks it up when the 05:52 run is too early.

**Cost guard.** Every request is quoted first (`metadata.get_cost`). It is refused when it would take the day's
(UTC) spend above **US$1.00**. The cap is shared by my marks and Janus's. Quotes, requests and refusals are logged
privately in `ledger/databento_spend.jsonl`. A typical daily request costs well under US$0.01: the first run, ten
days of 22 contract months, was quoted at US$0.0059 on 6 Nov 2026.

**Dropped: the CME website.** On 6 Nov 2026, cmegroup.com held every scripted request from GitHub Actions until
the 60-second timeout, five times a run, and answered 403 from other environments. That fetch is gone. Hand entry
remains for emergencies:

```bash
python -m ledger.derivs settle --product BRENT --month 2027-03 --date 2026-11-09 --price 95.12 \
       --source "..."
```

## Licence: settlements are stored privately, only P&L in % is published

CME's terms do not allow settlement prices to be copied, redistributed or republished without CME's licence:
cmegroup.com's Terms of Use (last updated 31 Jan 2025), its data terms, and the Information License Agreement.
Databento adds no restrictions of its own but passes CME's on. So:

- **Settlements** are stored only in the private repository `EthanC100/em-macro-data`, in
  `ledger/futures_settlements.csv`, with the spend log beside it. `ledger-daily` checks the repository out with
  the secret `EM_MACRO_DATA_TOKEN` and fetches with `DATABENTO_API_KEY`.
- **This repository** publishes P&L in % of account only: `data/ledger/derivative_pnl.csv` for my decisions and
  `data/janus/futures_pnl.csv` for Janus. It never publishes a settlement, a model value, a fill or exit price, a
  notional or a contract count. An automatic close writes `exit_price` as text.
- Prices a decision record states itself (entry level, premium, strikes) are mine and stay in the record. Janus's
  stop levels are Janus's own decisions and stay in its records.
- Before relying on this beyond personal use, confirm in Databento's licence manager which CME use category the
  account falls under. Automated daily pulls may count as non-display use.

## Options: model estimate (Black-76)

- Value per unit = Σ legs q × Black-76(F, K, T, σ, r). F is the underlying contract month's daily settlement. T is
  the time to the option expiry in years (act/365). σ is the implied volatility recorded at entry. r is the 3-month
  T-bill (FRED DTB3) at entry.
- **Implied volatility** is recorded at entry with its source, or as an estimate. `Implied volatility: implied from
  premium` backs it out of the stated premium with Black-76. It is recorded as "estimate: implied from the stated
  entry premium ...; not an observed market implied volatility". For a vertical, value is not monotonic in σ (it
  goes to 0 as σ grows without bound), so the lowest σ that reproduces the premium is used. It changes only with
  `python -m ledger.derivs iv <id> <iv> --source "..."`, run through `scripts/ledger_commit.sh`. A source is
  required, and "estimate" is refused. Updates go to `data/ledger/iv_updates.csv` and are sealed.
- The app labels the value **model estimate**. From the option expiry date the value is **intrinsic** on that day's
  settlement: max(F − K, 0) for a call, max(K − F, 0) for a put.
- **Maximum loss:** for a long call, a long put or a debit vertical it is the premium, so size (% at risk) = premium.
  For a credit vertical it is width − credit. A naked short option has no defined maximum loss and is rejected.
  P&L in % of account = size × (value − entry value) / maximum loss per unit, so a debit structure can never lose
  more than its size.
- **Futures:** P&L = size × q × (F − entry) / |entry − stop|, as for every linear position.

## Closes

Only a daily exchange settlement of the contract month can act, or of its flagged proxy. A decision closes:
- **Stop:** when that settlement crosses the stop, which is a level of the underlying future (for example "close
  below 85.00"). It closes at that day's model value.
- **Horizon:** at the model value on the first settlement on or after the horizon.
- **Option expiry:** at intrinsic value.

The spot-proxy resolver (`ledger/resolve.py`) skips these decisions. A Resolve block or form can override an
automatic close. For an option, the exit is the structure's price per unit, and P&L = size × (exit − premium) /
premium.

## Decision record lines

| line | example |
|---|---|
| Contract | `ICE Brent March 2027` (else read from the Instrument) |
| Structure | `call spread`, `put spread`, `call`, `put`, `future` (else from the legs) |
| Legs | `long 110 call, short 130 call` or `+1 C 110, -1 C 130` (else read from the Instrument) |
| Option expiry | `2027-01-26` |
| Underlying at entry | `94.00` (the future's price) |
| Premium | `3.00` (per unit; a credit is negative) |
| Implied volatility | `48% (CME CVOL, 6 Nov 2026)`, `55 estimate`, or `implied from premium` |
| IV source | optional, if not given on the line above |
| Quantity | optional, e.g. `65` |

A decision whose Instrument names a supported future and a call, a put or a contract month is a futures or options
position. Without these lines it is rejected, so it can never be marked on spot.
