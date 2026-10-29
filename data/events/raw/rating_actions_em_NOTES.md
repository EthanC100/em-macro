# rating_actions_em.csv: notes

Scope: Brazil, Mexico, South Africa, Turkey, Indonesia, Colombia and Chile; S&P, Moody's and Fitch.
Each row is a long-term foreign-currency sovereign rating (for Moody's, the government bond/issuer rating) and its outlook or watch status.
The first row per country-agency is `initial_state`, dated 2005-01-01. After that the file lists every action found up to 2026-10-29. The sources were compiled on 2026-10-29.

## Conventions
- `action` is derived mechanically, in this order of precedence:
  - `upgrade` or `downgrade` when the rating notch changes. This applies even if the action also ends a watch or review.
  - `watch_on` or `watch_off` when the rating is unchanged and a watch or review status starts or ends.
  - `outlook_change` when only the outlook changes.
  - `affirmation` otherwise.
- `outlook_*` takes one of positive, stable, negative, watch_positive or watch_negative. Moody's "review for upgrade/downgrade" maps to watch_positive/watch_negative.
- Most Moody's review rows come from countryeconomy, which records only "under review". The direction is inferred from the action that followed, and the notes flag each case.
- `source` is a ` ; `-separated list of URLs that were fetched. The first URL is the main source.
- `notes` records the following:
  - the original assignment date of the rating held on 2005-01-01
  - date disagreements between sources
  - local-currency (LC) ratings that moved differently from foreign-currency (FC) ratings
  - rows marked DOUBTFUL
- Affirmations are included only where an anchor source listed them. They are not complete.

## Anchor sources
| Country | S&P | Moody's | Fitch |
|---|---|---|---|
| Brazil | Tesouro Nacional rating history, sisweb.tesouro.gov.br APEX app (CSV export), plus TradingEconomics (TE) | Tesouro + countryeconomy (CE) | Tesouro + CE |
| South Africa | National Treasury "Historical and Current Ratings" PDF + TE | Treasury PDF + CE | Treasury PDF + CE |
| Indonesia | Bank Indonesia IRU "Indonesia Sovereign Rating - July 2026" PDF + TE | BI + CE | BI + CE |
| Mexico | TE (S&P history) + CE | CE + news | CE + news (CE only before 2013) |
| Turkey | TE + CE | CE + Moody's press releases hosted on ms.hmb.gov.tr (2009-2013) + news | CE (to 2022) + FXEmpire + news |
| Colombia | TE + CE | CE + FXEmpire | CE (to 2021) + FXEmpire + news |
| Chile | TE + CE + news | CE + news | CE (to 2020) + FXEmpire |

FXEmpire (fxempire.com/credit-ratings/...) lists only the 20 most recent changes per country, so it covers roughly 2016-2026. It has a few known errors, which the notes point out.

## Sources that could not be used
- S&P "Sovereign Ratings History": spglobal.com returns a security block (403).
- Chile Hacienda "Ratings Históricos": hacienda.cl connections were reset or returned 503.
- Mexico SHCP finanzaspublicas: TLS failure through the proxy.
- Colombia minhacienda.gov.co: bot-check page, so it was not used.
- Turkey hmb.gov.tr: no history table. Only five Moody's press releases were found.
- No source was found for these:
  - Fitch Turkey review of July 2026. Moody's July 2026 Turkey review and S&P October 2026 Turkey review are reported as "no change / no publication".
  - Fitch Mexico affirmations 2021-2026.
  - S&P Brazil affirmations 2024-2025.
  - Moody's Chile 2025-2026 review dates.

## Main doubts
See rows whose notes contain "DOUBTFUL", "DATE DISPUTED" or "Single source". The principal ones:
- Moody's review rows from CE whose direction or date is uncertain: BRA 2006-08-01 and 2007-05-24, IDN 2006-02-26, COL 2006-03-09, CHL 2008-11-20.
- Moody's BRA Ba1 upgrade: Aug 2007 (2007-08-23 per CE, 2007-08-01 per Tesouro).
- Moody's CHL 2009-03-23 upgrade to A1 (positive).
- Fitch rows supported by CE alone: MEX 2005-2009, TUR 2005-2011, IDN 2006-2007.
- Fitch ZAF 2008-11-08 (weekend date).
