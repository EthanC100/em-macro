"""Synthetic fenced market panels. **Synthetic data only.**

A panel holds daily excess returns and a slow "carry" observable for three synthetic asset classes:

    commodity  12 assets   ~1.5% daily vol, one class factor, strong vol clustering
    rates       8 assets   ~0.4% daily vol, a level factor shared by all
    fx         10 assets   ~0.6% daily vol, a "dollar" factor

Innovations are Student-t (5 d.o.f.) scaled to unit variance; volatility follows a GARCH(1,1)-type recursion; a
global risk factor links the classes. Nothing is calibrated to any market and nothing here is a market fact.

**Planted structure** (off by default, ``planted`` > 0): a small, known predictable component
``planted · σ · tanh(m_{t-1})`` where ``m`` is each asset's normalised 60-day trend. It exists so that tests can
check that the pipeline *can* recover a known synthetic effect; any such recovery is a property of the generator,
not a discovery.

**Fence.** The last ``protected_days`` days are a synthetic stand-in for a protected (reserve-like) window. They are
generated (so the data hash covers them) but ``FencedPanel`` never hands them out: every accessor returns arrays
cut at the fence, and ``window`` refuses an end past it. Stage 5 (protected evaluation) is disabled anyway
(``protected.py``); the fence exists so that adversarial tests can show that nothing in stages 0-4 reads past it.

**Identity.** ``data_hash`` is the SHA-256 of the canonical generator parameters and the bytes of every array,
including the protected tail. ``verify_synthetic`` regenerates the panel from its recorded parameters and checks the
hash: a panel that was not produced by this generator (for example real data) cannot pass it, and the runner calls
it before every run.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np

from manhattan.spec import canonical_bytes

GENERATOR = "hte.data/1"
CLASSES = {
    # name: (n_assets, daily vol, class-factor loading, garch alpha, garch beta, carry persistence)
    "commodity": (12, 0.015, 0.45, 0.08, 0.90, 0.995),
    "rates": (8, 0.004, 0.75, 0.05, 0.93, 0.998),
    "fx": (10, 0.006, 0.55, 0.06, 0.92, 0.997),
}
DOMAINS = tuple(CLASSES)


class ProtectedDataRefused(PermissionError):
    """A read past the fence (the synthetic protected window)."""


class NotSynthetic(PermissionError):
    """The panel is not a verified output of this synthetic generator."""


def _calendar(n: int, start: date = date(2000, 1, 3)) -> np.ndarray:
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return np.array(out, dtype="datetime64[D]")


def _student(rng: np.random.Generator, shape, dof: float = 5.0) -> np.ndarray:
    return rng.standard_t(dof, size=shape) / np.sqrt(dof / (dof - 2.0))


@dataclass(frozen=True)
class PanelParams:
    seed: int = 20261118
    n_days: int = 2772                 # 11 synthetic years of business days
    protected_days: int = 252          # the last synthetic year is the protected stand-in
    planted: float = 0.0               # strength of the planted trend effect (0 = pure null world)
    global_loading: float = 0.25

    def as_dict(self) -> dict:
        return {"generator": GENERATOR, "seed": int(self.seed), "n_days": int(self.n_days),
                "protected_days": int(self.protected_days), "planted": float(self.planted),
                "global_loading": float(self.global_loading)}


@dataclass(frozen=True)
class FencedPanel:
    """Returns and carry per domain, cut at the fence. Construct only with ``generate``."""

    params: PanelParams
    data_hash: str
    fence: int                                   # first protected index; usable rows are [0, fence)
    dates: np.ndarray = field(repr=False)
    _returns: dict = field(repr=False)
    _carry: dict = field(repr=False)
    provenance: dict = field(default_factory=dict)

    def domains(self) -> tuple:
        return tuple(self._returns)

    def returns(self, domain: str) -> np.ndarray:
        """Daily excess returns ``(fence, n_assets)``, read-only. ``r[t]`` is realised over day ``t``."""
        return self._returns[domain][: self.fence]

    def carry(self, domain: str) -> np.ndarray:
        """The carry observable as *published*: ``carry[t]`` is known at the close of day ``t`` (the generator
        applies a one-day publication lag before it is stored here)."""
        return self._carry[domain][: self.fence]

    def n_assets(self, domain: str) -> int:
        return self._returns[domain].shape[1]

    def window(self, start: int, end: int) -> tuple[int, int]:
        if not 0 <= start < end:
            raise ValueError("window must satisfy 0 <= start < end")
        if end > self.fence:
            raise ProtectedDataRefused(f"window end {end} is past the fence {self.fence} (protected window)")
        return start, end

    def protected_tail(self, domain: str):
        raise ProtectedDataRefused("the protected window is not readable by stages 0-4; stage 5 is disabled")

    @property
    def n_days(self) -> int:
        return self.fence


def _hash_arrays(params: PanelParams, returns: dict, carry: dict, dates: np.ndarray) -> str:
    h = hashlib.sha256(canonical_bytes(params.as_dict()))
    h.update(dates.astype("int64").tobytes())
    for d in sorted(returns):
        h.update(d.encode())
        h.update(np.ascontiguousarray(returns[d]).tobytes())
        h.update(np.ascontiguousarray(carry[d]).tobytes())
    return h.hexdigest()


def generate(params: PanelParams = PanelParams()) -> FencedPanel:
    if params.protected_days < 0 or params.n_days - params.protected_days < 300:
        raise ValueError("need at least 300 unprotected days")
    rng = np.random.default_rng(np.random.SeedSequence([params.seed, 0x48544531]))
    n = params.n_days
    g = _student(rng, n) * 0.008                       # global risk factor
    returns, carry = {}, {}
    for name, (k, vol, load, a, b, phi) in CLASSES.items():
        f = _student(rng, n)                           # class factor (unit variance)
        e = _student(rng, (n, k))
        # GARCH(1,1)-type variance on the unit-variance shocks, common persistence per class
        omega = 1.0 - a - b
        h = np.empty((n, k))
        hv = np.ones(k)
        z = np.sqrt(load) * f[:, None] + np.sqrt(1.0 - load) * e
        for t in range(n):
            h[t] = hv
            hv = omega + a * z[t] ** 2 * hv + b * hv
        sig = vol * rng.uniform(0.7, 1.3, size=k)
        r = sig * np.sqrt(h) * z + params.global_loading * g[:, None] * (sig / 0.01)
        # carry: a persistent AR(1) per asset, unrelated to future returns in the null world
        c = np.empty((n, k))
        cv = rng.normal(0.0, 1.0, size=k)
        s = np.sqrt(1.0 - phi ** 2)
        eta = rng.normal(0.0, 1.0, size=(n, k))
        for t in range(n):
            cv = phi * cv + s * eta[t]
            c[t] = cv
        published = np.empty_like(c)
        published[0] = np.nan                          # one-day publication lag
        published[1:] = c[:-1]
        if params.planted:
            lr = np.log1p(np.clip(r, -0.9, None))
            cs = np.cumsum(lr, axis=0)
            m = np.zeros_like(r)
            m[60:] = (cs[60:] - cs[:-60]) / (np.sqrt(60.0) * sig)
            add = np.zeros_like(r)
            add[1:] = params.planted * sig * np.tanh(m[:-1])   # depends on returns up to t-1 only
            r = r + add
        returns[name] = r
        carry[name] = published
    dates = _calendar(n)
    for d in returns:
        returns[d].setflags(write=False)
        carry[d].setflags(write=False)
    dh = _hash_arrays(params, returns, carry, dates)
    return FencedPanel(params=params, data_hash=dh, fence=n - params.protected_days, dates=dates,
                       _returns=returns, _carry=carry,
                       provenance={"synthetic": True, "generator": GENERATOR, "params": params.as_dict()})


_VERIFIED: dict[str, bool] = {}


def verify_synthetic(panel) -> str:
    """Refuse anything that is not a verified output of ``generate`` (returns the data hash)."""
    if not isinstance(panel, FencedPanel) or not panel.provenance.get("synthetic"):
        raise NotSynthetic("HTE runs on synthetic panels from manhattan.hte.data.generate only")
    if panel.provenance.get("generator") != GENERATOR:
        raise NotSynthetic(f"unknown generator {panel.provenance.get('generator')!r}")
    if panel.fence != panel.params.n_days - panel.params.protected_days:
        raise NotSynthetic("the fence does not match the panel's recorded protected window")
    if _VERIFIED.get(panel.data_hash):
        # still check the arrays have not been swapped since verification
        if _hash_arrays(panel.params, panel._returns, panel._carry, panel.dates) != panel.data_hash:
            raise NotSynthetic("panel arrays do not match the verified data hash")
        return panel.data_hash
    fresh = generate(panel.params)
    if fresh.data_hash != panel.data_hash or \
            _hash_arrays(panel.params, panel._returns, panel._carry, panel.dates) != panel.data_hash:
        raise NotSynthetic("panel does not reproduce from its recorded synthetic parameters")
    _VERIFIED[panel.data_hash] = True
    return panel.data_hash
