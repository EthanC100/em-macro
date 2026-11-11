"""D005: volatility floor for managed currencies, applied to v1.0's monthly book before it is booked.

    python -m em_macro.d005 update                    # monthly workflow step, after `em_macro.overlay update`
    python -m em_macro.d005 dry-run [--as-of 2026-10] # print v1.0 vs D005 weights for a month; writes nothing

Decision D005 supersedes D004 rule 4 (drop a held currency under a managed peg or crawl). Instead of dropping the
currency, its volatility estimate is floored:

1. v1.0 computes its month-end weights with the frozen code (em_macro/systematic.py, tag v1.0-frozen), imported
   read-only here. Nothing frozen is changed: not the code, not results/systematic/fit/, not the tags.
2. For each currency on the managed list (config/v1_managed_fx.csv) that v1.0 holds, its trailing volatility
   (v1.0's own estimate: 36-month annualised standard deviation of the monthly excess return) is floored at the
   median of that month's volatility estimates of v1.0's eight emerging-market currencies (BRL MXN ZAR TRY IDR PLN
   COP CLP; GBP and EUR are not emerging-market). The leg's inverse-volatility weight is recomputed with the
   floored volatility: weight x (own vol / floored vol). Every other factor of the weight is common to the book.
3. The whole book (FX and bonds) is rescaled to v1.0's 10% volatility target on v1.0's own measure (pro-forma
   standard deviation of the trailing 36 months of monthly returns, annualised), then held to v1.0's 6x gross
   leverage cap. If no floor binds, the book is v1.0's, unchanged.

Only the FX leg of a managed currency is floored; its country's bond is v1.0's (rescaled with the book).

The override is booked from the 3 December 2026 rebalance (positions as of 2026-11, effective 2026-12). Each run:

* results/systematic/d005/positions.csv: the current book, every v1.0 leg with v1.0's and D005's size;
* results/systematic/d005/weights.csv: the booked record, one row per (as_of, instrument), append-only (a re-run of
  the same month replaces that month); P&L is computed from it, so booked months never change;
* results/systematic/paper_pnl.csv: adds ``d005_adj`` (D005 book's net minus v1.0's, costs included) and
  ``net_before_d005`` (= model_net + override_pnl, the unadjusted line), and sets ``final_net`` = model_net +
  override_pnl + d005_adj, ``cumulative_final`` accordingly. ``net`` and ``model_net`` stay v1.0's, unadjusted.

v1.0's own files (positions.csv, rebalance_log.csv, overrides_log.csv, position_adjustments.csv) are not touched.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from . import systematic as SY
from .config import ROOT

DECISION_ID = "D005"
SUPERSEDES = "D004 rule 4"
FIRST_AS_OF = "2026-11"                 # first rebalance with D005: 3 Dec 2026, positions effective 2026-12
MANAGED_FILE = ROOT / "config/v1_managed_fx.csv"
MANAGED_COLUMNS = ["currency", "imf_classification", "source", "date", "evidence"]
# IMF de facto categories that count as managed (AREAER: soft pegs). A row with another classification is still
# applied (D005: a currency Ethan lists is floored even if the IMF does not class it as managed) and is labelled so.
IMF_MANAGED = ("crawl-like arrangement", "stabilized arrangement", "crawling peg", "conventional peg")
EM_FX = [k for k in SY.FX_INSTR if k not in ("GBP", "EUR")]
TARGET_VOL = SY.DESIGN["portfolio_target_vol"]
GROSS_CAP = SY.DESIGN["gross_leverage_cap"]
LOOKBACK = SY.DESIGN["vol_lookback_months"]
OUT = SY.OUT / "d005"
POSITIONS_FILE, WEIGHTS_FILE = OUT / "positions.csv", OUT / "weights.csv"
PAPER_PNL = SY.OUT / "paper_pnl.csv"
WEIGHT_COLUMNS = ["as_of", "instrument", "book", "v10_weight", "d005_weight"]
POSITION_COLUMNS = ["as_of", "effective_from", "book", "instrument", "side", "managed", "v10_size_pct_of_capital",
                    "d005_size_pct_of_capital", "change_pct_of_capital", "instrument_vol_pct", "vol_floor_pct",
                    "vol_used_pct", "floored", "book_scale"]


# ----------------------------------------------------------------------------- the managed list
def load_managed(path: Path = MANAGED_FILE) -> list[dict]:
    """Rows of config/v1_managed_fx.csv, validated. Raises ValueError listing every problem."""
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    problems, out, seen = [], [], set()
    for n, r in enumerate(rows, start=2):
        cur = (r.get("currency") or "").strip().upper()
        cls = (r.get("imf_classification") or "").strip()
        src, dt = (r.get("source") or "").strip(), (r.get("date") or "").strip()
        if cur not in SY.FX_INSTR:
            problems.append(f"line {n}: currency '{cur}' is not one of v1.0's currencies {list(SY.FX_INSTR)}")
        if cur in seen:
            problems.append(f"line {n}: {cur} is listed twice")
        if not cls or not src:
            problems.append(f"line {n}: imf_classification and source are required")
        try:
            date.fromisoformat(dt)
        except ValueError:
            problems.append(f"line {n}: date '{dt}' is not YYYY-MM-DD")
        seen.add(cur)
        out.append({"currency": cur, "imf_classification": cls, "source": src, "date": dt,
                    "evidence": (r.get("evidence") or "").strip(), "imf_managed": cls.lower() in IMF_MANAGED})
    if problems:
        raise ValueError(f"{path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}: " + "; ".join(problems))
    return out


# ----------------------------------------------------------------------------- the override (pure)
def vol_floor(vol: pd.Series) -> float:
    """Median of the month's volatility estimates of v1.0's emerging-market currencies."""
    v = vol.reindex(EM_FX).dropna()
    if v.empty:
        raise ValueError("no emerging-market volatility estimate this month")
    return float(v.median())


def pro_forma_vol(w: pd.Series, hist: pd.DataFrame) -> float:
    """v1.0's measure: std of the trailing monthly returns of the weights held fixed, annualised."""
    h = hist.reindex(columns=w.index).fillna(0.0)
    return float((h @ w.fillna(0.0)).std() * np.sqrt(12))


def adjust(w: pd.Series, vol: pd.Series, hist: pd.DataFrame, managed: list[str],
           target: float = TARGET_VOL, cap: float = GROSS_CAP) -> pd.DataFrame:
    """D005 weights for one month-end.

    w: v1.0's weights (fraction of capital) for every instrument; vol: v1.0's volatility estimates (the floor is
    the median over its emerging-market currencies; only managed currencies are floored); hist: the trailing monthly returns (rows) of every instrument, v1.0's 36-month window.
    Returns one row per instrument: v10_weight, d005_weight, vol, vol_used, floored, managed, plus attrs
    ``floor``, ``scale``, ``pro_forma_vol_before`` and ``pro_forma_vol_after``.
    """
    w = w.astype(float)
    floor = vol_floor(vol)
    managed = [m.upper() for m in managed if m.upper() in SY.FX_INSTR]
    vol = vol.reindex(w.index)
    vol_used = vol.copy()
    w1 = w.copy()
    floored = pd.Series(False, index=w.index)
    for k in managed:
        if k in w.index and abs(w[k]) > 0 and pd.notna(vol.get(k)) and vol[k] < floor:
            w1[k] = w[k] * vol[k] / floor            # inverse-vol weight with the floored volatility
            vol_used[k] = floor
            floored[k] = True
    scale = 1.0
    pv_before = pro_forma_vol(w, hist)
    if floored.any():
        pv = pro_forma_vol(w1, hist)
        scale = target / pv if pv > 0 else 1.0
        gross = (w1 * scale).abs().sum()
        if gross > cap:
            scale *= cap / gross
    w2 = w1 * scale
    out = pd.DataFrame({"v10_weight": w, "d005_weight": w2, "vol": vol, "vol_used": vol_used, "floored": floored,
                        "managed": w.index.isin(managed)})
    out.attrs.update({"floor": floor, "scale": float(scale), "pro_forma_vol_before": pv_before,
                      "pro_forma_vol_after": pro_forma_vol(w2, hist)})
    return out


# ----------------------------------------------------------------------------- v1.0 (frozen, read-only)
def v10_state() -> dict:
    """v1.0's inputs, weights and volatility estimates from the frozen code (read-only)."""
    SY._check_frozen(strict=False)
    inp = SY.build_inputs()
    res = SY.run(inp, SY.VARIANTS["combined"])
    allR = pd.concat([inp["fx"]["ret"], inp["bond"]["ret"]], axis=1)
    vol = pd.concat([SY._vol(inp["fx"]["ret"]), SY._vol(inp["bond"]["ret"])], axis=1)
    return {"inp": inp, "W": res.attrs["weights"][allR.columns], "allR": allR, "vol": vol,
            "books": {**{k: "fx" for k in inp["fx"]["ret"].columns}, **{k: "bond" for k in inp["bond"]["ret"].columns}}}


def month_adjustment(st: dict, as_of: str, managed: list[str]) -> pd.DataFrame:
    t = pd.Period(as_of, "M")
    hist = st["allR"].loc[:t].iloc[-LOOKBACK:]
    adj = adjust(st["W"].loc[t], st["vol"].loc[t], hist, managed)
    adj["book"] = [st["books"][k] for k in adj.index]
    return adj


def positions_table(adj: pd.DataFrame, as_of: str) -> pd.DataFrame:
    held = adj[(adj["v10_weight"].abs() > 1e-9) | (adj["d005_weight"].abs() > 1e-9)]
    t = pd.Period(as_of, "M")
    rows = []
    for k, r in held.iterrows():
        rows.append({"as_of": as_of, "effective_from": str(t + 1), "book": r["book"], "instrument": k,
                     "side": "long" if r["d005_weight"] > 0 else "short", "managed": bool(r["managed"]),
                     "v10_size_pct_of_capital": round(100 * r["v10_weight"], 3),
                     "d005_size_pct_of_capital": round(100 * r["d005_weight"], 3),
                     "change_pct_of_capital": round(100 * (r["d005_weight"] - r["v10_weight"]), 3),
                     "instrument_vol_pct": round(100 * r["vol"], 3) if pd.notna(r["vol"]) else None,
                     "vol_floor_pct": round(100 * adj.attrs["floor"], 3),
                     "vol_used_pct": round(100 * r["vol_used"], 3) if pd.notna(r["vol_used"]) else None,
                     "floored": bool(r["floored"]), "book_scale": round(adj.attrs["scale"], 6)})
    df = pd.DataFrame(rows, columns=POSITION_COLUMNS)
    return df.sort_values(["book", "side", "d005_size_pct_of_capital"], ascending=[True, True, False])


# ----------------------------------------------------------------------------- P&L
def pnl_adjustment(log: pd.DataFrame, st: dict) -> pd.Series:
    """Monthly net P&L of the booked D005 book minus v1.0's (costs included), by month earned.

    Timing and costs as v1.0 (em_macro.systematic.run): FX weights decided at t earn t+1, bond weights t+2; the
    trade into a month's weights is charged when they start earning, at v1.0's cost per unit of notional. Months
    without a booked D005 row hold v1.0's weights, so the trade out of D005 is charged too."""
    inp, W = st["inp"], st["W"]
    months = inp["months"]
    if log.empty:
        return pd.Series(0.0, index=months)
    v10 = W.copy()
    d = W.copy()
    for r in log.itertuples():
        t = pd.Period(r.as_of, "M")
        if t in v10.index and r.instrument in v10.columns:
            v10.at[t, r.instrument] = float(r.v10_weight)
            d.at[t, r.instrument] = float(r.d005_weight)
    lag = {"fx": 1, "bond": 1 + SY.DESIGN["bond_execution_lag_months"]}
    cost = pd.Series(inp["cost"])
    out = pd.Series(0.0, index=months)
    for b in ("fx", "bond"):
        cols = list(inp[b]["ret"].columns)
        dw = (d[cols] - v10[cols]).shift(lag[b])
        gross = (dw * inp[b]["ret"][cols]).sum(axis=1, min_count=1).fillna(0.0)
        tc = ((d[cols].diff().abs() - v10[cols].diff().abs()).shift(lag[b]) * cost[cols]).sum(axis=1).fillna(0.0)
        out = out.add(gross - tc, fill_value=0.0)
    return out.reindex(months).fillna(0.0)


def book_paper_pnl(adj_month: pd.Series, path: Path = PAPER_PNL) -> pd.DataFrame:
    """Add d005_adj / net_before_d005 to paper_pnl.csv and set final_net and cumulative_final. Idempotent: the
    unadjusted line is rebuilt from model_net + override_pnl (em_macro.overlay's final_net) on every run."""
    pnl = pd.read_csv(path)
    m = pd.PeriodIndex(pnl["month"], freq="M")
    model = pnl["model_net"] if "model_net" in pnl else pnl["net"]
    ovr = pnl["override_pnl"] if "override_pnl" in pnl else 0.0
    pnl["net_before_d005"] = model + ovr
    pnl["d005_adj"] = adj_month.reindex(m).fillna(0.0).values
    pnl["final_net"] = pnl["net_before_d005"] + pnl["d005_adj"]
    pnl["cumulative_final"] = (1 + pnl["final_net"]).cumprod()
    _atomic_csv(pnl, path, float_format="%.6f")
    return pnl


def _atomic_csv(df: pd.DataFrame, path: Path, **kw) -> None:
    """Write to a temporary file, then rename: a failure never leaves a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    df.to_csv(tmp, index=False, **kw)
    tmp.replace(path)


def read_log(path: Path = WEIGHTS_FILE) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=WEIGHT_COLUMNS)
    return pd.read_csv(path, dtype={"as_of": str, "instrument": str, "book": str})


def merge_log(log: pd.DataFrame, adj: pd.DataFrame, as_of: str) -> pd.DataFrame:
    """The booked record with ``as_of`` replaced by this adjustment (pure)."""
    held = adj[(adj["v10_weight"].abs() > 1e-12) | (adj["d005_weight"].abs() > 1e-12)]
    new = pd.DataFrame({"as_of": as_of, "instrument": held.index, "book": held["book"].values,
                        "v10_weight": held["v10_weight"].values, "d005_weight": held["d005_weight"].values})
    return (pd.concat([log[log["as_of"] != as_of], new], ignore_index=True)
            .sort_values(["as_of", "book", "instrument"]).reindex(columns=WEIGHT_COLUMNS))


def write_log(log: pd.DataFrame, adj: pd.DataFrame, as_of: str, path: Path = WEIGHTS_FILE) -> pd.DataFrame:
    log = merge_log(log, adj, as_of)
    _atomic_csv(log, path, float_format="%.8f")
    return log


# ----------------------------------------------------------------------------- stages
def _v10_as_of(path: Path) -> str | None:
    try:
        return str(pd.read_csv(path, dtype=str)["as_of"].iloc[0])
    except Exception:  # noqa: BLE001 - the as_of is only needed to drop this month's D005 rows
        return None


def stage_update(state_fn=None, out: Path = OUT, paper_pnl: Path = PAPER_PNL, managed_file: Path = MANAGED_FILE,
                 v10_positions: Path = SY.OUT / "positions.csv", git_root: Path = ROOT, now=None) -> int:
    """The monthly step. Fail-safe: everything is computed before anything is written. Any error books the current
    month as v1.0 unadjusted (no D005 row for it), keeps the D005 P&L of months already booked (recomputed from the
    booked record, else carried forward from the committed paper_pnl.csv), writes status.json and returns 1, so the
    workflow raises its alert while v1.0 still rebalances and is committed. v1.0's own files are never written."""
    from . import d005_fallback as FB
    now = now or pd.Timestamp.now(tz="UTC").floor("s").to_pydatetime()
    errors: list[str] = []
    positions_file, weights_file, status_file = out / "positions.csv", out / "weights.csv", out / "status.json"
    st = None
    try:
        st = (state_fn or v10_state)()
    except Exception as e:  # noqa: BLE001 - fail safe: log and book unadjusted
        errors.append(f"v1.0 state: {type(e).__name__}: {e}")
    as_of = str(st["inp"]["months"][-1]) if st else _v10_as_of(v10_positions)
    log = read_log(weights_file)
    table, adj = None, None
    if as_of and as_of >= FIRST_AS_OF:
        try:
            if st is None:
                raise RuntimeError("no v1.0 state")
            managed = [r["currency"] for r in load_managed(managed_file)]
            adj = month_adjustment(st, as_of, managed)
            table = positions_table(adj, as_of)
            log = merge_log(log, adj, as_of)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{as_of} adjustment: {type(e).__name__}: {e}")
            table, adj = None, None
            log = log[log["as_of"] != as_of]                       # this month books v1.0 unadjusted
    pnl_source = "recomputed from the booked record (weights.csv)"
    try:
        if st is None:
            raise RuntimeError("no v1.0 state")
        adj_month = pnl_adjustment(log, st)
    except Exception as e:  # noqa: BLE001
        errors.append(f"D005 P&L: {type(e).__name__}: {e}")
        carried = FB.committed_d005_adj(git_root)
        adj_month = pd.Series({pd.Period(m, "M"): v for m, v in carried.items()}, dtype=float)
        pnl_source = "carried forward from the committed paper_pnl.csv (HEAD)"
    # ---- writes (atomic per file)
    if table is not None:
        _atomic_csv(table, positions_file)
    elif positions_file.exists():
        cur = pd.read_csv(positions_file, dtype=str)
        if (cur.get("as_of") == as_of).any():                     # never show a D005 book for an unadjusted month
            _atomic_csv(cur[cur["as_of"] != as_of], positions_file)
    if len(log) or weights_file.exists():
        _atomic_csv(log.reindex(columns=WEIGHT_COLUMNS), weights_file, float_format="%.8f")
    pnl = book_paper_pnl(adj_month, paper_pnl)
    status = {"decision": DECISION_ID, "as_of": as_of, "status": "failed" if errors else "ok",
              "applied": table is not None, "errors": errors, "pnl_source": pnl_source,
              "booked": ("D005 book" if table is not None else
                         "v1.0 unadjusted for this month (fail-safe)" if errors else
                         f"v1.0 unchanged (before the first D005 rebalance, {FIRST_AS_OF})"),
              "evaluated_at": now.isoformat().replace("+00:00", "Z")}
    if adj is not None:
        status.update({"floor_pct": round(100 * adj.attrs["floor"], 4), "book_scale": round(adj.attrs["scale"], 6),
                       "floored": list(adj.index[adj["floored"]])})
    if as_of and (as_of >= FIRST_AS_OF or errors):
        status_file.parent.mkdir(parents=True, exist_ok=True)
        status_file.write_text(json.dumps(status, indent=1) + "\n", encoding="utf-8")
    live = pnl[pnl["sample"].astype(str).str.startswith("live")] if "sample" in pnl else pnl.iloc[0:0]
    print(f"D005 {as_of}: {status['booked']}"
          + (f"; floor {status['floor_pct']:.2f}%, floored {', '.join(status['floored']) or 'none'}, "
             f"book scale {status['book_scale']:.4f}" if adj is not None else ""))
    print(f"D005 P&L vs unadjusted v1.0 over {len(live)} live month(s): {live['d005_adj'].sum():+.4%} ({pnl_source})")
    for e in errors:
        print(f"D005 ERROR: {e}", file=sys.stderr)
    return 1 if errors else 0


def dry_run(as_of: str | None = None, managed: list[str] | None = None) -> pd.DataFrame:
    st = v10_state()
    as_of = as_of or str(st["inp"]["months"][-1])
    managed = managed if managed is not None else [r["currency"] for r in load_managed()]
    adj = month_adjustment(st, as_of, managed)
    tab = positions_table(adj, as_of)
    print(f"D005 dry run, positions as of {as_of} (effective {pd.Period(as_of, 'M') + 1}); nothing written.")
    print(f"managed list: {', '.join(managed) or 'empty'}; floor = median EM FX vol {100 * adj.attrs['floor']:.2f}%; "
          f"book scale {adj.attrs['scale']:.4f}; pro-forma vol {100 * adj.attrs['pro_forma_vol_before']:.2f}% -> "
          f"{100 * adj.attrs['pro_forma_vol_after']:.2f}%; gross {adj['v10_weight'].abs().sum():.3f}x -> "
          f"{adj['d005_weight'].abs().sum():.3f}x")
    print(tab[["book", "instrument", "side", "managed", "instrument_vol_pct", "vol_used_pct",
               "v10_size_pct_of_capital", "d005_size_pct_of_capital", "change_pct_of_capital"]].to_string(index=False))
    return tab


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m em_macro.d005", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("update")
    d = sub.add_parser("dry-run")
    d.add_argument("--as-of", default=None, help="month of the positions (YYYY-MM); default the latest")
    a = ap.parse_args(argv)
    if a.cmd == "update":
        return stage_update()
    else:
        dry_run(a.as_of)
    return 0


if __name__ == "__main__":
    sys.exit(main())
