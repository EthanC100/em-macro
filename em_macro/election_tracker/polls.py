"""Final poll average, following the original study's rule (docs/elections/ORIGINAL_STUDY.md section 2).

* Take the most recent poll from each pollster whose fieldwork ended before the vote.
* Window: fieldwork ending in the final 7 days; widened to 10 days when fewer than 2
  pollsters qualify (the study's Poland rule) and to 21 days when still fewer than 2
  (the study's South Africa / Turkey / Indonesia rule, "roughly the final 3 weeks").
* Equal weight across pollsters.
* Normalisation per poll:
    - "candidate": rescale so the listed candidates sum to 100;
    - "two_option" (run-offs, referendums): a / (a + b) * 100;
    - "party": as published, divided by (1 - undecided) where an undecided share is reported.
* Party-commissioned (partisan) polls are excluded.
* The study also used reputable aggregators where they existed; that cannot be
  reproduced point-in-time from free sources, so it is not used.

Input: a DataFrame with columns
    pollster, fieldwork_end (date), [published (date)], [partisan (bool)], [undecided (pct)]
and one column per option share (pct).
"""
from __future__ import annotations

import pandas as pd

WINDOWS = (7, 10, 21)
MIN_POLLSTERS = 2


def _normalise(df: pd.DataFrame, options: list[str], kind: str, a: str, b: str) -> pd.DataFrame:
    out = df.copy()
    if kind == "candidate":
        tot = out[options].sum(axis=1, min_count=1)
        for o in options:
            out[o] = 100.0 * out[o] / tot
    elif kind == "two_option":
        tot = out[a] + out[b]
        out[a], out[b] = 100.0 * out[a] / tot, 100.0 * out[b] / tot
    elif kind == "party":
        if "undecided" in out:
            und = pd.to_numeric(out["undecided"], errors="coerce").fillna(0.0)
            scale = 1.0 / (1.0 - und / 100.0)
            for o in options:
                out[o] = out[o] * scale
    else:
        raise ValueError(f"unknown race kind {kind!r}")
    return out


def final_poll_average(polls: pd.DataFrame, vote_date, options: list[str], kind: str,
                       as_of=None) -> dict:
    """Final poll average for the two leading options.

    `options` lists every option column to use (for "candidate" normalisation all listed
    candidates count). `as_of` (default: the vote date) excludes polls published on or after
    it, when a publication date is known. Returns a dict with the leader (a), runner-up (b),
    their average shares, the margin a - b, the window used and the pollsters included.
    """
    vote = pd.Timestamp(vote_date).normalize()
    cutoff = pd.Timestamp(as_of).normalize() if as_of is not None else vote
    df = polls.copy()
    df["fieldwork_end"] = pd.to_datetime(df["fieldwork_end"]).dt.normalize()
    for o in options:
        df[o] = pd.to_numeric(df[o], errors="coerce")
    df = df[df["fieldwork_end"] < vote]
    if "published" in df:
        pub = pd.to_datetime(df["published"], errors="coerce")
        df = df[pub.isna() | (pub < cutoff)]
    df = df[df["fieldwork_end"] < cutoff]
    if "partisan" in df:
        df = df[~df["partisan"].fillna(False).astype(bool)]
    df = df.dropna(subset=options, how="all")
    df = df[df["pollster"].astype(str).str.strip() != ""]

    empty = {"a": None, "b": None, "share_a": None, "share_b": None, "margin": None,
             "window_days": None, "n_pollsters": 0, "pollsters": [], "thin": True}
    if df.empty or len(options) < 2:
        return empty

    for w in WINDOWS:
        sub = df[df["fieldwork_end"] >= vote - pd.Timedelta(days=w)]
        if sub["pollster"].nunique() >= MIN_POLLSTERS:
            break
    if sub.empty:
        return empty
    order = ["fieldwork_end"] + (["published"] if "published" in sub else [])
    last = sub.sort_values(order).groupby("pollster", sort=False).tail(1)

    # leader and runner-up on the as-published average, then normalise for that pair
    raw_mean = last[options].mean()
    a, b = raw_mean.sort_values(ascending=False).index[:2]
    norm = _normalise(last, options, kind, a, b)
    share_a, share_b = float(norm[a].mean()), float(norm[b].mean())
    if share_b > share_a:                       # normalisation can reorder a near-tie
        a, b, share_a, share_b = b, a, share_b, share_a
    return {"a": a, "b": b, "share_a": share_a, "share_b": share_b, "margin": share_a - share_b,
            "window_days": w, "n_pollsters": int(last["pollster"].nunique()),
            "pollsters": sorted(last["pollster"].astype(str).tolist()),
            "thin": int(last["pollster"].nunique()) < MIN_POLLSTERS}
