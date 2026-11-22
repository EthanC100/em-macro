"""First Light: an end-to-end SYNTHETIC reproducibility harness (S17_NEXT_PRS.md, PR-3).

    python -m manhattan.firstlight.harness --out DIR --seed N              # one run into DIR
    python -m manhattan.firstlight.harness --out DIR --seed N --resume     # finish an interrupted run in DIR
    python -m manhattan.firstlight.harness --out DIR --seed N --reproduce  # two fresh processes, DIR/run_a and
                                                                           # DIR/run_b, compared

Synthetic data only. It writes nothing outside ``--out`` and refuses to run unless ``config/manhattan.yaml`` has
``reserve.enabled``, ``claims.enabled`` and ``forward.real_money`` all false (and validates). One run:

1. builds a seeded synthetic futures-like daily dataset 2005-01-03..2019-12-31 (``synthetic.py``), marked synthetic,
   with its SHA-256;
2. loads it through ``cap.CappedStore`` (nothing dated or published after 2019-12-31), and probes the cap: a load of
   2020-01-02, a read reaching 2020-01-02 and a declared window ending 2020-01-02 are each refused;
3. declares one family and one hypothesis with a 12-point trend grid (``spec``), and freezes the batch with
   ``freeze.prepare``/``freeze.write`` into ``--out``. **This is a synthetic freeze, not owner-signed**:
   ``freeze.verify_frozen`` is called and refuses it for want of the timestamp proof and the signed tag (genuine
   verification is PR-2's); its content checks (canonical manifest, spec hashes, Merkle root) run first and pass;
4. writes a ``batch_freeze`` record to a scratch ledger under ``--out`` and anchors it, then registers each variant
   as an exploration-role attempt (``access.register_evaluation`` with the cap's own fence, every declared window
   passing ``cap.check_declared_windows`` and the capped reader) and evaluates it through ``engine.evaluate``
   (execution lag 1, monthly rebalance, 2 bp one-way proportional cost);
5. closes the run with a ``run_summary`` record and a ``run_close`` anchor (``anchor_stub.py``: a local file, D-7);
6. builds the report from the ledger plus the anchor only (``report.py``).

``reproduce`` runs the whole thing twice, each in a fresh subprocess, and compares the result hash of every
computation and the report files byte for byte.

**The variant log.** ``engine.evaluate`` also logs each exploration evaluation with ``nightshift.logs.log_variant``
(hard rule 6), whose cutoff is read from main's ``config/night.yaml`` through a ``git fetch`` at every call. That
would reach the network and write refs outside ``--out``. So the harness reads the explorer cutoff of the **local**
``config/night.yaml`` from disk (no git, no network), refuses to run if it is unreadable or earlier than
``cap.DATA_END``, and for the duration of the evaluations only gives ``log_variant`` ``min(local cutoff,
cap.DATA_END)``: it can only tighten, never widen. The rows go to ``--out/ledger/exploration_variants.csv``, never
to ``results/exploration/log.csv``, and a run is complete only with exactly one row per completion. The override
replaces a module attribute, so it is held under a module-level lock and **the harness is single-threaded**: nothing
else in the process may log variants while it runs. The clean design, an explicit cutoff argument to
``engine.evaluate``/``log_variant`` taken as the minimum with main's, changes existing files and is an owner
decision outside this PR.

**Secrets.** ``reproduce`` starts its child processes with every ``*TOKEN*``, ``*SECRET*``, ``*KEY*``,
``*PASSWORD*``, ``*CREDENTIAL*`` and ``GIT_CONFIG_*`` variable removed from the environment.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import subprocess
import sys
import threading
from datetime import date
from pathlib import Path

import numpy as np
import yaml

from manhattan import access
from manhattan import config as mconfig
from manhattan import freeze, roles
from manhattan import ledger as L
from manhattan import spec as S
from manhattan.engine import backtest, evaluate

from . import anchor_stub, cap, report, synthetic

ROOT = Path(__file__).resolve().parents[2]
HARNESS_VERSION = "firstlight-harness/1"
LABEL = "SYNTHETIC First Light harness run: synthetic freeze, not owner-signed; exploration only; no claim"
DOMAIN = "firstlight_synthetic_futures_daily"
CALLER = "explorer"
WRITER = "firstlight-harness-synthetic"
BATCH_NUMBER = 9001
WINDOW_ID = f"{DOMAIN}:{synthetic.START.isoformat()}:{synthetic.END.isoformat()}"
GRID = {"lookback_days": [21, 42, 63, 126, 189, 252], "skip_days": [0, 21]}
COST_ONE_WAY = 0.0002
COST_MODEL_ID = "proportional-2bp-one-way"
LAG, REBALANCE = 1, "M"
PROTOCOL_FILE = ROOT / "docs/manhattan/PROTOCOL_v3.1.md"
PROBE_DAY = date(2020, 1, 2)
SWITCHES = (("reserve", "enabled"), ("claims", "enabled"), ("forward", "real_money"))
LEDGER_REL, LOG_REL, ANCHORS_REL = "ledger/ledger.jsonl", "ledger/exploration_variants.csv", "anchors"
DATA_REL, FREEZE_REL, REPORT_REL = "data", "freeze", "report"
EXIT_OK, EXIT_INCOMPLETE, EXIT_REFUSED = 0, 1, 3
NIGHT_CONFIG = ROOT / "config/night.yaml"          # read from disk only: never fetched
_LOG_LOCK = threading.Lock()
SECRET_MARKERS = ("TOKEN", "SECRET", "KEY", "PASSWORD", "CREDENTIAL")


class HarnessRefused(RuntimeError):
    """The harness will not run (a protected switch, an unreadable configuration, a used output directory)."""


# ---------------------------------------------------------------- the switches

def check_switches() -> dict:
    """``config/manhattan.yaml`` must validate and hold reserve, claims and real money all exactly false."""
    try:
        cfg = mconfig.load()
    except Exception as e:                       # noqa: BLE001 - unreadable means refuse
        raise HarnessRefused(f"config/manhattan.yaml could not be read ({type(e).__name__})") from None
    if not isinstance(cfg, dict):
        raise HarnessRefused("config/manhattan.yaml is not a mapping")
    state = {}
    for section, key in SWITCHES:
        sec = cfg.get(section)
        value = sec.get(key) if isinstance(sec, dict) else None
        state[f"{section}.{key}"] = value
        if value is not False:
            raise HarnessRefused(f"{section}.{key} is {value!r}: First Light's harness runs only while it is false")
    errs = mconfig.validate(cfg)
    if errs:
        raise HarnessRefused("config/manhattan.yaml does not validate: " + "; ".join(errs))
    return state


# ---------------------------------------------------------------- specs and strategy

def specs(code_commit: str) -> dict:
    fam = S.family(mechanism="SYNTHETIC: time-series trend in a seeded synthetic futures-like panel; no economic "
                             "mechanism is claimed", mechanism_class="other", sign="+",
                   counterparty="none (synthetic data)", kill_condition="harness fixture: never promoted",
                   tail_exposure="none (synthetic data)", synthetic=True)
    hyp = S.hypothesis(fam, domain=DOMAIN,
                       data_sources=[{"name": s, "publication_lag_days": synthetic.LAG_DAYS} for s in synthetic.SERIES],
                       signal="sign of each series' trailing return over lookback_days, ending skip_days before the "
                              "decision; equal weight across the series; monthly decisions",
                       primary_binding={"universe_id": "synthetic-4", "cost_model_id": COST_MODEL_ID,
                                        "sizing_id": "equal-weight-sign"},
                       grid=GRID, predicted_sign="+", execution_lag=LAG, rebalance=REBALANCE,
                       cost_one_way=COST_ONE_WAY, windows=[WINDOW_ID], role="exploration",
                       rejection_rule="none: exploration role, evidential weight 0, no claim", synthetic=True)
    rows = [(v, S.primary_executable(hyp, v, code_commit)) for v in S.variants(hyp)]
    return {"family": fam, "hypothesis": hyp, "variants": rows}


def strategy(point: dict) -> backtest.Strategy:
    lb, skip = int(point["lookback_days"]), int(point["skip_days"])
    names = synthetic.SERIES
    need = lb + skip + 1

    def signal(view):
        w = {}
        for s in names:
            _, v = view.get(s, need)
            if v.size < need:
                return None                       # warm-up: no position until every series has its history
            w[s] = float(np.sign(v[-1 - skip] / v[-1 - skip - lb] - 1.0)) / len(names)
        return w

    instruments = tuple(backtest.Instrument(name=s, price=s, kind="excess", cost=COST_ONE_WAY) for s in names)
    return backtest.Strategy(instruments=instruments, signal=signal, rebalance=REBALANCE, lag=LAG)


# ---------------------------------------------------------------- pieces of a run

def variant_log_cutoff() -> date:
    """The cutoff the harness gives the variant log: ``min(local explorer cutoff, cap.DATA_END)``. The local
    ``config/night.yaml`` is read from disk; unreadable, or earlier than the cap, refuses the run."""
    try:
        cfg = yaml.safe_load(Path(NIGHT_CONFIG).read_text(encoding="utf-8"))
        v = cfg["explorer"]["data_end"]
        local = v if type(v) is date else date.fromisoformat(v)
    except Exception as e:                       # noqa: BLE001 - unreadable means refuse
        raise HarnessRefused(f"the local config/night.yaml explorer cutoff is unreadable ({type(e).__name__})") \
            from None
    if local < cap.DATA_END:
        raise HarnessRefused(f"the local explorer cutoff {local} is earlier than First Light's {cap.DATA_END}: "
                             "the harness's window would be refused by the variant log")
    return min(local, cap.DATA_END)


@contextlib.contextmanager
def _variant_log_cutoff(cutoff: date):
    """Give ``nightshift.logs.log_variant`` ``cutoff`` instead of a ``git fetch`` of main's night.yaml, under a
    module-level lock (single-threaded). Restored on exit."""
    from nightshift import logs
    if cutoff > cap.DATA_END:
        raise HarnessRefused("the variant-log cutoff can only tighten the cap")
    if not _LOG_LOCK.acquire(blocking=False):
        raise HarnessRefused("another harness run in this process holds the variant log (single-threaded)")
    original = logs.main_cutoff
    try:
        logs.main_cutoff = lambda: cutoff
        yield
    finally:
        logs.main_cutoff = original
        _LOG_LOCK.release()


def _probes(capped: cap.CappedStore) -> dict:
    """The cap's refusals, exercised inside the run. Any probe that is not refused stops the run."""
    before = capped.store.data_hash()
    out = {}
    try:
        capped.add("probe_after_cap", [PROBE_DAY], [1.0], lag_days=0)
        out["load_dated_2020_01_02"] = "ACCEPTED"
    except cap.CapError:
        out["load_dated_2020_01_02"] = "refused"
    try:
        capped.reader(caller=CALLER, domain=DOMAIN).window(date(2019, 12, 2), PROBE_DAY)
        out["read_2019_12_02_to_2020_01_02"] = "ACCEPTED"
    except cap.CapError:
        out["read_2019_12_02_to_2020_01_02"] = "refused"
    try:
        cap.check_declared_windows([access.DeclaredWindow("probe", DOMAIN, synthetic.START, PROBE_DAY,
                                                          roles.EXPLORATION, "evaluation", before)])
        out["declared_window_to_2020_01_02"] = "ACCEPTED"
    except cap.CapError:
        out["declared_window_to_2020_01_02"] = "refused"
    out["data_hash_unchanged"] = capped.store.data_hash() == before
    if any(v == "ACCEPTED" for v in out.values()) or not out["data_hash_unchanged"]:
        raise cap.CapError(f"a First Light cap probe was not refused: {out}")
    return out


def _freeze(out: Path, sp: dict, code_commit: str, *, resume: bool = False) -> tuple[freeze.Batch, dict]:
    """Prepare the batch; write it (fresh run) or compare it with the one on disk before writing nothing (resume);
    then ask ``verify_frozen``, which must refuse it for want of the owner's proof only."""
    fence = cap.fence()
    batch = freeze.prepare(
        BATCH_NUMBER, [sp["family"]], [sp["hypothesis"]], channel="blind",
        template_hash=S.spec_hash({"template": HARNESS_VERSION}), generator_model="none (hand-written synthetic spec)",
        protocol_hash=hashlib.sha256(PROTOCOL_FILE.read_bytes()).hexdigest(),
        fence={**access.fence_snapshot(fence, DOMAIN), "source": "manhattan.firstlight.cap (a constant in code)"},
        code_version=code_commit, critic_records=["SYNTHETIC: no critic review; harness fixture, not a review"])
    d = out / FREEZE_REL
    if resume:
        written = d / batch.id
        try:
            on_disk = (written / freeze.MANIFEST).read_bytes()
        except OSError:
            raise HarnessRefused("the interrupted run has no frozen batch") from None
        if on_disk != S.canonical_bytes(batch.manifest):
            raise HarnessRefused("the regenerated batch is not the interrupted run's")
    else:
        written = freeze.write(batch, d)
    try:
        freeze.verify_frozen(d, BATCH_NUMBER, expected_manifest_hash=batch.manifest_hash,
                             tag_is_signed=lambda tag, root: False)
        verification = "ACCEPTED"
    except freeze.FreezeError as e:
        verification = str(e)
    if "no external timestamp proof" not in verification:
        raise freeze.FreezeError(f"the synthetic freeze did not verify as expected: {verification}")
    info = {"batch": batch.id, "manifest_hash": batch.manifest_hash, "merkle_root": batch.manifest["merkle_root"],
            "kind": "synthetic freeze, not owner-signed",
            "verification": "content checks passed (canonical manifest, spec hashes, Merkle root); verify_frozen "
                            "refuses it: no external timestamp proof and no signed tag (PR-2's work)",
            "directory": written.relative_to(out).as_posix()}
    return batch, info


def _freeze_payload(sp: dict, info: dict, contract: dict) -> dict:
    return {"kind": report.HARNESS_KIND, "harness": HARNESS_VERSION, "label": LABEL, "freeze": info,
            "data": contract, "family": S.spec_id(sp["family"]), "hypothesis": S.spec_id(sp["hypothesis"]),
            "grid": GRID, "grid_size": len(sp["variants"]),
            "window": {"id": WINDOW_ID, "start": synthetic.START.isoformat(), "end": synthetic.END.isoformat(),
                       "role": roles.EXPLORATION, "domain": DOMAIN},
            "execution": {"lag": LAG, "rebalance": REBALANCE, "cost_model_id": COST_MODEL_ID,
                          "cost_one_way": str(COST_ONE_WAY)},
            "variants": [{"variant": S.spec_id(v), "executable": S.spec_id(x), "point": v["point"]}
                         for v, x in sp["variants"]]}


def _identity(sp: dict, v: dict, x: dict, data_hash: str, version: dict) -> dict:
    return {"executable": S.spec_id(x), "variant": S.spec_id(v), "hypothesis": S.spec_id(sp["hypothesis"]),
            "family": S.spec_id(sp["family"]), "batch": f"AB-{BATCH_NUMBER:04d}", "channel": "blind",
            "role": roles.EXPLORATION, "designated": False, "spec_hash": S.spec_hash(x), "data_hash": data_hash,
            "window": {"id": WINDOW_ID, "start": synthetic.START.isoformat(), "end": synthetic.END.isoformat(),
                       "frequency": "daily"},
            "code_version": version}


def _prepare_out(out: Path, resume: bool) -> None:
    if resume:
        if not (out / LEDGER_REL).is_file():
            raise HarnessRefused(f"--resume needs an earlier run's ledger in {out}")
        return
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise HarnessRefused(f"{out} is not empty: every run writes into a new directory")
    out.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------- one run

def run(out: Path, seed: int, *, resume: bool = False, after_register=None) -> dict:
    """One harness run into ``out`` (or, with ``resume``, the completion of an interrupted one). ``after_register``
    (tests only) is called with ``(index, attempt context)`` after each registration, before the window is opened:
    the fault-injection point."""
    switches = check_switches()
    log_cutoff = variant_log_cutoff()
    out = Path(out).resolve()
    _prepare_out(out, resume)
    version = evaluate.code_version()
    code_commit = version["commit"]
    data_dir = out / DATA_REL
    contract, raw = synthetic.make(seed)
    if resume:                                   # compare everything before writing anything
        try:
            prior = synthetic.read_contract(data_dir)
        except (OSError, ValueError):
            raise HarnessRefused("the interrupted run's data contract is unreadable") from None
        if {k: v for k, v in prior.items() if k != "pit_data_hash"} != contract:
            raise HarnessRefused("the regenerated dataset is not the interrupted run's (seed or generator)")
    else:
        synthetic.write_file(data_dir, raw)
    capped = synthetic.load(data_dir, contract)
    contract["pit_data_hash"] = capped.store.data_hash()
    if resume:
        if prior != contract:
            raise HarnessRefused("the regenerated dataset is not the interrupted run's")
    else:
        synthetic.write_contract(data_dir, contract)
    probes = _probes(capped)
    sp = specs(code_commit)
    batch, info = _freeze(out, sp, code_commit, resume=resume)

    ledger_path, anchors_dir = out / LEDGER_REL, out / ANCHORS_REL
    protocol = hashlib.sha256(PROTOCOL_FILE.read_bytes()).hexdigest()
    book = L.Ledger(ledger_path, writer=WRITER, protocol=protocol)
    payload = _freeze_payload(sp, info, contract)
    runs = sum(1 for _ in book.iter_records("run_summary"))
    run_id = f"firstlight-synthetic-seed{seed}-run{runs + 1}"
    if resume:
        check = anchor_stub.verify_against_anchor(ledger_path, anchors_dir, open_run=True)
        if not check["ok"]:
            raise HarnessRefused("the interrupted ledger does not match its anchors: " + "; ".join(check["problems"]))
        frozen = [r for r in book.iter_records("batch_freeze") if r["payload"].get("kind") == report.HARNESS_KIND]
        if len(frozen) != 1 or frozen[0]["payload"] != json.loads(S.canonical_bytes(payload)):
            raise HarnessRefused("the interrupted ledger's batch_freeze record is not this batch")
    else:
        book.append("batch_freeze", payload)
        anchor_stub.write_anchor(anchors_dir, ledger_path, event="batch_freeze", run_id=run_id,
                                 code_commit=code_commit)

    done = {r["payload"]["spec_hash"] for r in book.iter_records() if r["type"] in L.COMPLETIONS
            and r["payload"].get("window", {}).get("id") == WINDOW_ID}
    open_by_spec = {}
    for r in book.unfinished():
        if not book.is_superseded(r["hash"]):
            open_by_spec[r["payload"].get("spec_hash")] = r["hash"]
    counts = {"evaluated": 0, "skipped_completed": 0, "retried_interrupted": 0, "failed": 0}
    data_hash = capped.store.data_hash()
    with _variant_log_cutoff(log_cutoff):
        for i, (v, x) in enumerate(sp["variants"]):
            xh = S.spec_hash(x)
            if xh in done:
                counts["skipped_completed"] += 1
                continue
            dw = access.DeclaredWindow(WINDOW_ID, DOMAIN, synthetic.START, synthetic.END, roles.EXPLORATION,
                                       "evaluation", data_hash)
            cap.check_declared_windows([dw])
            capped.reader(caller=CALLER, domain=DOMAIN).window(dw.start, dw.end)      # the cap's own read check
            supersedes = open_by_spec.get(xh)
            ctx = access.register_evaluation(book, identity=_identity(sp, v, x, data_hash, version), windows=[dw],
                                             caller=CALLER, fence=cap.fence(), supersedes=supersedes)
            counts["retried_interrupted"] += supersedes is not None
            if after_register is not None:
                after_register(i, ctx)
            w = ctx.window(capped.store)
            try:
                evaluate.evaluate(w, strategy(v["point"]), ledger=book, executable=x, variant=v,
                                  hypothesis=sp["hypothesis"], family=sp["family"], batch=f"AB-{BATCH_NUMBER:04d}",
                                  channel="blind", designated=False, window_id=WINDOW_ID, seed=seed,
                                  description=f"SYNTHETIC First Light harness: {S.spec_id(v)} {v['point']}",
                                  log_path=out / LOG_REL, attempt=ctx)
                counts["evaluated"] += 1
            except Exception:                    # noqa: BLE001 - evaluate closed the attempt; the census shows it
                counts["failed"] += 1
    book.append("run_summary", {"kind": report.HARNESS_KIND, "harness": HARNESS_VERSION, "run_id": run_id,
                                "mode": "resume" if resume else "fresh", "probes": probes, "switches": switches,
                                "this_run": counts, **book.run_summary_payload()})
    anchor_stub.write_anchor(anchors_dir, ledger_path, event="run_close", run_id=run_id, code_commit=code_commit)
    try:
        files = report.write(ledger_path, anchors_dir, out / REPORT_REL, variant_log=out / LOG_REL)
    except report.ReportRefused as e:
        return {"out": str(out), "complete": False, "census": None, "this_run": counts, "report_refused": str(e),
                "report_sha256": None}
    rep = json.loads(files[report.REPORT_JSON])
    c = rep["census"]
    complete = (counts["failed"] == 0 and c["balanced"] and c["unfinished"] == 0 and c["failed"] == 0
                and c["aborted"] == 0 and c["violations"] == 0
                and rep["variants_evaluated"] == rep["variants_in_grid"])
    return {"out": str(out), "complete": complete, "census": c, "this_run": counts,
            "report_sha256": {k: hashlib.sha256(b).hexdigest() for k, b in files.items()}}


# ---------------------------------------------------------------- reproduction

def result_hashes(ledger_path: Path) -> dict:
    """{executable@window: result_hash} of every completion in a ledger."""
    recs, errs = L.verify_snapshot(Path(ledger_path).read_bytes())
    if errs:
        raise L.LedgerError("; ".join(errs))
    out = {}
    for r in recs:
        if r["type"] in L.COMPLETIONS:
            p = r["payload"]
            out.setdefault(f"{p['executable']}@{p['window']['id']}", []).append(p["result_hash"])
    return out


def child_env(environ=None) -> dict:
    """The environment for a child run: everything but tokens, secrets, keys, passwords and credentials. The
    ``GIT_CONFIG_*`` group (count, keys and values, which can carry credentials) goes as a whole, since git refuses
    a count without its keys; the child needs only ``git rev-parse``."""
    environ = os.environ if environ is None else environ
    env = {k: v for k, v in environ.items() if not any(m in k.upper() for m in SECRET_MARKERS)
           and not k.upper().startswith("GIT_CONFIG_")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _subprocess_run(out: Path, seed: int) -> subprocess.CompletedProcess:
    env = child_env()
    return subprocess.run([sys.executable, "-m", "manhattan.firstlight.harness", "--out", str(out), "--seed",
                           str(seed)], cwd=ROOT, env=env, capture_output=True, text=True, timeout=900)


def reproduce(out: Path, seed: int) -> dict:
    """Run the harness twice, each in a fresh subprocess (``out/run_a``, ``out/run_b``), and compare: the result
    hash of every computation, the census, and the three report files byte for byte. Writes
    ``out/reproduction.json``."""
    check_switches()
    out = Path(out).resolve()
    _prepare_out(out, False)
    runs = {}
    for name in ("run_a", "run_b"):
        p = _subprocess_run(out / name, seed)
        runs[name] = {"exit": p.returncode, "stderr_tail": p.stderr[-2000:] if p.returncode else ""}
    cmp = {"schema": "firstlight.reproduction/1", "seed": seed, "runs": runs, "synthetic": True}
    if all(r["exit"] == EXIT_OK for r in runs.values()):
        ha, hb = (result_hashes(out / n / LEDGER_REL) for n in ("run_a", "run_b"))
        files = {}
        for name in (report.REPORT_JSON, report.REPORT_MD, report.PUBLIC_JSON):
            a, b = ((out / n / REPORT_REL / name).read_bytes() for n in ("run_a", "run_b"))
            files[name] = {"identical": a == b, "sha256_a": hashlib.sha256(a).hexdigest(),
                           "sha256_b": hashlib.sha256(b).hexdigest()}
        ca, cb = (json.loads((out / n / REPORT_REL / report.REPORT_JSON).read_bytes())["census"]
                  for n in ("run_a", "run_b"))
        cmp.update(computations=len(ha), result_hashes_identical=ha == hb and bool(ha),
                   differing_computations=sorted(k for k in set(ha) | set(hb) if ha.get(k) != hb.get(k)),
                   report_files=files, census_identical=ca == cb)
        cmp["reproduced"] = (cmp["result_hashes_identical"] and cmp["census_identical"]
                             and all(f["identical"] for f in files.values()))
    else:
        cmp["reproduced"] = False
    (out / "reproduction.json").write_bytes(report.dumps(cmp))
    return cmp


# ---------------------------------------------------------------- command line

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m manhattan.firstlight.harness", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True, help="the only directory the harness writes to")
    ap.add_argument("--seed", type=int, required=True)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--resume", action="store_true", help="finish an interrupted run in --out")
    mode.add_argument("--reproduce", action="store_true", help="two fresh processes into --out/run_a and run_b")
    a = ap.parse_args(argv)
    try:
        if a.reproduce:
            res = reproduce(a.out, a.seed)
            ok = res["reproduced"]
        else:
            res = run(a.out, a.seed, resume=a.resume)
            ok = res["complete"]
    except HarnessRefused as e:
        print(f"refused: {e}", file=sys.stderr)
        return EXIT_REFUSED
    print(json.dumps(res, sort_keys=True, indent=1))
    return EXIT_OK if ok else EXIT_INCOMPLETE


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    sys.exit(main())
