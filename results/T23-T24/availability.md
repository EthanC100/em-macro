# T23-T24 Phase 1: market availability per month, 1978-01..1999-12 (counts and dates only)

Produced by `python -m em_macro.t2324_avail run` with the a160bfd data code (`commod_data`, `commod_build0`) unchanged and the schedule and contract loading moved earlier (`t2324_window`). Only the existence of a settlement on a date and the contract calendar are used: no price is summarised and no return, signal or statistic is computed.

## First month with at least 6 active markets (pre-registration T20-T22 §2.1 rule 3)

| trial | universe checked | markets passing the window checks | first month >= 6 active | months below 6 after it |
|---|---|---|---|---|
| T21 basis-momentum (T23) | 20 | 19: CL B HO NG G HG ZC ZS ZW KE ZM ZL SB KC CC CT LE GF HE | **1979-05** | 0 |
| T22 diversified trend (T24) | 30 | 24: CL B HO NG G HG GC SI PL ZC ZS ZW KE ZM ZL SB KC CC CT LE GF HE 6B 6M | **1979-04** | 0 |
| T20 carry (control) | 20 | 19: CL B HO NG G HG ZC ZS ZW KE ZM ZL SB KC CC CT LE GF HE | **1981-05** | 5 |

A2 analogue (20-market cross-sectional universe, F1/F2 coverage >= 95% from the later of 1978-01 and entry to 1999-12): **19 of 20**.

## Per market

| market | entry | window from | coverage | A6 notice / F1 last-10 / F2 last-10 / first-settle | A4.4 missing | A11 | F1 gaps > 5d | F2 gaps > 5d | FND source (used contracts) | result T21 / T22 |
|---|---|---|---|---|---|---|---|---|---|---|
| CL | 1984-05 | 1984-05 | 100.0% (188/188) | 0 / 0 / 0 / 0 | 0 | 0 | 0 | 0 | none 200 | pass / pass |
| B | 1989-08 | 1989-08 | 99.2% (124/125) | 0 / 0 / 0 / 0 | 1 | 0 | 0 | 0 | none 137 | pass / pass |
| RB | — | — | — | — | — | — | — | — | — | not in window: no contract with a settlement before 2000 in the primary source |
| HO | 1980-01 | 1980-01 | 100.0% (240/240) | 0 / 0 / 0 / 0 | 0 | 0 | 0 | 0 | none 252 | pass / pass |
| NG | 1991-06 | 1991-06 | 100.0% (103/103) | 0 / 0 / 0 / 0 | 0 | 0 | 0 | 0 | none 115 | pass / pass |
| G | 1990-01 | 1990-01 | 100.0% (120/120) | 0 / 0 / 0 / 0 | 0 | 0 | 0 | 0 | none 132 | pass / pass |
| HG | 1979-05 | 1979-05 | 100.0% (248/248) | 0 / 0 / 0 / 0 | 0 | 0 | 0 | 0 | norgate 106 | pass / pass |
| GC | 1979-05 | 1979-05 | 100.0% (248/248) | 0 / 0 / 0 / 0 | 0 | 0 | 0 | 0 | norgate 127 | — / pass |
| SI | 1979-04 | 1979-04 | 100.0% (249/249) | 0 / 0 / 0 / 0 | 0 | 0 | 0 | 0 | norgate 106 | — / pass |
| PL | 1979-07 | 1979-07 | 100.0% (246/246) | 0 / 0 / 0 / 0 | 0 | 0 | 0 | 0 | norgate 86 | — / pass |
| ZC | 1979-03 | 1979-03 | 100.0% (250/250) | 0 / 0 / 0 / 0 | 0 | 0 | 0 | 0 | norgate 110 | pass / pass |
| ZS | 1979-01 | 1979-01 | 100.0% (252/252) | 0 / 0 / 0 / 0 | 0 | 0 | 0 | 0 | norgate 155 | pass / pass |
| ZW | 1979-03 | 1979-03 | 100.0% (250/250) | 0 / 0 / 0 / 0 | 0 | 0 | 0 | 0 | norgate 110 | pass / pass |
| KE | 1980-06 | 1980-06 | 100.0% (235/235) | 0 / 0 / 0 / 0 | 0 | 0 | 0 | 0 | norgate 103 | pass / pass |
| ZM | 1979-03 | 1979-03 | 100.0% (250/250) | 0 / 0 / 0 / 0 | 0 | 0 | 0 | 0 | norgate 176 | pass / pass |
| ZL | 1979-03 | 1979-03 | 100.0% (250/250) | 0 / 0 / 0 / 0 | 0 | 0 | 0 | 0 | norgate 176 | pass / pass |
| SB | 1979-11 | 1979-11 | 100.0% (242/242) | 0 / 0 / 0 / 0 | 0 | 0 | 0 | 0 | none 85 | pass / pass |
| KC | 1980-02 | 1980-02 | 100.0% (239/239) | 0 / 0 / 0 / 0 | 0 | 0 | 0 | 0 | norgate 105 | pass / pass |
| CC | 1981-02 | 1981-02 | 100.0% (227/227) | 0 / 0 / 0 / 0 | 0 | 0 | 0 | 0 | norgate 100 | pass / pass |
| CT | 1979-11 | 1979-11 | 100.0% (242/242) | 0 / 0 / 0 / 0 | 0 | 0 | 0 | 0 | norgate 106 | pass / pass |
| LE | 1979-12 | 1979-12 | 100.0% (241/241) | 0 / 0 / 0 / 0 | 0 | 0 | 0 | 0 | norgate 127 | pass / pass |
| GF | 1980-03 | 1980-03 | 100.0% (238/238) | 0 / 0 / 0 / 0 | 0 | 0 | 0 | 0 | none 167 | pass / pass |
| HE | 1980-01 | 1980-01 | 100.0% (240/240) | 0 / 0 / 0 / 0 | 0 | 0 | 0 | 0 | none 148 | pass / pass |
| 6E | 2000-03 | — | — | — | — | — | — | — | — | not in window: entry after 1999-12 |
| 6B | 1980-05 | 1980-05 | 100.0% (236/236) | 0 / 0 / 0 / 0 | 0 | 0 | 0 | 0 | none 83 | — / pass |
| 6M | 1996-06 | 1996-06 | 100.0% (43/43) | 0 / 0 / 0 / 0 | 0 | 0 | 0 | 0 | none 19 | — / pass |
| FGBL | 2000-03 | — | — | — | — | — | — | — | — | not in window: entry after 1999-12 |
| FOAT | — | — | — | — | — | — | — | — | — | not in window: no contract with a settlement before 2000 in the primary source |
| FBTP | — | — | — | — | — | — | — | — | — | not in window: no contract with a settlement before 2000 in the primary source |
| R | 1989-04 | 1989-04 | 70.5% (91/129) | 0 / 0 / 0 / 0 | 38 | 0 | 0 | 35 | norgate 48 | — / fail |

## Active markets per month (December of each year, and the yearly minimum and maximum)

| year | T21 Dec | T21 min-max | T22 Dec | T22 min-max | T20 control Dec | T20 min-max |
|---|---|---|---|---|---|---|
| 1978 | 0 | 0-0 | 0 | 0-0 | 0 | 0-0 |
| 1979 | 9 | 1-9 | 12 | 1-12 | 3 | 0-3 |
| 1980 | 14 | 11-14 | 18 | 14-18 | 2 | 2-5 |
| 1981 | 15 | 14-15 | 19 | 18-19 | 5 | 3-9 |
| 1982 | 15 | 15-15 | 19 | 19-19 | 8 | 4-11 |
| 1983 | 15 | 15-15 | 19 | 19-19 | 11 | 9-13 |
| 1984 | 16 | 15-16 | 20 | 19-20 | 11 | 9-13 |
| 1985 | 16 | 16-16 | 20 | 20-20 | 12 | 9-14 |
| 1986 | 16 | 16-16 | 20 | 20-20 | 10 | 10-12 |
| 1987 | 16 | 16-16 | 20 | 20-20 | 10 | 10-13 |
| 1988 | 16 | 16-16 | 20 | 20-20 | 11 | 10-13 |
| 1989 | 17 | 16-17 | 21 | 20-21 | 11 | 11-14 |
| 1990 | 18 | 18-18 | 22 | 22-22 | 12 | 11-15 |
| 1991 | 19 | 18-19 | 23 | 22-23 | 12 | 11-15 |
| 1992 | 19 | 19-19 | 23 | 23-23 | 14 | 14-19 |
| 1993 | 19 | 19-19 | 23 | 23-23 | 16 | 15-18 |
| 1994 | 19 | 19-19 | 23 | 23-23 | 16 | 15-19 |
| 1995 | 19 | 19-19 | 23 | 23-23 | 16 | 16-19 |
| 1996 | 19 | 19-19 | 24 | 23-24 | 15 | 15-19 |
| 1997 | 19 | 19-19 | 24 | 24-24 | 15 | 15-19 |
| 1998 | 19 | 19-19 | 24 | 24-24 | 15 | 15-19 |
| 1999 | 19 | 19-19 | 24 | 24-24 | 15 | 15-19 |

Monthly counts: `results/T23-T24/availability_counts.csv`; per-market detail: `availability.json`.
