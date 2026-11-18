"""The nightly runner for public-data families, and registration (criteria O-06 to O-09, O-20, O-29 to O-31).

    python -m manhattan.ops.runner nightly  --ledger-dir D --remote URL --batches DIR --asof YYYY-MM-DD [...]
    python -m manhattan.ops.runner register --ledger-dir D --remote URL --batches DIR --batch N --pr-json F [--witness-json F]
    python -m manhattan.ops.runner issue-body --health F

Everything the runner learns goes to the private ledger (``manhattan.ops.store``). Its public output, on stdout, in
``$GITHUB_STEP_SUMMARY`` and in the failure issue, is one health record (``manhattan.ops.blinding``). While it
works, file descriptors 1 and 2 point at a private log, which is committed to the private ledger at the end.

A nightly run, in order (each step is idempotent, so a rerun of the same day adds nothing):

    open      clone the private ledger and verify its hash chain
    reconcile finish every journal entry a crash left unfinished
    lock      take the ledger lock (an expired lock is broken, a live one stops the run)
    missed    record every weekday since the last heartbeat with no completed run as ``missed_run``
    capture   fetch every source and store the raw bytes and a ``capture`` record **before** evaluating
    evaluate  rebuild the point-in-time store from first-seen captures; for each registered prediction, run its
              executable over a forward window and record each new observation day (or ``missed_observation``)
    heartbeat a ``heartbeat`` record with the day's counts
    unlock, private log, mirror, verification, then the public health record

Registration (``register``) reads GitHub's merge time from the pull-request JSON (the API's ``merged_at``) and an
external witness, and records each prediction's timing and eligibility (``manhattan.ops.timing``).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import traceback
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from manhattan import access as A
from manhattan import ledger as L
from manhattan import roles
from manhattan import spec as S
from manhattan.engine import backtest
from manhattan.engine import evaluate as EV

from . import blinding as B
from . import compiler as CP
from . import data as D
from . import promotion
from . import store as ST
from . import timing as TM
from .inputs import read_json

RUNNER = "gha-public"


@dataclass
class RunConfig:
    ledger_dir: Path
    remote: str
    batches_dir: Path
    asof: date
    sources: tuple = ()
    mirror: str | None = None
    run_id: str = "local"
    run_attempt: int = 1
    commit: str = "0" * 40
    private_dir: Path | None = None
    run_calendar: str = "us_fed_fx"
    lock_ttl_minutes: int = 75
    crash_at: str | None = None
    extra: dict = field(default_factory=dict)
    fence: roles.Fence | None = None    # injected; otherwise read from config/manhattan.yaml when first needed


def run_fence(cfg: RunConfig) -> roles.Fence:
    """The fence for forward-observation attempts: the injected one, else ``config/manhattan.yaml``. The config
    module (PyYAML) is imported only here, when a run has predictions to observe, so the runner imports and runs
    without PyYAML otherwise (the hash-locked runner environment; S7 H1). A locked environment that must observe
    predictions needs the fence injected or PyYAML added to its lock (owner decision D-12)."""
    if cfg.fence is not None:
        if not isinstance(cfg.fence, roles.Fence):
            raise TypeError("RunConfig.fence is a roles.Fence")
        return cfg.fence
    from manhattan import config as MC
    return roles.Fence.from_config(MC.load())


# ---------------------------------------------------------------- the frozen batches (public specs)

def load_batch(batches_dir: Path, number: int) -> tuple[dict, dict]:
    """(manifest, {spec hash: spec}) of a batch folder, after checking canonical form, every spec hash and the
    Merkle root. (``manhattan.freeze.verify_frozen`` also needs a signed tag; registration rests on the merge time
    and the witness instead, so it is not called here.)"""
    d = Path(batches_dir) / f"AB-{number:04d}"
    raw = (d / "manifest.json").read_bytes()
    manifest = json.loads(raw)
    if S.canonical_bytes(manifest) != raw:
        raise ValueError(f"batch {number}: the manifest is not canonical")
    specs = {}
    for p in sorted((d / "specs").glob("*.json")):
        sp = S.read(p)
        specs[S.spec_hash(sp)] = sp
    if set(manifest["spec_hashes"]) - set(specs):
        raise ValueError(f"batch {number}: a spec named in the manifest is missing")
    if L.merkle_root(manifest["spec_hashes"]) != manifest["merkle_root"]:
        raise ValueError(f"batch {number}: the Merkle root does not match")
    return manifest, specs


def batch_executables(specs: dict) -> list[CP.Executable]:
    out = []
    for sp in specs.values():
        if sp["level"] == "executable":
            v = specs[sp["variant"]]
            h = specs[v["hypothesis"]]
            out.append(CP.from_specs(sp, v, h, specs[h["family"]]))
    return out


def prediction_id(manifest_hash: str, executable_hash: str) -> str:
    return "AP-" + hashlib.sha256((manifest_hash + executable_hash).encode()).hexdigest()[:16]


# ---------------------------------------------------------------- registration

def registration_intents(manifest: dict, specs: dict, *, merged: datetime, merge_commit: str,
                         witness: TM.Witness | None, batch_number: int) -> list[ST.Intent]:
    mh = S.spec_hash(manifest)
    out = []
    for x in batch_executables(specs):
        pred = prediction_id(mh, x.spec_hash)
        a = TM.assess(prediction_id=pred, spec_hash=x.spec_hash, manifest_hash=mh, merged=merged,
                      merge_commit=merge_commit, witness=witness, timing=x.hypothesis["timing"])
        a.update(batch=f"AB-{batch_number:04d}", executable=x.id, hypothesis=S.spec_id(x.hypothesis),
                 family=S.spec_id(x.family), domain=x.universe.domain, universe=x.universe.id,
                 channel=manifest.get("channel", "blind"))
        out.append(ST.Intent("registration", ("registration", pred, a["registration_status"]), a,
                             source="github_api"))
    return out


def registrations(ledger: ST.Store) -> dict:
    """The registration in force per prediction: the witnessed one when there is one, else the provisional one."""
    out = {}
    for r in ledger.of_type("registration"):
        p = r["payload"]
        if p["prediction"] not in out or p["registration_status"] == "witnessed":
            out[p["prediction"]] = p
    return out


# ---------------------------------------------------------------- observation

def code_identity(commit: str) -> dict:
    """The runner's code identity for an attempt: the checked-out commit and the engine's content digest. Fails
    closed (``LedgerError``) on an unknown or all-zero commit."""
    version = {"commit": commit, "engine_sha256": EV.code_version()["engine_sha256"]}
    L.require_code_identity(version)
    return version


def forward_attempt(reg: dict, exe: CP.Executable, asof: date, data_hash: str, version: dict) -> A.StoreAttempt:
    """The declaration of one night's forward observation of one prediction (an accounting unit, not a test:
    BINDING_ACCOUNTING.md section 2). Evaluation window: first observation to ``asof`` + 7 days; signal warm-up:
    the executable's warm-up days before it."""
    start = date.fromisoformat(reg["first_observation"])
    end = asof + timedelta(days=7)
    wid = f"forward:{reg['prediction']}:{asof.isoformat()}"
    windows = [A.DeclaredWindow(wid, exe.universe.domain, start, end, roles.FORWARD, "evaluation", data_hash)]
    if exe.warmup_days > 0:
        windows.insert(0, A.DeclaredWindow(wid + ":warmup", exe.universe.domain, start - timedelta(days=exe.warmup_days),
                                           start - timedelta(days=1), roles.FORWARD, "signal_warmup", data_hash))
    identity = {"executable": exe.id, "variant": S.spec_id(exe.variant), "hypothesis": S.spec_id(exe.hypothesis),
                "family": S.spec_id(exe.family), "batch": reg["batch"], "role": roles.FORWARD,
                "channel": reg.get("channel", "blind"), "designated": False, "spec_hash": exe.spec_hash,
                "data_hash": data_hash, "window": {"id": wid, "start": start.isoformat(), "end": end.isoformat(),
                                                   "frequency": "daily"},
                "code_version": version}
    return A.StoreAttempt("forward_observation", identity, tuple(windows),
                          {"prediction": reg["prediction"], "asof": asof.isoformat()},
                          freeze=date.fromisoformat(reg["registration_utc"][:10]))


def observation_intents(ledger: ST.Store, fs: D.FirstSeen, pit, reg: dict, exe: CP.Executable,
                        asof: date, *, attempt: A.AttemptContext) -> tuple[list[ST.Intent], dict]:
    """Observation (or missed-observation) intents for one prediction up to ``asof``, read through the forward
    window of its registered, active forward-observation ``attempt`` (Phase 4B)."""
    cal = TM.calendar(exe.universe.calendar)
    start = date.fromisoformat(reg["first_observation"])
    series = [p for _, p in exe.universe.instruments]
    srcs = [D.SOURCES[s] for s in exe.universe.sources]
    lag = max(s.lag_days for s in srcs)
    grace = max(s.grace_days for s in srcs)
    monitoring = min(fs.monitoring_start.get(s.id, asof) for s in srcs)
    counts = {"new": 0, "reconstructed": 0, "missed": 0, "expected": 0}
    if asof <= start:
        return [], counts
    # the window ends a settlement lag after asof, so the marks of asof itself (seen after its close) are in it;
    # nothing dated after asof exists in the captures, and decisions only see what was available at each close
    window = D.forward_window(attempt, pit)
    if (window.start, window.end, window.signal_start) != (start - timedelta(days=exe.warmup_days),
                                                           asof + timedelta(days=7), start):
        raise A.AccessError("the attempt did not declare this prediction's forward window")
    res = backtest.run(window, exe.strategy())
    at = {str(d): i for i, d in enumerate(res.dates.astype("datetime64[D]"))}
    out = []
    for d in cal.sessions(start + timedelta(days=1), asof):
        ds = d.isoformat()
        counts["expected"] += 1
        if fs.complete(series, ds) and ds in at:
            i = at[ds]
            base = cal.prev_session(d).isoformat()             # the return runs from the previous close
            recon = fs.reconstructed(series, ds) or (fs.complete(series, base) and fs.reconstructed(series, base)) \
                or d < monitoring
            weight = L.forward_observation_weight(eligible=bool(reg["eligible"]),
                                                  registration_weight=reg["evidential_weight"],
                                                  reconstructed=bool(recon), channel=reg.get("channel", "blind"))
            payload = {"prediction": reg["prediction"], "executable": exe.id, "date": ds,
                       "net": round(float(res.net[i]), 12), "gross": round(float(res.gross[i]), 12),
                       "cost": round(float(res.cost[i]), 12), "turnover": round(float(res.turnover[i]), 12),
                       "exposure": [round(float(e), 12) for e in res.exposure[i]],
                       "eligible": bool(reg["eligible"]), "reconstructed": bool(recon), "evidential_weight": weight,
                       "registration_status": reg["registration_status"], "role": "forward"}
            if ledger.get(("observation", reg["prediction"], ds)) is None:
                counts["new"] += 1
                counts["reconstructed"] += int(recon)
            out.append(ST.Intent("observation", ("observation", reg["prediction"], ds), payload,
                                 source=",".join(exe.universe.sources)))
        elif d + timedelta(days=lag + grace) < asof:
            if ledger.get(("missed_observation", reg["prediction"], ds)) is None:
                counts["missed"] += 1
            out.append(ST.Intent("missed_observation", ("missed_observation", reg["prediction"], ds),
                                 {"prediction": reg["prediction"], "date": ds, "reason": "data_not_available_by_grace"}))
    return out, counts


def missed_run_intents(ledger: ST.Store, asof: date, cal: TM.Calendar) -> list[ST.Intent]:
    beats = [date.fromisoformat(r["payload"]["asof"]) for r in ledger.of_type("heartbeat")]
    if not beats:
        return []
    last = max(beats)
    return [ST.Intent("missed_run", ("missed_run", d.isoformat()), {"date": d.isoformat()})
            for d in cal.sessions(last + timedelta(days=1), asof - timedelta(days=1))]


# ---------------------------------------------------------------- the nightly run

def _fail_attempts(s: ST.Store, ctxs: list, require_lock: bool = False) -> None:
    """Close every attempt of a failed batch as ``failed: execution_error`` (no result of the batch was written).
    Best effort: when this write fails too (or the lock is gone), the attempts stay unfinished and the next run's
    recovery aborts them."""
    try:
        A.commit_failures(s, ctxs, require_lock=require_lock)
    except Exception:                                           # noqa: BLE001 - recovery covers it
        traceback.print_exc()

def _counts(health: dict, **kw) -> None:
    for k, v in kw.items():
        health[k] = health.get(k, 0) + v


def nightly(cfg: RunConfig, fetchers: dict, *, clock: Callable[[], datetime] = ST.utcnow,
            summary_path: str | None = None) -> dict:
    """One nightly run. Returns the public health record (already checked by ``blinding.health``)."""
    started = clock()
    private = Path(cfg.private_dir or Path(cfg.ledger_dir).parent / "private")
    log = private / f"run-{cfg.run_id}-{cfg.run_attempt}.log"
    health = {"runner": RUNNER, "asof": cfg.asof.isoformat(), "started_utc": TM.iso(started), "commit": cfg.commit,
              "checkpoints": [], "promotion": promotion.status(None, None)[1].replace("_", "-")}
    if str(cfg.run_id).isdigit():
        health["run_id"] = int(cfg.run_id)
    health["run_attempt"] = int(cfg.run_attempt)
    stage = "open"
    s = None
    with B.quiet(log):
        try:
            s = ST.Store(workdir=Path(cfg.ledger_dir), remote=cfg.remote, run_id=str(cfg.run_id),
                         run_attempt=cfg.run_attempt, commit=cfg.commit, clock=clock, crash_at=cfg.crash_at).open()
            health["chain_ok"] = True
            health["checkpoints"].append("open")
            stage = "reconcile"
            health["journal_reconciled"] = s.reconcile()
            health["checkpoints"].append("reconcile")
            stage = "lock"
            lk = s.acquire(timedelta(minutes=cfg.lock_ttl_minutes))
            health["lock_status"], health["locks_broken"] = lk["status"], lk["broken"]
            health["checkpoints"].append("lock")
            stage = "attempts"
            # Finish, under the lock, any entry an earlier run pushed while it still held its lock; then every
            # unfinished forward attempt is a dead run's and can never finish (BINDING_ACCOUNTING.md section 8).
            health["journal_reconciled"] += s.reconcile()
            health["attempts_recovered"] = A.commit_recovery(s, epoch=True, require_lock=True)
            health["checkpoints"].append("attempts")
            stage = "missed"
            missed = missed_run_intents(s, cfg.asof, TM.calendar(cfg.run_calendar))
            new_missed = [m for m in missed if s.get(m.key) is None]
            if missed:
                s.write(missed, f"missed runs before {cfg.asof}")
            health["missed_runs"] = [r["payload"]["date"] for r in s.of_type("missed_run")][-60:]
            health["missed_runs_new"] = len(new_missed)
            health["checkpoints"].append("missed")
            stage = "capture"
            ok, failed, new_caps = [], [], 0
            for sid in cfg.sources:
                src = D.SOURCES[sid]
                try:
                    raw = fetchers[sid]()
                    it, files = D.capture_intent(src, raw, clock())
                except Exception:                                    # a source failure is recorded, not fatal
                    traceback.print_exc()
                    failed.append(sid)
                    s.write([ST.Intent("capture_failed", ("capture_failed", sid, cfg.asof.isoformat()),
                                       {"source": sid, "asof": cfg.asof.isoformat()})], f"capture failed {sid}")
                    continue
                have = s.get(it.key)
                if have is not None and "source_definition" not in have["payload"]:
                    legacy_payload = {k: v for k, v in it.payload.items() if k != "source_definition"}
                    if have["payload"] == legacy_payload:
                        # Preserve an identical legacy capture without claiming
                        # that its source definition has now been verified.
                        ok.append(sid)
                        continue
                res = s.write([it], f"capture {sid}", files=files)
                new_caps += res["appended"]
                ok.append(sid)
            health.update(sources_ok=ok, sources_failed=failed, captures_new=new_caps,
                          captures_total=len(s.of_type("capture")))
            health["checkpoints"].append("capture")
            stage = "evaluate"
            regs = registrations(s)
            exes = {}
            for bdir in sorted(Path(cfg.batches_dir).glob("AB-*")) if Path(cfg.batches_dir).exists() else []:
                manifest, specs = load_batch(cfg.batches_dir, int(bdir.name[3:]))
                for x in batch_executables(specs):
                    exes[prediction_id(S.spec_hash(manifest), x.spec_hash)] = x
            fs = D.first_seen(s, cfg.sources)
            pit = fs.pit_store()
            plans = []
            for pred, reg in sorted(regs.items()):
                x = exes.get(pred)
                if x is None or not set(x.universe.sources) <= set(cfg.sources):
                    continue
                if cfg.asof <= date.fromisoformat(reg["first_observation"]):
                    continue                                         # nothing to observe yet
                plans.append((reg, x))
            ctxs = []
            if plans:
                # Registration before exposure: every start is durable on the remote before any window opens.
                version, data_hash = code_identity(cfg.commit), pit.data_hash()
                ctxs = A.register_store_attempts(
                    s, [forward_attempt(reg, x, cfg.asof, data_hash, version) for reg, x in plans],
                    fence=run_fence(cfg), label=f"forward attempts {cfg.asof}", require_lock=True)
            health["attempts_registered"] = len(ctxs)
            intents, terminals = [], []
            try:
                for (reg, x), ctx in zip(plans, ctxs):
                    its, c = observation_intents(s, fs, pit, reg, x, cfg.asof, attempt=ctx)
                    intents += its
                    terminals.append(A.completion(ctx, s, its))
                    _counts(health, observations_new=c["new"], observations_reconstructed=c["reconstructed"],
                            missed_observations=c["missed"], observations_expected=c["expected"])
                before = len(s.of_type("conflict"))
                if intents or terminals:
                    # Results and their attempts' terminals: one journal entry, so a crash leaves both or neither;
                    # refused (Locked) if another run has broken this run's lock meanwhile.
                    A.commit_results(s, intents, terminals, f"observations to {cfg.asof}", require_lock=True)
            except Exception:
                _fail_attempts(s, ctxs, require_lock=True)
                raise
            health["conflicts"] = len(s.of_type("conflict")) - before
            health["batches"] = len({r["batch"] for r in regs.values()})
            health["predictions_registered"] = len(regs)
            health["predictions_eligible"] = sum(1 for r in regs.values() if r["eligible"])
            health["predictions_ineligible"] = sum(1 for r in regs.values() if not r["eligible"])
            health["predictions_provisional"] = sum(1 for r in regs.values() if r["registration_status"] == "provisional")
            health["observations_total"] = len(s.of_type("observation"))
            health["checkpoints"].append("evaluate")
            stage = "heartbeat"
            s.write([ST.Intent("heartbeat", ("heartbeat", cfg.asof.isoformat()),
                               {"asof": cfg.asof.isoformat(), "observations_total": health["observations_total"],
                                "captures_total": health["captures_total"]})], f"heartbeat {cfg.asof}")
            health["checkpoints"].append("heartbeat")
            stage = "unlock"
            s.release()
            health["checkpoints"].append("unlock")
            stage = "mirror"
            m = s.mirror(cfg.mirror)
            health["mirror_status"] = m["status"].replace("_", "-")
            health["checkpoints"].append("mirror")
            stage = "verify"
            v = s.verify_mirror(cfg.mirror, private / "mirror-check")
            health["mirror_ok"] = v["status"] == "equal"
            if "mirror_head" in v:
                health["mirror_head"] = v["mirror_head"]
            health["checkpoints"].append("verify")
            health["status"] = "ok" if (not failed and (health["mirror_ok"] or not cfg.mirror)) else "partial"
            health["stage"] = "done"
        except ST.SimulatedCrash:
            raise
        except ST.Locked:
            health.update(status="locked", stage=stage)
        except Exception as e:                                       # noqa: BLE001 - reported publicly by class only
            traceback.print_exc()                                    # to the private log
            health.update(B.failure(stage, e))
            if s is not None and "lock" in health["checkpoints"] and "unlock" not in health["checkpoints"]:
                try:                                                 # a handled failure ends the run: free the lock
                    s.release()
                    health["checkpoints"].append("unlock")
                    health["mirror_status"] = s.mirror(cfg.mirror)["status"].replace("_", "-")
                except Exception:                                    # noqa: BLE001 - it then expires on its own
                    traceback.print_exc()
        finally:
            # Handled failures need their diagnostics too. Never publish the log or
            # turn an unsuccessful run into a heartbeat. Simulated process deaths
            # and another runner's live lock deliberately skip this path.
            if s is not None and health.get("status") in ("ok", "partial", "failed"):
                try:
                    sys.stdout.flush()
                    files = {f"logs/{log.name}": log.read_bytes()}
                    if health.get("stage") == "done":
                        files["heartbeat.json"] = json.dumps({"asof": cfg.asof.isoformat()}).encode()
                    s.put_files(files, f"private log {cfg.run_id}.{cfg.run_attempt}")
                    # The mirror must include the final log commit, not just the
                    # chain as it stood before diagnostics were saved.
                    mirrored = s.mirror(cfg.mirror)
                    health["mirror_status"] = mirrored["status"].replace("_", "-")
                    v = s.verify_mirror(cfg.mirror, private / "mirror-check")
                    health["mirror_ok"] = mirrored["status"] == "pushed" and v["status"] == "equal"
                    health.pop("mirror_head", None)
                    if "mirror_head" in v:
                        health["mirror_head"] = v["mirror_head"]
                    if cfg.mirror and not health["mirror_ok"] and health["status"] == "ok":
                        health["status"] = "partial"
                except Exception as e:                                # private storage may itself be unavailable
                    traceback.print_exc()                             # still inside the private fd redirect
                    health.update(B.failure("private-log", e))
                    health["mirror_ok"] = False                      # an earlier check predates these diagnostics
                    health.pop("mirror_head", None)
    if s is not None:
        health["ledger_records"] = len(s.records)
        health["ledger_head"] = s.head
    finished = clock()
    health["finished_utc"] = TM.iso(finished)
    health["duration_seconds"] = int((finished - started).total_seconds())
    rec = B.health(health)
    print(B.render(rec))
    B.write_step_summary(rec, summary_path)
    return rec


# ---------------------------------------------------------------- registration run

def register(cfg: RunConfig, batch_number: int, pr: dict, witness: TM.Witness | None, *,
             clock: Callable[[], datetime] = ST.utcnow) -> dict:
    private = Path(cfg.private_dir or Path(cfg.ledger_dir).parent / "private")
    log = private / f"register-{cfg.run_id}-{cfg.run_attempt}.log"
    health = {"runner": RUNNER, "stage": "register", "started_utc": TM.iso(clock())}
    s, acquired = None, False
    with B.quiet(log):
        try:
            manifest, specs = load_batch(cfg.batches_dir, batch_number)
            merged, commit = TM.merged_at_from_api(pr)
            s = ST.Store(workdir=Path(cfg.ledger_dir), remote=cfg.remote, run_id=str(cfg.run_id),
                         run_attempt=cfg.run_attempt, commit=cfg.commit, clock=clock).open()
            s.acquire(timedelta(minutes=cfg.lock_ttl_minutes))
            acquired = True
            intents = registration_intents(manifest, specs, merged=merged, merge_commit=commit, witness=witness,
                                           batch_number=batch_number)
            s.write(intents, f"registration AB-{batch_number:04d}")
            s.release()
            acquired = False
            regs = registrations(s)
            health.update(status="ok", batches=1, predictions_registered=len(regs),
                          predictions_eligible=sum(1 for r in regs.values() if r["eligible"]),
                          predictions_ineligible=sum(1 for r in regs.values() if not r["eligible"]),
                          predictions_provisional=sum(1 for r in regs.values()
                                                      if r["registration_status"] == "provisional"),
                          ledger_records=len(s.records), ledger_head=s.head)
        except ST.SimulatedCrash:
            raise
        except ST.Locked:
            health.update(status="locked")
        except Exception as e:                                       # noqa: BLE001
            traceback.print_exc()
            health.update(B.failure("register", e))
        finally:
            if s is not None and health.get("status") in ("ok", "failed"):
                if acquired:
                    try:
                        s.release()
                    except Exception as e:                           # noqa: BLE001
                        traceback.print_exc()
                        health.update(B.failure("unlock", e))
                try:
                    sys.stdout.flush()
                    s.put_files({f"logs/{log.name}": log.read_bytes()},
                                f"private registration log {cfg.run_id}.{cfg.run_attempt}")
                    if cfg.mirror:
                        m = s.mirror(cfg.mirror)
                        v = s.verify_mirror(cfg.mirror, private / "mirror-check")
                        health["mirror_status"] = m["status"].replace("_", "-")
                        health["mirror_ok"] = m["status"] == "pushed" and v["status"] == "equal"
                        if "mirror_head" in v:
                            health["mirror_head"] = v["mirror_head"]
                        if not health["mirror_ok"] and health["status"] == "ok":
                            health["status"] = "partial"
                except Exception as e:                               # noqa: BLE001
                    traceback.print_exc()
                    health.update(B.failure("private-log", e))
                    health["mirror_ok"] = False
                    health.pop("mirror_head", None)
    if s is not None:
        health.update(ledger_records=len(s.records), ledger_head=s.head)
    rec = B.health(health)
    print(B.render(rec))
    return rec


# ---------------------------------------------------------------- exploration screening (labelled, private)

def screen(ledger: ST.Store, exes: list[CP.Executable], pit, fence, start: date, end: date) -> dict:
    """Run each executable on exploration-role data (``roles.check_read`` decides the role, as a session) and
    record a ``screening`` record in the **private** ledger, labelled exploration with evidential weight 0.
    Returns {hypothesis hash: (n_days, n_variants) array of daily net returns} for the effective-count report,
    in memory only.

    Phase 4B: each executable's screening is a registered attempt (kind ``screening``), written durably before any
    window opens; the screening records and their completions are one journalled write."""
    from manhattan.engine.pit import Reader
    import numpy as np

    version, data_hash = code_identity(ledger.commit), pit.data_hash()
    declared = []
    for x in exes:
        wid = f"{x.universe.domain}:{start}:{end}"
        identity = {"executable": x.id, "variant": S.spec_id(x.variant), "hypothesis": S.spec_id(x.hypothesis),
                    "family": S.spec_id(x.family), "batch": "pre-freeze", "role": roles.EXPLORATION,
                    "channel": x.variant.get("channel", "blind"), "designated": False, "spec_hash": x.spec_hash,
                    "data_hash": data_hash,
                    "window": {"id": wid, "start": str(start), "end": str(end), "frequency": "daily"},
                    "code_version": version}
        declared.append(A.StoreAttempt("screening", identity,
                                       (A.DeclaredWindow(wid, x.universe.domain, start, end, roles.EXPLORATION,
                                                         "evaluation", data_hash),),
                                       {"window": f"{start}:{end}"}, caller="session"))
    ctxs = A.register_store_attempts(ledger, declared, fence=fence, label=f"screening attempts {start}:{end}")
    out, intents, terminals = {}, [], []
    try:
        for x, ctx in zip(exes, ctxs):
            w = Reader(pit, caller="session", domain=x.universe.domain, fence=fence, attempt=ctx).window(start, end)
            res = backtest.run(w, x.strategy())
            summ = res.summary()
            it = ST.Intent("screening", ("screening", x.spec_hash, f"{start}:{end}"),
                           {"executable": x.id, "hypothesis": S.spec_id(x.hypothesis), "role": w.role,
                            "label": "exploration: no evidential weight", "evidential_weight": 0,
                            "window": {"start": str(start), "end": str(end)}, "data_hash": w.data_hash(),
                            "result_hash": res.result_hash(),
                            "summary": {k: (round(v, 10) if isinstance(v, float) and v == v else None)
                                        if isinstance(v, float) else v for k, v in summ.items()}},
                           source="exploration")
            intents.append(it)
            terminals.append(A.completion(ctx, ledger, [it]))
            out.setdefault(S.spec_hash(x.hypothesis), []).append(res.returns)
        A.commit_results(ledger, intents, terminals, f"screening {start}:{end}")
    except Exception:
        _fail_attempts(ledger, ctxs)
        raise
    return {h: np.column_stack(v) for h, v in out.items()}


# ---------------------------------------------------------------- CLI

def _witness(path: str | None) -> TM.Witness | None:
    if not path:
        return None
    w = read_json(path)
    verified = w.get("verified", False)
    if type(verified) is not bool:
        raise ValueError("witness verification must be a boolean")
    return TM.Witness(w["kind"], w["digest"], TM.parse_time(w["attested_utc"]) if w.get("attested_utc") else None,
                      verified)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m manhattan.ops.runner")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("nightly", "register"):
        p = sub.add_parser(name)
        p.add_argument("--ledger-dir", required=True)
        p.add_argument("--remote", required=True)
        p.add_argument("--batches", required=True)
        p.add_argument("--private-dir")
        p.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", "local"))
        p.add_argument("--attempt", type=int, default=int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")))
        p.add_argument("--commit", default=os.environ.get("GITHUB_SHA", "0" * 40))
        p.add_argument("--health-out")
        if name == "nightly":
            p.add_argument("--asof", default=datetime.now(timezone.utc).date().isoformat())
            p.add_argument("--sources", default="fred_DEXBZUS,fred_DEXMXUS,fred_DEXSFUS")
            p.add_argument("--mirror", default=os.environ.get("MANHATTAN_MIRROR_URL") or None)
        else:
            p.add_argument("--batch", type=int, required=True)
            p.add_argument("--pr-json", required=True)
            p.add_argument("--witness-json")
    ib = sub.add_parser("issue-body")
    ib.add_argument("--health", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "issue-body":
        try:
            rec = read_json(a.health)
            if not isinstance(rec, dict):
                raise ValueError("invalid health mapping")
            rec.pop("schema_version", None)
            print(B.summary_markdown(rec))
        except (OSError, ValueError, B.BlindingError):
            print(B.summary_markdown({"status": "failed", "stage": "unknown"}))
        return 0
    try:
        return _run_cli(a)
    except Exception as e:                                           # the public boundary includes log I/O failures
        rec = B.failure("runner", e)
        print(B.render(rec))                                         # never print the exception or its context
        if a.health_out:
            try:
                Path(a.health_out).write_text(B.render(rec) + "\n")
            except (OSError, ValueError):
                pass                                                # stdout still carries sanitized failure health
        return 1


def _run_cli(a) -> int:
    cfg = RunConfig(ledger_dir=Path(a.ledger_dir), remote=a.remote, batches_dir=Path(a.batches),
                    asof=date.fromisoformat(getattr(a, "asof", "2000-01-01")), run_id=a.run_id, run_attempt=a.attempt,
                    commit=a.commit, private_dir=Path(a.private_dir) if a.private_dir else None)
    if a.cmd == "nightly":
        cfg.sources = tuple(x for x in a.sources.split(",") if x)
        cfg.mirror = a.mirror
        fetchers = {sid: (lambda src=D.SOURCES[sid]: D.fetch_fred(src)) for sid in cfg.sources
                    if D.SOURCES[sid].kind == "fred"}
        rec = nightly(cfg, fetchers)
    else:
        rec = register(cfg, a.batch, read_json(a.pr_json), _witness(a.witness_json))
    if a.health_out:
        Path(a.health_out).write_text(B.render(rec) + "\n")
    return 0 if rec.get("status") == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
