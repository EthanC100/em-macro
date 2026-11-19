"""Manhattan HTE funnel: attempt accounting, determinism, crash recovery, failures, caching, repeated runs,
selection audit, packaging, and the scientific safeguards (adversarial tests). Synthetic data only."""
from __future__ import annotations

import hashlib
import inspect
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from manhattan.hte import CONFIRMATORY, adapters, data as D, fixtures as X, ids, kernels
from manhattan.hte import protected, registry as R, store
from manhattan.hte import runner as RN
from manhattan.hte import templates as TP
from manhattan.hte.log import AttemptLog
from manhattan.hte.policy import Policy
from manhattan.hte.runner import Runner, Workspace, reconcile, history

ROOT = Path(__file__).resolve().parents[1]


# -- a test-only template whose candidates fail on purpose ---------------------------------------------------

def _poison(cache, dom, p):
    if p["boom"] == 7:
        raise ValueError("injected candidate failure")
    s = np.nan_to_num(np.sign(cache.get(dom, "mom", L=p["lookback"])), nan=0.0)
    if p["boom"] == 3:
        s = s * np.inf                                   # non-finite statistics
    return s


TP.TEMPLATES.setdefault("poison_test", TP.Template(
    "poison_test", 1, {"name": "test-poison", "mechanism": "TEST ONLY", "sign": "+", "density": "dense"},
    {"lookback": ("int", 5, 60), "boom": ("int", 0, 10)}, lambda p: p["lookback"], _poison,
    lambda p: [("mom", {"L": p["lookback"]})], test_only=True))


@pytest.fixture(scope="module")
def panel():
    return D.generate(X.SMALL_PANEL)


def _ws(path, bundles=None) -> Workspace:
    ws = Workspace(path)
    reg = ws.registry()
    if len(reg) == 0:
        b = bundles if bundles is not None else X.small_bundles()
        test = any(TP.TEMPLATES[x.spec["template"]].test_only for x in b)
        reg.submit(b, allow_test_templates=test)
        reg.freeze()
    return ws


def _run(path, panel, policy=Policy(), bundles=None, **kw):
    ws = _ws(path, bundles)
    return ws, Runner(ws, panel, policy, **kw).run()


@pytest.fixture(scope="module")
def baseline(tmp_path_factory, panel):
    ws, out = _run(tmp_path_factory.mktemp("base"), panel, chunk_size=32)
    return ws, out


def _types(ws):
    return [r["type"] for r in AttemptLog(ws.log_path).records()]


# -- end-to-end accounting -------------------------------------------------------------------------------------

def test_every_registered_candidate_has_a_terminal_status(baseline):
    ws, out = baseline
    assert out["reused"] is False and out["confirmatory"] is False
    rec = reconcile(ws, out["run_id"])
    assert rec["violations"] == [] and rec["registered"]["candidates"] == 120
    fs = rec["final_status"]
    assert fs["s1"]["not_run"] == 0 and sum(fs["s1"].values()) == 120
    assert fs["s3"]["not_run"] == 0 and sum(fs["s3"].values()) == 120
    a = rec["attempts"]
    assert a["started"] == a["completed"] and a["unfinished"] == a["failed"] == a["interrupted"] == 0
    assert rec["access_reconciled"] is False and rec["independent_statistical_tests"] is None


def test_aliases_are_counted_and_share_their_representatives_results(baseline):
    ws, out = baseline
    t = store.read_arrays(ws.run_dir(out["run_id"]) / "results.bin", out["results_sha256"])
    al = np.flatnonzero(t["alias_of"] >= 0)
    assert al.size > 0                                     # rates xsmom quantiles 0.25/0.3 collapse on 8 assets
    rep = t["alias_of"][al]
    assert np.all(t["s3"][al] == RN.S3["alias"])
    assert np.array_equal(t["stats3"][al], t["stats3"][rep], equal_nan=True)
    assert np.array_equal(t["fingerprint"][al], t["fingerprint"][rep])
    assert np.array_equal(t["stats2"][al], t["stats2"][rep], equal_nan=True)   # same positions: same stage 2


def test_alias_results_equal_direct_computation(baseline, panel):
    """Skipping an alias's stage 3 is exact: computing it directly gives the representative's series."""
    ws, out = baseline
    t = store.read_arrays(ws.run_dir(out["run_id"]) / "results.bin", out["results_sha256"])
    r = Runner(ws, panel, Policy(), chunk_size=32)
    for i in np.flatnonzero(t["alias_of"] >= 0)[:3]:
        d = r.view.describe(int(i))
        Pw, Rw = RN._positions_window(r.cache, d, r.policy, panel.fence)
        c, k = kernels.cost_coefficients(d["domain"], TP.COST_MODELS[d["cost_model"]])
        net = RN._series(r.policy, [(Pw, Rw, c, k)])["net"][0]
        assert hashlib.sha256(net.tobytes()).digest() == bytes(t["series_sha256"][i])


def test_candidate_history_lists_every_attempt(baseline):
    ws, out = baseline
    h = history(ws, out["run_id"], 5)
    assert [x["pass"] for x in h] == ["A", "B"] and all(x["terminal"] == "attempt_completed" for x in h)


# -- determinism ---------------------------------------------------------------------------------------------

def test_results_independent_of_chunk_size_workers_and_input_order(tmp_path, panel, baseline):
    root = baseline[1]["result_root"]
    _, o1 = _run(tmp_path / "c5", panel, chunk_size=5)
    _, o2 = _run(tmp_path / "c1000", panel, chunk_size=1000)
    _, o3 = _run(tmp_path / "w3", panel, chunk_size=16, workers=3)
    b = X.small_bundles()
    perm = list(np.random.default_rng(1).permutation(len(b)))
    _, o4 = _run(tmp_path / "perm", panel, bundles=[b[i] for i in perm], chunk_size=24)
    assert o1["result_root"] == o2["result_root"] == o3["result_root"] == o4["result_root"] == root


def test_feature_cache_on_or_off_gives_identical_results(tmp_path, panel, baseline):
    ws = _ws(tmp_path)
    out = Runner(ws, panel, Policy(), chunk_size=40, cache_enabled=False).run()
    assert out["result_root"] == baseline[1]["result_root"]
    assert out["cache"]["mem_hits"] == 0 and out["cache"]["misses"] > 0


# -- crash, interruption, partial writes and resume (in a subprocess) ------------------------------------------

SCRIPT = """
import json, sys
from manhattan.hte import data as D, fixtures as X
from manhattan.hte.runner import Workspace, Runner
from manhattan.hte.policy import Policy
ws = Workspace(sys.argv[1])
reg = ws.registry()
if len(reg) == 0:
    reg.submit(X.small_bundles()); reg.freeze()
out = Runner(ws, D.generate(X.SMALL_PANEL), Policy(), chunk_size=int(sys.argv[2]), workers=int(sys.argv[3])).run()
print(json.dumps({"root": out.get("result_root"), "closed": out.get("closed", True), "run_id": out["run_id"]}))
"""


def _sub(path, fault=None, chunk=16, workers=1):
    env = dict(os.environ, PYTHONPATH=str(ROOT), OPENBLAS_NUM_THREADS="1")
    env.pop("HTE_FAULT", None)
    if fault:
        env["HTE_FAULT"] = fault
    p = subprocess.run([sys.executable, "-c", SCRIPT, str(path), str(chunk), str(workers)], env=env, cwd=ROOT,
                       capture_output=True, text=True, timeout=600)
    return p


@pytest.mark.parametrize("fault,expect", [
    ("exit_after_start:3", "attempt_interrupted"),          # crash in pass A after an intent record
    ("exit_after_start:10", "attempt_interrupted"),         # crash in pass B (8 A chunks of 16, then B)
    ("exit_after_file:2", "attempt_interrupted"),           # result file written, completion never logged
    ("torn_completion:4", "torn_tail_quarantined"),         # a half-written completion line
])
def test_crash_and_resume_reproduce_the_clean_result(tmp_path, baseline, fault, expect):
    p = _sub(tmp_path, fault)
    assert p.returncode == 77, p.stderr[-2000:]
    p2 = _sub(tmp_path, chunk=40, workers=2)                 # resume with a different chunking and workers
    assert p2.returncode == 0, p2.stderr[-3000:]
    res = json.loads(p2.stdout.strip().splitlines()[-1])
    assert res["root"] == baseline[1]["result_root"]
    ws = Workspace(tmp_path)
    types = _types(ws)
    assert expect in types
    rec = reconcile(ws, res["run_id"])
    assert rec["violations"] == []
    assert rec["attempts"]["interrupted"] >= (1 if expect == "attempt_interrupted" else 0)
    # the interrupted attempt is counted, never erased, and its successor names it
    starts = [r for r in AttemptLog(ws.log_path).records() if r["type"] == "attempt_started"]
    if expect == "attempt_interrupted":
        assert any(r["payload"].get("supersedes") for r in starts)
    if fault.startswith("exit_after_file"):
        named = {r["payload"]["file"] for r in AttemptLog(ws.log_path).of_type("attempt_completed")}
        on_disk = {f"A/{f.name}" for f in (ws.run_dir(res["run_id"]) / "A").iterdir()}
        assert on_disk - named, "the orphan result file should remain on disk, unnamed"


def test_worker_failure_is_logged_retried_and_counted(tmp_path, baseline):
    p = _sub(tmp_path, "worker_raise:2")
    assert p.returncode == 0, p.stderr[-2000:]
    first = json.loads(p.stdout.strip().splitlines()[-1])
    assert first["closed"] is False                          # fail closed: no stage 3 on an incomplete stage 2
    ws = Workspace(tmp_path)
    assert "attempt_failed" in _types(ws) and "run_incomplete" in _types(ws)
    p2 = _sub(tmp_path)
    res = json.loads(p2.stdout.strip().splitlines()[-1])
    assert res["root"] == baseline[1]["result_root"]
    rec = reconcile(ws, res["run_id"])
    assert rec["attempts"]["failed"] == 1 and rec["violations"] == []
    retry = [r for r in AttemptLog(ws.log_path).of_type("attempt_started") if r["payload"].get("supersedes")]
    assert len(retry) == 1


# -- failed computations stay in the denominator -------------------------------------------------------------

def _poison_bundles():
    fam = R.family("test-poison", "TEST ONLY", "+", "dense")
    hyp = R.hypothesis(fam, "fx")
    spec = R.strategy_spec(hyp, "poison_test", {"lookback": [10, 20], "boom": [0, 3, 7]})
    return X.small_bundles(domains=("fx",), templates=("trend",)) + [R.Bundle(fam, hyp, spec)]


def test_failed_candidates_are_recorded_and_block_an_incomplete_spa(tmp_path, panel):
    ws, out = _run(tmp_path, panel, bundles=_poison_bundles(), chunk_size=8)
    t = store.read_arrays(ws.run_dir(out["run_id"]) / "results.bin", out["results_sha256"])
    failed = np.flatnonzero(t["s1"] == RN.S1["failed"])
    assert failed.size == 4                                  # boom 3 (non-finite) and 7 (exception) x 2 look-backs
    assert set(t["reason1"][failed]) == {RN.REASONS["execution_error"], RN.REASONS["non_finite"]}
    assert np.all(t["s3"][failed] == RN.S3["skipped_failed_upstream"])
    pk = [json.loads(p.read_text()) for p in (ws.run_dir(out["run_id"]) / "packages").glob("*.json")]
    poison = [p for p in pk if p["family"]["name"] == "test-poison"][0]
    assert poison["denominators"]["candidates"] == 6 and poison["denominators"]["stage1"]["failed"] == 4
    assert poison["spa"]["computed"] is False
    rec = reconcile(ws, out["run_id"])
    assert rec["violations"] == []
    errors = [r["payload"]["errors"] for r in AttemptLog(ws.log_path).of_type("attempt_completed")]
    assert any(e.get("ValueError") for e in errors)


# -- repeated runs, nondeterminism and tampering -------------------------------------------------------------

def test_repeated_run_is_reused_and_verification_reproduces_bitwise(tmp_path, panel):
    ws, out = _run(tmp_path, panel, chunk_size=50)
    again = Runner(ws, panel, Policy(), chunk_size=7).run()
    assert again["reused"] is True and again["result_root"] == out["result_root"]
    ver = Runner(ws, panel, Policy(), chunk_size=7, workers=2).run(verify_rerun=True)
    assert ver["result_root"] == out["result_root"]
    recs = AttemptLog(ws.log_path).of_type("attempt_completed")
    assert any(r["payload"].get("verification") == "identical" for r in recs)
    rec = reconcile(ws, out["run_id"])
    assert rec["attempts"]["verification"] > 0 and rec["violations"] == []
    assert rec["invocations"] == 3


def test_nondeterminism_is_detected_and_never_replaces_the_result(tmp_path, panel, monkeypatch):
    ws, out = _run(tmp_path, panel, chunk_size=60)
    real = kernels.screen

    def drifting(*a, **k):
        r = real(*a, **k)
        if "net_mean" in r:
            r["net_mean"] += 1e-15
        return r

    monkeypatch.setattr(kernels, "screen", drifting)
    with pytest.raises(RN.RunError, match="nondeterminism"):
        Runner(ws, panel, Policy(), chunk_size=60).run(verify_rerun=True)
    assert "nondeterminism" in _types(ws)
    closed = AttemptLog(ws.log_path).of_type("run_closed")
    assert len(closed) == 1 and closed[0]["payload"]["result_root"] == out["result_root"]


def test_corrupted_result_file_is_refused(tmp_path, panel):
    ws, out = _run(tmp_path, panel, chunk_size=60)
    f = sorted((ws.run_dir(out["run_id"]) / "A").iterdir())[0]
    raw = bytearray(f.read_bytes())
    raw[-3] ^= 0x10
    f.write_bytes(bytes(raw))
    with pytest.raises(store.CorruptFile):
        reconcile(ws, out["run_id"])
    with pytest.raises(store.CorruptFile):
        Runner(ws, panel, Policy()).run(verify_rerun=True)


def test_feature_cache_corruption_is_detected_logged_and_harmless(tmp_path, panel, baseline):
    ws = _ws(tmp_path)
    Runner(ws, panel, Policy(), chunk_size=40).run()
    files = sorted((ws.root / "cache" / "features").glob("*.npy"))
    assert files
    for f in files[:3]:
        raw = bytearray(f.read_bytes())
        raw[-1] ^= 0xFF
        f.write_bytes(bytes(raw))
    # a new run identity (other policy) has to read the cache again
    out = Runner(ws, panel, Policy(vol_halflife=21), chunk_size=40).run()
    # only entries that are read are checked (a dependency of a cached feature is never re-read)
    assert out["cache"]["corrupt"] >= 1
    assert len(AttemptLog(ws.log_path).of_type("cache_corrupt")) == out["cache"]["corrupt"]
    assert len(list((ws.root / "cache" / "features").glob("*.corrupt-*"))) == out["cache"]["corrupt"]
    clean = _run(tmp_path / "clean", panel, policy=Policy(vol_halflife=21), chunk_size=40)[1]
    assert out["result_root"] == clean["result_root"]


# -- changed configuration, code or data identity -------------------------------------------------------------

def test_changed_policy_code_or_data_is_a_new_counted_run(tmp_path, panel, monkeypatch):
    ws, out = _run(tmp_path, panel, chunk_size=60)
    o2 = Runner(ws, panel, Policy(vol_target_ann=0.12), chunk_size=60).run()
    assert o2["run_id"] != out["run_id"]
    real = RN.ids.code_identity
    monkeypatch.setattr(RN.ids, "code_identity", lambda: dict(real(), engine_sha256="f" * 64))
    o3 = Runner(ws, panel, Policy(), chunk_size=60).run()
    assert o3["run_id"] not in (out["run_id"], o2["run_id"]) and o3["result_root"] == out["result_root"]
    monkeypatch.undo()
    other = D.generate(D.PanelParams(seed=8, n_days=760, protected_days=100))
    o4 = Runner(ws, other, Policy(), chunk_size=60).run()
    assert o4["run_id"] not in (out["run_id"], o2["run_id"], o3["run_id"])
    assert o4["result_root"] != out["result_root"]
    pk = json.loads(next((ws.run_dir(o4["run_id"]) / "packages").glob("*.json")).read_text())
    assert pk["looks"]["runs_on_this_registry"] == 4          # every look at the same candidates is counted


def test_bootstrap_seed_cannot_be_chosen_by_a_caller():
    for f in (Runner.__init__, Runner.run):
        assert not any("seed" in p for p in inspect.signature(f).parameters)


# -- selection and screening -----------------------------------------------------------------------------------

def test_selection_is_reproducible_from_logged_inputs(baseline, panel):
    ws, out = baseline
    r = Runner(ws, panel, Policy(), chunk_size=32)
    sel = r._selection()
    again = r.compute_selection()
    assert all(np.array_equal(sel[k], again[k]) for k in sel)
    rec = r._recs("selection")[-1]["payload"]
    assert rec["performance_gate"] is False and rec["policy_hash"] == Policy().hash()


def test_performance_gate_requires_benchmark_flag_and_is_disclosed(tmp_path, panel):
    with pytest.raises(ValueError):
        Policy(stage3_selection="top_k_per_spec", top_k=2)
    pol = Policy(stage3_selection="top_k_per_spec", top_k=2, benchmark_only=True)
    ws, out = _run(tmp_path, panel, policy=pol, chunk_size=64)
    t = store.read_arrays(ws.run_dir(out["run_id"]) / "results.bin", out["results_sha256"])
    assert (t["s3"] == RN.S3["skipped_not_selected"]).sum() > 0
    assert sum(1 for _ in t["s3"]) == 120                    # the unselected stay in the denominator
    for p in (ws.run_dir(out["run_id"]) / "packages").glob("*.json"):
        pk = json.loads(p.read_text())
        assert pk["run"]["performance_gate"] is True
        assert "selection_warning" in pk["stage3"] and pk["spa"]["computed"] is False


def test_dominated_candidates_skip_stage3_but_stay_counted(tmp_path, panel, monkeypatch):
    monkeypatch.setitem(kernels.COSTS, "fx", (0.02, 0.0))   # absurd costs: most candidates are provably dominated
    b = X.small_bundles(domains=("fx",))
    ws, out = _run(tmp_path, panel, bundles=b, chunk_size=30)
    t = store.read_arrays(ws.run_dir(out["run_id"]) / "results.bin", out["results_sha256"])
    dom = t["s1"] == RN.S1["dominated"]
    assert dom.sum() > 0
    nm = t["stats2"][dom, kernels.S2_COLS.index("net_mean")]
    assert np.all(nm <= 0.0)
    assert np.all(t["s3"][dom] == RN.S3["skipped_dominated"])   # aliases of dominated reps inherit the skip
    for p in (ws.run_dir(out["run_id"]) / "packages").glob("*.json"):
        pk = json.loads(p.read_text())
        if pk["denominators"]["stage1"]["dominated"]:
            assert pk["spa"]["computed"] is False            # an SPA over an incomplete set is refused


# -- packages: never confirmatory, never a discovery count ------------------------------------------------------

def _keys(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield k
            yield from _keys(v)
    elif isinstance(o, list):
        for v in o:
            yield from _keys(v)


def test_packages_are_descriptive_and_state_every_denominator(baseline):
    ws, out = baseline
    pk = [json.loads(p.read_text()) for p in (ws.run_dir(out["run_id"]) / "packages").glob("*.json")]
    assert len(pk) == 5 and CONFIRMATORY is False
    total = 0
    for p in pk:
        assert p["confirmatory"] is False and p["synthetic"] is True
        assert p["evidence_class"] == "synthetic_screening_descriptive"
        assert p["independent_statistical_tests"] is None
        assert not [k for k in _keys(p) if "discover" in k.lower() or "significant" in k.lower()]
        assert p["stage2"]["max_is_over_candidates"] == p["denominators"]["stage1"]["pass"] + \
            p["denominators"]["stage1"]["dominated"]
        d = p["denominators"]
        assert d["candidates"] >= d["variants"] >= d["strategy_specs"] >= d["hypotheses"] >= 1
        total += d["candidates"]
        for v in p["m_eff"].values():
            assert v["value"] is None or v["value"] <= v["series_used"]
    assert total == 120


def test_post_look_registrations_are_flagged(tmp_path, panel):
    ws, out = _run(tmp_path, panel, chunk_size=60)
    reg = ws.registry()
    fam = R.family(TP.TEMPLATES["trend"].family["name"], TP.TEMPLATES["trend"].family["mechanism"], "+", "dense")
    hyp = R.hypothesis(fam, "fx")
    spec = R.strategy_spec(hyp, "trend", {"lookback": [33], "shape": ["sign"], "vol_halflife": [20],
                                          "rebalance": [1]})
    assert reg.submit([R.Bundle(fam, hyp, spec)])["registered_candidates"] == 1
    reg.freeze()
    o2 = Runner(ws, panel, Policy(), chunk_size=60).run()
    pk = [json.loads(p.read_text()) for p in (ws.run_dir(o2["run_id"]) / "packages").glob("*.json")]
    trend = [p for p in pk if p["family"]["name"] == "synthetic-trend"][0]
    assert trend["looks"]["post_look_specs"] == [ids.full_hash(spec)]
    others = [p for p in pk if p["family"]["name"] != "synthetic-trend"]
    assert all(p["looks"]["post_look_specs"] == [] for p in others)


def test_planted_synthetic_effect_is_recoverable_and_labelled_synthetic(tmp_path):
    """A pipeline check, not a discovery: the generator plants a trend effect; the trend family's SPA must see it."""
    planted = D.generate(D.PanelParams(seed=7, n_days=760, protected_days=100, planted=0.6))
    b = X.small_bundles(templates=("trend", "carry"))
    ws, out = _run(tmp_path, planted, bundles=b, chunk_size=64)
    pk = {json.loads(p.read_text())["family"]["name"]: json.loads(p.read_text())
          for p in (ws.run_dir(out["run_id"]) / "packages").glob("*.json")}
    assert pk["synthetic-trend"]["spa"]["p_c"] < 0.05
    assert "SYNTHETIC DATA" in pk["synthetic-trend"]["warnings"][0]


# -- stage 5 and the integration boundary ------------------------------------------------------------------------

def test_stage5_is_disabled_whatever_the_caller_passes(tmp_path, panel):
    cfg = (ROOT / "config" / "manhattan.yaml").read_bytes()
    with pytest.raises(protected.ProtectedEvaluationDisabled):
        protected.evaluate(enabled=True, force=True)
    with pytest.raises(protected.ProtectedEvaluationDisabled):
        Runner(_ws(tmp_path), panel, Policy(), stages=(1, 2, 3, 4, 5))
    st = protected.status()
    assert st["enabled"] is False and any("reserve.enabled is false" in b for b in st["blockers"])
    assert protected.ENABLED is False
    assert (ROOT / "config" / "manhattan.yaml").read_bytes() == cfg


def test_pr86_adapter_is_disabled_and_identity_shape_matches_contract(baseline, panel):
    ws, out = baseline
    with pytest.raises(adapters.AdapterDisabled):
        adapters.Pr86AccessAdapter()
    r = Runner(ws, panel, Policy())
    ident = adapters.to_pr86_identity(r.view, 3, run_id=out["run_id"], data_hash=r.data_hash, code=r.code,
                                      window={"id": "synthetic", "start": "2001-03-01", "end": "2002-07-15",
                                              "frequency": "daily"})
    assert tuple(sorted(ident)) == tuple(sorted(adapters.PR86_IDENTITY_FIELDS))
    assert ident["role"] == "exploration" and ident["designated"] is False and ident["channel"] == "blind"
    assert ident["spec_hash"] == r.view.candidate_hash(3)


def test_hte_does_not_import_pr86_private_names():
    src = "".join(p.read_text() for p in (ROOT / "manhattan" / "hte").glob("*.py"))
    for name in ("_open_window", "_SEAL_KEY", "_CTX_KEY", "run_bound", "forward_window", "manhattan.access",
                 "RunnerToken", "em-macro-data", "Norgate", "Databento"):
        assert name not in src.replace("PR #86", ""), name


# -- performance regression ---------------------------------------------------------------------------------

def test_throughput_has_not_regressed_grossly(tmp_path, panel):
    """A generous ceiling (about 20x the measured cost on the reference machine) that catches a regression of
    an order of magnitude, not noise. Measured numbers are in docs/manhattan/hte/BENCHMARKS.md."""
    ws, out = _run(tmp_path, panel, chunk_size=120, stages=(1, 2, 3))
    per = (out["timings"]["pass_A_s"] + out["timings"]["pass_B_s"]) / 120
    assert per < 0.05, per


# -- regressions from the adversarial pass ------------------------------------------------------------------------

def test_a_lost_worker_cannot_hang_the_run_and_is_retried(tmp_path, baseline):
    p = _sub(tmp_path, "worker_exit:2", workers=2)
    assert p.returncode == 0, p.stderr[-2000:]
    assert json.loads(p.stdout.strip().splitlines()[-1])["closed"] is False
    ws = Workspace(tmp_path)
    failed = AttemptLog(ws.log_path).of_type("attempt_failed")
    assert failed and any(r["payload"]["reason"] == "worker_lost" for r in failed)
    p2 = _sub(tmp_path, workers=2)
    res = json.loads(p2.stdout.strip().splitlines()[-1])
    assert res["root"] == baseline[1]["result_root"]
    assert reconcile(ws, res["run_id"])["violations"] == []


def test_one_runner_per_workspace(tmp_path, panel):
    import fcntl
    ws = _ws(tmp_path)
    with open(ws.root / ".lock", "a+") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        with pytest.raises(RN.RunError, match="another runner"):
            Runner(ws, panel, Policy()).run()
    assert Runner(ws, panel, Policy(), chunk_size=60).run()["reused"] is False


def test_disk_preflight_refuses_and_logs(tmp_path, panel, monkeypatch):
    ws = _ws(tmp_path)
    monkeypatch.setattr(Runner, "BYTES_PER_CANDIDATE", 10 ** 15)
    with pytest.raises(RN.RunError, match="preflight"):
        Runner(ws, panel, Policy()).run()
    assert "run_refused" in _types(ws)


# -- regressions from the independent review -----------------------------------------------------------------------

def test_stages_are_part_of_the_run_identity(tmp_path, panel):
    ws = _ws(tmp_path)
    o1 = Runner(ws, panel, Policy(), chunk_size=60, stages=(1, 2)).run()
    o2 = Runner(ws, panel, Policy(), chunk_size=60).run()
    assert o1["run_id"] != o2["run_id"] and o2["reused"] is False
    t = store.read_arrays(ws.run_dir(o2["run_id"]) / "results.bin", o2["results_sha256"])
    assert "s3" in t and (t["s3"] == RN.S3["not_run"]).sum() == 0


def test_an_interrupted_run_resumes_and_reconciles_on_its_own_frozen_version(tmp_path, baseline):
    p = _sub(tmp_path, "exit_after_start:3")
    assert p.returncode == 77
    ws = Workspace(tmp_path)
    old_root = ws.registry().frozen().root
    reg = ws.registry()
    fam = R.family("later", "TEST", "+", "dense")
    hyp = R.hypothesis(fam, "fx")
    reg.submit([R.Bundle(fam, hyp, R.strategy_spec(hyp, "trend", {"lookback": [33], "shape": ["sign"],
                                                                    "vol_halflife": [20], "rebalance": [1]}))])
    reg.freeze()
    panel = D.generate(X.SMALL_PANEL)
    out = Runner(ws, panel, Policy(), chunk_size=16, registry_root=old_root).run()
    assert out["result_root"] == baseline[1]["result_root"]
    rec = reconcile(ws, out["run_id"])
    assert rec["violations"] == [] and rec["registered"]["candidates"] == 120
    assert rec["attempts"]["interrupted"] == 2         # two intents were in flight (window of 2) at the crash


def test_specs_registered_after_freeze_cannot_renumber_a_runs_families(tmp_path, panel):
    ws = _ws(tmp_path)
    r = Runner(ws, panel, Policy())
    fam = R.family("aaaa-new", "TEST", "+", "dense")
    hyp = R.hypothesis(fam, "fx")
    ws.registry().submit([R.Bundle(fam, hyp, R.strategy_spec(hyp, "trend", {"lookback": [33], "shape": ["sign"],
                                                                           "vol_halflife": [20],
                                                                           "rebalance": [1]}))])
    r2 = Runner(ws, panel, Policy())                       # same frozen version: same run, same families
    assert r2.run_id == r.run_id and r2.families == r.families
    assert np.array_equal(r2.fam_of_spec[r2.view.spec_index], r.fam_of_spec[r.view.spec_index])


def test_renamed_family_keeps_its_own_complete_spa_and_is_flagged(tmp_path, panel):
    b = X.small_bundles(domains=("fx",), templates=("trend",))
    fam2 = R.family("renamed-trend", "same rule, new words", "+", "dense")
    hyp2 = R.hypothesis(fam2, "fx")
    b2 = R.Bundle(fam2, hyp2, R.strategy_spec(hyp2, "trend", X.small_grids()["trend"], cost_models=("c1", "c2")))
    ws, out = _run(tmp_path, panel, bundles=b + [b2], chunk_size=20)
    t = store.read_arrays(ws.run_dir(out["run_id"]) / "results.bin", out["results_sha256"])
    r = Runner(ws, panel, Policy())
    fam = r.fam_of_spec[r.view.spec_index]
    al = np.flatnonzero(t["alias_of"] >= 0)
    assert np.all(fam[al] == fam[t["alias_of"][al]])       # no alias crosses a family
    pk = {json.loads(p.read_text())["family"]["name"]: json.loads(p.read_text())
          for p in (ws.run_dir(out["run_id"]) / "packages").glob("*.json")}
    a, c = pk["synthetic-trend"], pk["renamed-trend"]
    assert a["spa"]["computed"] and c["spa"]["computed"]
    assert a["spa"]["variants"] == c["spa"]["variants"] and a["spa"]["p_c"] == c["spa"]["p_c"]
    for p in (a, c):
        assert p["denominators"]["cross_family_semantic_duplicates"] == p["denominators"]["candidates"]
        assert p["denominators"]["cross_family_behavioural_duplicates"] > 0
        assert any("not independent" in w for w in p["warnings"])


def test_re_registering_looked_at_economics_under_a_new_name_is_post_look(tmp_path, panel):
    b = X.small_bundles(domains=("fx",), templates=("trend",))
    ws, out = _run(tmp_path, panel, bundles=b, chunk_size=60)
    fam2 = R.family("renamed-trend", "same rule, new words", "+", "dense")
    hyp2 = R.hypothesis(fam2, "fx")
    spec2 = R.strategy_spec(hyp2, "trend", {"lookback": [40], "shape": ["sign"], "vol_halflife": [20],
                                            "rebalance": [1]})
    reg = ws.registry()
    reg.submit([R.Bundle(fam2, hyp2, spec2)])
    reg.freeze()
    o2 = Runner(ws, panel, Policy(), chunk_size=60).run()
    pk = {json.loads(p.read_text())["family"]["name"]: json.loads(p.read_text())
          for p in (ws.run_dir(o2["run_id"]) / "packages").glob("*.json")}
    assert pk["renamed-trend"]["looks"]["post_look_specs"] == [ids.full_hash(spec2)]
    assert pk["synthetic-trend"]["looks"]["runs_on_any_registry_version"] == 2


def test_verification_covers_spa_and_never_rewrites_packages(tmp_path, panel, monkeypatch):
    ws, out = _run(tmp_path, panel, chunk_size=64)
    pdir = ws.run_dir(out["run_id"]) / "packages"
    before = {p.name: p.read_bytes() for p in pdir.glob("*.json")}
    v = Runner(ws, panel, Policy(), chunk_size=64).run(verify_rerun=True)
    assert v["verified"] is True and "run_verified" in _types(ws)
    assert {p.name: p.read_bytes() for p in pdir.glob("*.json")} == before
    real = kernels.spa_partial

    def drifting(*a, **k):
        res = real(*a, **k)
        return {g: (T + 1e-12,) + tuple(rest) for g, (T, *rest) in res.items()}

    monkeypatch.setattr(kernels, "spa_partial", drifting)
    with pytest.raises(RN.RunError, match="spa_T"):
        Runner(ws, panel, Policy(), chunk_size=64).run(verify_rerun=True)
    rec = reconcile(ws, out["run_id"])
    assert any(v["code"] == "nondeterminism" for v in rec["violations"])
    failed = AttemptLog(ws.log_path).of_type("attempt_failed")
    assert any(r["payload"]["reason"] == "nondeterminism" for r in failed)


# -- S10 review, F2: orphaned workers and the inherited workspace lock ---------------------------------------------

def _procs_with(marker: str) -> list[int]:
    out = []
    for d in Path("/proc").iterdir():
        if d.name.isdigit():
            try:
                if marker.encode() in (d / "cmdline").read_bytes():
                    out.append(int(d.name))
            except OSError:
                pass
    return out


def test_f2_killing_the_parent_leaves_no_workers_and_no_lock(tmp_path, baseline):
    import signal
    import time
    _ws(tmp_path)
    marker = f"hte-f2-{tmp_path.name}"
    env = dict(os.environ, PYTHONPATH=str(ROOT), OPENBLAS_NUM_THREADS="1", HTE_FAULT="worker_hang:3")
    p = subprocess.Popen([sys.executable, "-c", SCRIPT, str(tmp_path), "4", "2", marker], env=env, cwd=ROOT,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + 60
    while time.time() < deadline and len(_procs_with(marker)) < 3:      # parent + 2 workers
        time.sleep(0.1)
    assert len(_procs_with(marker)) >= 3
    time.sleep(0.5)
    os.kill(p.pid, signal.SIGKILL)                                      # abrupt parent termination
    p.wait()
    deadline = time.time() + 10
    while time.time() < deadline and _procs_with(marker):
        time.sleep(0.1)
    left = _procs_with(marker)
    for pid in left:
        os.kill(pid, signal.SIGKILL)
    assert left == [], "workers outlived their parent"
    res = _sub(tmp_path, chunk=40, workers=2)                           # resume is not blocked by any lock
    assert res.returncode == 0, res.stderr[-2000:]
    out = json.loads(res.stdout.strip().splitlines()[-1])
    assert out["root"] == baseline[1]["result_root"]
    assert reconcile(Workspace(tmp_path), out["run_id"])["violations"] == []


LOCK_SCRIPT = """
import os, sys, time
from manhattan.hte.log import locked
with locked(sys.argv[1]):
    pid = os.fork()
    if pid == 0:
        time.sleep(30)
        os._exit(0)
    print(pid, flush=True)
    os._exit(0)                       # the holder dies without unlocking; its forked child lives on
"""


def test_f2_a_forked_child_never_holds_the_workspace_lock(tmp_path):
    import signal
    from manhattan.hte.log import locked
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    p = subprocess.run([sys.executable, "-c", LOCK_SCRIPT, str(tmp_path / "attempts.jsonl")], env=env, cwd=ROOT,
                       capture_output=True, text=True, timeout=60)
    child = int(p.stdout.strip())
    try:
        os.kill(child, 0)                                               # the child is still alive
        with locked(tmp_path / "attempts.jsonl"):                       # ... and the lock is free
            pass
    finally:
        os.kill(child, signal.SIGKILL)
