"""Trial T01 runner: pre-registered comparison of T01 (time-series trend sleeve) with frozen v1.0.

    python -m em_macro.t01 run        # -> results/T01/*.csv, results/T01/RUN.json
    python -m em_macro.t01 report     # -> results/T01_ts_trend.md from the saved tables

Pre-registration: docs/prereg/T01_ts_trend.md.  v1.0 numbers come from the frozen
em_macro/systematic.py (tag v1.0-frozen, commit 7886867), which is imported, never modified.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import holdout as HO
from . import mtstats as MT
from . import systematic as SY
from . import tstrend as TS
from .config import RESULTS, ROOT

OUT = RESULTS / "T01"
REPORT = RESULTS / "T01_ts_trend.md"
SEED = 20261103
TEST = (pd.Period("2020-01", "M"), pd.Period("2026-09", "M"))
INSAMPLE = (None, pd.Period("2019-12", "M"))
PERIODS = {"2020-01..2026-09 (test)": TEST, "2005-2019 (in-sample, context)": INSAMPLE}
N_SPEC_V1, N_LEDGER_V1 = 7, 10
V1 = ["carry", "trend", "value"]
LAG = {"fx": 1, "bond": 1 + SY.DESIGN["bond_execution_lag_months"]}


# ============================================================ statistics
def expected_shortfall(r: pd.Series, alpha: float = 0.025) -> float:
    """Historical ES (Acerbi-Tasche) of returns, as a positive loss."""
    x = np.sort(np.asarray(r.dropna(), dtype=float))
    m = alpha * len(x)
    k = int(np.floor(m))
    tail = x[:k].sum() + (m - k) * (x[k] if k < len(x) else 0.0)
    return float(-tail / m)


def max_drawdown(r: pd.Series) -> float:
    w = (1 + r.dropna()).cumprod()
    return float((w / w.cummax() - 1).min())


def sharpe(r) -> float:
    r = np.asarray(r, dtype=float)
    s = r.std(ddof=1)
    return float(r.mean() / s * np.sqrt(12)) if s > 0 else np.nan


def turnover(res: pd.DataFrame) -> pd.Series:
    """One-way notional traded per month (sum |dW|), dated like the costs (month the trade starts earning)."""
    W = res.attrs["weights"]
    fx = [c for c in W.columns if c in SY.FX_INSTR]
    bond = [c for c in W.columns if c not in SY.FX_INSTR]
    out = 0.0
    for cols, lag in ((fx, LAG["fx"]), (bond, LAG["bond"])):
        out = out + W[cols].diff().abs().sum(axis=1).shift(lag).fillna(0.0)
    return out.reindex(res.index)


def metrics(res: pd.DataFrame, period) -> dict:
    a, b = period
    r = res["net"].loc[a:b]
    yrs = len(r) / 12
    w = (1 + r).cumprod()
    return {"start": str(r.index[0]), "end": str(r.index[-1]), "months": len(r),
            "ann_return_%": 100 * (w.iloc[-1] ** (1 / yrs) - 1), "ann_vol_%": 100 * r.std() * np.sqrt(12),
            "sharpe": sharpe(r), "max_drawdown_%": 100 * max_drawdown(r), "ES97.5_monthly_%": 100 * expected_shortfall(r),
            "skew": float(r.skew()), "kurtosis_raw": float(r.kurt() + 3),
            "turnover_x_pa": float(turnover(res).loc[a:b].mean() * 12),
            "cost_drag_%_pa": 100 * res["cost"].loc[a:b].mean() * 12,
            "avg_gross_leverage": float(res["gross_leverage"].loc[a:b].mean())}


def circular_block_indices(T: int, L: int, rng) -> np.ndarray:
    nb = int(np.ceil(T / L))
    starts = rng.integers(0, T, nb)
    return (starts[:, None] + np.arange(L)[None, :]).ravel()[:T] % T


def bootstrap_delta_sharpe(a: pd.Series, b: pd.Series, B: int = 10_000, L: int = 6, seed: int = SEED) -> dict:
    """Paired circular block bootstrap of SR(a) - SR(b); one-sided p for H1: delta > 0, from the
    bootstrap distribution centred on the null (delta* - delta_hat >= delta_hat)."""
    x = np.column_stack([np.asarray(a, float), np.asarray(b, float)])
    T = len(x)
    d_hat = sharpe(x[:, 0]) - sharpe(x[:, 1])
    rng = np.random.default_rng(seed)
    d = np.empty(B)
    for i in range(B):
        s = x[circular_block_indices(T, L, rng)]
        d[i] = sharpe(s[:, 0]) - sharpe(s[:, 1])
    p = (1 + np.sum(d - d_hat >= d_hat)) / (B + 1)
    return {"delta_sr": d_hat, "p_one_sided": float(p), "boot_mean": float(d.mean()), "boot_sd": float(d.std(ddof=1)),
            "boot_q05": float(np.quantile(d, 0.05)), "boot_q95": float(np.quantile(d, 0.95)), "B": B, "block": L,
            "seed": seed}


def dsr_row(r: pd.Series, N: int) -> dict:
    T = len(r)
    sr_m = float(r.mean() / r.std())
    g3, g4 = float(r.skew()), float(r.kurt() + 3)
    sd_noise, sd_disp = 1 / np.sqrt(T - 1), 0.20 / np.sqrt(12)
    return {"N": N, "T": T, "SR_ann": sr_m * np.sqrt(12), "skew": g3, "kurtosis_raw": g4,
            "PSR(SR*=0)": MT.psr(sr_m, T, g3, g4),
            "SR0_noise_ann": MT.sr0(N, sd_noise) * np.sqrt(12), "DSR_noise": MT.dsr(sr_m, T, N, sd_noise, g3, g4),
            "SR0_dispersed_ann": MT.sr0(N, sd_disp) * np.sqrt(12), "DSR_dispersed": MT.dsr(sr_m, T, N, sd_disp, g3, g4)}


def annual(r: pd.Series) -> pd.Series:
    return r.groupby(r.index.year).apply(lambda x: (1 + x).prod() - 1)


def _sha(path) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def _git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    except OSError:
        return ""


# ============================================================ run
def reproduce_v1(inp: dict) -> dict:
    """Frozen v1.0 evaluate() on these inputs vs the committed result tables."""
    out = {}
    for name, per, path in (("test", slice(SY.TEST_START, TEST[1]), "results/systematic/test/performance_2020_on.csv"),
                            ("fit", slice(None, SY.FIT_END), "results/systematic/fit/performance_2005_2019.csv")):
        tab = SY.evaluate(inp, per)
        ref = pd.read_csv(ROOT / path)
        num = [c for c in ref.columns if ref[c].dtype.kind == "f"]
        diff = np.abs(tab[num].astype(float).round(4).values - ref[num].values)
        out[name] = {"file": path, "rows": len(ref), "max_abs_diff_at_4dp": float(np.nanmax(diff)),
                     "exact": bool(np.nanmax(diff) == 0.0)}
    return out


def stage_run():
    OUT.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    inp1 = SY.build_inputs()
    repro = reproduce_v1(inp1)
    print("v1.0 reproduction:", repro)
    halfB, halfA = HO.instruments("B"), HO.instruments("A")

    runs = {}            # (universe, costs, strategy) -> result frame
    for cm in (1.0, 2.0):
        inp_c = TS.with_costs(inp1, cm) if cm != 1.0 else inp1
        for uni, ins in (("all", None), ("half B", halfB), ("half A", halfA)):
            x = inp_c if ins is None else TS.subset(inp_c, ins)
            t = TS.run_t01(x)
            runs[(uni, cm, "v1.0")] = SY.run(x, V1)
            runs[(uni, cm, "T01")] = t["T01"]
            runs[(uni, cm, "trend sleeve (T01)")] = t["trend sleeve"]
            runs[(uni, cm, "core sleeve alone (diagnostic)")] = t["core sleeve"]
            runs[(uni, cm, "carry sleeve (v1.0 carry only)")] = SY.run(x, ["carry"])
            # the frozen v1.0 machinery with carry+value must equal the T01 core sleeve
            assert (SY.run(x, ["carry", "value"])["net"] - t["core sleeve"]["net"]).abs().max() < 1e-12
            print("done", uni, cm)

    # ---- performance table
    rows = []
    for (uni, cm, strat), res in runs.items():
        for pname, per in PERIODS.items():
            rows.append({"universe": uni, "costs": f"{cm:g}x", "strategy": strat, "period": pname, **metrics(res, per)})
    perf = pd.DataFrame(rows)
    perf.to_csv(OUT / "performance.csv", index=False, float_format="%.4f")

    # ---- monthly net returns
    mon = pd.DataFrame({f"{uni}|{cm:g}x|{s}": r["net"] for (uni, cm, s), r in runs.items()})
    mon.index.name = "month"
    mon.reset_index().assign(month=lambda d: d["month"].astype(str)).to_csv(OUT / "monthly_net.csv", index=False,
                                                                           float_format="%.6f")

    # ---- annual returns, test period
    ann = []
    for cm in (1.0, 2.0):
        for s in ("v1.0", "T01", "trend sleeve (T01)", "core sleeve alone (diagnostic)"):
            a = annual(runs[("all", cm, s)]["net"].loc[TEST[0]:TEST[1]])
            for y, v in a.items():
                ann.append({"costs": f"{cm:g}x", "strategy": s, "year": int(y), "return_%": 100 * v})
    pd.DataFrame(ann).to_csv(OUT / "annual_2020_2026.csv", index=False, float_format="%.4f")

    # ---- criteria
    crit = {}
    for cm in (1.0, 2.0):
        tag = f"{cm:g}x"
        v1 = runs[("all", cm, "v1.0")]["net"].loc[TEST[0]:TEST[1]]
        t1 = runs[("all", cm, "T01")]["net"].loc[TEST[0]:TEST[1]]
        assert len(v1) == len(t1) == 81 and (v1.index == t1.index).all()
        bs = bootstrap_delta_sharpe(t1, v1)
        vB = runs[("half B", cm, "v1.0")]["net"].loc[TEST[0]:TEST[1]]
        tB = runs[("half B", cm, "T01")]["net"].loc[TEST[0]:TEST[1]]
        carry = runs[("all", cm, "carry sleeve (v1.0 carry only)")]["net"]
        trend = runs[("all", cm, "trend sleeve (T01)")]["net"]
        cw = {}
        for pname, (a, b) in {**PERIODS, "2006-2026 (all months)": (None, TEST[1])}.items():
            c, tr = carry.loc[a:b], trend.reindex(carry.loc[a:b].index)
            ok = tr.notna()
            c, tr = c[ok], tr[ok]
            n = int(round(0.10 * len(c)))
            worst = c.nsmallest(n).index
            cw[pname] = {"months": len(c), "n_worst": n, "corr_all": float(tr.corr(c)),
                         "corr_worst10": float(tr.loc[worst].corr(c.loc[worst])),
                         "trend_mean_in_worst_%": 100 * float(tr.loc[worst].mean()),
                         "carry_mean_in_worst_%": 100 * float(c.loc[worst].mean()),
                         "worst_months": " ".join(str(m) for m in sorted(worst))}
        d_v1 = {"spec": dsr_row(v1, N_SPEC_V1), "ledger": dsr_row(v1, N_LEDGER_V1)}
        d_t1 = {"spec": dsr_row(t1, N_SPEC_V1 + 1), "ledger": dsr_row(t1, N_LEDGER_V1 + 1)}
        es_v, es_t = expected_shortfall(v1), expected_shortfall(t1)
        dd_v, dd_t = max_drawdown(v1), max_drawdown(t1)
        c = [
            {"#": 1, "criterion": "2020-01..2026-09: dSR > 0 and block-bootstrap one-sided p < 0.10",
             "T01": f"SR {sharpe(t1):.3f}", "v1.0": f"SR {sharpe(v1):.3f}",
             "statistic": f"dSR {bs['delta_sr']:+.3f}, p = {bs['p_one_sided']:.4f}",
             "pass": bool(bs["delta_sr"] > 0 and bs["p_one_sided"] < 0.10)},
            {"#": 2, "criterion": "holdout half B, 2020-01..2026-09: dSR > 0 and |MaxDD| not worse",
             "T01": f"SR {sharpe(tB):.3f}, MaxDD {100 * max_drawdown(tB):.2f}%",
             "v1.0": f"SR {sharpe(vB):.3f}, MaxDD {100 * max_drawdown(vB):.2f}%",
             "statistic": f"dSR {sharpe(tB) - sharpe(vB):+.3f}; |DD| ratio {max_drawdown(tB) / max_drawdown(vB):.3f}",
             "pass": bool(sharpe(tB) > sharpe(vB) and abs(max_drawdown(tB)) <= abs(max_drawdown(vB)))},
            {"#": 3, "criterion": "2020-01..2026-09: |MaxDD| and ES97.5 each <= 1.10 x v1.0",
             "T01": f"MaxDD {100 * dd_t:.2f}%, ES {100 * es_t:.2f}%",
             "v1.0": f"MaxDD {100 * dd_v:.2f}%, ES {100 * es_v:.2f}%",
             "statistic": f"DD ratio {dd_t / dd_v:.3f}; ES ratio {es_t / es_v:.3f}",
             "pass": bool(abs(dd_t) <= 1.10 * abs(dd_v) and es_t <= 1.10 * es_v)},
            {"#": 4, "criterion": "DSR (noise-only null) of T01 at N = 8 >= DSR of v1.0 at N = 7",
             "T01": f"DSR {d_t1['spec']['DSR_noise']:.3f} (N 8)", "v1.0": f"DSR {d_v1['spec']['DSR_noise']:.3f} (N 7)",
             "statistic": f"difference {d_t1['spec']['DSR_noise'] - d_v1['spec']['DSR_noise']:+.3f}",
             "pass": bool(d_t1["spec"]["DSR_noise"] >= d_v1["spec"]["DSR_noise"])},
            {"#": 5, "criterion": "corr(trend sleeve, carry sleeve) < 0 in carry's worst 10% of months, 2020-01..2026-09",
             "T01": f"corr {cw['2020-01..2026-09 (test)']['corr_worst10']:+.3f} "
                    f"(n {cw['2020-01..2026-09 (test)']['n_worst']})", "v1.0": "n/a",
             "statistic": f"worst months: {cw['2020-01..2026-09 (test)']['worst_months']}",
             "pass": bool(cw["2020-01..2026-09 (test)"]["corr_worst10"] < 0)},
        ]
        crit[tag] = {"criteria": c, "overall_pass": all(x["pass"] for x in c), "bootstrap": bs,
                     "dsr": {"v1.0": d_v1, "T01": d_t1}, "carry_worst": cw}
        pd.DataFrame(c).to_csv(OUT / f"pass_fail_{tag}.csv", index=False)
    (OUT / "criteria.json").write_text(json.dumps(crit, indent=1, default=float))

    files = ["em_macro/systematic.py", "results/systematic/fit/frozen_design.json", "em_macro/tstrend.py",
             "em_macro/t01.py", "em_macro/holdout.py", "docs/prereg/T01_ts_trend.md",
             "data/processed/daily_panel.csv", "data/processed/country_month_panel.csv",
             "data/processed/risk_model_input.csv"]
    (OUT / "RUN.json").write_text(json.dumps({
        "run_started_utc": started, "run_finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_head_at_run": _git_head(), "pandas": pd.__version__, "numpy": np.__version__,
        "last_month": str(inp1["months"][-1]), "v1_reproduction": repro, "decision_costs": "1x",
        "overall_pass_1x": crit["1x"]["overall_pass"], "sha256": {f: _sha(f) for f in files}}, indent=1))
    print(pd.DataFrame(crit["1x"]["criteria"]).to_string())
    print("OVERALL (1x):", "PASS" if crit["1x"]["overall_pass"] else "FAIL")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "run":
        stage_run()
    elif cmd == "report":
        from . import t01_report
        t01_report.write()
    else:
        sys.exit(__doc__)
