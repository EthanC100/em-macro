"""Data roles and their fences (ARCHITECTURE.md section 6): exploration, screening reserve, forward.

    exploration   anyone working in the open may read it; no evidential weight
    reserve       **the runner only**, inside a frozen batch, for that batch's one designated evaluation per domain
    forward       recorded by the runner after a spec's own freeze date

The fence (which dates are which, per domain) is Ethan's, in ``config/manhattan.yaml`` on main. The default is no
reserve at all (``reserve.enabled: false``): then every read of reserve dates is refused, for everyone. Between
two roles an embargo of the hypothesis's longest holding period plus one period is dropped, so that no position
spans a fence. Periods are counted as weekdays here; an exchange calendar belongs to the data layer (milestone E).

This module decides; it cannot enforce what code outside Manhattan does (ARCHITECTURE section 8). Every Manhattan
code path that reads dated data must call ``check_read`` first.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np

EXPLORATION, RESERVE, FORWARD, EMBARGO = "exploration", "reserve", "forward", "embargo"
RUNNER = "runner"
CALLERS = (RUNNER, "session", "explorer", "generator_adaptive", "generator_blind", "critic")
NO_DATA = ("generator_blind", "critic")          # they see a template or specs: never dated data
MAX_READ_DAYS = 40_000


class RoleError(PermissionError):
    """A read across a fence was refused."""


@dataclass(frozen=True)
class Fence:
    exploration_end: date
    reserve: dict                    # domain -> (start, end), both inclusive
    enabled: bool = False

    @classmethod
    def from_config(cls, cfg: dict) -> "Fence":
        res = cfg.get("reserve", {})
        windows = {d: (_day(w["start"]), _day(w["end"])) for d, w in (res.get("windows") or {}).items()}
        return cls(exploration_end=_day(cfg["exploration"]["data_end"]), reserve=windows, enabled=bool(res.get("enabled")))


def _day(v) -> date:
    return v if isinstance(v, date) else date.fromisoformat(str(v))


def _busdays_between(a: date, b: date) -> int:
    """Business days in ``[a, b)``."""
    return int(np.busday_count(np.datetime64(a), np.datetime64(b)))


def role_of(day: date, domain: str, fence: Fence, freeze: date | None = None, holding: int = 0) -> str:
    """The role of one date for a spec of ``domain`` frozen on ``freeze`` (None: not frozen yet).

    Embargo: the last ``holding + 1`` business days before the reserve starts and before it ends (a position
    opened there would span the fence), every date that belongs to no role (after the exploration end and
    outside the reserve; after the reserve and up to the freeze), and the whole reserve while it is not enabled."""
    day = _day(day)
    gap = holding + 1
    if freeze is not None and day > _day(freeze):
        return FORWARD
    window = fence.reserve.get(domain)
    if window is not None:
        start, end = window
        if start <= day <= end:
            if not fence.enabled:
                return EMBARGO
            return EMBARGO if _busdays_between(day, end) < gap else RESERVE
        if day < start and _busdays_between(day, start) <= gap:
            return EMBARGO
    if day <= fence.exploration_end and (window is None or day < window[0]):
        return EXPLORATION
    return EMBARGO


@dataclass(frozen=True)
class RunnerToken:
    """What lets the runner read a reserve window: a batch whose freeze it has verified (signed tag, manifest
    hash, timestamp), and the designated evaluations that batch's manifest names and that are not yet used."""
    batch: str
    manifest_hash: str
    verified: bool
    designated: frozenset = field(default_factory=frozenset)     # (domain, window id) pairs still unused


def check_read(caller: str, domain: str, start: date, end: date, fence: Fence, *, freeze: date | None = None,
               holding: int = 0, token: RunnerToken | None = None, window_id: str | None = None) -> str:
    """Allow or refuse a read of ``domain`` data dated ``start..end``. Returns the role read; raises ``RoleError``.

    A read must lie in one role. Reserve dates: the runner only, with a verified token whose manifest names this
    (domain, window) as a designated evaluation, and only while the reserve is enabled. Forward dates: the runner
    (it records them; everyone may read the recorded results in the ledger, which is not a read of dated data).
    Exploration dates: every caller that works in the open. The blind generator and the critic read no data."""
    if caller not in CALLERS:
        raise RoleError(f"unknown caller {caller}")
    if caller in NO_DATA:
        raise RoleError(f"{caller} reads no dated data at all")
    start, end = _day(start), _day(end)
    if end < start:
        raise RoleError("a read needs start on or before end")
    if (end - start).days > MAX_READ_DAYS:
        raise RoleError(f"a single read covers at most {MAX_READ_DAYS} days")
    days = np.arange(np.datetime64(start), np.datetime64(end) + np.timedelta64(1, "D"))
    roles = {role_of(d.astype(object), domain, fence, freeze, holding) for d in days}       # every day: no gaps
    if EMBARGO in roles:
        raise RoleError("the read touches embargoed dates (no role, a disabled reserve, or the days before a fence)")
    if len(roles) > 1:
        raise RoleError(f"the read spans roles {sorted(roles)}: one read, one role")
    role = roles.pop()
    if role == EXPLORATION:
        return role
    if caller != RUNNER:
        raise RoleError(f"{role} dates are read by the runner only")
    if role == RESERVE:
        if not fence.enabled:
            raise RoleError("the reserve is not enabled (config/manhattan.yaml reserve.enabled)")
        if token is None or not token.verified:
            raise RoleError("a reserve read needs a batch whose freeze the runner has verified")
        if (domain, window_id) not in token.designated:
            raise RoleError("this (domain, window) is not an unused designated evaluation of the batch")
    return role
