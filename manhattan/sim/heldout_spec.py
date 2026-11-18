"""The held-out scenarios of SIM_PREREG section 3.2 and SIM_PREREG_v2 section 3.2, as data, and what stops their
construction. Nothing here draws a value, builds a world, or runs anything.

Every parameter range is copied from the frozen text, with the exact words it comes from (``quote``); a test checks
that each quote occurs verbatim in the frozen file, so this table cannot drift from it. What the frozen text does
**not** fix is listed as an ambiguity, per scenario and for all of them (``GENERAL``). Construction stays disabled
while any ambiguity is open: ``construction_allowed`` is false for every scenario, and the runner refuses held-out
scenarios outside a tagged confirmation run in any case (``manhattan/sim/runlog.py``).

Resolving an ambiguity is the owner's decision, made in writing before any held-out value is drawn (an addition to
``docs/manhattan/SIM_PREREG_AMENDMENTS.md`` under SIM_PREREG section 8.4, or a new pre-registration version). It is
not made here: the table below records the questions, not answers.
"""
from __future__ import annotations

from dataclasses import dataclass, field

SIM_PREREG = "docs/manhattan/SIM_PREREG.md"
SIM_PREREG_V2 = "docs/manhattan/SIM_PREREG_v2.md"


@dataclass(frozen=True)
class Param:
    name: str
    kind: str                       # "real range", "integer range", "choice", "fixed", "schedule"
    values: tuple
    quote: str                      # the words of the frozen file this comes from, verbatim


@dataclass(frozen=True)
class HeldOut:
    id: str
    source: str                     # SIM_PREREG or SIM_PREREG_V2
    sizes: tuple
    params: tuple
    ambiguities: tuple = field(default_factory=tuple)

    @property
    def construction_allowed(self) -> bool:
        return not self.ambiguities and not GENERAL


# Open for every held-out scenario: SIM_PREREG section 8.2 says "Set k fixes every range of section 3.2 by draws
# from a random generator seeded with ...", and nothing more about the draws.
GENERAL = (
    "G1 distribution: the distribution of a value drawn from a range is not stated (uniform, log-uniform, uniform "
    "over the integers of an integer range, equal probabilities over a listed choice).",
    "G2 order: the order in which the generator of set k is consumed (scenario order, parameter order, one value "
    "per range or one per use) is not stated, so two faithful implementations draw different sets.",
    "G3 level: the text does not say, for each range, whether it is fixed once per held-out set (\"values drawn per "
    "set\") or redrawn per replication, per batch, per family or per hypothesis; several rows only make sense at a "
    "lower level (a date per family, a β path per hypothesis).",
    "G4 world streams: the confirmation branch of seeds.Streams (branch k, 10 + k for the pooled re-run) is fixed by "
    "code, but which stream ids a held-out world's own randomness uses (missing days, crash days, regime paths, "
    "mirror pairs) is not, and version 1's stream ids are part of its frozen code hash (manhattan/sim/seeds.py).",
)

H = HeldOut
SCENARIOS = {s.id: s for s in (
    H("H01", SIM_PREREG, ("STD", "STD E-ALL"), (
        Param("share of families with ℓ_f = −1", "fixed", (0.5,), "half the families have `ℓ_f = −1`"),
        Param("w_c", "real range", (0.3, 0.6), "with `w_c` in [0.3, 0.6]"),
        Param("share of families in mirror pairs", "real range", (0.2, 0.5), "a share in [0.2, 0.5] of families form mirror pairs"),
        Param("mirror correlation r", "real range", (0.6, 0.9), "`r` in [0.6, 0.9]")),
      ("how the other weights (w_g, w_u, w_e) change when w_c is drawn so that they still sum to 1",
       "\"half the families\": exactly half, or each family with probability 0.5",
       "which component of a mirror pair correlates −r (the family term g, the whole ε, the returns), and how −r is "
       "produced together with the common term",
       "what happens to the odd family of a batch with an odd number of families")),
    H("H02a", SIM_PREREG, ("STD",), (
        Param("holding period H", "integer range", (5, 21), "`H` in 5..21"),),
      ("whether the sum of H positions is rescaled (variance and edge) back to the defaults' unit",
       "whether H is one value per set or per family or per variant")),
    H("H02b", SIM_PREREG, ("STD E-ALL",), (
        Param("averaging window H", "integer range", (2, 21), "`H` in 2..21"),),
      ("whether the averaged return is rescaled to unit variance, and whether the edge is",
       "whether H is one value per set or per family or per variant")),
    H("H02c", SIM_PREREG, ("STD E-ALL",), (
        Param("first-order autocorrelation", "real range", (0.03, 0.10), "first-order autocorrelation is in [0.03, 0.10]"),),
      ("k solves a quadratic with two roots for a given autocorrelation: which root",
       "whether the target autocorrelation is drawn once per set or per family",
       "whether the stale-marked return is rescaled to unit variance")),
    H("H03", SIM_PREREG, ("STD", "HB"), (
        Param("expected stay, calm (days)", "real range", (500, 1500), "expected stay 500-1,500 days calm"),
        Param("expected stay, stress (days)", "real range", (60, 250), "60-250 days stress"),
        Param("stress volatility multiple", "real range", (2, 3), "volatility is 2-3 times higher"),
        Param("share of edge families that lose the edge for good", "fixed", (0.30,),
              "30% of families with an edge lose it for good at a uniform date in their reserve window")),
      ("one regime path for the whole programme or one per family",
       "\"volatility 2-3 times higher\": the multiple of σ or of σ²",
       "whether the state at the start of the calendar is drawn from the chain's stationary law",
       "30%: exactly 30% of the edge families or each with probability 0.3")),
    H("H04", SIM_PREREG, ("STD", "STD E-ALL"), (
        Param("episodes per decade", "integer range", (1, 3), "1-3 episodes per decade"),
        Param("episode length (days)", "integer range", (20, 60), "of 20-60 days"),
        Param("w_c in an episode", "real range", (0.7, 0.9), "`w_c` rises to [0.7, 0.9]"),
        Param("volatility multiple in an episode", "real range", (2, 4), "volatility is 2-4 times higher"),
        Param("share of families with ℓ_f = +1", "real range", (0.5, 1.0), "a share in [0.5, 1.0] of families have `ℓ_f = +1`")),
      ("how the other weights change when w_c rises in an episode",
       "\"per decade\": over the programme's calendar (history and forward, 5,530 days) or over the 2,520 forward days",
       "whether episodes may overlap, and where they are placed (uniformly on the calendar?)",
       "\"2-4 times\": the multiple of σ or of σ²")),
    H("H05", SIM_PREREG, ("STD", "HB"), (
        Param("pool draws K", "choice", (10, 30, 100), "`K` in {10, 30, 100}"),
        Param("π_1", "real range", (0.01, 0.05), "`π_1` in [0.01, 0.05]")),
      ("the probabilities of K = 10, 30 and 100",
       "the selection score: the family portfolio's realised Sharpe ratio over exploration and reserve together "
       "(as D08 on the exploration window), or another score")),
    H("H06", SIM_PREREG, ("STD", "HB"), (
        Param("retention, class A", "fixed", (1.0,), "retention 1 (class A)"),
        Param("retention, class B", "choice", (0.3, 0.7), "0.3 or 0.7 (class B)"),
        Param("retention, class C", "schedule", (0.0, 0.6, 0.5), "0 with probability 0.6 else 0.5 (class C)"),
        Param("half-life h, class B (years)", "real range", (3, 6), "in [3, 6] (B)"),
        Param("half-life h, class C (years)", "real range", (1, 2), "in [1, 2] (C)")),
      ("the shares of families in classes A, B and C",
       "class B: the probabilities of retention 0.3 and 0.7",
       "the date the halving starts from (the freeze?), and whether it is continuous or in steps",
       "whether h is one value per set, per class or per family",
       "how the HB model's mechanism classes relate to the true classes (SIM_PREREG_v2 section 2(f): \"H06 has real ones\")")),
    H("H07", SIM_PREREG, ("HB",), (
        Param("θ_h", "real range", (0.2, 3.0), "`θ_h` log-uniform on [0.2, 3]"),
        Param("null variant mean", "real range", (-0.4, 0.0), "null variants have mean uniform on [−0.4, 0]"),
        Param("π_1 by batch", "schedule", (0.10, 0.01), "`π_1` falls linearly from 0.10 in the first batch to 0.01 in the last")),
      ("whether the null mean is drawn per variant, per hypothesis or per family",)),
    H("H08m", SIM_PREREG, ("STD E-ALL",), (
        Param("share of null families that are rare-event", "real range", (0.05, 0.20), "a share in [0.05, 0.20] of null families"),
        Param("crash size J (daily standard deviations)", "real range", (15, 40), "`J` in [15, 40]")),
      ("\"at least 2 crashes are expected in the family's forward life\": a bound, not a value; and forward lives "
       "differ by batch",
       "which returns carry the premium and the crash (every variant of the family, one hypothesis, the family "
       "portfolio) and whether crashes are common to the family",
       "whether the crash is on top of the noise ε or replaces it")),
    H("H08x", SIM_PREREG, ("STD E-ALL",), (
        Param("crash size J (daily standard deviations)", "real range", (100, 400), "`J` in [100, 400]"),),
      ("\"fewer than 1 crash expected in the forward life\": a bound, not a value",
       "the share of rare-event families: \"as H08m\" (the same range, or the same drawn value)")),
    H("H09", SIM_PREREG, ("HB",), (
        Param("share of edge families starting late", "real range", (0.2, 0.4), "a share in [0.2, 0.4] of families with an edge"),
        Param("years without the edge", "real range", (2, 5), "have none for the first 2-5 years after freeze"),
        Param("share of families not cheap", "fixed", (0.20,), "20% of families are not cheap")),
      ("whether the 2-5 years are one value per set or per family, and the same draw for the families that lose "
       "their edge",
       "what \"not cheap\" changes in the simulated programme: Protocol §9.2's cost of continued evaluation is not "
       "implemented in the HB pipeline (manhattan/sim/hb_v2.py treats every family as cheap)")),
    H("H10", SIM_PREREG, ("STD E-ALL", "HB"), (
        Param("share of days missing", "real range", (0.01, 0.05), "1-5% of days missing at random"),
        Param("relative chance of missing for |z| > 3", "fixed", (10,), "10 times as likely to be missing"),
        Param("gap length (days)", "integer range", (1, 5), "gaps of 1-5 days"),
        Param("share of observations revised", "real range", (0.02, 0.05), "2-5% of observations are revised"),
        Param("revision noise (standard deviations)", "fixed", (0.5, 0.1), "noise of 0.5 standard deviations plus 0.1"),
        Param("share of executables that stop", "real range", (0.01, 0.03), "1-3% of executables stop for good"),
        Param("final loss (standard deviations)", "real range", (5, 20), "final loss of 5-20 standard deviations")),
      ("how \"1-5% at random\", \"10 times as likely\" and \"gaps of 1-5 days\" combine into one missingness rate",
       "the unit of \"plus 0.1 in the strategy's favour\" (standard deviations?)",
       "how the screening, SPA and forward pipeline consume missing and revised days: the pipeline has no missing-"
       "data path today (Protocol §6.6 covers the forward test only)")),
    H("H11", SIM_PREREG, ("STD", "LONG", "HB"), (
        Param("noise distribution", "fixed", (4,), "Student-t with 4 degrees of freedom"),
        Param("pool draws K (H05)", "fixed", (10,), "H05 with `K = 10`")),
      ("every ambiguity of H01, H05, H06 and H10, and the order in which the five layers are applied",
       "whether H11's own ranges are drawn separately from H01's, H05's, H06's and H10's for the same set")),
    H("H12", SIM_PREREG_V2, ("STD",), (
        Param("core factors K", "choice", (1, 2, 3, 4), "`K` in {1, 2, 3, 4}"),
        Param("factor Sharpe ratio", "real range", (0.0, 0.8), "annualised Sharpe ratio in [0, 0.8]"),
        Param("pairwise factor correlation", "real range", (0.0, 0.5), "pairwise factor correlation in [0, 0.5]"),
        Param("β start", "real range", (-1.0, 1.0), "a random walk started uniformly in [−1, 1]"),
        Param("β annual standard deviation", "real range", (0.05, 0.4), "annual standard deviation in [0.05, 0.4]"),
        Param("share of hypotheses with constant β", "real range", (0.0, 0.5), "a share in [0, 0.5] of hypotheses have constant `β`"),
        Param("noise", "fixed", (4,), "Student-t with 4 degrees of freedom scaled to variance 1")),
      ("one correlation for every pair of factors or one per pair (and how a non-positive-definite draw is handled)",
       "whether the factor Sharpe ratios and the β standard deviation are one value per set, per factor or per path",
       "the probabilities of K = 1, 2, 3, 4",
       "the runner's held-out fence: H12 is not in manhattan.sim.world.HELD_OUT (version 1's hashed code), so "
       "`run --scenario H12` stops as an unknown scenario rather than through the logged held-out refusal")),
)}


def readiness() -> dict:
    """{scenario: {"construction_allowed": bool, "open": [ambiguities, the general ones first]}}."""
    return {s.id: {"construction_allowed": s.construction_allowed, "open": list(GENERAL) + list(s.ambiguities)}
            for s in SCENARIOS.values()}
