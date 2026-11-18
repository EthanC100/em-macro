# D08 calibration: 0.114 against 0.10

A separate explanation, as the owner asked in the S6 follow-up of PR #83. Synthetic data only. It decides nothing,
changes no threshold, and does not treat the records it reads as valid.

## The number and where it comes from

| item | value |
|---|---|
| criterion | V6, central model's expected calibration error (M7) at years 4 and 10; upper end of the 95% interval **≤ 0.10** (SIM_PREREG §5; SIM_PREREG_v2 §5 keeps it, on the analytic model) |
| scenario | D08, historical selection bias, HB size, 400 replications, reviews every 63 days |
| records | the HB records of workflow run `43467828524`, code `4252b971831004e3`, artifact `manhattan-sim-results` (SHA-256 `a81b137c…fe35e1`) |
| year 10 | **0.114 (0.106 to 0.122)**, over 400 reviews, every one computed |
| year 4 | 0.069 (0.061 to 0.077) |
| pilot of record (12 replications, quarterly) | 0.0998 (0.0357 to 0.1356) |

**Status: not decided.** The records were made by code `4252b971…`, and current main computes `c864e579…`
(`manhattan/ledger.py` changed after the run: SIMULATION_READINESS.md section 1.4). SIM_PREREG_v2 §9 says records of
different code are never pooled. These numbers are therefore information for the owner, not a result of record.
They are not counted as a pass or as a fail, and nothing here makes them valid.

## Why it does not satisfy the frozen criterion

- **The criterion is about the upper end of the interval, not the point estimate.** At year 10 the upper end is
  0.122. The point estimate, 0.114, is also above 0.10. The rule has no tolerance band beyond the interval, so a
  value like this is a failure as written, should the records ever count.
- **There is no exception for D08.** V6 is required "in every scenario run at HB" (SIM_PREREG §5). Neither
  pre-registration, nor `criteria.py`, nor `criteria_v2.py` exempts D08.
- **What the tiers use does not rescue it.** The tiers read the ends of the scale (Π^min ≥ 0.80 and ≥ 0.40), and
  there the D08 shares pass easily: 0.995 (0.993 to 0.998) at ≥ 0.80 against a lower bound of 0.70. But V6 lists the
  ECE as a separate condition beside those shares. Passing two of its conditions does not satisfy the third.
- **More replications would not help.** The interval at 400 replications is already narrow (±0.008). The issue is
  the level of the error, not the noise around it.
- **Consequence fixed in advance.** If V6 fails in a development scenario, there are no posterior-based tiers
  (SIM_PREREG_v2 §5, "Consequences"; SIM_PREREG §8.1 rule 2). The threshold does not move (§8.1 rule 1).

## Why it may warrant investigation

Pooled reliability of the central model in D08 on the same records. A bin is counted in the ECE only with at least 200
observations; every bin here has thousands.

| stated Π (bin) | year 4: n / stated / observed | year 10: n / stated / observed |
|---|---|---|
| 0.0–0.1 | 8,601 / 0.052 / 0.031 | 19,291 / 0.046 / 0.014 |
| 0.1–0.2 | 6,788 / 0.147 / 0.069 | 13,685 / 0.147 / 0.039 |
| 0.2–0.3 | 5,023 / 0.248 / 0.137 | 10,232 / 0.249 / 0.070 |
| 0.3–0.4 | 3,790 / 0.347 / 0.218 | 8,035 / 0.348 / 0.117 |
| 0.4–0.5 | 3,051 / 0.448 / 0.335 | 6,446 / 0.448 / 0.186 |
| 0.5–0.6 | 2,552 / 0.549 / 0.485 | 5,612 / 0.548 / 0.283 |
| 0.6–0.7 | 2,216 / 0.649 / 0.668 | 4,688 / 0.649 / 0.424 |
| 0.7–0.8 | 2,060 / 0.751 / 0.828 | 4,625 / 0.750 / 0.624 |
| 0.8–0.9 | 2,264 / 0.852 / 0.935 | 5,487 / 0.853 / 0.825 |
| 0.9–1.0 | 3,655 / 0.958 / 0.990 | 17,899 / 0.973 / 0.984 |

Four things in this table matter:

1. **The middle of the scale is overstated, and more so with time.** At year 10, a family the model gives 0.45–0.55
   has an edge 0.19–0.28 of the time. By year 10 forward records are longer, the posteriors are sharper, and a
   wrongly shaped prior shows more.
2. **The ends are right.** The top two bins are within 0.03 at year 10, and the bottom bin is within 0.033.
3. **This is the shape the earlier diagnosis predicted** (`results/manhattan_sim/v2/DORMANCY_DIAGNOSIS.md`, part 2;
   Protocol v3.1 §7.2(d)). D08 has about a third of its families with an edge and two thirds at exactly zero. The
   model's single normal hump over the apparent edge cannot describe two groups. Fed the same estimates, a prior with
   the true two-group shape gave an ECE of 0.009 there. The two-group candidate that was tried
   (`results/manhattan_sim/v2/D08_SPIKE_SLAB.md`) put its group in the wrong place (in retention, not in the
   apparent edge), was not identified, and was not adopted.
4. **The pilot sat on the bound** (0.0998), with an interval too wide to decide. At full count the error is above
   it.

## What this note does not do

- It does not change V6, the ECE estimator, the bins or the small-groups rule.
- It does not count the records of code `4252b971…`, and it does not run D08 again on the current code.
- It does not propose or build a new prior. If the owner wants one, it is a new protocol version, tested on every HB
  scenario again (ETHAN_ACTIONS item 21(b), option (ii)). The alternative is option (iii): the posterior-based tiers
  stay off. That choice is decision D5 in SIMULATION_READINESS.md.

Reproduce: download the artifact, unzip it to `<dir>`, then run `python -m manhattan.sim.dev_status --out <dir>
--include-stale`. The bins come from `metrics._ece` on the `cal_n`, `cal_true` and `cal_p` fields of the year-4 and
year-10 reviews.
