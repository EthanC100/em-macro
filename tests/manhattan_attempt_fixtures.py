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


def reserve_token(domain: str, window_id: str, batch: str = "AB-0001", specs: dict = SPECS) -> roles.RunnerToken:
    return roles.RunnerToken(batch, "f" * 64, True, frozenset({(domain, window_id)}),
                             frozenset({spec.spec_hash(specs["executable"])}))


def forge(book, type_: str, payload: dict, *, writer: str | None = None) -> dict:
    """A hostile or buggy writer with file access: append a hash-valid record without any API rule (the public
    ``Ledger.append`` refuses lifecycle types). Only the reconciler can catch what this writes."""
    import json
    from datetime import datetime, timezone
    from manhattan import ledger as L
    rec = {"seq": len(book) + 1, "ts_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "type": type_,
           "writer": book.writer if writer is None else writer, "protocol": book.protocol, "payload": json.loads(spec.canonical_bytes(payload)),
           "prev_hash": book.head}
    rec["hash"] = L.record_hash(rec)
    with book.path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")
    book._index(rec)
    return rec
