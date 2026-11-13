# Manhattan simulation, the parts changed by Protocol v3.1: PILOT report (nothing here is decided)

Written 2026-11-12 18:09 UTC by `python -m manhattan.sim.report_v2`. **Synthetic data only: nothing in this file is market evidence.**

- Pre-registration, version 2 (the changed parts): `docs/manhattan/SIM_PREREG_v2.md`, SHA-256 `677073309c0914ded0a6d39cc7ee0b8dcbcca855b2de21022a88639a522d7161`.
- Pre-registration, version 1 (everything else, and the seeds): `docs/manhattan/SIM_PREREG.md`, SHA-256 `e4bbcc44bebbc601b8bccc0e609131ad5185982f3047108dfaaf2fe2908c21e6` (never edited).
- Method under test here: `docs/manhattan/PROTOCOL_v3.1.md` 3.1.0, SHA-256 `40ad6532b2929a9acdcec0da98dcb0186cd6e0e477a2307e93ac1b5088e9f2dd`. Both v2 files are drafts until Ethan adopts them.
- Development scenarios only (seed branch 0). Held-out scenarios run: **none**.
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
| D01 | HB | analytic model, tiers, dormancy | 12 | 400 | 388 | `c22815235975c486` | 68 |
| D02 | HB | analytic model, tiers, dormancy | 12 | 400 | 388 | `c22815235975c486` | 75 |
| D05 | HB | analytic model, tiers, dormancy | 12 | 400 | 388 | `c22815235975c486` | 85 |
| D08 | HB | analytic model, tiers, dormancy | 12 | 400 | 388 | `c22815235975c486` | 149 |
| D10 | HB | analytic model, tiers, dormancy | 12 | 400 | 388 | `c22815235975c486` | 85 |

32 replication records on file were made by earlier code (the model changed during this revision) and are **not counted** anywhere in this report: records of different code are never pooled.

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
| M12 | reviews not computed (a fit fails the grid gate), of 48 | 0.0000 | - | 48 | exactly 0 | yes | pilot: not decided (none so far) |
| fit | largest posterior mass on the ends of the grid of μ_A, any fit | 0.0000 | - | 48 | gate: at most 0.01 | no | reported |
| M7 | year 2: share with a true edge among families with Π^min ≥ 0.8 (0 family observations) | - | - | 0 | - | no | reported |
| M7 | year 2: share with a true edge among families with Π^min ≥ 0.4 (0 family observations) | - | - | 0 | - | no | reported |
| M7 | year 2: expected calibration error of the central model | 0.0369 | 0.0336 to 0.0413 | 600 | - | no | reported |
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
| M7 | year 4: expected calibration error of the central model | 0.0295 | 0.0265 to 0.0328 | 1200 | upper bound ≤ 0.1 | yes | pilot: not decided (within threshold so far) |
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
| M7 | year 7: expected calibration error of the central model | 0.0224 | 0.0211 to 0.0239 | 2040 | - | no | reported |
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
| M7 | year 10: share with a true edge among families with Π^min ≥ 0.4 (2 family observations) | 0.0000 | 0.0000 to 0.0000 | 2 | lower bound ≥ 0.3 | yes | not evaluated: fewer than 200 observations |
| M7 | year 10: expected calibration error of the central model | 0.0189 | 0.0181 to 0.0198 | 2880 | upper bound ≤ 0.1 | yes | pilot: not decided (within threshold so far) |
| M7 | year 10: share of family evaluations with Π^min ≥ 0.80 (no edges exist) | 0.0000 | 0.0000 to 0.0000 | 2880 | upper bound ≤ 0.01 | yes | pilot: not decided (within threshold so far) |
| M9 | year 10: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (3 obs.) | 1.3529 | 0.0920 to 2.0037 | 3 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 10: bias of the naive estimate, Promising or higher, candidate (i) | 0.5269 | 0.3571 to 0.8013 | 3 | - | no | reported |
| M9 | year 10: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (0 obs.) | - | - | 0 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 10: bias of the naive estimate, Statistically supported or higher, candidate (i) | - | - | 0 | - | no | reported |
| M9 | year 10: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (2 obs.) | 1.9833 | 1.9630 to 2.0037 | 2 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 10: bias of the naive estimate, Promising or higher, candidate (ii) | 0.3897 | 0.3571 to 0.4223 | 2 | - | no | reported |
| M9 | year 10: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (0 obs.) | - | - | 0 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 10: bias of the naive estimate, Statistically supported or higher, candidate (ii) | - | - | 0 | - | no | reported |
| M8 | premature elimination: families with a true edge that end dormant, candidate (i) | - | - | 0 | upper bound ≤ 0.1 | yes | no data |
| info | at the end, candidate (i): passed screening / Promising / supported / dormant (means) | - | - | 12 | - | no | 0.1 / 0.2 / 0.0 / 87.1 |
| M8 | premature elimination: families with a true edge that end dormant, candidate (ii) | - | - | 0 | upper bound ≤ 0.1 | yes | no data |
| info | at the end, candidate (ii): passed screening / Promising / supported / dormant (means) | - | - | 12 | - | no | 0.0 / 0.2 / 0.0 / 87.5 |
| cost | seconds per replication | 68.1583 | - | 12 | - | no | reported |
| cost | year 2: seconds for the six fits of a review (50 families) | 19.8668 | - | 12 | - | no | reported |
| info | year 2: common share r of the forward estimates' variance | 0.0731 | - | 12 | - | no | reported |
| info | year 2: posterior means under S0 of μ_A / τ_A / ψ / the classes' ρ (means over reviews) | - | - | 12 | - | no | 0.084 / 0.084 / 1.060 / 0.37, 0.38, 0.38 |
| cost | year 4: seconds for the six fits of a review (100 families) | 11.8055 | - | 12 | - | no | reported |
| info | year 4: common share r of the forward estimates' variance | 0.0710 | - | 12 | - | no | reported |
| info | year 4: posterior means under S0 of μ_A / τ_A / ψ / the classes' ρ (means over reviews) | - | - | 12 | - | no | 0.061 / 0.066 / 1.054 / 0.36, 0.37, 0.36 |
| cost | year 7: seconds for the six fits of a review (170 families) | 7.4945 | - | 12 | - | no | reported |
| info | year 7: common share r of the forward estimates' variance | 0.0679 | - | 12 | - | no | reported |
| info | year 7: posterior means under S0 of μ_A / τ_A / ψ / the classes' ρ (means over reviews) | - | - | 12 | - | no | 0.046 / 0.052 / 1.053 / 0.35, 0.35, 0.34 |
| cost | year 10: seconds for the six fits of a review (240 families) | 6.3695 | - | 12 | - | no | reported |
| info | year 10: common share r of the forward estimates' variance | 0.0666 | - | 12 | - | no | reported |
| info | year 10: posterior means under S0 of μ_A / τ_A / ψ / the classes' ρ (means over reviews) | - | - | 12 | - | no | 0.013 / 0.047 / 1.053 / 0.31, 0.31, 0.31 |
| cost | seconds per replication spent on the model (estimates, six fits at four dates, forecasts) | 46.0517 | - | 12 | - | no | reported |
| info | model | - | - | 12 | - | no | analytic-normal-normal-3.1 |

### D02 at HB: rare edges (12 of 400 replications)

| metric | what | estimate | 95% interval | n | threshold | required here | verdict |
|---|---|---|---|---|---|---|---|
| M12 | reviews not computed (a fit fails the grid gate), of 48 | 0.0000 | - | 48 | exactly 0 | yes | pilot: not decided (none so far) |
| fit | largest posterior mass on the ends of the grid of μ_A, any fit | 0.0000 | - | 48 | gate: at most 0.01 | no | reported |
| M7 | year 2: share with a true edge among families with Π^min ≥ 0.8 (0 family observations) | - | - | 0 | - | no | reported |
| M7 | year 2: share with a true edge among families with Π^min ≥ 0.4 (0 family observations) | - | - | 0 | - | no | reported |
| M7 | year 2: expected calibration error of the central model | 0.0307 | 0.0205 to 0.0380 | 600 | - | no | reported |
| M9 | year 2: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (2 obs.) | -0.3003 | -0.3481 to -0.2524 | 2 | - | no | reported |
| M9 | year 2: bias of the naive estimate, Promising or higher, candidate (i) | 0.4330 | 0.2370 to 0.6291 | 2 | - | no | reported |
| M9 | year 2: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (0 obs.) | - | - | 0 | - | no | reported |
| M9 | year 2: bias of the naive estimate, Statistically supported or higher, candidate (i) | - | - | 0 | - | no | reported |
| M9 | year 2: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (0 obs.) | - | - | 0 | - | no | reported |
| M9 | year 2: bias of the naive estimate, Promising or higher, candidate (ii) | - | - | 0 | - | no | reported |
| M9 | year 2: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (0 obs.) | - | - | 0 | - | no | reported |
| M9 | year 2: bias of the naive estimate, Statistically supported or higher, candidate (ii) | - | - | 0 | - | no | reported |
| M7 | year 4: share with a true edge among families with Π^min ≥ 0.8 (0 family observations) | - | - | 0 | lower bound ≥ 0.7 | yes | not evaluated: fewer than 200 observations |
| M7 | year 4: share with a true edge among families with Π^min ≥ 0.4 (1 family observations) | 1.0000 | 1.0000 to 1.0000 | 1 | lower bound ≥ 0.3 | yes | not evaluated: fewer than 200 observations |
| M7 | year 4: expected calibration error of the central model | 0.0224 | 0.0134 to 0.0291 | 1200 | upper bound ≤ 0.1 | yes | pilot: not decided (within threshold so far) |
| M9 | year 4: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (5 obs.) | -0.1878 | -0.6491 to 0.0485 | 5 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 4: bias of the naive estimate, Promising or higher, candidate (i) | 0.5076 | 0.2012 to 0.7303 | 5 | - | no | reported |
| M9 | year 4: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (0 obs.) | - | - | 0 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 4: bias of the naive estimate, Statistically supported or higher, candidate (i) | - | - | 0 | - | no | reported |
| M9 | year 4: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (1 obs.) | 0.0485 | 0.0485 to 0.0485 | 1 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 4: bias of the naive estimate, Promising or higher, candidate (ii) | 0.2176 | 0.2176 to 0.2176 | 1 | - | no | reported |
| M9 | year 4: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (0 obs.) | - | - | 0 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 4: bias of the naive estimate, Statistically supported or higher, candidate (ii) | - | - | 0 | - | no | reported |
| M7 | year 7: share with a true edge among families with Π^min ≥ 0.8 (0 family observations) | - | - | 0 | - | no | reported |
| M7 | year 7: share with a true edge among families with Π^min ≥ 0.4 (2 family observations) | 1.0000 | 1.0000 to 1.0000 | 2 | - | no | reported |
| M7 | year 7: expected calibration error of the central model | 0.0171 | 0.0127 to 0.0209 | 2040 | - | no | reported |
| M9 | year 7: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (7 obs.) | -0.1755 | -0.5064 to 0.0275 | 7 | - | no | reported |
| M9 | year 7: bias of the naive estimate, Promising or higher, candidate (i) | 0.5458 | 0.1379 to 0.7316 | 7 | - | no | reported |
| M9 | year 7: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (0 obs.) | - | - | 0 | - | no | reported |
| M9 | year 7: bias of the naive estimate, Statistically supported or higher, candidate (i) | - | - | 0 | - | no | reported |
| M9 | year 7: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (3 obs.) | -0.0379 | -0.3122 to 0.2475 | 3 | - | no | reported |
| M9 | year 7: bias of the naive estimate, Promising or higher, candidate (ii) | 0.4659 | 0.1379 to 0.6598 | 3 | - | no | reported |
| M9 | year 7: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (0 obs.) | - | - | 0 | - | no | reported |
| M9 | year 7: bias of the naive estimate, Statistically supported or higher, candidate (ii) | - | - | 0 | - | no | reported |
| M7 | year 10: share with a true edge among families with Π^min ≥ 0.8 (0 family observations) | - | - | 0 | lower bound ≥ 0.7 | yes | not evaluated: fewer than 200 observations |
| M7 | year 10: share with a true edge among families with Π^min ≥ 0.4 (5 family observations) | 1.0000 | 1.0000 to 1.0000 | 5 | lower bound ≥ 0.3 | yes | not evaluated: fewer than 200 observations |
| M7 | year 10: expected calibration error of the central model | 0.0141 | 0.0105 to 0.0176 | 2880 | upper bound ≤ 0.1 | yes | pilot: not decided (within threshold so far) |
| M9 | year 10: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (11 obs.) | -0.2606 | -0.5834 to 0.0004 | 11 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 10: bias of the naive estimate, Promising or higher, candidate (i) | 0.3936 | 0.1383 to 0.5877 | 11 | - | no | reported |
| M9 | year 10: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (0 obs.) | - | - | 0 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 10: bias of the naive estimate, Statistically supported or higher, candidate (i) | - | - | 0 | - | no | reported |
| M9 | year 10: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (5 obs.) | -0.0460 | -0.4043 to 0.1103 | 5 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 10: bias of the naive estimate, Promising or higher, candidate (ii) | 0.3874 | 0.0380 to 0.6232 | 5 | - | no | reported |
| M9 | year 10: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (0 obs.) | - | - | 0 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 10: bias of the naive estimate, Statistically supported or higher, candidate (ii) | - | - | 0 | - | no | reported |
| M8 | premature elimination: families with a true edge that end dormant, candidate (i) | 0.1667 | 0.0455 to 0.2609 | 42 | upper bound ≤ 0.1 | yes | pilot: not decided (outside threshold so far) |
| info | at the end, candidate (i): passed screening / Promising / supported / dormant (means) | - | - | 12 | - | no | 1.0 / 0.9 / 0.0 / 85.6 |
| M8 | premature elimination: families with a true edge that end dormant, candidate (ii) | 0.1667 | 0.0455 to 0.2609 | 42 | upper bound ≤ 0.1 | yes | pilot: not decided (outside threshold so far) |
| info | at the end, candidate (ii): passed screening / Promising / supported / dormant (means) | - | - | 12 | - | no | 0.1 / 0.4 / 0.0 / 85.8 |
| cost | seconds per replication | 75.2833 | - | 12 | - | no | reported |
| cost | year 2: seconds for the six fits of a review (50 families) | 22.7979 | - | 12 | - | no | reported |
| info | year 2: common share r of the forward estimates' variance | 0.0729 | - | 12 | - | no | reported |
| info | year 2: families with a true edge (8 observations): mean Π^min / mean Π under S0 / mean Π^max | - | - | 8 | - | no | 0.131 / 0.269 / 0.405 |
| info | year 2: families with a true edge: the most cautious model is S0 / S1 / S2 / S3 / S4 / S5 (shares) | - | - | 8 | - | no | 0.00 / 0.25 / 0.12 / 0.00 / 0.62 / 0.00 |
| info | year 2: families with a true edge: share Statistically supported / share dormant, candidate (i) | - | - | 8 | - | no | 0.000 / 0.000 |
| info | year 2: posterior means under S0 of μ_A / τ_A / ψ / the classes' ρ (means over reviews) | - | - | 12 | - | no | 0.034 / 0.101 / 1.068 / 0.38, 0.38, 0.38 |
| cost | year 4: seconds for the six fits of a review (100 families) | 13.0183 | - | 12 | - | no | reported |
| info | year 4: common share r of the forward estimates' variance | 0.0674 | - | 12 | - | no | reported |
| info | year 4: families with a true edge (18 observations): mean Π^min / mean Π under S0 / mean Π^max | - | - | 18 | - | no | 0.144 / 0.300 / 0.430 |
| info | year 4: families with a true edge: the most cautious model is S0 / S1 / S2 / S3 / S4 / S5 (shares) | - | - | 18 | - | no | 0.00 / 0.17 / 0.00 / 0.00 / 0.61 / 0.22 |
| info | year 4: families with a true edge: share Statistically supported / share dormant, candidate (i) | - | - | 18 | - | no | 0.000 / 0.111 |
| info | year 4: posterior means under S0 of μ_A / τ_A / ψ / the classes' ρ (means over reviews) | - | - | 12 | - | no | 0.026 / 0.071 / 1.058 / 0.39, 0.38, 0.38 |
| cost | year 7: seconds for the six fits of a review (170 families) | 8.1581 | - | 12 | - | no | reported |
| info | year 7: common share r of the forward estimates' variance | 0.0658 | - | 12 | - | no | reported |
| info | year 7: families with a true edge (28 observations): mean Π^min / mean Π under S0 / mean Π^max | - | - | 28 | - | no | 0.133 / 0.286 / 0.382 |
| info | year 7: families with a true edge: the most cautious model is S0 / S1 / S2 / S3 / S4 / S5 (shares) | - | - | 28 | - | no | 0.00 / 0.14 / 0.00 / 0.00 / 0.46 / 0.39 |
| info | year 7: families with a true edge: share Statistically supported / share dormant, candidate (i) | - | - | 28 | - | no | 0.000 / 0.250 |
| info | year 7: posterior means under S0 of μ_A / τ_A / ψ / the classes' ρ (means over reviews) | - | - | 12 | - | no | 0.030 / 0.054 / 1.053 / 0.37, 0.34, 0.34 |
| cost | year 10: seconds for the six fits of a review (240 families) | 6.7586 | - | 12 | - | no | reported |
| info | year 10: common share r of the forward estimates' variance | 0.0669 | - | 12 | - | no | reported |
| info | year 10: families with a true edge (42 observations): mean Π^min / mean Π under S0 / mean Π^max | - | - | 42 | - | no | 0.144 / 0.377 / 0.466 |
| info | year 10: families with a true edge: the most cautious model is S0 / S1 / S2 / S3 / S4 / S5 (shares) | - | - | 42 | - | no | 0.00 / 0.14 / 0.00 / 0.00 / 0.43 / 0.43 |
| info | year 10: families with a true edge: share Statistically supported / share dormant, candidate (i) | - | - | 42 | - | no | 0.000 / 0.167 |
| info | year 10: posterior means under S0 of μ_A / τ_A / ψ / the classes' ρ (means over reviews) | - | - | 12 | - | no | 0.043 / 0.046 / 1.053 / 0.40, 0.37, 0.37 |
| cost | seconds per replication spent on the model (estimates, six fits at four dates, forecasts) | 51.2408 | - | 12 | - | no | reported |
| info | model | - | - | 12 | - | no | analytic-normal-normal-3.1 |

### D05 at HB: fat tails (12 of 400 replications)

| metric | what | estimate | 95% interval | n | threshold | required here | verdict |
|---|---|---|---|---|---|---|---|
| M12 | reviews not computed (a fit fails the grid gate), of 48 | 0.0000 | - | 48 | exactly 0 | yes | pilot: not decided (none so far) |
| fit | largest posterior mass on the ends of the grid of μ_A, any fit | 0.0000 | - | 48 | gate: at most 0.01 | no | reported |
| M7 | year 2: share with a true edge among families with Π^min ≥ 0.8 (0 family observations) | - | - | 0 | - | no | reported |
| M7 | year 2: share with a true edge among families with Π^min ≥ 0.4 (1 family observations) | 1.0000 | 1.0000 to 1.0000 | 1 | - | no | reported |
| M7 | year 2: expected calibration error of the central model | 0.0174 | 0.0117 to 0.0231 | 600 | - | no | reported |
| M9 | year 2: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (9 obs.) | -0.4291 | -0.7133 to -0.2852 | 9 | - | no | reported |
| M9 | year 2: bias of the naive estimate, Promising or higher, candidate (i) | 0.4941 | 0.3612 to 0.5598 | 9 | - | no | reported |
| M9 | year 2: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (0 obs.) | - | - | 0 | - | no | reported |
| M9 | year 2: bias of the naive estimate, Statistically supported or higher, candidate (i) | - | - | 0 | - | no | reported |
| M9 | year 2: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (2 obs.) | -0.4667 | -0.4667 to -0.4667 | 2 | - | no | reported |
| M9 | year 2: bias of the naive estimate, Promising or higher, candidate (ii) | 0.5602 | 0.5602 to 0.5602 | 2 | - | no | reported |
| M9 | year 2: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (0 obs.) | - | - | 0 | - | no | reported |
| M9 | year 2: bias of the naive estimate, Statistically supported or higher, candidate (ii) | - | - | 0 | - | no | reported |
| M7 | year 4: share with a true edge among families with Π^min ≥ 0.8 (1 family observations) | 1.0000 | 1.0000 to 1.0000 | 1 | lower bound ≥ 0.7 | yes | not evaluated: fewer than 200 observations |
| M7 | year 4: share with a true edge among families with Π^min ≥ 0.4 (6 family observations) | 1.0000 | 1.0000 to 1.0000 | 6 | lower bound ≥ 0.3 | yes | not evaluated: fewer than 200 observations |
| M7 | year 4: expected calibration error of the central model | 0.0130 | 0.0049 to 0.0224 | 1200 | upper bound ≤ 0.1 | yes | pilot: not decided (within threshold so far) |
| M9 | year 4: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (18 obs.) | -0.4435 | -0.6357 to -0.2621 | 18 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 4: bias of the naive estimate, Promising or higher, candidate (i) | 0.3610 | 0.2327 to 0.4472 | 18 | - | no | reported |
| M9 | year 4: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (1 obs.) | 0.0774 | 0.0774 to 0.0774 | 1 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 4: bias of the naive estimate, Statistically supported or higher, candidate (i) | 0.2547 | 0.2547 to 0.2547 | 1 | - | no | reported |
| M9 | year 4: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (6 obs.) | -0.0751 | -0.5941 to 0.5611 | 6 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 4: bias of the naive estimate, Promising or higher, candidate (ii) | 0.3085 | -0.0380 to 0.4848 | 6 | - | no | reported |
| M9 | year 4: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (1 obs.) | 0.0774 | 0.0774 to 0.0774 | 1 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 4: bias of the naive estimate, Statistically supported or higher, candidate (ii) | 0.2547 | 0.2547 to 0.2547 | 1 | - | no | reported |
| M7 | year 7: share with a true edge among families with Π^min ≥ 0.8 (5 family observations) | 1.0000 | 1.0000 to 1.0000 | 5 | - | no | reported |
| M7 | year 7: share with a true edge among families with Π^min ≥ 0.4 (13 family observations) | 1.0000 | 1.0000 to 1.0000 | 13 | - | no | reported |
| M7 | year 7: expected calibration error of the central model | 0.0040 | 0.0002 to 0.0127 | 2040 | - | no | reported |
| M9 | year 7: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (26 obs.) | -0.2190 | -0.4048 to -0.0973 | 26 | - | no | reported |
| M9 | year 7: bias of the naive estimate, Promising or higher, candidate (i) | 0.4147 | 0.3197 to 0.5077 | 26 | - | no | reported |
| M9 | year 7: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (4 obs.) | -0.0539 | -0.3909 to 0.4679 | 4 | - | no | reported |
| M9 | year 7: bias of the naive estimate, Statistically supported or higher, candidate (i) | 0.2141 | 0.0621 to 0.4007 | 4 | - | no | reported |
| M9 | year 7: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (16 obs.) | -0.0763 | -0.2106 to 0.1541 | 16 | - | no | reported |
| M9 | year 7: bias of the naive estimate, Promising or higher, candidate (ii) | 0.3481 | 0.2068 to 0.4595 | 16 | - | no | reported |
| M9 | year 7: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (4 obs.) | -0.0539 | -0.3909 to 0.4679 | 4 | - | no | reported |
| M9 | year 7: bias of the naive estimate, Statistically supported or higher, candidate (ii) | 0.2141 | 0.0621 to 0.4007 | 4 | - | no | reported |
| M7 | year 10: share with a true edge among families with Π^min ≥ 0.8 (8 family observations) | 1.0000 | 1.0000 to 1.0000 | 8 | lower bound ≥ 0.7 | yes | not evaluated: fewer than 200 observations |
| M7 | year 10: share with a true edge among families with Π^min ≥ 0.4 (20 family observations) | 1.0000 | 1.0000 to 1.0000 | 20 | lower bound ≥ 0.3 | yes | not evaluated: fewer than 200 observations |
| M7 | year 10: expected calibration error of the central model | 0.0048 | 0.0002 to 0.0229 | 2880 | upper bound ≤ 0.1 | yes | pilot: not decided (within threshold so far) |
| M9 | year 10: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (38 obs.) | -0.1241 | -0.3647 to 0.0361 | 38 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 10: bias of the naive estimate, Promising or higher, candidate (i) | 0.4092 | 0.2775 to 0.5188 | 38 | - | no | reported |
| M9 | year 10: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (10 obs.) | 0.0713 | -0.2169 to 0.1978 | 10 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 10: bias of the naive estimate, Statistically supported or higher, candidate (i) | 0.2245 | 0.0599 to 0.3814 | 10 | - | no | reported |
| M9 | year 10: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (25 obs.) | -0.0371 | -0.1986 to 0.1049 | 25 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 10: bias of the naive estimate, Promising or higher, candidate (ii) | 0.3052 | 0.1527 to 0.4163 | 25 | - | no | reported |
| M9 | year 10: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (10 obs.) | 0.0713 | -0.2169 to 0.1978 | 10 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 10: bias of the naive estimate, Statistically supported or higher, candidate (ii) | 0.2245 | 0.0599 to 0.3814 | 10 | - | no | reported |
| M8 | premature elimination: families with a true edge that end dormant, candidate (i) | 0.1786 | 0.1379 to 0.2161 | 140 | upper bound ≤ 0.1 | yes | pilot: not decided (outside threshold so far) |
| info | at the end, candidate (i): passed screening / Promising / supported / dormant (means) | - | - | 12 | - | no | 3.4 / 3.2 / 0.8 / 86.7 |
| M8 | premature elimination: families with a true edge that end dormant, candidate (ii) | 0.1929 | 0.1562 to 0.2266 | 140 | upper bound ≤ 0.1 | yes | pilot: not decided (outside threshold so far) |
| info | at the end, candidate (ii): passed screening / Promising / supported / dormant (means) | - | - | 12 | - | no | 1.0 / 2.1 / 0.8 / 86.4 |
| cost | seconds per replication | 85.0333 | - | 12 | - | no | reported |
| cost | year 2: seconds for the six fits of a review (50 families) | 24.2379 | - | 12 | - | no | reported |
| info | year 2: common share r of the forward estimates' variance | 0.0710 | - | 12 | - | no | reported |
| info | year 2: families with a true edge (24 observations): mean Π^min / mean Π under S0 / mean Π^max | - | - | 24 | - | no | 0.122 / 0.232 / 0.349 |
| info | year 2: families with a true edge: the most cautious model is S0 / S1 / S2 / S3 / S4 / S5 (shares) | - | - | 24 | - | no | 0.00 / 0.42 / 0.00 / 0.00 / 0.46 / 0.12 |
| info | year 2: families with a true edge: share Statistically supported / share dormant, candidate (i) | - | - | 24 | - | no | 0.000 / 0.000 |
| info | year 2: posterior means under S0 of μ_A / τ_A / ψ / the classes' ρ (means over reviews) | - | - | 12 | - | no | 0.021 / 0.115 / 1.074 / 0.39, 0.38, 0.38 |
| cost | year 4: seconds for the six fits of a review (100 families) | 15.6069 | - | 12 | - | no | reported |
| info | year 4: common share r of the forward estimates' variance | 0.0606 | - | 12 | - | no | reported |
| info | year 4: families with a true edge (51 observations): mean Π^min / mean Π under S0 / mean Π^max | - | - | 51 | - | no | 0.158 / 0.295 / 0.402 |
| info | year 4: families with a true edge: the most cautious model is S0 / S1 / S2 / S3 / S4 / S5 (shares) | - | - | 51 | - | no | 0.00 / 0.14 / 0.00 / 0.00 / 0.67 / 0.20 |
| info | year 4: families with a true edge: share Statistically supported / share dormant, candidate (i) | - | - | 51 | - | no | 0.020 / 0.196 |
| info | year 4: posterior means under S0 of μ_A / τ_A / ψ / the classes' ρ (means over reviews) | - | - | 12 | - | no | 0.018 / 0.089 / 1.059 / 0.39, 0.41, 0.39 |
| cost | year 7: seconds for the six fits of a review (170 families) | 11.0100 | - | 12 | - | no | reported |
| info | year 7: common share r of the forward estimates' variance | 0.0652 | - | 12 | - | no | reported |
| info | year 7: families with a true edge (93 observations): mean Π^min / mean Π under S0 / mean Π^max | - | - | 93 | - | no | 0.171 / 0.316 / 0.410 |
| info | year 7: families with a true edge: the most cautious model is S0 / S1 / S2 / S3 / S4 / S5 (shares) | - | - | 93 | - | no | 0.00 / 0.16 / 0.00 / 0.00 / 0.52 / 0.32 |
| info | year 7: families with a true edge: share Statistically supported / share dormant, candidate (i) | - | - | 93 | - | no | 0.043 / 0.269 |
| info | year 7: posterior means under S0 of μ_A / τ_A / ψ / the classes' ρ (means over reviews) | - | - | 12 | - | no | 0.010 / 0.074 / 1.053 / 0.41, 0.43, 0.41 |
| cost | year 10: seconds for the six fits of a review (240 families) | 8.9803 | - | 12 | - | no | reported |
| info | year 10: common share r of the forward estimates' variance | 0.0770 | - | 12 | - | no | reported |
| info | year 10: families with a true edge (140 observations): mean Π^min / mean Π under S0 / mean Π^max | - | - | 140 | - | no | 0.183 / 0.390 / 0.479 |
| info | year 10: families with a true edge: the most cautious model is S0 / S1 / S2 / S3 / S4 / S5 (shares) | - | - | 140 | - | no | 0.00 / 0.08 / 0.00 / 0.01 / 0.41 / 0.51 |
| info | year 10: families with a true edge: share Statistically supported / share dormant, candidate (i) | - | - | 140 | - | no | 0.071 / 0.179 |
| info | year 10: posterior means under S0 of μ_A / τ_A / ψ / the classes' ρ (means over reviews) | - | - | 12 | - | no | 0.031 / 0.062 / 1.053 / 0.54, 0.54, 0.51 |
| cost | seconds per replication spent on the model (estimates, six fits at four dates, forecasts) | 60.3442 | - | 12 | - | no | reported |
| info | model | - | - | 12 | - | no | analytic-normal-normal-3.1 |

### D08 at HB: historical selection bias (12 of 400 replications)

| metric | what | estimate | 95% interval | n | threshold | required here | verdict |
|---|---|---|---|---|---|---|---|
| M12 | reviews not computed (a fit fails the grid gate), of 48 | 0.0000 | - | 48 | exactly 0 | yes | pilot: not decided (none so far) |
| fit | largest posterior mass on the ends of the grid of μ_A, any fit | 0.0000 | - | 48 | gate: at most 0.01 | no | reported |
| M7 | year 2: share with a true edge among families with Π^min ≥ 0.8 (2 family observations) | 1.0000 | 1.0000 to 1.0000 | 2 | - | no | reported |
| M7 | year 2: share with a true edge among families with Π^min ≥ 0.4 (45 family observations) | 0.9778 | 0.9605 to 1.0000 | 45 | - | no | reported |
| M7 | year 2: expected calibration error of the central model | 0.0076 | 0.0005 to 0.0368 | 600 | - | no | reported |
| M9 | year 2: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (87 obs.) | -0.5376 | -0.6189 to -0.4725 | 87 | - | no | reported |
| M9 | year 2: bias of the naive estimate, Promising or higher, candidate (i) | 0.4396 | 0.3778 to 0.5169 | 87 | - | no | reported |
| M9 | year 2: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (2 obs.) | -0.4258 | -0.6111 to -0.2404 | 2 | - | no | reported |
| M9 | year 2: bias of the naive estimate, Statistically supported or higher, candidate (i) | 0.2546 | 0.1405 to 0.3687 | 2 | - | no | reported |
| M9 | year 2: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (43 obs.) | -0.5421 | -0.6732 to -0.4626 | 43 | - | no | reported |
| M9 | year 2: bias of the naive estimate, Promising or higher, candidate (ii) | 0.3610 | 0.2654 to 0.4154 | 43 | - | no | reported |
| M9 | year 2: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (2 obs.) | -0.4258 | -0.6111 to -0.2404 | 2 | - | no | reported |
| M9 | year 2: bias of the naive estimate, Statistically supported or higher, candidate (ii) | 0.2546 | 0.1405 to 0.3687 | 2 | - | no | reported |
| M7 | year 4: share with a true edge among families with Π^min ≥ 0.8 (18 family observations) | 1.0000 | 1.0000 to 1.0000 | 18 | lower bound ≥ 0.7 | yes | not evaluated: fewer than 200 observations |
| M7 | year 4: share with a true edge among families with Π^min ≥ 0.4 (138 family observations) | 0.9275 | 0.8894 to 1.0000 | 138 | lower bound ≥ 0.3 | yes | not evaluated: fewer than 200 observations |
| M7 | year 4: expected calibration error of the central model | 0.0343 | 0.0042 to 0.0675 | 1200 | upper bound ≤ 0.1 | yes | pilot: not decided (within threshold so far) |
| M9 | year 4: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (208 obs.) | -0.3079 | -0.4176 to -0.2259 | 208 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | pilot: not decided |
| M9 | year 4: bias of the naive estimate, Promising or higher, candidate (i) | 0.4365 | 0.3888 to 0.4827 | 208 | - | no | reported |
| M9 | year 4: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (16 obs.) | -0.0978 | -0.2359 to 0.0261 | 16 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 4: bias of the naive estimate, Statistically supported or higher, candidate (i) | 0.2674 | 0.1098 to 0.4155 | 16 | - | no | reported |
| M9 | year 4: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (137 obs.) | -0.2279 | -0.3351 to -0.1640 | 137 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 4: bias of the naive estimate, Promising or higher, candidate (ii) | 0.4057 | 0.3213 to 0.4506 | 137 | - | no | reported |
| M9 | year 4: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (16 obs.) | -0.0978 | -0.2359 to 0.0261 | 16 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 4: bias of the naive estimate, Statistically supported or higher, candidate (ii) | 0.2674 | 0.1098 to 0.4155 | 16 | - | no | reported |
| M7 | year 7: share with a true edge among families with Π^min ≥ 0.8 (57 family observations) | 1.0000 | 1.0000 to 1.0000 | 57 | - | no | reported |
| M7 | year 7: share with a true edge among families with Π^min ≥ 0.4 (320 family observations) | 0.8844 | 0.8163 to 0.9775 | 320 | - | no | reported |
| M7 | year 7: expected calibration error of the central model | 0.0686 | 0.0222 to 0.1083 | 2040 | - | no | reported |
| M9 | year 7: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (442 obs.) | -0.2035 | -0.2988 to -0.1311 | 442 | - | no | reported |
| M9 | year 7: bias of the naive estimate, Promising or higher, candidate (i) | 0.4122 | 0.3591 to 0.4556 | 442 | - | no | reported |
| M9 | year 7: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (56 obs.) | 0.0055 | -0.0586 to 0.0679 | 56 | - | no | reported |
| M9 | year 7: bias of the naive estimate, Statistically supported or higher, candidate (i) | 0.3347 | 0.1953 to 0.4107 | 56 | - | no | reported |
| M9 | year 7: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (341 obs.) | -0.1600 | -0.2639 to -0.0879 | 341 | - | no | reported |
| M9 | year 7: bias of the naive estimate, Promising or higher, candidate (ii) | 0.3831 | 0.3040 to 0.4356 | 341 | - | no | reported |
| M9 | year 7: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (52 obs.) | 0.0261 | -0.0433 to 0.0776 | 52 | - | no | reported |
| M9 | year 7: bias of the naive estimate, Statistically supported or higher, candidate (ii) | 0.3453 | 0.1963 to 0.4250 | 52 | - | no | reported |
| M7 | year 10: share with a true edge among families with Π^min ≥ 0.8 (113 family observations) | 0.9912 | 0.9773 to 1.0000 | 113 | lower bound ≥ 0.7 | yes | not evaluated: fewer than 200 observations |
| M7 | year 10: share with a true edge among families with Π^min ≥ 0.4 (435 family observations) | 0.9011 | 0.8685 to 0.9398 | 435 | lower bound ≥ 0.3 | yes | pilot: not decided (within threshold so far) |
| M7 | year 10: expected calibration error of the central model | 0.1015 | 0.0341 to 0.1357 | 2880 | upper bound ≤ 0.1 | yes | pilot: not decided (outside threshold so far) |
| M9 | year 10: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (659 obs.) | -0.1457 | -0.2274 to -0.0845 | 659 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | pilot: not decided |
| M9 | year 10: bias of the naive estimate, Promising or higher, candidate (i) | 0.3920 | 0.3382 to 0.4289 | 659 | - | no | reported |
| M9 | year 10: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (120 obs.) | -0.0251 | -0.0689 to 0.0375 | 120 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 10: bias of the naive estimate, Statistically supported or higher, candidate (i) | 0.3335 | 0.2477 to 0.3826 | 120 | - | no | reported |
| M9 | year 10: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (574 obs.) | -0.1162 | -0.2033 to -0.0522 | 574 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | pilot: not decided |
| M9 | year 10: bias of the naive estimate, Promising or higher, candidate (ii) | 0.3796 | 0.3135 to 0.4214 | 574 | - | no | reported |
| M9 | year 10: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (112 obs.) | -0.0175 | -0.0708 to 0.0475 | 112 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 10: bias of the naive estimate, Statistically supported or higher, candidate (ii) | 0.3329 | 0.2471 to 0.3825 | 112 | - | no | reported |
| M8 | premature elimination: families with a true edge that end dormant, candidate (i) | 0.1081 | 0.0808 to 0.1384 | 944 | upper bound ≤ 0.1 | yes | pilot: not decided (outside threshold so far) |
| info | at the end, candidate (i): passed screening / Promising / supported / dormant (means) | - | - | 12 | - | no | 40.8 / 54.9 / 10.0 / 62.9 |
| M8 | premature elimination: families with a true edge that end dormant, candidate (ii) | 0.1081 | 0.0814 to 0.1365 | 944 | upper bound ≤ 0.1 | yes | pilot: not decided (outside threshold so far) |
| info | at the end, candidate (ii): passed screening / Promising / supported / dormant (means) | - | - | 12 | - | no | 10.0 / 47.8 / 9.3 / 62.6 |
| cost | seconds per replication | 149.4083 | - | 12 | - | no | reported |
| cost | year 2: seconds for the six fits of a review (50 families) | 34.1217 | - | 12 | - | no | reported |
| info | year 2: common share r of the forward estimates' variance | 0.0749 | - | 12 | - | no | reported |
| info | year 2: families with a true edge (182 observations): mean Π^min / mean Π under S0 / mean Π^max | - | - | 182 | - | no | 0.285 / 0.512 / 0.622 |
| info | year 2: families with a true edge: the most cautious model is S0 / S1 / S2 / S3 / S4 / S5 (shares) | - | - | 182 | - | no | 0.00 / 0.32 / 0.00 / 0.00 / 0.62 / 0.06 |
| info | year 2: families with a true edge: share Statistically supported / share dormant, candidate (i) | - | - | 182 | - | no | 0.011 / 0.000 |
| info | year 2: posterior means under S0 of μ_A / τ_A / ψ / the classes' ρ (means over reviews) | - | - | 12 | - | no | 0.230 / 0.311 / 1.114 / 0.50, 0.51, 0.51 |
| cost | year 4: seconds for the six fits of a review (100 families) | 27.4987 | - | 12 | - | no | reported |
| info | year 4: common share r of the forward estimates' variance | 0.0677 | - | 12 | - | no | reported |
| info | year 4: families with a true edge (379 observations): mean Π^min / mean Π under S0 / mean Π^max | - | - | 379 | - | no | 0.336 / 0.649 / 0.707 |
| info | year 4: families with a true edge: the most cautious model is S0 / S1 / S2 / S3 / S4 / S5 (shares) | - | - | 379 | - | no | 0.00 / 0.01 / 0.00 / 0.00 / 0.79 / 0.20 |
| info | year 4: families with a true edge: share Statistically supported / share dormant, candidate (i) | - | - | 379 | - | no | 0.042 / 0.058 |
| info | year 4: posterior means under S0 of μ_A / τ_A / ψ / the classes' ρ (means over reviews) | - | - | 12 | - | no | 0.229 / 0.348 / 1.081 / 0.62, 0.63, 0.66 |
| cost | year 7: seconds for the six fits of a review (170 families) | 22.9860 | - | 12 | - | no | reported |
| info | year 7: common share r of the forward estimates' variance | 0.0671 | - | 12 | - | no | reported |
| info | year 7: families with a true edge (667 observations): mean Π^min / mean Π under S0 / mean Π^max | - | - | 667 | - | no | 0.380 / 0.770 / 0.796 |
| info | year 7: families with a true edge: the most cautious model is S0 / S1 / S2 / S3 / S4 / S5 (shares) | - | - | 667 | - | no | 0.00 / 0.00 / 0.00 / 0.00 / 0.53 / 0.47 |
| info | year 7: families with a true edge: share Statistically supported / share dormant, candidate (i) | - | - | 667 | - | no | 0.084 / 0.153 |
| info | year 7: posterior means under S0 of μ_A / τ_A / ψ / the classes' ρ (means over reviews) | - | - | 12 | - | no | 0.254 / 0.380 / 1.060 / 0.76, 0.74, 0.77 |
| cost | year 10: seconds for the six fits of a review (240 families) | 20.0939 | - | 12 | - | no | reported |
| info | year 10: common share r of the forward estimates' variance | 0.0684 | - | 12 | - | no | reported |
| info | year 10: families with a true edge (944 observations): mean Π^min / mean Π under S0 / mean Π^max | - | - | 944 | - | no | 0.361 / 0.813 / 0.827 |
| info | year 10: families with a true edge: the most cautious model is S0 / S1 / S2 / S3 / S4 / S5 (shares) | - | - | 944 | - | no | 0.00 / 0.00 / 0.00 / 0.01 / 0.33 / 0.67 |
| info | year 10: families with a true edge: share Statistically supported / share dormant, candidate (i) | - | - | 944 | - | no | 0.126 / 0.108 |
| info | year 10: posterior means under S0 of μ_A / τ_A / ψ / the classes' ρ (means over reviews) | - | - | 12 | - | no | 0.264 / 0.386 / 1.058 / 0.82, 0.79, 0.82 |
| cost | seconds per replication spent on the model (estimates, six fits at four dates, forecasts) | 105.1800 | - | 12 | - | no | reported |
| info | model | - | - | 12 | - | no | analytic-normal-normal-3.1 |

### D10 at HB: misspecified priors (12 of 400 replications)

| metric | what | estimate | 95% interval | n | threshold | required here | verdict |
|---|---|---|---|---|---|---|---|
| M12 | reviews not computed (a fit fails the grid gate), of 48 | 0.0000 | - | 48 | exactly 0 | yes | pilot: not decided (none so far) |
| fit | largest posterior mass on the ends of the grid of μ_A, any fit | 0.0000 | - | 48 | gate: at most 0.01 | no | reported |
| M7 | year 2: share with a true edge among families with Π^min ≥ 0.8 (2 family observations) | 1.0000 | 1.0000 to 1.0000 | 2 | - | no | reported |
| M7 | year 2: share with a true edge among families with Π^min ≥ 0.4 (6 family observations) | 0.8333 | 0.5000 to 1.0000 | 6 | - | no | reported |
| M7 | year 2: expected calibration error of the central model | 0.0148 | 0.0075 to 0.0215 | 600 | - | no | reported |
| M9 | year 2: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (31 obs.) | -0.3106 | -0.4828 to -0.1235 | 31 | - | no | reported |
| M9 | year 2: bias of the naive estimate, Promising or higher, candidate (i) | 1.1455 | 1.0080 to 1.2867 | 31 | - | no | reported |
| M9 | year 2: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (2 obs.) | 0.1291 | -0.1072 to 0.3654 | 2 | - | no | reported |
| M9 | year 2: bias of the naive estimate, Statistically supported or higher, candidate (i) | 1.1941 | 1.0344 to 1.3537 | 2 | - | no | reported |
| M9 | year 2: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (13 obs.) | -0.2472 | -0.5656 to 0.0059 | 13 | - | no | reported |
| M9 | year 2: bias of the naive estimate, Promising or higher, candidate (ii) | 1.1699 | 0.7984 to 1.4224 | 13 | - | no | reported |
| M9 | year 2: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (2 obs.) | 0.1291 | -0.1072 to 0.3654 | 2 | - | no | reported |
| M9 | year 2: bias of the naive estimate, Statistically supported or higher, candidate (ii) | 1.1941 | 1.0344 to 1.3537 | 2 | - | no | reported |
| M7 | year 4: share with a true edge among families with Π^min ≥ 0.8 (6 family observations) | 1.0000 | 1.0000 to 1.0000 | 6 | lower bound ≥ 0.7 | yes | not evaluated: fewer than 200 observations |
| M7 | year 4: share with a true edge among families with Π^min ≥ 0.4 (21 family observations) | 0.7143 | 0.5600 to 0.9231 | 21 | lower bound ≥ 0.3 | yes | not evaluated: fewer than 200 observations |
| M7 | year 4: expected calibration error of the central model | 0.0089 | 0.0014 to 0.0158 | 1200 | upper bound ≤ 0.1 | yes | pilot: not decided (within threshold so far) |
| M9 | year 4: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (54 obs.) | -0.1554 | -0.3112 to 0.0375 | 54 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 4: bias of the naive estimate, Promising or higher, candidate (i) | 1.0494 | 0.9435 to 1.1653 | 54 | - | no | reported |
| M9 | year 4: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (4 obs.) | -0.0373 | -0.4492 to 0.1752 | 4 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 4: bias of the naive estimate, Statistically supported or higher, candidate (i) | 0.6940 | -0.0652 to 1.2156 | 4 | - | no | reported |
| M9 | year 4: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (33 obs.) | -0.1063 | -0.3872 to 0.1475 | 33 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 4: bias of the naive estimate, Promising or higher, candidate (ii) | 1.0054 | 0.7259 to 1.1928 | 33 | - | no | reported |
| M9 | year 4: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (3 obs.) | 0.1000 | 0.0323 to 0.1752 | 3 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 4: bias of the naive estimate, Statistically supported or higher, candidate (ii) | 0.9471 | 0.5462 to 1.2156 | 3 | - | no | reported |
| M7 | year 7: share with a true edge among families with Π^min ≥ 0.8 (12 family observations) | 0.9167 | 0.7000 to 1.0000 | 12 | - | no | reported |
| M7 | year 7: share with a true edge among families with Π^min ≥ 0.4 (43 family observations) | 0.7907 | 0.6410 to 0.9111 | 43 | - | no | reported |
| M7 | year 7: expected calibration error of the central model | 0.0042 | 0.0003 to 0.0091 | 2040 | - | no | reported |
| M9 | year 7: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (86 obs.) | -0.0105 | -0.1213 to 0.1015 | 86 | - | no | reported |
| M9 | year 7: bias of the naive estimate, Promising or higher, candidate (i) | 1.0457 | 0.9066 to 1.2043 | 86 | - | no | reported |
| M9 | year 7: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (13 obs.) | -0.2715 | -0.4342 to -0.1055 | 13 | - | no | reported |
| M9 | year 7: bias of the naive estimate, Statistically supported or higher, candidate (i) | 0.4356 | 0.1296 to 0.7273 | 13 | - | no | reported |
| M9 | year 7: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (64 obs.) | 0.0294 | -0.1087 to 0.1895 | 64 | - | no | reported |
| M9 | year 7: bias of the naive estimate, Promising or higher, candidate (ii) | 1.0330 | 0.8278 to 1.2646 | 64 | - | no | reported |
| M9 | year 7: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (13 obs.) | -0.2715 | -0.4342 to -0.1055 | 13 | - | no | reported |
| M9 | year 7: bias of the naive estimate, Statistically supported or higher, candidate (ii) | 0.4356 | 0.1296 to 0.7273 | 13 | - | no | reported |
| M7 | year 10: share with a true edge among families with Π^min ≥ 0.8 (24 family observations) | 0.7083 | 0.5332 to 0.8947 | 24 | lower bound ≥ 0.7 | yes | not evaluated: fewer than 200 observations |
| M7 | year 10: share with a true edge among families with Π^min ≥ 0.4 (57 family observations) | 0.7544 | 0.6440 to 0.8667 | 57 | lower bound ≥ 0.3 | yes | not evaluated: fewer than 200 observations |
| M7 | year 10: expected calibration error of the central model | 0.0035 | 0.0003 to 0.0076 | 2880 | upper bound ≤ 0.1 | yes | pilot: not decided (within threshold so far) |
| M9 | year 10: bias of the model's Sharpe ratio, Promising or higher, candidate (i) (115 obs.) | 0.0828 | -0.0067 to 0.1706 | 115 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 10: bias of the naive estimate, Promising or higher, candidate (i) | 0.9734 | 0.9235 to 1.0314 | 115 | - | no | reported |
| M9 | year 10: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (i) (24 obs.) | 0.0448 | -0.1331 to 0.2505 | 24 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 10: bias of the naive estimate, Statistically supported or higher, candidate (i) | 0.5838 | 0.3163 to 0.8922 | 24 | - | no | reported |
| M9 | year 10: bias of the model's Sharpe ratio, Promising or higher, candidate (ii) (88 obs.) | 0.1161 | 0.0357 to 0.2158 | 88 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 10: bias of the naive estimate, Promising or higher, candidate (ii) | 0.9255 | 0.8423 to 1.0134 | 88 | - | no | reported |
| M9 | year 10: bias of the model's Sharpe ratio, Statistically supported or higher, candidate (ii) (24 obs.) | 0.0448 | -0.1331 to 0.2505 | 24 | upper bound ≤ +0.1 and lower bound ≥ -0.25 | yes | not evaluated: fewer than 200 observations |
| M9 | year 10: bias of the naive estimate, Statistically supported or higher, candidate (ii) | 0.5838 | 0.3163 to 0.8922 | 24 | - | no | reported |
| M8 | premature elimination: families with a true edge that end dormant, candidate (i) | 0.1463 | 0.0917 to 0.1971 | 123 | upper bound ≤ 0.1 | yes | pilot: not decided (outside threshold so far) |
| info | at the end, candidate (i): passed screening / Promising / supported / dormant (means) | - | - | 12 | - | no | 11.8 / 9.6 / 2.0 / 88.2 |
| M8 | premature elimination: families with a true edge that end dormant, candidate (ii) | 0.1463 | 0.0917 to 0.1971 | 123 | upper bound ≤ 0.1 | yes | pilot: not decided (outside threshold so far) |
| info | at the end, candidate (ii): passed screening / Promising / supported / dormant (means) | - | - | 12 | - | no | 6.1 / 7.3 / 2.0 / 88.5 |
| cost | seconds per replication | 84.6083 | - | 12 | - | no | reported |
| cost | year 2: seconds for the six fits of a review (50 families) | 26.1848 | - | 12 | - | no | reported |
| info | year 2: common share r of the forward estimates' variance | 0.0699 | - | 12 | - | no | reported |
| info | year 2: families with a true edge (27 observations): mean Π^min / mean Π under S0 / mean Π^max | - | - | 27 | - | no | 0.207 / 0.355 / 0.477 |
| info | year 2: families with a true edge: the most cautious model is S0 / S1 / S2 / S3 / S4 / S5 (shares) | - | - | 27 | - | no | 0.00 / 0.37 / 0.00 / 0.00 / 0.59 / 0.04 |
| info | year 2: families with a true edge: share Statistically supported / share dormant, candidate (i) | - | - | 27 | - | no | 0.074 / 0.000 |
| info | year 2: posterior means under S0 of μ_A / τ_A / ψ / the classes' ρ (means over reviews) | - | - | 12 | - | no | -0.243 / 0.146 / 1.087 / 0.40, 0.43, 0.42 |
| cost | year 4: seconds for the six fits of a review (100 families) | 17.3592 | - | 12 | - | no | reported |
| info | year 4: common share r of the forward estimates' variance | 0.0673 | - | 12 | - | no | reported |
| info | year 4: families with a true edge (55 observations): mean Π^min / mean Π under S0 / mean Π^max | - | - | 55 | - | no | 0.297 / 0.482 / 0.579 |
| info | year 4: families with a true edge: the most cautious model is S0 / S1 / S2 / S3 / S4 / S5 (shares) | - | - | 55 | - | no | 0.00 / 0.11 / 0.00 / 0.00 / 0.67 / 0.22 |
| info | year 4: families with a true edge: share Statistically supported / share dormant, candidate (i) | - | - | 55 | - | no | 0.073 / 0.127 |
| info | year 4: posterior means under S0 of μ_A / τ_A / ψ / the classes' ρ (means over reviews) | - | - | 12 | - | no | -0.270 / 0.105 / 1.060 / 0.47, 0.51, 0.50 |
| cost | year 7: seconds for the six fits of a review (170 families) | 12.3177 | - | 12 | - | no | reported |
| info | year 7: common share r of the forward estimates' variance | 0.0694 | - | 12 | - | no | reported |
| info | year 7: families with a true edge (88 observations): mean Π^min / mean Π under S0 / mean Π^max | - | - | 88 | - | no | 0.321 / 0.537 / 0.597 |
| info | year 7: families with a true edge: the most cautious model is S0 / S1 / S2 / S3 / S4 / S5 (shares) | - | - | 88 | - | no | 0.00 / 0.01 / 0.02 / 0.00 / 0.59 / 0.38 |
| info | year 7: families with a true edge: share Statistically supported / share dormant, candidate (i) | - | - | 88 | - | no | 0.148 / 0.205 |
| info | year 7: posterior means under S0 of μ_A / τ_A / ψ / the classes' ρ (means over reviews) | - | - | 12 | - | no | -0.268 / 0.073 / 1.055 / 0.56, 0.57, 0.56 |
| cost | year 10: seconds for the six fits of a review (240 families) | 10.4118 | - | 12 | - | no | reported |
| info | year 10: common share r of the forward estimates' variance | 0.0689 | - | 12 | - | no | reported |
| info | year 10: families with a true edge (123 observations): mean Π^min / mean Π under S0 / mean Π^max | - | - | 123 | - | no | 0.330 / 0.589 / 0.644 |
| info | year 10: families with a true edge: the most cautious model is S0 / S1 / S2 / S3 / S4 / S5 (shares) | - | - | 123 | - | no | 0.00 / 0.03 / 0.01 / 0.00 / 0.44 / 0.52 |
| info | year 10: families with a true edge: share Statistically supported / share dormant, candidate (i) | - | - | 123 | - | no | 0.171 / 0.146 |
| info | year 10: posterior means under S0 of μ_A / τ_A / ψ / the classes' ρ (means over reviews) | - | - | 12 | - | no | -0.258 / 0.065 / 1.054 / 0.61, 0.61, 0.60 |
| cost | seconds per replication spent on the model (estimates, six fits at four dates, forecasts) | 66.7733 | - | 12 | - | no | reported |
| info | model | - | - | 12 | - | no | analytic-normal-normal-3.1 |

## 3. Cost of the whole development programme under version 2

Replications still to run times the seconds per replication on file (one core). Seconds measured while more jobs than cores were running are too high; the runbook gives timings on an idle core.

| part | runs | replications still to run | runs with a timing | CPU-hours |
|---|---|---|---|---|
| version 1 code: STD and LONG scenarios other than D11 | 17 | 33808 | 17 of 17 | 1189 |
| version 2 code: D11, full pipeline with the hedge-aware SPA test | 1 | 1964 | 1 of 1 | 204 |
| version 2 code: nine hedged twins, SPA only | 9 | 3546 | 9 of 9 | 301 |
| version 2 code: HB scenarios, analytic model | 5 | 1940 | 5 of 5 | 50 |
| **all development runs** | 32 | 41258 | | **1744** |

The six fits of one review took 16.4 seconds on average over 240 reviews (so 2.73 seconds a fit), and the model's share of a replication 66 seconds. The sampled model of 3.0 did not finish one replication in 2 hours 31 minutes of CPU time at a fifth of its budget.

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
- **HB: evaluation dates.** Years 2, 4, 7 and 10 (version 1's reduction (c)), consecutive dates standing for consecutive reviews.
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

Notes:

- `note-5M-01` (D11, STD): Session 5M, outside the runner, on uncommitted code: replications 0 to 39 of D11's world, SPA only, a fixed 999 resamples per family, to choose the centre of the hedge-aware resamples. Six tests on the same resamples: the 3.0 test, the hedge re-estimated and centred at the live mean, at the resamples' own mean, at the window's least-squares intercept (adopted in PROTOCOL_v3.1 section 5.1), the in-window intercept as the statistic, and the 3.0 test on the true hedged returns. Numbers: results/manhattan_sim/v2/DEVELOPMENT_NOTES.md section 1. Not a pilot of record. No held-out scenario was run.
- `note-5M-02` (D11, STD): Session 5M, outside the runner, on uncommitted code: replications 0 to 11 of D11's world with the factor's annualised Sharpe ratio raised from 0.6 to 0.8 and the exposure's annual standard deviation from 0.3 to 0.4 (in memory only: no scenario was added), the same six tests at 999 resamples. Numbers: DEVELOPMENT_NOTES.md section 2. It is the top corner of the one-factor ranges SIM_PREREG_v2 gives held-out scenario H12; it is not H12, which is not coded.
- `note-5M-03` (D01,D02,D05,D08,D10, HB): Session 5M, outside the runner, on uncommitted code: replications 0 to 3 of each HB development scenario with the first version of the analytic model (families independent, no common shock). It showed shared luck read as a shared edge in D05 replication 1, which is why PROTOCOL_v3.1 section 7.1 has a common forward shock. Numbers: DEVELOPMENT_NOTES.md section 3. Also by hand: D02 replication 0 (three times) and D05 replication 1 (three times) with per-family printouts or timings, and runner smoke tests on programmes of a few batches written to a temporary directory.

Held-out runs refused: 0. Held-out runs made: 0.
