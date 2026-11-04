"""v1.1 systematic macro strategy = frozen v1.0 + exactly the T18 rebalancing rule (docs/v1.1_freeze.md).

    python -m em_macro.systematic_v11 verify      # reproduce T18's committed results exactly (exit 1 if not)
    python -m em_macro.systematic_v11 costs       # diagnostic: v1.0 and v1.1, 2020-01..2026-09, at several costs
    python -m em_macro.systematic_v11 update      # v1.1 positions.csv and paper_pnl.csv (monthly workflow)
    python -m em_macro.systematic_v11 rebalance   # stamp the v1.1 rebalance dates (monthly workflow)

What v1.1 is.  Everything that decides v1.0's targets is v1.0's frozen code, imported and never modified
(em_macro/systematic.py, tag v1.0-frozen, commit 7886867; frozen design results/systematic/fit/frozen_design.json):
signals, thirds, inverse-vol sizing, 10% book and total vol targets, 50/50 book mix, 6x gross cap, cost model,
execution lags.  The one change is the one T18 tested and passed (pre-registration docs/prereg/T16-T19_risk_batch.md
section 3.3, commit 4c10856; result results/T16-T19_risk_batch.md): v1.0's 25% relative no-trade band is replaced by

    band in risk units   trade only if |delta w_i| * sigma_i > 0.1 * the position's risk budget
    partial rebalancing  w_new = w + 0.5 * (w* - w)

applied by the trial's own code, em_macro/t18_rebal.py (`run`), as committed at the T18 run (898bc21) and unchanged.
No other change.  v1.0 remains the frozen control; both run live in parallel.

Outputs.  v1.0 keeps writing results/systematic/ (unchanged).  v1.1 writes only results/systematic_v1.1/
(positions.csv, paper_pnl.csv, rebalance_log.csv, freeze/) and results/live_compare/turnover.csv (both
versions' monthly turnover from the same inputs, for the Ledger's side-by-side table).
"""
from __future__ import annotations

import hashlib
import io
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import systematic as SY
from . import t18_rebal as T18
from . import tstrend as TS
from .config import RESULTS, ROOT

VERSION = "v1.1"
OUT = RESULTS / "systematic_v1.1"
FREEZE_DIR = OUT / "freeze"
COMPARE_DIR = RESULTS / "live_compare"
V1 = SY.VARIANTS["combined"]
TEST = (SY.TEST_START, pd.Period("2026-09", "M"))
FIT = (None, SY.FIT_END)
LAG = {"fx": 1, "bond": 1 + SY.DESIGN["bond_execution_lag_months"]}

# The live record starts with the 3 December 2026 rebalance (positions as of 2026-11, effective 2026-12).
LIVE_START_MONTH = "2026-12"
LIVE_SINCE = "2026-12-03"

# The rule, as pre-registered (section 3.3) and as T18 ran it; asserted equal to t18_rebal's constants.
RULE = {"replaces": "v1.0's 25% relative no-trade band (systematic._apply_band, DESIGN['no_trade_band'] = 0.25)",
        "band_risk_units": 0.10, "partial_rebalancing": 0.5,
        "targets": "v1.0's targets after the 10% total rescaling and the 6x gross cap (its pre-band weights)",
        "risk_budget": "equal risk v1.0 gives each selected position of its book: mean |w*_i| sigma_i over the "
                       "book's selected instruments (sigma = v1.0's 36-month vol)",
        "band_applied_to": "the proposed half-trade; the residual of an exited position (target 0) is closed once "
                           "its half-trade falls inside the band",
        "code": "em_macro/t18_rebal.py: run() = capped_targets -> apply_rules -> pnl"}

# Frozen files v1.1 is built from: SHA-256 at the T18 run (results/T16-T19/RUN.json) and at the v1.0 freeze.
FROZEN = {
    "em_macro/systematic.py": "1eb4cf6b1c537c1711e5fff0b7aa044fee932c20992eb0d3cea4c3c5fc50be66",
    "results/systematic/fit/frozen_design.json": "f0cce4c9a819379c7bce4310ad58e8765b8149ef0d045ab25dd84c1b13983858",
    "em_macro/t18_rebal.py": "dda6456d676281b48080d3c0a6c304d51c928cea39e0f70c696a364a10f96c43",
    "em_macro/tstrend.py": "f02acd6e05232273b6a531674fe00be0cf63cf4704edbce012af5048f29c2344",
}
assert T18.BAND_RISK == RULE["band_risk_units"] and T18.PARTIAL == RULE["partial_rebalancing"]


def _sha(path: str) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def check_frozen() -> None:
    """Refuse to run if a frozen file v1.1 is built from has changed, or v1.0's design differs from its freeze."""
    bad = [f"{p}: sha256 {_sha(p)[:16]}..., expected {h[:16]}..." for p, h in FROZEN.items() if _sha(p) != h]
    if bad:
        sys.exit("v1.1 refuses to run, a frozen file changed:\n  " + "\n  ".join(bad))
    SY._check_frozen(strict=False)          # v1.0's DESIGN equals frozen_design.json


# ============================================================ the strategy
def run(inp: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """v1.1 monthly P&L (v1.0's columns; weights in .attrs['weights']) and the rebalancing log."""
    return T18.run(inp)


def turnover(res: pd.DataFrame) -> pd.Series:
    """One-way notional traded per month (sum |dW|), dated like the costs: the month the trade starts earning
    (same definition as t01.turnover, used in the T18 report)."""
    W = res.attrs["weights"]
    fx = [c for c in W.columns if c in SY.FX_INSTR]
    bond = [c for c in W.columns if c not in SY.FX_INSTR]
    out = 0.0
    for cols, lag in ((fx, LAG["fx"]), (bond, LAG["bond"])):
        out = out + W[cols].diff().abs().sum(axis=1).shift(lag).fillna(0.0)
    return out.reindex(res.index)


def describe(k: str, book: str) -> str:
    """Instrument description, worded as in v1.0's positions.csv (systematic.stage_update)."""
    c = SY.FX_INSTR.get(k, k[:2])
    if book == "fx":
        return f"{k} vs USD ({SY.NAME.get(c, c)})"
    if k.endswith("-DE"):
        return f"{SY.NAME[c]} 10y bond spread over the Bund (long {SY.NAME[c]}, short Bund)"
    if k == "DE10Y":
        return "German 10y Bund (excess over the ECB rate)"
    return f"{SY.NAME[c]} 10y local-currency bond (excess over local policy rate)"


def sample_label(m: pd.Period) -> str:
    if m <= SY.FIT_END:
        return "design 2005-2019 (in-sample, v1.0's design period)"
    if m <= TEST[1]:
        return "test 2020-01..2026-09 (T18 trial, evaluated once)"
    if str(m) < LIVE_START_MONTH:
        return "pre-live (not counted)"
    return "live paper trading (v1.1)"


# ============================================================ monthly update
def stage_update(out: Path = OUT, compare_dir: Path = COMPARE_DIR) -> pd.DataFrame:
    """positions.csv (this month's v1.1 book) and paper_pnl.csv (full history) under results/systematic_v1.1/,
    plus results/live_compare/turnover.csv.  Reads the same refreshed inputs as v1.0's update; writes nothing
    under results/systematic/."""
    check_frozen()
    inp = SY.build_inputs()
    res, log = run(inp)
    W = res.attrs["weights"]
    target = T18.capped_targets(inp)
    t = inp["months"][-1]
    sig = {b: SY.signals(inp[b]) for b in ("fx", "bond")}
    vol = {b: SY._vol(inp[b]["ret"]) for b in ("fx", "bond")}
    prev = W.shift(1).fillna(0.0)
    rows = []
    for b in ("fx", "bond"):
        for k in inp[b]["ret"].columns:
            w = W.at[t, k]
            if abs(w) < 1e-9:
                continue
            rows.append({"as_of": f"{t}", "effective_from": f"{t + 1}", "version": VERSION, "book": b,
                         "instrument": k, "description": describe(k, b), "side": "long" if w > 0 else "short",
                         "size_pct_of_capital": round(100 * w, 2), "risk_share_pct": np.nan,
                         "instrument_vol_pct": round(100 * vol[b].at[t, k], 2),
                         "carry_z": sig[b]["carry"].at[t, k], "trend_z": sig[b]["trend"].at[t, k],
                         "value_z": sig[b]["value"].at[t, k], "cost_pct_per_trade": 100 * inp["cost"][k],
                         "target_pct_of_capital": round(100 * target.at[t, k], 2),
                         "trade_pct_of_capital": round(100 * (w - prev.at[t, k]), 2)})
    pos = pd.DataFrame(rows)
    if len(pos):
        rv = pos["size_pct_of_capital"].abs() * pos["instrument_vol_pct"]
        pos["risk_share_pct"] = (100 * rv / rv.sum()).round(1)
        pos = pos.sort_values(["book", "side", "size_pct_of_capital"], ascending=[True, True, False])
    out.mkdir(parents=True, exist_ok=True)
    pos.to_csv(out / "positions.csv", index=False, float_format="%.3f")

    pnl = res[["fx_gross", "bond_gross", "cost", "net", "gross_leverage"]].copy()
    pnl["turnover"] = turnover(res)
    pnl["sample"] = [sample_label(m) for m in pnl.index]
    pnl["cumulative_net"] = (1 + pnl["net"]).cumprod()
    pnl["carry_basket"] = inp["carry_basket"].reindex(pnl.index)
    pnl["sp500_tr"] = inp["spx"].reindex(pnl.index)
    pnl.index.name = "month"
    pnl.reset_index().assign(month=lambda d: d["month"].astype(str)).to_csv(out / "paper_pnl.csv", index=False,
                                                                           float_format="%.6f")
    # both versions' monthly turnover on the same inputs (v1.0's paper_pnl.csv has no turnover column)
    v1 = SY.run(inp, V1)
    cmp = pd.DataFrame({"v1.0_turnover": turnover(v1), "v1.1_turnover": turnover(res)})
    cmp.index.name = "month"
    compare_dir.mkdir(parents=True, exist_ok=True)
    cmp.reset_index().assign(month=lambda d: d["month"].astype(str)).to_csv(compare_dir / "turnover.csv",
                                                                           index=False, float_format="%.6f")
    print(f"v1.1 positions as of {t} (effective {t + 1}): {len(pos)} positions, gross "
          f"{pos['size_pct_of_capital'].abs().sum() if len(pos) else 0:.1f}% of capital")
    print(pos.to_string())
    return pos


def stage_rebalance(out: Path = OUT) -> dict:
    """Scheduled vs actual date of this v1.1 rebalance -> results/systematic_v1.1/rebalance_log.csv."""
    from . import rebalance
    return rebalance.record(out=out)


# ============================================================ freeze checks (frozen v1.0 input snapshots)
def frozen_inputs(tmp: Path) -> dict:
    """SY.build_inputs() on v1.0's input snapshots at the freeze commit 7886867, as T18 was run."""
    from . import verify_v1 as V
    proc = V.extract_snapshots(tmp / "processed")
    with V.frozen_inputs(proc):
        return SY.build_inputs()


def _csv_text(df: pd.DataFrame, fmt: str) -> pd.DataFrame:
    """A table as the T16-T19 runner wrote it (to_csv with float_format), read back as text."""
    buf = io.StringIO()
    df.to_csv(buf, index=False, float_format=fmt)
    buf.seek(0)
    return pd.read_csv(buf, dtype=str, keep_default_na=False)


def _committed(name: str) -> pd.DataFrame:
    return pd.read_csv(RESULTS / "T16-T19" / name, dtype=str, keep_default_na=False)


def reproduce_t18(inp: dict) -> dict:
    """v1.1 on these inputs vs T18's committed results (results/T16-T19/): every T18 row of performance.csv,
    the T18 columns of monthly_net.csv, the T18 rows of by_year_2020_2026.csv, the six trade logs (text equality
    at the files' precision), and the decisive 1x criteria statistics (float equality)."""
    from . import holdout as HO
    from . import t01 as T01
    from . import t1619 as B
    sub = {"all": inp, "half B": TS.subset(inp, HO.instruments("B")), "half A": TS.subset(inp, HO.instruments("A"))}
    runs, logs = {}, {}
    for cm in B.COSTS:
        for u in B.UNIVERSES:
            x = sub[u] if cm == 1.0 else TS.with_costs(sub[u], cm)
            runs[(u, cm)], logs[(u, cm)] = run(x)
    checks = {}
    # performance.csv
    rows = [{"universe": u, "costs": f"{cm:g}x", "strategy": "T18", "period": p, **T01.metrics(res, per)}
            for (u, cm), res in runs.items() for p, per in B.PERIODS.items()]
    mine = _csv_text(pd.DataFrame(rows), "%.4f")
    ref = _committed("performance.csv").query("strategy == 'T18'").reset_index(drop=True)
    checks["performance.csv (T18 rows)"] = {"rows": len(ref), "identical": mine.equals(ref)}
    # monthly_net.csv
    ref = _committed("monthly_net.csv")
    cols = [f"{u}|{cm:g}x|T18" for (u, cm) in runs]
    mon = pd.DataFrame({f"{u}|{cm:g}x|T18": B._net(r) for (u, cm), r in runs.items()})
    mon.index = mon.index.astype(str)
    mon = mon.reindex(ref["month"])
    mon.index.name = "month"
    mine = _csv_text(mon.reset_index(), "%.6f")
    checks["monthly_net.csv (T18 columns)"] = {"columns": len(cols), "months": len(ref),
                                               "identical": mine.equals(ref[["month", *cols]])}
    # by_year_2020_2026.csv
    yr = []
    for cm in B.COSTS:
        t = B.by_year(runs[("all", cm)])
        t.insert(0, "strategy", "T18")
        t.insert(0, "costs", f"{cm:g}x")
        yr.append(t)
    mine = _csv_text(pd.concat(yr), "%.4f")
    ref = _committed("by_year_2020_2026.csv").query("strategy == 'T18'").reset_index(drop=True)
    checks["by_year_2020_2026.csv (T18 rows)"] = {"rows": len(ref), "identical": mine.equals(ref)}
    # trade logs
    for (u, cm), lg in logs.items():
        name = f"t18_tradelog_{u.replace(' ', '')}_{cm:g}x.csv"
        ref = _committed(name)
        checks[name] = {"rows": len(ref), "identical": _csv_text(lg, "%.6f").equals(ref)}
    # the decisive 1x statistics in criteria.json, recomputed with the runner's own functions
    crit = json.loads((RESULTS / "T16-T19" / "criteria.json").read_text())["1x"]["per_trial"]["T18"]
    v1 = B._net(SY.run(inp, V1)).loc[TEST[0]:TEST[1]]
    v1B = B._net(SY.run(sub["half B"], V1)).loc[TEST[0]:TEST[1]]
    t = B._net(runs[("all", 1.0)]).loc[TEST[0]:TEST[1]]
    tB = B._net(runs[("half B", 1.0)]).loc[TEST[0]:TEST[1]]
    bs = B.bootstrap_noninferiority(t, v1)
    stats = {"sr": B.sharpe(t), "sr_v1": B.sharpe(v1), "dd": B.max_drawdown(t), "es": B.expected_shortfall(t),
             "srB": B.sharpe(tB), "srB_v1": B.sharpe(v1B), "ddB": B.max_drawdown(tB),
             "turnover": float(T01.turnover(runs[("all", 1.0)]).loc[TEST[0]:TEST[1]].mean() * 12),
             "p_one_sided": bs["p_one_sided"], "delta_sr": bs["delta_sr"]}
    ref_stats = {**{k: crit[k] for k in stats if k in crit}, "p_one_sided": crit["bootstrap"]["p_one_sided"],
                 "delta_sr": crit["bootstrap"]["delta_sr"]}
    checks["criteria.json (1x, T18 statistics)"] = {
        "values": stats, "max_abs_diff": max(abs(stats[k] - ref_stats[k]) for k in stats),
        "identical": all(stats[k] == ref_stats[k] for k in stats)}
    # turnover definition used for the live comparison = the trial's
    checks["turnover() == t01.turnover"] = {"identical": bool((turnover(runs[("all", 1.0)])
                                                               == T01.turnover(runs[("all", 1.0)])).all())}
    return checks


def stage_verify() -> bool:
    check_frozen()
    from . import verify_v1 as V
    with tempfile.TemporaryDirectory() as tmp:
        inp = frozen_inputs(Path(tmp))
    ok_v1 = all(r["identical"] for r in V.compare({
        V.DESIGN_TABLE: SY.evaluate(inp, slice(None, SY.FIT_END)),
        V.TEST_TABLE: SY.evaluate(inp, slice(*TEST))}).values())
    checks = reproduce_t18(inp)
    ok = ok_v1 and all(c["identical"] for c in checks.values())
    for k, c in checks.items():
        print(f"{k}: {'IDENTICAL' if c['identical'] else 'DIFFERENT'}  "
              f"{ {a: b for a, b in c.items() if a not in ('identical', 'values')} }")
    print(f"v1.0 on the same inputs: {'IDENTICAL' if ok_v1 else 'DIFFERENT'} to its committed tables")
    t = checks["criteria.json (1x, T18 statistics)"]["values"]
    print(f"v1.1, 2020-01..2026-09, 1x: Sharpe {t['sr']:.4f}, MaxDD {100 * t['dd']:.3f}%, turnover "
          f"{t['turnover']:.2f}x/yr (v1.0 Sharpe {t['sr_v1']:.4f})")
    FREEZE_DIR.mkdir(parents=True, exist_ok=True)
    (FREEZE_DIR / "reproduction.json").write_text(json.dumps({
        "run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "inputs": "v1.0's data/processed snapshots at 7886867 (verify_v1.extract_snapshots) and the raw downloads "
                  "kept in data/kept/T16-T19/",
        "pandas": pd.__version__, "numpy": np.__version__, "v1.0_reproduced_exactly": ok_v1,
        "t18_reproduced_exactly": ok, "checks": checks,
        "sha256": {p: _sha(p) for p in [*FROZEN, "em_macro/systematic_v11.py"]}}, indent=1, default=float))
    print("v1.1 REPRODUCES T18 EXACTLY" if ok else "v1.1 DOES NOT REPRODUCE T18 EXACTLY")
    return ok


# ============================================================ cost diagnostic (not a decision)
def stage_costs() -> pd.DataFrame:
    """v1.0 and v1.1, 2020-01..2026-09, at 0x (context), 0.5x, the cost audit's literature central per-instrument
    estimates (without and with its roll-cost convention), 1x and 2x.  Costs never feed back into either version's
    weights (asserted), so every row has the same positions as at 1x; only the cost line changes."""
    check_frozen()
    from . import cost_audit as CA
    from . import t01 as T01
    with tempfile.TemporaryDirectory() as tmp:
        inp = frozen_inputs(Path(tmp))
    base = pd.Series(inp["cost"])
    central = (CA.load_estimates()["central_bp"] / 1e4).reindex(base.index)
    assert central.notna().all()
    scenarios = [("0x (gross, context)", base * 0.0, False), ("0.5x v1.0 costs", base * 0.5, False),
                 ("cost audit central (per instrument)", central, False),
                 ("cost audit central + roll costs", central, True),
                 ("1x v1.0 costs (decisive for T18)", base, False), ("2x v1.0 costs", base * 2.0, False)]
    W1 = {"v1.0": SY.run(inp, V1).attrs["weights"], "v1.1": run(inp)[0].attrs["weights"]}
    rows = []
    for label, cv, roll in scenarios:
        x = {**inp, "cost": {k: float(cv[k]) for k in inp["cost"]}}
        for name, res in (("v1.0", SY.run(x, V1)), ("v1.1", run(x)[0])):
            assert (res.attrs["weights"] - W1[name]).abs().max().max() == 0.0          # same positions
            if roll:
                rc = CA.roll_cost_series(x, res.attrs["weights"], cv.to_dict(), res.index)
                res = res.copy()
                res["cost"] = res["cost"] + rc
                res["net"] = res["net"] - rc
                res.attrs["weights"] = W1[name]
            m = T01.metrics(res, TEST)
            rows.append({"scenario": label, "strategy": name, "months": m["months"], "sharpe": m["sharpe"],
                         "ann_return_%": m["ann_return_%"], "ann_vol_%": m["ann_vol_%"],
                         "max_drawdown_%": m["max_drawdown_%"], "ES97.5_monthly_%": m["ES97.5_monthly_%"],
                         "turnover_x_pa": m["turnover_x_pa"], "cost_drag_%_pa": m["cost_drag_%_pa"]})
    tab = pd.DataFrame(rows)
    a = tab[tab.strategy == "v1.0"].set_index("scenario")
    b = tab[tab.strategy == "v1.1"].set_index("scenario")
    diff = pd.DataFrame({"d_sharpe": b["sharpe"] - a["sharpe"], "d_ann_return_%": b["ann_return_%"] - a["ann_return_%"],
                         "d_max_drawdown_%": b["max_drawdown_%"] - a["max_drawdown_%"],
                         "d_cost_drag_%_pa": b["cost_drag_%_pa"] - a["cost_drag_%_pa"]})
    tab = tab.merge(diff.reset_index().assign(strategy="v1.1"), on=["scenario", "strategy"], how="left")
    FREEZE_DIR.mkdir(parents=True, exist_ok=True)
    tab.to_csv(FREEZE_DIR / "cost_sensitivity.csv", index=False, float_format="%.4f")
    # cross-checks against the published tables: v1.0 rows vs the cost audit, v1.1 1x/2x rows vs T18
    audit = pd.read_csv(RESULTS / "cost_audit" / "step3_sensitivity.csv").query("period == '2020-01..2026-09'")
    pairs = {"0x (gross, context)": "0x v1.0 costs", "0.5x v1.0 costs": "0.5x v1.0 costs",
             "cost audit central (per instrument)": "literature central (per instrument)",
             "cost audit central + roll costs": "literature central + roll costs",
             "1x v1.0 costs (decisive for T18)": "1x v1.0 costs", "2x v1.0 costs": "2x v1.0 costs"}
    gaps = []
    for mine, theirs in pairs.items():
        r = audit[audit.scenario == theirs].iloc[0]
        x = a.loc[mine]
        gaps.append(max(abs(round(x[c], 4) - r[c]) for c in ("sharpe", "ann_return_%", "max_drawdown_%",
                                                               "cost_drag_%_pa")))
    perf = pd.read_csv(RESULTS / "T16-T19" / "performance.csv").query(
        "universe == 'all' and strategy == 'T18' and period == '2020-01..2026-09 (test)'").set_index("costs")
    t18_gap = max(abs(round(b.loc[s, c], 4) - perf.loc[k, c]) for s, k in
                  (("1x v1.0 costs (decisive for T18)", "1x"), ("2x v1.0 costs", "2x"))
                  for c in ("sharpe", "ann_return_%", "max_drawdown_%", "turnover_x_pa", "cost_drag_%_pa"))
    meta = {"run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "max_abs_diff_v1.0_vs_cost_audit_step3_at_4dp": max(gaps),
            "max_abs_diff_v1.1_vs_T18_performance_at_4dp": t18_gap,
            "note": "diagnostic only, not a decision; positions identical across scenarios (asserted)"}
    (FREEZE_DIR / "cost_sensitivity.json").write_text(json.dumps(meta, indent=1))
    print(tab.round(3).to_string())
    print(json.dumps(meta, indent=1))
    return tab


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "verify":
        sys.exit(0 if stage_verify() else 1)
    elif cmd == "costs":
        stage_costs()
    elif cmd == "update":
        stage_update()
    elif cmd == "rebalance":
        stage_rebalance()
    else:
        sys.exit(__doc__)
