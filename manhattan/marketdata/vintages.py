"""Vintages, revisions and point-in-time reads over stored datasets (DESIGN.md section 5).

``VintageSet`` combines datasets (snapshots, daily deliveries) into one first-seen history per series, where a
series is ``<source>:<instrument>:<contract>:<field>`` (sources are never merged: a Norgate settlement and a
Databento settlement of the same contract are two series).

* Datasets are applied in order of retrieval time. A key's first value takes its availability from
  ``manhattan.marketdata.timing.availability``, with monitoring counted per series (the first delivery holding any
  row of it): only history that predates the series' first capture is backfill. A later value that equals the latest one is a re-delivery and adds
  nothing. A different value is a **revision**: available from its own publication time (vendor_receipt) or from
  the first time this project saw it (declared_delay), never earlier than the delivery that carried it.
* ``as_of(series, t)`` answers at a **time**: the value of each session known at ``t``.
* ``pit_store()`` hands the same history to ``manhattan.engine.pit.PitStore`` with availability **days** from the
  research clock, so the engine reads it through ``Reader`` and ``manhattan.roles`` like every other input.

**Fence on load.** A dataset whose ingestion admitted reserve or forward rows was ingested by the runner; only
the runner may load it. A session loading it is refused (``FenceRefused``).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from manhattan import roles
from manhattan.engine.pit import PitStore, Reader

from .errors import FenceRefused, MarketDataError
from .provenance import SourceDescriptor
from .schema import Instrument, as_utc
from .store import DatasetStore
from .timing import ResearchClock, availability


def series_name(source_id: str, instrument_id: str, contract_id: str | None, field: str) -> str:
    return f"{source_id}:{instrument_id}:{contract_id or '-'}:{field}"


@dataclass(frozen=True)
class Version:
    value: float
    available_utc: datetime
    basis: str
    dataset_id: str


class VintageSet:
    def __init__(self, store: DatasetStore, dataset_ids, instruments: dict, sources: dict, clock: ResearchClock,
                 *, caller: str = "session"):
        """``sources``: source_id -> SourceDescriptor (as stored; checked against each manifest)."""
        self.clock, self.instruments = clock, instruments
        loaded = []
        for did in sorted(set(dataset_ids)):
            ds = store.load(did)
            m = ds["manifest"]
            admitted = set(m["fence"]["admitted"])
            if admitted - {roles.EXPLORATION} and caller != roles.RUNNER:
                raise FenceRefused(f"{did} holds {sorted(admitted - {roles.EXPLORATION})} rows: runner only")
            src: SourceDescriptor = sources.get(m["source"]["source_id"])
            if src is None or src.to_dict() != m["source"]:
                raise MarketDataError(f"{did}: source descriptor differs from the one supplied")
            if not src.availability_ready:
                raise MarketDataError(f"{did}: availability cannot be computed: " + "; ".join(src.provenance_gaps()))
            loaded.append((as_utc(m["retrieved_utc"], "retrieved_utc"), did, src, ds["observations"]))
        loaded.sort(key=lambda x: (x[0], x[1]))
        # monitoring starts per series: the retrieval time of the first delivery that held any row of it. A value
        # first delivered by a later snapshot for a series already monitored (a gap the vendor filled later) is
        # then judged against that earlier start, so it is late (available when seen), never backfilled.
        monitoring = {}
        for t, _, src, obs in loaded:
            for o in obs:
                monitoring.setdefault(series_name(src.source_id, o.instrument_id, o.contract_id, o.field), t)
        self.versions: dict = defaultdict(list)
        self.revisions: dict = defaultdict(int)
        self.basis_counts: dict = defaultdict(int)
        for _, did, src, obs in loaded:
            # within a delivery: publication order (preliminary before final)
            for o in sorted(obs, key=lambda o: (o.published_at_utc or o.first_seen_utc, o.sort_key())):
                inst: Instrument = instruments[o.instrument_id]
                name = series_name(src.source_id, o.instrument_id, o.contract_id, o.field)
                a = availability(o, inst, src, monitoring[name])
                hist = self.versions[(name, o.session_date)]
                if hist and hist[-1].value == o.value:
                    continue
                if hist:
                    self.revisions[name] += 1
                    avail = a.available_utc if src.timestamp_semantics == "vendor_receipt" \
                        else max(a.available_utc, o.first_seen_utc)
                    basis = a.basis if src.timestamp_semantics == "vendor_receipt" else "revision_first_seen"
                    if avail < hist[-1].available_utc:
                        raise MarketDataError(f"{name} {o.session_date}: a revision available before the "
                                              "value it revises")
                else:
                    avail, basis = a.available_utc, a.basis
                hist.append(Version(o.value, avail, basis, did))
                self.basis_counts[basis] += 1
        self.dataset_ids = tuple(d for _, d, _, _ in loaded)

    def names(self) -> list:
        return sorted({n for n, _ in self.versions})

    def as_of(self, series: str, t: datetime) -> dict:
        """{session_date: value} for ``series`` as known at time ``t``."""
        t = as_utc(t, "t")
        out = {}
        for (name, d), hist in self.versions.items():
            if name != series:
                continue
            known = [v for v in hist if v.available_utc <= t]
            if known:
                out[d] = known[-1].value
        return dict(sorted(out.items()))

    def decision_time(self, day: date) -> datetime:
        return datetime.combine(day, self.clock.decision_time, tzinfo=ZoneInfo(self.clock.tz))

    def reconstructed(self) -> bool:
        return any(v.basis in ("backfill", "late") for hist in self.versions.values() for v in hist)

    def pit_store(self) -> PitStore:
        st = PitStore()
        by = defaultdict(list)
        for (name, d), hist in self.versions.items():
            per_day = {}                      # versions usable from the same day: the last one known that day
            for v in hist:
                day = self.clock.available_day(v.available_utc)
                if day < d:
                    raise MarketDataError(f"{name} {d}: available on {day}, before the session it describes")
                per_day[day] = v
            for day, v in per_day.items():
                by[name].append((d, v.value, day, v.basis in ("backfill", "late")))
        for name in sorted(by):
            rows = sorted(by[name])
            st.add(name, [r[0] for r in rows], [r[1] for r in rows], available=[r[2] for r in rows],
                   reconstructed=any(r[3] for r in rows))
        return st

    def reader(self, *, caller: str, domain: str, fence: roles.Fence, **kw) -> Reader:
        return Reader(self.pit_store(), caller=caller, domain=domain, fence=fence, **kw)

    def summary(self) -> dict:
        """Counts only (no values): what a report may show for licensed data."""
        return {"datasets": list(self.dataset_ids), "series": len(self.names()),
                "versions": sum(len(h) for h in self.versions.values()),
                "revisions": int(sum(self.revisions.values())), "basis": dict(sorted(self.basis_counts.items())),
                "reconstructed": self.reconstructed()}
