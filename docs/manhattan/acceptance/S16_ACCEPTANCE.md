# S16: system acceptance gate for the integrated synthetic research platform

Status: **the acceptance gate is NOT_READY.** This suite is independent of the five approved Manhattan PRs: #84
(evidence classification), #85 (futures execution), #86 (binding attempt accounting), #87 (technology equities) and
#89 (HTE). It changes no code in them and adds no adapter. It enables nothing, and it reads no real, licensed,
reserve or forward data.

## 1. One command

```
python tests/acceptance/run.py --out acceptance.json [--label "<what tree this is>"] [--require-ready]
```

- **Pytest.** It runs `tests/acceptance/` under pytest. The suite also runs inside the normal full suite and the
  `tests` workflow, where every test it cannot run skips.
- **Report.** It writes a JSON report with schema `manhattan.s16.acceptance/1`. The report holds:
  - every test, with its acceptance id, area, outcome and reason;
  - the capability probes;
  - a rollup by id;
  - the verdict.
- **Outcomes.**
  - `PASS`.
  - `FAIL`.
  - `ERROR`: a fixture or setup failed.
  - `BLOCKED`: a required capability is missing. The probe states the reason, from the code.
  - `UNBOUND`: the capability has appeared, but the test has not yet been bound to its API.
  - `SKIPPED`: any other skip. It never counts as a pass.
- **Verdict.** `READY` requires all of the following. Otherwise the verdict is `NOT_READY` and lists the reasons.
  - Every id in `REQUIRED_IDS` (run.py) ran.
  - Every test passed.
  - Nothing was blocked, skipped or unbound.
  - pytest exited 0.
- **Exit status.**
  - `0`: no test failed.
  - `1`: a test failed, errored or was unbound, or a required id is missing.
  - `3`: `--require-ready` was passed and the verdict is not READY.
- **No claim of scientific verification.** `scientifically_verified` is always `false`, and `evidence_class` is
  `synthetic_acceptance_only`. Passing the gate shows only that the synthetic platform behaves as specified. It
  shows nothing about markets.

A mutation check confirms that the suite catches defects:

```
python tests/acceptance/mutation_check.py --tree <disposable worktree> --out mutations.json
```

- **What it does.** It plants 13 defects (M01–M13), one at a time, in the platform code of a disposable linked
  worktree. Each time it runs the suite and requires an expected acceptance id to fail. The planted defects include:
  - a results hash that is never checked;
  - a bypassed synthetic check;
  - a skipped PIT probe;
  - a fill at the decision's own close;
  - a forged weight that is honoured;
  - an erased interrupted attempt.
- **Safeguards.** It refuses a primary checkout and any tree with uncommitted platform code. It restores each file.

## 2. The end-to-end synthetic experiment

| id | area | what is accepted |
|---|---|---|
| E2E-01 | frozen hypothesis registration | HTE registry submit + freeze. Each candidate id is the hash of its canonical configuration. A run is bound to its frozen root, and a later registration cannot change that run. |
| E2E-02 | evaluation identity | The run identity contains registry root, data hash, engine digest, policy, fence, methodology, stages, execution timing and numerical environment. It does not depend on chunking. Any change gives a new identity. |
| E2E-03 | synthetic data | Only verified generator output runs. Arrays are read-only. |
| E2E-04 | authorized computation | Reads stop at the fence. The protected tail is refused, and stage 5 is disabled. |
| E2E-05 | attempt accounting | Every registered candidate has exactly one terminal status per stage. Attempt counts balance, and per-candidate history is complete. |
| E2E-06 | statistical testing | Each family has an SPA with p in [0,1]. Denominators cover every candidate exactly once. A planted synthetic effect is found (power check), and the result is still labelled synthetic and non-confirmatory. |
| E2E-07 | reconciliation | The reconciler rebuilds the result bit for bit from the attempt files. An independent recomputation reproduces it. HTE never claims access reconciliation. |
| E2E-08 | research-only output | No package, run record or log payload says confirmatory, verified, significant, discovery or eligible. |
| E2E-09 | cross-PR identity (#89→#86) | Every HTE attempt identity passes PR #86's own `ledger.validate_attempt_identity`. The role is exploration and the attempt is not designated. No two candidates share an identity. |
| E2E-10 | binding accounting (#86) | A synthetic exploration attempt registers, reads through its context and reconciles. It is never independently anchored or certified. |
| E2E-11 | execution realism (#85) | Fills happen at a later close. Net equals gross minus costs, and the result is deterministic. The package is research-only and uncalibrated. |
| E2E-12 | equities PIT (#87) | In the synthetic world, an as-of read hides a delisting return that is not yet known. Runtime integration is off. |
| E2E-13 | cross-PR interface (#87→#84, #86) | Every interface PR #87 recorded for #84 and #86 is a `structural_match` with the merged code. |
| E2E-14 | evidence of the run (#89→#84) | Shipped state: HTE output classifies as unverified with weight 0. Under a simulated trusted authority it reaches at most synthetic/`infrastructure_validation`, still with weight 0. Promotion is refused. |

## 3. Adversarial tests

| id | attack | required response |
|---|---|---|
| ADV-LA-01 | register a template whose position at t reads r[t+1], even with the test allowance | rejected by the PIT probe; reason logged |
| ADV-LA-02 | read past the fence; use carry before publication | `ProtectedDataRefused`; carry is lagged one day |
| ADV-LA-03 | fill at a price already published; inputs known after the decision; lag 0; decision exactly at the close | `LookAheadError` / refused; the fill falls on a later day |
| ADV-LA-04 | equities: read past `as_of`; a delisting with no known return; restatement before it is public | `TemporalError`; `CorporateActionError` (survivorship); value invisible |
| ADV-DUP-01 | re-submit the registered specs | nothing registered; `duplicate_submission` logged |
| ADV-DUP-02 | re-run an identical closed evaluation | reused; no new attempt; same root |
| ADV-DUP-03 | evaluate a finished PR #86 attempt again, or "retry" it | `AccessError`; `LedgerError`; nothing written |
| ADV-DUP-04 | combine the same evidence twice | unverified |
| ADV-INT-01 | hard exit after an attempt start; torn completion line | no result reported; state `incomplete`; resume gives the clean result; the interrupted attempt is counted and superseded |
| ADV-INT-02 | process dies after a PR #86 registration | `missing_terminal`; not reconciled until a superseding retry completes |
| ADV-COR-01 | flip a results byte; delete results; corrupt an attempt file; edit a package to say confirmatory | state `corrupted` with the specific violation |
| ADV-COR-02 | alter, delete or reorder an HTE log record | `LogError` from verify and from reconcile |
| ADV-COR-03 | swap panel values; relabel the generator | `NotSynthetic` |
| ADV-COR-04 | delete, truncate or alter the Manhattan ledger | `ReconciliationError` |
| ADV-PRO-01 | claimed labels; untrusted verifier; forged or mutated classification; metadata edited after verification | weight 0; unverified |
| ADV-PRO-02 | promote any tier; with a forged `claims.enabled` | `PromotionDisabled` |
| ADV-PRO-03 | promote an equities research record | `EvidenceError`; weight 0 |
| ADV-PRO-04 | ask HTE for confirmatory output | impossible in code; stage 5 refuses |
| ADV-PRT-01 | configuration | reserve, claims and real money are off; loss cap 0; exploration ends 2019-12-31 |
| ADV-PRT-02 | stage 5 or a disabled adapter with `enabled=True` | refused |
| ADV-PRT-03 | reserve read with a valid token but no attempt; session or explorer callers; reserve without token; forward dates as exploration; exploration attempt opening reserve dates | refused; nothing written |
| ADV-PRT-04 | licensed equities data into the public store; non-synthetic research scope | refused |
| ADV-PRT-05 | static: network clients or private-store names in the new packages | none |
| ADV-OBS-01 | a failure in stage 4 | `run_failed` with its phase; no `run_closed`; the stray results file is reported as not of record |
| ADV-OBS-02 | invalid spec; insufficient disk | `submission_rejected` with reasons; `run_refused` |
| HARNESS-01/02 | the gate itself | the verdict fails closed on any blocked, skipped, unbound, failed or missing id; probes never raise |

## 4. Integration gaps (BLOCKED today, confirmed from the code)

Each gap test is BLOCKED while its probe finds the capability missing. Once the capability appears, the test fails
as `UNBOUND` and prints its criteria until it is bound to the real adapter. S16 does not guess an adapter API.

| id | capability | probe evidence on the five-PR tree | acceptance criteria |
|---|---|---|---|
| GAP-01 | HTE → PR #86 attempt accounting | `hte.adapters.Pr86AccessAdapter` is disabled (B1–B5) | each HTE attempt is registered in the Manhattan Ledger before it computes, with cardinality per B4. `attempts.reconcile` counts equal HTE's. A registration failure leaves no `run_closed`. The role stays exploration. |
| GAP-02 | HTE → PR #85 execution | `Pr85ExecutionAdapter` is disabled (E1–E4); HTE fills at the decision close | stage 3 runs through `execution.run` with lag ≥ 1. The timing is in the identity and in every package. |
| GAP-03 | HTE → PR #84 evidence | no production module imports `manhattan.evidence` | each package carries evidence metadata and verifier results from code. It classifies as synthetic/`infrastructure_validation` with weight 0. An edited package is unverified. |
| GAP-04 | PR #87 → HTE | HTE accepts only its own generator | the synthetic equities world becomes an HTE domain. The PIT probe and the as-of, delisting and restatement guards hold inside HTE. |
| GAP-05 | independent anchors | `attempts.reconcile` reports `independently_anchored: False` as a constant (D-7, G-2) | an independent custodian holds the ledger and HTE log anchors. The field is true only against those anchors. |
| GAP-06 | trusted verifier authority | `evidence.TRUSTED_AUTHORITIES` is empty | an authority exists for `spec_registry` and `synthetic_generator`, with keys outside the repository. E2E-14 passes without patching. |
| GAP-07 | counting unit D-1 | HTE BLOCKERS lists "B3 counting unit open (D-1)" | one decided unit is shared by the HTE denominators and PR #86 `distinct_specifications`. |

## 5. Results (19 November 2026)

| tree | PASS | FAIL | BLOCKED | verdict | report |
|---|---:|---:|---:|---|---|
| main `9b24bd7` with only this suite | 5 | 0 | 51 | NOT_READY | `results/manhattan_acceptance/main.json` |
| local scratch merge of the five PR heads onto main (never pushed) | 49 | 0 | 7 (GAP-01–07) | NOT_READY | `results/manhattan_acceptance/integration_5pr.json` |
| mutation check on the same scratch tree | 13 of 13 planted defects caught | | | | `results/manhattan_acceptance/mutations_integration_5pr.json` |

- **PR heads tested:** #84 `e1882be`, #85 `3f6b213`, #86 `bab1a4d`, #87 `8c210a0`, #89 `232d0d6`.
- **Merge:** the local octopus merge of the five heads onto main `9b24bd7` had no textual conflicts. This is not an
  integration review; that is S6's.
- **Run time:** the whole suite takes about 11 s on the merged tree, plus about 4 s for each interrupted-run
  subprocess case.

**Observations, not defects:**

- **Two meanings of "reconciled".** HTE `reconcile` always reports `access_reconciled: False`. PR #86's
  `attempts.reconcile` reports `access_reconciled: True` for a clean synthetic exploration attempt. These are two
  separate accounting systems, and today neither sees the other's attempts (GAP-01).
- **Same-close execution in HTE.** HTE's same-close execution (`kernels.EXECUTION_TIMING`) is at least one day more
  optimistic than PR #85's model. The acceptance suite accepts HTE statistics only as synthetic throughput or
  pipeline output (GAP-02).

## 6. When the integrated synthetic platform is ready

All of the following, checked on `main` (not on a scratch merge):

1. **Merged.** PRs #84, #85, #86, #87 and #89 are merged through Ethan's review, with no change to protected paths.
2. **Gate passes.** `python tests/acceptance/run.py --require-ready --out <report>` exits 0 on main:
   - verdict `READY`;
   - every id in `REQUIRED_IDS` passes;
   - zero BLOCKED, SKIPPED, UNBOUND, FAIL and ERROR.
3. **Gaps bound.** GAP-01 to GAP-07 are bound to the real adapters and decisions and pass their criteria (section 4):
   - GAP-01 needs owner decisions D-1, D-10 and B4;
   - GAP-05 needs anchor custody;
   - GAP-06 needs a trusted authority, an owner decision.

   If the owner decides that a gap is out of scope for the synthetic platform, that decision is recorded, and the
   id is removed from `REQUIRED_IDS` in a reviewed change that cites it. A gap is never skipped silently.
4. **Defects caught.** `tests/acceptance/mutation_check.py` reports `all_caught: true` on a worktree of that main
   commit. Each new adapter adds at least one mutation of its own.
5. **CI green.** The `tests` workflow is green on the pull request that makes the gate READY. The suite runs in it
   unchanged.
6. **Repeatable.** Two consecutive runs on the same commit give the same `by_id` outcomes. E2E-07 reproduces the
   HTE result root bit for bit.
7. **Still disabled.** `config/manhattan.yaml` keeps:
   - `reserve.enabled: false`;
   - `claims.enabled: false`;
   - `forward.real_money: false`;
   - `forward.loss_cap_usd: 0`.

   ADV-PRT-01 enforces this. HTE stage 5 stays disabled. No real, licensed, reserve or forward data is read.

**READY means only** "the synthetic research platform is integrated and behaves as specified". It does not make any
result evidence. Forward evidence, the reserve and trading remain separately gated, by PR #86 G-1 to G-6, PR #84's
unimplemented gates, the protocol and Ethan's configuration.
