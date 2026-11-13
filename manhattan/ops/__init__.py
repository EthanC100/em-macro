"""Manhattan operations: the minimum trustworthy system for the first research cycle on public data.

Session 7M, branch ``build/manhattan-ops``; criteria in ``docs/manhattan/OPS_PROGRESS.md``. Statistical claims stay
gated (``promotion.promote`` refuses every tier). The modules:

    blinding      the public channel carries operational health only; outcomes go to the private ledger
    promotion     tier changes are refused in code until Ethan adopts a validated protocol version
    timing        registration time, first eligible observation, prospective eligibility
    store         the durable private ledger: hash chain, journal, lock, idempotency, mirror, verification
    justify       evidence-aware variant limits: justification, effective count, power loss, budget
    critic_rules  the mechanical, spec-only half of the critic
    compiler      spec to engine executable at the family's natural frequency
    data          first-seen capture of public data, and the synthetic data used by tests
    runner        the nightly runner (GitHub Actions, public data)
    freeze_pr     prepares a manifest pull request; commits and pushes nothing
    mockgen       a mock generator for tests: SYNTHETIC families only, never a real hypothesis
    isolation_kit the generator isolation test kit (standard library only; copy it into a candidate environment)
    leakscan      searches every public output channel for performance values
    capacity      runtime and memory measurements

Nothing here edits shared engine or registry code; adapters stand in where a change is needed
(OPS_PROGRESS.md, "Requests to the shared code").
"""
