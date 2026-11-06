"""Everything that needs Claude runs in Claude Code sessions: no Anthropic API call from code or GitHub Actions."""
import json
from pathlib import Path

import pytest

from ledger import letters

ROOT = Path(__file__).resolve().parents[1]


def test_no_workflow_uses_the_api_key_and_no_code_imports_the_sdk():
    for f in (ROOT / ".github/workflows").glob("*.yml"):
        t = f.read_text()
        assert "ANTHROPIC_API_KEY" not in t and "pip install anthropic" not in t and " anthropic " not in t, f.name
    for py in [p for p in list((ROOT / "ledger").glob("*.py")) + list((ROOT / "em_macro").glob("*.py")) + list((ROOT / "scripts").glob("*")) if p.is_file()]:
        t = py.read_text(errors="ignore")
        assert "import anthropic" not in t and "ANTHROPIC_API_KEY" not in t, py.name
    assert not (ROOT / "ledger/llm.py").exists() and not (ROOT / "ledger/resolver_api.py").exists()
    for doc in ("docs/janus/quick_check.md", "docs/janus/daily_review.md", "docs/ledger/forecast_resolver.md",
                "docs/letters/monthly_letters.md"):
        assert (ROOT / doc).exists(), doc


FIGS = {"month_change_index_pts": [-0.3061, 99.694], "risk_used_pct": 1.0, "brier": None,
        "open_positions": [{"id": "D001", "live_pnl_pct": -0.306}]}
NARR = {"summary": "The book lost 0.31% in November.", "what_worked": "Nothing closed.",
        "what_did_not": "D001 moved against me by 0.3%.", "risk": "One position, 1.0% at risk."}


def test_letter_narrative_may_only_quote_figures_in_the_data():
    assert letters.check_narrative(NARR, FIGS) == []
    bad = dict(NARR, summary="The book gained 4.2% in November.")
    errs = letters.check_narrative(bad, FIGS)
    assert errs and "4.2%" in errs[0]
    assert any("required" in e for e in letters.check_narrative(dict(NARR, risk=""), FIGS))


def test_letters_are_written_once_and_only_after_the_month_is_booked(tmp_path, monkeypatch):
    monkeypatch.setattr(letters, "REPORTS", tmp_path)
    monkeypatch.setattr(letters, "_context", lambda m: ({"me": FIGS, "algorithm": {}, "janus": {}}, m <= "2026-11"))
    p = letters.write("me", "2026-11", NARR, "claude-opus-5-5")
    text = p.read_text()
    assert p.name == "2026-12-03_letter-me-2026-11.md" and "type: investor letter" in text and '"risk_used_pct": 1.0' in text
    assert "narrative by claude-opus-5-5" in text
    with pytest.raises(ValueError, match="already exists"):
        letters.write("me", "2026-11", NARR, "claude-opus-5-5")
    with pytest.raises(ValueError, match="not booked"):
        letters.write("me", "2026-12", NARR, "claude-opus-5-5")
    with pytest.raises(ValueError, match="model"):
        letters.write("janus", "2026-11", NARR, "")
