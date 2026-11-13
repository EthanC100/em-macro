"""Reproduce carry and time-series momentum with the Manhattan engine, on exploration dates only.

    python -m manhattan.factors.reproduce          # results/manhattan_engine/REPRODUCTION.md and reproduction.json

Milestone E, criterion E-08: before anything new is evaluated, the engine must give the numbers the repository
already has for two known factors, from data already in the repository, dated on or before 2019-12-31.

What is compared, on the public daily panel (six emerging-market currencies, 2005 to 2019):

1. **Carry.** The engine holds each currency's deposit, financed in dollars, rebalanced monthly, and the
   equal-weight basket. Against (a) the frozen code ``em_macro.carry.carry_returns`` run here on the same rows
   and (b) the committed file ``data/processed/carry_monthly_returns.csv``, read up to 2019-12 only. The frozen
   benchmark charges a flat 0.10% a month; the engine run has no cost, so the benchmark's cost is added back.
2. **Time-series momentum.** The trend signal of trial T01 (``em_macro.tstrend``: the mean over 1, 3, 6 and 12
   months of the clipped, volatility-scaled return, sized by inverse volatility). The engine computes it at
   each month end from its point-in-time view, by code written here; the frozen function is run on the same
   monthly returns. Compared: the weights, month by month, and the sleeve's monthly gross return.

Neither is a new hypothesis and neither result is evidence for anything: both are exploration-role evaluations
of factors the repository already holds, recorded in a ledger and a variant log that this module writes next
to its report. The frozen modules are imported, never edited, and are handed rows up to the cut-off only.

**What this is not.** The published results for time-series momentum (Moskowitz, Ooi and Pedersen 2012) and for
carry across asset classes (Koijen, Moskowitz, Pedersen and Vrugt 2018) are for dozens of futures markets from
the 1980s. Six currencies from 2005 cannot be compared with them. That comparison needs the futures history,
which is licensed and is not in this repository.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np

from manhattan import config as mconfig
from manhattan import ledger as L
from manhattan import roles, spec
from manhattan.engine import accounting, backtest, evaluate, pit

from . import public_fx as fx

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/manhattan_engine"
START = date(2005, 1, 3)
TSMOM_K = (1, 3, 6, 12)
EWMA_COM_MONTHS = 60 / 21
EWMA_MIN_MONTHS = 12
SLEEVE_TARGET_VOL = 0.10
BENCHMARK_COST = 0.001
# what "reproduced" means, fixed before the first run of this module
TOL = {"carry_corr_min": 0.999, "carry_mean_abs_max": 0.0010, "trend_weight_abs_max": 1e-9,
       "trend_return_corr_min": 0.999, "trend_return_mean_abs_max": 0.0005}


# ------------------------------------------------------------------ the engine's side

def window(store: pit.PitStore, end: date = fx.CUTOFF) -> pit.Window:
    fence = roles.Fence.from_config(mconfig.load())
    return pit.Reader(store, caller="session", domain=fx.DOMAIN, fence=fence).window(START, end)


def hold_one(c: str) -> backtest.Strategy:
    return backtest.Strategy(fx.instruments((c,)), lambda v: {c: 1.0}, rebalance="M", lag=0)


def equal_weight(view: backtest.View) -> dict:
    """1/n in every currency whose deposit has a price by now."""
    live = [c for c in view.instruments if view.get(f"dep_{c}", 1)[1].size]
    return {c: 1.0 / len(live) for c in live}


def month_returns(view: backtest.View, name: str) -> tuple[np.ndarray, np.ndarray]:
    """(months, excess returns) of one deposit over the complete months known at the view: the deposit's
    growth less dollar interest for the days held, compounded within the month, as the accounting books it."""
    d, v = view.get(f"dep_{name}")
    if d.size < 2:
        return np.array([], dtype="datetime64[M]"), np.array([])
    rd, rv = view.get("us_ff")
    rate = rv[np.searchsorted(rd, d[:-1], "right") - 1]
    daily = v[1:] / v[:-1] - 1.0 - rate * np.diff(d).astype(float) / 365.0
    m = d[1:].astype("datetime64[M]")
    months = np.unique(m)
    out = np.array([np.prod(1.0 + daily[m == x]) - 1.0 for x in months])
    first = d[0].astype("datetime64[M]")
    keep = months > first                                         # the first month is not complete
    return months[keep], out[keep]


def ewma_vol(r: np.ndarray, com: float = EWMA_COM_MONTHS, min_periods: int = EWMA_MIN_MONTHS) -> float:
    """Annualised exponentially weighted standard deviation of monthly returns, about their weighted mean, with
    the small-sample correction (what ``pandas.Series.ewm(com=...).std()`` gives for its last row)."""
    if r.size < min_periods:
        return float("nan")
    w = (com / (1.0 + com)) ** np.arange(r.size - 1, -1, -1)
    mean = (w @ r) / w.sum()
    biased = (w @ (r - mean) ** 2) / w.sum()
    return float(np.sqrt(biased * w.sum() ** 2 / (w.sum() ** 2 - (w @ w)) * 12.0))


def trend_weights(view: backtest.View) -> dict:
    """T01's trend sleeve: ``TREND = mean_k clip(Σ_k r / (σ √(k/12)), −2, 2) / 2`` for k = 1, 3, 6, 12 months,
    ``w = TREND · 0.10 / σ / n_active``; zero for an instrument without 12 complete months."""
    raw = {}
    for name in view.instruments:
        _, r = month_returns(view, name)
        sigma = ewma_vol(r)
        if not (sigma > 0) or r.size < max(TSMOM_K):
            continue
        trend = np.mean([np.clip(r[-k:].sum() / (sigma * np.sqrt(k / 12.0)), -2.0, 2.0) / 2.0 for k in TSMOM_K])
        raw[name] = trend * SLEEVE_TARGET_VOL / sigma
    return {name: raw.get(name, 0.0) / max(len(raw), 1) for name in view.instruments}


# ------------------------------------------------------------------ the repository's side

def frozen_carry(end: date = fx.CUTOFF):
    """``em_macro.carry.carry_returns`` (frozen, imported) on the panel's rows up to the cut-off."""
    import pandas as pd

    from em_macro import carry
    days, data = fx.read_panel(end=end)
    panel = pd.DataFrame(data, index=pd.DatetimeIndex(days.astype("datetime64[ns]")))
    return carry.carry_returns(panel)


def committed_carry(end_month: str = "2019-12", path: Path = ROOT / "data/processed/carry_monthly_returns.csv") -> dict:
    """The committed benchmark file, read from the top and no further than ``end_month``."""
    out: dict = {}
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["date"] > end_month:
                break
            for k, v in row.items():
                if k != "date":
                    out.setdefault(k, {})[row["date"]] = float(v) if v != "" else np.nan
    return out


def frozen_trend(months: np.ndarray, returns: dict):
    """``em_macro.tstrend.trend_raw_weights`` (frozen, imported) on the engine's own monthly returns."""
    import pandas as pd

    from em_macro import tstrend
    idx = pd.PeriodIndex([str(m) for m in months], freq="M")
    r = pd.DataFrame({c: pd.Series(v, index=idx) for c, v in returns.items()})
    return tstrend.trend_raw_weights(r), r


def compare(a: np.ndarray, b: np.ndarray, months=None) -> dict:
    ok = np.isfinite(a) & np.isfinite(b)
    worst = str(np.asarray(months)[ok][np.argmax(np.abs(a[ok] - b[ok]))]) if months is not None else ""
    a, b = a[ok], b[ok]
    return {"months": int(a.size), "corr": float(np.corrcoef(a, b)[0, 1]), "mean_abs_diff": float(np.abs(a - b).mean()),
            "max_abs_diff": float(np.abs(a - b).max()), "worst_month": worst, "mean_annual_engine": float(a.mean() * 12),
            "mean_annual_reference": float(b.mean() * 12),
            "sharpe_engine": accounting.sharpe(a, 12), "sharpe_reference": accounting.sharpe(b, 12)}


# ------------------------------------------------------------------ specs and records

def specs(name: str, mechanism: str, signal: str, universe: str):
    fam = spec.family(mechanism=mechanism, mechanism_class="risk_premium", sign="+",
                      counterparty="holders of low-yielding currencies; hedgers", kill_condition="reproduction only: not a hypothesis",
                      tail_exposure="currency crashes", tags=["reproduction", name])
    hyp = spec.hypothesis(fam, domain=fx.DOMAIN, signal=signal, grid={"definition": [name]},
                          data_sources=[{"name": "daily_panel fx, policy rates, federal funds", "publication_lag_days": fx.LAG_DAYS}],
                          primary_binding={"universe_id": universe, "cost_model_id": "none", "sizing_id": "as_defined"})
    var = spec.variants(hyp)[0]
    return fam, hyp, var, spec.primary_executable(hyp, var, code_version="manhattan.factors.reproduce")


def run(out: Path = OUT, end: date = fx.CUTOFF, record: bool = True) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    store = fx.store(end=end)
    w = window(store, end)
    led = L.Ledger(out / "exploration_ledger.jsonl", writer="session", protocol=evaluate_protocol()) if record else None
    version = evaluate.code_version()

    def go(strategy, key, mechanism, signal, universe, description):
        if not record:
            return backtest.run(w, strategy), None
        fam, hyp, var, exe = specs(key, mechanism, signal, universe)
        return evaluate.evaluate(w, strategy, ledger=led, executable=exe, variant=var, hypothesis=hyp, family=fam,
                                 description=description, log_path=out / "exploration_log.csv", version=version)

    res: dict = {"window": {"start": str(w.start), "end": str(w.end), "role": w.role}, "data_hash": store.data_hash(),
                 "tolerances": TOL, "carry": {}, "records": []}
    # ---- 1. carry
    ref = frozen_carry(end)
    file = committed_carry(f"{end.year:04d}-{end.month:02d}")
    engine_monthly = {}
    for c in fx.CURRENCIES + ("EW",):
        strategy = hold_one(c) if c != "EW" else backtest.Strategy(fx.instruments(), equal_weight, rebalance="M", lag=0)
        r, rec = go(strategy, f"fx_carry_{c}", "a high-yielding currency pays more than it loses against the dollar",
                    "hold the local deposit against dollar cash" if c != "EW" else "equal weight in every currency with a deposit",
                    c if c != "EW" else "six_em_currencies", f"carry benchmark reproduction, {c}, monthly rebalance")
        months, x = fx.monthly(r.dates, r.net)
        engine_monthly[c] = dict(zip([str(m) for m in months], x))
        keys = [m for m in engine_monthly[c] if m in ref.index.astype(str)]
        a = np.array([engine_monthly[c][m] for m in keys])
        b = np.array([ref[c].get(m, np.nan) for m in keys]) + BENCHMARK_COST
        f_ = np.array([file.get(c, {}).get(m, np.nan) for m in keys]) + BENCHMARK_COST
        res["carry"][c] = {"vs_frozen_code": compare(a, b, keys), "vs_committed_file": compare(a, f_, keys),
                           "frozen_code_vs_file_max_abs": float(np.nanmax(np.abs(b - f_)))}
        if rec:
            res["records"].append({"what": f"carry {c}", "seq": rec["seq"], "type": rec["type"], "hash": rec["hash"]})
    # ---- 2. time-series momentum
    trend = backtest.Strategy(fx.instruments(), trend_weights, rebalance="M", lag=0)
    store0 = fx.store(end=end, lag_days=0)            # the frozen signal uses the month's own last fixing: same information
    w0 = window(store0, end)
    r = backtest.run(w0, trend)
    if record:
        fam, hyp, var, exe = specs("fx_tsmom_t01", "price trends persist for months", "T01 trend signal, inverse volatility",
                                   "six_em_currencies")
        _, rec = evaluate.evaluate(w0, trend, ledger=led, executable=exe, variant=var, hypothesis=hyp, family=fam,
                                   description="T01 trend sleeve reproduction on six EM currencies, monthly",
                                   log_path=out / "exploration_log.csv", version=version)
        res["records"].append({"what": "trend sleeve", "seq": rec["seq"], "type": rec["type"], "hash": rec["hash"]})
    last_view = backtest.View(w0, r.dates, r.dates.size - 1, r.instruments)
    by_ccy = {c: month_returns(last_view, c) for c in fx.CURRENCIES}
    months = np.unique(np.concatenate([m for m, _ in by_ccy.values()]))
    table = {c: np.array([dict(zip(m, v)).get(x, np.nan) for x in months]) for c, (m, v) in by_ccy.items()}
    wf, rf = frozen_trend(months, table)
    decided = {str(r.dates[j].astype("datetime64[M]")): r.decisions[j] for j in r.decisions}
    diffs, n_w = [], 0
    for m in wf.index.astype(str):
        if m in decided:
            diffs.append(np.abs(decided[m] - wf.loc[m, list(r.instruments)].to_numpy()).max())
            n_w += 1
    ref_ret = (wf.shift(1) * rf).sum(axis=1, min_count=1)          # weights of month t earn month t + 1
    em, ex = fx.monthly(r.dates, r.net)
    eng = dict(zip([str(m) for m in em], ex))
    keys = [m for m in ref_ret.index.astype(str) if m in eng and np.isfinite(ref_ret[m])]
    res["trend"] = {"weights": {"months_compared": n_w, "max_abs_diff": float(max(diffs)),
                                "months_with_a_position": int(sum(np.abs(v).sum() > 0 for v in decided.values()))},
                    "returns": compare(np.array([eng[m] for m in keys]), np.array([ref_ret[m] for m in keys]), keys)}
    c_ok = all(v[k]["corr"] >= TOL["carry_corr_min"] and v[k]["mean_abs_diff"] <= TOL["carry_mean_abs_max"]
               for v in res["carry"].values() for k in ("vs_frozen_code", "vs_committed_file"))
    t = res["trend"]
    t_ok = (t["weights"]["max_abs_diff"] <= TOL["trend_weight_abs_max"] and t["returns"]["corr"] >= TOL["trend_return_corr_min"]
            and t["returns"]["mean_abs_diff"] <= TOL["trend_return_mean_abs_max"])
    res["reproduced"] = {"carry": bool(c_ok), "trend": bool(t_ok)}
    return res


def evaluate_protocol() -> str:
    """The protocol hash a ledger record names: the adopted version's (PROTOCOL_v3.md, 3.0.0)."""
    import hashlib
    return hashlib.sha256((ROOT / "docs/manhattan/PROTOCOL_v3.md").read_bytes()).hexdigest()


def report(res: dict) -> str:
    f4 = lambda x: f"{x:.4f}"
    L_ = ["# Manhattan engine: reproduction of carry and time-series momentum (exploration dates only)", "",
          "Written by `python -m manhattan.factors.reproduce`. **Public data only** (the repository's daily panel: six "
          f"emerging-market currencies). Window {res['window']['start']} to {res['window']['end']}, role "
          f"`{res['window']['role']}`: the read was allowed by `manhattan.roles.check_read`, and no row dated after the "
          "window was read from any file. Nothing here is evidence: these are two factors the repository already holds, "
          "run through the new engine to see that it gives the numbers the old code gives.", "",
          f"Data hash `{res['data_hash']}`.", "",
          "## 1. Carry: each currency's deposit against dollar cash, and the equal-weight basket", "",
          "Monthly returns of the engine (daily accounting, monthly rebalancing, no cost) against the frozen benchmark "
          "`em_macro.carry` with its flat 0.10% monthly cost added back: (a) the frozen code run on the same rows, (b) the "
          "committed file `data/processed/carry_monthly_returns.csv` up to 2019-12.", "",
          "| series | months | correlation with (a) | mean abs. difference | largest abs. difference (month) | mean a year: engine | (a) | Sharpe: engine | (a) | largest difference between (a) and (b) |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for c, v in res["carry"].items():
        a = v["vs_frozen_code"]
        L_.append(f"| {c} | {a['months']} | {a['corr']:.6f} | {a['mean_abs_diff']:.5f} | {a['max_abs_diff']:.5f} ({a['worst_month']}) | "
                  f"{f4(a['mean_annual_engine'])} | {f4(a['mean_annual_reference'])} | {a['sharpe_engine']:.3f} | "
                  f"{a['sharpe_reference']:.3f} | {v['frozen_code_vs_file_max_abs']:.1e} |")
    L_ += ["", "The committed file is the frozen code's output to its six decimals; where the last column is above "
               "5e-7 the daily panel has been refreshed since the file was written (a few parts in a million).", "",
           "The differences between the engine and the benchmark are conventions, not errors: the benchmark accrues one month of simple interest at the "
               "month-start rate over the month's calendar days; the engine accrues day by day at the rate in force, over "
               "the days actually between fixings, and compounds. The last fixing of the window (31 December 2019) is "
               "published on 1 January 2020, after the window ends, so the engine's last month stops one day earlier.", "",
           "## 2. Time-series momentum: the trend sleeve of trial T01 on the six currencies", "",
           "The engine computes the signal at each month end from its point-in-time view (code in "
           "`manhattan/factors/reproduce.py`); the frozen `em_macro.tstrend.trend_raw_weights` is run on the same monthly "
           "returns. For this comparison the data are stamped available on the day they describe, because the frozen "
           "signal uses the month's own last fixing.", ""]
    t = res["trend"]
    L_ += ["| what | value |", "|---|---|",
           f"| months with a decision compared | {t['weights']['months_compared']} ({t['weights']['months_with_a_position']} with a position) |",
           f"| largest absolute difference between a weight of the engine and of the frozen code | {t['weights']['max_abs_diff']:.2e} |",
           f"| monthly sleeve return, engine against frozen weights times next month's returns: months | {t['returns']['months']} |",
           f"| correlation | {t['returns']['corr']:.6f} |",
           f"| mean absolute difference | {t['returns']['mean_abs_diff']:.6f} |",
           f"| largest absolute difference | {t['returns']['max_abs_diff']:.6f} ({t['returns']['worst_month']}) |",
           f"| Sharpe ratio (gross, 2005 to 2019): engine / frozen | {t['returns']['sharpe_engine']:.3f} / {t['returns']['sharpe_reference']:.3f} |",
           "", "The return differences come from the engine holding positions that drift within the month and compounding "
               "daily, where the reference multiplies month-start weights by monthly returns.", "",
           "## 3. Verdict against the tolerances fixed in the code before the first run", "",
           "| check | tolerance | result |", "|---|---|---|",
           f"| carry: correlation with the frozen benchmark, every series, both references | at least {TOL['carry_corr_min']} | {'**reproduced**' if res['reproduced']['carry'] else '**NOT reproduced**'} |",
           f"| carry: mean absolute monthly difference | at most {TOL['carry_mean_abs_max']} | (same row) |",
           f"| trend: every weight | within {TOL['trend_weight_abs_max']:.0e} of the frozen code | {'**reproduced**' if res['reproduced']['trend'] else '**NOT reproduced**'} |",
           f"| trend: sleeve return correlation / mean absolute difference | at least {TOL['trend_return_corr_min']} / at most {TOL['trend_return_mean_abs_max']} | (same row) |",
           "", "## 4. What is not reproduced here", "",
           "The **published** results (time-series momentum: Moskowitz, Ooi and Pedersen 2012; carry across asset classes: "
           "Koijen, Moskowitz, Pedersen and Vrugt 2018) are for dozens of futures markets from the 1980s on. Six currencies "
           "from 2005 are not that universe, and no number above should be read against those papers. The repository's own "
           "futures sleeves (trials T20 to T22) are built from licensed data that is not in this repository. See "
           "docs/manhattan/ETHAN_ACTIONS.md item 20.", "",
           "## 5. Records", "",
           "Each engine run above is an `evaluation` record in `results/manhattan_engine/exploration_ledger.jsonl` (a hash "
           "chain; exploration role, evidential weight 0) and one row of `results/manhattan_engine/exploration_log.csv`, "
           "written by `nightshift.logs.log_variant`, which refuses a window after 2019-12-31. A second run of this module "
           "adds `rerun` records and no rows.", ""]
    for r in res["records"]:
        L_.append(f"- {r['what']}: record {r['seq']} ({r['type']}), `{r['hash'][:16]}`")
    return "\n".join(L_) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m manhattan.factors.reproduce")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--no-record", action="store_true", help="compute and print, write no ledger record and no log row")
    a = ap.parse_args(argv)
    res = run(a.out, record=not a.no_record)
    print(json.dumps({"reproduced": res["reproduced"], "trend": res["trend"],
                      "carry": {c: v["vs_frozen_code"] for c, v in res["carry"].items()}}, indent=1, default=float))
    if not a.no_record:
        (a.out / "REPRODUCTION.md").write_text(report(res), encoding="utf-8")
        (a.out / "reproduction.json").write_text(json.dumps(res, indent=1, sort_keys=True, default=float) + "\n", encoding="utf-8")
    return 0 if all(res["reproduced"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
