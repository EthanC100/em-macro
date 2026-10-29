# cbi.csv — central bank independence (de jure)

Downloaded: 2026-10-29. Rows: 13 countries x 2005–2023 (247 rows). Key: `iso3, year`.

| column | definition | source |
|---|---|---|
| `cbie_index` | Romelli Central Bank Independence – Extended (CBIE) overall index, [0,1], higher = more independent | Romelli CBIE dataset, **2025 vintage** ("Latest version – June 2025"; covers statutes 1923–2023) |
| `garriga_lvau` | Garriga Cukierman-Webb-Neyapti-type index, unweighted ("CBI Garriga (raw average)", `lvau_garriga`), [0,1] | Garriga CBI dataset, **version 3 (January 2025 release)**, 1970–2023 |
| `garriga_lvaw` | Garriga CWN-type index, weighted ("CBI Garriga (weighted)", `lvaw_garriga`; weights CEO 0.20, objectives 0.15, policy 0.15, lending limits 0.50), [0,1] | same |
| `source` | provenance string | |

## Exact files
- Romelli: https://cbidata.org/dataset/CBIData_Romelli_2025.xlsx (sheet `CBI data`, column `cbie_index`; server Last-Modified 2026-07-11). Codebook: https://cbidata.org/dataset/CBIData_Romelli_2024_Codebook.pdf. Vintages page: https://cbidata.org/vintages. Cite Romelli (2022, *Economic Policy* 37(112)) and Romelli (2024, BAFFI CAREFIN WP 217). Values rounded to 6 dp (file precision 4 dp).
- Garriga: file `CBI_2025_websiteGarriga.dta`, linked as "LATEST VERSION (version 3)" from https://sites.google.com/site/carogarriga/cbi-data-1 (Google Drive id 1A2Ez69Lg-9fJPyRCsJKKAbm1smHAmZjj). Mapped by ISO numeric `ccodewb`. Cite Garriga (2025) *International Studies Quarterly* 69(2) sqaf024, and Garriga (2016) *International Interactions* 42(5). The same variables are in the Harvard Dataverse replication file doi:10.7910/DVN/NWUUEY (`Replication_ISQ_2025.tab`, V1, 2025-04-15); the original 2016 data is doi:10.7910/DVN/I2BUGZ.

## Coverage
All 13 countries complete for 2005–2023 in both datasets. Neither dataset goes past 2023.

## Euro-area countries (FRA, DEU, ITA, ESP) after 1999
- **Romelli CBIE** codes the statute of each **national central bank** (as amended for ESCB membership). Scores differ across members: FRA/DEU 0.912 vs ITA/ESP 0.8955 from 1998 onward, so no single ECB score is used.
- **Garriga** codes euro members as members of a **regional central bank** (`regional = 1` from 1998, with a reform recorded in 1998). From 1998 all four countries get the identical ECB/ESCB score (lvau 0.796, lvaw 0.857), so there is no cross-country variation within the euro area. Garriga's own replication code drops `regional==1` in robustness checks. Consider doing the same, or adding a euro-area dummy.
