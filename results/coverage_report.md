# Data coverage report

Daily panel: 2005-01-03 to 2026-10-29, 5694 weekdays. Coverage = share of weekdays with an observation (holidays count as missing, so ~96% is complete).

## Series

| series | source | first | last | obs | % weekdays since 2005 | % since first obs | max gap (days) |
|---|---|---|---|---|---|---|---|
| FX_BR | FRED DEXBZUS | 2005-01-03 | 2026-10-23 | 5465 | 96.0 | 96.0 | 5 |
| FXCHK_BR | BCB SGS 1 | 2005-01-03 | 2026-10-28 | 5479 | 96.2 | 96.2 | 5 |
| FX_MX | FRED DEXMXUS | 2005-01-03 | 2026-10-23 | 5465 | 96.0 | 96.0 | 5 |
| FXCHK_MX | Banxico SIE SF43718 | 2005-01-03 | 2026-10-28 | 5491 | 96.4 | 96.4 | 5 |
| FX_ZA | FRED DEXSFUS | 2005-01-03 | 2026-10-23 | 5465 | 96.0 | 96.0 | 5 |
| FXCHK_ZA | SARB EXCX135D | 2005-01-03 | 2026-10-28 | 5455 | 95.8 | 95.8 | 5 |
| FX_TR | Yahoo Finance TRY=X | 2005-01-03 | 2026-10-29 | 5674 | 99.6 | 99.6 | 5 |
| FX_ID | Yahoo Finance IDR=X | 2005-01-03 | 2026-10-29 | 5654 | 99.3 | 99.3 | 26 |
| FX_PL | Yahoo Finance PLN=X | 2005-01-03 | 2026-10-29 | 5660 | 99.4 | 99.4 | 26 |
| FXCHK_PL | NBP usd | 2005-01-03 | 2026-10-28 | 5512 | 96.8 | 96.8 | 6 |
| Y10_BR | Tesouro Direto (Tesouro Transparente) NTN-F | 2005-01-03 | 2026-10-27 | 5446 | 95.6 | 95.6 | 7 |
| Y10MAT_BR | derived | 2005-01-03 | 2026-10-27 | 5446 | 95.6 | 95.6 | 7 |
| Y10_MX | Banxico SIE CF300 (SF45455/45478/45430) | 2005-01-03 | 2026-10-28 | 5491 | 96.4 | 96.4 | 5 |
| Y10MAT_MX | derived | 2005-01-03 | 2026-10-28 | 5491 | 96.4 | 96.4 | 5 |
| Y10_ZA | SARB CMJD004A | 2005-01-03 | 2026-10-27 | 5447 | 95.7 | 95.7 | 6 |
| Y10_TR | Borsa Istanbul debt market bulletin | 2018-07-02 | 2026-10-28 | 2073 | 36.4 | 95.4 | 7 |
| Y10_PL | Treasury BondSpot Poland fixing | 2005-01-03 | 2026-10-28 | 5456 | 95.8 | 95.8 | 6 |
| POL_BR | BIS WS_CBPOL D.BR | 2005-01-01 | 2026-10-20 | 7963 | 99.9 | 99.9 | 1 |
| POL_MX | BIS WS_CBPOL D.MX | 2005-01-03 | 2026-10-20 | 7521 | 99.3 | 99.3 | 5 |
| POL_ZA | BIS WS_CBPOL D.ZA | 2005-01-03 | 2026-10-19 | 6565 | 95.7 | 95.7 | 4 |
| POL_TR | BIS WS_CBPOL D.TR | 2005-01-03 | 2026-10-16 | 5481 | 96.3 | 96.3 | 7 |
| POL_ID | BIS WS_CBPOL D.ID | 2005-07-05 | 2026-10-19 | 5207 | 91.1 | 93.3 | 12 |
| POL_PL | BIS WS_CBPOL D.PL | 2005-01-03 | 2026-10-20 | 5506 | 96.7 | 96.7 | 6 |
| POL_US | BIS WS_CBPOL D.US | 2005-01-01 | 2026-10-20 | 7962 | 99.9 | 99.9 | 2 |
| STR_BR | BCB SGS 12 | 2005-01-03 | 2026-10-27 | 5478 | 96.2 | 96.2 | 5 |
| STR_MX | Banxico SF43783 | 2005-01-03 | 2026-10-29 | 5492 | 96.5 | 96.5 | 5 |
| STR_ZA | SARB MMRD403A | 2008-09-01 | 2026-10-27 | 5030 | 79.7 | 95.8 | 5 |
| US10Y | FRED DGS10 | 2005-01-03 | 2026-10-27 | 5459 | 95.9 | 95.9 | 4 |
| VIX | FRED VIXCLS | 2005-01-03 | 2026-10-27 | 5522 | 97.0 | 97.0 | 5 |
| DXY | Yahoo Finance DX-Y.NYB | 2005-01-03 | 2026-10-29 | 5497 | 96.5 | 96.5 | 5 |
| USD_BROAD | FRED DTWEXBGS | 2006-01-02 | 2026-10-23 | 5217 | 91.6 | 96.0 | 7 |
| US_FF | FRED DFF | 2005-01-01 | 2026-10-27 | 7970 | 100.0 | 100.0 | 1 |

## Cross-checks

FX: correlation of daily log changes, primary vs. second source (timing differs: H.10 = noon New York, Yahoo ~ London close, PTAX/FIX/NBP = local fixings, so daily correlations below 1 are expected; 5-day correlations should be close to 1).

| pair | daily corr | 5-day corr | median abs level gap % | n |
|---|---|---|---|---|
| BRL | 0.846 | 0.966 | 0.17 | 5692 |
| MXN | 0.906 | 0.981 | 0.06 | 5692 |
| ZAR | 0.441 | 0.877 | 0.43 | 5692 |
| PLN | 0.524 | 0.899 | 0.26 | 5678 |

10-year yields vs. OECD monthly long-term rate (FRED IRLTLT01..., monthly average of daily):

| country | corr of monthly levels | mean diff (pp) | n months |
|---|---|---|---|
| Mexico | 0.992 | -0.04 | 198 |
| South Africa | 1.000 | -0.00 | 261 |
| Poland | 1.000 | -0.00 | 261 |

## Gaps and caveats

- IDR: removed 6 isolated Yahoo bad ticks (>8% move reversed next day).
Indonesia: no free, keyless daily 10y government yield found (PHEI/IBPA publishes only the latest two days; DJPPR only PDFs; IDX blocks API access; OECD monthly covers 2012-2024 only). Indonesian bond events are not studied.
Turkey: daily 10y yield only from July 2018 (Borsa Istanbul CSV bulletins); traded-bond closest to 10y, so the series switches bonds and is noisy. Older bulletins are legacy .xls with changing layouts and no 10y TRY bond existed before 2010.
Poland: BondSpot fixing interpolated to 10y across fixed-rate bonds.
Brazil: Tesouro Direto NTN-F quotes are morning ("Manha") rates; before ~2007 the longest NTN-F was <10y, so Y10_BR is the longest available bond (see Y10MAT_BR).
Mexico: yield computed from Banxico's on-the-run 7-10y Bono M dirty price, coupon and days to maturity; maturity drifts between ~7.5 and 10.9 years as the benchmark rolls (Y10MAT_MX).
South Africa: SARB average yield on government bonds with 10 years and longer to maturity (not a single benchmark).
