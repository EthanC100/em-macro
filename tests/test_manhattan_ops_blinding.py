"""Manhattan ops, component 1: the public channel carries health only (O-01 to O-04) and the leak scanner (O-05)."""
import os
import subprocess
import sys

import pytest

from manhattan.ops import blinding as B
from manhattan.ops import leakscan as LS
from manhattan.ops import promotion as P

GOOD = {"status": "ok", "runner": "gha-public", "run_id": 123456, "asof": "2026-11-16",
        "ledger_head": "ab" * 32, "commit": "cd" * 20, "observations_new": 12, "missed_runs": ["2026-11-13"],
        "sources_failed": ["fred_DEXMXUS"], "chain_ok": True}


# ---- O-01

def test_health_record_accepts_operational_facts():
    rec = B.health(GOOD)
    assert rec["schema_version"] == 1 and "0." not in B.render(GOOD)
    assert "| observations_new | 12 |" in B.summary_markdown(GOOD)


@pytest.mark.parametrize("bad", [
    {"observations_new": 0.5},                       # a float, anywhere
    {"observations_new": 1.0},
    {"sharpe": 1},                                   # an unknown key
    {"stage": "evaluate 0.0123"},                    # free text
    {"stage": "0.012345"},                           # a number disguised as a word
    {"ledger_head": "1234567"},                      # a short "hash" made of digits
    {"missed_runs": ["2026-11-13", 0.25]},
    {"sources_failed": ["fred DEXMXUS ok 1.2"]},
    {"status": "great"},
    {"asof": "2026-11-16T00:00"},
])
def test_health_record_refuses_anything_else(bad):
    with pytest.raises(B.BlindingError) as e:
        B.health({**GOOD, **bad})
    assert "0.0123" not in str(e.value) and "0.5" not in str(e.value)           # the refusal names keys only


# ---- O-02

def test_quiet_sends_every_file_descriptor_write_to_the_private_log(tmp_path, capfd):
    log = tmp_path / "private" / "run.log"
    with B.quiet(log):
        print("return 0.0123456789")
        sys.stderr.write("warning 0.987654321\n")
        os.write(1, b"fd1 0.11223344\n")
        os.write(2, b"fd2 0.55667788\n")
        subprocess.run(["sh", "-c", "echo child 0.99887766; echo child-err 0.44332211 >&2"], check=True)
    out, err = capfd.readouterr()
    assert out == "" and err == ""
    text = log.read_text()
    for s in ("0.0123456789", "0.987654321", "0.11223344", "0.55667788", "0.99887766", "0.44332211"):
        assert s in text
    print("after")                                    # restored
    assert capfd.readouterr().out == "after\n"


def test_failure_says_stage_and_class_only():
    try:
        raise ValueError("capital exhausted: return -0.4567891234 on 2026-11-16")
    except ValueError as e:
        f = B.failure("evaluate", e)
    assert f == {"status": "failed", "stage": "evaluate", "error_class": "ValueError"}
    assert B.failure("bad stage!", RuntimeError())["stage"] == "unknown"


# ---- O-03

def test_nonce_is_128_bits_and_fresh():
    a, b = B.nonce(), B.nonce()
    assert len(a) == 32 and int(a, 16) >= 0 and a != b


# ---- O-04

@pytest.mark.parametrize("tier", P.TIERS)
def test_every_promotion_is_refused_in_this_branch(tier):
    assert P.ADOPTED_PROTOCOLS == frozenset()
    with pytest.raises(P.PromotionDisabled, match="no_adopted_protocol"):
        P.promote("AF-1", tier, protocol_hash="e" * 64, config={"claims": {"enabled": True}})


def test_promotion_needs_both_the_adopted_hash_and_claims_enabled(monkeypatch):
    monkeypatch.setattr(P, "ADOPTED_PROTOCOLS", frozenset({"e" * 64}))
    with pytest.raises(P.PromotionDisabled, match="claims_disabled"):
        P.promote("AF-1", "promising", protocol_hash="e" * 64, config={"claims": {"enabled": False}})
    with pytest.raises(P.PromotionDisabled, match="protocol_not_adopted"):
        P.promote("AF-1", "promising", protocol_hash="f" * 64, config={"claims": {"enabled": True}})
    assert P.promote("AF-1", "promising", protocol_hash="e" * 64,
                     config={"claims": {"enabled": True}})["state"] == "intent_needs_stats_module"
    with pytest.raises(ValueError):
        P.promote("AF-1", "famous", protocol_hash="e" * 64, config={})


def test_repository_config_keeps_claims_off():
    from manhattan import config
    assert P.status("e" * 64, config.load()) == (False, "no_adopted_protocol")


# ---- O-05: the scanner itself

V = -0.0123456789123


@pytest.mark.parametrize("rendering", [repr(V), f"{V:.6f}", f"{V:.8g}", f"{V * 100:.4f}%", f"{V * 1e4:.3f} bp",
                                       f"{abs(V):.10f}", f"{V:.7e}", "0.0123456"])        # the last: truncated
def test_scanner_finds_every_rendering(rendering):
    found = LS.scan_text(f"log line: value={rendering} done", LS.Needles([V]), "log")
    assert found and found[0]["channel"] == "log"


def test_scanner_ignores_short_numbers_integers_and_hashes():
    text = "took 1.25 s, 3 records, version 2.5.3, head 0123456789abcdef, run 123456789, 0.0123"
    assert LS.scan_text(text, LS.Needles([V, 1.25, 0.0123]), "log") == []


def test_scanner_reads_trees_and_every_git_object(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    g = lambda *a: subprocess.run(["git", *a], cwd=repo, check=True, capture_output=True)
    g("init", "-q")
    g("config", "user.email", "t@example.invalid")
    g("config", "user.name", "t")
    (repo / "a.txt").write_text(f"x {V!r}\n")
    g("add", "-A")
    g("commit", "-qm", "c1")
    (repo / "a.txt").unlink()                                      # deleted, but still in history
    g("add", "-A")
    g("commit", "-qm", f"c2 mentions {abs(V) * 100:.6f}")         # and a commit message
    n = LS.Needles([V])
    assert LS.scan_tree(repo, n, "tree") == []
    hits = LS.scan_git(repo, n, "git")
    assert {h["channel"].split(":")[1] for h in hits} == {"blob", "commit"}


def test_performance_values_reads_floats_and_canonical_decimal_strings():
    recs = [{"payload": {"net": "0.00123456789", "n": 3, "date": "2026-11-16", "x": [1.5, {"y": -2.25}]}}]
    assert sorted(LS.performance_values(recs)) == [-2.25, 0.00123456789, 1.5]
