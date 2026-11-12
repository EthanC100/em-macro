"""Q009: tests/test_janus_futures.py::test_option_spread_fill_model_value_and_expiry failed about 1.2% of the time.

Its last check searched the whole Janus records file for the settlement prices "4500" and "4110". ledger/janus.py
stamps each record with ``recorded_at`` (now, one-second resolution) and chains a SHA-256 hash over it, so every
``hash`` / ``prev_hash`` changes each second, and 64 hex digits contain "4500" or "4110" by chance. The fix keeps the
guarantee that no settlement price is in the records: a price is found as a JSON number or inside any string, and only
the hash and digest fields are left out (``price_hits`` in tests/test_janus_futures.py). Tests only: ledger/ is unchanged.

Everything here runs in tmp_path with the frozen repository mirror and a temporary settlement store; it never reads
data/janus/ or em-macro-data. Assertion messages show clock values and JSON paths only, never a record or a price.
"""
import json
import os
from datetime import datetime, timedelta, timezone

import pytest

import test_janus_futures as TJF
from ledger import janus as J

T0 = datetime(2026, 11, 10, tzinfo=timezone.utc)
STEP = timedelta(seconds=7)                    # the sweep in the Q009 evidence: T0 + 7*i seconds, i = 0..5999
N_SWEEP = 6000
# the first three clocks at which the old check failed on main 93eba8e (Q009 evidence). Which seconds collide depends
# on the records' content (on dev after Janus C13: 68 of 6000, from 00:12:57), so the tests below also find the
# colliding clocks of the code they run against, with the old check, and run the test at those.
EVIDENCE_CLOCKS = ("2026-11-10T00:01:38+00:00", "2026-11-10T00:12:50+00:00", "2026-11-10T00:16:48+00:00")


def _pinned(at: datetime):
    class Pinned(datetime):
        @classmethod
        def now(cls, tz=None):
            return at if tz is None else at.astimezone(tz)
    return Pinned


def _run_at(at: datetime, root, frozen_repo, monkeypatch):
    """test_option_spread_fill_model_value_and_expiry with ledger.janus's clock pinned to ``at``, in a fresh directory
    with its own settlement store. Returns the records path."""
    root.mkdir(parents=True)
    store = root / "em-macro-data"
    store.mkdir()
    monkeypatch.setenv("EM_MACRO_DATA", str(store))
    monkeypatch.setattr(J, "datetime", _pinned(at))
    try:
        TJF.test_option_spread_fill_model_value_and_expiry(root, store, frozen_repo)
    finally:
        monkeypatch.undo()
    return root / "r.jsonl"


def _restamp(records: list[dict], old: str, new: str) -> list[dict]:
    """The records a run at clock ``new`` writes, from those of a run at clock ``old``: the clock only enters through
    ``recorded_at`` and the hash chain over it."""
    out, prev = [], J.GENESIS
    for r in records:
        r = {k: v for k, v in r.items() if k != "hash"}
        if r.get("recorded_at") == old:
            r["recorded_at"] = new
        r["prev_hash"] = prev
        r["hash"] = prev = J.chain_hash(prev, r)
        out.append(r)
    return out


def _text(records: list[dict]) -> str:
    return "".join(json.dumps(r, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n" for r in records)


def _old_check_fails(text: str) -> bool:
    """The check before Q009: either price's digits anywhere in the file, hashes included."""
    return "4500" in text or "4110" in text


def _sweep(base: list[dict]):
    t0 = T0.isoformat()
    for i in range(N_SWEEP):
        clock = (T0 + i * STEP).isoformat()
        yield clock, _restamp(base, t0, clock)


def test_q009_option_spread_test_passes_at_colliding_clocks(tmp_path, frozen_repo, monkeypatch):
    """At the clocks where the old check finds "4500"/"4110" inside a record hash, the test passes (failed before
    the fix at its last assert, tests/test_janus_futures.py:149)."""
    base = J.load(_run_at(T0, tmp_path / "base", frozen_repo, monkeypatch))
    colliding = [clock for clock, recs in _sweep(base) if _old_check_fails(_text(recs))]
    if not colliding:
        pytest.skip("no clock in the sweep makes a record hash contain 4500 or 4110 with the current records")
    for k, clock in enumerate(colliding[:3] + list(EVIDENCE_CLOCKS)):
        _run_at(datetime.fromisoformat(clock), tmp_path / f"run{k}", frozen_repo, monkeypatch)


def test_q009_price_check_still_finds_a_price():
    """The check is not weakened: a price as a JSON number, inside a string, or in a key is found, also nested;
    the same digits inside hash, prev_hash and digest fields are not; the hits name JSON paths, never values."""
    h = "ab4500cd" * 8
    clean = {"seq": 1, "hash": h, "prev_hash": h, "entry_digest": h, "exit_digest": h, "proposal_sha256": h,
             "option": {"legs": "long 4200 call, short 4600 call"}, "stop": 3800.0}
    assert TJF.price_hits(_text([clean]), 4500.0, 4110.0) == []
    for leak, where in (({"close": {"exit_level": 4500.0}}, "close.exit_level"),
                        ({"close": {"exit_level": 4500}}, "close.exit_level"),
                        ({"fill": {"premium": [1.0, 4110.0]}}, "fill.premium[1]"),
                        ({"note": "settled at 4110 on expiry"}, "note"),
                        ({"note": "settled at 4500.0"}, "note"),
                        ({"levels": {"4500": "x"}}, "levels.4500")):
        hits = TJF.price_hits(_text([clean, {**clean, "seq": 2, **leak}]), 4500.0, 4110.0)
        assert hits == [f"line 2: {where}"], (where, hits)
    assert TJF.price_hits(_text([{"note": "88.37", "hash": "8837"}]), 88.37) == ["line 1: note"]


def test_q009_clock_sweep_has_no_failure(tmp_path, frozen_repo, monkeypatch):
    """6000 distinct clock values (T0 + 7*i s): the price check finds nothing at any of them. One real run at T0
    gives the records; each clock's records are T0's re-stamped and re-chained, which is checked to be exactly
    what a real run writes at the colliding clocks and at a few others. (Q009_FULL_SWEEP=1 runs all 6000 for real,
    about 100 s, too slow for the suite that gates the writers' commits.)"""
    base = J.load(_run_at(T0, tmp_path / "base", frozen_repo, monkeypatch))
    t0 = T0.isoformat()
    assert any(r.get("recorded_at") == t0 for r in base)
    sweep = list(_sweep(base))
    colliding = [clock for clock, recs in sweep if _old_check_fails(_text(recs))]
    for k, clock in enumerate(colliding[:2] + list(EVIDENCE_CLOCKS) + ["2026-11-10T03:00:01+00:00"]):
        real = _run_at(datetime.fromisoformat(clock), tmp_path / f"real{k}", frozen_repo, monkeypatch)
        assert _text(_restamp(base, t0, clock)) == real.read_text(), clock
    heads, failed = set(), []
    for clock, recs in sweep:
        heads.add(recs[-1]["hash"])
        if TJF.price_hits(_text(recs), 4500.0, 4110.0):
            failed.append(clock)
    assert len(heads) == N_SWEEP                       # 6000 distinct hash sets, not a few re-used seconds
    assert failed == [], f"{len(failed)} of {N_SWEEP} clocks fail, first {failed[:3]}"


@pytest.mark.skipif(os.environ.get("Q009_FULL_SWEEP") != "1", reason="Q009_FULL_SWEEP=1 runs 6000 real runs (~100 s)")
def test_q009_full_clock_sweep_real_runs(tmp_path, frozen_repo, monkeypatch):
    failed = []
    for i in range(N_SWEEP):
        at = T0 + i * STEP
        try:
            _run_at(at, tmp_path / str(i), frozen_repo, monkeypatch)
        except AssertionError:
            failed.append(at.isoformat())
    assert failed == [], f"{len(failed)} of {N_SWEEP} clocks fail, first {failed[:3]}"
