"""Synthetic Phase 4B attempt fixtures: hand-made spec mappings, fabricated windows, no real data."""
from __future__ import annotations

from datetime import date

from manhattan import access, roles, spec
from manhattan.engine import evaluate

SPECS = {level: {"level": level, "fixture": "phase4b synthetic"}
         for level in ("executable", "variant", "hypothesis", "family")}
OPEN_FENCE = roles.Fence(exploration_end=date(2019, 12, 31), reserve={}, enabled=False)


def spec_kwargs(specs: dict = SPECS, *, batch: str = "AB-0001", channel: str = "blind",
                designated: bool = False) -> dict:
    """The keyword arguments ``engine.evaluate`` takes for these specs."""
    return {**specs, "batch": batch, "channel": channel, "designated": designated}


def identity(store, *, domain: str, start: date, end: date, role: str, window_id: str | None = None,
             specs: dict = SPECS, batch: str = "AB-0001", channel: str = "blind", designated: bool = False,
             version: dict | None = None) -> dict:
    wid = window_id or f"{domain}:{start}:{end}"
    return {"executable": spec.spec_id(specs["executable"]), "variant": spec.spec_id(specs["variant"]),
            "hypothesis": spec.spec_id(specs["hypothesis"]), "family": spec.spec_id(specs["family"]),
            "batch": batch, "role": role, "channel": channel, "designated": designated,
            "spec_hash": spec.spec_hash(specs["executable"]), "data_hash": store.data_hash(),
            "window": {"id": wid, "start": str(start), "end": str(end), "frequency": "daily"},
            "code_version": version or evaluate.code_version()}


def declared(store, *, domain: str, start: date, end: date, role: str, window_id: str | None = None):
    wid = window_id or f"{domain}:{start}:{end}"
    return [access.DeclaredWindow(wid, domain, start, end, role, "evaluation", store.data_hash())]


def register(ledger, store, *, domain: str, start: date, end: date, role: str, fence: roles.Fence,
             caller: str = roles.RUNNER, freeze: date | None = None, token=None, holding: int = 0,
             window_id: str | None = None, supersedes: str | None = None, **ident):
    return access.register_evaluation(
        ledger, identity=identity(store, domain=domain, start=start, end=end, role=role, window_id=window_id,
                                  **ident),
        windows=declared(store, domain=domain, start=start, end=end, role=role, window_id=window_id),
        caller=caller, fence=fence, freeze=freeze, holding=holding, token=token, supersedes=supersedes)


def reserve_fence(domain: str, start: date, end: date, exploration_end: date) -> roles.Fence:
    return roles.Fence(exploration_end=exploration_end, reserve={domain: (start, end)}, enabled=True)


def reserve_token(domain: str, window_id: str, batch: str = "AB-0001") -> roles.RunnerToken:
    return roles.RunnerToken(batch, "f" * 64, True, frozenset({(domain, window_id)}))
