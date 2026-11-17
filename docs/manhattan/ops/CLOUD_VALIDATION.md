# Cloud validation — 2026-11-16

## Phase 3 PIT validation — 2026-11-17

Branch: `codex/manhattan-pit-integrity`. Base main:
`e7f6272b2acd5ffdcc01e37a7a27cb221f9077ca` (owner's merged PR #74).
Fresh environment: **CPython 3.12.14, Linux 6.18.57 x86_64**. No dependency,
workflow, lock or platform support change. Older phase results below are retained
as history, not substituted for these fresh runs. The audit and real-data
limitations are in [PIT_INTEGRITY_AUDIT.md](PIT_INTEGRITY_AUDIT.md).

### Regression evidence and focused suites

The initial data-only regression run against unchanged source returned **27
failed, 11 passed** (exit 1). It reproduced ambiguous same-vintage values,
missing/intraday cutoff acceptance, mutation through returned arrays, coerced
lags, naive capture times and missing replay metadata validation. Existing hash
checks and ordinary revision handling passed. Subsequent boundary/compatibility
cases caught current-day after-close backdating and identical legacy recapture
conflicts. These are corrected without changing accounting or source definitions.

Final broad focused run:

```bash
PATH=/tmp/manhattan-venv/bin:$PATH \
MANHATTAN_RUNNER_WHEELHOUSE=/tmp/manhattan-runner-wheels \
PYTHONDONTWRITEBYTECODE=1 \
python -m pytest -q -p no:cacheprovider \
  tests/test_manhattan_pit_integrity.py tests/test_manhattan_engine.py \
  tests/test_manhattan_factors.py tests/test_manhattan_ops_*.py \
  --junitxml=/tmp/manhattan-pit-final-targeted.xml \
  > /tmp/manhattan-pit-final-targeted.log 2>&1
```

**Exit 0; 324 passed, 0 failed/skipped/errors; 112.43 seconds; 1 warning.**
This includes 54 PIT regressions and all 232 existing ops tests, including the
clean, hash-locked runner installation and synthetic probe. The existing engine
and factor tests remain intact. No private snapshots or new strategies were used.

Two additional fabricated FRED-format tests (nonfinite/conflicting quotes and
missing-marker preservation) were added after broad/full-suite collection,
without changing implementation. The final PIT file was then run in full:

```bash
PATH=/tmp/manhattan-venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 \
python -m pytest -q -p no:cacheprovider tests/test_manhattan_pit_integrity.py \
  --junitxml=/tmp/manhattan-pit-final-unit.xml \
  > /tmp/manhattan-pit-final-unit.log 2>&1
```

**Exit 0; 56 passed, 0 failed/skipped/errors; 1.83 seconds; 1 warning.**
The warning is NumPy's generic-NaT unit-comparison deprecation in a negative-test
fixture. It is not a failure or a skipped integrity case. These overlapping totals
must not be added as though they were distinct tests.

### Complete suite and unchanged security controls

```bash
PATH=/tmp/manhattan-venv/bin:$PATH \
MANHATTAN_RUNNER_WHEELHOUSE=/tmp/manhattan-runner-wheels \
EM_MACRO_DATA=/nonexistent/em-macro-data \
DATA_REPO_URL=/nonexistent/em-macro-data.git \
PYTHONDONTWRITEBYTECODE=1 \
python -m pytest -q -p no:cacheprovider \
  --junitxml=/tmp/manhattan-pit-final-full.xml \
  > /tmp/manhattan-pit-final-full.log 2>&1
```

**Exit 0; 1,751 passed, 132 skipped, 0 failed, 0 errors; 720.84 seconds;
11 warnings.** All **86 unchanged Q019 security tests passed**, with no skips.
Skip categories: 125 unavailable private Norgate snapshots, 3 unavailable optional
numpyro imports, 1 unavailable optional reportlab import, and 3 explicit opt-ins
(slow model compilation, full sweep, full real-data reproduction). None was
silently treated as passing. Warnings comprise the one negative-NaT fixture
warning and existing synthetic numerical warnings; no security guarantee was
weakened or platform failure reclassified.

The earlier full attempt was deliberately interrupted to include the final
legacy-recapture correction (exit 2); it is not counted as a successful run.
No implementation changed after the final full run started. Its collection
includes 54 PIT regressions; the two later parser-only cases passed in the final
56-case file above. No full-reproduction/research opt-in was enabled, no actual
source fetched, and all new cases use bounded fabricated data/local stores.

Additional checks: `python -m pip check` and
`git apply --check docs/manhattan/ops/patches/runner-integrity.patch` both exit 0.
The owner patch remains **unapplied**. Protected-path checking against branch and
main CODEOWNERS plus `nightshift.protected.ALWAYS` found zero protected delivery
paths; live workflows/configuration/protocol/data/results paths are unchanged.
`git diff --check` passes. The dependency lock, candidate baseline, owner switches,
research protocols and existing security tests are unchanged. No private evidence,
licensed data, Mac, dispatch, schedule, deployment, freeze or merge was accessed
or initiated.

GitHub CI is checked read-only after opening the new draft PR; its exact head,
run URL and completed result belong in the PR status/final handoff. Local success
above is not evidence of GitHub completion. No manual dispatch or rerun is used.

## Phase 2 validation — 2026-11-17

Base: `9698b131413f798f9b752321c86b2ee44341aed9` (owner's merge of PR #72,
verified through GitHub and fetched main). Branch: `codex/manhattan-phase2-hardening`.
This phase uses a new PR; the merged PR was not edited. Python is CPython 3.12.14
on Linux x86_64. The older results below remain historical records, not substitutes
for the fresh phase-2 checks.

### Candidate dependency lock: isolated installation and synthetic probe

Executed in a newly created venv, without installing the broader requirements or
pytest into that venv:

```bash
python -m venv /tmp/manhattan-phase2-locked
/tmp/manhattan-phase2-locked/bin/python -m pip install \
  --require-hashes --only-binary=:all: -r requirements-manhattan-runner.lock
/tmp/manhattan-phase2-locked/bin/python -m pip check
/tmp/manhattan-phase2-locked/bin/python -c 'import manhattan.ops.runner'
/tmp/manhattan-phase2-locked/bin/python -I tests/runner_locked_probe.py
```

Each command exited **0**. The probe ran **1 standalone unittest**, without
pytest, scipy, pandas or PyYAML installed. Installed distributions were exactly
the six locked packages (certifi 2026.10.23, charset-normalizer 3.5.2, idna 3.20,
numpy 2.5.5, requests 2.34.2, urllib3 2.8.0) plus bootstrap pip 25.0.1 supplied
by venv. No dependency or lock version changed. This verifies candidate dependency
closure, not owner adoption or vulnerability-free package provenance.

The probe exercises runner import and a **synthetic local dry run** of nightly
capture, rerun idempotency, chain verification and complete mirror verification.
All stores are temporary local bare Git repositories; HTTP/socket calls are
refused during the run. There is no approved batch, registration, actual source
fetch or strategy/performance evaluation. No production dry-run dispatch or new
production CLI mode is implied.

`tests/test_manhattan_ops_lock_install.py` is the CI-compatible regression. It
creates another fresh venv, installs only the lock with hash/binary enforcement,
and invokes the standalone probe with Python `-I`. Normal CI uses its package
index; a restricted/offline caller can supply an exact wheelhouse (pip still
checks every hash). It explicitly skips unsupported Python/platform targets.
Fresh local execution:

```bash
PATH=/tmp/manhattan-venv/bin:$PATH \
MANHATTAN_RUNNER_WHEELHOUSE=/tmp/manhattan-runner-wheels \
PYTHONDONTWRITEBYTECODE=1 \
python -m pytest -q -p no:cacheprovider tests/test_manhattan_ops_lock_install.py
```

**Exit 0; 1 passed, 0 skipped/failed, 10.92 seconds.** The offline wheelhouse was
already present from the earlier phase; its bytes were rechecked against the lock
on every clean installation. The independent manual installation above fetched
the locked wheels afresh. No workflow was modified to run this regression.

The same regression was also executed with `MANHATTAN_RUNNER_WHEELHOUSE` unset,
using the normal package index (network permission for this test only):
`PATH=/tmp/manhattan-venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 python -m pytest -q
-p no:cacheprovider tests/test_manhattan_ops_lock_install.py`.
**Exit 0; 1 passed, 8.44 seconds.** This verifies the unmodified CI-compatible
index-install path as well as the offline path.

### Concurrent finalization regressions

Real separate local Git clones inject another writer after unlock but before
`put_files` in nightly and registration. The first regression run reproduced
colliding-log overwrite in both paths (**2 failed, 2 passed**, expected before
the fix). Additional configured-mirror failure checks reproduced stale/missing
final mirror-certification flags (**2 failed, 2 passed** before correction).

Final cases verify byte-identical preservation of all original/peer records,
valid chain and released locks, no overwritten peer logs, monotonic heartbeat
cache, all diagnostics in the final mirror on success, and sanitized failed
health with `mirror_ok: false` on persistence failure. Local diagnostics remain
available on that failure; no durable persistence is claimed when storage fails.
The synthetic log-name reuse test also verifies idempotent collision retention.

```bash
PATH=/tmp/manhattan-venv/bin:$PATH \
MANHATTAN_RUNNER_WHEELHOUSE=/tmp/manhattan-runner-wheels \
EM_MACRO_DATA=/nonexistent/em-macro-data \
DATA_REPO_URL=/nonexistent/em-macro-data.git \
PYTHONDONTWRITEBYTECODE=1 \
python -m pytest -q -p no:cacheprovider tests/test_manhattan_ops_*.py \
  --junitxml=/tmp/manhattan-phase2-ops.xml > /tmp/manhattan-phase2-ops.log 2>&1
```

**Exit 0; 232 passed, 0 skipped/failed/errors; 84.14 seconds.** Includes the clean
lock install and peer-writer success/failure tests. Raw local logs/XML are not
committed to the public repository.

### Complete suite and security checks

```bash
PATH=/tmp/manhattan-venv/bin:$PATH \
MANHATTAN_RUNNER_WHEELHOUSE=/tmp/manhattan-runner-wheels \
EM_MACRO_DATA=/nonexistent/em-macro-data \
DATA_REPO_URL=/nonexistent/em-macro-data.git \
PYTHONDONTWRITEBYTECODE=1 \
python -m pytest -q -p no:cacheprovider \
  --junitxml=/tmp/manhattan-phase2-full.xml > /tmp/manhattan-phase2-full.log 2>&1
```

**Exit 0; 1,685 passed, 132 skipped, 0 failed/errors; 694.56 seconds; 10 warnings.**
The full suite includes the 232 ops tests and all 86 unchanged Q019 security
tests (86 passed, no skips). These counts are not additional to the full total.
The skips are 125 unavailable private Norgate snapshots, 3 optional numpyro tests,
1 optional reportlab test, and 3 explicit opt-in checks (slow models, Q009 full
sweep, frozen-v1 full reproduction). Skips do not establish private integration
or research readiness. No unresolved failure remains.

The repository's protected-path check was applied to every changed/untracked
delivery file using both branch and fetched main CODEOWNERS: **zero protected
paths changed**. Additional path checks and diff checks confirm no workflow,
activation switch, research protocol, data/result file, candidate baseline,
candidate workflow patch or dependency lock changed. `git diff --check` passed.
No baseline was adopted/moved/generated, no private evidence or licensed data was
accessed, and no live workflow, service or production schedule was activated.
Task 3's baseline commands remain future owner instructions only.

The phase is ready for independent engineering review, not operational activation.
Shared-clone concurrency, actual private-store outages/hard kills, Mac behavior,
and authenticating/adopting an independent baseline remain deployment limitations
or owner decisions. The original Genesis specifications remain missing; the
handoff explicitly assigns ordinary-session proposals to the adaptive channel.

Branch: `codex/manhattan-ops-hardening`, based on main
`8769803c92ef351bdf22d7503efbfb82f3f58181`. Implementation and limitations:
[CLOUD_ENGINEERING_HANDOFF.md](CLOUD_ENGINEERING_HANDOFF.md).

Environment: **CPython 3.12.14, Linux 6.18.57 x86_64**, Codex Cloud.
Fresh virtual environment `/tmp/manhattan-venv`, installed with
`python -m pip install -r requirements.txt -r requirements-elections.txt`.
Resolved versions are recorded in [cloud-test-environment.txt](cloud-test-environment.txt).
No optional numpyro/JAX sampler or private data was installed or attached.
The recorded package list is a diagnostic snapshot, not an adopted production lock.

## Test results

All commands ran from `/workspace/em-macro`, without output pipelines, with
the runner's actual exit code observed. Output was redirected to local files
under `/tmp`; raw test logs and XML were not added to this public repository.

```bash
PATH=/tmp/manhattan-venv/bin:$PATH \
EM_MACRO_DATA=/nonexistent/em-macro-data \
DATA_REPO_URL=/nonexistent/em-macro-data.git \
PYTHONDONTWRITEBYTECODE=1 \
python -m pytest -q -p no:cacheprovider --junitxml=/tmp/manhattan-full.xml \
  > /tmp/manhattan-full.log 2>&1
```

**Exit 0; 1,584 passed, 132 skipped, 0 failed, 0 errors; 712.10 seconds;
10 warnings.** Collection started before the new offline tools' test files were
added. This is not presented as a full run collecting every final new test: the
following consolidated ops run verifies the completed changes and new tests.

```bash
PATH=/tmp/manhattan-venv/bin:$PATH \
EM_MACRO_DATA=/nonexistent/em-macro-data \
DATA_REPO_URL=/nonexistent/em-macro-data.git \
PYTHONDONTWRITEBYTECODE=1 \
python -m pytest -q -p no:cacheprovider --junitxml=/tmp/manhattan-final-ops.xml \
  tests/test_manhattan_ops_*.py > /tmp/manhattan-final-ops.log 2>&1
```

**Exit 0; 170 passed, 0 skipped, 0 failed, 0 errors; 71.14 seconds.** Includes
private-log failure/mirror regressions, public-channel canaries, crash recovery,
offline monitoring, artifact verification, readiness and actual application and
YAML parsing of the proposed workflow patch in a temporary checkout.

```bash
PATH=/tmp/manhattan-venv/bin:$PATH \
EM_MACRO_DATA=/nonexistent/em-macro-data \
DATA_REPO_URL=/nonexistent/em-macro-data.git \
PYTHONDONTWRITEBYTECODE=1 \
python -m pytest -q -p no:cacheprovider tests/test_q019_explorer_data_loader.py \
  > /tmp/manhattan-security.log 2>&1
```

**Exit 0; 86 passed, 0 failed, 0 skipped; 15.62 seconds.** No Q019 source,
protected security test or sandbox guarantee was changed. The reported eight
macOS `/proc/self/fd` failures do not reproduce on this Linux environment.

The reported unqualified-Python subprocess failures also did not reproduce with
the intended venv first on `PATH`. No protected test was rewritten to hide an
interpreter failure. The default Cloud Python initially lacked pytest; using a
fresh venv resolved that setup issue without resetting GitHub authentication.

Full-run skip categories (from JUnit XML):

| Count | Reason |
|---:|---|
| 125 | Private Norgate snapshot unavailable |
| 3 | Optional numpyro sampler unavailable |
| 1 | Slow model-compilation opt-in unset |
| 1 | Optional reportlab unavailable |
| 1 | Q009 full-sweep opt-in unset |
| 1 | Frozen v1 full reproduction/download opt-in unset |

No failed checks remain. Skips are not passes. Private-data integration, actual
FRED retrieval, the optional sampler and the Macs remain unverified. Tests use
existing fixtures and synthetic inputs; no designated research evaluation or
full reproduction opt-in was enabled.

## Installation and other checks

Fresh second venv `/tmp/manhattan-runner-venv`:

```bash
python -m pip install --no-index --find-links=/tmp/manhattan-runner-wheels \
  --only-binary=:all: --require-hashes -r requirements-manhattan-runner.lock
python -m pip check
python -m manhattan.ops.runner --help
```

Each exited **0**. This tests exact offline wheel installation and runner
imports/CLI availability, not a real nightly run. No nightly CLI was executed
outside the synthetic tests.

A temporary copy of the lock with one hash replaced by zeros was tested with
`pip install --dry-run --ignore-installed --no-deps --no-index
--find-links=/tmp/manhattan-runner-wheels --only-binary=:all: --require-hashes
-r /tmp/manhattan-bad-hash.lock`: **exit 1, expected hash mismatch**. The real
lock remained unchanged. An earlier development test caught an unquoted colon
in the proposed YAML install step; the patch was corrected to a block scalar
and the patch tests now pass.

`git apply --check docs/manhattan/ops/patches/runner-integrity.patch`: **exit 0**.
The patch was not applied to the live workflow. The patch test applies it only
inside a temporary repository, parses the result and checks immutable Action
references and unchanged dispatch-only/main-only/environment/permission gates.

`python -m manhattan.ops.readiness docs/manhattan/ops/genesis_data_readiness.json`:
**exit 0**, ten family inventories, twenty unverified dataset requirements,
`research_execution_authorized: false`.

Workflow comparison against `workflow_baseline_candidate.json`: **exit 0**, zero
differences from the original fetched workflow tree. This only verifies snapshot
consistency; the candidate is **not** an independently owner-approved baseline.

The repository's `nightshift.protected.protected` check was run over every changed
and untracked delivery path: **no protected paths changed**. `git diff --check`
passed. No workflow, private ledger, writer-owned data, freeze, template, promotion
gate, protected code/test or macOS/Tailscale setting was modified. No schedule,
workflow dispatch, background service, port, purchase or trade was initiated.

## Continuation

Use the continuation prompt and owner-only checklist in
[CLOUD_ENGINEERING_HANDOFF.md](CLOUD_ENGINEERING_HANDOFF.md). Local `/tmp`
environments/logs may disappear; the committed sources, tests, environment
snapshot, candidate lock and documents carry the reproducible handoff.

## PR #72 review follow-up (same branch, 2026-11-16)

Independently reviewed the complete original diff at `0d53828` and confirmed
GitHub CI run `43887821034` completed successfully for that commit. The fixes
and remaining trust boundaries are described in `CLOUD_ENGINEERING_HANDOFF.md`.
The Python version, operating system and installed-package snapshot are unchanged;
`pip freeze` matches `cloud-test-environment.txt` exactly. No dependency was added.

Two added mirror regressions failed against the prior code, reproducing both
equal-chain/missing-file certification and a rejected final-log mirror push
reported as success. Both pass with complete committed-tree verification and
the corrected final health result. Other new regression coverage exercises:

* registration failure cleanup, private diagnostics and distinct attempt logs;
* per-call Git deadlines and noninteractive Git environment;
* actual read limits despite an understated stat size; FIFO/symlink refusal;
* duplicate keys, non-finite numbers, excessive nesting and exact schema types;
* log permissions under umask 022 and refusal of linked/special log files;
* sanitized startup/issue-body failures and strict witness Boolean validation.

Final focused command:

```bash
PATH=/tmp/manhattan-venv/bin:$PATH \
EM_MACRO_DATA=/nonexistent/em-macro-data \
DATA_REPO_URL=/nonexistent/em-macro-data.git \
PYTHONDONTWRITEBYTECODE=1 \
python -m pytest -q -p no:cacheprovider tests/test_manhattan_ops_*.py \
  --junitxml=/tmp/manhattan-review-final-ops.xml \
  > /tmp/manhattan-review-final-ops.log 2>&1
```

**Exit 0; 226 passed, 0 skipped, 0 failed, 0 errors; 76.70 seconds.**
All new tests use synthetic inputs and local bare Git stand-ins. The unchanged
candidate owner patch still passes `git apply --check`. Metadata validation still
reports all twenty Genesis requirements unverified and research unauthorized.

A preliminary full run was deliberately interrupted after further CLI defects
were found, so that the full suite could restart against the completed source.
It exited 2 (interrupt), with 458 passed and 125 skipped before interruption;
it is not counted as a successful full run. Final full-suite results follow.

```bash
PATH=/tmp/manhattan-venv/bin:$PATH \
EM_MACRO_DATA=/nonexistent/em-macro-data \
DATA_REPO_URL=/nonexistent/em-macro-data.git \
PYTHONDONTWRITEBYTECODE=1 \
python -m pytest -q -p no:cacheprovider \
  --junitxml=/tmp/manhattan-review-final-full.xml \
  > /tmp/manhattan-review-final-full.log 2>&1
```

**Exit 0; 1,679 passed, 132 skipped, 0 failed, 0 errors; 672.97 seconds;
10 warnings.** This run collected all final source and regression tests. It
includes all 86 unchanged Q019 security tests, passing without skips. The 132
skip reasons match the earlier table: no private snapshots, optional numpyro
and reportlab, and the three explicit opt-ins. No private integration or research
evaluation is claimed. The 226-test ops total is included in the full total,
not additional to it.

Checks against both the branch and freshly fetched main CODEOWNERS found **zero
protected delivery paths**. Whitespace checks passed. Live workflows, owner
switches, research/protocol files and writer-owned data are unchanged. The
candidate baseline and workflow patch still await owner approval; no workflow
was dispatched and no external watcher, private repository or Mac was accessed.

## Final engineering review for owner handoff

Verified clean branch `codex/manhattan-ops-hardening` at source commit `36cc090`;
fetched main and reviewed the complete PR diff. Independently queried GitHub:
`tests` run `43972851460` completed successfully for that source head. The final
review found no additional material code defect, and adds documentation only.

Fresh validation on CPython 3.12.14, Linux 6.18.57 x86_64:

```bash
PATH=/tmp/manhattan-venv/bin:$PATH \
EM_MACRO_DATA=/nonexistent/em-macro-data \
DATA_REPO_URL=/nonexistent/em-macro-data.git \
PYTHONDONTWRITEBYTECODE=1 \
python -m pytest -q -p no:cacheprovider \
  tests/test_manhattan_ops_*.py tests/test_q019_explorer_data_loader.py \
  --junitxml=/tmp/manhattan-owner-review.xml \
  > /tmp/manhattan-owner-review.log 2>&1
```

**Exit 0; 312 passed, 0 skipped, 0 failed, 0 errors; 83.14 seconds.** This is
226 ops tests plus 86 Q019 tests, not 312 additional tests beyond those groups.
The full suite was not rerun locally in this final documentation-only pass;
its latest source-head GitHub CI result was verified rather than inferred from
the older local report above. No unresolved test failure was found.

Other fresh checks, each exit 0:

* `git diff origin/main...HEAD --check` and the protected-path check using both
  branch and main CODEOWNERS: zero protected paths among the 23 delivery files.
* `git apply --check docs/manhattan/ops/patches/runner-integrity.patch`.
* `/tmp/manhattan-runner-venv/bin/python -m pip check` and
  `/tmp/manhattan-runner-venv/bin/python -m manhattan.ops.runner --help`.
* `python -m manhattan.ops.monitor integrity --approved
  docs/manhattan/ops/workflow_baseline_candidate.json`: no differences; this
  verifies consistency only, not owner approval.
* `python -m manhattan.ops.readiness docs/manhattan/ops/genesis_data_readiness.json`:
  twenty unverified requirements; research execution unauthorized.

The final approval/activation distinctions, platform limits and three recommended
next tasks are recorded in `CLOUD_ENGINEERING_HANDOFF.md`. None of those next
tasks was begun. No deployment, schedule, dispatch, private evidence access,
scientific change, protected-path edit or merge occurred.

## Phase 3B final PIT corrections

Base: latest main `718c1ab371f4d2b957c4a407e99030e8258f13b0`.
Branch: `codex/manhattan-phase3b-pit`. Python 3.12.14 / Linux x86_64;
a fresh `/workspace/em-macro-venv` installed the **unchanged CI requirements**:
`pip install -r requirements.txt -r requirements-elections.txt pytest`.
No optional research opt-ins or private data were enabled. The package proxy
required running the install and full suite outside the command sandbox; no
sandbox policy, workflow or environment configuration was edited.

```bash
set -o pipefail
EM_MACRO_DATA=/nonexistent/em-macro-data \
DATA_REPO_URL=/nonexistent/em-macro-data.git \
PYTHONDONTWRITEBYTECODE=1 \
/workspace/em-macro-venv/bin/python -m pytest -q -rs -p no:cacheprovider \
  tests/test_manhattan_pit* tests/test_manhattan_engine.py \
  tests/test_manhattan_registry.py tests/test_manhattan_ops_compiler.py \
  tests/test_q019* 2>&1 | tee /tmp/phase3b-targeted-final.log
```

**Exit 0: 288 passed, zero skipped/failed, 22.18s.** Includes 125 PIT cases
(56 existing plus 69 new) and all 86 unchanged Q019 security tests. The ten
warnings are NumPy's generic-unit deprecation in intentional rejection fixtures.
The initial targeted run had one API allowlist assertion failure (the new
non-reading methods were absent from the allowlist); fixed without relaxing the
reader fence. An initial full run was interrupted to add reconstruction marking
to look-ahead copies: exit 2, 458 passed/125 skipped. It is not a validation result.

Final full-suite command (CI's command/environment plus skip reasons and XML):

```bash
set -o pipefail
EM_MACRO_DATA=/nonexistent/em-macro-data \
DATA_REPO_URL=/nonexistent/em-macro-data.git \
PYTHONDONTWRITEBYTECODE=1 PATH=/workspace/em-macro-venv/bin:$PATH \
python -m pytest -q -rs -p no:cacheprovider \
  --junitxml=/tmp/phase3b-final-full.xml 2>&1 | tee /tmp/phase3b-final-full.log
```

**Final full run: exit 0; 1,822 passed, 132 skipped, zero failures/errors,
686.09s.** All 125 PIT and 86 Q019 cases pass. Twenty warnings: ten intentional
NumPy generic-unit rejection-fixture deprecations and ten existing synthetic
numerical warnings. Core versions match PR #76 CI: NumPy 2.5.5, pandas 3.1.1,
SciPy 1.18.1, pytest 9.2.0. No implementation or test changed during this final run.

Every skip reported by `-rs`:

| Count | Location | Confirmed reason |
|---:|---|---|
| 125 | `test_commod_data.py:132,137,145,153,164` (1 + 31 + 31 + 31 + 31) | private Norgate snapshot not available (`EM_MACRO_DATA`) |
| 3 | `test_manhattan_hier.py:190,203,233` | could not import `numpyro`: No module named `numpyro` |
| 1 | `test_manhattan_hier.py:237` | slow (compiles all six models twice): set `MANHATTAN_SLOW_TESTS=1` |
| 1 | `test_nightshift.py:399` | could not import `reportlab`: No module named `reportlab` |
| 1 | `test_q009_janus_price_check_hash_collision.py:134` | `Q009_FULL_SWEEP=1` runs 6000 real runs (~100 s) |
| 1 | `test_verify_v1.py:56` | full reproduction: set `EM_MACRO_VERIFY_V1=1` (downloads uncached series) |

`pip check`, `git diff --check` and protection checks against both branch/main
CODEOWNERS plus `nightshift.protected.ALWAYS` pass. All 15 changed paths are
unprotected; no `.github/`, `config/`, `data/`, `results/` or `.claude/` path is
changed. No protected protocol, writer workflow, activation or blinding rule was
modified. GitHub CI results will be recorded on the draft PR after completion.

### Confirmed explanation of PR #76's two extra CI skips

Read the actual [run 44009157504](https://github.com/EthanC100/em-macro/actions/runs/44009157504)
job `133791688909`: checkout explicitly used `fetch-depth: 1`, `fetch-tags: false`,
and merge commit `95b46d4ea5969663698da343042c41b4c0296207`. That workflow did not
use `-rs`; the aggregate alone could not establish skip causes. Independently
reproduced both conditions, without changing the workflow or any test:

```bash
git clone --depth=1 --no-tags file:///workspace/em-macro /workspace/em-macro-shallow
# Run separately in each checkout with the same CI environment and venv:
python -m pytest -q -rs -p no:cacheprovider \
  tests/test_q002_rebalance_kick.py tests/test_verify_v1.py
```

| Test | Depth-one reason from `-rs` | Full-history result |
|---|---|---|
| `test_the_update_job_computes_exactly_as_before` | `commit a5f9dd4 (main before Q002) is not in this checkout` (`test_q002_rebalance_kick.py:54`) | passed |
| `test_snapshots_from_the_freeze_commit_match_the_record` | `commit 7886867 not in this clone (shallow)` (`test_verify_v1.py:50`) | passed |
| `test_v1_reproduces_exactly` | `full reproduction: set EM_MACRO_VERIFY_V1=1 (downloads uncached series)` | deliberately skipped in both |

Depth-one: **9 passed, 3 skipped, exit 0, 0.57s**. Full-history run also included
Q003 and Q016 skip-sensitive tests: **21 passed, 1 skipped, exit 0, 0.65s**; neither
Q003 nor Q016 skipped. Both additional CI skips really are missing-history checks,
but this conclusion follows separate reproduction of each, not the aggregate.

PR #76's unchanged 1,751 pass count across local/CI is not evidence of identical
collection: its local full run contained 54 PIT cases, and two parser cases were
added afterward (documented above). Those two additional CI passes offset the two
history checks changing from pass to skip. The final phase 3B suite includes all
125 PIT cases. No real-data reproduction is needed to resolve this discrepancy.
