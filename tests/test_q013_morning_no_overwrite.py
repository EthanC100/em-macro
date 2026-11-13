"""Q013: the morning report generator refuses to overwrite an existing report for the same date.

ROOT is monkeypatched to tmp_path and build() is stubbed, so the real results/night/morning/ is never read or
written. The check runs before build(): a refused run never assembles the report. The one exception: when the
existing report's "Promoted to main" line differs from promoted(<date>) now (the 05:30 promote refused, the 06:30
rerun passed), the report is rewritten. --stdout prints and writes nothing.
"""
from __future__ import annotations

import pytest

from nightshift import morning as M

DAY = "2026-11-12"
OLD = ("# Night shift, 2026-11-11 -> 2026-11-12\n\n**Promoted to main:** no - (b) unexplained data/meta.json\n\n"
       "**Needs Ethan:**\n- hand-written line => keep it\n")


@pytest.fixture
def env(tmp_path, monkeypatch):
    calls = []

    def fake_build(day, dev, needs):
        calls.append(day)
        return f"# Night shift, rebuilt\n\n**Promoted to main:** {M.promoted(day)}\n"

    monkeypatch.setattr(M, "ROOT", tmp_path)
    monkeypatch.setattr(M, "build", fake_build)
    monkeypatch.setattr(M, "promoted", lambda day, main="origin/main": "no - (b) unexplained data/meta.json")
    out = tmp_path / f"results/night/morning/{DAY}.md"
    return tmp_path, out, calls, monkeypatch


def test_q013_refuses_existing_report(env, capsys):
    root, out, calls, _ = env
    out.parent.mkdir(parents=True)
    out.write_bytes(OLD.encode("utf-8"))
    rc = M.main(["--date", DAY, "--needs", "other => text"])
    err = capsys.readouterr()
    assert rc != 0
    assert f"results/night/morning/{DAY}.md" in (err.err + err.out)
    assert out.read_bytes() == OLD.encode("utf-8")
    assert calls == [], "the existing report must be checked before build() runs"


def test_q013_rewrites_when_promote_outcome_changed(env):
    root, out, calls, mp = env
    out.parent.mkdir(parents=True)
    out.write_text(OLD, encoding="utf-8")
    mp.setattr(M, "promoted", lambda day, main="origin/main": "yes - merged into main (PR #50)")
    assert M.main(["--date", DAY]) == 0
    assert calls and "**Promoted to main:** yes - merged into main (PR #50)" in out.read_text(encoding="utf-8")


def test_q013_refuses_report_without_promoted_line(env):
    root, out, calls, _ = env
    out.parent.mkdir(parents=True)
    out.write_text("# hand-edited report\n", encoding="utf-8")
    assert M.main(["--date", DAY]) != 0
    assert out.read_text(encoding="utf-8") == "# hand-edited report\n" and calls == []


def test_q013_stdout_never_writes(env, capsys):
    root, out, calls, _ = env
    out.parent.mkdir(parents=True)
    out.write_text(OLD, encoding="utf-8")
    assert M.main(["--date", DAY, "--stdout"]) == 0
    assert "# Night shift, rebuilt" in capsys.readouterr().out
    assert out.read_text(encoding="utf-8") == OLD
    other = root / "results/night/morning/2026-11-13.md"
    assert M.main(["--date", "2026-11-13", "--stdout"]) == 0
    assert not other.exists()


def test_q013_new_date_written_as_before(env):
    root, out, calls, _ = env
    assert not out.exists()
    assert M.main(["--date", DAY]) == 0
    assert out.read_text(encoding="utf-8").startswith("# Night shift, rebuilt")
