"""Build the event calendars (data/events/*.csv) from sources and research files.

* Brazil rate decisions: BCB Copom history API + Focus survey expectations.
* Other rate decisions and all elections: hand-compiled, sourced research files
  in data/events/raw/ (see the *_NOTES.md files there).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import sources as S
from .config import EVENTS, ISO3_ALL, START

ISO2 = {v: k for k, v in ISO3_ALL.items()}


def brazil_copom(refresh: bool = False) -> pd.DataFrame:
    cp = S.bcb_copom(refresh)
    cp["date"] = pd.to_datetime(cp["DataReuniaoCopom"]).dt.tz_convert("America/Sao_Paulo").dt.tz_localize(None).dt.normalize()
    cp = cp.sort_values("date").reset_index(drop=True)
    cp["rate_before_pct"] = cp["MetaSelic"].shift(1)
    cp = cp[cp["date"] >= START].copy()
    cp["extra"] = cp["ReuniaoExtraordinaria"].astype(bool)
    # Focus labels scheduled meetings Rk/YYYY, k = order within the year
    cp["k"] = cp[~cp.extra].groupby(cp["date"].dt.year).cumcount() + 1
    cp["label"] = np.where(cp.extra, None, "R" + cp["k"].astype("Int64").astype(str) + "/" + cp["date"].dt.year.astype(str))

    f = S.bcb_focus_selic(refresh)
    f = f[f["baseCalculo"] == 0].copy()
    f["Data"] = pd.to_datetime(f["Data"])
    exp = []
    for r in cp.itertuples():
        g = f[(f["Reuniao"] == r.label) & (f["Data"] < r.date)]
        if g.empty:
            exp.append((np.nan, None))
        else:
            last = g.loc[g["Data"].idxmax()]
            exp.append((last["Mediana"], last["Data"].date()))
    cp["expected_rate"] = [e[0] for e in exp]
    cp["expectation_date"] = [e[1] for e in exp]

    out = pd.DataFrame({
        "country": "Brazil", "iso3": "BRA", "announce_date": cp["date"].dt.date,
        "announce_time_local": "after market close (~18:00-18:30 BRT)",
        "rate_after_pct": cp["MetaSelic"], "rate_before_pct": cp["rate_before_pct"],
        "change_bp": ((cp["MetaSelic"] - cp["rate_before_pct"]) * 100).round(0),
        "scheduled": np.where(cp.extra, "N", "Y"), "policy_rate_name": "Selic target",
        "source": "https://www.bcb.gov.br/api/servico/sitebcb/historicotaxasjuros",
        "expected_change_bp": ((cp["expected_rate"] - cp["rate_before_pct"]) * 100).round(1),
        "expectation_basis": "BCB Focus survey median Selic for this meeting, last survey date before the "
                             "meeting (" + cp["expectation_date"].astype(str) + ")",
        "expectation_source": "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/ExpectativasMercadoSelic",
        "notes": "meeting " + cp["NumeroReuniaoCopom"].astype(int).astype(str),
    })
    out.loc[out["expected_change_bp"].isna(), ["expectation_basis", "expectation_source"]] = ""
    out["decision"] = np.select([out.change_bp > 0, out.change_bp < 0], ["hike", "cut"], "hold")
    return out


RATE_COLS = ["country", "iso3", "announce_date", "announce_time_local", "rate_after_pct", "rate_before_pct",
             "change_bp", "decision", "scheduled", "policy_rate_name", "source", "expected_change_bp",
             "expectation_basis", "expectation_source", "notes"]


def rate_decisions(refresh: bool = False) -> pd.DataFrame:
    parts = [brazil_copom(refresh)]
    for f in sorted((EVENTS / "raw").glob("rate_decisions_*.csv")):
        parts.append(pd.read_csv(f, dtype={"announce_time_local": str}))
    df = pd.concat(parts, ignore_index=True)[RATE_COLS]
    df["announce_date"] = pd.to_datetime(df["announce_date"]).dt.date
    df = df[pd.to_datetime(df["announce_date"]) >= START]
    # NBP extraordinary meeting on liquidity measures, no rate vote (see NOTES)
    df = df[~((df["iso3"] == "POL") & (pd.to_datetime(df["announce_date"]) == "2008-10-08"))]
    df = df.sort_values(["iso3", "announce_date"]).reset_index(drop=True)
    df.to_csv(EVENTS / "rate_decisions.csv", index=False)
    return df


def elections() -> pd.DataFrame:
    parts = [pd.read_csv(f) for f in sorted((EVENTS / "raw").glob("elections_*.csv"))]
    df = pd.concat(parts, ignore_index=True)
    df["vote_date"] = pd.to_datetime(df["vote_date"]).dt.date
    df = df.sort_values(["iso3", "vote_date"]).reset_index(drop=True)
    df.to_csv(EVENTS / "elections.csv", index=False)
    return df


def to_event_table(rates: pd.DataFrame, elec: pd.DataFrame) -> pd.DataFrame:
    """Normalize both calendars to the event-study schema."""
    r = pd.DataFrame({
        "country": rates["iso3"].map(ISO2), "event_type": "rate_decision",
        "subtype": rates["decision"], "event_date": pd.to_datetime(rates["announce_date"]),
        "change_bp": pd.to_numeric(rates["change_bp"], errors="coerce"),
        "expected_change_bp": pd.to_numeric(rates["expected_change_bp"], errors="coerce"),
        "scheduled": rates["scheduled"]})
    # operational-framework changes coded as rate moves in the source calendar but
    # with no change in the effective policy stance (see rate_decisions_tr_id_NOTES.md)
    technical = (rates["iso3"] == "TUR") & (pd.to_datetime(rates["announce_date"]) == "2018-05-28")
    r.loc[technical.values, "subtype"] = "technical"
    r["surprise_bp"] = r["change_bp"] - r["expected_change_bp"]
    r["event_id"] = "RD_" + r["country"] + "_" + r["event_date"].dt.strftime("%Y%m%d")

    e = elec.copy()
    num = lambda c: pd.to_numeric(e[c], errors="coerce")
    poll_err = num("actual_margin_pp") - num("poll_margin_pp")       # positive: poll leader beat polls
    orient = e["market_preferred"].map({"a": 1.0, "b": -1.0})
    # odds surprise: did candidate a win, minus its pre-vote probability.  Only for
    # votes that settle the contest (not first rounds that went to a run-off,
    # where the quoted market was on the eventual winner).
    fav = e["odds_favourite"].fillna("").astype(str).str.lower().str.split().str[0]
    fav_is_a = pd.Series([isinstance(f, str) and bool(f) and f in str(a).lower() for f, a in zip(fav, e["cand_a"])], index=e.index)
    p_a = pd.Series(np.where(fav_is_a, num("odds_prob_favourite"), 1 - num("odds_prob_favourite")), index=e.index)
    a_won = (num("actual_margin_pp") > 0).astype(float)
    went_to_runoff = e["winner"].astype(str).str.contains("runoff|run-off", case=False)
    odds_surprise_a = (a_won - p_a).where(~went_to_runoff)
    el = pd.DataFrame({
        "country": e["iso3"].map(ISO2), "event_type": "election",
        "subtype": e["type"].astype(str) + np.where(num("round") == 2, "_r2", ""),
        "event_date": pd.to_datetime(e["vote_date"]),
        "poll_margin_pp": num("poll_margin_pp"), "actual_margin_pp": num("actual_margin_pp"),
        "abs_poll_error_pp": poll_err.abs(),
        "surprise_mp_pp": poll_err * orient,                      # + = market-preferred side beat polls
        "odds_surprise_mp": odds_surprise_a * orient,             # + = market-preferred side did better than odds
        "market_preferred": e["market_preferred"], "election": e["election"], "round": num("round")})
    el["event_id"] = ("EL_" + el["country"] + "_" + el["event_date"].dt.strftime("%Y%m%d"))
    # one event per country-day: a referendum held alongside a general vote is dropped
    el = el.sort_values("subtype", key=lambda s: s.str.startswith("referendum")).drop_duplicates("event_id")
    return pd.concat([r, el], ignore_index=True)
