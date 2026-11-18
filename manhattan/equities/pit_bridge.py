"""Bridge to the existing point-in-time store (``manhattan.engine.pit``), which is reused, not modified.

The equity layer resolves intraday, timezone-aware publication and capture times to the **session close** at which
a value may first be used (``sessions.usable_close``). Those days are exactly what ``PitStore.add(available=...)``
takes, so equity data reach the Manhattan engine through its one door: a ``Reader`` bound to a caller, a domain and
the fence of ``config/manhattan.yaml``. A restatement exported here is a later vintage in the ``PitStore`` and is
invisible before its availability day, by the store's own rules.

Series names: ``eq.fund.<company>.<metric>`` (a fundamental's period end is its PIT period),
``eq.px.<security>`` (total-return index; period = availability = the session).

A licensed source is refused (hard rule 7 applies to anything that could be written out), unless the caller states
that the store stays private (``private_store=True``: the iMac runner).
"""
from __future__ import annotations

import numpy as np

from manhattan.engine.pit import PitStore

from .errors import ContractError
from .fundamentals import FundamentalStore
from .prices import DelistingPolicy, PriceBook
from .sources import DataContract


def _check(contract: DataContract, private_store: bool) -> None:
    contract.require("signal")
    if not private_store:
        contract.assert_publishable()


def fundamentals_to_pit(fs: FundamentalStore, store: PitStore, contract: DataContract, *, companies=None,
                        metrics=None, private_store: bool = False) -> list[str]:
    if contract.kind != "fundamentals_pit":
        raise ContractError(f"{contract.name} is not a fundamentals contract")
    _check(contract, private_store)
    names = []
    for c in companies or fs.companies():
        for m in metrics or fs.metrics():
            facts = fs.facts(c, m)
            if not facts:
                continue
            name = f"eq.fund.{c}.{m}"
            periods = [f.period_end for f in facts]
            avail = [fs.usable_from(f) for f in facts]
            store.add(name, np.array(periods, dtype="datetime64[D]"), [f.value for f in facts],
                      available=np.array(avail, dtype="datetime64[D]"))
            names.append(name)
    return names


def prices_to_pit(book: PriceBook, store: PitStore, contract: DataContract, securities, start, end, *,
                  delisting: DelistingPolicy | None = None, private_store: bool = False) -> list[str]:
    """Total-return indices (1 at ``start``), each daily value available at its own session's close."""
    if contract.kind != "prices_daily":
        raise ContractError(f"{contract.name} is not a price contract")
    _check(contract, private_store)
    names = []
    for s in securities:
        rs = book.total_returns(s, start, end, as_of=end, delisting=delisting)
        if rs.days.size == 0:
            continue
        idx = np.cumprod(1 + rs.returns)
        days = np.array(list(rs.days), dtype="datetime64[D]")
        name = f"eq.px.{s}"
        store.add(name, days, idx, available=days)
        names.append(name)
    return names
