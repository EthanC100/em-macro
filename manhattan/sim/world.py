"""The simulated world of SIM_PREREG section 2 and the development scenarios of section 3.1.

    X_{v,t} = σ_{f,t} · ( μ_{v,t} + ε_{v,t} ),       μ_{v,t} = θ_v(t) / √252
    ε_{v,t} = √w_c ℓ_f c_t + √w_g g_{f,t} + √w_u u_{h,t} + √w_e e_{v,t}

Time. A period is a trading day; 252 a year, 5 a week. A family has 1,260 exploration days, then 1,750 reserve
days, both ending at its batch's freeze; forward days follow the freeze to day 2,520. Batches are frozen at equal
intervals over the programme. **Convention fixed here:** batch ``b`` (from 0) is frozen on day
``5 · ⌊504 b / B⌋``, a week boundary, so every family's weeks line up with the programme's; the first batch is
frozen on day 0 and the last one still has a forward life.

Nothing here is drawn from the priors of Protocol v3 section 7.1: edges are discrete or bounded.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

import numpy as np
from scipy.signal import lfilter

from manhattan.stats import hedge as hedge_mod

from . import seeds

YEAR, WEEK = 252, 5
EXPLORE, RESERVE, T_END = 1260, 1750, 2520
HISTORY = EXPLORE + RESERVE
THETA_MIN = 0.25
DEFAULT_WEIGHTS = (0.05, 0.25, 0.30, 0.40)


@dataclass(frozen=True)
class Size:
    name: str
    B: int
    nb_lo: int
    nb_hi: int
    H: int
    m: int
    N: int          # screening schedule
    N_F: int        # forward schedule

    @property
    def expected_families(self) -> float:
        return self.B * (self.nb_lo + self.nb_hi) / 2

    @property
    def N_F_all(self) -> int:
        """Forward schedule when every family is enrolled at its freeze (section 2.5(d)): 576 for STD."""
        return round(1.2 * self.expected_families)


SIZES = {"STD": Size("STD", 40, 8, 16, 2, 6, 48, 120),
         "LONG": Size("LONG", 100, 4, 8, 2, 4, 120, 300),
         "HB": Size("HB", 24, 10, 10, 2, 4, 29, 60)}


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    sizes: tuple
    e_all: tuple = ()                       # sizes also evaluated with every family enrolled at its freeze
    group: str = "development"
    weights: tuple = DEFAULT_WEIGHTS
    m: int | None = None                    # variants per hypothesis, when not the size's
    dist: str = "normal"                    # "normal", "t3", "t5": always scaled to variance 1
    pi1: float = 0.05
    both: float = 0.5                       # P(both hypotheses have the edge | the family has one)
    theta: tuple = ((0.5, 0.5), (1.0, 0.3), (1.5, 0.2))     # (hypothesis edge, probability)
    q_lo: float = 0.5                       # variant edge = θ_h · q_v, q_v uniform on (q_lo, 1)
    null_mean: float = 0.0                  # annualised mean of a variant with no edge
    retention: tuple | None = None          # ((retention, probability), ...): forward edge = retention × edge
    garch: bool = False
    ar: float = 0.0                         # AR(1) coefficient of g and u
    select_k: int = 1                       # the submitted family is the best of this many pool draws ...
    select_days: int = EXPLORE              # ... by family-portfolio Sharpe ratio over its first days
    adaptive: str | None = None             # "exploration" or "reserve": the window the adaptive channel sees
    hedge: bool = False                     # D11: unhedged returns and a core factor; the hedge is estimated

    def variants(self, size: Size) -> int:
        return self.m or size.m


def _power(i: int, theta: float) -> Scenario:
    return Scenario(f"P{i}", f"power, both hypotheses at {theta}", ("STD",), theta=((theta, 1.0),), both=1.0)


SCENARIOS = {s.id: s for s in (
    Scenario("D01", "no edges", ("STD", "LONG", "HB"), e_all=("STD",), pi1=0.0),
    Scenario("D02", "rare edges", ("STD", "LONG", "HB"), pi1=0.02),
    Scenario("D03", "correlated variants", ("STD",), weights=(0.02, 0.08, 0.85, 0.05), m=20),
    Scenario("D04", "correlated families", ("STD",), e_all=("STD",), weights=(0.40, 0.20, 0.20, 0.20)),
    Scenario("D05", "fat tails", ("STD", "HB"), dist="t3"),
    Scenario("D06", "volatility clustering", ("STD",), dist="t5", garch=True),
    Scenario("D07a", "serial correlation +0.2", ("STD",), e_all=("STD",), ar=0.2),
    Scenario("D07b", "serial correlation -0.2", ("STD",), ar=-0.2),
    Scenario("D08", "historical selection bias", ("STD", "HB"), select_k=20),
    Scenario("D09a", "adaptive variants from the exploration window", ("STD",), adaptive="exploration"),
    Scenario("D09b", "adaptive variants from the reserve window", ("STD",), adaptive="reserve"),
    Scenario("D10", "misspecified priors", ("HB",), pi1=0.15, theta=((0.3, 0.7), (2.0, 0.3)), null_mean=-0.2,
             retention=((0.0, 0.5), (1.0, 0.5))),
    Scenario("D11", "hedge estimation", ("STD",), hedge=True),
    _power(1, 0.5), _power(2, 1.0), _power(3, 1.5), _power(4, 2.5),
)}
HELD_OUT = ("H01", "H02a", "H02b", "H02c", "H03", "H04", "H05", "H06", "H07", "H08m", "H08x", "H09", "H10", "H11")
ADAPT_ROUNDS, ADAPT_PER_ROUND, ADAPT_CORR = 3, 6, 0.9
GARCH = (0.02, 0.10, 0.88)
FACTOR_SHARPE, BETA_START, BETA_ANNUAL_SD = 0.6, 0.5, 0.3


def is_heldout(scenario_id: str) -> bool:
    return scenario_id in HELD_OUT


def freeze_days(B: int) -> np.ndarray:
    return WEEK * ((np.arange(B) * (T_END // WEEK)) // B)


def noise(rng: np.random.Generator, shape, dist: str) -> np.ndarray:
    """Draws from ``D`` with mean 0 and variance 1."""
    if dist == "normal":
        return rng.standard_normal(shape)
    if dist in ("t3", "t5"):
        df = int(dist[1:])
        return rng.standard_t(df, shape) * math.sqrt((df - 2) / df)
    raise ValueError(f"unknown distribution {dist}")


def ar1(z: np.ndarray, phi: float) -> np.ndarray:
    """A stationary AR(1) with variance 1 built from unit-variance innovations along the last axis."""
    if phi == 0.0:
        return z
    b = math.sqrt(1 - phi * phi)
    x, _ = lfilter([b], [1.0, -phi], z, axis=-1, zi=z[..., :1] * (1 - b))     # first value: z_0 itself
    return x


def garch_variance(z: np.ndarray) -> np.ndarray:
    """``s²_t = 0.02 + 0.10 s²_{t−1} z²_{t−1} + 0.88 s²_{t−1}`` along the last axis, started at its mean, 1."""
    w, a, b = GARCH
    z = np.asarray(z, dtype=float)
    coef = a * z * z + b                                         # s²_t = w + coef_{t−1} s²_{t−1}
    if z.ndim == 1:                                              # plain floats: the fast path for one series
        out, s2 = [1.0], 1.0
        for k in coef[:-1].tolist():
            s2 = w + k * s2
            out.append(s2)
        return np.array(out)
    out = np.empty_like(z)
    out[..., 0] = 1.0
    for t in range(1, z.shape[-1]):
        out[..., t] = w + coef[..., t - 1] * out[..., t - 1]
    return out


@dataclass
class Common:
    """What every family of a replication shares: the common factor, the market volatility term, the core factor."""
    c: np.ndarray
    s2_mkt: np.ndarray | None = None
    factor: np.ndarray | None = None


@dataclass
class Family:
    idx: int                    # number in the programme, in freeze order
    batch: int
    freeze: int                 # programme day of the freeze
    X: np.ndarray               # (H, m, days): core-hedged net returns of the frozen grid; day 0 is freeze − 3,010
    theta: np.ndarray           # (H, m): annualised edge on history (exploration and reserve)
    theta_fwd: np.ndarray       # (H, m): annualised edge on forward days
    has_edge: bool
    noise_sd_h: float           # daily standard deviation of a hypothesis portfolio's noise (σ = 1)
    noise_sd_f: float           # ... of the family portfolio's noise
    X_adaptive: np.ndarray | None = None        # (H, rounds · per round, days)
    theta_adaptive: np.ndarray | None = None    # (H, rounds · per round)
    mean_sigma: float = 1.0
    extra: dict = field(default_factory=dict)

    @property
    def n_forward(self) -> int:
        return self.X.shape[2] - HISTORY

    @property
    def reserve_null(self) -> bool:
        """Section 2.4: every variant's mean over the reserve window is at most 0."""
        return bool(np.all(self.theta <= 0))

    @property
    def component_edges(self) -> np.ndarray:
        """True forward mean of each hypothesis portfolio and of the family portfolio, in the variants' units."""
        h = self.theta_fwd.mean(axis=1)
        return np.append(h, h.mean())

    @property
    def forward_null(self) -> bool:
        """Section 2.4: for every component the mean forward return is at most 0."""
        return bool(np.all(self.component_edges <= 0))

    @property
    def true_sharpe_f(self) -> float:
        """The family portfolio's true forward Sharpe ratio (annualised)."""
        return float(self.theta_fwd.mean() * self.mean_sigma / self.noise_sd_f)

    @property
    def true_sharpe_h(self) -> np.ndarray:
        return self.theta_fwd.mean(axis=1) * self.mean_sigma / self.noise_sd_h


def programme(scn: Scenario, size: Size, streams: seeds.Streams) -> np.ndarray:
    """Families per batch, drawn before any return is simulated (section 2.2)."""
    return streams.rng(seeds.PROGRAMME).integers(size.nb_lo, size.nb_hi + 1, size=size.B)


def common(scn: Scenario, streams: seeds.Streams) -> Common:
    rng = streams.rng(seeds.COMMON)
    c = noise(rng, HISTORY + T_END, scn.dist)
    out = Common(c=c)
    if scn.garch:
        out.s2_mkt = garch_variance(c)
    if scn.hedge:
        out.factor = FACTOR_SHARPE / math.sqrt(YEAR) + streams.rng(seeds.FACTOR).standard_normal(HISTORY + T_END)
    return out


def draw_edges(rng: np.random.Generator, scn: Scenario, H: int, m: int) -> tuple[np.ndarray, np.ndarray, bool]:
    """(historical edge, forward edge, has an edge) of one pool draw: annualised, shape ``(H, m)``."""
    theta = np.full((H, m), scn.null_mean)
    has = bool(rng.random() < scn.pi1)
    which = np.zeros(H, dtype=bool)
    if has:
        if rng.random() < scn.both:
            which[:] = True
        else:
            which[rng.integers(H)] = True
        vals = np.array([v for v, _ in scn.theta])
        probs = np.array([p for _, p in scn.theta])
        th = rng.choice(vals, size=H, p=probs)
        q = rng.uniform(scn.q_lo, 1.0, size=(H, m))
        theta = np.where(which[:, None], th[:, None] * q, theta)
    fwd = theta.copy()
    if scn.retention is not None:
        r = rng.choice([v for v, _ in scn.retention], p=[p for _, p in scn.retention])
        fwd = np.where(theta > 0, r * theta, theta)
    return theta, fwd, has


def _draw_noise(rng, scn: Scenario, H: int, m: int, days: int):
    return noise(rng, days, scn.dist), noise(rng, (H, days), scn.dist), noise(rng, (H, m, days), scn.dist)


def _returns(scn: Scenario, cm: Common, start: int, theta_path, g, u, e, ell: float = 1.0):
    """Returns ``(X, σ, ε)`` for days ``start .. start + days`` of the programme's calendar (0 = day −3,010)."""
    wc, wg, wu, we = scn.weights
    days = g.shape[-1]
    g, u = ar1(g, scn.ar), ar1(u, scn.ar)
    eps = (math.sqrt(wc) * ell * cm.c[start : start + days] + math.sqrt(wg) * g)[None, None, :] \
        + math.sqrt(wu) * u[:, None, :] + math.sqrt(we) * e
    sigma = np.ones(days)
    if scn.garch:
        sigma = np.sqrt(0.5 * cm.s2_mkt[start : start + days] + 0.5 * garch_variance(g))
    return sigma * (theta_path / math.sqrt(YEAR) + eps), sigma, eps


def _sharpe(x: np.ndarray) -> np.ndarray:
    return x.mean(axis=-1) / x.std(axis=-1)


def _theta_path(theta: np.ndarray, fwd: np.ndarray, days: int) -> np.ndarray:
    out = np.repeat(theta[:, :, None], days, axis=2)
    out[:, :, HISTORY:] = fwd[:, :, None]
    return out


def make_family(scn: Scenario, size: Size, streams: seeds.Streams, cm: Common, idx: int, batch: int,
                freeze: int) -> Family:
    """One submitted family: a pool draw, or the best of ``select_k`` pool draws on its first ``select_days``."""
    H, m = size.H, scn.variants(size)
    days = HISTORY + T_END - freeze
    start = freeze                                   # calendar index of the family's day 0 (freeze − 3,010 + 3,010)
    first = scn.select_days
    best = None
    for j in range(scn.select_k):
        theta, fwd, has = draw_edges(streams.rng(seeds.FAMILY_PARAMS, idx, j), scn, H, m)
        rng = streams.rng(seeds.FAMILY_NOISE, idx, j)
        head = _draw_noise(rng, scn, H, m, first)
        if scn.select_k > 1:
            Xh, _, _ = _returns(scn, cm, start, theta[:, :, None], *head)
            score = float(_sharpe(Xh.mean(axis=(0, 1))))
        else:
            score = 0.0
        if best is None or score > best[0]:
            best = (score, theta, fwd, has, rng, head)
    _, theta, fwd, has, rng, head = best
    tail = _draw_noise(rng, scn, H, m, days - first)
    g, u, e = (np.concatenate([a, b], axis=-1) for a, b in zip(head, tail))
    X, sigma, eps = _returns(scn, cm, start, _theta_path(theta, fwd, days), g, u, e)
    wc, wg, wu, we = scn.weights
    fam = Family(idx=idx, batch=batch, freeze=freeze, X=X, theta=theta, theta_fwd=fwd, has_edge=has,
                 noise_sd_h=math.sqrt(wc + wg + wu + we / m), noise_sd_f=math.sqrt(wc + wg + wu / H + we / (H * m)),
                 mean_sigma=float(sigma[HISTORY:].mean()) if scn.garch else 1.0)
    if scn.adaptive:
        _add_adaptive(scn, streams, fam, sigma, eps)
    if scn.hedge:
        _apply_hedge(streams, cm, fam, start)
    return fam


def _add_adaptive(scn: Scenario, streams: seeds.Streams, fam: Family, sigma: np.ndarray, eps: np.ndarray) -> None:
    """D09: three rounds of six noisy copies (correlation 0.9) of each hypothesis's best variant so far, judged by
    realised Sharpe ratio on the window the channel sees. A copy has the copied variant's true edge. The frozen
    grid's returns are not touched, and the channel has its own random stream."""
    rng = streams.rng(seeds.ADAPTIVE, fam.idx)
    H, m, days = fam.X.shape
    lo, hi = (0, EXPLORE) if scn.adaptive == "exploration" else (EXPLORE, HISTORY)
    theta_path = _theta_path(fam.theta, fam.theta_fwd, days) / math.sqrt(YEAR)
    X_all, th_all, thf_all = [], [], []
    for h in range(H):
        xs = [fam.X[h, v] for v in range(m)]
        es = [eps[h, v] for v in range(m)]
        mus = [theta_path[h, v] for v in range(m)]
        th = list(fam.theta[h]); thf = list(fam.theta_fwd[h])
        for _ in range(ADAPT_ROUNDS):
            best = int(np.argmax([_sharpe(x[lo:hi]) for x in xs]))
            fresh = noise(rng, (ADAPT_PER_ROUND, days), scn.dist)
            for k in range(ADAPT_PER_ROUND):
                e_new = ADAPT_CORR * es[best] + math.sqrt(1 - ADAPT_CORR**2) * fresh[k]
                xs.append(sigma * (mus[best] + e_new)); es.append(e_new); mus.append(mus[best])
                th.append(th[best]); thf.append(thf[best])
        X_all.append(np.stack(xs[m:])); th_all.append(th[m:]); thf_all.append(thf[m:])
    fam.X_adaptive = np.stack(X_all)
    fam.theta_adaptive = np.array(th_all)
    fam.extra["theta_adaptive_fwd"] = np.array(thf_all)


def _apply_hedge(streams: seeds.Streams, cm: Common, fam: Family, start: int) -> None:
    """D11: unhedged return = β_t C_t + X_t with β a random walk from 0.5 (annual standard deviation 0.3), one per
    hypothesis; the pipeline then sees only the hedge of Protocol v3 section 2.2 applied to it."""
    rng = streams.rng(seeds.FACTOR, fam.idx)
    H, m, days = fam.X.shape
    C = cm.factor[start : start + days]
    beta = BETA_START + np.cumsum(rng.standard_normal((H, days)) * BETA_ANNUAL_SD / math.sqrt(YEAR), axis=1)
    unhedged = fam.X + beta[:, None, :] * C
    Xh, bhat = hedge_mod.hedged(unhedged.reshape(H * m, days), C)
    fam.extra["true_X"] = fam.X
    fam.extra["beta_error"] = float(np.mean(np.abs(bhat[:, 0, EXPLORE:].reshape(H, m, -1) - beta[:, None, EXPLORE:])))
    fam.X = Xh.reshape(H, m, days)


def batches(scn: Scenario, size: Size, streams: seeds.Streams):
    """Yield ``(batch number from 0, freeze day, [families])`` in freeze order."""
    n_b = programme(scn, size, streams)
    cm = common(scn, streams)
    idx = 0
    for b, (fz, n) in enumerate(zip(freeze_days(size.B), n_b)):
        fams = []
        for _ in range(int(n)):
            fams.append(make_family(scn, size, streams, cm, idx, b, int(fz)))
            idx += 1
        yield b, int(fz), fams


def without_adaptive(scn: Scenario) -> Scenario:
    return replace(scn, adaptive=None)
