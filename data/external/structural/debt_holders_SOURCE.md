# debt_holders.csv — government debt investor base (nonresident share, FX share)

Downloaded: 2026-10-29. Long format with 1,417 rows. Key: `iso3, period, freq, source`. Each source keeps its own rows and nothing is spliced, so several sources can overlap for the same period. Pick one series per country, or use `source` / `*_basis` to splice deliberately.
- `period`: `YYYYQn` when `freq = Q`, and `YYYY` (end-year) when `freq = A`.
- `foreign_share_pct`: debt held by nonresidents (external creditors) as a % of the total on the stated basis.
- `fx_share_pct`: foreign-currency-denominated debt as a % of the total on the stated basis.
- `foreign_share_basis` / `fx_share_basis`: the exact government perimeter, instrument coverage, valuation and the numerator/denominator series. Blank when the value is blank.
- Shares are computed by me as numerator/denominator x 100, rounded to 3 dp, from the levels in the fetched files. For the Arslanalp–Tsuda (A-T) files I took the "Percent of Total Debt" block and checked it against Foreign/Total, which match exactly.

## Sources
1. **Arslanalp & Tsuda, Sovereign Investor Base Dataset for Emerging Markets** (IMF WP/14/39). File: http://www.imf.org/external/pubs/ft/wp/2014/Data/wp1439.zip → `wp1439.xlsx`, "This Version: October 30, 2016", sample 2004Q1–2016Q2. Uses `Table 2. Foreign`, block "Percent of Total Debt" = foreign holdings / general government gross debt (all instruments), face value or valuation-adjusted. Covers BRA CHL COL IDN MEX POL ZAF TUR. The 2016 EM file has **no FX-share series**.
2. **Arslanalp & Tsuda, Sovereign Investor Base Dataset for Advanced Economies** (IMF WP/12/284; IMF Economic Review 62(3)). File: http://www.imf.org/external/pubs/ft/wp/2012/Data/wp12284.zip → `wp12284.xlsx`, "as of Oct 31, 2016", 2004Q1–2016Q2. Same table and block, on a consolidated general government gross debt basis with intra-government holdings netted out. Covers FRA DEU ITA ESP GBR. For euro countries, "foreign" includes other euro-area residents.
3. **World Bank/IMF Quarterly Public Sector Debt (QPSD)**, World Bank API source 20, `lastupdated` 2026-10-22. Series (national currency, nominal value, all maturities, all instruments): `DP.DOD.DECT.CR.GG` (total), `DP.DOD.DECX.CR.GG` (external creditors), `DP.DOD.DECF.CR.GG` (foreign currency). I use central-government (`.CG`) equivalents only where GG is not reported (TUR 2005Q4–2016Q3). URL pattern: `https://api.worldbank.org/v2/country/<ISO3 list>/indicator/<id>?source=20&format=json&per_page=20000`. QPSD residency is by creditor residence ("external creditors"). For EU members the QPSD figures equal Eurostat's (ITA identical).
4. **Eurostat `gov_10q_ggdebt`** (Quarterly government debt), updated 2026-10-21: S13, MIO_NAC, `GD_S2/GD` (non-domestic counterparts) and `GD_FOR/GD` (foreign currency). Maastricht consolidated gross debt at face value. Only **Italy** reports these breakdowns in this table for the countries here. API: `https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/gov_10q_ggdebt?geo=..&sector=S13&na_item=GD&na_item=GD_S2&na_item=GD_FOR&unit=MIO_NAC&sinceTimePeriod=2004-Q1`
5. **Eurostat `gov_10dd_ggd`** (General government debt, annual), updated 2026-06-05: S13, na_item GD, maturity TOTAL, MIO_NAC; share = holder sector2 `S2` (rest of world) / `S1_S2` (all holders). Year-end, face value. API: `https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/gov_10dd_ggd?geo=..&sector=S13&na_item=GD&sector2=S1_S2&sector2=S2&maturity=TOTAL&unit=MIO_NAC&sinceTimePeriod=2004`. Italy's 2025 value is flagged provisional ("p").

## Coverage from 2005 (first–last)
| iso3 | A-T (Q) foreign | QPSD (Q) foreign / fx | Eurostat |
|---|---|---|---|
| BRA | 2005Q1–2016Q2 | 2009Q3–2026Q2 / same | – |
| MEX | 2005Q1–2016Q2 | 2008Q1–2026Q2 / same | – |
| ZAF | 2005Q1–2016Q2 | 2010Q1–2026Q1 / same | – |
| TUR | 2005Q1–2016Q2 | 2005Q4–2026Q2 / same (CG to 2016Q3, GG from 2016Q4) | – |
| IDN | 2005Q1–2016Q2 | 2010Q1–2026Q2 / same | – |
| POL | 2005Q1–2016Q2 | none (QPSD has totals only) | annual foreign 2020–2025 |
| COL | 2005Q1–2016Q2 | foreign none / fx 2008Q1–2026Q2 | – |
| CHL | 2005Q1–2016Q2 | not in QPSD | – |
| FRA | 2005Q1–2016Q2 | none (totals only) | annual foreign 2020–2025 |
| DEU | 2005Q1–2016Q2 | none (totals only) | annual foreign 2005–2025 |
| ITA | 2005Q1–2016Q2 | 2005Q1–2026Q2 / same | Q 2005Q1–2026Q2 (foreign+fx); annual 2020–2025 |
| ESP | 2005Q1–2016Q2 | 2005Q1–2026Q2 / same | annual foreign 2020–2025 |
| GBR | 2005Q1–2016Q2 | 2005Q1–2026Q2 / same | – |

## Caveats
- **I could not find an A-T vintage newer than 2016.** imf.org has been redesigned: the "updated" dataset links (`/-/media/Files/Publications/WP/2014/datasets/wp1439.ashx`, `.../2012/datasets/wp12284.ashx`) and the WP landing pages' data links now return "Blob not found" (404). The new WP landing pages (e.g. .../tracking-global-demand-for-emerging-market-sovereign-debt-41399 and the advanced-economy page -40135) list only the paper PDF. The only A-T files still served are the legacy zips above (2016 vintage). web.archive.org could not be reached from this environment.
- The bases differ across sources, so levels are not comparable without care. A-T uses its own estimates (face value, valuation-adjusted, with sector reallocations), while QPSD and Eurostat use creditor residence at nominal or face value. Example, GBR 2010Q4: A-T 26.2% vs QPSD 16.8%. I have not checked the reason; it is most likely the estimation method and instrument coverage, so compare within one source.
- The FX share is for all GG (or CG) debt by currency of denomination, including loans. For euro-area members the euro counts as domestic currency, so the FX share is close to 0. No source here gives an FX share for CHL, POL, FRA or DEU.
- None of these series are restricted to marketable debt. A-T's separate "o/w general government securities" and "central government LC securities" blocks were not extracted.
- Gaps with no fetched source: CHL after 2016Q2 (foreign share); COL foreign share after 2016Q2; FRA and POL 2016Q3–2019; ESP annual Eurostat starts 2020 (quarterly QPSD covers ESP anyway).
