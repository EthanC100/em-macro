"""A deterministic synthetic job, for smoke tests and failure-injection tests of the orchestration layer.

It follows the same attempt protocol as the HTE engine, at toy scale, so that every orchestration path (crash,
retry, cancellation, timeout, memory cap, duplicate launch, tampering) can be exercised in seconds without the
engine:

* its own attempt log (``work/attempts.jsonl``, the orchestrator's hash-chained journal format), with
  ``attempt_started`` (the intent) written before a chunk is computed and ``attempt_completed`` naming a result file
  and its SHA-256 written after the file is atomically in place;
* on every start, unterminated attempts from a crashed invocation are marked ``attempt_interrupted``; retries name
  every failed or interrupted attempt they cover in ``supersedes``; nothing is deleted;
* a unit's value is a pure function of ``(seed, unit, work)`` (iterated SHA-256: identical on every platform), so the
  final ``result_root`` is identical however the work was chunked, interrupted and resumed.

Fault injection (``faults`` in the parameters; part of the job's identity, so a faulty job is never confused with a
clean one). Each fault fires only on the invocations listed in ``fault_invocations`` (default: the first):

    crash_at_unit   hard exit (``os._exit(137)``) after the attempt covering that unit has started
    raise_at_unit   an exception inside the attempt covering that unit (the attempt is logged ``attempt_failed``)
    hang_at_unit    sleep forever inside that attempt (for timeouts and cancellation)
    alloc_mb        allocate and touch this many MiB at the start (for the memory cap)
    exit_code       exit with this code after the work (for unexpected exit codes)
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

from .journal import Journal, atomic_write, canonical, sha256_bytes

TERMINALS = ("attempt_completed", "attempt_failed", "attempt_interrupted")


def unit_value(seed: int, unit: int, work: int) -> int:
    h = f"{seed}:{unit}".encode()
    for _ in range(max(1, work)):
        h = hashlib.sha256(h).digest()
    return int.from_bytes(h[:6], "big")


class Faults:
    def __init__(self, params: dict, invocation: int):
        f = params.get("faults") or {}
        on = invocation in (params.get("fault_invocations") or [1])
        self.f = f if on else {}

    def hit(self, name: str, lo: int, hi: int) -> bool:
        u = self.f.get(name)
        return u is not None and lo <= u < hi


def _log(work: Path) -> Journal:
    return Journal(Path(work) / "attempts.jsonl")


def _state(recs: list[dict]) -> tuple[dict, dict]:
    starts = {r["hash"]: r["payload"] for r in recs if r["type"] == "attempt_started"}
    terms: dict[str, list[str]] = {}
    for r in recs:
        if r["type"] in TERMINALS:
            terms.setdefault(r["payload"]["attempt_id"], []).append(r["type"])
    return starts, terms


def run(params: dict, work: Path, ctx: dict) -> int:
    work = Path(work)
    units, chunk, seed, w = params["units"], params["chunk"], params["seed"], params["work"]
    faults = Faults(params, ctx.get("invocation", 1))
    if faults.f.get("alloc_mb"):
        block = bytearray(int(faults.f["alloc_mb"]) * 1024 * 1024)
        for i in range(0, len(block), 4096):
            block[i] = 1
    log = _log(work)
    with log.locked(timeout=10):
        recs = log.records()
        starts, terms = _state(recs)
        for aid, p in starts.items():
            if aid not in terms:
                log.append("attempt_interrupted", {"attempt_id": aid, "lo": p["lo"], "hi": p["hi"],
                                                   "reason": "interrupted"})
        recs = log.records()
        starts, terms = _state(recs)
        cov = [0] * units
        for r in recs:
            if r["type"] == "attempt_completed":
                for u in range(r["payload"]["lo"], r["payload"]["hi"]):
                    cov[u] += 1
        prior = [(p["lo"], p["hi"], aid) for aid, p in starts.items()
                 if terms.get(aid, [""])[0] in ("attempt_failed", "attempt_interrupted")]
        pending = [u for u in range(units) if not cov[u]]
        ranges, i = [], 0
        while i < len(pending):
            j = i
            while j + 1 < len(pending) and pending[j + 1] == pending[j] + 1 and j + 1 - i < chunk:
                j += 1
            ranges.append((pending[i], pending[j] + 1))
            i = j + 1
        for lo, hi in ranges:
            sup = [h for (plo, phi, h) in prior if plo < hi and lo < phi]
            rec = log.append("attempt_started", {"lo": lo, "hi": hi, "invocation": ctx.get("invocation", 1),
                                                 **({"supersedes": sup} if sup else {})})
            aid = rec["hash"]
            try:
                if faults.hit("crash_at_unit", lo, hi):
                    os._exit(137)
                if faults.hit("raise_at_unit", lo, hi):
                    raise RuntimeError("injected fault")
                if faults.hit("hang_at_unit", lo, hi):
                    while True:
                        time.sleep(0.2)
                vals = [unit_value(seed, u, w) for u in range(lo, hi)]
                if params.get("sleep_per_chunk_s"):
                    time.sleep(float(params["sleep_per_chunk_s"]))
                name = f"units/{aid[:20]}.json"
                sha = atomic_write(work / name, canonical({"lo": lo, "hi": hi, "values": vals}))
            except Exception as e:
                log.append("attempt_failed", {"attempt_id": aid, "lo": lo, "hi": hi, "reason": "execution_error",
                                              "error_class": type(e).__name__})
                raise
            except BaseException:                    # cancellation or deadline (KeyboardInterrupt)
                log.append("attempt_interrupted", {"attempt_id": aid, "lo": lo, "hi": hi, "reason": "cancelled"})
                raise
            log.append("attempt_completed", {"attempt_id": aid, "lo": lo, "hi": hi, "file": name, "sha256": sha})
        table = _table(work, log.records(), units)
        root = sha256_bytes(canonical({"values": table}))
        if not any(r["type"] == "run_closed" for r in log.records()):
            sha = atomic_write(work / "result.json", canonical({"values": table}))
            log.append("run_closed", {"result_root": root, "results_sha256": sha, "units": units})
    if faults.f.get("exit_code"):
        return int(faults.f["exit_code"])
    return 0


def _table(work: Path, recs: list[dict], units: int) -> list[int]:
    out: list = [None] * units
    for r in recs:
        if r["type"] != "attempt_completed":
            continue
        p = r["payload"]
        raw = (work / p["file"]).read_bytes()
        if sha256_bytes(raw) != p["sha256"]:
            raise ValueError(f"{p['file']} does not match its recorded hash")
        d = json.loads(raw)
        out[p["lo"]:p["hi"]] = d["values"]
    if any(v is None for v in out):
        raise ValueError("a unit has no completed attempt")
    return out


def anchor(work: Path) -> dict | None:
    p = Path(work) / "attempts.jsonl"
    return _log(work).head() if p.exists() else None


def verify_anchor(work: Path, anchor_: dict | None) -> None:
    if anchor_:
        _log(work).verify(anchor_)


def reconcile(params: dict, work: Path, anchor_: dict | None) -> dict:
    work = Path(work)
    violations: list[dict] = []
    log = _log(work)
    try:
        log.verify(anchor_)
        recs = log.records()
    except Exception as e:
        return {"state": "corrupted", "violations": [{"code": "attempt_log_damaged", "error_class": type(e).__name__}],
                "counts": {}}
    starts, terms = _state(recs)
    for aid, ts in terms.items():
        if aid not in starts:
            violations.append({"code": "terminal_without_start"})
        if len(ts) > 1:
            violations.append({"code": "multiple_terminals"})
    units = params["units"]
    cov = [0] * units
    for r in recs:
        if r["type"] == "attempt_completed":
            for u in range(r["payload"]["lo"], r["payload"]["hi"]):
                cov[u] += 1
    if any(c > 1 for c in cov):
        violations.append({"code": "double_coverage", "n": sum(1 for c in cov if c > 1)})
    by = {"started": len(starts), "completed": 0, "failed": 0, "interrupted": 0,
          "unfinished": sum(1 for a in starts if a not in terms)}
    for ts in terms.values():
        by[ts[0].split("_", 1)[1]] += 1
    closed = [r["payload"] for r in recs if r["type"] == "run_closed"]
    state = "incomplete"
    if closed:
        state = "closed"
        try:
            raw = (work / "result.json").read_bytes()
            if sha256_bytes(raw) != closed[0]["results_sha256"]:
                violations.append({"code": "results_tampered"})
            table = _table(work, recs, units)
            if sha256_bytes(canonical({"values": table})) != closed[0]["result_root"]:
                violations.append({"code": "results_not_reproducible_from_attempts"})
        except (OSError, ValueError) as e:
            violations.append({"code": "attempt_files_unreadable", "error_class": type(e).__name__})
        if by["unfinished"]:
            violations.append({"code": "unfinished_attempts_in_closed_run", "n": by["unfinished"]})
        if violations:
            state = "corrupted"
    return {"state": state, "violations": violations,
            "counts": {"units": units, "covered": sum(1 for c in cov if c == 1), "attempts": by},
            "result_root": closed[0]["result_root"] if closed else None}


def progress(params: dict, work: Path) -> dict:
    try:
        recs = _log(work).records()
    except Exception:
        return {}
    done = sum(r["payload"]["hi"] - r["payload"]["lo"] for r in recs if r["type"] == "attempt_completed")
    return {"unit": "units", "done": done, "total": params["units"]}
