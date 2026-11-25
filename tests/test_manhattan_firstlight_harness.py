"""First Light's end-to-end SYNTHETIC reproducibility harness (manhattan/firstlight/harness.py; S17_NEXT_PRS.md PR-3,
acceptance P3-f..P3-j). Synthetic data only: the harness generates its dataset from a seed, reads no real data,
fetches nothing over the network and writes only under its output directory (a pytest temporary directory here).
P3-a..P3-e are the cap's own tests (tests/test_manhattan_firstlight_cap.py)."""
from __future__ import annotations

import ast
import json
import shutil
import signal
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from manhattan import config as mconfig
from manhattan import ledger as L
from manhattan import roles
from manhattan import spec as S
from manhattan.firstlight import anchor_stub, cap, harness, report, synthetic

ROOT = Path(__file__).resolve().parents[1]
SEED = 7
GRID_SIZE = 12


@pytest.fixture(scope="module")
def clean(tmp_path_factory):
    """One complete harness run, in this process."""
    out = tmp_path_factory.mktemp("fl") / "run"
    res = harness.run(out, SEED)
    return out, res


def _rep(out: Path) -> dict:
    return json.loads((out / harness.REPORT_REL / report.REPORT_JSON).read_bytes())


def _copy(out: Path, tmp_path: Path) -> Path:
    dest = tmp_path / "copy"
    shutil.copytree(out, dest)
    return dest


def _rechain(lines: list[bytes], start: int) -> list[bytes]:
    """Recompute every hash from record ``start`` (1-based) on, as a writer holding the file could."""
    recs = [json.loads(x) for x in lines]
    for i in range(start - 1, len(recs)):
        recs[i]["prev_hash"] = recs[i - 1]["hash"] if i else L.GENESIS
        recs[i]["hash"] = L.record_hash(recs[i])
    return [json.dumps(r, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8") for r in recs]


def _write_lines(path: Path, lines: list[bytes]) -> None:
    path.write_bytes(b"".join(x + b"\n" for x in lines))


# ---------------------------------------------------------------- the design: what is run

def test_the_declared_family_is_one_bounded_grid_with_lag_and_cost_and_capped_windows():
    sp = harness.specs("a" * 40)
    assert len(sp["variants"]) == GRID_SIZE <= S.MAX_GRID
    assert S.validate_family(sp["family"]) == [] and S.validate_hypothesis(sp["hypothesis"]) == []
    st = harness.strategy(sp["variants"][0][0]["point"])
    assert st.lag >= 1 and all(i.cost == harness.COST_ONE_WAY > 0 for i in st.instruments)
    assert synthetic.END == cap.DATA_END and synthetic.START == date(2005, 1, 3)
    from manhattan import access
    cap.check_declared_windows([access.DeclaredWindow(harness.WINDOW_ID, harness.DOMAIN, synthetic.START,
                                                      synthetic.END, roles.EXPLORATION, "evaluation", "0" * 64)])


def test_the_dataset_is_synthetic_deterministic_and_ends_at_the_cap(tmp_path):
    a, b = synthetic.to_csv(*synthetic.generate(SEED)), synthetic.to_csv(*synthetic.generate(SEED))
    assert a == b and a != synthetic.to_csv(*synthetic.generate(SEED + 1))
    contract = synthetic.build(tmp_path, SEED)
    assert contract["synthetic"] is True and contract["real_data"] is False and contract["licensed"] is False
    assert contract["end"] == "2019-12-31" and contract["start"] == "2005-01-03"
    capped = synthetic.load(tmp_path, contract)
    assert capped.store.names() == sorted(synthetic.SERIES)
    (tmp_path / synthetic.CSV_NAME).write_bytes(a.replace(b"2019-12-31", b"2020-01-02"))
    with pytest.raises(synthetic.DatasetError):                     # the file no longer matches its contract
        synthetic.load(tmp_path, contract)
    with pytest.raises(cap.CapError):                               # and the cap refuses it on its own
        days, levels = synthetic.from_csv((tmp_path / synthetic.CSV_NAME).read_bytes())
        cap.CappedStore(synthetic=True).add("x", days, levels[synthetic.SERIES[0]], lag_days=0)


# ---------------------------------------------------------------- P3-f: reproduction in separate processes

def test_p3f_two_runs_in_separate_processes_are_identical(tmp_path):
    res = harness.reproduce(tmp_path / "repro", SEED)
    assert all(r["exit"] == 0 for r in res["runs"].values()), res["runs"]
    assert res["computations"] == GRID_SIZE
    assert res["result_hashes_identical"] and res["differing_computations"] == []
    assert res["census_identical"]
    assert all(f["identical"] for f in res["report_files"].values()) and len(res["report_files"]) == 3
    assert res["reproduced"] is True
    assert json.loads((tmp_path / "repro/reproduction.json").read_bytes())["reproduced"] is True
    assert harness.result_hashes(tmp_path / "repro/run_a" / harness.LEDGER_REL) == \
        harness.result_hashes(tmp_path / "repro/run_b" / harness.LEDGER_REL)


def test_p3f_the_in_process_run_matches_the_subprocess_runs(clean, tmp_path):
    out, _ = clean
    p = harness._subprocess_run(tmp_path / "sub", SEED)
    assert p.returncode == 0, p.stderr[-2000:]
    sub = tmp_path / "sub"
    assert harness.result_hashes(out / harness.LEDGER_REL) == harness.result_hashes(sub / harness.LEDGER_REL)
    for name in (report.REPORT_JSON, report.REPORT_MD, report.PUBLIC_JSON):
        assert (out / harness.REPORT_REL / name).read_bytes() == (sub / harness.REPORT_REL / name).read_bytes()


def test_two_report_builds_from_one_ledger_are_byte_identical(clean, tmp_path):
    out, _ = clean
    files = report.write(out / harness.LEDGER_REL, out / harness.ANCHORS_REL, tmp_path / "again",
                         variant_log=out / harness.LOG_REL)
    for name, data in files.items():
        assert data == (out / harness.REPORT_REL / name).read_bytes()


# ---------------------------------------------------------------- P3-g: the census

def test_p3g_the_census_balances_with_nothing_unfinished_and_every_variant_evaluated(clean):
    out, res = clean
    assert res["complete"] is True
    c = _rep(out)["census"]
    assert c["balanced"] and c["unfinished"] == 0 and c["violations"] == 0 and c["access_reconciled"]
    assert c["registered_executions"] == c["completed"] + c["failed"] + c["aborted"] == GRID_SIZE
    assert c["superseded_interrupted"] == 0 and c["independent_statistical_tests"] is None
    rep = _rep(out)
    assert rep["variants_evaluated"] == rep["variants_in_grid"] == GRID_SIZE
    recs = L.read(out / harness.LEDGER_REL)
    freeze_seq = next(r["seq"] for r in recs if r["type"] == "batch_freeze")
    assert all(r["seq"] > freeze_seq for r in recs if r["type"] == "evaluation_started")   # frozen before any read
    assert all(r["payload"]["role"] == "exploration" and r["payload"]["evidential_weight"] == 0
               for r in recs if r["type"] in L.COMPLETIONS)


_KILL = """
import os, signal, sys
from pathlib import Path
from manhattan.firstlight import harness

def kill(i, ctx):
    if i == 4:
        os.kill(os.getpid(), signal.SIGKILL)       # mid-run: attempt 5 registered, nothing computed

harness.run(Path(sys.argv[1]), int(sys.argv[2]), after_register=kill)
"""


def test_p3g_a_killed_run_leaves_a_visible_unfinished_attempt_that_the_retry_supersedes(clean, tmp_path):
    out = tmp_path / "killed"
    p = subprocess.run([sys.executable, "-c", _KILL, str(out), str(SEED)], cwd=ROOT, capture_output=True, text=True,
                       timeout=600)
    assert p.returncode == -signal.SIGKILL, p.stderr[-2000:]
    book = L.Ledger(out / harness.LEDGER_REL, writer="reader", protocol="x")
    open_ = [r for r in book.unfinished() if not book.is_superseded(r["hash"])]
    assert len(open_) == 1                                           # visible, unfinished
    assert len(list(book.iter_records("evaluation"))) == 4
    killed = open_[0]["hash"]
    # no report while the run is open: the latest anchor is the freeze and the tail is unanchored
    assert not anchor_stub.verify_against_anchor(out / harness.LEDGER_REL, out / harness.ANCHORS_REL)["ok"]
    assert anchor_stub.verify_against_anchor(out / harness.LEDGER_REL, out / harness.ANCHORS_REL, open_run=True)["ok"]
    with pytest.raises(report.ReportRefused):
        report.build(out / harness.LEDGER_REL, out / harness.ANCHORS_REL, out / harness.LOG_REL)
    with pytest.raises(harness.HarnessRefused):                      # a fresh run never reuses the directory
        harness.run(out, SEED)

    res = harness.run(out, SEED, resume=True)
    assert res["complete"] is True and res["this_run"]["retried_interrupted"] == 1
    assert res["this_run"]["skipped_completed"] == 4 and res["this_run"]["evaluated"] == GRID_SIZE - 4
    c = _rep(out)["census"]
    assert c["registered_executions"] == GRID_SIZE + 1 and c["completed"] == GRID_SIZE
    assert c["superseded_interrupted"] == 1 and c["retries"] == 1 and c["unfinished"] == 0 and c["balanced"]
    assert c["violations"] == 0 and c["access_reconciled"]
    recs = L.read(out / harness.LEDGER_REL)
    assert any(r["type"] == "evaluation_started" and r["payload"].get("supersedes") == killed for r in recs)
    assert killed in {r["hash"] for r in recs}                       # the interrupted start is kept, never erased
    assert _rep(out)["variants_evaluated"] == GRID_SIZE
    # the retried run computes exactly what the uninterrupted one did
    assert harness.result_hashes(out / harness.LEDGER_REL) == harness.result_hashes(clean[0] / harness.LEDGER_REL)


# ---------------------------------------------------------------- P3-h: the anchor stub, on a copy

def test_p3h_the_untouched_ledger_verifies_against_its_anchors_but_is_not_independently_anchored(clean):
    out, _ = clean
    v = anchor_stub.verify_against_anchor(out / harness.LEDGER_REL, out / harness.ANCHORS_REL)
    assert v["ok"] and v["checked_against_anchor"] and v["tail"] == 0 and v["anchors"] == 2
    assert v["latest_event"] == "run_close" and v["independently_anchored"] is False


def test_p3h_truncation_by_one_record_is_detected(clean, tmp_path):
    c = _copy(clean[0], tmp_path)
    led = c / harness.LEDGER_REL
    lines = anchor_stub.ledger_lines(led.read_bytes())
    _write_lines(led, lines[:-1])
    assert L.verify(led) == []                                       # the chain alone still verifies
    v = anchor_stub.verify_against_anchor(led, c / harness.ANCHORS_REL)
    assert not v["ok"] and any("truncated" in p for p in v["problems"])
    with pytest.raises(report.ReportRefused):
        report.build(led, c / harness.ANCHORS_REL, c / harness.LOG_REL)


@pytest.mark.parametrize("target", ["middle", "first"])
def test_p3h_a_hash_valid_prefix_rewrite_is_detected(clean, tmp_path, target):
    c = _copy(clean[0], tmp_path)
    led = c / harness.LEDGER_REL
    lines = anchor_stub.ledger_lines(led.read_bytes())
    recs = [json.loads(x) for x in lines]
    k = 1 if target == "first" else next(r["seq"] for r in recs if r["type"] == "evaluation")
    if target == "first":
        recs[0]["payload"]["label"] = "rewritten"
    else:
        recs[k - 1]["payload"]["summary"]["sharpe"] = "9.99"         # a better-looking result, chain recomputed
    lines[k - 1] = json.dumps(recs[k - 1], sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    _write_lines(led, _rechain(lines, k))
    assert L.verify(led) == []                                       # hash-valid: only the anchor can tell
    v = anchor_stub.verify_against_anchor(led, c / harness.ANCHORS_REL)
    assert not v["ok"]
    want = "no anchor for this ledger id" if target == "first" else "rewritten"
    assert any(want in p for p in v["problems"]), v["problems"]
    with pytest.raises(report.ReportRefused):
        report.build(led, c / harness.ANCHORS_REL, c / harness.LOG_REL)


def test_p3h_a_removed_or_edited_anchor_and_an_unanchored_tail_are_detected(clean, tmp_path):
    c = _copy(clean[0], tmp_path)
    led, adir = c / harness.LEDGER_REL, c / harness.ANCHORS_REL
    apath = next(adir.glob("*.jsonl"))
    original = apath.read_bytes()
    lines = [x for x in original.split(b"\n") if x]
    apath.write_bytes(lines[1] + b"\n")                              # the freeze anchor removed
    v = anchor_stub.verify_against_anchor(led, adir)
    assert not v["ok"] and any("prev_anchor" in p for p in v["problems"])
    n = json.loads(lines[1])["records"]
    apath.write_bytes(original.replace(b'"records":%d' % n, b'"records":%d' % (n - 1)))
    assert not anchor_stub.verify_against_anchor(led, adir)["ok"]
    apath.write_bytes(original)
    book = L.Ledger(led, writer="w", protocol="p")
    book.append("run_summary", {"note": "a record after the run closed"})
    v = anchor_stub.verify_against_anchor(led, adir)
    assert not v["ok"] and v["tail"] == 1
    with pytest.raises(report.ReportRefused):
        report.build(led, adir, c / harness.LOG_REL)


def test_the_anchor_stub_refuses_to_anchor_a_ledger_that_no_longer_matches(clean, tmp_path):
    c = _copy(clean[0], tmp_path)
    led = c / harness.LEDGER_REL
    lines = anchor_stub.ledger_lines(led.read_bytes())
    _write_lines(led, lines[:-1])
    with pytest.raises(anchor_stub.AnchorError):
        anchor_stub.write_anchor(c / harness.ANCHORS_REL, led, event="run_close", run_id="x", code_commit="y")


# ---------------------------------------------------------------- P3-i: the report and the public artefact

def test_p3i_the_public_index_carries_no_outcome_key_and_lists_every_variant(clean):
    out, _ = clean
    public = json.loads((out / harness.REPORT_REL / report.PUBLIC_JSON).read_bytes())
    assert report.scan_public(public) == [] and L.outcome_keys_in(public) == []
    assert len(public["variants"]) == GRID_SIZE and all(v["status"] == "completed" for v in public["variants"])
    assert public["synthetic"] is True and public["claim"] == "none"
    assert public["evidence"] == {"role": "exploration", "class": "exploration", "eligibility": "descriptive",
                                  "evidential_weight": 0}
    # the scan does see outcomes where they are (the full report is not public)
    assert report.scan_public(_rep(out)) != []
    assert report.scan_public({"variants": [{"sharpe": "0.1"}]}) == ["variants[0].sharpe"]


def test_p3i_the_report_lists_every_variant_including_negatives_and_its_identity(clean):
    out, _ = clean
    rep = _rep(out)
    assert [v["variant"] for v in rep["variants"]] == [S.spec_id(v) for v, _ in harness.specs("a" * 40)["variants"]]
    assert all(v["summary"] is not None and v["result_hash"] for v in rep["variants"])
    negatives = [v for v in rep["variants"] if float(v["summary"]["sharpe"]) < 0]
    assert len(negatives) == rep["negative_sharpe_variants"] >= 1
    assert rep["evidence"]["evidential_weight"] == 0 and rep["evidence"]["class"] == "exploration"
    contract = synthetic.read_contract(out / harness.DATA_REL)
    assert rep["data"]["pit_data_hash"] == contract["pit_data_hash"] and rep["data_hash_in_every_completion"]
    assert rep["data"]["synthetic"] is True and rep["code"]["commit"] and len(rep["code"]["commit"]) == 40
    assert rep["freeze"]["kind"] == "synthetic freeze, not owner-signed"
    assert rep["probes"] == {"load_dated_2020_01_02": "refused", "read_2019_12_02_to_2020_01_02": "refused",
                             "declared_window_to_2020_01_02": "refused", "data_hash_unchanged": True}
    md = (out / harness.REPORT_REL / report.REPORT_MD).read_text(encoding="utf-8")
    assert all(v["variant"] in md for v in rep["variants"]) and "SYNTHETIC" in md


# ---------------------------------------------------------------- P3-j: the switches

def test_p3j_the_configuration_check_passes_with_every_protected_switch_off():
    assert mconfig.main(["check"]) == 0
    assert harness.check_switches() == {"reserve.enabled": False, "claims.enabled": False,
                                        "forward.real_money": False}


@pytest.mark.parametrize("section,key,value", [("reserve", "enabled", True), ("claims", "enabled", True),
                                               ("forward", "real_money", True), ("reserve", "enabled", None),
                                               ("claims", "enabled", "false")])
def test_p3j_the_harness_refuses_if_a_protected_switch_is_not_false(monkeypatch, tmp_path, section, key, value):
    cfg = mconfig.load()
    cfg[section] = {**cfg[section], key: value}
    monkeypatch.setattr(mconfig, "load", lambda *a, **k: cfg)
    out = tmp_path / "out"
    with pytest.raises(harness.HarnessRefused):
        harness.run(out, SEED)
    with pytest.raises(harness.HarnessRefused):
        harness.reproduce(tmp_path / "repro", SEED)
    assert harness.main(["--out", str(out), "--seed", str(SEED)]) == harness.EXIT_REFUSED
    assert not out.exists() and not (tmp_path / "repro").exists()


def test_p3j_an_unreadable_configuration_refuses(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise OSError("unreadable")
    monkeypatch.setattr(mconfig, "load", boom)
    with pytest.raises(harness.HarnessRefused):
        harness.run(tmp_path / "out", SEED)
    assert not (tmp_path / "out").exists()


# ---------------------------------------------------------------- containment

def test_a_used_output_directory_is_refused(tmp_path):
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "x").write_text("earlier", encoding="utf-8")
    with pytest.raises(harness.HarnessRefused):
        harness.run(tmp_path / "out", SEED)
    with pytest.raises(harness.HarnessRefused):
        harness.run(tmp_path / "fresh", SEED, resume=True)


def test_a_run_writes_nothing_outside_its_output_and_restores_the_variant_log_cutoff(tmp_path):
    from nightshift import logs
    before_cutoff = logs.main_cutoff
    status = ["git", "status", "--porcelain", "--untracked-files=all"]
    before = subprocess.run(status, cwd=ROOT, capture_output=True, text=True, check=True).stdout
    outside = sorted(p.name for p in tmp_path.iterdir())
    harness.run(tmp_path / "out", SEED)
    assert subprocess.run(status, cwd=ROOT, capture_output=True, text=True, check=True).stdout == before
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(outside + ["out"])
    assert logs.main_cutoff is before_cutoff
    rows = (tmp_path / "out" / harness.LOG_REL).read_text(encoding="utf-8").splitlines()
    assert len(rows) == GRID_SIZE + 1 and all(",2019-12-31," in r for r in rows[1:])


def test_the_harness_modules_import_no_network_client_and_name_no_private_store():
    network = {"socket", "requests", "urllib", "http", "ftplib", "smtplib", "paramiko", "boto3", "httpx", "aiohttp"}
    private = ("EM_MACRO_DATA", "DATA_REPO_READ_TOKEN", "DATA_REPO_URL", "em-macro-data", "norgate", "databento")
    for p in sorted((ROOT / "manhattan/firstlight").glob("*.py")):
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                assert not any(a.name.split(".")[0] in network for a in n.names), p.name
            elif isinstance(n, ast.ImportFrom) and n.module:
                assert n.module.split(".")[0] not in network, p.name
            elif isinstance(n, ast.Constant) and isinstance(n.value, str):
                assert not any(s in n.value.lower() for s in (x.lower() for x in private)), (p.name, n.value[:60])


def test_the_harness_is_not_an_evidence_producer():
    """The S16 probe for an HTE evidence adapter counts every production importer of manhattan.evidence (GAP-03)."""
    for p in sorted((ROOT / "manhattan/firstlight").glob("*.py")):
        for n in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            names = ([a.name for a in n.names] if isinstance(n, ast.Import)
                     else [n.module or ""] + [f"{n.module}.{a.name}" for a in n.names]
                     if isinstance(n, ast.ImportFrom) else [])
            assert not any(x.startswith("manhattan.evidence") for x in names), p.name


# ---------------------------------------------------------------- PR #107 review: variant log completeness (item 2)

@pytest.mark.parametrize("fail_on", ["every", "third"])
def test_a_run_whose_variant_logging_fails_is_incomplete_and_unreported(monkeypatch, tmp_path, fail_on):
    from nightshift import logs
    original, calls = logs.log_variant, []

    def flaky(*a, **k):
        calls.append(1)
        if fail_on == "every" or len(calls) == 3:
            raise ValueError("variant log refused")
        return original(*a, **k)
    monkeypatch.setattr(logs, "log_variant", flaky)
    res = harness.run(tmp_path / "out", SEED)
    assert res["complete"] is False and res["this_run"]["failed"] == (GRID_SIZE if fail_on == "every" else 1)
    assert "variant log" in res["report_refused"]
    assert not (tmp_path / "out" / harness.REPORT_REL).exists()
    if fail_on == "every":
        assert harness.main(["--out", str(tmp_path / "cli"), "--seed", str(SEED)]) == harness.EXIT_INCOMPLETE


def test_the_report_refuses_a_variant_log_missing_or_repeating_a_row(clean, tmp_path):
    c = _copy(clean[0], tmp_path)
    log = c / harness.LOG_REL
    rows = log.read_text(encoding="utf-8").splitlines()
    for bad in (rows[:-1], rows + rows[-1:]):
        log.write_text("\n".join(bad) + "\n", encoding="utf-8")
        with pytest.raises(report.ReportRefused, match="variant log"):
            report.build(c / harness.LEDGER_REL, c / harness.ANCHORS_REL, log)
    log.unlink()
    with pytest.raises(report.ReportRefused, match="variant log"):
        report.build(c / harness.LEDGER_REL, c / harness.ANCHORS_REL, log)


# ---------------------------------------------------------------- item 3: the variant-log cutoff only tightens

@pytest.mark.parametrize("text", ['explorer:\n  data_end: "2014-12-31"\n', "explorer: {}\n", "- a list\n", None])
def test_the_local_explorer_cutoff_must_be_readable_and_reach_the_cap(monkeypatch, tmp_path, text):
    night = tmp_path / "night.yaml"
    if text is not None:
        night.write_text(text, encoding="utf-8")
    monkeypatch.setattr(harness, "NIGHT_CONFIG", night)
    with pytest.raises(harness.HarnessRefused, match="explorer cutoff"):
        harness.run(tmp_path / "out", SEED)
    assert not (tmp_path / "out").exists()


def test_the_variant_log_cutoff_is_never_wider_than_the_cap(monkeypatch, tmp_path):
    assert harness.variant_log_cutoff() == cap.DATA_END                       # the repository's night.yaml
    night = tmp_path / "night.yaml"
    night.write_text('explorer:\n  data_end: "2023-12-31"\n', encoding="utf-8")
    monkeypatch.setattr(harness, "NIGHT_CONFIG", night)
    assert harness.variant_log_cutoff() == cap.DATA_END                       # min(local, cap)
    with pytest.raises(harness.HarnessRefused):
        with harness._variant_log_cutoff(date(2020, 1, 1)):
            pass
    from nightshift import logs
    with harness._variant_log_cutoff(cap.DATA_END):
        assert logs.main_cutoff() == cap.DATA_END
        with pytest.raises(harness.HarnessRefused, match="single-threaded"):   # the lock is held
            with harness._variant_log_cutoff(cap.DATA_END):
                pass
    assert not harness._LOG_LOCK.locked()


# ---------------------------------------------------------------- item 4: the raw store stays inside the harness

def test_the_harness_never_hands_out_the_raw_store(clean):
    import re
    from manhattan.engine import pit

    def walk(x):
        assert not isinstance(x, (pit.PitStore, cap.CappedStore))
        for y in (x.values() if isinstance(x, dict) else x if isinstance(x, (list, tuple)) else ()):
            walk(y)
    walk(clean[1])
    src = (ROOT / "manhattan/firstlight/harness.py").read_text(encoding="utf-8")
    uses = re.findall(r"capped\.store(\.data_hash\(\)|\))", src)
    assert len(uses) == src.count("capped.store") and "ctx.window(capped.store)" in src
    tree = ast.parse(src)
    assert not any(isinstance(n, ast.Return) and isinstance(n.value, ast.Name) and n.value.id == "capped"
                   for n in ast.walk(tree))


# ---------------------------------------------------------------- item 5: a refused resume writes nothing

def _tree(d: Path) -> dict:
    import hashlib
    return {p.relative_to(d).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(d.rglob("*")) if p.is_file()}


def test_a_resume_with_another_seed_is_refused_before_anything_is_written(clean, tmp_path):
    c = _copy(clean[0], tmp_path)
    before = _tree(c)
    with pytest.raises(harness.HarnessRefused, match="seed"):
        harness.run(c, SEED + 1, resume=True)
    assert _tree(c) == before


# ---------------------------------------------------------------- item 6: the anchor check never raises

@pytest.mark.parametrize("mangle", ["records_string", "not_json", "a_list", "head_number", "not_utf8"])
def test_a_malformed_anchor_fails_the_check_without_raising(clean, tmp_path, mangle):
    c = _copy(clean[0], tmp_path)
    apath = next((c / harness.ANCHORS_REL).glob("*.jsonl"))
    lines = [x for x in apath.read_bytes().split(b"\n") if x]
    a = json.loads(lines[-1])
    if mangle == "records_string":
        a["records"] = str(a["records"])
        lines[-1] = json.dumps(a, sort_keys=True, separators=(",", ":")).encode()
    elif mangle == "head_number":
        a["head"] = 7
        lines[-1] = json.dumps(a, sort_keys=True, separators=(",", ":")).encode()
    elif mangle == "not_json":
        lines[-1] = b"{not json"
    elif mangle == "a_list":
        lines[-1] = b"[1,2,3]"
    else:
        lines[-1] = b"\xff\xfe"
    apath.write_bytes(b"\n".join(lines) + b"\n")
    v = anchor_stub.verify_against_anchor(c / harness.LEDGER_REL, c / harness.ANCHORS_REL)
    assert v["ok"] is False and v["problems"] and v["independently_anchored"] is False
    with pytest.raises(report.ReportRefused):
        report.build(c / harness.LEDGER_REL, c / harness.ANCHORS_REL, c / harness.LOG_REL)


# ---------------------------------------------------------------- item 7: one exploration completion per variant

def _forge_append(led: Path, type_: str, payload: dict) -> None:
    """Append a hash-valid record as a writer holding the file could, then anchor it as a closed run."""
    last = json.loads(anchor_stub.ledger_lines(led.read_bytes())[-1])
    rec = {"seq": last["seq"] + 1, "ts_utc": last["ts_utc"], "type": type_, "writer": last["writer"],
           "protocol": last["protocol"], "payload": payload, "prev_hash": last["hash"]}
    rec["hash"] = L.record_hash(rec)
    with led.open("ab") as f:
        f.write(json.dumps(rec, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8") + b"\n")
    anchor_stub.write_anchor(led.parent.parent / harness.ANCHORS_REL, led, event="run_close", run_id="forged",
                             code_commit="0" * 40)


@pytest.mark.parametrize("change,match", [({}, "more than one completion"),
                                          ({"role": "forward"}, "exploration-role"),
                                          ({"evidential_weight": 1}, "weight 0"),
                                          ({"executable": "AX-0000000000000000"}, "outside the frozen grid")])
def test_the_report_refuses_extra_foreign_or_non_exploration_completions(clean, tmp_path, change, match):
    c = _copy(clean[0], tmp_path)
    led = c / harness.LEDGER_REL
    first = next(r for r in L.read(led) if r["type"] == "evaluation")
    _forge_append(led, "rerun", {**first["payload"], **change})
    assert anchor_stub.verify_against_anchor(led, c / harness.ANCHORS_REL)["ok"]   # only the content check can tell
    with pytest.raises(report.ReportRefused, match=match):
        report.build(led, c / harness.ANCHORS_REL, c / harness.LOG_REL)


# ---------------------------------------------------------------- item 8: mutants of the probes and the close check

@pytest.mark.parametrize("weaken", ["declared_window", "read", "load"])
def test_the_run_stops_if_a_cap_probe_is_not_refused(monkeypatch, tmp_path, weaken):
    if weaken == "declared_window":
        monkeypatch.setattr(cap, "check_declared_windows", lambda windows: None)
    elif weaken == "read":
        monkeypatch.setattr(cap.CappedReader, "window", lambda self, start, end: None)
    else:
        original = cap.CappedStore.add

        def add(self, series, periods, values, **kw):
            if series == "probe_after_cap":
                return None                                                    # a cap that lets 2020 in
            return original(self, series, periods, values, **kw)
        monkeypatch.setattr(cap.CappedStore, "add", add)
    with pytest.raises(cap.CapError, match="probe"):
        harness.run(tmp_path / "out", SEED)
    assert not (tmp_path / "out" / harness.LEDGER_REL).exists()


def test_the_report_refuses_unless_the_latest_anchor_closes_a_run(clean, tmp_path):
    c = _copy(clean[0], tmp_path)
    anchor_stub.write_anchor(c / harness.ANCHORS_REL, c / harness.LEDGER_REL, event="heartbeat", run_id="x",
                             code_commit="0" * 40)
    assert anchor_stub.verify_against_anchor(c / harness.LEDGER_REL, c / harness.ANCHORS_REL)["ok"]
    with pytest.raises(report.ReportRefused, match="run_close"):
        report.build(c / harness.LEDGER_REL, c / harness.ANCHORS_REL, c / harness.LOG_REL)


# ---------------------------------------------------------------- item 9: no secrets reach the child processes

def test_child_processes_get_no_token_secret_or_key(monkeypatch, tmp_path):
    env = {"PATH": "/usr/bin", "HOME": "/h", "DATA_REPO_READ_TOKEN": "t", "GITHUB_TOKEN": "g", "GH_TOKEN": "h",
           "MY_SECRET": "s", "api_key": "k", "SIGNING_KEY_PATH": "p", "DB_PASSWORD": "w",
           "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "http.extraheader", "GIT_CONFIG_VALUE_0": "AUTH x"}
    out = harness.child_env(env)
    assert set(out) == {"PATH", "HOME", "PYTHONDONTWRITEBYTECODE"}
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    seen = {}

    def fake_run(cmd, **kw):
        seen.update(kw["env"])
        return subprocess.CompletedProcess(cmd, 0, "", "")
    monkeypatch.setattr(harness.subprocess, "run", fake_run)
    harness._subprocess_run(tmp_path / "x", SEED)
    assert seen and not any(m in k.upper() for k in seen for m in ("TOKEN", "SECRET", "KEY", "PASSWORD", "GIT_CONFIG"))


def test_a_failure_after_a_recorded_and_logged_evaluation_still_makes_the_run_incomplete(monkeypatch, tmp_path):
    """The census and the variant log can both be whole while the run itself raised: complete is then False."""
    from manhattan.engine import evaluate as E
    original, calls = E.evaluate, []

    def then_raise(*a, **k):
        out = original(*a, **k)
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError("after the record and the log row")
        return out
    monkeypatch.setattr(E, "evaluate", then_raise)
    res = harness.run(tmp_path / "out", SEED)
    assert res["census"]["completed"] == GRID_SIZE and res["census"]["unfinished"] == 0
    assert res["this_run"]["failed"] == 1 and res["complete"] is False


def test_the_anchor_check_turns_any_unexpected_error_into_a_failure(clean, monkeypatch):
    def boom(path):
        raise RuntimeError("unexpected")
    monkeypatch.setattr(anchor_stub, "read_anchors", boom)
    v = anchor_stub.verify_against_anchor(clean[0] / harness.LEDGER_REL, clean[0] / harness.ANCHORS_REL)
    assert v["ok"] is False and "cannot be checked" in v["problems"][-1] and v["independently_anchored"] is False


@pytest.mark.parametrize("name", [
    "DATA_REPO_URL", "HTTPS_PROXY", "http_proxy", "ALL_PROXY", "GITHUB_PAT", "NETRC", "SSH_AUTH_SOCK",
    "AUTHORIZATION", "COOKIE", "AWS_PROFILE", "GOOGLE_APPLICATION_CREDENTIALS", "PYTHONPATH",
    "PYTHONSTARTUP", "PYTHONHOME", "LD_PRELOAD", "GIT_SSH_COMMAND", "GIT_CONFIG_GLOBAL",
    "GIT_CONFIG_COUNT", "GIT_CONFIG_VALUE_0", "ARBITRARY_UNRECOGNIZED_NAME",
])
def test_reproduction_children_do_not_inherit_unneeded_account_or_injection_variables(name):
    # Synthetic marker only; the test never reads or prints the real environment.
    supplied = {"PATH": "/usr/bin", "HOME": "/fixture", name: "https://fixture:fake@invalid.example"}
    expected = {"PATH": "/usr/bin", "HOME": "/fixture", "PYTHONDONTWRITEBYTECODE": "1"}
    assert harness.child_env(supplied) == expected
    assert name in supplied  # filtering must not mutate the parent's environment


def test_reproduction_forwards_runtime_locale_and_thread_settings_only(monkeypatch, tmp_path):
    supplied = {"PATH": "/usr/bin", "HOME": "/fixture", "LANG": "C.UTF-8", "OMP_NUM_THREADS": "1",
                "TMPDIR": str(tmp_path), "SSH_AUTH_SOCK": "/fixture/agent", "PYTHONPATH": "/fixture/injection"}
    expected = {k: v for k, v in supplied.items() if k not in ("SSH_AUTH_SOCK", "PYTHONPATH")}
    expected["PYTHONDONTWRITEBYTECODE"] = "1"
    monkeypatch.setattr(harness.os, "environ", supplied)
    def fake_run(cmd, **kwargs):
        assert kwargs["env"] == expected
        return subprocess.CompletedProcess(cmd, 0, "", "")
    monkeypatch.setattr(harness.subprocess, "run", fake_run)
    assert harness._subprocess_run(tmp_path / "out", SEED).returncode == 0


@pytest.mark.parametrize("text", ['explorer:\n  data_end: "2014-12-31"\n', "explorer: {}\n", "- a list\n", None])
@pytest.mark.parametrize("existing_empty_directory", [False, True])
def test_reproduce_refuses_bad_cutoff_before_writes_or_children(monkeypatch, tmp_path, text,
                                                              existing_empty_directory):
    night = tmp_path / "night.yaml"
    if text is not None:
        night.write_text(text, encoding="utf-8")
    monkeypatch.setattr(harness, "NIGHT_CONFIG", night)
    out = tmp_path / "repro"
    if existing_empty_directory:
        out.mkdir()
    monkeypatch.setattr(harness, "_subprocess_run", lambda *a: pytest.fail("a refused run must spawn no child"))
    with pytest.raises(harness.HarnessRefused, match="explorer cutoff"):
        harness.reproduce(out, SEED)
    assert out.exists() == existing_empty_directory
    if out.exists():
        assert not list(out.iterdir())
    assert harness.main(["--out", str(out), "--seed", str(SEED), "--reproduce"]) == harness.EXIT_REFUSED


@pytest.mark.parametrize("head", ["z" * 64, "a" * 63, "a" * 65, "A" * 64])
def test_anchor_heads_require_lowercase_sha256_syntax(clean, tmp_path, head):
    c = _copy(clean[0], tmp_path)
    apath = next((c / harness.ANCHORS_REL).glob("*.jsonl"))
    lines = [x for x in apath.read_bytes().split(b"\n") if x]
    a = json.loads(lines[-1])
    a["head"] = head
    lines[-1] = json.dumps(a, sort_keys=True, separators=(",", ":")).encode()
    apath.write_bytes(b"\n".join(lines) + b"\n")
    assert not anchor_stub.verify_against_anchor(c / harness.LEDGER_REL, c / harness.ANCHORS_REL)["ok"]
    with pytest.raises(report.ReportRefused):
        report.build(c / harness.LEDGER_REL, c / harness.ANCHORS_REL, c / harness.LOG_REL)


def test_variant_log_extra_unknown_row_is_refused(clean, tmp_path):
    import csv
    c = _copy(clean[0], tmp_path)
    log = c / harness.LOG_REL
    with log.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    unknown = {**rows[0], "code_ref": "f" * 64}
    with log.open("a", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writerow(unknown)
    with pytest.raises(report.ReportRefused, match="unknown"):
        report.build(c / harness.LEDGER_REL, c / harness.ANCHORS_REL, log)


@pytest.mark.parametrize('mode', ['run', 'resume', 'reproduce'])
def test_output_inside_repository_is_refused_before_writes(monkeypatch, tmp_path, mode):
    repo = tmp_path / 'repo'
    repo.mkdir()
    monkeypatch.setattr(harness, 'ROOT', repo)
    out = repo / 'data/ledger/fixture'
    with pytest.raises(harness.HarnessRefused, match='outside the repository'):
        if mode == 'reproduce':
            harness.reproduce(out, SEED)
        else:
            harness.run(out, SEED, resume=mode == 'resume')
    assert not (repo / 'data').exists()


def test_children_disable_environment_and_user_site_injection(monkeypatch, tmp_path):
    def run(cmd, **kwargs):
        assert cmd[:5] == [sys.executable, '-B', '-E', '-s', '-m']
        return subprocess.CompletedProcess(cmd, 0, '', '')
    monkeypatch.setattr(harness.subprocess, 'run', run)
    harness._subprocess_run(tmp_path / 'run', SEED)


def test_freeze_content_errors_are_never_an_expected_attestation_refusal(monkeypatch, tmp_path):
    from manhattan import freeze
    def fail(*a, **kw):
        raise freeze.FreezeError('synthetic corrupt manifest content')
    monkeypatch.setattr(freeze, 'verify_frozen', fail)
    with pytest.raises(freeze.FreezeError, match='corrupt manifest content'):
        harness.run(tmp_path / 'out', SEED)
    assert not (tmp_path / 'out' / harness.LEDGER_REL).exists()


def test_reproduction_child_does_not_execute_user_sitecustomize(monkeypatch, tmp_path):
    home = tmp_path / 'home'
    user_site = home / '.local/lib' / f'python{sys.version_info.major}.{sys.version_info.minor}' / 'site-packages'
    user_site.mkdir(parents=True)
    marker = tmp_path / 'user-site-executed'
    (user_site / 'sitecustomize.py').write_text('from pathlib import Path\nPath(' + repr(str(marker)) + ').touch()\n')
    monkeypatch.setenv('HOME', str(home))
    result = harness._subprocess_run(tmp_path / 'run', SEED)
    assert result.returncode == 0, result.stderr[-1500:]
    assert not marker.exists()


def test_child_bytecode_writes_are_disabled_even_when_environment_is_ignored(monkeypatch, tmp_path):
    real_run = subprocess.run
    def probe(cmd, **kwargs):
        prefix = cmd[:cmd.index('-m')]
        check = 'import sys; assert sys.dont_write_bytecode and sys.flags.ignore_environment and sys.flags.no_user_site'
        return real_run(prefix + ['-c', check], **kwargs)
    monkeypatch.setattr(harness.subprocess, 'run', probe)
    result = harness._subprocess_run(tmp_path / 'run', SEED)
    assert result.returncode == 0, result.stderr
