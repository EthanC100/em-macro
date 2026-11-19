"""S16 acceptance runner: one command, machine-readable results.

    python tests/acceptance/run.py --out acceptance.json [--require-ready] [-- <extra pytest args>]

Runs the S16 system acceptance suite (tests/acceptance) under pytest and writes a JSON report:
every test with its acceptance id, area, outcome (PASS, FAIL, UNBOUND, ERROR, BLOCKED, SKIPPED) and reason, the
capability probes, a per-id rollup and a verdict for the integrated synthetic platform.

Exit status: 0 no test failed (BLOCKED allowed); 1 a test failed or errored, or a required acceptance id is
missing; 3 with --require-ready, when the verdict is not READY. The report never says that anything was
scientifically verified: an acceptance pass shows the synthetic platform behaves as specified, nothing about
markets (``scientifically_verified`` is always false).
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path += [p for p in (str(HERE), str(ROOT)) if p not in sys.path]          # appended: never shadows tests/

SCHEMA = "manhattan.s16.acceptance/1"
PASS, FAIL, UNBOUND_, ERROR, BLOCKED_, SKIPPED = "PASS", "FAIL", "UNBOUND", "ERROR", "BLOCKED", "SKIPPED"
_WORST = (ERROR, FAIL, UNBOUND_, BLOCKED_, SKIPPED, PASS)        # a rollup takes the first present

# Every acceptance id the gate requires. A missing id (deleted or renamed test) is itself a failure.
REQUIRED_IDS = (
    "E2E-01", "E2E-02", "E2E-03", "E2E-04", "E2E-05", "E2E-06", "E2E-07", "E2E-08", "E2E-09", "E2E-10", "E2E-11",
    "E2E-12", "E2E-13", "E2E-14",
    "ADV-LA-01", "ADV-LA-02", "ADV-LA-03", "ADV-LA-04",
    "ADV-DUP-01", "ADV-DUP-02", "ADV-DUP-03", "ADV-DUP-04",
    "ADV-INT-01", "ADV-INT-02",
    "ADV-COR-01", "ADV-COR-02", "ADV-COR-03", "ADV-COR-04",
    "ADV-PRO-01", "ADV-PRO-02", "ADV-PRO-03", "ADV-PRO-04",
    "ADV-PRT-01", "ADV-PRT-02", "ADV-PRT-03", "ADV-PRT-04", "ADV-PRT-05",
    "ADV-OBS-01", "ADV-OBS-02",
    "GAP-01", "GAP-02", "GAP-03", "GAP-04", "GAP-05", "GAP-06", "GAP-07",
    "HARNESS-01", "HARNESS-02",
)


class _Collector:
    def __init__(self):
        self.tests: dict[str, dict] = {}

    def pytest_runtest_logreport(self, report):
        props = dict(report.user_properties)
        if "acceptance_id" not in props:
            return
        t = self.tests.setdefault(report.nodeid, {
            "id": props["acceptance_id"], "area": props.get("area"), "nodeid": report.nodeid,
            "requires": [x for x in props.get("requires", "").split(",") if x], "outcome": PASS, "detail": "",
            "blocked_by": [], "duration_s": 0.0})
        t["duration_s"] = round(t["duration_s"] + float(report.duration or 0.0), 3)
        if report.skipped:
            reason = report.longrepr[2] if isinstance(report.longrepr, tuple) else str(report.longrepr)
            reason = reason.removeprefix("Skipped: ")
            if reason.startswith("BLOCKED"):
                t["outcome"] = BLOCKED_
                t["blocked_by"] = reason[reason.index("[") + 1:reason.index("]")].split(",")
            else:
                t["outcome"] = SKIPPED
            t["detail"] = reason[:2000]
        elif report.failed:
            msg = getattr(report, "longreprtext", "") or str(report.longrepr)
            if report.when != "call":
                t["outcome"] = ERROR
            elif "UNBOUND[" in msg:
                t["outcome"] = UNBOUND_
            else:
                t["outcome"] = FAIL
            lines = [ln for ln in msg.splitlines() if ln.startswith("E ")] or msg.splitlines()[-5:]
            t["detail"] = "\n".join(lines)[:4000]


def rollup(tests: list[dict]) -> dict:
    by: dict[str, list] = {}
    for t in tests:
        by.setdefault(t["id"], []).append(t["outcome"])
    return {k: next(o for o in _WORST if o in v) for k, v in sorted(by.items())}


def verdict(tests: list[dict], *, pytest_exit: int, required=REQUIRED_IDS) -> dict:
    """READY only when every required acceptance id ran and passed, nothing was blocked, skipped, unbound or
    failed, and pytest itself exited 0."""
    ids = rollup(tests)
    summary = {o: sum(1 for t in tests if t["outcome"] == o) for o in (PASS, FAIL, UNBOUND_, ERROR, BLOCKED_,
                                                                       SKIPPED)}
    missing = [i for i in required if i not in ids]
    reasons = []
    if missing:
        reasons.append(f"required acceptance ids missing: {', '.join(missing)}")
    for o in (ERROR, FAIL, UNBOUND_, BLOCKED_, SKIPPED):
        bad = [i for i, v in ids.items() if v == o]
        if bad:
            reasons.append(f"{o}: {', '.join(bad)}")
    if pytest_exit not in (0,) and not any(t["outcome"] in (FAIL, ERROR, UNBOUND_) for t in tests):
        reasons.append(f"pytest exited {pytest_exit} with no failing acceptance test recorded")
    failing = bool(missing) or summary[FAIL] or summary[ERROR] or summary[UNBOUND_] or pytest_exit not in (0, 5)
    return {"verdict": "READY" if not reasons else "NOT_READY", "reasons": reasons, "summary": summary,
            "by_id": ids, "exit": 1 if failing else 0,
            # constant: acceptance of a synthetic platform is not scientific verification of anything
            "scientifically_verified": False, "evidence_class": "synthetic_acceptance_only"}


def _git(*args) -> str | None:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=30,
                              check=True).stdout.strip()
    except Exception:
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, help="write the JSON report here (default: stdout only)")
    ap.add_argument("--label", default="", help="free text recorded in the report (e.g. which PR heads were merged)")
    ap.add_argument("--require-ready", action="store_true", help="exit 3 unless the verdict is READY")
    ap.add_argument("pytest_args", nargs="*", help="extra pytest arguments (after --)")
    a = ap.parse_args(argv)
    import numpy
    import pytest
    import s16_capabilities as CAP
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    col = _Collector()
    t0 = time.perf_counter()
    code = int(pytest.main(["-q", "-p", "no:cacheprovider", str(HERE), *a.pytest_args], plugins=[col]))
    tests = sorted(col.tests.values(), key=lambda t: (t["id"], t["nodeid"]))
    v = verdict(tests, pytest_exit=code)
    report = {
        "schema": SCHEMA,
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "command": "python tests/acceptance/run.py " + " ".join(argv if argv is not None else sys.argv[1:]),
        "label": a.label,
        "tree": {"commit": _git("rev-parse", "HEAD"), "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
                 "dirty": bool(_git("status", "--porcelain", "--", "manhattan", "tests", "config"))},
        "environment": {"python": platform.python_version(), "numpy": numpy.__version__,
                        "platform": platform.platform()},
        "capabilities": CAP.snapshot(),
        "pytest_exit": code, "wall_s": round(time.perf_counter() - t0, 2),
        **v, "tests": tests,
    }
    text = json.dumps(report, indent=1, sort_keys=False)
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(text + "\n")
    print(json.dumps({k: report[k] for k in ("verdict", "summary", "reasons", "scientifically_verified")},
                     indent=1))
    if v["exit"]:
        return 1
    if a.require_ready and v["verdict"] != "READY":
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
