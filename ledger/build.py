"""Build the Ledger static site: read the repository's plain files, write JSON and the
site under app/.

    python -m ledger.build            # writes app/
    python -m ledger.build --out DIR  # writes elsewhere (tests)

Sources (read only, never written):
  data/ledger/decisions.csv, data/ledger/forecasts.csv, data/ledger/reports/
  trials.csv
  results/systematic/paper_pnl.csv, positions.csv, test/performance_2020_on.csv,
  test/TEST_RUN.json, fit/performance_2005_2019.csv, overrides_log.csv
  results/*.md (research write-ups, listed as reports)
  data/elections/calendar.csv and data/elections/signals.csv if they exist, otherwise
  data/events/elections.csv + data/events/upcoming_events.csv and
  results/repricing/signals_daily.csv
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .schema import (DECISION_OUTCOMES, FORECAST_OUTCOMES, REPORT_TYPES, kelly_size_pct,
                     parse_date, parse_number, parse_probability)
from .scoring import (calibration_bins, cumulative, score_decision, score_forecast)

ROOT = Path(__file__).resolve().parents[1]
SITE_SRC = ROOT / "ledger" / "site"
REPO_URL = "https://github.com/ethanc100/em-macro"
RELEASE_URL = f"{REPO_URL}/releases/tag/v1.0-frozen"
FREEZE_COMMIT = "7886867"
# The v1.0 live record starts with the first rebalance after the freeze (3 Nov 2026), whose positions are
# effective for November 2026. Months after the test period (2020-01 to the freeze month) and before
# LIVE_START_MONTH are a pre-live gap: shown on charts as "pre-live (not counted)", excluded from the live
# and backtest statistics. See docs/config_changes.md.
LIVE_START_MONTH = "2026-11"
LIVE_SINCE = "2026-11-03"
# The live account index is 100 at the end of the month before LIVE_START_MONTH (October 2026) and moves only
# with live months. Backtest and pre-live months keep their own history index (100 at the end of the freeze month).
ACCOUNT_INDEX_LABEL = "Account index (start = 100, live from Nov 2026)"
# US$ equivalent of the account index. Before the switch: US$100,000 x index / 100. The switch is the
# 3 December 2026 rebalance, i.e. when the positions effective from 2026-12 are published (keyed on the
# positions' effective month, not the calendar, so a late run switches when it actually happens). New capital
# enters at the index level of the switch, so from it: US$10,000,000 x index / index_at_switch, where
# index_at_switch is the account index at the end of the month before the switch's effective month (the
# month that rebalance books). The dollar figure starts at exactly US$10,000,000; percentages are unaffected.
USD_INITIAL_CAPITAL = 100_000.0
USD_SWITCH_CAPITAL = 10_000_000.0
USD_SWITCH_EFFECTIVE_MONTH = "2026-12"
USD_SWITCH_REBALANCE = "2026-12-03"
USD_SWITCH_NOTE = "Paper capital raised to US$10,000,000 (configuration change, not performance)"


def _prev_month(m: str) -> str:
    y, mm = int(m[:4]), int(m[5:7])
    return f"{y - 1}-12" if mm == 1 else f"{y}-{mm - 1:02d}"


def usd_account(months: list[dict], effective_from: str | None) -> dict:
    """US$ value of the live account index, with new capital entering at the index level of the switch."""
    live_rows = [m for m in months if m.get("live")]
    index = live_rows[-1]["account_index"] if live_rows else 100.0
    switched = (effective_from or "") >= USD_SWITCH_EFFECTIVE_MONTH
    if not switched:
        return {"account_usd": round(USD_INITIAL_CAPITAL * index / 100.0, 2), "usd_capital": USD_INITIAL_CAPITAL,
                "usd_switched": False, "index_at_switch": None, "usd_switch_month": None,
                "usd_switch_note": None}
    switch_month = _prev_month(USD_SWITCH_EFFECTIVE_MONTH)
    at = next((m["account_index"] for m in months
               if m["month"] == switch_month and m.get("account_index") is not None), None)
    index_at_switch = at if at is not None else index
    return {
        "account_usd": round(USD_SWITCH_CAPITAL * index / index_at_switch, 2), "usd_capital": USD_SWITCH_CAPITAL,
        "usd_switched": True, "index_at_switch": index_at_switch, "usd_switch_month": switch_month,
        # shown on the Home tile while the switch rebalance's positions are the current ones
        "usd_switch_note": USD_SWITCH_NOTE if (effective_from or "") == USD_SWITCH_EFFECTIVE_MONTH else None,
    }

COUNTRY_OF = {
    "BRL": "Brazil", "BR10Y": "Brazil", "MXN": "Mexico", "MX10Y": "Mexico",
    "ZAR": "South Africa", "ZA10Y": "South Africa", "TRY": "Turkey", "TR10Y": "Turkey",
    "IDR": "Indonesia", "ID10Y": "Indonesia", "PLN": "Poland", "PL-DE": "Poland",
    "EUR": "Euro area", "FR-DE": "France", "IT-DE": "Italy", "ES-DE": "Spain",
    "DE10Y": "Germany", "GBP": "United Kingdom", "GB-DE": "United Kingdom",
    "COP": "Colombia", "CO10Y": "Colombia", "CLP": "Chile", "CL10Y": "Chile",
}
ISO3 = {"BRA": "Brazil", "MEX": "Mexico", "ZAF": "South Africa", "TUR": "Turkey",
        "IDN": "Indonesia", "POL": "Poland", "FRA": "France", "ITA": "Italy", "ESP": "Spain",
        "DEU": "Germany", "GBR": "United Kingdom", "COL": "Colombia", "CHL": "Chile",
        "USA": "United States"}
COUNTRY_NAMES = sorted(set(ISO3.values()) | {"Euro area"}, key=len, reverse=True)


# ----------------------------------------------------------------------------- helpers
def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def fnum(x, nd=4):
    v = parse_number(x) if not isinstance(x, (int, float)) else float(x)
    return None if v is None else round(v, nd)


def git(*args) -> str | None:
    try:
        out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=30)
        return out.stdout.strip() if out.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def git_last_date(path: str) -> str | None:
    return git("log", "-1", "--format=%as", "--", path) or None


def git_first_date(path: str) -> str | None:
    out = git("log", "--diff-filter=A", "--follow", "--format=%as", "--", path)
    return out.splitlines()[-1] if out else None


def slug(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:60] or "report"


def iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def guess_country(text: str) -> str:
    for name in COUNTRY_NAMES:
        if re.search(rf"\b{re.escape(name)}\b", text, re.I):
            return name
    return ""


# ----------------------------------------------------------------------------- decisions
def build_decisions(today: date) -> dict:
    rows = read_csv(ROOT / "data/ledger/decisions.csv")
    out = []
    for r in rows:
        sc = score_decision(r)
        prob = parse_probability(r.get("probability"))
        horizon = parse_date(r.get("horizon"))
        d = {**r}
        d.update({
            "size_pct": fnum(r.get("size_pct"), 3),
            "probability": prob,
            "claude_probability": parse_probability(r.get("claude_probability")),
            "date": iso(parse_date(r.get("date"))),
            "horizon": iso(horizon),
            "resolved_date": iso(parse_date(r.get("resolved_date"))),
            "entry_level": fnum(r.get("entry_level"), 4),
            "exit_price": fnum(r.get("exit_price"), 4),
            "stop_level": fnum(r.get("stop"), 4),
            "status": (r.get("status") or "open").strip().lower(),
            "outcome": (r.get("outcome") or "").strip().lower(),
            "kind": "position" if r.get("action") in ("Buy", "Sell") else "no trade",
            "kelly_cap_pct": kelly_size_pct(prob) if prob is not None else None,
            "days_to_horizon": (horizon - today).days if horizon else None,
            "brier": sc["brier"],
            "brier_claude": sc["brier_claude"],
            "pnl_pct": sc["pnl_pct"],
            "issue_url": f"{REPO_URL}/issues/{r['issue']}" if r.get("issue") else None,
        })
        out.append(d)
    out.sort(key=lambda d: (d["date"] or "", d["id"]), reverse=True)
    resolved = [d for d in out if d["status"] == "resolved"]
    briers = [d["brier"] for d in resolved]
    pnls = [d["pnl_pct"] for d in resolved if d["pnl_pct"] is not None]
    summary = {
        "n": len(out), "open": sum(d["status"] == "open" for d in out), "resolved": len(resolved),
        "right": sum(d["outcome"] == "right" for d in resolved),
        "wrong": sum(d["outcome"] == "wrong" for d in resolved),
        "brier": cumulative(briers)["mean"], "brier_n": cumulative(briers)["n"],
        "pnl_pct_total": round(sum(pnls), 3) if pnls else None,
        "countries": sorted({d["country"] for d in out if d["country"]}),
        "outcomes": list(DECISION_OUTCOMES),
    }
    return {"items": out, "summary": summary}


# ----------------------------------------------------------------------------- forecasts
def build_forecasts(today: date) -> dict:
    rows = read_csv(ROOT / "data/ledger/forecasts.csv")
    out = []
    for r in rows:
        sc = score_forecast(r)
        rd = parse_date(r.get("resolution_date"))
        f = {**r}
        f.update({
            "date": iso(parse_date(r.get("date"))),
            "resolution_date": iso(rd),
            "resolved_date": iso(parse_date(r.get("resolved_date"))),
            "my_prob": parse_probability(r.get("my_prob")),
            "market_prob": parse_probability(r.get("market_prob")),
            "claude_prob": parse_probability(r.get("claude_prob")),
            "status": (r.get("status") or "open").strip().lower(),
            "outcome": (r.get("outcome") or "").strip().lower(),
            "days_to_resolution": (rd - today).days if rd else None,
            "outcome01": sc["outcome01"],
            "brier_me": sc["brier_me"], "brier_market": sc["brier_market"],
            "brier_claude": sc["brier_claude"],
            "issue_url": f"{REPO_URL}/issues/{r['issue']}" if r.get("issue") else None,
        })
        out.append(f)
    out.sort(key=lambda f: (f["date"] or "", f["id"]))
    resolved = [f for f in out if f["outcome01"] is not None]
    # cumulative Brier on the same forecasts: only those where all present scorers have a value
    same = [f for f in resolved if f["brier_market"] is not None]
    cum = {
        "me": cumulative([f["brier_me"] for f in same]),
        "market": cumulative([f["brier_market"] for f in same]),
        "claude": cumulative([f["brier_claude"] if f["brier_claude"] is not None else None for f in same]),
        "ids": [f["id"] for f in same],
    }
    # Claude is scored on the subset where Claude gave a number; report that n separately
    claude_same = [f for f in same if f["brier_claude"] is not None]
    cum["claude_vs"] = {
        "n": len(claude_same),
        "me": cumulative([f["brier_me"] for f in claude_same])["mean"],
        "market": cumulative([f["brier_market"] for f in claude_same])["mean"],
        "claude": cumulative([f["brier_claude"] for f in claude_same])["mean"],
    }
    calib = {
        "me": calibration_bins([(f["my_prob"], f["outcome01"]) for f in resolved if f["my_prob"] is not None]),
        "market": calibration_bins([(f["market_prob"], f["outcome01"]) for f in resolved if f["market_prob"] is not None]),
        "claude": calibration_bins([(f["claude_prob"], f["outcome01"]) for f in resolved if f["claude_prob"] is not None]),
    }
    summary = {"n": len(out), "open": sum(f["status"] == "open" for f in out), "resolved": len(resolved),
               "outcomes": list(FORECAST_OUTCOMES)}
    return {"items": out, "summary": summary, "cumulative": cum, "calibration": calib}


# ----------------------------------------------------------------------------- algorithm
def perf_stats(nets: list[float]) -> dict:
    n = len(nets)
    if n == 0:
        return {"months": 0}
    import math
    mean = sum(nets) / n
    var = sum((x - mean) ** 2 for x in nets) / (n - 1) if n > 1 else 0.0
    vol = math.sqrt(var) * math.sqrt(12)
    cum = 1.0
    peak, mdd = 1.0, 0.0
    for x in nets:
        cum *= 1 + x
        peak = max(peak, cum)
        mdd = min(mdd, cum / peak - 1)
    ann = cum ** (12 / n) - 1 if n else None
    return {
        "months": n,
        "total_return_pct": round((cum - 1) * 100, 3),
        "ann_return_pct": round(ann * 100, 3) if ann is not None else None,
        "ann_vol_pct": round(vol * 100, 3),
        "sharpe": round(mean * 12 / vol, 3) if vol > 0 else None,
        "max_drawdown_pct": round(mdd * 100, 3),
        "hit_rate_pct": round(100 * sum(x > 0 for x in nets) / n, 1),
        "mean_month_pct": round(mean * 100, 3),
        "best_month_pct": round(max(nets) * 100, 3),
        "worst_month_pct": round(min(nets) * 100, 3),
    }


def build_algorithm() -> dict:
    pnl = read_csv(ROOT / "results/systematic/paper_pnl.csv")
    positions = read_csv(ROOT / "results/systematic/positions.csv")
    perf_test = read_csv(ROOT / "results/systematic/test/performance_2020_on.csv")
    perf_fit = read_csv(ROOT / "results/systematic/fit/performance_2005_2019.csv")
    overrides = read_csv(ROOT / "results/systematic/overrides_log.csv")
    adjustments = read_csv(ROOT / "results/systematic/position_adjustments.csv")
    run_path = ROOT / "results/systematic/test/TEST_RUN.json"
    test_run = json.loads(run_path.read_text()) if run_path.exists() else {}
    freeze_month = test_run.get("last_month", "2026-09")

    months = []
    for r in pnl:
        m = r.get("month")
        if not m or m < "2020-01":
            continue
        net = fnum(r.get("final_net") or r.get("net"), 6)
        sample = r.get("sample", "")
        live = m >= LIVE_START_MONTH
        pre_live = freeze_month < m < LIVE_START_MONTH
        phase = "live" if live else ("pre_live" if pre_live else "backtest")
        months.append({
            "month": m, "net": net, "model_net": fnum(r.get("model_net"), 6),
            "override_pnl": fnum(r.get("override_pnl"), 6), "fx_gross": fnum(r.get("fx_gross"), 6),
            "bond_gross": fnum(r.get("bond_gross"), 6), "cost": fnum(r.get("cost"), 6),
            "carry_basket": fnum(r.get("carry_basket"), 6), "sp500_tr": fnum(r.get("sp500_tr"), 6),
            "gross_leverage": fnum(r.get("gross_leverage"), 3), "sample": sample, "live": live,
            "pre_live": pre_live, "phase": phase,
        })
    # cumulative and drawdown from 2020-01, index 100 at the end of the freeze month
    cum, peak = 1.0, 1.0
    cum_at_freeze = None
    for row in months:
        cum *= 1 + (row["net"] or 0.0)
        peak = max(peak, cum)
        row["cumulative"] = round(cum, 6)
        row["drawdown_pct"] = round((cum / peak - 1) * 100, 3)
        if row["month"] == freeze_month:
            cum_at_freeze = cum
    if cum_at_freeze is None and months:
        cum_at_freeze = months[-1]["cumulative"]
    # history index (backtest and pre-live only; figures as before): 100 at the end of the freeze month
    for row in months:
        row["account_value"] = (round(100 * row["cumulative"] / cum_at_freeze, 3)
                                if cum_at_freeze and not row["live"] else None)
    # live account index: 100 at the end of the month before LIVE_START_MONTH, then live months only
    base_rows = [r for r in months if r["month"] < LIVE_START_MONTH]
    cum_at_live_start = base_rows[-1]["cumulative"] if base_rows else 1.0
    live_base_month = base_rows[-1]["month"] if base_rows else None
    for row in months:
        if row["live"]:
            row["account_index"] = round(100 * row["cumulative"] / cum_at_live_start, 3)
        elif row["month"] == live_base_month:
            row["account_index"] = 100.0
        else:
            row["account_index"] = None
    live_rows = [r for r in months if r["live"]]
    backtest_rows = [r for r in months if r["phase"] == "backtest"]
    pre_live_rows = [r for r in months if r["phase"] == "pre_live"]
    live_stats = perf_stats([r["net"] for r in live_rows if r["net"] is not None])
    backtest_stats = perf_stats([r["net"] for r in backtest_rows if r["net"] is not None])

    def perf_row(rows, strategy="combined", books="both books"):
        for r in rows:
            if r.get("strategy") == strategy and r.get("books") == books:
                return {k: (fnum(v, 4) if k not in ("strategy", "books", "start", "end", "months") else v)
                        for k, v in r.items()}
        return None

    frozen = {
        "test_2020_on": perf_row(perf_test),
        "design_2005_2019": perf_row(perf_fit),
        "test_rows": [{k: (fnum(v, 4) if k not in ("strategy", "books", "start", "end", "months") else v)
                       for k, v in r.items()} for r in perf_test],
        "test_run_utc": test_run.get("run_utc"), "freeze_month": freeze_month,
    }
    pos = []
    for p in positions:
        inst = p.get("instrument", "")
        pos.append({
            **{k: p.get(k) for k in ("as_of", "effective_from", "book", "instrument", "description", "side")},
            "country": COUNTRY_OF.get(inst, inst),
            "sleeve": "Currencies" if p.get("book") == "fx" else "Bonds",
            "size_pct_of_capital": fnum(p.get("size_pct_of_capital"), 3),
            "risk_share_pct": fnum(p.get("risk_share_pct"), 3),
            "instrument_vol_pct": fnum(p.get("instrument_vol_pct"), 3),
            "carry_z": fnum(p.get("carry_z"), 3), "trend_z": fnum(p.get("trend_z"), 3),
            "value_z": fnum(p.get("value_z"), 3), "cost_pct_per_trade": fnum(p.get("cost_pct_per_trade"), 3),
        })
    by_country: dict[str, dict] = {}
    for p in pos:
        c = by_country.setdefault(p["country"], {"country": p["country"], "risk_share_pct": 0.0,
                                                 "gross_pct": 0.0, "positions": []})
        c["risk_share_pct"] = round(c["risk_share_pct"] + (p["risk_share_pct"] or 0), 3)
        c["gross_pct"] = round(c["gross_pct"] + abs(p["size_pct_of_capital"] or 0), 3)
        c["positions"].append(f"{p['side']} {p['instrument']}")
    by_sleeve = {}
    for p in pos:
        s = by_sleeve.setdefault(p["sleeve"], {"sleeve": p["sleeve"], "risk_share_pct": 0.0,
                                               "gross_pct": 0.0, "n": 0})
        s["risk_share_pct"] = round(s["risk_share_pct"] + (p["risk_share_pct"] or 0), 3)
        s["gross_pct"] = round(s["gross_pct"] + abs(p["size_pct_of_capital"] or 0), 3)
        s["n"] += 1
    rebalance_date = git_last_date("results/systematic/positions.csv")
    as_of = positions[0].get("as_of") if positions else None
    effective_from = positions[0].get("effective_from") if positions else None
    return {
        "months": months, "live": live_stats, "backtest": backtest_stats, "frozen": frozen,
        "account_index_label": ACCOUNT_INDEX_LABEL,
        "positions": pos,
        "by_country": sorted(by_country.values(), key=lambda c: -c["risk_share_pct"]),
        "by_sleeve": sorted(by_sleeve.values(), key=lambda s: s["sleeve"]),
        "rebalance": {"date": rebalance_date, "as_of": as_of, "effective_from": effective_from,
                      "live_since": LIVE_SINCE, "live_start_month": LIVE_START_MONTH,
                      "n_live_months": len(live_rows),
                      "pre_live_months": [r["month"] for r in pre_live_rows],
                      "live_base_month": live_base_month},
        "overrides": overrides, "adjustments": adjustments,
        "release_url": RELEASE_URL, "freeze_commit": FREEZE_COMMIT,
        "freeze_doc_url": f"{REPO_URL}/blob/main/docs/v1.0_freeze.md",
        "gross_leverage": months[-1]["gross_leverage"] if months else None,
    }


# ----------------------------------------------------------------------------- trials
def trial_status(r: dict) -> str:
    res = (r.get("result") or "").strip().lower()
    dec = (r.get("decision") or "").strip().lower()
    if res.startswith("fail") or "rejected" in dec or "not adopted" in dec or dec.startswith("null"):
        return "fail"
    if "kept" in dec or "pass" in dec or res.startswith("pass"):
        return "pass"
    if "pending" in dec or not dec:
        return "pending"
    return "fail"


def build_trials() -> dict:
    rows = read_csv(ROOT / "trials.csv")
    items = []
    for r in rows:
        items.append({**r, "status": trial_status(r),
                      "counted": str(r.get("counted_in_spec_N7", "")).lower() == "true"})
    items.sort(key=lambda t: t.get("trial_id", ""))
    summary = {"n": len(items), "pass": sum(t["status"] == "pass" for t in items),
               "fail": sum(t["status"] == "fail" for t in items),
               "pending": sum(t["status"] == "pending" for t in items),
               "counted_n7": sum(t["counted"] for t in items)}
    return {"items": items, "summary": summary, "source": "trials.csv",
            "updated": git_last_date("trials.csv")}


# ----------------------------------------------------------------------------- elections
def build_elections(today: date) -> dict:
    cal_path = ROOT / "data/elections/calendar.csv"
    sig_path = ROOT / "data/elections/signals.csv"
    sources = []
    calendar = []
    if cal_path.exists():
        sources.append("data/elections/calendar.csv")
        for r in read_csv(cal_path):
            d = parse_date(r.get("date") or r.get("vote_date"))
            calendar.append({**r, "country": r.get("country") or ISO3.get(r.get("iso3", ""), ""),
                             "date": iso(d), "event": r.get("election") or r.get("description", "")})
    else:
        sources += ["data/events/elections.csv", "data/events/upcoming_events.csv"]
        for r in read_csv(ROOT / "data/events/elections.csv"):
            d = parse_date(r.get("vote_date"))
            calendar.append({
                "country": r.get("country"), "iso3": r.get("iso3"), "event": r.get("election"),
                "type": r.get("type"), "round": r.get("round"), "date": iso(d),
                "results_known": iso(parse_date(r.get("results_known"))),
                "cand_a": r.get("cand_a"), "cand_b": r.get("cand_b"),
                "poll_margin_pp": fnum(r.get("poll_margin_pp"), 2),
                "actual_margin_pp": fnum(r.get("actual_margin_pp"), 2),
                "winner": r.get("winner"), "odds_favourite": r.get("odds_favourite"),
                "odds_prob_favourite": fnum(r.get("odds_prob_favourite"), 3),
                "market_preferred": r.get("market_preferred"), "notes": r.get("notes"),
                "source": r.get("actual_source") or r.get("poll_source"),
            })
        for r in read_csv(ROOT / "data/events/upcoming_events.csv"):
            d = parse_date(r.get("date"))
            calendar.append({
                "country": r.get("country"), "iso3": r.get("iso3"), "event": r.get("description"),
                "type": r.get("subtype") or r.get("event_type"), "round": "", "date": iso(d),
                "results_known": None, "cand_a": "", "cand_b": "", "poll_margin_pp": None,
                "actual_margin_pp": None, "winner": "", "odds_favourite": "", "odds_prob_favourite": None,
                "market_preferred": "", "notes": r.get("notes"), "source": r.get("source"),
            })
    calendar = [c for c in calendar if c.get("date")]
    calendar.sort(key=lambda c: c["date"], reverse=True)
    upcoming = sorted([c for c in calendar if c["date"] >= today.isoformat()], key=lambda c: c["date"])
    past = [c for c in calendar if c["date"] < today.isoformat()]

    signals = []
    if sig_path.exists():
        sources.append("data/elections/signals.csv")
        for r in read_csv(sig_path):
            signals.append(r)
    else:
        sp = ROOT / "results/repricing/signals_daily.csv"
        if sp.exists():
            sources.append("results/repricing/signals_daily.csv")
            with sp.open(newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                header = next(reader)
                cols = header[1:]
                series: dict[str, list] = {c: [] for c in cols}
                for row in reader:
                    d = row[0]
                    for c, v in zip(cols, row[1:]):
                        if v not in ("", "nan"):
                            series[c].append((d, float(v)))
            for c in cols:
                pts = series[c]
                if not pts:
                    continue
                m = re.match(r"(odds|polls_h2h|polls)_([A-Z]{3})_(\d{8})", c)
                kind, iso3, ed = (m.group(1), m.group(2), m.group(3)) if m else ("", "", "")
                edate = f"{ed[:4]}-{ed[4:6]}-{ed[6:]}" if ed else ""
                label = {"odds": "Betting odds (favourite's win probability, %)",
                         "polls_h2h": "Head-to-head poll margin (pp)",
                         "polls": "Poll-of-polls two-party margin (pp)"}.get(kind, c)
                recent = pts[-90:]
                signals.append({
                    "id": c, "kind": kind, "label": label, "country": ISO3.get(iso3, iso3),
                    "iso3": iso3, "election_date": edate,
                    "first": pts[0][0], "last": pts[-1][0], "last_value": pts[-1][1],
                    "n": len(pts), "active": edate >= (today - timedelta(days=120)).isoformat(),
                    "series": [[d, v] for d, v in recent],
                })
            signals.sort(key=lambda s: (s["election_date"], s["kind"]), reverse=True)
    return {"upcoming": upcoming, "past": past[:60], "n_past": len(past), "signals": signals,
            "sources": sources, "countries": sorted({c["country"] for c in calendar if c.get("country")})}


# ----------------------------------------------------------------------------- reports
_FM = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)


def parse_front_matter(text: str) -> tuple[dict, str]:
    m = _FM.match(text)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip().lower()] = v.strip().strip('"').strip("'")
    return meta, text[m.end():]


def build_reports(out_dir: Path, today: date) -> dict:
    items = []
    rep_out = out_dir / "data" / "reports"
    rep_out.mkdir(parents=True, exist_ok=True)

    def add(path: Path, meta: dict, body: str | None, kind: str, source_rel: str):
        d = parse_date(meta.get("date")) or (parse_date(git_first_date(source_rel)) if source_rel else None)
        if d is None:
            d = date.fromtimestamp(path.stat().st_mtime)
        title = meta.get("title") or (next((ln.lstrip("# ").strip() for ln in (body or "").splitlines()
                                            if ln.startswith("#")), path.stem))
        rtype = (meta.get("type") or "other").strip().lower()
        if rtype not in REPORT_TYPES:
            rtype = "other"
        rid = f"{d.isoformat()}_{slug(path.stem)}"
        ext = ".md" if kind == "md" else ".pdf"
        target = rep_out / f"{rid}{ext}"
        if kind == "md":
            target.write_text(body or "", encoding="utf-8")
        else:
            shutil.copyfile(path, target)
        items.append({
            "id": rid, "date": d.isoformat(), "title": title, "type": rtype,
            "country": meta.get("country") or guess_country(title) or "Global",
            "format": kind, "file": f"data/reports/{rid}{ext}", "source": source_rel,
            "source_url": f"{REPO_URL}/blob/main/{source_rel}",
            "words": len((body or "").split()) if body else None,
            "issue_url": f"{REPO_URL}/issues/{meta['issue']}" if meta.get("issue") else None,
        })

    ledger_dir = ROOT / "data/ledger/reports"
    if ledger_dir.exists():
        for p in sorted(ledger_dir.iterdir()):
            if p.name.lower() == "readme.md" or p.name.startswith("."):
                continue
            rel = p.relative_to(ROOT).as_posix()
            if p.suffix.lower() == ".md":
                meta, body = parse_front_matter(p.read_text(encoding="utf-8"))
                add(p, meta, body, "md", rel)
            elif p.suffix.lower() == ".pdf":
                side = p.with_suffix(".meta.yml")
                meta = {}
                if side.exists():
                    meta, _ = parse_front_matter("---\n" + side.read_text(encoding="utf-8") + "\n---\n")
                add(p, meta, None, "pdf", rel)
    results_dir = ROOT / "results"
    for p in sorted(results_dir.glob("*.md")):
        rel = p.relative_to(ROOT).as_posix()
        meta, body = parse_front_matter(p.read_text(encoding="utf-8"))
        meta.setdefault("type", "research")
        add(p, meta, body, "md", rel)
    items.sort(key=lambda r: (r["date"], r["id"]), reverse=True)
    return {"items": items, "types": list(REPORT_TYPES),
            "countries": sorted({r["country"] for r in items})}


# ----------------------------------------------------------------------------- evidence
MIN_TRACK_RECORD_YEARS = 4.6          # spec MinTRL for 90% confidence in v1.0's Sharpe
ELECTION_RULE_THRESHOLD = 15          # scored EM elections before the continuation rule is judged
SCORED_COLUMNS = ("scored", "outcome", "result", "rule_return", "rule_pnl", "pnl", "realised", "realized")


def count_scored_elections(path: Path, today: date) -> dict:
    """Scored elections for the EM election continuation rule from data/elections/signals.csv.

    A row counts as scored when any of SCORED_COLUMNS has a value, or, if the file has none
    of those columns, when its election/vote date is in the past. The file is optional: when
    it is missing the count is 0 and the note says so."""
    rel = path.relative_to(ROOT).as_posix() if path.is_absolute() and ROOT in path.parents else path.as_posix()
    if not path.exists():
        return {"scored": 0, "pending": 0, "rows": 0, "found": False,
                "note": f"{rel} not found; the count starts when the file exists (one row per election, with a scored/outcome column)."}
    rows = read_csv(path)
    if not rows:
        return {"scored": 0, "pending": 0, "rows": 0, "found": True, "note": f"{rel} is empty."}
    cols = {c.lower(): c for c in rows[0].keys()}
    score_col = next((cols[c] for c in SCORED_COLUMNS if c in cols), None)
    date_col = next((cols[c] for c in ("vote_date", "election_date", "date") if c in cols), None)
    scored = pending = 0
    for r in rows:
        if score_col is not None:
            ok = bool(str(r.get(score_col) or "").strip())
        else:
            d = parse_date(r.get(date_col)) if date_col else None
            ok = d is not None and d <= today
        scored += ok
        pending += (not ok)
    basis = f"column '{score_col}'" if score_col else (f"past '{date_col}'" if date_col else "all rows")
    return {"scored": scored, "pending": pending, "rows": len(rows), "found": True,
            "note": f"{rel}: {scored} scored of {len(rows)} rows (by {basis})."}


def one_line_reason(t: dict, limit: int = 160) -> str:
    dec = " ".join((t.get("decision") or "").split())
    res = " ".join((t.get("result") or "").split())
    first = re.split(r"(?<=[.;])\s", res, maxsplit=1)[0] if res else ""
    text = dec if not first else (f"{dec}: {first}" if dec else first)
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "\u2026"


def build_evidence(trials: dict, algorithm: dict, today: date) -> dict:
    live = algorithm["live"]
    live_months = live.get("months", 0)
    months_needed = round(MIN_TRACK_RECORD_YEARS * 12)
    v1 = next((t for t in trials["items"] if t.get("trial_id") == "T01"), None)
    live_entry = {
        "id": "v1.0", "trial_id": v1["trial_id"] if v1 else None,
        "name": "v1.0 systematic macro strategy (carry, trend, value; FX and bonds)",
        "status": "live", "live_months": live_months, "live_sharpe": live.get("sharpe"),
        "live_return_pct": live.get("total_return_pct"), "live_max_drawdown_pct": live.get("max_drawdown_pct"),
        "backtest_sharpe": algorithm["backtest"].get("sharpe"),
        "backtest_max_drawdown_pct": algorithm["backtest"].get("max_drawdown_pct"),
        "months_needed": months_needed, "progress_pct": round(100 * min(live_months, months_needed) / months_needed, 1),
        "live_since": algorithm["rebalance"]["live_since"], "last_month": algorithm["months"][-1]["month"] if algorithm["months"] else None,
        "reason": one_line_reason(v1) if v1 else "", "link": "#/algorithm",
    }
    elections = count_scored_elections(ROOT / "data/elections/signals.csv", today)
    prospective = [{
        "id": "election-rule", "name": "EM election continuation rule (trade the post-result surprise, hold 5 days)",
        "status": "under test", "scored": elections["scored"], "threshold": ELECTION_RULE_THRESHOLD,
        "progress_pct": round(100 * min(elections["scored"], ELECTION_RULE_THRESHOLD) / ELECTION_RULE_THRESHOLD, 1),
        "reason": f"{elections['scored']} of {ELECTION_RULE_THRESHOLD} elections scored. {elections['note']}",
        "link": "#/elections", "source": "data/elections/signals.csv",
    }]
    for t in trials["items"]:
        if t["status"] == "pending":
            prospective.append({"id": t["trial_id"], "name": t["name"], "status": "under test", "scored": None,
                                "threshold": None, "progress_pct": None, "reason": one_line_reason(t) or "not yet run",
                                "link": "#/trials", "source": "trials.csv"})
    passed = [{"id": t["trial_id"], "name": t["name"], "status": "passed", "date": t.get("date_tested"),
               "reason": one_line_reason(t), "link": "#/trials"}
              for t in trials["items"] if t["status"] == "pass" and t.get("trial_id") != "T01"]
    failed = [{"id": t["trial_id"], "name": t["name"], "status": "failed", "date": t.get("date_tested"),
               "group": t.get("trial_group"), "reason": one_line_reason(t), "link": "#/trials"}
              for t in trials["items"] if t["status"] == "fail"]
    n_live = live_months
    if passed:
        overall = (f"{len(passed)} validated discretionary idea{'s' if len(passed) != 1 else ''}; "
                   f"v1.0 live for {n_live} month{'s' if n_live != 1 else ''} of the {months_needed} needed; "
                   f"{len(failed)} rejected.")
    else:
        overall = (f"No validated discretionary edge yet; v1.0 live for {n_live} month{'s' if n_live != 1 else ''} "
                   f"({months_needed} needed for a 90%-confidence track record); "
                   f"{len(prospective)} idea{'s' if len(prospective) != 1 else ''} under prospective test; "
                   f"{len(failed)} rejected.")
    return {
        "overall": overall, "as_of": today.isoformat(),
        "groups": [
            {"key": "live", "title": "Live and under test", "items": [live_entry]},
            {"key": "prospective", "title": "Under prospective test", "items": prospective},
            {"key": "passed", "title": "Passed trials", "items": passed},
            {"key": "failed", "title": "Failed or rejected ideas", "items": failed},
        ],
        "counts": {"live": 1, "prospective": len(prospective), "passed": len(passed), "failed": len(failed)},
        "sources": ["trials.csv", "results/systematic/paper_pnl.csv", "data/elections/signals.csv"],
        "min_track_record": {"years": MIN_TRACK_RECORD_YEARS, "months": months_needed, "confidence": "90%"},
    }


# ----------------------------------------------------------------------------- home
def build_home(today: date, decisions, forecasts, algorithm, elections, reports, evidence) -> dict:
    horizon = today + timedelta(days=30)
    cat = []
    for e in elections["upcoming"]:
        if e["date"] <= horizon.isoformat():
            cat.append({"date": e["date"], "kind": "election", "country": e["country"],
                        "label": e["event"], "link": "#/elections"})
    for d in decisions["items"]:
        if d["status"] == "open" and d["horizon"] and today.isoformat() <= d["horizon"] <= horizon.isoformat():
            cat.append({"date": d["horizon"], "kind": "decision horizon", "country": d["country"],
                        "label": f"{d['id']} {d['instrument']} ({d['action']})", "link": f"#/decisions/{d['id']}"})
    for f in forecasts["items"]:
        if f["status"] == "open" and f["resolution_date"] and today.isoformat() <= f["resolution_date"] <= horizon.isoformat():
            cat.append({"date": f["resolution_date"], "kind": "forecast resolves", "country": f["country"],
                        "label": f"{f['id']} {f['question']}", "link": "#/forecasts"})
    # next monthly run of the v1.0 workflow: 07:23 UTC on the 3rd
    nxt = date(today.year + (today.month == 12), (today.month % 12) + 1, 3) if today.day >= 3 else date(today.year, today.month, 3)
    if nxt <= horizon:
        cat.append({"date": nxt.isoformat(), "kind": "algorithm rebalance", "country": "",
                    "label": "v1.0 monthly run (positions and paper P&L)", "link": "#/algorithm"})
    cat.sort(key=lambda c: (c["date"], c["kind"]))
    months = algorithm["months"]
    last = months[-1] if months else None
    live_rows = [m for m in months if m["live"]]
    account_index = live_rows[-1]["account_index"] if live_rows else 100.0
    usd = usd_account(months, algorithm["rebalance"].get("effective_from"))
    return {
        "account_index": account_index, "account_index_label": ACCOUNT_INDEX_LABEL,
        "account_base": 100.0, "account_base_month": algorithm["rebalance"]["live_base_month"],
        "live_start_month": LIVE_START_MONTH,
        "account_change_pct": round(account_index - 100.0, 3),
        **usd, "usd_switch_rebalance": USD_SWITCH_REBALANCE,
        "history_index_base_month": algorithm["frozen"]["freeze_month"],
        "history_index_last": next((m["account_value"] for m in reversed(months) if not m["live"]), None),
        "last_month": last["month"] if last else None,
        "last_month_net_pct": round(last["net"] * 100, 3) if last and last["net"] is not None else None,
        "live": algorithm["live"],
        "equity": [[m["month"], m["account_value"], m["account_index"], m["live"], m["pre_live"]] for m in months],
        "positions": algorithm["positions"],
        "open_decisions": [d for d in decisions["items"] if d["status"] == "open"],
        "catalysts": cat,
        "latest_report": reports["items"][0] if reports["items"] else None,
        "rebalance": algorithm["rebalance"],
        "open_forecasts": forecasts["summary"]["open"],
        "evidence_status": evidence["overall"],
    }


# ----------------------------------------------------------------------------- site
def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":"), allow_nan=False),
                    encoding="utf-8")


def build(out_dir: Path, today: date | None = None, now: datetime | None = None) -> dict:
    today = today or date.today()
    now = now or datetime.now(timezone.utc)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(SITE_SRC, out_dir, ignore=shutil.ignore_patterns("sw.template.js"))
    decisions = build_decisions(today)
    forecasts = build_forecasts(today)
    algorithm = build_algorithm()
    trials = build_trials()
    elections = build_elections(today)
    reports = build_reports(out_dir, today)
    evidence = build_evidence(trials, algorithm, today)
    home = build_home(today, decisions, forecasts, algorithm, elections, reports, evidence)
    commit = git("rev-parse", "--short", "HEAD")
    meta = {
        "app": "Ledger", "built_at": now.replace(microsecond=0).isoformat(), "today": today.isoformat(),
        "commit": commit, "repo_url": REPO_URL,
        "sources": {
            "paper_pnl_last_month": algorithm["months"][-1]["month"] if algorithm["months"] else None,
            "positions_as_of": algorithm["rebalance"]["as_of"],
            "trials_updated": trials["updated"],
            "decisions_updated": git_last_date("data/ledger/decisions.csv"),
            "forecasts_updated": git_last_date("data/ledger/forecasts.csv"),
            "elections": elections["sources"],
        },
        "issue_forms": {
            "decision": f"{REPO_URL}/issues/new?template=decision.yml",
            "forecast": f"{REPO_URL}/issues/new?template=forecast.yml",
            "resolve": f"{REPO_URL}/issues/new?template=resolve.yml",
            "report": f"{REPO_URL}/issues/new?template=report.yml",
        },
    }
    data = out_dir / "data"
    for name, obj in (("meta", meta), ("home", home), ("decisions", decisions), ("forecasts", forecasts),
                      ("algorithm", algorithm), ("trials", trials), ("elections", elections),
                      ("reports", reports), ("evidence", evidence)):
        write_json(data / f"{name}.json", obj)
    # precache manifest and the service worker with a build id
    files = sorted(p.relative_to(out_dir).as_posix() for p in out_dir.rglob("*")
                   if p.is_file() and p.name not in ("sw.js", "manifest.json"))
    h = hashlib.sha256()
    for f in files:
        h.update(f.encode()); h.update((out_dir / f).read_bytes())
    build_id = h.hexdigest()[:12]
    write_json(data / "manifest.json", {"build": build_id, "built_at": meta["built_at"], "files": files})
    sw = (SITE_SRC / "sw.template.js").read_text(encoding="utf-8").replace("__BUILD_ID__", build_id)
    (out_dir / "sw.js").write_text(sw, encoding="utf-8")
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")
    return {"build": build_id, "files": len(files) + 2, "out": str(out_dir)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(ROOT / "app"))
    ap.add_argument("--today", default=None, help="override the build date (YYYY-MM-DD)")
    a = ap.parse_args(argv)
    info = build(Path(a.out), today=parse_date(a.today) if a.today else None)
    print(json.dumps(info))
    return 0


if __name__ == "__main__":
    sys.exit(main())
