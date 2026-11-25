# First Light overnight hardening

Baseline: draft PR #107 at `9546f03ed96fbfe13e0e67b07b8cb23da736c740`, stacked on
PR #106 at `c3f665145d1c7e055b484f629b0314af648d39b5`. PRs #104, #105 and #108
were already merged when this work began. No merges or activations are performed
by this continuation. PR #107 remains draft and requires independent review.

## Changes

- Reproduction children inherit only an explicit runtime environment allowlist:
  platform paths, locale and numerical thread controls. Unrecognized variables,
  proxy URLs, personal access tokens, authentication sockets, NETRC and Python/Git
  injection settings are excluded. The parent environment is not mutated. This
  is environment isolation, not a filesystem or network sandbox.
- Reproduction checks the existing local explorer cutoff before creating its
  output directory or launching either child. Invalid or unreadable cutoff files
  refuse with CLI exit 3, matching the single-run path. The local-file cutoff
  is scoped to the synthetic harness; owner authorization is not established by this document. Production logging is unchanged.
- Added regression coverage for non-hex/malformed anchor heads and an unknown
  extra variant-log row. Existing refusal behavior is preserved.

No protected paths, scientific rules, configuration, signatures, screening,
research switches, workflows, schedules or production controls change. Signing
key pins remain empty. No real or licensed data is used.

## Evidence before publication

- Focused First Light harness and cap suites: 139 passed, exit 0.
- Child isolation and early-refusal subset: 30 passed, 56 deselected, exit 0.
- New environment/cutoff tests against the old #107 head: 25 failed and 4 passed,
  exit 1. All run without real credentials; failures establish the old defects.
- #106 freeze/equities targeted check: 92 passed, 2 failed in the restricted
  sandbox. The two disposable GPG-key tests both passed with additional runtime
  permissions. A separate synthetic key-generation probe showed the restricted
  sandbox cannot start gpg-agent ("No agent running"). No production key was
  created, pinned or modified.
- The overnight guard passed after reading main's protected configuration and
  checking for conflicting writer workflows. No writer workflow was dispatched.

- Full suite: 4,355 passed, 165 skipped, 1 failed, 248 warnings, exit 1
  (1,685.28 seconds). The failure is
  `test_spawn_workers_of_a_dead_invocation_are_killed_before_the_next_starts`.
  It also fails in isolation on untouched main `52bd8c9` (98.56 seconds) and on
  this branch (90.44 seconds): recorded Linux zombies remain under PID 1 and
  prevent the supervisor from starting a retry. No First Light code is involved;
  a separate orchestra correction is required. The local full suite is not green.
- Remote CI must be checked for the new head separately. The PR is stacked on
  #106 and the tests workflow targets pull requests to main, so a new push may
  not trigger CI until the existing owner-approved retarget step. An older green
  check must not be reported as validation of the new head.

## Remaining owner and review gates

PR #106 needs review of its updated head and owner approval before merge. PR #107
stays draft and unmerged. Real freeze verification still needs an owner signing
key and a genuine timestamp-attestation verifier; this continuation supplies
neither. Independent anchor custody, canonical ledger choice and other existing
scientific policy decisions remain open. A local synthetic harness report is not
research evidence and authorizes no promotion or trading.

## S17 corrective review

Masked arrays and every ndarray subclass are refused before ingestion. Both lag
and explicit-availability paths pass the checked plain period/availability arrays
to PitStore. Content-error refusal is tested independently of missing attestation.

Output must resolve outside the checkout, including on resume and reproduction;
writer-owned directories inside the checkout are therefore refused. Children use
-B -E -s as well as the runtime environment allowlist, so user site-packages are not
loaded, and -B prevents bytecode writes even though -E ignores the environment's PYTHONDONTWRITEBYTECODE setting. The local cutoff override does not verify main's current configuration.
The earlier wording claiming owner approval was unsupported and has been removed;
authorization of this local-file cutoff remains an explicit owner question.

The cap also needs the same correction on the separate S17 audit branch. Its
exact current branch/head must be identified before updating it; no unrelated
audit work should be overwritten. GitHub CI for this stacked draft still requires
the existing dependency merge and retarget sequence.
