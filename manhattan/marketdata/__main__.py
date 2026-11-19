"""Command line.

    python -m manhattan.marketdata demo [--out DIR]
        End-to-end on synthetic fixtures (Norgate and Databento layouts): ingest, validate, store, read point in
        time, build a continuous series as of a date. Writes to DIR (default: a new temporary directory).

    python -m manhattan.marketdata verify --store DIR
        Recompute the registry chain and re-hash every dataset in a store.

    python -m manhattan.marketdata ingest-norgate --snapshot DIR --store DIR --instruments FILE --retrieved ISO
            [--markets XA,XB] [--delay-minutes N --delay-reference TEXT --owner-approval TEXT]
        Ingest the exploration dates (to config/manhattan.yaml's exploration end) of a Norgate export snapshot
        into a private store, as caller "session" with policy "exclude". Refuses a store inside this repository.
        FILE is the owner-supplied instrument reference (JSON list; DESIGN.md section 9). --retrieved is the time
        the snapshot was captured (for em-macro-data: the commit time that added it); it is never guessed.
        Prints counts only, never a value.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import date, datetime, time, timezone
from pathlib import Path

from manhattan import roles

from . import continuous as CT
from .adapters import fixture as FX
from .adapters.databento import DatabentoStatisticsAdapter, databento_source
from .adapters.norgate import NorgateExportAdapter, norgate_source
from .fence import default_fence
from .ingest import ingest
from .schema import Instrument, as_date
from .store import DatasetStore
from .timing import ResearchClock
from .vintages import VintageSet

UTC = timezone.utc


def load_instruments(path: Path) -> tuple[dict, dict]:
    """(instruments by id, Norgate market -> instrument id) from a JSON list of instrument dicts, each with an
    optional ``norgate_market``."""
    insts, markets = {}, {}
    for d in json.loads(Path(path).read_text(encoding="utf-8")):
        d = dict(d)
        market = d.pop("norgate_market", None)
        d["session_close"] = time.fromisoformat(d["session_close"])
        if d.get("maturity"):
            d["maturity"] = as_date(d["maturity"])
        inst = Instrument(**d)
        insts[inst.instrument_id] = inst
        if market:
            markets[market] = inst.instrument_id
    return insts, markets


def demo(out: Path) -> dict:
    inst = FX.synthetic_instruments()
    cons = FX.synthetic_contracts("XA", "SYN_XA", 2018, 2020)
    fence = roles.Fence(date(2019, 12, 31), {}, False)
    store = DatasetStore(out / "store", allow_licensed=True)
    retrieved = datetime(2026, 11, 19, tzinfo=UTC)
    ng = norgate_source(delay_minutes=600, delay_reference="synthetic demo", owner_approval="synthetic demo")
    r1 = ingest(NorgateExportAdapter({"XA": "SYN_XA"}, inst, ng), FX.synthetic_norgate_export(cons, date(2020, 3, 31)),
                request={"snapshot": "synthetic"}, retrieved_utc=retrieved, instruments=inst, store=store,
                fence=fence, caller="session", policy="exclude")
    raw, sm = FX.synthetic_databento_statistics(cons, inst["SYN_XA"], date(2019, 1, 2), date(2019, 3, 29),
                                                revise_final={("XA-2019H", date(2019, 2, 1)): 99.99})
    db = databento_source()
    r2 = ingest(DatabentoStatisticsAdapter(inst, db), {"statistics.csv": raw},
                request={"symbol_map": sm, "ts_format": "ns", "price_format": "fixed_1e9"}, retrieved_utc=retrieved,
                instruments=inst, contracts=cons, store=store, fence=fence, caller="session")
    clock = ResearchClock("America/New_York", time(17, 0))
    vs = VintageSet(store, [r1.dataset_id, r2.dataset_id], inst, {ng.source_id: ng, db.source_id: db}, clock)
    w = vs.reader(caller="session", domain="futures_daily", fence=fence).window(date(2018, 1, 2), date(2019, 12, 31))
    t = date(2019, 6, 28)
    days, _, held = CT.build(w, ng.source_id, "SYN_XA", list(cons.values()), t, decision_time=vs.decision_time(t))
    return {"store": str(store.root), "datasets": [r1.dataset_id, r2.dataset_id], "registry_records": store.verify(),
            "norgate_fence": r1.manifest.fence, "vintages": vs.summary(),
            "continuous": {"as_of": t.isoformat(), "sessions": len(days), "contracts_held": sorted(set(held))}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m manhattan.marketdata", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("demo")
    d.add_argument("--out", type=Path)
    v = sub.add_parser("verify")
    v.add_argument("--store", type=Path, required=True)
    n = sub.add_parser("ingest-norgate")
    n.add_argument("--snapshot", type=Path, required=True)
    n.add_argument("--store", type=Path, required=True)
    n.add_argument("--instruments", type=Path, required=True)
    n.add_argument("--retrieved", required=True)
    n.add_argument("--markets", default="")
    n.add_argument("--delay-minutes", type=int)
    n.add_argument("--delay-reference", default="")
    n.add_argument("--owner-approval", default="")
    a = ap.parse_args(argv)
    if a.cmd == "demo":
        out = a.out or Path(tempfile.mkdtemp(prefix="manhattan-marketdata-demo-"))
        print(json.dumps(demo(out), indent=1, default=str))
        return 0
    if a.cmd == "verify":
        print(json.dumps({"store": str(a.store), "registry_records": DatasetStore(a.store).verify()}))
        return 0
    insts, markets = load_instruments(a.instruments)
    wanted = [m for m in a.markets.split(",") if m] or sorted(markets)
    unknown = set(wanted) - set(markets)
    if unknown:
        print(f"no instrument for Norgate markets {sorted(unknown)} in {a.instruments}", file=sys.stderr)
        return 2
    store = DatasetStore(a.store, allow_licensed=True)                      # refuses a path inside the repository
    files = {}
    for p in sorted(a.snapshot.rglob("*")):
        rel = p.relative_to(a.snapshot).as_posix()
        if p.is_file() and (rel in ("manifest.csv", "manifest.json", "metadata.csv")
                            or any(rel.startswith(f"contracts/{m}/") for m in wanted)):
            files[rel] = p.read_bytes()
    src = norgate_source(delay_minutes=a.delay_minutes, delay_reference=a.delay_reference,
                         owner_approval=a.owner_approval)
    r = ingest(NorgateExportAdapter({m: markets[m] for m in wanted}, insts, src), files,
               request={"snapshot": a.snapshot.name, "markets": wanted}, retrieved_utc=a.retrieved,
               instruments=insts, store=store, fence=default_fence(), caller="session", policy="exclude")
    print(json.dumps({"dataset_id": r.dataset_id, "created": r.created, "rows": r.manifest.row_count,
                      "coverage": r.manifest.coverage, "fence": r.manifest.fence,
                      "warnings": r.report["warnings"], "provenance_gaps": list(r.manifest.provenance_gaps)},
                     indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
