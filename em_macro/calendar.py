"""Unified dated event calendar for the 13-country extension.

    python -m em_macro.calendar     # -> data/events/calendar_13.csv, results/calendar_coverage.md

Stacks, with one row per dated event and a source URL on every row:
  * elections        data/events/raw/elections_*.csv
  * government events data/events/raw/govt_events_*.csv
                     (government_collapse, confidence_vote, budget)
  * rating actions   data/events/raw/rating_actions_*.csv (initial_state rows excluded)
  * rate decisions   data/events/rate_decisions.csv (original six countries)
"""
from __future__ import annotations

import pandas as pd

from .config import EVENTS, RESULTS
from .panel import ISO3, NAMES

COLS = ["iso3", "country", "date", "event_type", "subtype", "description", "outcome", "source", "notes"]


def _elections() -> pd.DataFrame:
    e = pd.concat([pd.read_csv(f) for f in sorted((EVENTS / "raw").glob("elections_*.csv"))], ignore_index=True)
    e["vote_date"] = pd.to_datetime(e["vote_date"], errors="coerce")
    e.sort_values(["iso3", "vote_date"]).to_csv(EVENTS / "elections.csv", index=False,
                                                date_format="%Y-%m-%d")
    rnd = pd.to_numeric(e["round"], errors="coerce")
    return pd.DataFrame({
        "iso3": e["iso3"], "date": e["vote_date"], "event_type": "election",
        "subtype": e["type"].astype(str) + rnd.map(lambda r: "_r2" if r == 2 else ""),
        "description": e["election"], "outcome": e["winner"],
        "source": e["actual_source"].fillna(e["poll_source"]), "notes": e["notes"]})


def _govt() -> pd.DataFrame:
    files = sorted((EVENTS / "raw").glob("govt_events_*.csv"))
    if not files:
        return pd.DataFrame(columns=COLS)
    g = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    g["date"] = pd.to_datetime(g["date"], errors="coerce")
    return g[["iso3", "date", "event_type", "subtype", "description", "outcome", "source", "notes"]]


def _ratings() -> pd.DataFrame:
    files = sorted((EVENTS / "raw").glob("rating_actions_*.csv"))
    r = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    r = r[r["action"] != "initial_state"]
    return pd.DataFrame({
        "iso3": r["iso3"], "date": pd.to_datetime(r["date"], errors="coerce"), "event_type": "rating_action",
        "subtype": r["agency"].astype(str) + ":" + r["action"].astype(str),
        "description": (r["agency"].astype(str) + " " + r["rating_before"].astype(str) + "/" + r["outlook_before"].astype(str)
                        + " -> " + r["rating_after"].astype(str) + "/" + r["outlook_after"].astype(str)),
        "outcome": r["action"], "source": r["source"], "notes": r["notes"]})


def _rate_decisions() -> pd.DataFrame:
    f = EVENTS / "rate_decisions.csv"
    if not f.exists():
        return pd.DataFrame(columns=COLS)
    r = pd.read_csv(f)
    return pd.DataFrame({
        "iso3": r["iso3"], "date": pd.to_datetime(r["announce_date"], errors="coerce"),
        "event_type": "rate_decision", "subtype": r["decision"],
        "description": r["policy_rate_name"].astype(str) + ": " + r["rate_before_pct"].astype(str) + " -> "
                       + r["rate_after_pct"].astype(str),
        "outcome": r["change_bp"], "source": r["source"], "notes": r["notes"]})


def build() -> pd.DataFrame:
    cal = pd.concat([_elections(), _govt(), _ratings(), _rate_decisions()], ignore_index=True)
    name = {ISO3[k]: v for k, v in NAMES.items()}
    cal["date"] = pd.to_datetime(cal["date"], errors="coerce")
    cal["country"] = cal["iso3"].map(name)
    cal = cal[cal["date"] >= "2005-01-01"].sort_values(["date", "iso3", "event_type"])[COLS]
    cal.to_csv(EVENTS / "calendar_13.csv", index=False, date_format="%Y-%m-%d")
    coverage(cal)
    return cal


def coverage(cal: pd.DataFrame):
    order = list(ISO3.values())
    t = cal.pivot_table(index="event_type", columns="iso3", values="date", aggfunc="count").reindex(columns=order)
    span = cal.groupby(["event_type", "iso3"])["date"].agg(["min", "max"])
    nosrc = cal["source"].isna().sum()
    L = ["# Event calendar coverage (13 countries)", "",
         f"`data/events/calendar_13.csv`: {len(cal)} dated events from {cal['date'].min():%Y-%m-%d} to "
         f"{cal['date'].max():%Y-%m-%d}; rows without a source URL: {nosrc}.", "",
         "| event type | " + " | ".join(order) + " |", "|---|" + "---|" * len(order)]
    for et, r in t.iterrows():
        L.append(f"| {et} | " + " | ".join("" if pd.isna(v) else str(int(v)) for v in r.values) + " |")
    L += ["", "Rate decisions are compiled for the original six countries only (ECB, BoE, BanRep and BCCh "
          "decisions are not in the calendar yet).", "",
          "## Subtypes", ""]
    for et, g in cal.groupby("event_type"):
        vc = g["subtype"].value_counts()
        if et == "rating_action":
            vc = g["outcome"].value_counts()
        L.append(f"- **{et}**: " + ", ".join(f"{k} ({v})" for k, v in vc.head(25).items()))
    L += ["", "## First and last event by type and country", "",
          "| event type | country | first | last |", "|---|---|---|---|"]
    for (et, iso), r in span.iterrows():
        L.append(f"| {et} | {iso} | {r['min']:%Y-%m-%d} | {r['max']:%Y-%m-%d} |")
    (RESULTS / "calendar_coverage.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    build()
