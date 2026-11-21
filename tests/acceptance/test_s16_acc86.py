"""S16 phase 2: acceptance of candidate-level HTE -> PR #86 attempt accounting (ACC86-*).

Each test runs twice. The ``adapter`` run uses the real S11 adapter: it is BLOCKED while
``hte.adapters.Pr86AccessAdapter`` is disabled, and UNBOUND once it exists but is not yet bound in s16_drivers.py.
The ``oracle`` run uses a test-only reference built from the public functions of PR #90 and PR #86, and is reported
under ``ORC-ACC86-*``. The oracle proves only that the tests are satisfiable and sharp; it never stands in for the
adapter.

The cross-check is the test's own: it joins HTE's results of record (``results.bin`` and ``reconcile``) with
PR #86's ledger and reconciler and the PR #90 lineage. It trusts no driver output.
"""
from __future__ import annotations

import hashlib
import json

import pytest

import s16_drivers as DRV

COMPONENTS = ("hte", "access", "hte_identity_levels")
P = DRV.driver_params


def _ledger(tmp_path, name="ledger.jsonl"):
    from manhattan import ledger as L
    return L.Ledger(tmp_path / name, writer="s16-acc86", protocol="0" * 64)


def _anchor(book):
    return {"records": len(book), "head": book.head}


def _table(e):
    from manhattan.hte import store
    out = e["out"]
    return store.read_arrays(e["ws"].run_dir(out["run_id"]) / "results.bin", out["results_sha256"])


def result_hashes(e) -> dict:
    """Per candidate, a hash of its row in HTE's results of record (statuses, fingerprint, stage-3 series hash)."""
    t = _table(e)
    out = {}
    for i in range(t["s1"].shape[0]):
        h = hashlib.sha256()
        for k in ("s1", "s3", "fingerprint", "series_sha256"):
            h.update(k.encode())
            h.update(t[k][i].tobytes())
        out[i] = h.hexdigest()
    return out


def cross_check(e, book, drv) -> list[dict]:
    """Every discrepancy between HTE's run of record and PR #86's ledger, at candidate level."""
    from manhattan import ledger as L
    r = e["runner"]
    want = {}
    for i in range(len(r.view)):
        ident, lin = drv.identity(r, i), drv.lineage(r, i)
        want[ident["spec_hash"]] = (i, ident, lin)
    expect = result_hashes(e)
    seen: dict = {}
    issues = []
    for rec in book.records():
        if rec["type"] not in L.COMPLETIONS:
            continue
        p = rec["payload"]
        if not str(p.get("batch", "")).startswith("hte-"):
            continue
        seen.setdefault(p["spec_hash"], []).append(rec)
        if p["spec_hash"] not in want:
            issues.append({"code": "unexpected_completion", "spec_hash": p["spec_hash"][:16]})
            continue
        i, ident, lin = want[p["spec_hash"]]
        if (p["family"], p["hypothesis"], p["variant"]) != (lin["family"], lin["hypothesis"], lin["variant"]):
            issues.append({"code": "lineage_mismatch", "candidate": i})
        if p["role"] != "exploration" or p["designated"] is not False or p["channel"] != "blind":
            issues.append({"code": "protected_role", "candidate": i})
        if p["result_hash"] != expect[i]:
            issues.append({"code": "result_mismatch", "candidate": i})
        if rec["type"] == "nondeterminism":
            issues.append({"code": "nondeterminism", "candidate": i})
    for sh, (i, _, _) in want.items():
        if sh not in seen:
            issues.append({"code": "missing_candidate", "candidate": i})
    return issues


def _run_accounting(e, tmp_path, drv):
    book = _ledger(tmp_path)
    attempts = {}
    hashes = result_hashes(e)
    r = e["runner"]
    for i in range(len(r.view)):
        aid = drv.register(book, r, i)
        drv.complete(book, r, i, aid, hashes[i])
        attempts[i] = aid
    return book, attempts


# ------------------------------------------------------------------------------------------------- the clean run

@pytest.mark.parametrize("which", P("accounting", "ACC86-01", "accounting", COMPONENTS))
def test_acc86_01_every_candidate_is_accounted_exactly_once(which, hte_null_experiment, tmp_path):
    from manhattan import attempts as A
    from manhattan.hte.runner import reconcile
    e = hte_null_experiment
    drv = DRV.get("accounting", which)
    book, att = _run_accounting(e, tmp_path, drv)
    N = len(e["runner"].view)
    assert len(set(att.values())) == N                                    # one attempt per candidate
    assert cross_check(e, book, drv) == []
    hte = reconcile(e["ws"], e["out"]["run_id"])
    pr86 = A.reconcile(ledger_path=book.path, ledger_anchor=_anchor(book))
    assert hte["violations"] == [] and pr86["violations"] == [] and pr86["access_reconciled"]
    assert pr86["registered_executions"] == pr86["completed"] == pr86["completed_evaluation_keys"] == N
    assert hte["registered"]["candidates"] == N == book.looks()
    assert pr86["independent_statistical_tests"] is None and pr86["independently_certified"] is False
    starts = {r["hash"]: r["seq"] for r in book.records("evaluation_started")}
    for r in book.records("evaluation"):                                  # every start precedes its completion
        assert starts[r["payload"]["attempt_id"]] < r["seq"]


@pytest.mark.parametrize("which", P("accounting", "ACC86-02", "identity", COMPONENTS))
def test_acc86_02_scientific_binding_identity_matches_the_frozen_registry(which, hte_null_experiment, tmp_path):
    from manhattan.hte import adapters
    e = hte_null_experiment
    r = e["runner"]
    drv = DRV.get("accounting", which)
    book, _ = _run_accounting(e, tmp_path, drv)
    lins = {}
    for i in range(len(r.view)):
        lin = drv.lineage(r, i)
        lins[lin["executable"]] = lin
        d = r.view.describe(i)
        assert (lin["family"], lin["hypothesis"], lin["candidate"]) == (d["family_hash"], d["hypothesis_hash"],
                                                                         r.view.candidate_hash(i))
        assert lin["binding"] == adapters.evaluation_binding_hash(r.view, i, policy=r.policy, fence=r.panel.fence)
    acc = adapters.executable_accounting(book.records("evaluation"), lins)
    counts = e["frozen"]["counts"]
    assert acc["scientific"]["family"] == counts["families"]
    assert acc["scientific"]["hypothesis"] == counts["hypotheses"]
    assert acc["scientific"]["variant"] == counts["variants"]
    assert acc["scientific"]["candidate"] == acc["scientific"]["binding"] == counts["candidates"]
    assert acc["looks"] == acc["executables"] == acc["completions"] == counts["candidates"]
    assert acc["hold_families"] == [] and acc["independent_statistical_tests"] is None


@pytest.mark.parametrize("which", P("accounting", "ACC86-03", "identity", COMPONENTS))
def test_acc86_03_executable_identity_is_deterministic_and_complete(which, hte_null_experiment, tmp_path,
                                                                    monkeypatch):
    import shutil
    from manhattan.hte import kernels
    from manhattan.hte.policy import Policy
    from manhattan.hte.runner import Runner, Workspace
    e = hte_null_experiment
    r = e["runner"]
    drv = DRV.get("accounting", which)
    N = len(r.view)
    base = [drv.identity(r, i) for i in range(N)]
    assert len({x["spec_hash"] for x in base}) == N and all(x["executable"] == x["spec_hash"] for x in base)
    # deterministic: an independent runner over a copy of the workspace gives bit-identical identities
    shutil.copytree(e["ws"].root, tmp_path / "copy")
    r2 = Runner(Workspace(tmp_path / "copy"), e["panel"], Policy(), chunk_size=11)
    assert [drv.identity(r2, i) for i in range(N)] == base
    # engine, numerical environment, policy and cost assumptions each give new executables of ...
    variants = {
        "engine": dict(code=DRV.code_of(r, engine="e" * 64)),
        "environment": dict(code=DRV.code_of(r, env_core="S16OtherCore")),
        "policy": dict(policy=Policy(vol_target_ann=0.2)),
    }
    for what, kw in variants.items():
        other = [drv.identity(r, i, **kw) for i in range(N)]
        assert all(a["spec_hash"] != b["spec_hash"] for a, b in zip(base, other)), what
        lin_a, lin_b = drv.lineage(r, 0), drv.lineage(r, 0, **kw)
        # ... the same scientific evaluation when only code or environment changed
        same_sci = all(lin_a[k] == lin_b[k] for k in ("family", "hypothesis", "variant", "candidate", "binding"))
        assert same_sci is (what != "policy"), what
    real = kernels.cost_coefficients
    monkeypatch.setattr(kernels, "cost_coefficients", lambda dom, m: tuple(1.5 * x for x in real(dom, m)))
    costly = [drv.identity(r, i) for i in range(N)]
    assert all(a["spec_hash"] != b["spec_hash"] for a, b in zip(base, costly)), "cost assumptions not in identity"
    monkeypatch.setattr(kernels, "cost_coefficients", real)
    # re-accounting the same run is a rerun of every look, never a new look
    book, _ = _run_accounting(e, tmp_path, drv)
    hashes = result_hashes(e)
    for i in range(N):
        assert drv.complete(book, r, i, drv.register(book, r, i), hashes[i])["type"] == "rerun"
    assert book.looks() == N and book.suspended_families() == set()


@pytest.mark.parametrize("which", P("accounting", "ACC86-04", "interruption", COMPONENTS))
def test_acc86_04_retry_resumes_only_the_identical_evaluation(which, hte_null_experiment, tmp_path):
    from manhattan import attempts as A, ledger as L
    from manhattan.hte.policy import Policy
    e = hte_null_experiment
    r = e["runner"]
    drv = DRV.get("accounting", which)
    h = result_hashes(e)
    book = _ledger(tmp_path)
    first = drv.register(book, r, 7)                                      # the process dies before completing
    book = _ledger(tmp_path)
    rep = A.reconcile(ledger_path=book.path, ledger_anchor=_anchor(book))
    assert not rep["access_reconciled"] and rep["unfinished"] == 1
    assert any(v["code"] == "missing_terminal" for v in rep["violations"])
    for bad in (dict(code=DRV.code_of(r, engine="e" * 64)), dict(code=DRV.code_of(r, env_core="S16OtherCore")),
                dict(policy=Policy(vol_target_ann=0.2))):
        with pytest.raises(L.LedgerError):
            drv.register(book, r, 7, supersedes=first, **bad)             # a retry may not change what is evaluated
    with pytest.raises(L.LedgerError):
        drv.register(book, r, 8, supersedes=first)                        # nor which candidate
    retry = drv.register(book, r, 7, supersedes=first)
    assert drv.complete(book, r, 7, retry, h[7])["type"] == "evaluation"
    rep = A.reconcile(ledger_path=book.path, ledger_anchor=_anchor(book))
    assert rep["access_reconciled"] and rep["retries"] == 1 and rep["completed"] == 1
    assert [x["hash"] for x in book.unfinished()] == [first]              # the interrupted start stays visible
    with pytest.raises(L.LedgerError):
        drv.register(book, r, 7, supersedes=retry)                        # a completed attempt is not retried


# --------------------------------------------------------------------------------------- deliberate mismatches

DAMAGE = ["skip_candidate", "swap_results", "conflicting_result", "foreign_completion", "relabelled_family",
          "edited_record", "divergent_engine"]


@pytest.mark.parametrize("damage", DAMAGE)
@pytest.mark.parametrize("which", P("accounting", "ACC86-05", "accounting", COMPONENTS))
def test_acc86_05_accounting_mismatches_are_detected(which, damage, hte_null_experiment, tmp_path):
    from manhattan import attempts as A
    from manhattan.hte import adapters
    import s16_fixtures as F
    e = hte_null_experiment
    r = e["runner"]
    drv = DRV.get("accounting", which)
    h = result_hashes(e)
    book = _ledger(tmp_path)
    N = len(r.view)
    for i in range(N):
        if damage == "skip_candidate" and i == 5:
            continue
        res = h[i]
        if damage == "swap_results" and i in (3, 4):
            res = h[7 - i]
        drv.complete(book, r, i, drv.register(book, r, i), res)
    codes = lambda: {x["code"] for x in cross_check(e, book, drv)}       # noqa: E731
    if damage == "skip_candidate":
        assert codes() == {"missing_candidate"}
    elif damage == "swap_results":
        assert codes() == {"result_mismatch"}
    elif damage == "conflicting_result":
        drv.complete(book, r, 9, drv.register(book, r, 9), "f" * 64)      # same executable, other bits
        assert "nondeterminism" in codes() and book.suspended_families()
    elif damage == "foreign_completion":                                  # a completion nobody registered
        ident = dict(drv.identity(r, 2), spec_hash="c" * 64, executable="c" * 64)
        F.forge(book, "evaluation", dict(ident, result_hash="d" * 64, n_obs=1, summary={}, seed=0,
                                         reconstructed=False, evidential_weight=0, attempt_id="e" * 64))
        assert "unexpected_completion" in codes()
        rep = A.reconcile(ledger_path=book.path, ledger_anchor=_anchor(book))
        assert not rep["access_reconciled"] and rep["violations"]
    elif damage == "relabelled_family":                                   # a hash-valid record in another family
        last = book.records("evaluation")[-1]["payload"]
        F.forge(book, "evaluation", dict(last, family="ab" * 32))
        assert "lineage_mismatch" in codes()
    elif damage == "edited_record":
        a = _anchor(book)
        rows = book.path.read_text().splitlines()
        rec = json.loads(rows[-1])
        rec["payload"]["result_hash"] = "0" * 64
        rows[-1] = json.dumps(rec)
        book.path.write_text("\n".join(rows) + "\n")
        with pytest.raises(A.ReconciliationError):
            A.reconcile(ledger_path=book.path, ledger_anchor=a)
    else:                                                                 # another engine, another answer
        code = DRV.code_of(r, engine="e" * 64)
        drv.complete(book, r, 0, drv.register(book, r, 0, code=code), "a" * 64, code=code)
        lins = {drv.lineage(r, i)["executable"]: drv.lineage(r, i) for i in range(N)}
        lins[drv.lineage(r, 0, code=code)["executable"]] = drv.lineage(r, 0, code=code)
        acc = adapters.executable_accounting(book.records("evaluation"), lins)
        assert acc["hold_families"] == [drv.lineage(r, 0)["family"]]
        assert any(g["divergent"] for g in acc["cross_executable"])
        assert book.suspended_families() == set()                         # not a false PR #86 nondeterminism


@pytest.mark.parametrize("which", P("accounting", "ACC86-06", "protected_data", COMPONENTS))
def test_acc86_06_hte_accounting_never_reaches_a_protected_role(which, hte_null_experiment, tmp_path):
    from datetime import date
    from manhattan import access, roles
    from manhattan.engine import pit
    e = hte_null_experiment
    r = e["runner"]
    drv = DRV.get("accounting", which)
    for i in range(len(r.view)):
        x = drv.identity(r, i)
        assert (x["role"], x["designated"], x["channel"]) == ("exploration", False, "blind")
        assert x["batch"].startswith("hte-")
    book = _ledger(tmp_path)
    x = dict(drv.identity(r, 0), role="reserve", designated=True)
    w = x["window"]
    fence = roles.Fence(exploration_end=date(2019, 12, 31), reserve={DRV.HTE_DOMAIN: (date(2000, 1, 3),
                                                                                      date(2019, 12, 31))},
                        enabled=True)
    dw = access.DeclaredWindow(w["id"], DRV.HTE_DOMAIN, date.fromisoformat(w["start"]), date.fromisoformat(w["end"]),
                               "reserve", "evaluation", x["data_hash"])
    with pytest.raises((pit.AccessError, roles.RoleError)):              # no token, no reserve, whatever the label
        access.register_evaluation(book, identity=x, windows=[dw], caller=roles.RUNNER, fence=fence)
    assert len(book) == 0
