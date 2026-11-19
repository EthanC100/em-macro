"""From HTE's continuous synthetic returns to a contract-aware panel, and from HTE's costs to contract costs.

**Contractisation (synthetic only).** HTE holds daily excess returns per domain and asset, with no prices,
contracts or calendar spreads. ``contractise`` gives each asset a synthetic futures root:

* a level path ``S_t = anchor × Π_{s<=t} (1 + r_s)`` on the root's tick grid (whole ticks, so the adapter's
  unit guard holds; tick rounding adds less than half a tick of noise to each day's change);
* a held month that rolls every ``roll_every`` trading days into the next, whose settlement sits
  ``calendar_spread_ticks`` away; same-contract changes carry the P&L, the gap is never P&L;
* ADV (contracts per day) from the template and an optional per-day scale; volatility in points **known at the
  close of t**: an EWMA of returns through ``t`` times ``S_t``;
* roots quoted in EUR (``eur_assets``) and a synthetic EURUSD fix, so FX conversion is exercised.

Root names are ``H`` + the domain's initial + the asset number (``HC00``, ``HR07``, ``HF03``).

**Costs.** ``hte_matched_costs`` sets per-contract terms so that, at the template's nominal price, volatility and
ADV and at the run's capital,
the adapter's continuous cost equals HTE's per-notional cost ``c·|ΔW| + k·|ΔW|^1.5``
(inverting ``execution_realism.costs.hte_equivalent_coefficients``). The difference between HTE and the adapter
is then timing, whole contracts, whole ticks, rolls and liquidity, not a different cost level. Every term is a
``scenario`` source whose reference states the derivation. HTE's coefficients are synthetic, so nothing derived
from them describes a market.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field

import numpy as np

from manhattan.execution_realism.costs import CostModel, CostValue, RootCosts
from manhattan.execution_realism.instruments import Instrument
from manhattan.execution_realism.panel import SettlementPanel
from manhattan.execution_realism.provenance import Source

from .clock import as_dates
from .errors import BridgeError


@dataclass(frozen=True)
class InstrumentTemplate:
    tick_size: float
    multiplier: float
    anchor_price: float
    adv_contracts: float
    calendar_spread_ticks: int
    nominal_daily_vol: float                # where HTE's costs are matched (HTE data.CLASSES vols)
    price_unit_value: float = 1.0


DEFAULT_TEMPLATES = {
    "commodity": InstrumentTemplate(0.01, 1000.0, 60.0, 20000.0, 40, 0.015),
    "rates": InstrumentTemplate(0.015625, 1000.0, 110.0, 60000.0, -16, 0.004),
    "fx": InstrumentTemplate(0.00005, 125000.0, 1.10, 40000.0, 6, 0.006),
}


@dataclass(frozen=True)
class ContractMap:
    templates: dict = field(default_factory=lambda: dict(DEFAULT_TEMPLATES))
    eur_assets: dict = field(default_factory=lambda: {"rates": (1, 3, 5, 7)})   # domain -> asset indices in EUR
    roll_every: int = 63
    vol_halflife: int = 60
    fx_seed: int = 20261119

    def __post_init__(self):
        if self.roll_every < 2 or self.vol_halflife < 1:
            raise BridgeError("roll_every >= 2 and vol_halflife >= 1")

    def root(self, domain: str, a: int) -> str:
        return f"H{domain[0].upper()}{a:02d}"

    def instrument(self, domain: str, a: int) -> Instrument:
        t = self.templates.get(domain)
        if t is None:
            raise BridgeError(f"no instrument template for domain {domain!r}")
        ccy = "EUR" if a in self.eur_assets.get(domain, ()) else "USD"
        return Instrument(self.root(domain, a), ccy, t.tick_size, t.tick_size * t.multiplier * t.price_unit_value,
                          t.multiplier, t.price_unit_value)

    def as_dict(self) -> dict:
        return {"templates": {k: asdict(v) for k, v in sorted(self.templates.items())},
                "eur_assets": {k: list(v) for k, v in sorted(self.eur_assets.items())},
                "roll_every": self.roll_every, "vol_halflife": self.vol_halflife, "fx_seed": self.fx_seed,
                "version": "hte-contractise/1"}

    def digest(self) -> str:
        return hashlib.sha256(json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _ewvol(r: np.ndarray, hl: int) -> np.ndarray:
    """EWMA standard deviation (about zero) of returns through each row: row t reads r[:t+1] only."""
    lam = 0.5 ** (1.0 / hl)
    out = np.empty_like(r)
    v = r[0] * r[0]
    for t in range(r.shape[0]):
        v = lam * v + (1 - lam) * r[t] * r[t] if t else v
        out[t] = np.sqrt(v)
    return out


def contractise(returns, dates, domain: str, cmap: ContractMap = ContractMap(), *, missing=(), adv_scale=None,
                base_currency: str = "USD") -> SettlementPanel:
    """``returns``: HTE's ``panel.returns(domain)``, ``(fence, A)``, ``r[t]`` realised over day ``t``.
    ``missing``: ``(row, root)`` pairs with no settlement for any month of that root. ``adv_scale``: optional
    ``(fence, A)`` multipliers on ADV (a liquidity drought scenario)."""
    R = np.asarray(returns, float)
    if R.ndim != 2 or not np.isfinite(R).all():
        raise BridgeError("returns must be a finite (days, assets) array")
    n, A = R.shape
    days = as_dates(dates)
    if len(days) != n:
        raise BridgeError(f"{len(days)} dates for {n} rows")
    tmpl = cmap.templates.get(domain)
    if tmpl is None:
        raise BridgeError(f"no instrument template for domain {domain!r}")
    miss = set(missing)
    insts, prices, held = [], {}, {}
    adv = np.full((n, A), tmpl.adv_contracts)
    if adv_scale is not None:
        sc = np.asarray(adv_scale, float)
        if sc.shape != (n, A) or (sc < 0).any():
            raise BridgeError("adv_scale is a non-negative (days, assets) array")
        adv = adv * sc
    vol = np.empty((n, A))
    for a in range(A):
        inst = cmap.instrument(domain, a)
        root = inst.root
        level = tmpl.anchor_price * np.exp(np.cumsum(np.log1p(np.clip(R[:, a], -0.9, None))))
        ticks = np.round(level / tmpl.tick_size)
        if (ticks <= 0).any():
            raise BridgeError(f"{root}: the synthetic level reaches zero on the tick grid")
        book = {}
        for k in range(n // cmap.roll_every + 1):
            px = np.round((ticks + k * tmpl.calendar_spread_ticks) * tmpl.tick_size, 10)
            for t in range(n):
                if (t, root) in miss:
                    px[t] = np.nan
            book[f"{root}M{k:03d}"] = px
        prices[root] = book
        held[root] = [f"{root}M{t // cmap.roll_every:03d}" for t in range(n)]
        vol[:, a] = _ewvol(R[:, a], cmap.vol_halflife) * ticks * tmpl.tick_size
        insts.append(inst)
    fx = {}
    if any(i.currency == "EUR" for i in insts):
        rng = np.random.default_rng(cmap.fx_seed)
        fx["EUR"] = np.round(1.10 * np.exp(np.cumsum(0.005 * rng.standard_normal(n))), 6)
    return SettlementPanel.from_contracts(days=days, instruments=insts, prices=prices, held=held, adv=adv,
                                          vol_points=vol, base_currency=base_currency, fx=fx, data_kind="synthetic")


def hte_matched_costs(panel: SettlementPanel, cmap: ContractMap, domain: str, *, c: float, k: float,
                      capital: float, commission: float = 1.0, exchange_fee: float = 0.5,
                      max_participation: float = 0.1, fx_conversion_bps: float | None = 1.0) -> CostModel:
    """Per-contract terms reproducing HTE's ``(c, k)`` per unit notional at the template's nominal point: anchor
    price, nominal daily volatility, template ADV and ``capital`` (fees in each root's own currency). The match
    point is fixed by the contract map, not read from the data, so it is the same for every lag and window.
    Refuses when the fees alone already exceed ``c`` there."""
    if not (c >= 0 and k >= 0 and capital > 0):
        raise BridgeError("c, k >= 0 and capital > 0")
    t = cmap.templates.get(domain)
    if t is None:
        raise BridgeError(f"no instrument template for domain {domain!r}")
    P, adv, vfrac = t.anchor_price, t.adv_contracts, t.nominal_daily_vol
    src = Source("scenario", f"scenario: per-contract terms derived to reproduce HTE per-notional costs c={c!r}, "
                             f"k={k!r} for {domain} at price {P!r}, daily vol {vfrac!r}, ADV {adv!r}, capital "
                             f"{capital:g} (contract map {cmap.digest()[:12]}); HTE's coefficients are synthetic")
    v = lambda x: CostValue(float(x), src)
    terms = []
    for inst in panel.instruments:
        pv = inst.point_value
        fee_frac = (commission + exchange_fee) / (P * pv)
        if fee_frac > c:
            raise BridgeError(f"{inst.root}: fees alone ({fee_frac:.3g} of notional) exceed HTE's c={c:g}")
        ticks = (c - fee_frac) * P / inst.tick_size
        coef = k / (vfrac * math.sqrt(capital / (P * pv * adv)))
        terms.append((inst.root, RootCosts(inst.currency, v(commission), v(exchange_fee), v(ticks / 2), v(ticks / 2),
                                           v(coef), v(max_participation),
                                           None if (inst.currency == panel.base_currency or fx_conversion_bps is None)
                                           else v(fx_conversion_bps))))
    return CostModel(f"hte-matched {domain}", tuple(terms))
