"""Verify that v1.0's committed results still reproduce exactly with the frozen code.

    python -m em_macro.verify_v1                 # rebuild and compare (exit status 1 on any difference)
    python -m em_macro.verify_v1 --keep DIR      # also write the rebuilt tables to DIR

Why this exists: ``python -m em_macro.systematic test --force`` refuses to run, because
``results/systematic/fit/frozen_design.json`` records the code hash of ``systematic.py`` at the
design-freeze commit 2dbfeb1 (``6a0234d9b1a92102``), and the v1.0 file (commit 7886867) differs
from it by one cosmetic label line in ``stage_update()`` (docs/v1.0_freeze.md).  Neither frozen file
may be edited, so this module does what ``stage_fit`` and ``stage_test`` do -- ``build_inputs()``
then ``evaluate()`` -- without their guards and without writing anything under ``results/``:

1. checks that ``em_macro/systematic.py``, ``em_macro/risk_model.py``, ``frozen_design.json``,
   ``frozen_params.json`` and the two result tables have the SHA-256 recorded in
   docs/v1.0_freeze.md, and that ``systematic.DESIGN`` equals the frozen design;
2. takes the three input snapshots (``data/processed/daily_panel.csv``,
   ``country_month_panel.csv``, ``risk_model_input.csv``) as committed in 7886867 -- the monthly
   workflow rewrites the working-tree copies -- and checks their freeze-record hashes;
3. points the frozen loaders at those snapshots (the module-level ``PROC`` of ``systematic`` and
   ``risk_model``; nothing is written there) and calls ``systematic.build_inputs()``;
4. calls ``systematic.evaluate()`` for the design sample (2005-01..2019-12) and the test
   (2020-01..``last_month`` of ``TEST_RUN.json``, 2026-09), writes each table exactly as
   ``stage_fit``/``stage_test`` do (``to_csv(index=False, float_format="%.4f")``) and compares the
   bytes with the committed ``performance_2005_2019.csv`` and ``performance_2020_on.csv``.

Use it whenever v1.0's results need to be re-confirmed: after a change to a data loader, a
dependency upgrade, or before relying on the frozen numbers in a new trial.  Series that are not
in git (FRED, Yahoo, BIS, BanRep TRM, BCCh) are read from ``data/raw/`` and downloaded if absent;
a source that has revised its history since the freeze would show up here as a mismatch.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

from . import risk_model as RM
from . import systematic as SY
from .config import ROOT

FREEZE_COMMIT = "7886867094958f96e13cf77eff1099f9f837de60"

# SHA-256 at commit 7886867, as recorded in docs/v1.0_freeze.md
FROZEN_CODE = {
    "em_macro/systematic.py": "1eb4cf6b1c537c1711e5fff0b7aa044fee932c20992eb0d3cea4c3c5fc50be66",
    "em_macro/risk_model.py": "2000a49747a2fba4064efe25a7eaf107e14b484ded7e5534f068a81b73738e74",
    "results/systematic/fit/frozen_design.json": "f0cce4c9a819379c7bce4310ad58e8765b8149ef0d045ab25dd84c1b13983858",
    "results/risk_model/fit/frozen_params.json": "52f4a92b78d0aad849283b687123d149d9a00124f01a4d2e83849156459ac398",
    "results/systematic/fit/performance_2005_2019.csv":      # first 16 hex in the freeze record's reproduction table
        "00bae5baaa1bf0532abf801892242b19cbbd74a44172c1b273ef61a32d344ef7",
    "results/systematic/test/performance_2020_on.csv":
        "1f8828109a6ab741993f2f49947320cc2a87c66abb308d3d37684151175087ed",
    "results/systematic/test/TEST_RUN.json": "d78199dcc4c3cd9674e5ca917063bf7b6b1f59322e2e073307581eaac5485549",
}
FROZEN_INPUTS = {
    "data/processed/daily_panel.csv": "64921b287f799ca15c4d4232fbcab64ef24d97c4fd112ea1bac6195fa2179217",
    "data/processed/country_month_panel.csv": "b4e83024ed9f5790ee3ca80557bb350d4ca57c51b6033478a4397d80a8ce1c99",
    "data/processed/risk_model_input.csv": "bef27012ebfa6d089cbab64ed823ecc4c0a667e8f6abeee5faa44294d05c5062",
}
DESIGN_TABLE = "results/systematic/fit/performance_2005_2019.csv"
TEST_TABLE = "results/systematic/test/performance_2020_on.csv"


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def table_bytes(tab: pd.DataFrame) -> bytes:
    """The table exactly as stage_fit / stage_test write it."""
    buf = io.StringIO()
    tab.to_csv(buf, index=False, float_format="%.4f")
    return buf.getvalue().encode()


def check_frozen_files(root: Path = ROOT) -> list[str]:
    """Problems with the frozen code, design and results (empty list = all as recorded)."""
    bad = [f"{p}: sha256 {sha256((root / p).read_bytes())[:16]}..., freeze record {h[:16]}..."
           for p, h in FROZEN_CODE.items() if sha256((root / p).read_bytes()) != h]
    fr = json.loads((root / "results/systematic/fit/frozen_design.json").read_text())
    if fr["design"] != json.loads(json.dumps(SY.DESIGN)):
        bad.append("systematic.DESIGN differs from frozen_design.json")
    return bad


def extract_snapshots(dest: Path, commit: str = FREEZE_COMMIT, root: Path = ROOT) -> Path:
    """Write the input snapshots of ``commit`` to ``dest`` and check their freeze-record hashes."""
    dest.mkdir(parents=True, exist_ok=True)
    for path, h in FROZEN_INPUTS.items():
        try:
            b = subprocess.run(["git", "-C", str(root), "show", f"{commit}:{path}"], check=True,
                               capture_output=True).stdout
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"cannot read {path} at {commit} from git (shallow clone? run "
                               f"`git fetch --unshallow`): {e.stderr.decode().strip()}") from e
        if sha256(b) != h:
            raise RuntimeError(f"{path} at {commit} has sha256 {sha256(b)}, freeze record {h}")
        (dest / Path(path).name).write_bytes(b)
    return dest


@contextlib.contextmanager
def frozen_inputs(proc: Path):
    """Point the frozen loaders' PROC at ``proc`` for the duration (read-only use)."""
    old = SY.PROC, RM.PROC
    SY.PROC = RM.PROC = Path(proc)
    try:
        yield
    finally:
        SY.PROC, RM.PROC = old


def rebuild(proc: Path, test_end: str) -> dict[str, pd.DataFrame]:
    """v1.0's design and test tables, recomputed with the frozen functions on the inputs in ``proc``."""
    with frozen_inputs(proc):
        inp = SY.build_inputs()
    return {DESIGN_TABLE: SY.evaluate(inp, slice(None, SY.FIT_END)),
            TEST_TABLE: SY.evaluate(inp, slice(SY.TEST_START, pd.Period(test_end, "M")))}


def compare(tables: dict[str, pd.DataFrame], root: Path = ROOT) -> dict[str, dict]:
    """Byte comparison of each rebuilt table with the committed file, plus the largest numeric gap."""
    out = {}
    for path, tab in tables.items():
        new, old = table_bytes(tab), (root / path).read_bytes()
        rec = {"identical": new == old, "sha256_rebuilt": sha256(new), "sha256_committed": sha256(old)}
        if not rec["identical"]:
            a = pd.read_csv(io.BytesIO(new))
            b = pd.read_csv(io.BytesIO(old))
            if a.shape == b.shape and list(a.columns) == list(b.columns):
                num = a.select_dtypes("number").columns
                rec["max_abs_diff"] = float((a[num] - b[num]).abs().max().max())
            else:
                rec["shape"] = (a.shape, b.shape)
        out[path] = rec
    return out


def verify(root: Path = ROOT, commit: str = FREEZE_COMMIT, keep: Path | None = None) -> bool:
    problems = check_frozen_files(root)
    for p in problems:
        print(f"FROZEN FILE CHANGED: {p}")
    if problems:
        return False
    print("frozen code, design and result files: SHA-256 as in docs/v1.0_freeze.md")
    test_end = json.loads((root / "results/systematic/test/TEST_RUN.json").read_text())["last_month"]
    with tempfile.TemporaryDirectory() as tmp:
        proc = extract_snapshots(Path(tmp) / "processed", commit, root)
        print(f"input snapshots from {commit[:7]}: SHA-256 as in docs/v1.0_freeze.md")
        tables = rebuild(proc, test_end)
    if keep:
        keep.mkdir(parents=True, exist_ok=True)
        for path, tab in tables.items():
            (keep / Path(path).name).write_bytes(table_bytes(tab))
    res = compare(tables, root)
    for path, r in res.items():
        status = "IDENTICAL" if r["identical"] else f"DIFFERENT ({ {k: v for k, v in r.items() if k != 'identical'} })"
        print(f"{path}: {status}  rebuilt {r['sha256_rebuilt'][:16]}... committed {r['sha256_committed'][:16]}...")
    comb = tables[TEST_TABLE].query("strategy == 'combined' and books == 'both books'").iloc[0]
    print(f"combined, both books, {comb['start']}..{comb['end']}: {comb['ann_return_%']:+.3f}% a year, "
          f"Sharpe {comb['sharpe']:.3f}, max drawdown {comb['max_drawdown_%']:.3f}%")
    ok = all(r["identical"] for r in res.values())
    print("v1.0 REPRODUCED EXACTLY" if ok else "v1.0 DID NOT REPRODUCE EXACTLY")
    return ok


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--commit", default=FREEZE_COMMIT, help="commit holding the frozen input snapshots")
    ap.add_argument("--keep", type=Path, help="directory to write the rebuilt tables to")
    a = ap.parse_args(argv)
    return 0 if verify(ROOT, a.commit, a.keep) else 1


if __name__ == "__main__":
    sys.exit(main())
