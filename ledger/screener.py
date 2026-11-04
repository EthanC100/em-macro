"""Screener: every country of the v1.0 universe after the monthly rebalance. No API.

    python -m ledger.screener            # after `python -m em_macro.systematic update`
    python -m ledger.screener --today 2026-11-04

From the same inputs and signal code the algorithm uses (em_macro.systematic.build_inputs and
signals, read only; nothing frozen is changed) plus the 13-country monthly panel, the positions
file and the Ledger calendars, it writes
  * results/screener/latest.json and screener_<as_of>.csv (the table), and
  * a report data/ledger/reports/<date>_screener-<as_of>.md (type "screener"),
with, per instrument and country: carry, real carry, value, trend, each signal's rank within
its book, the composite rank, the algorithm's position, upcoming elections and rating reviews
in the next 12 months, and any instrument whose month return was more than two standard
deviations (trailing 36 months) from zero.

Definitions: carry as the algorithm (FX: policy rate minus fed funds, pp; bonds: 10y yield
minus policy rate, pp; spreads: the spread, pp); real carry: FX, the real policy-rate
differential against the US (policy minus CPI inflation, both countries); EM bonds, the real
10y yield (10y minus CPI inflation); spreads, the spread itself. Value and trend are the
algorithm's z-scores (value: FX real exchange rate against its 5-year mean, bonds: the risk
model's mispricing in bp; trend: 12- and 3-month return z-scores). Ranks: 1 = highest within
the book, among instruments with data in the month.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from .marks import CONFIG, load_registry
from .risk import NAME_OF, ledger_calendar
from .schema import parse_date

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "results/screener"
REPORT_DIR = ROOT / "data/ledger/reports"
COLUMNS = ["as_of", "book", "instrument", "country", "iso3", "data_month", "stale", "carry", "real_carry", "value", "trend",
           "carry_z", "value_z", "trend_z", "composite", "rank_carry", "rank_value", "rank_trend", "rank_composite", "n_ranked",
           "position", "size_pct_of_capital", "risk_share_pct", "month_return_pct", "return_sigma", "move_2sd",
           "next_election", "rating_reviews"]


def _f(x, nd=3):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) else round(v, nd)


def _rank(values: dict[str, float | None]) -> dict[str, int | None]:
    have = sorted(((v, k) for k, v in values.items() if v is not None), key=lambda kv: -kv[0])
    out = {k: None for k in values}
    for i, (_, k) in enumerate(have, 1):
        out[k] = i
    return out


def latest_panel(panel_rows: list[dict], iso3: str, month: str, cols: tuple[str, ...]) -> dict:
    """Latest panel row for iso3 at or before ``month`` with all of ``cols`` present."""
    best = None
    for r in panel_rows:
        if r.get("iso3") != iso3 or (r.get("month") or "") > month:
            continue
        if all(_f(r.get(c)) is not None for c in cols) and (best is None or r["month"] > best["month"]):
            best = r
    return best or {}


def compute(inp: dict, positions: list[dict], panel_rows: list[dict], registry: list[dict], calendar: list[dict],
            today: date, as_of: str | None = None, us_real_rate: float | None = None, config: dict = CONFIG) -> dict:
    """The screener table from the algorithm's inputs (see the module docstring)."""
    from em_macro import systematic as SY   # read-only use of the frozen signal code
    import pandas as pd

    months = inp["months"]
    t = pd.Period(as_of, "M") if as_of else months[-1]
    sigma_n = int(config.get("screener_vol_months", 36))
    thresh = float(config.get("screener_sigma", 2.0))
    by_id = {r["instrument"]: r for r in registry}
    pos = {p["instrument"]: p for p in positions}
    horizon_end = date(today.year + 1, today.month, min(today.day, 28))
    elections = {}
    ratings = {}
    for c in calendar:
        if not (today <= c["date"] <= horizon_end) or not c.get("iso3"):
            continue
        if c["kind"] == "election":
            elections.setdefault(c["iso3"], []).append(f"{c['date'].isoformat()} {c['label']}")
        elif c["kind"] in ("rating review", "rating_action"):
            ratings.setdefault(c["iso3"], []).append(f"{c['date'].isoformat()} {c['label']}")
    rows = []
    for book in ("fx", "bond"):
        sig = SY.signals(inp[book])
        ret, carry, value = inp[book]["ret"], inp[book]["carry"], inp[book]["value"]
        comp = pd.concat([sig[k] for k in ("carry", "trend", "value")], keys=["carry", "trend", "value"]).groupby(level=1).mean()
        # ranks at the common month t among instruments with data
        at_t = {k: {inst: _f(sig[k].at[t, inst]) if t in sig[k].index else None for inst in ret.columns} for k in sig}
        at_t["composite"] = {inst: _f(comp.at[t, inst]) if t in comp.index else None for inst in ret.columns}
        ranks = {k: _rank(v) for k, v in at_t.items()}
        n_ranked = sum(v is not None for v in at_t["composite"].values())
        for inst in ret.columns:
            reg = by_id.get(inst, {})
            iso3 = reg.get("iso3", "")
            # the latest month at or before t with a composite signal (data lags by instrument)
            avail = comp[inst].loc[:t].dropna()
            m = avail.index[-1] if len(avail) else None
            stale = bool(m is not None and m < t)
            r_series = ret[inst].loc[:t].dropna()
            rm = r_series.index[-1] if len(r_series) else None
            r_last = _f(r_series.iloc[-1] * 100, 3) if len(r_series) else None
            hist = ret[inst].loc[:rm].iloc[-(sigma_n + 1):-1].dropna() if rm is not None else pd.Series(dtype=float)
            sigma = _f(hist.std() * 100, 3) if len(hist) >= 12 else None
            move = bool(r_last is not None and sigma and abs(r_last) > thresh * sigma)
            pr = latest_panel(panel_rows, iso3, str(t), ("policy_rate", "cpi_yoy")) if iso3 else {}
            real = None
            if book == "fx" and pr and us_real_rate is not None:
                real = round(_f(pr["policy_rate"]) - _f(pr["cpi_yoy"]) - us_real_rate, 3)
            elif book == "bond" and not inst.endswith("-DE"):
                pr2 = latest_panel(panel_rows, iso3, str(t), ("y10", "cpi_yoy")) if iso3 else {}
                if pr2:
                    real = round(_f(pr2["y10"]) - _f(pr2["cpi_yoy"]), 3)
            elif book == "bond" and m is not None:
                real = _f(carry.at[m, inst])
            p = pos.get(inst, {})
            rows.append({
                "as_of": str(t), "book": book, "instrument": inst, "country": reg.get("country", inst), "iso3": iso3,
                "data_month": str(m) if m is not None else "", "stale": stale,
                "carry": _f(carry.at[m, inst]) if m is not None else None, "real_carry": real,
                "value": _f(value.at[m, inst]) if m is not None else None,
                "trend": _f(sig["trend"].at[m, inst]) if m is not None else None,
                "carry_z": _f(sig["carry"].at[m, inst]) if m is not None else None,
                "value_z": _f(sig["value"].at[m, inst]) if m is not None else None,
                "trend_z": _f(sig["trend"].at[m, inst]) if m is not None else None,
                "composite": _f(comp.at[m, inst]) if m is not None else None,
                "rank_carry": ranks["carry"][inst], "rank_value": ranks["value"][inst], "rank_trend": ranks["trend"][inst],
                "rank_composite": ranks["composite"][inst], "n_ranked": n_ranked,
                "position": p.get("side", "") or "none", "size_pct_of_capital": _f(p.get("size_pct_of_capital")),
                "risk_share_pct": _f(p.get("risk_share_pct")),
                "month_return_pct": r_last, "return_sigma": sigma, "move_2sd": move,
                "next_election": "; ".join(elections.get(iso3, [])[:2]), "rating_reviews": "; ".join(ratings.get(iso3, [])[:3]),
            })
    countries = {}
    for r in rows:
        c = countries.setdefault(r["country"], {"country": r["country"], "iso3": r["iso3"], "instruments": [],
                                                "positions": [], "next_election": r["next_election"],
                                                "rating_reviews": r["rating_reviews"], "moves": []})
        c["instruments"].append(r["instrument"])
        if r["position"] != "none":
            c["positions"].append(f"{r['position']} {r['instrument']}")
        if r["move_2sd"]:
            c["moves"].append(r["instrument"])
    return {"as_of": str(t), "generated": today.isoformat(), "rows": rows,
            "countries": sorted(countries.values(), key=lambda c: c["country"]),
            "moves": [r["instrument"] for r in rows if r["move_2sd"]],
            "stale": [r["instrument"] for r in rows if r["stale"] or not r["data_month"]],
            "sigma": thresh, "vol_months": sigma_n, "us_real_rate": us_real_rate}


# ----------------------------------------------------------------------------- outputs
def _fmt(v, nd=2, suffix=""):
    return "—" if v is None else f"{v:.{nd}f}{suffix}"


def report_markdown(res: dict) -> str:
    L = [f"# Screener after the {res['as_of']} rebalance", "",
         f"Generated {res['generated']} from the algorithm's own inputs (data to {res['as_of']}), the 13-country panel, "
         f"`results/systematic/positions.csv` and the Ledger calendars. Ranks are within each book, 1 = highest. "
         f"Instruments marked * have no data for {res['as_of']} and show their latest month.", ""]
    if res["moves"]:
        L += [f"**Moved more than {res['sigma']:g} standard deviations in the month:** " + ", ".join(res["moves"]) + ".", ""]
    else:
        L += [f"No instrument moved more than {res['sigma']:g} standard deviations in the month.", ""]
    if res["stale"]:
        L += ["**Without data for the month (stale or missing):** " + ", ".join(res["stale"]) + ".", ""]
    for book, title in (("fx", "Currencies (vs USD)"), ("bond", "Bonds (10y; spreads over the Bund)")):
        L += [f"## {title}", "",
              "| Country | Instr. | Carry | Real carry | Value | Trend | Rk carry | Rk value | Rk trend | Rk comp. | Position | Month ret. | σ | Next election | Rating review |",
              "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---|---|"]
        for r in sorted((x for x in res["rows"] if x["book"] == book), key=lambda x: (x["rank_composite"] is None, x["rank_composite"] or 0)):
            nm = r["instrument"] + ("*" if r["stale"] or not r["data_month"] else "")
            posn = f"{r['position']} {_fmt(r['size_pct_of_capital'], 1, '%')}" if r["position"] != "none" else "—"
            move = f"{_fmt(r['month_return_pct'], 2, '%')}" + (" ⚠" if r["move_2sd"] else "")
            L.append(f"| {r['country']} | {nm} | {_fmt(r['carry'])} | {_fmt(r['real_carry'])} | {_fmt(r['value'], 3)} | {_fmt(r['trend'])} | "
                     f"{r['rank_carry'] or '—'} | {r['rank_value'] or '—'} | {r['rank_trend'] or '—'} | {r['rank_composite'] or '—'} | {posn} | "
                     f"{move} | {_fmt(r['return_sigma'], 2, '%')} | {r['next_election'] or '—'} | {r['rating_reviews'] or '—'} |")
        L.append("")
    L += ["## Definitions", "",
          "- Carry: FX, policy rate minus fed funds (pp); EM bonds, 10y yield minus policy rate (pp); spreads, the spread over the Bund (pp); Bund, yield minus the ECB rate.",
          f"- Real carry: FX, (policy rate − CPI inflation) minus the same for the US ({_fmt(res['us_real_rate'])}%); EM bonds, 10y yield minus CPI inflation; spreads, the spread.",
          "- Value and trend: the algorithm's signals (value: FX real exchange rate against its 5-year mean, in log points; bonds, the risk model's mispricing in bp; trend: the average of the 12- and 3-month return z-scores).",
          f"- Month return: the instrument's return in the month; σ is the standard deviation of the previous {res['vol_months']} months; ⚠ marks a move beyond {res['sigma']:g}σ.",
          "- Position: the algorithm's position for the coming month (signed % of capital). Elections and rating reviews: next 12 months from data/events/ (upcoming_events.csv, elections.csv, rating_calendar.csv).", ""]
    return "\n".join(L)


def write_outputs(res: dict, root: Path = ROOT) -> list[str]:
    out = root / "results/screener"
    out.mkdir(parents=True, exist_ok=True)
    (out / "latest.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    csv_path = out / f"screener_{res['as_of']}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        for r in res["rows"]:
            w.writerow({k: ("" if v is None else v) for k, v in r.items()})
    rep_dir = root / "data/ledger/reports"
    rep_dir.mkdir(parents=True, exist_ok=True)
    rep = rep_dir / f"{res['generated']}_screener-{res['as_of']}.md"
    header = (f"---\ndate: {res['generated']}\ntitle: Screener after the {res['as_of']} rebalance\ntype: screener\n"
              f"country: Global\n---\n\n")
    rep.write_text(header + report_markdown(res), encoding="utf-8")
    return [str(p.relative_to(root)).replace("\\", "/") for p in (out / "latest.json", csv_path, rep)]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--today", default=None)
    a = ap.parse_args(argv)
    today = parse_date(a.today) if a.today else datetime.now(timezone.utc).date()
    from em_macro import panel_sources as PS
    from em_macro import sources as S
    from em_macro import systematic as SY
    inp = SY.build_inputs()
    us_real = None
    try:
        cpi = PS.bis_cpi_index("US").dropna()
        us_cpi_yoy = float(cpi.iloc[-1] / cpi.iloc[-13] * 100 - 100)
        us_real = round(float(S.fred("DFF").dropna().iloc[-1]) - us_cpi_yoy, 3)
    except Exception as e:  # noqa: BLE001 - real carry for FX is then blank
        print(f"WARNING: US real rate unavailable ({e}); FX real carry left blank")
    with (ROOT / "results/systematic/positions.csv").open(newline="", encoding="utf-8") as f:
        positions = list(csv.DictReader(f))
    with (ROOT / "data/processed/country_month_panel.csv").open(newline="", encoding="utf-8") as f:
        panel_rows = list(csv.DictReader(f))
    res = compute(inp, positions, panel_rows, load_registry(), ledger_calendar(ROOT, today), today, us_real_rate=us_real)
    files = write_outputs(res)
    print(report_markdown(res))
    print("written:", ", ".join(files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
