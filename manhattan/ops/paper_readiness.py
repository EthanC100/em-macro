"""Readiness of the always-on paper runner for the first owner-frozen families (metadata only, no outcomes).

    python -m manhattan.ops.paper_readiness [--families 20] [--rehearse] [--json OUT]

Answers one question with evidence: **may the nightly paper runner start recording predictions for the first 10-20
owner-frozen families, and if not, what blocks it and whose step is it?** Every check reads repository files or runs
a synthetic rehearsal; none reads market data, a ledger, a secret or any outcome. A check that only the owner can
satisfy (a credential, a custody decision, a deployment authorization) is reported ``blocked_owner`` and never
attempted. Activation gates of BINDING_ACCOUNTING.md (forward results counting as evidence) are reported
separately from recording readiness: recording on paper can start before evidence may count, never the reverse.

``--rehearse`` runs the real entry point (``python -m manhattan.ops.runner ... --rehearsal``) as separate
processes on a synthetic batch of ``--families`` mock families: capture, registration, three nightly runs, a hard
kill after a protected read and its restart, then the attempt reconciler over the resulting ledger. It reports wall
time, attempts and ledger size per night (counts and seconds only).

Status words: ``ready``, ``blocked_owner`` (only Ethan can act), ``blocked_build`` (engineering work remains),
``blocked_gate`` (an activation gate; does not block paper recording), ``not_applicable``.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
READY, OWNER, BUILD, GATE, NA = "ready", "blocked_owner", "blocked_build", "blocked_gate", "not_applicable"


def _check(cid: str, what: str, status: str, evidence: str, owner_step: str | None = None) -> dict:
    return {"id": cid, "check": what, "status": status, "evidence": evidence, "owner_step": owner_step}


def _text(rel: str) -> str | None:
    p = ROOT / rel
    return p.read_text(encoding="utf-8") if p.exists() else None


def frozen_families(batches: Path) -> tuple[int, int, list[str]]:
    """(families, unique executable configurations, batch ids) of the frozen batches on disk, after each batch
    verifies (canonical manifest, spec hashes, Merkle root). A batch that does not verify raises."""
    from manhattan import spec as S
    from manhattan.ops import runner as R
    fams, exes, ids = set(), set(), []
    for d in sorted(Path(batches).glob("AB-*")):
        manifest, specs = R.load_batch(batches, int(d.name[3:]))
        ids.append(d.name)
        for x in R.batch_executables(specs):
            fams.add(S.spec_hash(x.family))
            exes.add(x.spec_hash)
    return len(fams), len(exes), ids


def static_checks(n_target: int, batches: Path = ROOT / "data/manhattan/batches") -> list[dict]:
    out = []
    # ---- the families themselves
    try:
        nf, nx, ids = frozen_families(batches)
        st = READY if nf >= n_target else OWNER
        out.append(_check("R01", f"at least {n_target} owner-frozen families in data/manhattan/batches", st,
                          f"{nf} frozen families, {nx} unique executable configurations, batches {ids or 'none'}",
                          "families are originated in the designated family chat and frozen only by Ethan's merge "
                          "of the manifest pull request (freeze_pr)"))
    except Exception as e:                                       # noqa: BLE001 - a batch that does not verify
        out.append(_check("R01", "frozen batches verify", BUILD, f"a batch does not verify: {type(e).__name__}"))
    # ---- the runner and its workflow
    wf = _text(".github/workflows/manhattan-ops-runner.yml") or ""
    sched_off = not re.search(r"^\s*schedule:", wf, re.M)
    guards = all(s in wf for s in ("workflow_dispatch", "github.ref == 'refs/heads/main'", "environment: manhattan-ledger",
                                   "persist-credentials: false", "cancel-in-progress: false"))
    out.append(_check("R02", "runner workflow: dispatch-only, main-only, secrets in a main-only environment",
                      READY if guards else BUILD, f"guards present: {guards}; schedule disabled: {sched_off}"))
    out.append(_check("R03", "runner schedule enabled", OWNER if sched_off else READY,
                      "schedule commented out" if sched_off else "schedule active",
                      "ETHAN_OPS_ACTIONS.md step 9 (first run by hand from main, then uncomment the schedule)"))
    registers = any("ops.runner register" in (p.read_text(encoding="utf-8", errors="replace"))
                    for p in (ROOT / ".github/workflows").glob("*.yml"))
    out.append(_check("R04", "a production path runs `runner register` (merge time + witness into the private ledger)",
                      READY if registers else BUILD,
                      "a workflow runs it" if registers else
                      "no workflow runs `register`; only the deploy-key holder could. Draft: "
                      "docs/manhattan/ops/drafts/manhattan-ops-register.yml (not installed)",
                      None if registers else "install a registration workflow on main (a deployment decision)"))
    out.append(_check("R05", "the timing witness is verified by code, not asserted",
                      BUILD, "runner register trusts the witness JSON's `verified` field; no OpenTimestamps (or "
                      "other) verifier is built, so a registration is only as good as whoever wrote that file",
                      "choose the witness (OpenTimestamps is free) and who runs its verifier"))
    lock_used = "requirements-manhattan-runner.lock" in wf
    out.append(_check("R06", "the workflow installs the hash-locked runner environment (gate G-4)",
                      READY if lock_used else OWNER, "installs " + ("the lock" if lock_used else "requirements.txt"),
                      None if lock_used else "adopt requirements-manhattan-runner.lock in the workflow (G-4)"))
    co = _text(".github/CODEOWNERS") or ""
    switches = all(p in co for p in ("/manhattan/ops/promotion.py", "/manhattan/ops/templates/",
                                     "/.github/workflows/manhattan-ops-runner.yml"))
    out.append(_check("R07", "ops switches protected in CODEOWNERS", READY if switches else OWNER,
                      f"promotion, templates and runner workflow listed: {switches}", "ETHAN_OPS_ACTIONS.md step 8"))
    critic = (ROOT / ".claude/agents/manhattan-critic.md").exists()
    out.append(_check("R08", "critic agent installed", READY if critic else OWNER,
                      f".claude/agents/manhattan-critic.md present: {critic}", "ETHAN_OPS_ACTIONS.md step 6"))
    # ---- what a session cannot see
    for cid, what, step in (
            ("R09", "private ledger repository, deploy key, main-only environment, sessions kept out",
             "ETHAN_OPS_ACTIONS.md steps 1-3 (credentials; a session cannot verify them)"),
            ("R10", "independent mirror of the private ledger", "ETHAN_OPS_ACTIONS.md step 4 (custody decision)"),
            ("R11", "independent custody of ledger anchors (D-7, gate G-2)",
             "choose who holds anchors outside the writing credential (PAPER_RUNNER_READINESS.md section 2)"),
            ("R12", "blind generator environment passes the isolation kit",
             "ETHAN_OPS_ACTIONS.md steps 5 and 7 (a PASS record from the blind environment)")):
        out.append(_check(cid, what, OWNER, "not visible from a session by design", step))
    # ---- switches that must stay off
    import yaml
    cfg = yaml.safe_load(_text("config/manhattan.yaml") or "{}") or {}
    reserve_on = bool((cfg.get("reserve") or {}).get("enabled"))
    claims_on = bool((cfg.get("claims") or {}).get("enabled"))
    from manhattan.ops import promotion
    adopted = bool(getattr(promotion, "ADOPTED_PROTOCOLS", ()))
    off = not (reserve_on or claims_on or adopted)
    out.append(_check("R13", "reserve, claims and promotion stay off", READY if off else BUILD,
                      f"reserve.enabled={reserve_on}, claims.enabled={claims_on}, adopted protocols={adopted}"))
    out.append(_check("R14", "forward observations may count as evidence (gates G-1..G-6, blockers B-1..B-3)", GATE,
                      "none lifted (BINDING_ACCOUNTING.md sections 16 and 19); recording proceeds, evidence does not",
                      "independent verification and the owner decisions D-1..D-4"))
    return out


# ---------------------------------------------------------------- synthetic rehearsal through the real entry point

def _git(*a, cwd):
    return subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True).stdout


def _head() -> str:
    return _git("rev-parse", "HEAD", cwd=ROOT).strip()


def rehearse(n_families: int, root: Path | None = None) -> dict:
    """Run the CLI on a synthetic batch, one process per run. Returns counts and seconds only."""
    from manhattan import attempts
    from manhattan.generate import parse_reply
    from manhattan.ops import freeze_pr, mockgen
    from manhattan.ops import store as ST
    own = root is None
    root = Path(root or tempfile.mkdtemp(prefix="paper-rehearsal-"))
    try:
        req = mockgen.blind_request(n_families=n_families, max_hypotheses=2, domains=("syn_daily",))
        fams, hyps = parse_reply(mockgen.mock_reply(req, n=n_families), "blind")
        prep = freeze_pr.prepare(1, fams, hyps, out_root=root / "batches", code_version="c" * 40,
                                 protocol_path=ROOT / "docs/manhattan/PROTOCOL_v3.md", generator_model="mock",
                                 template_hash=req.template_hash, fence={})
        remote = root / "ledger.git"
        _git("init", "-q", "--bare", "-b", "main", str(remote), cwd=root)
        (root / "pr.json").write_text(json.dumps({"merged": True, "merged_at": "2026-11-13T15:00:00Z",
                                                  "merge_commit_sha": "d" * 40}))
        (root / "w.json").write_text(json.dumps({"kind": "opentimestamps", "digest": prep["manifest_hash"],
                                                 "attested_utc": "2026-11-13T16:30:00Z", "verified": True}))
        head, k = _head(), {"n": 0}
        env = {k_: v for k_, v in os.environ.items() if not k_.startswith(("GITHUB_", "MANHATTAN_"))}
        env["PYTHONDONTWRITEBYTECODE"] = "1"

        def run(cmd, clock, asof=None, run_id=None, attempt=1, kill=False):
            k["n"] += 1
            w = root / f"run{k['n']}"
            argv = [cmd, "--rehearsal", "--rehearsal-clock", clock, "--ledger-dir", str(w / "private/ledger"),
                    "--private-dir", str(w / "private"), "--remote", str(remote), "--batches", str(root / "batches"),
                    "--run-id", run_id or str(k["n"]), "--attempt", str(attempt), "--commit", head,
                    "--health-out", str(w / "health.json")]
            argv += (["--asof", asof, "--sources", "synthetic"] if cmd == "nightly" else
                     ["--batch", "1", "--pr-json", str(root / "pr.json"), "--witness-json", str(root / "w.json")])
            if kill:
                full = [sys.executable, "-c", _KILLER, *argv]
            else:
                full = [sys.executable, "-m", "manhattan.ops.runner", *argv]
            t0 = time.perf_counter()
            p = subprocess.run(full, cwd=ROOT, env=env, capture_output=True, text=True, timeout=1800)
            dt = time.perf_counter() - t0
            h = json.loads((w / "health.json").read_text()) if (w / "health.json").exists() else {}
            return p.returncode, h, dt

        nights = []
        steps = [("nightly", "2026-11-12T23:30:00Z", "2026-11-12"), ("register", "2026-11-13T16:45:00Z", None),
                 ("nightly", "2026-11-16T23:30:00Z", "2026-11-16"), ("nightly", "2026-11-17T23:30:00Z", "2026-11-17")]
        for cmd, clock, asof in steps:
            rc, h, dt = run(cmd, clock, asof)
            nights.append({"step": f"{cmd} {asof or ''}".strip(), "exit": rc, "status": h.get("status"),
                           "seconds": round(dt, 2), "attempts_registered": h.get("attempts_registered", 0),
                           "observations_new": h.get("observations_new", 0), "ledger_records": h.get("ledger_records")})
        rc, h, dt = run("nightly", "2026-11-18T23:30:00Z", "2026-11-18", run_id="kill", kill=True)
        nights.append({"step": "nightly 2026-11-18 (hard kill after a protected read)", "exit": rc,
                       "status": h.get("status"), "seconds": round(dt, 2)})
        rc, h, dt = run("nightly", "2026-11-18T23:40:00Z", "2026-11-18", run_id="kill", attempt=2)
        nights.append({"step": "nightly 2026-11-18 (restart)", "exit": rc, "status": h.get("status"),
                       "seconds": round(dt, 2), "attempts_registered": h.get("attempts_registered", 0),
                       "attempts_recovered": h.get("attempts_recovered", 0),
                       "observations_new": h.get("observations_new", 0), "ledger_records": h.get("ledger_records")})
        led = ST.Store(workdir=root / "audit", remote=str(remote)).open()
        rep = attempts.reconcile(store_chain=led.workdir / ST.CHAIN,
                                 store_anchor={"records": len(led.records), "head": led.head})
        nf, nx, _ = frozen_families(root / "batches")
        size = sum(p.stat().st_size for p in (root / "audit").rglob("*") if p.is_file() and ".git" not in p.parts)
        expected = [0, 0, 0, 0, 137, 0]
        ok = [n["exit"] for n in nights] == expected and rep["access_reconciled"] and rep["unfinished"] == 0
        return {"families": nf, "unique_executable_configurations": nx,
                "predictions_registered": len({r["payload"]["prediction"] for r in led.of_type("registration")}),
                "total_attempts": rep["registered_executions"], "completed_attempts": rep["completed"],
                "aborted_attempts": len(led.of_type("attempt_aborted")), "failed_attempts": len(led.of_type("attempt_failed")),
                "repeated_observations": rep["repeated_observations"],
                "independent_statistical_tests": rep["independent_statistical_tests"],
                "access_reconciled": rep["access_reconciled"], "violations": [v["code"] for v in rep["violations"]],
                "ledger_bytes_working_tree": size, "runs": nights, "passed": bool(ok)}
    finally:
        if own:
            shutil.rmtree(root, ignore_errors=True)


# a hard process death right after the first protected value is read (no handler, no finally): os._exit
_KILLER = """
import os, sys
from manhattan.engine import pit
from manhattan.ops import runner as R
real = pit.Window._known
def known(self, s, t):
    out = real(self, s, t)
    if self.attempt_id:
        os._exit(137)
    return out
pit.Window._known = known
sys.exit(R.main(sys.argv[1:]))
"""


def verdict(checks: list[dict], rehearsal: dict | None) -> dict:
    owner = [c["id"] for c in checks if c["status"] == OWNER]
    build = [c["id"] for c in checks if c["status"] == BUILD]
    gates = [c["id"] for c in checks if c["status"] == GATE]
    rec_ok = rehearsal is None or rehearsal["passed"]
    if not owner and not build and rec_ok:
        word = "ready_to_record_on_paper"
    else:
        word = "not_ready"
    return {"paper_recording": word, "evidence_may_count": False if gates else None,
            "blocked_owner": owner, "blocked_build": build, "activation_gates": gates,
            "rehearsal_passed": None if rehearsal is None else rehearsal["passed"]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m manhattan.ops.paper_readiness")
    ap.add_argument("--families", type=int, default=20)
    ap.add_argument("--rehearse", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    checks = static_checks(min(a.families, 10))
    reh = rehearse(a.families) if a.rehearse else None
    out = {"schema": "manhattan-paper-readiness/1", "target_families": a.families, "checks": checks,
           "rehearsal": reh, "verdict": verdict(checks, reh)}
    text = json.dumps(out, indent=1, sort_keys=True)
    if a.json:
        Path(a.json).write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
