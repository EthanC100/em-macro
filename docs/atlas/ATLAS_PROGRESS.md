# Atlas progress

Updated 2026-11-12 (session "Atlas A-B: audit, architecture, Protocol v3, simulation pre-registration", branch
`build/atlas`). A new session starts here: read this file, then the document for the phase it is about to work on.

## Phases

| phase | what | status | deliverable | tests |
|---|---|---|---|---|
| **A** | Audit of what exists | **done** | [AUDIT.md](AUDIT.md) | none (document) |
| **B** | Architecture, Protocol v3, simulation pre-registration | **done; awaiting Ethan's review** | [ARCHITECTURE.md](ARCHITECTURE.md), [PROTOCOL_v3.md](PROTOCOL_v3.md) 3.0.0, [SIM_PREREG.md](SIM_PREREG.md) 1.0 with `sim_prereg.sha256`, `atlas/prereg.py`, `atlas/config.py`, `config/atlas.yaml` | `tests/test_atlas_prereg.py` (15) |
| **C** | Simulation harness; test and choose the methods | **next; not started** | `atlas/sim/` exactly as SIM_PREREG.md; `results/atlas_sim/runs.jsonl`; a confirmation report and a selection report | unit tests of every data-generating process and every statistic against known cases |
| **D** | Core infrastructure | not started | `atlas/spec.py` (canonical form, IDs), `atlas/ledger.py` (hash chain, rerun detection, corrections), `atlas/roles.py` (fences) | chain tamper tests; ID immutability; role refusal |
| **E** | Engine and core factors | not started; needs ETHAN_ACTIONS item 10 | daily core-factor library, hedge, cost models, executable runner | no look-ahead tests; hedge uses past data only |
| **F** | Generation, critic, freezing | not started; needs items 2, 3, 7 | templates, generators, critic call, manifest, tag and timestamp tooling | freeze refuses an unsigned or changed batch |
| **G** | Runners | not started; needs item 4 | iMac launchd job, Actions workflow, heartbeat, watchdog | guard refusal; path-list refusal; watchdog on a stale heartbeat |
| **H** | Statistics in production | not started; needs a passed Phase C | screening, SPA, Romano-Wolf, e-process, e-LOND, hierarchical model, tiers, dormancy | each against the simulation's reference implementation |
| **I** | First batch | not started; needs items 1, 2, 8, 9 | a dry run on synthetic specs, then the first real freeze by Ethan, forward recording, quarterly reviews, annual governance | end-to-end on synthetic data |

## What this session did

1. Read the repository without opening any result series (AUDIT.md header says exactly what was read).
2. Wrote AUDIT.md, ARCHITECTURE.md and PROTOCOL_v3.md and committed them (`b2f2fa5`).
3. Wrote SIM_PREREG.md and committed it with its SHA-256 (`4ea29a4`) **before any simulation code or `atlas/`
   package existed**. SHA-256: `07fb6ca2a22d01b5d18789a739c33ecea298dbe040d07108ce16df5ca035d715`. It names the
   protocol under test: 3.0.0, SHA-256 `60653417d3e9ce9934ba14c05975d0de4021bb2b22260106c7508bb7454668d5`.
4. Added the hash check (`python -m atlas.prereg verify`), a validated config with conservative defaults
   (`python -m atlas.config check`) and their tests.
5. Wrote ETHAN_ACTIONS.md and this file.

## Tests

| run | result |
|---|---|
| baseline, `main` at `a2e24fa`, before any change | 705 passed, 127 skipped, exit code 0 |
| this branch, full suite, before the push | 720 passed, 127 skipped, exit code 0 |
| `tests/test_atlas_prereg.py` alone | 15 passed; on a copy with one threshold edited: fails in a session and under `NIGHT_SHIFT_STRICT=1`, skips with a message under `GITHUB_ACTIONS=true` |

Command, as hard rule 15 requires (no pipe, exit code read directly):
`python -m pytest -q -p no:cacheprovider -rs tests > <log> 2>&1; echo "exit=$?"`.

## Decisions taken in this session

Each is written where it applies, with its reason. Those that are Ethan's were made configurable with the
conservative default and are in ETHAN_ACTIONS.md.

| # | decision | where |
|---|---|---|
| 1 | The screening unit is a blind-channel family in its batch; a family is registered in one batch; a new domain later is a new family that names its parent. | ARCHITECTURE §3 |
| 2 | "Once per batch, retired after use" means one designated evaluation per (batch, domain) on a shared reserve window; disjoint slices are an option for Ethan. | ARCHITECTURE §6.2 |
| 3 | The full ledger (with outcomes) is private; the public repository holds a hash-chained index. | ARCHITECTURE §4.1 |
| 4 | Screening candidate (i) is the paper's positive-dependence procedure (`Batch-BH^PRDS`), not its independence procedure, because families in a batch share dates. | PROTOCOL §4.3 |
| 5 | Screening candidate (ii) is e-BH inside the batch at e-LOND's level; derived here with a proof; historical e-values are the forward betting process replayed through the reserve. | PROTOCOL §4.4, §4.5, Appendix A.1 |
| 6 | No lower bound on returns can be guaranteed. The forward test bets on weekly returns truncated at 6 ex-ante standard deviations, tests the truncated null exactly, and adds an asymptotic guard on the untruncated record. | PROTOCOL §6.2-6.3 |
| 7 | Weekly test periods and a variance-ratio rule, because positive serial correlation breaks the test. | PROTOCOL §6.1, §6.7 |
| 8 | A family enters the forward 5% accounting when it becomes Promising, not at freeze. | PROTOCOL §6.8 |
| 9 | One retention parameter links history to the future; six pre-registered models; tiers use the most cautious, dormancy the most optimistic. | PROTOCOL §7, §9 |
| 10 | Simulation: 2,000 replications (400 for model fits), three held-out parameter sets, candidate (ii) preferred unless (i) is better by 0.05 in power. | SIM_PREREG §6-8 |
| 11 | Atlas tests of hand-edited files skip inside the existing writers' workflows and fail everywhere else. | `tests/test_atlas_prereg.py`; ETHAN_ACTIONS item 11 |

## Findings to keep in view

- **Formal forward-only support is slow**: about 15 years at a hedged Sharpe ratio of 1, about 5 at 2
  (PROTOCOL §6.9). It will be rare. The middle tiers carry most of the practical weight, and they rest on the
  hierarchical model.
- **Candidate (i) has no theorem behind it on a shared reserve window** (its across-batch independence condition
  fails). It can still win, but only on the simulation's evidence.
- **The Benjamini-Bogomolov link is not covered by its theorem here** (families are dependent; Romano-Wolf inside).
  It is a rule checked by simulation. The forward analogue with e-values is proved.
- **No historical reserve is clean** for the asset classes already traded (AUDIT §3.1), and none is clean with
  respect to the model's knowledge.

## Unverified

- Protocol v3 was checked against four of its sources (batch online FDR, e-LOND, the selection-adjusted procedure,
  the asymptotic confidence sequence). **Hansen's recentring constant and the Politis-White block-length rule are
  from memory**, and the Li-Ji formula was matched only to a secondary description; all three must be checked
  against the papers in Phase C before they are coded.
- The proofs in PROTOCOL Appendix A are short and were checked by hand only. A.1 and A.2 extend published results;
  neither extension has been reviewed by anyone else.
- No number in Protocol v3 has been tested: every threshold, schedule and prior is an assumed parameter until
  Phase C. The evidence-time table is arithmetic under a Gaussian approximation.
- Whether the rulesets on main are applied; whether a cloud session's git proxy serves public repositories when
  the network is closed; what the private Norgate snapshot contains beyond the 34 exported markets.
- The hierarchical model has not been fitted to anything; whether it converges at the simulated sizes is unknown.

## Exact next step

**After this PR is merged** (ETHAN_ACTIONS item 13; nothing else is needed to start):

1. New branch from main. Run `python -m atlas.prereg verify` and stop if it fails.
2. Check the three formulas listed under "Unverified" against Hansen (2005), Politis and White (2004) with Patton,
   Politis and White (2009), and Li and Ji (2005). If any differs from PROTOCOL_v3.md, correct the protocol as
   version 3.0.1 with a change-log entry **before** writing code that uses it.
3. Create `atlas/sim/dgp.py`: the return model of SIM_PREREG §2.3 with the defaults and scenario D01 only, seeded as
   in SIM_PREREG §9, with tests (weights sum to 1; null variants have mean 0 within Monte Carlo error; the three
   correlations are 0.60, 0.30 and 0.05).
4. Create `results/atlas_sim/runs.jsonl` logging from the very first run, held-out sets refused unless a
   confirmation flag and a tagged commit are present.
5. Then, in this order: the betting process and e-LOND (the simplest exact claims, C3), the SPA and Romano-Wolf
   (C2), the two screening candidates (C1), the hierarchical model (C5-C7). Development scenarios only until every
   required criterion passes on them.
