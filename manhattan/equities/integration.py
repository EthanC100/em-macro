"""Integration contracts with Manhattan components still under review: exact structure, and the semantics a
structural check cannot see (S8 M9, R2).

This module does **not** import, merge or activate unfinished branches. It records, pinned to the PR heads that
were reviewed, (a) the **structural** interface the equities layer will call — function signatures by parameter
names and kinds, one schema constant, the metadata keys — and (b) the **semantic** requirements those interfaces
impose at run time. ``check_all`` verifies (a) only. **A structural match does not establish runtime
integration:** it says the names and shapes agree, not that a call made from equities code would satisfy the
attempt store, the verified fence, the designation rules or the evidence verifier. Those are listed in
``SEMANTIC_REQUIREMENTS`` and are met only by adapters written after the PRs merge, tested against the merged code.

Pinned heads (reviewed by S8, 2026-11-18):

    PR #86  claude/phase4-binding-accounting-l3ihoz   5aa643f   (previously 8615c69)
    PR #84  claude/phase4-evidence-classification     1e86b33   (previously 178c5bd; the branch has since moved to
                                                                 e1882be, which keeps every interface below)

How the equities layer will use them (no adapter is written until the PRs merge):

* **#86** — a reserve or forward read of equity data needs ``access.register_evaluation(ledger, *, identity, windows,
  caller, fence, freeze, holding, token, supersedes)`` → ``AttemptContext``; the window is opened by
  ``ctx.window(store)`` (or ``pit.Reader(..., attempt=ctx).window(...)``); ``ctx.fail(reason)`` /
  ``ctx.abort(reason)`` end it. An operational computation is bound to its attempt only through #86's runner path:
  #86 restricts ``access.run_bound`` and ``AttemptContext.forward_window`` to ``access.py``, ``ops/runner.py`` (and
  ``ops/data.py``) and checks that no other module references them, so the equities layer neither calls nor pins them
  (an equities executable would be run by the runner, which binds it).
  The fence of a forward attempt comes from ``access.verified_fence(commit, *, root, expected_sha256)`` and its
  configuration hash (``config_sha256``) is recorded with the attempt's ``authorization``. Exploration reads keep
  using ``pit.Reader(...).window(start, end)`` without an attempt (``research.open_window``).
* **#84** — every equities output would be classified by ``evidence.classify(metadata, verifications, *, fence,
  config, protocol_hash)`` → ``Classification``, with metadata of schema ``manhattan.evidence/3``, whose attempt is
  an object ``{"id": ..., "store": ...}`` under the key ``attempt`` (not ``attempt_id``). A ``Classification`` is
  accepted only if ``evidence.issued(c)`` is True (minted by that module, unchanged since). The equities layer reads
  ``provenance``, ``eligibility``, ``weight_ceiling`` and ``promotion_authorized`` and never assigns them.
"""
from __future__ import annotations

import importlib
import importlib.util
import inspect

PINNED = {"#86": "5aa643f", "#84": "1e86b33"}
PREVIOUSLY_PINNED = {"#86": "8615c69681ff7b29795df91347608ab0a9b51367",
                     "#84": "178c5bdad49c467d19249ed64cde33b53218fad2"}

# (module, attribute path) -> (positional parameter names, keyword-only parameter names); ``self``/``cls`` dropped
EXPECTED = {
    ("manhattan.access", "register_evaluation"):
        (("ledger",), ("identity", "windows", "caller", "fence", "freeze", "holding", "token", "supersedes")),
    ("manhattan.access", "AttemptContext.window"): (("store",), ()),
    ("manhattan.access", "AttemptContext.fail"): (("reason",), ()),
    ("manhattan.access", "AttemptContext.abort"): (("reason",), ()),
    ("manhattan.access", "verified_fence"): (("commit",), ("root", "expected_sha256")),
    ("manhattan.access", "authorization"):
        (("kind", "windows"), ("caller", "fence", "freeze", "holding", "token", "identity", "config_sha256")),
    ("manhattan.engine.pit", "Reader.__init__"):
        (("store",), ("caller", "domain", "fence", "freeze", "holding", "token", "window_id", "attempt")),
    ("manhattan.engine.pit", "Reader.window"): (("start", "end"), ()),
    ("manhattan.evidence", "classify"): (("metadata", "verifications"), ("fence", "config", "protocol_hash")),
    ("manhattan.evidence", "combine"): (("parts",), ()),
    ("manhattan.evidence", "issued"): (("c",), ()),
}
EXPECTED_FIELDS = {
    ("manhattan.evidence", "Classification"): ("provenance", "eligibility", "weight_ceiling", "promotion_authorized"),
}
EXPECTED_CONSTANTS = {("manhattan.evidence", "SCHEMA"): "manhattan.evidence/3"}
# metadata keys the equities adapter will send to classify(); "attempt_id" is the obsolete form
EVIDENCE_METADATA = {"attempt_key": "attempt", "attempt_fields": ("id", "store"), "obsolete_keys": ("attempt_id",)}

# What a structural match cannot show. Each is a precondition of runtime integration, verified by no code here.
SEMANTIC_REQUIREMENTS = (
    ("#86", "bound_computation", "an operational computation is bound to its attempt by #86's runner path "
                                 "(access.run_bound(ctx, window, strategy), which #86 allows only in access.py and "
                                 "ops/runner.py); a result computed elsewhere is refused at completion, so equities "
                                 "code never calls it and is not pinned to it here"),
    ("#86", "verified_fence", "a forward attempt's fence comes from access.verified_fence: config/manhattan.yaml must "
                              "be byte-identical to its version at the registered commit, optionally hashing to "
                              "expected_sha256"),
    ("#86", "config_sha256", "the verified configuration's SHA-256 is recorded in the attempt's authorization and is "
                             "required for forward observations"),
    ("#86", "designated_reserve", "a reserve attempt is always its batch's designated evaluation of the domain, one "
                                  "per (batch, domain); a non-designated reserve attempt is refused"),
    ("#86", "window_sealing", "a Window is opened only by a Reader or a registered AttemptContext; never constructed, "
                              "copied or serialized"),
    ("#84", "schema_v3", "evidence metadata uses schema manhattan.evidence/3"),
    ("#84", "attempt_object", "metadata names its attempt as attempt={id, store}, not attempt_id"),
    ("#84", "issued", "a Classification is used only if evidence.issued(c) is True (minted by the module, unchanged)"),
    ("#84", "trusted_authorities", "facts count only from verifier results of a trusted authority; none is trusted "
                                   "today, so every classification is unverified"),
)
OWNER = {"manhattan.access": "#86", "manhattan.evidence": "#84", "manhattan.engine.pit": "#86"}
# a module that exists on main before the PR: its expected interface applies only once the PR's own module exists
MARKER = {"manhattan.engine.pit": "manhattan.access"}


def signature_of(fn) -> tuple:
    params = [p for p in inspect.signature(fn).parameters.values() if p.name not in ("self", "cls")]
    pos = tuple(p.name for p in params if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD))
    kw = tuple(p.name for p in params if p.kind == p.KEYWORD_ONLY)
    return pos, kw


def _resolve(module, path: str):
    obj = module
    for part in path.split("."):
        obj = getattr(obj, part)
    return obj


def _module(module_name: str, module):
    if module is not None:
        return module
    if module_name in MARKER and importlib.util.find_spec(MARKER[module_name]) is None:
        return None                          # the PR that brings this interface has not merged
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError:
        return None


def check(module_name: str, path: str, *, module=None) -> str:
    """``absent``, ``structural_match`` or ``mismatch: ...`` — structure only, never runtime compatibility."""
    want = EXPECTED[(module_name, path)]
    mod = _module(module_name, module)
    if mod is None:
        return "absent"
    try:
        got = signature_of(_resolve(mod, path))
    except AttributeError:
        return "absent"
    return "structural_match" if got == want else f"mismatch: expected {want}, found {got}"


def check_fields(module_name: str, cls: str, *, module=None) -> str:
    want = EXPECTED_FIELDS[(module_name, cls)]
    mod = _module(module_name, module)
    c = None if mod is None else getattr(mod, cls, None)
    if c is None:
        return "absent"
    missing = [f for f in want if f not in getattr(c, "__dataclass_fields__", {})]
    return "structural_match" if not missing else f"mismatch: missing fields {missing}"


def check_constant(module_name: str, name: str, *, module=None) -> str:
    mod = _module(module_name, module)
    if mod is None or not hasattr(mod, name):
        return "absent"
    want = EXPECTED_CONSTANTS[(module_name, name)]
    got = getattr(mod, name)
    return "structural_match" if got == want else f"mismatch: expected {want!r}, found {got!r}"


def evidence_metadata_attempt(attempt_id: str, store: str) -> dict:
    """The attempt entry of #84 schema-v3 metadata. Builds the shape only; it proves nothing about the attempt."""
    return {EVIDENCE_METADATA["attempt_key"]: {"id": attempt_id, "store": store}}


def check_all() -> dict:
    """Structural results only. ``runtime_integration`` is always False: see ``SEMANTIC_REQUIREMENTS``."""
    out = {f"{m}:{p}": check(m, p) for (m, p) in EXPECTED}
    out.update({f"{m}:{c}": check_fields(m, c) for (m, c) in EXPECTED_FIELDS})
    out.update({f"{m}:{c}": check_constant(m, c) for (m, c) in EXPECTED_CONSTANTS})
    return out


def runtime_integration() -> bool:
    """No adapter exists and no semantic requirement has been verified against merged code."""
    return False
