"""Smoke test of scripts/manhattan_ops_bench.py at its smallest size (one synthetic family, one forward night).

Synthetic data only, no network; the benchmark writes to pytest's temporary directory, never to the repository.
Checks the JSON shape and that families, unique executable configurations and attempts are reported separately,
with historical screening and forward confirmation kept apart.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_ops_bench_smallest_size(tmp_path):
    out = tmp_path / "bench.json"
    p = subprocess.run([sys.executable, str(ROOT / "scripts/manhattan_ops_bench.py"), "--families", "1",
                        "--nights", "1", "--out", str(out)], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert p.returncode == 0, p.stderr[-2000:]
    d = json.loads(out.read_text())
    assert d["synthetic_only"] is True and d["network"] == "none" and d["real_market_data"] == "none"
    assert d["machine"]["nproc"] >= 1 and d["machine"]["python"]
    assert len(d["commit"]) == 40
    (r,) = d["runs"]
    # families, unique executable configurations and attempts: three separate fields, three different quantities
    assert r["families"] == 1
    assert r["unique_executable_configs"] >= 1
    assert r["unique_executable_configs"] <= r["executables_compiled"]
    hs, fc = r["historical_screening"], r["forward_confirmation"]
    for block in (hs, fc):
        assert block["families"] == 1 and block["unique_executable_configs"] == r["unique_executable_configs"]
    assert hs["attempts"] == r["unique_executable_configs"]               # one screening attempt per executable
    assert fc["attempts_total"] == r["predictions_registered"] * fc["nights_run"]
    att = r["attempts_all_kinds"]
    assert att["screening"] == hs["attempts"] and att["forward_observation"] == fc["attempts_total"]
    assert set(att["by_kind"]) == {"screening", "forward_observation"}
    # per-stage timings of the pipeline and of each night
    for stage in ("generate_mock", "critic_mechanical", "compile", "historical_screening",
                  "freeze_pr_prepare_and_commit", "registration", "mirror_verify_final"):
        assert r["pipeline_wall_cpu_s"][stage]["wall_s"] >= 0
    kinds = [n["kind"] for n in fc["nights"]]
    assert kinds == ["capture_only_before_registration", "forward"]
    night = fc["nights"][-1]
    for stage in ("open_clone_verify", "capture_write", "fwd_register_attempts", "fwd_read_window", "fwd_compute",
                  "fwd_completion", "fwd_commit_results_terminals", "heartbeat", "mirror_push", "mirror_verify",
                  "other"):
        assert stage in night["stages_wall_s"], stage
    assert night["attempts"] == r["predictions_registered"] and night["attempts_per_s_forward_phase"] > 0
    assert night["git_commits_private_ledger"] > 0 and night["git_commits_mirror"] > 0
    assert set(night["ledger_working_tree_bytes_after"]) >= {"chain_jsonl", "journal_jsonl", "raw", "logs"}
    assert night["status"] == "ok" and r["failures"] == []
    assert r["final_ledger"]["chain_ok"] and r["final_ledger"]["mirror_status"] == "equal"
    assert not any(isinstance(v, float) and "net" in k for k, v in night.items())  # no performance values reported
