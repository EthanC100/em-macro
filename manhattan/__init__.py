"""Manhattan: a hypothesis-first research lab (docs/manhattan/).

Design: docs/manhattan/ARCHITECTURE.md. Rules of evidence: docs/manhattan/PROTOCOL_v3.md (not in force until the
simulation of docs/manhattan/SIM_PREREG.md has passed). Progress and the next step: docs/manhattan/MANHATTAN_PROGRESS.md.

    manhattan.prereg, manhattan.config   the frozen pre-registration's hash check; Ethan's switches
    manhattan.stats                      the statistical methods, as pure functions (under test, not in force)
    manhattan.sim                        the simulation lab: synthetic worlds, runs, metrics, reports
    manhattan.spec, ledger, roles        content-addressed specs; the hash-chained ledger; data-role fences
    manhattan.freeze, generate, critic   batch preparation and the runner's freeze check; generator requests;
                                         the critic's specs-only input

This package may import the frozen modules of em_macro, ledger, lab and nightshift; it never edits them. Nothing in
it produces a claim: ``claims.enabled`` is false until the simulation has passed.
"""
