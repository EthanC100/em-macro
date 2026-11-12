"""Manhattan simulation lab: the methods of PROTOCOL_v3.md run on synthetic worlds, under SIM_PREREG.md.

Everything here is synthetic. No market series is read, and no result of this package is market evidence.
docs/manhattan/SIM_PREREG.md fixes the scenarios, metrics, thresholds, replication counts and the selection rule;
it is never edited (additions go to SIM_PREREG_AMENDMENTS.md). Every run is logged in
results/manhattan_sim/runs.jsonl, and a held-out scenario is refused outside a tagged confirmation run.

    python -m manhattan.sim.run --help
"""
