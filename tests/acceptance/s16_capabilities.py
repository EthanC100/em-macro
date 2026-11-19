"""Capability probes for the S16 system acceptance suite (Project Manhattan, integrated synthetic platform).

Every acceptance test names the capabilities it needs. A capability that is not present makes the test BLOCKED
(reported, never counted as a pass). Probes only import modules and read constants or source text; none of them
enables, registers or writes anything, and none reads real, licensed, reserve or forward data.

Two kinds of capability:

* **component**: a module delivered by one of the five approved PRs (#84, #85, #86, #87, #89). On main today none
  is merged, so every test that needs one is BLOCKED there.
* **integration**: an adapter or owner decision that joins two components. These are missing on purpose today
  (the PRs ship them disabled). A test that needs one is BLOCKED while it is missing. When a probe starts to report
  the capability present, the test FAILS with ``UNBOUND`` until someone binds it to the adapter's real API, so the
  gate can never turn green just because a flag flipped.
"""
from __future__ import annotations

import ast
import importlib
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

BLOCKED = "BLOCKED"       # skip-reason prefix the runner recognises
UNBOUND = "UNBOUND"       # failure prefix: a capability arrived but its acceptance test is not bound to it yet


@dataclass(frozen=True)
class Probe:
    name: str
    kind: str            # component | integration
    source: str          # the PR or decision that delivers it
    description: str


PROBES = {
    "hte": Probe("hte", "component", "PR #89", "manhattan.hte: registry, synthetic panels, runner, reconcile"),
    "evidence": Probe("evidence", "component", "PR #84", "manhattan.evidence: fail-closed evidence classification"),
    "access": Probe("access", "component", "PR #86", "manhattan.access + attempts: binding attempt accounting"),
    "execution": Probe("execution", "component", "PR #85", "manhattan.execution: synthetic futures execution"),
    "equities": Probe("equities", "component", "PR #87", "manhattan.equities: synthetic equities research data"),
    "hte_identity_levels": Probe("hte_identity_levels", "component", "PR #90 (S11, stacked on #89)",
                                 "HTE binding and executable identity levels, executable_accounting"),
    "execution_realism": Probe("execution_realism", "component", "PR #93 (S14)",
                               "manhattan.execution_realism: lagged, costed, provenance-labelled execution"),
    "adapter:hte->delayed-execution": Probe("adapter:hte->delayed-execution", "integration", "S14 / HTE owner (X5)",
                                            "HTE candidates evaluated with an execution lag through PR #93"),
    "adapter:hte->access": Probe("adapter:hte->access", "integration", "S11 / PR #86 D-1, D-10, B4",
                                 "HTE attempts registered in the Manhattan Ledger (hte.adapters.Pr86AccessAdapter)"),
    "adapter:hte->execution": Probe("adapter:hte->execution", "integration", "S11 / PR #85 E1-E4",
                                    "HTE stage 3 executed through manhattan.execution at lag >= 1"),
    "adapter:hte->evidence": Probe("adapter:hte->evidence", "integration", "S11",
                                   "a producer of evidence metadata and verifier results for HTE runs"),
    "adapter:equities->hte": Probe("adapter:equities->hte", "integration", "S11",
                                   "the synthetic equities world as an HTE domain"),
    "anchor:independent": Probe("anchor:independent", "integration", "PR #86 G-2 / D-7",
                                "independent custody of attempt-log anchors"),
    "authority:trusted": Probe("authority:trusted", "integration", "PR #84 / owner decision",
                               "a trusted verifier authority (evidence.TRUSTED_AUTHORITIES non-empty)"),
    "decision:D-1": Probe("decision:D-1", "integration", "owner decision D-1 (PR #86) / HTE B3",
                          "the multiple-testing counting unit shared by HTE and PR #86"),
}


def _import(name: str):
    try:
        return importlib.import_module(name), None
    except Exception as exc:          # a missing module or a broken one: either way the capability is absent
        return None, f"{type(exc).__name__}: {exc}"


def _imports_of(path: Path) -> set:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return set()
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module)
            out.update(f"{node.module}.{a.name}" for a in node.names)
    return out


def production_importers(target: str, *, within: str = "manhattan", exclude: tuple = ()) -> list[str]:
    """Production modules (under ``within``) that import ``target`` (or one of its submodules)."""
    hits = []
    for p in sorted((ROOT / within).rglob("*.py")):
        rel = p.relative_to(ROOT).as_posix()
        if any(rel.startswith(e) for e in exclude):
            continue
        if any(i == target or i.startswith(target + ".") for i in _imports_of(p)):
            hits.append(rel)
    return hits


@lru_cache(maxsize=None)
def probe(name: str) -> tuple[bool, str]:
    """(present, detail). Never raises."""
    try:
        return _probe(name)
    except Exception as exc:          # a probe that cannot decide reports the capability absent (fail closed)
        return False, f"probe error {type(exc).__name__}: {exc}"


def _probe(name: str) -> tuple[bool, str]:
    if name == "hte":
        m, err = _import("manhattan.hte.runner")
        return (m is not None), (err or "manhattan.hte importable")
    if name == "evidence":
        m, err = _import("manhattan.evidence")
        return (m is not None), (err or "manhattan.evidence importable")
    if name == "access":
        a, err = _import("manhattan.access")
        b, err2 = _import("manhattan.attempts")
        ok = a is not None and b is not None and hasattr(b, "reconcile") and hasattr(a, "register_evaluation")
        return ok, (err or err2 or ("manhattan.access importable" if ok else "manhattan.attempts.reconcile missing"))
    if name == "execution":
        m, err = _import("manhattan.execution")
        return (m is not None), (err or "manhattan.execution importable")
    if name == "equities":
        m, err = _import("manhattan.equities.synthetic")
        return (m is not None), (err or "manhattan.equities importable")
    if name == "adapter:hte->access":
        m, err = _import("manhattan.hte.adapters")
        if m is None:
            return False, "manhattan.hte absent (PR #89 not merged)"
        if getattr(m.Pr86AccessAdapter, "enabled", False) is True:
            return True, "Pr86AccessAdapter.enabled is True"
        return False, "hte.adapters.Pr86AccessAdapter is disabled: " + "; ".join(getattr(m, "BLOCKERS", ()))
    if name == "adapter:hte->execution":
        m, err = _import("manhattan.hte.adapters")
        if m is None:
            return False, "manhattan.hte absent (PR #89 not merged)"
        if getattr(m.Pr85ExecutionAdapter, "enabled", False) is True:
            return True, "Pr85ExecutionAdapter.enabled is True"
        return False, "hte.adapters.Pr85ExecutionAdapter is disabled (E1-E4)"
    if name == "adapter:hte->evidence":
        if not (ROOT / "manhattan" / "evidence.py").exists():
            return False, "manhattan.evidence absent (PR #84 not merged)"
        users = production_importers("manhattan.evidence", exclude=("manhattan/evidence.py",))
        if users:
            return True, "evidence producers: " + ", ".join(sorted(set(users)))
        return False, "no production module produces evidence metadata (nothing imports manhattan.evidence)"
    if name == "adapter:equities->hte":
        if not (ROOT / "manhattan" / "hte").is_dir():
            return False, "manhattan.hte absent (PR #89 not merged)"
        users = production_importers("manhattan.equities", within="manhattan/hte")
        if users:
            return True, "HTE modules importing manhattan.equities: " + ", ".join(users)
        return False, "HTE accepts only its own generator (hte.data.verify_synthetic); no equities domain adapter"
    if name == "anchor:independent":
        m, err = _import("manhattan.attempts")
        if m is None or not hasattr(m, "reconcile"):
            return False, "manhattan.attempts.reconcile absent (PR #86 not merged)"
        src = Path(m.__file__).read_text(encoding="utf-8")
        if '"independently_anchored": False' in src:
            return False, "attempts.reconcile reports independently_anchored=False as a constant (D-7, G-2)"
        return True, "attempts.reconcile no longer hard-codes independently_anchored=False"
    if name == "authority:trusted":
        m, err = _import("manhattan.evidence")
        if m is None:
            return False, "manhattan.evidence absent (PR #84 not merged)"
        if m.TRUSTED_AUTHORITIES:
            return True, f"TRUSTED_AUTHORITIES = {sorted(m.TRUSTED_AUTHORITIES)}"
        return False, "evidence.TRUSTED_AUTHORITIES is empty: every classification is unverified"
    if name == "hte_identity_levels":
        m, err = _import("manhattan.hte.adapters")
        if m is None:
            return False, err
        need = ("evaluation_binding_hash", "executable_spec", "lineage", "executable_accounting")
        missing = [n for n in need if not hasattr(m, n)]
        return (not missing), ("hte.adapters has " + ", ".join(need) if not missing
                               else "hte.adapters lacks " + ", ".join(missing) + " (PR #90 not merged)")
    if name == "execution_realism":
        m, err = _import("manhattan.execution_realism.screening")
        return (m is not None), (err or "manhattan.execution_realism importable")
    if name == "adapter:hte->delayed-execution":
        if not (ROOT / "manhattan" / "hte").is_dir():
            return False, "manhattan.hte absent (PR #89 not merged)"
        if not (ROOT / "manhattan" / "execution_realism").is_dir():
            return False, "manhattan.execution_realism absent (PR #93 not merged)"
        hits = production_importers("manhattan.execution_realism", within="manhattan/hte")
        hits += production_importers("manhattan.hte", within="manhattan/execution_realism")
        pol, _ = _import("manhattan.hte.policy")
        if pol is not None and "lag" in getattr(pol.Policy, "__dataclass_fields__", {}):
            hits.append("manhattan/hte/policy.py: Policy.lag")
        if hits:
            return True, "HTE <-> PR #93 binding found: " + ", ".join(hits)
        return False, ("no HTE <-> PR #93 binding: HTE has no lag (kernels.EXECUTION_TIMING is same-close) and "
                       "nothing joins manhattan.hte and manhattan.execution_realism (PR #93 X5)")
    if name == "decision:D-1":
        m, err = _import("manhattan.hte.adapters")
        if m is None:
            return False, "manhattan.hte absent (PR #89 not merged)"
        open_ = [b for b in getattr(m, "BLOCKERS", ()) if re.search(r"\bD-1\b(?!\d)", b)]
        if open_:
            return False, "open: " + "; ".join(open_)
        return True, "HTE no longer lists D-1 as a blocker"
    return False, f"unknown capability {name!r}"


def blocked_reason(names) -> str | None:
    missing = [(n, probe(n)[1]) for n in names if not probe(n)[0]]
    if not missing:
        return None
    return f"{BLOCKED}[{','.join(n for n, _ in missing)}]: " + " | ".join(f"{n}: {d}" for n, d in missing)


def snapshot() -> dict:
    out = {}
    for n, p in PROBES.items():
        ok, detail = probe(n)
        out[n] = {"present": ok, "kind": p.kind, "source": p.source, "description": p.description, "detail": detail}
    return out
