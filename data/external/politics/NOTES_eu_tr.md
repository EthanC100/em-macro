# Cabinet and party data: France, Italy, Spain, UK, Germany, Poland, Turkey

Built 2026-10-29. Files:

- `cabinets_eu_tr.csv`: 106 cabinets in office at any time from 2000-01-01 to 2026-10-29.
- `parties_eu_tr.csv`: 155 rows covering 72 parties.

Brazil, Mexico, Colombia, Chile, Indonesia and South Africa are covered by separate files.

## Sources (all downloaded without keys or logins, using default request headers)

| Source | File / URL | Version |
|---|---|---|
| ParlGov | https://www.parlgov.org/data/parlgov-development_csv-utf-8/ `view_cabinet.csv`, `view_party.csv`, `view_election.csv`, plus `politician_president.csv` and `party.csv` from `parlgov-development_csv-utf-8.zip` | Development version, data build 2023-11-04 (server files dated 2025-09-20 are identical to the zip) |
| CHES | https://github.com/chesdata/chesdata.github.io/releases/download/ches-trend/1999-2024_CHES_dataset_meansV2.csv (EU and UK). Turkey uses the wave files `2007_CHES-candidates_dataset_means.csv`, `2010_CHES_dataset_means.csv`, `2014_CHES_dataset_means.csv`, `CHES2019V3.csv` and `CHES_2024_final_v2.csv` from the `ches-europe` release linked on https://www.chesdata.eu/ches-europe | Trend file 1999-2024 V2 |
| PopuList | https://popu-list.github.io/Data/The%20PopuList%204.0.csv | 4.0 (May 2026; elections up to 2026-05-01) |
| V-Party | https://raw.githubusercontent.com/vdeminstitute/vdemdata/master/data/vparty.RData, from V-Dem's official R package `vdemdata` v16.0 | V-Party v2 (2022; elections up to 2019) |
| Party Facts | https://partyfacts.herokuapp.com/download/external-parties-csv/ | Used only for ID crosswalks (ParlGov to CHES, V-Party and Manifesto) |
| Wikipedia | Raw wikitext of the pages cited row by row in `source` | Retrieved 2026-10-29 |

V-Party is not on v-dem.net as a plain download: that page uses an email and personal-data form, which was not used. The data come from V-Dem's own public GitHub R package instead.

The Manifesto Project main dataset (latest MPDS2026a) needs an API key or account. `get_core` without a key redirects to `not_authorized`. As a result, `manifesto_rile` and `manifesto_year` are blank. `manifesto_party_id` comes from ParlGov's `cmp` link, or from Party Facts when ParlGov has none.

## Cabinet conventions (`cabinets_eu_tr.csv`)

### Where cabinets come from

- Cabinets follow ParlGov's rules. A new cabinet starts when the head of government changes, when the party composition changes, or at a general election. ParlGov country practice is kept as it is.
  - Germany and Spain get a caretaker cabinet from election day.
  - France starts a cabinet at the second round of an election.
  - Poland and Italy do not get election-day cabinets.
- `end_date` is the start of the next cabinet. It is blank for cabinets still in office on 2026-10-29.
- ParlGov's last cabinets are:
  - DEU Scholz (2021-12-08)
  - ESP Sanchez III (2020-01-07)
  - FRA Borne II (2022-06-19)
  - GBR Sunak (2022-10-25)
  - ITA Meloni (2022-10-22)
  - POL Morawiecki II (2019-11-15)
  - TUR Erdogan V (2023-06-03)

  ParlGov does not include the 2023 elections in Spain or Poland.
- 15 later cabinets were added from Wikipedia, each with its own citation (`parlgov_cabinet_id` blank):
  - FRA: Attal I, Attal II, Barnier, Bayrou, Lecornu I, Lecornu II
  - GBR: Starmer, Burnham
  - DEU: Scholz II, Scholz III, Merz
  - ESP: Sanchez IV, Sanchez V
  - POL: Morawiecki III, Tusk III
- Added cabinets keep ParlGov's numbering, which can differ from Wikipedia's:
  - ESP "Sanchez V" is Wikipedia's "Third government of Pedro Sánchez".
  - ESP "Sanchez IV" is the caretaker cabinet after the July 2023 election.

### Columns

- `parties`: ParlGov party short names, sorted and separated by semicolons.
  - Added cabinets use the ParlGov code when a ParlGov party exists:
    - RE = `REM|R`
    - MoDem = `UDF|MD`
    - Horizons = `H`
    - LR = `UMP|LR`
    - Parti radical = `PR`
    - KO (Civic Coalition) = `PO`
    - Nowa Lewica = `SLD` (CHES and Party Facts treat it as the SLD's successor)
  - Parties with no ParlGov id: `Sumar`, `PL2050` and `FP` (Fédération progressiste).
  - ParlGov's code `PC` (a non-partisan PM) is not counted as a party. Monti has an empty party list and a seat count of 0.
- `seats_gov` and `seats_total`: lower-house seats from the most recent election before the cabinet started, following ParlGov. Mid-term defections are ignored.
  - Overrides are explained in `notes`:
    - ESP Sanchez III adds the 26 Unidas Podemos seats that ParlGov records under P.
    - TUR Erdogan IV and V use People's Alliance seats (AKP+MHP in 2018; AKP+MHP+YRP in 2023).
    - FRA from 2024 uses Le Monde's party tallies, as reported on Wikipedia.
    - DEU, ESP, GBR and POL after ParlGov's coverage use Wikipedia's election results.
- `minority` is Y when `seat_share` is below 0.5.
- `caretaker`:
  - Y when ParlGov codes the cabinet as caretaker.
  - Y for the added post-election caretakers: Attal II, Scholz III and Sanchez IV.
  - Y for Barnier, Bayrou, Lecornu I and Lecornu II, following this project's definition (fragile minority governments). Apart from Lecornu I's four days in October 2025, these were not caretaker governments in the legal sense.
  - Monti and Draghi I/II are Y in ParlGov. Draghi I was a broad national-unity coalition.
- `president` and `president_party`: the president at the cabinet's start date, filled for FRA, POL and TUR only. Italy and Germany have ceremonial presidents, and Spain and the UK are monarchies.
  - Values come from ParlGov `politician_president.csv`, extended and corrected with Wikipedia:
    - Macron took office 2017-05-14 (ParlGov has 2017-06-14).
    - Nawrocki has been president since 2025-08-06, as an independent backed by PiS.
  - ParlGov codes presidents' parties even when they were formally non-partisan (Gül and Erdoğan before 2017: AKP; Demirel: DYP; Duda: PiS).
- Turkey after 2018: `head` is the president, and the cabinet is the presidential cabinet.

## Party table conventions (`parties_eu_tr.csv`)

### Row structure

Each row is one party for one reference election. The reference election is the last lower-house election before the start of a cabinet in which the party held posts.

`vparty_year` is the calendar year of that reference election, and it is the merge key. Join cabinets to parties on `iso3`, `party` and the year of the cabinet's last election. This means the V-Party columns can be blank even when `vparty_year` is filled.

### Same-year elections

When two elections fall in the same year (ESP April and November 2019; TUR June and November 2015), they share one row. V-Party holds only the November election in both cases, and `notes` says so.

### Measures

- `parlgov_left_right`: ParlGov's 0-10 left-right score, which does not change over time. For 16 parties with no expert-survey link in ParlGov, the value is a party-family default (1.3, 3.3, 6.0, 7.4 or 8.8), flagged in `notes`.
- `ches_lrecon` and `ches_year`:
  - The value comes from the latest CHES wave in or before the reference-election year in which the party appears.
  - Rows are blank when the party's first wave comes later; `notes` then gives that first wave and its value.
  - CDU+CSU uses the CDU score.
  - Unidas Podemos uses the Podemos score.
- PopuList flags:
  - Each flag (0/1) is evaluated at `vparty_year` against PopuList's `_start` and `_end` years.
  - The ranges, and whether a case is borderline (`_bl`), are written in `notes`.
  - Parties not listed in PopuList 4.0 get 0 for populist, far-right and far-left. PopuList lists only parties it classifies, out of all parties with at least 1 seat or 2% of the vote since 1989.
  - `eurosceptic_popu_list` is blank for unlisted parties, because PopuList assesses Euroscepticism only for parties it lists.
  - Turkey is not covered.
  - FRA `UMP|LR` uses the PopuList 4.0 entry "LR" (far right, borderline, 1900-2100) only from 2015 onward, when the UMP was renamed LR. Earlier years are treated as not listed.
  - ITA `FI-PdL` maps to FI1 before 2008, PDL for 2008-2013 and FI2 from 2018. All three entries have the same flags.
  - `Sumar` maps to the PopuList entry SMR (populist, borderline).
- V-Party `v2pariglef` and `v2xpa_popul`: the V-Party observation for the reference election, matched through Party Facts ids.
  - Some parties use a different V-Party unit, noted in the row:
    - CDU+CSU uses CDU, because the joint unit has no scores.
    - Unidas Podemos uses Podemos.
    - AKP in 2018 uses People's Alliance.
    - Italian list and predecessor units are used where needed (PDS, IPdL, CCD/CDU, UdC, RnP).
  - V-Party v2 ends with 2019 elections, so all reference elections after 2019 are blank.

## Doubtful items

| Country | Cabinet / party | Issue |
|---|---|---|
| FRA | Philippe I | ParlGov start date 2017-06-14 was corrected to 2017-05-15. Seats are from the 2012 assembly, where REM had no seats. |
| FRA | Philippe I, Philippe II, Castex | ParlGov lists `UMP|LR` as a cabinet party, although LR was in opposition. `notes` gives the share without LR (Philippe II and Castex: 0.6118 instead of 0.8059). |
| FRA | Borne II, Attal I | `seats_gov` is the Ensemble alliance total that ParlGov books under `REM|R`. |
| FRA | 2024+ cabinets | Party seats are Le Monde tallies. The official Interior Ministry totals are 159 for Ensemble and 39 for LR. PR and FP seats are not counted. |
| ITA | Draghi II | ParlGov's party list (IV, M5S, PD, S) leaves out ministers from Lega, FI and IpF who stayed in office until October 2022. |
| ITA | Monti | No parties are recorded, so `seat_share` is 0. |
| POL | Morawiecki III | Coded `caretaker`=N. It never won investiture and lost a confidence vote on 2023-12-11. |
| POL | Tusk III | Seats are counted at list level. Poland 2050's 2026 split (the new Centre group, still in the coalition) is not coded as a new cabinet. |
| GBR | Burnham | Seats are Labour's 2024 election result. |
| — | V-Party via vdemdata | The vdemdata route is a judgment call. If it should not be used, drop the V-Party columns. |
