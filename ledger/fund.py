"""The Horizons fund: a combined view built from the separate books (docs/fund/allocation.md).

Read only. The fund is computed from the books' published daily indices on every build and written to the app's
fund.json. It never writes a figure into any book: v1.1's, Janus's and my records are unchanged and keep their own
P&L.

- **Members and risk shares.** Algorithm v1.1 80% and Janus 20% at the start (amendment of 2026-11-07 to config
  change C04, set before any Janus call resolved). My own decisions (Me) are outside the fund.
- **Combination by risk.** At each month start, each member's weight is proportional to its risk share divided by
  its trailing volatility. The volatility is the standard deviation of the member's monthly returns over up to the
  last 12 completed months, annualised with sqrt(12). Weights are normalised to sum to 1, so the fund is not
  levered. Until every member has 6 completed months of live data, the weights are the risk shares themselves
  (capital shares). Weights are held fixed through the month, and the fund's daily return is the weighted sum of
  the members' daily returns.
- **Janus's risk share** changes only by the rule in docs/fund/allocation.md (config change C04, amended
  2026-11-07), evaluated at each month start on data to the previous month end. It is 5% while Janus's drawdown
  from its peak exceeds 10%, overriding everything else. Otherwise, once Janus has at least 30 resolved calls
  (every position records a market probability, 50 where no market-implied one exists): 30% if its total net P&L
  (after costs) on those calls is positive and its Brier score is lower than the market's; 10% if that P&L is
  negative or its Brier score is higher than the market's. From config changes C08 and C09 (2026-11-11) a resolved
  call is one call per correlation cluster of forced forecasts per non-overlapping 20-trading-day window, scored on
  the mean Brier of its forecasts (``fund_calls`` in Janus's summary), and the P&L on those calls is Janus's net
  P&L from 10 November 2026. Otherwise (fewer than 30 calls, or a tie on either
  measure without a failure on the other) it stays at its starting 20%. The algorithm takes the rest.
- **Start.** The fund starts on the first date every member is live (v1.1: the 3 December 2026 rebalance, index
  100 on 30 November 2026).
- **Correlation** of monthly returns between the books (Me included for information) once two books share at
  least 6 completed months.
"""
from __future__ import annotations

import math
from datetime import date, timedelta

SHARES = {"algorithm v1.1": 0.80, "janus": 0.20}          # starting risk shares (C04 as amended 2026-11-07)
JANUS_START, JANUS_UP, JANUS_LOW, JANUS_DOWN = 0.20, 0.30, 0.10, 0.05
MIN_RESOLVED_CALLS = 30
# Config change C08 (2026-11-11), as amended by C09 before any forecast was made: Janus's resolved calls are its
# forced forecasts counted as one call per correlation cluster per non-overlapping 20-trading-day window, each scored
# on the mean Brier of its forecasts (ledger/janus.py fund_calls), and the P&L on them is Janus's net P&L after costs
# from the end of the day before C08 (10 November 2026) to the evaluation date
C08_FROM = date(2026, 11, 11)
DRAWDOWN_LIMIT_PCT = 10.0
MIN_MONTHS_FOR_VOL, VOL_WINDOW_MONTHS = 6, 12
MIN_MONTHS_FOR_CORR = 6
RULE_DOC = "docs/fund/allocation.md"


def _d(x) -> date:
    return x if isinstance(x, date) else date.fromisoformat(str(x)[:10])


def bdays(start: date, end: date) -> list[date]:
    out, d = [], start
    while d <= end:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def level_on(series: list[list], d: date) -> float | None:
    """The index on ``d``: its last point on or before ``d`` (carried forward)."""
    best = None
    for p in series:
        if _d(p[0]) <= d:
            best = float(p[1])
        else:
            break
    return best


def month_ends(series: list[list], start: date, upto: date) -> list[tuple[str, float]]:
    """[(YYYY-MM, index at that month's last point)] for completed months after ``start`` up to ``upto``."""
    import calendar as _cal
    out: dict[str, float] = {}
    for p in series:
        d = _d(p[0])
        month_end = date(d.year, d.month, _cal.monthrange(d.year, d.month)[1])
        if start <= d <= upto and month_end <= upto:          # completed months only
            out[d.strftime("%Y-%m")] = float(p[1])
    return sorted(out.items())


def monthly_returns(series: list[list], start: date, upto: date) -> dict[str, float]:
    """Completed-month returns from the index: the first month is measured from the index at ``start``."""
    base = level_on(series, start)
    out, prev = {}, base
    for m, v in month_ends(series, start, upto):
        if prev:
            out[m] = v / prev - 1
        prev = v
    return out


def stdev(xs: list[float]) -> float | None:
    if len(xs) < 2:
        return None
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def corr(a: list[float], b: list[float]) -> float | None:
    if len(a) < 2:
        return None
    sa, sb = stdev(a), stdev(b)
    if not sa or not sb:
        return None
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / ((len(a) - 1) * sa * sb)


def drawdown_pct(series: list[list], upto: date) -> float:
    """Current drawdown (%) from the peak of the index, on data up to ``upto``."""
    pts = [float(p[1]) for p in series if _d(p[0]) <= upto]
    if not pts:
        return 0.0
    return round(100 * (1 - pts[-1] / max(pts)), 4)


def janus_record(closed: list[dict], upto: date) -> dict:
    """The rule's inputs from Janus's resolved calls closed on or before ``upto``."""
    calls = [c for c in closed if c.get("close") and _d(c["close"]["date"]) <= upto]
    elig = [c for c in calls if c.get("market_probability") not in (None, "")]
    def brier(p, c):
        return (float(p) / 100.0 - (1.0 if c["close"]["outcome"] == "right" else 0.0)) ** 2
    bj = sum(brier(c["probability"], c) for c in elig) / len(elig) if elig else None
    bm = sum(brier(c["market_probability"], c) for c in elig) / len(elig) if elig else None
    net = sum(float(c["close"]["net_pnl_pct"]) for c in elig)
    return {"resolved_calls": len(calls), "calls_with_market_probability": len(elig),
            "net_pnl_pct_on_those_calls": round(net, 4), "brier_janus": round(bj, 4) if bj is not None else None,
            "brier_market": round(bm, 4) if bm is not None else None}


def janus_record_c08(calls: list[dict], janus_series: list[list], upto: date) -> dict:
    """The rule's inputs under C08/C09 (docs/fund/allocation.md): the resolved calls are the counted cluster calls whose
    window ends on or before ``upto``; Janus's Brier is the mean of the calls' Brier scores (each the mean over the
    cluster's forecasts, from p_final), the market's likewise from market_probability; the net P&L is the change in
    Janus's equity index (net of costs, % of the starting account) from 10 November 2026 to ``upto``."""
    cs = [c for c in calls if c.get("end_date") and _d(c["end_date"]) <= upto]
    bj = sum(float(c["brier_final"]) for c in cs) / len(cs) if cs else None
    bm = sum(float(c["brier_market"]) for c in cs) / len(cs) if cs else None
    a, b = level_on(janus_series, C08_FROM - timedelta(days=1)), level_on(janus_series, upto)
    net = (b - a) if (a is not None and b is not None) else 0.0
    return {"resolved_calls": len(cs), "calls_with_market_probability": len(cs),
            "net_pnl_pct_on_those_calls": round(net, 4), "brier_janus": round(bj, 4) if bj is not None else None,
            "brier_market": round(bm, 4) if bm is not None else None,
            "definition": "C09: one call per correlation cluster per non-overlapping 20-trading-day window"}


def janus_share(closed: list[dict], janus_series: list[list], upto: date, calls: list[dict] | None = None) -> dict:
    """Janus's risk share at a month start (docs/fund/allocation.md, C04 as amended 2026-11-07). ``calls``: the C08
    resolved calls (``fund_calls`` in Janus's summary); when given they replace the closed positions (C08)."""
    rec = janus_record(closed, upto) if calls is None else janus_record_c08(calls, janus_series, upto)
    dd = drawdown_pct(janus_series, upto) if janus_series else 0.0
    n, net, bj, bm = (rec["calls_with_market_probability"], rec["net_pnl_pct_on_those_calls"], rec["brier_janus"],
                      rec["brier_market"])
    stats = (f"{n} resolved calls, net P&L {net:+.2f}%, Brier {bj:.3f} vs market {bm:.3f}"
             if bj is not None and bm is not None else f"{n} resolved calls")
    if dd > DRAWDOWN_LIMIT_PCT:
        share, why = JANUS_DOWN, f"drawdown {dd:.1f}% exceeds {DRAWDOWN_LIMIT_PCT:g}% (overrides the others)"
    elif n < MIN_RESOLVED_CALLS:
        share, why = JANUS_START, f"starting share: {n} of {MIN_RESOLVED_CALLS} resolved calls needed for 30% or 10%"
    elif net > 0 and bj < bm:
        share, why = JANUS_UP, f"{stats}: positive P&L and a better Brier score than the market"
    elif net < 0 or bj > bm:
        share, why = JANUS_LOW, (f"{stats}: " + " and ".join(x for x, bad in (("negative P&L", net < 0),
                                                                             ("a worse Brier score than the market",
                                                                              bj > bm)) if bad))
    else:
        share, why = JANUS_START, f"{stats}: a tie on P&L or Brier, so neither 30% nor 10% applies (starting share)"
    return {"share": share, "reason": why, "drawdown_pct": dd, **rec}


def _month_starts(start: date, end: date) -> list[date]:
    out, d = [start], date(start.year + (start.month == 12), start.month % 12 + 1, 1)
    while d <= end:
        out.append(d)
        d = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return out


def build_fund(books: dict, today: date) -> dict:
    """``books`` is ledger.books.build_books's output (read only)."""
    v11 = next(v for v in books["algorithm"]["versions"] if v["id"] == "v1.1")
    members = {"algorithm v1.1": {"series": [p[:2] for p in v11.get("series") or []], "live_start": v11.get("live_start"),
                                  "is_live": bool(v11.get("is_live") or v11.get("series"))},
               "janus": {"series": books["janus"].get("series") or [], "live_start": books["janus"].get("live_start"),
                         "is_live": bool(books["janus"].get("series"))}}
    closed = (books["janus"].get("summary") or {}).get("closed") or []
    calls = (books["janus"].get("summary") or {}).get("fund_calls")         # C08: forced forecasts, when present
    base = {"name": "Horizons fund", "members": list(SHARES), "outside": ["me"], "rule_doc": RULE_DOC,
            "initial_shares": SHARES, "note": __doc__.split("\n\n", 1)[1].strip()}
    starts = [m["live_start"] for m in members.values()]
    if not all(starts) or not all(m["is_live"] for m in members.values()):
        pending = [k for k, m in members.items() if not m["is_live"] or not m["live_start"]]
        return {**base, "live": False, "live_start": max((s for s in starts if s), default=None), "series": [],
                "status": f"waiting for {', '.join(pending)} to go live",
                "allocation": _allocation(members, closed, books, today, None, calls),
                "correlation": correlations(books, today)}
    start = max(_d(s) for s in starts)
    if start > today:
        return {**base, "live": False, "live_start": start.isoformat(), "series": [],
                "status": f"starts {start.isoformat()} (when every member is live)",
                "allocation": _allocation(members, closed, books, today, None, calls),
                "correlation": correlations(books, today)}
    days = bdays(start, today)
    idx, series, history = 100.0, [[start.isoformat(), 100.0]], []
    months = _month_starts(start, today)
    w = None
    for d0, d1 in zip(days, days[1:]):
        ms = max(m for m in months if m <= d1)
        if not history or history[-1]["from"] != ms.isoformat():
            alloc = _weights(members, closed, ms - timedelta(days=1) if ms > start else start, start, calls)
            history.append({"from": ms.isoformat(), **alloc})
            w = alloc["weights"]
        r = 0.0
        for k, m in members.items():
            a, b = level_on(m["series"], d0), level_on(m["series"], d1)
            if a and b:
                r += w[k] * (b / a - 1)
        idx *= 1 + r
        series.append([d1.isoformat(), round(idx, 4)])
    month_start = today.replace(day=1)
    before = [p for p in series if _d(p[0]) < month_start]
    mtd = round(series[-1][1] - (before[-1][1] if before else 100.0), 4)
    return {**base, "live": True, "live_start": start.isoformat(), "series": series, "index": series[-1][1],
            "mtd_pct": mtd, "since_start_pct": round(series[-1][1] - 100, 4), "history": history,
            "allocation": history[-1] if history else _allocation(members, closed, books, today, start, calls),
            "correlation": correlations(books, today), "status": "live"}


def _weights(members: dict, closed: list[dict], upto: date, start: date, calls: list[dict] | None = None) -> dict:
    js = janus_share(closed, members["janus"]["series"], upto, calls)
    shares = {"algorithm v1.1": round(1 - js["share"], 4), "janus": js["share"]}
    vols = {}
    for k, m in members.items():
        mr = monthly_returns(m["series"], _d(m["live_start"]), upto)
        xs = list(mr.values())[-VOL_WINDOW_MONTHS:]
        sd = stdev(xs) if len(mr) >= MIN_MONTHS_FOR_VOL else None
        vols[k] = {"ann_vol_pct": round(100 * sd * math.sqrt(12), 3) if sd else None, "months": len(mr)}
    if all(v["ann_vol_pct"] for v in vols.values()):
        raw = {k: shares[k] / vols[k]["ann_vol_pct"] for k in shares}
        tot = sum(raw.values())
        weights, basis = {k: round(v / tot, 6) for k, v in raw.items()}, "risk (risk share / trailing volatility)"
    else:
        weights, basis = dict(shares), (f"capital shares (fewer than {MIN_MONTHS_FOR_VOL} completed months of data: "
                                        + ", ".join(f"{k} {v['months']}" for k, v in vols.items()) + ")")
    return {"as_of": upto.isoformat(), "risk_shares": shares, "weights": weights, "basis": basis, "vol": vols,
            "janus_rule": js}


def _allocation(members: dict, closed: list[dict], books: dict, today: date, start: date | None,
                calls: list[dict] | None = None) -> dict:
    """The allocation the rule gives today (shown before the fund starts)."""
    out = _weights({k: {**m, "live_start": m["live_start"] or today.isoformat()} for k, m in members.items()},
                   closed, today, start or today, calls)
    return {"from": None, **out}


def correlations(books: dict, today: date) -> dict:
    v11 = next(v for v in books["algorithm"]["versions"] if v["id"] == "v1.1")
    ser = {"algorithm v1.1": ([p[:2] for p in v11.get("series") or []], v11.get("live_start")),
           "janus": (books["janus"].get("series") or [], books["janus"].get("live_start")),
           "me": (books["me"].get("series") or [], books["me"].get("live_start"))}
    mr = {k: monthly_returns(s, _d(st), today) if s and st else {} for k, (s, st) in ser.items()}
    keys = list(ser)
    pairs = []
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            common = sorted(set(mr[a]) & set(mr[b]))
            c = corr([mr[a][m] for m in common], [mr[b][m] for m in common]) if len(common) >= MIN_MONTHS_FOR_CORR else None
            pairs.append({"a": a, "b": b, "months": len(common), "corr": round(c, 3) if c is not None else None})
    return {"pairs": pairs, "min_months": MIN_MONTHS_FOR_CORR, "basis": "monthly returns, completed months",
            "enough": any(p["corr"] is not None for p in pairs)}
