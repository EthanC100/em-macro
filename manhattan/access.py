"""Binding attempt authorization (Phase 4B; docs/manhattan/BINDING_ACCOUNTING.md).

    ctx = access.register_evaluation(ledger, identity=..., windows=[...], caller="runner", fence=fence, ...)
    window = ctx.window(store)                      # or pit.Reader(..., attempt=ctx).window(start, end)
    result, record = evaluate.evaluate(window, strategy, ledger=ledger, ..., attempt=ctx)

An ``AttemptContext`` is the capability a protected read needs. It exists only after the attempt's start record is
durable in its authoritative store: the Manhattan ``Ledger`` (engine evaluations; the start record's hash is the
attempt ID) or the operational ``Store`` (screening and forward observations; journalled and verified on the remote).
Registration validates the whole identity (``ledger.IDENTITY_FIELDS``, with a known code identity) and every declared
window **before** writing; an invalid declaration writes nothing.

Declared windows are re-validated when opened: the store's data hash, the domain, the dates, and the role, which is
re-derived from the fence recorded at registration (``roles.check_read`` for exploration and reserve windows and for
engine forward windows; the strengthened R-1 rule for the runner's forward observations). The context opens only its
declared windows, only while its attempt is active, and records whether any value was read (``data_read``), which
its terminal states. Nothing here decides a statistical question.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date, timedelta

from manhattan import ledger as L
from manhattan import roles
from manhattan import spec as S
from manhattan.engine import pit

AccessError = pit.AccessError
PROTECTED = pit.PROTECTED_ROLES
KINDS = ("engine_evaluation", "screening", "forward_observation")
WINDOW_PURPOSES = ("evaluation", "signal_warmup")
_CTX_KEY = object()


def _day(v) -> date:
    if isinstance(v, date):
        return v
    if not isinstance(v, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) is None:
        raise AccessError("a declared window date is an ISO day")
    return date.fromisoformat(v)


@dataclass(frozen=True)
class DeclaredWindow:
    """One window an attempt may open: ``purpose`` ``evaluation`` (exactly one) or ``signal_warmup`` (forward
    observations only: history the signal needs before the first observation)."""
    id: str
    domain: str
    start: date
    end: date
    role: str
    purpose: str
    data_hash: str

    def __post_init__(self):
        if any(not isinstance(x, str) or not x.strip() for x in (self.id, self.domain)):
            raise AccessError("a declared window has an id and a domain")
        if not isinstance(self.start, date) or not isinstance(self.end, date) or self.end < self.start:
            raise AccessError("a declared window runs from start to end, start first")
        if (self.end - self.start).days > roles.MAX_READ_DAYS:
            raise AccessError("a declared window is longer than one read may be")
        if self.role not in L.ROLES or self.purpose not in WINDOW_PURPOSES:
            raise AccessError("a declared window has a known role and purpose")
        if not isinstance(self.data_hash, str) or re.fullmatch(r"[0-9a-f]{64}", self.data_hash) is None:
            raise AccessError("a declared window names the data identity it reads")

    def as_dict(self) -> dict:
        return {"id": self.id, "domain": self.domain, "start": self.start.isoformat(), "end": self.end.isoformat(),
                "role": self.role, "purpose": self.purpose, "data_hash": self.data_hash}

    @classmethod
    def from_any(cls, w) -> "DeclaredWindow":
        if isinstance(w, cls):
            return w
        if not isinstance(w, dict) or set(w) != {"id", "domain", "start", "end", "role", "purpose", "data_hash"}:
            raise AccessError("a declared window has exactly id, domain, start, end, role, purpose and data_hash")
        return cls(w["id"], w["domain"], _day(w["start"]), _day(w["end"]), w["role"], w["purpose"], w["data_hash"])


# ---------------------------------------------------------------- the fence, as recorded

def fence_snapshot(fence: roles.Fence, domain: str) -> dict:
    w = fence.reserve.get(domain)
    return {"exploration_end": fence.exploration_end.isoformat(), "reserve_enabled": bool(fence.enabled),
            "reserve_window": None if w is None else [w[0].isoformat(), w[1].isoformat()]}


def fence_from_snapshot(snap: dict, domain: str) -> roles.Fence:
    if not isinstance(snap, dict) or set(snap) != {"exploration_end", "reserve_enabled", "reserve_window"}:
        raise AccessError("malformed fence snapshot")
    w = snap["reserve_window"]
    if w is not None and (not isinstance(w, list) or len(w) != 2):
        raise AccessError("malformed fence snapshot")
    if type(snap["reserve_enabled"]) is not bool:
        raise AccessError("malformed fence snapshot")
    reserve = {} if w is None else {domain: (_day(w[0]), _day(w[1]))}
    return roles.Fence(exploration_end=_day(snap["exploration_end"]), reserve=reserve,
                       enabled=snap["reserve_enabled"])


def _near_reserve(day: date, domain: str, fence: roles.Fence, holding: int) -> bool:
    """Inside a configured reserve window of the domain (enabled or not), or in its embargo margin before it."""
    w = fence.reserve.get(domain)
    if w is None:
        return False
    start, end = w
    return start <= day <= end or (day < start and roles._busdays_between(day, start) <= holding + 1)


def _days(a: date, b: date):
    d = a
    while d <= b:
        yield d
        d += timedelta(days=1)


def _role_now(kind: str, dw: DeclaredWindow, *, caller: str, fence: roles.Fence, freeze: date | None, holding: int,
              token: roles.RunnerToken | None) -> None:
    """Re-derive the role of one declared window from the fence; raise ``AccessError`` (or ``RoleError``)."""
    if dw.purpose == "signal_warmup":
        # R-1 warm-up: history the signal reads before the first observation. Fail closed on any configured reserve
        # window (decision D-3 is Ethan's); everything else keeps the adapter's existing semantics.
        if any(_near_reserve(d, dw.domain, fence, holding) for d in _days(dw.start, dw.end)):
            raise AccessError("signal warm-up overlaps a configured reserve window (owner decision D-3)")
        return
    if kind == "forward_observation":
        if dw.role != roles.FORWARD:
            raise AccessError("a forward observation evaluates a forward-role window")
        for d in _days(dw.start, dw.end):
            if d <= fence.exploration_end:
                raise AccessError("a forward observation window starts after the exploration cut-off")
            if (freeze is None or d <= freeze) and _near_reserve(d, dw.domain, fence, holding):
                raise AccessError("a forward observation window reaches reserve dates before the freeze")
        return
    role = roles.check_read(caller, dw.domain, dw.start, dw.end, fence, freeze=freeze, holding=holding, token=token,
                            window_id=dw.id)
    if role != dw.role:
        raise AccessError(f"declared role {dw.role} but the fence gives {role}")


def check_declaration(kind: str, identity: dict, windows: tuple, *, caller: str, fence: roles.Fence,
                      freeze: date | None, holding: int, token: roles.RunnerToken | None) -> None:
    """Every rule a declaration must meet before registration writes anything."""
    if kind not in KINDS:
        raise AccessError(f"unknown attempt kind {kind}")
    if caller not in roles.CALLERS or caller in roles.NO_DATA:
        raise AccessError(f"caller {caller} cannot hold an attempt")
    if isinstance(holding, bool) or not isinstance(holding, int) or holding < 0:
        raise AccessError("holding is a whole number of periods")
    if freeze is not None and not isinstance(freeze, date):
        raise AccessError("freeze is a day")
    if len({w.id for w in windows}) != len(windows):
        raise AccessError("declared window ids are unique")
    evals = [w for w in windows if w.purpose == "evaluation"]
    warm = [w for w in windows if w.purpose == "signal_warmup"]
    if len(evals) != 1:
        raise AccessError("an attempt declares exactly one evaluation window")
    ev = evals[0]
    iw = identity["window"]
    if (ev.id, ev.start.isoformat(), ev.end.isoformat()) != (iw["id"], iw["start"], iw["end"]):
        raise AccessError("the evaluation window is the identity's window")
    if ev.role != identity["role"]:
        raise AccessError("the evaluation window's role is the attempt's role")
    if any(w.data_hash != identity["data_hash"] for w in windows):
        raise AccessError("every declared window reads the attempt's data identity")
    if kind == "screening" and ev.role != roles.EXPLORATION:
        raise AccessError("screening reads exploration-role data only")
    if kind == "forward_observation":
        if caller != roles.RUNNER or freeze is None:
            raise AccessError("forward observations are the runner's, after a recorded freeze")
        if len(warm) > 1:
            raise AccessError("at most one signal warm-up window")
        for w in warm:
            if w.role != roles.FORWARD or w.domain != ev.domain or w.end != ev.start - timedelta(days=1):
                raise AccessError("the warm-up window ends the day before the evaluation window, same domain")
    elif warm:
        raise AccessError("only forward observations declare a signal warm-up")
    if ev.role in PROTECTED and caller != roles.RUNNER:
        raise AccessError(f"{ev.role} windows are the runner's")
    for w in windows:
        _role_now(kind, w, caller=caller, fence=fence, freeze=freeze, holding=holding, token=token)


def _token_snapshot(token) -> dict | None:
    if token is None:
        return None
    return {"batch": str(token.batch), "manifest_hash": str(token.manifest_hash)}


def authorization(kind, windows, *, caller, fence, freeze, holding, token) -> dict:
    domain = next(w.domain for w in windows if w.purpose == "evaluation")
    return {"caller": caller, "windows": [w.as_dict() for w in windows], "fence": fence_snapshot(fence, domain),
            "freeze": None if freeze is None else freeze.isoformat(), "holding": holding,
            "token": _token_snapshot(token)}


def check_recorded(kind: str, identity: dict, auth: dict) -> None:
    """Re-validate a persisted authorization from its own fence snapshot (the reconciler's check). The recorded
    token cannot be re-verified here, so a reserve window is checked for role and fence only."""
    if not isinstance(auth, dict) or set(auth) != {"caller", "windows", "fence", "freeze", "holding", "token"}:
        raise AccessError("malformed authorization")
    if not isinstance(auth["windows"], list) or not auth["windows"]:
        raise AccessError("malformed authorization")
    windows = tuple(DeclaredWindow.from_any(w) for w in auth["windows"])
    ev = next((w for w in windows if w.purpose == "evaluation"), None)
    if ev is None:
        raise AccessError("malformed authorization")
    fence = fence_from_snapshot(auth["fence"], ev.domain)
    token = None
    if ev.role == roles.RESERVE:
        t = auth["token"]
        if not isinstance(t, dict):
            raise AccessError("a reserve attempt records its batch token")
        token = roles.RunnerToken(t.get("batch"), t.get("manifest_hash"), True, frozenset({(ev.domain, ev.id)}))
    freeze = None if auth["freeze"] is None else _day(auth["freeze"])
    check_declaration(kind, identity, windows, caller=auth["caller"], fence=fence, freeze=freeze,
                      holding=auth["holding"], token=token)


# ---------------------------------------------------------------- the context

class AttemptContext:
    """One registered, active attempt and the windows it may open. Created only by the register functions."""

    def __init__(self, *, _key, backend, attempt_id: str, kind: str, identity: dict, windows: tuple, caller: str,
                 fence: roles.Fence, freeze: date | None, holding: int, token):
        if _key is not _CTX_KEY:
            raise AccessError("an AttemptContext is created by registration only")
        self._backend, self.attempt_id, self.kind = backend, attempt_id, kind
        self._identity, self._windows = dict(identity), {w.id: w for w in windows}
        self.caller, self._fence, self._freeze, self._holding, self._token = caller, fence, freeze, holding, token
        self._meter = pit._Meter()
        self._ended = False

    # ---- facts
    @property
    def identity(self) -> dict:
        return dict(self._identity)

    @property
    def role(self) -> str:
        return self._identity["role"]

    @property
    def data_read(self) -> bool:
        return self._meter.reads > 0

    @property
    def evaluation_window(self) -> DeclaredWindow:
        return next(w for w in self._windows.values() if w.purpose == "evaluation")

    def active(self) -> bool:
        return not self._ended and self._backend.is_active(self.attempt_id)

    def _require_active(self) -> None:
        if not self.active():
            raise AccessError("the attempt is not registered and active")

    def _check_store(self, store: pit.PitStore, dw: DeclaredWindow) -> None:
        if not isinstance(store, pit.PitStore) or store.data_hash() != dw.data_hash:
            raise AccessError("the store is not the data identity this attempt registered")

    def _recheck(self, dw: DeclaredWindow) -> None:
        _role_now(self.kind, dw, caller=self.caller, fence=self._fence, freeze=self._freeze,
                  holding=self._holding, token=self._token)

    # ---- opening windows
    def window(self, store: pit.PitStore) -> pit.Window:
        """The declared evaluation window (engine evaluations and screening)."""
        if self.kind == "forward_observation":
            raise AccessError("forward observations open their window with forward_window")
        self._require_active()
        dw = self.evaluation_window
        self._check_store(store, dw)
        self._recheck(dw)
        return pit._open_window(store, dw.start, dw.end, dw.role, dw.domain, self.caller, purpose="evaluation",
                                attempt_id=self.attempt_id, window_id=dw.id, meter=self._meter)

    def _open_read(self, reader: pit.Reader, start, end, role: str) -> pit.Window:
        """Called by ``pit.Reader.window`` after ``check_read``: the read must be this attempt's declared
        evaluation window, read by its caller under its recorded fence."""
        if self.kind == "forward_observation":
            raise AccessError("forward observations open their window with forward_window")
        self._require_active()
        dw = self.evaluation_window
        kw = reader._kw
        if (reader.caller, reader.domain, reader.fence, kw["freeze"], kw["holding"]) != (
                self.caller, dw.domain, self._fence, self._freeze, self._holding) or kw["token"] is not self._token \
                or kw["window_id"] not in (None, dw.id):
            raise AccessError("the reader is not the one this attempt registered")
        if (pit._day(start).astype(object), pit._day(end).astype(object), role) != (dw.start, dw.end, dw.role):
            raise AccessError("the read is not a window this attempt declared")
        return self.window(reader._store)

    def forward_window(self, store: pit.PitStore) -> pit.Window:
        """The runner's R-1 adapter, now authorized: warm-up from the declared warm-up start, observations from the
        evaluation window's start, to its end, labelled forward."""
        if self.kind != "forward_observation":
            raise AccessError("only a forward-observation attempt opens the forward adapter")
        self._require_active()
        dw = self.evaluation_window
        warm = [w for w in self._windows.values() if w.purpose == "signal_warmup"]
        for w in (dw, *warm):
            self._check_store(store, w)
            self._recheck(w)
        start = warm[0].start if warm else dw.start
        return pit._open_window(store, start, dw.end, roles.FORWARD, dw.domain, self.caller,
                                purpose="forward_observation", attempt_id=self.attempt_id, window_id=dw.id,
                                signal_start=dw.start, meter=self._meter)

    def check_evaluation_window(self, window: pit.Window) -> None:
        """The window an evaluation is about to run on is this attempt's declared evaluation window."""
        self._require_active()
        dw = self.evaluation_window
        if (window.attempt_id, window.window_id, window.purpose, window.role, window.domain, window.start,
                window.end) != (self.attempt_id, dw.id, "evaluation", dw.role, dw.domain, dw.start, dw.end):
            raise AccessError("the window is not this attempt's declared evaluation window")

    # ---- terminals (classified reason only; never exception text or values)
    def fail(self, reason: str = "execution_error"):
        return self._end("failed", reason)

    def abort(self, reason: str = "interrupted"):
        return self._end("aborted", reason)

    def _end(self, status: str, reason: str):
        if reason not in L.TERMINAL_REASONS:
            raise AccessError("unknown attempt reason classification")
        self._require_active()
        out = self._backend.terminal(self.attempt_id, status, reason, self.data_read)
        self._ended = True
        return out

    def _mark_completed(self) -> None:
        self._ended = True


# ---------------------------------------------------------------- the Ledger (engine evaluations)

class _LedgerBackend:
    def __init__(self, ledger: L.Ledger):
        self.ledger = ledger

    def is_active(self, attempt_id: str) -> bool:
        try:
            self.ledger.active_attempt(attempt_id)
            return True
        except L.LedgerError:
            return False

    def terminal(self, attempt_id, status, reason, data_read):
        return self.ledger.end_attempt(attempt_id, status=status, reason=reason, data_read=data_read)


def _identity(identity: dict) -> dict:
    if not isinstance(identity, dict):
        raise L.LedgerError("attempt identity must be an object")
    ident = {k: identity.get(k) for k in L.IDENTITY_FIELDS if k in identity}
    L.validate_attempt_identity(ident)
    return ident


def _fence(fence):
    if fence is None:
        from manhattan import config as mconfig
        return roles.Fence.from_config(mconfig.load())
    if not isinstance(fence, roles.Fence):
        raise AccessError("a fence is a roles.Fence")
    return fence


def register_evaluation(ledger: L.Ledger, *, identity: dict, windows, caller: str, fence: roles.Fence | None = None,
                        freeze: date | None = None, holding: int = 0, token: roles.RunnerToken | None = None,
                        supersedes: str | None = None) -> AttemptContext:
    """Register one engine evaluation in the Manhattan ``Ledger`` and return its context.

    ``fence`` defaults to ``config/manhattan.yaml`` (main's copy in production). The start record is fsynced
    before this returns; a retry names the interrupted attempt in ``supersedes`` (identical identity and
    authorization, known code identity)."""
    if not isinstance(ledger, L.Ledger) or isinstance(ledger, L.PublicIndex):
        raise AccessError("engine attempts are registered in the full Manhattan ledger")
    ident = _identity(identity)
    fence = _fence(fence)
    dws = tuple(DeclaredWindow.from_any(w) for w in windows)
    check_declaration("engine_evaluation", ident, dws, caller=caller, fence=fence, freeze=freeze, holding=holding,
                      token=token)
    auth = authorization("engine_evaluation", dws, caller=caller, fence=fence, freeze=freeze, holding=holding,
                         token=token)
    rec = ledger.start_evaluation({**ident, "attempt_schema": L.ATTEMPT_SCHEMA, "kind": "engine_evaluation",
                                   "authorization": auth}, supersedes=supersedes)
    return AttemptContext(_key=_CTX_KEY, backend=_LedgerBackend(ledger), attempt_id=rec["hash"],
                          kind="engine_evaluation", identity=ident, windows=dws, caller=caller, fence=fence,
                          freeze=freeze, holding=holding, token=token)


# ---------------------------------------------------------------- the operational Store (screening, forward)

STORE_START, STORE_TERMINAL = "attempt_started", "attempt_terminal"
STORE_TERMINAL_TYPES = {"completed": "attempt_completed", "failed": "attempt_failed", "aborted": "attempt_aborted"}
SUBJECT_KEYS = {"forward_observation": ("prediction", "asof"), "screening": ("window",)}


def store_attempt_id(payload: dict) -> str:
    return hashlib.sha256(S.canonical_bytes(payload)).hexdigest()


class _StoreBackend:
    def __init__(self, store):
        self.store = store

    def is_active(self, attempt_id: str) -> bool:
        return self.store.get((STORE_START, attempt_id)) is not None and \
            self.store.get((STORE_TERMINAL, attempt_id)) is None

    def terminal(self, attempt_id, status, reason, data_read):
        it = terminal_intent(attempt_id, status, reason=reason, data_read=data_read)
        self.store.write([it], f"attempt {status} {attempt_id[:12]}")
        return self.store.get((STORE_TERMINAL, attempt_id))


@dataclass(frozen=True)
class StoreAttempt:
    """What one operational attempt declares; ``register_store_attempts`` turns a list of these into contexts in
    one journalled write."""
    kind: str
    identity: dict
    windows: tuple
    subject: dict
    freeze: date | None = None
    holding: int = 0
    caller: str = roles.RUNNER


def start_payload(a: StoreAttempt, *, fence: roles.Fence, run_id: str, run_attempt: int, nonce: str,
                  retry_of: str | None) -> tuple[dict, tuple]:
    ident = _identity(a.identity)
    if not isinstance(a.subject, dict) or set(a.subject) != set(SUBJECT_KEYS.get(a.kind, ())) or \
            any(not isinstance(v, str) or not v for v in a.subject.values()):
        raise AccessError("an operational attempt names its subject")
    dws = tuple(DeclaredWindow.from_any(w) for w in a.windows)
    check_declaration(a.kind, ident, dws, caller=a.caller, fence=fence, freeze=a.freeze, holding=a.holding,
                      token=None)
    payload = {"attempt_schema": L.ATTEMPT_SCHEMA, "kind": a.kind, "identity": ident, "subject": dict(a.subject),
               "authorization": authorization(a.kind, dws, caller=a.caller, fence=fence, freeze=a.freeze,
                                              holding=a.holding, token=None),
               "run": {"run_id": str(run_id), "run_attempt": int(run_attempt)}, "nonce": nonce,
               "retry_of": retry_of}
    return payload, dws


def comparable(payload: dict) -> dict:
    """What a retry must repeat exactly: everything but the run, the nonce and the retry link."""
    return {k: v for k, v in payload.items() if k not in ("run", "nonce", "retry_of")}


def retry_candidates(store) -> dict:
    """Interrupted (aborted: interrupted) attempts not yet retried, by their comparable identity."""
    retried = {r["payload"].get("retry_of") for r in store.of_type(STORE_START)}
    out = {}
    for r in store.of_type(STORE_START):
        aid = r["key"][1]
        t = store.get((STORE_TERMINAL, aid))
        if t is not None and t["type"] == "attempt_aborted" and t["payload"].get("reason") == "interrupted" \
                and aid not in retried:
            out.setdefault(S.canonical_bytes(comparable(r["payload"])), aid)
    return out


def register_store_attempts(store, attempts: list[StoreAttempt], *, fence: roles.Fence | None = None,
                            label: str = "attempts") -> list[AttemptContext]:
    """Validate every declaration, then write all starts in one journalled write, verified on the remote before
    this returns. A later execution of an interrupted attempt's exact identity names it in ``retry_of``."""
    from manhattan.ops import blinding
    from manhattan.ops import store as ST
    fence = _fence(fence)
    retry = retry_candidates(store)
    intents, made = [], []
    for a in attempts:
        nonce = blinding.nonce()
        probe, dws = start_payload(a, fence=fence, run_id=store.run_id, run_attempt=store.run_attempt,
                                   nonce=nonce, retry_of=None)
        prior = retry.pop(S.canonical_bytes(comparable(probe)), None)
        payload = {**probe, "retry_of": prior}
        aid = store_attempt_id(payload)
        intents.append(ST.Intent(STORE_START, (STORE_START, aid), payload, source="runner"))
        made.append((aid, a, payload, dws))
    if intents:
        store.write(intents, label)
    return [AttemptContext(_key=_CTX_KEY, backend=_StoreBackend(store), attempt_id=aid, kind=a.kind,
                           identity=payload["identity"], windows=dws, caller=a.caller, fence=fence,
                           freeze=a.freeze, holding=a.holding, token=None)
            for aid, a, payload, dws in made]


def terminal_intent(attempt_id: str, status: str, *, reason: str | None = None, data_read: bool | None,
                    results: list | None = None):
    """A terminal of an operational attempt: one key per attempt, so a second, different terminal is a conflict."""
    from manhattan.ops import store as ST
    if status not in STORE_TERMINAL_TYPES:
        raise AccessError("terminal status is completed, failed or aborted")
    if status == "completed":
        if reason is not None or data_read is not True or not isinstance(results, list):
            raise AccessError("a completion read its window and lists its results")
    elif reason not in L.TERMINAL_REASONS or results is not None:
        raise AccessError("a failed or aborted attempt gives a reason class and no results")
    if data_read is not None and type(data_read) is not bool:
        raise AccessError("data_read is a boolean, or unknown (null) for a recovered interruption")
    payload = {"attempt_id": attempt_id, "status": status, "reason": reason, "data_read": data_read,
               "results": results if status == "completed" else []}
    return ST.Intent(STORE_TERMINAL_TYPES[status], (STORE_TERMINAL, attempt_id), payload, source="runner")


def completion(ctx: AttemptContext, store, result_intents: list):
    """The completed terminal of ``ctx``, linking each result by key, content hash and disposition (``new``,
    ``duplicate`` or ``conflict`` against what the Store already holds). Write it in the same ``Store.write`` as
    the results: one journal entry, so a crash leaves both or neither."""
    from manhattan.ops import store as ST
    if not isinstance(ctx, AttemptContext) or ctx.kind not in ("screening", "forward_observation"):
        raise AccessError("an operational completion belongs to an operational attempt")
    ctx._require_active()
    if not ctx.data_read:
        raise AccessError("an attempt that read nothing cannot complete")
    links = []
    for it in result_intents:
        h = ST.content_hash(it.type, it.key, ST._canon(it.payload))
        have = store.get(it.key)
        disp = "new" if have is None else (
            "duplicate" if ST.content_hash(have["type"], have["key"], have["payload"]) == h else "conflict")
        links.append({"key": [str(k) for k in it.key], "type": it.type, "content_hash": h, "disposition": disp})
    ctx._mark_completed()
    return terminal_intent(ctx.attempt_id, "completed", data_read=True, results=links)


def recover_interrupted(store, kinds: tuple = ("forward_observation",)) -> list:
    """Terminals closing every unfinished attempt of ``kinds`` as aborted (reason ``interrupted``, ``data_read``
    unknown). Call only while holding the Store lock and **before** registering anything in this process: every
    unfinished attempt is then a dead process's, whatever run identity it carries (a local rerun can reuse one).
    The nightly runner recovers forward observations, the only lock-protected kind; screening takes no lock, so an
    operator closes interrupted screening attempts with ``kinds=("screening",)`` while no screening runs."""
    if not kinds or any(k not in KINDS for k in kinds):
        raise AccessError("recover known operational attempt kinds")
    out = []
    for r in store.of_type(STORE_START):
        aid = r["key"][1]
        if store.get((STORE_TERMINAL, aid)) is None and r["payload"].get("kind") in kinds:
            out.append(terminal_intent(aid, "aborted", reason="interrupted", data_read=None))
    return out
