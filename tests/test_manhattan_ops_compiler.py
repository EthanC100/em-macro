"""Manhattan ops: compiler (O-26 to O-28), variant limits (O-23 to O-25), mechanical critic and freeze tooling (O-33).
Synthetic data only."""
import inspect
import json
import subprocess
from datetime import date
from pathlib import Path

import numpy as np
import pytest

from manhattan import critic as C
from manhattan import roles
from manhattan import spec as S
from manhattan.engine import backtest, lookahead
from manhattan.engine.pit import PitStore, Reader
from manhattan.generate import parse_reply
from manhattan.ops import compiler as CP
from manhattan.ops import critic_rules as CR
from manhattan.ops import freeze_pr as FP
from manhattan.ops import justify as J
from manhattan.ops import mockgen

ROOT = Path(__file__).resolve().parents[1]
FENCE = roles.Fence(exploration_end=date(2019, 12, 31), reserve={})
DAYS = np.array([d for d in np.arange(np.datetime64("2019-03-01"), np.datetime64("2019-04-30")) if np.is_busday(d)])
TIMING = {"calendar": "synthetic", "horizon_sessions": 1, "execution_lag": {"minutes": 0, "sessions": 0},
          "data_cutoff": "2019-12-31"}
REASON = "the hedging calendar of the counterparty is uncertain within this range of days"


def fam(sign="+"):
    return S.family(mechanism="SYNTHETIC test mechanism", mechanism_class="flow", sign=sign,
                    counterparty="synthetic", kill_condition="synthetic", tail_exposure="none declared")


def hyp(f, kind, fixed=None, grid=None, freq="D", sizing="EW", just=None, **extra):
    grid = grid or {}
    return S.hypothesis(f, domain="syn_daily", data_sources=[{"name": "syn", "publication_lag_days": 0}],
                        signal={"kind": kind, "description": "test", **(fixed or {})}, frequency=freq,
                        primary_binding={"universe_id": "U_SYN6", "cost_model_id": "C0", "sizing_id": sizing},
                        grid=grid, timing=TIMING,
                        grid_justification=just if just is not None else
                        {k: {"reason": REASON, "mechanism_range": [min(v), max(v)]} for k, v in grid.items() if len(v) > 1},
                        **extra)


def store(prices=None, carry=None, events=None):
    st = PitStore()
    n = DAYS.size
    for c in "ABCDEF":
        p = (prices or {}).get(c, np.full(n, 100.0))
        st.add(f"syn_px_{c}", DAYS, p, lag_days=0)
        st.add(f"syn_carry_{c}", DAYS, np.full(n, (carry or {}).get(c, 0.03)), lag_days=0)
    for c, (i, v) in (events or {}).items():
        st.add(f"syn_evt_{c}", DAYS[i:i + 1], [v], available=DAYS[i:i + 1])
    return st


def run(h, f, st):
    x = next(CP.iter_executables(f, h, "c" * 40))
    w = Reader(st, caller="session", domain="syn_daily", fence=FENCE).window(date(2019, 3, 1), date(2019, 4, 29))
    return backtest.run(w, x.strategy()), x


UP = 100 * 1.01 ** np.arange(DAYS.size)
DOWN = 100 * 0.99 ** np.arange(DAYS.size)


def w_at(res, day):
    j = int(np.flatnonzero(res.dates == np.datetime64(day))[0])
    return dict(zip(res.instruments, res.decisions[j]))


# ---- O-27, O-28: one hand check per kind

def test_tsmom_and_reversal_and_sign():
    st = store({"A": UP, "B": DOWN})
    w = w_at(run(hyp(fam(), "tsmom", grid={"lookback": [5]}), fam(), st)[0], "2019-03-20")
    assert w == {"SYN_A": 0.5, "SYN_B": -0.5, "SYN_C": 0.0, "SYN_D": 0.0, "SYN_E": 0.0, "SYN_F": 0.0}
    w = w_at(run(hyp(fam(), "reversal", grid={"lookback": [5]}), fam(), st)[0], "2019-03-20")
    assert w["SYN_A"] == -0.5 and w["SYN_B"] == 0.5
    w = w_at(run(hyp(fam("-"), "tsmom", grid={"lookback": [5]}), fam("-"), st)[0], "2019-03-20")
    assert w["SYN_A"] == -0.5 and w["SYN_B"] == 0.5                        # the family's sign flips every weight
    early = run(hyp(fam(), "tsmom", grid={"lookback": [5]}), fam(), st)[0]
    assert all(v == 0 for v in w_at(early, "2019-03-05").values())         # fewer than 6 prices known: no position


def test_xs_momentum_carry_calendar_event_buy_hold():
    st = store({"A": UP, "B": DOWN}, carry={"A": 0.05, "B": 0.01}, events={"C": (10, 0.2)})
    w = w_at(run(hyp(fam(), "xs_momentum", {"n_long": 1}, {"lookback": [5]}, freq="W"), fam(), st)[0], "2019-03-22")
    assert w["SYN_A"] == 0.5 and w["SYN_B"] == -0.5 and sum(abs(v) for v in w.values()) == 1.0
    w = w_at(run(hyp(fam(), "carry", grid={"threshold": [0.0]}, freq="M"), fam(), st)[0], "2019-03-29")
    assert w["SYN_A"] == 0.5 and w["SYN_B"] == -0.5 and w["SYN_C"] == 0.0
    res = run(hyp(fam(), "calendar", {"end_day": 28}, {"start_day": [20]}), fam(), st)[0]
    assert all(abs(v - 1 / 6) < 1e-15 for v in w_at(res, "2019-03-21").values())
    assert all(v == 0 for v in w_at(res, "2019-03-05").values())
    res = run(hyp(fam(), "event", grid={"hold": [2]}, freq="event"), fam(), st)[0]
    ev_day = str(DAYS[10])
    assert abs(w_at(res, ev_day)["SYN_C"] - 0.2 / 6) < 1e-15 and w_at(res, str(DAYS[11]))["SYN_C"] != 0
    assert w_at(res, str(DAYS[12]))["SYN_C"] == 0 and w_at(res, str(DAYS[9]))["SYN_C"] == 0     # never early
    res = run(hyp(fam(), "buy_hold", grid={"scale": [0.5]}, freq="M"), fam(), st)[0]
    assert all(abs(v - 0.5 / 6) < 1e-15 for v in w_at(res, "2019-03-29").values())


@pytest.mark.parametrize("kind, fixed, grid, freq", [
    ("tsmom", {}, {"lookback": [5]}, "D"), ("xs_momentum", {"n_long": 1}, {"lookback": [5]}, "W"),
    ("carry", {}, {"threshold": [0.0]}, "M"), ("event", {}, {"hold": [3]}, "event")])
def test_compiled_executables_pass_the_lookahead_check(kind, fixed, grid, freq):
    rng = np.random.default_rng(1)
    prices = {c: 100 * np.exp(np.cumsum(rng.normal(0, 0.01, DAYS.size))) for c in "ABCDEF"}
    st = store(prices, carry={c: float(rng.uniform(0, 0.06)) for c in "ABCDEF"}, events={"A": (8, 0.2), "D": (20, -0.2)})
    h = hyp(fam(), kind, fixed, grid, freq=freq)

    def go(s):
        return run(h, fam(), s)[0]

    assert lookahead.violations(go, st, ["2019-03-15", "2019-04-01", "2019-04-15"]) == []


def test_compilation_is_deterministic_and_refuses_what_it_does_not_know():
    f = fam()
    h = hyp(f, "tsmom", grid={"lookback": [20, 60]})
    a = [x.spec_hash for x in CP.iter_executables(f, h, "c" * 40)]
    assert a == [x.spec_hash for x in CP.iter_executables(f, h, "c" * 40)] and len(a) == 2
    for bad, msg in [
        (dict(signal={"kind": "magic"}), "kind"),
        (dict(frequency="H"), "frequency"),
        (dict(primary_binding={"universe_id": "U_X", "cost_model_id": "C0", "sizing_id": "EW"}), "universe"),
        (dict(primary_binding={"universe_id": "U_SYN6", "cost_model_id": "C9", "sizing_id": "EW"}), "cost_model"),
        (dict(primary_binding={"universe_id": "U_SYN6", "cost_model_id": "C0", "sizing_id": "KELLY"}), "sizing"),
        (dict(grid={"lookback": [2, 600]}), "lookback"),
        (dict(grid={"lookback": [20], "colour": [1]}), "no parameter"),
        (dict(frequency="event"), "event"),
        (dict(primary_binding={"universe_id": "U_FX_H10", "cost_model_id": "C0", "sizing_id": "EW"}), "domain"),
    ]:
        assert any(msg in e for e in CP.check_hypothesis({**h, **bad})), bad
    with pytest.raises(CP.CompileError):
        next(CP.iter_executables(fam("-"), h, "c" * 40))                   # wrong family


def test_interfaces_stream():
    f = fam()
    h = hyp(f, "tsmom", grid={"lookback": list(range(5, 205))})
    it = CP.iter_executables(f, h, "c" * 40)
    assert inspect.isgenerator(it) and CP.variant_count(h) == 200
    assert next(it).params == {"lookback": 5}


# ---- O-23 to O-25: justification, budget, report

def test_unjustified_dimensions_are_found():
    f = fam()
    g = {"lookback": [20, 60]}
    assert J.check_justification(hyp(f, "tsmom", grid=g)) == []
    probs = lambda just: [x["problem"] for x in J.check_justification(hyp(f, "tsmom", grid=g, just=just))]
    assert "no justification" in probs({})[0]
    assert "generic" in probs({"lookback": {"reason": "for robustness" + " " * 40, "mechanism_range": [20, 60]}})[0]
    assert "shorter" in probs({"lookback": {"reason": "carry", "mechanism_range": [20, 60]}})[0]
    assert "outside" in probs({"lookback": {"reason": REASON, "mechanism_range": [20, 40]}})[0]
    assert "mechanism_range" in probs({"lookback": {"reason": REASON}})[0]
    assert probs({"lookback": {"reason": REASON, "mechanism_values": [20, 60]}}) == []
    assert J.check_justification(hyp(f, "tsmom", grid={"lookback": [20]}, just={})) == []   # not varied


def test_budget_and_report():
    f = fam()
    big = hyp(f, "tsmom", grid={"lookback": list(range(5, 25))})                            # 20 > 16
    assert J.budget_finding(big)["justified"] is False
    ok = hyp(f, "tsmom", grid={"lookback": list(range(5, 25))},
             budget_justification="the hedging window of the counterparty is not known to within twenty days")
    assert J.budget_finding(ok)["justified"] is True
    r = J.grid_report(big)
    assert r["raw_variants"] == 20 and r["effective_variants"] == 20 and r["effective_basis"] == "raw_count_no_data"
    rng = np.random.default_rng(0)
    base = rng.normal(size=(500, 1))
    corr = np.hstack([base + 0.01 * rng.normal(size=(500, 1)) for _ in range(20)])
    m = J.effective_count(corr, 20)
    assert 1 <= m < 3
    p1, p20 = J.power_loss(1.0), J.power_loss(20.0)
    assert p1["power_loss"] == 0 and p20["power_loss"] > 0 and p20["critical_search"] > p1["critical_single"]
    assert "approximation" in p20["method"]


# ---- mechanical critic and freeze tooling

def test_critic_blocks_and_sees_specs_only():
    f = fam()
    bad = hyp(f, "tsmom", grid={"lookback": list(range(5, 25))}, just={})
    rev = CR.review([f], [bad])[0]
    reasons = {b["reason"] for b in rev["blocks"]}
    assert {"unjustified_dimension", "budget_exceeded_without_justification"} <= reasons and rev["block"]
    no_timing = {**hyp(f, "tsmom", grid={"lookback": [20]}), "timing": {}}
    assert "missing_timing" in {b["reason"] for b in CR.review([f], [no_timing])[0]["blocks"]}
    with pytest.raises(C.CriticError, match="outcome"):
        CR.review([f], [{**hyp(f, "tsmom", grid={"lookback": [20]}), "sharpe": 1.2}])


def test_freeze_tooling_prepares_and_refuses(tmp_path):
    req = mockgen.blind_request(n_families=3, max_hypotheses=2, domains=("syn_daily",))
    fams, hyps = parse_reply(mockgen.mock_reply(req, n=3), "blind")
    out = FP.prepare(7, fams, hyps, out_root=tmp_path, code_version="c" * 40,
                     protocol_path=ROOT / "docs/manhattan/PROTOCOL_v3.md", generator_model="mock",
                     template_hash=req.template_hash, fence={})
    d = Path(out["dir"])
    assert d.name == "AB-0007" and (d / "manifest.json").exists() and (d / "ops_manifest.json").exists()
    m = json.loads((d / "manifest.json").read_text())
    assert S.canonical_bytes(m) == (d / "manifest.json").read_bytes() and m["counts"]["families"] == 3
    assert out["executables"] == m["counts"]["variants"] == sum(CP.variant_count(h) for h in hyps)
    body = (d / "PR_BODY.md").read_text()
    assert "does not certify timing" in body and out["manifest_hash"] in body
    assert subprocess.run(["git", "rev-parse"], cwd=tmp_path, capture_output=True).returncode != 0   # nothing committed
    bad = [{**hyps[0], "grid_justification": {}}] + hyps[1:]
    bad[0] = {**bad[0], "grid": {"lookback": [20, 60, 120]}}
    with pytest.raises(FP.FreezePRError, match="unjustified_dimension"):
        FP.prepare(8, fams, bad, out_root=tmp_path, code_version="c" * 40,
                   protocol_path=ROOT / "docs/manhattan/PROTOCOL_v3.md", generator_model="mock",
                   template_hash=req.template_hash, fence={})


def test_template_v2_is_hash_checked_and_takes_no_results():
    text, h = mockgen.template_text()
    assert "grid_justification" in text and "timing" in text
    sig = inspect.signature(mockgen.blind_request)
    assert list(sig.parameters) == ["n_families", "max_hypotheses", "domains"]
