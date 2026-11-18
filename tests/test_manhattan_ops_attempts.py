"""Phase 4B: attempt accounting in the operational Store (forward observations and screening), crash stages,
recovery, retries and reconciliation. Synthetic data and local bare repositories only; no simulation runs."""
from __future__ import annotations

import json
import shutil
from datetime import date

import pytest

from manhattan import access as A
from manhattan import attempts, roles
from manhattan import ledger as L
from manhattan.engine import pit
from manhattan.ops import data as D
from manhattan.ops import runner as R
from manhattan.ops import store as ST
from test_manhattan_ops_runner import setup  # noqa: F401  (the runner fixture: batch, clock, nights)

PRIVATE = "private_canary_0.987654321"


def anchor(led: ST.Store) -> dict:
    return {"records": len(led.records), "head": led.head}


def audit(led: ST.Store, **kw) -> dict:
    return attempts.reconcile(store_chain=led.workdir / ST.CHAIN, store_anchor=anchor(led), **kw)


def codes(r: dict) -> list[str]:
    return sorted(v["code"] for v in r["violations"])


def first_night(s):
    s["night"](date(2026, 11, 12), "2026-11-12T23:30:00Z")
    s["register"]()


# ------------------------------------------------------------------ registration before exposure

def test_forward_night_registers_before_reading_and_reconciles(setup, monkeypatch):
    s = setup
    first_night(s)
    seen = []
    real = D.forward_window

    def watch(attempt, store, *a):
        led = s["ledger"]()                                   # a fresh clone of the remote, not the runner's cache
        seen.append(led.get((A.STORE_START, attempt.attempt_id)) is not None)
        return real(attempt, store, *a)

    monkeypatch.setattr(D, "forward_window", watch)
    h = s["night"](date(2026, 11, 16), "2026-11-16T23:30:00Z")
    assert h["status"] == "ok" and seen and all(seen)          # every start was on the remote before its window
    led = s["ledger"]()
    starts, done = led.of_type("attempt_started"), led.of_type("attempt_completed")
    obs = led.of_type("observation")
    assert h["attempts_registered"] == len(starts) == len(done) > 0 and obs
    assert max(r["seq"] for r in starts) < min(r["seq"] for r in obs)
    assert {p["payload"]["kind"] for p in starts} == {"forward_observation"}
    r = audit(led)
    assert r["access_reconciled"], r["violations"]
    assert (r["registered_executions"], r["completed"], r["unfinished"]) == (len(starts), len(starts), 0)
    assert r["repeated_observations"] == len(obs) and r["independent_statistical_tests"] is None


def test_unknown_code_identity_fails_closed_before_any_forward_window(setup, monkeypatch):
    s = setup
    first_night(s)
    monkeypatch.setattr(D, "forward_window", lambda *a: pytest.fail("a window opened"))
    h = s["night"](date(2026, 11, 16), "2026-11-16T23:30:00Z", commit="0" * 40)
    led = s["ledger"]()
    assert h["status"] == "failed" and h["stage"] == "evaluate" and h["error_class"] == "LedgerError"
    assert led.of_type("attempt_started") == [] and led.of_type("observation") == []


def test_observations_need_an_active_forward_attempt(setup):
    s = setup
    first_night(s)
    s["night"](date(2026, 11, 16), "2026-11-16T23:30:00Z")
    led = s["ledger"]()
    reg = sorted(R.registrations(led).items())[0][1]
    manifest, specs = R.load_batch(s["cfg"](date(2026, 11, 16)).batches_dir, 1)
    exe = next(x for x in R.batch_executables(specs) if R.prediction_id(R.S.spec_hash(manifest), x.spec_hash)
               == reg["prediction"])
    fs = D.first_seen(led, ("synthetic",))
    store = fs.pit_store()
    with pytest.raises(pit.AccessError):
        R.observation_intents(led, fs, store, reg, exe, date(2026, 11, 16), attempt=None)
    led2 = ST.Store(workdir=led.workdir.parent / "w2", remote=led.remote, run_id="t", commit="c" * 40).open()
    (ctx,) = A.register_store_attempts(led2, [R.forward_attempt(reg, exe, date(2026, 11, 17), store.data_hash(),
                                                                R.code_identity("c" * 40))],
                                       fence=roles.Fence.from_config(R.MC.load()))
    with pytest.raises(pit.AccessError):                       # declared for another night
        R.observation_intents(led2, fs, store, reg, exe, date(2026, 11, 16), attempt=ctx)
    ctx.fail("cancelled")
    with pytest.raises(pit.AccessError):                       # no longer active
        ctx.forward_window(store)


def test_warmup_overlapping_a_configured_reserve_is_refused(setup):
    """Owner decision D-3: fail closed, and write nothing."""
    s = setup
    first_night(s)
    led = s["ledger"]()
    reg = sorted(R.registrations(led).items())[0][1]
    manifest, specs = R.load_batch(s["cfg"](date(2026, 11, 16)).batches_dir, 1)
    exe = next(x for x in R.batch_executables(specs) if R.prediction_id(R.S.spec_hash(manifest), x.spec_hash)
               == reg["prediction"])
    attempt = R.forward_attempt(reg, exe, date(2026, 11, 16), "d" * 64, R.code_identity("c" * 40))
    warm = next(w for w in attempt.windows if w.purpose == "signal_warmup")
    fence = roles.Fence(exploration_end=date(2019, 12, 31), enabled=False,
                        reserve={exe.universe.domain: (warm.start, warm.start)})
    before = len(led.records)
    with pytest.raises(pit.AccessError, match="D-3"):
        A.register_store_attempts(led, [attempt], fence=fence)
    assert len(led.records) == before


# ------------------------------------------------------------------ crashes, recovery, retries and failures

def test_crash_after_registration_is_recovered_then_retried(setup, monkeypatch):
    s = setup
    first_night(s)

    def die(*a, **k):
        raise ST.SimulatedCrash("after registration")

    monkeypatch.setattr(R, "observation_intents", die)
    with pytest.raises(ST.SimulatedCrash):
        s["night"](date(2026, 11, 16), "2026-11-16T23:30:00Z")
    monkeypatch.undo()
    crashed = s["ledger"]()
    n = len(crashed.of_type("attempt_started"))
    assert n > 0 and crashed.of_type("observation") == []
    r = audit(crashed)
    assert not r["access_reconciled"] and r["unfinished"] == n and codes(r) == ["missing_terminal"] * n
    h = s["night"](date(2026, 11, 16), "2026-11-17T02:00:00Z")      # the dead run's lock has expired
    assert h["status"] == "ok" and h["attempts_recovered"] == n and h["locks_broken"] == 1
    led = s["ledger"]()
    aborted = led.of_type("attempt_aborted")
    assert len(aborted) == n and all(a["payload"]["reason"] == "interrupted" and a["payload"]["data_read"] is None
                                     for a in aborted)
    retries = [x for x in led.of_type("attempt_started") if x["payload"]["retry_of"]]
    assert {x["payload"]["retry_of"] for x in retries} == {a["payload"]["attempt_id"] for a in aborted}
    r = audit(led)
    assert r["access_reconciled"], r["violations"]
    assert (r["registered_executions"], r["completed"], r["aborted"], r["retries"]) == (2 * n, n, n, n)
    assert r["terminals_by_data_read"]["aborted_unknown"] == n


def test_a_rerun_with_the_same_run_identity_still_recovers(setup, monkeypatch):
    """A local rerun reuses run_id/run_attempt; its dead predecessor's attempts must still be closed."""
    import dataclasses
    s = setup
    first_night(s)
    cfg = dataclasses.replace(s["cfg"](date(2026, 11, 16)), run_id="local", run_attempt=1)
    fetch = {"synthetic": lambda: D.synthetic_csv(date(2026, 11, 16))}
    monkeypatch.setattr(R, "observation_intents", lambda *a, **k: (_ for _ in ()).throw(ST.SimulatedCrash("x")))
    s["clock"].at("2026-11-16T23:30:00Z")
    with pytest.raises(ST.SimulatedCrash):
        R.nightly(cfg, fetch, clock=s["clock"])
    monkeypatch.undo()
    s["clock"].at("2026-11-16T23:40:00Z")
    h = R.nightly(dataclasses.replace(cfg, ledger_dir=cfg.ledger_dir.parent / "again"), fetch, clock=s["clock"])
    assert h["status"] == "ok" and h["lock_status"] == "held" and h["attempts_recovered"] > 0
    r = audit(s["ledger"]())
    assert r["access_reconciled"], r["violations"]


@pytest.mark.parametrize("stage", ["after_journal_local", "after_journal_push", "mid_chain_write",
                                   "after_chain_commit_local", "after_chain_push"])
def test_crash_during_result_commit_keeps_results_and_terminals_together(setup, monkeypatch, stage):
    s = setup
    first_night(s)
    real = ST.Store.write

    def write(self, intents, label, files=None):
        if label.startswith("observations to"):
            self.crash_at = stage
        return real(self, intents, label, files)

    monkeypatch.setattr(ST.Store, "write", write)
    with pytest.raises(ST.SimulatedCrash):
        s["night"](date(2026, 11, 16), "2026-11-16T23:30:00Z")
    monkeypatch.undo()
    mid = s["ledger"]()
    terminals = {r["key"][1] for r in mid.of_type("attempt_completed")}
    linked = {tuple(x["key"]) for r in mid.of_type("attempt_completed") for x in r["payload"]["results"]}
    assert {tuple(r["key"]) for r in mid.of_type("observation")} <= linked   # never a result without its terminal
    assert all(k in {tuple(r["key"]) for r in mid.records} for k in linked) or not terminals
    h = s["night"](date(2026, 11, 16), "2026-11-17T02:00:00Z")
    assert h["status"] == "ok"
    led = s["ledger"]()
    r = audit(led)
    assert r["access_reconciled"], r["violations"]
    assert led.unfinished() == [] and r["unfinished"] == 0
    obs = led.of_type("observation")
    assert obs and r["repeated_observations"] == len(obs)
    keys = [tuple(x["key"]) for x in led.records]
    assert len(keys) == len(set(keys))


def test_handled_failure_closes_attempts_without_private_text(setup, monkeypatch):
    s = setup
    first_night(s)

    def broken(*a, **k):
        raise RuntimeError(PRIVATE)

    monkeypatch.setattr(R, "observation_intents", broken)
    h = s["night"](date(2026, 11, 16), "2026-11-16T23:30:00Z")
    led = s["ledger"]()
    failed = led.of_type("attempt_failed")
    assert h["status"] == "failed" and h["attempts_registered"] == len(failed) > 0
    assert all(f["payload"] == {"attempt_id": f["key"][1], "status": "failed", "reason": "execution_error",
                                "data_read": False, "results": []} for f in failed)
    assert PRIVATE not in (led.workdir / ST.CHAIN).read_text() and led.of_type("observation") == []
    r = audit(led)
    assert r["access_reconciled"] and r["completed"] == 0 and r["completed_evaluation_keys"] == 0
    assert r["terminals_by_data_read"]["failed_unread"] == len(failed)


def test_rerun_is_a_second_execution_with_duplicate_results_only(setup):
    s = setup
    first_night(s)
    s["night"](date(2026, 11, 16), "2026-11-16T23:30:00Z")
    n_obs = len(s["ledger"]().of_type("observation"))
    s["night"](date(2026, 11, 16), "2026-11-16T23:50:00Z")
    led = s["ledger"]()
    r = audit(led)
    assert r["access_reconciled"] and len(led.of_type("observation")) == n_obs == r["repeated_observations"]
    assert r["registered_executions"] == r["completed"] == 2 * len(R.registrations(led))
    assert r["distinct_specifications"] == len(R.registrations(led))


# ------------------------------------------------------------------ forgery, tampering and anchors

def _forger(led):
    return ST.Store(workdir=led.workdir.parent / "forger", remote=led.remote, run_id="forger", commit="c" * 40).open()


FORGERIES = ["unregistered_observation", "attempt_id_mismatch", "unknown_terminal", "bad_link", "bad_retry",
             "weight", "escalation"]


@pytest.mark.parametrize("forgery", FORGERIES)
def test_hash_valid_store_forgeries_are_reported(setup, forgery):
    s = setup
    first_night(s)
    s["night"](date(2026, 11, 16), "2026-11-16T23:30:00Z")
    f = _forger(s["ledger"]())
    start = f.of_type("attempt_started")[0]
    obs = f.of_type("observation")[-1]
    new_obs = dict(obs["payload"], date="2026-11-30")
    key = ("observation", obs["payload"]["prediction"], "2026-11-30")
    expect = {"unregistered_observation": "unregistered_protected_evaluation",
              "attempt_id_mismatch": "attempt_id_mismatch", "unknown_terminal": "terminal_without_attempt",
              "bad_link": "result_linkage_mismatch", "bad_retry": "invalid_retry",
              "weight": "evidential_weight_mismatch", "escalation": "invalid_identity_or_authorization"}[forgery]
    if forgery == "unregistered_observation":
        f.write([ST.Intent("observation", key, new_obs)], "forged")
    elif forgery == "attempt_id_mismatch":
        f.write([ST.Intent(A.STORE_START, (A.STORE_START, "f" * 64), start["payload"])], "forged")
    elif forgery == "unknown_terminal":
        f.write([A.terminal_intent("e" * 64, "failed", reason="execution_error", data_read=False)], "forged")
    elif forgery in ("bad_link", "bad_retry", "escalation"):
        p = {**start["payload"], "nonce": "1" * 32, "run": {"run_id": "forger", "run_attempt": 1}}
        if forgery == "bad_retry":
            p["retry_of"] = start["key"][1]                         # a completed attempt is never retried
        if forgery == "escalation":
            p = json.loads(json.dumps(p))
            p["identity"]["role"] = "exploration"
            for w in p["authorization"]["windows"]:
                w["role"] = "exploration"
        aid = A.store_attempt_id(p)
        its = [ST.Intent(A.STORE_START, (A.STORE_START, aid), p)]
        if forgery == "bad_link":
            its.append(A.terminal_intent(aid, "completed", data_read=True, results=[
                {"key": list(key), "type": "observation", "content_hash": "0" * 64, "disposition": "new"}]))
        f.write(its, "forged")
    else:                                                           # weight 1 on a reconstructed observation
        f.write([ST.Intent("observation", key, dict(new_obs, reconstructed=True, evidential_weight=1))], "forged")
    r = audit(_forger(f))
    assert expect in codes(r) and not r["access_reconciled"]


def test_a_second_terminal_is_refused_as_a_conflict(setup):
    s = setup
    first_night(s)
    s["night"](date(2026, 11, 16), "2026-11-16T23:30:00Z")
    f = _forger(s["ledger"]())
    aid = f.of_type("attempt_completed")[0]["key"][1]
    res = f.write([A.terminal_intent(aid, "failed", reason="execution_error", data_read=True)], "contradiction")
    assert res["conflict"] == 1 and res["appended"] == 0
    r = audit(_forger(f))
    assert r["access_reconciled"] and f.get((A.STORE_TERMINAL, aid))["type"] == "attempt_completed"


@pytest.mark.parametrize("damage", ["delete", "alter", "truncate", "replace", "stale_anchor_head"])
def test_deleted_or_altered_store_history_is_detected(setup, tmp_path, damage):
    s = setup
    first_night(s)
    s["night"](date(2026, 11, 16), "2026-11-16T23:30:00Z")
    led = s["ledger"]()
    a = anchor(led)
    copy = tmp_path / "chain-copy.jsonl"
    shutil.copy(led.workdir / ST.CHAIN, copy)
    rows = copy.read_text().splitlines()
    if damage == "delete":
        del rows[len(rows) // 2]
    elif damage == "alter":
        r = json.loads(rows[-3]); r["payload"]["x"] = 1; rows[-3] = json.dumps(r)
    elif damage == "truncate":
        rows = rows[:-1]
    elif damage == "replace":
        rows = rows[:3]
        a = {"records": len(led.records), "head": led.head}
    else:
        a = {"records": a["records"], "head": "a" * 64}
    copy.write_text("\n".join(rows) + "\n")
    with pytest.raises(attempts.ReconciliationError):
        attempts.reconcile(store_chain=copy, store_anchor=a)


def test_batch_scope_and_both_stores_together(setup, tmp_path):
    import manhattan_attempt_fixtures as F
    from manhattan.engine import evaluate
    from test_manhattan_binding_access import FWD_FENCE, book, forward_ctx, hold, store
    s = setup
    first_night(s)
    s["night"](date(2026, 11, 16), "2026-11-16T23:30:00Z")
    led = s["ledger"]()
    b, st = book(tmp_path), store()
    ctx = forward_ctx(b, st)
    evaluate.evaluate(ctx.window(st), hold(), ledger=b, **F.spec_kwargs(), attempt=ctx)
    both = attempts.reconcile(ledger_path=b.path, ledger_anchor={"records": len(b), "head": b.head},
                              store_chain=led.workdir / ST.CHAIN, store_anchor=anchor(led))
    alone = audit(led)
    assert both["stores_covered"] == ["ledger", "store"] and both["access_reconciled"]
    assert both["registered_executions"] == alone["registered_executions"] + 1
    assert audit(led, batch="AB-0001")["registered_executions"] == alone["registered_executions"]
    other = audit(led, batch="AB-0999")
    assert other["registered_executions"] == 0 and other["access_reconciled"]
    assert FWD_FENCE.exploration_end < date(2010, 1, 4)


# ------------------------------------------------------------------ screening (exploration, registered)

def test_screening_is_registered_and_linked(tmp_path):
    import subprocess
    from manhattan import config as MC
    from manhattan.generate import parse_reply
    from manhattan.ops import compiler as CP, mockgen
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    req = mockgen.blind_request(n_families=2, max_hypotheses=1, domains=("syn_daily",))
    fams, hyps = parse_reply(mockgen.mock_reply(req, n=2), "blind")
    exes = list(CP.iter_batch(fams, hyps, "c" * 40))[:3]
    st = pit.PitStore()
    by = {}
    for s_, p_, v_ in D.synthetic_rows(date(2008, 12, 31)):
        by.setdefault(s_, ([], []))
        by[s_][0].append(p_)
        by[s_][1].append(v_)
    for s_, (ps, vs) in by.items():
        st.add(s_, ps, vs, lag_days=0 if "px" in s_ or "evt" in s_ else 1)
    fence = roles.Fence.from_config(MC.load())
    led = ST.Store(workdir=tmp_path / "w", remote=str(remote), run_id="900", commit="c" * 40).open()
    out = R.screen(led, exes, st, fence, date(2007, 1, 2), date(2008, 12, 31))
    assert out
    r = audit(led)
    assert r["access_reconciled"], r["violations"]
    assert r["registered_executions"] == r["completed"] == len(exes) == len(led.of_type("screening"))
    assert r["legacy"]["unlinked_exploration"] == 0
    # an interrupted screening (no lock) is closed by an operator, never by the nightly forward recovery
    ident = led.of_type("attempt_started")[0]["payload"]
    (ctx,) = A.register_store_attempts(led, [A.StoreAttempt("screening", ident["identity"],
                                                            tuple(ident["authorization"]["windows"]),
                                                            ident["subject"], caller="session")], fence=fence)
    assert A.recover_interrupted(led) == []
    led.write(A.recover_interrupted(led, kinds=("screening",)), "operator screening recovery")
    assert not ctx.active()
    r = audit(led)
    assert r["access_reconciled"] and r["terminals_by_data_read"]["aborted_unknown"] == 1
    with pytest.raises(L.LedgerError):                               # screening also needs a known code identity
        R.screen(ST.Store(workdir=tmp_path / "w2", remote=str(remote), run_id="901").open(), exes, st, fence,
                 date(2007, 1, 2), date(2008, 12, 31))
