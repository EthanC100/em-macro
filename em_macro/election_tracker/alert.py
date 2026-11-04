"""Results-night alert and later scoring.

For an election whose results are out:
1. final poll average from the last polling-page revision before the vote day (snapshots.final);
2. market sign from the pre-registration as committed before the vote day (prereg.committed_block);
3. surprise, expected day-1 move (frozen study fit) and the position the spec 4.10 rule would take, logged
   at size 0 and labelled "paper, observation only" (the rule's own size is kept for scoring);
4. a GitHub issue "[ELECTION] <country> <date>: surprise <value>" and a row in data/elections/signals.csv.

`score()` later fills the actual day-1 and day-5 moves (study definitions), the post-day-1 move and the rule's
paper trade return, which score the prospective trial T15 in trials.csv. Nothing is ever traded.
"""
from __future__ import annotations

import datetime as dt
import io
import json
import re

import numpy as np
import pandas as pd
from bs4 import BeautifulSoup

from . import fx, prereg, snapshots, wiki
from .common import DATA, SIGNALS, load_calendar, load_config, post_issue, today
from .rule import (LOGGED_SIZE, POSITION_LABEL, expected_day1_move, implied_position, load_frozen_fit,
                   surprise)

ALERT_LABEL = "election-alert"
RESULTS_WINDOW_DAYS = 3
SIGNAL_COLS = [
    "id", "country", "currency", "vote_date", "results_known", "alert_utc", "status", "prereg_commit",
    "market_preferred", "cand_a", "cand_b", "poll_share_a", "poll_share_b", "poll_margin", "poll_window_days",
    "poll_n_pollsters", "poll_revid", "actual_share_a", "actual_share_b", "actual_margin", "result_source",
    "provisional", "market_sign", "surprise_pp", "expected_day1_pct", "direction", "position_label", "risk_frac",
    "notional_frac", "p", "b", "kelly", "rule_risk_frac", "sigma_daily_pct", "stop_pct", "rule_notional_frac",
    "entry_date", "exit_date", "fx_source", "issue_url",
    "actual_day1_raw_pct", "actual_day1_abn_pct", "actual_day5_raw_pct", "actual_day5_abn_pct",
    "actual_day1_raw_ecb_pct", "actual_day5_raw_ecb_pct", "post_day1_move_pct", "trade_return_pct", "trade_stopped",
    "rule_pnl_nav_pct", "scored", "fx_file", "scored_utc"]
# risk_frac / notional_frac: the logged size, always 0 (observation only).
# rule_risk_frac / rule_notional_frac: what the spec 4.10 rule would have sized (for scoring only).
# post_day1_move_pct: entry close -> exit close, signed by the surprise, no stop (T15 hit rate).
# trade_return_pct: the same with the rule's close-based stop (T15 mean return); rule_pnl_nav_pct =
#   trade_return_pct x rule_notional_frac, the paper P&L the rule would have made in % of NAV.
# scored: "yes" once a signal-status row has its post-day-1 move and trade return (counts towards T15's 15).


# ------------------------------------------------------------------ results
def parse_results(html: str, result_match: dict[str, str]) -> dict[str, float]:
    """Vote shares (%) by option from the first results table that has Votes and % columns."""
    soup = BeautifulSoup(html, "lxml")
    for t in soup.find_all("table"):
        for sup in t.find_all("sup"):
            sup.decompose()
        try:
            df = pd.read_html(io.StringIO(str(t)))[0]
        except ValueError:
            continue
        cols = [" ".join(map(str, c)) if isinstance(c, tuple) else str(c) for c in df.columns]
        if not any(re.search(r"\bvotes\b", c, re.I) for c in cols):
            continue
        pct = next((i for i, c in enumerate(cols) if re.search(r"%", c)), None)
        if pct is None:
            continue
        out = {}
        for opt, rx in result_match.items():
            for _, r in df.iterrows():
                label = " ".join(str(v) for v in r.iloc[:max(1, pct)].tolist())
                if re.search(rx, label, re.I) and not re.search(r"total|valid|invalid|blank|turnout", label, re.I):
                    v = pd.to_numeric(str(r.iloc[pct]).replace("%", "").replace(",", ""), errors="coerce")
                    if pd.notna(v):
                        out[opt] = float(v)
                        break
        if len(out) >= 2:
            return out
    return {}


def fetch_results(c: dict) -> tuple[dict, str] | None:
    if not c.get("result_match"):
        return None
    rv = wiki.revision(c["page"])
    if rv is None:
        return None
    shares = parse_results(wiki.html(rv["title"], rv["revid"]), c["result_match"])
    return (shares, wiki.permalink(rv["title"], rv["revid"])) if shares else None


# ------------------------------------------------------------------ signal
def build_signal(eid: str, shares: dict[str, float], source: str, results_known: str | None = None,
                 provisional: bool = True) -> dict:
    cal = load_calendar().set_index("id")
    row, c = cal.loc[eid].to_dict(), load_config()[eid]
    results_known = results_known or row["date"]
    fin = snapshots.final(eid)
    a, b = fin.get("a"), fin.get("b")
    block = prereg.committed_block(eid, snapshots.vote_cutoff_utc(row["date"], c["tz"]))
    mp = block.get("market_preferred") if block else None
    status = "signal"
    if block is None:
        status, sign = "excluded: no pre-registration committed before the vote", None
    elif not mp:
        status, sign = "excluded: market sign not classified before the vote", None
    else:
        sign = {a: 1, b: -1}.get(mp)
        if sign is None:
            status = f"excluded: market-preferred {mp} is not one of the two poll leaders ({a}, {b})"
    if a is None or a not in shares or b not in shares:
        status, s, actual_margin = "excluded: final poll average or result shares missing", None, None
    else:
        actual_margin = shares[a] - shares[b]
        s = surprise(actual_margin, float(fin["margin"]), sign)
    fit = load_frozen_fit()
    expected = expected_day1_move(s, fit) if s is not None else None

    entry = fx.entry_date(results_known)
    hist_start = (pd.Timestamp(today()) - pd.Timedelta(days=500)).date().isoformat()
    try:
        series, src = fx.spot(row["currency"], c.get("yahoo"), hist_start, (today() + dt.timedelta(days=1)).isoformat())
        sigma = fx.sigma_daily(fx.level(series), min(pd.Timestamp(today()), entry))
    except Exception as e:
        series, src, sigma = None, f"unavailable ({e})", float("nan")
    pos = implied_position(s if status == "signal" else None, sigma) if sigma == sigma else None
    return {
        "id": eid, "country": row["country"], "currency": row["currency"], "vote_date": row["date"],
        "results_known": results_known, "alert_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "status": status, "prereg_commit": (block or {}).get("commit"), "market_preferred": mp,
        "cand_a": a, "cand_b": b, "poll_share_a": fin.get("share_a"), "poll_share_b": fin.get("share_b"),
        "poll_margin": fin.get("margin"), "poll_window_days": fin.get("window_days"),
        "poll_n_pollsters": fin.get("n_pollsters"), "poll_revid": fin.get("revid"),
        "actual_share_a": shares.get(a), "actual_share_b": shares.get(b), "actual_margin": actual_margin,
        "result_shares": json.dumps(shares), "result_source": source, "provisional": provisional, "market_sign": sign, "surprise_pp": s,
        "expected_day1_pct": expected, "direction": pos.direction if pos else None,
        "position_label": POSITION_LABEL, "risk_frac": LOGGED_SIZE, "notional_frac": LOGGED_SIZE,
        "p": pos.p if pos else None, "b": pos.b if pos else None, "kelly": pos.kelly if pos else None,
        "rule_risk_frac": pos.risk_frac if pos else None, "sigma_daily_pct": sigma,
        "stop_pct": pos.stop_pct if pos else None,
        "rule_notional_frac": pos.notional_frac if pos else None, "entry_date": entry.date().isoformat(),
        "exit_date": fx.exit_date(entry).date().isoformat(), "fx_source": src}


def _f(v, fmt="{:+.2f}", na="n/a"):
    return na if v is None or (isinstance(v, float) and np.isnan(v)) else fmt.format(v)


def issue_text(sig: dict) -> tuple[str, str]:
    s = sig["surprise_pp"]
    title = f"[ELECTION] {sig['country']} {sig['vote_date']}: surprise {_f(s, '{:+.1f}pp', 'n/a')}"
    direction = {1: f"long {sig['currency']} vs USD", -1: f"short {sig['currency']} vs USD", 0: "no position"}.get(sig["direction"], "n/a")
    body = f"""**{sig['position_label'].capitalize()}: size 0. No position is taken by this repository.** Status: **{sig['status']}**.

| | |
|---|---|
| Final poll average{' (**THIN: fewer than 2 pollsters within 21 days**)' if (sig['poll_n_pollsters'] or 0) < 2 else ''} | {sig['cand_a']} {_f(sig['poll_share_a'], '{:.1f}')}% vs {sig['cand_b']} {_f(sig['poll_share_b'], '{:.1f}')}% (margin {_f(sig['poll_margin'], '{:+.1f}')}pp; {_f(sig['poll_window_days'], '{:.0f}')}-day window, {_f(sig['poll_n_pollsters'], '{:.0f}')} pollsters; Wikipedia rev {sig['poll_revid']}) |
| Result{' (provisional)' if sig['provisional'] else ''} | {sig['cand_a']} {_f(sig['actual_share_a'], '{:.1f}')}% vs {sig['cand_b']} {_f(sig['actual_share_b'], '{:.1f}')}% (margin {_f(sig['actual_margin'], '{:+.1f}')}pp); all shares read: {', '.join(f'{k} {v:.1f}%' for k, v in json.loads(sig['result_shares']).items())} — {sig['result_source']} |
| Market-preferred (pre-registered, commit {str(sig['prereg_commit'])[:7]}) | {sig['market_preferred'] or 'not classified'} → sign {_f(sig['market_sign'], '{:+.0f}')} |
| **Surprise** | **{_f(s, '{:+.2f}')} pp** (+ = market-preferred side beat its polls) |
| **Expected day-1 move** | **{_f(sig['expected_day1_pct'], '{:+.2f}')}%** {sig['currency']} vs USD, abnormal (0.0368 + 0.0596 × surprise) |
| **Implied position ({sig['position_label']})** | **{direction}, size {_f(sig['notional_frac'], '{:.0f}')}** (logged size 0; nothing is traded) |
| Spec 4.10 rule would have taken (for scoring only) | {direction}; risk {_f(sig['rule_risk_frac'], '{:.2%}')} of NAV; stop {_f(sig['stop_pct'], '{:.2f}')}% (1.5 × σ {_f(sig['sigma_daily_pct'], '{:.2f}')}% × √5); notional {_f(sig['rule_notional_frac'], '{:.2f}')}× NAV |
| Entry / exit | close {sig['entry_date']} / close {sig['exit_date']} (5 trading days) |
| FX data | {sig['fx_source']} |

Caveats: the day-1 slope was not significant in-sample (p 0.20); the 0.72 correlation is on 9 hold-out events.
**Continuation after day 1 is not established**: the tracker exists to test it (trials.csv T15; judged after at least
15 scored elections). Actual day-1 and day-5 moves and the paper trade return will be added to
`data/elections/signals.csv`.
Pre-registration: `docs/elections/{sig['id']}.md`."""
    return title, body


def append_signal(sig: dict) -> None:
    df = pd.read_csv(SIGNALS) if SIGNALS.exists() else pd.DataFrame(columns=SIGNAL_COLS)
    df = pd.concat([df[df["id"] != sig["id"]], pd.DataFrame([sig])], ignore_index=True)
    df.reindex(columns=SIGNAL_COLS).to_csv(SIGNALS, index=False)


def has_signal(eid: str) -> bool:
    return SIGNALS.exists() and eid in set(pd.read_csv(SIGNALS)["id"])


def alert(eid: str, shares: dict, source: str, results_known: str | None = None, provisional: bool = True) -> dict:
    sig = build_signal(eid, shares, source, results_known, provisional)
    title, body = issue_text(sig)
    sig["issue_url"] = post_issue(title, body, ALERT_LABEL, dedupe_prefix=f"[ELECTION] {sig['country']} {sig['vote_date']}:")
    append_signal(sig)
    return sig


def check() -> list[str]:
    """Daily during each election window (vote day to vote day + 3): final snapshot, results, alert."""
    cal, cfg, out = load_calendar(), load_config(), []
    for _, row in cal.iterrows():
        vote = dt.date.fromisoformat(row["date"])
        if row["status"] not in ("scheduled", "held") or not (vote <= today() <= vote + dt.timedelta(days=RESULTS_WINDOW_DAYS)):
            continue
        if has_signal(row["id"]):
            continue
        c = cfg.get(row["id"], {})
        if snapshots.config_gaps(c):
            print(f"{row['id']}: poll tracking not configured; cannot compute the surprise")
            continue
        snapshots.final(row["id"])
        res = fetch_results(c)
        if res is None:
            print(f"{row['id']}: results not found yet")
            if today() == vote + dt.timedelta(days=RESULTS_WINDOW_DAYS):
                post_issue(f"[ELECTION-RESULTS] {row['country']} {row['date']}: results not parsed",
                           "The daily check could not read results from Wikipedia. Run the `elections-daily` "
                           f"workflow manually with id `{row['id']}` and the result shares.", "election-config")
            continue
        alert(row["id"], *res)
        out.append(row["id"])
    return out


# ------------------------------------------------------------------ scoring
def score() -> list[str]:
    """Fill actual day-1/day-5 moves and the trade return once the data exist."""
    if not SIGNALS.exists():
        return []
    df = pd.read_csv(SIGNALS, dtype={"trade_stopped": "object", "scored_utc": "object", "fx_source": "object",
                                     "fx_file": "object", "scored": "object", "position_label": "object"})
    cfg, done = load_config(), []
    for i, r in df.iterrows():
        if pd.notna(r.get("scored_utc")) or today() <= dt.date.fromisoformat(r["exit_date"]):
            continue
        c = cfg.get(r["id"], {})
        start = (pd.Timestamp(r["vote_date"]) - pd.Timedelta(days=400)).date().isoformat()
        end = (today() + dt.timedelta(days=1)).isoformat()
        series, src = fx.spot(r["currency"], c.get("yahoo"), start, end)
        x = fx.level(series)
        raw = fx.raw_moves(x, r["vote_date"])
        betas = fx.frozen_betas(c.get("iso2", ""))
        ab = {1: np.nan, 5: np.nan}
        if betas:
            try:
                ab = fx.abnormal_moves(raw, r["vote_date"], betas, fx.factor_levels(start, end))
            except Exception as e:
                print(f"{r['id']}: abnormal move unavailable ({e})")
        df.loc[i, ["actual_day1_raw_pct", "actual_day5_raw_pct", "actual_day1_abn_pct", "actual_day5_abn_pct"]] = \
            [raw[1], raw[5], ab[1], ab[5]]
        if pd.notna(r.get("direction")) and int(r["direction"]) != 0 and pd.notna(r.get("stop_pct")):
            t = fx.trade_return(x, pd.Timestamp(r["entry_date"]), int(r["direction"]), float(r["stop_pct"]))
            df.loc[i, ["post_day1_move_pct", "trade_return_pct", "trade_stopped"]] = \
                [t["post_move_pct"], t["trade_return_pct"], t["stopped"]]
            if pd.notna(r.get("rule_notional_frac")):
                df.loc[i, "rule_pnl_nav_pct"] = t["trade_return_pct"] * float(r["rule_notional_frac"])
        if pd.isna(raw[5]):
            continue                            # data not in yet: try again tomorrow
        # Save the exact series used (reproducible scoring) and cross-check against the ECB reference
        # rate (14:15 CET fixing, so day-1 moves differ from closes by timing).
        frames = {"primary": series}
        try:
            ecb = fx._frankfurter(r["currency"], start, end)
            raw_ecb = fx.raw_moves(fx.level(ecb), r["vote_date"])
            df.loc[i, ["actual_day1_raw_ecb_pct", "actual_day5_raw_ecb_pct"]] = [raw_ecb[1], raw_ecb[5]]
            frames["ecb"] = ecb
        except Exception as e:
            print(f"{r['id']}: ECB cross-check unavailable ({e})")
        out = DATA / "fx" / f"{r['id']}.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(frames).loc[str(pd.Timestamp(r["vote_date"]) - pd.Timedelta(days=120)):].to_csv(out, index_label="date")
        df.loc[i, "fx_file"] = str(out.relative_to(DATA.parents[1]))
        df.loc[i, "scored_utc"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        if r["status"] == "signal" and pd.notna(df.loc[i, "post_day1_move_pct"]) and pd.notna(df.loc[i, "trade_return_pct"]):
            df.loc[i, "scored"] = "yes"
        df.loc[i, "fx_source"] = f"{r['fx_source']}; scored with {src}"
        done.append(r["id"])
    df.reindex(columns=SIGNAL_COLS).to_csv(SIGNALS, index=False)
    return done
