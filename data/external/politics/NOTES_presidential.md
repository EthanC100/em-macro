# Presidential-system cabinets: Brazil, Mexico, Colombia, Chile, Indonesia, South Africa

Files: `cabinets_presidential.csv` (79 spells) and `parties_presidential.csv` (251 rows, 84 party codes). Built on
2026-10-29 from the sources below. Raw downloads are in `/tmp/claude-0/politics_pres/` and are not in the repo.

## Spell definition
- A spell starts with a new presidential term, or when a party enters or leaves the cabinet within a term. Changes
  of minister that do not change the party set are not spells. Spells in office at any time from 2000-01-01 are
  included, so some start before 2000 (Cardoso II-2, Zedillo, Pastrana, Frei, Wahid, Mbeki I).
- `end_date` is the day before the next spell starts. It is blank for spells still in office on 2026-10-29.
- `parties` lists the parties holding cabinet (minister-level) posts, using the source's coding of party
  representation. Parties holding only deputy-minister posts are excluded and mentioned in `notes` (South Africa:
  FF+ 2009-14, NFP 2014-19, UDM and Al Jama-ah in the GNU; Indonesia 2019-24: PSI, Perindo, PBB). For Mexico,
  `parties` uses the party list in the cabinet annex infobox on es.wikipedia. Calderón's PRI-affiliated
  secretaries are excluded. The formal electoral coalition is given in `notes`.
- Sources for the party sets, by country:
  - **Brazil 1999-2020:** IPEA Nota Técnica 53 (Almeida 2021, "Gabinetes ministeriais da Nova República"). It gives
    the start month only, so these spells start on the first day of the month. Exact days come from Figueiredo
    (2007, BPSR, Chart 2) for Cardoso II and Lula I.
  - **Brazil 2021-22 (Centrão entry):** taken from minister party affiliations on Wikipedia, so flagged doubtful.
  - **Brazil, Lula III:** press sources (CUT, CNN Brasil, SBT News).
  - **Colombia and Chile to 2019:** Presidential Cabinets Project, PresCab_BASIC (Camerlo & Martínez-Gallardo,
    Harvard Dataverse). Spells are derived from the party set of the ministers in office on each date. A one-day
    artefact on 2016-04-24 was dropped, and the 18-day Uribe I cabinet of 2006-07-20 was merged into the one
    before it. Cabinet counts were cross-checked against Couto & Albala (2023, DADOS) `Coalescencia.csv`, which
    follows Amorim Neto (2019) and Camerlo & Martínez-Gallardo.
  - **Later periods and Indonesia / South Africa:** cabinet pages on Wikipedia (en/es/pt), with the URLs in
    `source`.

## Seats
- `seats_gov` and `seats_total` count lower-house seats at the latest general or legislative election before the
  spell starts, as election-day seats on the cited Wikipedia results page. The page wikitext was fetched with
  `action=raw` on 2026-10-29, so the page URL is cited and there is no revision id. Wikipedia's API was
  rate-limited and gave no revision id.
- Party switching after the election is not reflected. This matters most for Brazil (for example, PSD was founded
  in 2011 and has 0 seats for Dilma I-4/I-5). Where Figueiredo (2007) or a press source gives the share at
  formation, it is quoted in `notes`.
- `seat_basis` gives the house, the counting rule and the election year. Special cases:
  - Chile before 2009: Concertación coalition totals, including coalition independents.
  - Mexico 2000: the joint Alliance for Change total (PAN+PVEM).
  - Colombia: single-party lists only. Joint lists from 2022 on are excluded, which slightly understates
    `seats_gov`.
  - Indonesia 1999: `seats_total` is the 462 elected seats. The 38 appointed military seats are excluded.
- Parties with no separately reported seats count as 0 and are named in `notes`.
- `notes` also gives the president's own party seat share. For Mexico and Chile (Lagos) it gives the seat share
  after the midterm election.
- Each spell starting 2000-2020 also gets a **DPI2020** cross-check in `notes`. This covers `numgov/totalseats`,
  `maj` and the listed government parties, read from the first January-1 coding year after the spell starts.
  - File: `DPI2020.csv`, read from the copy in Harvard Dataverse doi:10.7910/DVN/G2SQ6Y (file 7019047,
    md5 6f91a24fef52e4c6d20cae9a29ddb6f8).
  - The same md5 appears in a second, independent deposit (doi:10.7910/DVN/9BVJGU), which suggests it is the
    unmodified file as distributed.
  - The IDB page (publications.iadb.org) was behind a Cloudflare challenge, and the World Bank catalogue API
    returned HTTP 429. Neither was bypassed.
  - DPI often codes "government" differently from cabinet membership. Examples: Liberals counted for Uribe I,
    PES for AMLO, UDM for Mbeki II, and Chile coded by coalition.

## Party ideology (`parties_presidential.csv`)
- **V-Party:** one row per party × V-Party election year (1998-2019), giving `v2pariglef` (economic left-right)
  and `v2xpa_popul` (populism). Parties not covered get a single row with blanks.
  - The v-dem.net download form requires an email address and gender, so it was not used.
  - The data come instead from V-Party v2 as shipped in the official V-Dem R package `vdemdata` (v16.0,
    `data/vparty.RData`, raw.githubusercontent.com/vdeminstitute/vdemdata), read with pyreadr.
  - V-Party v2 ends in 2019 and covers only parties with more than 5% of seats. Newer or small parties are blank
    (União Brasil, PSOL, Rede, PCdoB, PV, Pacto Histórico, Chilean Republicans, FRVS, Comunes, PBB, GOOD, PA,
    FF+ and others).
  - Renamed parties repeat the V-Party id of their predecessor: PFL/DEM, PMDB/MDB, PPB/PP, PRB/Republicanos,
    PRSD/PR (Chile), PK/PKS. Brazil `PL` lists both the 1985-2006 PL (id 1823) and PR (id 4405).
- **Global Party Survey 2019** (Norris; Harvard Dataverse doi:10.7910/DVN/WMGTNS v3.0, "Global Party Survey by
  Party Stata V2_1_Apr_2020", file 3788853): `gps_lr_econ` = V4_Scale and `gps_populism` = V8_Scale, both 0-10.
  These values are constant across a party's rows.
  - Chile was surveyed by coalition only, so Chilean parties carry their 2017 coalition's score (noted in `notes`).
  - Mexico's PRI and PVEM share the joint "PRI-PVEM" score.
  - Indonesian "PDI" is assumed to be PDI-P.
  - Colombia's scores rest on 4 experts.
- **Manifesto Project:** left blank. The API (`get_core`) redirects to `not_authorized` without a key, and the
  dataset files redirect to `forbidden` without a login. No account was registered.
- Coverage of the 84 party codes: V-Party 53, GPS 50. Over the 395 spell × party pairs: V-Party 324, GPS 269.

## Doubtful rows (prefixed `DOUBTFUL:` in `notes`)
20 rows: Lula I-4, Dilma I-2, Dilma I-4, Dilma I-5, Bolsonaro-4/5/6, Lula III-3, Fox, Pastrana, Uribe I-1,
Uribe I-2, Duque-2, Petro-2, De la Espriella, Bachelet II-1, Bachelet II-2, Boric, Wahid, Mbeki II. The `notes`
column gives the reason for each: the sources disagree, party entry was inferred from minister affiliation, the
date is month-level or unsourced, or seats are near zero because the president's movement ran no lists.
