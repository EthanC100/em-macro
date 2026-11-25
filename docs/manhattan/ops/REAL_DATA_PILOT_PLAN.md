# Real-data pilot plan: the nightly runner on FRED H.10 (paper only)

Written 2026-11-25 by a build session. **This is a plan, not an authorization.**

> **It must NOT be executed without Ethan's explicit authorization.** Nothing in this work activated real-data
> access: no FRED request was made, no workflow was dispatched or scheduled, no secret, environment, repository or
> setting was created or changed, `config/manhattan.yaml` is unchanged, and the benchmark behind this plan
> ([BENCHMARKS_OPS.md](BENCHMARKS_OPS.md)) ran on synthetic data in local temporary repositories only.

## 1. Purpose and scope

Measure what the operational path costs on a real public source **before** anything is sized for a
million-executable campaign: throughput, storage, failures and cost per stage, on the three H.10 series the runner
already declares (`fred_DEXBZUS`, `fred_DEXMXUS`, `fred_DEXSFUS`; universe `U_FX_H10`, spot only). Paper only: no
order, no account, no spending beyond free GitHub Actions minutes, no licensed data.

The pilot is an **operations** pilot. Its forward observations carry no evidential weight until the activation
gates (section 2, part C) are lifted; it produces no claim.

## 2. Gates that must all hold before the pilot may run

Each gate is the owner's. A session may check and report, never satisfy one on Ethan's behalf.

**A. Authorization**

| gate | condition | how it is checked |
|---|---|---|
| A-0 | Ethan authorizes this pilot in writing (issue, PR comment or brief), naming the sizes in section 4 and the end date | the written authorization, linked in the pilot record |
| A-1 | the exposure designation of [EXPOSURE_AUDIT_FRED_H10.md](EXPOSURE_AUDIT_FRED_H10.md) is accepted by Ethan: H.10 BRL/MXN/ZAR history is **previously examined**; only observations after a family's freeze and witnessed registration are forward data (the audit's proposal, which is not yet a decision) | Ethan's acceptance, recorded with A-0 |

**B. Operations set-up: [ETHAN_OPS_ACTIONS.md](ETHAN_OPS_ACTIONS.md)**

| gate | step | condition |
|---|---|---|
| B-ops-1 | step 1 | private `manhattan-ledger` repository exists, empty, in no Claude Code environment |
| B-ops-2 | step 2 | deploy key with write access; environment `manhattan-ledger` restricted to `main`; environment secret `MANHATTAN_LEDGER_DEPLOY_KEY`; GitHub host key checked |
| B-ops-3 | step 3 | the Claude GitHub App does not include `manhattan-ledger`; no environment lists it |
| B-ops-4 | step 4 | mirror chosen and configured (or knowingly absent: `mirror_status: not-configured`) |
| B-ops-9 | step 9 | runner enabled by Ethan: the first hand-started run from `main` (capture only, the first real test of the FRED fetcher), then, only if Ethan chooses, the schedule lines uncommented on `main` |

Steps 5 to 8 (blind environment, critic, isolation kit, CODEOWNERS for the ops switches) are needed before a **real
blind batch**. A pilot with owner-frozen families (part D) does not need a generator run, but step 8 (protecting
`promotion.py`, the templates and the runner workflow) is strongly advised before any scheduled run.

**C. Activation gates: [BINDING_ACCOUNTING.md](../BINDING_ACCOUNTING.md) §16-§19 (the G-1..G-6 table closes §18, after the §16 test evidence; B-1..B-3 are in §19)**

Until each is independently verified or decided, **no forward result of the pilot counts as evidence**. The pilot may
run for operations measurement with these gates open only if Ethan says so explicitly in A-0; its observations stay
weight-0 bookkeeping.

| gate | what must hold |
|---|---|
| G-1 / B-3 | `reconstructed` provenance and the observation set re-derive from authoritative capture records, independently verified |
| G-2 | independent custody of anchors (D-7) |
| G-3 / B-2 | every production forward caller registers with the verified configuration; one computation of the registered specification is the only path to a result; engine evaluations have no production caller |
| G-4 | a workflow adopts the candidate lock (owner) |
| G-5 | reserve stays disabled in `config/manhattan.yaml`; no reserve workflow |
| G-6 | D-1, the counting unit of any multiple-testing denominator, decided by Ethan (with NT-8 for cross-track counting). **Open; this plan chooses nothing** |
| B-1 | every forward attempt's configuration claim re-verifies, and the configuration custody on `main` is what it claims |

**D. Families**

| gate | condition |
|---|---|
| D-fam-1 | the families observed are **frozen by Ethan**: a manifest PR prepared by `freeze_pr.prepare`, reviewed by the critic, merged by Ethan, with an external witness (OpenTimestamps) of the manifest hash; registration by `runner register` |
| D-fam-2 | the families target `U_FX_H10` (spot only; carry kinds are not computable there) and declare `calendar: us_fed_fx` |
| D-fam-3 | Ethan states whether they are research families or **operations placeholders** (e.g. SYNTHETIC-labelled families re-bound to `U_FX_H10`). For a measurement pilot, placeholders are preferable: no research claim is consumed |

## 3. Keeping historical screening and forward confirmation distinct

| | historical screening | forward confirmation |
|---|---|---|
| data | H.10 history up to the fence (`exploration_end` 2019-12-31 in `config/manhattan.yaml`), **previously examined** | H.10 observations dated after the family's witnessed registration |
| role | `exploration`, evidential weight 0, `screening` records in the private ledger | `forward`, `observation` records, weight 1 only when eligible, not reconstructed, and the gates of section 2C are lifted |
| attempts | kind `screening` | kind `forward_observation` (one per prediction per night) |
| reporting | separate tables, separate counts; never pooled with forward | separate tables; families, unique executable configurations and attempts each reported |
| purpose in the pilot | optional; measures the screening stage's cost on real rows | the pilot's core measurement |

The audit's designation applies: no H.10 history is "unexamined", so screening results are a filter at most. The
pilot reports **families, unique executable configurations (distinct spec hashes) and attempts separately** in
every table, and never sums screening and forward attempts into one figure.

## 4. Sizes and duration

| phase | families | unique executable configurations | forward attempts per night | nights |
|---|---|---|---|---|
| P0 capture only | 0 | 0 | 0 | 5 weekdays (FRED posts H.10 dailies weekly, so this spans one posting) |
| P1 small | 10 | ≈ 27 with the mock's grid shape (depends on the frozen grids) | = predictions registered | 10 weekdays |
| P2 medium (only if P1 met every stop condition) | 50 | ≈ 135 | = predictions registered | 10 weekdays |

Sizes follow the synthetic benchmark (10, 20, 50 families measured). Anything larger is the million-executable
campaign, which this pilot exists to size and which needs its own authorization.

## 5. What to measure (as in the synthetic benchmark)

Per night, from the runner's health record (public, health-only) and the private ledger (private):

| measure | source | synthetic reference ([BENCHMARKS_OPS.md](BENCHMARKS_OPS.md)) |
|---|---|---|
| wall seconds per stage: open, recovery, lock, missed runs, capture (fetch, parse, write), forward attempts (register, read, compute, plan, completion, commit results+terminals), heartbeat, unlock, private log, mirror push, mirror verify | private log timings; for a per-stage split, run `scripts/manhattan_ops_bench.py`'s wrapper idea in a private replay, never in the public log | measured per stage |
| attempts per second (forward phase and whole night) | `attempts_registered` / stage time | measured |
| git writes per night (private ledger commits, mirror pushes) | `git rev-list --count main` on the ledger before/after | measured |
| private ledger bytes per night: `chain.jsonl`, `journal.jsonl`, `raw/`, `logs/`; bare repository growth | private clone | measured |
| captures: new captures, revisions, late values, `capture_failed` per source | chain records | synthetic source never fails; FRED will |
| failures: run status, `error_class`, failed stage, `missed_runs`, `missed_observation`, conflicts, attempts aborted/failed | health record, chain | 0 in synthetic runs |
| GitHub Actions minutes per run (billed minutes are rounded up per job) | the workflow run's timing | estimated in BENCHMARKS_OPS.md |
| schedule lateness (Q018) | `started_utc` against the cron time | n/a |

All of these are operational quantities. **No return, Sharpe or other performance value is published**; the public
log and step summary stay health-only (`manhattan.ops.blinding`), and the leak scan of the e2e test is re-run on the
pilot's public channels at the end.

## 6. Stop conditions

Stop the pilot (Ethan disables the schedule; nothing is deleted) if any of these occurs:

1. any performance value or private record appears in a public channel (Actions log, step summary, issue, artifact,
   public repository): stop at once, report, do not resume without Ethan;
2. the chain fails verification, the mirror verification is not `equal` on two consecutive runs, or a `conflict`
   record appears;
3. a run fails twice in a row at the same stage, or more than 2 of 10 scheduled weekday runs are missed;
4. a FRED source fails (`capture_failed`) on 3 consecutive nights, or a revision rewrites a first-seen value (it
   must not; revisions are counted, never applied);
5. any attempt stays unfinished after the next run's recovery, or reconciliation reports a violation;
6. a run exceeds 30 minutes wall time, or the private ledger grows by more than 50 MB in a week;
7. any gate of section 2 is found not to hold (for example the App gains access to `manhattan-ledger`);
8. Ethan says stop.

## 7. Outputs and what happens next

- a private pilot record in `manhattan-ledger` (the chain itself) and a public, health-only summary: counts of
  nights, failures, stage times, bytes and Actions minutes, with no performance value;
- a sizing note for the million-executable campaign that replaces the synthetic projection of BENCHMARKS_OPS.md with
  the pilot's measured per-attempt time, per-night fixed cost, bytes per attempt and failure rates;
- no promotion, no claim: promotion stays disabled in code, `claims.enabled` stays false, D-1/NT-8 stay Ethan's.
