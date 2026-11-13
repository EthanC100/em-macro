"""First-seen capture of source data, and the point-in-time store built from it (criteria O-20, O-30).

**First seen, before evaluated.** Each run fetches every source and stores the raw bytes in the private ledger
(``raw/<sha256>.bin``) with a ``capture`` record (source, SHA-256, size, retrieval time) **before** any value is
used. Identical bytes give the same key, so a re-fetch of unchanged data adds nothing. The store a run evaluates on
is rebuilt from the captures alone, in chain order: the first capture that holds a (series, period) fixes its value
and the day it became available. A later capture with a different value for that period is a **revision**: it is
counted and never replaces the first-seen value (Protocol v3 section 6.6: revisions never rewrite the process).

**Availability of a value** (the day at whose close it may be used):

    seen      the retrieval time, in the market's zone, moved to the next day when it was after the close
    nominal   period + the source's publication lag in days
    backfill  a period whose nominal day is before the source's first capture (history that existed before
              monitoring began): available on its nominal day; usable as signal warm-up
    otherwise available = max(nominal, seen); **late** when seen > nominal + the source's grace days

An observation whose marks were late or backfilled is recorded as ``reconstructed`` with evidential weight 0
(ARCHITECTURE section 6.3). The rule looks at availability only, never at a value.

Sources: ``synthetic`` (deterministic synthetic prices, carry and events for tests; never a market) and FRED's H.10
dollar exchange rates (public). The FRED fetcher is written but was not run from the session that wrote it.
"""
from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np

from manhattan.engine.pit import PitStore, Window

from . import store as ST
from . import timing as TM


@dataclass(frozen=True)
class Source:
    id: str
    kind: str                       # "synthetic" or "fred"
    calendar: str
    lag_days: int
    grace_days: int
    fred_id: str | None = None
    series: str | None = None       # for a FRED source: the series name it fills (the dollar value of the currency)


SOURCES = {
    "synthetic": Source("synthetic", "synthetic", "synthetic", 0, 3),
    # H.10 noon buying rates, local currency per dollar; the series filled is 1 / rate (the dollar value of one unit).
    # FRED posts the H.10 dailies weekly, so the grace is ten days.
    "fred_DEXBZUS": Source("fred_DEXBZUS", "fred", "us_fed_fx", 1, 10, "DEXBZUS", "fx_BRL"),
    "fred_DEXMXUS": Source("fred_DEXMXUS", "fred", "us_fed_fx", 1, 10, "DEXMXUS", "fx_MXN"),
    "fred_DEXSFUS": Source("fred_DEXSFUS", "fred", "us_fed_fx", 1, 10, "DEXSFUS", "fx_ZAR"),
}
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={id}"


# ---------------------------------------------------------------- parsing

def parse(source: Source, raw: bytes) -> list[tuple[str, str, float]]:
    """(series, period, value) rows of a capture. Missing values are skipped (a gap is not a value)."""
    text = raw.decode("utf-8")
    rows = []
    if source.kind == "synthetic":
        for r in csv.DictReader(io.StringIO(text)):
            rows.append((r["series"], r["period"], float(r["value"])))
        return rows
    if source.kind == "fred":
        rd = csv.reader(io.StringIO(text))
        header = next(rd)
        if len(header) < 2 or header[1].strip() != source.fred_id:
            raise ValueError(f"{source.id}: unexpected header")
        for r in rd:
            if len(r) < 2 or r[1].strip() in ("", "."):
                continue
            v = float(r[1])
            if v > 0:
                rows.append((source.series, date.fromisoformat(r[0].strip()).isoformat(), 1.0 / v))
        return rows
    raise ValueError(f"unknown source kind {source.kind}")


def fetch_fred(source: Source, timeout: float = 30.0) -> bytes:
    """The public FRED CSV of one series (no key needed)."""
    import requests                                           # imported here: tests never fetch
    r = requests.get(FRED_URL.format(id=source.fred_id), timeout=timeout,
                     headers={"User-Agent": "manhattan-ops-runner"})
    r.raise_for_status()
    return r.content


# ---------------------------------------------------------------- synthetic data (tests, the end-to-end proof)

SYN_START = date(2005, 1, 3)


def synthetic_rows(asof: date, seed: int = 0, *, drop: dict | None = None, revise: dict | None = None):
    """Every synthetic value with period on or before ``asof``. Values depend on the period alone, never on
    ``asof``, so captures on different days agree. ``drop``: {(series, period)} withheld (a data gap);
    ``revise``: {(series, period): value} replaced (a vendor revision)."""
    cal = TM.calendar("synthetic")
    days = np.array(cal.sessions(SYN_START, asof), dtype="datetime64[D]")
    n = days.size
    out = []
    for k, c in enumerate("ABCDEF"):
        r = np.random.default_rng([seed, k])
        # draw a fixed long path and take its first n values, so a value never depends on asof
        path = r.normal(0.0002, 0.009, 12000)[:n]
        px = 100.0 * np.exp(np.cumsum(path))
        carry = 0.02 + 0.03 * np.sin(np.arange(12000)[:n] / 400.0 + k) + 0.01 * k
        ev_mask = r.random(12000)[:n] < 0.01
        ev_val = np.where(r.random(12000)[:n] < 0.5, -0.2, 0.2)
        for i, d in enumerate(days):
            p = str(d)
            out.append((f"syn_px_{c}", p, float(px[i])))
            out.append((f"syn_carry_{c}", p, float(carry[i])))
            if ev_mask[i]:
                out.append((f"syn_evt_{c}", p, float(ev_val[i])))
    drop, revise = drop or set(), revise or {}
    out = [(s, p, revise.get((s, p), v)) for s, p, v in out if (s, p) not in drop]
    return out


def synthetic_csv(asof: date, seed: int = 0, **kw) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["series", "period", "value"])
    for s, p, v in synthetic_rows(asof, seed, **kw):
        w.writerow([s, p, repr(v)])
    return buf.getvalue().encode("utf-8")


# ---------------------------------------------------------------- capture

def capture_intent(source: Source, raw: bytes, retrieved: datetime) -> tuple[ST.Intent, dict]:
    sha = hashlib.sha256(raw).hexdigest()
    rows = parse(source, raw)                                # a capture that cannot be parsed is refused here
    periods = sorted(p for _, p, _ in rows)
    it = ST.Intent("capture", ("capture", source.id, sha),
                   {"source": source.id, "sha256": sha, "bytes": len(raw), "rows": len(rows),
                    "first_period": periods[0] if periods else None, "last_period": periods[-1] if periods else None},
                   source=source.id, retrieved_utc=TM.iso(retrieved))
    return it, {f"raw/{sha}.bin": raw}


def _seen_day(cal: TM.Calendar, retrieved: datetime) -> date:
    local = retrieved.astimezone(ZoneInfo(cal.tz))
    return local.date() if local.timetz().replace(tzinfo=None) < cal.close else local.date() + timedelta(days=1)


@dataclass
class FirstSeen:
    """First-seen values of every series, with availability and flags, rebuilt from the ledger's captures."""
    values: dict          # (series, period) -> value
    available: dict       # (series, period) -> date
    late: set             # {(series, period)} seen after nominal + grace
    backfill: set         # {(series, period)} before monitoring began
    revisions: int
    monitoring_start: dict  # source -> date
    capture_count: int

    def pit_store(self) -> PitStore:
        st = PitStore()
        by: dict = {}
        for (s, p), v in self.values.items():
            by.setdefault(s, []).append((p, v, self.available[(s, p)]))
        for s, rows in sorted(by.items()):
            rows.sort()
            st.add(s, [r[0] for r in rows], [r[1] for r in rows], available=[r[2] for r in rows])
        return st

    def complete(self, series: list[str], period: str) -> bool:
        return all((s, period) in self.values for s in series)

    def reconstructed(self, series: list[str], period: str) -> bool:
        return any((s, period) in self.late or (s, period) in self.backfill for s in series)


def first_seen(ledger: ST.Store, source_ids) -> FirstSeen:
    values, avail, late, back, firstcap = {}, {}, set(), set(), {}
    revisions, n = 0, 0
    for rec in ledger.of_type("capture"):
        src = SOURCES.get(rec["payload"]["source"])
        if src is None or src.id not in source_ids:
            continue
        n += 1
        cal = TM.calendar(src.calendar)
        retrieved = TM.parse_time(rec["provenance"]["retrieved_utc"])
        seen = _seen_day(cal, retrieved)
        start = firstcap.setdefault(src.id, seen)
        raw = ledger.raw_path(rec["payload"]["sha256"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != rec["payload"]["sha256"]:
            raise ST.StoreError("a raw capture does not match its recorded hash")
        for s, p, v in parse(src, raw):
            k = (s, p)
            if k in values:
                if values[k] != v:
                    revisions += 1
                continue
            nominal = date.fromisoformat(p) + timedelta(days=src.lag_days)
            values[k] = v
            if nominal < start:
                avail[k] = nominal
                back.add(k)
            else:
                avail[k] = max(nominal, seen)
                if seen > nominal + timedelta(days=src.grace_days):
                    late.add(k)
    return FirstSeen(values, avail, late, back, revisions, firstcap, n)


def forward_window(pit: PitStore, domain: str, start: date, end: date) -> Window:
    """ADAPTER (OPS_PROGRESS.md, request R-1). ``manhattan.roles.check_read`` allows one role per read and has no
    role for history read as **signal input** before a forward window: with the default fence the dates between
    the exploration cut-off and a freeze are embargoed, so a forward strategy could not compute a 60-day momentum.
    The runner therefore opens the window itself, as the runner, labelled ``forward``. Returns dated on or before the
    first observation are computed in memory as warm-up and never recorded (the runner records only later dates)."""
    return Window(pit, start, end, "forward", domain, "runner")
