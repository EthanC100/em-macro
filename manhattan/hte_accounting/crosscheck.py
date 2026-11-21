"""Cross-check of one HTE run's native attempt log against the PR #86 ledger. Read-only; reports, never repairs.

Checks, each reported as a violation code:

    unregistered_computation   an HTE invocation that computed (not ``run_reused``) without a PR #86 registration
                               recorded before it in HTE's log
    registration_file_corrupt  a registration file missing or not matching its recorded SHA-256 or Merkle root
    ledger_anchor_mismatch     an HTE bridge record names a PR #86 ledger head the ledger does not have
    registered_after_anchor    a registered attempt appears in the ledger after the head its HTE record anchored
    attempt_missing            a registered attempt ID is not an ``evaluation_started`` record of this run's batch
    identity_mismatch          a registered start's identity differs from the candidate's recomputed #90 identity
    foreign_attempt            a start in this run's batch that no registration names
    outcome_batch_corrupt      an outcome batch missing, not matching its SHA-256, or with a row whose hashes do not
                               match its columns
    result_hash_mismatch       a stored result or cohort hash differs from the one recomputed from the results of
                               record
    terminal_mismatch          a PR #86 terminal differs from the outcome (failed vs completed, result hash, batch
                               reference)
    open_after_completion      an attempt of a completed registration with no terminal
    hte_run_<state>            the HTE run does not reconcile (``corrupted``), with HTE's own violations attached
    ledger_does_not_verify, pr86_reconciler    PR #86's chain or strict reconciler reports a problem

Counts are kept at every level and never collapsed (``units``): HTE chunks, PR #86 attempts, retries, reruns,
completions, looks (completed PR #86 keys), executables, and the scientific units (bindings, candidates, variants,
hypotheses, families). ``independent_statistical_tests`` is ``None``: which unit is a test is owner decision D-1.
"""
from __future__ import annotations

import time

import numpy as np

from manhattan.hte import adapters, ids, store
from manhattan.hte.log import AttemptLog, verify as verify_hte_log
from manhattan.hte.runner import Runner, reconcile

from . import outcomes as O
from .bridge import _digests, _hexes, _pr86, batch_of, identities, run_records


def _verify_file(L, path) -> list[str]:
    """``ledger.verify(path)``, streamed: the regular case is checked line by line (``iter_verified``); anything
    irregular, or any problem, is answered by ``verify`` itself, so the errors reported are its own."""
    try:
        with open(path, "rb") as f:
            for _ in L.iter_verified(f):
                pass
        return []
    except FileNotFoundError:
        return L.verify(path)
    except L.IrregularSnapshot:
        return L.verify(path)


def crosscheck(runner: Runner, ledger) -> dict:
    t0 = time.perf_counter()
    _, L, _ = _pr86()
    from manhattan import attempts as A
    v: list[dict] = []
    ws, run_id = runner.ws, runner.run_id
    verify_hte_log(ws.log_path)
    recs = run_records(AttemptLog(ws.log_path), run_id)
    hrec = reconcile(ws, run_id)
    if hrec["state"] != "closed" or hrec["violations"]:
        if hrec["state"] == "corrupted" or hrec["violations"]:
            v.append({"code": f"hte_run_{hrec['state']}", "hte_violations": hrec["violations"]})
    errs = _verify_file(L, ledger.path)
    if errs:
        v.append({"code": "ledger_does_not_verify", "errors": errs[:5]})
    # Every ledger check reads one snapshot of the file, not the caller's object, which may be stale (another writer)
    # or differ from the file (independent review, 2026-11-21). A file that does not open is already reported; the
    # caller's object is then read so that the remaining checks still run.
    try:
        disk = L.Ledger(ledger.path, writer=ledger.writer, protocol=ledger.protocol)
    except L.LedgerError:
        disk = None
    if disk is not None and (len(disk) != len(ledger) or disk.head != ledger.head):
        v.append({"code": "ledger_object_differs_from_file", "object_records": len(ledger),
                  "file_records": len(disk)})
    src = disk if disk is not None else ledger
    batch = batch_of(run_id)
    idents, lins = identities(runner)
    # one streamed pass over the ledger (Ledger.iter_records, PR #100): this batch's starts and their terminals, kept
    # as the fields checked below, and the record hashes at every sequence number an HTE record anchors
    wanted = {r["payload"]["ledger_head"]["records"] for r in recs if r["type"] in ("pr86_registered", "pr86_completed")
              and isinstance(r["payload"].get("ledger_head"), dict)
              and isinstance(r["payload"]["ledger_head"].get("records"), int)}
    starts: dict[str, dict] = {}
    term: dict[str, list] = {}
    at: dict[int, str] = {}
    n_records = 0
    for r in src.iter_records():
        n_records += 1
        if r["seq"] in wanted:
            at[r["seq"]] = r["hash"]
        p = r["payload"]
        if not isinstance(p, dict):
            continue
        if r["type"] == "evaluation_started" and p.get("batch") == batch:
            starts[r["hash"]] = {"seq": r["seq"], "payload": {k: p[k] for k in (*L.IDENTITY_FIELDS, "supersedes")
                                                               if k in p}}
        elif r["type"] in L.COMPLETIONS + ("attempt_failed", "attempt_aborted") and p.get("attempt_id") in starts:
            summary = p.get("summary") if isinstance(p.get("summary"), dict) else {}
            term.setdefault(p["attempt_id"], []).append({"type": r["type"], "seq": r["seq"], "payload": {
                **{k: p[k] for k in ("executable", "spec_hash", "family", "data_hash", "window", "result_hash")
                   if k in p},
                "summary": {k: summary[k] for k in ("outcome_batch", "row") if k in summary}}})

    def anchored(head: dict, code_ctx: str) -> bool:
        n = head["records"]
        ok = 0 < n <= n_records and at.get(n) == head["head"]
        if not ok:
            v.append({"code": "ledger_anchor_mismatch", "record": code_ctx})
        return ok

    # 1. every computing invocation follows its own registration in HTE's chain
    reused = set()
    last_start = None
    for r in recs:
        if r["type"] == "run_started":
            last_start = r["seq"]
        elif r["type"] == "run_reused" and last_start is not None:
            reused.add(last_start)
    armed, computing, regs = False, 0, []
    for r in recs:
        if r["type"] == "pr86_registered":
            armed = True
            regs.append(r)
        elif r["type"] == "run_started" and r["seq"] not in reused:
            computing += 1
            if not armed:
                v.append({"code": "unregistered_computation", "seq": r["seq"]})
            armed = False
    # 1b. a finished invocation whose attempts were superseded by a later registration before being completed or
    # abandoned (its computation would be recorded as an interrupted one), and a registration whose invocation
    # computed nothing (run_reused), which leaves its attempts to be retried
    segment = None
    for r in recs:
        if r["type"] == "pr86_registered":
            if segment and segment["finished"] and not segment["closed"]:
                v.append({"code": "finished_invocation_superseded", "seq": segment["seq"]})
            segment = {"seq": r["seq"], "finished": False, "closed": False, "started": None}
        elif segment is None:
            continue
        elif r["type"] == "run_started" and segment["started"] is None:
            segment["started"] = r["seq"]
            if r["seq"] in reused:
                v.append({"code": "registration_without_computation", "seq": segment["seq"]})
        elif r["type"] in ("run_closed", "run_verified"):
            segment["finished"] = True
        elif r["type"] in ("pr86_completed", "pr86_failed", "pr86_abandoned"):
            segment["closed"] = True
    # 2. registrations: files, anchors, identities
    registered: set[str] = set()
    reg_attempts: dict[int, list[str]] = {}
    for p in regs:
        pp = p["payload"]
        try:
            arr = store.read_arrays(runner.dir / "pr86" / pp["registration_file"], pp["registration_sha256"])
            if ids.merkle_root_array(arr["attempt"]) != pp["attempts_root"]:
                raise store.CorruptFile("root")
        except (OSError, store.CorruptFile):
            v.append({"code": "registration_file_corrupt", "seq": p["seq"]})
            continue
        aids = _hexes(arr["attempt"])
        reg_attempts[p["seq"]] = aids
        registered.update(aids)
        anchored(pp["ledger_head"], f"hte seq {p['seq']}")
        for i, a in enumerate(aids):
            s = starts.get(a)
            if s is None:
                v.append({"code": "attempt_missing", "candidate": i, "attempt": a[:16]})
                continue
            if s["seq"] > pp["ledger_head"]["records"]:
                v.append({"code": "registered_after_anchor", "attempt": a[:16]})
            if i >= len(idents) or not L.same_identity(s["payload"], idents[i]) or \
                    s["payload"]["executable"] != idents[i]["executable"]:
                v.append({"code": "identity_mismatch", "candidate": i, "attempt": a[:16]})
    for a in starts:
        if a not in registered:
            v.append({"code": "foreign_attempt", "attempt": a[:16]})
    # 3. completions: outcome batches, recomputed hashes, PR #86 terminals
    closed = [r for r in recs if r["type"] == "run_closed"]
    recomputed = None
    if closed and hrec["state"] == "closed":
        cp = closed[0]["payload"]
        table = store.read_arrays(runner.dir / cp["results_file"], cp["results_sha256"])
        cands = _digests([x["candidate"] for x in lins])
        recomputed = (O.row_hashes(O.RESULT_DOMAIN, cands, O.intrinsic_columns(table)),
                      O.row_hashes(O.COHORT_DOMAIN, cands, O.cohort_columns(table, cands)))
    completed_regs = set()
    for c in (r for r in recs if r["type"] == "pr86_completed"):
        cp = c["payload"]
        completed_regs.add(cp["registration_seq"])
        anchored(cp["ledger_head"], f"hte seq {c['seq']}")
        aids = reg_attempts.get(cp["registration_seq"], [])
        for b in cp["batches"]:
            try:
                arr = O.read_batch(runner.dir / "pr86", b)
            except (OSError, store.CorruptFile):
                v.append({"code": "outcome_batch_corrupt", "file": b["file"]})
                continue
            bad = O.verify_batch(arr)
            if bad:
                v.append({"code": "outcome_batch_corrupt", "file": b["file"], "rows": bad[:5]})
            if ids.merkle_root_array(arr["result_hash"]) != b["root"]:
                v.append({"code": "outcome_batch_corrupt", "file": b["file"], "root": True})
            for k in range(b["hi"] - b["lo"]):
                i = b["lo"] + k
                a = bytes(arr["attempt"][k]).hex()
                if i >= len(aids) or a != aids[i]:
                    v.append({"code": "terminal_mismatch", "candidate": i, "why": "attempt not registered here"})
                    continue
                if recomputed is not None and not (np.array_equal(recomputed[0][i], arr["result_hash"][k])
                                                   and np.array_equal(recomputed[1][i], arr["cohort_hash"][k])):
                    v.append({"code": "result_hash_mismatch", "candidate": i})
                t = term.get(a, [])
                failed = arr["terminal"][k] == O.TERMINAL["failed"]
                ok = len(t) == 1 and (
                    t[0]["type"] == "attempt_failed" if failed else
                    (t[0]["type"] in L.COMPLETIONS
                     and t[0]["payload"]["result_hash"] == bytes(arr["result_hash"][k]).hex()
                     and t[0]["payload"]["summary"].get("outcome_batch") == b["sha256"]
                     and t[0]["payload"]["summary"].get("row") == k))
                if not ok:
                    v.append({"code": "terminal_mismatch", "candidate": i, "attempt": a[:16]})
    superseded = {s["payload"]["supersedes"] for s in starts.values()
                  if isinstance(s["payload"].get("supersedes"), str)}
    open_ = {a for a in starts if a not in term and a not in superseded}
    for seq in completed_regs:
        for a in reg_attempts.get(seq, []):
            if a in open_:
                v.append({"code": "open_after_completion", "attempt": a[:16]})
    # 4. PR #86's own strict audit of the whole ledger
    t_bridge = time.perf_counter() - t0
    t1 = time.perf_counter()
    try:
        pr86 = A.reconcile(ledger_path=ledger.path, ledger_anchor={"records": n_records, "head": src.head})
    except A.ReconciliationError as exc:                 # reported, never raised past the cross-check
        pr86 = {"violations": [{"code": "reconciliation_refused", "error": str(exc)[:200]}], "access_reconciled": False}
    t_pr86 = time.perf_counter() - t1
    if pr86["violations"]:
        v.append({"code": "pr86_reconciler", "n": len(pr86["violations"]), "first": pr86["violations"][:3]})
    # 5. counts at every level
    comps = [r for a in starts for r in term.get(a, []) if r["type"] in L.COMPLETIONS]
    lin_of = {x["executable"]: x for x in lins}
    acct = adapters.executable_accounting(comps, lin_of)
    by_type = {t: sum(1 for a in starts for r in term.get(a, []) if r["type"] == t)
               for t in L.COMPLETIONS + ("attempt_failed", "attempt_aborted")}
    started_exe = {s["payload"]["executable"] for s in starts.values()}
    reg_lins = [x for x in lins if x["executable"] in started_exe]
    units = {"registered_executions": len(starts),
             "completed_evaluation_keys": len({(r["payload"]["spec_hash"], r["payload"]["data_hash"],
                                                r["payload"]["window"]["id"]) for r in comps}),
             "executables": len(started_exe),
             **{unit: len({x[level] for x in reg_lins}) for unit, level in (
                 ("bindings", "binding"), ("candidates", "candidate"), ("variants", "variant"),
                 ("hypotheses", "hypothesis"), ("families", "family"))}}
    return {"run_id": run_id, "pr86_batch": batch, "consistent": not v, "violations": v,
            "hte": {"state": hrec["state"], "chunk_attempts": hrec["attempts"], "invocations": hrec["invocations"],
                    "computing_invocations": computing, "registrations": len(regs),
                    "completions": len(completed_regs)},
            "pr86": {"attempts": len(starts), "retries": len(superseded), "open": len(open_), **by_type,
                     "reconciler_violations": len(pr86["violations"]),
                     "access_reconciled": pr86["access_reconciled"]},
            "units": units, "accounting": acct, "independent_statistical_tests": None,
            "timing_s": {"bridge_checks": round(t_bridge, 3), "pr86_reconciler": round(t_pr86, 3)},
            "evidence": "synthetic infrastructure validation only (PR #84: E_INFRA); never evidence"}
