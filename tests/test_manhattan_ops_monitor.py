"""Synthetic operational metadata only; no Actions dispatch or network access."""
import json
import subprocess
import sys

import pytest

from manhattan.ops import monitor as M

START = M.utc("2026-11-13T00:00:00Z")  # Friday


def run(at="2026-11-13T23:45:00Z", **kw):
    return {"path": M.WORKFLOW, "head_branch": "main", "event": "schedule",
            "created_at": at, "updated_at": at, "status": "completed", "conclusion": "success", **kw}


def check(runs=(), now="2026-11-16T12:00:00Z", **kw):
    return M.watchdog(list(runs), now=M.utc(now), activated=START, enabled=True, **kw)


def test_disabled_by_default():
    assert M.watchdog([], now=START)["status"] == "disabled"


def test_grace_and_weekend_then_missing_first_run():
    assert check(now="2026-11-14T08:00:00Z")["status"] == "pending"
    assert check()["missed"] == 1  # no weekend slots and no heartbeat required
    assert check([run()])["status"] == "ok"


def test_gap_is_not_erased_by_a_later_success():
    assert check([run("2026-11-16T23:45:00Z")], now="2026-11-17T12:00:00Z")["missed"] == 1


@pytest.mark.parametrize("change", [{"head_branch": "dev"}, {"path": ".github/workflows/tests.yml"},
                                    {"event": "pull_request"}])
def test_unrelated_runs_cannot_mask_a_miss(change):
    assert check([run(**change)])["missed"] == 1


@pytest.mark.parametrize("conclusion", ["failure", "cancelled", "skipped", "timed_out", None])
def test_non_success_is_not_a_heartbeat(conclusion):
    assert check([run(conclusion=conclusion)])["failed"] == 1


def test_delayed_run_runtime_and_stalled_queue():
    late = run("2026-11-14T12:00:00Z", status="in_progress", conclusion=None)
    assert check([late], now="2026-11-14T12:30:00Z")["status"] == "pending"
    assert check([late], now="2026-11-14T14:00:00Z")["failed"] == 1
    assert check([run("2026-11-14T12:00:00Z")])["status"] == "ok"


def test_new_queued_runs_cannot_extend_a_slot_deadline_indefinitely():
    late = run("2026-11-16T11:59:00Z", status="queued", conclusion=None)
    assert check([late])["status"] == "alert"


def test_activation_bounds_and_future_timestamps():
    with pytest.raises(ValueError):
        check(now="2027-01-01T00:00:00Z")
    with pytest.raises(ValueError):
        check([run("2026-11-17T00:00:00Z")])
    with pytest.raises(ValueError):
        M.utc("2026-11-16T00:00:00")


def test_workflow_changes_require_approval_but_code_changes_do_not(tmp_path):
    wf = tmp_path / M.WORKFLOW
    wf.parent.mkdir(parents=True)
    wf.write_text("name: synthetic\n")
    approved = M.workflow_digests(tmp_path)
    (tmp_path / "ordinary.py").write_text("# harmless change\n")
    assert M.integrity(M.workflow_digests(tmp_path), approved)["status"] == "ok"
    wf.write_text("name: changed\n")
    assert M.integrity(M.workflow_digests(tmp_path), approved)["changed"] == 1
    added = wf.with_name("new.yaml")
    added.write_text("name: new\n")
    wf.unlink()
    verdict = M.integrity(M.workflow_digests(tmp_path), approved)
    assert verdict["added"] == verdict["removed"] == 1


def test_symlink_workflow_refused(tmp_path):
    wf = tmp_path / M.WORKFLOW
    wf.parent.mkdir(parents=True)
    source = tmp_path / "outside"
    source.write_text("private")
    wf.symlink_to(source)
    with pytest.raises(ValueError):
        M.workflow_digests(tmp_path)


def test_cli_does_not_echo_untrusted_input(tmp_path):
    snapshot = tmp_path / "runs.json"
    snapshot.write_text(json.dumps([run(created_at="secret_canary_0.123456789")]))
    result = subprocess.run([sys.executable, "-m", "manhattan.ops.monitor", "watchdog", "--runs", str(snapshot),
                             "--enabled", "--activated", START.isoformat(), "--now", "2026-11-16T12:00:00Z"],
                            capture_output=True, text=True)
    assert result.returncode == 2
    assert json.loads(result.stdout) == {"status": "invalid_input"}
    assert not result.stderr and "secret_canary" not in result.stdout
