"""Exploratory: pre-election repricing of currencies and 10y yields as polls and
betting odds move.

For each election with a daily (odds) or at-least-weekly (polls) signal over the
pre-vote window, regress the daily change in the currency (% , + = local
currency up) and the 10y yield (bp) on the daily change in the signal, net of
same-day changes in DXY, US 10y and log VIX:

    y_d = a + b * dS_d + c1*dDXY_d + c2*dUS10_d + c3*dlogVIX_d + e_d   (HAC, 5 lags)

Signals are oriented to the *leading candidate* (cand_a in elections.csv):
  * odds:  implied win probability of cand_a, in percentage points
           (sensitivity reported per 10pp)
  * polls: poll-of-polls margin cand_a - cand_b, pp (sensitivity per 1pp)

Lead/lag: y_d on dS_{d+k} for k = -5..5 (k > 0: today's market move vs. a
later signal change, i.e. the market leads).  Reversal: local projections of
the cumulative move from d-1 to d+h (h = 0..10) on dS_d.

All of this uses the full sample (including the 2022+ hold-out period) and is
not part of the frozen fit/test design.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm

from . import sources as S
from .config import EVENTS, ISO3, PROC, RESULTS

ISO2 = {v: k for k, v in ISO3.items()}
OUT = RESULTS / "repricing"
WINDOW_DAYS = 183
LAGS = range(-5, 6)
LP_H = range(0, 11)
MIN_POLLS_PER_WEEK = 1.0

# Polymarket winner markets with a stored daily history.  `invert`: the market
# prices cand_b (or "Erdogan wins" when Kilicdaroglu was cand_a), so cand_a's
# probability is 1 - p.
ODDS_MARKETS = [
    # iso3, first-round date, last vote date (run-off if any), event_id, market title, invert, note
    ("BRA", "2026-10-04", "2026-10-25", 45915, "Luiz Inácio Lula da Silva", False, "Lula wins presidency"),
    ("MEX", "2024-06-02", "2024-06-02", 903204, "Claudia Sheinbaum", False, "Sheinbaum wins"),
    ("TUR", "2023-05-14", "2023-05-28", 901259, "Will Erdoğan win", True, "Erdogan wins presidency (inverted)"),
    ("POL", "2025-05-18", "2025-06-01", 14874, "Rafał Trzaskowski", False, "Trzaskowski wins presidency"),
    ("IDN", "2024-02-14", "2024-02-14", 902796, "Prabowo", False, "Prabowo wins"),
    ("ZAF", "2024-05-29", "2024-05-29", 10330, "ANC win a majority", False, "ANC wins a seat majority"),
]


# ------------------------------------------------------------------ signals
def _elections() -> pd.DataFrame:
    e = pd.read_csv(EVENTS / "elections.csv")
    e["vote_date"] = pd.to_datetime(e["vote_date"])
    return e


def _window(vote_date: pd.Timestamp, last_vote: pd.Timestamp | None = None) -> pd.DatetimeIndex:
    """Weekdays from 183 days before the (first-round) vote to the last weekday
    before the final vote.  When a run-off follows, the first-round result day
    (first weekday after round 1) is dropped: it is the election-day event, not
    pre-vote repricing."""
    last_vote = vote_date if last_vote is None else last_vote
    days = pd.bdate_range(vote_date - pd.Timedelta(days=WINDOW_DAYS), last_vote - pd.Timedelta(days=1))
    if last_vote > vote_date:
        days = days[days != days[days.searchsorted(vote_date, side="right")]]
    return days


def odds_signals(refresh: bool = False) -> list[dict]:
    el = _elections()
    out = []
    for iso, vd, last, eid, title, invert, note in ODDS_MARKETS:
        vd, last = pd.Timestamp(vd), pd.Timestamp(last)
        row = el[(el.iso3 == iso) & (el.vote_date == vd)].iloc[0]
        p = S.polymarket_daily(eid, title, refresh) * 100
        if invert:
            p = 100 - p
        out.append({"iso3": iso, "vote_date": vd, "last_vote": last, "kind": "odds", "cand_a": row.cand_a,
                    "market_preferred": row.market_preferred,
                    "signal_note": f"Polymarket event {eid}: {note}, prob. of {row.cand_a}",
                    "level": p, "days": _window(vd, last)})
    return out


def poll_average(polls: pd.DataFrame, days: pd.DatetimeIndex, max_age: int = 30) -> pd.Series:
    """Poll-of-polls margin (a - b) on each day: mean over pollsters of each
    pollster's latest poll already released (published date, else fieldwork
    end + 1 day) whose fieldwork ended within `max_age` days."""
    p = polls.copy()
    p["release"] = p["published"].fillna(p["field_end"] + pd.Timedelta(days=1))
    p["margin"] = p["a_pct"] - p["b_pct"]
    out = {}
    for d in days:
        g = p[(p["release"] <= d) & (p["field_end"] >= d - pd.Timedelta(days=max_age))]
        if g.empty:
            continue
        out[d] = g.sort_values("release").groupby("pollster")["margin"].last().mean()
    return pd.Series(out, dtype=float)


def poll_signals() -> list[dict]:
    el = _elections()
    files = sorted((EVENTS / "raw").glob("prevote_polls_*.csv"))
    if not files:
        return []
    P = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    for c in ("field_start", "field_end", "published", "vote_date"):
        P[c] = pd.to_datetime(P[c], errors="coerce")
    for c in ("a_pct", "b_pct"):
        P[c] = pd.to_numeric(P[c], errors="coerce")
    P = P.dropna(subset=["field_end", "a_pct", "b_pct"])
    P = P[P["contest"].isin(["round1", "single"])]   # run-off windows (2-4 weeks) are too short
    out = []
    for (iso, vd, contest), g in P.groupby(["iso3", "vote_date", "contest"]):
        match = el[(el.iso3 == iso) & (el.vote_date == vd)]
        if match.empty:
            continue
        row = match.iloc[0]
        days = _window(vd)
        g = g[(g["field_end"] >= days[0] - pd.Timedelta(days=30)) & (g["field_end"] < vd)]
        in_window = g[g["field_end"] >= days[0]]
        weeks = max(len(days) / 5, 1)
        out.append({"iso3": iso, "vote_date": vd, "last_vote": vd, "days": days, "kind": "polls",
                    "cand_a": row.cand_a, "market_preferred": row.market_preferred,
                    "signal_note": f"{contest} polls, {len(in_window)} in window, "
                                   f"{len(in_window) / weeks:.1f}/week, basis {','.join(sorted(g['basis'].dropna().unique()))}",
                    "level": poll_average(g, days), "n_obs": len(in_window),
                    "per_week": len(in_window) / weeks})
    return out


# --------------------------------------------------------------- regressions
def _daily(panel: pd.DataFrame, col: str, kind: str) -> pd.Series:
    s = panel[col].ffill(limit=3)
    if kind == "fx":
        return -100 * np.log(s).diff()
    if kind == "logpct":
        return 100 * np.log(s).diff()
    return 100 * s.diff()                       # yields in % -> bp


def _controls(panel):
    return pd.DataFrame({"dDXY": _daily(panel, "DXY", "logpct"), "dUS10": _daily(panel, "US10Y", "bp"),
                         "dVIX": _daily(panel, "VIX", "logpct")})


def _ols(y, X, hac=5):
    d = pd.concat([y.rename("y"), X], axis=1).dropna()
    if len(d) < 30 or d.iloc[:, 1].std() == 0:
        return None
    return sm.OLS(d["y"], sm.add_constant(d.drop(columns="y"))).fit(cov_type="HAC", cov_kwds={"maxlags": hac})


def analyse(sig: dict, panel: pd.DataFrame) -> tuple[list[dict], list[dict]]:
    c = ISO2[sig["iso3"]]
    days = sig["days"]
    lvl = sig["level"].reindex(pd.date_range(days[0] - pd.Timedelta(days=40), days[-1])).ffill()
    lvl = lvl.reindex(pd.bdate_range(days[0] - pd.Timedelta(days=30), days[-1] + pd.Timedelta(days=15)))
    ds = lvl.diff()
    scale = 10.0 if sig["kind"] == "odds" else 1.0     # per 10pp of probability / per 1pp of margin
    ctrl = _controls(panel)
    rows, lp = [], []
    base = {k: sig[k] for k in ("iso3", "vote_date", "last_vote", "kind", "cand_a", "market_preferred", "signal_note")}
    for asset, col, kind in (("FX", f"FX_{c}", "fx"), ("Y10", f"Y10_{c}", "bp")):
        if col not in panel:
            continue
        y = _daily(panel, col, kind)
        inwin = days                      # all regressions are run on the window's weekdays
        n_days = int(pd.concat([y.reindex(days), ds.reindex(days)], axis=1).dropna().shape[0])
        if n_days < 15:
            continue
        r = {**base, "asset": asset, "n_days": n_days, "signal_sd_daily": ds.reindex(days).std() / scale,
             "signal_range": lvl.reindex(days).max() - lvl.reindex(days).min()}
        for k in LAGS:
            x = (ds.shift(-k) / scale).rename("dS")
            m = _ols(y.reindex(inwin), pd.concat([x, ctrl], axis=1).reindex(inwin))
            if m is None:
                continue
            r[f"b_k{k:+d}"], r[f"t_k{k:+d}"] = m.params["dS"], m.tvalues["dS"]
            if k == 0:
                r["b"], r["t"], r["p"], r["r2"] = m.params["dS"], m.tvalues["dS"], m.pvalues["dS"], m.rsquared
        # joint distributed lag: sums of leads (market ahead) and lags (market behind)
        X = pd.concat([(ds.shift(-k) / scale).rename(f"k{k:+d}") for k in LAGS] + [ctrl], axis=1)
        m = _ols(y.reindex(inwin), X.reindex(inwin))
        if m is not None:
            leads = [f"k{k:+d}" for k in LAGS if k > 0]
            lags = [f"k{k:+d}" for k in LAGS if k < 0]
            for name, cols in (("lead_sum", leads), ("lag_sum", lags)):
                w = np.array([1.0 if v in cols else 0.0 for v in m.params.index])
                t = m.t_test(w)
                r[name], r[f"t_{name}"] = float(t.effect[0]), float(np.ravel(t.tvalue)[0])
            r["joint_k0"] = m.params["k+0"]
        # local projections: cumulative move d-1 -> d+h on dS_d
        for h in LP_H:
            ycum = y.rolling(h + 1).sum().shift(-h)
            Xc = ctrl.rolling(h + 1).sum().shift(-h)
            m = _ols(ycum.reindex(inwin), pd.concat([(ds / scale).rename("dS"), Xc], axis=1).reindex(inwin),
                     hac=max(5, h + 1))
            if m is not None:
                lp.append({**base, "asset": asset, "h": h, "b": m.params["dS"], "t": m.tvalues["dS"]})
        rows.append(r)
    return rows, lp


def summarize_lp(lp: pd.DataFrame) -> pd.DataFrame:
    """Reversal: share of the day-0/1 response still there after 5 and 10 days.
    Only computed when the day-0/1 response is itself significant (|t| >= 1.96);
    otherwise there is nothing to reverse and the ratio is noise."""
    out = []
    for key, g in lp.groupby(["iso3", "vote_date", "kind", "asset"]):
        b, t = g.set_index("h")["b"], g.set_index("h")["t"]
        peak = t.loc[[0, 1]].abs().idxmax()
        sig = abs(t.loc[peak]) >= 1.96
        out.append({"iso3": key[0], "vote_date": key[1], "kind": key[2], "asset": key[3],
                    "b_h0": b.get(0), "t_h0": t.get(0), "b_h1": b.get(1), "t_h1": t.get(1),
                    "b_h5": b.get(5), "t_h5": t.get(5), "b_h10": b.get(10), "t_h10": t.get(10),
                    "initial_response_significant": sig,
                    "retained_h5": b.get(5) / b.loc[peak] if sig else np.nan,
                    "retained_h10": b.get(10) / b.loc[peak] if sig else np.nan})
    return pd.DataFrame(out)


def pooled(sigs: list[dict], panel: pd.DataFrame, kind: str, asset: str) -> dict:
    """Stack elections, orienting the signal toward the market-preferred side
    (elections without a coded market-preferred side are dropped); controls
    enter election by election (Frisch-Waugh)."""
    ys, xs, ids = [], [], []
    for sig in sigs:
        if sig["kind"] != kind or sig["market_preferred"] not in ("a", "b"):
            continue
        c = ISO2[sig["iso3"]]
        col = f"{'FX' if asset == 'FX' else 'Y10'}_{c}"
        if col not in panel:
            continue
        days = sig["days"]
        lvl = sig["level"].reindex(pd.date_range(days[0] - pd.Timedelta(days=40), days[-1])).ffill()
        ds = lvl.reindex(pd.bdate_range(days[0] - pd.Timedelta(days=10), days[-1])).diff()
        ds = ds * (1 if sig["market_preferred"] == "a" else -1) / (10.0 if kind == "odds" else 1.0)
        y = _daily(panel, col, "fx" if asset == "FX" else "bp")
        d = pd.concat([y.rename("y"), ds.rename("x"), _controls(panel)], axis=1).reindex(days).dropna()
        if len(d) < 15:
            continue
        C = sm.add_constant(d[["dDXY", "dUS10", "dVIX"]])
        ys.append(sm.OLS(d["y"], C).fit().resid)
        xs.append(sm.OLS(d["x"], C).fit().resid)
        ids.append(f"{sig['iso3']} {sig['vote_date']:%Y-%m-%d}")
    if not ys:
        return {"kind": kind, "asset": asset, "elections": 0}
    m = sm.OLS(pd.concat(ys).values, pd.concat(xs).values).fit(cov_type="HAC", cov_kwds={"maxlags": 5})
    return {"kind": kind, "asset": asset, "elections": len(ids), "which": "; ".join(ids), "n_days": int(m.nobs),
            "b_toward_market_preferred": m.params[0], "t": m.tvalues[0]}


def run(refresh: bool = False):
    OUT.mkdir(parents=True, exist_ok=True)
    panel = pd.read_csv(PROC / "daily_panel.csv", index_col=0, parse_dates=True)
    polls = poll_signals()
    eligible = [s for s in polls if s.get("per_week", 0) >= MIN_POLLS_PER_WEEK]
    sigs = odds_signals(refresh) + eligible
    rows, lps = [], []
    for s in sigs:
        r, lp = analyse(s, panel)
        rows += r
        lps += lp
    res = pd.DataFrame(rows)
    lp = pd.DataFrame(lps)
    res.to_csv(OUT / "sensitivity_leadlag.csv", index=False, float_format="%.4f")
    lp.to_csv(OUT / "local_projections.csv", index=False, float_format="%.4f")
    summarize_lp(lp).to_csv(OUT / "reversal.csv", index=False, float_format="%.4f")
    pd.DataFrame([pooled(sigs, panel, k, a) for k in ("odds", "polls") for a in ("FX", "Y10")]).to_csv(
        OUT / "pooled.csv", index=False, float_format="%.4f")
    # signal series used, for inspection
    sig_df = pd.concat({f"{s['kind']}_{s['iso3']}_{s['vote_date']:%Y%m%d}": s["level"] for s in sigs}, axis=1,
                       sort=True)
    sig_df.to_csv(OUT / "signals_daily.csv", float_format="%.3f")
    pd.DataFrame([{k: s.get(k) for k in ("iso3", "vote_date", "kind", "n_obs", "per_week", "signal_note")}
                  for s in polls]).to_csv(OUT / "poll_coverage.csv", index=False, float_format="%.2f")
    return res, lp


if __name__ == "__main__":
    run()
