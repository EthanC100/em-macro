"""em_macro/verify_v1.py: rebuild v1.0's design and test tables with the frozen functions.

The full reproduction downloads the series that are not in git (FRED, Yahoo, BIS, BanRep, BCCh) unless
data/raw/ already holds them, and needs commit 7886867 in the clone (the monthly workflow checks out a
shallow clone), so it runs only with EM_MACRO_VERIFY_V1=1:

    EM_MACRO_VERIFY_V1=1 python -m pytest -q tests/test_verify_v1.py
"""
import os
import subprocess

import pandas as pd
import pytest

from em_macro import risk_model as RM
from em_macro import systematic as SY
from em_macro import verify_v1 as V
from em_macro.config import PROC, ROOT


def _has_commit(c: str) -> bool:
    r = subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", f"{c}^{{commit}}"], capture_output=True)
    return r.returncode == 0


def test_frozen_files_match_the_freeze_record():
    assert V.check_frozen_files() == []


def test_table_bytes_is_how_the_stages_write_the_committed_tables():
    committed = (ROOT / V.TEST_TABLE).read_bytes()
    assert V.table_bytes(pd.read_csv(ROOT / V.TEST_TABLE)) == committed


def test_compare_reports_identical_and_different_tables(tmp_path):
    tab = pd.DataFrame({"strategy": ["combined", "carry only"], "sharpe": [0.65412, 0.5], "months": [81, 81]})
    (tmp_path / "t.csv").write_bytes(V.table_bytes(tab))
    assert V.compare({"t.csv": tab}, tmp_path)["t.csv"]["identical"]
    off = tab.assign(sharpe=[0.6551, 0.5])                    # moves the 4th decimal
    r = V.compare({"t.csv": off}, tmp_path)["t.csv"]
    assert not r["identical"] and r["max_abs_diff"] == pytest.approx(0.001)


def test_frozen_inputs_redirects_and_restores_proc(tmp_path):
    with V.frozen_inputs(tmp_path):
        assert SY.PROC == tmp_path and RM.PROC == tmp_path
    assert SY.PROC == PROC and RM.PROC == PROC


@pytest.mark.skipif(not _has_commit(V.FREEZE_COMMIT), reason="commit 7886867 not in this clone (shallow)")
def test_snapshots_from_the_freeze_commit_match_the_record(tmp_path):
    out = V.extract_snapshots(tmp_path)
    assert sorted(p.name for p in out.iterdir()) == sorted(p.split("/")[-1] for p in V.FROZEN_INPUTS)


@pytest.mark.skipif(os.environ.get("EM_MACRO_VERIFY_V1") != "1",
                    reason="full reproduction: set EM_MACRO_VERIFY_V1=1 (downloads uncached series)")
def test_v1_reproduces_exactly(tmp_path):
    assert V.verify(keep=tmp_path)
    assert (tmp_path / "performance_2020_on.csv").read_bytes() == (ROOT / V.TEST_TABLE).read_bytes()
    assert (tmp_path / "performance_2005_2019.csv").read_bytes() == (ROOT / V.DESIGN_TABLE).read_bytes()
