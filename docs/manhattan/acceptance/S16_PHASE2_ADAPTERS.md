# S16 phase 2: acceptance coverage for the HTE integration adapters

**Status: the adapters do not exist yet. Every adapter test is BLOCKED, and the verdict is NOT_READY.**

This phase extends the acceptance gate of draft PR #91 (`S16_ACCEPTANCE.md`). The PR #91 branch is unchanged; this
work is stacked on it. It prepares independent acceptance tests for two adapters:

| adapter | joins | owner |
|---|---|---|
| candidate-level HTE → PR #86 accounting | HTE (#89, with the #90 identity levels) to PR #86 | S11 |
| delayed-execution HTE → PR #93 | HTE to PR #93's lagged, costed execution | S14 / HTE owner |

It implements neither adapter.

The command, outcomes and verdict are unchanged:

```
python tests/acceptance/run.py --out report.json [--require-ready]
```

- The outcomes are PASS, FAIL, UNBOUND, ERROR, BLOCKED and SKIPPED.
- READY needs every id in `REQUIRED_IDS` to pass. The 31 phase 2 ids (30 plus HARNESS-03) were added to that list; no requirement was
  removed or relaxed.

## 1. Interfaces inspected (exact heads)

| PR | head | interface used |
|---|---|---|
| #90 (S11, stacked on #89) | `e64397d` | `hte.adapters`: `evaluation_spec`, `evaluation_binding_hash`, `executable_spec`, `lineage`, `to_pr86_identity`, `executable_accounting`, `PR86_KEY`. `Pr86AccessAdapter` and `Pr85ExecutionAdapter` are still disabled. |
| #91 (S16) | `2c3c2e0` | the gate, probes, runner and mutation check this phase extends |
| #93 (S14) | `50caa18` | `execution_realism`: `ExecutionTiming`, `ExecutionPolicy`, `execute`, `ExecutionResult.result_hash`, `CostModel.model_id`, `Source`, `screening.series`, `align_lagged`, `lagged_scales`, `present_trading_return`, `fixtures`. Nothing imports it. |
| #86 | `bab1a4d` | `access.register_evaluation`, `DeclaredWindow`, `Ledger.record_evaluation`, `Ledger.key`, `attempts.reconcile` |

## 2. How an adapter acceptance test runs

Each adapter test is parametrised over two **drivers** (`tests/acceptance/s16_drivers.py`):

- **`adapter`: the real adapter.** It is reported under the plain id, for example `ACC86-01`.
  - Its `requires` includes the adapter's capability probe:
    - `adapter:hte->access`: `Pr86AccessAdapter.enabled`;
    - `adapter:hte->delayed-execution`: any HTE ↔ `execution_realism` import, or an HTE `Policy.lag`.
  - While the probe finds nothing, the test is **BLOCKED**.
  - When the probe finds the adapter but `ADAPTER_BINDINGS` has no binding to its real API, the test is
    **UNBOUND**, which fails the run. S16 does not guess an API that S11 or S14 has not written.
  - An unimplemented adapter can therefore never appear to pass. HARNESS-03 checks this, and mutations MU1 and MU2
    switch an adapter on without a binding and require UNBOUND.
- **`oracle`: a test-only reference.** It is reported under `ORC-<id>`, area `harness`.
  - It is composed from the public functions of #90, #86 and #93, and nothing outside `tests/acceptance` imports it.
  - It shows that each test can be satisfied: it passes on a correct composition.
  - It shows that each test is sharp: mutations MO1–MO5 plant adapter-like defects in it, and the tests fail.
  - An `ORC-` pass never satisfies the adapter's id.

## 3. Candidate-level HTE → #86 accounting (ACC86)

The cross-check is the test's own. It joins HTE's results of record (`results.bin` and `hte.runner.reconcile`)
with PR #86's ledger and `attempts.reconcile`, and with #90's lineage. It does not trust driver output.

| id | requirement |
|---|---|
| ACC86-01 | one PR #86 attempt per HTE candidate, each started before it completes. The independent cross-check finds no discrepancy. Both reconcilers are clean, and HTE candidates = PR #86 executions = completions = keys = looks. Nothing is independently certified, and there is no test count. |
| ACC86-02 | **scientific binding identity**: lineage family, hypothesis and candidate equal HTE's frozen registry, and binding = `evaluation_binding_hash`. In `executable_accounting`, the scientific counts equal the frozen counts, nothing is held, and `independent_statistical_tests` is None. |
| ACC86-03 | **executable identity and deterministic hashes**. Identities are bit-identical across an independent runner. Engine, numerical environment, policy and **cost assumptions** each give a new executable for every candidate. Only the policy changes the scientific binding. Re-accounting gives a `rerun` of every look and never a new look. |
| ACC86-04 | **retry**. A crash after registration is `missing_terminal` and is not reconciled. A retry that changes the engine, environment, policy or candidate is refused. The identical retry reconciles, and the interrupted start stays visible. A completed attempt cannot be retried. |
| ACC86-05 | **deliberate accounting mismatches** (7 cases), each detected: a skipped candidate; swapped results; a conflicting result (nondeterminism, family suspended); a forged completion nobody registered; a family-relabelled record; an edited record (`ReconciliationError`); a divergent second engine (held by `executable_accounting`, with no false PR #86 nondeterminism). |
| ACC86-06 | every identity is exploration, not designated, blind and `hte-` batched. An HTE identity relabelled reserve cannot register, and nothing is written. |

## 4. Delayed-execution HTE → #93 (CON93 contracts, DEX93 integration)

**CON93 tests (PR #93 alone; they run as soon as #93 is in the tree):**

| id | requirement |
|---|---|
| CON93-01 | the lag defaults to at least 1. Lag 0 is refused unless explicitly allowed, and is then `throughput_only` with every statistic prefixed `same_close_optimistic_`. Nothing claims a realistic return. |
| CON93-02 | **cost assumptions and lag are in the result identity**: lag, cost multiple, capital, cost sources, shocks, and the missing-price policy (an assumption that changes no output here). Hashes are deterministic. `model_id` is a content address: a new name changes nothing, while any term or source changes it. |
| CON93-03 | **look-ahead**. Decision rows from t onwards reach only earning periods from t − W + 1 + lag onwards, and returns from day j onwards change nothing before day j. Lags 1, 2 and 5 are tested. |
| CON93-04 | **the volatility-target trap**: the scale s[i] reads g[:i−lag] only. |
| CON93-05 | **same-close leakage**. The planted same-close-only reversal has a Sharpe above 2 at lag 0 and falls by more than 2 at lag 1. `present_trading_return` refuses both results. |
| CON93-06 | no cost may claim `calibrated`, `realistic`, `actual`, `measured` or `live`. |

**DEX93 tests (the HTE → #93 integration):**

| id | requirement |
|---|---|
| DEX93-01 | **conformance**. At lag 0 (explicitly allowed), the result equals HTE's reference kernel bit for bit and HTE's results of record within 1e-12. The record's hash is re-derived from HTE's vectorised kernel. At lag 1 every computed candidate's result differs. |
| DEX93-02 | **lag and costs in the executable identity**. Lags {0, 1, 2} × cost multiples {1, 2} give six distinct executables, none equal to HTE's same-close one. All six are one scientific candidate. Engine or environment gives a new executable of the same binding. Identities are deterministic across runners. |
| DEX93-03 | **no look-ahead through the adapter**. Lag 0 is never implicit, and a delayed result is not labelled same-close. Perturbing realised returns from day j changes nothing before j, at lags 1 and 2. |
| DEX93-04 | the planted synthetic trend uses returns up to t−1 only, so it survives a one-day delay in its predicted direction. This guards against a mis-aligned lag. |
| DEX93-05 | **delayed evaluations in PR #86**: lag 1, lag 2, a ×2 cost and lag 0 are four separate looks, and a repeat is a `rerun`. A retry cannot change the lag or the costs. The identical retry reconciles. |
| DEX93-06 | delayed results and identities are bitwise deterministic. |

## 5. Mutation check (integration boundaries)

`tests/acceptance/mutation_check.py` keeps M01–M13 and adds 15 mutations. A mutation counts as caught when an
expected id ends FAIL, ERROR or UNBOUND.

**PR #90 and PR #93 code:**

- MX01: the executable ignores the numerical environment.
- MX02: the binding ignores costs.
- MX03: `executable_accounting` never flags divergence.
- MX04: the alignment ignores the lag.
- MX05: the volatility scale reads the future.
- MX06: `result_hash` omits the policy.
- MX07: lag 0 is accepted silently.
- MX08: `model_id` ignores the cost terms.

**Defects a faulty adapter would have (planted in the oracle):**

- MO1: it ignores the engine and environment.
- MO2: it ignores the policy.
- MO3: the lag is missing from the identity.
- MO4: it executes at the same close.
- MO5: it reads the next day's return.

**An adapter switched on without a binding:**

- MU1: the PR #86 adapter's flag is flipped.
- MU2: an HTE ↔ #93 import appears.

## 6. Remaining integration blockers (confirmed from the code)

1. **No candidate-level HTE → #86 adapter.**
   - `Pr86AccessAdapter` is disabled: B1 #86 unmerged, B2 D-10 exploration attempts unregistered, B3 D-1 counting
     unit, B4 chunk-to-attempt cardinality, B5 synthetic only.
   - "Candidate-level" (one PR #86 attempt per HTE candidate) is this phase's working assumption. B4 is still the
     owner's decision.
2. **No HTE → #93 binding** (PR #93 X5): HTE has no lag, and `kernels.EXECUTION_TIMING` is the same-close constant.
3. **HTE's binding has no lag field.**
   - `evaluation_spec["execution"]` is a constant label, so the binding cannot tell lag 0 from lag 1.
   - A delayed adapter must add the lag, the timing label, the execution model and the cost model to the binding.
     Otherwise same-close and delayed evaluations share a PR #86 key: a false `rerun`, or a `nondeterminism` that
     suspends the family. This is the same class of defect #90 fixed for engines.
   - DEX93-02 and MO3 enforce this.
4. **Conformance to HTE's records needs a tolerance or a vectorised lagged kernel.**
   - HTE's results of record come from the vectorised `stage3_series`.
   - PR #93 reproduces the reference `ref_stage3_series` bit for bit (112 of 112 computed candidates). It differs
     from the vectorised kernel by up to 2.1e-17.
   - An adapter therefore cannot verify against HTE's recorded series hashes. Either HTE gains a vectorised lagged
     kernel, or the conformance tolerance (1e-12 in DEX93-01) becomes a recorded decision.
5. **#93 restates #85's arithmetic** (X1), and on synthetic data its costs are estimated or scenario only (X2).
   `exploratory_grade` and `present_trading_return` are unreachable, by design.
6. **Unchanged from phase 1:** GAP-03 to GAP-07 (evidence producer, equities domain, independent anchors, trusted
   authority, D-1). #90 also notes that the native engine's `code_version` has no numerical-environment digest.
7. **The adapter binding itself.** When S11's or S14's adapter merges, someone writes its binding in
   `s16_drivers.ADAPTER_BINDINGS` against the merged API, in a reviewed change. Until then those ids stay BLOCKED,
   then UNBOUND.

All protected capabilities stay disabled:

- reserve, claims, real money and HTE stage 5;
- both HTE adapters' `enabled = False`;
- PR #93 `CALIBRATED = False`.
