# em-macro

How emerging-market currencies and local bonds react to elections and central-bank rate decisions, for Brazil, Mexico,
South Africa, Turkey, Indonesia and Poland, 2005 to October 2026. Built only from free, public sources. Everything is
estimated on 2005–2021, and the 2022+ hold-out was evaluated once against frozen parameters.

**Short answer.**
- **Rate decisions:** policy surprises move currencies in the expected direction, but most decision days are not
  unusual.
- **Elections:** election days are unusual. Currencies move in the direction of the poll surprise, and that held up
  out of sample.
- **Drift and reversal:** the fit sample's election-reversal pattern did not survive the hold-out. The trading rule
  built on it lost money against the carry benchmark.

```
pip install -r requirements.txt
python -m em_macro.run data   # download, build panel + calendars, coverage report, carry benchmark
python -m em_macro.run fit    # 2005-2021 only -> results/fit/, frozen_params.json
python -m em_macro.run test   # 2022+ with frozen parameters -> results/test/ (refuses to run twice)
python -m em_macro.figures    # README charts
python -m em_macro.repricing  # exploratory pre-election repricing (section 7)
pytest -q
```

---

## 1. Data

All series are in `data/processed/daily_panel.csv`, one row per weekday from 2005-01-03 to 2026-10-29. Full coverage
statistics and cross-checks are in [`results/coverage_report.md`](results/coverage_report.md).

| What | Source (free, no API key) | Notes |
|---|---|---|
| Spot FX vs USD: BRL, MXN, ZAR | FRED H.10 (`DEXBZUS`, `DEXMXUS`, `DEXSFUS`), noon New York | Cross-checked against BCB PTAX, Banxico FIX and SARB: 5-day return correlations 0.97, 0.98 and 0.88 |
| Spot FX vs USD: TRY, IDR, PLN | Yahoo Finance (`TRY=X`, `IDR=X`, `PLN=X`) | Not in H.10. Isolated bad ticks removed (6 for IDR). PLN cross-checked against the NBP fixing (5-day correlation 0.90). Yahoo has a 26-day gap in IDR/PLN in Aug 2008 |
| 10y yield, Brazil | Tesouro Direto (Tesouro Transparente) NTN-F rates | Interpolated to 10y. Before ~2007 the longest NTN-F was shorter (maturity recorded in `Y10MAT_BR`) |
| 10y yield, Mexico | Banxico SIE vector of on-the-run Bonos M (7–10y bucket) | Yield to maturity computed from dirty price, coupon and days to maturity. Matches OECD monthly with correlation 0.99 and a −4bp mean gap |
| 10y yield, South Africa | SARB `CMJD004A`, daily average yield on bonds of 10y and longer | Matches OECD monthly with correlation 1.00 |
| 10y yield, Poland | Treasury BondSpot Poland daily fixing, every fixed-rate bond | Interpolated to 10y. Matches OECD monthly with correlation 0.9998 |
| 10y yield, Turkey | Borsa Istanbul debt-market bulletins, **from July 2018 only** | Compound yield of the traded TRY fixed-coupon bond closest to 10y. CPI-linkers and off-market prints removed |
| 10y yield, Indonesia | **none found** | No free, keyless daily history: PHEI shows only 2 days, DJPPR only PDFs, IDX blocks access |
| Policy rates (6 countries + US) | BIS `WS_CBPOL`, daily | |
| Market short rates | BCB CDI, Banxico TIIE-28, SARB JIBAR-3M | Used in the carry sensitivity check |
| US 10y, VIX, fed funds | FRED `DGS10`, `VIXCLS`, `DFF` | |
| Dollar index | Yahoo `DX-Y.NYB` (ICE DXY); FRED broad dollar as a cross-check | |

Raw downloads are cached in `data/raw/` (gitignored) and recreated by `run data`.

## 2. Carry benchmark — the bar to beat

The strategy goes long each currency against USD, earning the local policy rate minus US fed funds. It rebalances
monthly, and every month is charged a 0.10% round-trip cost:
`r_t = S_{t-1}/S_t·(1 + i_loc·τ) − (1 + i_us·τ) − 0.001`, where S is local currency per USD.
These are excess returns, so Sharpe = mean/sd·√12. The basket is the equal-weight average of the available currencies.

![carry](results/fig_carry_basket.png)

| series | period | months | ann. return % | ann. vol % | Sharpe | max drawdown % |
|---|---|---|---|---|---|---|
| Brazil | 2005-2021 (fit) | 203 | 3.4 | 15.8 | 0.29 | -46.4 |
| Brazil | 2022- (hold-out) | 57 | 9.9 | 12.1 | 0.84 | -18.0 |
| Mexico | 2005-2021 (fit) | 203 | -0.4 | 11.6 | 0.03 | -37.9 |
| Mexico | 2022- (hold-out) | 57 | 6.8 | 8.9 | 0.79 | -18.0 |
| South Africa | 2005-2021 (fit) | 203 | -1.7 | 15.7 | -0.03 | -49.8 |
| South Africa | 2022- (hold-out) | 57 | 1.3 | 11.8 | 0.17 | -24.4 |
| Turkey | 2005-2021 (fit) | 203 | -4.8 | 16.7 | -0.20 | -73.7 |
| Turkey | 2022- (hold-out) | 57 | -1.3 | 12.6 | -0.03 | -44.4 |
| Indonesia | 2005-2021 (fit) | 197 | 2.0 | 12.7 | 0.22 | -27.5 |
| Indonesia | 2022- (hold-out) | 57 | -4.3 | 6.2 | -0.69 | -20.7 |
| Poland | 2005-2021 (fit) | 203 | -1.1 | 13.5 | -0.02 | -45.5 |
| Poland | 2022- (hold-out) | 57 | 1.3 | 10.5 | 0.18 | -15.4 |
| **Equal-weight basket** | **2005-2021 (fit)** | 203 | **0.0** | 10.9 | **0.06** | **-37.4** |
| **Equal-weight basket** | **2022- (hold-out)** | 57 | **2.6** | 5.9 | **0.46** | **-10.1** |
| Equal-weight basket | full | 260 | 0.6 | 10.0 | 0.11 | -39.9 |

Swapping in market short rates (CDI, TIIE-28, JIBAR-3M) changes the basket by at most 0.1pp a year.

Full table: [`results/carry_benchmark.csv`](results/carry_benchmark.csv). Monthly returns:
`data/processed/carry_monthly_returns.csv`.

After costs, carry earned nothing for 17 years, with a 37% drawdown. It then had a good 2022–26.

## 3. Event calendar

All events are in `data/events/`. Every row cites its source URL, and the method notes for each research file sit
next to it in `data/events/raw/*_NOTES.md`.

**Elections: 67 votes, 66 event days.** Each two-round contest has a row for each round.

| | BR | MX | ZA | TR | ID | PL |
|---|---|---|---|---|---|---|
| votes | 13 | 10 | 4 | 16 | 6 | 18 |

The calendar covers:
- presidential, legislative and general elections, with first rounds and run-offs;
- referendums;
- Turkey's nationwide local elections and the 2019 Istanbul re-run;
- Mexico's 2021–22 popular consultations and its 2025 judicial election.

Each row records:
- the two leading candidates or parties, ranked by the final polls;
- the final pre-election poll margin, from a poll average where one exists, otherwise the mean of each pollster's last
  poll, with the basis recorded;
- the official result margin;
- where available, prediction-market or betting odds;
- a judgment code for which side financial press called market-friendly, with a citation.

Surprise measures:
- **poll error** = actual margin − final poll margin (pp);
- **signed surprise** = poll error, oriented so that + means the market-preferred side beat its polls. 27 fit-sample
  elections are coded; the rest are judged not clear-cut;
- **odds surprise** = outcome − pre-vote probability. Odds exist only for 8 votes, all in 2022+, so this measure is
  reported but cannot be fitted.

**Rate decisions: 1,251 announcements.** These are all decisions, including holds and unscheduled moves:

| | BR | MX | ZA | TR | ID | PL |
|---|---|---|---|---|---|---|
| decisions | 178 | 197 | 135 | 251 | 260 | 230 |
| with a market expectation | 166 | 30 | 35 | 21 | 22 | 114 |

How the calendar was built and checked:
- **Brazil** comes from the BCB Copom history API. Its expectation is the median Selic for that meeting in the BCB
  **Focus** survey, taken from the last survey before the meeting.
- **Other countries** come from central-bank release archives, with news sources filling gaps (flagged in the notes).
  Expectations come from Bloomberg or Reuters consensus figures quoted in free sources: Deutsche Bank Polska dailies
  for Poland, Anadolu Agency surveys for Turkey, and Reuters polls quoted by Kontan for Indonesia.
- **BIS cross-check:** every hike and cut was checked against the BIS policy-rate series. One BIS error was found
  (Indonesia, Nov 2014) and one missed emergency hike (Indonesia, Aug 2005).
- **Known gaps:**
  - About 15 Polish hold meetings in 2005–06 are missing.
  - The March 2011 Bank Indonesia meeting is undated.
  - Mexico's 2005–07 "corto" announcements are coded as hikes or cuts by interpretation.
  - Turkey's 28-May-2018 change of operating framework is flagged `technical` rather than counted as a +850bp hike.
- **Surprise:** actual change − expected change, in bp.

## 4. Method

**Timing:** for an event dated *d*:
- **base** is the last weekday before *d*;
- **day h** is the h-th weekday after *d*;
- a move at h is level(day h) − level(base).

So "day 1" covers the event day plus the next session. This captures Sunday votes (Friday to Monday), Copom's
after-close announcements, and intraday decisions alike, even though FX snapshot times differ by source. A window
end must be a fresh observation dated after the base. Units are % change in the local currency's USD value
(+ = appreciation) and bp change in the 10y yield.

**Abnormal moves:**
- **Model:** for each series, `y = a + b1·ΔDXY + b2·ΔUS10y + b3·ΔlogVIX + e`, estimated on non-overlapping 5-day
  changes over **2005–2021 only**, and applied unchanged to hold-out events.
- **Abnormal move:** the actual move minus the move predicted from the same-window factor moves (`results/fit/factor_betas.csv`).
- **Statistics:**
  - a cross-sectional t;
  - a standardised z, where each move is divided by its normal-time residual sd (Boehmer-style);
  - a **variance ratio**: mean(abnormal²)/normal variance, where >1 means event days move more than ordinary days.

**Surprise regressions** (OLS, robust SE):
- election moves on the signed poll surprise;
- |election move| on |poll error|;
- decision moves on the rate surprise, pooled and by country.

**Drift vs reversal:**
- **Regression:** `move(day1→day h)` on `move(base→day1)`, both scaled by normal-time sd. A positive slope means drift
  (continuation); a negative slope means reversal.
- **Raw-move version:** the same regression on unadjusted moves. These are tradeable, because the raw day-1 move is
  known at the day-1 price.
- **Placebo:** the same regression on ~2,800 non-event "placebo" days, to separate event-specific behaviour from
  generic short-term reversal and timing artefacts.

**Hold-out discipline:**
- **What fit sees:** only events whose 20-day window closes by 2021-12-31, and only factor data through 2021.
- **What is frozen:** everything the test needs — betas, regression coefficients and the trading rule — is in
  `results/fit/frozen_params.json`. It was committed before the test ran (commit `08c4f07`).
- **Pre-registered rule:** for each event type, trade FX from day 1 to day 5 (or day 20), in the direction of the
  fit-sample raw drift slope, *only if that slope has p < 0.10*. Each trade earns the rate differential and is charged
  0.10% round trip. Result: elections are traded as **fade the day-1 move**; rate decisions are not traded.
- **One disclosed re-run:** after the first hold-out evaluation I found a data-alignment bug. When a country's own
  series had no fresh print, a window end silently reused the base-day price. Examples are FRED's BRL series ending
  on 23-Oct-2026, and US holidays.
  - The fix changed two fit-sample rows (EL_BR_20181007 FX, RD_ID_20080805 FX) and did not change the trading rule.
  - Fit and test were re-run once.
  - The first run is kept in `results/test_run1_superseded/`. Its strategy results are identical, and its
    regression numbers differ only through the dropped Brazil run-off FX row.

## 5. Findings — fit sample, 2005–2021

All files are in `results/fit/`. Moves are abnormal unless marked raw.

**Rate decisions.**

Currencies respond to the direction of the decision, but holds are non-events:

| FX, day 1 | n | mean % | t | variance ratio |
|---|---|---|---|---|
| hikes | 137 | +0.56 | 4.1 | 2.0 |
| cuts | 227 | −0.17 | −1.9 | 1.4 |
| holds | 611 | −0.02 | −0.5 | 0.9 |

- **All decisions together:** the variance ratio is only 1.17. Most decisions are anticipated.
- **Surprises do move markets:**
  - **Brazil** (Focus, n=127): BRL gains 0.016% per bp of hawkish surprise on day 1 (t=1.9) and 0.028% by day 5
    (t=2.7). A 25bp surprise is worth about 0.4–0.7%.
  - **10y yields respond to surprises** in Mexico (+0.50bp per bp, t=6.1), Poland (+0.30, t=4.4) and South Africa
    (+0.28, t=2.4).
  - **Pooled across all countries** the FX effect is weak (t=1.3). Expectation coverage outside Brazil and Poland is
    thin and partly qualitative.
- **Long yields after hikes:** they fall 5bp on day 1 (curve flattening, t=−2.0), then rise 15bp by day 20 (t=2.8).

**Elections.**
- **Yields** move clearly. Day-1 10y yields fall 10.8bp on average (n=35, t=−2.6, z=−2.4), consistent with uncertainty
  resolving. General elections fall 17bp (t=−2.0), with a variance ratio of 4.
- **Currencies** on general elections (presidential and congressional votes together) have a day-1 variance ratio of
  2.2. They gain +2.1% by day 5 (n=12, t=4.7), but n is small.
- **Signed poll surprise:**
  - **FX:** +0.06% per pp, not significant in-sample (t=1.3, n=26).
  - **Yields:** −2.4bp per pp (t=−2.0, n=17). When the market-preferred side beats its polls, yields fall.
- **The size of the poll miss** does not predict the size of the move (|move| on |poll error|: t=−1.4).

**Drift vs reversal** (slope of day 1→5 on day 1; t in parentheses):

| | abnormal | raw | placebo days (raw) |
|---|---|---|---|
| FX, elections | −0.46 (−2.1) | −0.55 (−2.0) | 0.00 (0.0) |
| FX, rate decisions | −0.25 (−3.9) | −0.08 (−1.2) | — |
| 10y, elections | +0.47 (3.1) | +0.39 (2.7) | +0.15 (1.7) |
| 10y, rate decisions | +0.06 (0.7) | +0.13 (1.5) | — |

- **Rate decisions:** the apparent FX reversal is mostly an artefact of the factor adjustment, mixing noon-NY FX with
  end-of-day US factors. On raw moves it is small and insignificant, and placebo days show the same adjusted pattern
  (−0.06 at h=5, −0.26 at h=20).
- **Elections:** in-sample, currencies **reverse** part of their day-1 move. Bond moves **continue**.

Applying the pre-registered fade-the-day-1-move rule to elections in-sample earns +1.0% a year with a Sharpe of 0.23
(50 trades). That beats in-sample carry (Sharpe 0.06), but the rule was chosen on the same data.

## 6. Hold-out, 2022 to Oct 2026 — evaluated once

All files are in `results/test/`.

**Trading rule vs carry** (`strategy_vs_carry.csv`, monthly, 2022-01 to 2026-09):

| | ann. return % | Sharpe | max DD % | trades | hit rate |
|---|---|---|---|---|---|
| carry basket (the bar) | +2.6 | 0.46 | −10.1 | — | — |
| fade election day-1 move, hold to day 5 | −3.3 | −1.00 | −15.7 | 14 | 29% |
| fade election day-1 move, hold to day 20 | −4.8 | −0.53 | −26.2 | 14 | 43% |

**The rule fails.** Hold-out election FX moves *continued* rather than reversed: the raw slope is +0.46 (t=1.7, n=14).
It lost on Brazil's 2022 run-off, Turkey's 2023 run-off and Mexico's 2024 election. The in-sample reversal is best
read as a small-sample artefact, not a tradeable effect.

**What did hold up** (`oos_surprise_predictions.csv`):
- **Poll surprise and day-1 FX moves:** the frozen fit-sample regression predicts the hold-out moves with a
  correlation of 0.72, the right sign in 8 of 9 elections, and an out-of-sample R² of 0.15 against a zero forecast.
  The cases are Brazil 2022 and 2026, Poland 2023 and 2025, Turkey 2023 and Indonesia 2024 (chart below).
- **But the fitted slope was not significant in-sample**, and 9 events is very few. Treat this as consistent evidence,
  not proof.
- **The bond-yield surprise regression did not hold up** (R² ≈ 0, correlation −0.17).
- **The rate-surprise regressions add almost nothing out of sample** (pooled FX correlation 0.18, R² 0.02).
- **Rate decisions overall:** hold-out decisions are even quieter than in-sample. The FX variance ratio is 0.82, hikes
  average +0.15% with t=0.9, and the FX drift slopes are insignificant.

![election surprise](results/fig_election_surprise.png)

**The biggest hold-out events:**
- **Brazil, 2-Oct-2022, first round:** Bolsonaro beat his polls by 7.8pp. BRL +4.1% abnormal on day 1, 10y −31bp.
- **Brazil, 4-Oct-2026, first round:** BRL +4.8%, 10y −120bp.
- **Brazil, 25-Oct-2026, run-off:** Lula beat odds that gave Flávio Bolsonaro 80%. The 10y rose +255bp on day 1. The
  FX move is outside the study because FRED's BRL ends on 23-Oct, but BCB PTAX shows BRL −8.4%.
- **Turkey, 14-May-2023:** the 10y fell 298bp on day 1 and 533bp by day 5.
- **Mexico, 2-Jun-2024:** MXN −3.5% on day 1 and −7.2% by day 5. Note this is *not* a poll miss on the presidency
  (Sheinbaum led by 17pp and won by 33pp). The worry was Morena's congressional supermajority, which a two-candidate
  margin cannot capture.

## 7. Exploratory: pre-election repricing as polls and odds move

> **Exploratory.** This section was added after the hold-out evaluation. It uses all dates, including 2022+, and is
> not part of the frozen fit/test design. Nothing in it was pre-registered, and it runs many regressions, so isolated
> significant coefficients are expected by chance.

**Question.** In the six months before a vote, do currencies and 10y yields move day by day with the leading
candidate's poll margin or win probability?

**Signals.**
- **Betting odds:** daily Polymarket prices for the 6 elections that have a stored price history.
  - Brazil 2026 (Lula), Mexico 2024 (Sheinbaum), Turkey 2023 (Kılıçdaroğlu, i.e. 1 − Erdoğan) and Poland 2025
    (Trzaskowski) price who wins.
  - Indonesia 2024 (Prabowo) and South Africa 2024 (ANC wins a seat majority) also have histories.
  - Polymarket's Brazil 2022 market has no stored history, and there were no markets for earlier votes.
  - For markets that price the eventual winner, the window runs on to the run-off. The round-1 result day is dropped
    (it is the election-day event in §4–6).
- **Polls:** 2,497 poll rows compiled from Wikipedia poll tables (exact page revisions cited). Files:
  `data/events/raw/prevote_polls_*.csv` and their NOTES.
  - **Daily poll-of-polls:** the mean, across pollsters, of each pollster's latest released poll from the last 30 days.
  - **Release date:** fieldwork end + 1 day where no publication date is given (almost always).
  - **Two-party margin:** 100·(a−b)/(a+b). Bases (total, decided, valid) are mixed within elections, so two-party
    shares keep polls comparable.
  - **Eligibility:** ≥1 poll per week over the window. Brazil 2018 scenarios with Lula as the candidate are excluded.
  - **Head-to-head run-off simulations** fielded before round 1 are a separate signal (Brazil 2018/22/26, Poland 2025,
    Turkey 2023).
  - **What qualified:** 21 elections with a first-round/single-round poll signal and 5 with a head-to-head signal.
    Poland 2020 qualified but the window is too short to estimate.
- **Orientation:** every signal is oriented to the **leading candidate** (`cand_a` in `elections.csv`). For pooling
  and sign checks it is re-oriented toward the side the press called market-preferred, where that is coded.

**Regression** (`em_macro/repricing.py`):
`ΔFX_d (or Δy10_d) = a + b·ΔS_d + c1·ΔDXY_d + c2·ΔUS10y_d + c3·ΔlogVIX_d`, on weekdays, with HAC(5) standard errors.
- **Sensitivity units:** FX % (+ = local currency up) or bp, per **1pp of two-party poll margin** or per **10pp of win
  probability**.
- **Lead/lag:** a distributed lag of ΔS from 5 days before to 5 days after. Sums over the 5 future signal changes mean
  the market leads; sums over the 5 past changes mean it lags.
- **Partial reversal:** local projections of the cumulative move from d−1 to d+h (h = 0…10) on ΔS_d. The share of the
  day-0/1 response still present at h = 10 is computed only when that initial response is significant.

**Brazil 2022 and Mexico 2024** (`results/repricing/sensitivity_leadlag.csv`; t in parentheses):

| | signal | FX % per unit | 10y bp per unit | currency leads (Σ leads) | currency lags (Σ lags) |
|---|---|---|---|---|---|
| Brazil 2022 (Lula − Bolsonaro) | poll margin, per 1pp | −0.01 (−0.1) | −2.3 (−2.5) | FX −0.10 (−0.6); 10y +9.9 (2.8) | FX −0.41 (−2.6); 10y +3.8 (1.0) |
| Brazil 2022 | run-off simulation, per 1pp | −0.02 (−0.2) | −2.7 (−2.4) | FX −0.25 (−1.2); 10y +9.2 (2.4) | FX −0.46 (−2.3) |
| Mexico 2024 (Sheinbaum − Gálvez) | poll margin, per 1pp | 0.00 (0.4) | +0.2 (1.0) | FX −0.02 (−0.7) | FX −0.05 (−1.9); 10y +0.6 (2.6) |
| Mexico 2024 | Polymarket, per 10pp | −0.14 (−1.0) | +0.1 (0.1) | FX −0.40 (−0.6) | FX +0.33 (0.6) |

- **Mexico 2024** shows nothing: Sheinbaum led by a wide margin and was priced at about 93% throughout, so neither signal
  carried news.
- **Brazil 2022** shows no same-day BRL response to polls. One item fits a delayed reaction: a Lula gain is followed
  by a weaker BRL over the next five days (Σ lags −0.41% per pp, t=−2.6).
- **Brazil 2022 10y yields** go the "wrong" way on the day: −2.3bp per pp of Lula margin. Their lead terms go the other
  way (+9.9bp, t=2.8). This sign flip, combined with Tesouro Direto's morning quote times, points to timing noise, or
  to a common cause, rather than a clean poll effect. The mid-2022 fiscal package moved Bolsonaro's polls and yields at
  the same time.

**All elections** (`results/repricing/evidence_counts.csv`, `pooled.csv`; significance means |t| ≥ 1.96):

| signal / asset | elections | same-day b significant | expected sign¹ (of coded) | expected sign & significant | market leads signif. | market lags signif. |
|---|---|---|---|---|---|---|
| odds / FX | 6 | 0 | 1 of 4 | 0 | 1 | 1 |
| odds / 10y | 5 | 1 (South Africa) | 1 of 3 | 0 | 1 | 1 |
| polls / FX | 21 | 0 | 10 of 17 | 0 | 3 | 5 |
| polls / 10y | 15 | 1 (Brazil 2022, wrong sign) | 5 of 12 | 0 | 4 | 2 |
| run-off sims / FX | 5 | 0 | 3 of 5 | 0 | 2 | 1 |
| run-off sims / 10y | 5 | 1 (Brazil 2022, wrong sign) | 1 of 5 | 0 | 2 | 0 |

¹ "Expected sign" means the local currency rises, or the yield falls, as the market-preferred side gains.

**Pooled** (oriented toward the market-preferred side, election-specific controls):

| signal | elections | FX per unit | t |
|---|---|---|---|
| polls | 17 | +0.017% per pp | 0.9 |
| run-off simulations | 5 | −0.006% per pp | −0.2 |
| odds | 4 | −0.11% per 10pp | −1.6 |

**Reading.**
- **Sensitivity:** no election shows a significant same-day currency response to poll or odds changes. Signs split
  roughly 50/50 around the market-friendly hypothesis: 10 of 17, 3 of 5 and 1 of 4. The largest point estimates are
  economically small:
  - **Brazil 2026:** −0.46% BRL per 10pp rise in Lula's win probability, t=−1.9. This has the expected sign, since
    Flávio Bolsonaro was coded market-preferred.
  - **Poland 2025:** −0.30% PLN per 10pp for Trzaskowski, t=−1.9. This is the wrong sign.
- **The only significant same-day coefficient** is South Africa 2024: the 10y falls 2.6bp per 10pp of ANC-majority
  probability (t=−5.1). It rests on 32 trading days of a thin market.
- **Lead/lag:** significant lead sums appear in 1–4 elections and lag sums in 0–5 per signal/asset row, with no
  consistent direction. For polls this is also limited by dating: fieldwork end + 1 is only a proxy for when a poll
  became public. For FX against odds, FRED's noon-New-York FX predates Polymarket's end-of-day (UTC) price, which by
  itself would make FX look one day late. **No conclusion about leading or lagging is supported.**
- **Partial reversal:** the initial response is significant in only 1–2 elections per row. Among those, only 1 (polls,
  FX) gives back half or more within 10 days. **There are too few events to say anything about reversal.**
- **Bottom line:** with free daily polls and odds, pre-election repricing is not detectable day by day in these six
  markets. The election-day jump (§5–6) is where the information shows up.

**Caveats specific to this section.**
- **Odds history:** Polymarket covers only 2023–26, and several markets were thin (South Africa, Indonesia,
  Mexico 2024).
- **Turkish lira:** TRY was heavily managed in 2023, so FX sensitivities there are mechanically near zero.
- **Poll timing and noise:** fieldwork-to-publication lags vary. The daily poll average jumps when a pollster with a
  large house effect publishes.
- **What the regressions measure:** association, not causation. Campaign news, fiscal announcements and global shocks
  move polls and markets together.

## 8. Limitations

- **Small samples.**
  - There are 66 election days, of which only 27 fit-sample elections have a signed, coded surprise (26 with a day-1
    FX move), and 14 hold-out election days in total.
  - Any country-by-type cell for elections is anecdotal.
  - Betting odds exist only for 2022+, so the odds-surprise regression could not be estimated.
- **Judgment coding.**
  - The "market-preferred" side is a press-based judgment. Several codings in Turkey, Indonesia and South Africa lean
    on how markets reacted after the vote.
  - Poll bases differ across countries and decades: valid-vote vs all-voter shares, and averages vs single polls. The
    method for each row is in the NOTES files.
  - A two-candidate margin misses coalition and legislative-majority stakes (South Africa 2024, Mexico 2024).
- **Expectations for rate decisions.**
  - Only Brazil (Focus) and Poland (a Bloomberg consensus from 2019) have systematic coverage.
  - Mexico, South Africa, Turkey and Indonesia have 21–35 surveyed meetings each, mostly after 2015.
  - Some expectations are coded from "as expected" or "surprise" wording rather than a numeric poll.
- **Yield data.**
  - No Indonesian daily 10y.
  - Turkey's 10y starts in July 2018; the traded bond closest to 10y is noisy and thinly traded.
  - Brazil's "10y" before 2007 is the longest NTN-F, at 3–9y.
  - South Africa's series is a 10y-plus average, and Mexico's benchmark maturity drifts between 7.5 and 10.9y.
  - Tesouro Direto quotes are morning snapshots.
- **FX data.**
  - Yahoo's daily FX close for TRY, IDR and PLN is taken in the late European evening, versus noon New York for
    H.10. The day-1 window
    absorbs this, but the factor adjustment mixes timestamps, which is why the abnormal-move reversal on rate
    decisions is an artefact.
  - Yahoo has an Aug-2008 gap in IDR/PLN.
  - FRED H.10 ends on 23-Oct-2026 in this download.
- **Carry uses policy rates.**
  - Turkey's effective funding cost exceeded the one-week repo for much of 2011–18 and in 2021–23, so TRY carry is
    understated.
  - Turkey's corridor-era tightenings (e.g. 23-May-2018) appear as "holds" in the calendar.
  - Indonesian policy rates start in July 2005.
- **Costs** are a flat 0.10% round trip. Real EM FX costs vary with crises and with the size of the trade.
- **One re-run.** The hold-out was evaluated a second time after a data-alignment bug fix, as disclosed in §4. Neither
  the frozen rule nor the conclusions changed.

## Repository layout

```
em_macro/
  config.py        countries, series ids, sample split
  sources.py       downloaders: FRED, Yahoo, BIS, BCB (SGS, Copom, Focus), Banxico SIE, SARB, NBP,
                   Tesouro Direto, BondSpot, Borsa Istanbul
  yields.py        Brazil (NTN-F) and Mexico (Bono M) 10y construction
  extra_yields.py  Poland (BondSpot) and Turkey (BIST) 10y construction
  build_data.py    daily panel + coverage report
  carry.py         carry benchmark
  events.py        Copom + Focus calendar; merges research calendars; surprise measures
  event_study.py   windows, factor betas, abnormal moves, summaries, drift regression, placebo days
  run.py           data / fit / test stages, drift-rule backtest
  repricing.py     exploratory pre-election repricing (polls, Polymarket odds) -> results/repricing/
  figures.py       README charts
data/events/       elections.csv, rate_decisions.csv (+ raw/ research files with NOTES)
data/processed/    daily_panel.csv, carry_monthly_returns.csv, event_table.csv, coverage.csv
results/           coverage_report.md, carry_benchmark.csv, fit/, test/, test_run1_superseded/, figures
tests/             unit tests (bond maths, windows, carry formula, spike filter)
```
