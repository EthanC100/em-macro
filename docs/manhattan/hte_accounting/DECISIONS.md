# HTE → PR #86 attempt accounting: the owner decisions still open

This memo is for the owner. Each section gives:
- the exact question;
- the alternatives;
- what each alternative does to scientific validity and to accounting correctness;
- a recommendation.

**Nothing here is decided or implemented.** The bridge (`manhattan/hte_accounting/`) stays dormant: `bridge.ENABLED = False`,
`BridgePolicy` has no defaults, and every undecided field fails closed (`OwnerDecisionRequired` /
`OwnerDecisionUnsupported`). Recording a decision means setting a `BridgePolicy` field together with an `approval_ref`
that names where the owner recorded it. A policy without one is refused.

All the numbers below are synthetic measurements on the indexed ledger (PR #100). None of them is evidence.

## Summary

| id | question | recommendation | blocks |
|---|---|---|---|
| D-10 | Do HTE exploration evaluations register PR #86 attempts? | **Register every evaluation**, but only once A-1 and A-2 (ledger choice) are decided. Until then, unregistered. | every bridge write |
| D-1 | Which unit enters a multiple-testing denominator? | **The layered rule of S13 §2.3**: attempts and executions never; variants per family and window = SPA's *m*; one unit per scientific class per batch = *n_b*. | any HTE statistic used to screen, not the bridge |
| B4 | HTE work → PR #86 attempts: per candidate or per chunk? | **Per candidate** (implemented). | nothing more (decide to confirm) |
| A-1 | Which module may write HTE completions to the ledger? | **(a) Allow `manhattan/hte_accounting/bridge.py` to call `record_evaluation`, for exploration only.** | `complete` |
| A-2 | Ledger scaling, and which ledger HTE writes to | Scaling is **resolved by PR #100**. Still open: **a dedicated, persistent HTE exploration ledger with its own anchor**. | activation |
| A-3 | Data identity: binding by hash, or reads through PR #86 windows? | **Binding by hash for synthetic panels only (as now); require PIT-window reads before any real data.** | any non-synthetic use |

Each decision is independent of the others except where noted. D-10 = register makes A-1 and A-2 necessary. D-10 =
unregistered makes them moot.

## D-10: Do HTE exploration evaluations register PR #86 attempts?

**Question.** When HTE evaluates a batch of candidates on exploration-role data, does each evaluation create a PR #86
attempt (start, then a terminal) in a Manhattan ledger?

**Today.** PR #86 leaves exploration open by design. `docs/manhattan/BINDING_ACCOUNTING.md` lists D-10 as open, with
`factors/reproduce.py` and other exploration code unregistered. HTE records its work only in its own hash-chained log,
which no PR #86 anchor covers.

| alternative | scientific validity | accounting correctness | cost (100k candidates) |
|---|---|---|---|
| **`unregistered`** (status quo) | Nothing changes for exploration, which carries no evidential weight. But how many candidates were looked at before something was screened can be reconstructed only from HTE's log. An HTE run that was started and then discarded leaves no trace PR #86 can audit. | PR #86's census does not see HTE at all. The HTE log is complete and hash-chained, but has no external anchor. | none |
| **`register_every_evaluation`** (implemented) | Every evaluation, including failed ones and discarded runs, is in the census **before** it computes. The selection history behind a later screening decision is auditable, which is the main protection against an undisclosed multiple-testing denominator. Exploration stays at weight 0; registration is accounting, not evidence. | One attempt and one terminal per candidate. Retries, reruns and crashes are accounted for (tested), and PR #86's strict reconciler and the cross-check pass. | 142 s of accounting against 47 s of HTE computation (3.0×); 3.56 kB of ledger per candidate (338 MiB) |
| `register_selected_only` | **Invalid.** The registered set would depend on the outcomes, which is exactly the hidden-denominator problem. | It would look complete, but would not be. | Rejected. Not offered by `BridgePolicy`. |

**Recommendation: `register_every_evaluation`**, but only for runs whose results may later feed a screening or
promotion decision, and only after A-1 and A-2 are decided. HTE today is throughput infrastructure: its same-close
execution, #89 F8, already makes every HTE number non-evidential. So staying `unregistered` until then costs nothing
scientifically. What matters is that registration comes *before* any HTE output is used to choose what to screen.

## D-1: Which unit enters a multiple-testing denominator?

**Question.** When a family of HTE candidates is tested, what is counted as one test? The bridge counts every level
and never collapses them:

| unit | what it is |
|---|---|
| registered executions | attempts |
| completed evaluation keys | looks |
| executables | |
| bindings | code-free identity (#90) |
| candidates | |
| variants | |
| hypotheses | |
| families | |

`independent_statistical_tests` stays `None`, and `policy.denominator()` refuses without D-1 and an `approval_ref`.

| alternative | scientific validity | accounting correctness |
|---|---|---|
| registered executions or completed keys | **Over-counts.** Retries, reruns, and engine or environment changes multiply *m* with no new hypothesis. Conservative, but arbitrary: the same science gives a different *m* after a software update. | Easy to compute, and already exact. |
| executables | Also multiplies with engine and environment changes (#90 identity). | Exact. |
| bindings / candidates | One per evaluation-affecting parameter set, code-free. A reasonable *m* within a family **if** aliases (bit-identical behaviour) are collapsed. | Exact. Aliases are known to HTE. |
| variants (per family and window) | This is the SPA test's *m*: every variant ever evaluated on that window, including adaptive and failed-after-read ones (Protocol §5.3). | Needs D-10 = register, or the HTE log, to be complete. |
| families / scientific classes per batch | The screening procedure's *n_b*. Counting less than this, for example only "promising" families, is anti-conservative. | Exact if every family is registered. |

**Recommendation: the layered rule already proposed in `docs/manhattan/methodology/S13_RESEARCH_METHODOLOGY.md`
§2.3.**
- **Attempts, retries and executions:** census only, never a denominator.
- **Repeated computations:** a rerun detector, not a count.
- **Variants of a family on a window:** SPA's *m*, every variant ever evaluated there, failed-after-read included. Exact
  aliases are harmless, because they duplicate a column.
- **One unit per scientific class per batch:** this is *n_b*. Later units of a class inherit its decision and enter no
  denominator.

The bridge already reports every one of these counts. D-1 decides which ones a statistic uses, and it binds the
statistics layer, not the bridge.

## B4: HTE work → PR #86 attempts, per candidate or per chunk?

| alternative | scientific validity | accounting correctness | cost |
|---|---|---|---|
| **`per_candidate_attempts`** (implemented) | Each candidate's failure, retry and terminal is its own record, so a failed-after-read candidate stays in every count. | It matches PR #86's contract, under which an attempt is one executable. Its identity, retry and terminal rules apply unchanged. | 2 ledger records per candidate. Linear on the indexed ledger (3.0× the HTE run at 100k). |
| `per_chunk_attempt` (up to 512 candidates) | A chunk's outcome hides which candidates failed. A partial chunk failure must be failed or retried as a whole. | It needs a new PR #86 attempt kind whose identity is a set of executables. That changes PR #86's attempt contract, and every rule (retry identity, completion identity, the reconciler) would need a set version. | About 512× fewer records |

**Recommendation: `per_candidate_attempts`.** The indexed ledger removed the cost argument for chunking. Confirming B4
records what is already built; the alternative would be a PR #86 redesign.

## A-1: Which module may write HTE completions to the ledger?

**Question.** PR #86 lets only `manhattan/ledger.py` and `manhattan/engine/evaluate.py` call `Ledger.record_evaluation`
(`tests/test_manhattan_binding_access.py` `ALLOWED`: "adding a module here is a reviewable decision"). The bridge
does not call it. `complete` refuses (`OwnerDecisionRequired: A-1`) unless the caller injects a writer, and only the
tests and the benchmark do.

| alternative | scientific validity | accounting correctness | effort and risk |
|---|---|---|---|
| **(a) add `manhattan/hte_accounting/bridge.py` to `ALLOWED`** | No change: the completions are the same records. | Completions are written by a module that did not read data through a PR #86 window (see A-3). Protected roles are still impossible: `record_evaluation` requires a `CompletionProof` for reserve and forward, which only `engine.evaluate` can mint, and the bridge refuses every non-exploration fence. | One allowlist line plus removal of the injected writer. Small and reviewable. |
| (b) run HTE through `engine.evaluate` under an `AttemptContext` | Strongest: every value read is metered and bound to its attempt. | The completion is tied to a metered read. | A redesign of HTE's vectorised stages, one evaluation at a time, which costs most of HTE's throughput. |
| (c) keep HTE completions out of the ledger | Equivalent to D-10 = unregistered for outcomes. Attempts could be started but never completed, so the reconciler would report them unfinished. | Not coherent with D-10 = register. | none |

**Recommendation: (a), restricted to exploration.** Implement it only if D-10 = register. It is the smallest
change, and the boundary that matters (no protected-role completion without a proof) stays enforced by PR #86 itself.
Pair it with a test that the bridge module never mints or imports a `CompletionProof`.

## A-2: Ledger scaling, and which ledger HTE writes to

**Scaling: resolved.** PR #100, the indexed ledger, is merged.

| | main before PR #100 | indexed ledger |
|---|---|---|
| bridge accounting at 100k | 1,569 s (35.6× the HTE run) | 142 s (3.0×) |
| ledger-only cost per candidate, 10k–1M | | 0.85–0.90 ms, linear |

This PR's own measurements on the merged ledger are in its description.

**Still open: which ledger.**

| alternative | scientific validity | accounting correctness | operations |
|---|---|---|---|
| **(i) one dedicated, persistent HTE exploration ledger** | Reruns and nondeterminism are detected across HTE runs, because they share a key space. | One anchor to keep. HTE executables have their own `spec_hash` (engine and environment in the identity, #90), so nothing collides with engine looks. | Grows by about 3.6 kB per candidate (≈ 340 MB per 100k). Needs anchor custody (D-7), like the main ledger. |
| (ii) the main Manhattan ledger | The same as (i), plus one census for everything. | Exact. | HTE volume dominates the production ledger, and its anchor and audit time. |
| (iii) one ledger per HTE run | **Loses cross-run rerun and nondeterminism detection.** Measured: 1,681 reruns counted as new looks out of 100k, with every per-ledger reconciler passing. | Silently wrong at the aggregate level. | Smallest files. |

**Recommendation: (i).**

## A-3: Data identity

**Question.** A registered HTE attempt binds the synthetic panel's `data_hash`, checked by `verify_synthetic`, and declares
an exploration window. But HTE reads its own in-memory panel, not a PR #86 `PitStore` window, so PR #86 records no
metered read. The bridge states `data_read=True` on every terminal, which is conservative.

| alternative | scientific validity | accounting correctness |
|---|---|---|
| **(a) identity binding, synthetic panels only (as now)** | Sound for synthetic data: the panel is generated from a seed and verified by hash, and there is nothing to leak. | The attempt names exactly the data it used. The read itself is not metered. |
| (b) load the panel into a synthetic `PitStore` and compute inside the attempt's windows | Required for real data. It is the only way PR #86's access control (role fences, embargo, reserve) applies to what HTE reads. | Reads are metered and bound to the attempt. |

**Recommendation: (a) for synthetic panels only**, which the bridge already enforces: it refuses any panel that is not
the verified synthetic one. **(b) must exist before HTE reads any real data.** Until then, real-data HTE must not be
connected to the bridge.

## Also still open from earlier phases (#90)

- **Native engine environment identity:**
  - the numerical environment digest covers BLAS, NumPy and CPU flags;
  - whether two machines that produce the same bits count as one environment is unresolved.
- **AF schema:** the schema of HTE's result tables when HTE is used beyond throughput testing.
- **Anchor custody (D-7):** an independently kept anchor for any ledger HTE writes to (A-2).
