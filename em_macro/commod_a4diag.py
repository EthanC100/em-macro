"""A4 diagnostic for Build 0 (docs/prereg/T20-T22_A4_diagnostic.md).

    EM_MACRO_DATA=... AQR_DATA=... python -m em_macro.commod_a4diag a      # step (a): error checks
    EM_MACRO_DATA=... AQR_DATA=... python -m em_macro.commod_a4diag c      # step (c): AQR's construction, once

Only counts, flags and correlations are printed or written publicly; every series stays in the private data repo.
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from . import commod_build0 as B
from . import commod_data as CD

OUT = CD.ROOT / "results" / "T20-T22" / "build0_a4_diagnostic.json"


# ------------------------------------------------------------------------------------------------ step (a)
def _raw_market(code: str) -> tuple[dict[str, pd.Series], pd.DatetimeIndex]:
    """Independent re-read of the raw Norgate CSVs (no commod_data code): close series per contract and the
    market's trading days (union of all contract dates)."""
    folder = CD.snapshot_dir() / "contracts" / code
    closes = {}
    for p in sorted(folder.glob("*.csv")):
        df = pd.read_csv(p)
        closes[p.stem] = pd.Series(df["close"].astype(float).values, index=pd.to_datetime(df["date"]))
    days = pd.DatetimeIndex(sorted(set().union(*[set(s.index) for s in closes.values()])))
    return closes, days


def check_a(code: str) -> tuple[dict, list[dict]]:
    md = CD.MarketData(code)
    ct = md.contracts
    names = list(ct.index)
    r = md.rolls.dropna(subset=["F1"])
    rets = md.daily_returns("F1")
    inputs = B.carry_portfolio_inputs(md, rets)            # exactly what A4 used
    raw, days = _raw_market(code)
    flags, res = [], {"pairing": 0, "d_range": 0, "sign": 0, "unit": 0, "settle_mismatch": 0,
                      "hold_mismatch": 0, "carry_outliers": 0, "months_used": 0}
    ex = list(r["execution"])
    for k in range(len(r) - 1):
        m = r.index[k]
        row = r.iloc[k]
        t, f1c, f2c = row["decision"], row["F1"], row["F2"]
        c = inputs.at[m, "carry_log"] if m in inputs.index else np.nan
        if not np.isfinite(c):
            continue
        res["months_used"] += 1
        # 1. pairing
        if f2c is None or names.index(f2c) != names.index(f1c) + 1:
            res["pairing"] += 1
            flags.append({"market": code, "month": str(m), "check": "pairing"})
        d1, d2 = (ct.at[f1c, "ltd"] - t).days, (ct.at[f2c, "ltd"] - t).days
        if not (15 <= d2 - d1 <= 400) or d2 <= d1:
            res["d_range"] += 1
            flags.append({"market": code, "month": str(m), "check": "D2-D1", "value": d2 - d1})
        # 4. raw settlements on t
        p1, p2 = raw[f1c].get(t, np.nan), raw[f2c].get(t, np.nan)
        u1, u2 = md.settle(f1c, t), md.settle(f2c, t)
        if not (np.isclose(p1, u1, rtol=1e-9, atol=0) and np.isclose(p2, u2, rtol=1e-9, atol=0)):
            res["settle_mismatch"] += 1
            flags.append({"market": code, "month": str(m), "check": "settlement"})
        # 2. sign and units
        cc = (np.log(p1) - np.log(p2)) * 365.0 / (d2 - d1)
        if not np.isclose(cc, c, rtol=1e-9, atol=1e-12) or (np.sign(cc) != np.sign(p1 - p2) and p1 != p2):
            res["sign"] += 1
            flags.append({"market": code, "month": str(m), "check": "sign/formula"})
        if abs(np.log(p1 / p2)) > 0.5:
            res["unit"] += 1
            flags.append({"market": code, "month": str(m), "check": "|ln F1/F2|>0.5",
                          "d2_d1": d2 - d1})
        if abs(c) > 5:
            res["carry_outliers"] += 1
            flags.append({"market": code, "month": str(m), "check": "|carry|>5", "d2_d1": d2 - d1,
                          "d1": d1})
        # 4. holding return from the raw CSV of F1 alone (carry the last settlement forward over market days)
        a, b = ex[k], ex[k + 1]
        s = raw[f1c].reindex(days).ffill()
        h_raw = s.get(b) / s.get(a) - 1 if a in s.index and b in s.index else np.nan
        h = inputs.at[m, "hold_ret"]
        if not (np.isfinite(h_raw) and np.isfinite(h) and np.isclose(h_raw, h, rtol=1e-9, atol=1e-12)):
            if not (np.isnan(h_raw) and np.isnan(h)):
                res["hold_mismatch"] += 1
                flags.append({"market": code, "month": str(m), "check": "holding return"})
    return res, flags


def check_weights(sig: pd.DataFrame) -> dict:
    bad = 0
    for m in sig.index:
        s = sig.loc[m].dropna()
        w = B.rank_weights(s)
        if len(w) < 2:
            continue
        ok = abs(w.sum()) < 1e-12 and abs(w.abs().sum() - 2) < 1e-12
        order = s.sort_values().index
        ok &= bool((np.diff(w[order].values) > 0).all() or s.nunique() < len(s))
        bad += not ok
    return {"months": int(len(sig)), "weight_violations": int(bad)}


def check_alignment() -> dict:
    _, carry = B.load_aqr()
    import openpyxl  # noqa: F401  (read the raw dates)
    fp = pd.read_excel(CD.data_root().parent / "aqr" / B.AQR_COFP, sheet_name=0, header=None) \
        if not __import__("os").environ.get(B.AQR_DIR_ENV) else \
        pd.read_excel(__import__("pathlib").Path(__import__("os").environ[B.AQR_DIR_ENV]) / B.AQR_COFP,
                      sheet_name=0, header=None)
    hrow = fp.index[fp.iloc[:, 0].astype(str) == "Date"][0]
    dates = pd.to_datetime(fp.iloc[hrow + 1:, 0].dropna(), format="%m/%d/%Y", errors="coerce").dropna()
    month_end = bool((dates == dates + pd.offsets.BMonthEnd(0)).all())          # last business day of month
    consecutive = bool(dates.dt.to_period("M").is_unique
                       and (dates.dt.to_period("M").diff().dropna().apply(lambda x: x.n) == 1).all())
    # our month m: execution near the 3rd of m to the next execution; AQR row m: calendar month m (to its end)
    md = CD.MarketData("CL")
    r = md.rolls.loc["2000-01":"2026-02"]
    lag_ok = bool(((r["execution"].dt.to_period("M") == r.index) & (r["execution"].dt.day <= 7)).all())
    return {"aqr_dates_business_month_end": month_end, "aqr_months_consecutive": consecutive,
            "aqr_rows": int(len(dates)),
            "our_label_is_execution_month": lag_ok}


def run_a() -> dict:
    allres, allflags, sig = {}, [], {}
    for code in CD.COMMODITIES:
        print(f"[a] {code}", file=sys.stderr, flush=True)
        res, flags = check_a(code)
        allres[code] = res
        allflags += flags
    sig = pd.read_csv(CD.derived_dir() / "A4_carry_log_signal.csv", index_col=0)
    out = {"per_market": allres, "weights": check_weights(sig), "alignment": check_alignment(),
           "totals": {k: int(sum(v[k] for v in allres.values())) for k in next(iter(allres.values()))}}
    pd.DataFrame(allflags).to_csv(CD.derived_dir() / "A4diag_a_flags.csv", index=False)
    out["flags_summary"] = pd.DataFrame(allflags).groupby("check").size().to_dict() if allflags else {}
    out["outlier_list"] = [(f["market"], f["month"], f.get("d1"), f.get("d2_d1")) for f in allflags
                           if f["check"] == "|carry|>5"]
    out["unit_list"] = [(f["market"], f["month"], f.get("d2_d1")) for f in allflags
                        if f["check"] == "|ln F1/F2|>0.5"]
    return out


def main(argv=None):
    step = (argv or sys.argv[1:])[0]
    prev = json.loads(OUT.read_text()) if OUT.exists() else {}
    if step == "a":
        prev["a"] = run_a()
    elif step == "c":
        from .commod_a4aqr import run_c
        prev["c"] = run_c()
    OUT.write_text(json.dumps(prev, indent=1, default=str))
    print(json.dumps(prev[step], indent=1, default=str)[:4000])


if __name__ == "__main__":
    main()
