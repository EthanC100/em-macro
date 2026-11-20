"""The allowlisted job kinds. Nothing else can be run by the orchestrator.

Each kind validates its parameters strictly (unknown keys refused), names how many worker processes it uses, runs
one invocation, and reconciles its own accounting from persisted files only. Every kind is synthetic:

* ``smoke``: the deterministic toy job of ``smoke.py`` (failure injection for tests).
* ``hte``: one HTE run (docs/manhattan/hte/ARCHITECTURE.md) on the engine's synthetic panel and synthetic workload,
  under the engine's *default* policy. Driven only through HTE's public API (``Workspace``, ``Registry.submit`` /
  ``freeze``, ``Runner.run``, ``reconcile``); nothing in the engine is changed. Stage 5 is refused here as well as
  in the engine; test templates, performance gates and policy overrides are not reachable. Available once
  ``manhattan.hte`` is importable (PR #89).
* ``sim``: one scenario of the Manhattan simulation's *development* plan (``manhattan.sim.run``), into the job's own
  output directory. A held-out scenario, a confirmation run (``--confirm``) and the pooled rerun are refused here
  as well as in the runner.

Exit codes of an invocation (the outcome itself is in ``exit.json``): 0 done, 75 unfinished (retry), 78 refused
(never retried), 65 integrity violation (never retried), 1 error, 130 cancelled.
"""
from __future__ import annotations

import os
from pathlib import Path

from . import smoke

EXIT_OK, EXIT_RETRY, EXIT_REFUSED, EXIT_INTEGRITY, EXIT_ERROR, EXIT_CANCELLED = 0, 75, 78, 65, 1, 130


class ParamError(ValueError):
    pass


class IntegrityError(RuntimeError):
    """Persisted accounting does not match its anchor or its hashes."""


def _check(params: dict, spec: dict) -> dict:
    """``spec``: name -> (type, default, validator or None). Unknown keys and invalid values are refused."""
    if not isinstance(params, dict):
        raise ParamError("params must be an object")
    errors = [f"unknown parameter {k!r}" for k in sorted(set(params) - set(spec))]
    out = {}
    for k, (typ, default, ok) in spec.items():
        v = params.get(k, default)
        if v is None and default is None and k not in params:
            out[k] = None
            continue
        if typ is float and isinstance(v, int) and not isinstance(v, bool):
            v = float(v)
        if typ is int and isinstance(v, bool) or not isinstance(v, typ):
            errors.append(f"{k} must be {getattr(typ, '__name__', typ)}")
            continue
        if ok is not None:
            msg = ok(v)
            if msg:
                errors.append(f"{k}: {msg}")
                continue
        out[k] = v
    if errors:
        raise ParamError("; ".join(errors))
    return out


def _range(lo, hi):
    return lambda v: None if lo <= v <= hi else f"must lie in [{lo}, {hi}]"


class Kind:
    name = ""
    strict_environment = True          # resume only in the numerical environment of registration
    code_paths: tuple = ("manhattan",)

    def normalise(self, params: dict) -> dict:
        raise NotImplementedError

    def workers(self, params: dict) -> int:
        return int(params.get("workers", 1))

    def run(self, params: dict, work: Path, ctx: dict) -> int:
        raise NotImplementedError

    def reconcile(self, params: dict, work: Path, anchor: dict | None) -> dict:
        raise NotImplementedError

    def anchor(self, params: dict, work: Path) -> dict | None:
        return None

    def verify_anchor(self, params: dict, work: Path, anchor: dict | None) -> None:
        return None

    def progress(self, params: dict, work: Path) -> dict:
        return {}

    def label(self, params: dict) -> str:
        return self.name


# -- smoke ----------------------------------------------------------------------------------------------------

FAULT_KEYS = {"crash_at_unit", "raise_at_unit", "hang_at_unit", "alloc_mb", "exit_code", "spawn_helper"}


class Smoke(Kind):
    name = "smoke"

    def normalise(self, params):
        def faults_ok(f):
            if not isinstance(f, dict):
                return "must be an object"
            bad = set(f) - FAULT_KEYS
            if bad:
                return f"unknown fault(s) {sorted(bad)}"
            if any(not isinstance(v, int) or isinstance(v, bool) or v < 0 for v in f.values()):
                return "fault values are non-negative integers"
            return None
        p = _check(params, {
            "units": (int, 64, _range(1, 1_000_000)),
            "chunk": (int, 8, _range(1, 100_000)),
            "seed": (int, 20261119, _range(0, 2**63 - 1)),
            "work": (int, 200, _range(1, 1_000_000)),
            "workers": (int, 1, _range(1, 1)),
            "sleep_per_chunk_s": (float, 0.0, _range(0.0, 60.0)),
            "faults": (dict, {}, faults_ok),
            "fault_invocations": (list, [1], lambda v: None if all(isinstance(x, int) and x >= 1 for x in v)
                                  else "positive integers"),
        })
        return p

    def run(self, params, work, ctx):
        return smoke.run(params, work, ctx)

    def reconcile(self, params, work, anchor):
        return smoke.reconcile(params, work, anchor)

    def anchor(self, params, work):
        return smoke.anchor(work)

    def verify_anchor(self, params, work, anchor):
        try:
            smoke.verify_anchor(work, anchor)
        except Exception as e:
            raise IntegrityError(f"smoke attempt log does not match its anchor: {e}") from None

    def progress(self, params, work):
        return smoke.progress(params, work)

    def label(self, params):
        return f"smoke units={params['units']}"


# -- hte ------------------------------------------------------------------------------------------------------

HTE_FAULTS = ("exit_after_start", "exit_after_file", "torn_completion", "worker_raise", "worker_exit")


class Hte(Kind):
    name = "hte"

    def normalise(self, params):
        def stages_ok(v):
            if not v or any(not isinstance(x, int) or isinstance(x, bool) for x in v):
                return "a non-empty list of integers"
            if 5 in v:
                return "stage 5 (protected evaluation) is disabled"
            if set(v) - {1, 2, 3, 4} or 1 not in v:
                return "a subset of [1, 2, 3, 4] that contains 1"
            return None

        def fault_ok(v):
            kind, _, k = v.partition(":")
            return None if kind in HTE_FAULTS and k.isdigit() else f"one of {HTE_FAULTS} followed by ':k'"
        p = _check(params, {
            "target": (int, 10_000, _range(100, 2_000_000)),
            "seed": (int, 20261118, _range(0, 2**32 - 1)),
            "chunk_size": (int, 512, _range(1, 65_536)),
            "workers": (int, 1, _range(1, 64)),
            "stages": (list, [1, 2, 3, 4], stages_ok),
            "cache": (bool, True, None),
            "verify": (bool, False, None),
            "test_fault": (str, None, fault_ok),
            "fault_invocations": (list, [1], lambda v: None if all(isinstance(x, int) and x >= 1 for x in v)
                                  else "positive integers"),
        })
        p["stages"] = sorted(set(p["stages"]))
        return p

    @staticmethod
    def _mods():
        try:
            from manhattan.hte import data as D, workload as W
            from manhattan.hte.policy import Policy
            from manhattan.hte import runner as R
            from manhattan.hte.log import AttemptLog
        except ImportError as e:
            raise ParamError("manhattan.hte is not available in this checkout (PR #89 not merged)") from e
        return D, W, Policy, R, AttemptLog

    def run(self, params, work, ctx):
        D, W, Policy, R, AttemptLog = self._mods()
        if params.get("test_fault") and ctx.get("invocation", 1) in params["fault_invocations"]:
            os.environ["HTE_FAULT"] = params["test_fault"]
        else:
            os.environ.pop("HTE_FAULT", None)
        ws = R.Workspace(Path(work) / "hte")
        log = ws.log()
        if not log.of_type("registry_frozen"):
            reg = ws.registry()
            bundles, _scale = W.build(params["target"])
            reg.submit(bundles)                     # never allow_test_templates
            reg.freeze()
            log.refresh()
        root = log.of_type("registry_frozen")[0]["payload"]["root"]
        panel = D.generate(D.PanelParams(seed=params["seed"]))
        kw = dict(chunk_size=params["chunk_size"], workers=params["workers"], cache_enabled=params["cache"],
                  stages=tuple(params["stages"]), registry_root=root)
        try:
            r = R.Runner(ws, panel, Policy(), **kw)
            (Path(work) / "hte_run.json").write_text(f'{{"run_id": "{r.run_id}"}}\n')
            res = r.run()
            if not res.get("result_root") or res.get("closed") is False:
                return EXIT_RETRY
            if params["verify"]:
                R.Runner(ws, panel, Policy(), **kw).run(verify_rerun=True)
        except R.RunError as e:
            if "another runner" in str(e):
                return EXIT_RETRY
            raise
        return EXIT_OK

    def _run_id(self, work):
        p = Path(work) / "hte_run.json"
        if not p.exists():
            return None
        import json
        return json.loads(p.read_text())["run_id"]

    def reconcile(self, params, work, anchor):
        D, W, Policy, R, AttemptLog = self._mods()
        run_id = self._run_id(work)
        if run_id is None:
            return {"state": "incomplete", "violations": [], "counts": {}, "note": "no run started yet"}
        ws = R.Workspace(Path(work) / "hte")
        try:
            rec = R.reconcile(ws, run_id, anchor)
        except Exception as e:
            return {"state": "corrupted", "violations": [{"code": "reconcile_failed", "error_class": type(e).__name__}],
                    "counts": {}}
        verify_ok = True
        if params["verify"] and rec["state"] == "closed":
            verify_ok = any(r["type"] == "run_verified" and r["payload"].get("run_id") == run_id
                            for r in ws.log().records())
        state = rec["state"]
        if state == "closed" and rec["violations"]:
            state = "corrupted"
        if state == "closed" and not verify_ok:
            state = "incomplete"
        return {"state": state, "violations": rec["violations"], "run_id": run_id,
                "counts": {"registered": rec["registered"].get("candidates"), "attempts": rec["attempts"],
                           "passes": rec["passes"], "invocations": rec["invocations"],
                           "failed_invocations": len(rec["failed_invocations"])},
                "access_reconciled": rec.get("access_reconciled"),
                "independent_statistical_tests": rec.get("independent_statistical_tests")}

    def anchor(self, params, work):
        p = Path(work) / "hte" / "attempts.jsonl"
        if not p.exists():
            return None
        _, _, _, _, AttemptLog = self._mods()
        return AttemptLog(p).head()          # tolerant of a torn tail, which the next writer quarantines

    def verify_anchor(self, params, work, anchor):
        """The HTE log keeps no anchor of its own (ARCHITECTURE section 5); the orchestrator's journal does. A
        suffix deleted or a history replaced between invocations stops the job."""
        if not anchor:
            return
        p = Path(work) / "hte" / "attempts.jsonl"
        _, _, _, _, AttemptLog = self._mods()
        try:
            recs = AttemptLog(p).records()
        except Exception as e:
            raise IntegrityError(f"HTE attempt log unreadable: {type(e).__name__}") from None
        n = int(anchor["records"])
        if n > len(recs):
            raise IntegrityError(f"HTE attempt log has {len(recs)} records, its anchor names {n} (suffix deleted)")
        if n and recs[n - 1]["hash"] != anchor["head"]:
            raise IntegrityError(f"HTE attempt log record {n} does not match its anchor (history replaced)")

    def progress(self, params, work):
        p = Path(work) / "hte" / "attempts.jsonl"
        if not p.exists():
            return {"phase": "registration"}
        _, _, _, _, AttemptLog = self._mods()
        try:
            recs = AttemptLog(p).records()
        except Exception:
            return {}
        run_id = self._run_id(work)
        mine = [r for r in recs if r["payload"].get("run_id") == run_id] if run_id else []
        out = {"phase": "registration" if not run_id else "run", "log_records": len(recs)}
        for pas in ("A", "B"):
            out[f"pass_{pas}_candidates_done"] = sum(r["payload"]["hi"] - r["payload"]["lo"] for r in mine
                                                     if r["type"] == "attempt_completed"
                                                     and r["payload"]["pass"] == pas
                                                     and not r["payload"].get("verification"))
        fr = [r for r in recs if r["type"] == "registry_frozen"]
        if fr:
            out["candidates"] = fr[0]["payload"]["n_candidates"]
        out["closed"] = any(r["type"] == "run_closed" for r in mine)
        return out

    def label(self, params):
        return f"hte target={params['target']} stages={''.join(map(str, params['stages']))}"


# -- sim ------------------------------------------------------------------------------------------------------

class Sim(Kind):
    name = "sim"
    strict_environment = False        # replications pool by code hash; seeds depend on the replication number only

    def normalise(self, params):
        p = _check(params, {
            "prereg": (str, "v2", lambda v: None if v in ("v1", "v2") else "v1 or v2"),
            "scenario": (str, None, None),
            "size": (str, None, lambda v: None if v in ("STD", "LONG", "HB") else "STD, LONG or HB"),
            "reps": (int, None, _range(1, 100_000)),
            "first": (int, 0, _range(0, 100_000)),
            "label": (str, None, lambda v: None if v in ("pilot", "part", "test") else "pilot, part or test"),
            "workers": (int, 1, _range(1, 64)),
            "time_budget_minutes": (int, None, _range(1, 24 * 60)),
        })
        if p["scenario"] is None or p["size"] is None or p["reps"] is None:
            raise ParamError("scenario, size and reps are required")
        try:
            from manhattan.sim import criteria_v2, world
        except ImportError as e:
            raise ParamError("manhattan.sim is not available") from e
        s = p["scenario"]
        if world.is_heldout(s) or s.startswith("H"):
            raise ParamError(f"{s} is a held-out scenario: only a tagged confirmation run, by hand, may run it")
        if s not in world.SCENARIOS and not criteria_v2.is_twin(s):
            raise ParamError(f"unknown scenario {s}")
        if p["first"] > p["reps"]:
            raise ParamError("first must not exceed reps")
        return p

    def _out(self, work):
        return Path(work) / "sim_out"

    def run(self, params, work, ctx):
        from manhattan import prereg, prereg_v2
        from manhattan.sim import run as SR
        errs = prereg_v2.verify() if params["prereg"] == "v2" else [e for r in prereg.RECORDS for e in prereg.verify(r)]
        if errs:
            print("pre-registration does not match its recorded hash: refused", flush=True)
            return EXIT_REFUSED
        left = (ctx.get("deadline", 0) - ctx.get("now", 0)) / 60.0 - 5.0
        budget = params["time_budget_minutes"] or int(max(1.0, left))
        if ctx.get("deadline"):
            budget = int(max(1.0, min(budget, left)))
        argv = ["--prereg", params["prereg"], "--scenario", params["scenario"], "--size", params["size"],
                "--reps", str(params["reps"]), "--workers", str(params["workers"]), "--out", str(self._out(work)),
                "--time-budget-minutes", str(budget)]
        if params["first"]:
            argv += ["--first", str(params["first"])]
        if params["label"]:
            argv += ["--label", params["label"]]
        try:
            rc = SR.main(argv)
        except SystemExit as e:                   # argument or plan errors: never retried blindly
            print(f"sim refused or failed: {e}", flush=True)
            return EXIT_REFUSED if isinstance(e.code, str) else int(e.code or 0)
        return {0: EXIT_OK, SR.EXIT_BUDGET: EXIT_RETRY, 3: EXIT_REFUSED}.get(rc, EXIT_ERROR)

    def reconcile(self, params, work, anchor):
        import json
        out = self._out(work)
        violations, starts, ends = [], {}, {}
        runs = out / "runs.jsonl"
        if runs.exists():
            for line in runs.read_text(encoding="utf-8").splitlines():
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    violations.append({"code": "run_log_line_unreadable"})
                    continue
                (starts if r.get("event") == "start" else ends)[r.get("run_id")] = r
        abandoned = len(set(starts) - set(ends))
        try:
            from manhattan.sim import run as SR
            version = SR.route(params["scenario"], params["size"], params["prereg"])
            code = SR.code_hash(params["size"], version=version)
        except Exception as e:
            return {"state": "corrupted", "violations": [{"code": "code_hash_unavailable",
                                                          "error_class": type(e).__name__}], "counts": {}}
        seen: dict[int, int] = {}
        for f in out.rglob(f"{params['scenario']}_{params['size']}_*.jsonl"):
            for line in f.read_text(encoding="utf-8").splitlines():
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    violations.append({"code": "replication_line_unreadable", "file": f.name})
                    continue
                if r.get("code") == code:
                    seen[r["rep"]] = seen.get(r["rep"], 0) + 1
        dup = sum(1 for v in seen.values() if v > 1)
        if dup:
            violations.append({"code": "duplicate_replication", "n": dup})
        want = range(params["first"], params["reps"])
        have = sum(1 for r in want if r in seen)
        state = "closed" if have == len(want) else "incomplete"
        if violations and state == "closed":
            state = "corrupted"
        return {"state": state, "violations": violations,
                "counts": {"wanted": len(want), "on_file": have, "run_log_starts": len(starts),
                           "run_log_abandoned": abandoned, "code": code[:16]}}

    def anchor(self, params, work):
        """A digest of this scenario's replication files: used to tell an invocation that added replications from
        one that added none (``no_progress``). The simulation keeps no hash chain, so nothing is verified against
        it before an invocation."""
        import hashlib
        files = sorted(self._out(work).rglob(f"{params['scenario']}_{params['size']}_*.jsonl"))
        if not files:
            return None
        h, n = hashlib.sha256(), 0
        for f in files:
            b = f.read_bytes()
            n += b.count(b"\n")
            h.update(f.name.encode() + b"\0" + hashlib.sha256(b).digest())
        return {"records": n, "head": h.hexdigest()}

    def progress(self, params, work):
        hb = self._out(work) / "heartbeat.json"
        try:
            import json
            d = json.loads(hb.read_text())
            return {"unit": "replications", "done": d.get("on_file"), "total": d.get("wanted")}
        except (OSError, ValueError):
            return {}

    def label(self, params):
        return f"sim {params['prereg']} {params['scenario']} {params['size']} reps={params['reps']}"


KINDS: dict[str, Kind] = {k.name: k for k in (Smoke(), Hte(), Sim())}


def get(name: str) -> Kind:
    if name not in KINDS:
        raise ParamError(f"unknown job kind {name!r}; allowed: {sorted(KINDS)}")
    return KINDS[name]
