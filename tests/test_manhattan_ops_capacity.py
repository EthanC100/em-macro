"""Manhattan ops: the capacity harness runs and reports (O-36). Tiny sizes; the real measurements are in
results/manhattan_ops/CAPACITY.md."""
import json

from manhattan.ops import capacity as C


def test_executables_are_distinct_and_cover_every_kind():
    xs = [C.executable_at(i) for i in range(64)]
    assert len({x.spec_hash for x in xs}) == 64
    assert {x.kind for x in xs} == {k for k, *_ in C.KINDS}


def test_measure_and_report(tmp_path):
    for mode in ("daily", "full"):
        r = C.measure(4, mode, 1, chunk=2)
        assert r["n_executables"] == 4 and r["cpu_seconds"] > 0 and r["peak_rss_mib_largest_process"] > 0
        (tmp_path / f"{mode}_1000.json").write_text(json.dumps({**r, "n_executables": 1000}))
    led = C.measure_ledger(30)
    assert led["n_records"] == 30 and led["chain_bytes"] > 0
    text = C.report(tmp_path)
    assert "| daily | 1,000 | 1 |" in text and "nothing is extrapolated" in text
