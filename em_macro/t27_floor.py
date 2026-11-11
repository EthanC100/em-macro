"""T27: volatility floor for managed currencies (docs/prereg/T27_managed_fx_vol_floor.md).

    python -m em_macro.t27_floor step0      # Step 0 only (pre-registration §3.3): no T27 return is computed

Step 0 builds the point-in-time managed/not-managed matrix from the IMF AREAER classification tables in
``data/kept/T27/`` (§3.2) and counts the currency-months in which the floor binds: managed, v1.0's
36-month sigma below the EM8 median q_t, and the currency selected (non-zero weight) in v1.0's FX book.
It uses v1.0's own volatilities and selections only. v1.0 is imported unchanged.
"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import risk_model as RM
from . import systematic as SY
from . import verify_v1 as V
from .t01 import reproduce_v1

ROOT = Path(__file__).resolve().parents[1]
KEPT = ROOT / "data" / "kept" / "T27"
OUT = ROOT / "results" / "T27"

EXPLORE = (pd.Period("2005-01", "M"), pd.Period("2019-12", "M"))
CONFIRM = (pd.Period("2020-01", "M"), pd.Period("2026-09", "M"))
EM8 = ["BRL", "MXN", "ZAR", "TRY", "IDR", "PLN", "COP", "CLP"]
MIN_EM = 4

# Category mapping, fixed in the pre-registration (§3.2) before any classification was looked up.
MANAGED = {
    "2009": {"crawl-like arrangement", "stabilized arrangement", "crawling peg", "conventional peg",
             "other managed arrangement"},
    "1999": {"conventional fixed peg", "crawling peg", "crawling band"},
}
NOT_MANAGED = {
    "2009": {"no separate legal tender", "currency board", "pegged exchange rate within horizontal bands",
             "floating", "free floating"},
    "1999": {"no separate legal tender", "currency board", "pegged exchange rate within horizontal bands",
             "managed floating with no predetermined path", "independently floating"},
}


def first_use_month(published: str) -> pd.Period:
    """An edition published in month m is first used for the decision at the end of month m + 1."""
    return pd.Period(published[:7], "M") + 1


def managed_matrix(months: pd.PeriodIndex) -> tuple[pd.DataFrame, pd.DataFrame]:
    """M[t, ccy] in {0, 1} and the edition in force at each decision month (§3.2).

    M is NaN (unknown) in months whose edition in force exists but could not be obtained
    (``obtained == "no"`` in the editions table); 0 before the first edition (not covered)."""
    ed = pd.read_csv(KEPT / "imf_areaer_editions.csv", dtype=str)
    cl = pd.read_csv(KEPT / "imf_areaer_classification.csv", dtype=str)
    ed["first_use"] = [first_use_month(p) for p in ed["published_used"]]
    ed = ed.sort_values(["first_use", "edition"])
    cls = {}
    for _, r in cl.iterrows():
        scheme, cat = r["scheme"], r["category"].strip().lower()
        if cat in MANAGED[scheme]:
            m = 1
        elif cat in NOT_MANAGED[scheme]:
            m = 0
        else:
            raise ValueError(f"unmapped category {cat!r} ({r['edition']}, {r['ccy']})")
        cls[(r["edition"], r["ccy"])] = m
    ccys = list(SY.FX_INSTR)
    M = pd.DataFrame(0.0, index=months, columns=ccys)
    in_force = pd.DataFrame("", index=months, columns=ccys)
    for t in months:
        live = ed[ed["first_use"] <= t]
        if live.empty:
            continue
        e, got = live.iloc[-1]["edition"], live.iloc[-1]["obtained"] == "yes"
        for c in ccys:
            in_force.at[t, c] = e if got else f"{e} (not obtained)"
            if not got:
                M.at[t, c] = np.nan
            elif (e, c) not in cls:
                raise ValueError(f"edition {e} has no row for {c}")
            else:
                M.at[t, c] = cls[(e, c)]
    return M, in_force


def em_median(sigma: pd.DataFrame) -> pd.Series:
    """q_t: median of v1.0's 36-month sigma across the EM8 (at least 4 values, else NaN)."""
    s = sigma[EM8]
    return s.median(axis=1).where(s.notna().sum(axis=1) >= MIN_EM)


def floored_sigma(sigma: pd.DataFrame, M: pd.DataFrame) -> pd.DataFrame:
    """sigma*_{i,t} = max(sigma_{i,t}, q_t) for managed currencies when q_t is defined (§3.1)."""
    q = em_median(sigma)
    lift = (M.reindex_like(sigma).fillna(0) == 1) & q.notna().values[:, None]
    return sigma.where(~lift, np.maximum(sigma, q.values[:, None]))


def frozen_inputs(tmp: Path) -> dict:
    proc = V.extract_snapshots(tmp / "processed")
    snapshots = {p: V.sha256((proc / Path(p).name).read_bytes()) for p in V.FROZEN_INPUTS}
    assert snapshots == V.FROZEN_INPUTS
    for mod in (SY, RM):
        mod.PROC = proc
    return SY.build_inputs()


def stage_step0():
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    inp = frozen_inputs(Path(tempfile.mkdtemp(prefix="t27_frozen_inputs_")))
    repro = reproduce_v1(inp)
    print("v1.0 reproduction:", repro)
    if not (repro["test"]["exact"] and repro["fit"]["exact"]):
        sys.exit("v1.0 does not reproduce exactly on these inputs; nothing run")
    months = inp["months"]
    sigma = SY._vol(inp["fx"]["ret"])                                   # v1.0's own sigma
    selected = SY.book_weights(inp["fx"], ["carry", "trend", "value"]) != 0   # v1.0's FX selection
    q = em_median(sigma)
    M, in_force = managed_matrix(months)
    binds = (M == 1) & (sigma.lt(q, axis=0)) & selected & q.notna().values[:, None]

    unknown = M.isna()
    rows = []
    for t in months:
        for c in M.columns:
            if M.at[t, c] == 1:
                rows.append({"month": str(t), "ccy": c, "edition": in_force.at[t, c],
                             "sigma_pct": round(100 * sigma.at[t, c], 3) if pd.notna(sigma.at[t, c]) else None,
                             "q_pct": round(100 * q.at[t], 3) if pd.notna(q.at[t]) else None,
                             "selected": bool(selected.at[t, c]), "binds": bool(binds.at[t, c])})
    det = pd.DataFrame(rows, columns=["month", "ccy", "edition", "sigma_pct", "q_pct", "selected", "binds"])

    def count(df, lo, hi):
        sl = df.loc[lo:hi].astype(int)
        return {"currency_months": int(sl.values.sum()),
                "by_currency": {c: int(v) for c, v in sl.sum().items() if v}}

    summary = {}
    for name, (lo, hi) in (("2005-01..2019-12", EXPLORE), ("2020-01..2026-09", CONFIRM)):
        summary[name] = {
            "managed": count(M == 1, lo, hi),
            "managed_and_selected": count((M == 1) & selected, lo, hi),
            "floor_binds": count(binds, lo, hi),
            "binding_months": sorted({str(t) for t in binds.loc[lo:hi].index[binds.loc[lo:hi].any(axis=1)]}),
            "classification_unknown": {
                "decision_months": [str(t) for t in unknown.loc[lo:hi].index[unknown.loc[lo:hi].any(axis=1)]],
                "selected_currency_months": count(unknown & selected, lo, hi),
                "selected_and_sigma_below_q": count(unknown & selected & sigma.lt(q, axis=0), lo, hi),
            },
        }
    degenerate = summary["2020-01..2026-09"]["floor_binds"]["currency_months"] == 0
    OUT.mkdir(parents=True, exist_ok=True)
    det.to_csv(OUT / "step0_managed_months.csv", index=False)
    mm = M.copy()
    mm.index = mm.index.astype(str)
    mm.to_csv(OUT / "step0_managed_matrix.csv", index_label="decision_month", float_format="%.0f")
    rec = {"stage": "step0", "started_utc": started,
           "prereg": "docs/prereg/T27_managed_fx_vol_floor.md",
           "sha256": {p: V.sha256((ROOT / p).read_bytes()) for p in
                      ("docs/prereg/T27_managed_fx_vol_floor.md", "em_macro/t27_floor.py",
                       "data/kept/T27/imf_areaer_editions.csv", "data/kept/T27/imf_areaer_classification.csv",
                       "data/kept/T27/imf_annual_report_crosscheck.csv")},
           "input_snapshots": {"commit": V.FREEZE_COMMIT, "sha256": V.FROZEN_INPUTS},
           "v1_reproduction": repro, "summary": summary,
           "degenerate_in_confirmatory_window": degenerate,
           "note": "No T27 return computed. Counts use v1.0's own 36-month sigma and FX selections."}
    (OUT / "STEP0.json").write_text(json.dumps(rec, indent=2, default=str) + "\n")
    print(json.dumps(summary, indent=2))
    print("degenerate in 2020-01..2026-09:", degenerate)


if __name__ == "__main__":
    if sys.argv[1:] == ["step0"]:
        stage_step0()
    else:
        sys.exit(__doc__)
