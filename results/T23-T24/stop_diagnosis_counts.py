"""Diagnose the T22 active-count mismatch: counts and dates only (no sleeve, return or statistic)."""
import json, numpy as np, pandas as pd
from em_macro import t2022 as T, t2324_window as WIN, commod_data as CD, commod_build0 as B0
WIN.apply()
av = json.load(open("results/T23-T24/availability.json"))
u22 = av["passing"]["T22"]
fx = pd.DataFrame(columns=["EUR", "GBP"])
rows = []
for c in u22:
    mk = T.Mkt(c, fx)
    if mk.entry is None or mk.entry > pd.Period("1981-12", "M"):
        continue
    s = mk.sigma_mop()
    sig = T.signal_t22(mk, s)
    r = mk.r1["r"]
    for m in pd.period_range("1979-03", "1980-06", freq="M"):
        if m not in mk.rolls.index:
            continue
        t = mk.rolls.at[m, "decision"]
        rows.append({"market": c, "month": str(m), "entry": str(mk.entry), "missing": bool(mk.rolls.at[m, "missing"]),
                     "entered": bool(m >= mk.entry), "sigma_ok": bool(np.isfinite(T.asof(s, t))),
                     "signal_ok": bool(np.isfinite(sig.get(m, np.nan))),
                     "n_r_nonnan_to_t": int(r.loc[:t].notna().sum()), "n_r_rows_to_t": int((r.index <= t).sum()),
                     "idx1_first": str(mk.idx1.index[0].date()), "t_minus_12m": str((t - pd.DateOffset(months=12)).date())})
df = pd.DataFrame(rows)
df["active_code"] = df.entered & ~df.missing & df.sigma_ok & df.signal_ok
df.to_csv("/tmp/claude-0/diag_active.csv", index=False)
print(df.groupby("month")["active_code"].sum().to_string())
