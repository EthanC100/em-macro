"""Economic relationship graph: who supplies, buys from, competes with or depends on whom, and since when it was known.

    g = RelationshipGraph()
    g.add(Relationship("C_FAB", "C_EQUIP", "customer_of", valid_from=..., public_from=..., recorded_from=...,
                       provenance="10-K customer concentration note", confidence=0.8))
    g.edges(as_of=date(2012, 3, 30))

**Three dates per edge.** ``valid_from``/``valid_to``: when the economic relationship existed. ``public_from``: the
first day it was publicly disclosed (a filing, a press release). ``recorded_from``: the first day it was in *our*
data. An edge is usable for research at ``t`` only if ``valid_from ≤ t ≤ valid_to``, ``public_from ≤ t`` and
``recorded_from ≤ t``. A supplier link discovered by a researcher in 2020 and back-dated to 2012 has
``recorded_from = 2020``: it is not usable in 2012 however true it was. ``edges(..., retrospective=True)`` shows the
back-dated view for description only and marks the result ``retrospective``.

**Confidence** is the source's own reliability in ``[0, 1]`` (``uncertainty`` describes how it was derived). It is
metadata, not an estimate of predictive value.

**Propagation** (``propagate``) is the lagged, confidence-weighted average of a feature over a node's neighbours
along chosen relationship types. It describes a hypothesis's input ("customers' revenue surprise reaches suppliers
with a delay"); it estimates no causal effect.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .errors import EquityDataError, TemporalError

RELATIONSHIP_TYPES = ("supplier_of", "customer_of", "competitor_of", "partner_of", "infrastructure_for",
                      "licensor_of", "subsidiary_of", "complement_of")
SYMMETRIC = frozenset({"competitor_of", "partner_of", "complement_of"})


@dataclass(frozen=True)
class Relationship:
    source: str
    destination: str
    rel_type: str
    valid_from: date
    public_from: date
    recorded_from: date
    provenance: str
    confidence: float
    valid_to: date | None = None
    uncertainty: str = ""

    def __post_init__(self):
        if self.rel_type not in RELATIONSHIP_TYPES:
            raise EquityDataError(f"unknown relationship type {self.rel_type!r}")
        if self.source == self.destination:
            raise EquityDataError(f"{self.source}: a relationship with itself")
        if not self.provenance:
            raise EquityDataError(f"{self.source}->{self.destination}: provenance is required")
        if not 0.0 <= self.confidence <= 1.0:
            raise EquityDataError("confidence is in [0, 1]")
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise TemporalError(f"{self.source}->{self.destination}: valid_to before valid_from")
        if self.recorded_from < self.public_from:
            raise TemporalError(f"{self.source}->{self.destination}: recorded before it was public")

    @property
    def backdated(self) -> bool:
        """Recorded after the relationship started: usable only from ``recorded_from``."""
        return self.recorded_from > self.valid_from

    def usable(self, t: date) -> bool:
        return self.valid_from <= t and (self.valid_to is None or t <= self.valid_to) \
            and self.public_from <= t and self.recorded_from <= t


@dataclass(frozen=True)
class EdgeView:
    edges: tuple
    as_of: date
    retrospective: bool


class RelationshipGraph:
    def __init__(self, edges=()):
        self._edges: list[Relationship] = []
        for e in edges:
            self.add(e)

    def add(self, e: Relationship) -> None:
        for o in self._edges:
            if (o.source, o.destination, o.rel_type, o.valid_from) == (e.source, e.destination, e.rel_type,
                                                                       e.valid_from) and o != e:
                raise EquityDataError(f"{e.source}->{e.destination} {e.rel_type}: two records for one relationship")
        self._edges.append(e)

    def edges(self, as_of: date, *, types=None, retrospective: bool = False) -> EdgeView:
        """Edges usable at ``as_of``; with ``retrospective=True`` also edges recorded later (description only)."""
        out = []
        for e in self._edges:
            if types is not None and e.rel_type not in types:
                continue
            ok = e.usable(as_of) if not retrospective else (
                e.valid_from <= as_of and (e.valid_to is None or as_of <= e.valid_to))
            if ok:
                out.append(e)
        return EdgeView(tuple(sorted(out, key=lambda e: (e.source, e.destination, e.rel_type))), as_of, retrospective)

    def neighbours(self, node: str, as_of: date, *, types=None, direction: str = "in") -> list[tuple[str, float]]:
        """(neighbour, confidence) pairs: ``in`` = sources pointing at ``node``; ``out`` = destinations of ``node``.
        Symmetric types count both ways."""
        if direction not in ("in", "out"):
            raise ValueError("direction is 'in' or 'out'")
        out = []
        for e in self.edges(as_of, types=types).edges:
            if direction == "in" and e.destination == node:
                out.append((e.source, e.confidence))
            elif direction == "out" and e.source == node:
                out.append((e.destination, e.confidence))
            if e.rel_type in SYMMETRIC:
                if direction == "in" and e.source == node:
                    out.append((e.destination, e.confidence))
                elif direction == "out" and e.destination == node:
                    out.append((e.source, e.confidence))
        return out

    def propagate(self, feature_at, nodes, as_of: date, *, lag_sessions: int, calendar, types=None,
                  direction: str = "in", min_neighbours: int = 1) -> dict:
        """For each node, the confidence-weighted mean of ``feature_at(neighbour, d)`` over its neighbours at
        ``as_of``, where ``d`` is ``lag_sessions`` sessions before ``as_of``. ``feature_at`` must itself be point in
        time (return what was known at the close of ``d``). Nodes with fewer than ``min_neighbours`` neighbours
        with a value get None."""
        if lag_sessions < 0:
            raise TemporalError("a propagation lag cannot be negative")
        d = calendar.offset(as_of, -lag_sessions) if lag_sessions else as_of
        out = {}
        for n in nodes:
            num = den = 0.0
            k = 0
            for nb, w in self.neighbours(n, as_of, types=types, direction=direction):
                v = feature_at(nb, d)
                if v is None:
                    continue
                num, den, k = num + w * v, den + w, k + 1
            out[n] = (num / den) if k >= min_neighbours and den > 0 else None
        return out
