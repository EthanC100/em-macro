"""The Manhattan operations app (v1) on its synthetic demo: sections, outcome blinding, counting levels, labels.

One demo is built through the command line (a subprocess; no network, a local bare repository as the ledger); its
ledger is then read back to seed the leak scanner with every performance value it holds. Synthetic data only.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from manhattan import spec as S
from manhattan.app import __main__ as CLI
from manhattan.app import model as M
from manhattan.app import render
from manhattan.ops import leakscan as LS
from manhattan.ops import promotion
from manhattan.ops import runner as R
from manhattan.ops import store as ST

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    base = tmp_path_factory.mktemp("app")
    out, wd = base / "out", base / "work"
    p = subprocess.run([sys.executable, "-m", "manhattan.app", "demo", "--out", str(out), "--workdir", str(wd)],
                       cwd=ROOT, capture_output=True, text=True, timeout=240)
    store = ST.Store(workdir=base / "read", remote=str(wd / "manhattan-ledger.git")).open() if p.returncode == 0 \
        else None
    return {"proc": p, "out": out, "work": wd, "base": base, "store": store,
            "batches": wd / "public/data/manhattan/batches",
            "html": (out / "index.html").read_text() if p.returncode == 0 else "",
            "json_text": (out / "view.json").read_text() if p.returncode == 0 else ""}


@pytest.fixture(scope="module")
def view(demo):
    return json.loads(demo["json_text"])


def families(view):
    return [f for b in view["batches"] for f in b["families"]]


def test_cli_demo_exits_zero_and_writes_both_files(demo):
    p = demo["proc"]
    assert p.returncode == 0, p.stderr[-2000:]
    assert (demo["out"] / "index.html").is_file() and (demo["out"] / "view.json").is_file()
    assert "SYNTHETIC DEMO" in p.stdout
    # the demo's ledger is the local bare repository inside its work directory, never a real ledger
    assert (demo["work"] / "manhattan-ledger.git").is_dir()


def test_required_sections_are_present(demo, view):
    h = demo["html"]
    assert h.startswith("<!doctype html>") and "<script" not in h and "http://" not in h and "https://" not in h
    assert h.count("SYNTHETIC DEMO") >= 1 and view["synthetic"] is True
    assert "prefers-color-scheme:dark" in h and 'name="viewport"' in h
    for s in ("Operations overview", "Counts (each level counted separately)", "Runner status", "Evidence status",
              'id="families"'):
        assert s in h, s
    fams = families(view)
    assert len(fams) == 10
    for f in fams:
        assert f'href="#{f["anchor"]}"' in h and f'id="{f["anchor"]}"' in h
    for s in ("Explanation (verbatim from the frozen family spec)", "Hypotheses", "Executable variants",
              "Freeze version", "Data provenance", "Evidence label",
              "Registration, attempts and coverage per prediction"):
        assert h.count(s) == 10, s
    for key in ("explanation", "hypotheses", "variants", "freeze", "provenance", "registration", "evidence_labels",
                "attempts", "coverage", "predictions", "channel"):
        assert all(key in f for f in fams), key


def test_explanations_are_verbatim_from_the_frozen_specs(demo, view):
    specs = {S.spec_id(sp): sp for sp in (S.read(p) for p in (demo["batches"] / "AB-0001/specs").glob("AF-*.json"))}
    for f in families(view):
        sp = specs[f["id"]]
        x = f["explanation"]
        for k in ("mechanism", "mechanism_class", "counterparty", "kill_condition", "tail_exposure"):
            assert x[k] == sp[k]
        assert x["predicted_sign"] == sp["sign"]
        assert f["channel"] == "blind"
        fr = f["freeze"]
        assert fr["batch_id"] == "AB-0001" and re.fullmatch(r"[0-9a-f]{64}", fr["manifest_hash"])
        assert fr["merkle_root"] and fr["template_hash"] and fr["protocol_hash"] and fr["code_versions"] == ["c" * 40]


# ---- the hard blinding rule

def outcome_needles(store):
    return LS.Needles(LS.performance_values([r for r in store.records if r["type"] in ("observation", "screening")]))


def test_no_outcome_reaches_the_page_or_the_export(demo, view):
    n = outcome_needles(demo["store"])
    assert len(n) > 300                                       # the ledger really holds outcomes
    assert LS.scan_text(demo["html"], n, "html") == []
    assert LS.scan_text(demo["json_text"], n, "json") == []
    assert LS.scan_tree(demo["out"], n, "out") == []
    M.assert_no_outcomes(view)

    floats = []

    def walk(x):
        if isinstance(x, float):
            floats.append(x)
        elif isinstance(x, dict):
            [walk(v) for v in x.values()]
        elif isinstance(x, list):
            [walk(v) for v in x]
    walk(view)
    assert floats == []
    keys = set()

    def keys_of(x):
        if isinstance(x, dict):
            keys.update(x)
            [keys_of(v) for v in x.values()]
        elif isinstance(x, list):
            [keys_of(v) for v in x]
    keys_of(view)
    assert not {k for k in keys if M._key_denied(k)}
    assert not keys & {"net", "gross", "sharpe", "turnover", "exposure", "summary", "result_hash", "rank"}


def test_the_scanner_would_catch_a_leak_on_the_page(demo, view):
    vals = LS.performance_values(demo["store"].of_type("observation"))
    leak = next(x for x in vals if 1e-3 < abs(x) < 1 and len(repr(abs(x))[2:].lstrip("0")) >= 8)
    bad = json.loads(json.dumps(view))
    families(bad)[0]["explanation"]["mechanism"] += f" (net {leak!r})"   # free text: only the scanner sees it
    assert LS.scan_text(render.page(bad), outcome_needles(demo["store"]), "html")


def test_assert_no_outcomes_refuses_outcome_keys_and_floats():
    for bad in ({"net": "x"}, {"a": {"gross_exposure": 1}}, {"sharpe": None}, {"turnover_annual": 3},
                {"a": [{"exposure": []}]}, {"rank": 1}, {"family_score": 2}, {"summary": {}},
                {"a": 0.5}, {"a": "0.0123456"}, {"a": ["1e-3"]}, {"grid": {"x": [0.5]}}, {"hit_rate": 1}):
        with pytest.raises(M.OutcomeLeak):
            M.assert_no_outcomes(bad)
    M.assert_no_outcomes({"tail_exposure": "text", "grid": {"x": ["0.01", 2]}, "point": {"t": "0.005"},
                          "mechanism_range": ["0.5", 1], "counts": {"families": 3}, "outcomes_included": False})


def test_projection_is_an_allow_list_and_fails_closed(demo):
    obs = demo["store"].of_type("observation")[0]
    p = M.project(obs)
    assert set(p) <= set(M.RECORD_FIELDS) | set(M.ALLOWED["observation"])
    assert not {"net", "gross", "cost", "exposure", "turnover"} & set(p)
    scr = M.project(demo["store"].of_type("screening")[0])
    assert "summary" not in scr and "result_hash" not in scr
    forged = {**obs, "payload": {**obs["payload"], "date": 0.0123}}
    with pytest.raises(M.OutcomeLeak):
        M.project(forged)
    forged = {**obs, "payload": {**obs["payload"], "reconstructed": "0.004572982079"}}
    with pytest.raises(M.OutcomeLeak):
        M.project(forged)


# ---- counting levels

def test_counting_levels_are_separate_and_match_the_ledger(demo, view):
    st = demo["store"]
    manifest, specs = R.load_batch(demo["batches"], 1)
    c = view["counts"]
    levels = {lvl: sum(1 for sp in specs.values() if sp["level"] == lvl) for lvl in ("family", "hypothesis",
                                                                                       "variant", "executable")}
    regs = R.registrations(st)
    started = st.of_type("attempt_started")
    assert c["families"] == levels["family"] == 10
    assert c["hypotheses"] == levels["hypothesis"] == 14
    assert c["variants"] == levels["variant"] == 27
    assert c["unique_executable_configurations"] == len({p["spec_hash"] for p in regs.values()}) == 27
    assert c["registered_predictions"] == len(regs) == 27
    assert c["attempts_total"] == len(started) == 81
    k = c["attempts_by_kind"]
    assert k["forward_observation"]["registered"] == sum(1 for s in started
                                                         if s["payload"]["kind"] == "forward_observation") == 54
    assert k["screening"]["registered"] == 27 and k["screening"]["completed"] == 27
    assert sum(x["unfinished"] + x["failed"] + x["aborted"] for x in k.values()) == 0
    assert c["observation_records"] == len(st.of_type("observation"))
    assert c["predictions_ineligible"] == sum(1 for p in regs.values() if not p["eligible"]) == 4
    fams = families(view)
    assert sum(f["counts"]["hypotheses"] for f in fams) == c["hypotheses"]
    assert sum(f["counts"]["variants"] for f in fams) == c["variants"]
    assert sum(f["attempts"]["forward_observation"]["registered"] for f in fams) == 54
    # coverage: counts only, and they add up
    obs_by_pred = {}
    for o in st.of_type("observation"):
        obs_by_pred[o["payload"]["prediction"]] = obs_by_pred.get(o["payload"]["prediction"], 0) + 1
    for f in fams:
        for p in f["predictions"]:
            cov = p["coverage"]
            assert cov["recorded_days"] == obs_by_pred.get(p["prediction"], 0)
            assert cov["expected_days"] == cov["recorded_days"] + cov["missed_observation_days"] + cov["pending_days"]
            late = not p["registration"]["eligible"]
            assert cov["expected_days"] == (3 if late else 2)       # 13 (late only), 16 and 17 November
            assert p["attempts"]["forward_observation"]["completed"] == 2
    assert sum(f["coverage"]["recorded_days"] for f in fams) == len(st.of_type("observation"))
    assert sum(f["coverage"]["reconstructed_days"] for f in fams) == sum(
        1 for o in st.of_type("observation") if o["payload"]["reconstructed"])


def test_runner_status(view):
    r = view["runner"]
    assert r["last_heartbeat"] == "2026-11-17" and r["missed_runs"] == ["2026-11-13"]
    assert r["active_locks"] == 0 and r["journal"]["unfinished_entries"] == 0 and r["chain_ok"] is True
    assert r["last_lock"]["run_id"] == r["last_unlock"]["run_id"] == "104"


# ---- evidence labels

def test_evidence_label_is_not_eligible_while_gates_are_closed(view):
    assert view["evidence"]["label"] == M.NOT_ELIGIBLE_GATES == "not eligible: activation gates closed"
    assert view["evidence"]["eligible_for_evidence"] is False
    assert view["evidence"]["promotion"] == promotion.status(None, None)[1]
    assert {g["id"] for g in view["evidence"]["gates"]} == {f"G-{i}" for i in range(1, 7)} | {"B-1", "B-2", "B-3"}
    for f in families(view):
        assert f["evidence_labels"] == [M.NOT_ELIGIBLE_GATES]
        assert all(p["evidence"]["eligible_for_evidence"] is False for p in f["predictions"])
    # claims switched on in config alone changes nothing: no protocol is adopted
    assert M.evidence_label("a" * 64, {"claims": {"enabled": True}})["label"] == M.NOT_ELIGIBLE_GATES


def test_evidence_label_when_promotion_is_switched_on(monkeypatch):
    h = "b" * 64
    monkeypatch.setattr(promotion, "ADOPTED_PROTOCOLS", frozenset({h}))
    on = {"claims": {"enabled": True}}
    assert M.evidence_label(h, {"claims": {"enabled": False}})["label"] == M.NOT_ELIGIBLE_GATES
    late = M.evidence_label(h, on, {"eligible": False, "ineligible_reasons": ["window_begun_at_registration"]})
    assert late["label"] == "not eligible: window_begun_at_registration"
    ok = M.evidence_label(h, on, {"eligible": True})
    assert ok["label"] == "eligibility: none (unverified)" and ok["eligible_for_evidence"] is False


# ---- other inputs

def test_build_from_a_clone_and_from_batches_only(demo, view, tmp_path):
    res = CLI.build(demo["batches"], tmp_path / "a", ledger_clone=demo["store"].workdir,
                    generated_utc=view["generated_utc"])
    assert res["view"] == view                                  # a clone read from disk gives the same view
    bare = CLI.build(demo["batches"], tmp_path / "b", generated_utc="2026-11-18T00:00:00Z")["view"]
    assert bare["runner"] is None and bare["ledger_connected"] is False
    assert bare["counts"]["families"] == 10 and bare["counts"]["registered_predictions"] == 0
    assert "No private ledger connected" in (tmp_path / "b/index.html").read_text()
