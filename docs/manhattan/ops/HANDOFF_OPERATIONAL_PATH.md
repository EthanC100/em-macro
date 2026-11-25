# Handoff: Manhattan operational path (session of 2026-11-25)

Branch `claude/manhattan-operational-path-7zaf0s`. Paper-only; synthetic data only; nothing dispatched, enabled,
or changed in settings, secrets, protected paths, the protocol, thresholds or `config/manhattan.yaml`.

| workstream | result | read |
|---|---|---|
| #86 accounting at the real entry point | **holds end to end**; the gap was that the CLI was never tested and could not run synthetic data. Added a guarded `--rehearsal` mode and 11 process-level tests (registration before read, atomic results+terminals, hard kills, restart, rerun, concurrent lockout, public channels, anchored audit); each guarantee mutation-checked | [ENTRYPOINT_EVIDENCE.md](ENTRYPOINT_EVIDENCE.md) |
| paper runner + private ledger | control, anchor custody, record binding, recovery and audit specified; `manhattan.ops.audit`; readiness **not ready**: 9 owner items, 2 build items (R04 registration path, R05 witness verifier); rehearsal at 10 and 20 families passes | [PAPER_RUNNER_READINESS.md](PAPER_RUNNER_READINESS.md) |
| first dataset | FRED H.10 BRL/MXN/ZAR: **previously examined, every segment**; no stronger designation supported | [EXPOSURE_AUDIT_FRED_H10.md](EXPOSURE_AUDIT_FRED_H10.md) |
| benchmarks | ops path ≈ 0.05 s per forward attempt + 5-6 s per night; 1M nightly forward confirmation infeasible as built (≈ 14.5 h/night, projection); HTE 1M screening ≈ 12.5 min (projection) | [BENCHMARKS_OPS.md](BENCHMARKS_OPS.md) |
| pilot plan | gates, sizes, measures, stop conditions; **not to be executed without Ethan's authorization** | [REAL_DATA_PILOT_PLAN.md](REAL_DATA_PILOT_PLAN.md) |
| app v1 | outcome-blind operations page + JSON export; synthetic demo `python -m manhattan.app demo --out DIR`; reveal designed, not implemented | [APP.md](APP.md) |

For the family chat: the runner can record 10-20 frozen families now in rehearsal; a real start needs Ethan's
freeze of the first batch plus the owner items in PAPER_RUNNER_READINESS section 6.

Queue items for the night shift to record on dev (not edited here): R04, R05; the ops nights slow with ledger age
(first-seen rebuild and whole-chain rewrite per commit, BENCHMARKS_OPS.md); orchestra status must be re-audited
before any job kind touches real data.
