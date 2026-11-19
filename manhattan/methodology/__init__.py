"""Manhattan research methodology (session S13): accounting rules and synthetic-world tests of the evidence chain
at the scale Manhattan is built for.

Nothing here reads a file, a market series, the ledger or the store, and nothing here is a rule in force. The
package tests the *existing* procedures of ``manhattan.stats`` (screening candidates (i) and (ii), Hansen's SPA,
e-LOND) on synthetic null and planted-effect worlds that the pre-registered simulation (SIM_PREREG, SIM_PREREG_v2)
does not cover: very large grids, thousands of families, duplicated candidates, opposite-sign families, reruns and
the end-to-end research funnel.

Every number it produces describes a synthetic generator. A synthetic "discovery" is a check of a procedure, never
a trading signal. No module here is in ``manhattan.sim.run.CODE_FILES``, so nothing here changes the code hash of
any simulation record.

    identity     the three identity layers (scientific, evaluation, scheduling) and the population census
    maxnull      exact null distribution of the maximum of equicorrelated normal statistics (an oracle SPA)
    worlds       programme-scale synthetic worlds: null, planted, duplicated, mirrored, shared or disjoint windows
    evaluate     runs the screening candidates over a world and counts errors per unit and per scientific class
    experiments  the experiments of docs/manhattan/methodology/S13_RESEARCH_METHODOLOGY.md, with a CLI
"""
