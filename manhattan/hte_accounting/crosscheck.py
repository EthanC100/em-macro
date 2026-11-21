"""Cross-check of one HTE run's native attempt log against the PR #86 ledger. Read-only; reports, never repairs.

Checks, each reported as a violation code:

    unregistered_computation   an HTE invocation that computed (not ``run_reused``) without a PR #86 registration
                               still active when it started
    finished_invocation_abandoned / finished_invocation_without_completion
                               a finished invocation whose accounting did not reach a valid completion
    outcome_manifest_invalid     a completion does not name an exact partition of all its registered candidates
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
from pathlib import Path

import numpy as np

from manhattan.hte import adapters, ids, store
from manhattan.hte.log import AttemptLog, verify as verify_hte_log
from manhattan.hte.runner import Runner, reconcile

from . import outcomes as O
from .bridge import BRIDGE_TYPES, _digests, _hexes, _pr86, batch_of, identities, run_records


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


def _file_name(name) -> bool:
    return isinstance(name, str) and bool(name) and name != ".." and Path(name).name == name


def _complete_manifest(batches, candidates: int) -> bool:
    """Require an exact, ordered partition before reading any batch files."""
    if not isinstance(batches, list) or not batches:
        return False
    end, files = 0, set()
    for batch in batches:
        if not isinstance(batch, dict):
            return False
        lo, hi, name = batch.get("lo"), batch.get("hi"), batch.get("file")
        if (type(lo) is not int or type(hi) is not int or lo != end or
                not lo < hi <= min(candidates, lo + O.BATCH_MAX) or not _file_name(name) or name in files or
                not isinstance(batch.get("sha256"), str) or not isinstance(batch.get("root"), str)):
            return False
        end = hi
        files.add(name)
    return end == candidates


def crosscheck(runner: Runner, ledger) -> dict:
    t0 = time.perf_counter()
    _, L, _ = _pr86()
    from manhattan import attempts as A
    v: list[dict] = []
    ws, run_id = runner.ws, runner.run_id
    verify_hte_log(ws.log_path)
    recs = run_records(AttemptLog(ws.log_path), run_id)
    if recs and all(r["type"] in BRIDGE_TYPES for r in recs):
        # A registration may be cancelled before HTE has a native invocation to reconcile.
        hrec = {"state": "not_started", "violations": [], "invocations": 0,
                "attempts": dict.fromkeys(("started", "completed", "failed", "interrupted", "unfinished",
                                           "verification"), 0)}
    else:
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
    wanted = {r["payload"]["ledger_head"]["records"] for r in recs if r["type"] in BRIDGE_TYPES
              and isinstance(r["payload"].get("ledger_head"), dict)
              and type(r["payload"]["ledger_head"].get("records")) is int}
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
        elif (r["type"] in L.COMPLETIONS + ("attempt_failed", "attempt_aborted")
              and isinstance(p.get("attempt_id"), str) and p["attempt_id"] in starts):
            summary = p.get("summary") if isinstance(p.get("summary"), dict) else {}
            term.setdefault(p["attempt_id"], []).append({"type": r["type"], "seq": r["seq"], "payload": {
                **{k: p[k] for k in ("executable", "spec_hash", "family", "data_hash", "window", "result_hash")
                   if k in p},
                "summary": {k: summary[k] for k in ("outcome_batch", "row") if k in summary}}})

    def anchored(head, code_ctx: str) -> bool:
        n = head.get("records") if isinstance(head, dict) else None
        ok = type(n) is int and 0 < n <= n_records and n in at and at[n] == head.get("head")
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
    computing, regs, completions, abandonments, replacements = 0, [], [], [], []
    segment = None
    for r in recs:
        kind, seq, payload = r["type"], r["seq"], r["payload"]
        if kind == "pr86_registered":
            if segment is not None:
                if segment["finished"]:
                    v.append({"code": "finished_invocation_superseded", "seq": segment["seq"]})
                replacements.append((segment["seq"], seq))
            regs.append(r)
            segment = {"seq": seq, "started": False, "finished": False,
                       "expected": "run_verified" if payload.get("verify_rerun") is True else "run_closed"}
        elif kind == "run_started":
            if seq not in reused:
                computing += 1
                if segment is None or segment["started"]:
                    v.append({"code": "unregistered_computation", "seq": seq})
            elif segment is not None and not segment["started"]:
                v.append({"code": "registration_without_computation", "seq": segment["seq"]})
            if segment is not None:
                segment["started"] = True
        elif segment is not None and segment["started"] and kind in ("run_closed", "run_verified"):
            if kind != segment["expected"]:
                v.append({"code": "registration_invocation_mismatch", "seq": segment["seq"]})
            segment["finished"] = True
        elif kind in BRIDGE_TYPES:
            if segment is None:
                v.append({"code": "unexpected_bridge_terminal", "seq": seq})
                continue
            registration_seq = segment["seq"]
            if kind == "pr86_completed":
                claimed = payload.get("registration_seq")
                if segment["finished"] and type(claimed) is int and claimed == registration_seq:
                    completions.append(r)
                else:
                    v.append({"code": "unexpected_bridge_terminal", "seq": seq})
            elif kind == "pr86_abandoned":
                if segment["finished"]:
                    v.append({"code": "finished_invocation_abandoned", "seq": registration_seq})
                abandonments.append((registration_seq, r))
            elif not hrec["violations"]:
                v.append({"code": "unexpected_bridge_terminal", "seq": seq})
            segment = None
    if segment is not None:
        code = "finished_invocation_without_completion" if segment["finished"] else "registration_without_terminal"
        v.append({"code": code, "seq": segment["seq"]})
    # 2. registrations: files, anchors, identities
    registered: set[str] = set()
    reg_attempts: dict[int, list[str]] = {}
    for p in regs:
        pp = p["payload"]
        head = pp.get("ledger_head")
        anchor_valid = anchored(head, f"hte seq {p['seq']}")
        try:
            if not _file_name(pp.get("registration_file")) or not isinstance(pp.get("registration_sha256"), str):
                raise store.CorruptFile("registration reference")
            arr = store.read_arrays(runner.dir / "pr86" / pp["registration_file"], pp["registration_sha256"])
            attempts = arr["attempt"]
            if (type(pp.get("attempts")) is not int or pp["attempts"] != len(idents)
                    or type(pp.get("verify_rerun")) is not bool or attempts.shape != (len(idents), 32)
                    or attempts.dtype != np.uint8 or ids.merkle_root_array(attempts) != pp.get("attempts_root")
                    or arr["executable"].shape != attempts.shape or arr["executable"].dtype != np.uint8
                    or _hexes(arr["executable"]) != [ident["executable"] for ident in idents]):
                raise store.CorruptFile("registration cardinality, identity or root")
        except (OSError, ValueError, KeyError, TypeError, OverflowError, store.CorruptFile):
            v.append({"code": "registration_file_corrupt", "seq": p["seq"]})
            continue
        aids = _hexes(attempts)
        if len(set(aids)) != len(aids) or registered.intersection(aids):
            v.append({"code": "duplicate_registered_attempt", "seq": p["seq"]})
        reg_attempts[p["seq"]] = aids
        registered.update(aids)
        for i, a in enumerate(aids):
            s = starts.get(a)
            if s is None:
                v.append({"code": "attempt_missing", "candidate": i, "attempt": a[:16]})
                continue
            if anchor_valid and s["seq"] > head["records"]:
                v.append({"code": "registered_after_anchor", "attempt": a[:16]})
            if i >= len(idents) or not L.same_identity(s["payload"], idents[i]) or \
                    s["payload"]["executable"] != idents[i]["executable"]:
                v.append({"code": "identity_mismatch", "candidate": i, "attempt": a[:16]})
    for a in starts:
        if a not in registered:
            v.append({"code": "foreign_attempt", "attempt": a[:16]})
    for prior, replacement in replacements:
        prior_ids = set(reg_attempts.get(prior, ()))
        superseded_ids = {starts[aid]["payload"].get("supersedes") for aid in reg_attempts.get(replacement, ())
                          if aid in starts and isinstance(starts[aid]["payload"].get("supersedes"), str)}
        if prior_ids != superseded_ids:
            v.append({"code": "registration_replacement_mismatch", "seq": prior, "replacement": replacement})
    for registration_seq, record in abandonments:
        payload = record["payload"]
        aids = reg_attempts.get(registration_seq, ())
        if type(payload.get("aborted")) is not int or not 0 <= payload["aborted"] <= len(aids):
            v.append({"code": "abandoned_attempt_count_invalid", "seq": record["seq"]})
        head = payload.get("ledger_head")
        if anchored(head, f"hte seq {record['seq']}"):
            for aid in aids:
                terminals = term.get(aid, [])
                if (len(terminals) != 1 or terminals[0]["type"] != "attempt_aborted" or
                        terminals[0]["seq"] > head["records"]):
                    v.append({"code": "abandoned_attempt_mismatch", "attempt": aid[:16], "seq": record["seq"]})
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
    for c in completions:
        cp = c["payload"]
        completed_regs.add(cp["registration_seq"])
        head = cp.get("ledger_head")
        anchor_valid = anchored(head, f"hte seq {c['seq']}")
        aids, batches = reg_attempts.get(cp["registration_seq"], []), cp.get("batches")
        if (type(cp.get("candidates")) is not int or cp["candidates"] != len(aids) or
                not _complete_manifest(batches, len(aids))):
            v.append({"code": "outcome_manifest_invalid", "seq": c["seq"]})
            continue
        if recomputed is not None and tuple(ids.merkle_root_array(hashes) for hashes in recomputed) != (
                cp.get("result_root"), cp.get("cohort_root")):
            v.append({"code": "result_hash_mismatch", "seq": c["seq"]})
        for b in batches:
            count = b["hi"] - b["lo"]
            try:
                arr = O.read_batch(runner.dir / "pr86", b)
                if (any(a.ndim == 0 or a.shape[0] != count for a in arr.values())
                        or any(arr[k].shape != (count, 32) or arr[k].dtype != np.uint8
                               for k in ("attempt", "candidate", "result_hash", "cohort_hash"))
                        or arr["terminal"].shape != (count,)
                        or not np.isin(arr["terminal"], list(O.TERMINAL.values())).all()):
                    raise store.CorruptFile("outcome row shape or terminal")
                bad = O.verify_batch(arr)
            except (OSError, ValueError, KeyError, IndexError, TypeError, OverflowError, store.CorruptFile):
                v.append({"code": "outcome_batch_corrupt", "file": b["file"]})
                continue
            if bad:
                v.append({"code": "outcome_batch_corrupt", "file": b["file"], "rows": bad[:5]})
            if ids.merkle_root_array(arr["result_hash"]) != b["root"]:
                v.append({"code": "outcome_batch_corrupt", "file": b["file"], "root": True})
            for k in range(count):
                i = b["lo"] + k
                a = bytes(arr["attempt"][k]).hex()
                if a != aids[i]:
                    v.append({"code": "terminal_mismatch", "candidate": i, "why": "attempt not registered here"})
                    continue
                if recomputed is not None and not (np.array_equal(recomputed[0][i], arr["result_hash"][k])
                                                   and np.array_equal(recomputed[1][i], arr["cohort_hash"][k])):
                    v.append({"code": "result_hash_mismatch", "candidate": i})
                t = term.get(a, [])
                failed = arr["terminal"][k] == O.TERMINAL["failed"]
                ok = len(t) == 1 and (not anchor_valid or t[0]["seq"] <= head["records"]) and (
                    t[0]["type"] == "attempt_failed" if failed else
                    (t[0]["type"] in L.COMPLETIONS
                     and t[0]["payload"].get("result_hash") == bytes(arr["result_hash"][k]).hex()
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
    by_type = {t: sum(any(r["type"] == t for r in terminals) for terminals in term.values())
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
