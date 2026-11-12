"""The look-ahead test: nothing decided by a day may depend on anything that became available after it.

    problems = lookahead.violations(run, store, cutoffs)        # [] when the run is clean

``run`` takes a ``PitStore`` and returns a ``backtest.Result``. For each cut-off day the store is copied with
**every value that became available after the cut-off replaced by a different number**; the run is repeated on
the copy; and the two results are compared, bit for bit, on everything that was fixed by the cut-off:

- every decision taken on or before it (the target weights and the volatility-target multiplier), and
- the net return of every day whose marks had all become available by it.

A clean strategy passes whatever the data. The test **fails** when an input is visible too early.
``prepare`` lets a caller show that: it is applied to the store before each run, and
``shifted(store, series)`` gives every value of a series the date stamps of the observation before it, so that
a run on the shifted store peeks at tomorrow's value. The honest availability decides what is replaced; the shifted one
decides what the run sees.
"""
from __future__ import annotations

from typing import Callable

import numpy as np

from .backtest import Result
from .pit import PitStore, _day


def tampered_after(store: PitStore, cutoff, seed: int = 0) -> PitStore:
    """A copy of ``store`` in which every value that became available after ``cutoff`` is a different number."""
    rng = np.random.default_rng(seed)
    out = PitStore()
    for name in store.names():
        p, a, v = store._period[name], store._available[name], store._value[name]
        late = a > _day(cutoff)
        new = np.where(late, v * (1.0 + rng.uniform(0.05, 0.5, v.size)) + rng.uniform(0.01, 1.0, v.size), v)
        out.add(name, p, new, available=a)
    return out


def shifted(store: PitStore, series: str, steps: int = 1) -> PitStore:
    """A copy of ``store`` in which ``series`` is seen ``steps`` observations early: each value takes the period
    and the availability of the observation ``steps`` before it, so a run on the copy sees, at every decision,
    the value it should only have seen ``steps`` observations later. This is the error the test exists to
    catch."""
    if steps < 1:
        raise ValueError("shift by at least one observation")
    out = PitStore()
    for name in store.names():
        p, a, v = store._period[name], store._available[name], store._value[name]
        if name == series:
            p, a, v = p[:-steps], a[:-steps], v[steps:]
        out.add(name, p, v, available=a)
    return out


def violations(run: Callable[[PitStore], Result], store: PitStore, cutoffs, *, prepare: Callable | None = None,
               seed: int = 0) -> list[str]:
    """What changed that should not have, over all ``cutoffs`` (empty when the run looks at nothing ahead)."""
    prepare = prepare or (lambda s: s)
    base = run(prepare(store))
    out = []
    for i, c in enumerate(cutoffs):
        c = _day(c)
        other = run(prepare(tampered_after(store, c, seed + i)))
        if not np.array_equal(base.dates, other.dates):
            out.append(f"{c}: the calendar itself changed")
            continue
        fixed = [j for j in base.decisions if base.dates[j] <= c]
        for j in fixed:
            if j not in other.decisions or not np.array_equal(base.decisions[j], other.decisions[j]) \
                    or base.scale.get(j) != other.scale.get(j):
                out.append(f"{c}: the decision of {base.dates[j]} depends on data that became available after {c}")
                break
        if any(j not in base.decisions for j in other.decisions if other.dates[j] <= c):
            out.append(f"{c}: a decision appeared on or before {c} when later data changed")
        settled = base.marks_known <= c
        if not np.array_equal(base.net[settled], other.net[settled]):
            out.append(f"{c}: a return whose marks were all known by {c} changed")
    return out
