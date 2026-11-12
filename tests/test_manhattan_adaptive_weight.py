"""The rule that adaptive-channel families carry zero evidential weight on the reserve, enforced in code.

Protocol v3.1 sections 5.3 and 7.3; ARCHITECTURE section 6.3; SIM_PREREG_v2 criterion V14. The evidence for the
rule is pilot scenario D09b (after adaptive search on the reserve the SPA test on the full set rejects about
seven times as often as its level says); a test here checks that the protocol quotes the number on file.

What "enforced" means: the weight is computed from the channel by one function, the model takes a channel and
not a weight, and no reserve number of an adaptive-channel family can change any output of the model, to the
last bit.
"""
from __future__ import annotations

import dataclasses
import json
import re
from pathlib import Path

import numpy as np
import pytest

from manhattan import ledger
from manhattan.stats import hier_analytic as ha
from manhattan.testing import reads_hand_edited_file

ROOT = Path(__file__).resolve().parents[1]
ADAPTIVE = (3, 17, 30)


def data(y_H=None, s_H=None, channel=None, designated=None, y_F=None) -> ha.Data:
    rng = np.random.default_rng(7)
    n = 40
    a = np.where(np.arange(n) < 6, 0.9, 0.0)
    ch = np.array(["adaptive" if i in ADAPTIVE else "blind" for i in range(n)])
    base_yH = a + 0.3 * rng.standard_normal(n)
    base_yF = a + 0.4 * rng.standard_normal(n)
    base_yF[35:] = np.nan                                             # five families have no forward record yet
    return ha.Data(y_H=base_yH if y_H is None else y_H, s_H=np.full(n, 0.3) if s_H is None else s_H,
                   y_F=base_yF if y_F is None else y_F, s_F=np.full(n, 0.4), mech=np.arange(n) % 3,
                   age=np.where(np.isnan(base_yF), 0.0, 3.0), channel=ch if channel is None else channel,
                   designated=designated, r_F=0.05)


def same(a: list[ha.Fit], b: list[ha.Fit]) -> bool:
    return all(np.array_equal(x.pi, y.pi) and np.array_equal(x.mean, y.mean) and np.array_equal(x.sd, y.sd)
               and np.array_equal(x.conflict, y.conflict) and np.array_equal(x.draws, y.draws)
               and x.hyper == y.hyper and x.log_evidence == y.log_evidence and x.edge_mass == y.edge_mass
               for x, y in zip(a, b))


# ------------------------------------------------------------------ the rule, in one place

def test_the_rule_adaptive_reserve_results_have_weight_zero():
    for designated in (True, False):
        assert ledger.evidential_weight("adaptive", "reserve", designated) == 0
    assert ledger.evidential_weight("blind", "reserve", designated=True) == 1
    assert ledger.evidential_weight("blind", "reserve", designated=False) == 0
    assert ledger.evidential_weight("adaptive", "forward") == 1         # the forward record of any family counts
    assert ledger.evidential_weight("adaptive", "exploration") == 0


def test_the_model_takes_a_channel_and_computes_the_weight_from_the_ledgers_rule(monkeypatch):
    d = data()
    assert [f.name for f in dataclasses.fields(ha.Data) if "weight" in f.name] == []      # no weight can be passed in
    with pytest.raises(AttributeError):
        d.reserve_weight = np.ones(d.n_f, dtype=bool)                                    # nor set afterwards
    w = d.reserve_weight
    assert not w[list(ADAPTIVE)].any() and w.sum() == d.n_f - len(ADAPTIVE)
    calls = []
    monkeypatch.setattr(ha, "evidential_weight", lambda *a: calls.append(a) or ledger.evidential_weight(*a))
    d.reserve_weight
    assert len(calls) == d.n_f and all(role == "reserve" for _, role, _ in calls)
    assert {c for c, _, _ in calls} == {"blind", "adaptive"}


def test_a_non_designated_reserve_evaluation_has_weight_zero_too():
    des = np.ones(40, dtype=bool)
    des[5] = False
    d = data(designated=des)
    assert not d.reserve_weight[5] and d.reserve_weight[4]


# ------------------------------------------------------------------ V14: nothing an adaptive family shows on the reserve can matter

def test_no_reserve_number_of_an_adaptive_family_changes_any_output():
    """SIM_PREREG_v2 criterion V14: all six models, every family, every hyperparameter and every draw."""
    base = ha.fit_many(data(), draws=50, seed=1)
    d0 = data()
    for y, s in ((5.0, 0.01), (-40.0, 3.0), (np.nan, np.nan), (np.inf, 0.0)):
        y_H, s_H = d0.y_H.copy(), d0.s_H.copy()
        y_H[list(ADAPTIVE)], s_H[list(ADAPTIVE)] = y, s
        assert same(base, ha.fit_many(data(y_H=y_H, s_H=s_H), draws=50, seed=1)), (y, s)
    # the check has teeth: the same change to a blind, designated family does move the numbers
    y_H = d0.y_H.copy()
    y_H[4] = 5.0
    moved = ha.fit_many(data(y_H=y_H), draws=50, seed=1)
    assert not same(base, moved) and abs(moved[0].mean[4] - base[0].mean[4]) > 0.5
    assert not np.array_equal(moved[0].pi[ADAPTIVE[0]], base[0].pi[ADAPTIVE[0]])      # and it moves the others through the group


def test_an_adaptive_family_is_a_family_with_no_reserve_term():
    """The same numbers as a blind family whose reserve evaluation is not the designated one, and not the numbers
    of a blind family whose reserve estimate counts."""
    base = ha.fit_many(data(), draws=0)
    des = np.ones(40, dtype=bool)
    des[list(ADAPTIVE)] = False
    as_undesignated = ha.fit_many(data(channel=np.full(40, "blind"), designated=des), draws=0)
    assert all(np.array_equal(x.pi, y.pi) and x.hyper == y.hyper for x, y in zip(base, as_undesignated))
    as_blind = ha.fit_many(data(channel=np.full(40, "blind")), draws=0)
    assert not np.array_equal(base[0].pi, as_blind[0].pi)
    # with no reserve term and no forward record, an adaptive family is exactly at its prior given the group
    lone = data()
    k = ADAPTIVE[0]
    y_F = lone.y_F.copy()
    y_F[k] = np.nan
    fit = ha.fit(data(y_F=y_F))
    blind_no_data = [i for i in range(35, 40)][0]
    assert fit.sd[k] > fit.sd[blind_no_data]                           # it knows less than a blind family with a reserve result


def test_the_forward_record_of_an_adaptive_family_counts_in_full():
    k = ADAPTIVE[1]
    d0 = data()
    y_F = d0.y_F.copy()
    y_F[k] = 2.0
    up = ha.fit(data(y_F=y_F))
    y_F[k] = -1.0
    down = ha.fit(data(y_F=y_F))
    assert up.pi[k] > 0.8 > 0.1 > down.pi[k]


# ------------------------------------------------------------------ the evidence the protocol cites

@reads_hand_edited_file
def test_the_protocol_cites_the_d09b_number_that_is_on_file():
    summary = json.loads((ROOT / "results/manhattan_sim/summary.json").read_text(encoding="utf-8"))
    row = next(r for r in summary["runs"]["D09b_STD"]["rows"] if r["metric"] == "M11")
    assert row["n"] == 12 and row["estimate"] > 6 * 0.05                 # the pilot: far above the 0.05 level
    for name in ("docs/manhattan/PROTOCOL_v3.1.md", "docs/manhattan/SIM_PREREG_v2.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        cited = re.findall(r"D09b\*{0,2}[^|]{0,400}?(0\.\d{3}) \((0\.\d{3}) to (0\.\d{3})\)", text, flags=re.S)
        assert cited, name
        for est, lo, hi in cited:
            assert float(est) == pytest.approx(row["estimate"], abs=6e-4), name
            assert float(lo) == pytest.approx(row["lo"], abs=6e-4) and float(hi) == pytest.approx(row["hi"], abs=6e-4), name
    protocol = (ROOT / "docs/manhattan/PROTOCOL_v3.1.md").read_text(encoding="utf-8")
    rule = protocol[protocol.index("**The rule, and its evidence.**"):protocol.index("### 5.4")]
    for needle in ("zero\nevidential weight on the reserve", "D09b", "manhattan.ledger.evidential_weight",
                   "tests/test_manhattan_adaptive_weight.py"):
        assert needle in rule, needle
