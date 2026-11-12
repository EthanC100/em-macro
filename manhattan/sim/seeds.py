"""Seeds (SIM_PREREG section 9): everything random descends from the pre-registration's own SHA-256.

The master seed is the first 8 bytes of the SHA-256 of docs/manhattan/SIM_PREREG.md, read as an integer. Each
stream is ``numpy.random.SeedSequence(master, spawn_key=(branch, scenario, size, replication, *stream))``:
``branch`` 0 is development, ``k`` is confirmation run ``k`` (1-3), ``10 + k`` is the one pooled re-run that
section 8.3 allows for confirmation run ``k``. A scenario's key is the first 4 bytes of the SHA-256 of its id, so
adding a scenario never moves another scenario's streams.

Held-out set ``k`` (section 8.2) is drawn from a generator seeded with the SHA-256 of the text
``manhattan-sim-heldout-<k>-`` followed by the pre-registration's SHA-256.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

from manhattan import prereg

SIM_PREREG = "docs/manhattan/SIM_PREREG.md"
SIZE_KEY = {"STD": 0, "LONG": 1, "HB": 2}
DEVELOPMENT = 0
# stream ids inside one replication
PROGRAMME, COMMON, FAMILY_PARAMS, FAMILY_NOISE, BOOTSTRAP, ADAPTIVE, ADAPTIVE_BOOT, FACTOR, MODEL, ESTIMATE = range(10)


def prereg_hash(root: Path = prereg.ROOT) -> str:
    """The recorded SHA-256 of SIM_PREREG.md, after checking that the file still matches it."""
    record = root / "docs/manhattan/sim_prereg.sha256"
    errs = prereg.verify(record, root)
    if errs:
        raise RuntimeError("the simulation pre-registration does not match its recorded hash: " + "; ".join(errs))
    for h, rel in prereg.read_record(record):
        if rel == SIM_PREREG:
            return h
    raise RuntimeError(f"{SIM_PREREG} is not in {record.name}")


def master_seed(sha: str) -> int:
    return int.from_bytes(bytes.fromhex(sha)[:8], "big")


def scenario_key(scenario_id: str) -> int:
    return int.from_bytes(hashlib.sha256(scenario_id.encode("utf-8")).digest()[:4], "big")


def confirmation_branch(k: int, pooled_rerun: bool = False) -> int:
    if k not in (1, 2, 3):
        raise ValueError("there are three held-out sets: k is 1, 2 or 3")
    return 10 + k if pooled_rerun else k


class Streams:
    """The random streams of one replication of one scenario at one size."""

    def __init__(self, sha: str, branch: int, scenario_id: str, size: str, rep: int):
        self.master = master_seed(sha)
        self.key = (int(branch), scenario_key(scenario_id), SIZE_KEY[size], int(rep))

    def seq(self, *stream: int) -> np.random.SeedSequence:
        return np.random.SeedSequence(self.master, spawn_key=self.key + tuple(int(s) for s in stream))

    def rng(self, *stream: int) -> np.random.Generator:
        return np.random.default_rng(self.seq(*stream))


def heldout_rng(k: int, sha: str) -> np.random.Generator:
    if k not in (1, 2, 3):
        raise ValueError("there are three held-out sets: k is 1, 2 or 3")
    digest = hashlib.sha256(f"manhattan-sim-heldout-{k}-{sha}".encode("utf-8")).digest()
    return np.random.default_rng(np.random.SeedSequence(int.from_bytes(digest, "big")))
