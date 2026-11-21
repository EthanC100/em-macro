"""The forward-observation plan of one prediction on one night: which sessions are observed, with which values and
provenance, and which are missed (Phase 4B, S7 G-1).

One pure function decides it, from the first-seen captures, the registration in force, the compiled executable,
the night and the bound computation. The runner writes what it returns; ``manhattan.access.completion``
recomputes it from the Store's own captures and registration and refuses anything else (a flipped ``reconstructed``
flag, an omitted observation, a ``missed_observation`` that the captures do not justify); the reconciler re-derives
the provenance part from the capture records. The rules are the runner's existing ones, moved here unchanged:

    observed     every series of the universe has a first-seen value for the session, and the computation has it
    reconstructed  a mark of the session, or of the previous session it returns from, was captured late or
                 backfilled, or the session precedes monitoring
    missed       not observed, and the session plus the sources' lag and grace is before the night
    weight       ``ledger.forward_observation_weight`` (eligibility and the registration's weight; 0 if reconstructed)
"""
from __future__ import annotations

from datetime import date, timedelta

from manhattan import ledger as L

from . import data as D
from . import store as ST
from . import timing as TM


def series_of(universe) -> list[str]:
    return [p for _, p in universe.instruments]


def _sources(universe):
    return [D.SOURCES[s] for s in universe.sources]


def monitoring_start(fs: D.FirstSeen, universe, asof: date) -> date:
    return min(fs.monitoring_start.get(s.id, asof) for s in _sources(universe))


def reconstructed(fs: D.FirstSeen, universe, d: date, asof: date) -> bool:
    """The provenance rule of one observed session (the runner's, unchanged)."""
    series = series_of(universe)
    cal = TM.calendar(universe.calendar)
    ds, base = d.isoformat(), cal.prev_session(d).isoformat()
    return bool(fs.reconstructed(series, ds) or (fs.complete(series, base) and fs.reconstructed(series, base))
                or d < monitoring_start(fs, universe, asof))


def missed_is_due(universe, d: date, asof: date) -> bool:
    srcs = _sources(universe)
    return d + timedelta(days=max(s.lag_days for s in srcs) + max(s.grace_days for s in srcs)) < asof


def sessions(universe, first_observation: date, asof: date) -> list[date]:
    return list(TM.calendar(universe.calendar).sessions(first_observation + timedelta(days=1), asof))


def expected(fs: D.FirstSeen, universe, first_observation: date, asof: date,
             computed: set | None = None) -> tuple[list[date], list[date]]:
    """(observed sessions, missed sessions). ``computed``: the sessions the computation has (all, if None)."""
    series = series_of(universe)
    obs, missed = [], []
    for d in sessions(universe, first_observation, asof):
        ds = d.isoformat()
        if fs.complete(series, ds) and (computed is None or ds in computed):
            obs.append(d)
        elif missed_is_due(universe, d, asof):
            missed.append(d)
    return obs, missed


def plan(fs: D.FirstSeen, reg: dict, exe, asof: date, res) -> tuple[list, int]:
    """The intents of one prediction's night, and how many sessions were expected."""
    from manhattan import access as A
    start = date.fromisoformat(reg["first_observation"])
    if asof <= start:
        return [], 0
    at = {str(d): i for i, d in enumerate(res.dates.astype("datetime64[D]"))}
    obs, missed = expected(fs, exe.universe, start, asof, set(at))
    out = []
    for d in sorted(obs + missed):
        ds = d.isoformat()
        if d in obs:
            recon = reconstructed(fs, exe.universe, d, asof)
            weight = L.forward_observation_weight(eligible=bool(reg["eligible"]),
                                                  registration_weight=reg["evidential_weight"],
                                                  reconstructed=recon, channel=reg.get("channel", "blind"))
            payload = {"prediction": reg["prediction"], "executable": exe.id, "date": ds,
                       **A.observation_values(res, at[ds]),
                       "eligible": bool(reg["eligible"]), "reconstructed": recon, "evidential_weight": weight,
                       "registration_status": reg["registration_status"], "role": "forward"}
            out.append(ST.Intent("observation", ("observation", reg["prediction"], ds), payload,
                                 source=",".join(exe.universe.sources)))
        else:
            out.append(ST.Intent("missed_observation", ("missed_observation", reg["prediction"], ds),
                                 {"prediction": reg["prediction"], "date": ds,
                                  "reason": "data_not_available_by_grace"}))
    return out, len(sessions(exe.universe, start, asof))


def registration_in_force(records_of_type, prediction: str) -> dict | None:
    """The witnessed registration of a prediction when there is one, else the provisional one (the runner's rule)."""
    found = None
    for r in records_of_type("registration"):
        p = r["payload"]
        if p.get("prediction") == prediction and (found is None or p.get("registration_status") == "witnessed"):
            found = p
    return found
