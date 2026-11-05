#!/usr/bin/env python3
"""Norgate futures: coverage check and per-contract daily CSV export.

Runs on the Windows server where Norgate Data Updater (NDU) is installed and signed in.
The `norgatedata` package reads from NDU's local API (http://localhost:38889), so NDU must be
running. This script holds no credentials and never needs any.

Subcommands
-----------
coverage  List every futures market Norgate offers, then check each target market for
          individual contracts (live and expired) and deferred months >= 12 months out.
          Writes  <out>/all_markets.csv  and  <out>/coverage.csv.
export    Write one CSV per individual contract
          (date,open,high,low,close,volume,open_interest; close is the settlement price) to
          <out>/contracts/<MARKET>/<CONTRACT>.csv, plus <out>/manifest.csv and
          <out>/manifest.json with a SHA-256 hash, byte size, row count and date range for each.
all       coverage, then export (the manifest also hashes coverage.csv and all_markets.csv).

Markets missing from Norgate are recorded as missing, never substituted.

Usage:  python norgate_export.py all --out C:\\norgate-export\\trial_2026-11
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

# Target markets: our code -> Norgate session symbols to try, in order. Only alternative
# spellings of the SAME contract are listed (e.g. ICE Brent), never a different market.
TARGETS: dict[str, list[str]] = {
    "CL": ["CL"], "B": ["B", "BRN"], "HO": ["HO"], "RB": ["RB"], "NG": ["NG"],
    "G": ["G", "GAS"], "HG": ["HG"], "GC": ["GC"], "SI": ["SI"], "PL": ["PL"], "PA": ["PA"],
    "ZC": ["ZC"], "ZS": ["ZS"], "ZW": ["ZW"], "KE": ["KE"], "ZM": ["ZM"], "ZL": ["ZL"],
    "SB": ["SB"], "KC": ["KC"], "CC": ["CC"], "CT": ["CT"],
    "LE": ["LE"], "GF": ["GF"], "HE": ["HE"],
}
MONTH_CODES = "FGHJKMNQUVXZ"
CONTRACT_RE = re.compile(r"-(\d{4})([FGHJKMNQUVXZ])$")
OUT_COLUMNS = ["date", "open", "high", "low", "close", "volume", "open_interest"]
# Norgate field name -> our column name (matched case-insensitively, spaces ignored)
FIELD_MAP = {"open": "open", "high": "high", "low": "low", "close": "close",
             "volume": "volume", "openinterest": "open_interest"}
DEFERRED_MONTHS_REQUIRED = 12
EXPIRY_GRACE_DAYS = 5  # a contract is "live" if quoted within this many days of the market's latest date


def _nd():
    try:
        import norgatedata
    except ImportError:
        sys.exit("norgatedata is not installed: python -m pip install norgatedata")
    return norgatedata


def call(fn, *args, **kwargs):
    """Call a norgatedata function. It raises ValueError for unknown symbols and calls
    sys.exit() when NDU cannot be reached, so turn both into ordinary results."""
    try:
        return fn(*args, **kwargs), None
    except SystemExit:
        return None, "NDU not reachable (is Norgate Data Updater running?)"
    except Exception as e:  # noqa: BLE001 - record and continue
        return None, f"{type(e).__name__}: {e}".strip(": ")


def parse_contract(symbol: str):
    m = CONTRACT_RE.search(symbol)
    if not m:
        return None
    return int(m.group(1)), MONTH_CODES.index(m.group(2)) + 1


def to_date(value):
    if value is None or value == "":
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(str(value)[:10])


def safe_name(symbol: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", symbol)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------- coverage
def list_markets(nd):
    sessions, err = call(nd.futures_market_session_symbols)
    if err:
        sys.exit(f"cannot list futures markets: {err}")
    rows = []
    for s in sessions:
        name, _ = call(nd.futures_market_session_name, s)
        stype, _ = call(nd.futures_market_session_type, s)
        exch, _ = call(nd.exchange_name, s)
        rows.append({"session_symbol": s, "name": name or "", "session_type": stype or "",
                     "exchange": exch or ""})
    return rows


def market_contracts(nd, session_symbol: str):
    """Return [(symbol, year, month, first_date, last_date)] for one market, sorted by delivery."""
    syms, err = call(nd.futures_market_session_contracts, session_symbol)
    if err:
        return [], err
    out = []
    for s in syms:
        ym = parse_contract(s)
        if ym is None:
            continue
        first, _ = call(nd.first_quoted_date, s)
        last, _ = call(nd.last_quoted_date, s)
        out.append((s, ym[0], ym[1], to_date(first), to_date(last)))
    out.sort(key=lambda r: (r[1], r[2]))
    return out, None


def coverage(nd, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    markets = list_markets(nd)
    with open(out / "all_markets.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["session_symbol", "name", "session_type", "exchange"])
        w.writeheader()
        w.writerows(markets)
    available = {m["session_symbol"] for m in markets}
    names = {m["session_symbol"]: m["name"] for m in markets}

    cov, resolved = [], {}
    for code, candidates in TARGETS.items():
        sym = next((c for c in candidates if c in available), None)
        row = {"market": code, "norgate_symbol": sym or "", "name": names.get(sym, ""),
               "status": "", "contracts": 0, "expired": 0, "live": 0,
               "first_contract": "", "last_contract": "", "first_date": "", "last_date": "",
               "furthest_live_months_out": "", "deferred_12m": "", "note": ""}
        if sym is None:
            row["status"] = "MISSING"
            row["note"] = "not in Norgate futures market list (tried: " + ", ".join(candidates) + ")"
            cov.append(row)
            continue
        contracts, err = market_contracts(nd, sym)
        if err or not contracts:
            row["status"] = "NO_CONTRACTS"
            row["note"] = err or "market listed but no individual contracts returned"
            cov.append(row)
            continue
        resolved[code] = (sym, contracts)
        last_dates = [c[4] for c in contracts if c[4]]
        firsts = [c[3] for c in contracts if c[3]]
        as_of = max(last_dates) if last_dates else None
        live = [c for c in contracts if c[4] and as_of and (as_of - c[4]).days <= EXPIRY_GRACE_DAYS]
        expired = [c for c in contracts if c not in live]
        row.update(contracts=len(contracts), expired=len(expired), live=len(live),
                   first_contract=contracts[0][0], last_contract=contracts[-1][0],
                   first_date=str(min(firsts)) if firsts else "", last_date=str(as_of or ""))
        if live and as_of:
            far = max(live, key=lambda c: (c[1], c[2]))
            months_out = (far[1] * 12 + far[2]) - (as_of.year * 12 + as_of.month)
            row["furthest_live_months_out"] = months_out
            row["deferred_12m"] = "yes" if months_out >= DEFERRED_MONTHS_REQUIRED else "no"
        else:
            row["deferred_12m"] = "no"
        problems = []
        if not expired:
            problems.append("no expired contracts")
        if row["deferred_12m"] != "yes":
            problems.append(f"no live contract >= {DEFERRED_MONTHS_REQUIRED} months out")
        row["status"] = "OK" if not problems else "GAP"
        row["note"] = "; ".join(problems)
        cov.append(row)

    with open(out / "coverage.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(cov[0].keys()))
        w.writeheader()
        w.writerows(cov)
    print(f"{len(markets)} futures markets available in Norgate")
    print(f"{'market':6} {'symbol':7} {'status':12} {'contr':>5} {'exp':>4} {'live':>4} {'mo_out':>6}  note")
    for r in cov:
        print(f"{r['market']:6} {r['norgate_symbol']:7} {r['status']:12} {r['contracts']:>5} "
              f"{r['expired']:>4} {r['live']:>4} {str(r['furthest_live_months_out']):>6}  {r['note']}")
    return resolved


# --------------------------------------------------------------------------- export
def export_contract(nd, symbol: str, path: Path):
    df, err = call(nd.price_timeseries, symbol,
                   stock_price_adjustment_setting=nd.StockPriceAdjustmentType.NONE,
                   padding_setting=nd.PaddingType.NONE,
                   timeseriesformat="pandas-dataframe")
    if err:
        return None, err
    colmap, missing = {}, []
    norm = {re.sub(r"\s+", "", c).lower(): c for c in df.columns}
    for key, ours in FIELD_MAP.items():
        if key in norm:
            colmap[ours] = norm[key]
        else:
            missing.append(ours)
    path.parent.mkdir(parents=True, exist_ok=True)
    n, first, last = 0, None, None
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(OUT_COLUMNS)
        for idx, rec in df.iterrows():
            d = to_date(idx.to_pydatetime() if hasattr(idx, "to_pydatetime") else idx)
            vals = []
            for c in OUT_COLUMNS[1:]:
                v = rec[colmap[c]] if c in colmap else None
                vals.append("" if v is None or v != v else (repr(float(v)) if c not in ("volume", "open_interest") else str(int(v))))
            w.writerow([d.isoformat()] + vals)
            n += 1
            first = first or d
            last = d
    return {"rows": n, "first_date": str(first or ""), "last_date": str(last or ""),
            "missing_fields": ",".join(missing)}, None


def export(nd, out: Path, resolved):
    entries, errors = [], []
    for code, (sym, contracts) in resolved.items():
        for c in contracts:
            rel = Path("contracts") / code / f"{safe_name(c[0])}.csv"
            info, err = export_contract(nd, c[0], out / rel)
            if err:
                errors.append({"market": code, "contract": c[0], "error": err})
                continue
            entries.append({"file": rel.as_posix(), "market": code, "norgate_symbol": sym,
                            "contract": c[0], **info})
        print(f"{code}: exported {sum(e['market'] == code for e in entries)} contracts")
    for extra in ("coverage.csv", "all_markets.csv"):
        if (out / extra).exists():
            entries.append({"file": extra, "market": "", "norgate_symbol": "", "contract": "",
                            "rows": "", "first_date": "", "last_date": "", "missing_fields": ""})
    for e in entries:
        p = out / e["file"]
        e["bytes"] = p.stat().st_size
        e["sha256"] = sha256(p)
    fields = ["file", "market", "norgate_symbol", "contract", "rows", "first_date", "last_date",
              "missing_fields", "bytes", "sha256"]
    with open(out / "manifest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(entries)
    nd_version = getattr(nd, "__version__", "")
    meta = {"generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "source": "Norgate Data via norgatedata " + nd_version,
            "columns": OUT_COLUMNS, "close_is": "settlement price", "adjustment": "none",
            "files": len(entries), "total_bytes": sum(e["bytes"] for e in entries),
            "errors": errors, "entries": entries}
    (out / "manifest.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"wrote {len(entries)} files, {meta['total_bytes']:,} bytes; {len(errors)} errors")
    for e in errors:
        print("  ERROR", e)
    return meta


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["coverage", "export", "all"])
    ap.add_argument("--out", required=True, type=Path, help="output directory")
    ap.add_argument("--markets", nargs="*", help="limit to these target codes (default: all)")
    a = ap.parse_args(argv)
    if a.markets:
        unknown = set(a.markets) - set(TARGETS)
        if unknown:
            ap.error(f"unknown market codes: {sorted(unknown)}")
        for k in list(TARGETS):
            if k not in a.markets:
                del TARGETS[k]
    nd = _nd()
    resolved = coverage(nd, a.out)
    if a.command in ("export", "all"):
        export(nd, a.out, resolved)


if __name__ == "__main__":
    main()
