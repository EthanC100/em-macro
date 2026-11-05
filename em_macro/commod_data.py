"""Commodity futures data layer for trials T20-T22 (Build 0; docs/prereg/T20-T22_commodity_trials.md).

Reads the private Norgate per-contract CSVs (EthanC100/em-macro-data, norgate/<snapshot>/contracts/) and builds,
per market:

* a contract table: every contract in the designated calendar (pre-registration §2.1) with its first and last
  settlement, last trade date (LTD), first notice date (FND) and notice(T) = min(FND, LTD);
* the monthly rebalance schedule (§2.3): execution date = the market's first settlement on or after the 3rd,
  decision date t = its last settlement before the execution date;
* the roll rule with the 35-day buffer: F1 = the earliest designated contract with notice(T) > execution + 35
  calendar days, F2 = the next designated contract, F13 = the designated contract whose LTD is closest to
  LTD(F1) + 365 days within +/-45 days (ties -> the later one);
* the chained same-contract excess-return index of the F1 (and F2) series (§2.3), no back-adjustment.

This module holds code only.  No vendor data, price, return or roll series is written to this repository: the
data directory is outside it (``EM_MACRO_DATA`` or ``../em-macro-data``) and every derived table goes to
``<data repo>/norgate/derived/`` (licence: Norgate Personal Use; see docs/infra/norgate_pipeline.md).

Last trade dates.  The Norgate export has no FND/LTD fields.  For an expired contract Norgate's
``last_quoted_date`` is its final bar (docs/infra/norgate_pipeline.md), so LTD = the contract's last settlement in
the primary source, except (i) a cash-settled contract whose final bar is a final-settlement row after a missing
market day (lean hogs: LTD = the bar before) and (ii) a contract whose quotes stop more than 30 days before its
scheduled LTD (stray or delisted far months: LTD = the exchange rule, flagged).  For a live contract (last bar on
the snapshot's latest date) LTD comes from the exchange rule below.  First notice dates come from the exchange rules (commodities spec Appendix B: "fnd, ltd: exchange
calendars"), on the market's own trading calendar (the union of its settlement dates; weekdays without US federal
holidays and Good Friday after the last observed date).
"""
from __future__ import annotations

import datetime as dt
import os
import re
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

import numpy as np
import pandas as pd

from .config import ROOT

MONTH_CODES = "FGHJKMNQUVXZ"
SNAPSHOT = "2026-11_futures"
BUFFER_DAYS = 35
F13_TARGET_DAYS = 365
F13_WINDOW_DAYS = 45
ASSEMBLY_START = pd.Timestamp("1990-01-01")   # A1: 1990-01 (or first listing) to 2026-10
ASSEMBLY_END_MONTH = pd.Period("2026-10", "M")
COVERAGE_START = pd.Period("2000-01", "M")      # §2.1 rule 1
COVERAGE_END = pd.Period("2026-09", "M")
DESIGN_START = pd.Period("2000-01", "M")        # §2.7 design sample (A7)
DESIGN_END = pd.Period("2019-12", "M")


def data_root() -> Path:
    """Root of the private data repo clone (never inside this repository)."""
    p = Path(os.environ.get("EM_MACRO_DATA", ROOT.parent / "em-macro-data"))
    return p


def snapshot_dir(snapshot: str = SNAPSHOT) -> Path:
    return data_root() / "norgate" / snapshot


def derived_dir() -> Path:
    return data_root() / "norgate" / "derived" / "build0"


# ----------------------------------------------------------------------------------------------- market table
@dataclass(frozen=True)
class Market:
    code: str
    name: str
    norgate: str | None          # Norgate session symbol; None = not in Norgate's futures list
    exchange: str
    sector: str
    months: str                  # designated contract months (roll calendar), pre-registration §2.1
    unit: str
    tick: float                  # minimum tick in price units
    tick_value: float            # per contract, contract currency
    slip_ticks: int
    settlement: str              # "physical" or "cash"
    ltd_rule: str                # key into LTD_RULES (used for live contracts)
    fnd_rule: str | None         # key into FND_RULES; None -> notice = LTD
    cme_group: bool              # CME, CBOT, NYMEX, COMEX (Databento GLBX.MDP3 cross-check, A5)
    half: str                    # holdout half (§2.7)
    kind: str = "commodity"      # or "financial"


C, F = "commodity", "financial"
MARKETS: dict[str, Market] = {m.code: m for m in [
    Market("CL", "WTI crude", "CL", "NYMEX", "energy", MONTH_CODES, "1,000 bbl", 0.01, 10, 1, "physical", "CL", None, True, "B"),
    Market("B", "Brent crude", "BRN", "ICE Europe", "energy", MONTH_CODES, "1,000 bbl", 0.01, 10, 1, "cash", "BRN", None, False, "A"),
    Market("RB", "RBOB gasoline", "RB", "NYMEX", "energy", MONTH_CODES, "42,000 gal", 0.0001, 4.2, 1, "physical", "LBD_PREV", None, True, "B"),
    Market("HO", "Heating oil / ULSD", "HO", "NYMEX", "energy", MONTH_CODES, "42,000 gal", 0.0001, 4.2, 1, "physical", "LBD_PREV", None, True, "B"),
    Market("NG", "Natural gas", "NG", "NYMEX", "energy", MONTH_CODES, "10,000 MMBtu", 0.001, 10, 1, "physical", "NG", None, True, "A"),
    Market("G", "Gasoil", "GAS", "ICE Europe", "energy", MONTH_CODES, "100 t", 0.25, 25, 1, "physical", "GAS", None, False, "A"),
    Market("HG", "Copper", "HG", "COMEX", "industrial metals", "HKNUZ", "25,000 lb", 0.05, 12.5, 1, "physical", "METAL", "LBD_PREV", True, "B"),
    Market("GC", "Gold", "GC", "COMEX", "precious metals", "GJMQVZ", "100 oz", 0.10, 10, 1, "physical", "METAL", "LBD_PREV", True, "B"),
    Market("SI", "Silver", "SI", "COMEX", "precious metals", "HKNUZ", "5,000 oz", 0.5, 25, 1, "physical", "METAL", "LBD_PREV", True, "A"),
    Market("PL", "Platinum", "PL", "NYMEX", "precious metals", "FJNV", "50 oz", 0.10, 5, 1, "physical", "METAL", "LBD_PREV", True, "A"),
    Market("PA", "Palladium", "PA", "NYMEX", "precious metals", "HMUZ", "100 oz", 0.10, 10, 1, "physical", "METAL", "LBD_PREV", True, "B"),
    Market("ZC", "Corn", "ZC", "CBOT", "grains and oilseeds", "HKNUZ", "5,000 bu", 0.25, 12.5, 1, "physical", "GRAIN", "LBD_PREV", True, "A"),
    Market("ZS", "Soybeans", "ZS", "CBOT", "grains and oilseeds", "FHKNQUX", "5,000 bu", 0.25, 12.5, 1, "physical", "GRAIN", "LBD_PREV", True, "A"),
    Market("ZW", "Wheat (SRW)", "ZW", "CBOT", "grains and oilseeds", "HKNUZ", "5,000 bu", 0.25, 12.5, 1, "physical", "GRAIN", "LBD_PREV", True, "A"),
    Market("KE", "KC wheat (HRW)", "KE", "CBOT", "grains and oilseeds", "HKNUZ", "5,000 bu", 0.25, 12.5, 1, "physical", "GRAIN", "LBD_PREV", True, "B"),
    Market("ZM", "Soybean meal", "ZM", "CBOT", "grains and oilseeds", "FHKNQUVZ", "100 short t", 0.10, 10, 1, "physical", "GRAIN", "LBD_PREV", True, "B"),
    Market("ZL", "Soybean oil", "ZL", "CBOT", "grains and oilseeds", "FHKNQUVZ", "60,000 lb", 0.01, 6, 1, "physical", "GRAIN", "LBD_PREV", True, "B"),
    Market("SB", "Sugar No. 11", "SB", "ICE US", "softs", "HKNV", "112,000 lb", 0.01, 11.2, 2, "physical", "LBD_PREV", None, False, "B"),
    Market("KC", "Coffee C", "KC", "ICE US", "softs", "HKNUZ", "37,500 lb", 0.05, 18.75, 2, "physical", "KC", "KC", False, "A"),
    Market("CC", "Cocoa", "CC", "ICE US", "softs", "HKNUZ", "10 t", 1.0, 10, 2, "physical", "CC", "CC", False, "B"),
    Market("CT", "Cotton No. 2", "CT", "ICE US", "softs", "HKNVZ", "50,000 lb", 0.01, 5, 2, "physical", "CT", "CT", False, "A"),
    Market("LE", "Live cattle", "LE", "CME", "livestock", "GJMQVZ", "40,000 lb", 0.025, 10, 2, "physical", "LBD", "FBD", True, "A"),
    Market("GF", "Feeder cattle", "GF", "CME", "livestock", "FHJKQUVX", "50,000 lb", 0.025, 12.5, 2, "cash", "GF", None, True, "A"),
    Market("HE", "Lean hogs", "HE", "CME", "livestock", "GJKMNQVZ", "40,000 lb", 0.025, 10, 2, "cash", "HE", None, True, "B"),
    # T22 financial futures (§2.1); Norgate symbols from all_markets.csv of the snapshot (None = not listed)
    Market("6E", "Euro FX", "6E", "CME", "currencies", "HMUZ", "EUR 125,000", 0.00005, 6.25, 1, "physical", "FX", None, True, "A", F),
    Market("6B", "British pound", "6B", "CME", "currencies", "HMUZ", "GBP 62,500", 0.0001, 6.25, 1, "physical", "FX", None, True, "B", F),
    Market("6M", "Mexican peso", "6M", "CME", "currencies", "HMUZ", "MXN 500,000", 0.00001, 5, 1, "physical", "FX", None, True, "A", F),
    Market("6L", "Brazilian real", None, "CME", "currencies", MONTH_CODES, "BRL 100,000", 0.00005, 5, 2, "cash", "FX", None, True, "B", F),
    Market("6Z", "South African rand", None, "CME", "currencies", "HMUZ", "ZAR 500,000", np.nan, np.nan, 2, "physical", "FX", None, True, "B", F),
    Market("FGBL", "Euro-Bund", "FGBL", "Eurex", "bonds", "HMUZ", "EUR 100,000", 0.01, 10, 1, "physical", "EUREX", None, False, "A", F),
    Market("FOAT", "Euro-OAT", "FOAT", "Eurex", "bonds", "HMUZ", "EUR 100,000", 0.01, 10, 1, "physical", "EUREX", None, False, "B", F),
    Market("FBTP", "Euro-BTP", "FBTP", "Eurex", "bonds", "HMUZ", "EUR 100,000", 0.01, 10, 1, "physical", "EUREX", None, False, "B", F),
    Market("FBON", "Euro-Bono", None, "Eurex", "bonds", "HMUZ", "EUR 100,000", 0.01, 10, 1, "physical", "EUREX", None, False, "A", F),
    Market("R", "Long Gilt", "LLG", "ICE Europe", "bonds", "HMUZ", "GBP 100,000", 0.01, 10, 1, "physical", "GILT", None, False, "B", F),
]}
# Ticks above are in the units Norgate quotes (US cents for copper, silver, grains, softs and livestock; USD
# otherwise), so that "within one tick" in A5 compares like with like.  The pre-registration's table states them
# in USD per unit; the value per contract is unchanged (e.g. ZL 0.01 c/lb x 60,000 lb = $6).
COMMODITIES = [c for c, m in MARKETS.items() if m.kind == C]
FINANCIALS = [c for c, m in MARKETS.items() if m.kind == F]
XS_UNIVERSE = [c for c in COMMODITIES if c not in ("GC", "SI", "PL", "PA")]   # Amendment 1: 20 markets

# Contract-specification changes inside the vendor's spliced history (§2.1 rule 2), checked in Build 0.
SPEC_CHANGES = {
    "HO": ("2013-05", "No. 2 heating oil -> ULSD (NY Harbor ULSD from the May 2013 contract)"),
    "G": ("2015-01", "ICE gasoil -> low sulphur gasoil (10 ppm)"),
    "RB": ("2006-01", "RBOB from the first listed contract (Oct 2005); unleaded gasoline not in Norgate"),
}


# ------------------------------------------------------------------------------------------ business calendars
def _good_friday(year: int) -> dt.date:
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    month = (h + l_ - 7 * m + 114) // 31
    day = ((h + l_ - 7 * m + 114) % 31) + 1
    return dt.date(year, month, day) - dt.timedelta(days=2)


def _future_bdays(start: pd.Timestamp, end: pd.Timestamp) -> pd.DatetimeIndex:
    from pandas.tseries.holiday import USFederalHolidayCalendar
    days = pd.bdate_range(start, end)
    hol = set(USFederalHolidayCalendar().holidays(start, end).date)
    hol |= {_good_friday(y) for y in range(start.year, end.year + 1)}
    return pd.DatetimeIndex([d for d in days if d.date() not in hol])


class BizCal:
    """A market's trading calendar: observed settlement dates, extended with weekdays (no US holidays)."""

    def __init__(self, observed: pd.DatetimeIndex, extend_to: str = "2045-12-31"):
        obs = pd.DatetimeIndex(sorted(set(observed)))
        ext = _future_bdays(obs[-1] + pd.Timedelta(days=1), pd.Timestamp(extend_to))
        self.days = obs.append(ext)
        self._arr = self.days.values

    def month_days(self, year: int, month: int) -> pd.DatetimeIndex:
        lo = np.datetime64(f"{year:04d}-{month:02d}-01")
        hi = np.datetime64(pd.Timestamp(year, month, 1) + pd.offsets.MonthBegin(1), "D")
        i, j = np.searchsorted(self._arr, [lo, hi])
        return self.days[i:j]

    def before(self, day: pd.Timestamp, n: int = 1) -> pd.Timestamp:
        """The n-th business day strictly before `day`."""
        i = np.searchsorted(self._arr, np.datetime64(day))
        return self.days[i - n]

    def on_or_after(self, day: pd.Timestamp) -> pd.Timestamp:
        i = np.searchsorted(self._arr, np.datetime64(day))
        return self.days[i]

    def count_between(self, a: pd.Timestamp, b: pd.Timestamp) -> int:
        """Business days d with a <= d <= b."""
        i, j = np.searchsorted(self._arr, [np.datetime64(a), np.datetime64(b)], side="left")
        j = np.searchsorted(self._arr, np.datetime64(b), side="right")
        return int(j - i)


def _prev_month(y: int, m: int, k: int = 1) -> tuple[int, int]:
    p = pd.Period(year=y, month=m, freq="M") - k
    return p.year, p.month


# LTD rules for live contracts (exchange rulebooks as commonly stated; verified in Build 0 against the final
# settlement of every expired contract, see ltd_rule_check).  (cal, year, month) -> Timestamp.
def _ltd_cl(cal, y, m):
    py, pm = _prev_month(y, m)
    d25 = pd.Timestamp(py, pm, 25)
    if d25 not in cal.days:
        d25 = cal.before(d25)
    return cal.before(d25, 3)


def _ltd_brn(cal, y, m):   # ICE Brent from the Mar-2016 contract: last business day of the second month before
    py, pm = _prev_month(y, m, 2)
    return cal.month_days(py, pm)[-1]


def _ltd_ng(cal, y, m):
    return cal.before(pd.Timestamp(y, m, 1), 3)


def _ltd_gas(cal, y, m):
    return cal.before(pd.Timestamp(y, m, 14), 2)


def _ltd_lbd_prev(cal, y, m):
    py, pm = _prev_month(y, m)
    return cal.month_days(py, pm)[-1]


def _ltd_metal(cal, y, m):
    return cal.month_days(y, m)[-3]


def _ltd_grain(cal, y, m):
    return cal.before(pd.Timestamp(y, m, 15), 1)


def _ltd_kc(cal, y, m):
    return cal.month_days(y, m)[-9]


def _ltd_cc(cal, y, m):
    return cal.month_days(y, m)[-12]


def _ltd_ct(cal, y, m):
    return cal.month_days(y, m)[-17]


def _ltd_lbd(cal, y, m):
    return cal.month_days(y, m)[-1]


def _ltd_gf(cal, y, m):
    days = cal.month_days(y, m)
    thu = [d for d in days if d.weekday() == 3]
    return thu[-1] if thu else days[-1]


def _ltd_he(cal, y, m):
    return cal.month_days(y, m)[9]


def _ltd_fx(cal, y, m):    # CME FX: two business days before the third Wednesday
    wed = [d for d in pd.date_range(pd.Timestamp(y, m, 1), periods=21) if d.weekday() == 2][2]
    return cal.before(wed, 2)


def _ltd_eurex(cal, y, m):  # two exchange days before the 10th calendar day (delivery day)
    return cal.before(cal.on_or_after(pd.Timestamp(y, m, 10)), 2)


def _ltd_gilt(cal, y, m):   # two business days before the last business day of the delivery month
    return cal.month_days(y, m)[-3]


LTD_RULES = {"CL": _ltd_cl, "BRN": _ltd_brn, "NG": _ltd_ng, "GAS": _ltd_gas, "LBD_PREV": _ltd_lbd_prev,
             "METAL": _ltd_metal, "GRAIN": _ltd_grain, "KC": _ltd_kc, "CC": _ltd_cc, "CT": _ltd_ct,
             "LBD": _ltd_lbd, "GF": _ltd_gf, "HE": _ltd_he, "FX": _ltd_fx, "EUREX": _ltd_eurex,
             "GILT": _ltd_gilt}


def _fnd_lbd_prev(cal, y, m):
    return _ltd_lbd_prev(cal, y, m)


def _fnd_kc(cal, y, m):     # seven business days before the first business day of the delivery month
    return cal.before(cal.month_days(y, m)[0], 7)


def _fnd_cc(cal, y, m):     # ICE: ten business days prior to the sixth business day of the delivery month
    return cal.before(cal.month_days(y, m)[5], 10)


def _fnd_ct(cal, y, m):     # five business days before the first business day of the delivery month
    return cal.before(cal.month_days(y, m)[0], 5)


def _fnd_fbd(cal, y, m):    # live cattle: first business day of the contract month
    return cal.month_days(y, m)[0]


FND_RULES = {"LBD_PREV": _fnd_lbd_prev, "KC": _fnd_kc, "CC": _fnd_cc, "CT": _fnd_ct, "FBD": _fnd_fbd}


# ----------------------------------------------------------------------------------------------- loading
CONTRACT_RE = re.compile(r"^(?P<root>.+)-(?P<year>\d{4})(?P<code>[FGHJKMNQUVXZ])$")


def parse_contract(name: str) -> tuple[int, int]:
    m = CONTRACT_RE.match(name)
    if not m:
        raise ValueError(f"not a contract symbol: {name}")
    return int(m.group("year")), MONTH_CODES.index(m.group("code")) + 1


def contract_label(code: str, year: int, month: int) -> str:
    """Our label, e.g. CLM20 style -> 'CL-2020M' (Norgate uses its own root, e.g. BRN-2020M)."""
    return f"{MARKETS[code].norgate}-{year:04d}{MONTH_CODES[month - 1]}"


def load_contract_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date"])
    return df.set_index("date").sort_index()


class MarketData:
    """Everything Build 0 needs for one market, loaded from the Norgate snapshot."""

    def __init__(self, code: str, snapshot: str = SNAPSHOT, load_from: str = "1985-01-01"):
        self.m = MARKETS[code]
        self.code = code
        folder = snapshot_dir(snapshot) / "contracts" / code
        if self.m.norgate is None or not folder.is_dir():
            raise FileNotFoundError(f"{code}: no contract files in {folder}")
        frames, rows = {}, []
        for p in sorted(folder.glob("*.csv")):
            name = p.stem
            y, mo = parse_contract(name)
            df = load_contract_csv(p)
            if df.empty:
                continue
            rows.append({"contract": name, "year": y, "month": mo, "code": MONTH_CODES[mo - 1],
                         "first": df.index[0], "last": df.index[-1], "rows": len(df),
                         "designated": MONTH_CODES[mo - 1] in self.m.months})
            if df.index[-1] >= pd.Timestamp(load_from):
                frames[name] = df
        self.all_contracts = pd.DataFrame(rows).sort_values(["year", "month"]).reset_index(drop=True)
        self.frames = frames
        self.close = pd.DataFrame({k: v["close"] for k, v in frames.items()}).sort_index()
        self.volume = pd.DataFrame({k: v["volume"] for k, v in frames.items()}).sort_index()
        # market trading days: dates on which any contract of the market has a settlement
        self.calendar = BizCal(self.close.index)
        self.latest = self.close.index[-1]

    # -------------------------------------------------------------------------------- contract table
    @cached_property
    def contracts(self) -> pd.DataFrame:
        """Designated-calendar contracts with LTD, FND and notice (A1)."""
        t = self.all_contracts[self.all_contracts["designated"]].copy()
        t = t[t["contract"].isin(self.frames)].copy()
        rule = LTD_RULES[self.m.ltd_rule]
        fnd_rule = FND_RULES.get(self.m.fnd_rule) if self.m.fnd_rule else None
        live = t["last"] >= self.latest
        t["live"] = live
        t["ltd_rule"] = pd.to_datetime([rule(self.calendar, y, mo) for y, mo in zip(t["year"], t["month"])])
        # final settlement row of a cash-settled contract: Norgate adds the index-based final settlement after
        # the last trading day, separated from it by a missing market day (lean hogs) -> LTD = the bar before
        final = t["last"].copy()
        if self.m.settlement == "cash":
            days = self.close.index
            for i in t.index[~live]:
                s = self.close[t.at[i, "contract"]].dropna().index
                if len(s) > 1 and ((days > s[-2]) & (days < s[-1])).any():
                    final[i] = s[-2]
        # a contract whose quotes stop more than 30 days before its scheduled LTD stopped quoting early
        # (delisted far months, stray single quotes); its LTD stays the exchange rule and it is flagged
        stopped = (~live) & (final < t["ltd_rule"] - pd.Timedelta(days=30))
        t["stopped_early"] = stopped
        t["final_settlement_row"] = final != t["last"]
        t["ltd"] = pd.to_datetime(np.where(live | stopped, t["ltd_rule"], final))
        t["fnd"] = ([fnd_rule(self.calendar, y, mo) for y, mo in zip(t["year"], t["month"])]
                    if fnd_rule else pd.NaT)
        t["fnd"] = pd.to_datetime(t["fnd"])
        t["notice"] = t[["fnd", "ltd"]].min(axis=1)
        t["ym"] = t["year"] * 12 + t["month"]
        return t.sort_values("ym").set_index("contract")

    # -------------------------------------------------------------------------------- schedule and roll
    @cached_property
    def schedule(self) -> pd.DataFrame:
        """Monthly rebalance schedule, 1990-01 (or the first month with a prior settlement) to 2026-10."""
        cal = self.close.index
        start = max(pd.Period(ASSEMBLY_START, "M"), pd.Period(cal[0], "M"))
        out = []
        for p in pd.period_range(start, ASSEMBLY_END_MONTH, freq="M"):
            third = pd.Timestamp(p.year, p.month, 3)
            i = cal.searchsorted(third)
            if i >= len(cal) or i == 0:
                continue
            out.append({"month": p, "execution": cal[i], "decision": cal[i - 1]})
        return pd.DataFrame(out).set_index("month")

    def roll(self, buffer_days: int = BUFFER_DAYS) -> pd.DataFrame:
        """F1, F2 and F13 per rebalance month (the 35-day rule, §2.3; F13 per §3.1)."""
        ct = self.contracts
        names = ct.index.to_numpy()
        notice = ct["notice"].to_numpy()
        ltd = ct["ltd"].to_numpy()
        rows = []
        for month, r in self.schedule.iterrows():
            limit = np.datetime64(r["execution"] + pd.Timedelta(days=buffer_days))
            ok = np.nonzero(notice > limit)[0]
            if len(ok) == 0:
                rows.append({"month": month, "F1": None, "F2": None, "F13": None})
                continue
            i1 = ok[0]
            f1, f2 = names[i1], (names[i1 + 1] if i1 + 1 < len(names) else None)
            target = ltd[i1] + np.timedelta64(F13_TARGET_DAYS, "D")
            dist = np.abs((ltd - target).astype("timedelta64[D]").astype(int))
            elig = np.nonzero(dist <= F13_WINDOW_DAYS)[0]
            f13 = None
            if len(elig):
                best = dist[elig].min()
                f13 = names[elig[dist[elig] == best].max()]   # ties -> the later contract
            rows.append({"month": month, "F1": f1, "F2": f2, "F13": f13})
        out = pd.DataFrame(rows).set_index("month")
        return self.schedule.join(out)

    @cached_property
    def rolls(self) -> pd.DataFrame:
        return self.roll()

    # -------------------------------------------------------------------------------- prices on dates
    def settle(self, contract: str | None, day: pd.Timestamp) -> float:
        if contract is None or contract not in self.close.columns:
            return np.nan
        try:
            return float(self.close.at[day, contract])
        except KeyError:
            return np.nan

    def has_settle(self, contract: str | None, day: pd.Timestamp) -> bool:
        return bool(np.isfinite(self.settle(contract, day)))

    # -------------------------------------------------------------------------------- chained index
    def held_series(self, which: str = "F1") -> pd.Series:
        """Contract held on each market day (decided at the previous execution date), from the first execution."""
        r = self.rolls.dropna(subset=[which])
        days = self.close.index
        held = pd.Series(index=days, dtype=object)
        ex = list(r["execution"])
        cs = list(r[which])
        for k, (e, c) in enumerate(zip(ex, cs)):
            end = ex[k + 1] if k + 1 < len(ex) else days[-1] + pd.Timedelta(days=1)
            held[(days >= e) & (days < end)] = c
        return held.dropna()

    def daily_returns(self, which: str = "F1") -> pd.DataFrame:
        """Same-contract daily excess return r_ex[d] = F[T,d]/F[T,d-1] - 1 with T held on d-1 (§2.3).

        A missing settlement carries the last one forward (zero return that day, flagged `filled`); the gap's return
        is realised on the next available settlement."""
        held = self.held_series(which)
        days = held.index
        prev_contract = held.shift(1)
        out = []
        for c in pd.unique(held.values):
            mask = (prev_contract == c).to_numpy()
            if not mask.any():
                continue
            s = self.close[c].reindex(self.close.index).ffill()
            px = s.reindex(days)
            prev_px = s.shift(1).reindex(days)
            filled = self.close[c].reindex(days).isna()
            r = px / prev_px - 1.0
            out.append(pd.DataFrame({"contract": c, "r": r[mask], "filled": filled[mask],
                                     "price": px[mask], "prev_price": prev_px[mask]}))
        df = pd.concat(out).sort_index()
        return df

    def index(self, which: str = "F1") -> pd.Series:
        r = self.daily_returns(which)["r"].fillna(0.0)
        return (1.0 + r).cumprod()


def available_markets(snapshot: str = SNAPSHOT) -> list[str]:
    root = snapshot_dir(snapshot) / "contracts"
    return [c for c in MARKETS if (root / c).is_dir()]
