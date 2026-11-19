"""The data-role fence at ingestion (DESIGN.md section 7).

``manhattan.roles`` already decides who may **read** which dates (exploration, reserve, forward, embargo), and
``manhattan.engine.pit.Reader`` applies it to every window the engine opens. This module applies the same decision
one step earlier, when raw vendor files are **parsed**: an adapter asks ``FenceGate.admit`` for every row's
instrument and session date **before** it converts the row's values. A row the caller may not read is never turned
into a number, an ``Observation`` or a stored row.

    exploration dates                 admitted for every caller that reads data
    reserve dates                     admitted only for the runner holding a verified token whose manifest names
                                      this (domain, window), while ``reserve.enabled`` is true (roles.check_read)
    forward dates (after a freeze)    admitted only for the runner
    embargoed dates                   never admitted (includes the whole reserve while it is disabled, and every
                                      date after the exploration end that belongs to no role)

Policies for a row that is not admitted:

    refuse   (default) stop the ingestion with ``FenceRefused``. Use it when a delivery is expected to hold only
             exploration dates: anything else is a mistake to look at.
    exclude  skip the row and count it. Only the count and the first and last excluded session dates are recorded
             (never a value). Use it to ingest the exploration part of a vendor snapshot that also covers later
             dates (every Norgate snapshot does).

When anything was excluded, the raw files hold protected dates, so the ingestion pipeline does not copy them into
the dataset store (it records their hashes only); they stay where they were, in the private store.

What this cannot do (ARCHITECTURE.md section 8): stop code outside Manhattan from opening the raw files, or stop a
session from constructing a ``RunnerToken`` that claims to be verified. It makes every Manhattan code path fail
closed and leaves a record of what each ingestion admitted.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date

from manhattan import roles

from .errors import FenceRefused
from .schema import Instrument

POLICIES = ("refuse", "exclude")


class FenceGate:
    def __init__(self, fence: roles.Fence, instruments: dict, caller: str, *, policy: str = "refuse",
                 freeze: date | None = None, holding: int = 0, token: roles.RunnerToken | None = None,
                 window_id: str | None = None):
        if policy not in POLICIES:
            raise ValueError(f"policy must be one of {POLICIES}")
        if caller not in roles.CALLERS or caller in roles.NO_DATA:
            raise FenceRefused(f"caller {caller!r} may not ingest dated data")
        self.fence, self.instruments, self.caller, self.policy = fence, instruments, caller, policy
        self._kw = dict(freeze=freeze, holding=holding, token=token, window_id=window_id)
        self._freeze, self._holding = freeze, holding
        self._role_cache: dict = {}
        self._auth_cache: dict = {}
        self.admitted: dict = defaultdict(int)
        self.excluded: dict = {}

    def _role(self, domain: str, d: date) -> str:
        k = (domain, d)
        if k not in self._role_cache:
            self._role_cache[k] = roles.role_of(d, domain, self.fence, self._freeze, self._holding)
        return self._role_cache[k]

    def _authorised(self, domain: str, role: str, d: date) -> tuple[bool, str]:
        if role == roles.EXPLORATION:
            return True, ""
        if role == roles.EMBARGO:
            return False, "embargoed dates (no role, a disabled reserve, or the days next to a fence)"
        k = (domain, role)
        if k not in self._auth_cache:
            try:
                roles.check_read(self.caller, domain, d, d, self.fence, **self._kw)
                self._auth_cache[k] = (True, "")
            except roles.RoleError as e:
                self._auth_cache[k] = (False, str(e))
        return self._auth_cache[k]

    def admit(self, instrument_id: str, session_date: date) -> bool:
        inst: Instrument | None = self.instruments.get(instrument_id)
        if inst is None:
            raise FenceRefused(f"instrument {instrument_id!r} has no reference data, so no fence domain: refused")
        role = self._role(inst.domain, session_date)
        ok, why = self._authorised(inst.domain, role, session_date)
        if ok:
            self.admitted[role] += 1
            return True
        if self.policy == "refuse":
            raise FenceRefused(f"{instrument_id} {session_date}: {role} row refused for caller {self.caller}: {why}")
        e = self.excluded.setdefault(role, {"rows": 0, "first_session": session_date, "last_session": session_date})
        e["rows"] += 1
        e["first_session"] = min(e["first_session"], session_date)
        e["last_session"] = max(e["last_session"], session_date)
        return False

    @property
    def excluded_any(self) -> bool:
        return bool(self.excluded)

    def decision(self) -> dict:
        """What the gate decided: counts and date bounds only, never a value."""
        return {"caller": self.caller, "policy": self.policy,
                "freeze": self._freeze.isoformat() if self._freeze else None,
                "exploration_end": self.fence.exploration_end.isoformat(),
                "reserve_enabled": self.fence.enabled,
                "reserve_domains": sorted(self.fence.reserve),
                "admitted": dict(sorted(self.admitted.items())),
                "excluded": {r: {"rows": v["rows"], "first_session": v["first_session"].isoformat(),
                                 "last_session": v["last_session"].isoformat()}
                             for r, v in sorted(self.excluded.items())}}


def default_fence() -> roles.Fence:
    """The fence in this checkout's ``config/manhattan.yaml`` (runners read main's copy)."""
    from manhattan import config
    return roles.Fence.from_config(config.load())
