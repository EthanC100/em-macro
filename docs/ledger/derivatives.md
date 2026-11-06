# Futures and options in the Me book

Code: `ledger/derivs.py`. Tests: `tests/test_derivs.py`. Decisions are logged through the clerk
(`docs/ledger/clerk.md`) with the extra lines below.

## Marks: exchange daily settlements by contract month

| product | contract | marked at | proxy |
|---|---|---|---|
| BRENT | ICE Brent crude, by contract month | CME Group daily settlement of NYMEX Brent Last Day Financial (BZ), same month | **yes**: BZ settles to the ICE Brent futures settlement on ICE's last trading day; flagged as proxy |
| WTI | NYMEX WTI (CL) | CME Group daily settlement (CL) | no |
| NATGAS | NYMEX Henry Hub (NG) | CME Group daily settlement (NG) | no |
| HEATOIL | NYMEX NY Harbor ULSD (HO) | CME Group daily settlement (HO) | no |
| RBOB | NYMEX RBOB (RB) | CME Group daily settlement (RB) | no |

Spot prices (EIA via FRED, the Janus estimates) are never used for a contract month. On 3 Nov 2026 spot Brent was
107.03 while March 2027 traded near 94, so in this backwardated market a spot mark would misprice every option.

**Fetching.** `python -m ledger.derivs mark` (run by `ledger-daily`) reads the CME Group settlements page's JSON
for the last five business days. It uses the project's own identifying user agent. If CME refuses an automated
request (cmegroup.com answered 403 to scripted requests from this environment on 6 Nov 2026), the day is skipped
and logged. The workaround is not to get past the block. Instead, a session or I enter the settlement by hand from
the exchange's page:

```bash
python -m ledger.derivs settle --product BRENT --month 2027-03 --date 2026-11-09 --price 95.12 \
       --source "CME Group NYMEX BZ settlements page, read 10 Nov 2026"
```

A hand-entered settlement states its source and acts like a fetched one. Days with no settlement carry the last
P&L, and nothing is closed on them.

## Licence: settlements are stored privately, only P&L in % is published

CME Group's website terms (cmegroup.com Terms of Use, last updated 31 Jan 2025) grant a limited licence for
personal, non-commercial use. They say that, unless CME authorises otherwise, site content may not be sold, copied
or distributed, and that republishing it on a non-CME site needs CME's prior written approval. CME's data terms
list settlement prices among that content. Redistributing them is licensed under CME's Information License
Agreement. ICE's end-of-day data carries similar terms. So:

- **Settlements** are stored only in the private repository `EthanC100/em-macro-data`, in
  `ledger/futures_settlements.csv` (found through `EM_MACRO_DATA`, or `../em-macro-data`). `ledger-daily` checks it
  out with the secret `EM_MACRO_DATA_TOKEN`, a token with contents read and write on that repository. **Add this
  secret once.** Without it, only the entry rows are written and nothing is marked or closed.
- **This repository** publishes `data/ledger/derivative_pnl.csv` only: date, decision id, P&L in % of account, the
  basis (`entry`, `settlement`, `model estimate`, `intrinsic at expiry`), the source's name and the proxy flag. It
  never publishes a settlement, a model value or an exit price. An automatic close writes `exit_price` as text
  ("model estimate (settlement-based; prices kept in em-macro-data)").
- Prices a decision record states itself (entry level, premium, strikes) are mine and stay in the record.

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
