# wgi.csv — Worldwide Governance Indicators (estimates)

Downloaded: 2026-10-29. Rows: 13 countries x 2005–2025 (273 rows, no missing values). Key: `iso3, year`.

**Source:** World Bank API, source id 3 (Worldwide Governance Indicators), `lastupdated` 2026-09-25. URL pattern:
`https://api.worldbank.org/v2/country/BRA;MEX;ZAF;TUR;IDN;POL;FRA;ITA;ESP;GBR;COL;CHL;DEU/indicator/GOV_WGI_<X>.EST?source=3&format=json&per_page=5000&date=2005:2026`

| column | indicator | definition |
|---|---|---|
| `va` | GOV_WGI_VA.EST | Voice and Accountability |
| `pv` | GOV_WGI_PV.EST | Political Stability and Absence of Violence/Terrorism |
| `ge` | GOV_WGI_GE.EST | Government Effectiveness |
| `rq` | GOV_WGI_RQ.EST | Regulatory Quality |
| `rl` | GOV_WGI_RL.EST | Rule of Law |
| `cc` | GOV_WGI_CC.EST | Control of Corruption |

All are governance estimates on an approximately −2.5..+2.5 scale (standard-normal units, higher = better). The values are as served by the API and are unrounded.

Caveats: WGI revises the whole history at each release, so do not mix vintages. Because the estimates are standardised each year, they are relative to other countries, not absolute levels. Standard errors and percentile ranks were not pulled.
