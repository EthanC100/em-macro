"""The HTE → PR #86 attempt bridge. **Dormant**: ``ENABLED`` is a constant ``False`` and every entry point refuses.

What it does when enabled (tests only, in a temporary ledger) and when the owner decisions it needs are stated
(``policy.BridgePolicy``: D-10, B4 and an approval reference; it never needs D-1):

    begin(runner)      before ``runner.run()``. Registers one PR #86 exploration attempt per candidate through
                       ``manhattan.access.register_evaluation`` (the public registration path), with the #90 identity
                       (``manhattan.hte.adapters.to_pr86_identity``: spec_hash = executable = binding + engine +
                       numerical environment). An unfinished attempt left by an interrupted invocation of the same run
                       is retried (``supersedes``), never replaced. The attempt IDs are written to a registration file
                       and anchored in HTE's own log (``pr86_registered``: the PR #86 ledger head, the file's SHA-256,
                       the Merkle root of the IDs), so registration is provably before the computation.
    complete(runner, completion_writer=...)
                       after the run closes (or after a ``verify_rerun`` invocation verifies). Recomputes each
                       candidate's intrinsic ``result_hash`` and ``cohort_hash`` from the results of record
                       (``outcomes``), writes outcome batches of at most 512 candidates, and closes each attempt:
                       a completion through the supplied writer (PR #86's ``Ledger.record_evaluation`` decides
                       evaluation / rerun / nondeterminism; who may call it is owner decision A-1) or, for a
                       candidate whose evaluation failed, ``Ledger.end_attempt(failed, execution_error)``. Anchored in
                       HTE's log as ``pr86_completed``. Resumable: a crash part-way is finished by calling it again.
                       If the run is corrupted or its verification failed, every open attempt is closed as
                       ``failed: validation_error`` and nothing is completed (``pr86_failed``).
    abandon(runner)    closes every open attempt of a run that will not be resumed (for example after an engine
                       change, which is a new run) as ``aborted: interrupted`` with ``data_read`` true.

Four units are kept apart:
* a **chunk** is HTE's own attempt over up to 512 candidates (HTE log);
* an **attempt** is one PR #86 registration of one candidate executable;
* a **retry** is an attempt that supersedes an interrupted one;
* a **rerun** is a completed attempt whose PR #86 key was already completed.
A **scientific evaluation** is the binding on a data set and window (``adapters.lineage``).

Fail-closed guards, independent of the switch:
* synthetic panels only (``verify_synthetic``);
* the exploration role only, on a ``roles.Fence`` with ``enabled=False`` and no reserve window;
* no ledger inside the repository (the production ledgers are never touched);
* no performance-gated (benchmark-only) policy, because its stage-3 set depends on the other candidates;
* no stage 5.

Nothing here is evidence. The output is synthetic infrastructure validation (PR #84: E_INFRA).
"""
from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

import numpy as np

from manhattan.hte import adapters, ids, store
from manhattan.hte import data as D
from manhattan.hte.log import AttemptLog, locked
from manhattan.hte.runner import Runner, boot_seed

from . import outcomes as O
from .policy import BridgePolicy, OwnerDecisionRequired

ENABLED = False
ROOT = Path(__file__).resolve().parents[2]
REG_DOMAIN = "hte-synthetic"
BRIDGE_TYPES = ("pr86_registered", "pr86_completed", "pr86_failed", "pr86_abandoned")


class BridgeDisabled(PermissionError):
    """The integration switch is off (``ENABLED`` is a constant ``False``)."""


class BridgeRefused(RuntimeError):
    """A guard refused the operation; nothing was written beyond what the message says."""


def _pr86():
    """PR #86's public modules, imported only when the bridge is used (the package imports without PR #86)."""
    from manhattan import access, ledger, roles
    return access, ledger, roles


def batch_of(run_id: str) -> str:
    return f"hte-{run_id}"


def window_of(runner: Runner) -> dict:
    """The evaluation window of an HTE run, in the synthetic calendar: the first evaluated day to the last usable day
    before the fence."""
    p = runner.panel
    start, end = str(p.dates[runner.policy.warmup]), str(p.dates[p.fence - 1])
    return {"id": f"{REG_DOMAIN}:{start}:{end}", "start": start, "end": end, "frequency": "daily"}


def run_records(log: AttemptLog, run_id: str) -> list[dict]:
    return [r for r in log.records() if r["payload"].get("run_id") == run_id]


def identities(runner: Runner, code: dict | None = None) -> tuple[list[dict], list[dict]]:
    """Every candidate's PR #86 identity (#90 ``to_pr86_identity``) and lineage, in canonical order."""
    code = code or runner.code
    win = window_of(runner)
    kw = {"policy": runner.policy, "fence": runner.panel.fence, "stages": runner.stages}
    idents, lins = [], []
    for i in range(len(runner.view)):
        idents.append(adapters.to_pr86_identity(runner.view, i, run_id=runner.run_id, data_hash=runner.data_hash,
                                                code=code, window=win, **kw))
        lins.append(adapters.lineage(runner.view, i, code=code, **kw))
    return idents, lins


def _digests(hexes) -> np.ndarray:
    return np.frombuffer(b"".join(bytes.fromhex(h) for h in hexes), np.uint8).reshape(-1, 32)


def _hexes(arr: np.ndarray) -> list[str]:
    return [bytes(r).hex() for r in arr]


class Bridge:
    def __init__(self, ledger, policy: BridgePolicy, *, fence, caller: str = "session"):
        if ENABLED is not True:
            raise BridgeDisabled("the HTE -> PR #86 attempt bridge is disabled (manhattan.hte_accounting.bridge."
                                 "ENABLED is False)")
        if not isinstance(policy, BridgePolicy):
            raise BridgeRefused("a BridgePolicy is required")
        policy.require_registration()
        access, L, roles = _pr86()
        if not isinstance(ledger, L.Ledger) or isinstance(ledger, L.PublicIndex):
            raise BridgeRefused("attempts are registered in a full PR #86 Ledger")
        lp = Path(ledger.path).resolve()
        if lp == ROOT or ROOT in lp.parents:
            raise BridgeRefused("the bridge never writes a ledger inside the repository (production ledgers)")
        if type(fence) is not roles.Fence or fence.enabled or fence.reserve:
            raise BridgeRefused("the bridge needs a plain roles.Fence with reserve disabled and no reserve window")
        if caller not in roles.CALLERS or caller in roles.NO_DATA:
            raise BridgeRefused(f"caller {caller!r} cannot hold an attempt")
        self.ledger, self.policy, self.fence, self.caller = ledger, policy, fence, caller

    # -- guards -------------------------------------------------------------------------------------------------
    def _check_runner(self, runner: Runner) -> None:
        if not isinstance(runner, Runner):
            raise BridgeRefused("an HTE Runner is required")
        if D.verify_synthetic(runner.panel) != runner.data_hash:
            raise BridgeRefused("the panel is not the verified synthetic panel of this run")
        if runner.policy.performance_gate or runner.policy.benchmark_only:
            raise BridgeRefused("performance-gated (benchmark-only) runs are not registered: their stage-3 set "
                                "depends on the other candidates' outcomes")
        if 5 in runner.stages:
            raise BridgeRefused("stage 5 is disabled")
        win = window_of(runner)
        if date.fromisoformat(win["end"]) > self.fence.exploration_end:
            raise BridgeRefused("the run's window is not inside the exploration role")

    def _declared(self, ident: dict, domain: str):
        access, _, _ = _pr86()
        w = ident["window"]
        return [access.DeclaredWindow(w["id"], f"{REG_DOMAIN}:{domain}", date.fromisoformat(w["start"]),
                                      date.fromisoformat(w["end"]), "exploration", "evaluation", ident["data_hash"])]

    def _batch_state(self, batch: str) -> dict:
        """Starts of one batch in the ledger: executable -> open attempt IDs; and every terminal by attempt."""
        _, L, _ = _pr86()
        starts = [r for r in self.ledger.records("evaluation_started") if r["payload"].get("batch") == batch]
        done = {}
        for r in self.ledger.records():
            if r["type"] in L.COMPLETIONS + ("attempt_failed", "attempt_aborted") and \
                    isinstance(r["payload"].get("attempt_id"), str):
                done[r["payload"]["attempt_id"]] = r
        superseded = {r["payload"]["supersedes"] for r in starts if isinstance(r["payload"].get("supersedes"), str)}
        open_by_exe: dict[str, list] = {}
        for r in starts:
            if r["hash"] not in done and r["hash"] not in superseded:
                open_by_exe.setdefault(r["payload"]["executable"], []).append(r["hash"])
        return {"starts": starts, "done": done, "open": open_by_exe}

    def _ledger_head(self) -> dict:
        return {"records": len(self.ledger), "head": self.ledger.head}

    def _log_record(self, runner: Runner, typ: str, payload: dict) -> dict:
        with locked(runner.ws.log_path):
            log = AttemptLog(runner.ws.log_path)
            return log.append(typ, dict(payload, run_id=runner.run_id))

    # -- begin ----------------------------------------------------------------------------------------------------
    def begin(self, runner: Runner, *, verify_rerun: bool = False) -> dict:
        """Register one attempt per candidate before ``runner.run(verify_rerun=...)``. Idempotent until the run
        starts: a second call with no ``run_started`` since the last registration returns that registration."""
        self._check_runner(runner)
        access, _, _ = _pr86()
        recs = run_records(AttemptLog(runner.ws.log_path), runner.run_id)
        if any(r["type"] == "run_closed" for r in recs) and not verify_rerun:
            raise BridgeRefused("this run is closed: a plain invocation reuses its results and computes nothing, so "
                                "nothing is registered (use verify_rerun=True for a recomputation)")
        last = next((r for r in reversed(recs) if r["type"] in BRIDGE_TYPES or r["type"] == "run_started"), None)
        if last is not None and last["type"] == "pr86_registered":
            if last["payload"]["verify_rerun"] != verify_rerun:
                raise BridgeRefused("a registration for another invocation kind is pending")
            return dict(last["payload"], reused=True)
        idents, lins = identities(runner)
        batch = batch_of(runner.run_id)
        state = self._batch_state(batch)
        aids, new, retries = [], 0, 0
        for i, ident in enumerate(idents):
            prior = state["open"].get(ident["executable"], [])
            if len(prior) > 1:
                raise BridgeRefused(f"candidate {i} has {len(prior)} open attempts: the ledger needs review")
            ctx = access.register_evaluation(self.ledger, identity=ident,
                                             windows=self._declared(ident, runner.view.describe(i)["domain"]),
                                             caller=self.caller, fence=self.fence,
                                             supersedes=prior[0] if prior else None)
            aids.append(ctx.attempt_id)
            retries += bool(prior)
            new += not prior
        arr = _digests(aids)
        name = f"registration_{hashlib.sha256(arr.tobytes()).hexdigest()[:16]}.bin"
        sha = store.write_arrays(runner.dir / "pr86" / name, {"attempt": arr, "executable": _digests(
            [x["executable"] for x in idents])})
        payload = {"pr86_batch": batch, "verify_rerun": verify_rerun, "ledger_head": self._ledger_head(),
                   "attempts": len(aids), "new": new, "retries": retries, "registration_file": name,
                   "registration_sha256": sha, "attempts_root": ids.merkle_root_array(arr),
                   "policy": self.policy.as_dict(), "evidence": "synthetic infrastructure validation only"}
        self._log_record(runner, "pr86_registered", payload)
        return dict(payload, reused=False)

    # -- complete -------------------------------------------------------------------------------------------------
    def _registration(self, runner: Runner) -> tuple[dict, list[dict]]:
        recs = run_records(AttemptLog(runner.ws.log_path), runner.run_id)
        reg = [r for r in recs if r["type"] == "pr86_registered"]
        if not reg:
            raise BridgeRefused("no PR #86 registration preceded this run: post-hoc registration is refused")
        p = reg[-1]
        after = [r for r in recs if r["seq"] > p["seq"]]
        if any(r["type"] in ("pr86_completed", "pr86_failed", "pr86_abandoned") for r in after):
            raise BridgeRefused("this registration is already closed")
        return p, after

    def _fail_open(self, runner: Runner, p: dict, reason: str, why: str) -> None:
        aids = _hexes(store.read_arrays(runner.dir / "pr86" / p["payload"]["registration_file"],
                                        p["payload"]["registration_sha256"])["attempt"])
        state = self._batch_state(batch_of(runner.run_id))
        n = 0
        for a in aids:
            if a not in state["done"]:
                self.ledger.end_attempt(a, status="failed", reason=reason, data_read=True)
                n += 1
        self._log_record(runner, "pr86_failed", {"ledger_head": self._ledger_head(), "failed": n, "reason": reason,
                                             "why": why})
        raise BridgeRefused(why)

    def complete(self, runner: Runner, *, completion_writer=None) -> dict:
        """Close every attempt of the run's latest registration from the results of record.

        ``completion_writer(ledger, **completion)`` writes one completion. PR #86 lets only ``manhattan/ledger.py``
        and ``manhattan/engine/evaluate.py`` call ``Ledger.record_evaluation``
        (``tests/test_manhattan_binding_access.py`` ``ALLOWED``; "adding a module here is a reviewable decision").
        This module is not on that list and does not add itself (owner decision A-1,
        docs/manhattan/hte_accounting/BRIDGE.md). Without a writer the bridge refuses
        before writing anything; only the tests supply one, as PR #86's own tests call ``record_evaluation``. A run
        that is corrupted or failed verification is still closed (``end_attempt`` is not restricted)."""
        from manhattan.hte.runner import reconcile
        self._check_runner(runner)
        _, L, _ = _pr86()
        p, after = self._registration(runner)
        types = [r["type"] for r in after]
        if "run_started" not in types:
            raise BridgeRefused("the registered invocation has not started")
        if types.count("run_started") > 1:
            raise BridgeRefused("more than one invocation ran on one registration: an interrupted invocation is "
                                "re-registered (begin, which retries its attempts) before it resumes")
        if any(t in ("verification_failed", "nondeterminism") for t in types):
            self._fail_open(runner, p, "validation_error", "the run's verification failed: nothing is completed")
        want = "run_verified" if p["payload"]["verify_rerun"] else "run_closed"
        if want not in types:
            raise BridgeRefused(f"the run has no {want} record after its registration (incomplete: the attempts stay "
                                "open and are retried by the next begin)")
        rec = reconcile(runner.ws, runner.run_id)
        if rec["state"] != "closed" or rec["violations"]:
            self._fail_open(runner, p, "validation_error",
                            f"the HTE run is {rec['state']} with {len(rec['violations'])} violation(s): nothing is "
                            "completed")
        if completion_writer is None:
            raise OwnerDecisionRequired("A-1: writing PR #86 completions from HTE needs this module on PR #86's "
                                        "record_evaluation allowlist (an owner decision); no completion writer was "
                                        "supplied, so nothing is written and the attempts stay open")
        closed = [r for r in run_records(AttemptLog(runner.ws.log_path), runner.run_id) if r["type"] == "run_closed"]
        cp = closed[0]["payload"]
        table = store.read_arrays(runner.dir / cp["results_file"], cp["results_sha256"])
        reg = store.read_arrays(runner.dir / "pr86" / p["payload"]["registration_file"],
                                p["payload"]["registration_sha256"])
        if ids.merkle_root_array(reg["attempt"]) != p["payload"]["attempts_root"]:
            raise BridgeRefused("the registration file does not match its record")
        idents, lins = identities(runner)
        if _hexes(reg["executable"]) != [x["executable"] for x in idents]:
            raise BridgeRefused("the run's identities differ from its registration")
        cands = _digests([x["candidate"] for x in lins])
        intr = O.intrinsic_columns(table)
        coh = O.cohort_columns(table, cands)
        batches, rh, ch, term = O.write_batches(runner.dir / "pr86", candidates=cands, executables=reg["executable"],
                                                attempts=reg["attempt"], intr=intr, coh=coh)
        aids = _hexes(reg["attempt"])
        state = self._batch_state(batch_of(runner.run_id))
        n_obs = runner.panel.fence - runner.policy.warmup
        types_out: dict[str, int] = {}
        resumed = 0
        for b in batches:
            for i in range(b["lo"], b["hi"]):
                a = aids[i]
                if a in state["done"]:                # a resumed completion: it must be this bridge's own write
                    d = state["done"][a]
                    ok = (d["type"] == "attempt_failed") if term[i] == O.TERMINAL["failed"] else (
                        d["type"] in L.COMPLETIONS and d["payload"]["result_hash"] == bytes(rh[i]).hex())
                    if not ok:
                        raise BridgeRefused(f"attempt {a[:16]} was closed by something other than this completion")
                    resumed += 1
                    continue
                if term[i] == O.TERMINAL["failed"]:
                    self.ledger.end_attempt(a, status="failed", reason="execution_error", data_read=True)
                    types_out["attempt_failed"] = types_out.get("attempt_failed", 0) + 1
                    continue
                r = completion_writer(
                    self.ledger, **idents[i], result_hash=bytes(rh[i]).hex(), n_obs=n_obs,
                    summary={"outcome_batch": b["sha256"], "row": i - b["lo"], "batch_root": b["root"],
                             "cohort_hash": bytes(ch[i]).hex(), "hte_run": runner.run_id},
                    seed=boot_seed(idents[i]["family"], runner.data_hash, runner.policy, runner.panel.fence),
                    attempt_id=a)
                types_out[r["type"]] = types_out.get(r["type"], 0) + 1
        payload = {"ledger_head": self._ledger_head(), "registration_seq": p["seq"], "batches": batches,
                   "result_root": ids.merkle_root_array(rh), "cohort_root": ids.merkle_root_array(ch),
                   "terminals": types_out, "resumed": resumed, "candidates": len(aids)}
        self._log_record(runner, "pr86_completed", payload)
        return payload

    # -- abandon --------------------------------------------------------------------------------------------------
    def abandon(self, runner: Runner, why: str) -> dict:
        """Close every open attempt of the run's latest registration as ``aborted: interrupted`` (reads unknown,
        so ``data_read`` is true). For a run that will not be resumed (another engine or environment is a new run)."""
        if not (isinstance(why, str) and why.strip()):
            raise BridgeRefused("abandoning needs a reason")
        p, _ = self._registration(runner)
        aids = _hexes(store.read_arrays(runner.dir / "pr86" / p["payload"]["registration_file"],
                                        p["payload"]["registration_sha256"])["attempt"])
        state = self._batch_state(batch_of(runner.run_id))
        n = 0
        for a in aids:
            if a not in state["done"]:
                self.ledger.end_attempt(a, status="aborted", reason="interrupted", data_read=True)
                n += 1
        payload = {"ledger_head": self._ledger_head(), "aborted": n, "why": why}
        self._log_record(runner, "pr86_abandoned", payload)
        return payload
