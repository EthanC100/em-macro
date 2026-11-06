"""T25-T26 live shadows: data (docs/prereg/T25-T26_live_shadows.md, Amendment 1 §A1.2).

    EM_MACRO_DATA=... DATABENTO_API_KEY=... python -m em_macro.t2526_data history   # one-off: quoted, cap US$20
    EM_MACRO_DATA=... python -m em_macro.t2526_data check                            # once, before go-live, against Norgate
    EM_MACRO_DATA=... DATABENTO_API_KEY=... python -m em_macro.t2526_data update    # daily, under the US$1 daily cap

**Where the data live (all private, em-macro-data):**
- ``databento/shadows/raw/<code>.csv``: Databento GLBX.MDP3 final settlements per contract (date, contract,
  settle in Databento's units).
- ``databento/shadows/contracts/<code>/<ROOT>-<YYYY><M>.csv``: the same settlements in the layout and price units
  the unchanged a160bfd code reads (``commod_data.MarketData``: date, close, volume). They are written only for
  markets that passed the check, using the unit factor the check measured.
- ``databento/shadows/factors.json``: the unit factor and check result per market.

**Process-local redirect, no a160bfd file edited** (``databento_layout``): ``commod_data.snapshot_dir`` points at
``databento/shadows``; ``commod_data.norgate_metadata`` returns None, so every first notice and last trade date
comes from the exchange rules; and ``ASSEMBLY_END_MONTH`` becomes the month being computed. Nothing about signals,
the roll rule, sizing, costs or statistics is touched.

**Licence.** No settlement value is ever written to this repository or printed. The check writes counts, shares and
unit factors only (``results/shadows/prelive.json``). The Norgate snapshot is read only by ``check``, before
go-live (Amendment 1: nothing depends on Norgate after the subscription ends, about 5 May 2027).
"""
from __future__ import annotations

import argparse
import contextlib
import json
import shutil
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import commod_data as CD
from .config import ROOT

HISTORY_START = date(2023, 1, 1)             # Amendment 1 A1.2: at least 40 months before M1's decision date
ONE_OFF_CAP_USD = 20.00
TOLERANCE_SHARE = 0.99                       # one tick on >= 99% of common days (Build 0 A5)
AVAIL = ROOT / "results/T25-T26/availability.json"
PRELIVE = ROOT / "results/shadows/prelive.json"
NORGATE_END = date(2027, 5, 5)               # Amendment 1 A1.2: the Norgate subscription ends about then
MONTH_CODES = CD.MONTH_CODES


def universes() -> dict[str, list[str]]:
    """The universes fixed by the availability check (§3.2)."""
    a = json.loads(AVAIL.read_text())["markets"]
    return {"T25": [c for c, s in a.items() if s.get("qualifies_T25")],
            "T26": [c for c, s in a.items() if s.get("qualifies_T26")]}


def all_markets() -> list[str]:
    u = universes()
    return sorted(set(u["T25"]) | set(u["T26"]), key=list(CD.MARKETS).index)


def base_dir() -> Path:
    return CD.data_root() / "databento" / "shadows"


def label(code: str, y: int, m: int) -> str:
    return CD.contract_label(code, y, m)


def designated(code: str, first: pd.Period, last: pd.Period) -> list[tuple[int, int]]:
    months = CD.MARKETS[code].months
    return [(p.year, p.month) for p in pd.period_range(first, last, freq="M") if MONTH_CODES[p.month - 1] in months]


def raw_symbols(code: str, y: int, m: int) -> list[str]:
    base = f"{code}{MONTH_CODES[m - 1]}"
    return [f"{base}{y % 10}", f"{base}{y % 100:02d}"]


# ----------------------------------------------------------------------------- the redirect
@contextlib.contextmanager
def databento_layout(end_month: pd.Period, base: Path | None = None):
    """Point the unchanged a160bfd data layer at the Databento contract files (process-local, restored on exit)."""
    base = base or base_dir()
    orig = (CD.snapshot_dir, CD.norgate_metadata, CD.ASSEMBLY_END_MONTH)
    CD.snapshot_dir = lambda snapshot=None: base
    CD.norgate_metadata = lambda: None
    CD.ASSEMBLY_END_MONTH = end_month
    try:
        yield base
    finally:
        CD.snapshot_dir, CD.norgate_metadata, CD.ASSEMBLY_END_MONTH = orig


# ----------------------------------------------------------------------------- raw store
def read_raw(code: str, base: Path | None = None) -> pd.DataFrame:
    p = (base or base_dir()) / "raw" / f"{code}.csv"
    if not p.exists():
        return pd.DataFrame(columns=["date", "contract", "settle"])
    return pd.read_csv(p, parse_dates=["date"])


def write_raw(code: str, new: pd.DataFrame, base: Path | None = None) -> int:
    base = base or base_dir()
    p = base / "raw" / f"{code}.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    old = read_raw(code, base)
    allr = pd.concat([old, new[["date", "contract", "settle"]]], ignore_index=True)
    allr["date"] = pd.to_datetime(allr["date"])
    allr = allr.drop_duplicates(["date", "contract"], keep="last").sort_values(["contract", "date"])
    allr.to_csv(p, index=False, date_format="%Y-%m-%d")
    return len(allr) - len(old)


def write_contracts(code: str, factor: float, base: Path | None = None) -> int:
    """Per-contract files in the a160bfd layout and Norgate's price units (raw settle x factor).

    A contract whose delivery month is the first month of the stored history (or earlier) is not written: its
    exchange-rule notice date falls before the history's calendar, where the unchanged a160bfd date rules cannot be
    evaluated, and the roll rule never holds it at the first rebalance with a decision date in the history."""
    base = base or base_dir()
    raw = read_raw(code, base)
    folder = base / "contracts" / code
    folder.mkdir(parents=True, exist_ok=True)
    if raw.empty:
        return 0
    first = pd.Period(raw["date"].min(), "M")
    n = 0
    for c, g in raw.groupby("contract"):
        y, m = CD.parse_contract(c)
        if pd.Period(year=y, month=m, freq="M") <= first:
            continue
        df = pd.DataFrame({"date": g["date"].dt.strftime("%Y-%m-%d"), "close": g["settle"] * factor, "volume": 0})
        df.to_csv(folder / f"{c}.csv", index=False)
        n += 1
    return n


# ----------------------------------------------------------------------------- Databento requests
def _client():
    from .commod_databento import client
    return client()


def _available_end(c) -> datetime:
    from .commod_databento import DATASET, SCHEMA
    rng = c.metadata.get_dataset_range(dataset=DATASET)
    end = str((rng.get("schema", {}).get(SCHEMA) or {}).get("end") or rng["end"]).replace("Z", "")
    return datetime.fromisoformat(end[:19]).replace(tzinfo=timezone.utc)


def _resolve(c, wanted: dict[tuple[str, int, int], list[str]], start: date, end: datetime) -> dict[str, tuple]:
    from .commod_databento import DATASET
    syms = [s for v in wanted.values() for s in v]
    out: dict[str, tuple] = {}
    for i in range(0, len(syms), 500):
        r = c.symbology.resolve(dataset=DATASET, symbols=syms[i:i + 500], stype_in="raw_symbol",
                                stype_out="instrument_id", start_date=start.isoformat(), end_date=end.date().isoformat())
        found = {k for k, v in (r.get("result") or {}).items() if v} - set(r.get("not_found") or [])
        for k, v in wanted.items():
            for s in v:
                if s in found and k not in out.values():
                    out[s] = k
    # keep one symbol per contract (one-digit year first)
    seen, chosen = set(), {}
    for s, k in out.items():
        if k not in seen:
            chosen[s] = k
            seen.add(k)
    return chosen


def _requests(c, codes: list[str], start: date, first_month: pd.Period, last_month: pd.Period, end: datetime,
              starts: dict[str, date] | None = None) -> dict[str, dict]:
    from .commod_databento import DATASET, SCHEMA
    reqs = {}
    for code in codes:
        wanted = {(code, y, m): raw_symbols(code, y, m) for y, m in designated(code, first_month, last_month)}
        chosen = _resolve(c, wanted, start, end)
        if not chosen:
            continue
        s0 = (starts or {}).get(code, start)
        if s0 >= end.date():
            continue
        reqs[code] = {"kw": dict(dataset=DATASET, symbols=sorted(chosen), stype_in="raw_symbol", schema=SCHEMA,
                                 start=f"{s0.isoformat()}T00:00:00Z", end=end.strftime("%Y-%m-%dT%H:%M:%SZ")),
                      "map": {s: label(code, y, m) for s, (_c, y, m) in chosen.items()}}
    return reqs


def _download(c, req: dict) -> pd.DataFrame:
    from .commod_databento import final_settlements
    fs = final_settlements(c.timeseries.get_range(**req["kw"]).to_df(map_symbols=True))
    return pd.DataFrame({"date": pd.to_datetime(fs["date"]), "contract": fs["symbol"].map(req["map"]),
                         "settle": fs["settle"].astype(float)}).dropna(subset=["contract"])


def history(c=None, codes: list[str] | None = None, today: date | None = None, base: Path | None = None,
            cap: float = ONE_OFF_CAP_USD, log=print, force: bool = False) -> dict:
    """One-off: every designated contract whose life overlaps HISTORY_START..today+18 months, from HISTORY_START.
    Every per-market request is quoted first; nothing is downloaded if the total exceeds ``cap``."""
    c = c or _client()
    codes = codes or all_markets()
    if not force:                                    # a retry never pays twice for a market already fetched
        codes = [k for k in codes if read_raw(k, base).empty]
        if not codes:
            return {"quote_usd": 0.0, "cap_usd": cap, "markets": 0, "contracts": 0, "refused": False, "stored": {},
                    "note": "every market already has its history"}
    today = today or date.today()
    end = _available_end(c)
    reqs = _requests(c, codes, HISTORY_START, pd.Period(HISTORY_START, "M"), pd.Period(today, "M") + 18, end)
    quotes = {code: float(c.metadata.get_cost(**r["kw"])) for code, r in reqs.items()}
    total = sum(quotes.values())
    rec = {"quote_usd": round(total, 4), "cap_usd": cap, "markets": len(reqs),
           "contracts": sum(len(r["map"]) for r in reqs.values())}
    if total > cap:
        log(f"refused: one-off quote US${total:.2f} above US${cap:.2f}")
        return {**rec, "refused": True}
    stored = {}
    for code, r in reqs.items():
        df = _download(c, r)
        stored[code] = write_raw(code, df, base)
        log(f"{code}: {len(r['map'])} contracts, {stored[code]} settlements stored privately")
    return {**rec, "refused": False, "stored": stored}


def update(c=None, codes: list[str] | None = None, today: date | None = None, base: Path | None = None,
           store: Path | None = None, log=print) -> dict:
    """Daily: final settlements since each market's last stored date, for the contracts from last month's to 18
    months ahead. One combined quote under the Ledger's shared US$1 daily cap (ledger/settlements.py)."""
    from ledger import settlements as ST
    base = base or base_dir()
    today = today or date.today()
    if not base.exists():
        return {"stored": 0, "log": ["no shadow data store"]}
    if ST.is_read_only(base):
        return {"stored": 0, "log": ["read-only store: nothing fetched"]}
    c = c or _client()
    codes = codes or all_markets()
    end = _available_end(c)
    starts = {}
    for code in codes:
        raw = read_raw(code, base)
        starts[code] = (raw["date"].max().date() + timedelta(days=1)) if len(raw) else HISTORY_START
    reqs = _requests(c, codes, min(starts.values()), pd.Period(today, "M") - 1, pd.Period(today, "M") + 18, end, starts)
    if not reqs:
        return {"stored": 0, "log": ["nothing to fetch"]}
    quote = sum(float(c.metadata.get_cost(**r["kw"])) for r in reqs.values())
    spend_store = store or ST.store_dir() or base
    spent = ST.spent_today(spend_store, today)
    rec = {"utc_date": today.isoformat(), "time": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
           "purpose": "shadows", "symbols": sorted(s for r in reqs.values() for s in r["kw"]["symbols"]),
           "quote_usd": quote}
    if spent + quote > ST.DAILY_CAP_USD + 1e-12:
        ST._log_spend(spend_store, {**rec, "downloaded": False, "reason": f"daily cap US${ST.DAILY_CAP_USD:.2f}"})
        return {"stored": 0, "log": [f"refused: quote US${quote:.4f} above the daily cap (spent US${spent:.4f})"]}
    ST._log_spend(spend_store, {**rec, "downloaded": True})
    factors = read_factors(base)
    n = 0
    for code, r in reqs.items():
        n += write_raw(code, _download(c, r), base)
        if code in factors and factors[code].get("passed"):
            write_contracts(code, factors[code]["factor"], base)
    return {"stored": n, "log": [f"{n} new final settlements stored privately; quote US${quote:.4f}"]}


# ----------------------------------------------------------------------------- the check against Norgate
def read_factors(base: Path | None = None) -> dict:
    p = (base or base_dir()) / "factors.json"
    return json.loads(p.read_text()) if p.exists() else {}


def _norgate_closes(code: str) -> pd.DataFrame:
    folder = CD.snapshot_dir(CD.snapshot_for(code)) / "contracts" / code
    frames = {}
    for p in sorted(folder.glob("*.csv")):
        df = CD.load_contract_csv(p)
        df = df[df.index >= pd.Timestamp(HISTORY_START)]
        if len(df):
            frames[p.stem] = df["close"]
    return pd.DataFrame(frames)


def compare_prices(code: str, norgate: pd.DataFrame, raw: pd.DataFrame) -> dict:
    """Unit factor (power of ten), common days and the share within one tick, over every contract in both sources."""
    db = raw.pivot_table(index="date", columns="contract", values="settle", aggfunc="last")
    common = [c for c in db.columns if c in norgate.columns]
    pairs = []
    for c in common:
        j = pd.concat([norgate[c], db[c]], axis=1, keys=["n", "d"]).dropna()
        j = j[j["d"] != 0]
        pairs.append(j)
    if not pairs or not sum(len(j) for j in pairs):
        return {"common_days": 0, "contracts": len(common), "factor": None, "share": None}
    allj = pd.concat(pairs)
    ratio = (allj["n"] / allj["d"]).abs()
    factor = float(10 ** np.round(np.log10(ratio.median())))
    tick = CD.MARKETS[code].tick
    ok = ((allj["n"] - allj["d"] * factor).abs() <= tick * (1 + 1e-6))
    return {"common_days": int(len(allj)), "contracts": len(common), "factor": factor, "share": round(float(ok.mean()), 6)}


def compare_chains(md_norgate: CD.MarketData, md_databento: CD.MarketData, first: pd.Period, last: pd.Period) -> dict:
    """F1 and F2 per rebalance month, Norgate dates against exchange-rule dates, over first..last."""
    a = md_norgate.rolls.loc[(md_norgate.rolls.index >= first) & (md_norgate.rolls.index <= last), ["F1", "F2"]]
    b = md_databento.rolls.reindex(a.index)[["F1", "F2"]]
    diff = [str(m) for m in a.index if (a.at[m, "F1"], a.at[m, "F2"]) != (b.at[m, "F1"], b.at[m, "F2"])]
    return {"months": len(a), "differing_months": diff, "equal": not diff}


def p1(code: str, raw: pd.DataFrame) -> dict:
    """§8 P1: the §3.2 counts on the then-current window (CHECK_START .. the last stored settlement before the plan's
    first rebalance), from the
    stored history, so no new request is made. Same contracts (the twelve rebalances from 2026-12) and the same rule
    as em_macro/t2526_avail.py."""
    from . import t2526_avail as AV
    r = AV.plan()[code]
    # the window ends before the first rebalance of the plan (3 Dec 2026), as the §3.2 check did: a contract that
    # expires later in the plan is not counted against days after its last trade date
    end = pd.Timestamp(AV.FIRST_REBALANCE.year, AV.FIRST_REBALANCE.month, 3) - pd.Timedelta(days=1)
    raw = raw[(raw["date"] >= pd.Timestamp(AV.CHECK_START)) & (raw["date"] <= end)]
    days = {c: set(g["date"]) for c, g in raw.groupby("contract")}
    lab = {ym: label(code, *ym) for ym in set(r["contracts_F1"]) | set(r["contracts_F2"])}
    market = set().union(*[days.get(x, set()) for x in lab.values()]) if lab else set()
    n = len(market)
    share = {ym: (len(days.get(x, set())) / n if n else 0.0) for ym, x in lab.items()}
    f1 = min(share[ym] for ym in r["contracts_F1"])
    f2 = min(share[ym] for ym in r["contracts_F2"])
    return {"window": [AV.CHECK_START, str(raw["date"].max().date()) if len(raw) else None], "market_days": n,
            "min_share_F1": round(f1, 4), "min_share_F2": round(f2, 4),
            "qualifies_T25": bool(r["in_T21"] and f1 >= AV.COVERAGE_MIN and f2 >= AV.COVERAGE_MIN),
            "qualifies_T26": bool(r["in_T22"] and f1 >= AV.COVERAGE_MIN)}


def check(codes: list[str] | None = None, base: Path | None = None, write: bool = True, log=print) -> dict:
    """Amendment 1 A1.2 check, once, before go-live. Writes counts only to results/shadows/prelive.json and, for the
    passing markets, the per-contract files in Norgate units."""
    base = base or base_dir()
    codes = codes or all_markets()
    first = pd.Period(HISTORY_START, "M") + 1
    out, factors = {}, {}
    for code in codes:
        raw = read_raw(code, base)
        if raw.empty:
            out[code] = {"passed": False, "reason": "no Databento history"}
            continue
        pr = compare_prices(code, _norgate_closes(code), raw)
        res = {"prices": pr}
        if pr["factor"] is None:
            out[code] = {**res, "passed": False, "reason": "no common days with the Norgate snapshot"}
            continue
        write_contracts(code, pr["factor"], base)
        md_n = CD.MarketData(code)
        last = min(pd.Period(md_n.latest, "M"), CD.ASSEMBLY_END_MONTH)
        md_n.rolls                                   # computed now, with Norgate's metadata, outside the redirect
        with databento_layout(last, base):
            md_d = CD.MarketData(code)
            ch = compare_chains(md_n, md_d, first, last)
        res["chain"] = ch
        res["P1"] = p1(code, raw)
        reasons = [r for r, bad in (("prices below 99% within one tick", pr["share"] < TOLERANCE_SHARE),
                                    ("F1/F2 chain differs", not ch["equal"])) if bad]
        res["passed"] = not reasons
        if reasons:
            res["reason"] = "; ".join(reasons)
            shutil.rmtree(base / "contracts" / code, ignore_errors=True)
        out[code] = res
        factors[code] = {"factor": pr["factor"], "passed": res["passed"]}
        log(f"{code}: share {pr['share']:.4f} over {pr['common_days']} days, factor {pr['factor']:g}, "
            f"chain {'equal' if ch['equal'] else 'differs'}, P1 T25 {res['P1']['qualifies_T25']} "
            f"T26 {res['P1']['qualifies_T26']}: {'PASS' if res['passed'] else 'FAIL'}")
    u = universes()
    after = {k: [c for c in v if out.get(c, {}).get("passed") and out[c]["P1"][f"qualifies_{k}"]]
             for k, v in u.items()}
    summary = {"checked_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
               "rule": "docs/prereg/T25-T26_live_shadows.md Amendment 1 A1.2 (prices, chain) and §8 P1",
               "tolerance": "one tick", "min_share": TOLERANCE_SHARE, "history_start": HISTORY_START.isoformat(),
               "markets": out, "universe_after_check": after}
    if write:
        (base / "factors.json").write_text(json.dumps(factors, indent=1))
        PRELIVE.parent.mkdir(parents=True, exist_ok=True)
        PRELIVE.write_text(json.dumps(summary, indent=1) + "\n")
    return summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["history", "check", "update"])
    ap.add_argument("--today", default=None)
    a = ap.parse_args(argv)
    today = date.fromisoformat(a.today) if a.today else date.today()
    if a.cmd == "history":
        r = history(today=today)
        print(json.dumps({k: v for k, v in r.items() if k != "stored"}))
        return 1 if r.get("refused") else 0
    if a.cmd == "check":
        if date.today() >= NORGATE_END:
            print("refused: on or after 5 May 2027 the Norgate snapshot is deleted (Amendment 1 A1.2 item 5)")
            return 1
        s = check()
        print(json.dumps(s["universe_after_check"]))
        return 0
    r = update(today=today)
    print("\n".join(r["log"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
