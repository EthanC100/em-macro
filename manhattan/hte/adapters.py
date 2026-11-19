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
    executable spec hash         executable   (the same hash as spec_hash, see below)
    variant full hash            variant
    hypothesis full hash         hypothesis
    family full hash             family
    run id                       batch        (HTE runs are not Manhattan batches; "hte-" prefix marks that)
    "exploration"                role         (the only role HTE could ever map to; reserve/forward refused)
    "blind"                      channel      (HTE workloads are declared grids; adaptive additions are post_look)
    False                        designated   (HTE never makes a designated evaluation)
    executable spec hash         spec_hash    (binding + engine digest + numerical environment: S11, below)
    panel data hash              data_hash
    {id, start, end, frequency}  window       (synthetic dates of the evaluation window)
    {commit, engine_sha256,      code_version
     numeric_environment_sha256}

Identity levels (S11, the residual of S10 F7). PR #86 decides whether a completion is a new look, a rerun or a
nondeterminism by ``Ledger.key`` = ``(spec_hash, data_hash, window id)`` alone; ``code_version`` is recorded but is
not in the key. Manhattan's own executables carry the code version *inside* ``spec_hash`` (``manhattan.spec.executable``;
ARCHITECTURE section 3: "a bug-fixed code version is a new executable of the same variant"). HTE therefore keeps
two levels apart:

    binding     ``evaluation_binding_hash``: the hash of ``evaluation_spec``: the scientific evaluation (candidate,
                sign, costs, sizing, policy, window, stages, timing, methodology). No code, no environment.
    executable  ``executable_spec``: {binding, engine_sha256, numeric_environment_sha256}. Its hash is PR #86's
                ``spec_hash`` and ``executable``: one executable evaluation instance.

So a change of engine code or of numerical environment is a new executable of the same binding: a new PR #86 key,
an ``evaluation`` record, never a ``rerun`` of another engine's look and never a false ``nondeterminism`` that would
suspend the family. The same binding, engine and environment keep one key, so PR #86's rerun and nondeterminism
rules keep their meaning: different bits there are a real nondeterminism. No identity is arbitrary: each is a
content hash of what ran, and an executable never adds a variant, hypothesis, family or binding, so no scientific
count moves (``executable_accounting``).

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


EXECUTABLE_LEVEL = "hte_executable"
EXECUTABLE_SCHEMA = 1
# PR #86 ``ledger.Ledger.key``: the fields that decide evaluation / rerun / nondeterminism (stated, not imported: B1)
PR86_KEY = ("spec_hash", "data_hash", "window.id")


def _sha(name: str, value) -> str:
    if not isinstance(value, str) or not _HEX64.match(value) or set(value) == {"0"}:
        raise ValueError(f"{name} is not a 64-hex SHA-256")
    return value


def evaluation_binding_hash(view, i: int, *, policy, fence: int, stages=(1, 2, 3, 4)) -> str:
    """The scientific evaluation of candidate ``i``: the hash of ``evaluation_spec``. Code- and environment-free,
    so every executable that evaluates the same thing on any engine or machine shares it."""
    from . import ids
    return ids.full_hash(evaluation_spec(view, i, policy=policy, fence=fence, stages=stages))


def executable_spec(binding: str, code: dict) -> dict:
    """One executable evaluation instance: a binding run by one engine digest in one numerical environment.
    Refuses a code identity without both digests, and one whose environment digest does not match the environment
    it carries (an environment is accounted for explicitly or not at all)."""
    from . import ids
    if not isinstance(code, dict):
        raise ValueError("code identity must be the mapping of ids.code_identity()")
    env_sha = _sha("numeric_environment_sha256", code.get("numeric_environment_sha256"))
    if "numeric_environment" in code and ids.full_hash(code["numeric_environment"]) != env_sha:
        raise ValueError("numeric_environment_sha256 does not match the numeric environment it describes")
    return {"level": EXECUTABLE_LEVEL, "schema": EXECUTABLE_SCHEMA, "binding": _sha("binding", binding),
            "engine_sha256": _sha("engine_sha256", code.get("engine_sha256")),
            "numeric_environment_sha256": env_sha}


def lineage(view, i: int, *, code: dict, policy, fence: int, stages=(1, 2, 3, 4)) -> dict:
    """Every identity level of one HTE evaluation, scientific first: family > hypothesis > variant > candidate >
    binding (all code-free), then the executable with the engine and environment it adds. PR #86's identity has no
    field for the binding; HTE keeps this mapping (it is a pure function of the frozen registry and the run)."""
    from . import ids
    d = view.describe(int(i))
    binding = evaluation_binding_hash(view, i, policy=policy, fence=fence, stages=stages)
    exe = executable_spec(binding, code)
    return {"family": d["family_hash"], "hypothesis": d["hypothesis_hash"],
            "variant": bytes(view.variant[int(i)]).hex(), "candidate": view.candidate_hash(int(i)),
            "binding": binding, "executable": ids.full_hash(exe), "engine_sha256": exe["engine_sha256"],
            "numeric_environment_sha256": exe["numeric_environment_sha256"]}


def to_pr86_identity(view, i: int, *, run_id: str, data_hash: str, code: dict, window: dict, policy, fence: int,
                     stages=(1, 2, 3, 4)) -> dict:
    """The PR #86 schema-2 attempt identity of one HTE evaluation. ``spec_hash`` and ``executable`` are the hash of
    ``executable_spec``: the binding (every evaluation-affecting parameter, S10 F7) plus the engine digest and the
    numerical environment (S11), so PR #86's key separates engines and environments as Manhattan executables do."""
    lin = lineage(view, i, code=code, policy=policy, fence=fence, stages=stages)
    out = {
        "executable": lin["executable"], "variant": lin["variant"], "hypothesis": lin["hypothesis"],
        "family": lin["family"], "batch": f"hte-{run_id}", "role": "exploration", "channel": "blind",
        "designated": False, "spec_hash": lin["executable"], "data_hash": data_hash, "window": dict(window),
        "code_version": {"commit": code.get("commit"), "engine_sha256": lin["engine_sha256"],
                         "numeric_environment_sha256": lin["numeric_environment_sha256"]},
    }
    for k in ("spec_hash", "data_hash"):
        if not _HEX64.match(out[k]):
            raise ValueError(f"{k} is not a 64-hex SHA-256")
    return out


def executable_accounting(completions, lineage_of: dict) -> dict:
    """Read-only counts of HTE completions at every identity level, so that executions are never mistaken for tests.

    ``completions``: PR #86 completion records (``{"type", "payload"}``, type ``evaluation``, ``rerun`` or
    ``nondeterminism``) of HTE executables; ``lineage_of``: executable hash -> ``lineage(...)``. A completion whose
    executable has no lineage is refused (it cannot be placed in a family).

    ``looks`` counts PR #86 keys (as ``Ledger.looks``); ``completions`` counts every record (reruns included).
    ``scientific`` counts distinct families, hypotheses, variants, candidates and bindings: engine and environment
    changes never move these. ``cross_executable`` lists every (binding, data, window) evaluated by more than one
    executable; ``divergent`` is true when their results differ (an engine or environment changed the answer),
    and such families are listed in ``hold_families`` with the families PR #86 marks nondeterministic. This counts;
    it never decides which unit is a statistical test (owner decision D-1)."""
    recs = list(completions)
    groups: dict = {}
    sci = {k: set() for k in ("family", "hypothesis", "variant", "candidate", "binding")}
    keys, exes, hold = set(), set(), set()
    for r in recs:
        if r.get("type") not in ("evaluation", "rerun", "nondeterminism"):
            raise ValueError(f"not a completion record: {r.get('type')!r}")
        p = r["payload"]
        lin = lineage_of.get(p["executable"])
        if lin is None or lin["executable"] != p["spec_hash"] or lin["family"] != p["family"]:
            raise ValueError("a completion's executable has no matching HTE lineage")
        for k in sci:
            sci[k].add(lin[k])
        keys.add((p["spec_hash"], p["data_hash"], p["window"]["id"]))
        exes.add(p["executable"])
        if r["type"] == "nondeterminism":
            hold.add(p["family"])
        g = groups.setdefault((lin["binding"], p["data_hash"], p["window"]["id"]),
                              {"family": lin["family"], "executables": set(), "engines": set(),
                               "environments": set(), "results": set()})
        g["executables"].add(p["executable"])
        g["engines"].add(lin["engine_sha256"])
        g["environments"].add(lin["numeric_environment_sha256"])
        g["results"].add(p["result_hash"])
    cross = []
    for (binding, data, win), g in sorted(groups.items()):
        if len(g["executables"]) > 1:
            divergent = len(g["results"]) > 1
            if divergent:
                hold.add(g["family"])
            cross.append({"binding": binding, "data_hash": data, "window": win, "family": g["family"],
                          "executables": len(g["executables"]), "engines": len(g["engines"]),
                          "environments": len(g["environments"]), "distinct_results": len(g["results"]),
                          "divergent": divergent})
    return {"completions": len(recs), "looks": len(keys), "executables": len(exes),
            "scientific": {k: len(v) for k, v in sci.items()}, "cross_executable": cross,
            "hold_families": sorted(hold), "independent_statistical_tests": None,
            "independent_statistical_tests_reason": "owner decision D-1 (PR #86): the counting unit is open"}


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
