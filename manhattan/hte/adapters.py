"""The boundary between HTE and Manhattan attempt accounting (PR #86). **Disabled.**

HTE keeps its own complete, hash-chained attempt log (``log.py``) so that it can be built and tested without
touching protected or unmerged systems. When PR #86 (``manhattan/access.py``, attempt schema 2) is merged and its
owner decisions are made, HTE attempts would be registered there. This module states that contract in code:

* ``to_pr86_identity`` maps an HTE candidate attempt onto the ``ledger.IDENTITY_FIELDS`` shape PR #86 validates
  (executable, variant, hypothesis, family, batch, role, channel, designated, spec_hash, data_hash, window,
  code_version). It is a pure function with no import of PR #86, so its shape is tested here against the documented
  field list, not against PR #86's validator (that check needs PR #86 merged: blocker B1 below).
* ``Pr86AccessAdapter`` refuses construction and lists the blockers.

Mapping decisions (docs/manhattan/hte/ARCHITECTURE.md section 7):

    HTE                          PR #86 identity field
    candidate + engine digest    executable   (PR #86 binds code into the executable; HTE keeps it on the attempt)
    variant full hash            variant
    hypothesis full hash         hypothesis
    family full hash             family
    run id                       batch        (HTE runs are not Manhattan batches; "hte-" prefix marks that)
    "exploration"                role         (the only role HTE could ever map to; reserve/forward refused)
    "blind"                      channel      (HTE workloads are declared grids; adaptive additions are post_look)
    False                        designated   (HTE never makes a designated evaluation)
    candidate full hash          spec_hash
    panel data hash              data_hash
    {id, start, end, frequency}  window       (synthetic dates of the evaluation window)
    {commit, engine_sha256}      code_version

Blockers (any one keeps the adapter disabled):
    B1  PR #86 is not merged; its API is not stable from this branch's point of view.
    B2  exploration attempts are deliberately unregistered in PR #86 (owner decision D-10).
    B3  the counting unit for a multiple-testing denominator is open (D-1).
    B4  HTE chunk attempts cover many candidates; PR #86 attempts are one executable each. A one-to-many mapping
        (or one PR #86 attempt per candidate: about 3 records per candidate, ~3 million for a 10^6 run) is a
        design decision for the owner.
    B5  HTE data is synthetic; PR #86's PitStore(synthetic=True) diagnostic windows are "never evidence", which is
        consistent, but reserve/forward roles must never be reachable from HTE.
"""
from __future__ import annotations

import re

from . import METHODOLOGY

BLOCKERS = ("B1 PR #86 not merged", "B2 exploration attempts unregistered (D-10)", "B3 counting unit open (D-1)",
            "B4 chunk-to-attempt cardinality undecided", "B5 synthetic-only engine")
PR86_IDENTITY_FIELDS = ("executable", "variant", "hypothesis", "family", "batch", "role", "channel", "designated",
                        "spec_hash", "data_hash", "window", "code_version")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class AdapterDisabled(RuntimeError):
    pass


def to_pr86_identity(view, i: int, *, run_id: str, data_hash: str, code: dict, window: dict) -> dict:
    from . import ids
    d = view.describe(int(i))
    cand = view.candidate_hash(int(i))
    variant = bytes(view.variant[int(i)]).hex()
    exe = ids.full_hash({"candidate": cand, "engine_sha256": code["engine_sha256"], "methodology": METHODOLOGY})
    out = {
        "executable": exe, "variant": variant, "hypothesis": d["hypothesis_hash"], "family": d["family_hash"],
        "batch": f"hte-{run_id}", "role": "exploration", "channel": "blind", "designated": False,
        "spec_hash": cand, "data_hash": data_hash, "window": dict(window),
        "code_version": {"commit": code.get("commit"), "engine_sha256": code["engine_sha256"]},
    }
    for k in ("spec_hash", "data_hash"):
        if not _HEX64.match(out[k]):
            raise ValueError(f"{k} is not a 64-hex SHA-256")
    return out


class Pr86AccessAdapter:
    enabled = False

    def __init__(self, *args, **kwargs):
        raise AdapterDisabled("the PR #86 accounting adapter is disabled: " + "; ".join(BLOCKERS))
