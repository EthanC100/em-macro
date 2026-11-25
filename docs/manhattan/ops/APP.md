# The Manhattan operations app (v1)

Code: `manhattan/app/` (`model.py`, `render.py`, `demo.py`, `__main__.py`). Tests: `tests/test_manhattan_app.py`
(synthetic demo only). Standard library plus what the ops code already imports; no new dependency.

**State: v1 is an outcome-blind, read-only status page.** It reads frozen batch folders and, optionally, the private
ledger, and writes one static HTML page and a JSON export. It never writes to the ledger and **implements no way to
reveal performance**. The last section is a design for that, not an implementation.

## Running it

```
python -m manhattan.app demo --out DIR [--workdir DIR]
python -m manhattan.app build --batches data/manhattan/batches [--ledger-clone DIR | --remote PATH] --out DIR
```

- `demo` builds a fully synthetic batch AB-0001 and ledger in a temporary directory (kept in `--workdir` if given),
  following `tests/test_manhattan_ops_e2e.py`:
  - ten SYNTHETIC mock families, with exploration screening recorded privately (weight 0);
  - `freeze_pr.prepare`, then a local bare repository as the ledger;
  - one capture-only night (12 November 2026), registration (merged 13 November 15:00 UTC, witnessed 16:30 UTC),
    and nightly runs on 16 and 17 November with a fixed fake clock. The Friday run is missed by design.
  - It never touches the network or a real ledger. Forward attempts record the repository's HEAD as their commit,
    because the runner verifies `config/manhattan.yaml` at that commit (D-12), so the demo needs a git checkout.
  - It takes about 20 seconds.
- `build` reads batch folders through `runner.load_batch`, which checks canonical form, spec hashes and the Merkle
  root. The ledger is optional:
  - `--ledger-clone`: an existing clone, read from disk without git; its hash chain is verified on load.
  - `--remote`: cloned read-only into a temporary folder.
  - Without either, the page shows specs and freeze data only.
- Output: `index.html` (self-contained: inline CSS, no script, light and dark themes, works at phone width) and
  `view.json` (the view model). A visible **SYNTHETIC DEMO** banner appears whenever the batch or ledger is synthetic:
  a family mechanism marked SYNTHETIC, a synthetic universe source, or a synthetic capture.

## What v1 shows

| section | content | source |
|---|---|---|
| overview | counts at each level (below), attempts by kind and terminal, registrations, runner status, evidence status and activation gates | manifest, specs, ledger |
| families table | id, batch, mechanism class, sign, channel, hypotheses, variants, registered predictions, registration status, evidence label, observation days recorded vs expected; ordered by id | as below |
| explanation | the family spec's fields verbatim: mechanism, mechanism class, predicted sign, counterparty, kill condition, tail exposure | frozen family spec |
| hypotheses | domain, frequency, signal kind and description, fixed parameters, grid, grid justification (reason, mechanism range), primary binding, timing | frozen hypothesis specs |
| executable variants | executable id, variant id, parameters, universe, domain, cost model id, sizing id, spec hash, prediction id | executable and variant specs |
| freeze version | batch, manifest hash, Merkle root, template hash, protocol hash, code version, generator model | manifest, executable specs |
| data provenance | declared sources (frequency, period label, publication lag, availability); captured sources (kind, calendar, lag, grace, capture count, first and last capture date, failures); calendars | specs, `ops.data.SOURCES`, `capture` records (no values) |
| registration | provisional or witnessed, eligible or ineligible (with reasons), registration time, first observation, merge time and commit, witness | `registration` records |
| attempts | per prediction and kind: registered executions, completed, failed, aborted, unfinished, retries | `attempt_*` records |
| runner status | last heartbeat, missed runs, last lock and unlock, active and broken locks, journal entries and unfinished entries, chain check, ledger head | ledger records and journal |
| coverage | per prediction: expected, recorded, missed-observation, reconstructed and pending days (counts only) | registrations, `observation` / `missed_observation` existence, calendar |

**Counting levels stay separate** (BINDING_ACCOUNTING.md section 2):
- families, hypotheses, variants;
- unique executable configurations (distinct executable spec hashes);
- registered predictions;
- attempts (registered executions; each retry is one more).

No level is offered as a multiple-testing denominator (D-1).

**Expected days** are the sessions of the universe's calendar after the first observation, up to the last heartbeat
(`ops.forward.sessions`, the runner's own rule). **Pending** means expected but neither recorded nor yet declared
missed (within the sources' lag and grace).

## The blinding guarantee

1. **Allow-list.** The model is built only from fields that are explicitly allowed.
   - Each ledger record passes through `model.project`, which keeps only the fields `model.ALLOWED` lists for its
     type. An observation keeps its prediction, date, eligibility, `reconstructed` flag and registration status; its
     net, gross, cost, exposure and turnover are never read.
   - A screening record keeps its executable, hypothesis and role. Its summary and result hash are never read.
   - A float, or a string spelling a decimal, in an allowed field makes the projection fail. A schema change upstream
     therefore stops the build instead of leaking.
   - `ops_manifest.json` and `PR_BODY.md` are not read: their variant report holds an effective variant count and
     power figures computed from screening returns.
2. **Checker.** `model.assert_no_outcomes` runs on every view before it is returned and again before rendering. It
   refuses:
   - any key on the deny-list, by exact name or by token (net, gross, return, pnl, sharpe, turnover, exposure, rank,
     score, hit rate, summary, result hash, power, effective variants, drawdown, ...);
   - any float anywhere;
   - any decimal-looking string outside the spec parameter contexts (`grid`, `point`, `parameters`,
     `fixed_parameters`, `mechanism_range`).

   Its error names paths, never values.
3. **No ordering by performance.** Everything is ordered by identifier.
4. **Tests.** The demo ledger's outcome values (every observation and screening value, more than 300 needles) are
   given to `ops.leakscan`. It scans the rendered page, the JSON export and the output folder, and must find nothing.
   A planted value in free text is shown to be caught. A walk of the JSON finds no float and no denied key.

**Limits, stated plainly.**
- The checker sees keys and value types, not meaning. An outcome written into free text of a frozen spec (a
  mechanism description) would pass it. Only the leak scanner in the tests catches that, and only for the values it
  is seeded with. Specs are frozen before any forward outcome exists, but they are written after exploration.
- Integer counts are allowed. Coverage counts tell how many days were recorded, which says nothing about their
  values. Attempt terminals show that a run failed, not why beyond a fixed reason class.
- Anyone who can read the private ledger can read outcomes directly. The app protects its own outputs, not the
  ledger.
- The ledger's commit history, raw captures and private logs are not read. The app trusts that the chain it verifies
  is the one the runner wrote; tamper evidence is the ledger's job (LEDGER.md).
- A page built from the real ledger holds no outcome, but it does show registration and run activity. Treat it as
  private operations output, not as a public health record (`ops.blinding` defines what may be public). Reading the
  real ledger needs its deploy key, which no Claude Code session holds.

## Evidence labels

`model.evidence_label` is the only source of a label. It uses the existing vocabulary only:
- `promotion.status` (`manhattan/ops/promotion.py`);
- the registration's recorded ineligibility reasons (`manhattan/ops/timing.py`);
- the evidence classifier's eligibility and provenance values (`manhattan/evidence.py`).

Today every prediction reads **`not eligible: activation gates closed`**. Two things keep it there: no protocol hash
is adopted (`ADOPTED_PROTOCOLS` is empty) and `claims.enabled` is false. The activation gates G-1 to G-6 and B-1 to
B-3 (BINDING_ACCOUNTING.md sections 18 and 19) are listed on the page as not lifted. v1 cannot lift them.

Even with promotion switched on, the app classifies nothing itself:
- an ineligible registration shows `not eligible: <recorded reasons>`;
- an eligible one shows `eligibility: none (unverified)`, because no evidence classification is wired into the ledger
  and the classifier trusts no authority.

`eligible_for_evidence` is false in every case in v1.

## Design (not implemented): later access to unpublished performance

**Nothing in v1 implements any of this.** v1 has no reveal path, no role check and no access log. The design below
must be reviewed and adopted by the owner before any code exists, and it must not weaken the blinding rules above for
the default page.

**Eligibility to reveal.** Forward performance may be shown only when all of these hold:
- the adopted protocol's publication and look rules allow that look (its schedule, its e-process or FDR accounting:
  a reveal is a look, and is counted as one);
- the activation gates for the evidence in question are lifted;
- `promotion.status` reports an adopted protocol with claims enabled.

Before that, the answer is a refusal that names the closed rule, never a partial or rounded value. Screening
(exploration) values follow the same rule. They are not evidence, but they can steer a generator or an approver.

**Role separation.**
- **Owner as freeze approver**, and every agent and generator session (blind and adaptive generators, critics, the
  night shift, any Claude Code session): never see unpublished forward performance, rankings, or anything ordered or
  filtered by it, including counts of "positive" predictions. The default page is theirs.
- **Auditor / statistician** (a separate person or a separately credentialed process, not the freeze approver):
  sees unpublished performance only under the protocol's rules, for the purposes the protocol names (verification,
  the scheduled statistical review). Results leave that role only as protocol-defined outputs: decisions, tier
  changes and published summaries.
- The roles are separate credentials, never a page toggle. The reveal view would be a different build, with a
  separate output location, run only where the auditor's credential and the ledger key exist. The public repository
  and its Actions never produce it.

**Append-only access audit trail.**
- Before any value is decrypted, read or rendered for a reveal, an `access_request` record is written to the private
  ledger. It holds who, which role, which predictions or batch, which protocol rule authorizes it, and why.
- The write goes through the existing journal, hash chain and mirror. The reveal proceeds only after the record is
  verified on the remote, the same "registration before exposure" rule the attempts use.
- A matching `access_completed` (or `access_refused`) record follows. The record holds no values.
- An access whose request record is missing is a reconciliation violation, like an unregistered attempt.

**Break-glass.** For an operational emergency (a suspected data error or a runner bug that needs values to diagnose):
- a separate `break_glass` request record names the reason class and the person;
- it is witnessed (the same external timestamping as manifests) before access;
- it is visible on the default page as a count and a date, never a value;
- it marks every prediction whose values were seen as exposed. For example, such predictions keep their observations
  but lose eligibility for the affected look until the protocol says otherwise. It must be reviewed by the owner
  afterwards.

Break-glass access is never available to agents or generator sessions.
