# The always-on paper runner and its private ledger: control, binding, recovery, blinding, readiness

Session "Manhattan operational path", 2026-11-25. Paper-only. Everything here was rehearsed on synthetic data; no
real data was read, no workflow was dispatched, no setting, secret or protected path was changed. Code:
`manhattan/ops/paper_readiness.py`, `manhattan/ops/audit.py`, the runner's `--rehearsal` mode
([ENTRYPOINT_EVIDENCE.md](ENTRYPOINT_EVIDENCE.md)). Tests: `tests/test_manhattan_ops_paper_readiness.py`,
`tests/test_manhattan_ops_entrypoint.py`.

## 1. Readiness result for the first 10-20 owner-frozen families

`python -m manhattan.ops.paper_readiness --families 20 --rehearse` on this branch:

**Paper recording: NOT READY.** The machinery passes its rehearsal; what blocks it is owner steps and two pieces of
engineering. Forward observations will not count as evidence even once recording starts (activation gates).

| id | check | status | who acts |
|---|---|---|---|
| R01 | ≥ 10 owner-frozen families in `data/manhattan/batches` | **blocked_owner**: 0 batches | families originate in the family chat; Ethan freezes by merging the manifest PR |
| R02 | runner workflow dispatch-only, main-only, secrets in a main-only environment | ready | |
| R03 | runner schedule enabled | blocked_owner | ETHAN_OPS_ACTIONS step 9 |
| R04 | a production path runs `runner register` | **blocked_build** | draft [drafts/manhattan-ops-register.yml](drafts/manhattan-ops-register.yml); installing it is a deployment decision (Ethan) |
| R05 | the timing witness is verified by code | **blocked_build** | `register` trusts the witness JSON's `verified` flag. Needs Ethan's choice of witness and of who runs its verifier |
| R06 | workflow installs the hash-locked environment (G-4) | blocked_owner | adopt `requirements-manhattan-runner.lock` |
| R07 | ops switches protected in CODEOWNERS | blocked_owner | step 8 |
| R08 | critic agent installed | blocked_owner | step 6 |
| R09 | private ledger repo, deploy key, main-only environment, sessions kept out | blocked_owner (not visible to a session) | steps 1-3 |
| R10 | independent mirror | blocked_owner | step 4 (custody) |
| R11 | independent anchor custody (D-7, G-2) | blocked_owner | section 2 |
| R12 | blind generator passes the isolation kit | blocked_owner | steps 5, 7 |
| R13 | reserve, claims, promotion off | ready | |
| R14 | forward observations may count as evidence | blocked_gate | G-1..G-6, B-1..B-3 (BINDING_ACCOUNTING.md §16, §19) |

**Rehearsal through the real entry point** (separate processes, `python -m manhattan.ops.runner ... --rehearsal`;
capture night, registration, two observation nights, a hard kill after a protected read, its restart; this
container, Python 3.13):

| families | unique executable configurations | registered predictions | total attempts | completed | aborted (interrupted, retried) | failed | reconciled | violations |
|---|---|---|---|---|---|---|---|---|
| 10 | 27 | 27 | 108 | 81 | 27 | 0 | true | none |
| 20 | 54 | 54 | 216 | 162 | 54 | 0 | true | none |

Wall seconds per run at 20 families: capture 2.3, registration 0.8, observation nights 5.5 and 6.1, killed run 3.0,
restart (recovery + 54 retries) 7.3. The workflow's timeout is 60 minutes and the lock's 75: at this scale a night
uses well under 1% of it. Ledger working tree after the sequence: 12.6 MB, almost all of it synthetic raw captures
(the synthetic source re-sends its whole history each night; FRED does too, so capture storage, not attempts,
dominates growth: see BENCHMARKS_OPS.md when merged). `independent_statistical_tests` stays `null` (D-1).

## 2. Who controls the ledger and the anchor

| asset | controlled by | how | what it cannot prevent |
|---|---|---|---|
| private ledger `EthanC100/manhattan-ledger` (chain, journal, raw captures, private logs) | **Ethan** owns the repository; the **runner** writes it with a deploy key held only in the `manhattan-ledger` environment (deployment branch `main`) | no session, agent or generator environment has access (ETHAN_OPS_ACTIONS step 3) | the key holder can rewrite history consistently |
| mirror | Ethan's choice (step 4: another provider; plus the iMac pulling) | fast-forward only; verified record by record and tree by tree after every run | a writer of both |
| **anchor** `{records, head}` | **must not be the writer** (D-7). Recommendation: Ethan's iMac retains each night's anchor printed by `python -m manhattan.ops.audit --remote … --print-anchor`, and optionally an OpenTimestamps stamp of the head | the auditor compares the ledger to the retained anchor (section 4) | until an independent custodian exists, results are `checked_against_supplied_anchor`, never independently certified |
| em-macro `main` (frozen batches, code, `config/manhattan.yaml`) | Ethan merges; protected paths in CODEOWNERS | the runner reads batches and the fence only from `main` at its commit | |

The runner's public health record carries `ledger_head` and `ledger_records`; Actions keeps it at most 90 days, so
it is a short-lived public anchor, not custody.

## 3. How timestamps and frozen versions are bound to prediction records

Every link is a hash recorded in the private ledger before the record that depends on it.

1. **Freeze.** `freeze_pr.prepare` writes the batch: canonical specs, their SHA-256s, the Merkle root, the manifest
   (template hash, code version, protocol path), and `PR_BODY.md`. Ethan's merge is the freeze. The manifest's bytes
   are hashed (`manifest_hash`); the runner refuses a batch whose manifest is not canonical or whose specs or root do
   not match (`runner.load_batch`).
2. **Registration** (`runner register`): per executable a `registration` record with `prediction =
   AP-sha256(manifest_hash + executable spec hash)`, `spec_hash`, `manifest_hash`, the **merge time from the GitHub
   API** (`merged_at`, server side) and `merge_commit`, the witness `{kind, digest, attested_utc, verified}`,
   `registration_utc` (the later of merge and witness), `registration_status` (`provisional` / `witnessed`),
   `first_observation`, eligibility and its reason, batch, executable, hypothesis, family, domain, universe, channel.
   Gap R05: `verified` is not checked by code yet.
3. **Each night's attempt** (`attempt_started`) binds: the executable's spec hash, variant, hypothesis, family IDs,
   batch, channel, role `forward`, the window, the **data hash** of the point-in-time store built from first-seen
   captures, the **code version** (em-macro commit + engine digest), and the **configuration claim** `{sha256,
   commit}` (the fence in `config/manhattan.yaml` at that commit, verified at registration and re-verified by the
   reconciler), plus run id and attempt, and `retry_of`.
4. **Observations** carry their date, values and provenance (`reconstructed`, eligibility, weight); the completion
   recomputes the forward plan from the ledger's own captures and the registration in force, and lists each linked
   result's key, content hash and disposition. Every record carries `ts_utc`, run id/attempt, commit, a nonce and
   the previous record's hash.

Timestamps are as good as their source: `ts_utc` is the runner's clock (GitHub's VM); merge time is GitHub's
server; only the witness is independent of GitHub, and only once it is verified (R05).

## 4. Recovery and audit

**Recovery is automatic.** Every run: open (verify chain) → finish unfinished journal entries → lock (break an
expired lock or the same run's earlier attempt) → finish entries again under the lock → abort every unfinished
forward attempt as `interrupted` (`data_read: null`) → normal work, retries naming `retry_of`. Proven at the entry
point for a hard death after a read and during the results write ([ENTRYPOINT_EVIDENCE.md](ENTRYPOINT_EVIDENCE.md)).
A source outage is `capture_failed` and the run is `partial`; a missed night becomes `missed_run`; late data
become `reconstructed` (weight 0).

**Restore from the mirror** (if the primary is lost or rewritten): the auditor compares both against the retained
anchor; the one that reaches the anchor with a valid chain is restored by Ethan to a new private repository and
the runner's remote is pointed at it (a settings change: Ethan).

**Audit** (`python -m manhattan.ops.audit --remote R --anchor A.json [--mirror M]`): clones afresh, verifies the
chain, checks the anchor, compares the mirror, runs the attempt reconciler; prints status words, counts and
violation codes only, so an auditor without access to forward performance can run it. A rewritten history fails
against the retained anchor (`test_audit_cli_reconciles_and_detects_a_rewritten_history`).

## 5. Generator isolation and blinding: what was verified

Rule: the owner, as freeze approver, and every agent (including generators and build sessions) see no unpublished
forward performance and no ranking.

| channel | what it carries | verified by |
|---|---|---|
| runner stdout / Actions log | one health record: counts, dates, hashes, status words, no decimal number | `test_public_output_of_the_entry_point_is_the_health_record_only` (process level), `test_manhattan_ops_blinding.py` |
| step summary | the health record | `test_step_summary_and_failure_notification_carry_no_private_value` |
| **notification**: failure issue `[ALERT] Manhattan ops runner failed` | `runner issue-body` of the health record: stage and exception class only | same test, with the private value placed in the exception text |
| private log | full tracebacks: goes only to the private ledger | same test (the value is in the private log, nowhere public) |
| attempt terminals | reason class and `data_read` only | same test; BINDING_ACCOUNTING §6 |
| artifacts, caches | none uploaded; pip cache only | workflow + `test_manhattan_ops_e2e.py::test_no_performance_value_in_any_public_channel` |
| **exports / API**: audit output | counts, codes, hashes | `test_audit_cli_reconciles_and_detects_a_rewritten_history` (leak scan) |
| exports / API: readiness output | counts and seconds | `test_rehearsal_through_the_real_entry_point_reconciles` |
| exports / API: operations app | see APP.md (allow-list model + leak scan) | the app's tests, when merged |
| exports / API: orchestra status (`orchestra/status.py`, loopback HTTP) | job statuses, counts, hashes; every job kind is synthetic today | its own tests; **must be re-audited before any kind touches real data** |
| freeze PR body (what the owner sees when approving) | spec text, hashes, raw and effective variant counts, power loss; screening returns are used in memory for the effective count only and never written | `freeze_pr.py`; no ranking or performance field |
| generator prompt | `blind_request` takes counts and domain names only: no result, path or free text can reach it | `test_manhattan_ops_e2e.py::test_nothing_reaches_the_generator` |
| generator environment | network, clones, files, credentials, tools, inherited context, indirect channels | `isolation_kit.py`; **only a run inside the blind environment can PASS** (R12); this session fails it by design |
| pretraining | cannot be closed | stated (BLIND_GENERATOR.md) |

The owner is the freeze approver and the ledger's owner. Holding the repository gives the technical ability to read
it; blinding of the owner is procedural: Ethan does not add the ledger to any session and does not read
observations. **A technical separation (the owner unable to read forward values) needs a different custody** (for
example the ledger readable only by a separate auditor account) and is listed as an owner decision.

## 6. Escalations (Ethan's credentials, custody or deployment authorization)

- Create the ledger, its deploy key and environment, keep sessions out (steps 1-3); choose the mirror (step 4).
- Choose the anchor custodian (not the writer), and whether the owner should be technically unable to read
  forward values (section 5).
- Choose and authorize the timing witness and its verifier (R05); authorize installing the registration workflow
  (R04); adopt the hash-locked environment (R06); protect the ops switches (R07); install the critic (R08).
- Create the blind environment and record an isolation-kit PASS (R12).
- Freeze the first 10-20 families (R01), then the first manual run and the schedule (R03).
