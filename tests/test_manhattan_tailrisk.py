"""The tail-risk check of Protocol v3.1 section 6.11 (``manhattan/stats/tailrisk.py``): the formula on hand-made
records, its agreement with the study it came from, where the protocol requires it, and the one thing it may
never do: change an e-LOND decision or count (SIM_PREREG_v2 criterion V15). Synthetic numbers only.
"""
from __future__ import annotations

import inspect
from pathlib import Path

import numpy as np
import pytest

from manhattan.sim import estimand_study as es
from manhattan.sim import run
from manhattan.stats import elond, eprocess, tailrisk
from manhattan.testing import reads_hand_edited_file

ROOT = Path(__file__).resolve().parents[1]


def test_the_constants_are_95_percent_and_a_floor_of_12():
    assert tailrisk.LEVEL == 0.95 and tailrisk.STRESS_FLOOR == 12.0 == 2 * eprocess.C_WEEKLY
    # the rule of three, and its next two values
    assert tailrisk.poisson_upper([0, 1, 2]) == pytest.approx([2.9957, 4.7439, 6.2958], abs=1e-4)
    assert float(tailrisk.poisson_upper(0)) == pytest.approx(-np.log(0.05))
    assert tailrisk.poisson_upper(3, level=0.90) < tailrisk.poisson_upper(3)


def test_the_stress_loss_is_the_largest_of_declared_worst_and_floor():
    assert tailrisk.stress_loss(None, 0.0) == 12.0                      # nothing declared, nothing seen: the floor
    assert tailrisk.stress_loss(8.0, 3.0) == 12.0                       # a declaration below the floor does not lower it
    assert tailrisk.stress_loss(30.0, 3.0) == 30.0                      # the declaration
    assert tailrisk.stress_loss(30.0, 41.0) == 41.0                     # a week on record worse than the declaration
    assert tailrisk.stress_loss(None, 14.5) == 14.5
    with pytest.raises(ValueError):
        tailrisk.stress_loss(-1.0, 0.0)


def test_the_check_on_hand_made_records():
    Z = np.full(100, 0.5)
    # no truncated week, the floor of 12: the capped record must have earned 3.00 x (12 - 6) = 17.97 in total
    ok = tailrisk.check(Z)
    assert ok.passed and ok.reason == "" and ok.n_trunc == 0 and ok.n_weeks == 100
    assert ok.truncated_gain == ok.untruncated_gain == 50.0 and ok.stress_loss == 12.0
    assert ok.upper_count == pytest.approx(2.9957, abs=1e-4) and ok.charge == pytest.approx(17.974, abs=1e-3)
    assert ok.margin == pytest.approx(50.0 - 17.974, abs=1e-3)
    short = tailrisk.check(Z[:35])                                      # 17.5 < 17.97: not yet
    assert not short.passed and "does not cover" in short.reason and short.margin < 0 < short.untruncated_gain
    assert tailrisk.check(Z[:36]).passed                                # 18.0 > 17.97
    # a declared stress loss of 30: 3.00 x 24 = 71.9 to cover, and 50 does not
    declared = tailrisk.check(Z, declared_stress=30.0)
    assert not declared.passed and declared.stress_loss == 30.0 and declared.charge == pytest.approx(71.90, abs=0.01)
    assert tailrisk.check(np.full(150, 0.5), declared_stress=30.0).passed            # 75 > 71.9
    # one week 40 standard deviations down: the record itself now sets the stress loss, and one event is on file
    crash = Z.copy()
    crash[10] = -40.0
    c = tailrisk.check(crash)
    assert c.n_trunc == 1 and c.stress_loss == 40.0 and c.truncated_gain == pytest.approx(43.5)
    assert c.untruncated_gain == pytest.approx(9.5) and c.upper_count == pytest.approx(4.7439, abs=1e-4)
    assert c.charge == pytest.approx(4.7439 * 34, abs=1e-2) and not c.passed       # 161 to pay for
    # the worst week of the family's whole record counts even when it is before enrolment
    assert not tailrisk.check(Z, worst_week=40.0).passed and tailrisk.check(Z, worst_week=11.0).passed
    # a record whose capped total is positive and whose uncapped total is not never passes
    two = np.full(400, 0.5)
    two[[3, 200]] = -120.0
    t = tailrisk.check(two, declared_stress=0.0)
    assert t.truncated_gain > 0 > t.untruncated_gain and not t.passed and "untruncated record is not positive" in t.reason
    assert not tailrisk.check(-Z).passed and not tailrisk.check(np.array([])).passed
    with pytest.raises(ValueError, match="missing week"):
        tailrisk.check(np.array([0.5, np.nan]))


def test_it_is_the_formula_of_the_estimand_study():
    """Section 3 of ESTIMAND_AND_TAIL_RISK.md, record for record, for stress losses at or above the floor."""
    rng = np.random.default_rng(611)
    Z = rng.uniform(-0.1, 0.6, size=(400, 1)) + rng.standard_normal((400, 520))     # ten years of weeks, edges from none to large
    Z[rng.random(Z.shape) < 0.002] -= 25.0                                           # about one crash a record
    Y = np.maximum(Z, -es.C)
    for L in (12.0, 17.9, 44.7):
        want = es.tail_check(Z, Y, L)
        got = tailrisk.passes(Z, L)
        assert np.array_equal(got, want) and 0 < want.sum() < want.size
        assert [tailrisk.check(z, declared_stress=L).passed for z in Z[:60]] == want[:60].tolist()
    assert es.DEFAULT_STRESS == tailrisk.STRESS_FLOOR and es.C == eprocess.C_WEEKLY
    assert np.array_equal(tailrisk.passes(Z, 3.0), es.tail_check(Z, Y, 12.0))        # below the floor: the floor
    assert np.allclose(tailrisk.poisson_upper([0, 4]), es.poisson_upper(np.array([0, 4])))


def test_a_rejection_is_recorded_and_counted_whatever_the_check_says():
    """V15: only the label is withheld. The e-LOND rule is run once; the check comes after it, takes the
    rejection as a fact and has no way back into the rule."""
    n_per = 40
    wealth = np.ones((3, n_per))
    wealth[0, 10:] = 1e6                                               # family 0 is rejected at period 10 ...
    wealth[1, 20:] = 1500.0                                            # ... which lowers family 1's bar (2,138, then 1,069) enough for it
    res = elond.run(wealth, np.ones((3, n_per), dtype=bool), np.zeros(3, dtype=int), N_F=300)
    assert res["reject_at"].tolist() == [10, 20, -1] and res["R"][-1] == 2
    alone = elond.run(wealth[1:], np.ones((2, n_per), dtype=bool), np.zeros(2, dtype=int), N_F=300,
                      gammas=res["gamma"][1:])
    assert alone["reject_at"].tolist() == [-1, -1]                     # family 1 needed family 0's rejection to be counted
    failing = tailrisk.check(np.full(20, 0.5))                         # 10 < 17.97
    passing = tailrisk.check(np.full(100, 0.5))
    assert not failing.passed and passing.passed
    # the label of family 0 depends on the check; nothing else does
    assert tailrisk.formal_label(True, failing) == tailrisk.WITHHELD and "withheld" in tailrisk.WITHHELD
    assert tailrisk.formal_label(True, None) == tailrisk.WITHHELD
    assert tailrisk.formal_label(True, passing) == tailrisk.FORMAL == "Formally supported by forward-only evidence"
    assert tailrisk.formal_label(False, passing) == ""                 # the check alone gives no label
    assert tailrisk.may_claim_profit(passing) and not tailrisk.may_claim_profit(failing) and not tailrisk.may_claim_profit(None)
    # by construction: the check does not import the e-LOND rule, and the rule takes no input from the check
    src = inspect.getsource(tailrisk)
    assert "import elond" not in src and "from .elond" not in src and "from . import" not in src
    assert set(inspect.signature(elond.run).parameters) == {"wealth", "guard", "start", "N_F", "alpha", "gammas"}
    assert "tail" not in inspect.getsource(elond).replace("detail", "")
    # and no run of record computes it: the simulation's counts of rejections cannot depend on it
    lists = run.CODE_FILES + run.CODE_FILES_HB + run.CODE_FILES_V2 + run.CODE_FILES_V2_HB
    assert "manhattan/stats/tailrisk.py" not in lists and "manhattan/stats/elond.py" in run.CODE_FILES


@reads_hand_edited_file
def test_the_protocol_states_the_check_and_where_it_is_required():
    text = (ROOT / "docs/manhattan/PROTOCOL_v3.1.md").read_text(encoding="utf-8")
    sec = text[text.index("### 6.11 The tail-risk check"):text.index("## 7. One hierarchical model")]
    for needle in ("Σ_{u≤t} Y_u − U( N_trunc ) · ( L − c )  >  0", "Σ_{u≤t} Z_u  >  0", "3.00", "4.74", "6.30",
                   "a floor of 12", "95%", "**An e-LOND rejection is still recorded and counted.**", "only the label is withheld",
                   "sections 8.3, 8.4 and 8.5", "ESTIMAND_AND_TAIL_RISK.md"):
        assert needle in sec, needle
    tiers = text[text.index("### 8.3 Live-experiment eligible"):text.index("## 9. Dormancy")]
    assert tiers.count("tail-risk check of section 6.11") >= 3          # 8.3, 8.4 and 8.5 each name it
    assert "label withheld" in tiers[tiers.index("### 8.5 Formally supported"):]
    top = text[: text.index("## 1. Symbols")]
    assert "| 6 | §6.11" in top and "ETHAN_ACTIONS item 23" in top
    assert "| tail-risk check | 95%; floor 12" in text                  # Appendix B
    prereg = (ROOT / "docs/manhattan/SIM_PREREG_v2.md").read_text(encoding="utf-8")
    assert "| V15 |" in prereg and "§6.11" in prereg
