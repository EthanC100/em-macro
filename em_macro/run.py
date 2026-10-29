"""Pipeline entry point.

    python -m em_macro.run data     # download + build panel, coverage report, event calendars
    python -m em_macro.run fit      # estimate everything on 2005-2021, freeze parameters
    python -m em_macro.run test     # evaluate frozen parameters on 2022+ (refuses to run twice)

The fit stage only ever sees events whose 20-day window closes by 2021-12-31
and factor data up to 2021-12-31.  Everything the test stage needs (factor
betas, regression coefficients, drift-rule directions) is written to
results/fit/frozen_params.json and read back unchanged.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import statsmodels.api as sm

from . import carry, event_study as ES, events as EV
from .config import FIT_END, PROC, RESULTS, TEST_START

FIT_DIR, TEST_DIR = RESULTS / "fit", RESULTS / "test"
COST = carry.COST


def load_panel() -> pd.DataFrame:
    return pd.read_csv(PROC / "daily_panel.csv", index_col=0, parse_dates=True)


def stage_data(refresh: bool = False):
    from . import build_data
    panel, _ = build_data.build(refresh)
    carry.run(panel)
    rates, elec = EV.rate_decisions(refresh), EV.elections()
    EV.to_event_table(rates, elec).to_csv(PROC / "event_table.csv", index=False)


def load_events() -> pd.DataFrame:
    ev = pd.read_csv(PROC / "event_table.csv", parse_dates=["event_date"])
    return ev.drop_duplicates("event_id")


def split(moves: pd.DataFrame, which: str) -> pd.DataFrame:
    bdays = pd.bdate_range("2004-12-01", "2027-12-31")
    end20 = moves["event_date"].map(lambda d: ES.window_dates(d, bdays)[20])
    if which == "fit":
        return moves[end20 <= pd.Timestamp(FIT_END)]
    return moves[moves["event_date"] >= pd.Timestamp(TEST_START)]


# ---------------------------------------------------------------- regressions
def ols(y, x, names):
    d = pd.concat([y, x], axis=1).dropna()
    if len(d) < 6:
        return {"n": len(d)}
    res = sm.OLS(d.iloc[:, 0], sm.add_constant(d.iloc[:, 1:])).fit(cov_type="HC1")
    out = {"n": int(res.nobs), "r2": res.rsquared, "const": res.params["const"]}
    for n in names:
        out.update({f"b_{n}": res.params[n], f"t_{n}": res.tvalues[n], f"p_{n}": res.pvalues[n]})
    return out


def election_regressions(m: pd.DataFrame) -> pd.DataFrame:
    rows = []
    el = m[m.event_type == "election"]
    for asset in ("FX", "Y10"):
        g = el[el.asset == asset]
        for h in ES.HORIZONS:
            y = g[f"ab_{h}"]
            for spec, x in [("signed poll surprise (pp, + = market-preferred beat polls)", g[["surprise_mp_pp"]]),
                            ("odds surprise (+ = market-preferred beat odds)", g[["odds_surprise_mp"]]),
                            ("|move| on |poll error| (pp)", g[["abs_poll_error_pp"]])]:
                yy = y.abs() if spec.startswith("|move|") else y
                rows.append({"asset": asset, "h": h, "spec": spec, **ols(yy, x, x.columns.tolist())})
    return pd.DataFrame(rows)


def rate_surprise_regressions(m: pd.DataFrame) -> pd.DataFrame:
    rows = []
    rd = m[(m.event_type == "rate_decision")]
    for asset in ("FX", "Y10"):
        for scope, g in [("pooled", rd[rd.asset == asset])] + \
                        [(c, x) for c, x in rd[rd.asset == asset].groupby("country")]:
            for h in ES.HORIZONS:
                rows.append({"asset": asset, "scope": scope, "h": h,
                             **ols(g[f"ab_{h}"], g[["surprise_bp"]], ["surprise_bp"])})
    return pd.DataFrame(rows)


def drift_table(m: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for asset in ("FX", "Y10"):
        for et in ("election", "rate_decision", "all"):
            g = m[(m.asset == asset) & ((m.event_type == et) | (et == "all"))]
            for h in ES.HORIZONS[1:]:
                rows.append({"asset": asset, "event_type": et, "h": h, **ES.drift_regression(g, h)})
    return pd.DataFrame(rows)


# ------------------------------------------------------------ drift strategy
def strategy_returns(m: pd.DataFrame, panel: pd.DataFrame, direction: dict, h: int) -> pd.DataFrame:
    """Per-event FX trade from close of day 1 to close of day h, long the local
    currency if direction * sign(day-1 abnormal move) > 0, short otherwise;
    earns/pays the policy-rate differential; 0.10% round-trip cost per trade.
    Returns monthly returns of an equal-weight book of the open trades (cash
    when no trade is open), comparable with the carry benchmark."""
    bdays = pd.bdate_range("2004-12-01", "2027-12-31")
    fx = panel[[c for c in panel if c.startswith("FX_")]].ffill(limit=5)
    pol = panel[[c for c in panel if c.startswith("POL_")]].ffill()
    daily = []
    trades = []
    for r in m[m.asset == "FX"].itertuples():
        d = direction.get(r.event_type, 0)
        if d == 0 or not np.isfinite(r.ab_1) or r.ab_1 == 0:
            continue
        sgn = d * np.sign(r.ab_1)
        w = ES.window_dates(r.event_date, bdays)
        dates = bdays[(bdays > w[1]) & (bdays <= w[h])]
        s = fx[f"FX_{r.country}"]
        ret = (s.shift(1) / s - 1).reindex(dates)                        # local ccy return vs USD
        diff = ((pol[f"POL_{r.country}"] - pol["POL_US"]) / 100 / 252).shift(1).reindex(dates)
        pnl = sgn * (ret + diff)
        if pnl.isna().all():
            continue
        pnl = pnl.fillna(0.0)
        pnl.iloc[0] -= COST
        daily.append(pnl.rename(r.event_id))
        trades.append({"event_id": r.event_id, "country": r.country, "event_type": r.event_type,
                       "event_date": r.event_date, "side": "long local" if sgn > 0 else "short local",
                       "return": (1 + pnl).prod() - 1})
    if not daily:
        return pd.DataFrame(), pd.DataFrame()
    book = pd.concat(daily, axis=1)
    port = book.mean(axis=1)                                             # equal weight across open trades
    port = port.reindex(pd.bdate_range(port.index.min(), port.index.max()), fill_value=0.0)
    monthly = (1 + port).groupby(port.index.to_period("M")).prod() - 1
    return monthly, pd.DataFrame(trades)


# ------------------------------------------------------------------- stages
def stage_fit():
    FIT_DIR.mkdir(parents=True, exist_ok=True)
    panel = load_panel()
    levels = ES.asset_levels(panel)
    betas = ES.factor_betas(levels, end=FIT_END)
    ev = load_events()
    moves = split(ES.event_moves(ev, levels, betas), "fit")
    moves.to_csv(FIT_DIR / "event_moves.csv", index=False, float_format="%.4f")
    betas.to_csv(FIT_DIR / "factor_betas.csv", float_format="%.5f")

    by_type = ES.summarize(moves, ["asset", "event_type", "country"])
    by_type_all = ES.summarize(moves, ["asset", "event_type"])
    by_sub = ES.summarize(moves, ["asset", "event_type", "subtype"])
    by_type.to_csv(FIT_DIR / "summary_by_country_type.csv", index=False, float_format="%.4f")
    by_type_all.to_csv(FIT_DIR / "summary_by_type.csv", index=False, float_format="%.4f")
    by_sub.to_csv(FIT_DIR / "summary_by_subtype.csv", index=False, float_format="%.4f")

    er = election_regressions(moves); er.to_csv(FIT_DIR / "election_surprise_regressions.csv", index=False, float_format="%.4f")
    rr = rate_surprise_regressions(moves); rr.to_csv(FIT_DIR / "rate_surprise_regressions.csv", index=False, float_format="%.4f")
    dr = drift_table(moves); dr.to_csv(FIT_DIR / "drift_regressions.csv", index=False, float_format="%.4f")

    # trading rule: direction per event type = sign of the fit-sample FX drift slope at h=5
    direction = {}
    for et in ("election", "rate_decision"):
        row = dr[(dr.asset == "FX") & (dr.event_type == et) & (dr.h == 5)]
        direction[et] = int(np.sign(row["slope"].iloc[0])) if len(row) and np.isfinite(row["slope"].iloc[0]) else 0
    strat = {}
    for h in (5, 20):
        monthly, trades = strategy_returns(moves, panel, direction, h)
        trades.to_csv(FIT_DIR / f"drift_rule_trades_h{h}.csv", index=False, float_format="%.5f")
        strat[h] = carry.stats(monthly.loc[:FIT_END[:7]]) if len(monthly) else {}

    frozen = {
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fit_end": FIT_END, "test_start": TEST_START,
        "factor_betas": betas.reset_index().astype({"start": str, "end": str}).to_dict("records"),
        "election_regressions": er.to_dict("records"),
        "rate_surprise_regressions": rr.to_dict("records"),
        "drift_rule_direction": direction,
        "drift_rule_fit_stats": strat,
    }
    (FIT_DIR / "frozen_params.json").write_text(json.dumps(frozen, indent=1, default=float))
    print("fit done; drift-rule direction:", direction)


def stage_test(force: bool = False):
    TEST_DIR.mkdir(parents=True, exist_ok=True)
    guard = TEST_DIR / "TEST_RUN.json"
    if guard.exists() and not force:
        sys.exit(f"hold-out already evaluated ({guard}); re-running would turn the hold-out into a fit sample. "
                 "Use --force only to reproduce the same numbers.")
    frozen = json.loads((FIT_DIR / "frozen_params.json").read_text())
    betas = pd.DataFrame(frozen["factor_betas"]).set_index("asset")
    panel = load_panel()
    levels = ES.asset_levels(panel)
    ev = load_events()
    moves = split(ES.event_moves(ev, levels, betas), "test")
    moves.to_csv(TEST_DIR / "event_moves.csv", index=False, float_format="%.4f")
    ES.summarize(moves, ["asset", "event_type", "country"]).to_csv(TEST_DIR / "summary_by_country_type.csv", index=False, float_format="%.4f")
    ES.summarize(moves, ["asset", "event_type"]).to_csv(TEST_DIR / "summary_by_type.csv", index=False, float_format="%.4f")
    ES.summarize(moves, ["asset", "event_type", "subtype"]).to_csv(TEST_DIR / "summary_by_subtype.csv", index=False, float_format="%.4f")
    drift_table(moves).to_csv(TEST_DIR / "drift_regressions.csv", index=False, float_format="%.4f")

    # out-of-sample predictions from frozen regressions
    oos = []
    specs = {"election": (frozen["election_regressions"], {"signed poll surprise": "surprise_mp_pp",
                                                           "odds surprise": "odds_surprise_mp"}),
             "rate_decision": (frozen["rate_surprise_regressions"], {"pooled": "surprise_bp"})}
    for et, (regs, xmap) in specs.items():
        for reg in regs:
            key = reg.get("spec", reg.get("scope", ""))
            var = next((v for k, v in xmap.items() if key.startswith(k)), None)
            if var is None or f"b_{var}" not in reg:
                continue
            g = moves[(moves.event_type == et) & (moves.asset == reg["asset"])][[var, f"ab_{reg['h']}"]].dropna()
            if g.empty:
                continue
            pred = reg["const"] + reg[f"b_{var}"] * g[var]
            y = g[f"ab_{reg['h']}"]
            oos.append({"event_type": et, "asset": reg["asset"], "h": reg["h"], "spec": key, "n_test": len(g),
                        "fit_slope": reg[f"b_{var}"], "fit_p": reg[f"p_{var}"],
                        "oos_r2_vs_zero": 1 - ((y - pred) ** 2).sum() / (y ** 2).sum(),
                        "corr_pred_actual": np.corrcoef(pred, y)[0, 1] if len(g) > 2 else np.nan,
                        "sign_hit_rate": (np.sign(pred) == np.sign(y)).mean()})
    pd.DataFrame(oos).to_csv(TEST_DIR / "oos_surprise_predictions.csv", index=False, float_format="%.4f")

    # frozen drift rule vs carry benchmark over the hold-out
    rows = []
    cr = pd.read_csv(PROC / "carry_monthly_returns.csv", index_col=0)
    cr.index = pd.PeriodIndex(cr.index, freq="M")
    last_full = pd.Period(panel.index.max(), "M") - (0 if panel.index.max().is_month_end else 1)
    rows.append({"strategy": "carry benchmark, equal-weight basket",
                 **carry.stats(cr["EW"].loc[TEST_START[:7]:last_full])})
    for h in (5, 20):
        monthly, trades = strategy_returns(moves, panel, frozen["drift_rule_direction"], h)
        trades.to_csv(TEST_DIR / f"drift_rule_trades_h{h}.csv", index=False, float_format="%.5f")
        if len(monthly):
            monthly = monthly.reindex(pd.period_range(TEST_START[:7], last_full, freq="M"), fill_value=0.0)
            rows.append({"strategy": f"event drift rule, hold day 1 -> day {h}", **carry.stats(monthly),
                         "n_trades": len(trades), "mean_trade_%": 100 * trades["return"].mean(),
                         "hit_rate": (trades["return"] > 0).mean()})
    pd.DataFrame(rows).to_csv(TEST_DIR / "strategy_vs_carry.csv", index=False, float_format="%.4f")
    guard.write_text(json.dumps({"run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                 "frozen_params_created_utc": frozen["created_utc"]}, indent=1))
    print("hold-out test done")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "data":
        stage_data("--refresh" in sys.argv)
    elif cmd == "fit":
        stage_fit()
    elif cmd == "test":
        stage_test("--force" in sys.argv)
    else:
        sys.exit(__doc__)
