"""Manhattan ops: the paper-runner readiness result (metadata and a synthetic rehearsal; no outcomes)."""
import json

from manhattan.ops import paper_readiness as P


def test_static_readiness_names_every_blocker_and_its_owner():
    checks = P.static_checks(10)
    by = {c["id"]: c for c in checks}
    assert by["R01"]["status"] == P.OWNER                    # no owner-frozen batch exists yet
    assert by["R04"]["status"] == P.BUILD and by["R05"]["status"] == P.BUILD
    assert by["R13"]["status"] == P.READY                    # reserve, claims and promotion are off
    assert by["R14"]["status"] == P.GATE
    assert all(c["owner_step"] for c in checks if c["status"] == P.OWNER)
    v = P.verdict(checks, None)
    assert v["paper_recording"] == "not_ready" and v["evidence_may_count"] is False


def test_rehearsal_through_the_real_entry_point_reconciles(tmp_path):
    r = P.rehearse(3, root=tmp_path)
    assert r["passed"], r
    assert [x["exit"] for x in r["runs"]] == [0, 0, 0, 0, 137, 0]
    assert r["families"] == 3 and r["unique_executable_configurations"] == r["predictions_registered"] > 0
    per_night = r["predictions_registered"]
    assert r["total_attempts"] == 4 * per_night                 # three nights + the retry of the killed one
    assert r["aborted_attempts"] == per_night and r["completed_attempts"] == 3 * per_night
    assert r["independent_statistical_tests"] is None
    text = json.dumps(r)
    for word in ("net", "gross", "sharpe", "pnl"):            # counts and seconds only
        assert f'"{word}"' not in text
