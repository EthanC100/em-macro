"""Q012: the morning report's Usage line reads the run cap and safe mode through C.load_main, never the dev copy.

On 11 Nov the report said "0 of 12 runs" with no "(SAFE MODE)": build() read config/night.yaml from the dev
checkout (C.load), which had not yet merged Ethan's safe-mode switch on main (cap 4). The line now comes from a small
pure helper, usage_line, that reads main's config through C.load_main (the guard's loader) and says so: it is main's
config when the report is written, not a cap recorded at each acquire. When load_main raises, the line says the cap
is unknown and never falls back to the dev copy.

Fixture configs only: C.load and C.load_main are both monkeypatched (never the live config/night.yaml, never the real
remote), and build() is never called.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from nightshift import config as C
from nightshift import morning as M

MORNING_SRC = Path(M.__file__).read_text(encoding="utf-8")
WINDOW = {"start": "22:30", "chain_stop": "05:00", "promote": "05:30", "promote_latest": "07:30"}
MAIN_SAFE = {"run_cap": 12, "safe_mode": {"enabled": True, "run_cap": 4}, "window": WINDOW}
MAIN_OFF = {"run_cap": 12, "safe_mode": {"enabled": False, "run_cap": 4}, "window": WINDOW}
DEV_OFF = {"run_cap": 12, "safe_mode": {"enabled": False, "run_cap": 4}, "window": WINDOW}
DEV_SAFE = {"run_cap": 7, "safe_mode": {"enabled": True, "run_cap": 2}, "window": WINDOW}


def _stub(monkeypatch, main, dev):
    calls = {"load": 0, "load_main": 0}

    def load(*a, **k):
        calls["load"] += 1
        return dev

    def load_main(*a, **k):
        calls["load_main"] += 1
        if isinstance(main, BaseException):
            raise main
        return main
    monkeypatch.setattr(C, "load", load)
    monkeypatch.setattr(C, "load_main", load_main)
    return calls


def test_q012_usage_line_reads_main_safe_mode_not_dev(monkeypatch):
    """Main has safe mode on (cap 4), the dev copy has it off (cap 12): the line shows main's, and says whose."""
    calls = _stub(monkeypatch, MAIN_SAFE, DEV_OFF)
    line = M.usage_line(0)
    assert line == "0 of 4 runs (SAFE MODE, main's config at report time)", line
    assert "of 12 runs" not in line
    assert calls == {"load": 0, "load_main": 1}


def test_q012_usage_line_safe_mode_off_on_main(monkeypatch):
    """Main has safe mode off, the dev copy has it on: no SAFE MODE, main's cap of 12."""
    calls = _stub(monkeypatch, MAIN_OFF, DEV_SAFE)
    line = M.usage_line(3)
    assert line == "3 of 12 runs (main's config at report time)", line
    assert "SAFE MODE" not in line
    assert calls["load"] == 0


@pytest.mark.parametrize("err", [C.MainConfigError("git fetch origin main failed: fixture"),
                                 OSError("fixture"), ValueError("fixture")])
def test_q012_unreadable_main_never_falls_back_to_dev(monkeypatch, err):
    """load_main raises: the cap is unknown, the run count is still shown, and dev's copy is never read."""
    calls = _stub(monkeypatch, err, DEV_OFF)
    line = M.usage_line(2)
    assert line == "2 runs (cap unknown: main's config unreadable)", line
    assert " of " not in line and "SAFE MODE" not in line
    assert calls["load"] == 0


@pytest.mark.parametrize("bad", [None, {"window": WINDOW, "run_cap": "twelve"}])
def test_q012_malformed_main_config_is_unreadable(monkeypatch, bad):
    """A config load_main returns but run_cap cannot read is reported as unreadable, never a crash."""
    calls = _stub(monkeypatch, bad, DEV_OFF)
    assert M.usage_line(1) == "1 runs (cap unknown: main's config unreadable)"
    assert calls["load"] == 0


def _calls_named(tree: ast.AST, mod: str, attr: str) -> list[int]:
    return [n.lineno for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == attr
            and isinstance(n.func.value, ast.Name) and n.func.value.id == mod]


def test_q012_morning_never_reads_the_dev_config():
    """No C.load call anywhere in nightshift/morning.py (AST, not text), and build() takes the line from usage_line."""
    tree = ast.parse(MORNING_SRC)
    assert _calls_named(tree, "C", "load") == [], "morning.py reads config/night.yaml from the dev checkout"
    build = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "build")
    assert any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "usage_line"
               for n in ast.walk(build)), "build() does not use usage_line"
    helper = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "usage_line")
    assert _calls_named(helper, "C", "load_main"), "usage_line must call C.load_main through the module"
