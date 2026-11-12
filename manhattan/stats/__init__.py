"""Manhattan statistics: the methods of docs/manhattan/PROTOCOL_v3.md as pure functions of arrays.

Nothing here reads a file, a market series or the ledger. ``manhattan.sim`` runs these functions on synthetic data
under docs/manhattan/SIM_PREREG.md; production code (milestone F) may call a method only after the simulation has
passed for it (``claims.enabled`` in config/manhattan.yaml). Until then every output is a number under test, not a
claim.

Formulas were checked against the primary papers before they were coded; pages are in
docs/manhattan/MANHATTAN_PROGRESS.md ("Phase C entry criteria").
"""
