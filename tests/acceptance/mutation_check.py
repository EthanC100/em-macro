"""S16 mutation check: does the acceptance suite catch planted defects?

    python tests/acceptance/mutation_check.py --tree <scratch worktree> --out mutations.json

Plants one defect at a time in the platform code of ``--tree`` (a disposable git worktree, never your working
checkout), runs the acceptance suite there, and records which acceptance ids failed. Every mutation must be caught
by at least one of its expected ids. Each file is restored after its mutation; if the process is killed, restore
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
            failing = sorted(i for i, v in rep["by_id"].items() if v in ("FAIL", "ERROR"))
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
