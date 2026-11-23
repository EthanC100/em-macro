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
import hmac
import json
import re
import secrets
import weakref
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
_PROOF_KEY = secrets.token_bytes(32)        # completion proofs (Ledger) and sealed writes (Store); never persisted


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


_ALLOWED_READS: dict = {}
_ALLOWED_READS_MAX = 4096


def _allowed_role(caller: str, dw: DeclaredWindow, *, fence: roles.Fence, freeze: date | None, holding: int,
                  token) -> str:
    """``roles.check_read`` for one declared window, remembering allowed token-free reads (Manhattan phase 3).

    ``check_read`` is a pure function of its arguments: it walks every day of the window (about 2 ms for an 8.8-year
    window), which dominated registering and reconciling large batches of attempts on one window. The decision is
    never changed; only its repetition is saved, under these rules (independent security review, PR #100):

    * Only an *allowed* read without a token is remembered. A refusal, a reserve read (token), a fence that is not a
      ``roles.Fence``, or anything whose key cannot be built is decided by ``check_read`` itself, every time.
    * Only exact built-in types are remembered (``str`` caller, domain and window ID; ``date`` dates, never a
      subclass; ``bool`` enabled flag; ``int`` holding; the domain's reserve window a 2-tuple of ``date`` or absent).
      Anything else, including a subclass that could lie about its value, is decided without the memo.
    * The key holds exactly what ``check_read`` reads: the caller, the window, the freeze and holding, and from the
      fence only ``exploration_end``, ``enabled`` and the reserve window *of this domain* (``role_of`` reads
      ``fence.reserve.get(domain)`` and nothing else of the reserve). It also holds the identity of ``check_read``,
      ``role_of``, ``_busdays_between`` and ``_day`` and the values of the ``roles`` settings they read, so a replaced
      function or a tightened setting is never bypassed.
    * The decision is made on a snapshot fence built from the same values as the key, so a reserve mapping changed
      by another thread mid-call cannot store one content's decision under another content's key."""
    def decide(f) -> str:
        return roles.check_read(caller, dw.domain, dw.start, dw.end, f, freeze=freeze, holding=holding,
                                token=token, window_id=dw.id)
    if token is not None or type(fence) is not roles.Fence:
        return decide(fence)
    try:
        enabled, exploration_end = fence.enabled, fence.exploration_end
        w = fence.reserve.get(dw.domain) if type(fence.reserve) is dict and type(dw.domain) is str else ...
        exact = (w is not ... and type(caller) is str and type(dw.id) is str and type(enabled) is bool
                 and type(exploration_end) is date and type(dw.start) is date and type(dw.end) is date
                 and (freeze is None or type(freeze) is date) and type(holding) is int
                 and (w is None or (type(w) is tuple and len(w) == 2 and all(type(x) is date for x in w))))
        if not exact:
            return decide(fence)
        key = (roles.check_read, roles.role_of, roles._busdays_between, roles._day, roles.MAX_READ_DAYS,
               roles.CALLERS, roles.NO_DATA, roles.RUNNER, roles.EXPLORATION, roles.RESERVE, roles.FORWARD,
               roles.EMBARGO, caller, dw.domain, dw.id, dw.start, dw.end, freeze, holding, exploration_end, enabled, w)
        hash(key)
    except Exception:                                    # noqa: BLE001 - whatever cannot be keyed is decided anew
        return decide(fence)
    role = _ALLOWED_READS.get(key)
    if role is None:
        snapshot = roles.Fence(exploration_end=exploration_end, reserve={} if w is None else {dw.domain: w},
                               enabled=enabled)
        role = decide(snapshot)
        if len(_ALLOWED_READS) >= _ALLOWED_READS_MAX:
            _ALLOWED_READS.clear()
        _ALLOWED_READS[key] = role
    return role


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
    role = _allowed_role(caller, dw, fence=fence, freeze=freeze, holding=holding, token=token)
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
    if ev.role == roles.RESERVE and identity["designated"] is not True:
        raise AccessError("a reserve attempt is its batch's designated evaluation of the domain; non-designated "
                          "reserve reads have no permitted lifecycle (S7 N1)")
    if ev.role == roles.RESERVE:
        # S7 M6: the token is bound to the attempt it authorizes: its batch, a manifest, the specification and the
        # declared (domain, window) pair (the last also checked by roles.check_read).
        if not isinstance(token, roles.RunnerToken) or token.verified is not True:
            raise AccessError("a reserve attempt needs a verified batch token")
        if token.batch != identity["batch"]:
            raise AccessError("the reserve token's batch is not the attempt's batch")
        if not isinstance(token.manifest_hash, str) or re.fullmatch(r"[0-9a-f]{64}", token.manifest_hash) is None:
            raise AccessError("the reserve token names its manifest hash")
        if identity["spec_hash"] not in token.specs:
            raise AccessError("the reserve token does not name this specification")
        if (ev.domain, ev.id) not in token.designated:
            raise AccessError("the reserve token does not name this (domain, window)")
    elif token is not None:
        raise AccessError("only a reserve attempt carries a batch token")
    for w in windows:
        _role_now(kind, w, caller=caller, fence=fence, freeze=freeze, holding=holding, token=token)


CONFIG_PATH = "config/manhattan.yaml"


def _fence_key(fence: roles.Fence) -> str:
    return json.dumps({"exploration_end": fence.exploration_end.isoformat(), "enabled": bool(fence.enabled),
                       "reserve": {d: [w[0].isoformat(), w[1].isoformat()] for d, w in sorted(fence.reserve.items())}},
                      sort_keys=True, separators=(",", ":"))


class VerifiedFence:
    """The capability forward registration requires (S7 F1): a fence produced only by ``verified_fence``, bound to
    the configuration's SHA-256 and the commit it was verified against. A ``roles.Fence`` or a 64-hex string alone
    proves nothing. The binding is an in-process MAC: it protects the supported API from substitution, not against
    hostile code in the process (section 1); the reconciler re-verifies every recorded claim independently."""
    __slots__ = ("fence", "config_sha256", "commit", "_tag")

    def __init__(self, *, _key, fence: roles.Fence, config_sha256: str, commit: str):
        if _key is not _CTX_KEY:
            raise AccessError("a verified fence is produced by access.verified_fence only")
        self.fence, self.config_sha256, self.commit = fence, config_sha256, commit
        self._tag = _mac("verified-fence", _fence_key(fence), config_sha256, commit)

    def valid(self) -> bool:
        return isinstance(self.fence, roles.Fence) and hmac.compare_digest(
            self._tag, _mac("verified-fence", _fence_key(self.fence), self.config_sha256, self.commit))

    def record(self) -> dict:
        return {"sha256": self.config_sha256, "commit": self.commit}

    def __reduce_ex__(self, protocol):
        raise AccessError("a verified fence cannot be serialized")

    def __copy__(self):
        raise AccessError("a verified fence cannot be copied")

    def __deepcopy__(self, memo):
        raise AccessError("a verified fence cannot be copied")


def _git_config(commit: str, root) -> bytes:
    import subprocess
    if not isinstance(commit, str) or re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", commit) is None or set(commit) == {"0"}:
        raise AccessError("the configuration is pinned by a known commit")
    try:
        return subprocess.run(["git", "show", f"{commit}:{CONFIG_PATH}"], cwd=root, capture_output=True,
                              check=True, timeout=60).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise AccessError("the configuration at the registered commit is unavailable") from exc


def _fence_of(raw: bytes) -> roles.Fence:
    try:
        from manhattan import config as mconfig
        data = mconfig.loads(raw.decode("utf-8"))      # yaml.safe_load, refusing a repeated key
        return roles.Fence.from_config(data)
    except Exception as exc:                             # noqa: BLE001 - any parse or shape error fails closed
        raise AccessError("the configuration cannot be read as a fence") from exc


def _repo_root(root=None):
    from pathlib import Path
    return Path(root) if root is not None else Path(__file__).resolve().parents[1]


def verified_fence(commit: str, *, root=None, expected_sha256: str | None = None) -> VerifiedFence:
    """The fence from the authoritative configuration, verified against its pinned identity (owner decision D-12).

    The working ``config/manhattan.yaml`` must be byte-identical to that file at ``commit`` (the attempt's registered
    code identity: ``git show <commit>:config/manhattan.yaml``) and, if ``expected_sha256`` is given, hash to it. It
    is parsed with ``yaml.safe_load``. Anything unavailable, unparseable or mismatched raises ``AccessError``.
    Returns the ``VerifiedFence`` capability (S7 F1), the only way to register a forward observation."""
    root = _repo_root(root)
    pinned = _git_config(commit, root)
    try:
        raw = (root / CONFIG_PATH).read_bytes()
    except OSError as exc:
        raise AccessError("the configuration is unavailable") from exc
    sha = hashlib.sha256(raw).hexdigest()
    if raw != pinned:
        raise AccessError("the configuration differs from its version at the registered commit")
    if expected_sha256 is not None and expected_sha256 != sha:
        raise AccessError("the configuration does not match its pinned SHA-256")
    return VerifiedFence(_key=_CTX_KEY, fence=_fence_of(raw), config_sha256=sha, commit=commit)


def verify_recorded_config(auth: dict, identity: dict, root=None, _cache: dict | None = None) -> None:
    """The reconciler's independent check of a recorded configuration claim (S7 F1): the recorded commit is the
    attempt's code-identity commit, the configuration at that commit hashes to the recorded SHA-256, and the fence
    it yields is the recorded fence for the domain. Raises ``AccessError``; a syntactically valid hash proves
    nothing by itself."""
    cfg = auth.get("config") if isinstance(auth, dict) else None
    if not isinstance(cfg, dict) or set(cfg) != {"sha256", "commit"}:
        raise AccessError("no configuration claim to verify")
    if cfg["commit"] != (identity.get("code_version") or {}).get("commit"):
        raise AccessError("the configuration was verified against another commit than the attempt's")
    key = cfg["commit"]
    if _cache is not None and key in _cache:
        raw = _cache[key]
    else:
        raw = _git_config(cfg["commit"], _repo_root(root))
        if _cache is not None:
            _cache[key] = raw
    if hashlib.sha256(raw).hexdigest() != cfg["sha256"]:
        raise AccessError("the recorded configuration hash is not the configuration at that commit")
    domain = next(w["domain"] for w in auth["windows"] if w.get("purpose") == "evaluation")
    if fence_snapshot(_fence_of(raw), domain) != auth["fence"]:
        raise AccessError("the recorded fence is not the fence of that configuration")


def _token_snapshot(token, identity: dict) -> dict | None:
    if token is None:
        return None
    return {"batch": str(token.batch), "manifest_hash": str(token.manifest_hash), "spec_hash": identity["spec_hash"]}


def authorization(kind, windows, *, caller, fence, freeze, holding, token, identity: dict,
                  config: dict | None = None) -> dict:
    """``config``: ``{"sha256", "commit"}`` of the verified configuration the fence came from (D-12, F1); ``None``
    when the caller supplied the fence (synthetic and engine tests), which the reconciler reports as unpinned."""
    domain = next(w.domain for w in windows if w.purpose == "evaluation")
    return {"caller": caller, "windows": [w.as_dict() for w in windows], "fence": fence_snapshot(fence, domain),
            "freeze": None if freeze is None else freeze.isoformat(), "holding": holding,
            "token": _token_snapshot(token, identity), "config": config}


def check_recorded(kind: str, identity: dict, auth: dict) -> None:
    """Re-validate a persisted authorization from its own fence snapshot (the reconciler's check). The recorded
    token's signature or tag cannot be re-verified here: a reserve window is checked for role, fence, and the
    token's recorded binding to the attempt's batch, specification and window. The configuration claim is only
    checked for shape here; ``verify_recorded_config`` verifies it."""
    if not isinstance(auth, dict) or set(auth) != {"caller", "windows", "fence", "freeze", "holding", "token",
                                                   "config"}:
        raise AccessError("malformed authorization")
    c = auth["config"]
    if c is not None and (not isinstance(c, dict) or set(c) != {"sha256", "commit"}
                          or not isinstance(c["sha256"], str) or re.fullmatch(r"[0-9a-f]{64}", c["sha256"]) is None
                          or not isinstance(c["commit"], str)):
        raise AccessError("malformed configuration claim")
    if kind == "forward_observation" and c is None:
        raise AccessError("a forward observation records the verified configuration it was fenced by (D-12)")
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
        if set(t) != {"batch", "manifest_hash", "spec_hash"}:
            raise AccessError("malformed reserve token record")
        token = roles.RunnerToken(t["batch"], t["manifest_hash"], True, frozenset({(ev.domain, ev.id)}),
                                  frozenset({t["spec_hash"]}))
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
        self._meter.alive = self._may_read          # every protected read re-checks this (S7 H2)
        self._ended = False
        self._computing = False

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

    def _may_read(self) -> bool:
        """An operational attempt's windows are read only inside its one computation (``run_bound``, S7 F2), so
        no other strategy can read them; an engine evaluation's window is read by ``engine.evaluate``."""
        return self.active() and (self.kind == "engine_evaluation" or self._computing)

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

    def _completion_proof(self, result_hash: str) -> CompletionProof:
        """For ``engine.evaluate`` only: the attempt is active and has read its window."""
        if self.kind != "engine_evaluation" or not isinstance(self._backend, _LedgerBackend):
            raise AccessError("only an engine evaluation completes in the Ledger")
        self._require_active()
        if not self.data_read:
            raise AccessError("an attempt that read nothing cannot complete")
        return CompletionProof(_key=_CTX_KEY, attempt_id=self.attempt_id, result_hash=result_hash,
                               ledger_id=id(self._backend.ledger))

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
        _BOUND.pop(self.attempt_id, None)
        return out

    def _mark_completed(self) -> None:
        self._ended = True


# ---------------------------------------------------------------- the Ledger (engine evaluations)

def _one_designated(ledger: L.Ledger, batch: str, dws: tuple, supersedes: str | None) -> None:
    """D-6 and D-13, conservatively: one reserve attempt per (batch, domain), and it is the designated evaluation
    (S7 N1: a reserve attempt is never non-designated). A second registration is refused unless it retries
    (``supersedes``) the one unfinished earlier attempt of that pair. A failed, aborted or completed attempt
    consumes the designation, **even if it failed before any read** (owner decision D-13): it is never released or
    recycled."""
    domain = next(w.domain for w in dws if w.purpose == "evaluation")
    prior = ledger.designated_reserve_starts(batch, domain)
    if not prior:
        return
    if supersedes is not None and supersedes in prior and all(
            h == supersedes or ledger.is_superseded(h) for h in prior):
        return
    raise AccessError(f"batch {batch} already has its designated reserve evaluation for {domain} (D-6)")


class CompletionProof:
    """What ``Ledger.record_evaluation`` needs to write a reserve or forward completion: minted only by an active
    attempt that has read its window, for one result, and used once (S7 M5). An attempt ID alone is not enough."""
    __slots__ = ("attempt_id", "result_hash", "ledger_id", "mac", "used")

    def __init__(self, *, _key, attempt_id: str, result_hash: str, ledger_id: int):
        if _key is not _CTX_KEY:
            raise AccessError("completion proofs are minted by an attempt only")
        self.attempt_id, self.result_hash, self.ledger_id, self.used = attempt_id, result_hash, ledger_id, False
        self.mac = _mac("completion", attempt_id, result_hash, ledger_id)

    def __reduce_ex__(self, protocol):
        raise AccessError("a completion proof cannot be serialized")

    def __copy__(self):
        raise AccessError("a completion proof cannot be copied")

    def __deepcopy__(self, memo):
        raise AccessError("a completion proof cannot be copied")


def _mac(*parts) -> str:
    return hmac.new(_PROOF_KEY, repr(parts).encode("utf-8"), hashlib.sha256).hexdigest()


def verify_completion(proof, *, attempt_id: str | None, result_hash: str, ledger: L.Ledger) -> None:
    """Called by ``Ledger.record_evaluation`` for every reserve or forward completion; consumes the proof."""
    if (not isinstance(proof, CompletionProof) or proof.used or attempt_id is None
            or (proof.attempt_id, proof.result_hash, proof.ledger_id) != (attempt_id, result_hash, id(ledger))
            or not hmac.compare_digest(proof.mac, _mac("completion", attempt_id, result_hash, id(ledger)))):
        raise L.LedgerError("a reserve or forward completion needs its attempt's completion proof (engine.evaluate)")
    proof.used = True


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
    """An explicit fence. There is no silent default: the authoritative one comes from ``verified_fence`` (D-12)."""
    if not isinstance(fence, roles.Fence):
        raise AccessError("an operational attempt needs an explicit fence (access.verified_fence for forward runs)")
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
    config = None
    if fence is None:                                    # the authoritative configuration, verified (D-12)
        fence = verified_fence(ident["code_version"]["commit"])
    if isinstance(fence, VerifiedFence):
        if not fence.valid() or fence.commit != ident["code_version"]["commit"]:
            raise AccessError("the verified fence is not this attempt's (commit) or was altered")
        config, fence = fence.record(), fence.fence
    elif not isinstance(fence, roles.Fence):
        raise AccessError("a fence is a roles.Fence or an access.VerifiedFence")
    dws = tuple(DeclaredWindow.from_any(w) for w in windows)
    check_declaration("engine_evaluation", ident, dws, caller=caller, fence=fence, freeze=freeze, holding=holding,
                      token=token)
    auth = authorization("engine_evaluation", dws, caller=caller, fence=fence, freeze=freeze, holding=holding,
                         token=token, identity=ident, config=config)
    if ident["role"] == roles.RESERVE:
        _one_designated(ledger, ident["batch"], dws, supersedes)
    rec = ledger.start_evaluation({**ident, "attempt_schema": L.ATTEMPT_SCHEMA, "kind": "engine_evaluation",
                                   "authorization": auth}, supersedes=supersedes)
    return AttemptContext(_key=_CTX_KEY, backend=_LedgerBackend(ledger), attempt_id=rec["hash"],
                          kind="engine_evaluation", identity=ident, windows=dws, caller=caller, fence=fence,
                          freeze=freeze, holding=holding, token=token)


# ---------------------------------------------------------------- the operational Store (screening, forward)

STORE_START, STORE_TERMINAL = "attempt_started", "attempt_terminal"
STORE_TERMINAL_TYPES = {"completed": "attempt_completed", "failed": "attempt_failed", "aborted": "attempt_aborted"}
SUBJECT_KEYS = {"forward_observation": ("prediction", "asof", "sources"), "screening": ("window",)}


def store_attempt_id(payload: dict) -> str:
    return hashlib.sha256(S.canonical_bytes(payload)).hexdigest()


class _StoreBackend:
    def __init__(self, store, require_lock: bool = False):
        self.store, self.require_lock = store, require_lock

    def is_active(self, attempt_id: str) -> bool:
        return self.store.get((STORE_START, attempt_id)) is not None and \
            self.store.get((STORE_TERMINAL, attempt_id)) is None

    def terminal(self, attempt_id, status, reason, data_read):
        it = terminal_intent(attempt_id, status, reason=reason, data_read=data_read)
        _sealed_write(self.store, [it], f"attempt {status} {attempt_id[:12]}", self.require_lock)
        return self.store.get((STORE_TERMINAL, attempt_id))


# ---- sealed writes: the only way a protected record type reaches the Store through its public API (S7 M5)

def _store_mac(intents, label: str) -> str:
    return _mac("store", label, [S.canonical_bytes(it.as_dict()).decode("utf-8") for it in intents])


def store_seal_ok(seal, intents, label: str) -> bool:
    """Called by ``Store.write`` when a batch holds a protected record type."""
    return isinstance(seal, str) and hmac.compare_digest(seal, _store_mac(intents, label))


def _sealed_write(store, intents: list, label: str, require_lock: bool) -> dict:
    return store.write(intents, label, sealed=_store_mac(intents, label), require_lock=require_lock)


_MINTED: dict[int, tuple] = {}                     # completions minted by ``completion``, until committed


def epoch_intent():
    """The record after which every protected Store result must be linked to a registered attempt."""
    from manhattan.ops import store as ST
    return ST.Intent("accounting_epoch", ("accounting_epoch", str(L.ATTEMPT_SCHEMA)),
                     {"attempt_schema": L.ATTEMPT_SCHEMA})


def commit_recovery(store, *, kinds: tuple = ("forward_observation",), epoch: bool = False,
                    require_lock: bool = True) -> int:
    """Write the recovery terminals of ``recover_interrupted`` (and the accounting epoch once). Returns how many
    attempts were closed. With ``require_lock`` the write is refused unless this run still holds the Store lock."""
    its = recover_interrupted(store, kinds)
    if epoch and store.get(("accounting_epoch", str(L.ATTEMPT_SCHEMA))) is None:
        its = its + [epoch_intent()]
    if its:
        _sealed_write(store, its, "attempt recovery", require_lock)
    return sum(1 for it in its if it.type == "attempt_aborted")


def commit_failures(store, ctxs: list, *, require_lock: bool = False) -> int:
    """Close every listed attempt still without a terminal as ``failed: execution_error`` (reason class only)."""
    its = [terminal_intent(c.attempt_id, "failed", reason="execution_error", data_read=c.data_read)
           for c in ctxs if store.get((STORE_TERMINAL, c.attempt_id)) is None
           and c.attempt_id not in _COMMIT_PENDING]
    for c in ctxs:
        c._ended = True
    if its:
        _sealed_write(store, its, "attempts failed", require_lock)
    return len(its)


def commit_results(store, results: list, completions: list, label: str, *, require_lock: bool = False) -> dict:
    """Write results and their attempts' completions in one journalled write, after checking that every protected
    result in the batch is linked, with its exact content, by exactly one completion minted here, and that every
    new or conflicting link names a result of the batch. A crash leaves both or neither."""
    from manhattan.ops import store as ST
    linked: dict[tuple, str] = {}
    for c in completions:
        rec = _MINTED.get(id(c))
        if rec is None or rec[0] != S.canonical_bytes(c.as_dict()):
            raise AccessError("a completion was not minted by access.completion, or was altered")
        for link in c.payload["results"]:
            k = tuple(link["key"])
            if k in linked:
                raise AccessError("a result is linked by two completions")
            linked[k] = link["content_hash"]
    batch = {}
    for it in results:
        if it.type not in ST.PROTECTED_TYPES or it.type.startswith("attempt_") or it.type == "accounting_epoch":
            raise AccessError("commit_results writes result records only")
        h = ST.content_hash(it.type, it.key, ST._canon(it.payload))
        if linked.get(tuple(it.key)) != h:
            raise AccessError("a result is not linked, with this content, by a completion of the batch")
        batch[tuple(it.key)] = h
    for c in completions:
        for link in c.payload["results"]:
            if link["disposition"] in ("new", "conflict") and tuple(link["key"]) not in batch:
                raise AccessError("a completion links a new result that is not in the batch")
    intents = list(results) + list(completions)
    try:
        out = _sealed_write(store, intents, label, require_lock)
    except Exception:
        _settle_failed_commit(store, intents, label, [_MINTED[id(c)][1] for c in completions])
        raise
    for c in completions:
        _MINTED.pop(id(c), None)
    return out


_COMMIT_PENDING: set = set()       # attempts whose completion may still be applied from the journal (S7 N8)


def _settle_failed_commit(store, intents: list, label: str, attempt_ids: list) -> None:
    """S7 N8. A results write failed. Before anyone may write another terminal for these attempts, find out where
    their completion stands: reset the clone to the remote (dropping any half-applied local state); if the
    results entry reached the remote journal, finish it now, or leave it for the next run's journal recovery,
    and in either case never write a failed terminal for these attempts in this process. Only if the entry
    provably never left this process may ``commit_failures`` close them as failed."""
    try:
        store._reset_to_remote()
        pushed = any(j["entry"] == store.entry_id(intents, label) for j in store.journal())
    except Exception:                                    # noqa: BLE001 - unknown state: leave it to recovery
        _COMMIT_PENDING.update(attempt_ids)
        return
    if not pushed:
        return
    try:
        store.reconcile()                                # idempotent; the entry was written under the lock
    except Exception:                                    # noqa: BLE001 - the next run's journal recovery finishes it
        pass
    _COMMIT_PENDING.update(attempt_ids)


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


def start_payload(a: StoreAttempt, *, fence, run_id: str, run_attempt: int, nonce: str,
                  retry_of: str | None) -> tuple[dict, tuple]:
    """``fence``: a ``VerifiedFence`` (required for forward observations, S7 F1) or, for screening, a fence."""
    ident = _identity(a.identity)
    if not isinstance(a.subject, dict) or set(a.subject) != set(SUBJECT_KEYS.get(a.kind, ())) or \
            any(not isinstance(v, str) or not v for v in a.subject.values()):
        raise AccessError("an operational attempt names its subject")
    dws = tuple(DeclaredWindow.from_any(w) for w in a.windows)
    config = None
    if isinstance(fence, VerifiedFence):
        if not fence.valid():
            raise AccessError("the verified fence was altered")
        if fence.commit != ident["code_version"]["commit"]:
            raise AccessError("the fence was verified against another commit than the attempt's code identity")
        config, fence = fence.record(), fence.fence
    elif a.kind == "forward_observation":
        raise AccessError("a forward observation needs the verified fence capability (access.verified_fence)")
    elif not isinstance(fence, roles.Fence):
        raise AccessError("a fence is a roles.Fence or an access.VerifiedFence")
    check_declaration(a.kind, ident, dws, caller=a.caller, fence=fence, freeze=a.freeze, holding=a.holding,
                      token=None)
    payload = {"attempt_schema": L.ATTEMPT_SCHEMA, "kind": a.kind, "identity": ident, "subject": dict(a.subject),
               "authorization": authorization(a.kind, dws, caller=a.caller, fence=fence, freeze=a.freeze,
                                              holding=a.holding, token=None, identity=ident, config=config),
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


def register_store_attempts(store, attempts: list[StoreAttempt], *, fence=None,
                            label: str = "attempts", require_lock: bool = False) -> list[AttemptContext]:
    """Validate every declaration, then write all starts in one journalled write, verified on the remote before
    this returns. A later execution of an interrupted attempt's exact identity names it in ``retry_of``. With
    ``require_lock`` (the nightly runner) every write of these attempts is refused unless the run still holds the
    Store lock."""
    from manhattan.ops import blinding
    from manhattan.ops import store as ST
    if not isinstance(fence, VerifiedFence):
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
        _sealed_write(store, intents, label, require_lock)
    backend = _StoreBackend(store, require_lock)
    plain = fence.fence if isinstance(fence, VerifiedFence) else fence
    return [AttemptContext(_key=_CTX_KEY, backend=backend, attempt_id=aid, kind=a.kind,
                           identity=payload["identity"], windows=dws, caller=a.caller, fence=plain,
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


RESULT_TYPES = {"forward_observation": ("observation", "missed_observation"), "screening": ("screening",)}
_BOUND: dict[str, object] = {}     # attempt ID -> the backtest result computed by run_bound (S7 N2)


_COMPUTED: set = set()             # attempts whose one computation has begun (S7 F2)


def run_bound(ctx: AttemptContext, window: pit.Window, executable):
    """The attempt's one computation (S7 N2, F2). ``executable`` is the compiled executable: its four specs are
    re-linked and recompiled here (``compiler.from_specs``) and must be the attempt's registered identity
    (specification hash, executable, variant, hypothesis and family IDs), so the strategy is the registered one,
    never a caller's. A second computation under the same attempt is refused, even with the same strategy, and the
    computation is recorded as begun before it runs: a failure part-way leaves the attempt computed (its terminal
    states the read). The window must be the attempt's own; it is readable only during this computation."""
    from manhattan.engine import backtest
    from manhattan.ops import compiler as CP
    if not isinstance(ctx, AttemptContext) or ctx.kind not in RESULT_TYPES:
        raise AccessError("only an operational attempt binds a computation")
    ctx._require_active()
    if ctx.attempt_id in _COMPUTED:
        raise AccessError("this attempt has already computed once; a second computation is never bound")
    purpose = "forward_observation" if ctx.kind == "forward_observation" else "evaluation"
    if (window.attempt_id, window.window_id, window.purpose) != (ctx.attempt_id, ctx.evaluation_window.id, purpose):
        raise AccessError("the window is not this attempt's own")
    try:
        x = CP.from_specs(executable.executable, executable.variant, executable.hypothesis, executable.family)
    except Exception as exc:                             # noqa: BLE001 - anything that is not the specs fails closed
        raise AccessError("the executable's specs do not compile") from exc
    ident = ctx.identity
    if (S.spec_hash(x.executable), x.id, S.spec_id(x.variant), S.spec_id(x.hypothesis), S.spec_id(x.family)) != (
            ident["spec_hash"], ident["executable"], ident["variant"], ident["hypothesis"], ident["family"]):
        raise AccessError("the executable is not the attempt's registered specification")
    _COMPUTED.add(ctx.attempt_id)
    ctx._computing = True
    try:
        res = backtest.run(window, x.strategy())
    finally:
        ctx._computing = False
    _BOUND[ctx.attempt_id] = (res, x)
    return res


def observation_values(res, i: int) -> dict:
    """The computed fields of one forward observation (day ``i`` of a bound result)."""
    return {"net": round(float(res.net[i]), 12), "gross": round(float(res.gross[i]), 12),
            "cost": round(float(res.cost[i]), 12), "turnover": round(float(res.turnover[i]), 12),
            "exposure": [round(float(e), 12) for e in res.exposure[i]]}


def screening_values(res) -> dict:
    """The computed fields of one screening record."""
    return {"result_hash": res.result_hash(),
            "summary": {k: (round(v, 10) if isinstance(v, float) and v == v else None) if isinstance(v, float)
                        else v for k, v in res.summary().items()}}


def _bound_values_ok(kind: str, payload: dict, res) -> bool:
    """A result's computed values are those of the bound computation (S7 N2). Missed observations carry none."""
    if kind == "missed_observation":
        return True
    canon = lambda x: json.loads(S.canonical_bytes(x))                    # as the Store holds payloads
    if kind == "screening":
        return {k: payload.get(k) for k in ("result_hash", "summary")} == canon(screening_values(res))
    days = [str(d) for d in res.dates.astype("datetime64[D]")]
    if payload.get("date") not in days:
        return False
    want = canon(observation_values(res, days.index(payload["date"])))
    return {k: payload.get(k) for k in want} == want


def result_fits(kind: str, key, payload: dict, start: dict) -> bool:
    """A result belongs to its attempt (``start`` is the attempt's start payload): its subject and executable, its
    data identity, and a date or window inside the declared evaluation window. Used when a completion is minted
    and again by the reconciler (S7 M1)."""
    ident, subj = start["identity"], start["subject"]
    ev = next(w for w in start["authorization"]["windows"] if w["purpose"] == "evaluation")
    key = tuple(key)
    if kind not in RESULT_TYPES[start["kind"]] or not isinstance(payload, dict):
        return False
    if kind in ("observation", "missed_observation"):
        d = payload.get("date")
        ok = (isinstance(d, str) and ev["start"] < d <= subj["asof"] and payload.get("prediction") == subj["prediction"]
              and key == (kind, subj["prediction"], d))
        if kind == "observation":
            ok = ok and payload.get("executable") == ident["executable"] and payload.get("role") == "forward"
        return ok
    return (key == ("screening", ident["spec_hash"], subj["window"])
            and payload.get("executable") == ident["executable"] and payload.get("hypothesis") == ident["hypothesis"]
            and payload.get("data_hash") == ident["data_hash"] and payload.get("role") == ident["role"]
            and payload.get("window") == {"start": ev["start"], "end": ev["end"]})


_FS_CACHE: dict = {}


def _check_forward_plan(store, start: dict, res, x, result_intents: list) -> None:
    """S7 G-1. The results must be exactly the forward plan recomputed here from the Store's own captures (first
    seen, hash-checked raw files) and the registration in force: values, ``reconstructed`` provenance, eligibility,
    weight, no omitted observation and no ``missed_observation`` the captures do not justify."""
    from manhattan.ops import data as D
    from manhattan.ops import forward as FW
    from manhattan.ops import store as ST
    subj = start["subject"]
    sources = tuple(subj["sources"].split(","))
    key = (id(store), store.head, sources)
    if key not in _FS_CACHE:
        _FS_CACHE.clear()
        fs = D.first_seen(store, sources)
        _FS_CACHE[key] = (fs, fs.pit_store().data_hash())
    fs, data_hash = _FS_CACHE[key]
    if data_hash != start["identity"]["data_hash"]:
        raise AccessError("the Store's captures are not the attempt's data identity")
    reg = FW.registration_in_force(store.of_type, subj["prediction"])
    if reg is None:
        raise AccessError("the prediction has no registration in the Store")
    want, _ = FW.plan(fs, reg, x, date.fromisoformat(subj["asof"]), res)
    canon = lambda its: sorted(S.canonical_bytes({"type": i.type, "key": [str(k) for k in i.key],
                                                  "payload": ST._canon(i.payload)}) for i in its)
    if canon(result_intents) != canon(want):
        raise AccessError("the results are not the forward plan of the attempt's computation and captures "
                          "(provenance, eligibility, weight, omission or an unjustified missed observation)")


def completion(ctx: AttemptContext, store, result_intents: list):
    """The completed terminal of ``ctx``, linking each result by key, content hash and disposition (``new``,
    ``duplicate`` or ``conflict`` against what the Store already holds). Write it in the same ``Store.write`` as
    the results through ``commit_results``: one journal entry, so a crash leaves both or neither."""
    from manhattan.ops import store as ST
    if not isinstance(ctx, AttemptContext) or ctx.kind not in ("screening", "forward_observation"):
        raise AccessError("an operational completion belongs to an operational attempt")
    ctx._require_active()
    if not ctx.data_read:
        raise AccessError("an attempt that read nothing cannot complete")
    start = store.get((STORE_START, ctx.attempt_id))["payload"]
    bound = _BOUND.get(ctx.attempt_id)
    if bound is None:
        raise AccessError("an operational completion needs the attempt's bound computation (access.run_bound)")
    res, x = bound
    for it in result_intents:
        if not result_fits(it.type, it.key, ST._canon(it.payload), start):
            raise AccessError("a result does not belong to this attempt (subject, executable, data or window)")
        if not _bound_values_ok(it.type, ST._canon(it.payload), res):
            raise AccessError("a result's values are not those of the attempt's bound computation")
    if ctx.kind == "forward_observation":
        _check_forward_plan(store, start, res, x, result_intents)
    links = []
    for it in result_intents:
        h = ST.content_hash(it.type, it.key, ST._canon(it.payload))
        have = store.get(it.key)
        disp = "new" if have is None else (
            "duplicate" if ST.content_hash(have["type"], have["key"], have["payload"]) == h else "conflict")
        links.append({"key": [str(k) for k in it.key], "type": it.type, "content_hash": h, "disposition": disp})
    ctx._mark_completed()
    _BOUND.pop(ctx.attempt_id, None)
    it = terminal_intent(ctx.attempt_id, "completed", data_read=True, results=links)
    key = id(it)
    _MINTED[key] = (S.canonical_bytes(it.as_dict()), ctx.attempt_id)
    weakref.finalize(it, _MINTED.pop, key, None)
    return it


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
