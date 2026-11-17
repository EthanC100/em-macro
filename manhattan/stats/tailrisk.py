"""The tail-risk check of Protocol v3.1 section 6.11: what a profitability claim needs beyond a rejection.

The forward test bets on weekly returns with every loss beyond ``c = 6`` ex-ante standard deviations counted as
six (section 6.3). A rejection is therefore about the **truncated** mean, and a strategy that earns a premium and
occasionally loses a great deal can have a positive truncated mean and a negative mean
(``results/manhattan_sim/v2/ESTIMAND_AND_TAIL_RISK.md``). Before a family is called profitable, is made
Live-experiment or Scale eligible, or carries the label "Formally supported", its leading component's forward
record must satisfy

    Σ Y_t  −  U( N_trunc ) · ( L − c )  >  0          and          Σ Z_t  >  0

    Σ Y_t     the truncated record's total gain, in ex-ante weekly standard deviations (what the e-process bets on)
    Σ Z_t     the same record untruncated
    N_trunc   the number of weeks truncated so far (section 6.3's tail record)
    U(N)      the one-sided 95% upper confidence bound for the mean of a Poisson count after N events:
              ½ χ²_0.95(2(N + 1)), which is 3.00 after none (the rule of three), 4.74 after one, 6.30 after two
    L         the stress loss of one week, in ex-ante weekly standard deviations: the largest of the loss the
              family's spec declares under "tail exposure", the worst week on the family's whole record, and a
              floor of 12 (twice the truncation point)

The record is every test period since enrolment, the weeks the variance-ratio rule skipped included.

**The check withholds a label and nothing else.** An e-LOND rejection is recorded and counted when it happens,
whatever this check says: the number of rejections, every other family's bar and the 5% accounting are those of
section 6.8 (``manhattan.stats.elond``, which this module does not call and cannot change). ``formal_label``
takes the rejection as a fact and returns what the family may be called.

It is not a test of the mean: a strategy with no edge and no crash passes it in about a fifth of ten-year
records. It is a condition added to a rejection or a tier, never a substitute for one.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import chi2

from .eprocess import C_WEEKLY

LEVEL = 0.95                            # of the upper bound on the number of tail weeks the record cannot rule out
STRESS_FLOOR = 2 * C_WEEKLY             # 12: the least stress loss any family is charged, declared or not
FORMAL = "Formally supported by forward-only evidence"
WITHHELD = "e-LOND rejection on record; label withheld: tail-risk check not met (section 6.11)"


def poisson_upper(n, level: float = LEVEL):
    """One-sided upper confidence bound for a Poisson mean after ``n`` events (3.00 for none: the rule of three)."""
    return 0.5 * chi2.ppf(level, 2 * (np.asarray(n, dtype=float) + 1))


def stress_loss(declared: float | None, worst_week: float, floor: float = STRESS_FLOOR) -> float:
    """``L``: the largest of the declared stress loss, the worst week on record and the floor, all as positive
    numbers of ex-ante weekly standard deviations. ``declared=None`` is a spec that declares no number."""
    if declared is not None and not declared >= 0:
        raise ValueError("a declared stress loss is a non-negative number of ex-ante weekly standard deviations")
    return float(max(floor, worst_week, 0.0 if declared is None else declared))


@dataclass(frozen=True)
class TailCheck:
    passed: bool
    truncated_gain: float           # Σ Y
    untruncated_gain: float         # Σ Z
    n_weeks: int
    n_trunc: int
    upper_count: float              # U(N_trunc)
    stress_loss: float              # L
    charge: float                   # U(N_trunc) · (L − c)
    margin: float                   # Σ Y − charge
    declared: float | None
    reason: str                     # "" when passed; otherwise which condition failed


def check(Z, *, declared_stress: float | None = None, worst_week: float | None = None, c: float = C_WEEKLY,
          level: float = LEVEL, floor: float = STRESS_FLOOR) -> TailCheck:
    """The check on one record. ``Z``: the leading component's untruncated standardised weekly returns, every
    week since enrolment. ``worst_week``: the largest weekly loss on the family's **whole** record (from its
    freeze), as a positive number, when that record is longer than ``Z``; by default the worst week of ``Z``."""
    Z = np.asarray(Z, dtype=float)
    if Z.ndim != 1:
        raise ValueError("one record at a time")
    if not np.isfinite(Z).all():
        raise ValueError("the record has a missing week: section 6.6 leaves no week out")
    Y = np.maximum(Z, -c)
    n_trunc = int((Y > Z).sum())
    worst = max(0.0, float(-Z.min()) if Z.size else 0.0, 0.0 if worst_week is None else float(worst_week))
    L = stress_loss(declared_stress, worst, floor)
    U = float(poisson_upper(n_trunc, level))
    charge = U * (L - c)
    gain, raw = float(Y.sum()), float(Z.sum())
    margin = gain - charge
    reason = ""
    if not margin > 0:
        reason = "the truncated record does not cover the tail losses it cannot rule out"
    if not raw > 0:
        reason = (reason + "; " if reason else "") + "the untruncated record is not positive"
    return TailCheck(passed=not reason, truncated_gain=gain, untruncated_gain=raw, n_weeks=int(Z.size), n_trunc=n_trunc,
                     upper_count=U, stress_loss=L, charge=charge, margin=margin, declared=declared_stress, reason=reason)


def passes(Z: np.ndarray, L, c: float = C_WEEKLY, level: float = LEVEL, floor: float = STRESS_FLOOR) -> np.ndarray:
    """The same check for many records at once (rows of ``Z``), with declared stress loss ``L`` (a number or one
    per record). Returns a boolean per record."""
    Z = np.atleast_2d(np.asarray(Z, dtype=float))
    Y = np.maximum(Z, -c)
    n_trunc = (Y > Z).sum(axis=1)
    worst = np.maximum(np.maximum(np.asarray(L, dtype=float), -Z.min(axis=1)), floor)
    return (Y.sum(axis=1) - poisson_upper(n_trunc, level) * (worst - c) > 0) & (Z.sum(axis=1) > 0)


def formal_label(elond_rejected: bool, tail: TailCheck | None) -> str:
    """What a family may be called (section 8.5). The rejection is a fact of record and is not this function's
    to change: with no rejection there is no label; with one, the label needs the check, and until the check
    holds the family is reported as rejected with the label withheld."""
    if not elond_rejected:
        return ""
    return FORMAL if (tail is not None and tail.passed) else WITHHELD


def may_claim_profit(tail: TailCheck | None) -> bool:
    """Whether a family may be described as profitable or as having a positive mean return, as far as this check
    goes (the claim's other conditions are section 8's)."""
    return bool(tail is not None and tail.passed)
