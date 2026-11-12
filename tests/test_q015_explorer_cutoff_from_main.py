"""Q015: the explorer's data cutoff (explorer.data_end, 2019-12-31) comes from main's protected config/night.yaml
through nightshift.config.load_main(), never from the dev checkout's copy (C.load()). data_end_max can only tighten
it. An unreadable cutoff refuses with exit 2 and logs nothing.

Every config here is a fixture: C.load_main and C.load are monkeypatched, so neither the live config file nor the
real remote is ever read. Writes go to tmp_path or to a captured stub, never to results/exploration/log.csv."""
from __future__ import annotations

import ast
import csv
from datetime import date
from pathlib import Path

import pytest

from nightshift import config as C
from nightshift import logs as LG

LOGS_PY = Path(LG.__file__)
ROW = {"hypothesis_id": "H1", "variant_id": "V1", "description": "d", "data_start": "2005-01-01",
       "data_end": "2019-12-31", "metric": "sharpe", "value": "0.4"}
ARGV = ["variant", "--hypothesis", "H1", "--variant", "V9", "--description", "d", "--data-start", "2005-01-01",
        "--data-end", "2019-06-30", "--metric", "sharpe", "--value", "0.4"]


def _cfg(data_end):
    return {"window": {"start": "22:30"}, "explorer": {"max_hypotheses_per_night": 0, "data_end": data_end}}


@pytest.fixture
def configs(monkeypatch):
    """main at 2019-12-31, the dev checkout's copy loosened to 2021-12-31."""
    monkeypatch.setattr(C, "load_main", lambda *a, **k: _cfg("2019-12-31"))
    monkeypatch.setattr(C, "load", lambda *a, **k: _cfg("2021-12-31"))


@pytest.fixture
def no_writes(monkeypatch):
    """CLI tests: capture appends instead of touching the real exploration log."""
    written = []
    monkeypatch.setattr(LG, "_rows", lambda path: [])
    monkeypatch.setattr(LG, "_append", lambda path, cols, row: written.append(row))
    return written


def _n(p: Path) -> int:
    return len(list(csv.DictReader(p.open()))) if p.exists() else 0


def test_q015_cutoff_comes_from_main_not_dev(tmp_path, configs):
    p = tmp_path / "log.csv"
    with pytest.raises(ValueError, match="2020"):
        LG.log_variant({**ROW, "variant_id": "V2", "data_end": "2020-01-02"}, p)
    assert _n(p) == 0
    LG.log_variant(dict(ROW), p)        # exactly at main's cutoff: accepted
    assert _n(p) == 1


def test_q015_cutoff_accepts_yaml_date(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "load_main", lambda *a, **k: _cfg(date(2019, 12, 31)))   # unquoted YAML date
    p = tmp_path / "log.csv"
    with pytest.raises(ValueError, match="2020"):
        LG.log_variant({**ROW, "data_end": "2020-01-02"}, p)
    LG.log_variant(dict(ROW), p)
    assert _n(p) == 1


def test_q015_data_end_max_only_tightens(tmp_path, configs):
    p = tmp_path / "log.csv"
    # a later data_end_max never loosens main's cutoff
    with pytest.raises(ValueError, match="2020"):
        LG.log_variant({**ROW, "data_end": "2020-01-02"}, p, data_end_max="2021-12-31")
    # an earlier data_end_max tightens it
    with pytest.raises(ValueError, match="after 2018-12-31"):
        LG.log_variant({**ROW, "data_end": "2019-06-30"}, p, data_end_max="2018-12-31")
    assert _n(p) == 0
    LG.log_variant({**ROW, "data_end": "2018-12-31"}, p, data_end_max="2018-12-31")
    assert _n(p) == 1


class Boom(Exception):
    pass


def _raise(exc):
    def f(*a, **k):
        raise exc
    return f


UNREADABLE = {
    "main_config_error": _raise(C.MainConfigError("git fetch origin main failed: fixture")),
    "other_exception": _raise(Boom("anything else")),
    "missing_explorer": lambda *a, **k: {"window": {"start": "22:30"}},
    "missing_data_end": lambda *a, **k: {"window": {"start": "22:30"}, "explorer": {"max_hypotheses_per_night": 0}},
    "null_data_end": lambda *a, **k: _cfg(None),
    "garbage_data_end": lambda *a, **k: _cfg("not a date"),
}


@pytest.mark.parametrize("case", sorted(UNREADABLE))
def test_q015_unreadable_cutoff_logs_nothing(tmp_path, monkeypatch, case):
    monkeypatch.setattr(C, "load_main", UNREADABLE[case])
    monkeypatch.setattr(C, "load", lambda *a, **k: _cfg("2019-12-31"))   # a readable dev copy is never a fallback
    p = tmp_path / "log.csv"
    with pytest.raises(LG.CutoffUnreadable):
        LG.log_variant(dict(ROW), p)
    with pytest.raises(LG.CutoffUnreadable):
        LG.log_variant(dict(ROW), p, data_end_max="2019-12-31")   # nor is data_end_max
    assert not p.exists()


@pytest.mark.parametrize("case", sorted(UNREADABLE))
def test_q015_cli_exit_2_when_cutoff_unreadable(monkeypatch, capsys, no_writes, case):
    monkeypatch.setattr(C, "load_main", UNREADABLE[case])
    monkeypatch.setattr(C, "load", lambda *a, **k: _cfg("2019-12-31"))
    rc = LG.main(ARGV)
    out = capsys.readouterr()
    assert rc == 2
    assert "refused: cutoff unreadable" in out.out
    assert "Traceback" not in out.out + out.err
    assert no_writes == []


def test_q015_cli_exit_1_over_cutoff_exit_0_within(capsys, configs, no_writes):
    argv = list(ARGV)
    argv[argv.index("--data-end") + 1] = "2020-01-02"
    assert LG.main(argv) == 1
    assert "refused:" in capsys.readouterr().out
    assert no_writes == []
    assert LG.main(ARGV) == 0
    assert len(no_writes) == 1 and no_writes[0]["variant_id"] == "V9"


def test_q015_logs_py_never_calls_config_load():
    """AST, not text: no C.load / config.load attribute in any form, no `from .config import load`, no
    getattr(..., "load")."""
    tree = ast.parse(LOGS_PY.read_text(encoding="utf-8"))
    bad = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "load":
            bad.append(f"line {node.lineno}: .load attribute")
        if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[-1] == "config":
            bad += [f"line {node.lineno}: imports {a.name}" for a in node.names if a.name in ("load", "*")]
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "getattr":
            if any(isinstance(x, ast.Constant) and x.value == "load" for x in node.args):
                bad.append(f"line {node.lineno}: getattr(..., 'load')")
    assert bad == [], bad
    # and it does read main's copy
    assert any(isinstance(n, ast.Attribute) and n.attr == "load_main" for n in ast.walk(tree))
