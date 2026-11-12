# Atlas architecture

Version 0.1, 2026-11-12, branch `build/atlas`. Phase B of [ATLAS_PROGRESS.md](ATLAS_PROGRESS.md). Design only: apart
from a hash check and a config loader, nothing described here is built yet. Statistical rules are in
[PROTOCOL_v3.md](PROTOCOL_v3.md); what exists today is in [AUDIT.md](AUDIT.md); decisions that are Ethan's are in
[ETHAN_ACTIONS.md](ETHAN_ACTIONS.md).

## 1. What Atlas is

Atlas is a research lab that starts from stated mechanisms, not from data. It may run up to 250,000 executable
strategies, but it judges evidence family by family. Three principles shape every component:

1. **Write it down before looking.** Every hypothesis, every parameter grid and every rule of evidence is frozen and
   hashed before a designated evaluation.
2. **Record every look.** Every evaluation of every executable, in every data role, is a ledger record. The number of
   executables measures compute, never evidence.
3. **History is a filter; the future is the test.** Historical screening runs at a 20% false discovery rate on data
   the generating model may know. Claims at 5% rest on data dated after the freeze.

## 2. Components

| # | component | job | built on | phase |
|---|---|---|---|---|
| 1 | Spec registry | canonical form, SHA-256, IDs, frozen-file check for families, hypotheses, variants, executables | `lab.book` (`sha256`, `registry`, `check_frozen`) | D |
| 2 | Generators | blind channel and adaptive channel; produce batches of 50-100 hypothesis specs | new; the night explorer is an adaptive generator | F |
| 3 | Critic | reviews each spec before freezing; never sees outcomes | The Opposition, restricted | F |
| 4 | Freezer | builds the batch manifest, tag and external timestamp | new; Ethan signs | F |
| 5 | Data roles | assigns every data point to exploration, reserve or forward and refuses reads across the fence | `nightshift.logs` cap for exploration; new for the rest | D |
| 6 | Engine | turns an executable into a daily net return series, core-hedged | `em_macro` modules (import only); new daily core-factor library | E |
| 7 | Ledger | hash-chained, append-only record of every evaluation; rerun detection | pattern of `ledger.audit`; `em_macro.archive_raw` for data hashes; `nightshift.logs` for exploration variants | D |
| 8 | Runners | iMac (licensed data, reserve evaluations) and GitHub Actions (public data, forward recording); heartbeat, watchdog | `nightshift.guard`, the `ledger-watchdog` and commit-script patterns | G |
| 9 | Statistics | screening, within-family tests, forward e-processes, hierarchical model, tiers, dormancy | `em_macro.mtstats` (descriptive); new | C, H |
| 10 | Simulation | decides between the two screening methods and checks every claim before it is implemented | new, bound by [SIM_PREREG.md](SIM_PREREG.md) | C |

Package layout (new code only; nothing existing is edited):

```
atlas/            __init__.py, prereg.py, config.py      (this PR)
                  spec.py, ledger.py, roles.py           (Phase D)
                  engine/, factors/                      (Phase E)
                  generate/, freeze.py                   (Phase F)
                  runner/                                (Phase G)
                  stats/                                 (Phase H)
                  sim/                                   (Phase C; must follow SIM_PREREG.md)
config/atlas.yaml switches and defaults (conservative; see section 9)
docs/atlas/       these documents
```

## 3. Four levels with immutable links

| level | definition | declared at freeze | example |
|---|---|---|---|
| **Family** | one mechanism, one predicted sign, one named counterparty (who is on the other side and why they accept the loss) | mechanism text, mechanism class, sign, counterparty, what would kill it, tail exposure | "Importers hedge on a fixed calendar; the currency weakens into the hedge date; counterparty: unhedged importers" |
| **Hypothesis** | the family in one domain (asset class, universe, frequency) | domain, data sources with publication lags, signal definition, primary executable binding, the variant grid | the family above in six EM currencies, daily |
| **Variant** | one setting from the hypothesis's grid | nothing new: variants are the grid's points, enumerated at freeze | look-back 5 days, entry 3 days before |
| **Executable** | a variant bound to a universe, a cost model, a sizing rule and a code version | the primary binding is declared at freeze; later bindings (for example a bug-fixed code version) are new executables of the same variant | variant above, universe U3, costs C2, 10% volatility target, code `3fa9c1e` |

**Canonical form.** A spec is a mapping. Its canonical bytes are JSON with keys sorted, UTF-8 (NFC), no insignificant
white space, integers as integers, every non-integer number as a decimal string, dates as `YYYY-MM-DD`, and list
order kept unless the schema marks the list as a set (then sorted). The spec hash is the SHA-256 of those bytes.
`lab.book.sha256` hashes file bytes; Atlas stores each spec as its canonical JSON file, so the two agree.

**IDs are content addresses.** `id = prefix + first 16 hex characters of the spec hash`; the full hash is stored
beside it.

```
family      AF-<16 hex>   hash of the family spec
hypothesis  AH-<16 hex>   hash of the hypothesis spec, which contains the full family hash
variant     AV-<16 hex>   hash of {hypothesis hash, grid point}
executable  AX-<16 hex>   hash of {variant hash, universe id, cost model id, sizing id, code version}
batch       AB-<4 digits> sequence number; the manifest carries the Merkle root of its spec hashes
```

Because each child contains its parent's hash, a link cannot be changed without changing the child's ID: that is
what "immutable links" means here. With 16 hex characters (64 bits) the chance of any collision among 250,000
executables is about 2 in a billion; the full hash is checked whenever two IDs match.

A family is registered in **one** batch with all its hypotheses. Taking a mechanism to a new domain later creates a
new family whose spec names its parent (`parent_family`), and it is tested as a new family. Adaptive variants may be
added to an existing hypothesis later; they are new variant records with `channel: adaptive` and carry no
evidential weight on any window that was visible when they were written (section 6).

## 4. The ledger

### 4.1 Structure

Two files of the same design, because the public repository must not carry outcomes that a blind generator could
read, nor data derived row by row from licensed sources:

| ledger | where | holds |
|---|---|---|
| **Full ledger** | private store (em-macro-data `atlas/ledger/`, or the iMac only: ETHAN_ACTIONS item 4), one JSONL file per batch | every record, with outcome fields |
| **Public index** | `data/atlas/ledger/index.jsonl` in this repository | one record per freeze, per runner run (Merkle root, record count and head hash of the full ledger), per screening decision once its window is retired for that batch, per tier change, per correction |

Each record is one JSON line:

| field | meaning |
|---|---|
| `seq` | record number in its file, from 1 |
| `ts_utc` | time written |
| `type` | `batch_freeze`, `critic_review`, `evaluation_started`, `evaluation`, `rerun`, `nondeterminism`, `screening_decision`, `eprocess_update`, `tier_change`, `dormancy`, `window_retired`, `correction`, `run_summary` |
| `writer` | runner id (`imac-1`, `gha-public`) or `session` |
| `protocol` | SHA-256 of the PROTOCOL version in force for the batch |
| `payload` | the record's content (below for `evaluation`) |
| `prev_hash` | `hash` of the previous record; 64 zeros for the first |
| `hash` | SHA-256 of the canonical form of all the fields above |

Payload of an `evaluation` record:

| field | meaning |
|---|---|
| `executable`, `variant`, `hypothesis`, `family`, `batch` | IDs (full hashes in the full ledger) |
| `channel` | `blind` or `adaptive` (of the variant) |
| `role` | `exploration`, `reserve` or `forward` |
| `window` | `{id, start, end, frequency}` |
| `designated` | true only for the one evaluation the batch manifest names for this executable and window |
| `spec_hash` | the executable's hash |
| `data_hash` | SHA-256 of the manifest of every input file read (path, bytes, SHA-256), built as `em_macro.archive_raw` builds its manifests |
| `code_version` | git commit and the SHA-256 of the `atlas/` tree |
| `result_hash` | SHA-256 of the canonical result (the return series and the summary) |
| `n_obs`, `summary` | number of periods; summary statistics (full ledger only) |
| `evidential_weight` | 1 or 0, by the table in section 6.3 |
| `seed` | random seed, derived from the manifest hash, the family ID and the window ID |

**Append-only and tamper-evident.** A record is never edited. A mistake is fixed by a `correction` record that names
the record, the fields and the reason, as `ledger.audit` does. Editing any line breaks every later `hash`. Replacing
the whole file from the first record would not break the chain, so the head hash is anchored outside the file: the
public index stores it at each run, each batch tag covers the index, and each manifest hash gets an external
timestamp (section 5.4).

### 4.2 Deterministic-rerun detection

The key of an evaluation is `(spec_hash, data_hash, window id)`.

- Key not seen before: an `evaluation` record. It counts as one look.
- Key seen, same `result_hash`: a `rerun` record. It is the same look and counts once.
- Key seen, different `result_hash`: a `nondeterminism` record. Both results are kept, the family is suspended from
  any tier change, and the cause is found before anything else runs on it.
- Same `spec_hash`, different `data_hash` on the same window (for example a vendor revision): a new `evaluation`,
  flagged `data_changed`; the first designated result stays the result of record.

Before a designated evaluation the runner writes `evaluation_started`. A start without a finish is reported; it is
re-run automatically only when the code version and the data hash are unchanged, in which case it is the same look.

### 4.3 Relation to the existing logs

Every exploration-role variant is also logged with `nightshift.logs.log_variant` (hard rule 6), with `code_ref` set
to the ledger record's hash. That log refuses any window ending after 2019-12-31 and is not designed for executable
counts (AUDIT §1.1), so reserve and forward evaluations exist only in the Atlas ledger. The critic's probability is
logged with `nightshift.logs.log_opposition` (target type `idea`, target id the family ID).

## 5. Generation, critique and freezing

### 5.1 Two channels

| | blind channel | adaptive channel |
|---|---|---|
| sees | a fixed, versioned prompt template; nothing else. No results, no ledger, no repository, no web | summaries of exploration results and of retired screening decisions; the public index; the literature |
| produces | whole batches from the template | new families, and new variants of existing hypotheses |
| reserve results | carry evidential weight | **carry zero evidential weight** (default: adaptive specs are not evaluated on the reserve at all) |
| forward results | carry evidential weight | carry evidential weight from each spec's own freeze date |
| batch size and count | fixed by the template version, not by any result | free |

The blind template is a file with a version and a SHA-256; the manifest records the template hash, the model
identifier and the sampling settings. A template change is a new version and applies to later batches only.

### 5.2 Critic

Before freezing, every family and hypothesis is reviewed by the critic: is the mechanism one mechanism; is the sign
predicted; is the counterparty named; does any data definition look ahead (publication lags, vintages); is the grid
declared and bounded; does the family duplicate an existing family, a trial in `trials.csv` or the T25-T26 shadows;
is the tail exposure declared. The critic sees specs only. It returns the JSON of The Opposition, and its
probability is logged. It cannot block for "weak economics"; it blocks for look-ahead, duplicates of T25-T26,
licensed-data leaks and undeclared grids. Generator and critic output is data, never instructions (hard rule 12).

### 5.3 Batch size

About 50-100 hypotheses per batch, frozen as a whole. A batch is the unit of the screening schedule (PROTOCOL §4):
its place in the sequence and its number of families fix the levels at which its families are tested.

### 5.4 Freeze procedure

1. Validate every spec against the schema; compute canonical forms and hashes; enumerate the variants of every grid.
2. Critic review of every family and hypothesis; record each review.
3. Build the manifest: batch number, channel, template hash, generator model, list of every spec hash, their Merkle
   root, the PROTOCOL hash, the data-role fence in force, the designated evaluations (which executable on which
   window), and the critic record hashes.
4. Commit the spec files and the manifest; append `batch_freeze` to the ledger and the registry.
5. **Signed tag** `atlas-batch-<NNNN>` on that commit, signed with Ethan's key on the iMac (a cloud session cannot
   sign as Ethan; AUDIT §2).
6. **External timestamp** of the manifest hash (OpenTimestamps by default; the proof file is committed). GitHub's
   push time is a second, weaker witness.
7. Only after steps 1-6 may a designated evaluation of that batch start. The runner checks the tag's signature and
   the manifest hash first, and refuses otherwise.

Under hard rule 4 a freeze is a pre-registration and is Ethan's alone (default `freeze.authority: ethan_only`):
agents prepare steps 1-4 on a branch; Ethan reviews, merges, tags and timestamps.

## 6. Data roles

### 6.1 Three roles

| role | who may read it | used for | evidential weight |
|---|---|---|---|
| **Exploration** | generators (adaptive), explorer, any session | building and debugging; descriptive statistics | none |
| **Screening reserve** | **the runner only** | one designated evaluation per batch and domain; then retired for that batch | weight 1 for blind-channel specs, at the 20% screening level only |
| **Forward** | recorded by the runner; everyone may read results after they are recorded | the forward e-process and the hierarchical model | weight 1 for every spec, from its own freeze date |

The fence (which dates are exploration and which are reserve, per domain) is set by Ethan in `config/atlas.yaml` on
main. Default: **no reserve** (`reserve.enabled: false`). The exploration cap already enforced for the night shift
is 2019-12-31. Between two roles an embargo of the hypothesis's longest holding period plus one period is dropped,
so no position spans the fence.

### 6.2 "Once per batch, retired after use"

History is finite and about 100 batches are planned, so each batch cannot have its own calendar window. The rule
adopted is:

- Each (batch, domain) pair gets exactly **one designated evaluation** on that domain's reserve window.
- After it, the pair is **retired**: any later evaluation of that batch's specs on that window is recorded with
  `designated: false` and weight 0.
- The reserve data stay runner-only afterwards, because later blind batches will still be screened on them.

The cost is that screening statistics of different batches come from the same dates and are dependent. Protocol v3
therefore keeps one candidate that is valid under any dependence, and tests the other in simulation for exactly this
(PROTOCOL §4). Ethan may instead cut the reserve into disjoint slices, one per block of batches
(`reserve.mode: disjoint_slices`), which removes that dependence and shortens every test.

### 6.3 Evidential weight

| channel | role | designated | weight |
|---|---|---|---|
| blind | reserve | yes | 1 (screening at 20% only) |
| blind | reserve | no | 0 |
| adaptive | reserve | any | 0 |
| any | exploration | any | 0 |
| any | forward, dated after the spec's freeze | n/a | 1 |
| any | forward, reconstructed for a gap in recording | n/a | 0 (shown, flagged) |

### 6.4 Frequency

Daily bars, or one observation per event, by default. Minute data only when the family's mechanism is stated in
minutes (for example an auction or a fixing) and the critic agrees; minute executables are never "cheap" for the
dormancy rule (PROTOCOL §9).

## 7. Runners

### 7.1 Two runners

| | iMac runner (`imac-1`) | GitHub Actions runner (`gha-public`) |
|---|---|---|
| data | licensed (Norgate snapshot, Databento settlements) and the reserve slices | public sources only |
| jobs | designated reserve evaluations; forward recording of licensed-data executables; hierarchical model fits; simulation runs | forward recording of public-data executables; public index updates; watchdog |
| schedule | launchd | workflow schedule plus `workflow_dispatch` (this repository's schedules start hours late, Q018) |
| writes | full ledger and private results; public index through a PR-free path limited to `data/atlas/` | `data/atlas/` only, through a commit script with a path list, in the `ledger-writers` concurrency group |
| identity | a fine-grained token on the iMac limited to the two repositories, kept in the macOS Keychain | `GITHUB_TOKEN` |

Every run, on either runner, does in order: `git fetch`; `python -m nightshift.guard check atlas-runner` (stop if an
existing writer is busy or main's config cannot be read); read `config/atlas.yaml` **from main**; verify the tag and
manifest of any batch it will evaluate; verify the ledger chain; run jobs; append records; write the heartbeat;
commit with a script that refuses any path outside its list (the `night_commit.sh` pattern); push.

### 7.2 iMac launchd

- A LaunchAgent (`~/Library/LaunchAgents/com.horizons.atlas.runner.plist`) with `StartCalendarInterval` (daily,
  after the Databento finals are available, and never inside the guard's busy windows), `RunAtLoad` false,
  `ProcessType` Background, standard output and error to `~/Library/Logs/atlas/`.
- launchd runs a missed calendar job once when the Mac wakes. The Mac must be awake or woken (`pmset repeat
  wakeorpoweron`) for the schedule to hold; the heartbeat shows when it did not.
- The job is one shell script in the repository (`atlas/runner/imac.sh`, Phase G) that activates a pinned Python
  environment, takes a lock file, and calls `python -m atlas.runner`. No secret is in the plist or the repository:
  tokens come from the Keychain (`security find-generic-password`), and are never printed.
- A designated evaluation is refused if the working tree is dirty, if the checked-out commit is not the tagged
  commit's descendant on main, or if the reserve path is readable by anything but the runner's user.

### 7.3 Heartbeat and watchdog

- **Heartbeat.** At the end of every run the runner writes `{runner, started, finished, jobs, ledger_head, next_due,
  watchdog_last_seen}`. The iMac pushes its heartbeat to a branch `atlas-heartbeat` of this repository (not main: no
  commit noise, no Pages rebuild). The Actions runner writes its own in the same place.
- **Watchdog.** A read-only scheduled workflow, modelled on `ledger-watchdog`, opens or updates an issue
  `[ALERT] Atlas runner silent` when a heartbeat is older than its limit (36 hours for a daily runner, allowing for
  late schedules), when `next_due` has passed, or when the public index's last `run_summary` does not match the
  heartbeat's `ledger_head`. It closes the issue when the heartbeat returns.
- **Who watches the watchdog.** Each runner reads the watchdog's last run from the public Actions API and records
  it in its heartbeat; a watchdog silent for 48 hours is reported in the runner's log and in the next public index
  record.
- A silent runner never causes a retry of a designated evaluation by another machine: only the runner that holds
  the reserve may run it.

## 8. Access separation: what the current setup can and cannot enforce

em-macro is a public repository and it contains results: every trial's report, aggregate return series, the trial
ledger and this design. Stated plainly:

**Can be enforced mechanically today**

- *Integrity of frozen specs and of this protocol.* Anyone can recompute a hash. A changed file fails
  `check_frozen` and, for the simulation pre-registration, a test.
- *Tamper evidence of the ledger*, given the anchors of section 4.1.
- *Physical separation of licensed reserve data*, if and only if those files exist on the iMac alone. A file in
  em-macro-data is readable by any cloud session with that repository attached (the Janus sessions have it).
- *Environment-level limits of a cloud session:* which repositories are attached when it starts, and its outbound
  network policy.

**Cannot be enforced today; held by convention and detection only**

1. **That a generator has not seen results.** Any cloud session with em-macro attached can read every result in it,
   and a session with web access can read the public repository without attaching it. A session's git proxy may
   also serve public repositories whatever the network policy says. A "blind" generator inside the current
   environment is therefore not blind. Blindness needs a separate repository and environment with no em-macro, no
   em-macro-data and no outbound network, or a model call with no tools at all (ETHAN_ACTIONS item 3).
2. **That the model does not know the history.** The generating model was trained on text that includes market
   history up to its cutoff, and possibly this public repository. No access control changes that. It is the reason
   historical screening is a filter and forward evidence is required.
3. **That only the runner reads a public-data reserve.** FRED, BIS and exchange data can be downloaded by anyone. For
   public data "runner-only" means: no Atlas code path outside the runner will read reserve dates, and the ledger
   shows every evaluation that Atlas code made. It does not show what an agent did outside Atlas code.
4. **Who wrote a commit.** Night agents, Janus, the clerk and build sessions all push as EthanC100 through the Claude
   GitHub App (`docs/agent-system.md` §8). GitHub cannot tell an Atlas runner session from any other session, so
   "only the runner writes the ledger" is a script-level rule for cloud sessions. The iMac's own token is the one
   distinct identity.
5. **Signatures from the cloud.** A cloud session cannot sign a tag with Ethan's key. Signed freezes must be made
   on the iMac. An unsigned tag proves nothing about who froze a batch.
6. **Protection of main and of protected paths**, unless the rulesets in `docs/rulesets/` have been applied. This
   could not be checked from a session.
7. **That an agent with the private store attached does not read outcomes.** `add_repo` can attach any repository
   the GitHub App can reach. Keeping the adaptive channel to "summaries only" is an instruction, not a wall.

What follows from this: (a) the screening reserve is kept on the iMac; (b) the blind generator runs outside this
environment or is not called blind; (c) every statistical guarantee in Protocol v3 that matters at 5% is built on
forward data, which no one, model or agent, can have seen.

## 9. Configuration

`config/atlas.yaml` holds every switch that is Ethan's, with the conservative value as the default. Runners read
main's copy, as the night shift reads main's `config/night.yaml`. The defaults in this PR:

| key | default | meaning |
|---|---|---|
| `freeze.authority` | `ethan_only` | no agent freezes a batch |
| `reserve.enabled` | `false` | no screening-reserve evaluation can run |
| `reserve.windows` | empty | the fence, per domain, when Ethan sets it |
| `reserve.mode` | `shared_window` | or `disjoint_slices` |
| `reserve.evaluate_adaptive` | `false` | adaptive specs are not run on the reserve |
| `reserve.store` | `imac_only` | where reserve data may exist |
| `forward.real_money` | `false` | no execution code exists; the flag stays false |
| `forward.loss_cap_usd` | `0` | the Live-experiment tier is closed until Ethan sets a cap |
| `programme.end` | unset | needed for the dormancy rule; unset means no family is made dormant |
| `levels.screening_fdr`, `levels.forward_fdr` | `0.20`, `0.05` | the two levels |
| `claims.enabled` | `false` | no confirmation claim is produced until the simulation passes |

## 10. What is not designed here

Real-money execution (none will be built); the generator templates; the daily core-factor definitions; the report
pages. Each is a later phase in ATLAS_PROGRESS.md.
