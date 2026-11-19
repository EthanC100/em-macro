"""S16 mutation check: does the acceptance suite catch planted defects?

    python tests/acceptance/mutation_check.py --tree <scratch worktree> --out mutations.json

Plants one defect at a time in the platform code (or, for MO*, in the test-only oracle drivers) of ``--tree`` (a disposable git worktree, never your working
checkout), runs the acceptance suite there, and records which acceptance ids failed. Every mutation must be caught
by at least one of its expected ids (FAIL, ERROR or, for an adapter switched on without a
binding, UNBOUND). Each file is restored after its mutation; if the process is killed, restore
with ``git -C <tree> checkout -- manhattan``. Refuses a tree whose ``manhattan/`` has uncommitted changes and any
tree that is not a linked worktree.

A mutation whose anchor text is not in the tree (its PR is not merged there) is NOT_APPLICABLE, which is not a pass.
Exit status 0 only when every mutation applied and was caught.

Example (all five approved PR heads merged into a scratch worktree, never pushed):

    git worktree add --detach /tmp/s16 origin/main && cd /tmp/s16
    git merge --no-edit origin/<pr84 head> origin/<pr85 head> origin/<pr86 head> origin/<pr87 head> origin/<pr89 head>
    cp -r <this checkout>/tests/acceptance tests/        # only if the tree does not have the suite yet
    python tests/acceptance/mutation_check.py --tree . --out /tmp/s16-mutations.json
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


MUTATIONS = [
    ("M01", "HTE does not check the results hash", "manhattan/hte/runner.py",
     'if raw is not None and ids.sha256_bytes(raw) != cp["results_sha256"]:', "if False:", ["ADV-COR-01"]),
    ("M02", "HTE synthetic-panel check bypassed", "manhattan/hte/data.py",
     "def verify_synthetic(panel) -> str:\n",
     'def verify_synthetic(panel) -> str:\n    return getattr(panel, "data_hash", "0" * 64)\n',
     ["ADV-COR-03", "E2E-03"]),
    ("M03", "HTE PIT probe skipped at registration", "manhattan/hte/registry.py",
     "elif not (self._probe_ok(tmpl, ver, code, None, probed) and",
     "elif False and not (self._probe_ok(tmpl, ver, code, None, probed) and", ["ADV-LA-01"]),
    ("M04", "HTE registers duplicate specs", "manhattan/hte/registry.py",
     "if sh in known_specs or sh in batch_specs:", "if False:", ["ADV-DUP-01"]),
    ("M05", "HTE recomputes an identical closed run", "manhattan/hte/runner.py",
     "if closed and not verify_rerun:", "if False:", ["ADV-DUP-02"]),
    ("M06", "HTE run record claims confirmatory", "manhattan/hte/runner.py",
     '"evidence_class": "synthetic_screening_descriptive", "confirmatory": False}',
     '"evidence_class": "synthetic_screening_descriptive", "confirmatory": True}', ["E2E-08", "ADV-PRO-04"]),
    ("M07", "HTE stage 5 allowed", "manhattan/hte/runner.py", "if 5 in stages:", "if False:", ["ADV-PRT-02"]),
    ("M08", "evidence honours a forged weight", "manhattan/evidence.py",
     "return max(0, min(recorded_weight, c.weight_ceiling))", "return recorded_weight", ["ADV-PRO-01"]),
    ("M09", "execution fills at the decision's own close", "manhattan/execution/account.py",
     "after = [i for i, t in enumerate(market.calendar) if t.close_at > decided_at]",
     "after = [i for i, t in enumerate(market.calendar) if t.close_at >= decided_at.replace(hour=0)]",
     ["E2E-11", "ADV-LA-03"]),
    ("M10", "execution fills at an already-seen price", "manhattan/execution/costs.py",
     "if settlement.known_at <= decided_at:", "if False:", ["ADV-LA-03"]),
    ("M11", "attempt reconciler ignores unfinished attempts", "manhattan/attempts.py",
     'audit.v("missing_terminal", "ledger", seq)', "pass", ["ADV-INT-02"]),
    ("M12", "HTE resume skips interrupted-attempt recovery", "manhattan/hte/runner.py",
     "def _recover(self) -> None:\n", "def _recover(self) -> None:\n        return\n", ["ADV-INT-01"]),
    ("M13", "HTE does not check package hashes", "manhattan/hte/runner.py",
     'if ids.sha256_bytes((rdir / "packages" / name).read_bytes()) != h:', "if False:", ["ADV-COR-01"]),
    # -- phase 2: the HTE -> PR #86 and HTE -> PR #93 integration boundaries (PR #90, PR #93) -----------------------
    ("MX01", "executable identity ignores the numerical environment", "manhattan/hte/adapters.py",
     '            "numeric_environment_sha256": env_sha}', '            "numeric_environment_sha256": "1" * 64}',
     ["ORC-ACC86-03", "ORC-DEX93-02"]),
    ("MX02", "binding identity ignores cost assumptions", "manhattan/hte/adapters.py",
     '"costs": {"linear": c, "impact": k, "impact_power": 1.5},', '"costs": {},', ["ORC-ACC86-03"]),
    ("MX03", "executable accounting never flags divergent executables", "manhattan/hte/adapters.py",
     'divergent = len(g["results"]) > 1', "divergent = False", ["ORC-ACC86-05"]),
    ("MX04", "delayed alignment ignores the lag", "manhattan/execution_realism/screening.py",
     "return P[warmup - 1 - lag: fence - 1 - lag], R[warmup:fence]", "return P[warmup - 1: fence - 1], R[warmup:fence]",
     ["CON93-03", "ORC-DEX93-01"]),
    ("MX05", "volatility scale does not move with the lag (reads the future)", "manhattan/execution_realism/screening.py",
     "s[lag:] = s0[: n - lag]", "s[:] = s0", ["CON93-04"]),
    ("MX06", "result identity omits the execution policy", "manhattan/execution_realism/adapter.py",
     'doc = {"panel": self.panel_digest, "policy": self.policy,', 'doc = {"panel": self.panel_digest, "policy": None,',
     ["CON93-02"]),
    ("MX07", "lag 0 (same close) accepted silently", "manhattan/execution_realism/timing.py",
     "if self.lag == 0 and not self.allow_same_close:", "if False:", ["CON93-01", "ORC-DEX93-03"]),
    ("MX08", "cost model id ignores the cost terms", "manhattan/execution_realism/costs.py",
     "b = json.dumps(self.as_dict(), sort_keys=True", "b = json.dumps(self.name, sort_keys=True", ["CON93-02"]),
    # defects planted in the test-only oracle drivers: what a defective adapter would do (the tests must catch it)
    ("MO1", "accounting adapter ignores the engine and environment it ran under", "tests/acceptance/s16_drivers.py",
     "return adapters.to_pr86_identity(runner.view, i, run_id=runner.run_id, data_hash=runner.data_hash,\n"
     "                                         code=code or code_of(runner),",
     "return adapters.to_pr86_identity(runner.view, i, run_id=runner.run_id, data_hash=runner.data_hash,\n"
     "                                         code=code_of(runner),", ["ORC-ACC86-03", "ORC-ACC86-04"]),
    ("MO2", "accounting adapter ignores the evaluation policy", "tests/acceptance/s16_drivers.py",
     "                                         policy=policy or runner.policy, fence=runner.panel.fence)\n\n    def lineage",
     "                                         policy=runner.policy, fence=runner.panel.fence)\n\n    def lineage",
     ["ORC-ACC86-03", "ORC-ACC86-04"]),
    ("MO3", "delayed adapter leaves the lag out of the executable identity", "tests/acceptance/s16_drivers.py",
     'spec["execution"] = {**ExecutionTiming(lag, allow_same_close=allow_same_close).as_dict(), "model": self.MODEL}',
     'spec["execution"] = {"model": self.MODEL}', ["ORC-DEX93-02"]),
    ("MO4", "delayed adapter executes at the same close whatever the lag", "tests/acceptance/s16_drivers.py",
     "fence=runner.panel.fence, lag=lag, c=c, k=k,", "fence=runner.panel.fence, lag=0, c=c, k=k,", ["ORC-DEX93-01"]),
    ("MO5", "delayed adapter reads the next day's return", "tests/acceptance/s16_drivers.py",
     'R = (panel or runner.panel).returns(d["domain"])',
     'R = __import__("numpy").roll((panel or runner.panel).returns(d["domain"]), -1, axis=0)',
     ["ORC-DEX93-03", "ORC-DEX93-01"]),
    # an adapter switched on without an acceptance binding must never pass: its tests turn UNBOUND
    ("MU1", "PR #86 accounting adapter enabled but not bound", "manhattan/hte/adapters.py",
     "class Pr86AccessAdapter:\n    enabled = False", "class Pr86AccessAdapter:\n    enabled = True",
     ["ACC86-01", "GAP-01"]),
    ("MU2", "an HTE <-> PR #93 binding appears but is not bound", "manhattan/hte/workload.py",
     "from __future__ import annotations\n",
     "from __future__ import annotations\nimport manhattan.execution_realism as _s16_probe  # noqa: F401\n",
     ["DEX93-01"]),
]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--tree", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    tree = a.tree.resolve()
    def git(*args):
        return subprocess.run(["git", *args], cwd=tree, capture_output=True, text=True, check=True).stdout.strip()
    if Path(git("rev-parse", "--absolute-git-dir")) == Path(git("rev-parse", "--path-format=absolute",
                                                                "--git-common-dir")):
        sys.exit("refusing: --tree must be a linked, disposable worktree (git worktree add --detach <dir> <ref>), "
                 "not a primary checkout")
    if git("status", "--porcelain", "--", "manhattan"):
        sys.exit(f"refusing: {tree}/manhattan has uncommitted changes")
    if not (tree / "tests/acceptance/run.py").exists():
        sys.exit(f"{tree} has no tests/acceptance/run.py")
    results, ok = [], True
    with tempfile.TemporaryDirectory() as tmp:
        rep_path = Path(tmp) / "report.json"
        for mid, name, rel, old, new, expect in MUTATIONS:
            p = tree / rel
            src = p.read_text() if p.exists() else ""
            if src.count(old) != 1:
                results.append({"id": mid, "mutation": name, "file": rel, "outcome": "NOT_APPLICABLE",
                                "expected_ids": expect})
                ok = False
                print(f"NOT_APPLICABLE {mid} {name}", flush=True)
                continue
            p.write_text(src.replace(old, new))
            try:
                r = subprocess.run([sys.executable, "tests/acceptance/run.py", "--out", str(rep_path)], cwd=tree,
                                   capture_output=True, text=True, timeout=3000)
                rep = json.loads(rep_path.read_text())
            finally:
                p.write_text(src)
            failing = sorted(i for i, v in rep["by_id"].items() if v in ("FAIL", "ERROR", "UNBOUND"))
            caught = [i for i in expect if i in failing]
            outcome = "CAUGHT" if caught and r.returncode == 1 and rep["verdict"] == "NOT_READY" else "MISSED"
            ok &= outcome == "CAUGHT"
            results.append({"id": mid, "mutation": name, "file": rel, "outcome": outcome, "expected_ids": expect,
                            "failing_ids": failing, "runner_exit": r.returncode, "verdict": rep["verdict"]})
            print(f"{outcome} {mid} {name}: failing {failing}", flush=True)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps({"schema": "manhattan.s16.mutations/1", "tree": str(tree), "all_caught": ok,
                                 "mutations": results}, indent=1) + "\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
