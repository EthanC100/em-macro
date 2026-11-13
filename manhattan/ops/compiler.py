"""Spec to executable: compile a hypothesis's variants into engine strategies (criteria O-26 to O-29).

A hypothesis that can be compiled carries, besides the registry's required fields (``manhattan.spec``):

    signal      {"kind": <one of KINDS>, ...fixed parameters}; the grid's points supply the varied ones
    frequency   "D", "W", "M" or "event": the family's natural frequency, which is the rebalance rule
    timing      calendar, horizon, execution lag, data cutoff (``manhattan.ops.timing``)
    primary_binding  {universe_id, cost_model_id, sizing_id}, each from the registries below

The family's predicted sign multiplies every weight. Kinds are generic building blocks (momentum, reversal, carry,
a calendar window, events, holding), not hypotheses: the hypothesis is the mechanism the family states. Every
parameter is checked against the kind's schema, and unknown kinds, universes, cost models or sizing rules are
refused. Compilation is a pure function of the spec and the code version: the same spec gives the same executable
hash and the same strategy.

Interfaces stream (``iter_executables``) so that counting and compiling never need every executable in memory at
once. Nothing here is optimised beyond the first cycle.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterator

import numpy as np

from manhattan import spec as S
from manhattan.engine import events as EV
from manhattan.engine.backtest import Instrument, Strategy, View

FREQUENCIES = {"D": "D", "W": "W", "M": "M", "event": "D"}
# the outcome horizon of one prediction, in sessions, implied by the frequency (a hypothesis may declare a longer one)
NATURAL_HORIZON = {"D": 1, "W": 5, "M": 21, "event": 1}


class CompileError(ValueError):
    pass


# ---------------------------------------------------------------- registries

@dataclass(frozen=True)
class Universe:
    id: str
    domain: str
    calendar: str
    instruments: tuple                 # (name, price series)
    carry: dict                        # instrument -> carry series (annual, decimal)
    events: dict                       # instrument -> event series
    sources: tuple                     # source ids (manhattan.ops.data.SOURCES) the universe is built from


SYN = tuple("ABCDEF")
UNIVERSES = {
    # synthetic data: tests, the end-to-end proof and the capacity harness. Never a market.
    "U_SYN6": Universe("U_SYN6", "syn_daily", "synthetic", tuple((f"SYN_{c}", f"syn_px_{c}") for c in SYN),
                       {f"SYN_{c}": f"syn_carry_{c}" for c in SYN}, {f"SYN_{c}": f"syn_evt_{c}" for c in SYN},
                       ("synthetic",)),
    # public data: three EM currencies against the dollar from the Federal Reserve's H.10 release (FRED), spot only
    "U_FX_H10": Universe("U_FX_H10", "fx_daily", "us_fed_fx",
                         (("BRL", "fx_BRL"), ("MXN", "fx_MXN"), ("ZAR", "fx_ZAR")), {}, {},
                         ("fred_DEXBZUS", "fred_DEXMXUS", "fred_DEXSFUS")),
}
COST_MODELS = {"C0": 0.0, "C2BP": 0.0002, "C5BP": 0.0005, "C10BP": 0.0010}
SIZING = {"EW": None, "VT10": 0.10}


def _int(lo, hi):
    return ("int", lo, hi)


def _num(lo, hi):
    return ("num", lo, hi)


KINDS = {
    "tsmom": {"lookback": _int(5, 504)},
    "xs_momentum": {"lookback": _int(5, 504), "n_long": _int(1, 3)},
    "reversal": {"lookback": _int(1, 60)},
    "carry": {"threshold": _num(0, 0.5)},
    "calendar": {"start_day": _int(1, 31), "end_day": _int(1, 31)},
    "event": {"hold": _int(1, 60)},
    "buy_hold": {"scale": _num(0.1, 1.0)},
}
KIND_NEEDS = {"carry": "carry", "event": "events"}


def _check_param(kind: str, name: str, value) -> None:
    sch = KINDS[kind].get(name)
    if sch is None:
        raise CompileError(f"signal kind {kind} has no parameter {name}")
    t, lo, hi = sch
    if isinstance(value, bool):
        raise CompileError(f"{kind}.{name} must be a number")
    if t == "int" and (not isinstance(value, int) or not lo <= value <= hi):
        raise CompileError(f"{kind}.{name} must be a whole number from {lo} to {hi}")
    if t == "num":
        try:
            v = float(value)
        except (TypeError, ValueError):
            raise CompileError(f"{kind}.{name} must be a number") from None
        if not (math.isfinite(v) and lo <= v <= hi):
            raise CompileError(f"{kind}.{name} must be from {lo} to {hi}")


def params_of(hypothesis: dict, point: dict) -> tuple[str, dict]:
    """(kind, full parameter set) of a hypothesis at a grid point, checked against the kind's schema."""
    sig = hypothesis.get("signal")
    if not isinstance(sig, dict) or sig.get("kind") not in KINDS:
        raise CompileError(f"signal must be a mapping with a kind from {sorted(KINDS)}")
    kind = sig["kind"]
    fixed = {k: v for k, v in sig.items() if k not in ("kind", "description")}
    overlap = set(fixed) & set(point)
    if overlap:
        raise CompileError(f"parameters both fixed and varied: {sorted(overlap)}")
    params = {**fixed, **point}
    for k, v in params.items():
        _check_param(kind, k, v)
    missing = set(KINDS[kind]) - set(params)
    if missing:
        raise CompileError(f"signal kind {kind} needs {sorted(missing)}")
    if kind == "calendar" and params["start_day"] > params["end_day"]:
        raise CompileError("calendar.start_day must not be after end_day")
    return kind, params


# ---------------------------------------------------------------- signals

def _momentum_scores(view: View, universe: Universe, lookback: int) -> dict:
    out = {}
    for name, series in universe.instruments:
        _, v = view.get(series, lookback + 1)
        out[name] = float(v[-1] / v[0] - 1.0) if v.size == lookback + 1 and v[0] > 0 else 0.0
    return out


def _normalise(scores: dict, sign: float) -> dict:
    gross = sum(abs(x) for x in scores.values())
    if gross == 0:
        return {k: 0.0 for k in scores}
    return {k: sign * x / gross for k, x in scores.items()}


def make_signal(kind: str, params: dict, universe: Universe, sign: float):
    """The engine signal for a kind: a function of a ``View`` only (it sees nothing but what was known)."""
    names = [n for n, _ in universe.instruments]
    if kind == "tsmom":
        L = params["lookback"]
        return lambda view: _normalise({k: float(np.sign(x)) for k, x in _momentum_scores(view, universe, L).items()}, sign)
    if kind == "reversal":
        L = params["lookback"]
        return lambda view: _normalise({k: -float(np.sign(x)) for k, x in _momentum_scores(view, universe, L).items()}, sign)
    if kind == "xs_momentum":
        L, n = params["lookback"], params["n_long"]

        def xs(view):
            s = _momentum_scores(view, universe, L)
            if all(x == 0.0 for x in s.values()):
                return {k: 0.0 for k in s}
            order = sorted(s, key=lambda k: (s[k], k))
            w = {k: 0.0 for k in s}
            for k in order[:n]:
                w[k] = -1.0
            for k in order[-n:]:
                w[k] = 1.0
            return _normalise(w, sign)
        return xs
    if kind == "carry":
        thr = float(params["threshold"])

        def carry(view):
            c = {k: view.last(universe.carry[k]) for k in names}
            if any(not math.isfinite(x) for x in c.values()):
                return {k: 0.0 for k in names}
            med = float(np.median(list(c.values())))
            return _normalise({k: (float(np.sign(x - med)) if abs(x - med) > thr else 0.0) for k, x in c.items()}, sign)
        return carry
    if kind == "calendar":
        a, b = params["start_day"], params["end_day"]

        def cal(view):
            dom = int(str(view.t)[8:10])
            on = 1.0 if a <= dom <= b else 0.0
            return {k: sign * on / len(names) for k in names}
        return cal
    if kind == "event":
        base = EV.event_signal(dict(universe.events), params["hold"])
        return lambda view: {k: sign * v / len(names) for k, v in base(view).items()}
    if kind == "buy_hold":
        sc = float(params["scale"])
        return lambda view: {k: sign * sc / len(names) for k in names}
    raise CompileError(f"unknown kind {kind}")                    # pragma: no cover - params_of refused it


def warmup_days(kind: str, params: dict, sizing_id: str) -> int:
    """Calendar days of history a forward window needs before its first observation."""
    look = int(params.get("lookback", 0)) + int(params.get("hold", 0))
    vol = 90 if SIZING.get(sizing_id) else 0
    return int((look + vol) * 7 / 5) + 30


# ---------------------------------------------------------------- executables

@dataclass(frozen=True)
class Executable:
    executable: dict
    variant: dict
    hypothesis: dict
    family: dict
    kind: str
    params: dict
    frequency: str
    universe: Universe
    cost: float
    vol_target: float | None
    warmup_days: int

    @property
    def id(self) -> str:
        return S.spec_id(self.executable)

    @property
    def spec_hash(self) -> str:
        return S.spec_hash(self.executable)

    def strategy(self, lag: int = 1) -> Strategy:
        sign = 1.0 if self.family["sign"] == "+" else -1.0
        ins = tuple(Instrument(n, p, cost=self.cost) for n, p in self.universe.instruments)
        sig = make_signal(self.kind, self.params, self.universe, sign)
        return Strategy(instruments=ins, signal=sig, rebalance=FREQUENCIES[self.frequency], lag=lag,
                        vol_target=self.vol_target, vol_halflife=60.0, vol_min_obs=60,
                        max_scale=4.0 if self.vol_target else None)


def check_hypothesis(h: dict) -> list[str]:
    """Problems that stop a hypothesis compiling (empty when it compiles)."""
    errs = []
    if h.get("frequency") not in FREQUENCIES:
        errs.append(f"frequency must be one of {sorted(FREQUENCIES)}")
    b = h.get("primary_binding") or {}
    u = UNIVERSES.get(b.get("universe_id"))
    if u is None:
        errs.append(f"universe_id must be one of {sorted(UNIVERSES)}")
    elif u.domain != h.get("domain"):
        errs.append(f"universe {u.id} is in domain {u.domain}, the hypothesis in {h.get('domain')}")
    if b.get("cost_model_id") not in COST_MODELS:
        errs.append(f"cost_model_id must be one of {sorted(COST_MODELS)}")
    if b.get("sizing_id") not in SIZING:
        errs.append(f"sizing_id must be one of {sorted(SIZING)}")
    sig = h.get("signal")
    kind = sig.get("kind") if isinstance(sig, dict) else None
    if kind not in KINDS:
        errs.append(f"signal must be a mapping with a kind from {sorted(KINDS)}")
    elif u is not None and KIND_NEEDS.get(kind) and not getattr(u, KIND_NEEDS[kind]):
        errs.append(f"signal kind {kind} needs {KIND_NEEDS[kind]} series, which universe {u.id} does not have")
    if (h.get("frequency") == "event") != (kind == "event"):
        errs.append("an event signal has frequency 'event', and only an event signal does")
    if not errs:
        try:
            for p in S.enumerate_grid(h["grid"]):
                params_of(h, p)
        except (CompileError, S.SpecError) as e:
            errs.append(str(e))
    return errs


def variant_count(h: dict) -> int:
    """How many variants a grid has, without enumerating it."""
    return math.prod(len(v) for v in h["grid"].values())


def iter_executables(family: dict, hypothesis: dict, code_version: str) -> Iterator[Executable]:
    """The primary executable of every variant of a hypothesis, in the grid's order, one at a time."""
    errs = check_hypothesis(hypothesis)
    if errs:
        raise CompileError("; ".join(errs))
    if hypothesis["family"] != S.spec_hash(family):
        raise CompileError("the hypothesis does not belong to this family")
    b = hypothesis["primary_binding"]
    u = UNIVERSES[b["universe_id"]]
    for v in S.variants(hypothesis):
        kind, params = params_of(hypothesis, v["point"])
        x = S.primary_executable(hypothesis, v, code_version)
        yield Executable(x, v, hypothesis, family, kind, params, hypothesis["frequency"], u,
                         COST_MODELS[b["cost_model_id"]], SIZING[b["sizing_id"]],
                         warmup_days(kind, params, b["sizing_id"]))


def from_specs(executable: dict, variant: dict, hypothesis: dict, family: dict) -> Executable:
    """Rebuild a compiled executable from its four stored specs (what the runner does with a frozen batch)."""
    if executable["variant"] != S.spec_hash(variant) or variant["hypothesis"] != S.spec_hash(hypothesis) \
            or hypothesis["family"] != S.spec_hash(family):
        raise CompileError("the specs do not link: executable -> variant -> hypothesis -> family")
    errs = check_hypothesis(hypothesis)
    if errs:
        raise CompileError("; ".join(errs))
    kind, params = params_of(hypothesis, variant["point"])
    return Executable(executable, variant, hypothesis, family, kind, params, hypothesis["frequency"],
                      UNIVERSES[executable["universe_id"]], COST_MODELS[executable["cost_model_id"]],
                      SIZING[executable["sizing_id"]], warmup_days(kind, params, executable["sizing_id"]))


def iter_batch(families: list[dict], hypotheses: list[dict], code_version: str) -> Iterator[Executable]:
    by = {S.spec_hash(f): f for f in families}
    for h in hypotheses:
        yield from iter_executables(by[h["family"]], h, code_version)
