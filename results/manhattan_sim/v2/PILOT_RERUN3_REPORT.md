# Manhattan simulation, the parts changed by Protocol v3.1: PILOT report (nothing here is decided)

Written 2026-11-13 15:50 UTC by `python -m manhattan.sim.report_v2`. **Synthetic data only: nothing in this file is market evidence.**

- Pre-registration, version 2 (the changed parts): `docs/manhattan/SIM_PREREG_v2.md`, SHA-256 `65c19e68f673e2eb3254e3d4e226ec90e187976645735ea1bde27babfb6cebbf`.
- Pre-registration, version 1 (everything else, and the seeds): `docs/manhattan/SIM_PREREG.md`, SHA-256 `e4bbcc44bebbc601b8bccc0e609131ad5185982f3047108dfaaf2fe2908c21e6` (never edited).
- Method under test here: `docs/manhattan/PROTOCOL_v3.1.md` 3.1.0, SHA-256 `c4ce79d25bf1503981ce72071fcb257fe3f268761341fe256db1bf174dfc78a1`. Both v2 files are drafts until Ethan adopts them.
- Development scenarios only (seed branch 0). Held-out scenarios run: **none**.
- **Some runs below were made under an earlier draft of the version 2 files** (hashes `677073309c09` / `40ad6532b292`; `77496b2f4cb7` / `9fdc8b07838c`; `db9804905522` / `4d7b1063acd6`): the text changed after them. Their replication records carry the hash of the code that made them, and only records of the code now checked out are counted.
- **This is a pilot.** Replication counts are below those pre-registered, so every verdict below reads "pilot: not decided". "within" or "outside" only says where the interval sits so far. No method is selected, no claim is enabled, and `claims.enabled` stays false.

## Runs and shortfall

| scenario | size | what | replications run | pre-registered | shortfall | code | seconds per replication |
|---|---|---|---|---|---|---|---|
| D11 | STD | full pipeline, hedge-aware SPA | 36 | 2000 | 1964 | `9d1b680ff7e19ca7` | 374 |
| D01h | STD | three SPA tests only | 6 | 400 | 394 | `9d1b680ff7e19ca7` | 290 |
| D02h | STD | three SPA tests only | 6 | 400 | 394 | `9d1b680ff7e19ca7` | 260 |
| D03h | STD | three SPA tests only | 6 | 400 | 394 | `9d1b680ff7e19ca7` | 304 |
| D04h | STD | three SPA tests only | 6 | 400 | 394 | `9d1b680ff7e19ca7` | 207 |
| D05h | STD | three SPA tests only | 6 | 400 | 394 | `9d1b680ff7e19ca7` | 291 |
| D06h | STD | three SPA tests only | 6 | 400 | 394 | `9d1b680ff7e19ca7` | 251 |
| D07ah | STD | three SPA tests only | 6 | 400 | 394 | `9d1b680ff7e19ca7` | 305 |
| D07bh | STD | three SPA tests only | 6 | 400 | 394 | `9d1b680ff7e19ca7` | 246 |
| D08h | STD | three SPA tests only | 6 | 400 | 394 | `9d1b680ff7e19ca7` | 599 |
| D01 | HB | analytic model, tiers, dormancy | 12 | 400 | 388 | `4252b971831004e3` | 653 |
| D02 | HB | analytic model, tiers, dormancy | 12 | 400 | 388 | `4252b971831004e3` | 721 |
| D05 | HB | analytic model, tiers, dormancy | 12 | 400 | 388 | `4252b971831004e3` | 860 |
| D08 | HB | analytic model, tiers, dormancy | 12 | 400 | 388 | `4252b971831004e3` | 1489 |
| D10 | HB | analytic model, tiers, dormancy | 12 | 400 | 388 | `4252b971831004e3` | 993 |

152 replication records on file were made by earlier code (the model, then the dormancy rule, then the review dates changed while the draft was revised) and are **not counted** anywhere in this report: records of different code, or of another review calendar, are never pooled.

## 1. The SPA test where the hedge is estimated

Share of families with no edge rejected at the 0.05 level (the bound on the upper end is 0.06), by three tests on the **same** resamples: the 3.0 test on the hedged returns as given, the 3.1 test that re-estimates the hedge in every resample, and the 3.0 test on the true hedged returns, which no real analysis has. The last column is version 1's own run of the scenario on file (for D11: the 3.0 test on the estimated hedge; for a twin: its version 1 scenario, whose returns need no hedge).

| scenario | replications | 3.0 test, estimated hedge | **3.1 test, hedge re-estimated** | oracle | 3.1 minus oracle (paired) | version 1 run on file |
|---|---|---|---|---|---|---|
| D11 | 36 | 0.0728 (0.0627 to 0.0829) | **0.0468 (0.0399 to 0.0538)** | 0.0539 (0.0458 to 0.0619) | -0.0071 (-0.0100 to -0.0041) | 0.0774 (0.0611 to 0.0937), 12 replications |
| D01h | 6 | 0.1130 (0.0701 to 0.1558) | **0.0619 (0.0416 to 0.0822)** | 0.0668 (0.0461 to 0.0875) | -0.0049 (-0.0119 to 0.0021) | 0.0616 (0.0425 to 0.0808), 12 replications |
| D02h | 6 | 0.0608 (0.0462 to 0.0755) | **0.0400 (0.0252 to 0.0549)** | 0.0451 (0.0236 to 0.0665) | -0.0050 (-0.0127 to 0.0026) | 0.0456 (0.0322 to 0.0589), 12 replications |
| D03h | 6 | 0.0728 (0.0568 to 0.0889) | **0.0472 (0.0366 to 0.0577)** | 0.0518 (0.0376 to 0.0660) | -0.0047 (-0.0131 to 0.0038) | 0.0504 (0.0411 to 0.0598), 12 replications |
| D04h | 6 | 0.0368 (0.0024 to 0.0712) | **0.0249 (-0.0042 to 0.0539)** | 0.0338 (-0.0020 to 0.0697) | -0.0090 (-0.0163 to -0.0017) | 0.0362 (0.0080 to 0.0643), 12 replications |
| D05h | 6 | 0.0646 (0.0333 to 0.0960) | **0.0417 (0.0259 to 0.0574)** | 0.0500 (0.0289 to 0.0710) | -0.0083 (-0.0175 to 0.0009) | 0.0495 (0.0380 to 0.0609), 12 replications |
| D06h | 6 | 0.0548 (0.0406 to 0.0690) | **0.0271 (0.0221 to 0.0322)** | 0.0337 (0.0260 to 0.0415) | -0.0066 (-0.0143 to 0.0010) | 0.0391 (0.0280 to 0.0503), 12 replications |
| D07ah | 6 | 0.0892 (0.0485 to 0.1299) | **0.0539 (0.0278 to 0.0801)** | 0.0573 (0.0354 to 0.0792) | -0.0034 (-0.0133 to 0.0066) | 0.0595 (0.0435 to 0.0755), 12 replications |
| D07bh | 6 | 0.0635 (0.0433 to 0.0836) | **0.0335 (0.0258 to 0.0411)** | 0.0416 (0.0318 to 0.0515) | -0.0082 (-0.0125 to -0.0039) | 0.0510 (0.0360 to 0.0660), 12 replications |
| D08h | 6 | 0.0909 (0.0627 to 0.1192) | **0.0495 (0.0344 to 0.0646)** | 0.0599 (0.0411 to 0.0787) | -0.0104 (-0.0183 to -0.0025) | 0.0486 (0.0345 to 0.0627), 12 replications |

### D11 at STD: hedge estimation (36 of 2000 replications)

The three SPA tests side by side:

| metric | what | estimate | 95% interval | n | threshold | required here | verdict |
|---|---|---|---|---|---|---|---|
| M3 | hedge-aware test (3.1): SPA size at 0.2 | 0.1963 | 0.1768 to 0.2158 | 36 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M3 | hedge-aware test (3.1): SPA size at 0.05 | 0.0468 | 0.0399 to 0.0538 | 36 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M3 | hedge-aware test (3.1): SPA size at 0.001 (pooled) | 0.0010 | 0.0004 to 0.0016 | 16162 | upper bound ≤ 0.0015 | yes | pilot: not decided (outside threshold so far) |
| M3 | hedge-aware test (3.1): Romano-Wolf FWER at 0.05 | 0.0468 | 0.0398 to 0.0537 | 36 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M3 | hedge-aware test (3.1): SPA size at 0.05, lower p-value | 0.0517 | 0.0443 to 0.0591 | 36 | - | no | reported |
| M3 | hedge-aware test (3.1): SPA size at 0.05, upper p-value | 0.0468 | 0.0399 to 0.0538 | 36 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.2 | 0.2548 | 0.2316 to 0.2779 | 36 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.05 | 0.0728 | 0.0627 to 0.0829 | 36 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.001 (pooled) | 0.0029 | 0.0019 to 0.0039 | 16162 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: Romano-Wolf FWER at 0.05 | 0.0722 | 0.0621 to 0.0822 | 36 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.05, lower p-value | 0.0810 | 0.0702 to 0.0917 | 36 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.05, upper p-value | 0.0727 | 0.0627 to 0.0828 | 36 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.2 | 0.2077 | 0.1867 to 0.2287 | 36 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.05 | 0.0539 | 0.0458 to 0.0619 | 36 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.001 (pooled) | 0.0017 | 0.0011 to 0.0023 | 16162 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): Romano-Wolf FWER at 0.05 | 0.0536 | 0.0457 to 0.0616 | 36 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.05, lower p-value | 0.0590 | 0.0506 to 0.0673 | 36 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.05, upper p-value | 0.0539 | 0.0458 to 0.0619 | 36 | - | no | reported |
| M3 | paired difference at 0.2: hedge-aware test (3.1) minus the oracle | -0.0114 | -0.0170 to -0.0058 | 36 | - | no | reported |
| M3 | paired difference at 0.2: 3.0 test on the estimated hedge minus the oracle | 0.0470 | 0.0361 to 0.0580 | 36 | - | no | reported |
| M3 | paired difference at 0.2: hedge-aware test minus the 3.0 test on the estimated hedge | -0.0585 | -0.0674 to -0.0495 | 36 | - | no | reported |
| M3 | paired difference at 0.05: hedge-aware test (3.1) minus the oracle | -0.0071 | -0.0100 to -0.0041 | 36 | - | no | reported |
| M3 | paired difference at 0.05: 3.0 test on the estimated hedge minus the oracle | 0.0189 | 0.0128 to 0.0250 | 36 | - | no | reported |
| M3 | paired difference at 0.05: hedge-aware test minus the 3.0 test on the estimated hedge | -0.0260 | -0.0309 to -0.0210 | 36 | - | no | reported |
| cost | seconds per replication | 373.9217 | - | 36 | - | no | reported |
| cost | mean bootstrap resamples per family, hedge-aware test (3.1) | 2111.8546 | - | 36 | - | no | reported |
| cost | mean bootstrap resamples per family, 3.0 test on the estimated hedge | 2476.0772 | - | 36 | - | no | reported |
| cost | mean bootstrap resamples per family, 3.0 test on the true hedged returns (oracle) | 2225.3005 | - | 36 | - | no | reported |
| info | families per replication | 473.5000 | - | 36 | - | no | reported |

Every metric of the pipeline, with the hedge-aware p-values as the p-values of record:

| metric | what | estimate | 95% interval | n | threshold | required here | verdict |
|---|---|---|---|---|---|---|---|
| M1 | screening FDR, candidate (i), batch 10 | 0.0231 | -0.0091 to 0.0554 | 36 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (i), batch 20 | 0.0542 | -0.0075 to 0.1158 | 36 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (i), batch 40 | 0.0477 | 0.0109 to 0.0846 | 36 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 10 | 0.0000 | 0.0000 to 0.0000 | 36 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 20 | 0.0000 | 0.0000 to 0.0000 | 36 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M1 | screening FDR, candidate (ii), batch 40 | 0.0000 | 0.0000 to 0.0000 | 36 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 3 | 0.0000 | 0.0000 to 0.0000 | 36 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 5 | 0.0000 | 0.0000 to 0.0000 | 36 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (i), year 10 | 0.0000 | 0.0000 to 0.0000 | 36 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 3 | 0.0000 | 0.0000 to 0.0000 | 36 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 5 | 0.0000 | 0.0000 to 0.0000 | 36 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M2 | forward FDR, enrolment by candidate (ii), year 10 | 0.0000 | 0.0000 to 0.0000 | 36 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M3 | SPA size at 0.2 | 0.1963 | 0.1768 to 0.2158 | 36 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M3 | SPA size at 0.05 | 0.0468 | 0.0399 to 0.0538 | 36 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M3 | SPA size at 0.001 (pooled) | 0.0010 | 0.0004 to 0.0016 | 16162 | upper bound ≤ 0.0015 | yes | pilot: not decided (outside threshold so far) |
| M3 | Romano-Wolf FWER at 0.05 | 0.0468 | 0.0398 to 0.0537 | 36 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M3 | SPA size at 0.05, lower p-value (reported) | 0.0517 | 0.0443 to 0.0591 | 36 | - | no | reported |
| M3 | SPA size at 0.05, upper p-value (reported) | 0.0468 | 0.0399 to 0.0538 | 36 | - | no | reported |
| M4 | linked average error, candidate (i) (140 families passed) | 0.0477 | 0.0109 to 0.0846 | 36 | upper bound ≤ 0.22 | yes | not evaluated: fewer than 200 observations |
| M4 | linked average error, candidate (ii) (16 families passed) | 0.0000 | 0.0000 to 0.0000 | 36 | upper bound ≤ 0.22 | yes | not evaluated: fewer than 200 observations |
| M5 | null component wealth ever reaches 20 | 0.0071 | 0.0055 to 0.0086 | 36 | upper bound ≤ 0.06 | no | pilot: not decided (within threshold so far) |
| M5 | null component wealth ever reaches 100 | 0.0008 | 0.0004 to 0.0012 | 36 | upper bound ≤ 0.015 | no | pilot: not decided (within threshold so far) |
| M6 | screening power, candidate (i) | 0.1482 | 0.1203 to 0.1767 | 884 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | screening power, candidate (ii) | 0.0181 | 0.0078 to 0.0308 | 884 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | forward power by the end (first-quarter families), enrolment by candidate (i) | 0.0341 | 0.0100 to 0.0625 | 205 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | median years from freeze to formal support, enrolment by candidate (i) | 7.5400 | - | 7 | - | no | reported |
| M6 | forward power by the end (first-quarter families), enrolment by candidate (ii) | 0.0000 | 0.0000 to 0.0000 | 205 | lower bound ≥ 0.5 | no | pilot: not decided (outside threshold so far) |
| M6 | median years from freeze to formal support, enrolment by candidate (ii) | - | - | 0 | - | no | reported |
| cost | seconds per replication | 373.9217 | - | 36 | - | no | reported |
| cost | mean bootstrap resamples per family | 2111.8546 | - | 36 | - | no | reported |
| info | share of weeks with a bet (variance-ratio rule) | 0.9688 | - | 36 | - | no | reported |
| info | families per replication | 473.5000 | - | 36 | - | no | reported |
| info | families enrolled, E-ALL / (i) / (ii) | - | - | 36 | - | no | - / 3.9 / 0.4 |

### D01h at STD: no edges, with an estimated core hedge (6 of 400 replications)

| metric | what | estimate | 95% interval | n | threshold | required here | verdict |
|---|---|---|---|---|---|---|---|
| M3 | hedge-aware test (3.1): SPA size at 0.2 | 0.2420 | 0.1906 to 0.2933 | 6 | upper bound ≤ 0.22 | yes | pilot: not decided (outside threshold so far) |
| M3 | hedge-aware test (3.1): SPA size at 0.05 | 0.0619 | 0.0416 to 0.0822 | 6 | upper bound ≤ 0.06 | yes | pilot: not decided (outside threshold so far) |
| M3 | hedge-aware test (3.1): SPA size at 0.001 (pooled) | 0.0007 | 0.0000 to 0.0014 | 2868 | upper bound ≤ 0.0015 | yes | pilot: not decided (within threshold so far) |
| M3 | hedge-aware test (3.1): Romano-Wolf FWER at 0.05 | 0.0616 | 0.0417 to 0.0814 | 6 | upper bound ≤ 0.06 | yes | pilot: not decided (outside threshold so far) |
| M3 | hedge-aware test (3.1): SPA size at 0.05, lower p-value | 0.0685 | 0.0492 to 0.0878 | 6 | - | no | reported |
| M3 | hedge-aware test (3.1): SPA size at 0.05, upper p-value | 0.0616 | 0.0417 to 0.0814 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.2 | 0.3258 | 0.2507 to 0.4008 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.05 | 0.1130 | 0.0701 to 0.1558 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.001 (pooled) | 0.0038 | 0.0007 to 0.0082 | 2868 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: Romano-Wolf FWER at 0.05 | 0.1130 | 0.0701 to 0.1558 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.05, lower p-value | 0.1237 | 0.0787 to 0.1687 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.05, upper p-value | 0.1130 | 0.0701 to 0.1558 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.2 | 0.2539 | 0.2079 to 0.2998 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.05 | 0.0668 | 0.0461 to 0.0875 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.001 (pooled) | 0.0014 | 0.0000 to 0.0028 | 2868 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): Romano-Wolf FWER at 0.05 | 0.0668 | 0.0461 to 0.0875 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.05, lower p-value | 0.0720 | 0.0494 to 0.0945 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.05, upper p-value | 0.0668 | 0.0461 to 0.0875 | 6 | - | no | reported |
| M3 | paired difference at 0.2: hedge-aware test (3.1) minus the oracle | -0.0119 | -0.0277 to 0.0039 | 6 | - | no | reported |
| M3 | paired difference at 0.2: 3.0 test on the estimated hedge minus the oracle | 0.0719 | 0.0286 to 0.1152 | 6 | - | no | reported |
| M3 | paired difference at 0.2: hedge-aware test minus the 3.0 test on the estimated hedge | -0.0838 | -0.1159 to -0.0516 | 6 | - | no | reported |
| M3 | paired difference at 0.05: hedge-aware test (3.1) minus the oracle | -0.0049 | -0.0119 to 0.0021 | 6 | - | no | reported |
| M3 | paired difference at 0.05: 3.0 test on the estimated hedge minus the oracle | 0.0462 | 0.0159 to 0.0764 | 6 | - | no | reported |
| M3 | paired difference at 0.05: hedge-aware test minus the 3.0 test on the estimated hedge | -0.0511 | -0.0775 to -0.0247 | 6 | - | no | reported |
| precision | 95% half-width of the hedge-aware size at 0.2 | 0.0513 | - | 6 | at most 0.02 (SIM_PREREG_v2 section 6) | no | pilot |
| precision | 95% half-width of the hedge-aware size at 0.05 | 0.0203 | - | 6 | at most 0.01 (SIM_PREREG_v2 section 6) | no | pilot |
| cost | seconds per replication | 290.4317 | - | 6 | - | no | reported |
| cost | mean bootstrap resamples per family, hedge-aware test (3.1) | 2079.3757 | - | 6 | - | no | reported |
| cost | mean bootstrap resamples per family, 3.0 test on the estimated hedge | 2696.3095 | - | 6 | - | no | reported |
| cost | mean bootstrap resamples per family, 3.0 test on the true hedged returns (oracle) | 2162.3604 | - | 6 | - | no | reported |
| info | families per replication | 478.0000 | - | 6 | - | no | reported |

### D02h at STD: rare edges, with an estimated core hedge (6 of 400 replications)

| metric | what | estimate | 95% interval | n | threshold | required here | verdict |
|---|---|---|---|---|---|---|---|
| M3 | hedge-aware test (3.1): SPA size at 0.2 | 0.1684 | 0.1326 to 0.2043 | 6 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M3 | hedge-aware test (3.1): SPA size at 0.05 | 0.0400 | 0.0252 to 0.0549 | 6 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M3 | hedge-aware test (3.1): SPA size at 0.001 (pooled) | 0.0004 | 0.0000 to 0.0011 | 2829 | upper bound ≤ 0.0015 | yes | pilot: not decided (within threshold so far) |
| M3 | hedge-aware test (3.1): Romano-Wolf FWER at 0.05 | 0.0396 | 0.0250 to 0.0543 | 6 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M3 | hedge-aware test (3.1): SPA size at 0.05, lower p-value | 0.0450 | 0.0295 to 0.0605 | 6 | - | no | reported |
| M3 | hedge-aware test (3.1): SPA size at 0.05, upper p-value | 0.0400 | 0.0252 to 0.0549 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.2 | 0.2132 | 0.1771 to 0.2493 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.05 | 0.0608 | 0.0462 to 0.0755 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.001 (pooled) | 0.0011 | 0.0000 to 0.0025 | 2829 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: Romano-Wolf FWER at 0.05 | 0.0605 | 0.0465 to 0.0746 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.05, lower p-value | 0.0661 | 0.0518 to 0.0804 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.05, upper p-value | 0.0608 | 0.0462 to 0.0755 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.2 | 0.1798 | 0.1318 to 0.2279 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.05 | 0.0451 | 0.0236 to 0.0665 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.001 (pooled) | 0.0011 | 0.0004 to 0.0018 | 2829 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): Romano-Wolf FWER at 0.05 | 0.0446 | 0.0234 to 0.0658 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.05, lower p-value | 0.0503 | 0.0290 to 0.0716 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.05, upper p-value | 0.0451 | 0.0236 to 0.0665 | 6 | - | no | reported |
| M3 | paired difference at 0.2: hedge-aware test (3.1) minus the oracle | -0.0114 | -0.0247 to 0.0019 | 6 | - | no | reported |
| M3 | paired difference at 0.2: 3.0 test on the estimated hedge minus the oracle | 0.0334 | 0.0173 to 0.0494 | 6 | - | no | reported |
| M3 | paired difference at 0.2: hedge-aware test minus the 3.0 test on the estimated hedge | -0.0448 | -0.0517 to -0.0378 | 6 | - | no | reported |
| M3 | paired difference at 0.05: hedge-aware test (3.1) minus the oracle | -0.0050 | -0.0127 to 0.0026 | 6 | - | no | reported |
| M3 | paired difference at 0.05: 3.0 test on the estimated hedge minus the oracle | 0.0158 | 0.0059 to 0.0256 | 6 | - | no | reported |
| M3 | paired difference at 0.05: hedge-aware test minus the 3.0 test on the estimated hedge | -0.0208 | -0.0244 to -0.0172 | 6 | - | no | reported |
| precision | 95% half-width of the hedge-aware size at 0.2 | 0.0358 | - | 6 | at most 0.02 (SIM_PREREG_v2 section 6) | no | pilot |
| precision | 95% half-width of the hedge-aware size at 0.05 | 0.0149 | - | 6 | at most 0.01 (SIM_PREREG_v2 section 6) | no | pilot |
| cost | seconds per replication | 259.8650 | - | 6 | - | no | reported |
| cost | mean bootstrap resamples per family, hedge-aware test (3.1) | 1841.2273 | - | 6 | - | no | reported |
| cost | mean bootstrap resamples per family, 3.0 test on the estimated hedge | 2138.8092 | - | 6 | - | no | reported |
| cost | mean bootstrap resamples per family, 3.0 test on the true hedged returns (oracle) | 1972.7685 | - | 6 | - | no | reported |
| info | families per replication | 481.5000 | - | 6 | - | no | reported |

### D03h at STD: correlated variants, with an estimated core hedge (6 of 400 replications)

| metric | what | estimate | 95% interval | n | threshold | required here | verdict |
|---|---|---|---|---|---|---|---|
| M3 | hedge-aware test (3.1): SPA size at 0.2 | 0.2022 | 0.1706 to 0.2338 | 6 | upper bound ≤ 0.22 | yes | pilot: not decided (outside threshold so far) |
| M3 | hedge-aware test (3.1): SPA size at 0.05 | 0.0472 | 0.0366 to 0.0577 | 6 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M3 | hedge-aware test (3.1): SPA size at 0.001 (pooled) | 0.0007 | 0.0000 to 0.0022 | 2726 | upper bound ≤ 0.0015 | yes | pilot: not decided (outside threshold so far) |
| M3 | hedge-aware test (3.1): Romano-Wolf FWER at 0.05 | 0.0458 | 0.0357 to 0.0559 | 6 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M3 | hedge-aware test (3.1): SPA size at 0.05, lower p-value | 0.0545 | 0.0445 to 0.0645 | 6 | - | no | reported |
| M3 | hedge-aware test (3.1): SPA size at 0.05, upper p-value | 0.0468 | 0.0368 to 0.0568 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.2 | 0.2480 | 0.2092 to 0.2868 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.05 | 0.0728 | 0.0568 to 0.0889 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.001 (pooled) | 0.0022 | 0.0000 to 0.0058 | 2726 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: Romano-Wolf FWER at 0.05 | 0.0714 | 0.0554 to 0.0873 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.05, lower p-value | 0.0857 | 0.0664 to 0.1050 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.05, upper p-value | 0.0725 | 0.0568 to 0.0881 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.2 | 0.2072 | 0.1715 to 0.2430 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.05 | 0.0518 | 0.0376 to 0.0660 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.001 (pooled) | 0.0015 | 0.0004 to 0.0029 | 2726 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): Romano-Wolf FWER at 0.05 | 0.0510 | 0.0366 to 0.0654 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.05, lower p-value | 0.0573 | 0.0437 to 0.0710 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.05, upper p-value | 0.0518 | 0.0376 to 0.0660 | 6 | - | no | reported |
| M3 | paired difference at 0.2: hedge-aware test (3.1) minus the oracle | -0.0050 | -0.0163 to 0.0063 | 6 | - | no | reported |
| M3 | paired difference at 0.2: 3.0 test on the estimated hedge minus the oracle | 0.0407 | 0.0218 to 0.0596 | 6 | - | no | reported |
| M3 | paired difference at 0.2: hedge-aware test minus the 3.0 test on the estimated hedge | -0.0458 | -0.0599 to -0.0316 | 6 | - | no | reported |
| M3 | paired difference at 0.05: hedge-aware test (3.1) minus the oracle | -0.0047 | -0.0131 to 0.0038 | 6 | - | no | reported |
| M3 | paired difference at 0.05: 3.0 test on the estimated hedge minus the oracle | 0.0210 | 0.0111 to 0.0309 | 6 | - | no | reported |
| M3 | paired difference at 0.05: hedge-aware test minus the 3.0 test on the estimated hedge | -0.0257 | -0.0364 to -0.0149 | 6 | - | no | reported |
| precision | 95% half-width of the hedge-aware size at 0.2 | 0.0316 | - | 6 | at most 0.02 (SIM_PREREG_v2 section 6) | no | pilot |
| precision | 95% half-width of the hedge-aware size at 0.05 | 0.0105 | - | 6 | at most 0.01 (SIM_PREREG_v2 section 6) | no | pilot |
| cost | seconds per replication | 304.0750 | - | 6 | - | no | reported |
| cost | mean bootstrap resamples per family, hedge-aware test (3.1) | 2168.6944 | - | 6 | - | no | reported |
| cost | mean bootstrap resamples per family, 3.0 test on the estimated hedge | 2476.3239 | - | 6 | - | no | reported |
| cost | mean bootstrap resamples per family, 3.0 test on the true hedged returns (oracle) | 2227.0708 | - | 6 | - | no | reported |
| info | families per replication | 481.0000 | - | 6 | - | no | reported |

### D04h at STD: correlated families, with an estimated core hedge (6 of 400 replications)

| metric | what | estimate | 95% interval | n | threshold | required here | verdict |
|---|---|---|---|---|---|---|---|
| M3 | hedge-aware test (3.1): SPA size at 0.2 | 0.1043 | 0.0315 to 0.1772 | 6 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M3 | hedge-aware test (3.1): SPA size at 0.05 | 0.0249 | -0.0042 to 0.0539 | 6 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M3 | hedge-aware test (3.1): SPA size at 0.001 (pooled) | 0.0011 | 0.0000 to 0.0034 | 2733 | upper bound ≤ 0.0015 | yes | pilot: not decided (outside threshold so far) |
| M3 | hedge-aware test (3.1): Romano-Wolf FWER at 0.05 | 0.0257 | -0.0040 to 0.0553 | 6 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M3 | hedge-aware test (3.1): SPA size at 0.05, lower p-value | 0.0260 | -0.0037 to 0.0557 | 6 | - | no | reported |
| M3 | hedge-aware test (3.1): SPA size at 0.05, upper p-value | 0.0249 | -0.0042 to 0.0539 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.2 | 0.1374 | 0.0591 to 0.2157 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.05 | 0.0368 | 0.0024 to 0.0712 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.001 (pooled) | 0.0018 | 0.0000 to 0.0057 | 2733 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: Romano-Wolf FWER at 0.05 | 0.0380 | 0.0026 to 0.0734 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.05, lower p-value | 0.0386 | 0.0042 to 0.0730 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.05, upper p-value | 0.0368 | 0.0024 to 0.0712 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.2 | 0.1112 | 0.0373 to 0.1851 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.05 | 0.0338 | -0.0020 to 0.0697 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.001 (pooled) | 0.0022 | 0.0000 to 0.0068 | 2733 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): Romano-Wolf FWER at 0.05 | 0.0351 | -0.0017 to 0.0720 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.05, lower p-value | 0.0342 | -0.0016 to 0.0699 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.05, upper p-value | 0.0338 | -0.0020 to 0.0697 | 6 | - | no | reported |
| M3 | paired difference at 0.2: hedge-aware test (3.1) minus the oracle | -0.0068 | -0.0157 to 0.0020 | 6 | - | no | reported |
| M3 | paired difference at 0.2: 3.0 test on the estimated hedge minus the oracle | 0.0262 | 0.0103 to 0.0421 | 6 | - | no | reported |
| M3 | paired difference at 0.2: hedge-aware test minus the 3.0 test on the estimated hedge | -0.0330 | -0.0430 to -0.0230 | 6 | - | no | reported |
| M3 | paired difference at 0.05: hedge-aware test (3.1) minus the oracle | -0.0090 | -0.0163 to -0.0017 | 6 | - | no | reported |
| M3 | paired difference at 0.05: 3.0 test on the estimated hedge minus the oracle | 0.0029 | -0.0016 to 0.0075 | 6 | - | no | reported |
| M3 | paired difference at 0.05: hedge-aware test minus the 3.0 test on the estimated hedge | -0.0119 | -0.0183 to -0.0055 | 6 | - | no | reported |
| precision | 95% half-width of the hedge-aware size at 0.2 | 0.0729 | - | 6 | at most 0.02 (SIM_PREREG_v2 section 6) | no | pilot |
| precision | 95% half-width of the hedge-aware size at 0.05 | 0.0291 | - | 6 | at most 0.01 (SIM_PREREG_v2 section 6) | no | pilot |
| cost | seconds per replication | 206.7217 | - | 6 | - | no | reported |
| cost | mean bootstrap resamples per family, hedge-aware test (3.1) | 1615.0631 | - | 6 | - | no | reported |
| cost | mean bootstrap resamples per family, 3.0 test on the estimated hedge | 1832.7938 | - | 6 | - | no | reported |
| cost | mean bootstrap resamples per family, 3.0 test on the true hedged returns (oracle) | 1730.5688 | - | 6 | - | no | reported |
| info | families per replication | 479.5000 | - | 6 | - | no | reported |

### D05h at STD: fat tails, with an estimated core hedge (6 of 400 replications)

| metric | what | estimate | 95% interval | n | threshold | required here | verdict |
|---|---|---|---|---|---|---|---|
| M3 | hedge-aware test (3.1): SPA size at 0.2 | 0.1963 | 0.1472 to 0.2454 | 6 | upper bound ≤ 0.22 | yes | pilot: not decided (outside threshold so far) |
| M3 | hedge-aware test (3.1): SPA size at 0.05 | 0.0417 | 0.0259 to 0.0574 | 6 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M3 | hedge-aware test (3.1): SPA size at 0.001 (pooled) | 0.0014 | 0.0000 to 0.0036 | 2772 | upper bound ≤ 0.0015 | yes | pilot: not decided (outside threshold so far) |
| M3 | hedge-aware test (3.1): Romano-Wolf FWER at 0.05 | 0.0420 | 0.0256 to 0.0585 | 6 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M3 | hedge-aware test (3.1): SPA size at 0.05, lower p-value | 0.0467 | 0.0289 to 0.0645 | 6 | - | no | reported |
| M3 | hedge-aware test (3.1): SPA size at 0.05, upper p-value | 0.0417 | 0.0259 to 0.0574 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.2 | 0.2365 | 0.1684 to 0.3046 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.05 | 0.0646 | 0.0333 to 0.0960 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.001 (pooled) | 0.0025 | 0.0000 to 0.0054 | 2772 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: Romano-Wolf FWER at 0.05 | 0.0650 | 0.0331 to 0.0970 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.05, lower p-value | 0.0722 | 0.0388 to 0.1056 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.05, upper p-value | 0.0646 | 0.0333 to 0.0960 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.2 | 0.2114 | 0.1568 to 0.2659 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.05 | 0.0500 | 0.0289 to 0.0710 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.001 (pooled) | 0.0014 | 0.0000 to 0.0036 | 2772 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): Romano-Wolf FWER at 0.05 | 0.0501 | 0.0288 to 0.0715 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.05, lower p-value | 0.0547 | 0.0335 to 0.0759 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.05, upper p-value | 0.0500 | 0.0289 to 0.0710 | 6 | - | no | reported |
| M3 | paired difference at 0.2: hedge-aware test (3.1) minus the oracle | -0.0150 | -0.0240 to -0.0061 | 6 | - | no | reported |
| M3 | paired difference at 0.2: 3.0 test on the estimated hedge minus the oracle | 0.0251 | -0.0037 to 0.0539 | 6 | - | no | reported |
| M3 | paired difference at 0.2: hedge-aware test minus the 3.0 test on the estimated hedge | -0.0402 | -0.0670 to -0.0134 | 6 | - | no | reported |
| M3 | paired difference at 0.05: hedge-aware test (3.1) minus the oracle | -0.0083 | -0.0175 to 0.0009 | 6 | - | no | reported |
| M3 | paired difference at 0.05: 3.0 test on the estimated hedge minus the oracle | 0.0146 | -0.0075 to 0.0367 | 6 | - | no | reported |
| M3 | paired difference at 0.05: hedge-aware test minus the 3.0 test on the estimated hedge | -0.0229 | -0.0437 to -0.0021 | 6 | - | no | reported |
| precision | 95% half-width of the hedge-aware size at 0.2 | 0.0491 | - | 6 | at most 0.02 (SIM_PREREG_v2 section 6) | no | pilot |
| precision | 95% half-width of the hedge-aware size at 0.05 | 0.0157 | - | 6 | at most 0.01 (SIM_PREREG_v2 section 6) | no | pilot |
| cost | seconds per replication | 291.1750 | - | 6 | - | no | reported |
| cost | mean bootstrap resamples per family, hedge-aware test (3.1) | 2049.3839 | - | 6 | - | no | reported |
| cost | mean bootstrap resamples per family, 3.0 test on the estimated hedge | 2315.7807 | - | 6 | - | no | reported |
| cost | mean bootstrap resamples per family, 3.0 test on the true hedged returns (oracle) | 2167.0861 | - | 6 | - | no | reported |
| info | families per replication | 485.5000 | - | 6 | - | no | reported |

### D06h at STD: volatility clustering, with an estimated core hedge (6 of 400 replications)

| metric | what | estimate | 95% interval | n | threshold | required here | verdict |
|---|---|---|---|---|---|---|---|
| M3 | hedge-aware test (3.1): SPA size at 0.2 | 0.1589 | 0.1393 to 0.1786 | 6 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M3 | hedge-aware test (3.1): SPA size at 0.05 | 0.0271 | 0.0221 to 0.0322 | 6 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M3 | hedge-aware test (3.1): SPA size at 0.001 (pooled) | 0.0004 | 0.0000 to 0.0011 | 2767 | upper bound ≤ 0.0015 | yes | pilot: not decided (within threshold so far) |
| M3 | hedge-aware test (3.1): Romano-Wolf FWER at 0.05 | 0.0268 | 0.0219 to 0.0317 | 6 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M3 | hedge-aware test (3.1): SPA size at 0.05, lower p-value | 0.0315 | 0.0272 to 0.0357 | 6 | - | no | reported |
| M3 | hedge-aware test (3.1): SPA size at 0.05, upper p-value | 0.0271 | 0.0221 to 0.0322 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.2 | 0.2195 | 0.1861 to 0.2530 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.05 | 0.0548 | 0.0406 to 0.0690 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.001 (pooled) | 0.0007 | 0.0000 to 0.0022 | 2767 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: Romano-Wolf FWER at 0.05 | 0.0534 | 0.0389 to 0.0679 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.05, lower p-value | 0.0656 | 0.0489 to 0.0824 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.05, upper p-value | 0.0545 | 0.0402 to 0.0687 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.2 | 0.1668 | 0.1385 to 0.1950 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.05 | 0.0337 | 0.0260 to 0.0415 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.001 (pooled) | 0.0007 | 0.0000 to 0.0015 | 2767 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): Romano-Wolf FWER at 0.05 | 0.0328 | 0.0253 to 0.0404 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.05, lower p-value | 0.0380 | 0.0312 to 0.0448 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.05, upper p-value | 0.0337 | 0.0260 to 0.0415 | 6 | - | no | reported |
| M3 | paired difference at 0.2: hedge-aware test (3.1) minus the oracle | -0.0078 | -0.0260 to 0.0104 | 6 | - | no | reported |
| M3 | paired difference at 0.2: 3.0 test on the estimated hedge minus the oracle | 0.0527 | 0.0127 to 0.0928 | 6 | - | no | reported |
| M3 | paired difference at 0.2: hedge-aware test minus the 3.0 test on the estimated hedge | -0.0606 | -0.0838 to -0.0374 | 6 | - | no | reported |
| M3 | paired difference at 0.05: hedge-aware test (3.1) minus the oracle | -0.0066 | -0.0143 to 0.0010 | 6 | - | no | reported |
| M3 | paired difference at 0.05: 3.0 test on the estimated hedge minus the oracle | 0.0211 | 0.0019 to 0.0403 | 6 | - | no | reported |
| M3 | paired difference at 0.05: hedge-aware test minus the 3.0 test on the estimated hedge | -0.0277 | -0.0406 to -0.0148 | 6 | - | no | reported |
| precision | 95% half-width of the hedge-aware size at 0.2 | 0.0197 | - | 6 | at most 0.02 (SIM_PREREG_v2 section 6) | no | pilot |
| precision | 95% half-width of the hedge-aware size at 0.05 | 0.0051 | - | 6 | at most 0.01 (SIM_PREREG_v2 section 6) | no | pilot |
| cost | seconds per replication | 250.7600 | - | 6 | - | no | reported |
| cost | mean bootstrap resamples per family, hedge-aware test (3.1) | 1808.2377 | - | 6 | - | no | reported |
| cost | mean bootstrap resamples per family, 3.0 test on the estimated hedge | 2211.9793 | - | 6 | - | no | reported |
| cost | mean bootstrap resamples per family, 3.0 test on the true hedged returns (oracle) | 1923.2091 | - | 6 | - | no | reported |
| info | families per replication | 487.3333 | - | 6 | - | no | reported |

### D07ah at STD: serial correlation +0.2, with an estimated core hedge (6 of 400 replications)

| metric | what | estimate | 95% interval | n | threshold | required here | verdict |
|---|---|---|---|---|---|---|---|
| M3 | hedge-aware test (3.1): SPA size at 0.2 | 0.2158 | 0.1667 to 0.2648 | 6 | upper bound ≤ 0.22 | yes | pilot: not decided (outside threshold so far) |
| M3 | hedge-aware test (3.1): SPA size at 0.05 | 0.0539 | 0.0278 to 0.0801 | 6 | upper bound ≤ 0.06 | yes | pilot: not decided (outside threshold so far) |
| M3 | hedge-aware test (3.1): SPA size at 0.001 (pooled) | 0.0007 | 0.0000 to 0.0015 | 2727 | upper bound ≤ 0.0015 | yes | pilot: not decided (outside threshold so far) |
| M3 | hedge-aware test (3.1): Romano-Wolf FWER at 0.05 | 0.0533 | 0.0273 to 0.0793 | 6 | upper bound ≤ 0.06 | yes | pilot: not decided (outside threshold so far) |
| M3 | hedge-aware test (3.1): SPA size at 0.05, lower p-value | 0.0568 | 0.0316 to 0.0820 | 6 | - | no | reported |
| M3 | hedge-aware test (3.1): SPA size at 0.05, upper p-value | 0.0539 | 0.0278 to 0.0801 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.2 | 0.2800 | 0.2187 to 0.3413 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.05 | 0.0892 | 0.0485 to 0.1299 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.001 (pooled) | 0.0029 | 0.0011 to 0.0049 | 2727 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: Romano-Wolf FWER at 0.05 | 0.0884 | 0.0465 to 0.1303 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.05, lower p-value | 0.0989 | 0.0535 to 0.1444 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.05, upper p-value | 0.0881 | 0.0468 to 0.1293 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.2 | 0.2234 | 0.1698 to 0.2770 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.05 | 0.0573 | 0.0354 to 0.0792 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.001 (pooled) | 0.0007 | 0.0000 to 0.0022 | 2727 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): Romano-Wolf FWER at 0.05 | 0.0573 | 0.0352 to 0.0794 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.05, lower p-value | 0.0606 | 0.0400 to 0.0812 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.05, upper p-value | 0.0573 | 0.0354 to 0.0792 | 6 | - | no | reported |
| M3 | paired difference at 0.2: hedge-aware test (3.1) minus the oracle | -0.0076 | -0.0170 to 0.0018 | 6 | - | no | reported |
| M3 | paired difference at 0.2: 3.0 test on the estimated hedge minus the oracle | 0.0566 | 0.0348 to 0.0784 | 6 | - | no | reported |
| M3 | paired difference at 0.2: hedge-aware test minus the 3.0 test on the estimated hedge | -0.0643 | -0.0835 to -0.0451 | 6 | - | no | reported |
| M3 | paired difference at 0.05: hedge-aware test (3.1) minus the oracle | -0.0034 | -0.0133 to 0.0066 | 6 | - | no | reported |
| M3 | paired difference at 0.05: 3.0 test on the estimated hedge minus the oracle | 0.0319 | 0.0073 to 0.0564 | 6 | - | no | reported |
| M3 | paired difference at 0.05: hedge-aware test minus the 3.0 test on the estimated hedge | -0.0352 | -0.0522 to -0.0183 | 6 | - | no | reported |
| precision | 95% half-width of the hedge-aware size at 0.2 | 0.0490 | - | 6 | at most 0.02 (SIM_PREREG_v2 section 6) | no | pilot |
| precision | 95% half-width of the hedge-aware size at 0.05 | 0.0262 | - | 6 | at most 0.01 (SIM_PREREG_v2 section 6) | no | pilot |
| cost | seconds per replication | 304.9633 | - | 6 | - | no | reported |
| cost | mean bootstrap resamples per family, hedge-aware test (3.1) | 2232.6995 | - | 6 | - | no | reported |
| cost | mean bootstrap resamples per family, 3.0 test on the estimated hedge | 2646.5390 | - | 6 | - | no | reported |
| cost | mean bootstrap resamples per family, 3.0 test on the true hedged returns (oracle) | 2255.1269 | - | 6 | - | no | reported |
| info | families per replication | 478.3333 | - | 6 | - | no | reported |

### D07bh at STD: serial correlation -0.2, with an estimated core hedge (6 of 400 replications)

| metric | what | estimate | 95% interval | n | threshold | required here | verdict |
|---|---|---|---|---|---|---|---|
| M3 | hedge-aware test (3.1): SPA size at 0.2 | 0.1731 | 0.1444 to 0.2018 | 6 | upper bound ≤ 0.22 | yes | pilot: not decided (within threshold so far) |
| M3 | hedge-aware test (3.1): SPA size at 0.05 | 0.0335 | 0.0258 to 0.0411 | 6 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M3 | hedge-aware test (3.1): SPA size at 0.001 (pooled) | 0.0004 | 0.0000 to 0.0011 | 2710 | upper bound ≤ 0.0015 | yes | pilot: not decided (within threshold so far) |
| M3 | hedge-aware test (3.1): Romano-Wolf FWER at 0.05 | 0.0321 | 0.0242 to 0.0401 | 6 | upper bound ≤ 0.06 | yes | pilot: not decided (within threshold so far) |
| M3 | hedge-aware test (3.1): SPA size at 0.05, lower p-value | 0.0383 | 0.0320 to 0.0446 | 6 | - | no | reported |
| M3 | hedge-aware test (3.1): SPA size at 0.05, upper p-value | 0.0331 | 0.0249 to 0.0412 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.2 | 0.2395 | 0.1945 to 0.2845 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.05 | 0.0635 | 0.0433 to 0.0836 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.001 (pooled) | 0.0011 | 0.0000 to 0.0033 | 2710 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: Romano-Wolf FWER at 0.05 | 0.0613 | 0.0422 to 0.0803 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.05, lower p-value | 0.0709 | 0.0489 to 0.0928 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.05, upper p-value | 0.0627 | 0.0437 to 0.0818 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.2 | 0.1765 | 0.1530 to 0.2000 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.05 | 0.0416 | 0.0318 to 0.0515 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.001 (pooled) | 0.0000 | 0.0000 to 0.0000 | 2710 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): Romano-Wolf FWER at 0.05 | 0.0405 | 0.0308 to 0.0502 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.05, lower p-value | 0.0472 | 0.0379 to 0.0564 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.05, upper p-value | 0.0416 | 0.0318 to 0.0515 | 6 | - | no | reported |
| M3 | paired difference at 0.2: hedge-aware test (3.1) minus the oracle | -0.0034 | -0.0103 to 0.0035 | 6 | - | no | reported |
| M3 | paired difference at 0.2: 3.0 test on the estimated hedge minus the oracle | 0.0630 | 0.0384 to 0.0876 | 6 | - | no | reported |
| M3 | paired difference at 0.2: hedge-aware test minus the 3.0 test on the estimated hedge | -0.0664 | -0.0864 to -0.0464 | 6 | - | no | reported |
| M3 | paired difference at 0.05: hedge-aware test (3.1) minus the oracle | -0.0082 | -0.0125 to -0.0039 | 6 | - | no | reported |
| M3 | paired difference at 0.05: 3.0 test on the estimated hedge minus the oracle | 0.0218 | 0.0088 to 0.0348 | 6 | - | no | reported |
| M3 | paired difference at 0.05: hedge-aware test minus the 3.0 test on the estimated hedge | -0.0300 | -0.0431 to -0.0169 | 6 | - | no | reported |
| precision | 95% half-width of the hedge-aware size at 0.2 | 0.0287 | - | 6 | at most 0.02 (SIM_PREREG_v2 section 6) | no | pilot |
| precision | 95% half-width of the hedge-aware size at 0.05 | 0.0076 | - | 6 | at most 0.01 (SIM_PREREG_v2 section 6) | no | pilot |
| cost | seconds per replication | 245.7133 | - | 6 | - | no | reported |
| cost | mean bootstrap resamples per family, hedge-aware test (3.1) | 1899.8599 | - | 6 | - | no | reported |
| cost | mean bootstrap resamples per family, 3.0 test on the estimated hedge | 2359.1791 | - | 6 | - | no | reported |
| cost | mean bootstrap resamples per family, 3.0 test on the true hedged returns (oracle) | 2047.7031 | - | 6 | - | no | reported |
| info | families per replication | 478.0000 | - | 6 | - | no | reported |

### D08h at STD: historical selection bias, with an estimated core hedge (6 of 400 replications)

| metric | what | estimate | 95% interval | n | threshold | required here | verdict |
|---|---|---|---|---|---|---|---|
| M3 | hedge-aware test (3.1): SPA size at 0.2 | 0.2117 | 0.1699 to 0.2535 | 6 | upper bound ≤ 0.22 | yes | pilot: not decided (outside threshold so far) |
| M3 | hedge-aware test (3.1): SPA size at 0.05 | 0.0495 | 0.0344 to 0.0646 | 6 | upper bound ≤ 0.06 | yes | pilot: not decided (outside threshold so far) |
| M3 | hedge-aware test (3.1): SPA size at 0.001 (pooled) | 0.0016 | 0.0005 to 0.0028 | 1886 | upper bound ≤ 0.0015 | yes | pilot: not decided (outside threshold so far) |
| M3 | hedge-aware test (3.1): Romano-Wolf FWER at 0.05 | 0.0503 | 0.0355 to 0.0652 | 6 | upper bound ≤ 0.06 | yes | pilot: not decided (outside threshold so far) |
| M3 | hedge-aware test (3.1): SPA size at 0.05, lower p-value | 0.0527 | 0.0383 to 0.0671 | 6 | - | no | reported |
| M3 | hedge-aware test (3.1): SPA size at 0.05, upper p-value | 0.0495 | 0.0344 to 0.0646 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.2 | 0.2733 | 0.2291 to 0.3175 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.05 | 0.0909 | 0.0627 to 0.1192 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.001 (pooled) | 0.0053 | 0.0011 to 0.0097 | 1886 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: Romano-Wolf FWER at 0.05 | 0.0892 | 0.0643 to 0.1141 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.05, lower p-value | 0.1001 | 0.0687 to 0.1314 | 6 | - | no | reported |
| M3 | 3.0 test on the estimated hedge: SPA size at 0.05, upper p-value | 0.0909 | 0.0627 to 0.1192 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.2 | 0.2145 | 0.1689 to 0.2600 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.05 | 0.0599 | 0.0411 to 0.0787 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.001 (pooled) | 0.0021 | 0.0005 to 0.0042 | 1886 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): Romano-Wolf FWER at 0.05 | 0.0607 | 0.0405 to 0.0808 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.05, lower p-value | 0.0663 | 0.0465 to 0.0860 | 6 | - | no | reported |
| M3 | 3.0 test on the true hedged returns (oracle): SPA size at 0.05, upper p-value | 0.0599 | 0.0411 to 0.0787 | 6 | - | no | reported |
| M3 | paired difference at 0.2: hedge-aware test (3.1) minus the oracle | -0.0028 | -0.0126 to 0.0070 | 6 | - | no | reported |
| M3 | paired difference at 0.2: 3.0 test on the estimated hedge minus the oracle | 0.0588 | 0.0405 to 0.0772 | 6 | - | no | reported |
| M3 | paired difference at 0.2: hedge-aware test minus the 3.0 test on the estimated hedge | -0.0616 | -0.0769 to -0.0464 | 6 | - | no | reported |
| M3 | paired difference at 0.05: hedge-aware test (3.1) minus the oracle | -0.0104 | -0.0183 to -0.0025 | 6 | - | no | reported |
| M3 | paired difference at 0.05: 3.0 test on the estimated hedge minus the oracle | 0.0310 | 0.0121 to 0.0499 | 6 | - | no | reported |
| M3 | paired difference at 0.05: hedge-aware test minus the 3.0 test on the estimated hedge | -0.0414 | -0.0575 to -0.0253 | 6 | - | no | reported |
| precision | 95% half-width of the hedge-aware size at 0.2 | 0.0418 | - | 6 | at most 0.02 (SIM_PREREG_v2 section 6) | no | pilot |
| precision | 95% half-width of the hedge-aware size at 0.05 | 0.0151 | - | 6 | at most 0.01 (SIM_PREREG_v2 section 6) | no | pilot |
| cost | seconds per replication | 599.0067 | - | 6 | - | no | reported |
| cost | mean bootstrap resamples per family, hedge-aware test (3.1) | 4223.8059 | - | 6 | - | no | reported |
| cost | mean bootstrap resamples per family, 3.0 test on the estimated hedge | 4648.2256 | - | 6 | - | no | reported |
| cost | mean bootstrap resamples per family, 3.0 test on the true hedged returns (oracle) | 4400.6838 | - | 6 | - | no | reported |
| info | families per replication | 481.3333 | - | 6 | - | no | reported |

## 2. The analytic hierarchical model (HB scenarios)

### D01 at HB: no edges (12 of 400 replications)

| metric | what | estimate | 95% interval | n | threshold | required here | verdict |
|---|---|---|---|---|---|---|---|
| M12 | reviews not computed (a fit fails the grid gate), of 480 | 0.0000 | - | 480 | exactly 0 | yes | pilot: not decided (none so far) |
| fit | largest posterior mass on the ends of the grid of μ_A, any fit of any review | 0.0000 | - | 480 | gate: at most 0.01 | no | reported |
| info | review calendar | - | - | 12 | - | no | a review every 63 trading days (40 reviews a replication); M7 and M9 read at years 2, 4, 7, 10 |
| M7 | year 2: share with a true edge among families with Π^min ≥ 0.8 (0 family observations) | - | - | 0 | - | no | reported |
| M7 | year 2: share with a true edge among families with Π^min ≥ 0.4 (0 family observations) | - | - | 0 | - | no | reported |
| M7 | year 2: expected calibration error of the central model | 0.0372 | 0.0337 to 0.0417 | 600 | - | no | reported |
| M7 | year 2: share of family evaluations with Π^min ≥ 0.80 (no edges exist) | 0.0000 | 0.0000 to 0.0000 | 600 | - | no | reported |
| M9 | year 2: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (0 obs.) | - | - | 0 | - | no | reported |
| M9 | year 2: bias of the naive estimate, Promising or higher, candidate (i) | - | - | 0 | - | no | reported |
| M9 | year 2: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (0 obs.) | - | - | 0 | - | no | reported |
| M9 | year 2: bias of the naive estimate, Statistically supported or higher, candidate (i) | - | - | 0 | - | no | reported |
| M9 | year 2: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (0 obs.) | - | - | 0 | - | no | reported |
| M9 | year 2: bias of the naive estimate, Promising or higher, candidate (ii) | - | - | 0 | - | no | reported |
| M9 | year 2: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (0 obs.) | - | - | 0 | - | no | reported |
| M9 | year 2: bias of the naive estimate, Statistically supported or higher, candidate (ii) | - | - | 0 | - | no | reported |
| M7 | year 4: share with a true edge among families with Π^min ≥ 0.8 (0 family observations) | - | - | 0 | lower bound ≥ 0.7 | yes | not evaluated: fewer than 200 observations |
| M7 | year 4: share with a true edge among families with Π^min ≥ 0.4 (0 family observations) | - | - | 0 | lower bound ≥ 0.3 | yes | not evaluated: fewer than 200 observations |
| M7 | year 4: expected calibration error of the central model | 0.0296 | 0.0264 to 0.0331 | 1200 | upper bound ≤ 0.1 | yes | pilot: not decided (within threshold so far) |
| M7 | year 4: share of family evaluations with Π^min ≥ 0.80 (no edges exist) | 0.0000 | 0.0000 to 0.0000 | 1200 | upper bound ≤ 0.01 | yes | pilot: not decided (within threshold so far) |
| M9 | year 4: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (0 obs.) | - | - | 0 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 4: bias of the naive estimate, Promising or higher, candidate (i) | - | - | 0 | - | no | reported |
| M9 | year 4: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (0 obs.) | - | - | 0 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 4: bias of the naive estimate, Statistically supported or higher, candidate (i) | - | - | 0 | - | no | reported |
| M9 | year 4: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (0 obs.) | - | - | 0 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 4: bias of the naive estimate, Promising or higher, candidate (ii) | - | - | 0 | - | no | reported |
| M9 | year 4: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (0 obs.) | - | - | 0 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 4: bias of the naive estimate, Statistically supported or higher, candidate (ii) | - | - | 0 | - | no | reported |
| M7 | year 7: share with a true edge among families with Π^min ≥ 0.8 (0 family observations) | - | - | 0 | - | no | reported |
| M7 | year 7: share with a true edge among families with Π^min ≥ 0.4 (0 family observations) | - | - | 0 | - | no | reported |
| M7 | year 7: expected calibration error of the central model | 0.0222 | 0.0210 to 0.0235 | 2040 | - | no | reported |
| M7 | year 7: share of family evaluations with Π^min ≥ 0.80 (no edges exist) | 0.0000 | 0.0000 to 0.0000 | 2040 | - | no | reported |
| M9 | year 7: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (0 obs.) | - | - | 0 | - | no | reported |
| M9 | year 7: bias of the naive estimate, Promising or higher, candidate (i) | - | - | 0 | - | no | reported |
| M9 | year 7: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (0 obs.) | - | - | 0 | - | no | reported |
| M9 | year 7: bias of the naive estimate, Statistically supported or higher, candidate (i) | - | - | 0 | - | no | reported |
| M9 | year 7: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (0 obs.) | - | - | 0 | - | no | reported |
| M9 | year 7: bias of the naive estimate, Promising or higher, candidate (ii) | - | - | 0 | - | no | reported |
| M9 | year 7: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (0 obs.) | - | - | 0 | - | no | reported |
| M9 | year 7: bias of the naive estimate, Statistically supported or higher, candidate (ii) | - | - | 0 | - | no | reported |
| M7 | year 10: share with a true edge among families with Π^min ≥ 0.8 (0 family observations) | - | - | 0 | lower bound ≥ 0.7 | yes | not evaluated: fewer than 200 observations |
| M7 | year 10: share with a true edge among families with Π^min ≥ 0.4 (1 family observations) | 0.0000 | 0.0000 to 0.0000 | 1 | lower bound ≥ 0.3 | yes | not evaluated: fewer than 200 observations |
| M7 | year 10: expected calibration error of the central model | 0.0186 | 0.0177 to 0.0196 | 2880 | upper bound ≤ 0.1 | yes | pilot: not decided (within threshold so far) |
| M7 | year 10: share of family evaluations with Π^min ≥ 0.80 (no edges exist) | 0.0000 | 0.0000 to 0.0000 | 2880 | upper bound ≤ 0.01 | yes | pilot: not decided (within threshold so far) |
| M9 | year 10: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (3 obs.) | 1.6366 | 1.1909 to 2.0048 | 3 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 10: bias of the naive estimate, Promising or higher, candidate (i) | 0.3108 | 0.1529 to 0.4223 | 3 | - | no | reported |
| M9 | year 10: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (0 obs.) | - | - | 0 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 10: bias of the naive estimate, Statistically supported or higher, candidate (i) | - | - | 0 | - | no | reported |
| M9 | year 10: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (3 obs.) | 1.6366 | 1.1909 to 2.0048 | 3 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 10: bias of the naive estimate, Promising or higher, candidate (ii) | 0.3108 | 0.1529 to 0.4223 | 3 | - | no | reported |
| M9 | year 10: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (0 obs.) | - | - | 0 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 10: bias of the naive estimate, Statistically supported or higher, candidate (ii) | - | - | 0 | - | no | reported |
| M8 | premature elimination: families with a true edge that end dormant, candidate (i) | - | - | 0 | upper bound ≤ 0.1 | yes | no data |
| info | at the end, candidate (i): passed screening / Promising / supported / dormant (means) | - | - | 12 | - | no | 0.1 / 0.2 / 0.0 / 43.2 |
| M8 | premature elimination: families with a true edge that end dormant, candidate (ii) | - | - | 0 | upper bound ≤ 0.1 | yes | no data |
| info | at the end, candidate (ii): passed screening / Promising / supported / dormant (means) | - | - | 12 | - | no | 0.0 / 0.2 / 0.0 / 43.2 |
| cost | seconds per replication | 653.0500 | - | 12 | - | no | reported |
| cost | year 2: seconds for the six fits of a review (50 families) | 21.7246 | - | 12 | - | no | reported |
| info | year 2: common share r of the forward estimates' variance | 0.0731 | - | 12 | - | no | reported |
| info | year 2: posterior means under S0 of μ_A / τ_A / ψ / the classes' ρ (means over reviews) | - | - | 12 | - | no | 0.084 / 0.084 / 1.060 / 0.37, 0.38, 0.38 |
| cost | year 4: seconds for the six fits of a review (100 families) | 13.1922 | - | 12 | - | no | reported |
| info | year 4: common share r of the forward estimates' variance | 0.0710 | - | 12 | - | no | reported |
| info | year 4: posterior means under S0 of μ_A / τ_A / ψ / the classes' ρ (means over reviews) | - | - | 12 | - | no | 0.061 / 0.066 / 1.054 / 0.36, 0.37, 0.36 |
| cost | year 7: seconds for the six fits of a review (170 families) | 8.4983 | - | 12 | - | no | reported |
| info | year 7: common share r of the forward estimates' variance | 0.0679 | - | 12 | - | no | reported |
| info | year 7: posterior means under S0 of μ_A / τ_A / ψ / the classes' ρ (means over reviews) | - | - | 12 | - | no | 0.046 / 0.052 / 1.053 / 0.35, 0.35, 0.34 |
| cost | year 10: seconds for the six fits of a review (240 families) | 7.4564 | - | 12 | - | no | reported |
| info | year 10: common share r of the forward estimates' variance | 0.0666 | - | 12 | - | no | reported |
| info | year 10: posterior means under S0 of μ_A / τ_A / ψ / the classes' ρ (means over reviews) | - | - | 12 | - | no | 0.013 / 0.047 / 1.053 / 0.31, 0.31, 0.31 |
| cost | attention: reviews written per replication, candidate (i) (of 5080 family-reviews; a family dormant before and after a date needs none) | 4442.2500 | 4315.5052 to 4568.9948 | 12 | - | no | reported |
| cost | attention: share of the families with no edge of at least θ_min that are dormant at the end, candidate (i) | 0.1802 | 0.1368 to 0.2205 | 2880 | - | no | reported |
| info | year 2: families dormant after the review / reviews written / families evaluated (means), candidate (i) | - | - | 12 | - | no | 1.7 / 48.8 / 50.0 |
| info | year 4: families dormant after the review / reviews written / families evaluated (means), candidate (i) | - | - | 12 | - | no | 7.6 / 93.6 / 100.0 |
| info | year 7: families dormant after the review / reviews written / families evaluated (means), candidate (i) | - | - | 12 | - | no | 24.8 / 147.2 / 170.0 |
| info | year 10: families dormant after the review / reviews written / families evaluated (means), candidate (i) | - | - | 12 | - | no | 43.2 / 196.8 / 240.0 |
| cost | attention: reviews written per replication, candidate (ii) (of 5080 family-reviews; a family dormant before and after a date needs none) | 4442.2500 | 4315.2657 to 4569.2343 | 12 | - | no | reported |
| cost | attention: share of the families with no edge of at least θ_min that are dormant at the end, candidate (ii) | 0.1802 | 0.1368 to 0.2205 | 2880 | - | no | reported |
| info | dormancy rule | - | - | 12 | - | no | protocol-3.1-section-9.1-forward-record |
| cost | seconds per replication spent on the model (estimates, six fits at every review, forecasts) | 626.9917 | - | 12 | - | no | reported |
| cost | of which the dormancy forecasts | 35.9775 | - | 12 | - | no | reported |
| cost | seconds for the six fits of a review, mean over every review | 14.7137 | - | 480 | - | no | reported |
| info | model | - | - | 12 | - | no | analytic-normal-normal-3.1 |

### D02 at HB: rare edges (12 of 400 replications)

| metric | what | estimate | 95% interval | n | threshold | required here | verdict |
|---|---|---|---|---|---|---|---|
| M12 | reviews not computed (a fit fails the grid gate), of 480 | 0.0000 | - | 480 | exactly 0 | yes | pilot: not decided (none so far) |
| fit | largest posterior mass on the ends of the grid of μ_A, any fit of any review | 0.0000 | - | 480 | gate: at most 0.01 | no | reported |
| info | review calendar | - | - | 12 | - | no | a review every 63 trading days (40 reviews a replication); M7 and M9 read at years 2, 4, 7, 10 |
| M7 | year 2: share with a true edge among families with Π^min ≥ 0.8 (0 family observations) | - | - | 0 | - | no | reported |
| M7 | year 2: share with a true edge among families with Π^min ≥ 0.4 (0 family observations) | - | - | 0 | - | no | reported |
| M7 | year 2: expected calibration error of the central model | 0.0307 | 0.0203 to 0.0382 | 600 | - | no | reported |
| M9 | year 2: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (2 obs.) | -0.3400 | -0.4277 to -0.2524 | 2 | - | no | reported |
| M9 | year 2: bias of the naive estimate, Promising or higher, candidate (i) | 0.4330 | 0.2370 to 0.6291 | 2 | - | no | reported |
| M9 | year 2: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (0 obs.) | - | - | 0 | - | no | reported |
| M9 | year 2: bias of the naive estimate, Statistically supported or higher, candidate (i) | - | - | 0 | - | no | reported |
| M9 | year 2: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (1 obs.) | -0.4277 | -0.4277 to -0.4277 | 1 | - | no | reported |
| M9 | year 2: bias of the naive estimate, Promising or higher, candidate (ii) | 0.2370 | 0.2370 to 0.2370 | 1 | - | no | reported |
| M9 | year 2: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (0 obs.) | - | - | 0 | - | no | reported |
| M9 | year 2: bias of the naive estimate, Statistically supported or higher, candidate (ii) | - | - | 0 | - | no | reported |
| M7 | year 4: share with a true edge among families with Π^min ≥ 0.8 (0 family observations) | - | - | 0 | lower bound ≥ 0.7 | yes | not evaluated: fewer than 200 observations |
| M7 | year 4: share with a true edge among families with Π^min ≥ 0.4 (1 family observations) | 1.0000 | 1.0000 to 1.0000 | 1 | lower bound ≥ 0.3 | yes | not evaluated: fewer than 200 observations |
| M7 | year 4: expected calibration error of the central model | 0.0230 | 0.0159 to 0.0287 | 1200 | upper bound ≤ 0.1 | yes | pilot: not decided (within threshold so far) |
| M9 | year 4: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (4 obs.) | -0.2354 | -0.6867 to 0.0054 | 4 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 4: bias of the naive estimate, Promising or higher, candidate (i) | 0.4878 | 0.2012 to 0.7662 | 4 | - | no | reported |
| M9 | year 4: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (0 obs.) | - | - | 0 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 4: bias of the naive estimate, Statistically supported or higher, candidate (i) | - | - | 0 | - | no | reported |
| M9 | year 4: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (1 obs.) | 0.0054 | 0.0054 to 0.0054 | 1 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 4: bias of the naive estimate, Promising or higher, candidate (ii) | 0.2176 | 0.2176 to 0.2176 | 1 | - | no | reported |
| M9 | year 4: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (0 obs.) | - | - | 0 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 4: bias of the naive estimate, Statistically supported or higher, candidate (ii) | - | - | 0 | - | no | reported |
| M7 | year 7: share with a true edge among families with Π^min ≥ 0.8 (0 family observations) | - | - | 0 | - | no | reported |
| M7 | year 7: share with a true edge among families with Π^min ≥ 0.4 (2 family observations) | 1.0000 | 1.0000 to 1.0000 | 2 | - | no | reported |
| M7 | year 7: expected calibration error of the central model | 0.0170 | 0.0125 to 0.0208 | 2040 | - | no | reported |
| M9 | year 7: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (6 obs.) | -0.1285 | -0.5047 to 0.1594 | 6 | - | no | reported |
| M9 | year 7: bias of the naive estimate, Promising or higher, candidate (i) | 0.4640 | 0.1671 to 0.6985 | 6 | - | no | reported |
| M9 | year 7: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (0 obs.) | - | - | 0 | - | no | reported |
| M9 | year 7: bias of the naive estimate, Statistically supported or higher, candidate (i) | - | - | 0 | - | no | reported |
| M9 | year 7: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (4 obs.) | 0.0067 | -0.2392 to 0.2423 | 4 | - | no | reported |
| M9 | year 7: bias of the naive estimate, Promising or higher, candidate (ii) | 0.4295 | 0.1986 to 0.6449 | 4 | - | no | reported |
| M9 | year 7: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (0 obs.) | - | - | 0 | - | no | reported |
| M9 | year 7: bias of the naive estimate, Statistically supported or higher, candidate (ii) | - | - | 0 | - | no | reported |
| M7 | year 10: share with a true edge among families with Π^min ≥ 0.8 (0 family observations) | - | - | 0 | lower bound ≥ 0.7 | yes | not evaluated: fewer than 200 observations |
| M7 | year 10: share with a true edge among families with Π^min ≥ 0.4 (4 family observations) | 1.0000 | 1.0000 to 1.0000 | 4 | lower bound ≥ 0.3 | yes | not evaluated: fewer than 200 observations |
| M7 | year 10: expected calibration error of the central model | 0.0142 | 0.0106 to 0.0177 | 2880 | upper bound ≤ 0.1 | yes | pilot: not decided (within threshold so far) |
| M9 | year 10: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (10 obs.) | -0.1655 | -0.4924 to 0.0792 | 10 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 10: bias of the naive estimate, Promising or higher, candidate (i) | 0.3499 | 0.1115 to 0.5273 | 10 | - | no | reported |
| M9 | year 10: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (0 obs.) | - | - | 0 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 10: bias of the naive estimate, Statistically supported or higher, candidate (i) | - | - | 0 | - | no | reported |
| M9 | year 10: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (7 obs.) | -0.0336 | -0.2522 to 0.1535 | 7 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 10: bias of the naive estimate, Promising or higher, candidate (ii) | 0.3618 | 0.1369 to 0.5443 | 7 | - | no | reported |
| M9 | year 10: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (0 obs.) | - | - | 0 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 10: bias of the naive estimate, Statistically supported or higher, candidate (ii) | - | - | 0 | - | no | reported |
| M8 | premature elimination: families with a true edge that end dormant, candidate (i) | 0.0000 | 0.0000 to 0.0000 | 42 | upper bound ≤ 0.1 | yes | pilot: not decided (within threshold so far) |
| info | at the end, candidate (i): passed screening / Promising / supported / dormant (means) | - | - | 12 | - | no | 1.0 / 0.8 / 0.0 / 30.0 |
| M8 | premature elimination: families with a true edge that end dormant, candidate (ii) | 0.0000 | 0.0000 to 0.0000 | 42 | upper bound ≤ 0.1 | yes | pilot: not decided (within threshold so far) |
| info | at the end, candidate (ii): passed screening / Promising / supported / dormant (means) | - | - | 12 | - | no | 0.1 / 0.6 / 0.0 / 30.0 |
| cost | seconds per replication | 720.5250 | - | 12 | - | no | reported |
| cost | year 2: seconds for the six fits of a review (50 families) | 24.7481 | - | 12 | - | no | reported |
| info | year 2: common share r of the forward estimates' variance | 0.0729 | - | 12 | - | no | reported |
| info | year 2: families with a true edge (8 observations): mean Π^min / mean Π under S0 / mean Π^max | - | - | 8 | - | no | 0.127 / 0.268 / 0.406 |
| info | year 2: families with a true edge: the most cautious model is S0 / S1 / S2 / S3 / S4 / S5 (shares) | - | - | 8 | - | no | 0.00 / 0.25 / 0.12 / 0.00 / 0.62 / 0.00 |
| info | year 2: families with a true edge: share Statistically supported / share dormant, candidate (i) | - | - | 8 | - | no | 0.000 / 0.000 |
| info | year 2: posterior means under S0 of μ_A / τ_A / ψ / the classes' ρ (means over reviews) | - | - | 12 | - | no | 0.034 / 0.101 / 1.069 / 0.38, 0.38, 0.38 |
| cost | year 4: seconds for the six fits of a review (100 families) | 15.0531 | - | 12 | - | no | reported |
| info | year 4: common share r of the forward estimates' variance | 0.0674 | - | 12 | - | no | reported |
| info | year 4: families with a true edge (18 observations): mean Π^min / mean Π under S0 / mean Π^max | - | - | 18 | - | no | 0.141 / 0.297 / 0.429 |
| info | year 4: families with a true edge: the most cautious model is S0 / S1 / S2 / S3 / S4 / S5 (shares) | - | - | 18 | - | no | 0.00 / 0.17 / 0.00 / 0.00 / 0.61 / 0.22 |
| info | year 4: families with a true edge: share Statistically supported / share dormant, candidate (i) | - | - | 18 | - | no | 0.000 / 0.000 |
| info | year 4: posterior means under S0 of μ_A / τ_A / ψ / the classes' ρ (means over reviews) | - | - | 12 | - | no | 0.026 / 0.071 / 1.058 / 0.39, 0.38, 0.37 |
| cost | year 7: seconds for the six fits of a review (170 families) | 9.5531 | - | 12 | - | no | reported |
| info | year 7: common share r of the forward estimates' variance | 0.0658 | - | 12 | - | no | reported |
| info | year 7: families with a true edge (28 observations): mean Π^min / mean Π under S0 / mean Π^max | - | - | 28 | - | no | 0.132 / 0.281 / 0.379 |
| info | year 7: families with a true edge: the most cautious model is S0 / S1 / S2 / S3 / S4 / S5 (shares) | - | - | 28 | - | no | 0.00 / 0.14 / 0.00 / 0.00 / 0.50 / 0.36 |
| info | year 7: families with a true edge: share Statistically supported / share dormant, candidate (i) | - | - | 28 | - | no | 0.000 / 0.000 |
| info | year 7: posterior means under S0 of μ_A / τ_A / ψ / the classes' ρ (means over reviews) | - | - | 12 | - | no | 0.031 / 0.054 / 1.053 / 0.36, 0.34, 0.34 |
| cost | year 10: seconds for the six fits of a review (240 families) | 7.5061 | - | 12 | - | no | reported |
| info | year 10: common share r of the forward estimates' variance | 0.0669 | - | 12 | - | no | reported |
| info | year 10: families with a true edge (42 observations): mean Π^min / mean Π under S0 / mean Π^max | - | - | 42 | - | no | 0.143 / 0.380 / 0.465 |
| info | year 10: families with a true edge: the most cautious model is S0 / S1 / S2 / S3 / S4 / S5 (shares) | - | - | 42 | - | no | 0.00 / 0.14 / 0.00 / 0.00 / 0.43 / 0.43 |
| info | year 10: families with a true edge: share Statistically supported / share dormant, candidate (i) | - | - | 42 | - | no | 0.000 / 0.000 |
| info | year 10: posterior means under S0 of μ_A / τ_A / ψ / the classes' ρ (means over reviews) | - | - | 12 | - | no | 0.043 / 0.046 / 1.053 / 0.40, 0.37, 0.36 |
| cost | attention: reviews written per replication, candidate (i) (of 5080 family-reviews; a family dormant before and after a date needs none) | 4684.1667 | 4604.5804 to 4763.7529 | 12 | - | no | reported |
| cost | attention: share of the families with no edge of at least θ_min that are dormant at the end, candidate (i) | 0.1268 | 0.1058 to 0.1533 | 2838 | - | no | reported |
| info | year 2: families dormant after the review / reviews written / families evaluated (means), candidate (i) | - | - | 12 | - | no | 1.3 / 49.0 / 50.0 |
| info | year 4: families dormant after the review / reviews written / families evaluated (means), candidate (i) | - | - | 12 | - | no | 6.2 / 94.7 / 100.0 |
| info | year 7: families dormant after the review / reviews written / families evaluated (means), candidate (i) | - | - | 12 | - | no | 14.6 / 156.6 / 170.0 |
| info | year 10: families dormant after the review / reviews written / families evaluated (means), candidate (i) | - | - | 12 | - | no | 30.0 / 210.0 / 240.0 |
| cost | attention: reviews written per replication, candidate (ii) (of 5080 family-reviews; a family dormant before and after a date needs none) | 4685.1667 | 4606.0734 to 4764.2599 | 12 | - | no | reported |
| cost | attention: share of the families with no edge of at least θ_min that are dormant at the end, candidate (ii) | 0.1268 | 0.1058 to 0.1533 | 2838 | - | no | reported |
| info | dormancy rule | - | - | 12 | - | no | protocol-3.1-section-9.1-forward-record |
| cost | seconds per replication spent on the model (estimates, six fits at every review, forecasts) | 690.6642 | - | 12 | - | no | reported |
| cost | of which the dormancy forecasts | 36.3325 | - | 12 | - | no | reported |
| cost | seconds for the six fits of a review, mean over every review | 16.2949 | - | 480 | - | no | reported |
| info | model | - | - | 12 | - | no | analytic-normal-normal-3.1 |

### D05 at HB: fat tails (12 of 400 replications)

| metric | what | estimate | 95% interval | n | threshold | required here | verdict |
|---|---|---|---|---|---|---|---|
| M12 | reviews not computed (a fit fails the grid gate), of 480 | 0.0000 | - | 480 | exactly 0 | yes | pilot: not decided (none so far) |
| fit | largest posterior mass on the ends of the grid of μ_A, any fit of any review | 0.0000 | - | 480 | gate: at most 0.01 | no | reported |
| info | review calendar | - | - | 12 | - | no | a review every 63 trading days (40 reviews a replication); M7 and M9 read at years 2, 4, 7, 10 |
| M7 | year 2: share with a true edge among families with Π^min ≥ 0.8 (0 family observations) | - | - | 0 | - | no | reported |
| M7 | year 2: share with a true edge among families with Π^min ≥ 0.4 (1 family observations) | 1.0000 | 1.0000 to 1.0000 | 1 | - | no | reported |
| M7 | year 2: expected calibration error of the central model | 0.0189 | 0.0136 to 0.0244 | 600 | - | no | reported |
| M9 | year 2: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (7 obs.) | -0.5061 | -0.8936 to -0.3728 | 7 | - | no | reported |
| M9 | year 2: bias of the naive estimate, Promising or higher, candidate (i) | 0.4514 | 0.1669 to 0.5602 | 7 | - | no | reported |
| M9 | year 2: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (0 obs.) | - | - | 0 | - | no | reported |
| M9 | year 2: bias of the naive estimate, Statistically supported or higher, candidate (i) | - | - | 0 | - | no | reported |
| M9 | year 2: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (2 obs.) | -0.4789 | -0.4789 to -0.4789 | 2 | - | no | reported |
| M9 | year 2: bias of the naive estimate, Promising or higher, candidate (ii) | 0.5602 | 0.5602 to 0.5602 | 2 | - | no | reported |
| M9 | year 2: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (0 obs.) | - | - | 0 | - | no | reported |
| M9 | year 2: bias of the naive estimate, Statistically supported or higher, candidate (ii) | - | - | 0 | - | no | reported |
| M7 | year 4: share with a true edge among families with Π^min ≥ 0.8 (0 family observations) | - | - | 0 | lower bound ≥ 0.7 | yes | not evaluated: fewer than 200 observations |
| M7 | year 4: share with a true edge among families with Π^min ≥ 0.4 (6 family observations) | 1.0000 | 1.0000 to 1.0000 | 6 | lower bound ≥ 0.3 | yes | not evaluated: fewer than 200 observations |
| M7 | year 4: expected calibration error of the central model | 0.0135 | 0.0063 to 0.0219 | 1200 | upper bound ≤ 0.1 | yes | pilot: not decided (within threshold so far) |
| M9 | year 4: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (14 obs.) | -0.4372 | -0.6906 to -0.1987 | 14 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 4: bias of the naive estimate, Promising or higher, candidate (i) | 0.3579 | 0.1885 to 0.4688 | 14 | - | no | reported |
| M9 | year 4: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (1 obs.) | 0.0602 | 0.0602 to 0.0602 | 1 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 4: bias of the naive estimate, Statistically supported or higher, candidate (i) | 0.2547 | 0.2547 to 0.2547 | 1 | - | no | reported |
| M9 | year 4: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (6 obs.) | -0.0631 | -0.5814 to 0.6048 | 6 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 4: bias of the naive estimate, Promising or higher, candidate (ii) | 0.3085 | -0.0380 to 0.4848 | 6 | - | no | reported |
| M9 | year 4: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (1 obs.) | 0.0602 | 0.0602 to 0.0602 | 1 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 4: bias of the naive estimate, Statistically supported or higher, candidate (ii) | 0.2547 | 0.2547 to 0.2547 | 1 | - | no | reported |
| M7 | year 7: share with a true edge among families with Π^min ≥ 0.8 (6 family observations) | 1.0000 | 1.0000 to 1.0000 | 6 | - | no | reported |
| M7 | year 7: share with a true edge among families with Π^min ≥ 0.4 (13 family observations) | 1.0000 | 1.0000 to 1.0000 | 13 | - | no | reported |
| M7 | year 7: expected calibration error of the central model | 0.0030 | 0.0002 to 0.0118 | 2040 | - | no | reported |
| M9 | year 7: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (17 obs.) | -0.1736 | -0.4463 to 0.0833 | 17 | - | no | reported |
| M9 | year 7: bias of the naive estimate, Promising or higher, candidate (i) | 0.2981 | 0.1749 to 0.4319 | 17 | - | no | reported |
| M9 | year 7: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (5 obs.) | 0.0887 | -0.4096 to 0.6667 | 5 | - | no | reported |
| M9 | year 7: bias of the naive estimate, Statistically supported or higher, candidate (i) | 0.2605 | 0.1188 to 0.4431 | 5 | - | no | reported |
| M9 | year 7: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (16 obs.) | -0.0836 | -0.2324 to 0.1248 | 16 | - | no | reported |
| M9 | year 7: bias of the naive estimate, Promising or higher, candidate (ii) | 0.3100 | 0.1828 to 0.4393 | 16 | - | no | reported |
| M9 | year 7: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (5 obs.) | 0.0887 | -0.4096 to 0.6667 | 5 | - | no | reported |
| M9 | year 7: bias of the naive estimate, Statistically supported or higher, candidate (ii) | 0.2605 | 0.1188 to 0.4431 | 5 | - | no | reported |
| M7 | year 10: share with a true edge among families with Π^min ≥ 0.8 (8 family observations) | 1.0000 | 1.0000 to 1.0000 | 8 | lower bound ≥ 0.7 | yes | not evaluated: fewer than 200 observations |
| M7 | year 10: share with a true edge among families with Π^min ≥ 0.4 (21 family observations) | 1.0000 | 1.0000 to 1.0000 | 21 | lower bound ≥ 0.3 | yes | not evaluated: fewer than 200 observations |
| M7 | year 10: expected calibration error of the central model | 0.0052 | 0.0004 to 0.0228 | 2880 | upper bound ≤ 0.1 | yes | pilot: not decided (within threshold so far) |
| M9 | year 10: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (31 obs.) | -0.0860 | -0.2674 to 0.0528 | 31 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 10: bias of the naive estimate, Promising or higher, candidate (i) | 0.3343 | 0.2234 to 0.4464 | 31 | - | no | reported |
| M9 | year 10: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (10 obs.) | 0.1602 | 0.0247 to 0.2579 | 10 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 10: bias of the naive estimate, Statistically supported or higher, candidate (i) | 0.2654 | 0.1163 to 0.3952 | 10 | - | no | reported |
| M9 | year 10: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (29 obs.) | -0.0311 | -0.1664 to 0.0917 | 29 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 10: bias of the naive estimate, Promising or higher, candidate (ii) | 0.3198 | 0.2001 to 0.4331 | 29 | - | no | reported |
| M9 | year 10: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (10 obs.) | 0.1602 | 0.0247 to 0.2579 | 10 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 10: bias of the naive estimate, Statistically supported or higher, candidate (ii) | 0.2654 | 0.1163 to 0.3952 | 10 | - | no | reported |
| M8 | premature elimination: families with a true edge that end dormant, candidate (i) | 0.0143 | 0.0000 to 0.0355 | 140 | upper bound ≤ 0.1 | yes | pilot: not decided (within threshold so far) |
| info | at the end, candidate (i): passed screening / Promising / supported / dormant (means) | - | - | 12 | - | no | 3.4 / 2.6 / 0.8 / 28.5 |
| M8 | premature elimination: families with a true edge that end dormant, candidate (ii) | 0.0143 | 0.0000 to 0.0355 | 140 | upper bound ≤ 0.1 | yes | pilot: not decided (within threshold so far) |
| info | at the end, candidate (ii): passed screening / Promising / supported / dormant (means) | - | - | 12 | - | no | 1.0 / 2.4 / 0.8 / 28.5 |
| cost | seconds per replication | 859.8417 | - | 12 | - | no | reported |
| cost | year 2: seconds for the six fits of a review (50 families) | 28.7744 | - | 12 | - | no | reported |
| info | year 2: common share r of the forward estimates' variance | 0.0710 | - | 12 | - | no | reported |
| info | year 2: families with a true edge (24 observations): mean Π^min / mean Π under S0 / mean Π^max | - | - | 24 | - | no | 0.122 / 0.233 / 0.348 |
| info | year 2: families with a true edge: the most cautious model is S0 / S1 / S2 / S3 / S4 / S5 (shares) | - | - | 24 | - | no | 0.00 / 0.42 / 0.00 / 0.00 / 0.46 / 0.12 |
| info | year 2: families with a true edge: share Statistically supported / share dormant, candidate (i) | - | - | 24 | - | no | 0.000 / 0.000 |
| info | year 2: posterior means under S0 of μ_A / τ_A / ψ / the classes' ρ (means over reviews) | - | - | 12 | - | no | 0.021 / 0.115 / 1.074 / 0.39, 0.38, 0.38 |
| cost | year 4: seconds for the six fits of a review (100 families) | 19.5160 | - | 12 | - | no | reported |
| info | year 4: common share r of the forward estimates' variance | 0.0606 | - | 12 | - | no | reported |
| info | year 4: families with a true edge (51 observations): mean Π^min / mean Π under S0 / mean Π^max | - | - | 51 | - | no | 0.159 / 0.291 / 0.398 |
| info | year 4: families with a true edge: the most cautious model is S0 / S1 / S2 / S3 / S4 / S5 (shares) | - | - | 51 | - | no | 0.00 / 0.14 / 0.00 / 0.00 / 0.69 / 0.18 |
| info | year 4: families with a true edge: share Statistically supported / share dormant, candidate (i) | - | - | 51 | - | no | 0.020 / 0.020 |
| info | year 4: posterior means under S0 of μ_A / τ_A / ψ / the classes' ρ (means over reviews) | - | - | 12 | - | no | 0.018 / 0.089 / 1.058 / 0.39, 0.41, 0.39 |
| cost | year 7: seconds for the six fits of a review (170 families) | 14.0054 | - | 12 | - | no | reported |
| info | year 7: common share r of the forward estimates' variance | 0.0652 | - | 12 | - | no | reported |
| info | year 7: families with a true edge (93 observations): mean Π^min / mean Π under S0 / mean Π^max | - | - | 93 | - | no | 0.168 / 0.309 / 0.403 |
| info | year 7: families with a true edge: the most cautious model is S0 / S1 / S2 / S3 / S4 / S5 (shares) | - | - | 93 | - | no | 0.00 / 0.17 / 0.01 / 0.00 / 0.47 / 0.34 |
| info | year 7: families with a true edge: share Statistically supported / share dormant, candidate (i) | - | - | 93 | - | no | 0.054 / 0.011 |
| info | year 7: posterior means under S0 of μ_A / τ_A / ψ / the classes' ρ (means over reviews) | - | - | 12 | - | no | 0.010 / 0.074 / 1.053 / 0.40, 0.42, 0.40 |
| cost | year 10: seconds for the six fits of a review (240 families) | 10.1371 | - | 12 | - | no | reported |
| info | year 10: common share r of the forward estimates' variance | 0.0770 | - | 12 | - | no | reported |
| info | year 10: families with a true edge (140 observations): mean Π^min / mean Π under S0 / mean Π^max | - | - | 140 | - | no | 0.186 / 0.389 / 0.477 |
| info | year 10: families with a true edge: the most cautious model is S0 / S1 / S2 / S3 / S4 / S5 (shares) | - | - | 140 | - | no | 0.00 / 0.09 / 0.00 / 0.01 / 0.39 / 0.51 |
| info | year 10: families with a true edge: share Statistically supported / share dormant, candidate (i) | - | - | 140 | - | no | 0.071 / 0.014 |
| info | year 10: posterior means under S0 of μ_A / τ_A / ψ / the classes' ρ (means over reviews) | - | - | 12 | - | no | 0.031 / 0.061 / 1.053 / 0.54, 0.54, 0.51 |
| cost | attention: reviews written per replication, candidate (i) (of 5080 family-reviews; a family dormant before and after a date needs none) | 4630.4167 | 4514.5571 to 4746.2763 | 12 | - | no | reported |
| cost | attention: share of the families with no edge of at least θ_min that are dormant at the end, candidate (i) | 0.1241 | 0.0851 to 0.1666 | 2740 | - | no | reported |
| info | year 2: families dormant after the review / reviews written / families evaluated (means), candidate (i) | - | - | 12 | - | no | 1.2 / 49.0 / 50.0 |
| info | year 4: families dormant after the review / reviews written / families evaluated (means), candidate (i) | - | - | 12 | - | no | 7.4 / 93.8 / 100.0 |
| info | year 7: families dormant after the review / reviews written / families evaluated (means), candidate (i) | - | - | 12 | - | no | 17.4 / 153.8 / 170.0 |
| info | year 10: families dormant after the review / reviews written / families evaluated (means), candidate (i) | - | - | 12 | - | no | 28.5 / 211.5 / 240.0 |
| cost | attention: reviews written per replication, candidate (ii) (of 5080 family-reviews; a family dormant before and after a date needs none) | 4631.5000 | 4516.2266 to 4746.7734 | 12 | - | no | reported |
| cost | attention: share of the families with no edge of at least θ_min that are dormant at the end, candidate (ii) | 0.1241 | 0.0851 to 0.1666 | 2740 | - | no | reported |
| info | dormancy rule | - | - | 12 | - | no | protocol-3.1-section-9.1-forward-record |
| cost | seconds per replication spent on the model (estimates, six fits at every review, forecasts) | 829.3383 | - | 12 | - | no | reported |
| cost | of which the dormancy forecasts | 38.1125 | - | 12 | - | no | reported |
| cost | seconds for the six fits of a review, mean over every review | 19.7160 | - | 480 | - | no | reported |
| info | model | - | - | 12 | - | no | analytic-normal-normal-3.1 |

### D08 at HB: historical selection bias (12 of 400 replications)

| metric | what | estimate | 95% interval | n | threshold | required here | verdict |
|---|---|---|---|---|---|---|---|
| M12 | reviews not computed (a fit fails the grid gate), of 480 | 0.0000 | - | 480 | exactly 0 | yes | pilot: not decided (none so far) |
| fit | largest posterior mass on the ends of the grid of μ_A, any fit of any review | 0.0000 | - | 480 | gate: at most 0.01 | no | reported |
| info | review calendar | - | - | 12 | - | no | a review every 63 trading days (40 reviews a replication); M7 and M9 read at years 2, 4, 7, 10 |
| M7 | year 2: share with a true edge among families with Π^min ≥ 0.8 (1 family observations) | 1.0000 | 1.0000 to 1.0000 | 1 | - | no | reported |
| M7 | year 2: share with a true edge among families with Π^min ≥ 0.4 (44 family observations) | 0.9773 | 0.9596 to 1.0000 | 44 | - | no | reported |
| M7 | year 2: expected calibration error of the central model | 0.0096 | 0.0006 to 0.0393 | 600 | - | no | reported |
| M9 | year 2: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (81 obs.) | -0.5405 | -0.6259 to -0.4740 | 81 | - | no | reported |
| M9 | year 2: bias of the naive estimate, Promising or higher, candidate (i) | 0.4262 | 0.3639 to 0.4974 | 81 | - | no | reported |
| M9 | year 2: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (1 obs.) | -0.2894 | -0.2894 to -0.2894 | 1 | - | no | reported |
| M9 | year 2: bias of the naive estimate, Statistically supported or higher, candidate (i) | 0.3687 | 0.3687 to 0.3687 | 1 | - | no | reported |
| M9 | year 2: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (42 obs.) | -0.5798 | -0.7111 to -0.5093 | 42 | - | no | reported |
| M9 | year 2: bias of the naive estimate, Promising or higher, candidate (ii) | 0.3554 | 0.2480 to 0.4102 | 42 | - | no | reported |
| M9 | year 2: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (1 obs.) | -0.2894 | -0.2894 to -0.2894 | 1 | - | no | reported |
| M9 | year 2: bias of the naive estimate, Statistically supported or higher, candidate (ii) | 0.3687 | 0.3687 to 0.3687 | 1 | - | no | reported |
| M7 | year 4: share with a true edge among families with Π^min ≥ 0.8 (16 family observations) | 1.0000 | 1.0000 to 1.0000 | 16 | lower bound ≥ 0.7 | yes | not evaluated: fewer than 200 observations |
| M7 | year 4: share with a true edge among families with Π^min ≥ 0.4 (133 family observations) | 0.9248 | 0.8839 to 1.0000 | 133 | lower bound ≥ 0.3 | yes | not evaluated: fewer than 200 observations |
| M7 | year 4: expected calibration error of the central model | 0.0317 | 0.0046 to 0.0649 | 1200 | upper bound ≤ 0.1 | yes | pilot: not decided (within threshold so far) |
| M9 | year 4: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (202 obs.) | -0.2881 | -0.4152 to -0.1980 | 202 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | pilot: not decided |
| M9 | year 4: bias of the naive estimate, Promising or higher, candidate (i) | 0.4272 | 0.3726 to 0.4666 | 202 | - | no | reported |
| M9 | year 4: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (18 obs.) | -0.0827 | -0.2221 to 0.0769 | 18 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 4: bias of the naive estimate, Statistically supported or higher, candidate (i) | 0.2692 | 0.1490 to 0.4181 | 18 | - | no | reported |
| M9 | year 4: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (152 obs.) | -0.2180 | -0.3360 to -0.1484 | 152 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 4: bias of the naive estimate, Promising or higher, candidate (ii) | 0.4104 | 0.3181 to 0.4601 | 152 | - | no | reported |
| M9 | year 4: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (18 obs.) | -0.0827 | -0.2221 to 0.0769 | 18 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 4: bias of the naive estimate, Statistically supported or higher, candidate (ii) | 0.2692 | 0.1490 to 0.4181 | 18 | - | no | reported |
| M7 | year 7: share with a true edge among families with Π^min ≥ 0.8 (56 family observations) | 1.0000 | 1.0000 to 1.0000 | 56 | - | no | reported |
| M7 | year 7: share with a true edge among families with Π^min ≥ 0.4 (322 family observations) | 0.8820 | 0.8093 to 0.9773 | 322 | - | no | reported |
| M7 | year 7: expected calibration error of the central model | 0.0686 | 0.0209 to 0.1108 | 2040 | - | no | reported |
| M9 | year 7: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (453 obs.) | -0.1665 | -0.2719 to -0.0891 | 453 | - | no | reported |
| M9 | year 7: bias of the naive estimate, Promising or higher, candidate (i) | 0.4065 | 0.3424 to 0.4554 | 453 | - | no | reported |
| M9 | year 7: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (72 obs.) | -0.0703 | -0.1494 to 0.0082 | 72 | - | no | reported |
| M9 | year 7: bias of the naive estimate, Statistically supported or higher, candidate (i) | 0.3219 | 0.1779 to 0.4088 | 72 | - | no | reported |
| M9 | year 7: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (394 obs.) | -0.1376 | -0.2462 to -0.0610 | 394 | - | no | reported |
| M9 | year 7: bias of the naive estimate, Promising or higher, candidate (ii) | 0.3935 | 0.3172 to 0.4467 | 394 | - | no | reported |
| M9 | year 7: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (68 obs.) | -0.0619 | -0.1468 to 0.0110 | 68 | - | no | reported |
| M9 | year 7: bias of the naive estimate, Statistically supported or higher, candidate (ii) | 0.3227 | 0.1779 to 0.4104 | 68 | - | no | reported |
| M7 | year 10: share with a true edge among families with Π^min ≥ 0.8 (117 family observations) | 0.9915 | 0.9778 to 1.0000 | 117 | lower bound ≥ 0.7 | yes | not evaluated: fewer than 200 observations |
| M7 | year 10: share with a true edge among families with Π^min ≥ 0.4 (441 family observations) | 0.8980 | 0.8682 to 0.9370 | 441 | lower bound ≥ 0.3 | yes | pilot: not decided (within threshold so far) |
| M7 | year 10: expected calibration error of the central model | 0.0998 | 0.0357 to 0.1356 | 2880 | upper bound ≤ 0.1 | yes | pilot: not decided (outside threshold so far) |
| M9 | year 10: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (580 obs.) | -0.1132 | -0.1941 to -0.0595 | 580 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | pilot: not decided |
| M9 | year 10: bias of the naive estimate, Promising or higher, candidate (i) | 0.3974 | 0.3403 to 0.4365 | 580 | - | no | reported |
| M9 | year 10: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (138 obs.) | -0.0440 | -0.0827 to 0.0087 | 138 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 10: bias of the naive estimate, Statistically supported or higher, candidate (i) | 0.3151 | 0.2481 to 0.3639 | 138 | - | no | reported |
| M9 | year 10: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (548 obs.) | -0.0989 | -0.1803 to -0.0454 | 548 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | pilot: not decided |
| M9 | year 10: bias of the naive estimate, Promising or higher, candidate (ii) | 0.3899 | 0.3264 to 0.4333 | 548 | - | no | reported |
| M9 | year 10: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (133 obs.) | -0.0404 | -0.0879 to 0.0163 | 133 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 10: bias of the naive estimate, Statistically supported or higher, candidate (ii) | 0.3103 | 0.2442 to 0.3589 | 133 | - | no | reported |
| M8 | premature elimination: families with a true edge that end dormant, candidate (i) | 0.0053 | 0.0011 to 0.0102 | 944 | upper bound ≤ 0.1 | yes | pilot: not decided (within threshold so far) |
| info | at the end, candidate (i): passed screening / Promising / supported / dormant (means) | - | - | 12 | - | no | 40.8 / 48.3 / 11.5 / 23.2 |
| M8 | premature elimination: families with a true edge that end dormant, candidate (ii) | 0.0053 | 0.0011 to 0.0102 | 944 | upper bound ≤ 0.1 | yes | pilot: not decided (within threshold so far) |
| info | at the end, candidate (ii): passed screening / Promising / supported / dormant (means) | - | - | 12 | - | no | 10.0 / 45.7 / 11.1 / 23.2 |
| cost | seconds per replication | 1488.5333 | - | 12 | - | no | reported |
| cost | year 2: seconds for the six fits of a review (50 families) | 42.1239 | - | 12 | - | no | reported |
| info | year 2: common share r of the forward estimates' variance | 0.0749 | - | 12 | - | no | reported |
| info | year 2: families with a true edge (182 observations): mean Π^min / mean Π under S0 / mean Π^max | - | - | 182 | - | no | 0.277 / 0.502 / 0.617 |
| info | year 2: families with a true edge: the most cautious model is S0 / S1 / S2 / S3 / S4 / S5 (shares) | - | - | 182 | - | no | 0.00 / 0.34 / 0.00 / 0.00 / 0.60 / 0.06 |
| info | year 2: families with a true edge: share Statistically supported / share dormant, candidate (i) | - | - | 182 | - | no | 0.005 / 0.000 |
| info | year 2: posterior means under S0 of μ_A / τ_A / ψ / the classes' ρ (means over reviews) | - | - | 12 | - | no | 0.230 / 0.309 / 1.116 / 0.49, 0.50, 0.50 |
| cost | year 4: seconds for the six fits of a review (100 families) | 36.7684 | - | 12 | - | no | reported |
| info | year 4: common share r of the forward estimates' variance | 0.0677 | - | 12 | - | no | reported |
| info | year 4: families with a true edge (379 observations): mean Π^min / mean Π under S0 / mean Π^max | - | - | 379 | - | no | 0.333 / 0.648 / 0.706 |
| info | year 4: families with a true edge: the most cautious model is S0 / S1 / S2 / S3 / S4 / S5 (shares) | - | - | 379 | - | no | 0.00 / 0.01 / 0.00 / 0.00 / 0.79 / 0.20 |
| info | year 4: families with a true edge: share Statistically supported / share dormant, candidate (i) | - | - | 379 | - | no | 0.047 / 0.003 |
| info | year 4: posterior means under S0 of μ_A / τ_A / ψ / the classes' ρ (means over reviews) | - | - | 12 | - | no | 0.229 / 0.349 / 1.080 / 0.62, 0.63, 0.66 |
| cost | year 7: seconds for the six fits of a review (170 families) | 29.0168 | - | 12 | - | no | reported |
| info | year 7: common share r of the forward estimates' variance | 0.0671 | - | 12 | - | no | reported |
| info | year 7: families with a true edge (667 observations): mean Π^min / mean Π under S0 / mean Π^max | - | - | 667 | - | no | 0.381 / 0.771 / 0.796 |
| info | year 7: families with a true edge: the most cautious model is S0 / S1 / S2 / S3 / S4 / S5 (shares) | - | - | 667 | - | no | 0.00 / 0.00 / 0.00 / 0.00 / 0.52 / 0.47 |
| info | year 7: families with a true edge: share Statistically supported / share dormant, candidate (i) | - | - | 667 | - | no | 0.108 / 0.003 |
| info | year 7: posterior means under S0 of μ_A / τ_A / ψ / the classes' ρ (means over reviews) | - | - | 12 | - | no | 0.254 / 0.380 / 1.061 / 0.76, 0.75, 0.77 |
| cost | year 10: seconds for the six fits of a review (240 families) | 24.6687 | - | 12 | - | no | reported |
| info | year 10: common share r of the forward estimates' variance | 0.0684 | - | 12 | - | no | reported |
| info | year 10: families with a true edge (944 observations): mean Π^min / mean Π under S0 / mean Π^max | - | - | 944 | - | no | 0.364 / 0.813 / 0.827 |
| info | year 10: families with a true edge: the most cautious model is S0 / S1 / S2 / S3 / S4 / S5 (shares) | - | - | 944 | - | no | 0.00 / 0.00 / 0.00 / 0.01 / 0.32 / 0.67 |
| info | year 10: families with a true edge: share Statistically supported / share dormant, candidate (i) | - | - | 944 | - | no | 0.145 / 0.005 |
| info | year 10: posterior means under S0 of μ_A / τ_A / ψ / the classes' ρ (means over reviews) | - | - | 12 | - | no | 0.265 / 0.387 / 1.058 / 0.82, 0.79, 0.82 |
| cost | attention: reviews written per replication, candidate (i) (of 5080 family-reviews; a family dormant before and after a date needs none) | 4741.5833 | 4676.9698 to 4806.1969 | 12 | - | no | reported |
| cost | attention: share of the families with no edge of at least θ_min that are dormant at the end, candidate (i) | 0.1410 | 0.1110 to 0.1760 | 1936 | - | no | reported |
| info | year 2: families dormant after the review / reviews written / families evaluated (means), candidate (i) | - | - | 12 | - | no | 1.1 / 49.3 / 50.0 |
| info | year 4: families dormant after the review / reviews written / families evaluated (means), candidate (i) | - | - | 12 | - | no | 5.5 / 95.3 / 100.0 |
| info | year 7: families dormant after the review / reviews written / families evaluated (means), candidate (i) | - | - | 12 | - | no | 12.8 / 158.0 / 170.0 |
| info | year 10: families dormant after the review / reviews written / families evaluated (means), candidate (i) | - | - | 12 | - | no | 23.2 / 216.8 / 240.0 |
| cost | attention: reviews written per replication, candidate (ii) (of 5080 family-reviews; a family dormant before and after a date needs none) | 4740.9167 | 4676.3554 to 4805.4780 | 12 | - | no | reported |
| cost | attention: share of the families with no edge of at least θ_min that are dormant at the end, candidate (ii) | 0.1410 | 0.1110 to 0.1760 | 1936 | - | no | reported |
| info | dormancy rule | - | - | 12 | - | no | protocol-3.1-section-9.1-forward-record |
| cost | seconds per replication spent on the model (estimates, six fits at every review, forecasts) | 1428.3600 | - | 12 | - | no | reported |
| cost | of which the dormancy forecasts | 35.4375 | - | 12 | - | no | reported |
| cost | seconds for the six fits of a review, mean over every review | 34.7600 | - | 480 | - | no | reported |
| info | model | - | - | 12 | - | no | analytic-normal-normal-3.1 |

### D10 at HB: misspecified priors (12 of 400 replications)

| metric | what | estimate | 95% interval | n | threshold | required here | verdict |
|---|---|---|---|---|---|---|---|
| M12 | reviews not computed (a fit fails the grid gate), of 480 | 0.0000 | - | 480 | exactly 0 | yes | pilot: not decided (none so far) |
| fit | largest posterior mass on the ends of the grid of μ_A, any fit of any review | 0.0000 | - | 480 | gate: at most 0.01 | no | reported |
| info | review calendar | - | - | 12 | - | no | a review every 63 trading days (40 reviews a replication); M7 and M9 read at years 2, 4, 7, 10 |
| M7 | year 2: share with a true edge among families with Π^min ≥ 0.8 (1 family observations) | 1.0000 | 1.0000 to 1.0000 | 1 | - | no | reported |
| M7 | year 2: share with a true edge among families with Π^min ≥ 0.4 (7 family observations) | 0.7143 | 0.4000 to 1.0000 | 7 | - | no | reported |
| M7 | year 2: expected calibration error of the central model | 0.0142 | 0.0069 to 0.0209 | 600 | - | no | reported |
| M9 | year 2: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (22 obs.) | -0.2491 | -0.4850 to -0.0082 | 22 | - | no | reported |
| M9 | year 2: bias of the naive estimate, Promising or higher, candidate (i) | 1.1945 | 1.0030 to 1.3655 | 22 | - | no | reported |
| M9 | year 2: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (1 obs.) | 0.3675 | 0.3675 to 0.3675 | 1 | - | no | reported |
| M9 | year 2: bias of the naive estimate, Statistically supported or higher, candidate (i) | 1.0344 | 1.0344 to 1.0344 | 1 | - | no | reported |
| M9 | year 2: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (11 obs.) | -0.1451 | -0.5103 to 0.1633 | 11 | - | no | reported |
| M9 | year 2: bias of the naive estimate, Promising or higher, candidate (ii) | 1.2519 | 0.8870 to 1.5641 | 11 | - | no | reported |
| M9 | year 2: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (1 obs.) | 0.3675 | 0.3675 to 0.3675 | 1 | - | no | reported |
| M9 | year 2: bias of the naive estimate, Statistically supported or higher, candidate (ii) | 1.0344 | 1.0344 to 1.0344 | 1 | - | no | reported |
| M7 | year 4: share with a true edge among families with Π^min ≥ 0.8 (6 family observations) | 1.0000 | 1.0000 to 1.0000 | 6 | lower bound ≥ 0.7 | yes | not evaluated: fewer than 200 observations |
| M7 | year 4: share with a true edge among families with Π^min ≥ 0.4 (21 family observations) | 0.7143 | 0.5600 to 0.9231 | 21 | lower bound ≥ 0.3 | yes | not evaluated: fewer than 200 observations |
| M7 | year 4: expected calibration error of the central model | 0.0082 | 0.0012 to 0.0143 | 1200 | upper bound ≤ 0.1 | yes | pilot: not decided (within threshold so far) |
| M9 | year 4: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (39 obs.) | -0.1547 | -0.3714 to 0.0819 | 39 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 4: bias of the naive estimate, Promising or higher, candidate (i) | 0.9910 | 0.8356 to 1.1511 | 39 | - | no | reported |
| M9 | year 4: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (4 obs.) | -0.0182 | -0.5582 to 0.2845 | 4 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 4: bias of the naive estimate, Statistically supported or higher, candidate (i) | 0.6940 | -0.0652 to 1.2156 | 4 | - | no | reported |
| M9 | year 4: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (31 obs.) | -0.1710 | -0.4431 to 0.1085 | 31 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 4: bias of the naive estimate, Promising or higher, candidate (ii) | 0.9087 | 0.6703 to 1.1163 | 31 | - | no | reported |
| M9 | year 4: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (3 obs.) | 0.1617 | 0.0250 to 0.2845 | 3 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 4: bias of the naive estimate, Statistically supported or higher, candidate (ii) | 0.9471 | 0.5462 to 1.2156 | 3 | - | no | reported |
| M7 | year 7: share with a true edge among families with Π^min ≥ 0.8 (13 family observations) | 0.9231 | 0.7273 to 1.0000 | 13 | - | no | reported |
| M7 | year 7: share with a true edge among families with Π^min ≥ 0.4 (42 family observations) | 0.7857 | 0.6389 to 0.9063 | 42 | - | no | reported |
| M7 | year 7: expected calibration error of the central model | 0.0044 | 0.0003 to 0.0092 | 2040 | - | no | reported |
| M9 | year 7: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (67 obs.) | 0.0223 | -0.1226 to 0.1653 | 67 | - | no | reported |
| M9 | year 7: bias of the naive estimate, Promising or higher, candidate (i) | 1.0196 | 0.8565 to 1.1920 | 67 | - | no | reported |
| M9 | year 7: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (14 obs.) | -0.2769 | -0.4210 to -0.1001 | 14 | - | no | reported |
| M9 | year 7: bias of the naive estimate, Statistically supported or higher, candidate (i) | 0.4562 | 0.2280 to 0.7273 | 14 | - | no | reported |
| M9 | year 7: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (58 obs.) | 0.0454 | -0.1081 to 0.1938 | 58 | - | no | reported |
| M9 | year 7: bias of the naive estimate, Promising or higher, candidate (ii) | 0.9802 | 0.8049 to 1.1616 | 58 | - | no | reported |
| M9 | year 7: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (14 obs.) | -0.2769 | -0.4210 to -0.1001 | 14 | - | no | reported |
| M9 | year 7: bias of the naive estimate, Statistically supported or higher, candidate (ii) | 0.4562 | 0.2280 to 0.7273 | 14 | - | no | reported |
| M7 | year 10: share with a true edge among families with Π^min ≥ 0.8 (28 family observations) | 0.7500 | 0.5667 to 0.9091 | 28 | lower bound ≥ 0.7 | yes | not evaluated: fewer than 200 observations |
| M7 | year 10: share with a true edge among families with Π^min ≥ 0.4 (60 family observations) | 0.7667 | 0.6667 to 0.8727 | 60 | lower bound ≥ 0.3 | yes | not evaluated: fewer than 200 observations |
| M7 | year 10: expected calibration error of the central model | 0.0030 | 0.0001 to 0.0073 | 2880 | upper bound ≤ 0.1 | yes | pilot: not decided (within threshold so far) |
| M9 | year 10: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (94 obs.) | 0.1155 | 0.0272 to 0.1993 | 94 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 10: bias of the naive estimate, Promising or higher, candidate (i) | 0.9384 | 0.8617 to 1.0119 | 94 | - | no | reported |
| M9 | year 10: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (31 obs.) | 0.1151 | -0.0237 to 0.2920 | 31 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 10: bias of the naive estimate, Statistically supported or higher, candidate (i) | 0.6705 | 0.4693 to 0.9225 | 31 | - | no | reported |
| M9 | year 10: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (86 obs.) | 0.1262 | 0.0298 to 0.2340 | 86 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 10: bias of the naive estimate, Promising or higher, candidate (ii) | 0.9087 | 0.8121 to 1.0062 | 86 | - | no | reported |
| M9 | year 10: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (31 obs.) | 0.1151 | -0.0237 to 0.2920 | 31 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 10: bias of the naive estimate, Statistically supported or higher, candidate (ii) | 0.6705 | 0.4693 to 0.9225 | 31 | - | no | reported |
| M8 | premature elimination: families with a true edge that end dormant, candidate (i) | 0.0488 | 0.0161 to 0.0862 | 123 | upper bound ≤ 0.1 | yes | pilot: not decided (within threshold so far) |
| info | at the end, candidate (i): passed screening / Promising / supported / dormant (means) | - | - | 12 | - | no | 11.8 / 7.8 / 2.6 / 69.7 |
| M8 | premature elimination: families with a true edge that end dormant, candidate (ii) | 0.0488 | 0.0161 to 0.0862 | 123 | upper bound ≤ 0.1 | yes | pilot: not decided (within threshold so far) |
| info | at the end, candidate (ii): passed screening / Promising / supported / dormant (means) | - | - | 12 | - | no | 6.1 / 7.2 / 2.6 / 69.7 |
| cost | seconds per replication | 993.4083 | - | 12 | - | no | reported |
| cost | year 2: seconds for the six fits of a review (50 families) | 32.8655 | - | 12 | - | no | reported |
| info | year 2: common share r of the forward estimates' variance | 0.0699 | - | 12 | - | no | reported |
| info | year 2: families with a true edge (27 observations): mean Π^min / mean Π under S0 / mean Π^max | - | - | 27 | - | no | 0.206 / 0.356 / 0.477 |
| info | year 2: families with a true edge: the most cautious model is S0 / S1 / S2 / S3 / S4 / S5 (shares) | - | - | 27 | - | no | 0.00 / 0.37 / 0.00 / 0.00 / 0.59 / 0.04 |
| info | year 2: families with a true edge: share Statistically supported / share dormant, candidate (i) | - | - | 27 | - | no | 0.037 / 0.000 |
| info | year 2: posterior means under S0 of μ_A / τ_A / ψ / the classes' ρ (means over reviews) | - | - | 12 | - | no | -0.243 / 0.145 / 1.087 / 0.40, 0.43, 0.42 |
| cost | year 4: seconds for the six fits of a review (100 families) | 21.4133 | - | 12 | - | no | reported |
| info | year 4: common share r of the forward estimates' variance | 0.0673 | - | 12 | - | no | reported |
| info | year 4: families with a true edge (55 observations): mean Π^min / mean Π under S0 / mean Π^max | - | - | 55 | - | no | 0.299 / 0.485 / 0.580 |
| info | year 4: families with a true edge: the most cautious model is S0 / S1 / S2 / S3 / S4 / S5 (shares) | - | - | 55 | - | no | 0.00 / 0.13 / 0.00 / 0.00 / 0.65 / 0.22 |
| info | year 4: families with a true edge: share Statistically supported / share dormant, candidate (i) | - | - | 55 | - | no | 0.073 / 0.000 |
| info | year 4: posterior means under S0 of μ_A / τ_A / ψ / the classes' ρ (means over reviews) | - | - | 12 | - | no | -0.270 / 0.105 / 1.060 / 0.48, 0.51, 0.50 |
| cost | year 7: seconds for the six fits of a review (170 families) | 15.5469 | - | 12 | - | no | reported |
| info | year 7: common share r of the forward estimates' variance | 0.0694 | - | 12 | - | no | reported |
| info | year 7: families with a true edge (88 observations): mean Π^min / mean Π under S0 / mean Π^max | - | - | 88 | - | no | 0.328 / 0.540 / 0.600 |
| info | year 7: families with a true edge: the most cautious model is S0 / S1 / S2 / S3 / S4 / S5 (shares) | - | - | 88 | - | no | 0.00 / 0.01 / 0.02 / 0.00 / 0.58 / 0.39 |
| info | year 7: families with a true edge: share Statistically supported / share dormant, candidate (i) | - | - | 88 | - | no | 0.159 / 0.023 |
| info | year 7: posterior means under S0 of μ_A / τ_A / ψ / the classes' ρ (means over reviews) | - | - | 12 | - | no | -0.268 / 0.073 / 1.055 / 0.56, 0.57, 0.57 |
| cost | year 10: seconds for the six fits of a review (240 families) | 13.0120 | - | 12 | - | no | reported |
| info | year 10: common share r of the forward estimates' variance | 0.0689 | - | 12 | - | no | reported |
| info | year 10: families with a true edge (123 observations): mean Π^min / mean Π under S0 / mean Π^max | - | - | 123 | - | no | 0.340 / 0.591 / 0.647 |
| info | year 10: families with a true edge: the most cautious model is S0 / S1 / S2 / S3 / S4 / S5 (shares) | - | - | 123 | - | no | 0.00 / 0.03 / 0.01 / 0.00 / 0.42 / 0.54 |
| info | year 10: families with a true edge: share Statistically supported / share dormant, candidate (i) | - | - | 123 | - | no | 0.211 / 0.041 |
| info | year 10: posterior means under S0 of μ_A / τ_A / ψ / the classes' ρ (means over reviews) | - | - | 12 | - | no | -0.258 / 0.065 / 1.054 / 0.60, 0.60, 0.60 |
| cost | attention: reviews written per replication, candidate (i) (of 5080 family-reviews; a family dormant before and after a date needs none) | 4012.5833 | 3854.4433 to 4170.7233 | 12 | - | no | reported |
| cost | attention: share of the families with no edge of at least θ_min that are dormant at the end, candidate (i) | 0.3014 | 0.2623 to 0.3423 | 2757 | - | no | reported |
| info | year 2: families dormant after the review / reviews written / families evaluated (means), candidate (i) | - | - | 12 | - | no | 3.3 / 47.3 / 50.0 |
| info | year 4: families dormant after the review / reviews written / families evaluated (means), candidate (i) | - | - | 12 | - | no | 17.1 / 85.2 / 100.0 |
| info | year 7: families dormant after the review / reviews written / families evaluated (means), candidate (i) | - | - | 12 | - | no | 41.7 / 132.0 / 170.0 |
| info | year 10: families dormant after the review / reviews written / families evaluated (means), candidate (i) | - | - | 12 | - | no | 69.7 / 170.3 / 240.0 |
| cost | attention: reviews written per replication, candidate (ii) (of 5080 family-reviews; a family dormant before and after a date needs none) | 4013.0833 | 3854.9730 to 4171.1937 | 12 | - | no | reported |
| cost | attention: share of the families with no edge of at least θ_min that are dormant at the end, candidate (ii) | 0.3014 | 0.2623 to 0.3423 | 2757 | - | no | reported |
| info | dormancy rule | - | - | 12 | - | no | protocol-3.1-section-9.1-forward-record |
| cost | seconds per replication spent on the model (estimates, six fits at every review, forecasts) | 969.1883 | - | 12 | - | no | reported |
| cost | of which the dormancy forecasts | 39.9442 | - | 12 | - | no | reported |
| cost | seconds for the six fits of a review, mean over every review | 23.1666 | - | 480 | - | no | reported |
| info | model | - | - | 12 | - | no | analytic-normal-normal-3.1 |

### Dormancy under Protocol 3.1 §9.1: what it retires and what it leaves to review (candidate (i))

Premature elimination is M8 (bound 0.10 on the upper end of the interval). The other columns have no threshold: they are the attention the rule saves. A review is written for every family that is not dormant both before and after a review. **The small-sample interval** beside M8 is the one to read on a pilot: the same estimate with the delete-one-replication jackknife and a Student-t quantile, and, where no replication retired a family, the exact bound over replications, `1 − 0.025^(1/R)` (`manhattan.sim.cluster_ci`). "0.000 (0.000 to 0.000)" in the pre-registered form means no event in the replications run, not a rate of zero.

| scenario | replications | families with a true edge | retired | premature elimination (M8), pre-registered interval | **the same, small-sample interval** | families with no edge dormant at the end | families dormant at the end, of 240 | reviews written per replication | family-reviews per replication |
|---|---|---|---|---|---|---|---|---|---|
| D01 | 12 | 0 | - | - (no family has an edge) | - | 0.180 (0.137 to 0.220) | 43.2 (32.7 to 53.8) | 4442.2 (4315.5 to 4569.0) | 5080 |
| D02 | 12 | 42 | 0 | 0.000 (0.000 to 0.000) | **0.000 (0.000 to 0.265)** | 0.127 (0.106 to 0.153) | 30.0 (24.1 to 35.9) | 4684.2 (4604.6 to 4763.8) | 5080 |
| D05 | 12 | 140 | 2 | 0.014 (0.000 to 0.035) | **0.014 (0.000 to 0.036)** | 0.124 (0.085 to 0.167) | 28.5 (18.4 to 38.6) | 4630.4 (4514.6 to 4746.3) | 5080 |
| D08 | 12 | 944 | 5 | 0.005 (0.001 to 0.010) | **0.005 (0.000 to 0.011)** | 0.141 (0.111 to 0.176) | 23.2 (18.0 to 28.4) | 4741.6 (4677.0 to 4806.2) | 5080 |
| D10 | 12 | 123 | 6 | 0.049 (0.016 to 0.086) | **0.049 (0.007 to 0.090)** | 0.301 (0.262 to 0.342) | 69.7 (59.7 to 79.7) | 4012.6 (3854.4 to 4170.7) | 5080 |

### Who reaches Statistically supported, by true Sharpe ratio (candidate (i); reported, no threshold)

Among the families with a true edge that were frozen before the date, the share that held the tier at that date or an earlier one. The Sharpe ratio is the true one of the family portfolio, hedged and net. Entry needs Π^min ≥ 0.80 (the most cautious of six models), a positive forward mean, 504 forward days (252 if Romano-Wolf named a variant on the reserve) and the tier Promising. A dormant family is not evaluated. Each cell: the share, its 95% interval over replications, and the number of families it rests on; a cell with few families says little.

**D01: no edges** (12 replications): no family has an edge.

**D02: rare edges** (12 replications)

| true Sharpe ratio | by year 2 | by year 4 | by year 7 | by year 10 |
|---|---|---|---|---|
| 0.25 to 0.5 | 0.00 (0.00 to 0.00), 1 | 0.00 (0.00 to 0.00), 2 | 0.00 (0.00 to 0.00), 3 | 0.00 (0.00 to 0.00), 7 |
| 0.5 to 0.75 | 0.00 (0.00 to 0.00), 2 | 0.00 (0.00 to 0.00), 5 | 0.00 (0.00 to 0.00), 10 | 0.00 (0.00 to 0.00), 16 |
| 0.75 to 1 | 0.00 (0.00 to 0.00), 4 | 0.00 (0.00 to 0.00), 8 | 0.00 (0.00 to 0.00), 11 | 0.00 (0.00 to 0.00), 12 |
| 1 to 1.5 | 0.00 (0.00 to 0.00), 1 | 0.00 (0.00 to 0.00), 3 | 0.00 (0.00 to 0.00), 4 | 0.00 (0.00 to 0.00), 7 |
| 1.5 and above | - | - | - | - |
| all with a true edge | 0.00 (0.00 to 0.00), 8 | 0.00 (0.00 to 0.00), 18 | 0.00 (0.00 to 0.00), 28 | 0.00 (0.00 to 0.00), 42 |

**D05: fat tails** (12 replications)

| true Sharpe ratio | by year 2 | by year 4 | by year 7 | by year 10 |
|---|---|---|---|---|
| 0.25 to 0.5 | 0.00 (0.00 to 0.00), 7 | 0.00 (0.00 to 0.00), 13 | 0.00 (0.00 to 0.00), 24 | 0.00 (0.00 to 0.00), 33 |
| 0.5 to 0.75 | 0.00 (0.00 to 0.00), 5 | 0.00 (0.00 to 0.00), 12 | 0.00 (0.00 to 0.00), 31 | 0.00 (0.00 to 0.00), 48 |
| 0.75 to 1 | 0.00 (0.00 to 0.00), 8 | 0.00 (0.00 to 0.00), 11 | 0.00 (0.00 to 0.00), 19 | 0.03 (0.00 to 0.09), 32 |
| 1 to 1.5 | 0.00 (0.00 to 0.00), 4 | 0.07 (0.00 to 0.23), 14 | 0.19 (0.00 to 0.40), 16 | 0.27 (0.06 to 0.52), 22 |
| 1.5 and above | - | 0.00 (0.00 to 0.00), 1 | 0.67 (0.00 to 1.00), 3 | 0.80 (0.25 to 1.00), 5 |
| all with a true edge | 0.00 (0.00 to 0.00), 24 | 0.02 (0.00 to 0.06), 51 | 0.05 (0.02 to 0.09), 93 | 0.08 (0.04 to 0.13), 140 |

**D08: historical selection bias** (12 replications)

| true Sharpe ratio | by year 2 | by year 4 | by year 7 | by year 10 |
|---|---|---|---|---|
| 0.25 to 0.5 | 0.00 (0.00 to 0.00), 17 | 0.00 (0.00 to 0.00), 42 | 0.00 (0.00 to 0.00), 75 | 0.02 (0.00 to 0.06), 107 |
| 0.5 to 0.75 | 0.00 (0.00 to 0.00), 29 | 0.00 (0.00 to 0.00), 70 | 0.03 (0.00 to 0.08), 126 | 0.04 (0.00 to 0.09), 184 |
| 0.75 to 1 | 0.00 (0.00 to 0.00), 67 | 0.00 (0.00 to 0.00), 125 | 0.05 (0.00 to 0.12), 220 | 0.10 (0.03 to 0.19), 290 |
| 1 to 1.5 | 0.02 (0.00 to 0.06), 59 | 0.10 (0.04 to 0.16), 125 | 0.21 (0.10 to 0.31), 217 | 0.34 (0.23 to 0.43), 325 |
| 1.5 and above | 0.00 (0.00 to 0.00), 10 | 0.29 (0.12 to 0.50), 17 | 0.59 (0.33 to 0.81), 29 | 0.71 (0.52 to 0.91), 38 |
| all with a true edge | 0.01 (0.00 to 0.02), 182 | 0.05 (0.02 to 0.07), 379 | 0.12 (0.06 to 0.18), 667 | 0.19 (0.11 to 0.26), 944 |

**D10: misspecified priors** (12 replications)

| true Sharpe ratio | by year 2 | by year 4 | by year 7 | by year 10 |
|---|---|---|---|---|
| 0.25 to 0.5 | 0.00 (0.00 to 0.00), 8 | 0.00 (0.00 to 0.00), 19 | 0.00 (0.00 to 0.00), 32 | 0.00 (0.00 to 0.00), 46 |
| 0.5 to 0.75 | 0.00 (0.00 to 0.00), 1 | 0.00 (0.00 to 0.00), 1 | 0.00 (0.00 to 0.00), 1 | 0.00 (0.00 to 0.00), 2 |
| 0.75 to 1 | 0.00 (0.00 to 0.00), 3 | 0.00 (0.00 to 0.00), 6 | 0.00 (0.00 to 0.00), 14 | 0.06 (0.00 to 0.20), 17 |
| 1 to 1.5 | 0.07 (0.00 to 0.27), 14 | 0.12 (0.00 to 0.30), 25 | 0.25 (0.11 to 0.42), 36 | 0.43 (0.30 to 0.56), 49 |
| 1.5 and above | 0.00 (0.00 to 0.00), 1 | 0.25 (0.00 to 1.00), 4 | 1.00 (1.00 to 1.00), 5 | 0.89 (0.50 to 1.00), 9 |
| all with a true edge | 0.04 (0.00 to 0.15), 27 | 0.07 (0.02 to 0.14), 55 | 0.16 (0.09 to 0.24), 88 | 0.24 (0.15 to 0.34), 123 |


## 3. Cost of the whole development programme under version 2

Replications still to run times the seconds per replication on file (one core). Seconds measured while more jobs than cores were running are too high; the runbook gives timings on an idle core.

| part | runs | replications still to run | runs with a timing | CPU-hours |
|---|---|---|---|---|
| version 1 code: STD and LONG scenarios other than D11 | 17 | 33808 | 17 of 17 | 1189 |
| version 2 code: D11, full pipeline with the hedge-aware SPA test | 1 | 1964 | 1 of 1 | 204 |
| version 2 code: nine hedged twins, SPA only | 9 | 3546 | 9 of 9 | 301 |
| version 2 code: HB scenarios, analytic model | 5 | 1940 | 5 of 5 | 508 |
| **all development runs** | 32 | 41258 | | **2202** |

The six fits of one review took 21.7 seconds on average over 2400 reviews (so 3.62 seconds a fit), and the model's share of a replication 909 seconds. The sampled model of 3.0 did not finish one replication in 2 hours 31 minutes of CPU time at a fifth of its budget.

## 4. The adaptive channel on the reserve: the evidence on file

Version 1's pilot of D09b (12 replications): the SPA test recomputed on the full set after three adaptive rounds on the reserve rejects **0.3435 (0.3075 to 0.3796)** of families with no edge at the 0.05 level. This is the evidence Protocol 3.1 §5.3 cites for the rule that adaptive-channel families carry zero evidential weight on the reserve. The rule is enforced by `tests/test_manhattan_adaptive_weight.py` (criterion V14); D09b itself is unchanged by version 2 and is decided, with V10(b), on the full run.

## Readings of SIM_PREREG_v2.md

Every place where the code had to fix a detail the text leaves open.

- **Seeds and worlds.** Version 1's master seed and stream keys, so D11 and the HB scenarios are the worlds version 1 drew. A twin draws from its version 1 scenario's streams: its true hedged returns are those of that scenario's version 1 run, and its oracle column reproduces that run's SPA counts replication by replication.
- **D11 and the twins: the hedge layer.** One core factor for the whole programme (daily volatility 1, annualised Sharpe ratio 0.6); one β path per hypothesis, a random walk from 0.5 with annual standard deviation 0.3; hedge cost 0; no hedge in a family's first 252 days. The unhedged returns are rebuilt from the same random streams the world used; a test checks that hedging them reproduces the family's returns exactly.
- **Hedge-aware SPA (Protocol 3.1 §5.1).** The pseudo-series of a resample is the 756 actual days before the reserve window followed by the resampled window. Each family's three tests (hedge-aware, 3.0 on the estimated hedge, 3.0 on the true hedged returns) start from the same generator state, so they see the same block draws; the number of resamples (999, then 9,999 when p ≤ 0.10) is decided by each test's own p-value.
- **Twins.** The three SPA tests and Romano-Wolf at 0.05 only: no screening, no forward test (those belong to the version 1 scenario). D09a and D09b have no twin.
- **HB: estimates.** Annualised sample Sharpe ratios of the family portfolio on the reserve window and on the forward record (63 forward days at least). Standard errors from a joint stationary bootstrap per batch (199 resamples).
- **HB: the common share r.** For every pair of families with a forward estimate, the sample correlation of the two forward return series over common dates times the number of common dates over the geometric mean of the two lengths; r is the average over pairs, floored at 0. It is the only dependence between families the model is given.
- **HB: mechanism classes.** Three classes assigned at random at freeze (the truth has none).
- **HB: when a fit is used.** At most 1% of the posterior mass of μ_A on the two end nodes of its grid; a review needs all six fits. There is no sampler and no convergence diagnostic.
- **HB: dormancy forecast.** Version 1's normal-update approximation (no refit), fed with 200 draws of θ_f per family and model from the closed-form posterior; not evaluated at the last date.
- **HB: dormancy rule.** Protocol 3.1 §9.1 (the forward-record rule, a pre-adoption change): dormant when the forecast PP^max and the one-sided p-value p^F of the family's own forward record against an edge of θ_min are both below 0.05 at two consecutive reviews (p^F is 1 until the family has 252 forward days); reactivated when either is at least 0.15. p^F is computed from the forward Sharpe estimate and standard error handed to the model. At the last review there is no forecast, so no family becomes dormant there; a dormant family is reactivated there if p^F ≥ 0.15. A review is "written" for every family that is not dormant both before and after the review.
- **HB: who reaches Statistically supported.** A family counts from the first review at which it holds the tier, whether or not it leaves later. Its true Sharpe ratio is that of the family portfolio over its forward life (SIM_PREREG section 2.4). The table reads the state at years 2, 4, 7 and 10.
- **HB: review dates.** Every 63 trading days, 40 reviews (SIM_PREREG_v2 amendment 1: the cadence production uses, in place of version 1's four dates). M7 and M9 are read at years 2, 4, 7 and 10; M12 is counted over all 40 reviews; M8 is the state after the last. Consecutive reviews are a quarter apart. Records made with any other step are refused.
- **HB: naive estimate (M9).** Version 1's: the largest sample Sharpe ratio among the family's variants, each over all its data up to the evaluation date.
- **Timing.** Seconds are wall-clock per replication inside a worker and are inflated whenever more jobs than cores run at once.

## Runs of the changed parts on record

From `results/manhattan_sim/runs.jsonl`: every run made with `--prereg v2`, and every note written during this revision (a start with no end is an abandoned run).

| time (UTC) | run | event | scenario | size | label | replications | status | commit | v2 hash |
|---|---|---|---|---|---|---|---|---|---|
| 2026-11-12T15:01:00Z | 5d91c1ab5300 | start | D01 | HB | pilot | 0/12 | started | `d046e2a` | `67707330` |
| 2026-11-12T15:04:44Z | 5d91c1ab5300 | end | D01 | HB | pilot | 12/12 | completed | `d046e2a` | `67707330` |
| 2026-11-12T15:04:45Z | 971ddabe2e45 | start | D02 | HB | pilot | 0/12 | started | `d046e2a` | `67707330` |
| 2026-11-12T15:09:21Z | 971ddabe2e45 | end | D02 | HB | pilot | 12/12 | completed | `d046e2a` | `67707330` |
| 2026-11-12T15:09:22Z | 0398140eaa7d | start | D05 | HB | pilot | 0/12 | started | `d046e2a` | `67707330` |
| 2026-11-12T15:13:03Z | ad59d7770757 | start | D11 | STD | pilot | 0/36 | started | `d046e2a` | `67707330` |
| 2026-11-12T16:11:22Z | ad59d7770757 | end | D11 | STD | pilot | 36/36 | completed | `d046e2a` | `67707330` |
| 2026-11-12T16:11:34Z | 9e0e43a40f93 | start | D05h | STD | pilot | 0/6 | started | `d046e2a` | `67707330` |
| 2026-11-12T16:20:32Z | 9e0e43a40f93 | end | D05h | STD | pilot | 6/6 | completed | `d046e2a` | `67707330` |
| 2026-11-12T16:20:33Z | bd9f6f7f18e2 | start | D07ah | STD | pilot | 0/6 | started | `d046e2a` | `67707330` |
| 2026-11-12T16:31:32Z | bd9f6f7f18e2 | end | D07ah | STD | pilot | 6/6 | completed | `d046e2a` | `67707330` |
| 2026-11-12T16:31:33Z | c383bf24b6a0 | start | D03h | STD | pilot | 0/6 | started | `d046e2a` | `67707330` |
| 2026-11-12T16:41:37Z | c383bf24b6a0 | end | D03h | STD | pilot | 6/6 | completed | `d046e2a` | `67707330` |
| 2026-11-12T16:41:38Z | 6878b7704297 | start | D06h | STD | pilot | 0/6 | started | `d046e2a` | `67707330` |
| 2026-11-12T16:50:19Z | 6878b7704297 | end | D06h | STD | pilot | 6/6 | completed | `d046e2a` | `67707330` |
| 2026-11-12T16:50:20Z | bd6caadd5ad0 | start | D08h | STD | pilot | 0/6 | started | `d046e2a` | `67707330` |
| 2026-11-12T17:10:04Z | bd6caadd5ad0 | end | D08h | STD | pilot | 6/6 | completed | `d046e2a` | `67707330` |
| 2026-11-12T17:10:04Z | c009e681fde3 | start | D04h | STD | pilot | 0/6 | started | `d046e2a` | `67707330` |
| 2026-11-12T17:17:13Z | c009e681fde3 | end | D04h | STD | pilot | 6/6 | completed | `d046e2a` | `67707330` |
| 2026-11-12T17:17:14Z | 98ae6456ae63 | start | D07bh | STD | pilot | 0/6 | started | `d046e2a` | `67707330` |
| 2026-11-12T17:25:22Z | 98ae6456ae63 | end | D07bh | STD | pilot | 6/6 | completed | `d046e2a` | `67707330` |
| 2026-11-12T17:25:22Z | 6d8b09c66e33 | start | D01h | STD | pilot | 0/6 | started | `d046e2a` | `67707330` |
| 2026-11-12T17:34:56Z | 6d8b09c66e33 | end | D01h | STD | pilot | 6/6 | completed | `d046e2a` | `67707330` |
| 2026-11-12T17:34:57Z | f83e62a9fb6f | start | D02h | STD | pilot | 0/6 | started | `d046e2a` | `67707330` |
| 2026-11-12T17:44:27Z | f83e62a9fb6f | end | D02h | STD | pilot | 6/6 | completed | `d046e2a` | `67707330` |
| 2026-11-12T17:44:28Z | 18ddf07d6aa9 | start | D01 | HB | pilot | 0/12 | started | `8ba5b3a` | `67707330` |
| 2026-11-12T17:48:07Z | 18ddf07d6aa9 | end | D01 | HB | pilot | 12/12 | completed | `8ba5b3a` | `67707330` |
| 2026-11-12T17:48:08Z | 59e64b5cc1f9 | start | D02 | HB | pilot | 0/12 | started | `8ba5b3a` | `67707330` |
| 2026-11-12T17:52:05Z | 59e64b5cc1f9 | end | D02 | HB | pilot | 12/12 | completed | `8ba5b3a` | `67707330` |
| 2026-11-12T17:52:06Z | 2fd94f28390c | start | D05 | HB | pilot | 0/12 | started | `8ba5b3a` | `67707330` |
| 2026-11-12T17:56:39Z | 2fd94f28390c | end | D05 | HB | pilot | 12/12 | completed | `8ba5b3a` | `67707330` |
| 2026-11-12T17:56:40Z | 57bb4e9fab20 | start | D08 | HB | pilot | 0/12 | started | `8ba5b3a` | `67707330` |
| 2026-11-12T18:04:37Z | 57bb4e9fab20 | end | D08 | HB | pilot | 12/12 | completed | `8ba5b3a` | `67707330` |
| 2026-11-12T18:04:38Z | 9a14591faac1 | start | D10 | HB | pilot | 0/12 | started | `8ba5b3a` | `67707330` |
| 2026-11-12T18:09:07Z | 9a14591faac1 | end | D10 | HB | pilot | 12/12 | completed | `8ba5b3a` | `67707330` |
| 2026-11-12T18:09:24Z | note-5M-01 | note | D11 | STD | development | 40/40 | note | `b0ec9c3` (dirty) | `67707330` |
| 2026-11-12T18:09:24Z | note-5M-02 | note | D11 | STD | development | 12/12 | note | `b0ec9c3` (dirty) | `67707330` |
| 2026-11-12T18:09:24Z | note-5M-03 | note | D01,D02,D05,D08,D10 | HB | development | 20/20 | note | `b0ec9c3` (dirty) | `67707330` |
| 2026-11-12T23:18:37Z | 9e0b73ea7505 | start | D01 | HB | pilot | 0/12 | started | `9b1f068` | `77496b2f` |
| 2026-11-12T23:22:09Z | 9e0b73ea7505 | end | D01 | HB | pilot | 12/12 | completed | `9b1f068` | `77496b2f` |
| 2026-11-12T23:22:09Z | e8ebeba718f3 | start | D02 | HB | pilot | 0/12 | started | `9b1f068` | `77496b2f` |
| 2026-11-12T23:25:50Z | e8ebeba718f3 | end | D02 | HB | pilot | 12/12 | completed | `9b1f068` | `77496b2f` |
| 2026-11-12T23:25:50Z | 2b3b7fe9ba21 | start | D05 | HB | pilot | 0/12 | started | `9b1f068` | `77496b2f` |
| 2026-11-12T23:29:54Z | 2b3b7fe9ba21 | end | D05 | HB | pilot | 12/12 | completed | `9b1f068` | `77496b2f` |
| 2026-11-12T23:29:54Z | 6f44098d637b | start | D08 | HB | pilot | 0/12 | started | `9b1f068` | `77496b2f` |
| 2026-11-12T23:37:29Z | 6f44098d637b | end | D08 | HB | pilot | 12/12 | completed | `9b1f068` | `77496b2f` |
| 2026-11-12T23:37:29Z | 763f0b2fbc9d | start | D10 | HB | pilot | 0/12 | started | `9b1f068` | `77496b2f` |
| 2026-11-12T23:41:40Z | 763f0b2fbc9d | end | D10 | HB | pilot | 12/12 | completed | `9b1f068` | `77496b2f` |
| 2026-11-13T00:24:25Z | note-6M-01 | note | D02,D05,D08,D10 | HB | development | 48/48 | note | `b5e64c3` | `77496b2f` |
| 2026-11-13T00:24:25Z | note-6M-02 | note | D02,D05,D08,D10 | HB | development | 48/48 | note | `b5e64c3` | `77496b2f` |
| 2026-11-13T00:24:25Z | note-6M-03 | note | D02,D05,D08,D10 | HB | development | 48/48 | note | `b5e64c3` | `77496b2f` |
| 2026-11-13T00:24:25Z | note-6M-04 | note | D02,D05,D08,D10 | HB | development | 48/48 | note | `9b1f068` (dirty) | `77496b2f` |
| 2026-11-13T02:01:48Z | note-6Mb-01 | note | D02,D05,D08,D10 | HB | development | 48/48 | note | `c914421` (dirty) | `77496b2f` |
| 2026-11-13T02:01:48Z | note-6Mb-02 | note | D02,D05,D08,D10 | HB | development | 96/96 | note | `c914421` (dirty) | `77496b2f` |
| 2026-11-13T02:01:48Z | note-6Mb-03 | note | none | STD | development | 0/0 | note | `c914421` (dirty) | `77496b2f` |
| 2026-11-13T02:01:48Z | note-6Mb-04 | note | D02,D08,D11,D05h | STD | development | 20/20 | note | `c914421` (dirty) | `77496b2f` |
| 2026-11-13T02:01:48Z | note-6Mb-05 | note | D02,D10 | HB | development | 54/54 | note | `c914421` (dirty) | `77496b2f` |
| 2026-11-13T11:14:00Z | note-10M-01 | note | D08 | HB | development | 12/12 | note | `02f3c0e` (dirty) | `db980490` |
| 2026-11-13T11:18:54Z | 324840ecc1b1 | start | D01 | HB | pilot | 0/6 | started | `8bcfd72` | `65c19e68` |
| 2026-11-13T11:39:51Z | 324840ecc1b1 | end | D01 | HB | pilot | 6/6 | completed | `8bcfd72` | `65c19e68` |
| 2026-11-13T11:39:52Z | e386ab2988f8 | start | D02 | HB | pilot | 0/6 | started | `8bcfd72` | `65c19e68` |
| 2026-11-13T12:02:48Z | e386ab2988f8 | end | D02 | HB | pilot | 6/6 | completed | `8bcfd72` | `65c19e68` |
| 2026-11-13T12:02:49Z | 56b789f676ba | start | D05 | HB | pilot | 0/6 | started | `8bcfd72` | `65c19e68` |
| 2026-11-13T12:30:54Z | 9e227e84eed4 | start | D10 | HB | pilot | 0/6 | started | `90bb59f` | `65c19e68` |
| 2026-11-13T12:33:24Z | 56b789f676ba | end | D05 | HB | pilot | 6/6 | completed | `8bcfd72` | `65c19e68` |
| 2026-11-13T12:33:25Z | 78a4ce38ac9e | start | D08 | HB | pilot | 0/6 | started | `8bcfd72` | `65c19e68` |
| 2026-11-13T13:27:50Z | 78a4ce38ac9e | end | D08 | HB | pilot | 6/6 | completed | `8bcfd72` | `65c19e68` |
| 2026-11-13T13:27:51Z | 369c3b8bef4c | start | D10 | HB | pilot | 0/6 | started | `8bcfd72` | `65c19e68` |
| 2026-11-13T14:00:05Z | 369c3b8bef4c | end | D10 | HB | pilot | 6/6 | completed | `8bcfd72` | `65c19e68` |
| 2026-11-13T14:00:07Z | 2e0c1c211095 | start | D01 | HB | pilot | 0/6 | started | `8bcfd72` | `65c19e68` |
| 2026-11-13T14:18:50Z | 9e227e84eed4 | end | D10 | HB | pilot | 6/6 | completed | `90bb59f` | `65c19e68` |
| 2026-11-13T14:18:51Z | ac7b97af4527 | start | D08 | HB | pilot | 0/3 | started | `90bb59f` | `65c19e68` |
| 2026-11-13T14:25:51Z | 2e0c1c211095 | end | D01 | HB | pilot | 6/6 | completed | `8bcfd72` | `65c19e68` |
| 2026-11-13T14:25:52Z | a7fc1d188cef | start | D02 | HB | pilot | 0/6 | started | `8bcfd72` | `65c19e68` |
| 2026-11-13T14:54:53Z | a7fc1d188cef | end | D02 | HB | pilot | 6/6 | completed | `8bcfd72` | `65c19e68` |
| 2026-11-13T14:54:54Z | 5d837fc3582f | start | D05 | HB | pilot | 0/6 | started | `8bcfd72` | `65c19e68` |
| 2026-11-13T15:24:30Z | 5d837fc3582f | end | D05 | HB | pilot | 6/6 | completed | `8bcfd72` | `65c19e68` |
| 2026-11-13T15:24:34Z | 5be62146b4f1 | start | D08 | HB | pilot | 0/3 | started | `90bb59f` | `65c19e68` |
| 2026-11-13T15:29:11Z | ac7b97af4527 | end | D08 | HB | pilot | 3/3 | completed | `90bb59f` | `65c19e68` |
| 2026-11-13T15:49:46Z | 5be62146b4f1 | end | D08 | HB | pilot | 3/3 | completed | `90bb59f` | `65c19e68` |
| 2026-11-13T11:13:04Z | 4a387aab2161 | start | D01 | HB | pilot | 0/6 | started | `02f3c0e` | `db980490` |
| 2026-11-13T15:49:59Z | note-10M-02 | note | D01 | HB | pilot | 0/6 | note | `90bb59f` (dirty) | `65c19e68` |
| 2026-11-13T15:49:59Z | note-10M-03 | note | D02,D05,D08,D10 | HB | development | 0/0 | note | `90bb59f` (dirty) | `65c19e68` |

Notes:

- `note-5M-01` (D11, STD): Session 5M, outside the runner, on uncommitted code: replications 0 to 39 of D11's world, SPA only, a fixed 999 resamples per family, to choose the centre of the hedge-aware resamples. Six tests on the same resamples: the 3.0 test, the hedge re-estimated and centred at the live mean, at the resamples' own mean, at the window's least-squares intercept (adopted in PROTOCOL_v3.1 section 5.1), the in-window intercept as the statistic, and the 3.0 test on the true hedged returns. Numbers: results/manhattan_sim/v2/DEVELOPMENT_NOTES.md section 1. Not a pilot of record. No held-out scenario was run.
- `note-5M-02` (D11, STD): Session 5M, outside the runner, on uncommitted code: replications 0 to 11 of D11's world with the factor's annualised Sharpe ratio raised from 0.6 to 0.8 and the exposure's annual standard deviation from 0.3 to 0.4 (in memory only: no scenario was added), the same six tests at 999 resamples. Numbers: DEVELOPMENT_NOTES.md section 2. It is the top corner of the one-factor ranges SIM_PREREG_v2 gives held-out scenario H12; it is not H12, which is not coded.
- `note-5M-03` (D01,D02,D05,D08,D10, HB): Session 5M, outside the runner, on uncommitted code: replications 0 to 3 of each HB development scenario with the first version of the analytic model (families independent, no common shock). It showed shared luck read as a shared edge in D05 replication 1, which is why PROTOCOL_v3.1 section 7.1 has a common forward shock. Numbers: DEVELOPMENT_NOTES.md section 3. Also by hand: D02 replication 0 (three times) and D05 replication 1 (three times) with per-family printouts or timings, and runner smoke tests on programmes of a few batches written to a temporary directory.
- `note-6M-01` (D02,D05,D08,D10, HB): Session 6M, outside the runner: the pilot's 12 replications of each of D02, D05, D08 and D10 at HB replayed with the pilot's own code (c22815235975c486, before any edit), keeping for every family and review its true Sharpe ratio, estimates, the six models' Pi, the forecast PP under each model and its tier. Each of the 48 replays equals its run record on the counts behind M8. Variants of the dormancy rule were then scored on the stored fits, one element changed at a time: cut-offs 0.02, 0.01 and exactly 0; reactivation at 0.05; 1, 2 and 3 forward years; three consecutive reviews; the forecast under the central model only; and a second condition Pi^max below 0.05, 0.10 or 0.20 with 0, 252 or 504 forward days. Numbers: results/manhattan_sim/v2/DORMANCY_DIAGNOSIS.md part 1. It is the evidence for change 5 of PROTOCOL_v3.1 (section 9.1). Not a pilot of record. No held-out scenario was run.
- `note-6M-02` (D02,D05,D08,D10, HB): Session 6M, outside the runner, on the stored fits of note-6M-01: the forecast PP recomputed from the stored posterior draws with two other definitions of its event (each model judges its own future; the Promising tier instead of Statistically supported), with this session's random numbers, and the pilot's rule replayed on each. Numbers: DORMANCY_DIAGNOSIS.md section 1.3. Neither was adopted.
- `note-6M-03` (D02,D05,D08,D10, HB): Session 6M, outside the runner, on the stored estimates of note-6M-01: for every family and review, three posteriors of an edge of at least 0.25 from the same reserve and forward estimates and standard errors: the central model's, a plain normal prior with the population's own mean and variance, and the population's true shape. Calibration error at year 10 in D08: 0.101, 0.102 and 0.009. Numbers: DORMANCY_DIAGNOSIS.md part 2. It is the evidence for the limitation stated in PROTOCOL_v3.1 section 7.2(d). The model was not changed.
- `note-6M-04` (D02,D05,D08,D10, HB): Session 6M, outside the runner: 48 replications (12 of each of D02, D05, D08 and D10, the pilot's worlds) at HB with yearly reviews (MANHATTAN_SIM_EVAL_YEARS=1,...,10 in place of the pre-registered years 2, 4, 7 and 10), with the code of commit 9b1f068 and the revised dormancy rule; the first nine ran while the working tree held uncommitted edits to other files, and the experiment was stopped once and resumed. The dormancy rule of 3.0 and variants of the revised rule were replayed on the stored fits. Reported: premature elimination under both rules at this cadence, and the share of families with a true edge that reach Statistically supported by years 4, 6 and 10, by true Sharpe ratio. Numbers: DORMANCY_DIAGNOSIS.md parts 3 and 4. It changes a declared reduction of the pre-registered pipeline (SIM_PREREG section 2.5(c)), so it is a development experiment only: it decides nothing and is pooled with no run of record.
- `note-6Mb-01` (D02,D05,D08,D10, HB): Session "6M Manhattan C: dormancy fix and statistical checks" (the second session of 2026-11-13 on this branch), outside the runner: replications 0 to 11 of each scenario run exactly as session 5M's pilot ran them (the same seeds and streams, the dormancy rule of 3.0, code c22815235975c486 in a clean state at the time), keeping every family's six posterior probabilities, forecasts, forward estimate and tier state at each review, and the same forecast with other bars and horizons and with the true edge in place of the posterior draws. All 48 reproduce the recorded counts of retired families. The tier state machine was then replayed with one part of the rule changed at a time, and the central model's reliability curve and a two-group prior fitted to the same estimates were computed for the calibration question. Scripts and outputs: results/manhattan_sim/v2/dev_6M_b/ (trace_hb.py, analyse_traces.py, who.py, calib.py). No held-out scenario was run.
- `note-6Mb-02` (D02,D05,D08,D10, HB): Session "6M Manhattan C: dormancy fix and statistical checks" (the second session of 2026-11-13 on this branch), outside the runner, on the code of commit c914421 with uncommitted new files beside it and no pipeline file edited: replications 0 to 11 of each scenario through manhattan.sim.hb_v2's own functions, with the tiers stepped four ways on the same fits (the rule on the branch, the rule of 3.0, an alternative second condition on the family's own forward record that is not adopted, no dormancy), once at the pre-registered review dates (48 replications; the branch's path equals the pilot of record and the 3.0 path equals session 5M's pilot in 48 of 48) and once with a review every year (48 replications, a change of the declared reduction 2.5(c)). Records: dev_6M_b/paths_4_dates.jsonl and paths_yearly.jsonl; numbers: results/manhattan_sim/v2/DORMANCY_SECOND_LOOK.md. No held-out scenario was run.
- `note-6Mb-03` (none, STD): Session "6M Manhattan C: dormancy fix and statistical checks" (the second session of 2026-11-13 on this branch), outside the runner: manhattan.sim.estimand_study, single return series on a grid of processes written in the module (normal, Student-t, GARCH, one-sided and two-sided jumps), 2,000 paths of ten years each, run through manhattan.stats.eprocess's scale, weekly sums, truncation and variance-ratio rule. Not a scenario of the pre-registration and not a held-out scenario: no programme, no screening, no e-LOND, no pre-registered metric, nothing drawn from the held-out generator, its own random streams (seed 20261113). No method was changed after it. Numbers: results/manhattan_sim/v2/ESTIMAND_AND_TAIL_RISK.md.
- `note-6Mb-04` (D02,D08,D11,D05h, STD): Session "6M Manhattan C: dormancy fix and statistical checks" (the second session of 2026-11-13 on this branch), outside the runner: manhattan.sim.benchmark, a timing slice. One replication (number 0) of D02 STD, D08 STD, D02 LONG, D11 STD, D05h STD and D08 HB alone on an idle machine, then replications 0 to 3 of each with four workers. Timing only: the replications' results were discarded and no replication record was written. Numbers: results/manhattan_sim/v2/benchmark.json and COMPUTE_OPTIONS.md.
- `note-6Mb-05` (D02,D10, HB): Session "6M Manhattan C: dormancy fix and statistical checks" (the second session of 2026-11-13 on this branch), outside the runner, before it found that another session had already revised Protocol 3.1 section 9.1 on this branch: an alternative revision (the forecast and the family's own forward record) was written, committed on another branch (claude/epic-mayer-kfhpsh, commits 1c1f648 and 1124fe7) and piloted through the runner from a clean checkout of 1c1f648: 36 replications of D02 and 18 of D10 at HB, interrupted once by a restart of the session's machine (a start record with no end) and then stopped for good. Fifteen replications with yearly reviews were also run on that code. None of those records, run-log lines or hashes is on build/manhattan, and none is counted in any report. They retired 2 of 143 families with an edge in D02 and none of 190 in D10.
- `note-10M-01` (D08, HB): Session "10M Manhattan C: final pre-adoption changes", outside the runner:  a two-group candidate for D08 (manhattan/stats/hier_spike.py: slab = the analytic model, spike = the slab at retention 0 with the 0.02 innovation, edge share uniform on ten nodes; with the share fixed at 1 it reproduces hier_analytic) was checked for identification before being wired into any pipeline, against a criterion written into the script before its first run. Inputs: the HB pipeline's own estimates for replications 0 to 11 of D08 at years 4 and 10 (the one-group fit reproduces the pilot of record's calibration counts at year 10), and data drawn from the candidate itself. Result: the share is not identified (posterior mean 0.777 at year 4 and 0.896 at year 10 against true shares 0.316 and 0.328; calibration error at year 10 0.096 against 0.101). The candidate was not adopted, no other scenario was run with it and no run of record uses it. Numbers: results/manhattan_sim/v2/D08_SPIKE_SLAB.md; script and outputs: results/manhattan_sim/v2/dev_10M/.
- `note-10M-02` (D01, HB): Session "10M Manhattan C: final pre-adoption changes". The start record just above (run 4a387aab2161, D01 at HB, commit 02f3c0e, v2 hashes db980490 / 4d7b1063) has no end record: that pilot was stopped by the session about three minutes after it began, before any replication had finished, so that the pilot of record could be started again from a clean checkout of commit 8bcfd72, whose hash record (65c19e68 / c4ce79d2) is the one put before Ethan for adoption. Nothing of it is on file. The pilot of record is the runs labelled pilot that follow note-10M-01 in this log: the five HB scenarios, replications 0 to 11, forward-record dormancy rule, a review every 63 days. Most were run from a clean checkout of 8bcfd72 with three workers; replications run by a fourth worker, added when a core came free, were run from a clean checkout of 90bb59f, which has the same HB code hash (4252b971831004e3) and the same hash record. The record appears here out of time order because the work tree it was written in was replaced.
- `note-10M-03` (D02,D05,D08,D10, HB): Session "10M Manhattan C: final pre-adoption changes", outside the runner: what the forward-record dormancy rule does to a family by arithmetic alone, at four review dates, yearly and quarterly (results/manhattan_sim/v2/dev_10M/dormancy_cadence.py). No world, no model, no pipeline: a forward record that is a random walk around a given true edge, the forecast taken as zero at every review that has one, the rule's own code (dormancy.step, dormancy.forward_p), counted as M8 counts; 4,000 paths a cell. A family whose edge is exactly 0.25 is retired in 0.026 of paths at four dates, 0.062 with yearly reviews and 0.086 with quarterly reviews; at an edge of 0.40, 0.012, 0.022 and 0.040. It was run to read the small counts of the pilot (D10 has many families with an edge just above 0.25) and decides nothing.

Held-out runs refused: 0. Held-out runs made: 0.
