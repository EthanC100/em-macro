# Cloud validation — 2026-11-16

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
