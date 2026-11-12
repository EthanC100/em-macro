"""Commodities: a Ledger book that runs the T26 shadow (the T22 diversified futures trend sleeve) at paper size.

Config change C12 (docs/config_changes.md). The book is a scaled reading of the shadow, nothing more:

- **Returns** = the T26 shadow's monthly net returns (decisive costs) x ``K``. ``K`` is fixed once, now, so that the
  T22 design-period backtest (2000-01..2019-12) runs at 10% annual volatility: ``K = 0.10 / 0.090675 = 1.1028``
  (see ``K_DERIVATION``). Signals, universe, timing, costs and rules are the shadow's, unchanged.
- **Read-only on the shadow.** The book reads the shadow's public output (``results/shadows/GO_LIVE.json`` and
  ``results/shadows/T26/``) and never writes to it. The pre-registration, its amendments and the prelive files are
  untouched; the 2031 evaluation reads the shadow's own returns, which sizing does not change.
- **Paper capital US$100,000,000**, used only to turn weights into contract counts. Every result is in %, excess of
  cash, with total return including T-bill interest shown as in the other books (ledger/books.py, display only).
- **Starts with the shadows:** positions from the first live rebalance's settlement (M1, 3 December 2026), once
  ledger-daily confirms go-live. Before then the book shows "Starts 3 Dec 2026".
- **Outside the Horizons fund**, like my decisions. The Fund rule (C04) is unchanged.

    EM_MACRO_DATA=... python -m ledger.commodities update   # ledger-daily: contract counts and risk shares
    python -m ledger.commodities status

``update`` runs where the private store is (ledger-daily). It reads the private Databento contract files to turn
the shadow's weights into whole contracts, and writes ``data/commodities/positions.csv``: market, direction,
contract month, number of contracts and share of risk. No settlement, price or notional in currency is written;
contract counts are the only figures derived from a price.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRIAL = "T26"
NAME = "Commodities"
K = 1.1028                                   # frozen by C12; never re-estimated
TARGET_VOL_PCT = 10.0
CAPITAL_USD = 100_000_000
K_DERIVATION = {
    "rule": "K = 10% / annual volatility of the T22 design-period backtest (2000-01..2019-12), rounded to 4 decimals",
    "source": "results/T20-T22/monthly_net.csv, column 'T22 sleeve|full|decisive' (net of decisive costs, the "
              "a160bfd universe); the same figure as results/T20-T22/performance.csv",
    "source_sha256": "8d6ba711db9742a5489494e4fc1d3c3eacd544b1cb24eccb5cef6f2306515e6b",
    "months": 240,
    "ann_vol_pct": 9.0675,                   # sample SD (ddof 1) of the 240 monthly returns x sqrt(12)
    "k_exact": 1.1028433,
    "k": K,
    "vol_at_k_pct": 9.9996,
    "why_not_the_restricted_universe": "No backtest of the 17-market T26 universe exists, and the T25-T26 "
                                       "pre-registration (§2.2 D3, §6) forbids computing one, so K comes from the "
                                       "design-period run of the same sleeve on its full a160bfd universe.",
}
NOTE = ("A trend-following futures book. Each month, on the 3rd, it looks at 17 futures markets (energy, metals, "
        "grains and three currencies) and goes long the ones whose prices have risen over the last 1, 3 and 12 months "
        "and short the ones that have fallen, sized so that each market contributes similar risk and the whole book "
        "aims at about 10% volatility a year. It is the pre-registered T26 shadow of the T22 trend sleeve, run "
        "unchanged, with every weight multiplied by one fixed factor (k = 1.1028, set once so the sleeve's 2000-2019 "
        "backtest would have run at 10% volatility) and turned into whole contracts on a US$100m paper account. "
        "Sizing changes nothing the shadow measures: its 2031 evaluation uses the shadow's own returns, which this book "
        "only reads. Results are in % of capital, net of the shadow's decisive cost model (twice the estimated "
        "commission and slippage). Paper only; outside the Horizons fund.")


# ----------------------------------------------------------------------------- read-only inputs
def paths(root: Path = ROOT) -> dict[str, Path]:
    sh = root / "results" / "shadows"
    return {"go_live": sh / "GO_LIVE.json", "status": sh / TRIAL / "status.json", "monthly": sh / TRIAL / "monthly.csv",
            "index": sh / TRIAL / "index.csv", "positions": sh / TRIAL / "positions.csv",
            "book_positions": root / "data" / "commodities" / "positions.csv"}


def _json(p: Path) -> dict | None:
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _csv(p: Path) -> list[dict]:
    if not p.exists():
        return []
    with p.open(newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def start_date(go_live: dict | None) -> date:
    """The 3rd of the first live month (M1): the rebalance whose settlement the book's first positions use."""
    m1 = (go_live or {}).get("M1") or "2026-12"
    return date(int(m1[:4]), int(m1[5:7]), 3)


def is_live(root: Path = ROOT) -> bool:
    p = paths(root)
    g, st = _json(p["go_live"]), _json(p["status"])
    return bool(g and g.get("confirmed") and st and (st.get("months_live") or 0) >= 1 and p["monthly"].exists())


# ----------------------------------------------------------------------------- returns: K x the shadow, exactly
def book_monthly(shadow_rows: list[dict]) -> list[dict]:
    """Each month's book return = K x the shadow's monthly net return at decisive costs (both in %)."""
    out = []
    for r in shadow_rows:
        s = float(r["net_decisive_%"])
        out.append({"month": r["month"], "shadow_net_pct": s, "book_net_pct": K * s})
    return out


def _prev_weekday(d: date) -> date:
    d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def book_series(index_rows: list[dict], monthly: list[dict]) -> list[list]:
    """Daily excess-of-cash index, 100 on the business day before the first live day. Within a month the book moves
    K x the shadow's month-to-date return; each month's last point is exactly K x the shadow's monthly return,
    compounded month by month."""
    if not index_rows:
        return []
    mret = {r["month"]: r["book_net_pct"] / 100 for r in monthly}
    pts = [(r["date"], float(r["index_net_decisive"])) for r in index_rows]
    last_of_month = {}
    for d, _ in pts:
        last_of_month[d[:7]] = d
    out = [[_prev_weekday(date.fromisoformat(pts[0][0])).isoformat(), 100.0]]
    book_base, shadow_base, cur = 100.0, 100.0, pts[0][0][:7]
    prev_shadow_close = 100.0
    for d, s in pts:
        m = d[:7]
        if m != cur:                                   # a new month: rebase on last month's closing points
            book_base, shadow_base, cur = out[-1][1], prev_shadow_close, m
        if d == last_of_month[m] and m in mret:
            b = book_base * (1 + mret[m])
        else:
            b = book_base * (1 + K * (s / shadow_base - 1))
        out.append([d, round(b, 6)])
        prev_shadow_close = s
    return out


def drawdown(series: list[list]) -> list[list]:
    out, peak = [], None
    for d, v in series:
        peak = v if peak is None else max(peak, v)
        out.append([d, round(100 * (v / peak - 1), 4)])
    return out


def realised_vol(series: list[list], window: int | None = None) -> float | None:
    """Annualised SD of daily returns (sqrt 252), over the last ``window`` days or since the start; None below
    10 returns."""
    v = [p[1] for p in series]
    r = [b / a - 1 for a, b in zip(v, v[1:]) if a]
    if window:
        r = r[-window:]
    if len(r) < 10:
        return None
    m = sum(r) / len(r)
    return round(100 * math.sqrt(sum((x - m) ** 2 for x in r) / (len(r) - 1)) * math.sqrt(252), 3)


def rolling_vol(series: list[list], window: int = 63) -> list[list]:
    out = []
    for i in range(10, len(series)):
        v = realised_vol(series[max(0, i - window):i + 1])
        if v is not None:
            out.append([series[i][0], v])
    return out


# ----------------------------------------------------------------------------- positions (ledger-daily, private)
def update(root: Path = ROOT, base: Path | None = None, out: Path | None = None, log=print) -> dict:
    """Contract counts and risk shares for the shadow's current rebalance, from the private Databento contract
    files. Reads the shadow's public output; writes only ``data/commodities/positions.csv`` (no price)."""
    p = paths(root)
    out = out or p["book_positions"]
    if not is_live(root):
        log(f"{NAME}: not live yet (starts {start_date(_json(p['go_live'])):%d %b %Y}); nothing written")
        return {"written": False}
    import pandas as pd
    from em_macro import commod_data as CD
    from em_macro import t2022 as T
    from em_macro import t2526 as M
    st = _json(p["status"])
    month = st.get("last_rebalance")
    rows = [r for r in _csv(p["positions"]) if r["month"] == month and float(r["held_weight"] or 0) != 0]
    if not rows:
        return _write_positions(out, [], month, log)
    m = pd.Period(month, "M")
    mks = M.load_markets(sorted({r["market"] for r in rows}), m, base)   # read-only, process-local layout
    recs, risks = [], {}
    for r in rows:
        c, w = r["market"], float(r["held_weight"])
        mk = mks.get(c)
        if mk is None or m not in mk.rolls.index:
            log(f"{c}: no private contract files for {month}: count not computed")
            recs.append({**_base_row(r, w), "contracts": "", "risk_share_pct": ""})
            continue
        ex, dec = mk.rolls.at[m, "execution"], mk.rolls.at[m, "decision"]
        F = mk.md.settle(r["contract"], ex)                  # private: used here and never written
        mult = mk.m.tick_value / mk.m.tick
        n = round(K * w * CAPITAL_USD / (F * mult)) if F and F == F else None
        sig = T.asof(mk.sigma_mop(), dec)
        risks[c] = abs(K * w) * sig if sig == sig else None
        recs.append({**_base_row(r, w), "contracts": "" if n is None else str(abs(int(n))), "risk_share_pct": ""})
    tot = sum(v for v in risks.values() if v)
    for rec in recs:
        v = risks.get(rec["market"])
        rec["risk_share_pct"] = f"{100 * v / tot:.2f}" if v and tot else ""
    return _write_positions(out, recs, month, log)


def _base_row(r: dict, w: float) -> dict:
    from em_macro import commod_data as CD
    y, mo = CD.parse_contract(r["contract"])
    return {"month": r["month"], "market": r["market"], "name": CD.MARKETS[r["market"]].name,
            "direction": "long" if w > 0 else "short", "contract": r["contract"], "contract_month": f"{y:04d}-{mo:02d}",
            "book_weight": f"{K * w:.6f}"}


POSITION_COLUMNS = ["month", "market", "name", "direction", "contract", "contract_month", "contracts", "risk_share_pct",
                    "book_weight"]


def _write_positions(out: Path, recs: list[dict], month: str | None, log) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=POSITION_COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows([{k: r.get(k, "") for k in POSITION_COLUMNS} for r in recs])
    log(f"{NAME}: {len(recs)} positions for {month} written (contract counts and risk shares only)")
    return {"written": True, "month": month, "n": len(recs)}


# ----------------------------------------------------------------------------- the app's book
def build(today: date | None = None, root: Path = ROOT, total_return: bool = True) -> dict:
    """commodities.json for the app, from public files only."""
    today = today or date.today()
    p = paths(root)
    g = _json(p["go_live"])
    start = start_date(g)
    base = {"name": NAME, "label": "Commodities: the T26 trend shadow at paper size", "trial": TRIAL, "k": K,
            "k_derivation": K_DERIVATION, "target_vol_pct": TARGET_VOL_PCT, "capital_usd": CAPITAL_USD,
            "start": start.isoformat(), "note": NOTE, "in_fund": False, "config_change": "C12",
            "universe": (g or {}).get("universe", {}).get(TRIAL, []),
            "evaluation": (g or {}).get("first_evaluation"), "as_of": today.isoformat()}
    if not is_live(root):
        return {**base, "live": False, "status": f"Starts {start.day} {start:%b %Y}", "series": [], "monthly": [],
                "positions": [], "drawdown": []}
    st = _json(p["status"])
    monthly = book_monthly(_csv(p["monthly"]))
    series = book_series(_csv(p["index"]), monthly)
    dd = drawdown(series)
    pos = [r for r in _csv(p["book_positions"]) if r.get("month") == st.get("last_rebalance")]
    if not pos:                                         # counts not computed yet: the shadow's weights, no counts
        pos = [{**{k: "" for k in POSITION_COLUMNS}, "month": r["month"], "market": r["market"],
                "direction": "long" if float(r["held_weight"]) > 0 else "short", "contract": r["contract"],
                "book_weight": f"{K * float(r['held_weight']):.6f}"}
               for r in _csv(p["positions"]) if r["month"] == st.get("last_rebalance") and float(r["held_weight"] or 0)]
    cum = 1.0
    for r in monthly:
        cum *= 1 + r["book_net_pct"] / 100
    obj = {**base, "live": True, "status": "live", "series": series, "index": series[-1][1] if series else 100.0,
           "since_start_pct": round(series[-1][1] - 100, 4) if series else 0.0,
           "monthly": [{**r, "month": r["month"]} for r in monthly], "drawdown": dd,
           "max_drawdown_pct": min((d[1] for d in dd), default=0.0),
           "vol": {"since_start_pct": realised_vol(series), "last_3m_pct": realised_vol(series, 63),
                   "monthly_since_start_pct": _monthly_vol(monthly), "target_pct": TARGET_VOL_PCT},
           "rolling_vol": rolling_vol(series), "months_live": st.get("months_live"),
           "last_rebalance": st.get("last_rebalance"), "positions": pos,
           "dropped": st.get("dropped", {}), "index_as_of": st.get("index_as_of")}
    from .books import mtd
    obj["mtd_pct"] = mtd(series, today)
    if total_return:
        from .books import MarkBook, add_total_return
        add_total_return(obj, MarkBook(), today)
    return obj


def _monthly_vol(monthly: list[dict]) -> float | None:
    r = [x["book_net_pct"] for x in monthly]
    if len(r) < 6:
        return None
    m = sum(r) / len(r)
    return round(math.sqrt(sum((x - m) ** 2 for x in r) / (len(r) - 1)) * math.sqrt(12), 3)


def build_safe(today: date) -> dict:
    """The app's commodities.json; a failure here never stops the Ledger build."""
    try:
        return build(today)
    except Exception as e:  # noqa: BLE001
        return {"name": NAME, "live": False, "status": "error", "errors": [repr(e)[:300]], "k": K, "note": NOTE,
                "series": [], "monthly": [], "positions": [], "drawdown": []}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["update", "status"])
    a = ap.parse_args(argv)
    if a.cmd == "update":
        update()
        return 0
    b = build(total_return=False)
    print(json.dumps({k: b.get(k) for k in ("live", "status", "k", "start", "months_live", "index", "last_rebalance")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
