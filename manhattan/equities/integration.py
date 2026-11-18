"""Integration contracts with Manhattan components still under review, stated as exact signatures (S8 M9).

The earlier version declared ``typing.Protocol`` classes that matched any object with methods of the right names.
They matched neither PR #86 (binding attempt accounting: ``register_evaluation`` returning an ``AttemptContext``,
not ``start``/``finish``) nor PR #84 (evidence classification: ``classify(metadata, verifications, *, fence, ...)``).
This module now records the exact interfaces the equities layer will call, **pinned to the PR heads inspected**,
and checks them by parameter names and kinds — never by method names alone. It does not import unfinished
branches: on main the modules are absent and ``check_all`` says so; once a PR merges, the same check says whether
its interface still matches what the equities adapters expect, and a test fails on a mismatch.

Pinned heads (inspected 2026-11-18):

    PR #86  claude/phase4-binding-accounting-l3ihoz   8615c69681ff7b29795df91347608ab0a9b51367
    PR #84  claude/phase4-evidence-classification     178c5bdad49c467d19249ed64cde33b53218fad2

How the equities layer will use them (adapters are not written until the PRs merge):

* **#86** — a reserve or forward read of equity data needs ``access.register_evaluation(ledger, *, identity,
  windows, caller, fence, freeze, holding, token, supersedes)`` → ``AttemptContext``, then ``ctx.window(store)`` or
  ``pit.Reader(..., attempt=ctx).window(start, end)``; ``ctx.fail(reason)`` / ``ctx.abort(reason)`` end it.
  Exploration reads keep using ``pit.Reader(...).window(start, end)`` without an attempt (``research.open_window``).
  A ``Window`` is never constructed directly (it raises ``AccessError`` under #86).
* **#84** — every equities output would be classified by ``evidence.classify(metadata, verifications, *, fence,
  config, protocol_hash)`` → ``Classification``; the equities layer only reads ``provenance``, ``eligibility``,
  ``weight_ceiling`` and ``promotion_authorized`` and never assigns them. Synthetic outputs must classify as
  provenance ``synthetic``, never above ``infrastructure_validation``.
"""
from __future__ import annotations

import importlib
import importlib.util
import inspect

PINNED = {"#86": "8615c69681ff7b29795df91347608ab0a9b51367", "#84": "178c5bdad49c467d19249ed64cde33b53218fad2"}

# (module, attribute path) -> (positional parameter names, keyword-only parameter names); ``self``/``cls`` dropped
EXPECTED = {
    ("manhattan.access", "register_evaluation"):
        (("ledger",), ("identity", "windows", "caller", "fence", "freeze", "holding", "token", "supersedes")),
    ("manhattan.access", "AttemptContext.window"): (("store",), ()),
    ("manhattan.access", "AttemptContext.forward_window"): (("store",), ()),
    ("manhattan.access", "AttemptContext.fail"): (("reason",), ()),
    ("manhattan.access", "AttemptContext.abort"): (("reason",), ()),
    ("manhattan.engine.pit", "Reader.__init__"):
        (("store",), ("caller", "domain", "fence", "freeze", "holding", "token", "window_id", "attempt")),
    ("manhattan.engine.pit", "Reader.window"): (("start", "end"), ()),
    ("manhattan.evidence", "classify"): (("metadata", "verifications"), ("fence", "config", "protocol_hash")),
    ("manhattan.evidence", "combine"): (("parts",), ()),
}
EXPECTED_FIELDS = {
    ("manhattan.evidence", "Classification"): ("provenance", "eligibility", "weight_ceiling", "promotion_authorized"),
}
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


def check(module_name: str, path: str, *, module=None) -> str:
    """``absent`` (the module or attribute does not exist yet), ``match`` or ``mismatch: ...``. ``module`` lets a
    test pass a stand-in; normally the module is imported if it exists."""
    want = EXPECTED[(module_name, path)]
    if module is None:
        if module_name in MARKER and importlib.util.find_spec(MARKER[module_name]) is None:
            return "absent"                  # the PR that brings this interface has not merged
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            return "absent"
    try:
        got = signature_of(_resolve(module, path))
    except AttributeError:
        return "absent"
    return "match" if got == want else f"mismatch: expected {want}, found {got}"


def check_fields(module_name: str, cls: str, *, module=None) -> str:
    want = EXPECTED_FIELDS[(module_name, cls)]
    if module is None:
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            return "absent"
    c = getattr(module, cls, None)
    if c is None:
        return "absent"
    names = set(getattr(c, "__dataclass_fields__", {}))
    missing = [f for f in want if f not in names]
    return "match" if not missing else f"mismatch: missing fields {missing}"


def check_all() -> dict:
    out = {f"{m}:{p}": check(m, p) for (m, p) in EXPECTED}
    out.update({f"{m}:{c}": check_fields(m, c) for (m, c) in EXPECTED_FIELDS})
    return out
