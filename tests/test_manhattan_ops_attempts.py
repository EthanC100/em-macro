"""Phase 4B: attempt accounting in the operational Store (forward observations and screening), crash stages,
recovery, retries and reconciliation. Synthetic data and local bare repositories only; no simulation runs."""
from __future__ import annotations

import json
import shutil
from datetime import date, timedelta

import pytest

from manhattan import access as A
from manhattan import attempts, roles
from manhattan import config as MC
from manhattan import ledger as L
from manhattan.engine import pit
from manhattan.ops import data as D
from manhattan.ops import runner as R
from manhattan.ops import store as ST
import manhattan_attempt_fixtures as F
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
    fence, sha = A.verified_fence(F.HEAD)
    (ctx,) = A.register_store_attempts(led2, [R.forward_attempt(reg, exe, date(2026, 11, 17), store.data_hash(),
                                                                R.code_identity("c" * 40), sha)], fence=fence)
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
    attempt = R.forward_attempt(reg, exe, date(2026, 11, 16), "d" * 64, R.code_identity("c" * 40), "e" * 64)
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

    def write(self, intents, label, files=None, **kw):
        if label.startswith("observations to"):
            self.crash_at = stage
        return real(self, intents, label, files, **kw)

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


def hostile(f: ST.Store, intents: list) -> dict:
    """A writer holding the deploy key: hash-valid records pushed without any API rule (the public Store.write
    refuses evidence and attempt types unless manhattan.access sealed them). Only the reconciler can catch these."""
    out = f._append_local(intents)
    f._commit("forged")
    assert f._push()
    return out


def forged_attempt(start: dict, *, asof: str | None = None, **identity) -> tuple[str, dict]:
    """A copy of a real forward attempt's start, re-keyed (new nonce and run), optionally for another night or with
    a different identity; its attempt ID recomputes."""
    p = json.loads(json.dumps(start["payload"]))
    p.update(nonce="1" * 32, run={"run_id": "forger", "run_attempt": 1}, retry_of=None)
    if asof is not None:
        p["subject"]["asof"] = asof
        ev = next(w for w in p["authorization"]["windows"] if w["purpose"] == "evaluation")
        ev["end"] = p["identity"]["window"]["end"] = "2026-12-31"
    p["identity"].update(identity)
    return A.store_attempt_id(p), p


def linked(aid: str, intents: list) -> ST.Intent:
    links = [{"key": list(it.key), "type": it.type, "disposition": "new",
              "content_hash": ST.content_hash(it.type, it.key, ST._canon(it.payload))} for it in intents]
    return A.terminal_intent(aid, "completed", data_read=True, results=links)


FORGERIES = ["unregistered_observation", "attempt_id_mismatch", "unknown_terminal", "bad_link", "bad_retry",
             "weight", "escalation", "outside_window", "wrong_executable", "registration_mismatch",
             "conflicting_observation", "second_terminal"]


@pytest.mark.parametrize("forgery", FORGERIES)
def test_hash_valid_store_forgeries_are_reported(setup, forgery):
    s = setup
    first_night(s)
    s["night"](date(2026, 11, 16), "2026-11-16T23:30:00Z")
    f = _forger(s["ledger"]())
    obs = f.of_type("observation")[-1]
    pred = obs["payload"]["prediction"]
    start = next(r for r in f.of_type("attempt_started") if r["payload"]["subject"]["prediction"] == pred)
    new_obs = dict(obs["payload"], date="2026-11-30")
    key = ("observation", pred, "2026-11-30")
    expect = {"unregistered_observation": "unregistered_protected_evaluation",
              "attempt_id_mismatch": "attempt_id_mismatch", "unknown_terminal": "terminal_without_attempt",
              "bad_link": "result_linkage_mismatch", "bad_retry": "invalid_retry",
              "weight": "evidential_weight_mismatch", "escalation": "invalid_identity_or_authorization",
              "outside_window": "result_outside_attempt_identity_or_window",
              "wrong_executable": "result_outside_attempt_identity_or_window",
              "registration_mismatch": "registration_mismatch",
              "conflicting_observation": "conflict_on_protected_record",
              "second_terminal": "conflict_on_protected_record"}[forgery]
    if forgery == "unregistered_observation":
        hostile(f, [ST.Intent("observation", key, new_obs)])
    elif forgery == "attempt_id_mismatch":
        hostile(f, [ST.Intent(A.STORE_START, (A.STORE_START, "f" * 64), start["payload"])])
    elif forgery == "unknown_terminal":
        hostile(f, [A.terminal_intent("e" * 64, "failed", reason="execution_error", data_read=False)])
    elif forgery in ("bad_link", "bad_retry", "escalation"):
        aid, p = forged_attempt(start)
        if forgery == "bad_retry":
            p["retry_of"] = start["key"][1]                         # a completed attempt is never retried
        if forgery == "escalation":
            p["identity"]["role"] = "exploration"
            for w in p["authorization"]["windows"]:
                w["role"] = "exploration"
        aid = A.store_attempt_id(p)
        its = [ST.Intent(A.STORE_START, (A.STORE_START, aid), p)]
        if forgery == "bad_link":
            its.append(A.terminal_intent(aid, "completed", data_read=True, results=[
                {"key": list(key), "type": "observation", "content_hash": "0" * 64, "disposition": "new"}]))
        hostile(f, its)
    elif forgery == "weight":                                       # weight 1 on a reconstructed observation
        hostile(f, [ST.Intent("observation", key, dict(new_obs, reconstructed=True, evidential_weight=1))])
    elif forgery == "outside_window":                               # observed after the attempt's night
        aid, p = forged_attempt(start)
        o = ST.Intent("observation", key, new_obs)
        hostile(f, [ST.Intent(A.STORE_START, (A.STORE_START, aid), p), o, linked(aid, [o])])
    elif forgery == "wrong_executable":                             # inside the window, another executable
        aid, p = forged_attempt(start, asof="2026-11-30")
        o = ST.Intent("observation", key, dict(new_obs, executable="AX-0000000000000000"))
        hostile(f, [ST.Intent(A.STORE_START, (A.STORE_START, aid), p), o, linked(aid, [o])])
    elif forgery == "registration_mismatch":                        # a specification the prediction never had
        aid, p = forged_attempt(start, asof="2026-11-30", spec_hash="a" * 64)
        o = ST.Intent("observation", key, new_obs)
        hostile(f, [ST.Intent(A.STORE_START, (A.STORE_START, aid), p), o, linked(aid, [o])])
    elif forgery == "conflicting_observation":
        hostile(f, [ST.Intent("observation", tuple(obs["key"]), dict(obs["payload"], net=0.5))])
    else:
        aid = f.of_type("attempt_completed")[0]["key"][1]
        res = hostile(f, [A.terminal_intent(aid, "failed", reason="execution_error", data_read=True)])
        assert res["conflict"] == 1 and res["appended"] == 0
    r = audit(_forger(f))
    assert expect in codes(r) and not r["access_reconciled"], codes(r)


def test_contradictions_through_the_public_api_are_refused(setup):
    """S7 M2/M5: the public Store API cannot write a second terminal, a different observation value, or any
    evidence or attempt record at all without manhattan.access; nothing reaches the chain."""
    s = setup
    first_night(s)
    s["night"](date(2026, 11, 16), "2026-11-16T23:30:00Z")
    f = _forger(s["ledger"]())
    before = len(f.records)
    aid = f.of_type("attempt_completed")[0]["key"][1]
    obs = f.of_type("observation")[-1]
    for its in ([A.terminal_intent(aid, "failed", reason="execution_error", data_read=True)],
                [ST.Intent("observation", tuple(obs["key"]), dict(obs["payload"], net=0.5))]):
        with pytest.raises(ST.StoreError, match="manhattan.access"):
            f.write(its, "contradiction")
    assert len(_forger(f).records) == before and audit(_forger(f))["access_reconciled"]


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
    assert A.commit_recovery(led, kinds=("screening",), require_lock=False) == 1
    assert not ctx.active()
    r = audit(led)
    assert r["access_reconciled"] and r["terminals_by_data_read"]["aborted_unknown"] == 1
    with pytest.raises(L.LedgerError):                               # screening also needs a known code identity
        R.screen(ST.Store(workdir=tmp_path / "w2", remote=str(remote), run_id="901").open(), exes, st, fence,
                 date(2007, 1, 2), date(2008, 12, 31))


# ================================================================== S7 audit corrections (each failed before)

def _one_ctx(s, asof=date(2026, 11, 16)):
    """One registered forward-observation attempt on a fresh clone, with its prediction, executable and store."""
    led = s["ledger"]()
    reg = sorted(R.registrations(led).items())[0][1]
    manifest, specs = R.load_batch(s["cfg"](asof).batches_dir, 1)
    exe = next(x for x in R.batch_executables(specs) if R.prediction_id(R.S.spec_hash(manifest), x.spec_hash)
               == reg["prediction"])
    fs = D.first_seen(led, ("synthetic",))
    store = fs.pit_store()
    w = ST.Store(workdir=led.workdir.parent / f"ctx-{asof}", remote=led.remote, run_id="ctx", commit="c" * 40).open()
    fence, sha = A.verified_fence(F.HEAD)
    (ctx,) = A.register_store_attempts(w, [R.forward_attempt(reg, exe, asof, store.data_hash(),
                                                             R.code_identity("c" * 40), sha)], fence=fence)
    return w, ctx, reg, exe, fs, store


@pytest.mark.parametrize("ending", ["fail", "complete", "recover"])
def test_store_window_reads_only_while_its_attempt_is_active(setup, ending):
    """S7 H2 for the Store: a forward window read after its attempt ended is refused."""
    s = setup
    first_night(s)
    w, ctx, reg, exe, fs, store = _one_ctx(s)
    win = ctx.forward_window(store)
    win.as_of(exe.universe.instruments[0][1], date(2026, 11, 16))
    if ending == "fail":
        ctx.fail("execution_error")
        assert w.get((A.STORE_TERMINAL, ctx.attempt_id))["payload"]["data_read"] is True
    elif ending == "complete":
        A.run_bound(ctx, win, exe.strategy())
        A.completion(ctx, w, [])
    else:
        assert A.commit_recovery(w, require_lock=False) == 1
    with pytest.raises(pit.AccessError, match="not registered and active"):
        win.as_of(exe.universe.instruments[0][1], date(2026, 11, 16))


def test_store_completions_need_a_read_and_cover_exactly_their_results(setup):
    """S7 M5 for the Store: no completion without a read; commit_results writes only minted, unaltered completions
    that link every result of the batch with its exact content."""
    s = setup
    first_night(s)
    from manhattan.ops import timing as TM
    cap = s["ledger"]()                                                # a capture that no attempt has observed yet
    it, files = D.capture_intent(D.SOURCES["synthetic"], D.synthetic_csv(date(2026, 11, 16)),
                                 TM.parse_time("2026-11-16T23:30:00Z"))
    cap.write([it], "capture", files=files)
    w, ctx, reg, exe, fs, store = _one_ctx(s, asof=date(2026, 11, 16))
    with pytest.raises(pit.AccessError, match="read nothing"):
        A.completion(ctx, w, [])
    its, _ = R.observation_intents(w, fs, store, reg, exe, date(2026, 11, 16), attempt=ctx)
    assert its and all(w.get(it.key) is None for it in its)             # new results
    outside = ST.Intent("observation", ("observation", reg["prediction"], "2026-11-20"),
                        dict(its[0].payload, date="2026-11-20"))
    with pytest.raises(pit.AccessError, match="does not belong"):       # after the attempt's night
        A.completion(ctx, w, its + [outside])
    assert ctx.active()
    done = A.completion(ctx, w, its)
    extra = ST.Intent("observation", ("observation", reg["prediction"], "2026-11-12"), dict(its[0].payload))
    altered = ST.Intent(done.type, done.key, json.loads(json.dumps(done.payload)))
    altered.payload["results"][0]["disposition"] = "duplicate"
    for results, comps in ((its + [extra], [done]),                          # a result nobody linked
                           (its, [altered]),                                  # a completion not minted here
                           (its, [A.terminal_intent(ctx.attempt_id, "completed", data_read=True,
                                                    results=done.payload["results"])]),
                           (its[:-1], [done])):                               # a linked new result missing
        with pytest.raises(pit.AccessError):
            A.commit_results(w, results, comps, "observations")
    before = len(w.records)
    A.commit_results(w, its, [done], "observations")
    assert len(w.records) == before + len(its) + 1


def test_a_run_whose_lock_was_broken_cannot_write_its_results(setup, monkeypatch):
    """S7 M2, the 75-minute case: run A is still alive when run B (A's lock expired) breaks the lock and recovers
    A's attempts. A's later write is refused, so its results never reach the chain without a valid terminal."""
    s = setup
    first_night(s)
    real = R.observation_intents
    seen = {}

    def slow(ledger, fs, pit_, reg, exe, asof, *, attempt):
        if not seen:                                        # A's first prediction: B takes over meanwhile
            seen["b"] = True
            b = ST.Store(workdir=ledger.workdir.parent / "run-b", remote=ledger.remote, run_id="B",
                         commit="c" * 40, clock=lambda: s["clock"].t + timedelta(hours=2)).open()
            assert b.acquire()["broken"] == 1
            b.reconcile()
            assert A.commit_recovery(b, require_lock=True) > 0
        return real(ledger, fs, pit_, reg, exe, asof, attempt=attempt)

    monkeypatch.setattr(R, "observation_intents", slow)
    h = s["night"](date(2026, 11, 16), "2026-11-16T23:30:00Z")
    assert h["status"] == "locked"
    led = s["ledger"]()
    assert led.of_type("observation") == [] and led.of_type("attempt_completed") == []
    assert led.of_type("conflict") == []
    r = audit(led)
    assert r["access_reconciled"], r["violations"]
    assert r["aborted"] == r["registered_executions"] > 0


def test_a_pending_entry_pushed_under_the_lock_is_finished_before_recovery(setup, monkeypatch):
    """The other side of the race: A pushed its results entry while it still held the lock, then died. B finishes
    that entry under its own lock before it recovers anything, so A's attempts complete instead of being aborted."""
    s = setup
    first_night(s)
    real = ST.Store.write

    def write(self, intents, label, files=None, **kw):
        if label.startswith("observations to"):
            self.crash_at = "after_journal_push"
        return real(self, intents, label, files, **kw)

    monkeypatch.setattr(ST.Store, "write", write)
    with pytest.raises(ST.SimulatedCrash):
        s["night"](date(2026, 11, 16), "2026-11-16T23:30:00Z")
    monkeypatch.undo()
    h = s["night"](date(2026, 11, 16), "2026-11-17T02:00:00Z")
    assert h["status"] == "ok" and h["attempts_recovered"] == 0
    r = audit(s["ledger"]())
    assert r["access_reconciled"] and r["aborted"] == 0


# ================================================================== S7 re-review (N8): failure while applying results

@pytest.mark.parametrize("persist", [False, True], ids=["transient", "until_restart"])
def test_failure_while_applying_results_never_contradicts_them(setup, monkeypatch, persist):
    """S7 N8. The results entry (observations + completions) is journalled and pushed; applying it then fails. The
    run must not write failed terminals for those attempts: the pending entry is finished (now, or by the next
    run's journal recovery) and is the attempts' only terminal. Restart, reconcile, and recover again: no conflict,
    no contradictory terminal, the same records."""
    s = setup
    first_night(s)
    real = ST.Store._apply
    calls = {"n": 0}

    def flaky(self, entry, intents, label):
        if label.startswith("observations to") and (persist or calls["n"] == 0):
            calls["n"] += 1
            raise ST.StoreError("injected: journal application failed")
        return real(self, entry, intents, label)

    monkeypatch.setattr(ST.Store, "_apply", flaky)
    h = s["night"](date(2026, 11, 16), "2026-11-16T23:30:00Z")
    assert h["status"] == "failed" and h["stage"] == "evaluate"
    monkeypatch.undo()
    first = s["ledger"]()
    started = {r["key"][1] for r in first.of_type("attempt_started")}
    assert first.of_type("attempt_failed") == [] and first.of_type("conflict") == []
    for when in ("2026-11-17T02:00:00Z", "2026-11-17T02:30:00Z"):     # restart, then an idempotent rerun
        assert s["night"](date(2026, 11, 16), when)["status"] == "ok"
    led = s["ledger"]()
    done = {r["key"][1] for r in led.of_type("attempt_completed")}
    assert started <= done and led.of_type("conflict") == [] and led.of_type("attempt_failed") == []
    assert led.of_type("attempt_aborted") == []
    keys = [tuple(x["key"]) for x in led.records]
    assert len(keys) == len(set(keys))
    r = audit(led)
    assert r["access_reconciled"], r["violations"]


def test_an_uncommitted_results_entry_never_becomes_a_success(setup, monkeypatch):
    """S7 N8, the other side: the results entry never reached the remote. The attempts are closed as failed
    (data read), nothing of the uncommitted evaluation is written, and the restart computes its own results."""
    s = setup
    first_night(s)
    real = ST.Store._push

    def refuse(self):
        msg = self._git("log", "-1", "--format=%s").stdout
        if msg.startswith("journal pending") and "observations to" in msg:
            raise ST.StoreError("injected: the results entry could not be pushed")
        return real(self)

    monkeypatch.setattr(ST.Store, "_push", refuse)
    h = s["night"](date(2026, 11, 16), "2026-11-16T23:30:00Z")
    assert h["status"] == "failed"
    monkeypatch.undo()
    first = s["ledger"]()
    failed = first.of_type("attempt_failed")
    assert failed and all(f["payload"]["data_read"] is True for f in failed)
    assert first.of_type("observation") == [] and first.of_type("attempt_completed") == []
    assert s["night"](date(2026, 11, 16), "2026-11-17T02:00:00Z")["status"] == "ok"
    led = s["ledger"]()
    done = {r["key"][1] for r in led.of_type("attempt_completed")}
    assert not done & {f["key"][1] for f in failed}                  # no success for the uncommitted attempts
    assert led.of_type("conflict") == []
    r = audit(led)
    assert r["access_reconciled"], r["violations"]
    assert r["failed"] == len(failed) and r["terminals_by_data_read"]["failed_read"] == len(failed)


# ================================================================== S7 re-review (N2): results bound to the computation

@pytest.mark.parametrize("fabrication", ["net", "exposure", "turnover", "unread_raw_backtest"])
def test_a_fabricated_observation_after_a_legitimate_read_is_refused(setup, fabrication):
    """S7 N2. The attempt has read its window legitimately; an observation whose computed values are not those
    of the attempt's own bound computation (access.run_bound) is refused before anything is written."""
    from manhattan.engine import backtest
    from manhattan.ops import timing as TM
    s = setup
    first_night(s)
    cap = s["ledger"]()
    it, files = D.capture_intent(D.SOURCES["synthetic"], D.synthetic_csv(date(2026, 11, 16)),
                                 TM.parse_time("2026-11-16T23:30:00Z"))
    cap.write([it], "capture", files=files)
    w, ctx, reg, exe, fs, store = _one_ctx(s, asof=date(2026, 11, 16))
    if fabrication == "unread_raw_backtest":
        # a computation outside run_bound, on the attempt's own window: read, but never bound
        backtest.run(D.forward_window(ctx, store), exe.strategy())
        its = [ST.Intent("observation", ("observation", reg["prediction"], "2026-11-16"),
                         {"prediction": reg["prediction"], "executable": exe.id, "date": "2026-11-16", "net": 0.01,
                          "gross": 0.01, "cost": 0.0, "turnover": 0.0, "exposure": [0.0], "role": "forward"})]
        match = "bound computation"
    else:
        its, _ = R.observation_intents(w, fs, store, reg, exe, date(2026, 11, 16), attempt=ctx)
        o = next(i for i in its if i.type == "observation")
        forged = dict(o.payload)
        forged[fabrication] = [0.5] * len(forged["exposure"]) if fabrication == "exposure" else 0.0123
        its = [ST.Intent(o.type, o.key, forged) if i is o else i for i in its]
        match = "values are not those"
    with pytest.raises(pit.AccessError, match=match):
        A.completion(ctx, w, its)
    assert ctx.active() and w.of_type("observation") == []


def test_the_bound_computation_is_the_attempts_own_window(setup):
    """run_bound computes only over the window the attempt itself opened."""
    s = setup
    first_night(s)
    w, ctx, reg, exe, fs, store = _one_ctx(s)
    w2, other, *_ = _one_ctx(s, asof=date(2026, 11, 17))
    with pytest.raises(pit.AccessError, match="own"):
        A.run_bound(ctx, D.forward_window(other, store), exe.strategy())


def _screening_setup(tmp_path, n=2):
    import subprocess
    from manhattan.generate import parse_reply
    from manhattan.ops import compiler as CP, mockgen
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    req = mockgen.blind_request(n_families=2, max_hypotheses=1, domains=("syn_daily",))
    fams, hyps = parse_reply(mockgen.mock_reply(req, n=2), "blind")
    exes = list(CP.iter_batch(fams, hyps, "c" * 40))[:n]
    st = pit.PitStore()
    by = {}
    for s_, p_, v_ in D.synthetic_rows(date(2008, 12, 31)):
        by.setdefault(s_, ([], []))
        by[s_][0].append(p_)
        by[s_][1].append(v_)
    for s_, (ps, vs) in by.items():
        st.add(s_, ps, vs, lag_days=0 if "px" in s_ or "evt" in s_ else 1)
    led = ST.Store(workdir=tmp_path / "w", remote=str(remote), run_id="900", commit="c" * 40).open()
    return led, exes, st, roles.Fence.from_config(MC.load())


def test_a_fabricated_screening_result_is_refused(tmp_path, monkeypatch):
    """S7 N2 for screening: a screening record whose result hash or summary is not the bound computation's is
    refused, and screen() then closes its attempts as failed (nothing of the batch is written)."""
    led, exes, st, fence = _screening_setup(tmp_path)
    real = A.completion

    def tamper(ctx, store, its):                     # the record handed in is not the bound computation's
        return real(ctx, store, [ST.Intent(i.type, i.key, {**i.payload, "result_hash": "f" * 64}) for i in its])

    monkeypatch.setattr(A, "completion", tamper)
    with pytest.raises(pit.AccessError, match="values are not those"):
        R.screen(led, exes, st, fence, date(2007, 1, 2), date(2008, 12, 31))
    assert led.of_type("screening") == [] and len(led.of_type("attempt_failed")) == len(exes)


def test_screening_failure_while_applying_results_never_contradicts_them(tmp_path, monkeypatch):
    """S7 N8 for screening: the results entry reached the journal, applying it failed; screen() writes no failed
    terminal, and finishing the journal completes the attempts without a conflict."""
    led, exes, st, fence = _screening_setup(tmp_path)
    real = ST.Store._apply

    def flaky(self, entry, intents, label):
        if label.startswith("screening 2007"):
            raise ST.StoreError("injected: journal application failed")
        return real(self, entry, intents, label)

    monkeypatch.setattr(ST.Store, "_apply", flaky)
    with pytest.raises(ST.StoreError):
        R.screen(led, exes, st, fence, date(2007, 1, 2), date(2008, 12, 31))
    monkeypatch.undo()
    later = ST.Store(workdir=tmp_path / "later", remote=led.remote, run_id="901", commit="c" * 40).open()
    assert later.of_type("attempt_failed") == []
    assert later.reconcile() == 1
    r = audit(later)
    assert r["access_reconciled"], r["violations"]
    assert r["completed"] == len(exes) and later.of_type("conflict") == []
