"""Capacity checks and a square-root market-impact estimate (diagnostic only).

    python -m ledger.capacity            # print the algorithm's capacity table at the configured capital

Nothing here changes a position of the frozen algorithm (v1.0, v1.1). For the algorithm the checks are a
diagnostic shown on the Algorithm page; for Janus (ledger/janus.py) they are a hard sizing rule.

For each position:
  * notional in US$ = |size % of capital| / 100 x capital (per leg for a spread);
  * average daily volume (ADV) in US$ from data/ledger/capacity_reference.csv: free published figures (BIS
    Triennial Survey for FX; Borsa Istanbul's bulletin for Turkish bonds, computed) or documented estimates
    marked ``estimate`` in ``adv_status``;
  * flag ``adv`` when the notional is above 10% of ADV (MAX_PCT_ADV);
  * for futures with a position limit: contracts = notional / (price x multiplier), flag ``limit`` at 80% of
    the limit or more (NEAR_LIMIT);
  * square-root impact (Almgren et al. 2005; Toth et al. 2011): cost as a fraction of the traded notional =
    Y x sigma_daily x sqrt(Q / ADV), with Y = 1 (conservative; estimates range 0.5 to 1) and sigma_daily the
    instrument's annualised volatility / sqrt(252). It is reported for building the whole position from zero
    and for the trade actually made at the last rebalance.
"""
from __future__ import annotations

import csv
import math
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "data/ledger/capacity_reference.csv"
MAX_PCT_ADV = 10.0
NEAR_LIMIT = 0.8
IMPACT_Y = 1.0
TRADING_DAYS = 252

# Paper capital by configuration change (docs/config_changes.md): C01 US$100,000 -> US$10,000,000 and C03
# US$10,000,000 -> US$500,000,000, both from the 3 December 2026 rebalance (positions effective 2026-12).
# All results are in percentages; only notional amounts depend on these.
ALGO_CAPITAL = [("2026-11", 100_000.0), ("2026-12", 500_000_000.0)]   # (first effective month, US$)
JANUS_CAPITAL = 500_000_000.0


def algo_capital(effective_month: str | None) -> float:
    cap = ALGO_CAPITAL[0][1]
    for m, c in ALGO_CAPITAL:
        if (effective_month or "") >= m:
            cap = c
    return cap


def load_reference(path: Path = REFERENCE) -> dict[str, dict]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = [dict(r) for r in csv.DictReader(f)]
    out = {}
    for r in rows:
        for k in ("adv_usd_m", "contract_multiplier", "position_limit_contracts", "default_ann_vol_pct"):
            try:
                r[k] = float(r[k]) if r.get(k) not in (None, "") else None
            except ValueError:
                r[k] = None
        out[r["instrument"]] = r
    return out


def impact_fraction(trade_usd: float, adv_usd: float | None, ann_vol_pct: float | None, y: float = IMPACT_Y) -> float | None:
    """Square-root impact as a fraction of the traded notional."""
    if not trade_usd or not adv_usd or not ann_vol_pct:
        return 0.0 if not trade_usd else None
    sigma_d = ann_vol_pct / 100.0 / math.sqrt(TRADING_DAYS)
    return y * sigma_d * math.sqrt(abs(trade_usd) / adv_usd)


def check(instrument: str, size_pct: float, capital: float, ref: dict[str, dict], ann_vol_pct: float | None = None,
          trade_pct: float | None = None, price: float | None = None) -> dict:
    """One position's capacity row. ``size_pct`` and ``trade_pct`` are % of capital (signed)."""
    r = ref.get(instrument) or {}
    notional = abs(size_pct or 0.0) / 100.0 * capital
    adv = (r.get("adv_usd_m") or 0.0) * 1e6 or None
    vol = ann_vol_pct if ann_vol_pct else r.get("default_ann_vol_pct")
    pct_adv = 100.0 * notional / adv if adv else None
    contracts = limit = pct_limit = None
    mult, lim = r.get("contract_multiplier"), r.get("position_limit_contracts")
    if lim and mult and price:
        contracts = notional / (price * mult)
        limit = lim
        pct_limit = 100.0 * contracts / lim
    full = impact_fraction(notional, adv, vol)
    trade_usd = abs(trade_pct or 0.0) / 100.0 * capital if trade_pct is not None else None
    tr = impact_fraction(trade_usd, adv, vol) if trade_usd is not None else None
    flags = []
    if pct_adv is not None and pct_adv > MAX_PCT_ADV:
        flags.append("adv")
    if pct_limit is not None and pct_limit >= 100 * NEAR_LIMIT:
        flags.append("limit")
    if not r:
        flags.append("no reference")
    return {
        "instrument": instrument, "implementation": r.get("implementation"), "size_pct": size_pct,
        "notional_usd": round(notional), "adv_usd": round(adv) if adv else None, "adv_status": r.get("adv_status"),
        "adv_source": r.get("adv_source"), "pct_adv": round(pct_adv, 2) if pct_adv is not None else None,
        "days_to_trade_at_10pct": round(pct_adv / MAX_PCT_ADV, 2) if pct_adv is not None else None,
        "contracts": round(contracts) if contracts is not None else None, "position_limit": limit,
        "pct_limit": round(pct_limit, 1) if pct_limit is not None else None, "limit_source": r.get("limit_source"),
        "ann_vol_pct": vol,
        "impact_bp_full": round(full * 1e4, 1) if full is not None else None,
        "impact_pct_capital_full": round(100 * full * notional / capital, 4) if full is not None and capital else None,
        "trade_pct": trade_pct, "trade_usd": round(trade_usd) if trade_usd is not None else None,
        "impact_bp_trade": round(tr * 1e4, 1) if tr is not None else None,
        "impact_pct_capital_trade": round(100 * tr * trade_usd / capital, 4) if tr is not None and capital else None,
        "flags": flags,
    }


def max_notional(instrument: str, ref: dict[str, dict], price: float | None = None) -> float | None:
    """The largest notional (US$) that passes both checks: <= 10% of ADV and < 80% of the position limit."""
    r = ref.get(instrument) or {}
    caps = []
    if r.get("adv_usd_m"):
        caps.append(r["adv_usd_m"] * 1e6 * MAX_PCT_ADV / 100.0)
    if r.get("position_limit_contracts") and r.get("contract_multiplier") and price:
        caps.append(NEAR_LIMIT * r["position_limit_contracts"] * r["contract_multiplier"] * price * 0.999)
    return min(caps) if caps else None


# ----------------------------------------------------------------------------- algorithm history
def _git(*args) -> str | None:
    try:
        out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=60)
        return out.stdout if out.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def position_history(rel: str) -> dict[str, dict[str, float]]:
    """{effective_from: {instrument: size % of capital}} from every committed version of a positions file."""
    shas = (_git("log", "--format=%H", "--", rel) or "").split()
    out: dict[str, dict[str, float]] = {}
    for sha in reversed(shas):
        text = _git("show", f"{sha}:{rel}")
        if not text:
            continue
        rows = list(csv.DictReader(text.splitlines()))
        if not rows:
            continue
        eff = rows[0].get("effective_from")
        out[eff] = {r["instrument"]: float(r["size_pct_of_capital"]) for r in rows if r.get("size_pct_of_capital")}
    path = ROOT / rel
    if path.exists():
        with path.open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if rows:
            out[rows[0].get("effective_from")] = {r["instrument"]: float(r["size_pct_of_capital"]) for r in rows
                                                  if r.get("size_pct_of_capital")}
    return dict(sorted(out.items()))


def monthly_impact(history: dict[str, dict[str, float]], ref: dict[str, dict], vols: dict[str, float]) -> dict[str, dict]:
    """Impact cost (fraction of capital) of each rebalance's trades, booked in the month the positions start."""
    out, prev = {}, {}
    for eff, pos in history.items():
        cap = algo_capital(eff)
        total, rows = 0.0, []
        for inst in sorted(set(pos) | set(prev)):
            trade_pct = pos.get(inst, 0.0) - prev.get(inst, 0.0)
            if abs(trade_pct) < 1e-9:
                continue
            c = check(inst, pos.get(inst, 0.0), cap, ref, vols.get(inst), trade_pct)
            if c["impact_pct_capital_trade"] is not None:
                total += c["impact_pct_capital_trade"] / 100.0
            rows.append({"instrument": inst, "trade_pct": round(trade_pct, 3), "impact_bp": c["impact_bp_trade"]})
        out[eff] = {"capital_usd": cap, "impact_frac": round(total, 8), "trades": rows, "first": not prev}
        prev = pos
    return out


def algorithm_table(positions: list[dict], capital: float, ref: dict[str, dict] | None = None) -> dict:
    ref = ref or load_reference()
    rows = []
    for p in positions:
        size = p.get("size_pct_of_capital")
        rows.append({**check(p["instrument"], size, capital, ref, p.get("instrument_vol_pct"), p.get("trade_pct_of_capital")),
                     "side": p.get("side"), "country": p.get("country")})
    rows.sort(key=lambda r: -(r["pct_adv"] or 0))
    flagged = [r for r in rows if r["flags"] and r["flags"] != ["no reference"]]
    return {"capital_usd": capital, "rows": rows, "flagged": [r["instrument"] for r in flagged],
            "max_pct_adv": MAX_PCT_ADV, "near_limit": NEAR_LIMIT, "impact_y": IMPACT_Y,
            "impact_pct_capital_full_total": round(sum(r["impact_pct_capital_full"] or 0 for r in rows), 4),
            "method": ("Notional = |size| x capital. ADV from data/ledger/capacity_reference.csv (published figures "
                       "or documented estimates, as marked). Flag above 10% of ADV, or at 80% or more of an exchange "
                       "position limit. Square-root impact = Y x daily vol x sqrt(notional / ADV), Y = 1, as a cost on "
                       "the traded notional. Diagnostic only: the frozen algorithm's positions and official P&L "
                       "(its own cost model) are unchanged.")}


def main(argv=None) -> int:
    from .build import read_csv  # noqa: WPS433 (lazy: avoid an import cycle)
    pos = read_csv(ROOT / "results/systematic/positions.csv")
    for p in pos:
        p["size_pct_of_capital"] = float(p["size_pct_of_capital"])
        p["instrument_vol_pct"] = float(p.get("instrument_vol_pct") or 0) or None
    t = algorithm_table(pos, algo_capital("2026-12"))
    for r in t["rows"]:
        print(f"{r['instrument']:7s} {r['notional_usd']/1e6:9.1f}m  ADV {((r['adv_usd'] or 0)/1e6):10.1f}m "
              f"{r['pct_adv'] if r['pct_adv'] is not None else '-':>8}%  impact {r['impact_bp_full']}bp  {','.join(r['flags'])}")
    print("flagged:", ", ".join(t["flagged"]) or "none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
