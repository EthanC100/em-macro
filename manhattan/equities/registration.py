"""Hypothesis first: the gate between a draft catalogue family and an executable equity experiment. **Dormant.**

    spec = experiment_spec(entry, programme="non_technology_equities", ...)      # anyone may draft one
    exp = admit(entry, spec, batch_dir=..., batch_number=..., manifest_hash=...) # only a verified freeze admits it
    lock = run_selection(world, exp, cost_model)                                 # the declared grid, in-sample only
    verdict = run_holdout(world, exp, lock, cost_model)                          # once, the locked variant only

**A catalogue family is not an experiment.** ``catalogue_nontech.yaml`` (and ``catalogue.yaml``) hold *draft*
families: a mechanism, a sign and a counterparty, untested and unregistered. Nothing turns a draft into something
that runs. The only path to a run is ``admit``, and it requires a **pre-registered, immutable experiment
specification**: a Manhattan hypothesis spec (``manhattan.spec``) whose family is exactly the catalogue's draft
family (``catalogue.family_draft``). Both hashes must be listed in a batch manifest that ``manhattan.freeze.
verify_frozen`` accepts, which means:

- the manifest and every spec in it still match their hashes and the Merkle root;
- the manifest has an external timestamp proof;
- the commit carries a **signed** tag.

A freeze is a pre-registration and is Ethan's alone (CLAUDE.md hard rule 4; ``freeze.authorise``). This module
prepares nothing for freezing and freezes nothing.

**The specification** (``experiment_spec``; ``REQUIRED`` lists every field) states:

- the economic mechanism and the predicted direction, which must equal the family's;
- the track and its point-in-time universe (the track's eligibility-rules hash), and the data kinds, which must be
  within the family's;
- the signal construction and the parameter grid (every variant, declared and finite);
- the benchmark, the full transaction-cost model with its reference, and the execution lag (at least 1);
- the testing windows: selection up to ``selection_end``, then an untouched holdout ``[holdout_start, holdout_end]``;
- machine-checkable rejection criteria;
- the attempt-accounting identity: batch, role, channel and designation. Each variant's PR #86-shaped identity
  derives from the frozen family, hypothesis, variant and primary-executable specs.

**Fail closed.** ``admit`` raises on a missing or unverifiable freeze, on a spec or family whose hash is not in the
manifest (any edit after registration changes the hash), and on an incomplete or inconsistent spec. An admitted
``ExperimentHandle`` keeps a canonical copy of the spec and its hash. ``run_*`` re-checks both, and refuses objects
this module did not issue and objects changed since.

**The holdout is untouched until the selection is locked.**

- ``run_selection`` reads nothing after ``selection_end``. It runs every declared variant, never another, chooses by
  the declared rule and returns a lock that names the chosen variant.
- ``run_holdout`` runs only that variant, only on the holdout, and only once per registration.
- The rejection criteria are evaluated there and nowhere else.

**Dormant.** ``EXECUTION_ON_REAL_DATA`` is a constant ``False``. An admitted experiment runs only on a synthetic
world (``synthetic.is_synthetic``), so this gate can be tested end to end and executes nothing on market data.
Results carry ``evidential_weight: 0``. Counting across tracks (``count_registered``) reports per track and
combined and decides no denominator (owner decisions NT-8 and D-1).
"""
from __future__ import annotations

import json
import weakref
from dataclasses import dataclass
from datetime import date

from manhattan import freeze as FZ
from manhattan import spec as S

from . import catalogue as C
from .costs import EquityCostModel
from .errors import EquityDataError
from .sectors import EQUITY_TRACKS

EXECUTION_ON_REAL_DATA = False          # a constant: no registered experiment runs on market data from this module
SCHEMA = "manhattan.equities.experiment/1"
REQUIRED = ("schema", "track", "catalogue_id", "mechanism", "mechanism_class", "predicted_sign", "data_sources",
            "universe", "signal", "grid", "benchmark", "costs", "execution", "windows", "selection_rule",
            "rejection_criteria", "attempt_accounting", "primary_binding", "domain")
SIGNAL_FUNCTIONS = ("trailing_total_return/1",)
BENCHMARKS = ("equal_weight_track_universe/1",)
SELECTION_RULES = ("max_in_sample_net_sharpe/1",)
CRITERION_METRICS = ("excess_sharpe", "excess_ann_return", "max_drawdown")
CRITERION_OPS = ("<", "<=", ">", ">=")
COST_FIELDS = ("half_spread", "commission", "impact", "short_financing", "long_financing", "recall_cost", "reference")


class RegistrationError(EquityDataError):
    """No admissible pre-registration: the experiment may not run."""


def _canon(x):
    return json.loads(S.canonical_bytes({"v": x}))["v"]


def cost_spec(cost_model: EquityCostModel) -> dict:
    return {k: getattr(cost_model, k) for k in COST_FIELDS}


def experiment_spec(entry: dict, *, programme: str, construction: str, lookbacks: list, skip: int,
                    top_fraction: float, cost_model: EquityCostModel, lag: int, selection_end: date,
                    holdout_start: date, holdout_end: date, rejection_criteria: list, batch: str,
                    data_sources: list | None = None) -> dict:
    """A draft experiment specification for one catalogue family. **Drafting is not registering**: the result is
    inert until it, and the family, are frozen in a batch that ``freeze.verify_frozen`` accepts. Raises on a
    malformed draft."""
    from .universe import track_rules
    if programme not in EQUITY_TRACKS:
        raise RegistrationError(f"{programme!r} is not an equity research track")
    family = C.family_draft(entry, programme=programme)
    kinds = list(data_sources if data_sources is not None else entry["required_data"])
    costs = cost_spec(cost_model)
    hyp = S.hypothesis(
        family, schema=SCHEMA, track=programme, catalogue_id=entry["id"],
        mechanism=" ".join(str(entry["rationale"]).split()), mechanism_class=entry["mechanism_class"],
        predicted_sign=entry["sign"], domain=f"equities:{programme}",
        data_sources=[{"name": k, "publication_lag_days": 1} for k in kinds],
        universe={"rules_hash": track_rules(programme).hash(), "track": programme, "point_in_time": True},
        signal={"function": SIGNAL_FUNCTIONS[0], "construction": construction, "skip": skip,
                "top_fraction": top_fraction},
        grid={"lookback": list(lookbacks)}, benchmark=BENCHMARKS[0], costs=costs, execution={"lag": lag},
        windows={"selection_end": selection_end, "holdout_start": holdout_start, "holdout_end": holdout_end},
        selection_rule=SELECTION_RULES[0], rejection_criteria=list(rejection_criteria),
        attempt_accounting={"batch": batch, "role": "exploration", "channel": "blind", "designated": False,
                            "store": "ledger", "track": programme},
        primary_binding={"universe_id": f"EU-{track_rules(programme).hash()[:16]}",
                         "cost_model_id": f"EC-{S.spec_hash(costs)[:16]}",
                         "sizing_id": f"equal_weight_top_fraction/1:{top_fraction}"})
    errs = validate_spec(entry, hyp, programme=programme)
    if errs:
        raise RegistrationError("; ".join(errs))
    return hyp


def validate_spec(entry: dict, hyp: dict, *, programme: str) -> list[str]:
    """Completeness and consistency of an experiment spec with its catalogue family. Never a statistical decision."""
    from .universe import track_rules
    errs = S.validate_hypothesis(hyp)
    h = _canon(hyp)
    for k in REQUIRED:
        if h.get(k) in (None, "", [], {}):
            errs.append(f"experiment spec: '{k}' is required")
    if errs:
        return errs
    family = C.family_draft(entry, programme=programme)
    if h["schema"] != SCHEMA:
        errs.append("experiment spec: unknown schema")
    if h["family"] != S.spec_hash(family):
        errs.append("experiment spec: its family is not this catalogue family as drafted")
    if h["track"] != programme or h["attempt_accounting"].get("track") != programme \
            or h["universe"].get("track") != programme or h["domain"] != f"equities:{programme}":
        errs.append("experiment spec: one track, named consistently (a combined portfolio is not a track)")
    if h["catalogue_id"] != entry["id"]:
        errs.append("experiment spec: catalogue_id differs from the family's")
    if h["predicted_sign"] != entry["sign"] or h["mechanism_class"] != entry["mechanism_class"]:
        errs.append("experiment spec: predicted direction and mechanism class must equal the family's")
    allowed = set(entry.get("required_data") or []) | set(entry.get("optional_data") or [])
    extra = sorted({d.get("name") for d in h["data_sources"]} - allowed)
    if extra:
        errs.append(f"experiment spec: data kinds {extra} are not in the family's declared data")
    if h["universe"].get("rules_hash") != track_rules(programme).hash() or h["universe"].get("point_in_time") is not True:
        errs.append("experiment spec: the universe must be the track's point-in-time universe")
    sig = h["signal"]
    if sig.get("function") not in SIGNAL_FUNCTIONS or not str(sig.get("construction", "")).strip():
        errs.append("experiment spec: signal function and construction are required")
    if set(h["grid"]) != {"lookback"} or any(not isinstance(x, int) or x <= int(sig.get("skip", 0))
                                             for x in h["grid"]["lookback"]):
        errs.append("experiment spec: the grid declares integer lookbacks longer than skip")
    if h["benchmark"] not in BENCHMARKS:
        errs.append(f"experiment spec: benchmark must be one of {BENCHMARKS}")
    if set(h["costs"]) != set(COST_FIELDS) or not str(h["costs"].get("reference", "")).strip():
        errs.append("experiment spec: the full cost model and its reference are required")
    lag = h["execution"].get("lag")
    if not isinstance(lag, int) or isinstance(lag, bool) or lag < 1:
        errs.append("experiment spec: execution lag of at least one session is required")
    try:
        w = {k: date.fromisoformat(h["windows"][k]) for k in ("selection_end", "holdout_start", "holdout_end")}
        if not w["selection_end"] < w["holdout_start"] <= w["holdout_end"]:
            errs.append("experiment spec: windows must be selection_end < holdout_start <= holdout_end")
    except (KeyError, TypeError, ValueError):
        errs.append("experiment spec: windows need selection_end, holdout_start and holdout_end dates")
    if h["selection_rule"] not in SELECTION_RULES:
        errs.append(f"experiment spec: selection rule must be one of {SELECTION_RULES}")
    crit = h["rejection_criteria"]
    if not isinstance(crit, list) or not crit or any(
            not isinstance(c, dict) or set(c) != {"metric", "op", "value"} or c["metric"] not in CRITERION_METRICS
            or c["op"] not in CRITERION_OPS for c in crit):
        errs.append("experiment spec: rejection criteria are a non-empty list of {metric, op, value}")
    aa = h["attempt_accounting"]
    if (aa.get("role"), aa.get("channel"), aa.get("designated"), aa.get("store")) != \
            ("exploration", "blind", False, "ledger") or not str(aa.get("batch", "")).startswith("AB-"):
        errs.append("experiment spec: attempt accounting is an exploration, blind, undesignated ledger attempt of "
                    "a named batch")
    return errs


# ---------------------------------------------------------------------------------------------------- the gate

_ISSUED: dict = {}
_HOLDOUT_READ: set = set()


@dataclass(frozen=True)
class ExperimentHandle:
    spec_hash: str
    family_hash: str
    canonical: bytes            # the registered spec, canonical bytes (the caller's dict is not kept)
    track: str
    catalogue_id: str
    batch: str
    manifest_hash: str
    executables: tuple          # (variant point, variant hash, executable hash) of every declared variant

    @property
    def spec(self) -> dict:
        return json.loads(self.canonical)


def _issue(obj):
    _ISSUED[id(obj)] = (weakref.ref(obj), repr(obj))
    return obj


def issued(obj) -> bool:
    e = _ISSUED.get(id(obj))
    return e is not None and e[0]() is obj and e[1] == repr(obj)


def admit(entry: dict, hyp: dict, *, programme: str, batch_dir, batch_number: int, manifest_hash: str,
          code_version: str, tag_is_signed=FZ.git_tag_is_signed) -> ExperimentHandle:
    """The only way to an executable experiment. ``batch_dir``/``batch_number``/``manifest_hash``: the frozen batch
    holding the family and this spec. ``code_version``: the engine identity its primary executables were frozen with.
    ``tag_is_signed`` defaults to ``git verify-tag``, and tests substitute it exactly as ``verify_frozen`` allows.
    Raises ``RegistrationError`` unless everything holds."""
    try:
        manifest = FZ.verify_frozen(batch_dir, batch_number, expected_manifest_hash=manifest_hash,
                                    tag_is_signed=tag_is_signed)
    except (FZ.FreezeError, OSError, KeyError, ValueError) as exc:
        raise RegistrationError(f"no verified freeze: {exc}") from None
    family = C.family_draft(entry, programme=programme)
    frozen = set(manifest.get("spec_hashes", ()))
    sh, fh = S.spec_hash(hyp), S.spec_hash(family)
    if fh not in frozen:
        raise RegistrationError("the catalogue family, as drafted now, is not in the frozen batch (it changed, or it "
                                "was never registered)")
    if sh not in frozen:
        raise RegistrationError("this experiment spec is not in the frozen batch (it was modified after registration, "
                                "or never registered)")
    errs = validate_spec(entry, hyp, programme=programme)       # a frozen spec must still be complete and consistent
    if errs:
        raise RegistrationError("; ".join(errs))
    h = _canon(hyp)
    if h["attempt_accounting"]["batch"] != f"AB-{batch_number:04d}" or manifest.get("batch") != batch_number:
        raise RegistrationError("the spec's attempt-accounting batch is not the batch that froze it")
    if manifest.get("channel") != "blind":
        raise RegistrationError("only a blind batch can register an experiment")
    exes = []
    for v in S.variants(hyp):
        x = S.primary_executable(hyp, v, code_version)
        if S.spec_hash(v) not in frozen or S.spec_hash(x) not in frozen:
            raise RegistrationError("a declared variant or its primary executable is not in the frozen batch (the "
                                    "grid or the engine identity changed)")
        exes.append((v["point"]["lookback"], S.spec_hash(v), S.spec_hash(x)))
    return _issue(ExperimentHandle(sh, fh, S.canonical_bytes(hyp), programme, entry["id"],
                                   f"AB-{batch_number:04d}", manifest_hash, tuple(exes)))


def attempt_identity(exp: ExperimentHandle, lookback: int, *, data_hash: str, window: dict,
                     code_version: dict) -> dict:
    """The PR #86 schema-2 attempt identity of one variant of an admitted experiment (``ledger.IDENTITY_FIELDS``)."""
    _require(exp)
    match = [e for e in exp.executables if e[0] == lookback]
    if not match:
        raise RegistrationError(f"lookback {lookback} is not a declared variant")
    _, vh, xh = match[0]
    h = exp.spec
    return {"executable": f"AX-{xh[:16]}", "variant": f"AV-{vh[:16]}", "hypothesis": f"AH-{exp.spec_hash[:16]}",
            "family": f"AF-{exp.family_hash[:16]}", "batch": exp.batch, "role": "exploration", "channel": "blind",
            "designated": False, "spec_hash": xh, "data_hash": data_hash, "window": dict(window),
            "code_version": dict(code_version), "track": h["track"]}


def _require(exp) -> dict:
    if type(exp) is not ExperimentHandle or not issued(exp):
        raise RegistrationError("not an admitted experiment (only admit issues one; copies and edits are refused)")
    if S.spec_hash(json.loads(exp.canonical)) != exp.spec_hash:     # defence in depth: an edit also breaks issue
        raise RegistrationError("the admitted specification changed after admission")
    return exp.spec


def _require_costs(h: dict, cost_model: EquityCostModel) -> None:
    if _canon(cost_spec(cost_model)) != h["costs"]:
        raise RegistrationError("the cost model differs from the registered one")


def _config(h: dict):
    from .track_compare import CompareConfig
    sig = h["signal"]
    return CompareConfig(is_end=date.fromisoformat(h["windows"]["selection_end"]),
                         lookbacks=tuple(h["grid"]["lookback"]), skip=int(sig["skip"]),
                         lag=int(h["execution"]["lag"]), top_fraction=float(sig["top_fraction"]),
                         warmup=max(260, max(h["grid"]["lookback"]) + 1))


@dataclass(frozen=True)
class SelectionLock:
    spec_hash: str
    chosen_lookback: int
    variants_tried: int
    in_sample: str               # canonical JSON of every variant's in-sample metrics


def run_selection(world, exp: ExperimentHandle, cost_model: EquityCostModel) -> SelectionLock:
    """Every declared variant over data up to ``selection_end`` (nothing later is read), chosen by the declared rule.
    Synthetic worlds only."""
    from .synthetic import is_synthetic
    from .track_compare import _split, run_sleeve
    h = _require(exp)
    _require_costs(h, cost_model)
    if not is_synthetic(world) or EXECUTION_ON_REAL_DATA:
        raise RegistrationError("dormant: an admitted experiment runs only on a synthetic world")
    cfg = _config(h)
    rows = {}
    for lb in cfg.lookbacks:
        sl = run_sleeve(world, cfg, cost_model, {exp.track: lb}, name=f"{exp.catalogue_id}:{lb}",
                        end=cfg.is_end)
        rows[lb] = _split(sl, cfg.is_end)[0]
    best = max(cfg.lookbacks, key=lambda lb: (rows[lb].get("sharpe", float("-inf")), -lb))
    return _issue(SelectionLock(exp.spec_hash, best, len(rows), json.dumps(rows, sort_keys=True)))


def run_holdout(world, exp: ExperimentHandle, lock: SelectionLock, cost_model: EquityCostModel) -> dict:
    """The locked variant on the holdout, once per registration; the rejection criteria are evaluated here only."""
    from .synthetic import is_synthetic
    from .track_compare import LABEL, metrics, replace, run_sleeve
    h = _require(exp)
    _require_costs(h, cost_model)
    if type(lock) is not SelectionLock or not issued(lock) or lock.spec_hash != exp.spec_hash:
        raise RegistrationError("no selection lock issued for this experiment: the holdout stays untouched")
    if not is_synthetic(world) or EXECUTION_ON_REAL_DATA:
        raise RegistrationError("dormant: an admitted experiment runs only on a synthetic world")
    if exp.spec_hash in _HOLDOUT_READ:
        raise RegistrationError("the holdout of this registration was already read: one look only")
    _HOLDOUT_READ.add(exp.spec_hash)
    cfg = _config(h)
    hs, he = (date.fromisoformat(h["windows"][k]) for k in ("holdout_start", "holdout_end"))
    sl = run_sleeve(world, cfg, cost_model, {exp.track: lock.chosen_lookback}, name="holdout", end=he)
    bench = run_sleeve(world, replace(cfg, top_fraction=1.0), cost_model, {exp.track: lock.chosen_lookback},
                       name="holdout-benchmark", end=he)
    keep = [i for i, d in enumerate(sl.days) if hs <= d <= he]
    net, bnet = sl.net[keep], bench.net[keep]
    m, ex = metrics(net), metrics(net - bnet)
    values = {"excess_sharpe": ex.get("sharpe"), "excess_ann_return": ex.get("ann_return"),
              "max_drawdown": m.get("max_drawdown")}
    ops = {"<": lambda a, b: a < b, "<=": lambda a, b: a <= b, ">": lambda a, b: a > b, ">=": lambda a, b: a >= b}
    hits = [c for c in h["rejection_criteria"] if values[c["metric"]] is not None
            and ops[c["op"]](values[c["metric"]], float(c["value"]))]
    return {**LABEL, "spec_hash": exp.spec_hash, "batch": exp.batch, "track": exp.track,
            "catalogue_id": exp.catalogue_id, "chosen_lookback": lock.chosen_lookback,
            "holdout": {"start": hs.isoformat(), "end": he.isoformat(), "days": len(keep)},
            "metrics": m, "excess_over_benchmark": ex, "rejected": bool(hits), "criteria_met": hits}


def count_registered(handles, *, nontech_catalogue: dict | None = None) -> dict:
    """Admitted experiments per track and combined. Never counts one registration twice, and never in two tracks.
    Links between tracks (``cross_track`` in the non-technology catalogue) are reported as dependent groups. Which
    count is the multiple-testing denominator is not decided here (NT-8, D-1)."""
    seen, by_track, refused, same_content = set(), {t: 0 for t in EQUITY_TRACKS}, [], []
    content: dict = {}
    for x in handles:
        _require(x)
        if x.spec_hash in seen:
            refused.append({"spec_hash": x.spec_hash, "reason": "duplicate registration counted once"})
            continue
        seen.add(x.spec_hash)
        h = x.spec
        # the same experiment content under another catalogue id or track is not a second, independent test
        key = S.spec_hash({k: v for k, v in h.items() if k not in ("family", "track", "catalogue_id", "domain",
                                                                   "attempt_accounting", "universe",
                                                                   "primary_binding", "mechanism",
                                                                   "mechanism_class", "predicted_sign",
                                                                   "data_sources")})
        if key in content and content[key][1] == x.track:
            refused.append({"spec_hash": x.spec_hash, "reason": f"same experiment as {content[key][0][:16]} in the "
                                                                "same track under another family"})
            continue
        if key in content:                          # the same experiment in the other track: dependent, not new
            same_content.append({"families": [content[key][2], x.catalogue_id], "tracks": [content[key][1], x.track]})
        content.setdefault(key, (x.spec_hash, x.track, x.catalogue_id))
        by_track[x.track] += 1
    links = {}
    for f in (nontech_catalogue or {}).get("families", []):
        ct = f.get("cross_track") or {}
        if ct.get("technology_counterpart"):
            links[ct["mechanism"]] = (f["id"], ct["technology_counterpart"])
    admitted_ids = {x.catalogue_id for x in handles}
    dependent = [{"mechanism": m, "families": list(p)} for m, p in sorted(links.items())
                 if p[0] in admitted_ids and p[1] in admitted_ids]
    return {"by_track": by_track, "combined": sum(by_track.values()), "refused": refused,
            "dependent_cross_track_groups": dependent, "same_experiment_in_two_tracks": same_content,
            "independent_confirmations": 0,
            "denominator": None, "denominator_reason": "owner decisions NT-8 and D-1 are open"}
