# Event calendar coverage (13 countries)

`data/events/calendar_13.csv`: 2755 dated events from 2005-01-06 to 2026-10-28; rows without a source URL: 0. 5 research rows have no exact date (month-only sources) and are listed in `data/events/calendar_13_undated.csv` instead.

| event type | BRA | MEX | ZAF | TUR | IDN | POL | FRA | ITA | ESP | GBR | COL | CHL | DEU |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| budget |  |  |  |  |  |  | 89 | 90 | 38 | 59 | 35 | 18 | 14 |
| confidence_vote |  |  |  |  |  |  | 84 | 49 | 21 | 4 | 11 | 15 | 9 |
| election | 13 | 10 | 4 | 16 | 6 | 18 | 20 | 12 | 10 | 9 | 19 | 23 | 6 |
| government_collapse |  |  |  |  |  |  | 43 | 31 | 21 | 26 | 13 | 13 | 12 |
| rate_decision | 178 | 197 | 135 | 251 | 260 | 230 |  |  |  |  |  |  |  |
| rating_action | 79 | 35 | 84 | 68 | 66 | 56 | 36 | 49 | 48 | 25 | 42 | 32 | 23 |

Rate decisions are compiled for the original six countries only (ECB, BoE, BanRep and BCCh decisions are not in the calendar yet). Government collapses, confidence votes and budgets are compiled for the seven new countries only (not yet for BR, MX, ZA, TR, ID, PL).

## Subtypes

- **budget**: budget_promulgated (42), budget (25), plf_presented (22), budget_final_approval (21), budget_law_enacted (19), pge_final_approval (16), imf_fcl (16), dbp_submitted (16), nadef_approved (12), def_approved (11), autumn_statement (9), pge_rollover (8), edp_126_3_report (7), edp_commission_report (7), edp_council_recommendation (7), budget_law_published (7), budget_presented (6), edp_opened_commission_rec (5), edp_opened (5), pre_budget_report (5), edp_closure (5), spring_statement (5), edp_opening (4), edp_abrogation_commission_rec (4), edp_closed (4)
- **confidence_vote**: censure_motion (73), investiture (20), no_confidence_motion_minister (17), confidence_vote (12), confidence_question (10), investiture_ballot_1 (9), constitutional_accusation_interior (8), investiture_ballot_2 (7), tax_reform_enacted (6), chancellor_election (5), motion_of_censure (4), constitutional_accusation_president (3), vertrauensfrage (2), no_confidence_motion (2), party_confidence_vote (2), tax_reform_vote (2), constitutional_accusation_finance (2), commons_no_confidence_motion (1), budget_totality_amendments (1), pension_withdrawal_law (1), tax_reform_withdrawn (1), commons_confidence_motion (1), pension_reform_enacted (1), financing_law_defeated (1), chancellor_election_ballot_1 (1)
- **election**: general (42), legislative (32), presidential_r2 (27), presidential (24), referendum (23), legislative_r2 (5), local_nationwide (5), regional (3), other_national (3), european (2)
- **government_collapse**: new_government (63), resignation (33), finance_minister_change (11), dissolution (10), snap_election_call (8), resignation_announcement (7), president_dissolves (4), early_election_vote (4), lost_confidence (3), coalition_exit (3), cabinet_reshuffle (3), election_call (2), court_ruling (1), resignation_timetable (1), coalition_talks_collapse (1), censure_motion_filed (1), formation_failed (1), ousted_by_censure (1), coalition_collapse (1), parliamentary_defeat (1)
- **rate_decision**: hold (757), cut (290), hike (204)
- **rating_action**: outlook_change (217), affirmation (185), downgrade (112), upgrade (96), watch_on (27), watch_off (6)

## First and last event by type and country

| event type | country | first | last |
|---|---|---|---|
| budget | CHL | 2006-09-30 | 2026-08-26 |
| budget | COL | 2005-12-01 | 2026-10-22 |
| budget | DEU | 2006-03-14 | 2026-06-03 |
| budget | ESP | 2005-12-29 | 2026-01-01 |
| budget | FRA | 2005-09-28 | 2026-10-01 |
| budget | GBR | 2005-03-16 | 2026-10-28 |
| budget | ITA | 2005-06-07 | 2026-10-28 |
| confidence_vote | CHL | 2011-08-31 | 2026-06-30 |
| confidence_vote | COL | 2012-12-26 | 2024-12-11 |
| confidence_vote | DEU | 2005-07-01 | 2025-05-06 |
| confidence_vote | ESP | 2008-04-09 | 2023-11-16 |
| confidence_vote | FRA | 2005-06-08 | 2026-07-06 |
| confidence_vote | GBR | 2018-12-12 | 2022-07-18 |
| confidence_vote | ITA | 2005-02-16 | 2025-03-26 |
| election | BRA | 2005-10-23 | 2026-10-25 |
| election | CHL | 2005-12-11 | 2025-12-14 |
| election | COL | 2006-03-12 | 2026-06-21 |
| election | DEU | 2005-09-18 | 2025-02-23 |
| election | ESP | 2008-03-09 | 2023-07-23 |
| election | FRA | 2005-05-29 | 2024-07-07 |
| election | GBR | 2005-05-05 | 2024-07-04 |
| election | IDN | 2009-04-09 | 2024-02-14 |
| election | ITA | 2006-04-10 | 2026-03-23 |
| election | MEX | 2006-07-02 | 2025-06-01 |
| election | POL | 2005-09-25 | 2025-06-01 |
| election | TUR | 2007-07-22 | 2024-03-31 |
| election | ZAF | 2009-04-22 | 2024-05-29 |
| government_collapse | CHL | 2006-03-11 | 2026-03-11 |
| government_collapse | COL | 2006-08-07 | 2026-08-07 |
| government_collapse | DEU | 2005-05-22 | 2025-05-06 |
| government_collapse | ESP | 2008-01-15 | 2026-10-06 |
| government_collapse | FRA | 2005-05-31 | 2025-10-12 |
| government_collapse | GBR | 2005-04-05 | 2026-07-20 |
| government_collapse | ITA | 2006-05-02 | 2022-10-22 |
| rate_decision | BRA | 2005-01-19 | 2026-09-16 |
| rate_decision | IDN | 2005-07-05 | 2026-10-21 |
| rate_decision | MEX | 2005-01-28 | 2026-09-24 |
| rate_decision | POL | 2005-03-30 | 2026-10-07 |
| rate_decision | TUR | 2005-01-11 | 2026-10-22 |
| rate_decision | ZAF | 2005-02-10 | 2026-09-23 |
| rating_action | BRA | 2005-01-12 | 2026-06-25 |
| rating_action | CHL | 2005-02-14 | 2025-09-26 |
| rating_action | COL | 2006-02-22 | 2026-04-08 |
| rating_action | DEU | 2011-12-05 | 2026-09-18 |
| rating_action | ESP | 2009-01-12 | 2026-03-13 |
| rating_action | FRA | 2011-12-05 | 2026-10-23 |
| rating_action | GBR | 2009-05-21 | 2025-11-21 |
| rating_action | IDN | 2005-01-27 | 2026-07-13 |
| rating_action | ITA | 2005-06-29 | 2026-09-11 |
| rating_action | MEX | 2005-01-06 | 2026-05-20 |
| rating_action | POL | 2005-03-22 | 2026-09-18 |
| rating_action | TUR | 2005-01-13 | 2026-04-10 |
| rating_action | ZAF | 2005-01-11 | 2026-06-05 |
