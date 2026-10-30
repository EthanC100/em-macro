"""Political-risk overlay and manual overrides on top of the frozen systematic strategy (v1).

    python -m em_macro.overlay fit      # choose the overlay rule on 2005-2019, freeze -> results/systematic/overlay/fit/
    python -m em_macro.overlay test     # 2020+ once, overlay vs v1 -> results/systematic/overlay/test/
    python -m em_macro.overlay update   # monthly: model (v1 + frozen overlay) + manual overrides from overrides.yaml

Overlay: before each high-importance scheduled political event in a country, scale that country's
positions from 5 business days before the event to 1 business day after it.  Candidate rules:
(a) cut to zero, (b) halve, (c) no change.  The rule with the best 2005-2019 Sharpe after costs is frozen.

It acts on the instruments that have daily prices (all 10 currencies and the BR/MX/ZA/TR 10y bonds);
other bond positions (European spreads, Bund, CO/CL/ID bonds) only have monthly-average yields, so the
overlay cannot be measured for them and leaves them unchanged.  The frozen v1 strategy is not modified:
the overlay is a separate P&L adjustment on top of v1's positions.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import yaml

from . import panel_sources as PS
from . import sources as S
from . import systematic as SY
from .config import EVENTS, PROC, ROOT

OUT = SY.OUT / "overlay"
FIT_DIR, TEST_DIR = OUT / "fit", OUT / "test"
CODE_FILE = ROOT / "em_macro" / "overlay.py"
OVERRIDES_FILE = ROOT / "overrides.yaml"
UPCOMING_FILE = EVENTS / "upcoming_events.csv"

RULES = {"a_cut_to_zero": 0.0, "b_halve": 0.5, "c_no_change": 1.0}
WINDOW_BEFORE, WINDOW_AFTER = 5, 1                      # business days
# --- event selection, fixed before any result was seen ---
ELECTION_SUBTYPES = {"general", "presidential", "presidential_r2", "legislative", "legislative_r2", "referendum"}
BUDGET_SUBTYPES = {"budget_final_approval", "pge_final_approval", "budget_approved", "plf_rejected_first_reading",
                   "budget", "autumn_statement", "spring_statement", "pre_budget_report"}
RATING_SCHEDULED_ISO3 = {"FRA", "ITA", "ESP", "GBR", "DEU", "POL"}     # EU calendar rule (CRA3) from 2014
RATING_SCHEDULED_FROM = "2014-01-01"
COUNTRY_INSTR = {"BRA": ["BRL", "BR10Y"], "MEX": ["MXN", "MX10Y"], "ZAF": ["ZAR", "ZA10Y"], "TUR": ["TRY", "TR10Y"],
                 "IDN": ["IDR", "ID10Y"], "POL": ["PLN", "PL-DE"], "FRA": ["EUR", "FR-DE"], "ITA": ["EUR", "IT-DE"],
                 "ESP": ["EUR", "ES-DE"], "DEU": ["EUR", "DE10Y"], "GBR": ["GBP", "GB-DE"], "COL": ["COP", "CO10Y"],
                 "CHL": ["CLP", "CL10Y"]}
DAILY_BONDS = {"BR10Y": "BR", "MX10Y": "MX", "ZA10Y": "ZA", "TR10Y": "TR"}
NAMES = {"brazil": "BRA", "mexico": "MEX", "south africa": "ZAF", "turkey": "TUR", "indonesia": "IDN",
         "poland": "POL", "france": "FRA", "italy": "ITA", "spain": "ESP", "united kingdom": "GBR", "uk": "GBR",
         "colombia": "COL", "chile": "CHL", "germany": "DEU", "euro area": "DEU"}


def _hash() -> str:
    return hashlib.sha256(CODE_FILE.read_bytes()).hexdigest()[:16]


# ============================================================== events
def political_events(include_upcoming: bool = True) -> pd.DataFrame:
    cal = pd.read_csv(EVENTS / "calendar_13.csv", parse_dates=["date"])
    if include_upcoming and UPCOMING_FILE.exists():
        up = pd.read_csv(UPCOMING_FILE, parse_dates=["date"])
        cal = pd.concat([cal, up], ignore_index=True)
    el = (cal.event_type == "election") & cal.subtype.isin(ELECTION_SUBTYPES)
    bu = (cal.event_type == "budget") & cal.subtype.isin(BUDGET_SUBTYPES)
    ra = ((cal.event_type == "rating_action") & cal.iso3.isin(RATING_SCHEDULED_ISO3)
          & (cal.date >= RATING_SCHEDULED_FROM))
    ev = cal[el | bu | ra].copy()
    ev["category"] = np.select([el[ev.index], bu[ev.index]], ["election", "budget vote"], "rating review")
    return ev.drop_duplicates(["iso3", "date", "category"]).sort_values("date")


def windows(ev: pd.DataFrame) -> pd.DataFrame:
    """One row per (instrument, window); overlapping windows on an instrument are merged."""
    bd = pd.bdate_range("2004-12-01", "2027-12-31")
    rows = []
    for e in ev.itertuples():
        i = bd.searchsorted(e.date, "left")
        j = bd.searchsorted(e.date, "right")
        start, end = bd[max(i - WINDOW_BEFORE, 0)], bd[j + WINDOW_AFTER - 1]
        for k in COUNTRY_INSTR.get(e.iso3, []):
            rows.append({"instrument": k, "start": start, "end": end, "iso3": e.iso3,
                         "event": f"{e.iso3} {e.category} {e.date:%Y-%m-%d}"})
    w = pd.DataFrame(rows).sort_values(["instrument", "start"])
    merged = []
    for k, g in w.groupby("instrument"):
        cur = None
        for r in g.itertuples():
            if cur and r.start <= cur["end"]:
                cur["end"] = max(cur["end"], r.end)
                cur["events"] += "; " + r.event
            else:
                if cur:
                    merged.append(cur)
                cur = {"instrument": k, "start": r.start, "end": r.end, "events": r.event}
        merged.append(cur)
    return pd.DataFrame(merged)


# ========================================================= daily returns
def daily_returns(months: pd.PeriodIndex) -> pd.DataFrame:
    daily = pd.read_csv(PROC / "daily_panel.csv", index_col=0, parse_dates=True)
    days = pd.bdate_range(months[0].start_time, months[-1].end_time.normalize())
    gap = pd.Series(days, index=days).diff().dt.days.fillna(1).values
    spot = {k: daily[f"FX_{c}"] for k, c in SY.FX_INSTR.items() if c in ("BR", "MX", "ZA", "TR", "ID", "PL")}
    spot["GBP"], spot["EUR"] = 1 / S.fred("DEXUSUK"), 1 / S.fred("DEXUSEU")
    spot["COP"], spot["CLP"] = PS.colombia_trm(), PS.chile_dolar_observado()
    us = S.fred("DFF").reindex(days, method="ffill")
    out = {}
    for k, s in spot.items():
        s = s[~s.index.duplicated()].reindex(days).ffill(limit=5)
        i = S.bis_policy(SY.FX_INSTR[k]).reindex(days, method="ffill")
        out[k] = s.shift(1) / s - 1 + (i.shift(1) - us.shift(1)) / 100 * gap / 365
    for k, c in DAILY_BONDS.items():
        y = daily[f"Y10_{c}"].reindex(days).ffill(limit=5)
        f = S.bis_policy(c).reindex(days, method="ffill")
        D, _ = SY._duration(pd.DataFrame({k: y.shift(1) / 100}))
        out[k] = (y.shift(1) - f.shift(1)) / 100 * gap / 365 - D[k] * y.diff() / 100
    return pd.DataFrame(out)


def held_daily(W: pd.DataFrame, days: pd.DatetimeIndex) -> pd.DataFrame:
    """v1 position held on each day: FX weights decided at the end of the previous
    month; bond weights two months back (v1's bond execution lag)."""
    m = days.to_period("M")
    out = {}
    for k in W.columns:
        lag = 1 if k in SY.FX_INSTR else 1 + SY.DESIGN["bond_execution_lag_months"]
        out[k] = W[k].shift(lag).reindex(m).values
    return pd.DataFrame(out, index=days).fillna(0.0)


def scaled_pnl(scale: pd.DataFrame, held: pd.DataFrame, rd: pd.DataFrame, cost: dict) -> tuple[pd.Series, pd.Series]:
    """P&L change (by month) from multiplying the held position by `scale`
    (1 = unchanged) on given days, including the cost of trading out and back."""
    cols = [c for c in scale.columns if c in rd.columns]
    d = (scale[cols] - 1.0) * held[cols]
    pnl = (d * rd[cols]).sum(axis=1)
    tc = (d.diff().abs().fillna(d.abs()) * pd.Series(cost)[cols]).sum(axis=1)
    m = pnl.index.to_period("M")
    return pnl.groupby(m).sum(), tc.groupby(m).sum()


def overlay_scale(win: pd.DataFrame, days, instruments, k: float) -> pd.DataFrame:
    sc = pd.DataFrame(1.0, index=days, columns=instruments)
    for r in win.itertuples():
        if r.instrument in sc:
            sc.loc[(days >= r.start) & (days <= r.end), r.instrument] = k
    return sc


def _base():
    inp = SY.build_inputs()
    res = SY.run(inp, SY.VARIANTS["combined"])
    W = res.attrs["weights"]
    rd = daily_returns(inp["months"])
    held = held_daily(W, rd.index)
    return inp, res, W, rd, held


def overlay_series(inp, res, rd, held, k: float, include_upcoming=False) -> pd.DataFrame:
    win = windows(political_events(include_upcoming))
    sc = overlay_scale(win, rd.index, list(rd.columns), k)
    pnl, tc = scaled_pnl(sc, held, rd, inp["cost"])
    out = pd.DataFrame({"v1_net": res["net"]})
    out["overlay_adj"] = (pnl - tc).reindex(out.index).fillna(0.0)
    out["overlay_net"] = out["v1_net"] + out["overlay_adj"]
    out.attrs["windows"] = win
    return out


# ============================================================= stages
def stage_fit():
    FIT_DIR.mkdir(parents=True, exist_ok=True)
    inp, res, W, rd, held = _base()
    P = slice(None, SY.FIT_END)
    rows = []
    for name, k in RULES.items():
        o = overlay_series(inp, res, rd, held, k)
        rows.append({"rule": name, "scale_in_window": k, **SY.stats(o["overlay_net"].loc[P], inp["spx"]),
                     "overlay_pnl_%_pa": 1200 * o["overlay_adj"].loc[P].mean()})
    tab = pd.DataFrame(rows)
    best = tab.loc[tab["sharpe"].idxmax(), "rule"]
    win = o.attrs["windows"]
    win[win["end"] <= "2019-12-31"].to_csv(FIT_DIR / "event_windows_2005_2019.csv", index=False)
    tab.to_csv(FIT_DIR / "rules_2005_2019.csv", index=False, float_format="%.4f")
    frozen = {"created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "code_sha256_16": _hash(),
              "chosen_rule": best, "scale_in_window": RULES[best], "window_business_days": [WINDOW_BEFORE, WINDOW_AFTER],
              "election_subtypes": sorted(ELECTION_SUBTYPES), "budget_subtypes": sorted(BUDGET_SUBTYPES),
              "rating_reviews": f"rating actions of {sorted(RATING_SCHEDULED_ISO3)} from {RATING_SCHEDULED_FROM}",
              "instruments_covered": list(rd.columns), "v1_frozen_design": "results/systematic/fit/frozen_design.json"}
    (FIT_DIR / "frozen_overlay.json").write_text(json.dumps(frozen, indent=1))
    print(tab.round(3).to_string())
    print("chosen:", best)


def load_frozen(strict=False) -> dict:
    fr = json.loads((FIT_DIR / "frozen_overlay.json").read_text())
    if strict and fr["code_sha256_16"] != _hash():
        sys.exit("overlay.py changed after freezing; restore it before testing.")
    return fr


def stage_test(force=False):
    TEST_DIR.mkdir(parents=True, exist_ok=True)
    guard = TEST_DIR / "TEST_RUN.json"
    if guard.exists() and not force:
        sys.exit(f"hold-out already evaluated ({guard}).")
    fr = load_frozen(strict=True)
    inp, res, W, rd, held = _base()
    P = slice(SY.TEST_START, inp["months"][-1])
    rows = []
    o = overlay_series(inp, res, rd, held, fr["scale_in_window"])
    rows.append({"strategy": "v1 (frozen, no overlay)", **SY.stats(o["v1_net"].loc[P], inp["spx"])})
    rows.append({"strategy": f"v1 + overlay ({fr['chosen_rule']}, frozen)", **SY.stats(o["overlay_net"].loc[P], inp["spx"]),
                 "overlay_pnl_%_pa": 1200 * o["overlay_adj"].loc[P].mean()})
    for name, k in RULES.items():          # for information only: the choice was made on 2005-2019
        if k != fr["scale_in_window"]:
            oo = overlay_series(inp, res, rd, held, k)
            rows.append({"strategy": f"(info) v1 + {name}", **SY.stats(oo["overlay_net"].loc[P], inp["spx"]),
                         "overlay_pnl_%_pa": 1200 * oo["overlay_adj"].loc[P].mean()})
    tab = pd.DataFrame(rows)
    tab.to_csv(TEST_DIR / "overlay_vs_v1_2020_on.csv", index=False, float_format="%.4f")
    win = o.attrs["windows"]
    win[(win["start"] >= "2020-01-01")].to_csv(TEST_DIR / "event_windows_2020_on.csv", index=False)
    guard.write_text(json.dumps({"run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                 "frozen_created_utc": fr["created_utc"]}, indent=1))
    print(tab.round(3).to_string())


# ========================================================== overrides
ACTIONS = "zero | halve | scale <factor> (e.g. 'scale 0.25', 'scale 1.5', 'scale -1' to reverse)"


def _factor(action: str) -> float:
    a = str(action).strip().lower()
    if a in ("zero", "flat", "close"):
        return 0.0
    if a == "halve":
        return 0.5
    if a.startswith("scale"):
        return float(a.split()[1])
    raise ValueError(f"unknown action '{action}' (allowed: {ACTIONS})")


def load_overrides() -> tuple[pd.DataFrame, list[dict]]:
    """Validated overrides and a list of rejected entries (with the reason)."""
    if not OVERRIDES_FILE.exists():
        return pd.DataFrame(), []
    doc = yaml.safe_load(OVERRIDES_FILE.read_text()) or {}
    ok, bad = [], []
    for n, o in enumerate(doc.get("overrides") or [], start=1):
        o = dict(o or {})
        try:
            ctry = str(o.get("country", "")).strip()
            iso = ctry.upper() if ctry.upper() in COUNTRY_INSTR else NAMES.get(ctry.lower())
            if iso is None:
                raise ValueError(f"unknown country '{ctry}'")
            inst = str(o.get("instrument", "all")).strip()
            allowed = COUNTRY_INSTR[iso]
            insts = allowed if inst.lower() == "all" else [inst.upper()]
            if any(i not in allowed for i in insts):
                raise ValueError(f"instrument '{inst}' is not one of {allowed} (or 'all')")
            f = _factor(o.get("action"))
            start, end = pd.Timestamp(str(o["start"])), pd.Timestamp(str(o["end"]))
            if end < start:
                raise ValueError("end before start")
            if not str(o.get("reason", "")).strip():
                raise ValueError("a reason is required")
            for i in insts:
                ok.append({"override_id": n, "country": iso, "instrument": i, "action": o.get("action"), "factor": f,
                           "start": start, "end": end, "reason": str(o["reason"]).strip()})
        except Exception as e:                       # noqa: BLE001 - every problem is logged, nothing is skipped silently
            bad.append({"override_id": n, **{k: o.get(k) for k in ("country", "instrument", "action", "start", "end",
                                                                    "reason")}, "status": f"rejected: {e}"})
    return pd.DataFrame(ok), bad


def stage_update():
    """Monthly run: model = v1 + frozen overlay; final = model x manual overrides.
    Writes paper_pnl.csv (extended), position_adjustments.csv, overrides_log.csv."""
    fr = load_frozen()
    inp, res, W, rd, held = _base()
    k = fr["scale_in_window"]
    o = overlay_series(inp, res, rd, held, k, include_upcoming=True)
    win = o.attrs["windows"]
    sc_overlay = overlay_scale(win, rd.index, list(rd.columns), k)
    model_held = held.copy()
    model_held[rd.columns] = held[rd.columns] * sc_overlay

    ovr, bad = load_overrides()
    months = inp["months"]
    log, ovr_month = [], pd.Series(0.0, index=months)
    bond_r = inp["bond"]["ret"]
    for r in ovr.itertuples():
        if r.instrument in rd.columns:              # daily P&L
            sc = pd.DataFrame(1.0, index=rd.index, columns=[r.instrument])
            sc.loc[(rd.index >= r.start) & (rd.index <= r.end), r.instrument] = r.factor
            pnl, tc = scaled_pnl(sc, model_held, rd, inp["cost"])
            note = "daily prices"
        else:                                         # monthly-only bond: pro rata by business days covered
            bd = pd.bdate_range(r.start, r.end)
            frac = pd.Series(bd.to_period("M")).value_counts() / pd.Series(
                [len(pd.bdate_range(m.start_time, m.end_time)) for m in bond_r.index], index=bond_r.index)
            frac = frac.reindex(bond_r.index).fillna(0.0)
            w = W[r.instrument].shift(1 + SY.DESIGN["bond_execution_lag_months"])
            pnl = ((r.factor - 1) * w * bond_r[r.instrument] * frac).fillna(0.0)
            entry = pd.Series(0.0, index=bond_r.index)
            for d in (r.start, r.end):
                m = d.to_period("M")
                if m in entry.index:
                    entry[m] += abs(r.factor - 1) * abs(w.get(m, 0.0) or 0.0) * inp["cost"][r.instrument]
            tc = entry
            note = "monthly-average yields: pro rata by business days (approximation)"
        net = (pnl - tc).reindex(months).fillna(0.0)
        ovr_month = ovr_month.add(net, fill_value=0.0)
        for m in pd.period_range(r.start.to_period("M"), r.end.to_period("M"), freq="M"):
            log.append({"override_id": r.override_id, "country": r.country, "instrument": r.instrument,
                        "action": r.action, "start": r.start.date(), "end": r.end.date(), "reason": r.reason,
                        "month": str(m), "pnl_vs_model": net.get(m, np.nan), "pricing": note,
                        "status": "applied" if m in net.index else "pending (month not yet complete)"})
    for b in bad:
        log.append({**b, "month": "", "pnl_vs_model": np.nan, "pricing": ""})
    logdf = pd.DataFrame(log, columns=["override_id", "country", "instrument", "action", "start", "end", "reason",
                                       "month", "pnl_vs_model", "pricing", "status"])
    logdf.to_csv(SY.OUT / "overrides_log.csv", index=False, float_format="%.6f")

    pnl = pd.read_csv(SY.OUT / "paper_pnl.csv")
    pnl["month"] = pd.PeriodIndex(pnl["month"], freq="M")
    pnl = pnl.set_index("month")
    pnl["overlay_rule"] = fr["chosen_rule"]
    pnl["overlay_adj"] = o["overlay_adj"].reindex(pnl.index).fillna(0.0)
    pnl["model_net"] = pnl["net"] + pnl["overlay_adj"]
    pnl["override_pnl"] = ovr_month.reindex(pnl.index).fillna(0.0)
    pnl["final_net"] = pnl["model_net"] + pnl["override_pnl"]
    pnl["cumulative_model"] = (1 + pnl["model_net"]).cumprod()
    pnl["cumulative_final"] = (1 + pnl["final_net"]).cumprod()
    pnl.reset_index().assign(month=lambda d: d["month"].astype(str)).to_csv(SY.OUT / "paper_pnl.csv", index=False,
                                                                            float_format="%.6f")
    # adjustments for the month the current positions are held
    nxt = months[-1] + 1
    adj = []
    for r in win.itertuples():
        if k != 1.0 and r.end.to_period("M") >= nxt and r.start.to_period("M") <= nxt:
            adj.append({"instrument": r.instrument, "start": r.start.date(), "end": r.end.date(),
                        "scale": k, "source": f"overlay rule {fr['chosen_rule']}", "reason": r.events})
    for r in ovr.itertuples():
        if r.end.to_period("M") >= nxt:
            adj.append({"instrument": r.instrument, "start": r.start.date(), "end": r.end.date(), "scale": r.factor,
                        "source": f"manual override #{r.override_id}", "reason": r.reason})
    pd.DataFrame(adj, columns=["instrument", "start", "end", "scale", "source", "reason"]).to_csv(
        SY.OUT / "position_adjustments.csv", index=False)
    live = pnl[pnl["sample"].str.startswith("live")]
    print(f"overlay rule {fr['chosen_rule']}; {len(ovr)} override rows, {len(bad)} rejected; "
          f"live months {len(live)}, override P&L to date {live['override_pnl'].sum():.4%}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "fit":
        stage_fit()
    elif cmd == "test":
        stage_test("--force" in sys.argv)
    elif cmd == "update":
        stage_update()
    else:
        sys.exit(__doc__)
