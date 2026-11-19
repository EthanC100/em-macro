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
    evaluation spec + engine     executable   (PR #86 binds code into the executable; HTE keeps it on the attempt)
    variant full hash            variant
    hypothesis full hash         hypothesis
    family full hash             family
    run id                       batch        (HTE runs are not Manhattan batches; "hte-" prefix marks that)
    "exploration"                role         (the only role HTE could ever map to; reserve/forward refused)
    "blind"                      channel      (HTE workloads are declared grids; adaptive additions are post_look)
    False                        designated   (HTE never makes a designated evaluation)
    evaluation_spec hash         spec_hash    (candidate + every policy, cost, sizing, sign, window, stage and
                                              timing parameter: S10 F7)
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


def evaluation_spec(view, i: int, *, policy, fence: int, stages=(1, 2, 3, 4)) -> dict:
    """Everything that can change an HTE evaluation of candidate ``i`` other than data and code (S10 F7): the
    candidate, the family's predicted sign, the template version, the resolved cost coefficients of its domain
    and cost model, the sizing constants, every policy field, the evaluation window, the requested stages, the
    execution-timing convention and the methodology. Data and code are separate identity fields."""
    from . import kernels
    from . import templates as TP
    d = view.describe(int(i))
    c, k = kernels.cost_coefficients(d["domain"], TP.COST_MODELS[d["cost_model"]])
    spec = view.reg.spec(int(view.spec_index[int(i)]))
    return {
        "candidate": view.candidate_hash(int(i)), "sign": d["sign"], "template": d["template"],
        "template_version": spec["template_version"], "domain": d["domain"],
        "costs": {"linear": c, "impact": k, "impact_power": 1.5},
        "sizing": {"rule": d["sizing"], "ann_risk": TP.ANN_RISK, "vol_halflife": 60},
        "policy": policy.as_dict(), "window": {"warmup": int(policy.warmup), "fence": int(fence)},
        "stages": sorted(int(x) for x in stages), "execution": kernels.EXECUTION_TIMING,
        "methodology": METHODOLOGY,
    }


def to_pr86_identity(view, i: int, *, run_id: str, data_hash: str, code: dict, window: dict, policy, fence: int,
                     stages=(1, 2, 3, 4)) -> dict:
    """The PR #86 schema-2 attempt identity of one HTE evaluation. ``spec_hash`` is the hash of
    ``evaluation_spec`` (so two evaluations that differ in any evaluation-affecting parameter never share it);
    ``executable`` binds that spec to the engine digest."""
    from . import ids
    d = view.describe(int(i))
    variant = bytes(view.variant[int(i)]).hex()
    spec_hash = ids.full_hash(evaluation_spec(view, i, policy=policy, fence=fence, stages=stages))
    exe = ids.full_hash({"evaluation_spec": spec_hash, "engine_sha256": code["engine_sha256"]})
    out = {
        "executable": exe, "variant": variant, "hypothesis": d["hypothesis_hash"], "family": d["family_hash"],
        "batch": f"hte-{run_id}", "role": "exploration", "channel": "blind", "designated": False,
        "spec_hash": spec_hash, "data_hash": data_hash, "window": dict(window),
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


# -- PR #85 (synthetic futures execution, cost and roll model): disabled boundary (S10 F8) ---------------------------

PR85_BLOCKERS = (
    "E1 PR #85 is not merged; its API (manhattan.execution: run, Decision, ExecutionPolicy, MarketData) is not "
    "stable from this branch",
    "E2 timing differs: HTE fills at the decision close (EXECUTION_TIMING); PR #85 executes at the settlement of "
    "the lag-th close strictly after the decision (lag >= 1). HTE results are therefore optimistic by one day and "
    "are restricted to synthetic throughput testing",
    "E3 PR #85 works on one position plan at a time (contracts, rolls, ticks, liquidity caps, FX); HTE stage 3 is "
    "vectorised over candidates on continuous synthetic returns. Wiring it in is a new, heavier stage 3, run only "
    "on stage-3 representatives",
    "E4 PR #85 is uncalibrated (CALIBRATED = False) and takes caller-supplied markets; HTE has no contract-level "
    "synthetic market to give it",
)


def to_pr85_decisions(*args, **kwargs):
    """The intended mapping (not implemented): HTE position row t (data through close t) -> a PR #85
    ``Decision(root, contracts, decided_at = close t, inputs_known_at = close t)`` with
    ``ExecutionPolicy(lag >= 1)``, contracts from target weight x capital / (price x point value) rounded by PR #85.
    Refuses until E1-E4 are resolved."""
    raise AdapterDisabled("the PR #85 execution boundary is disabled: " + "; ".join(PR85_BLOCKERS))


class Pr85ExecutionAdapter:
    enabled = False

    def __init__(self, *args, **kwargs):
        raise AdapterDisabled("the PR #85 execution adapter is disabled: " + "; ".join(PR85_BLOCKERS))
