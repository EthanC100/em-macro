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
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np

from manhattan.engine.pit import PitStore, Window
from manhattan.availability import AvailabilityError, sources_from_spec, validate_source

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

    frequency: str | None = None
    period_label: str | None = None
    availability_kind: str | None = None
    source_reference: str = ""
    day_mapping: str = ""

    def publication_contract(self) -> dict:
        return {"name": self.id, "frequency": self.frequency, "period_label": self.period_label,
                "publication_lag_days": self.lag_days,
                "availability": {"kind": self.availability_kind,
                                 "reference": self.source_reference, "day_mapping": self.day_mapping}}


def validate_capture_source(source: Source) -> None:
    validate_source(source.publication_contract())
    # Current CSV adapters carry no per-vintage release field. Fail closed until
    # an adapter supplies explicit availability; never infer it from period labels.
    if source.availability_kind != "daily_lag":
        raise AvailabilityError("capture adapter requires explicit per-vintage availability")


def capture_registry(sources) -> dict[str, Source]:
    sources = list(sources)
    for source in sources:
        validate_capture_source(source)
    sources_from_spec({"data_sources": [s.publication_contract() for s in sources]})
    out = {}
    for source in sources:
        if source.id in out and out[source.id] != source:
            raise AvailabilityError("conflicting capture source declarations")
        out[source.id] = source
    return out


SOURCES = {
    "synthetic": Source("synthetic", "synthetic", "synthetic", 0, 3,
                           frequency="daily", period_label="observation_date", availability_kind="daily_lag",
                           day_mapping="calendar-day lag; retrieval mapped by source calendar close",
                           source_reference="deterministic synthetic fixture"),
    # H.10 noon buying rates, local currency per dollar; the series filled is 1 / rate (the dollar value of one unit).
    # FRED posts the H.10 dailies weekly, so the grace is ten days.
    "fred_DEXBZUS": Source("fred_DEXBZUS", "fred", "us_fed_fx", 1, 10, "DEXBZUS", "fx_BRL",
                           frequency="daily", period_label="observation_date", availability_kind="daily_lag",
                           day_mapping="calendar-day lag; retrieval mapped by source calendar close",
                           source_reference="https://www.federalreserve.gov/releases/h10/"),
    "fred_DEXMXUS": Source("fred_DEXMXUS", "fred", "us_fed_fx", 1, 10, "DEXMXUS", "fx_MXN",
                           frequency="daily", period_label="observation_date", availability_kind="daily_lag",
                           day_mapping="calendar-day lag; retrieval mapped by source calendar close",
                           source_reference="https://www.federalreserve.gov/releases/h10/"),
    "fred_DEXSFUS": Source("fred_DEXSFUS", "fred", "us_fed_fx", 1, 10, "DEXSFUS", "fx_ZAR",
                           frequency="daily", period_label="observation_date", availability_kind="daily_lag",
                           day_mapping="calendar-day lag; retrieval mapped by source calendar close",
                           source_reference="https://www.federalreserve.gov/releases/h10/"),
}
SOURCES = capture_registry(SOURCES.values())
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={id}"


# ---------------------------------------------------------------- parsing

def _checked_rows(rows):
    """A capture cannot contain two different values for the same release key."""
    seen, out = {}, []
    for series, period, value in rows:
        if not isinstance(series, str) or not series or not np.isfinite(value):
            raise ValueError("capture has an invalid series or nonfinite value")
        period = date.fromisoformat(period).isoformat()
        key = (series, period)
        if key in seen and float(seen[key]).hex() != float(value).hex():
            raise ValueError("capture contains conflicting values for one observation")
        seen[key] = value
        out.append((series, period, value))
    return out


def parse(source: Source, raw: bytes) -> list[tuple[str, str, float]]:
    """(series, period, value) rows of a capture. Missing values are skipped (a gap is not a value)."""
    validate_capture_source(source)
    text = raw.decode("utf-8")
    rows = []
    if source.kind == "synthetic":
        for r in csv.DictReader(io.StringIO(text)):
            rows.append((r["series"], r["period"], float(r["value"])))
        return _checked_rows(rows)
    if source.kind == "fred":
        rd = csv.reader(io.StringIO(text))
        header = next(rd)
        if len(header) < 2 or header[1].strip() != source.fred_id:
            raise ValueError(f"{source.id}: unexpected header")
        for r in rd:
            if len(r) < 2 or r[1].strip() in ("", "."):
                continue
            v = float(r[1])
            if not np.isfinite(v):
                raise ValueError("capture has a nonfinite quote")
            if v > 0:
                rows.append((source.series, date.fromisoformat(r[0].strip()).isoformat(), 1.0 / v))
        return _checked_rows(rows)
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

def source_definition(source: Source) -> dict:
    """Declared replay configuration, not proof of provider release history."""
    validate_capture_source(source)
    cal = TM.calendar(source.calendar)
    return {"schema_version": 2, "source": asdict(source),
            "calendar": {"name": cal.name, "tz": cal.tz, "close": cal.close.isoformat(),
                         "publish_sessions": cal.publish_sessions,
                         "publish_time": cal.publish_time.isoformat() if cal.publish_time else None}}


def capture_intent(source: Source, raw: bytes, retrieved: datetime) -> tuple[ST.Intent, dict]:
    if not isinstance(retrieved, datetime) or retrieved.tzinfo is None or retrieved.utcoffset() is None:
        raise ValueError("capture observation time requires an explicit time zone")
    sha = hashlib.sha256(raw).hexdigest()
    rows = parse(source, raw)                                # a capture that cannot be parsed is refused here
    periods = sorted(p for _, p, _ in rows)
    it = ST.Intent("capture", ("capture", source.id, sha),
                   {"source": source.id, "sha256": sha, "bytes": len(raw), "rows": len(rows),
                    "first_period": periods[0] if periods else None, "last_period": periods[-1] if periods else None,
                    "source_definition": source_definition(source)},
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
            st.add(s, [r[0] for r in rows], [r[1] for r in rows], available=[r[2] for r in rows],
                   reconstructed=any((s, r[0]) in self.late or (s, r[0]) in self.backfill for r in rows))
        return st

    def complete(self, series: list[str], period: str) -> bool:
        return all((s, period) in self.values for s in series)

    def reconstructed(self, series: list[str], period: str) -> bool:
        return any((s, period) in self.late or (s, period) in self.backfill for s in series)


def first_seen(ledger: ST.Store, source_ids) -> FirstSeen:
    source_ids = frozenset(source_ids)
    if not source_ids <= SOURCES.keys():
        raise ST.StoreError("unknown source requested for capture replay")
    values, avail, late, back, firstcap, first_observed_day = {}, {}, set(), set(), {}, {}
    revisions, n = 0, 0
    for rec in ledger.of_type("capture"):
        src = SOURCES.get(rec["payload"]["source"])
        if src is None or src.id not in source_ids:
            if (len(rec["key"]) > 1 and rec["key"][1] in source_ids) \
                    or rec["provenance"].get("source") in source_ids:
                raise ST.StoreError("capture source identities conflict")
            continue
        payload = rec["payload"]
        if not isinstance(payload["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", payload["sha256"]):
            raise ST.StoreError("capture has an invalid raw version hash")
        if tuple(rec["key"]) != ("capture", src.id, payload["sha256"]) \
                or rec["provenance"].get("source") != src.id:
            raise ST.StoreError("capture source identities conflict")
        if "source_definition" in payload:
            recorded = payload["source_definition"]
            version = recorded.get("schema_version") if isinstance(recorded, dict) else None
            expected = source_definition(src)
            if type(version) is not int or version != expected["schema_version"]:
                raise ST.StoreError(f"capture schema version {version!r}; expected schema version "
                                    f"{expected['schema_version']}")
            if recorded != expected:
                raise ST.StoreError("capture source definition differs from replay configuration")
        n += 1
        cal = TM.calendar(src.calendar)
        retrieved = TM.parse_time(rec["provenance"]["retrieved_utc"])
        seen = _seen_day(cal, retrieved)
        start = firstcap.setdefault(src.id, seen)
        first_day = first_observed_day.setdefault(src.id, retrieved.astimezone(ZoneInfo(cal.tz)).date())
        raw = ledger.raw_path(rec["payload"]["sha256"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != rec["payload"]["sha256"]:
            raise ST.StoreError("a raw capture does not match its recorded hash")
        if len(raw) != payload["bytes"]:
            raise ST.StoreError("a raw capture does not match its recorded byte count")
        rows = parse(src, raw)
        periods = sorted(p for _, p, _ in rows)
        if len(rows) != payload["rows"] or payload["first_period"] != (periods[0] if periods else None) \
                or payload["last_period"] != (periods[-1] if periods else None):
            raise ST.StoreError("capture contents conflict with recorded coverage metadata")
        for s, p, v in rows:
            k = (s, p)
            if k in values:
                if values[k] != v:
                    revisions += 1
                continue
            nominal = date.fromisoformat(p) + timedelta(days=src.lag_days)
            values[k] = v
            if nominal < start:
                # Keep the existing reconstructed/warm-up classification, but
                # do not backdate a current-day value seen at/after that close.
                avail[k] = nominal if nominal < first_day else max(nominal, seen)
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
