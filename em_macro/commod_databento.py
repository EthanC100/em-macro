"""Build 0 test A5: Databento cross-check of F1/F2 settlements for the CME-group markets from 2010-06-06.

    EM_MACRO_DATA=... DATABENTO_API_KEY=... python -m em_macro.commod_databento quote     # cost quotes only
    EM_MACRO_DATA=... DATABENTO_API_KEY=... python -m em_macro.commod_databento run       # quote, download, compare

Source: Databento GLBX.MDP3 (CME Globex MDP 3.0), schema `statistics`, stat_type 3 (settlement price); for each
contract and trading date (ts_ref) the last settlement record received is used (CME publishes preliminary then
final settlements).  Daily OHLCV bars are not used because their close is the last trade of a UTC day, not the
settlement that Norgate's close is.

Spending guard: every historical request is quoted with metadata.get_cost first; the run stops before a request
that would take this session's spend above SESSION_CAP_USD.  Each quote and request is logged privately.

Days compared: for each rebalance month m with decision date on or after 2010-06-07, the F1(m) and F2(m)
contracts on every market day d with decision(m) <= d < decision(m+1) (the days on which each contract serves as F1
or F2), where both sources have a settlement.  Agreement = |Norgate - Databento x scale| <= one tick (+1e-9).
Downloaded settlements and per-day comparisons are written only to the private data repo.
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np
import pandas as pd

from . import commod_data as CD

DATASET = "GLBX.MDP3"
SCHEMA = "statistics"
START = pd.Timestamp("2010-06-07")       # first full trading day after the dataset start (2010-06-06, a Sunday)
END_MONTH = pd.Period("2026-09", "M")
SESSION_CAP_USD = 40.0
CME_COMMODITIES = [c for c in CD.COMMODITIES if CD.MARKETS[c].cme_group]
# Globex root where it differs from our code (none for the commodity markets)
GLOBEX_ROOT = {}


def raw_symbol(code: str, contract: str, digits: int = 1) -> str:
    """Globex raw symbol: root + month code + year (one digit; two for markets listed 10+ years out, e.g. NGX26)."""
    y, m = CD.parse_contract(contract)
    return f"{GLOBEX_ROOT.get(code, code)}{CD.MONTH_CODES[m - 1]}{y % 10 ** digits:0{digits}d}"


def resolve_symbols(reqs: list[dict]) -> None:
    """For each request pick, per contract, the raw-symbol form Databento resolves over the request's dates
    (one-digit year first, then two-digit); contracts not found in either form are recorded and skipped."""
    c = client()
    for q in reqs:
        cand = {}
        for con in q["contracts"]:
            for dgt in (1, 2):
                cand[raw_symbol(q["market"], con, dgt)] = con
        r = c.symbology.resolve(dataset=DATASET, symbols=list(cand), stype_in="raw_symbol",
                                stype_out="instrument_id", start_date=q["start"], end_date=q["end"])
        found = {k for k, v in r.get("result", {}).items() if v} - set(r.get("not_found", []))
        chosen = {}
        for sym, con in cand.items():
            if sym in found and con not in chosen.values():
                chosen[sym] = con
        q["map"] = chosen
        q["symbols"] = sorted(chosen)
        q["not_found"] = sorted(set(q["contracts"]) - set(chosen.values()))


def private_dir():
    d = CD.derived_dir() / "databento"
    d.mkdir(parents=True, exist_ok=True)
    return d


def plan(code: str, md: CD.MarketData | None = None) -> tuple[pd.DataFrame, list[dict]]:
    """(days table, requests).  days: one row per (contract, role, day) to compare."""
    md = md or CD.MarketData(code)
    r = md.rolls.dropna(subset=["F1"])
    days = md.close.index
    rows = []
    months = list(r.index)
    for k, m in enumerate(months[:-1]):
        if m > END_MONTH:
            break
        t0, t1 = r.at[m, "decision"], r.at[months[k + 1], "decision"]
        if t0 < START:
            continue
        win = days[(days >= t0) & (days < t1)]
        for role in ("F1", "F2"):
            c = r.at[m, role]
            if c is None:
                continue
            for d in win:
                rows.append({"market": code, "month": str(m), "role": role, "contract": c, "date": d})
    tab = pd.DataFrame(rows)
    reqs = []
    tab["year"] = tab["date"].dt.year
    for y, g in tab.groupby("year"):
        reqs.append({"market": code, "year": int(y), "contracts": sorted(set(g["contract"])),
                     "start": g["date"].min().strftime("%Y-%m-%d"),
                     "end": (g["date"].max() + pd.Timedelta(days=1)).strftime("%Y-%m-%d")})
    return tab.drop(columns="year"), reqs


class Spend:
    def __init__(self, cap: float = SESSION_CAP_USD):
        self.cap = cap
        self.ledger = private_dir() / "ledger.jsonl"
        self.spent = 0.0
        self.lock = __import__("threading").Lock()
        if self.ledger.exists():   # earlier requests of this session (same ledger)
            for line in self.ledger.read_text().splitlines():
                rec = json.loads(line)
                if rec.get("downloaded"):
                    self.spent += float(rec["quote"])

    def log(self, rec: dict):
        with self.ledger.open("a") as f:
            f.write(json.dumps(rec) + "\n")


def client():
    import databento as db
    return db.Historical(os.environ["DATABENTO_API_KEY"])


def quote_all(reqs: list[dict]) -> float:
    c = client()
    total = 0.0
    resolve_symbols(reqs)
    for q in reqs:
        if not q["symbols"]:
            q["quote"], q["error"] = 0.0, "no symbol resolved"
            print(f"[A5] {q['market']} {q['year']}: no symbol resolved", file=sys.stderr)
            continue
        try:
            cost = c.metadata.get_cost(dataset=DATASET, symbols=q["symbols"], stype_in="raw_symbol",
                                       schema=SCHEMA, start=q["start"], end=q["end"])
        except Exception as e:  # noqa: BLE001 - symbols not on Globex for that period
            q["quote"], q["error"] = 0.0, str(e).splitlines()[0]
            print(f"[A5] {q['market']} {q['year']}: {q['error']}", file=sys.stderr)
            continue
        q["quote"] = float(cost)
        total += float(cost)
    return total


def _previous_symbols(spend: Spend, market: str, year: int) -> set[str]:
    out = set()
    if spend.ledger.exists():
        for line in spend.ledger.read_text().splitlines():
            rec = json.loads(line)
            if rec.get("downloaded") and rec.get("market") == market and rec.get("year") == year:
                out |= set(rec.get("symbols", []))
    return out


def _fetch(c, q: dict, spend: Spend, cache) -> pd.DataFrame:
    """Cached per market-year; when the plan now needs contracts that an earlier request did not cover (a changed
    roll table), only those are requested (quoted first) and appended."""
    import hashlib
    f = cache / f"{q['market']}_{q['year']}.csv"
    have = None
    if f.exists():
        files = [f] + sorted(cache.glob(f"{q['market']}_{q['year']}_extra_*.csv"))
        have = pd.concat([pd.read_csv(x, parse_dates=["date"]) for x in files], ignore_index=True)
        missing = sorted(set(q["symbols"]) - _previous_symbols(spend, q["market"], q["year"]))
        if not missing:
            return have
        q = {**q, "symbols": missing, "map": {k: v for k, v in q["map"].items() if k in missing}}
        tag = hashlib.sha256(",".join(missing).encode()).hexdigest()[:10]
        f = cache / f"{q['market']}_{q['year']}_extra_{tag}.csv"
    kw = dict(dataset=DATASET, symbols=q["symbols"], stype_in="raw_symbol", schema=SCHEMA,
              start=q["start"], end=q["end"])
    cost = float(c.metadata.get_cost(**kw))            # quoted before every request
    with spend.lock:
        if spend.spent + cost > spend.cap:
            spend.log({**q, "quote": cost, "downloaded": False, "reason": "session cap"})
            raise RuntimeError(f"stop: request {q['market']} {q['year']} (US${cost:.4f}) would take the session "
                               f"spend above US${spend.cap:.2f} (spent US${spend.spent:.4f})")
        spend.spent += cost                               # reserved before the request is sent
    for attempt in range(3):                              # transient connection resets: retry the same request
        try:
            data = c.timeseries.get_range(**kw)
            break
        except Exception as e:  # noqa: BLE001
            if attempt == 2:
                raise
            print(f"[A5] retry {q['market']} {q['year']}: {str(e)[:80]}", file=sys.stderr)
            time.sleep(5 * (attempt + 1))
    with spend.lock:
        spend.log({**{k: v for k, v in q.items() if k != "map"}, "quote": cost, "downloaded": True,
                   "time": time.time()})
    df = data.to_df(map_symbols=True)
    if len(df):
        df = df[df["stat_type"] == 3].sort_values("ts_recv")
        df = df.groupby(["symbol", "ts_ref"]).tail(1)
        s = pd.DataFrame({"contract": df["symbol"].map(q["map"]).values,
                          "date": pd.to_datetime(df["ts_ref"]).dt.tz_localize(None).dt.normalize().values,
                          "settle": df["price"].astype(float).values})
    else:
        s = pd.DataFrame(columns=["contract", "date", "settle"])
    s.to_csv(f, index=False)
    return s if have is None else pd.concat([have, s], ignore_index=True)


def download(reqs: list[dict], spend: Spend, workers: int = 10) -> dict[str, pd.DataFrame]:
    """Quote-then-fetch every request (parallel; the spend check is serialised).  Returns market -> settlements."""
    from concurrent.futures import ThreadPoolExecutor
    c = client()
    cache = private_dir() / "settlements"
    cache.mkdir(exist_ok=True)
    todo = [q for q in reqs if not q.get("error")]
    with ThreadPoolExecutor(workers) as ex:
        frames = list(ex.map(lambda q: (q["market"], _fetch(c, q, spend, cache)), todo))
    out: dict[str, list] = {}
    for m, f in frames:
        out.setdefault(m, []).append(f)
    return {m: pd.concat(v, ignore_index=True) for m, v in out.items()}


def compare(code: str, md: CD.MarketData, tab: pd.DataFrame, dbn: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    tab = tab.copy()
    tab["norgate"] = [md.settle(c, d) for c, d in zip(tab["contract"], tab["date"])]
    dbn = dbn.dropna(subset=["contract"]).drop_duplicates(["contract", "date"], keep="last")
    tab = tab.merge(dbn, on=["contract", "date"], how="left").rename(columns={"settle": "databento"})
    both = tab.dropna(subset=["norgate", "databento"])
    both = both[both["databento"] != 0]
    ratio = (both["norgate"] / both["databento"]).abs()
    scale = float(10 ** np.round(np.log10(ratio.median()))) if len(ratio) else 1.0
    tick = CD.MARKETS[code].tick
    tab["diff_ticks"] = (tab["norgate"] - tab["databento"] * scale).abs() / tick
    tab["agree"] = tab["diff_ticks"] <= 1 + 1e-6
    ok = tab.dropna(subset=["norgate", "databento"])
    res = {"days_planned": int(len(tab)), "days_compared": int(len(ok)),
           "norgate_missing": int(tab["norgate"].isna().sum()),
           "databento_missing": int((tab["norgate"].notna() & tab["databento"].isna()).sum()),
           "scale": scale, "agree_share": float(ok["agree"].mean()) if len(ok) else None,
           "agree_share_F1": float(ok[ok.role == "F1"]["agree"].mean()) if len(ok) else None,
           "agree_share_F2": float(ok[ok.role == "F2"]["agree"].mean()) if len(ok) else None,
           "disagree_days": int((~ok["agree"]).sum()),
           "max_diff_ticks": float(ok["diff_ticks"].max()) if len(ok) else None}
    res["pass"] = res["agree_share"] is not None and res["agree_share"] >= 0.99
    return res, tab


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["quote", "run"])
    ap.add_argument("--markets", nargs="*", default=CME_COMMODITIES)
    a = ap.parse_args(argv)
    mds, tabs, reqs = {}, {}, []
    for code in a.markets:
        print(f"[A5] plan {code}", file=sys.stderr, flush=True)
        mds[code] = CD.MarketData(code)
        tabs[code], rq = plan(code, mds[code])
        reqs += rq
    total = quote_all(reqs)
    print(f"[A5] {len(reqs)} requests, total quoted cost US${total:.4f}", file=sys.stderr)
    spend = Spend()
    if a.cmd == "quote":
        return
    if spend.spent + total > SESSION_CAP_USD:
        sys.exit(f"stop: quoted total US${total:.4f} + spent US${spend.spent:.4f} exceeds the session cap")
    results = {}
    allset = download(reqs, spend)
    for code in a.markets:
        dbn = allset.get(code, pd.DataFrame(columns=["contract", "date", "settle"]))
        res, tab = compare(code, mds[code], tabs[code], dbn)
        tab.to_csv(private_dir() / f"A5_compare_{code}.csv", index=False)
        results[code] = res
        print(f"[A5] {code}: compared {res['days_compared']} agree {res['agree_share']:.4f}", file=sys.stderr)
    results["_not_found"] = {f"{q['market']} {q['year']}": q["not_found"] for q in reqs if q.get("not_found")}
    results["_spend_usd_session"] = spend.spent
    results["_requests"] = len(reqs)
    results["_quoted_total_usd"] = total
    out = CD.ROOT / "results" / "T20-T22" / "build0_a5.json"
    out.write_text(json.dumps(results, indent=1))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
