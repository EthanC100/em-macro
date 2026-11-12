"""Q008: two existing tests must not depend on whether a private settlement store happens to exist.

The Janus CLI and the promote routine create a read-only clone of em-macro-data at ``../em-macro-data``
(``ledger/settlements.py`` ``store_dir``: ``EM_MACRO_DATA`` or the sibling directory). With that clone present,
``tests/test_janus.py`` bad11 (a NATGAS proposal must be refused for want of a private settlement) and
``tests/test_settlements.py::test_no_store_fetches_nothing`` failed, because both read whatever store the machine has.

This test never creates, fills or deletes the real sibling ``../em-macro-data``: it simulates a store with
``EM_MACRO_DATA`` pointing at a temporary directory that holds one made-up NATGAS settlement row (synthetic, never
copied from the real store), with and without the read-only clone marker, and runs the two tests in a child pytest.
They must pass because they pin ``EM_MACRO_DATA`` to a missing path themselves.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from ledger import settlements as ST

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ["tests/test_janus.py::test_rule_breaking_proposals_are_rejected_whole[bad11-no private settlement]",
           "tests/test_settlements.py::test_no_store_fetches_nothing"]


def _dummy_store(base: Path, read_only: bool) -> Path:
    """A stand-in for em-macro-data with one synthetic NATGAS row for the front contract on 2026-11-06 (NGF27)."""
    store = base / "em-macro-data"
    store.mkdir()
    ST.write(store, [{"date": "2026-11-05", "product": "NATGAS", "contract_month": "2027-01", "settle": "3.9",
                      "source": ST.SOURCE, "source_url": "", "fetched_at": "synthetic", "note": "test_q008"}])
    if read_only:
        (store / ST.READ_ONLY_MARK).write_text("synthetic read-only clone (test_q008)\n")
    return store


@pytest.mark.parametrize("read_only", [False, True], ids=["store", "read-only-clone"])
def test_q008_tests_pass_with_a_private_store_present(tmp_path, read_only):
    store = _dummy_store(tmp_path, read_only)
    assert ST.read(store), "the synthetic NATGAS row was not written"
    env = {k: v for k, v in os.environ.items() if k not in (ST.TOKEN_ENV, "DATA_REPO_URL")}
    env["EM_MACRO_DATA"] = str(store)
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *TARGETS],
                       cwd=ROOT, env=env, capture_output=True, text=True, timeout=600)
    assert r.returncode == 0 and "2 passed" in r.stdout, r.stdout[-3000:] + r.stderr[-2000:]
