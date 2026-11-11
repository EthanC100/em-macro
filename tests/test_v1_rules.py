"""D004: v1.0's pre-committed cut and stop rules (ledger/v1_rules.py). Flags only; never exposure.

Every evaluation here runs on a synthetic repository in tmp_path (paper P&L, positions, screener file, rule-4 list),
never on the live ledger or the live results.
"""
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

from ledger import v1_rules as V

NOW = datetime(2026, 12, 3, 9, 0, tzinfo=timezone.utc)
THR = {"threshold_pp": 0.5202}
PNL_COLS = ["month", "net", "sample", "final_net"]


def _write_csv(path: Path, cols: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})


def _months(n: int, start: str = "2026-11") -> list[str]:
    out, m = [], start
    for _ in range(n):
        out.append(m)
        m = V.next_month(m)
    return out


def make_repo(root: Path, nets: list[float], as_of: str | None = None, carry: dict | None = None,
              positions: list[tuple[str, str, float]] | None = None, rule4: list[dict] | None = None) -> Path:
    """paper_pnl with 2026-10 (pre-live, ignored) and the given live nets; positions as_of the last booked month."""
    ms = _months(len(nets))
    rows = [{"month": "2026-10", "net": "-0.5", "final_net": "-0.5", "sample": "test"}]   # pre-live: never counted
    rows += [{"month": m, "net": f"{x:.6f}", "final_net": f"{x:.6f}", "sample": "live"} for m, x in zip(ms, nets)]
    _write_csv(root / V.PAPER_PNL, PNL_COLS, rows)
    as_of = as_of or (ms[-1] if ms else "2026-10")
    positions = positions or [("TRY", "long", 100.0), ("BRL", "long", 50.0), ("MXN", "short", -50.0),
                              ("TR10Y", "short", -50.0)]
    _write_csv(root / V.POSITIONS, ["as_of", "effective_from", "book", "instrument", "description", "side",
                                    "size_pct_of_capital"],
               [{"as_of": as_of, "effective_from": V.next_month(as_of), "instrument": i, "side": s,
                 "size_pct_of_capital": w} for i, s, w in positions])
    carry = carry if carry is not None else {"TRY": 30.0, "BRL": 10.0, "MXN": 2.0, "TR10Y": -1.0}
    _write_csv(root / V.SCREENER.format(as_of=as_of), ["as_of", "instrument", "data_month", "stale", "carry", "position"],
               [{"as_of": as_of, "instrument": i, "data_month": as_of, "stale": "False", "carry": c} for i, c in carry.items()])
    _write_csv(root / "config/v1_rules_rule4.csv", V.RULE4_COLUMNS, rule4 or [])
    return root


def status(res: dict, n: int) -> str:
    return next(r["status"] for r in res["rules"] if r["rule"] == n)


# ----------------------------------------------------------------------------- building blocks
def test_carry_spread_is_position_weighted_per_unit_of_gross():
    # (3 x 4 + 1 x 2 - 2 x 1) / (3 + 1 + 2) = 12 / 6
    assert V.carry_spread([("A", 3.0, 4.0), ("B", 1.0, 2.0), ("C", -2.0, 1.0)]) == pytest.approx(2.0)
    assert V.carry_spread([("A", 1.0, 4.0)]) == pytest.approx(4.0)               # one side only is still defined
    assert V.carry_spread([("A", 0.0, 4.0)]) is None                            # nothing held
    assert V.carry_spread([("A", 1.0, 4.0), ("C", -1.0, None)]) is None         # a held position without carry
    assert V.carry_spread([("A", None, 4.0)]) is None                           # a held position without a weight
    # a small high-carry position no longer dominates: equal weights would give (30 + 1) / 2 - 1 = 14.5
    assert V.carry_spread([("TRY", 0.1, 30.0), ("X", 2.0, 1.0), ("Y", -1.9, 1.0)]) == pytest.approx((3.0 + 2.0 - 1.9) / 4.0)


def test_percentile_matches_numpy():
    xs = [5.0, 1.0, 3.3, 2.2, 9.1, 4.4, 0.5]
    for q in (5, 10, 50, 90):
        assert V.percentile(xs, q) == pytest.approx(float(np.percentile(xs, q)))


def test_no_live_month_yet_is_index_100_and_no_flag(tmp_path):
    make_repo(tmp_path, [], as_of="2026-10")
    res = V.evaluate(tmp_path, NOW, THR, previous=[])
    assert res["live_months"] == 0 and res["index"] == 100.0 and res["drawdown_pct"] == 0.0
    assert res["carry_spread_pp"] == pytest.approx((100 * 30 + 50 * 10 - 50 * 2 - 50 * -1) / 250)
    assert res["flags"] == [] and not res["flagged"]
    assert [status(res, n) for n in range(1, 6)] == ["ok"] * 5


def test_pre_live_month_never_enters_the_index(tmp_path):
    make_repo(tmp_path, [0.01])
    res = V.evaluate(tmp_path, NOW, THR, previous=[])
    assert res["index"] == pytest.approx(101.0) and res["live_months"] == 1


# ----------------------------------------------------------------------------- rules 1 and 2
def test_rule1_halves_at_20pct_below_the_live_peak_and_restores_within_10pct():
    # peak 110, then down to 88 (-20%): halve; 92 (-16.4%): in force; 99.5 (-9.5%): restore
    path = V.index_path([{"month": m, "net": x} for m, x in zip(_months(4), [0.10, -0.20, 92 / 88 - 1, 99.5 / 92 - 1])])
    assert [p["halve_on"] for p in path] == [False, True, False, False]
    assert [p["halved"] for p in path] == [False, True, True, False]
    assert [p["restore"] for p in path] == [False, False, False, True]
    assert path[1]["drawdown"] == pytest.approx(-0.20)


def test_rule1_flag_in_force_and_restore(tmp_path):
    make_repo(tmp_path, [0.10, -0.20])
    res = V.evaluate(tmp_path, NOW, THR, previous=[])
    assert status(res, 1) == "triggered" and res["halved"]
    assert any("rule 1 (halve) triggered" in f and "halve gross exposure" in f for f in res["flags"])
    make_repo(tmp_path, [0.10, -0.20, 0.01])
    res = V.evaluate(tmp_path, NOW, THR, previous=[])
    assert status(res, 1) == "in force" and not any("rule 1" in f for f in res["flags"])
    make_repo(tmp_path, [0.10, -0.20, 0.20])
    res = V.evaluate(tmp_path, NOW, THR, previous=[])
    assert status(res, 1) == "triggered" and "restore full exposure" in res["rules"][0]["action"]


def test_rule1_not_triggered_at_19pct(tmp_path):
    make_repo(tmp_path, [0.05, -0.19])
    res = V.evaluate(tmp_path, NOW, THR, previous=[])
    assert status(res, 1) == "ok" and status(res, 2) == "ok" and res["drawdown_pct"] == pytest.approx(-19.0)


def test_rule2_stop_at_27pct_is_sticky(tmp_path):
    make_repo(tmp_path, [0.0, -0.27])
    res = V.evaluate(tmp_path, NOW, THR, previous=[])
    assert status(res, 2) == "triggered"
    assert any("rule 2 (stop) triggered" in f and "close v1.0 entirely" in f for f in res["flags"])
    make_repo(tmp_path, [0.0, -0.27, 0.40])          # recovers to a new peak: the stop still stands
    res = V.evaluate(tmp_path, NOW, THR, previous=[])
    assert status(res, 2) == "triggered" and "2026-12 month-end" in res["rules"][1]["detail"]


# ----------------------------------------------------------------------------- rule 3
def test_rule3_waits_for_24_months_then_flags_a_negative_sharpe(tmp_path):
    nets = [0.01, -0.02] * 11 + [-0.01]              # 23 months, negative mean: not yet evaluated
    make_repo(tmp_path, nets)
    res = V.evaluate(tmp_path, NOW, THR, previous=[])
    assert status(res, 3) == "ok" and res["sharpe"] < 0
    make_repo(tmp_path, nets + [-0.01])              # the 24th month
    res = V.evaluate(tmp_path, NOW, THR, previous=[])
    assert status(res, 3) == "triggered" and any("rule 3 (time) triggered" in f and "stop v1.0" in f for f in res["flags"])


def test_rule3_passes_with_a_positive_sharpe(tmp_path):
    make_repo(tmp_path, [0.02, -0.01] * 12)
    res = V.evaluate(tmp_path, NOW, THR, previous=[])
    assert status(res, 3) == "passed" and not any("rule 3" in f for f in res["flags"])


def test_sharpe_is_the_apps_figure(tmp_path):
    from ledger.build import perf_stats
    nets = [0.01, -0.005, 0.02, 0.003]
    make_repo(tmp_path, nets)
    res = V.evaluate(tmp_path, NOW, THR, previous=[])
    assert res["sharpe"] == pytest.approx(perf_stats(nets)["sharpe"], abs=1e-3)


# ----------------------------------------------------------------------------- rule 4
def test_rule4_a_listed_currency_covers_its_fx_and_its_bond(tmp_path):
    make_repo(tmp_path, [0.01], rule4=[
        {"currency": "TRY", "event": "capital controls", "start": "2026-11-15", "source": "CBRT"},
        {"instrument": "BRL", "event": "managed peg", "start": "2026-11-01", "end": "2026-11-20", "source": "x"},  # ended
        {"currency": "MXN", "event": "closed market", "start": "2027-01-05", "source": "y"}]) # after the month-end
    res = V.evaluate(tmp_path, NOW, THR, previous=[])
    assert status(res, 4) == "triggered"
    assert sorted(h["instrument"] for h in res["rule4_hits"]) == ["TR10Y", "TRY"]
    assert "drop TR10Y, TRY at the next rebalance" in res["flags"][0]


def test_rule4_unheld_currency_does_not_trigger(tmp_path):
    make_repo(tmp_path, [0.01], rule4=[{"currency": "COP", "event": "crawl", "start": "2026-01-01", "source": "z"}])
    assert status(V.evaluate(tmp_path, NOW, THR, previous=[]), 4) == "ok"


# ----------------------------------------------------------------------------- rule 5
LOW = {"TRY": 0.5, "BRL": 0.5, "MXN": 0.5, "TR10Y": 0.5}      # spread (50 + 25 - 25 - 25) / 250 = 0.1pp < 0.5202


def test_rule5_one_month_below_is_a_watch_two_consecutive_is_a_review(tmp_path):
    make_repo(tmp_path, [0.01], carry=LOW)
    res = V.evaluate(tmp_path, NOW, THR, previous=[{"as_of": "2026-10", "carry_below": "False"}])
    assert res["carry_spread_pp"] == pytest.approx(0.1) and status(res, 5) == "watch" and res["carry_streak"] == 1
    assert res["flags"] == []
    res = V.evaluate(tmp_path, NOW, THR, previous=[{"as_of": "2026-10", "carry_below": "True"}])
    assert status(res, 5) == "triggered" and res["carry_streak"] == 2
    assert any("rule 5 (carry-spread review) triggered" in f and "written review by 2026-12-10" in f
               and "no automatic cut" in f for f in res["flags"])


def test_rule5_needs_consecutive_month_ends(tmp_path):
    make_repo(tmp_path, [0.01, 0.01], carry=LOW)       # as_of 2026-12; 2026-11 missing from the history
    res = V.evaluate(tmp_path, NOW, THR, previous=[{"as_of": "2026-10", "carry_below": "True"}])
    assert status(res, 5) == "watch" and res["carry_streak"] == 1


def test_rule5_missing_screener_or_changed_threshold_is_flagged_not_silent(tmp_path):
    make_repo(tmp_path, [0.01])
    (tmp_path / V.SCREENER.format(as_of="2026-11")).unlink()
    res = V.evaluate(tmp_path, NOW, THR, previous=[])
    assert status(res, 5) == "error" and any("cannot be checked" in f for f in res["flags"])
    make_repo(tmp_path, [0.01])
    bad = tmp_path / "thr.json"
    bad.write_text(json.dumps({"threshold_pp": 9.0}))
    res = V.evaluate(tmp_path, NOW, V.load_threshold(bad, expected_sha="0" * 64), previous=[])
    assert status(res, 5) == "error" and "threshold file changed" in res["rules"][4]["detail"]


# ----------------------------------------------------------------------------- the frozen threshold
def test_live_sign_follows_the_side_and_a_missing_size_is_an_error(tmp_path):
    make_repo(tmp_path, [0.01], positions=[("TRY", "long", 100.0), ("MXN", "short", 50.0)])   # short written unsigned
    res = V.evaluate(tmp_path, NOW, THR, previous=[])
    assert res["carry_spread_pp"] == pytest.approx((100 * 30 - 50 * 2) / 150, abs=1e-4)
    assert [h["weight_pct"] for h in res["carry_holdings"]] == [100.0, -50.0]
    make_repo(tmp_path, [0.01], positions=[("TRY", "long", ""), ("MXN", "short", -50.0)])
    res = V.evaluate(tmp_path, NOW, THR, previous=[])
    assert status(res, 5) == "error" and "no size_pct_of_capital for held TRY" in res["rules"][4]["detail"]


def test_superseded_equal_weight_threshold_is_kept_unchanged():
    assert V.sha256_file(V.SUPERSEDED_THRESHOLD_FILE) == V.SUPERSEDED_THRESHOLD_SHA256
    old = json.loads(V.SUPERSEDED_THRESHOLD_FILE.read_text(encoding="utf-8"))
    assert old["threshold_pp"] == 3.176 and "equal-weighted" in old["method"]
    assert V.SUPERSEDED_HISTORY_FILE.exists()
    new = json.loads(V.THRESHOLD_FILE.read_text(encoding="utf-8"))
    ch = new["definition_change"]
    assert ch["before_first_live_evaluation"] is True and "TRY" in ch["why"]
    assert ch["previous_file_sha256"] == V.SUPERSEDED_THRESHOLD_SHA256 and ch["previous_threshold_pp"] == 3.176
    assert "divided by gross exposure" in new["method"]


def test_threshold_file_is_frozen_pinned_and_uses_2005_2019_only():
    thr = V.load_threshold()
    assert "error" not in thr, thr.get("error")
    assert V.sha256_file(V.THRESHOLD_FILE) == V.FROZEN_THRESHOLD_SHA256
    assert thr["decision"] == "D004" and thr["percentile"] == 10 and thr["data_through"] == "2019-12"
    assert thr["method"] and thr["source"]
    with V.THRESHOLD_HISTORY.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == thr["n_month_ends"] and all(r["as_of"] <= "2019-12" for r in rows)
    assert rows[0]["as_of"] >= "2005-01"
    for r in rows[:24]:          # gross exposure is the sum of the stored absolute weights
        assert float(r["gross_leverage"]) == pytest.approx(sum(abs(float(p.split(":")[1])) for p in r["positions"].split()), abs=1e-3)
    vals = [float(r["carry_spread_pp"]) for r in rows]
    assert round(float(np.percentile(vals, 10)), 4) == thr["threshold_pp"]
    assert thr["reproduction_check"]["max_abs_diff_net"] < 1e-5      # the official in-sample P&L was reproduced


def test_freeze_refuses_to_recompute():
    with pytest.raises(SystemExit):
        V.freeze()


# ----------------------------------------------------------------------------- outputs
def test_write_only_its_two_files_and_replaces_a_rerun_month(tmp_path):
    make_repo(tmp_path, [0.01])
    before = {p for p in tmp_path.rglob("*") if p.is_file()}
    res = V.evaluate(tmp_path, NOW, THR, previous=[])
    written = V.write(res, tmp_path)
    assert written == ["data/ledger/v1_rules.json", "data/ledger/v1_rules_history.csv"]
    after = {p for p in tmp_path.rglob("*") if p.is_file()}
    assert {p.relative_to(tmp_path).as_posix() for p in after - before} == set(written)
    V.write(V.evaluate(tmp_path, NOW, THR, previous=[]), tmp_path)        # a re-run of the same month
    with (tmp_path / V.HISTORY_FILE.relative_to(V.ROOT)).open(newline="") as f:
        rows = list(csv.DictReader(f))
    assert [r["as_of"] for r in rows] == ["2026-11"]
    assert V.load_state(tmp_path)["decision"] == "D004"


def test_monitor_reads_the_history_for_the_streak(tmp_path):
    make_repo(tmp_path, [0.01], carry=LOW)
    V.write(V.evaluate(tmp_path, NOW, THR, previous=[]), tmp_path)              # 2026-11: below (1)
    make_repo(tmp_path, [0.01, 0.0], carry=LOW)
    res = V.evaluate(tmp_path, NOW, THR)                                       # reads tmp history: 2026-12 below (2)
    assert res["carry_streak"] == 2 and status(res, 5) == "triggered"


def test_monitor_never_touches_frozen_or_exposure_files():
    src = (V.ROOT / "ledger/v1_rules.py").read_text(encoding="utf-8")
    # it writes with write_text / open("w") only in write() and freeze(); the frozen v1.0 paths never appear as targets
    for frozen in ("em_macro/systematic.py", "frozen_design.json", "frozen_params.json"):
        assert f'"{frozen}").write' not in src and f"'{frozen}').write" not in src
    assert "overrides.yaml" not in src and "positions.csv\").write" not in src


def test_summary_lines_and_morning_section():
    from nightshift import morning as M
    assert "no evaluation yet" in V.summary_lines(None)[0]
    res = {"as_of": "2027-03", "index": 79.5, "drawdown_pct": -21.2, "live_months": 5, "sharpe": -1.1,
           "carry_spread_pp": 4.1, "carry_threshold_pp": 3.176, "flags": ["D004 rule 1 (halve) triggered: x -> y"]}
    lines = M.v1_rules_section(res)
    assert lines[0].startswith("2027-03 month-end: index 79.50, drawdown -21.2%")
    assert lines[1] == "FLAG: D004 rule 1 (halve) triggered: x -> y"
    assert M.v1_rules_section({**res, "flags": []})[1] == "No rule triggered."


def test_app_build_reads_the_state(tmp_path, monkeypatch):
    from ledger import build as B
    monkeypatch.setattr(B, "ROOT", tmp_path)
    assert B.build_v1_rules()["available"] is False
    make_repo(tmp_path, [0.01])
    V.write(V.evaluate(tmp_path, NOW, THR, previous=[]), tmp_path)
    out = B.build_v1_rules()
    assert out["available"] is True and out["decision"] == "D004" and len(out["rules"]) == 5


def test_d004_files_are_protected_and_the_monitor_outputs_are_not():
    from nightshift import protected as P
    for path in ("ledger/v1_rules.py", "results/v1_rules/carry_spread_threshold.json",
                 "results/v1_rules/superseded/carry_spread_threshold_equal_weight.json", "config/v1_rules_rule4.csv"):
        assert P.protected([path]) == [path], path
        block = P.CODEOWNERS.read_text(encoding="utf-8").split("# protected:start")[1].split("# protected:end")[0]
        pats = [ln.split()[0] for ln in block.splitlines() if ln.strip() and not ln.strip().startswith("#")]
        assert P.protected([path], pats) == [path], f"{path} missing from the CODEOWNERS block"
    # the monitor's own outputs stay writable by the v1-rules-monitor workflow
    assert P.protected(["data/ledger/v1_rules.json", "data/ledger/v1_rules_history.csv"]) == []
