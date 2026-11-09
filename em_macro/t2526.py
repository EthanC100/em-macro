"""T25-T26: zero-size live shadows of the T21 basis-momentum and T22 diversified trend sleeves.

    python -m em_macro.t2526 golive [--today D]   # once, after the pre-live checks: fixes M1, both dates, universe, N
    python -m em_macro.t2526 daily  [--today D]   # every ledger-daily run: rebuild the live path, write the files
    python -m em_macro.t2526 status
    python -m em_macro.t2526 evaluate --date D    # on the dates of section 5.1 only

Pre-registration: docs/prereg/T25-T26_live_shadows.md with Amendment 1. The a160bfd code is called unchanged
(``t2022.Mkt``, ``signal_t21``, ``signal_t22``, ``build_targets``, ``Sleeve``, ``combine``, ``nw_tstat``, ``holm``),
fed from the Databento contract files through ``t2526_data.databento_layout``. Each sleeve is built with ``months``
= the live months only, so it starts flat at M1 and no restricted-universe history exists.

**Public** (this repository, ``results/shadows/<id>/``): positions as weights and contract codes, monthly and daily
returns in %, status. **Private** (em-macro-data ``shadows/<id>/``): per-market daily gross P&L and trades.
**Never published:** any settlement or price.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import commod_data as CD
from . import t2526_data as D
from .config import ROOT

TRIALS = ("T25", "T26")
KIND = {"T25": "T21", "T26": "T22"}
NAME = {"T25": "T21 basis-momentum shadow", "T26": "T22 diversified trend shadow"}
SR_POOLED = {"T25": 0.4346, "T26": 0.4998}            # §5.2, fixed before any live data
N0 = {"T25": 20, "T26": 30}
FIRST_MONTHS, EXTENSION_MONTHS = 60, 36               # §5.1
DECAY_ALPHA = 0.05                                    # §5.3, one-sided, Holm across the sleeves evaluated
SR_MARGIN, DD_MARGIN = 0.05, 1.10                     # T20-T22 non-inferiority margins
OUT = ROOT / "results/shadows"
GO_LIVE = OUT / "GO_LIVE.json"
# a160bfd trial code (pre-registration P0)
A160_HASHES = {
    "em_macro/t2022.py": "d54cdc750668baa26eb408bfb394ec25e0467fd6e7b77ea919583f8a3345528a",
    "em_macro/commod_data.py": "e5ffe76b98d959d268f46e38b97eb2bfe78aa2f114922efb43b9bbbb8f49cb25",
    "em_macro/commod_build0.py": "2c58f7e2bde920e76605d973a2cf6763fdf49b670c7724a33265affaf5e1951c",
    "em_macro/t18_rebal.py": "dda6456d676281b48080d3c0a6c304d51c928cea39e0f70c696a364a10f96c43",
    "em_macro/systematic.py": "1eb4cf6b1c537c1711e5fff0b7aa044fee932c20992eb0d3cea4c3c5fc50be66",
    "em_macro/systematic_v11.py": "b3c4404ed80209efd1b3fa0e993f30bbac2650b2a9af042f07f8e21175885952",
    "em_macro/t01.py": "bc52b3e01869efd0bf8c18bc891bcd17df376e96bbc8e68e40fe2f8412432b2b",
}


# ----------------------------------------------------------------------------- dates and the prediction
def sr_pred(trial: str, n: int) -> float:
    return SR_POOLED[trial] * math.sqrt(n / N0[trial])


def first_rebalance_month(today: date) -> pd.Period:
    """The first v1.0/v1.1 rebalance (the 3rd) on or after ``today``."""
    p = pd.Period(today, "M")
    return p if today.day <= 3 else p + 1


def evaluation_dates(m1: pd.Period) -> tuple[date, date]:
    first_last = m1 + FIRST_MONTHS - 1
    second_last = m1 + FIRST_MONTHS + EXTENSION_MONTHS - 1
    d1 = (first_last + 1).to_timestamp().date().replace(day=15)
    d2 = (second_last + 1).to_timestamp().date().replace(day=15)
    return d1, d2


def p0_hashes(root: Path = ROOT) -> dict:
    got = {f: hashlib.sha256((root / f).read_bytes()).hexdigest() for f in A160_HASHES}
    return {"ok": all(got[f] == h for f, h in A160_HASHES.items()),
            "mismatch": [f for f in A160_HASHES if got[f] != A160_HASHES[f]]}


def _commit() -> str:
    import os
    import subprocess
    if os.environ.get("GITHUB_SHA"):
        return os.environ["GITHUB_SHA"]
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    except OSError:
        return ""


def _dates(m1: pd.Period) -> dict:
    d1, d2 = evaluation_dates(m1)
    return {"M1": str(m1),
            "first_evaluation": {"months": f"{m1}..{m1 + FIRST_MONTHS - 1}", "date": d1.isoformat()},
            "second_evaluation": {"months": f"{m1}..{m1 + FIRST_MONTHS + EXTENSION_MONTHS - 1}",
                                  "date": d2.isoformat(), "applies_to": "sleeves inconclusive at the first evaluation"}}


def golive(today: date | None = None, prelive: Path = D.PRELIVE, out: Path | None = None) -> dict:
    """Write the go-live record (§8 item 4) with P0 and the pre-live check (Amendment 1 A1.2 and P1). M1 is the
    first rebalance on or after ``today``; it is provisional until ``daily`` passes P3 and P4 at M1's rebalance, and
    a P4 failure moves it to the next rebalance. Refuses on or after 5 May 2027, without the pre-live check, with a
    changed a160bfd file, or with fewer than 6 markets; never overwrites an existing record."""
    today = today or date.today()
    out = out or GO_LIVE
    if out.exists():
        return {"ok": False, "reason": "already live", **json.loads(out.read_text())}
    return _golive_record(today, prelive, out)


def golive_amend(prelive: Path = D.PRELIVE_A2, out: Path | None = None) -> dict:
    """Amendment 2: replace the universe, N and SR_pred of a provisional (not yet confirmed) go-live record with
    the single rerun's result. M1 and both evaluation dates are kept; refuses once go-live is confirmed."""
    out = out or GO_LIVE
    if not out.exists():
        return {"ok": False, "reason": "no go-live record to amend"}
    g = json.loads(out.read_text())
    if g.get("confirmed"):
        return {"ok": False, "reason": "go-live already confirmed: the universe is fixed"}
    if g.get("amendment_2"):
        return {"ok": False, "reason": "already amended by the Amendment 2 rerun"}
    if not prelive.exists():
        return {"ok": False, "reason": f"no Amendment 2 rerun ({prelive.name})"}
    pre = json.loads(prelive.read_text())
    uni = {k: list(pre["universe_after_check"].get(k, [])) for k in TRIALS}
    small = [k for k in TRIALS if len(uni[k]) < 6]
    if small:
        return {"ok": False, "reason": f"fewer than 6 markets after the rerun: {small}"}
    p0 = p0_hashes()
    if not p0["ok"]:
        return {"ok": False, "reason": f"P0: a160bfd files changed: {p0['mismatch']}"}
    rec = {**g, "universe": uni, "N": {k: len(v) for k, v in uni.items()},
           "sr_pred": {k: round(sr_pred(k, len(uni[k])), 4) for k in TRIALS}, "P0": p0,
           "amendment_2": {"amended_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                           "prelive": f"results/shadows/{prelive.name}", "before": {"universe": g["universe"],
                                                                                    "N": g["N"], "sr_pred": g["sr_pred"]},
                           "commit": _commit()},
           "rules": "docs/prereg/T25-T26_live_shadows.md with Amendments 1 and 2"}
    out.write_text(json.dumps(rec, indent=1) + "\n")
    return {"ok": True, **rec}


def _golive_record(today: date, prelive: Path, out: Path) -> dict:
    if today >= date(2027, 5, 5):
        return {"ok": False, "reason": "on or after 5 May 2027: not evaluable (Amendment 1 A1.2 item 5)"}
    if not prelive.exists():
        return {"ok": False, "reason": "no pre-live check (results/shadows/prelive.json)"}
    pre = json.loads(prelive.read_text())
    p0 = p0_hashes()
    if not p0["ok"]:
        return {"ok": False, "reason": f"P0: a160bfd files changed: {p0['mismatch']}"}
    uni = {k: list(pre["universe_after_check"].get(k, [])) for k in TRIALS}
    small = [k for k in TRIALS if len(uni[k]) < 6]
    if small:
        return {"ok": False, "reason": f"fewer than 6 markets after the pre-live check: {small}"}
    m1 = first_rebalance_month(today)
    rec = {"recorded_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(), **_dates(m1),
           "confirmed": False, "universe": uni, "N": {k: len(v) for k, v in uni.items()},
           "sr_pred": {k: round(sr_pred(k, len(uni[k])), 4) for k in TRIALS},
           "P0": p0, "P1_P2": {"prelive_checked_at": pre.get("checked_at"), "file": "results/shadows/prelive.json"},
           "commit": _commit(), "rules": "docs/prereg/T25-T26_live_shadows.md with Amendment 1"}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rec, indent=1) + "\n")
    return {"ok": True, **rec}


# ----------------------------------------------------------------------------- the sleeves
def load_markets(codes: list[str], end_month: pd.Period, base: Path | None = None) -> dict:
    """``t2022.Mkt`` per market on the Databento contract files. A market with no files is left out (missing in
    every month, §7.2)."""
    from . import t2022 as T
    mks = {}
    with D.databento_layout(end_month, base):
        for c in codes:
            try:
                mks[c] = T.Mkt(c, pd.DataFrame(columns=["EUR", "GBP"]))
            except FileNotFoundError:
                continue
    return mks


def rebalance_ready(m: pd.Period, codes: list[str], mks: dict, today: date) -> tuple[bool, list[str]]:
    """§4.2 and §7.2: a month is computed once every universe market has its decision-date settlements stored, or
    after the 10th of the month with the markets still missing then. Returns (ready, missing markets)."""
    missing = [c for c in codes if c not in mks or m not in mks[c].rolls.index or bool(mks[c].rolls.at[m, "missing"])]
    if not missing:
        return True, []
    return today > date(m.year, m.month, 10), missing


def freeze_rebalances(m1: pd.Period, codes: list[str], mks: dict, today: date, frozen: dict) -> dict:
    """Months computed so far, each with its missing markets, fixed the first time the month is computed (a market
    missing then stays missing for that month even if its settlement arrives later)."""
    frozen = dict(frozen)
    m = m1
    while m <= pd.Period(today, "M"):
        if str(m) not in frozen:
            ok, missing = rebalance_ready(m, codes, mks, today)
            if not ok:
                break
            frozen[str(m)] = {"computed_on": today.isoformat(), "missing": missing}
        m += 1
    return frozen


def force_missing(mks: dict, frozen: dict, dropped: dict) -> None:
    """Apply the frozen missing markets and the drops (§7.4: from the drop month on) to the a160bfd rolls flag."""
    for ms, rec in frozen.items():
        m = pd.Period(ms, "M")
        for c in rec["missing"]:
            if c in mks and m in mks[c].rolls.index:
                mks[c].rolls.at[m, "missing"] = True
    for c, d in dropped.items():
        if c in mks:
            r = mks[c].rolls
            r.loc[r.index >= pd.Period(d["from_month"], "M"), "missing"] = True


def build_sleeve(trial: str, codes: list[str], months: pd.PeriodIndex, end_month: pd.Period, base: Path | None = None,
                 frozen: dict | None = None, dropped: dict | None = None, mks: dict | None = None):
    """The a160bfd sleeve on the Databento contract files, targets for ``months`` only (starts flat, §2.2 D3)."""
    from . import t2022 as T
    mks = mks if mks is not None else load_markets(codes, end_month, base)
    force_missing(mks, frozen or {}, dropped or {})
    sig, sgm = {}, {}
    for c, mk in mks.items():
        if KIND[trial] == "T21":
            sgm[c] = mk.sigma_blend()
            sig[c] = T.signal_t21(mk)
        else:
            sgm[c] = mk.sigma_mop()
            sig[c] = T.signal_t22(mk, sgm[c])
    W, SG = T.build_targets(mks, sig, sgm, KIND[trial], months)
    sl = T.Sleeve(NAME[trial], mks, W, SG)
    if dropped:
        apply_drops(sl, dropped, months)
    return sl, mks, W, sig, sgm


def apply_drops(sl, dropped: dict, months: pd.PeriodIndex) -> None:
    """§7.4 / T20-T22 §2.1 rule 5: a dropped market is closed in full at the drop month's rebalance (its last
    settlement carried forward, so the exit is at the last settlement) and the exit costs 3x the one-way cost: the
    a160bfd closing trade charges 1x c_raw, 2x more is added at the exit date."""
    changed = False
    for c, d in dropped.items():
        if c not in sl.held.columns:
            continue
        f = pd.Period(d["from_month"], "M")
        sel = sl.held.index >= f
        if (sl.held.loc[sel, c] != 0).any() or (sl.targets.loc[sel, c] != 0).any():
            sl.held.loc[sel, c] = 0.0
            sl.targets.loc[sel, c] = 0.0
            changed = True
    if changed:
        sl.daily_gross, sl.daily_cost1, sl.per_market_gross, sl.trades = sl._daily()
    extra = pd.Series(0.0, index=sl.daily_cost1.index)
    rows = []
    for c, d in dropped.items():
        if c not in sl.mks:
            continue
        mk, f = sl.mks[c], pd.Period(d["from_month"], "M")
        t = (sl.trades[(sl.trades["market"] == c) & (sl.trades["month"] == d["from_month"]) & (sl.trades["w_new"] == 0)]
             if not sl.trades.empty else sl.trades)
        if len(t):
            for _, row in t.iterrows():
                extra[row["date"]] += 2.0 * abs(row["w_old"]) * sl.c_raw(mk, row["contract_old"], row["date"])
            continue
        # no settlement at all at the drop month's rebalance (the market stopped): the a160bfd loop has no closing
        # trade, so the exit is charged here in full (3x), at the last settlement's price, on the first day of the
        # book on or after the drop month's execution date in the other markets
        prior = [m for m in mk.rolls.index if m < f and m in sl.held.index]
        if not prior or sl.held.at[prior[-1], c] == 0 or not len(extra):
            continue
        w_old, contract = float(sl.held.at[prior[-1], c]), mk.rolls.at[prior[-1], "F1"]
        last = mk.md.close[contract].dropna().index[-1]
        ex = [o.rolls.at[f, "execution"] for o in sl.mks.values() if f in o.rolls.index]
        when = min(ex) if ex else pd.Timestamp(f.year, f.month, 3)
        on = extra.index[extra.index >= when]
        if not len(on):
            continue
        extra[on[0]] += 3.0 * abs(w_old) * sl.c_raw(mk, contract, last)
        rows.append({"market": c, "month": str(f), "date": on[0], "kind": "exit (dropped, §7.4)", "w_old": w_old,
                     "w_new": 0.0, "contract_old": contract, "contract_new": None})
    if extra.any():
        sl.daily_cost1 = sl.daily_cost1 + extra
    if rows:
        sl.trades = pd.concat([sl.trades, pd.DataFrame(rows)], ignore_index=True)


def detect_drops(sl, mks: dict, frozen: dict, dropped: dict, limit: int = 20) -> dict:
    """§7.4: a held contract without a final settlement for more than ``limit`` consecutive trading days (the union
    of the universe markets' settlement days) is dropped from the next rebalance after the 21st such day."""
    dropped = dict(dropped)
    days = sorted(set().union(*[set(mk.days) for mk in mks.values()])) if mks else []
    if not frozen or not days:
        return dropped
    last_m = pd.Period(max(frozen), "M")
    days = pd.DatetimeIndex(days)
    for c, mk in mks.items():
        if c in dropped or last_m not in sl.held.index or sl.held.at[last_m, c] == 0:
            continue
        r = mk.rolls[mk.rolls.index <= last_m]
        if r.empty:
            continue
        contract = r["F1"].iloc[-1]
        s = mk.md.close[contract].dropna()
        if s.empty:
            continue
        after = days[days > s.index[-1]]
        if len(after) > limit:
            d21 = after[limit]
            f = pd.Period(d21, "M") + (1 if d21.day >= 3 else 0)
            dropped[c] = {"contract": contract, "last_settlement": str(s.index[-1].date()),
                          "detected_day": str(d21.date()), "from_month": str(f),
                          "rule": "§7.4: more than 20 consecutive trading days without a final settlement"}
    return dropped


def live_months(frozen: dict) -> pd.PeriodIndex:
    return pd.PeriodIndex(sorted(pd.Period(m, "M") for m in frozen), freq="M")


def pending_cutoff(m_next: pd.Period, mks: dict):
    """First execution date of a month not yet computed: P&L from then on waits for that rebalance (§7.8)."""
    ex = [mk.rolls.at[m_next, "execution"] for mk in mks.values() if m_next in mk.rolls.index]
    return min(ex) if ex else None


def read_status(trial: str, out: Path) -> dict:
    p = out / trial / "status.json"
    return json.loads(p.read_text()) if p.exists() else {}


def run_trial(trial: str, g: dict, today: date, base: Path | None, out: Path, end_month: pd.Period | None = None):
    """Rebuild the live path from M1 (as v1.0's update does) with the frozen months and drops of the last status."""
    m1 = pd.Period(g["M1"], "M")
    end_month = end_month or pd.Period(today, "M")
    st = read_status(trial, out)
    codes = list(g["universe"][trial])
    mks = load_markets(codes, end_month, base)
    frozen = {k: v for k, v in st.get("rebalances", {}).items() if pd.Period(k, "M") >= m1}
    frozen = freeze_rebalances(m1, codes, mks, today, frozen)
    frozen = {k: v for k, v in frozen.items() if pd.Period(k, "M") <= end_month}
    dropped = dict(st.get("dropped", {}))
    months = live_months(frozen)
    sl, mks, W, sig, sgm = build_sleeve(trial, codes, months, end_month, base, frozen, dropped, mks)
    new_drops = detect_drops(sl, mks, frozen, dropped)
    if new_drops != dropped:
        dropped = new_drops
        mks = load_markets(codes, end_month, base)
        sl, mks, W, sig, sgm = build_sleeve(trial, codes, months, end_month, base, frozen, dropped, mks)
    return {"sl": sl, "mks": mks, "W": W, "sig": sig, "sgm": sgm, "frozen": frozen, "dropped": dropped,
            "months": months, "codes": codes}


def active_markets(run: dict, m: pd.Period) -> list[str]:
    """Markets eligible at month m under ``build_targets``' own condition (in the rolls, past entry, not missing, with
    sigma and a signal). A T21 rank weight can be exactly 0 for the middle market, so non-zero weights would
    undercount."""
    from . import t2022 as T
    out = []
    for c, mk in run["mks"].items():
        if m not in mk.rolls.index or mk.entry is None or m < mk.entry or bool(mk.rolls.at[m, "missing"]):
            continue
        s = T.asof(run["sgm"][c], mk.rolls.at[m, "decision"])
        v = run["sig"][c].get(m, np.nan)
        if np.isfinite(s) and s > 0 and np.isfinite(v):
            out.append(c)
    return out


def p3_p4(trial: str, run: dict, m1: pd.Period) -> dict:
    """P3: markets with sigma and a signal at M1's decision date (counts); P4: active markets at M1, >= 6."""
    from . import t2022 as T
    ok3 = []
    for c, mk in run["mks"].items():
        if m1 in mk.rolls.index:
            t = mk.rolls.at[m1, "decision"]
            s = T.asof(run["sgm"][c], t)
            v = run["sig"][c].get(m1, np.nan)
            if np.isfinite(s) and s > 0 and np.isfinite(v):
                ok3.append(c)
    active = len(active_markets(run, m1))
    return {"P3_with_sigma_and_signal": len(ok3), "P3_without": sorted(set(run["codes"]) - set(ok3)),
            "P4_active": active, "P4_ok": active >= 6}


def confirm_golive(g: dict, runs: dict, today: date, path: Path) -> dict:
    """At M1's rebalance: P3 and P4. P4 below 6 in either sleeve moves go-live to the next rebalance (§8 item 3)."""
    m1 = pd.Period(g["M1"], "M")
    if not all(str(m1) in runs[k]["frozen"] for k in TRIALS):
        return g
    checks = {k: p3_p4(k, runs[k], m1) for k in TRIALS}
    if all(c["P4_ok"] for c in checks.values()):
        g = {**g, "confirmed": True, "confirmed_on": today.isoformat(), "P3_P4": checks, "commit": _commit()}
    else:
        moves = g.get("moved", []) + [{"from": str(m1), "on": today.isoformat(), "P3_P4": checks}]
        g = {**g, **_dates(m1 + 1), "moved": moves}
    path.write_text(json.dumps(g, indent=1) + "\n")
    return g


def daily(today: date | None = None, base: Path | None = None, out: Path = OUT, private: Path | None = None,
          go_live: Path | None = None) -> dict:
    """Rebuild each shadow's live path from M1 and write the public and private files."""
    today = today or date.today()
    go_live = go_live or (out / "GO_LIVE.json")
    if not go_live.exists():
        return {"live": False, "reason": "not live yet (no go-live record)"}
    g = json.loads(go_live.read_text())
    if pd.Period(today, "M") < pd.Period(g["M1"], "M"):
        return {"live": False, "reason": f"first live month {g['M1']}"}
    private = private or (CD.data_root() / "shadows")
    runs = {k: run_trial(k, g, today, base, out) for k in TRIALS}
    if not g.get("confirmed"):
        m1 = g["M1"]
        g = confirm_golive(g, runs, today, go_live)
        if not g.get("confirmed"):
            return {"live": False, "reason": f"go-live not confirmed (M1 {g['M1']}"
                                             f"{'; moved from ' + m1 if g['M1'] != m1 else ''})"}
    res = {k: write_outputs(k, runs[k], g, out, private, today) for k in TRIALS}
    return {"live": True, **res}


def write_outputs(trial: str, run: dict, g: dict, out: Path, private: Path, today: date) -> dict:
    sl, mks, W, months = run["sl"], run["mks"], run["W"], run["months"]
    m1 = pd.Period(g["M1"], "M")
    d = out / trial
    d.mkdir(parents=True, exist_ok=True)
    held = sl.held.reindex(months).fillna(0.0)
    targets = sl.targets.reindex(months).fillna(0.0)
    rows = []
    for m in months:
        for c, mk in mks.items():
            if abs(held.at[m, c]) > 0 or abs(targets.at[m, c]) > 0:
                f1 = mk.rolls.at[m, "F1"] if m in mk.rolls.index else None
                rows.append({"month": str(m), "market": c, "contract": f1 or "",
                             "target_weight": round(float(targets.at[m, c]), 6),
                             "held_weight": round(float(held.at[m, c]), 6)})
    pd.DataFrame(rows, columns=["month", "market", "contract", "target_weight", "held_weight"]).to_csv(
        d / "positions.csv", index=False)
    start = min((mk.rolls.at[m1, "execution"] for mk in mks.values() if m1 in mk.rolls.index), default=None)
    net = sl.daily_gross - 2.0 * sl.daily_cost1
    if start is None or not len(months):
        net = net.iloc[0:0]
    else:
        net = net[net.index >= start]                 # entry costs at M1's execution included
        cut = pending_cutoff(months[-1] + 1, mks)
        if cut is not None:
            net = net[net.index < cut]
    idx = (1 + net).cumprod() * 100
    pd.DataFrame({"date": idx.index.strftime("%Y-%m-%d"), "index_net_decisive": idx.round(4).values}).to_csv(
        d / "index.csv", index=False)
    last_day = net.index[-1] if len(net) else None

    def mon(x):
        x = x.reindex(months)
        return (100 * x).round(4).values

    # monthly returns from the daily path shown (a month still running is partial; a pending rebalance's days wait)
    def monthly_of(cost_mult):
        dd = (sl.daily_gross - cost_mult * sl.daily_cost1).reindex(net.index)
        return (1 + dd).groupby(dd.index.to_period("M")).prod() - 1

    mtab = pd.DataFrame({"month": [str(m) for m in months], "gross_%": mon(monthly_of(0.0)),
                         "cost_1x_%": mon(monthly_of(0.0) - monthly_of(1.0)), "net_decisive_%": mon(monthly_of(2.0)),
                         "net_2x_%": mon(monthly_of(4.0))})
    mtab.to_csv(d / "monthly.csv", index=False)
    active = {str(m): len(active_markets(run, m)) for m in months}
    status = {"trial": trial, "name": NAME[trial], "M1": str(m1), "months_live": len(months),
              "months_in_first_window": FIRST_MONTHS, "last_rebalance": str(months[-1]) if len(months) else None,
              "first_evaluation": g["first_evaluation"], "second_evaluation": g["second_evaluation"],
              "universe": g["universe"][trial], "N": g["N"][trial], "sr_pred": g["sr_pred"][trial],
              "rebalances": run["frozen"], "dropped": run["dropped"], "active_markets": active,
              "months_with_fewer_than_6": [m for m, n in active.items() if n < 6],
              "index": round(float(idx.iloc[-1]), 4) if len(idx) else 100.0,
              "index_as_of": str(last_day.date()) if last_day is not None else None, "as_of": today.isoformat(),
              "label": "zero size, paper; not part of v1.0, v1.1 or the fund",
              "note": (f"Evaluated on {g['first_evaluation']['date']} (and, if inconclusive, on "
                       f"{g['second_evaluation']['date']}); nothing before then is a result.")}
    (d / "status.json").write_text(json.dumps(status, indent=1) + "\n")
    p = private / trial
    p.mkdir(parents=True, exist_ok=True)
    sl.per_market_gross.to_csv(p / "per_market_daily_gross.csv")
    sl.trades.to_csv(p / "trades.csv", index=False)
    return {"months_live": len(months), "index": status["index"]}


# ----------------------------------------------------------------------------- evaluation (section 5.3)
def decay_test(r: pd.Series, sr_predicted: float) -> dict:
    """t_d = (m - m0) / se_NW with m0 = SR_pred / sqrt(12) x s (ddof 1); one-sided p = Phi(t_d)."""
    from . import t2022 as T
    r = pd.Series(r).dropna()
    s = float(r.std(ddof=1))
    m0 = sr_predicted / math.sqrt(12) * s
    _, t_d = T.nw_tstat(r - m0)
    p = 0.5 * (1 + math.erf(t_d / math.sqrt(2))) if np.isfinite(t_d) else 1.0
    return {"mean": float(r.mean()), "m0": m0, "t_d": t_d, "p_d": p, "months": len(r)}


def max_drawdown(r: pd.Series) -> float:
    w = (1 + pd.Series(r).dropna()).cumprod()
    return float((w / w.cummax() - 1).min())


def sharpe(r: pd.Series) -> float:
    r = pd.Series(r).dropna()
    return float(r.mean() / r.std(ddof=1) * math.sqrt(12)) if r.std(ddof=1) > 0 else float("nan")


def outcomes(evaluated: dict[str, dict], second: bool) -> dict[str, dict]:
    """``evaluated``: trial -> {"r": shadow monthly net (decisive), "comb": v1.1 + shadow monthly net,
    "v11": v1.1 monthly net, "sr_pred": float}. Returns trial -> outcome and its statistics (section 5.3)."""
    from . import t2022 as T
    dec = {k: decay_test(v["r"], v["sr_pred"]) for k, v in evaluated.items()}
    padj = T.holm({k: d["p_d"] for k, d in dec.items()}) if len(dec) > 1 else {k: d["p_d"] for k, d in dec.items()}
    out = {}
    for k, v in evaluated.items():
        dsr = sharpe(v["comb"]) - sharpe(v["v11"])
        dd_c, dd_v = max_drawdown(v["comb"]), max_drawdown(v["v11"])
        decayed = padj[k] < DECAY_ALPHA
        confirmed = (not decayed and dec[k]["mean"] > 0 and dsr >= -SR_MARGIN and abs(dd_c) <= DD_MARGIN * abs(dd_v))
        outcome = "decayed" if decayed else "confirmed" if confirmed else ("decayed" if second else "inconclusive")
        out[k] = {"outcome": outcome, **dec[k], "p_d_holm": padj[k], "delta_sr": dsr, "maxdd_comb": dd_c,
                  "maxdd_v11": dd_v, "inconclusive_counted_as_decayed": bool(second and not decayed and not confirmed)}
    return out


def evaluable(frozen: dict, active: dict, months: pd.PeriodIndex, n_markets: int) -> dict:
    """§7.6: at least 90% of the window's months computed with at least 6 active markets, and no interruption of
    more than 3 consecutive months (months not computed, or computed with every market missing)."""
    need = math.ceil(0.9 * len(months))
    good, run, worst = 0, 0, 0
    for m in months:
        rec = frozen.get(str(m))
        n_active = active.get(str(m), 0)
        computed = rec is not None and len(rec["missing"]) < n_markets
        good += int(computed and n_active >= 6)
        run = 0 if computed else run + 1
        worst = max(worst, run)
    return {"months_with_6_active": good, "needed": need, "longest_interruption": worst,
            "evaluable": good >= need and worst <= 3}


def evaluate(on: date, out: Path = OUT, base: Path | None = None) -> dict:
    """At an evaluation date of the go-live record only: the shadows, v1.1 and the combined books (t2022.combine
    on v1.1's monthly run on that date's inputs), then sections 7.6 and 5.3."""
    from . import systematic as SY
    from . import systematic_v11 as V11
    from . import t2022 as T
    g = json.loads((out / "GO_LIVE.json").read_text())
    if not g.get("confirmed"):
        raise SystemExit("go-live not confirmed")
    d1, d2 = date.fromisoformat(g["first_evaluation"]["date"]), date.fromisoformat(g["second_evaluation"]["date"])
    if on not in (d1, d2):
        raise SystemExit(f"{on} is not an evaluation date ({d1}, {d2})")
    second = on == d2
    m1 = pd.Period(g["M1"], "M")
    last = m1 + (FIRST_MONTHS + EXTENSION_MONTHS if second else FIRST_MONTHS) - 1
    trials = list(TRIALS)
    if second:
        prev = json.loads((out / "evaluation_1.json").read_text())
        trials = [k for k in TRIALS if prev["outcomes"][k]["outcome"] == "inconclusive"]
    inp = SY.build_inputs()
    v11 = V11.run(inp)[0]
    months = pd.period_range(m1, last, freq="M")
    ev, notev = {}, {}
    for k in trials:
        run = run_trial(k, g, on, base, out, end_month=last)
        sl = run["sl"]
        e = evaluable(run["frozen"], {str(m): len(active_markets(run, m)) for m in months}, months, len(run["codes"]))
        if not e["evaluable"]:
            notev[k] = {"outcome": "not evaluable", **e}
            continue
        comb = T.combine(inp, v11, sl, 1.0, 2.0)
        ev[k] = {"r": sl.monthly(2.0).reindex(months), "comb": comb["net"].reindex(months),
                 "v11": v11["net"].reindex(months), "sr_pred": g["sr_pred"][k], "evaluable": e}
    res = {"date": on.isoformat(), "second": second, "months": f"{m1}..{last}",
           "outcomes": {**outcomes(ev, second), **notev}}
    (out / f"evaluation_{2 if second else 1}.json").write_text(json.dumps(res, indent=1, default=float) + "\n")
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["golive", "daily", "status", "evaluate"])
    ap.add_argument("--today", default=None)
    ap.add_argument("--date", default=None)
    ap.add_argument("--amend", action="store_true", help="golive: apply the Amendment 2 rerun to a provisional record")
    a = ap.parse_args(argv)
    today = date.fromisoformat(a.today) if a.today else date.today()
    if a.cmd == "golive":
        r = golive_amend() if a.amend else golive(today)
        print(json.dumps(r, indent=1))
        return 0 if r["ok"] else 1
    if a.cmd == "daily":
        print(json.dumps(daily(today), default=str))
        return 0
    if a.cmd == "evaluate":
        print(json.dumps(evaluate(date.fromisoformat(a.date)), indent=1, default=float))
        return 0
    print(json.dumps({t: read_status(t, OUT) or None for t in TRIALS}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
