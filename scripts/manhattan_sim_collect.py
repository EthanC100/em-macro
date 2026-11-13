#!/usr/bin/env python3
"""Put together a Manhattan simulation run made in pieces, and say what is missing.

    gh run download <run id> --pattern 'manhattan-sim-piece-*' --dir pieces      # or unzip the artifacts by hand
    python scripts/manhattan_sim_collect.py merge pieces                         # into results/manhattan_sim; refuses
                                                                                 # anything that may not be pooled
    python scripts/manhattan_sim_collect.py status                               # what is still missing; exit 1 if any
    python scripts/manhattan_sim_collect.py plan                                 # the pieces a new run would make

The work is done by ``manhattan/sim/collect.py`` (``python -m manhattan.sim.collect`` is the same command); this
file only makes it runnable from anywhere in a checkout. The pieces come from ``.github/workflows/manhattan-sim.yml``
or from any machine that ran ``python -m manhattan.sim.run --first a --reps b --label part --out <directory>``.
Synthetic data only. Runbook: docs/manhattan/SIM_RUNBOOK.md, "On GitHub's runners".
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from manhattan.sim import collect  # noqa: E402

if __name__ == "__main__":
    sys.exit(collect.main())
