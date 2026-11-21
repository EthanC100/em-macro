"""Manhattan equities research programme (technology and non-technology tracks): point-in-time foundations
(docs/manhattan/equities/).

Synthetic-only research infrastructure. Nothing in this package reads real market data, runs a strategy search,
produces evidence or a claim, or changes Manhattan's protocol, ledger, PIT reader, store or statistics. Candidate
pairs, analogue matches and features are research inputs with zero evidential weight (``evidence``).

    sessions      exchange sessions; the first close at which a public timestamp may be used
    sources       data-source contracts: provenance, timing, revisions, permitted roles (fail closed)
    identity      companies, securities, ticker intervals and lifecycle events through time
    prices        raw prices, corporate actions, split adjustment, total and delisting returns
    fundamentals  bitemporal financial statements: originals, restatements, availability
    estimates     analyst estimates, consensus as of a time, revisions and coverage
    events        earnings-release timing and surprise primitives
    universe      categories, classification history, point-in-time eligibility, per-track rules and snapshots
    sectors       the sector taxonomy: technology and ten non-technology sectors, and their research tracks
    graph         economic relationship graph with validity and disclosure dates; lagged propagation
    features      cross-sectional normalisation, neutralisation and factor exposures
    pairs         pair discovery inside an information boundary; spread and stability diagnostics
    analogues     historical fundamental analogues with descriptive and training eligibility
    macro         point-in-time macro sensitivities and incremental-information diagnostics
    costs         trading costs, borrow availability and fees, shorting constraints
    risk          long/short and directional exposure reports; effective number of bets
    evidence      the candidate/evidence boundary and the protocol-scope gate
    provenance    content hashes of research outputs (reuses manhattan.spec canonical form)
    pit_bridge    export to manhattan.engine.pit.PitStore (the existing one door to data)
    catalogue     the hypothesis-family catalogue (catalogue.yaml) and its validation
    integration   contracts for interfaces still being built elsewhere (attempts, evidence classes, costs)
    synthetic     deterministic synthetic fixtures
    sector_synthetic  a synthetic world with technology and non-technology sectors (issue #102)
    track_compare     technology-only, non-technology-only and combined portfolios; measured sector volatility

Two research tracks share this package: technology and non-technology equities (issue #102,
docs/manhattan/equities/NON_TECH_TRACK.md). They differ only in the categories their universes admit.
"""
