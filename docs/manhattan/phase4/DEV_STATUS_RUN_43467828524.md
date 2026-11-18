<!-- Snapshot written by `python -m manhattan.sim.dev_status --include-stale` (read-only) on the record files of the
artifact `manhattan-sim-results` (id 14116817108, zip SHA-256 a81b137cac29f964a9febcbd5fe74605628204916e09e9d574bc154886fe35e1,
equal to GitHub's recorded digest) of workflow run 43467828524 (commit 1a7f653, 2026-11-13/14), which also holds the
pilot records then on main. The records are NOT committed here (SIM_RUNBOOK section 8: the owner brings them home).
How to reproduce and what it means: SIMULATION_READINESS.md in this folder. -->

# Manhattan simulation: development status (read-only)

**DEVELOPMENT ONLY. No held-out scenario has been coded or run. No screening method is selected and no candidate is called eligible: SIM_PREREG section 7 makes the choice once, after the first confirmation run in which a candidate is eligible.**

Written by `python -m manhattan.sim.dev_status` with `--include-stale`. Synthetic data only.

## 1. Runs of the development plan

| scenario | size | code route | current code | on file (current code) | pre-registered | state | missing | other code on file |
|---|---|---|---|---|---|---|---|---|
| D01 | STD | v1 | `da641c096d17bbf4` | 2000 | 2000 | complete | none | - |
| D02 | STD | v1 | `da641c096d17bbf4` | 2000 | 2000 | complete | none | - |
| D03 | STD | v1 | `da641c096d17bbf4` | 2000 | 2000 | complete | none | - |
| D04 | STD | v1 | `da641c096d17bbf4` | 2000 | 2000 | complete | none | - |
| D05 | STD | v1 | `da641c096d17bbf4` | 2000 | 2000 | complete | none | - |
| D06 | STD | v1 | `da641c096d17bbf4` | 2000 | 2000 | complete | none | - |
| D07a | STD | v1 | `da641c096d17bbf4` | 2000 | 2000 | complete | none | - |
| D07b | STD | v1 | `da641c096d17bbf4` | 2000 | 2000 | complete | none | - |
| D08 | STD | v1 | `da641c096d17bbf4` | 2000 | 2000 | complete | none | - |
| D09a | STD | v1 | `da641c096d17bbf4` | 2000 | 2000 | complete | none | - |
| D09b | STD | v1 | `da641c096d17bbf4` | 2000 | 2000 | complete | none | - |
| D11 | STD | v2 | `9d1b680ff7e19ca7` | 2000 | 2000 | complete | none | - |
| P1 | STD | v1 | `da641c096d17bbf4` | 2000 | 2000 | complete | none | - |
| P2 | STD | v1 | `da641c096d17bbf4` | 2000 | 2000 | complete | none | - |
| P3 | STD | v1 | `da641c096d17bbf4` | 2000 | 2000 | complete | none | - |
| P4 | STD | v1 | `da641c096d17bbf4` | 2000 | 2000 | complete | none | - |
| D01 | LONG | v1 | `da641c096d17bbf4` | 2000 | 2000 | complete | none | - |
| D02 | LONG | v1 | `da641c096d17bbf4` | 2000 | 2000 | complete | none | - |
| D01h | STD | v2 | `9d1b680ff7e19ca7` | 400 | 400 | complete | none | - |
| D02h | STD | v2 | `9d1b680ff7e19ca7` | 400 | 400 | complete | none | - |
| D03h | STD | v2 | `9d1b680ff7e19ca7` | 400 | 400 | complete | none | - |
| D04h | STD | v2 | `9d1b680ff7e19ca7` | 368 | 400 | incomplete | 172 to 203 | - |
| D05h | STD | v2 | `9d1b680ff7e19ca7` | 400 | 400 | complete | none | - |
| D06h | STD | v2 | `9d1b680ff7e19ca7` | 400 | 400 | complete | none | - |
| D07ah | STD | v2 | `9d1b680ff7e19ca7` | 400 | 400 | complete | none | - |
| D07bh | STD | v2 | `9d1b680ff7e19ca7` | 400 | 400 | complete | none | - |
| D08h | STD | v2 | `9d1b680ff7e19ca7` | 400 | 400 | complete | none | - |
| D01 | HB | v2 | `c864e57955126c37` | 0 | 400 | other code only | 0 to 399 | 400 × `4252b971831004e3` step 63; 12 × `630059032fd6e5b8`; 12 × `6d71b497779d4842`; 12 × `c22815235975c486` |
| D02 | HB | v2 | `c864e57955126c37` | 0 | 400 | other code only | 0 to 399 | 400 × `4252b971831004e3` step 63; 12 × `630059032fd6e5b8`; 12 × `6d71b497779d4842`; 12 × `c22815235975c486` |
| D05 | HB | v2 | `c864e57955126c37` | 0 | 400 | other code only | 0 to 399 | 400 × `4252b971831004e3` step 63; 12 × `630059032fd6e5b8`; 12 × `c22815235975c486`; 8 × `6d71b497779d4842` |
| D08 | HB | v2 | `c864e57955126c37` | 0 | 400 | other code only | 0 to 399 | 400 × `4252b971831004e3` step 63; 12 × `630059032fd6e5b8`; 12 × `c22815235975c486` |
| D10 | HB | v2 | `c864e57955126c37` | 0 | 400 | other code only | 0 to 399 | 400 × `4252b971831004e3` step 63; 12 × `630059032fd6e5b8`; 12 × `c22815235975c486` |

## 2. Required criteria on development scenarios

Only rows the pre-registrations require in that scenario. A verdict is computed only on a complete run of the current code; numbers of other code are shown as "not decided".

The last column is what the metric code would say on records of other code: information for the owner, **not a verdict**.

| scenario | size | criterion | candidate | what | estimate | 95% interval | threshold | verdict | on other code |
|---|---|---|---|---|---|---|---|---|---|
| D01 | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 10 | 0.0535 | 0.0436 to 0.0634 | upper bound ≤ 0.22 | pass | - |
| D01 | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 20 | 0.0875 | 0.0751 to 0.0999 | upper bound ≤ 0.22 | pass | - |
| D01 | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 40 | 0.1500 | 0.1343 to 0.1657 | upper bound ≤ 0.22 | pass | - |
| D01 | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| D01 | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 20 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| D01 | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 40 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| D01 | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 3 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D01 | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 5 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D01 | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D01 | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 3 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D01 | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 5 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D01 | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D01 | STD | V2 | - | forward FDR, enrolment by E-ALL, year 3 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D01 | STD | V2 | - | forward FDR, enrolment by E-ALL, year 5 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D01 | STD | V2 | - | forward FDR, enrolment by E-ALL, year 10 | 0.0005 | -0.0005 to 0.0015 | upper bound ≤ 0.06 | pass | - |
| D01 | STD | V3 | - | SPA size at 0.2 | 0.2040 | 0.2013 to 0.2066 | upper bound ≤ 0.22 | pass | - |
| D01 | STD | V3 | - | SPA size at 0.05 | 0.0524 | 0.0513 to 0.0534 | upper bound ≤ 0.06 | pass | - |
| D01 | STD | V3 | - | SPA size at 0.001 (pooled) | 0.0012 | 0.0011 to 0.0013 | upper bound ≤ 0.0015 | pass | - |
| D01 | STD | V3 | - | Romano-Wolf FWER at 0.05 | 0.0523 | 0.0513 to 0.0534 | upper bound ≤ 0.06 | pass | - |
| D01 | STD | V4 | candidate (i) | linked average error, candidate (i) (348 families passed) | 0.1500 | 0.1343 to 0.1657 | upper bound ≤ 0.22 | pass | - |
| D01 | STD | V4 | candidate (ii) | linked average error, candidate (ii) (0 families passed) | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | not evaluated: fewer than 200 observations | - |
| D01 | STD | V5 | - | null component wealth ever reaches 20 | 0.0035 | 0.0033 to 0.0037 | upper bound ≤ 0.06 | pass | - |
| D01 | STD | V5 | - | null component wealth ever reaches 100 | 0.0003 | 0.0003 to 0.0003 | upper bound ≤ 0.015 | pass | - |
| D02 | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 10 | 0.0426 | 0.0345 to 0.0507 | upper bound ≤ 0.22 | pass | - |
| D02 | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 20 | 0.0602 | 0.0513 to 0.0691 | upper bound ≤ 0.22 | pass | - |
| D02 | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 40 | 0.0747 | 0.0662 to 0.0832 | upper bound ≤ 0.22 | pass | - |
| D02 | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| D02 | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 20 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| D02 | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 40 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| D02 | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 3 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D02 | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 5 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D02 | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D02 | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 3 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D02 | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 5 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D02 | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D02 | STD | V3 | - | SPA size at 0.2 | 0.2042 | 0.2016 to 0.2069 | upper bound ≤ 0.22 | pass | - |
| D02 | STD | V3 | - | SPA size at 0.05 | 0.0522 | 0.0512 to 0.0533 | upper bound ≤ 0.06 | pass | - |
| D02 | STD | V3 | - | SPA size at 0.001 (pooled) | 0.0012 | 0.0011 to 0.0013 | upper bound ≤ 0.0015 | pass | - |
| D02 | STD | V3 | - | Romano-Wolf FWER at 0.05 | 0.0520 | 0.0509 to 0.0530 | upper bound ≤ 0.06 | pass | - |
| D02 | STD | V4 | candidate (i) | linked average error, candidate (i) (3909 families passed) | 0.0747 | 0.0662 to 0.0832 | upper bound ≤ 0.22 | pass | - |
| D02 | STD | V4 | candidate (ii) | linked average error, candidate (ii) (360 families passed) | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| D03 | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 10 | 0.0353 | 0.0289 to 0.0416 | upper bound ≤ 0.22 | pass | - |
| D03 | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 20 | 0.0376 | 0.0322 to 0.0430 | upper bound ≤ 0.22 | pass | - |
| D03 | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 40 | 0.0399 | 0.0358 to 0.0440 | upper bound ≤ 0.22 | pass | - |
| D03 | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| D03 | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 20 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| D03 | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 40 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| D03 | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 3 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D03 | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 5 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D03 | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D03 | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 3 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D03 | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 5 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D03 | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D03 | STD | V3 | - | SPA size at 0.2 | 0.2044 | 0.2026 to 0.2061 | upper bound ≤ 0.22 | pass | - |
| D03 | STD | V3 | - | SPA size at 0.05 | 0.0523 | 0.0516 to 0.0531 | upper bound ≤ 0.06 | pass | - |
| D03 | STD | V3 | - | SPA size at 0.001 (pooled) | 0.0012 | 0.0011 to 0.0012 | upper bound ≤ 0.0015 | pass | - |
| D03 | STD | V3 | - | Romano-Wolf FWER at 0.05 | 0.0515 | 0.0508 to 0.0522 | upper bound ≤ 0.06 | pass | - |
| D03 | STD | V4 | candidate (i) | linked average error, candidate (i) (10479 families passed) | 0.0399 | 0.0359 to 0.0440 | upper bound ≤ 0.22 | pass | - |
| D03 | STD | V4 | candidate (ii) | linked average error, candidate (ii) (362 families passed) | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| D04 | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 10 | 0.0220 | 0.0172 to 0.0269 | upper bound ≤ 0.22 | pass | - |
| D04 | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 20 | 0.0257 | 0.0212 to 0.0301 | upper bound ≤ 0.22 | pass | - |
| D04 | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 40 | 0.0295 | 0.0250 to 0.0339 | upper bound ≤ 0.22 | pass | - |
| D04 | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| D04 | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 20 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| D04 | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 40 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| D04 | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 3 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D04 | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 5 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D04 | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D04 | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 3 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D04 | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 5 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D04 | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D04 | STD | V2 | - | forward FDR, enrolment by E-ALL, year 3 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D04 | STD | V2 | - | forward FDR, enrolment by E-ALL, year 5 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D04 | STD | V2 | - | forward FDR, enrolment by E-ALL, year 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D04 | STD | V3 | - | SPA size at 0.2 | 0.2035 | 0.1966 to 0.2104 | upper bound ≤ 0.22 | pass | - |
| D04 | STD | V3 | - | SPA size at 0.05 | 0.0528 | 0.0498 to 0.0558 | upper bound ≤ 0.06 | pass | - |
| D04 | STD | V3 | - | SPA size at 0.001 (pooled) | 0.0011 | 0.0010 to 0.0013 | upper bound ≤ 0.0015 | pass | - |
| D04 | STD | V3 | - | Romano-Wolf FWER at 0.05 | 0.0526 | 0.0496 to 0.0556 | upper bound ≤ 0.06 | pass | - |
| D04 | STD | V4 | candidate (i) | linked average error, candidate (i) (9777 families passed) | 0.0300 | 0.0255 to 0.0345 | upper bound ≤ 0.22 | pass | - |
| D04 | STD | V4 | candidate (ii) | linked average error, candidate (ii) (415 families passed) | 0.0003 | -0.0001 to 0.0007 | upper bound ≤ 0.22 | pass | - |
| D05 | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 10 | 0.0256 | 0.0201 to 0.0311 | upper bound ≤ 0.22 | pass | - |
| D05 | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 20 | 0.0315 | 0.0264 to 0.0366 | upper bound ≤ 0.22 | pass | - |
| D05 | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 40 | 0.0314 | 0.0275 to 0.0354 | upper bound ≤ 0.22 | pass | - |
| D05 | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| D05 | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 20 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| D05 | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 40 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| D05 | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 3 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D05 | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 5 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D05 | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D05 | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 3 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D05 | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 5 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D05 | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D05 | STD | V3 | - | SPA size at 0.2 | 0.2027 | 0.2000 to 0.2053 | upper bound ≤ 0.22 | pass | - |
| D05 | STD | V3 | - | SPA size at 0.05 | 0.0503 | 0.0493 to 0.0513 | upper bound ≤ 0.06 | pass | - |
| D05 | STD | V3 | - | SPA size at 0.001 (pooled) | 0.0009 | 0.0009 to 0.0010 | upper bound ≤ 0.0015 | pass | - |
| D05 | STD | V3 | - | Romano-Wolf FWER at 0.05 | 0.0499 | 0.0489 to 0.0510 | upper bound ≤ 0.06 | pass | - |
| D05 | STD | V4 | candidate (i) | linked average error, candidate (i) (10087 families passed) | 0.0317 | 0.0277 to 0.0356 | upper bound ≤ 0.22 | pass | - |
| D05 | STD | V4 | candidate (ii) | linked average error, candidate (ii) (1257 families passed) | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| D05 | STD | V5 | - | null component wealth ever reaches 20 | 0.0037 | 0.0036 to 0.0038 | upper bound ≤ 0.06 | pass | - |
| D05 | STD | V5 | - | null component wealth ever reaches 100 | 0.0003 | 0.0003 to 0.0004 | upper bound ≤ 0.015 | pass | - |
| D06 | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 10 | 0.0262 | 0.0203 to 0.0321 | upper bound ≤ 0.22 | pass | - |
| D06 | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 20 | 0.0269 | 0.0220 to 0.0319 | upper bound ≤ 0.22 | pass | - |
| D06 | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 40 | 0.0325 | 0.0278 to 0.0372 | upper bound ≤ 0.22 | pass | - |
| D06 | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| D06 | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 20 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| D06 | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 40 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| D06 | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 3 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D06 | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 5 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D06 | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D06 | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 3 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D06 | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 5 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D06 | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D06 | STD | V3 | - | SPA size at 0.2 | 0.2046 | 0.2020 to 0.2072 | upper bound ≤ 0.22 | pass | - |
| D06 | STD | V3 | - | SPA size at 0.05 | 0.0496 | 0.0486 to 0.0506 | upper bound ≤ 0.06 | pass | - |
| D06 | STD | V3 | - | SPA size at 0.001 (pooled) | 0.0008 | 0.0008 to 0.0009 | upper bound ≤ 0.0015 | pass | - |
| D06 | STD | V3 | - | Romano-Wolf FWER at 0.05 | 0.0491 | 0.0481 to 0.0501 | upper bound ≤ 0.06 | pass | - |
| D06 | STD | V4 | candidate (i) | linked average error, candidate (i) (7413 families passed) | 0.0327 | 0.0280 to 0.0375 | upper bound ≤ 0.22 | pass | - |
| D06 | STD | V4 | candidate (ii) | linked average error, candidate (ii) (732 families passed) | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| D06 | STD | V5 | - | null component wealth ever reaches 20 | 0.0034 | 0.0033 to 0.0035 | upper bound ≤ 0.06 | pass | - |
| D06 | STD | V5 | - | null component wealth ever reaches 100 | 0.0003 | 0.0003 to 0.0003 | upper bound ≤ 0.015 | pass | - |
| D07a | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 10 | 0.0532 | 0.0448 to 0.0616 | upper bound ≤ 0.22 | pass | - |
| D07a | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 20 | 0.0654 | 0.0574 to 0.0734 | upper bound ≤ 0.22 | pass | - |
| D07a | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 40 | 0.0717 | 0.0653 to 0.0781 | upper bound ≤ 0.22 | pass | - |
| D07a | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| D07a | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 20 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| D07a | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 40 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| D07a | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 3 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D07a | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 5 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D07a | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D07a | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 3 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D07a | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 5 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D07a | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D07a | STD | V2 | - | forward FDR, enrolment by E-ALL, year 3 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D07a | STD | V2 | - | forward FDR, enrolment by E-ALL, year 5 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D07a | STD | V2 | - | forward FDR, enrolment by E-ALL, year 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D07a | STD | V3 | - | SPA size at 0.2 | 0.2160 | 0.2136 to 0.2184 | upper bound ≤ 0.22 | pass | - |
| D07a | STD | V3 | - | SPA size at 0.05 | 0.0594 | 0.0584 to 0.0604 | upper bound ≤ 0.06 | FAIL | - |
| D07a | STD | V3 | - | SPA size at 0.001 (pooled) | 0.0017 | 0.0016 to 0.0018 | upper bound ≤ 0.0015 | FAIL | - |
| D07a | STD | V3 | - | Romano-Wolf FWER at 0.05 | 0.0588 | 0.0578 to 0.0598 | upper bound ≤ 0.06 | pass | - |
| D07a | STD | V4 | candidate (i) | linked average error, candidate (i) (7634 families passed) | 0.0731 | 0.0666 to 0.0796 | upper bound ≤ 0.22 | pass | - |
| D07a | STD | V4 | candidate (ii) | linked average error, candidate (ii) (30 families passed) | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | not evaluated: fewer than 200 observations | - |
| D07b | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 10 | 0.0220 | 0.0173 to 0.0266 | upper bound ≤ 0.22 | pass | - |
| D07b | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 20 | 0.0267 | 0.0225 to 0.0308 | upper bound ≤ 0.22 | pass | - |
| D07b | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 40 | 0.0268 | 0.0239 to 0.0298 | upper bound ≤ 0.22 | pass | - |
| D07b | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| D07b | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 20 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| D07b | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 40 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| D07b | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 3 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D07b | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 5 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D07b | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D07b | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 3 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D07b | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 5 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D07b | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D07b | STD | V3 | - | SPA size at 0.2 | 0.1979 | 0.1949 to 0.2008 | upper bound ≤ 0.22 | pass | - |
| D07b | STD | V3 | - | SPA size at 0.05 | 0.0486 | 0.0475 to 0.0498 | upper bound ≤ 0.06 | pass | - |
| D07b | STD | V3 | - | SPA size at 0.001 (pooled) | 0.0010 | 0.0009 to 0.0010 | upper bound ≤ 0.0015 | pass | - |
| D07b | STD | V3 | - | Romano-Wolf FWER at 0.05 | 0.0482 | 0.0471 to 0.0493 | upper bound ≤ 0.06 | pass | - |
| D07b | STD | V4 | candidate (i) | linked average error, candidate (i) (13078 families passed) | 0.0271 | 0.0241 to 0.0301 | upper bound ≤ 0.22 | pass | - |
| D07b | STD | V4 | candidate (ii) | linked average error, candidate (ii) (1514 families passed) | 0.0002 | -0.0002 to 0.0005 | upper bound ≤ 0.22 | pass | - |
| D07b | STD | V5 | - | null component wealth ever reaches 20 | 0.0018 | 0.0017 to 0.0019 | upper bound ≤ 0.06 | pass | - |
| D07b | STD | V5 | - | null component wealth ever reaches 100 | 0.0001 | 0.0001 to 0.0001 | upper bound ≤ 0.015 | pass | - |
| D08 | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 10 | 0.0091 | 0.0081 to 0.0100 | upper bound ≤ 0.22 | pass | - |
| D08 | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 20 | 0.0118 | 0.0110 to 0.0126 | upper bound ≤ 0.22 | pass | - |
| D08 | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 40 | 0.0167 | 0.0159 to 0.0175 | upper bound ≤ 0.22 | pass | - |
| D08 | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| D08 | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 20 | 0.0001 | -0.0000 to 0.0003 | upper bound ≤ 0.22 | pass | - |
| D08 | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 40 | 0.0002 | 0.0001 to 0.0003 | upper bound ≤ 0.22 | pass | - |
| D08 | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 3 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D08 | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 5 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D08 | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D08 | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 3 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D08 | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 5 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D08 | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D08 | STD | V3 | - | SPA size at 0.2 | 0.2039 | 0.2012 to 0.2065 | upper bound ≤ 0.22 | pass | - |
| D08 | STD | V3 | - | SPA size at 0.05 | 0.0525 | 0.0515 to 0.0536 | upper bound ≤ 0.06 | pass | - |
| D08 | STD | V3 | - | SPA size at 0.001 (pooled) | 0.0012 | 0.0011 to 0.0013 | upper bound ≤ 0.0015 | pass | - |
| D08 | STD | V3 | - | Romano-Wolf FWER at 0.05 | 0.0507 | 0.0496 to 0.0517 | upper bound ≤ 0.06 | pass | - |
| D08 | STD | V4 | candidate (i) | linked average error, candidate (i) (173108 families passed) | 0.0185 | 0.0177 to 0.0193 | upper bound ≤ 0.22 | pass | - |
| D08 | STD | V4 | candidate (ii) | linked average error, candidate (ii) (37747 families passed) | 0.0023 | 0.0018 to 0.0028 | upper bound ≤ 0.22 | pass | - |
| D09a | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 10 | 0.0343 | 0.0279 to 0.0407 | upper bound ≤ 0.22 | pass | - |
| D09a | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 20 | 0.0390 | 0.0334 to 0.0446 | upper bound ≤ 0.22 | pass | - |
| D09a | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 40 | 0.0390 | 0.0349 to 0.0432 | upper bound ≤ 0.22 | pass | - |
| D09a | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| D09a | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 20 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| D09a | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 40 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| D09a | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 3 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D09a | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 5 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D09a | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D09a | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 3 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D09a | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 5 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D09a | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D09a | STD | V4 | candidate (i) | linked average error, candidate (i) (10174 families passed) | 0.0400 | 0.0358 to 0.0442 | upper bound ≤ 0.22 | pass | - |
| D09a | STD | V4 | candidate (ii) | linked average error, candidate (ii) (1030 families passed) | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| D09b | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 10 | 0.0327 | 0.0265 to 0.0389 | upper bound ≤ 0.22 | pass | - |
| D09b | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 20 | 0.0405 | 0.0346 to 0.0464 | upper bound ≤ 0.22 | pass | - |
| D09b | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 40 | 0.0425 | 0.0380 to 0.0470 | upper bound ≤ 0.22 | pass | - |
| D09b | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| D09b | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 20 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| D09b | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 40 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| D09b | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 3 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D09b | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 5 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D09b | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D09b | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 3 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D09b | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 5 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D09b | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D09b | STD | V4 | candidate (i) | linked average error, candidate (i) (10217 families passed) | 0.0436 | 0.0390 to 0.0482 | upper bound ≤ 0.22 | pass | - |
| D09b | STD | V4 | candidate (ii) | linked average error, candidate (ii) (1019 families passed) | 0.0010 | -0.0004 to 0.0024 | upper bound ≤ 0.22 | pass | - |
| D09b | STD | V10(b) | - | adaptive SPA size at 0.05 on the full set | 0.3348 | 0.3318 to 0.3377 | if upper bound > 0.06: label | label needed: descriptive, not error-controlled | - |
| D11 | STD | V3 | - | hedge-aware test (3.1): SPA size at 0.2 | 0.1926 | 0.1901 to 0.1950 | upper bound ≤ 0.22 | pass | - |
| D11 | STD | V3 | - | hedge-aware test (3.1): SPA size at 0.05 | 0.0459 | 0.0449 to 0.0468 | upper bound ≤ 0.06 | pass | - |
| D11 | STD | V3 | - | hedge-aware test (3.1): SPA size at 0.001 (pooled) | 0.0009 | 0.0008 to 0.0009 | upper bound ≤ 0.0015 | pass | - |
| D11 | STD | V3 | - | hedge-aware test (3.1): Romano-Wolf FWER at 0.05 | 0.0454 | 0.0445 to 0.0463 | upper bound ≤ 0.06 | pass | - |
| D11 | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 10 | 0.0168 | 0.0122 to 0.0214 | upper bound ≤ 0.22 | pass | - |
| D11 | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 20 | 0.0263 | 0.0212 to 0.0314 | upper bound ≤ 0.22 | pass | - |
| D11 | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 40 | 0.0329 | 0.0284 to 0.0373 | upper bound ≤ 0.22 | pass | - |
| D11 | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 10 | 0.0004 | -0.0002 to 0.0010 | upper bound ≤ 0.22 | pass | - |
| D11 | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 20 | 0.0004 | -0.0002 to 0.0010 | upper bound ≤ 0.22 | pass | - |
| D11 | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 40 | 0.0009 | -0.0002 to 0.0021 | upper bound ≤ 0.22 | pass | - |
| D11 | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 3 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D11 | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 5 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D11 | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D11 | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 3 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D11 | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 5 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D11 | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D11 | STD | V4 | candidate (i) | linked average error, candidate (i) (7252 families passed) | 0.0331 | 0.0286 to 0.0376 | upper bound ≤ 0.22 | pass | - |
| D11 | STD | V4 | candidate (ii) | linked average error, candidate (ii) (878 families passed) | 0.0014 | -0.0001 to 0.0029 | upper bound ≤ 0.22 | pass | - |
| P1 | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 10 | 0.0465 | 0.0376 to 0.0553 | upper bound ≤ 0.22 | pass | - |
| P1 | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 20 | 0.0767 | 0.0655 to 0.0879 | upper bound ≤ 0.22 | pass | - |
| P1 | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 40 | 0.1084 | 0.0957 to 0.1212 | upper bound ≤ 0.22 | pass | - |
| P1 | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| P1 | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 20 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| P1 | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 40 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| P1 | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 3 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| P1 | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 5 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| P1 | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| P1 | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 3 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| P1 | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 5 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| P1 | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| P1 | STD | V4 | candidate (i) | linked average error, candidate (i) (1046 families passed) | 0.1084 | 0.0957 to 0.1212 | upper bound ≤ 0.22 | pass | - |
| P1 | STD | V4 | candidate (ii) | linked average error, candidate (ii) (3 families passed) | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | not evaluated: fewer than 200 observations | - |
| P2 | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 10 | 0.0334 | 0.0274 to 0.0394 | upper bound ≤ 0.22 | pass | - |
| P2 | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 20 | 0.0400 | 0.0344 to 0.0456 | upper bound ≤ 0.22 | pass | - |
| P2 | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 40 | 0.0416 | 0.0372 to 0.0460 | upper bound ≤ 0.22 | pass | - |
| P2 | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 10 | 0.0003 | -0.0002 to 0.0007 | upper bound ≤ 0.22 | pass | - |
| P2 | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 20 | 0.0003 | -0.0002 to 0.0007 | upper bound ≤ 0.22 | pass | - |
| P2 | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 40 | 0.0003 | -0.0002 to 0.0007 | upper bound ≤ 0.22 | pass | - |
| P2 | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 3 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| P2 | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 5 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| P2 | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| P2 | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 3 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| P2 | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 5 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| P2 | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| P2 | STD | V4 | candidate (i) | linked average error, candidate (i) (10576 families passed) | 0.0416 | 0.0372 to 0.0460 | upper bound ≤ 0.22 | pass | - |
| P2 | STD | V4 | candidate (ii) | linked average error, candidate (ii) (583 families passed) | 0.0003 | -0.0002 to 0.0007 | upper bound ≤ 0.22 | pass | - |
| P3 | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 10 | 0.0165 | 0.0138 to 0.0192 | upper bound ≤ 0.22 | pass | - |
| P3 | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 20 | 0.0181 | 0.0161 to 0.0201 | upper bound ≤ 0.22 | pass | - |
| P3 | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 40 | 0.0206 | 0.0191 to 0.0221 | upper bound ≤ 0.22 | pass | - |
| P3 | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 10 | 0.0001 | -0.0001 to 0.0004 | upper bound ≤ 0.22 | pass | - |
| P3 | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 20 | 0.0002 | -0.0000 to 0.0005 | upper bound ≤ 0.22 | pass | - |
| P3 | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 40 | 0.0003 | 0.0001 to 0.0005 | upper bound ≤ 0.22 | pass | - |
| P3 | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 3 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| P3 | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 5 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| P3 | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| P3 | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 3 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| P3 | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 5 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| P3 | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| P3 | STD | V4 | candidate (i) | linked average error, candidate (i) (37330 families passed) | 0.0206 | 0.0191 to 0.0221 | upper bound ≤ 0.22 | pass | - |
| P3 | STD | V4 | candidate (ii) | linked average error, candidate (ii) (15381 families passed) | 0.0003 | 0.0001 to 0.0005 | upper bound ≤ 0.22 | pass | - |
| P4 | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 10 | 0.0173 | 0.0147 to 0.0199 | upper bound ≤ 0.22 | pass | - |
| P4 | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 20 | 0.0186 | 0.0168 to 0.0205 | upper bound ≤ 0.22 | pass | - |
| P4 | STD | V1 | candidate (i) | screening FDR, candidate (i), batch 40 | 0.0203 | 0.0189 to 0.0217 | upper bound ≤ 0.22 | pass | - |
| P4 | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| P4 | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 20 | 0.0002 | 0.0000 to 0.0003 | upper bound ≤ 0.22 | pass | - |
| P4 | STD | V1 | candidate (ii) | screening FDR, candidate (ii), batch 40 | 0.0004 | 0.0002 to 0.0006 | upper bound ≤ 0.22 | pass | - |
| P4 | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 3 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| P4 | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 5 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| P4 | STD | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| P4 | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 3 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| P4 | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 5 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| P4 | STD | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| P4 | STD | V4 | candidate (i) | linked average error, candidate (i) (49176 families passed) | 0.0202 | 0.0188 to 0.0216 | upper bound ≤ 0.22 | pass | - |
| P4 | STD | V4 | candidate (ii) | linked average error, candidate (ii) (47795 families passed) | 0.0004 | 0.0002 to 0.0006 | upper bound ≤ 0.22 | pass | - |
| P4 | STD | V11 | candidate (i) | screening power, candidate (i) | 0.9997 | 0.9996 to 0.9999 | lower bound ≥ 0.5 | pass | - |
| P4 | STD | V11 | candidate (ii) | screening power, candidate (ii) | 0.9923 | 0.9914 to 0.9931 | lower bound ≥ 0.5 | pass | - |
| P4 | STD | V11 forward | candidate (i) | forward power by the end (first-quarter families), enrolment by candidate (i) | 0.9996 | 0.9992 to 0.9999 | lower bound ≥ 0.5 | pass | - |
| P4 | STD | V11 forward | candidate (ii) | forward power by the end (first-quarter families), enrolment by candidate (ii) | 0.9843 | 0.9818 to 0.9864 | lower bound ≥ 0.5 | pass | - |
| D01 | LONG | V1 | candidate (i) | screening FDR, candidate (i), batch 25 | 0.0565 | 0.0464 to 0.0666 | upper bound ≤ 0.22 | pass | - |
| D01 | LONG | V1 | candidate (i) | screening FDR, candidate (i), batch 50 | 0.0910 | 0.0784 to 0.1036 | upper bound ≤ 0.22 | pass | - |
| D01 | LONG | V1 | candidate (i) | screening FDR, candidate (i), batch 100 | 0.1410 | 0.1257 to 0.1563 | upper bound ≤ 0.22 | pass | - |
| D01 | LONG | V1 | candidate (ii) | screening FDR, candidate (ii), batch 25 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| D01 | LONG | V1 | candidate (ii) | screening FDR, candidate (ii), batch 50 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| D01 | LONG | V1 | candidate (ii) | screening FDR, candidate (ii), batch 100 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| D01 | LONG | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 3 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D01 | LONG | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 5 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D01 | LONG | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D01 | LONG | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 3 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D01 | LONG | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 5 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D01 | LONG | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D01 | LONG | V3 | - | SPA size at 0.2 | 0.2040 | 0.2015 to 0.2066 | upper bound ≤ 0.22 | pass | - |
| D01 | LONG | V3 | - | SPA size at 0.05 | 0.0522 | 0.0512 to 0.0532 | upper bound ≤ 0.06 | pass | - |
| D01 | LONG | V3 | - | SPA size at 0.001 (pooled) | 0.0012 | 0.0011 to 0.0012 | upper bound ≤ 0.0015 | pass | - |
| D01 | LONG | V3 | - | Romano-Wolf FWER at 0.05 | 0.0522 | 0.0512 to 0.0532 | upper bound ≤ 0.06 | pass | - |
| D01 | LONG | V4 | candidate (i) | linked average error, candidate (i) (333 families passed) | 0.1410 | 0.1257 to 0.1563 | upper bound ≤ 0.22 | pass | - |
| D01 | LONG | V4 | candidate (ii) | linked average error, candidate (ii) (0 families passed) | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | not evaluated: fewer than 200 observations | - |
| D01 | LONG | V5 | - | null component wealth ever reaches 20 | 0.0033 | 0.0032 to 0.0034 | upper bound ≤ 0.06 | pass | - |
| D01 | LONG | V5 | - | null component wealth ever reaches 100 | 0.0003 | 0.0002 to 0.0003 | upper bound ≤ 0.015 | pass | - |
| D02 | LONG | V1 | candidate (i) | screening FDR, candidate (i), batch 25 | 0.0361 | 0.0288 to 0.0435 | upper bound ≤ 0.22 | pass | - |
| D02 | LONG | V1 | candidate (i) | screening FDR, candidate (i), batch 50 | 0.0534 | 0.0454 to 0.0614 | upper bound ≤ 0.22 | pass | - |
| D02 | LONG | V1 | candidate (i) | screening FDR, candidate (i), batch 100 | 0.0678 | 0.0598 to 0.0758 | upper bound ≤ 0.22 | pass | - |
| D02 | LONG | V1 | candidate (ii) | screening FDR, candidate (ii), batch 25 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| D02 | LONG | V1 | candidate (ii) | screening FDR, candidate (ii), batch 50 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| D02 | LONG | V1 | candidate (ii) | screening FDR, candidate (ii), batch 100 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.22 | pass | - |
| D02 | LONG | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 3 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D02 | LONG | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 5 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D02 | LONG | V2 | candidate (i) | forward FDR, enrolment by candidate (i), year 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D02 | LONG | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 3 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D02 | LONG | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 5 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D02 | LONG | V2 | candidate (ii) | forward FDR, enrolment by candidate (ii), year 10 | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.06 | pass | - |
| D02 | LONG | V3 | - | SPA size at 0.2 | 0.2026 | 0.2000 to 0.2052 | upper bound ≤ 0.22 | pass | - |
| D02 | LONG | V3 | - | SPA size at 0.05 | 0.0518 | 0.0508 to 0.0528 | upper bound ≤ 0.06 | pass | - |
| D02 | LONG | V3 | - | SPA size at 0.001 (pooled) | 0.0012 | 0.0011 to 0.0012 | upper bound ≤ 0.0015 | pass | - |
| D02 | LONG | V3 | - | Romano-Wolf FWER at 0.05 | 0.0516 | 0.0506 to 0.0526 | upper bound ≤ 0.06 | pass | - |
| D02 | LONG | V4 | candidate (i) | linked average error, candidate (i) (4280 families passed) | 0.0681 | 0.0601 to 0.0761 | upper bound ≤ 0.22 | pass | - |
| D02 | LONG | V4 | candidate (ii) | linked average error, candidate (ii) (352 families passed) | 0.0005 | -0.0005 to 0.0015 | upper bound ≤ 0.22 | pass | - |
| D01h | STD | V3 | - | hedge-aware test (3.1): SPA size at 0.2 | 0.1976 | 0.1920 to 0.2032 | upper bound ≤ 0.22 | pass | - |
| D01h | STD | V3 | - | hedge-aware test (3.1): SPA size at 0.05 | 0.0473 | 0.0452 to 0.0494 | upper bound ≤ 0.06 | pass | - |
| D01h | STD | V3 | - | hedge-aware test (3.1): SPA size at 0.001 (pooled) | 0.0009 | 0.0008 to 0.0010 | upper bound ≤ 0.0015 | pass | - |
| D01h | STD | V3 | - | hedge-aware test (3.1): Romano-Wolf FWER at 0.05 | 0.0472 | 0.0451 to 0.0493 | upper bound ≤ 0.06 | pass | - |
| D02h | STD | V3 | - | hedge-aware test (3.1): SPA size at 0.2 | 0.1925 | 0.1873 to 0.1978 | upper bound ≤ 0.22 | pass | - |
| D02h | STD | V3 | - | hedge-aware test (3.1): SPA size at 0.05 | 0.0458 | 0.0438 to 0.0478 | upper bound ≤ 0.06 | pass | - |
| D02h | STD | V3 | - | hedge-aware test (3.1): SPA size at 0.001 (pooled) | 0.0008 | 0.0007 to 0.0009 | upper bound ≤ 0.0015 | pass | - |
| D02h | STD | V3 | - | hedge-aware test (3.1): Romano-Wolf FWER at 0.05 | 0.0456 | 0.0436 to 0.0475 | upper bound ≤ 0.06 | pass | - |
| D03h | STD | V3 | - | hedge-aware test (3.1): SPA size at 0.2 | 0.1946 | 0.1908 to 0.1984 | upper bound ≤ 0.22 | pass | - |
| D03h | STD | V3 | - | hedge-aware test (3.1): SPA size at 0.05 | 0.0469 | 0.0454 to 0.0484 | upper bound ≤ 0.06 | pass | - |
| D03h | STD | V3 | - | hedge-aware test (3.1): SPA size at 0.001 (pooled) | 0.0007 | 0.0006 to 0.0009 | upper bound ≤ 0.0015 | pass | - |
| D03h | STD | V3 | - | hedge-aware test (3.1): Romano-Wolf FWER at 0.05 | 0.0461 | 0.0447 to 0.0476 | upper bound ≤ 0.06 | pass | - |
| D05h | STD | V3 | - | hedge-aware test (3.1): SPA size at 0.2 | 0.1927 | 0.1872 to 0.1981 | upper bound ≤ 0.22 | pass | - |
| D05h | STD | V3 | - | hedge-aware test (3.1): SPA size at 0.05 | 0.0443 | 0.0423 to 0.0463 | upper bound ≤ 0.06 | pass | - |
| D05h | STD | V3 | - | hedge-aware test (3.1): SPA size at 0.001 (pooled) | 0.0006 | 0.0005 to 0.0007 | upper bound ≤ 0.0015 | pass | - |
| D05h | STD | V3 | - | hedge-aware test (3.1): Romano-Wolf FWER at 0.05 | 0.0441 | 0.0421 to 0.0461 | upper bound ≤ 0.06 | pass | - |
| D06h | STD | V3 | - | hedge-aware test (3.1): SPA size at 0.2 | 0.1936 | 0.1880 to 0.1993 | upper bound ≤ 0.22 | pass | - |
| D06h | STD | V3 | - | hedge-aware test (3.1): SPA size at 0.05 | 0.0426 | 0.0406 to 0.0446 | upper bound ≤ 0.06 | pass | - |
| D06h | STD | V3 | - | hedge-aware test (3.1): SPA size at 0.001 (pooled) | 0.0006 | 0.0005 to 0.0007 | upper bound ≤ 0.0015 | pass | - |
| D06h | STD | V3 | - | hedge-aware test (3.1): Romano-Wolf FWER at 0.05 | 0.0423 | 0.0403 to 0.0443 | upper bound ≤ 0.06 | pass | - |
| D07ah | STD | V3 | - | hedge-aware test (3.1): SPA size at 0.2 | 0.2076 | 0.2024 to 0.2127 | upper bound ≤ 0.22 | pass | - |
| D07ah | STD | V3 | - | hedge-aware test (3.1): SPA size at 0.05 | 0.0525 | 0.0504 to 0.0546 | upper bound ≤ 0.06 | pass | - |
| D07ah | STD | V3 | - | hedge-aware test (3.1): SPA size at 0.001 (pooled) | 0.0012 | 0.0010 to 0.0014 | upper bound ≤ 0.0015 | pass | - |
| D07ah | STD | V3 | - | hedge-aware test (3.1): Romano-Wolf FWER at 0.05 | 0.0520 | 0.0499 to 0.0541 | upper bound ≤ 0.06 | pass | - |
| D07bh | STD | V3 | - | hedge-aware test (3.1): SPA size at 0.2 | 0.1889 | 0.1826 to 0.1951 | upper bound ≤ 0.22 | pass | - |
| D07bh | STD | V3 | - | hedge-aware test (3.1): SPA size at 0.05 | 0.0427 | 0.0405 to 0.0449 | upper bound ≤ 0.06 | pass | - |
| D07bh | STD | V3 | - | hedge-aware test (3.1): SPA size at 0.001 (pooled) | 0.0007 | 0.0005 to 0.0008 | upper bound ≤ 0.0015 | pass | - |
| D07bh | STD | V3 | - | hedge-aware test (3.1): Romano-Wolf FWER at 0.05 | 0.0423 | 0.0401 to 0.0445 | upper bound ≤ 0.06 | pass | - |
| D08h | STD | V3 | - | hedge-aware test (3.1): SPA size at 0.2 | 0.1897 | 0.1841 to 0.1953 | upper bound ≤ 0.22 | pass | - |
| D08h | STD | V3 | - | hedge-aware test (3.1): SPA size at 0.05 | 0.0448 | 0.0426 to 0.0469 | upper bound ≤ 0.06 | pass | - |
| D08h | STD | V3 | - | hedge-aware test (3.1): SPA size at 0.001 (pooled) | 0.0008 | 0.0006 to 0.0010 | upper bound ≤ 0.0015 | pass | - |
| D08h | STD | V3 | - | hedge-aware test (3.1): Romano-Wolf FWER at 0.05 | 0.0429 | 0.0408 to 0.0449 | upper bound ≤ 0.06 | pass | - |
| D01 | HB | V12 | - | reviews not computed (a fit fails the grid gate), of 16000 | 0.0000 | - | exactly 0 | not decided: records of other code (4252b971831004e3) | pass |
| D01 | HB | V6 | - | year 4: share with a true edge among families with Π^min ≥ 0.8 (1 family observations) | 0.0000 | 0.0000 to 0.0000 | lower bound ≥ 0.7 | not decided: records of other code (4252b971831004e3) | not evaluated: fewer than 200 observations |
| D01 | HB | V6 | - | year 4: share with a true edge among families with Π^min ≥ 0.4 (5 family observations) | 0.0000 | 0.0000 to 0.0000 | lower bound ≥ 0.3 | not decided: records of other code (4252b971831004e3) | not evaluated: fewer than 200 observations |
| D01 | HB | V6 | - | year 4: expected calibration error of the central model | 0.0361 | 0.0351 to 0.0371 | upper bound ≤ 0.1 | not decided: records of other code (4252b971831004e3) | pass |
| D01 | HB | V6 | - | year 4: share of family evaluations with Π^min ≥ 0.80 (no edges exist) | 0.0000 | 0.0000 to 0.0001 | upper bound ≤ 0.01 | not decided: records of other code (4252b971831004e3) | pass |
| D01 | HB | V8 | candidate (i) | year 4: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (25 obs.) | 0.7396 | 0.4688 to 1.0239 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | not decided: records of other code (4252b971831004e3) | not evaluated: fewer than 200 observations |
| D01 | HB | V8 | candidate (i) | year 4: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (0 obs.) | - | - | upper bound ≤ +0.1 and lower bound ≥ -0.25 | not decided: records of other code (4252b971831004e3) | not evaluated: fewer than 200 observations |
| D01 | HB | V8 | candidate (ii) | year 4: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (12 obs.) | 1.3391 | 1.0608 to 1.6822 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | not decided: records of other code (4252b971831004e3) | not evaluated: fewer than 200 observations |
| D01 | HB | V8 | candidate (ii) | year 4: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (0 obs.) | - | - | upper bound ≤ +0.1 and lower bound ≥ -0.25 | not decided: records of other code (4252b971831004e3) | not evaluated: fewer than 200 observations |
| D01 | HB | V6 | - | year 10: share with a true edge among families with Π^min ≥ 0.8 (0 family observations) | - | - | lower bound ≥ 0.7 | not decided: records of other code (4252b971831004e3) | not evaluated: fewer than 200 observations |
| D01 | HB | V6 | - | year 10: share with a true edge among families with Π^min ≥ 0.4 (7 family observations) | 0.0000 | 0.0000 to 0.0000 | lower bound ≥ 0.3 | not decided: records of other code (4252b971831004e3) | not evaluated: fewer than 200 observations |
| D01 | HB | V6 | - | year 10: expected calibration error of the central model | 0.0262 | 0.0256 to 0.0271 | upper bound ≤ 0.1 | not decided: records of other code (4252b971831004e3) | pass |
| D01 | HB | V6 | - | year 10: share of family evaluations with Π^min ≥ 0.80 (no edges exist) | 0.0000 | 0.0000 to 0.0000 | upper bound ≤ 0.01 | not decided: records of other code (4252b971831004e3) | pass |
| D01 | HB | V8 | candidate (i) | year 10: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (25 obs.) | 0.9605 | 0.7228 to 1.2197 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | not decided: records of other code (4252b971831004e3) | not evaluated: fewer than 200 observations |
| D01 | HB | V8 | candidate (i) | year 10: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (0 obs.) | - | - | upper bound ≤ +0.1 and lower bound ≥ -0.25 | not decided: records of other code (4252b971831004e3) | not evaluated: fewer than 200 observations |
| D01 | HB | V8 | candidate (ii) | year 10: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (18 obs.) | 1.2574 | 1.0686 to 1.4692 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | not decided: records of other code (4252b971831004e3) | not evaluated: fewer than 200 observations |
| D01 | HB | V8 | candidate (ii) | year 10: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (0 obs.) | - | - | upper bound ≤ +0.1 and lower bound ≥ -0.25 | not decided: records of other code (4252b971831004e3) | not evaluated: fewer than 200 observations |
| D01 | HB | V7 | candidate (i) | premature elimination: families with a true edge that end dormant, candidate (i) | - | - | upper bound ≤ 0.1 | not decided: records of other code (4252b971831004e3) | no data |
| D01 | HB | V7 | candidate (ii) | premature elimination: families with a true edge that end dormant, candidate (ii) | - | - | upper bound ≤ 0.1 | not decided: records of other code (4252b971831004e3) | no data |
| D02 | HB | V12 | - | reviews not computed (a fit fails the grid gate), of 16000 | 0.0000 | - | exactly 0 | not decided: records of other code (4252b971831004e3) | pass |
| D02 | HB | V6 | - | year 4: share with a true edge among families with Π^min ≥ 0.8 (7 family observations) | 1.0000 | 1.0000 to 1.0000 | lower bound ≥ 0.7 | not decided: records of other code (4252b971831004e3) | not evaluated: fewer than 200 observations |
| D02 | HB | V6 | - | year 4: share with a true edge among families with Π^min ≥ 0.4 (60 family observations) | 0.9333 | 0.8750 to 0.9851 | lower bound ≥ 0.3 | not decided: records of other code (4252b971831004e3) | not evaluated: fewer than 200 observations |
| D02 | HB | V6 | - | year 4: expected calibration error of the central model | 0.0241 | 0.0224 to 0.0257 | upper bound ≤ 0.1 | not decided: records of other code (4252b971831004e3) | pass |
| D02 | HB | V8 | candidate (i) | year 4: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (142 obs.) | -0.1922 | -0.2970 to -0.0867 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | not decided: records of other code (4252b971831004e3) | not evaluated: fewer than 200 observations |
| D02 | HB | V8 | candidate (i) | year 4: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (8 obs.) | -0.0523 | -0.3691 to 0.3998 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | not decided: records of other code (4252b971831004e3) | not evaluated: fewer than 200 observations |
| D02 | HB | V8 | candidate (ii) | year 4: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (82 obs.) | -0.0481 | -0.2113 to 0.1102 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | not decided: records of other code (4252b971831004e3) | not evaluated: fewer than 200 observations |
| D02 | HB | V8 | candidate (ii) | year 4: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (8 obs.) | -0.0523 | -0.3691 to 0.3998 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | not decided: records of other code (4252b971831004e3) | not evaluated: fewer than 200 observations |
| D02 | HB | V6 | - | year 10: share with a true edge among families with Π^min ≥ 0.8 (40 family observations) | 1.0000 | 1.0000 to 1.0000 | lower bound ≥ 0.7 | not decided: records of other code (4252b971831004e3) | not evaluated: fewer than 200 observations |
| D02 | HB | V6 | - | year 10: share with a true edge among families with Π^min ≥ 0.4 (198 family observations) | 0.9545 | 0.9222 to 0.9813 | lower bound ≥ 0.3 | not decided: records of other code (4252b971831004e3) | not evaluated: fewer than 200 observations |
| D02 | HB | V6 | - | year 10: expected calibration error of the central model | 0.0160 | 0.0150 to 0.0172 | upper bound ≤ 0.1 | not decided: records of other code (4252b971831004e3) | pass |
| D02 | HB | V8 | candidate (i) | year 10: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (340 obs.) | -0.0880 | -0.1407 to -0.0318 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | not decided: records of other code (4252b971831004e3) | pass |
| D02 | HB | V8 | candidate (i) | year 10: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (60 obs.) | 0.1051 | 0.0156 to 0.1986 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | not decided: records of other code (4252b971831004e3) | not evaluated: fewer than 200 observations |
| D02 | HB | V8 | candidate (ii) | year 10: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (287 obs.) | -0.0103 | -0.0668 to 0.0473 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | not decided: records of other code (4252b971831004e3) | pass |
| D02 | HB | V8 | candidate (ii) | year 10: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (59 obs.) | 0.1115 | 0.0189 to 0.2067 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | not decided: records of other code (4252b971831004e3) | not evaluated: fewer than 200 observations |
| D02 | HB | V7 | candidate (i) | premature elimination: families with a true edge that end dormant, candidate (i) | 0.0137 | 0.0088 to 0.0193 | upper bound ≤ 0.1 | not decided: records of other code (4252b971831004e3) | pass |
| D02 | HB | V7 | candidate (ii) | premature elimination: families with a true edge that end dormant, candidate (ii) | 0.0137 | 0.0088 to 0.0193 | upper bound ≤ 0.1 | not decided: records of other code (4252b971831004e3) | pass |
| D05 | HB | V12 | - | reviews not computed (a fit fails the grid gate), of 16000 | 0.0000 | - | exactly 0 | not decided: records of other code (4252b971831004e3) | pass |
| D05 | HB | V6 | - | year 4: share with a true edge among families with Π^min ≥ 0.8 (29 family observations) | 1.0000 | 1.0000 to 1.0000 | lower bound ≥ 0.7 | not decided: records of other code (4252b971831004e3) | not evaluated: fewer than 200 observations |
| D05 | HB | V6 | - | year 4: share with a true edge among families with Π^min ≥ 0.4 (163 family observations) | 0.9448 | 0.9040 to 0.9808 | lower bound ≥ 0.3 | not decided: records of other code (4252b971831004e3) | not evaluated: fewer than 200 observations |
| D05 | HB | V6 | - | year 4: expected calibration error of the central model | 0.0089 | 0.0070 to 0.0115 | upper bound ≤ 0.1 | not decided: records of other code (4252b971831004e3) | pass |
| D05 | HB | V8 | candidate (i) | year 4: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (378 obs.) | -0.2044 | -0.2703 to -0.1412 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | not decided: records of other code (4252b971831004e3) | FAIL |
| D05 | HB | V8 | candidate (i) | year 4: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (35 obs.) | 0.2334 | 0.0582 to 0.4323 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | not decided: records of other code (4252b971831004e3) | not evaluated: fewer than 200 observations |
| D05 | HB | V8 | candidate (ii) | year 4: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (212 obs.) | 0.0039 | -0.0833 to 0.0932 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | not decided: records of other code (4252b971831004e3) | pass |
| D05 | HB | V8 | candidate (ii) | year 4: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (32 obs.) | 0.2028 | 0.0283 to 0.4051 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | not decided: records of other code (4252b971831004e3) | not evaluated: fewer than 200 observations |
| D05 | HB | V6 | - | year 10: share with a true edge among families with Π^min ≥ 0.8 (131 family observations) | 1.0000 | 1.0000 to 1.0000 | lower bound ≥ 0.7 | not decided: records of other code (4252b971831004e3) | not evaluated: fewer than 200 observations |
| D05 | HB | V6 | - | year 10: share with a true edge among families with Π^min ≥ 0.4 (548 family observations) | 0.9854 | 0.9750 to 0.9944 | lower bound ≥ 0.3 | not decided: records of other code (4252b971831004e3) | pass |
| D05 | HB | V6 | - | year 10: expected calibration error of the central model | 0.0052 | 0.0037 to 0.0069 | upper bound ≤ 0.1 | not decided: records of other code (4252b971831004e3) | pass |
| D05 | HB | V8 | candidate (i) | year 10: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (888 obs.) | -0.0603 | -0.0897 to -0.0302 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | not decided: records of other code (4252b971831004e3) | pass |
| D05 | HB | V8 | candidate (i) | year 10: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (201 obs.) | 0.0800 | 0.0310 to 0.1281 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | not decided: records of other code (4252b971831004e3) | FAIL |
| D05 | HB | V8 | candidate (ii) | year 10: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (753 obs.) | 0.0029 | -0.0287 to 0.0351 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | not decided: records of other code (4252b971831004e3) | pass |
| D05 | HB | V8 | candidate (ii) | year 10: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (194 obs.) | 0.0839 | 0.0383 to 0.1307 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | not decided: records of other code (4252b971831004e3) | not evaluated: fewer than 200 observations |
| D05 | HB | V7 | candidate (i) | premature elimination: families with a true edge that end dormant, candidate (i) | 0.0208 | 0.0161 to 0.0258 | upper bound ≤ 0.1 | not decided: records of other code (4252b971831004e3) | pass |
| D05 | HB | V7 | candidate (ii) | premature elimination: families with a true edge that end dormant, candidate (ii) | 0.0208 | 0.0161 to 0.0258 | upper bound ≤ 0.1 | not decided: records of other code (4252b971831004e3) | pass |
| D08 | HB | V12 | - | reviews not computed (a fit fails the grid gate), of 16000 | 0.0000 | - | exactly 0 | not decided: records of other code (4252b971831004e3) | pass |
| D08 | HB | V6 | - | year 4: share with a true edge among families with Π^min ≥ 0.8 (590 family observations) | 0.9966 | 0.9920 to 1.0000 | lower bound ≥ 0.7 | not decided: records of other code (4252b971831004e3) | pass |
| D08 | HB | V6 | - | year 4: share with a true edge among families with Π^min ≥ 0.4 (5823 family observations) | 0.8800 | 0.8628 to 0.8980 | lower bound ≥ 0.3 | not decided: records of other code (4252b971831004e3) | pass |
| D08 | HB | V6 | - | year 4: expected calibration error of the central model | 0.0692 | 0.0613 to 0.0772 | upper bound ≤ 0.1 | not decided: records of other code (4252b971831004e3) | pass |
| D08 | HB | V8 | candidate (i) | year 4: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (8277 obs.) | -0.2745 | -0.2954 to -0.2539 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | not decided: records of other code (4252b971831004e3) | FAIL |
| D08 | HB | V8 | candidate (i) | year 4: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (592 obs.) | -0.0846 | -0.1158 to -0.0514 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | not decided: records of other code (4252b971831004e3) | pass |
| D08 | HB | V8 | candidate (ii) | year 4: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (6494 obs.) | -0.2114 | -0.2321 to -0.1915 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | not decided: records of other code (4252b971831004e3) | pass |
| D08 | HB | V8 | candidate (ii) | year 4: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (555 obs.) | -0.0865 | -0.1161 to -0.0547 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | not decided: records of other code (4252b971831004e3) | pass |
| D08 | HB | V6 | - | year 10: share with a true edge among families with Π^min ≥ 0.8 (3875 family observations) | 0.9954 | 0.9926 to 0.9977 | lower bound ≥ 0.7 | not decided: records of other code (4252b971831004e3) | pass |
| D08 | HB | V6 | - | year 10: share with a true edge among families with Π^min ≥ 0.4 (15747 family observations) | 0.8664 | 0.8556 to 0.8771 | lower bound ≥ 0.3 | not decided: records of other code (4252b971831004e3) | pass |
| D08 | HB | V6 | - | year 10: expected calibration error of the central model | 0.1140 | 0.1059 to 0.1220 | upper bound ≤ 0.1 | not decided: records of other code (4252b971831004e3) | FAIL |
| D08 | HB | V8 | candidate (i) | year 10: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (21296 obs.) | -0.1213 | -0.1351 to -0.1076 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | not decided: records of other code (4252b971831004e3) | pass |
| D08 | HB | V8 | candidate (i) | year 10: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (4993 obs.) | -0.0738 | -0.0857 to -0.0615 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | not decided: records of other code (4252b971831004e3) | pass |
| D08 | HB | V8 | candidate (ii) | year 10: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (20317 obs.) | -0.1086 | -0.1220 to -0.0953 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | not decided: records of other code (4252b971831004e3) | pass |
| D08 | HB | V8 | candidate (ii) | year 10: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (4745 obs.) | -0.0681 | -0.0804 to -0.0560 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | not decided: records of other code (4252b971831004e3) | pass |
| D08 | HB | V7 | candidate (i) | premature elimination: families with a true edge that end dormant, candidate (i) | 0.0079 | 0.0068 to 0.0091 | upper bound ≤ 0.1 | not decided: records of other code (4252b971831004e3) | pass |
| D08 | HB | V7 | candidate (ii) | premature elimination: families with a true edge that end dormant, candidate (ii) | 0.0078 | 0.0067 to 0.0090 | upper bound ≤ 0.1 | not decided: records of other code (4252b971831004e3) | pass |
| D10 | HB | V12 | - | reviews not computed (a fit fails the grid gate), of 16000 | 0.0000 | - | exactly 0 | not decided: records of other code (4252b971831004e3) | pass |
| D10 | HB | V6 | - | year 4: share with a true edge among families with Π^min ≥ 0.8 (200 family observations) | 0.8600 | 0.8032 to 0.9086 | lower bound ≥ 0.7 | not decided: records of other code (4252b971831004e3) | pass |
| D10 | HB | V6 | - | year 4: share with a true edge among families with Π^min ≥ 0.4 (791 family observations) | 0.6549 | 0.6240 to 0.6868 | lower bound ≥ 0.3 | not decided: records of other code (4252b971831004e3) | pass |
| D10 | HB | V6 | - | year 4: expected calibration error of the central model | 0.0184 | 0.0167 to 0.0205 | upper bound ≤ 0.1 | not decided: records of other code (4252b971831004e3) | pass |
| D10 | HB | V8 | candidate (i) | year 4: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (1549 obs.) | -0.0258 | -0.0539 to 0.0018 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | not decided: records of other code (4252b971831004e3) | pass |
| D10 | HB | V8 | candidate (i) | year 4: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (197 obs.) | -0.0677 | -0.1542 to 0.0223 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | not decided: records of other code (4252b971831004e3) | not evaluated: fewer than 200 observations |
| D10 | HB | V8 | candidate (ii) | year 4: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (1185 obs.) | 0.0237 | -0.0079 to 0.0561 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | not decided: records of other code (4252b971831004e3) | pass |
| D10 | HB | V8 | candidate (ii) | year 4: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (195 obs.) | -0.0675 | -0.1535 to 0.0228 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | not decided: records of other code (4252b971831004e3) | not evaluated: fewer than 200 observations |
| D10 | HB | V6 | - | year 10: share with a true edge among families with Π^min ≥ 0.8 (841 family observations) | 0.8823 | 0.8607 to 0.9040 | lower bound ≥ 0.7 | not decided: records of other code (4252b971831004e3) | pass |
| D10 | HB | V6 | - | year 10: share with a true edge among families with Π^min ≥ 0.4 (2163 family observations) | 0.7642 | 0.7467 to 0.7813 | lower bound ≥ 0.3 | not decided: records of other code (4252b971831004e3) | pass |
| D10 | HB | V6 | - | year 10: expected calibration error of the central model | 0.0188 | 0.0178 to 0.0199 | upper bound ≤ 0.1 | not decided: records of other code (4252b971831004e3) | pass |
| D10 | HB | V8 | candidate (i) | year 10: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (3232 obs.) | 0.0721 | 0.0564 to 0.0893 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | not decided: records of other code (4252b971831004e3) | pass |
| D10 | HB | V8 | candidate (i) | year 10: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (983 obs.) | 0.0683 | 0.0391 to 0.0983 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | not decided: records of other code (4252b971831004e3) | pass |
| D10 | HB | V8 | candidate (ii) | year 10: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (2987 obs.) | 0.0867 | 0.0704 to 0.1033 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | not decided: records of other code (4252b971831004e3) | FAIL |
| D10 | HB | V8 | candidate (ii) | year 10: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (981 obs.) | 0.0667 | 0.0377 to 0.0971 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | not decided: records of other code (4252b971831004e3) | pass |
| D10 | HB | V7 | candidate (i) | premature elimination: families with a true edge that end dormant, candidate (i) | 0.0178 | 0.0140 to 0.0216 | upper bound ≤ 0.1 | not decided: records of other code (4252b971831004e3) | pass |
| D10 | HB | V7 | candidate (ii) | premature elimination: families with a true edge that end dormant, candidate (ii) | 0.0178 | 0.0140 to 0.0216 | upper bound ≤ 0.1 | not decided: records of other code (4252b971831004e3) | pass |
| D09a, D09b | STD | V10 | - | designated blind statistics identical with and without the adaptive channel (2 replications, 3 batches) | - | - | bit-for-bit identical | pass | - |

## 3. Screening candidates: the development half of SIM_PREREG section 7 step 1

Eligibility also needs the same criteria on the held-out scenarios of a confirmation run, which has not happened. **No candidate is eligible or selected here**, and the power comparison of step 2 is not computed.

| candidate | criteria | development state | required rows by category | runs not complete | held-out half | eligible |
|---|---|---|---|---|---|---|
| candidate (i) | V1, V4, V3, V10, V11 | FAIL on development | FAIL: 2, pass: 152 | D04h STD | not evaluated: needs a tagged confirmation run (SIM_PREREG section 8.1 rule 4) | not determined |
| candidate (ii) | V1, V4, V10, V11 | development rows pass | not evaluated (small group): 4, pass: 70 | - | not evaluated: needs a tagged confirmation run (SIM_PREREG section 8.1 rule 4) | not determined |

## 4. Components (SIM_PREREG section 8.1 rule 2)

| component | development state | required rows by category | runs not complete | note |
|---|---|---|---|---|
| within-family tests (SPA, Romano-Wolf, Benjamini-Bogomolov link) | FAIL on development | FAIL: 2, not evaluated (small group): 4, pass: 110 | D04h STD | - |
| forward test (e-process, e-LOND) | development rows pass | pass: 129 | - | forward criteria must hold for the candidate that is selected (SIM_PREREG section 2.5); no candidate is selected, so rows of both are shown |
| hierarchical model: posterior-based tiers | not decided | not decided: 77 | D01 HB, D02 HB, D05 HB, D08 HB, D10 HB | - |
| hierarchical model: dormancy | not decided | not decided: 15 | D01 HB, D02 HB, D05 HB, D08 HB, D10 HB | - |

Code properties checked by the test suite, not by runs: V10(a) (results file v10a.json and tests/test_manhattan_sim_pipeline.py); V13 (tests/test_manhattan_spa_hedged.py); V14 (tests/test_manhattan_adaptive_weight.py); V15 (tests/test_manhattan_tailrisk.py).

## 5. Held-out scenarios

| scenario | pre-registration | sizes | world coded | runs on record | refusals on record |
|---|---|---|---|---|---|
| H01 | v1 | STD, STD E-ALL | no | 0 | 0 |
| H02a | v1 | STD | no | 0 | 0 |
| H02b | v1 | STD E-ALL | no | 0 | 0 |
| H02c | v1 | STD E-ALL | no | 0 | 0 |
| H03 | v1 | STD, HB | no | 0 | 0 |
| H04 | v1 | STD, STD E-ALL | no | 0 | 0 |
| H05 | v1 | STD, HB | no | 0 | 0 |
| H06 | v1 | STD, HB | no | 0 | 0 |
| H07 | v1 | HB | no | 0 | 0 |
| H08m | v1 | STD E-ALL | no | 0 | 0 |
| H08x | v1 | STD E-ALL | no | 0 | 0 |
| H09 | v1 | HB | no | 0 | 0 |
| H10 | v1 | STD E-ALL, HB | no | 0 | 0 |
| H11 | v1 | STD, LONG, HB | no | 0 | 0 |
| H12 | v2 | STD | no | 0 | 0 |

## 6. Missing or unverified evidence

- D04h at STD: 368 of 400 for the current code 9d1b680ff7e19ca7 (missing: 172 to 203); other code on file: none
- D01 at HB: 0 of 400 for the current code c864e57955126c37 (missing: 0 to 399); other code on file: 400 by code 4252b971831004e3 (review step 63); 12 by code 630059032fd6e5b8; 12 by code 6d71b497779d4842; 12 by code c22815235975c486
- D02 at HB: 0 of 400 for the current code c864e57955126c37 (missing: 0 to 399); other code on file: 400 by code 4252b971831004e3 (review step 63); 12 by code 630059032fd6e5b8; 12 by code 6d71b497779d4842; 12 by code c22815235975c486
- D05 at HB: 0 of 400 for the current code c864e57955126c37 (missing: 0 to 399); other code on file: 400 by code 4252b971831004e3 (review step 63); 12 by code 630059032fd6e5b8; 12 by code c22815235975c486; 8 by code 6d71b497779d4842
- D08 at HB: 0 of 400 for the current code c864e57955126c37 (missing: 0 to 399); other code on file: 400 by code 4252b971831004e3 (review step 63); 12 by code 630059032fd6e5b8; 12 by code c22815235975c486
- D10 at HB: 0 of 400 for the current code c864e57955126c37 (missing: 0 to 399); other code on file: 400 by code 4252b971831004e3 (review step 63); 12 by code 630059032fd6e5b8; 12 by code c22815235975c486
- H01: world not coded; no held-out evidence of any kind
- H02a: world not coded; no held-out evidence of any kind
- H02b: world not coded; no held-out evidence of any kind
- H02c: world not coded; no held-out evidence of any kind
- H03: world not coded; no held-out evidence of any kind
- H04: world not coded; no held-out evidence of any kind
- H05: world not coded; no held-out evidence of any kind
- H06: world not coded; no held-out evidence of any kind
- H07: world not coded; no held-out evidence of any kind
- H08m: world not coded; no held-out evidence of any kind
- H08x: world not coded; no held-out evidence of any kind
- H09: world not coded; no held-out evidence of any kind
- H10: world not coded; no held-out evidence of any kind
- H11: world not coded; no held-out evidence of any kind
- H12: world not coded; no held-out evidence of any kind

## 7. Record files read (SHA-256)

- `v1/D01_STD_b0.jsonl`: `06ffe02b7913457d9ed65c13cc38a077d58cb57cb98a4c2fd66980e45a87b083`
- `v1/D02_STD_b0.jsonl`: `102f51e2ee69f79ec71ae90d2bcd285055dc1fd1d3abbb0d00283a2d99e31b7f`
- `v1/D03_STD_b0.jsonl`: `810cc9a0af777d13841ad44c02ce66906d544f4f176e0bc1084d0be9c6b410c6`
- `v1/D04_STD_b0.jsonl`: `ebf1270a2ca68a3487d3709d1eae1b8b991bbaf637b8033dfea694e4c82eebeb`
- `v1/D05_STD_b0.jsonl`: `515fb6d37cc81898f52d376a8716d8d0c4b9674368ef27be89c0bb05114a1af8`
- `v1/D06_STD_b0.jsonl`: `b3e0fb490d7ec4cd2dc28793dd549afd39d81c9ed5e71d91632d53fac5bc82fa`
- `v1/D07a_STD_b0.jsonl`: `9483c5d4e3229671668d7a8825d0644550cecc2975cd8aefe937068cff17faa8`
- `v1/D07b_STD_b0.jsonl`: `795a93db2972c72ddbc8e4f5e1ef2bd1f676a5edce0fd23113627550798ca2e8`
- `v1/D08_STD_b0.jsonl`: `b6b658d131eeae7adaa08ad01a0a4c92093635f99fedfb5b1ae7aed6ef6723ef`
- `v1/D09a_STD_b0.jsonl`: `39123b80b0f707c19ca777c14cb350e38517ea4c2baa85440951459271aa72a4`
- `v1/D09b_STD_b0.jsonl`: `3521f3ffd2cf3fd33b762ebee331b2075863591124842b394d18938e17f92876`
- `v2/D11_STD_b0.jsonl`: `dc2ae709c4c1e7b0edd676eab3274fb6c4e10940c55d425a63cd51fbaad4c071`
- `v1/P1_STD_b0.jsonl`: `45ffae234c04b37fefb001e783271c7432d30a889a4cb1538ae0e512445ff35d`
- `v1/P2_STD_b0.jsonl`: `26ef11e6beb4f25e9ff7a9a1ede46b57981a623aee697e9adb5047fea6dd678b`
- `v1/P3_STD_b0.jsonl`: `9d13421bcc69c44729897a3c2f174b500da71ff6b5fca4205debcddacd4e8782`
- `v1/P4_STD_b0.jsonl`: `190c207fad92f223cb399504fcfb92c3e13595faeb2d82a520cc6ff48f70ba7e`
- `v1/D01_LONG_b0.jsonl`: `cb45a4673d54acc36b1f8860166d0458aad62095a345c0fcc0823f6df7d5d55d`
- `v1/D02_LONG_b0.jsonl`: `ec53afca44b7e3215e00af96f6682a3db347083f37ba7acc7f732d807c35e476`
- `v2/D01h_STD_b0.jsonl`: `8a3861c971a9b917f3bb1419aa8502d66f5426de775bc48a7a04f18f4ad76a7a`
- `v2/D02h_STD_b0.jsonl`: `51cf7794e841223da28ffc2f9a9aa2caae1136866db13bd63bb70df107e78892`
- `v2/D03h_STD_b0.jsonl`: `0aaf82ebb701e355753eb5602eda3ba310df5252c401be4853cfa68265b2006b`
- `v2/D04h_STD_b0.jsonl`: `033971e6ccb92787496ea7fe4a0c10090b2410d129517e65bb3f9fd34b895b97`
- `v2/D05h_STD_b0.jsonl`: `e47b345c2f616b831596fb79228c3c2cb0de475e70de70102b4b5a27cdd61c45`
- `v2/D06h_STD_b0.jsonl`: `b0f6f28733aec5c532a5be773f978d96da4664aee4ccf081cb2db50c83ce971f`
- `v2/D07ah_STD_b0.jsonl`: `ba37639ac9a84bbf33d1f3c3de3396f679f5bf7f180484b3ef888d29432e63c4`
- `v2/D07bh_STD_b0.jsonl`: `8cac488891b0ac617c3adad0b2aa0dad608633ac542c96c90b5e363afd32a937`
- `v2/D08h_STD_b0.jsonl`: `9082cb746b8722246a6615e255118347f9794adc4bf5de491bb11000b96b7fcc`
- `v2/D01_HB_b0.jsonl`: `9dc7e0a99c706b7d976f7ccfcae78d15baef456014cfa1bd94ec4b7e1f358eb6`
- `v2/D02_HB_b0.jsonl`: `371a7ef4ee199c4d3c47a2947f9ddddd999aa51a5e085d7ad6bec279451f062d`
- `v2/D05_HB_b0.jsonl`: `88ab93e6a10a7c3d8149fe0b69c75341fe45ba162a3d7e05b005befd56f492a0`
- `v2/D08_HB_b0.jsonl`: `82352fc0988d2886b3dffb9eaa8079ba89623b7f81b227e1459ba9dc7325c738`
- `v2/D10_HB_b0.jsonl`: `fe69d501ddfba897d50e391b011b6dae4a4006a93dd0d5334656e91feecc8714`
