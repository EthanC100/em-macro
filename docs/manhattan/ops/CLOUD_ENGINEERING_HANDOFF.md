# Cloud engineering handoff — 2026-11-16

Source: `EthanC100/em-macro`, fetched `main` at
`8769803c92ef351bdf22d7503efbfb82f3f58181`. Work branch:
`codex/manhattan-ops-hardening`. This is a Codex Cloud Linux x86_64 session,
not either Mac. No Tailscale connection or Mac access was attempted.

## Verified state

GitHub's connected repository API confirms read permission; HTTPS fetch and
`git ls-remote origin HEAD` confirm working Git access. Default branch is `main`.
All remote branches were fetched; no open PRs were returned by the GitHub API.
Relevant branches include `build/manhattan`, `build/manhattan-ops`, `dev`, and
the historical `night/Q019-explorer-data-loader`. No `codex/local-ops` or
`codex/genesis-b1-feasibility` branch was advertised. Neither `98b21a2` nor
`94707e3` resolves in the fetched object database. This does not establish that
the local work never existed; it is unavailable here.

The reported local readiness/checklist files, Genesis feasibility audit and
`infra/local_ai/` are absent, including a path search of fetched history. No
SQLite local coordinator was found. The Mac hardware, accounts, heartbeat,
firewall, SSH configuration and worker activation remain **unverified**.

Read the complete root `CLAUDE.md`, `.github/CODEOWNERS` protected block and
`nightshift/protected.py` before editing. The project documents live under
`docs/manhattan/`, including `MANHATTAN_PROGRESS.md` and `ETHAN_ACTIONS.md`.
`ARCHITECTURE.md` is the original design, with later build notes. For ops,
`ops/DESIGN.md`, `ops/LEDGER.md`, `ops/RUNNER.md` and `OPS_PROGRESS.md` describe
the implemented private-ledger design and explicit adapters/remaining conflicts.
In particular, ops does **not** publish the older architecture's outcome index.
Historical progress prose can lag the actual protected-path list; both protocol
versions and both simulation pre-registration versions are protected now.

Implemented in GitHub: spec registry, role fences, engine, simulation/statistical
modules, private hash-chain store with journal reconciliation, locks, retry and
mirror support, compiler, registration timing, blinding, synthetic end-to-end
tests, and a dispatch-only public-data ops runner. These are source/test facts,
not evidence that a genuine research cycle has operated successfully.

There are 15 workflow files. CI `tests.yml` runs on PRs to main with a read-only
token and private data redirected to nonexistent paths. The ops runner is main-only,
uses a named environment for secrets, a separate concurrency group and no artifact
upload. Its schedule is commented out. The source promotion gate has an empty
`ADOPTED_PROTOCOLS`; claims, reserve access and real money remain disabled.
Existing writer workflows, research protocols, evidence and switches are unchanged.

Read-only API inspection of the latest 100 repository Actions runs found the
`tests` run `43645607133` successful on `dev` (2026-11-14), and simulation runs
`43467828524` failed and `43467884866` cancelled on main (2026-11-13). No ops
runner run appeared in that page. This bounded observation does not prove there
has never been an ops run. No workflow was dispatched or rerun here.

## Implementation and hardening status

| Requirement | Delivered | Remaining limit |
|---|---|---|
| A1 dependency/workflow integrity | Candidate runner-only wheel hash lock; two Action SHAs resolved from official tag refs; owner patch with unchanged triggers, permissions and main/environment gates; patch application/YAML regression test | Existing runner workflow deliberately not edited (ops owner-protection instructions); other workflows and their dependency files remain unpinned. Candidate versions are the fresh environment's resolution, not a recovered production lock. Review before adoption |
| A2 private failure logs | Nightly and registration handled-failure logs are saved privately; registration failures release their lock; logs use mode 0600; mirror verification checks the complete committed tree; persistence/startup errors produce sanitized failed health | Clone/open failure, primary-store outage and hard process kill still need an independent authorized private sink. No such sink is assumed or provisioned |
| A3 missed-run watchdog | Offline deterministic weekday 23:41 UTC slot checking, default disabled, 12-hour delay allowance, 75-minute runtime limit, missed/failed/pending counts, checks gaps even after a later success | No external invocation, schedule or alert delivery activated. Owner must establish monitoring start and independent caller before relying on it |
| A4 workflow changes | Exact workflow-byte hash comparison against trusted baseline; additions/removals detected; ordinary code changes ignored; fixed public output | Does not authenticate GitHub reviews. Baseline must come from an independently trusted owner-reviewed revision; the supplied candidate is not evidence of approval |

The new `artifacts` tool verifies file size and SHA-256 against an explicitly
supplied trusted manifest, reads in bounded chunks, rejects traversal, symlinks,
duplicates and special files, and emits counts only. It can verify synthetic
simulation artifacts or an authorized backup without interpreting contents.
It does not establish scientific validity, complete directory coverage, backup
independence or retention durability. No private ledger or real backup was opened.
Existing `store.verify_pair` already checks ledger/mirror chains; it was exercised
through synthetic repositories rather than a newly attached private store.

## Safe usage (manual, offline)

Run commands from the repository root with the intended virtual environment on
`PATH`. Exit 0 means a valid non-alert result, 1 an operational alert/integrity
mismatch, and 2 invalid input. Readiness validation exits 0 for a valid inventory,
even if every dataset remains unverified; it never authorizes research.

```bash
python -m manhattan.ops.readiness docs/manhattan/ops/genesis_data_readiness.json
python -m manhattan.ops.monitor integrity --root . --approved /trusted/workflow-digests.json
python -m manhattan.ops.monitor watchdog --runs /trusted/runs.json --now 2026-11-17T12:00:00Z
python -m manhattan.ops.artifacts --root /authorized/synthetic-backup --manifest /trusted/manifest.json
```

The watchdog above is disabled. Only an owner-approved activation would add
`--enabled --activated <UTC timestamp>`. Input is a JSON array of Actions run
objects with `path`, `head_branch`, `event`, `created_at`, `updated_at`, `status`,
`conclusion`. Collect **all** pages covering the monitoring interval; API failure
or incomplete pagination is an input-collection failure, not proof of a missed
run. Maximum 1,000 rows, 2 MB, 31 days; explicit timestamps include a zone.
The 31-day bound deliberately refuses an obsolete monitoring interval: archive
prior verdicts before moving the caller's monitoring window forward. No market
holiday assumption is made: this models the disabled workflow's weekday cron.
Run reruns are matched by original creation time; an old rerun cannot satisfy a
new slot. Exit 1 calls for inspecting Actions scheduling, queued/stalled jobs or
failed runs; never automatically retry a research evaluation.
This checks Actions execution metadata, not private capture freshness or the
`asof` used by a manual run. A successful Actions run alone is not proof of a
complete or scientifically eligible observation. An eventual private health
collector must check those separately without publishing outcomes.

`workflow_baseline_candidate.json` records the fetched tree for review. Do not
trust a baseline merely because it is committed beside code being checked.
Store an approved copy outside the writable repository or obtain it from a
verified owner-reviewed revision. An expected reviewed workflow edit requires
an explicit baseline update. A mismatch means **review required**, not malicious.

The artifact manifest shape is
`{"schema_version":1,"files":[{"path":"synthetic.bin","bytes":17,"sha256":"<64 hex>"}]}`.
Limit 10,000 entries and 1 GB total declared data. Extra files are not read or
certified. Use a stable trusted filesystem: this verifier is not a sandbox
against an attacker concurrently swapping filesystem components. Do not publish
private manifests or file paths; public command output contains fixed words/counts.
Metadata readers bound the actual descriptor read, reject final symlinks and
non-regular files without blocking on FIFOs, and reject duplicate JSON keys,
non-finite numbers and excessive nesting. Workflow inventory additionally caps
directory entries at 1,000 and total bytes at 8 MB. These are POSIX tools and fail
closed where no-follow/nonblocking opens are unavailable; Windows is unsupported.

## Owner workflow patch

The ops action list requests owner protection for the runner workflow; treat it
as owner-controlled even though those extra CODEOWNERS lines are not yet present.
The live workflow is unchanged. Review
`patches/runner-integrity.patch` and `requirements-manhattan-runner.lock` together.
After approval, `git apply --check` then `git apply` applies only Action SHA and
installation/cache changes. It does not activate a schedule or dispatch.
Official tag refs observed 2026-11-16:

* checkout v4: `11d5960a326750d5838078e36cf38b85af677262`
* setup-python v5: `a26af69be951a213d495a4c3e4e4022e16d87065`

The candidate lock supports CPython 3.12 on Linux x86_64, glibc >= 2.28. Only
runner imports and the FRED HTTP client require numpy/requests and the four HTTP
transitives. It is not a full-suite, simulation, macOS or ARM lock. No original
requirements or workflow was upgraded. Reproduction was tested with a second
fresh venv and local wheel directory, `--no-index --require-hashes
--only-binary=:all:`; `pip check` and runner `--help` succeeded. Review current
security advisories and provenance before adoption; hashes establish exact
bytes, not dependency safety. A nonmatching wheel/platform fails closed.

## Genesis readiness and exact missing documents

`genesis_data_readiness.json` contains ten families and twenty **provisional**
dataset categories derived solely from the handoff. Every category is unverified:
no advertised source, repository module or historic data-access claim is proof of
a usable licensed, vintage-aware extract. The validator requires complete
evidence metadata before accepting `verified_available` and always reports
`research_execution_authorized: false`. It checks metadata consistency, not the
truth of an attestation or a provider licence. Do not put raw data, private
performance, credentials or sensitive evidence contents into this public JSON.

| Family | Provisional data categories | Missing Claude specification/decision |
|---|---|---|
| F01 | CFTC first releases; futures contract data | post-volatility-scaling neutrality; real-time CFTC availability |
| F02 | index roll calendars/pairs; contract data | index-specific contract-pair mapping and versioning |
| F03 | auction releases/results; deliverable baskets | basket mapping and auction-overlap handling |
| F04 | FX conventions/prices; exposure proxy vintages | quote convention, approved proxy and limitations |
| F05 | duration-supply vintages; bond references | retained universe after dropped cross-country variant |
| F06 | terms-of-trade vintages; real FX inputs | change-signal/model consistency and theoretical model selection |
| F07 | option quotes/events; underlying references | covariance sign and straddle-P&L definition |
| F08 | fiscal vintages; EM/US rate references | treatment of common EM and US-rate confounding |
| F09 | contract units/multipliers; production inputs | unit mathematics and crush-spread ratios |
| F10 | announcement timestamps; bond references | explicit covariance assumption for premium direction |

Required deliveries, without reconstructing any missing equations:

1. Original complete Genesis Batch 1 F01–F10 specifications, with version/hash
   and Claude authorship, not only the handoff summaries.
2. Complete Claude v0.2 corrections and which original sections each supersedes.
3. Approved exact data dictionary per retained family: series/universe, units,
   quote directions, contract mapping, release clock/time zone, historical
   vintages, publication delay, missing-data policy and licence constraints.
4. Claude's finalized executable/timing/falsification/benchmark/cost/sizing
   definitions and resolution of the family-specific questions above. Engineering
   must not choose these by observing outcomes.
5. The reported `GENESIS_B1_DATA_FEASIBILITY_AUDIT.md` at `94707e3`, plus
   its evidence references, if it should inform further implementation.
6. The unpushed `codex/local-ops` readiness/checklist and any coordinator code,
   if local operations are to be reconciled. These are engineering handoffs,
   not prerequisites to the new offline tools.

No backtest, performance screen, hypothesis, algorithm, freeze or statistical
protocol change was created. The one-million executable objective is an engineering
target; no measurement at that scale was made and no evidence independence is claimed.

## Autonomy and owner-only actions

These components can run as finite deterministic commands under a later caller.
No background process, schedule, service, port or paid API was activated. Cloud
does not establish unattended operation of either Mac. The existing ops runner
still needs its private-store credentials/environment and actual owner activation;
none of the additional proposed repositories was inspected or assumed to exist.
Licensed data, Mac telemetry, launchd, backup retrieval, worker roles/authentication
and remote access require a separately authorized local handoff. The old privileged
MacBook bootstrap was not run. Security settings and local architectural claims
cannot be reconciled further without that handoff.

Owner priorities:

1. Deliver the missing Claude specifications/corrections; upload/push the missing
   local engineering branches if they are to be reused. No keys or tokens needed.
2. Review the branch and candidate workflow patch/lock; approve a trusted workflow
   baseline separately. Keep research schedules off.
3. Before activation, verify the private repository/access separation, independent
   private failure-log sink, mirror/backup and main-only environment following
   `ETHAN_OPS_ACTIONS.md`. Verify actual ruleset enforcement in GitHub settings.
4. On a Mac, verify local coordinator/heartbeat state, hardware and the outstanding
   non-Tailscale LAN-denial test; settle worker/admin roles before installing anything.

## Next session prompt

Continue `codex/manhattan-ops-hardening` from this handoff and the accompanying
`CLOUD_VALIDATION.md`. Reverify GitHub/HEAD, read all of CLAUDE.md and current
CODEOWNERS. Preserve owner-controlled files, blind/private data boundaries and
disabled schedules. Inspect the actual test outcomes before any push. Review the
offline monitor, artifact verifier, Genesis metadata validator and private-log
fix; do not interpret valid inventory as research readiness. Do not apply the
workflow patch or trust the candidate baseline as owner approval. Resolve any
recorded test/environment issues without weakening Q019. If Claude's finalized
Genesis specs arrive, audit engineering feasibility against those exact documents;
otherwise continue independent deterministic operations work. Do not dispatch,
freeze, merge, trade or change remote access.

## Independent review and follow-up on PR #72

Reviewed all 16 original changed files at `0d53828`, including implementation,
tests, dependency lock, candidate patch/baseline and inventory/documentation.
Confirmed that GitHub CI run `43887821034` passed for that head. Fetched main
advanced to `ab7f29d`; its intervening changes were writer-owned data, which were
not incorporated or edited. Work remains on the existing PR branch.

The review reproduced a false-success mirror case: matching chains do not prove
that a log-only commit was mirrored. Missing/changed committed files now produce
`files_differ`; a rejected final mirror push cannot produce `mirror_ok: true`.
The final verification also replaces any earlier mirror-head health value.

Other corrections: bound real metadata reads instead of relying on pre-read
stat size; reject ambiguous/malformed JSON and noninteger schema versions;
preserve registration attempt logs and release registration failure locks;
make Git calls noninteractive with a 120-second per-call deadline (configurable
up to 600 seconds); protect log file permissions independently of umask; sanitize
exceptions outside the private fd redirect and malformed issue-body input.
Witness JSON now requires an actual Boolean: the string `"false"` previously
became true. This is input validation, not external witness authentication;
the provenance/verification of an owner's witness file remains a separate trust
requirement. No timing, evidence-weight, freeze or economic rule was changed.

Review found no private evidence in the original delivery. Regression tests use
synthetic canaries, local bare Git stand-ins and local metadata only. Actual
production storage, external monitoring/alerts and both Macs remain unverified.
Owner approvals listed above still apply; no workflow patch was applied and no
research control was activated. Latest test outcomes are in `CLOUD_VALIDATION.md`.
